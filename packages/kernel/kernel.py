"""EARSHOT architectural reference, NOT production security software.

Exercises finite, explicitly labeled data, sealed continuation ownership,
version-bound disclosure leases, and request-stable public acknowledgements.
No real sensors, OAuth, encryption, calendar API, AI, or audio implementation.
"""
from dataclasses import dataclass, replace
from typing import FrozenSet, Optional
import secrets
import threading

PUBLIC = '*'

@dataclass(frozen=True)
class Label:
    readers: FrozenSet[str]
    topics: FrozenSet[str] = frozenset()

    def allows(self, audience: FrozenSet[str]) -> bool:
        return PUBLIC in self.readers or audience.issubset(self.readers)

    def join(self, other: 'Label') -> 'Label':
        readers = (other.readers if PUBLIC in self.readers else
                   self.readers if PUBLIC in other.readers else
                   self.readers & other.readers)
        return Label(readers, self.topics | other.topics)

@dataclass(frozen=True)
class Fact:
    key: str
    value: str
    label: Label

@dataclass(frozen=True)
class Context:
    tenant: str
    principal: str
    audience: FrozenSet[str]
    epoch: int
    observed_at: float
    evidence_valid: bool
    # A declared test assumption, not something a camera can prove.
    coverage_assumed: bool
    controlled_renderer: bool
    policy_version: int

    def effective_audience(self, now: float, ttl: float = 1.0) -> FrozenSet[str]:
        if (not self.evidence_valid or not self.coverage_assumed or
            now < self.observed_at or now - self.observed_at > ttl):
            return self.audience | frozenset({'UNKNOWN'})
        return self.audience

@dataclass(frozen=True)
class Lease:
    tenant: str
    principal: str
    audience: FrozenSet[str]
    epoch: int
    policy_version: int
    expires_at: float
    fact: Fact

class Kernel:
    def __init__(self):
        self._capsules = {}
        self._requests = {}
        self._lock = threading.Lock()

    @staticmethod
    def public_projection(facts: tuple[Fact, ...]) -> tuple[str, ...]:
        # In persistent/uncontrolled hosts only permanently public facts cross.
        return tuple(f.value for f in facts if PUBLIC in f.label.readers)

    @staticmethod
    def room_projection(facts: tuple[Fact, ...], ctx: Context, now: float):
        if not ctx.controlled_renderer:
            return Kernel.public_projection(facts)
        audience = ctx.effective_audience(now)
        return tuple(f.value for f in facts if f.label.allows(audience))

    @staticmethod
    def derive(key: str, value: str, dependencies: tuple[Fact, ...]) -> Fact:
        if not dependencies:
            raise ValueError('Explicit dependencies required')
        label = dependencies[0].label
        for fact in dependencies[1:]:
            label = label.join(fact.label)
        return Fact(key, value, label)

    @staticmethod
    def prepare(fact: Fact, ctx: Context, now: float) -> Optional[Lease]:
        if not ctx.controlled_renderer:
            return None
        audience = ctx.effective_audience(now)
        if not fact.label.allows(audience):
            return None
        return Lease(ctx.tenant, ctx.principal, audience, ctx.epoch,
                     ctx.policy_version, now + 0.25, fact)

    @staticmethod
    def redeem(lease: Lease, ctx: Context, now: float) -> Optional[str]:
        # Illustrates commit-time check; a distributed renderer needs atomic
        # ordering with invalidation, plus local checks for each audio chunk.
        if (not ctx.controlled_renderer or now >= lease.expires_at or
            (lease.tenant, lease.principal, lease.epoch, lease.policy_version) !=
            (ctx.tenant, ctx.principal, ctx.epoch, ctx.policy_version) or
            ctx.effective_audience(now) != lease.audience or
            not lease.fact.label.allows(ctx.effective_audience(now))):
            return None
        return lease.fact.value

    def accept(self, tenant: str, owner: str, request_key: str,
               facts: tuple[Fact, ...], now: float) -> dict:
        """Stable public shape; private contents cannot select the receipt text.

        A receipt is created for EVERY invocation, including empty results.
        Production must authenticate these arguments outside model control.
        """
        key = (tenant, owner, request_key)
        with self._lock:
            if key not in self._requests:
                receipt = secrets.token_urlsafe(24)
                self._requests[key] = receipt
                self._capsules[receipt] = {
                    'tenant': tenant, 'owner': owner, 'facts': facts,
                    'expires': now + 300, 'revoked': False,
                }
            receipt = self._requests[key]
        return {'receipt': receipt, 'state': 'accepted',
                'public_message': 'Your request is queued.'}

    def open_private(self, receipt: str, tenant: str, principal: str,
                     authenticated: bool, now: float) -> tuple[Fact, ...]:
        with self._lock:
            c = self._capsules.get(receipt)
            if (not c or not authenticated or c['tenant'] != tenant or
                c['owner'] != principal or c['revoked'] or now >= c['expires']):
                # Externally one generic error, not an existence oracle.
                raise PermissionError('Unavailable')
            return c['facts']

    def revoke(self, receipt: str, tenant: str, principal: str):
        with self._lock:
            c = self._capsules.get(receipt)
            if not c or c['tenant'] != tenant or c['owner'] != principal:
                raise PermissionError('Unavailable')
            c['revoked'] = True
