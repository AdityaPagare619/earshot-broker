"""J4 certification harness: a mock MCP facade over the REAL frozen kernel.

This is NOT J3's server. It is a test double that implements the wire-level
contracts C1-C5 from DESIGN.md against the actual kernel, so the failure-path
suite runs green today and becomes an integration gate for J3's server tomorrow.

Public-opacity rule: every denial renders the same public shape for its tool,
regardless of cause. The control plane (AuditSink) records the real reason.
"""
import sys
import os
# The j04 worktree is a full repo checkout: use ITS OWN frozen kernel copy.
_WORKTREE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         '..', '..'))
sys.path.insert(0, os.path.join(_WORKTREE, 'packages', 'kernel'))

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from kernel import PUBLIC, Context, Fact, Kernel, Label  # noqa: E402

GENERIC_MESSAGE = 'Your request is queued.'
CONTINUATION = 'personal_inbox'  # C3: never a bare empty result.

# --- control plane (never crosses to a public surface) -----------------------

@dataclass
class AuditEvent:
    cause: str          # machine reason code, e.g. 'invalid_timezone'
    tool: str           # which tool call was denied
    detail: str = ''    # control-plane-only detail; never rendered publicly


class AuditSink:
    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    def record(self, cause: str, tool: str, detail: str = '') -> None:
        self.events.append(AuditEvent(cause, tool, detail))

    def causes(self, tool: str) -> List[str]:
        return [e.cause for e in self.events if e.tool == tool]


# --- the facade ---------------------------------------------------------------

class CertifiedFacade:
    """Implements contracts C1-C5 over a real Kernel instance."""

    def __init__(self, kernel: Kernel, audit: AuditSink) -> None:
        self.k = kernel
        self.audit = audit
        # receipt -> bookkeeping the public surface may consult
        self._tasks: Dict[str, Dict[str, Any]] = {}
        # (tenant, owner, request_key) -> params fingerprint, for conflict detect
        self._keys: Dict[Tuple[str, str, str], str] = {}

    # -- public response shapes (C1: identical shape per tool, any cause) ------
    def _deny(self, tool: str, cause: str, detail: str = '',
              echo_ref: Optional[str] = None) -> Dict[str, Any]:
        """Opaque public denial. When the caller supplied a request reference,
        it is echoed back verbatim (their own input — harmless) so the denial
        shape is identical to a success shape: no shape oracle."""
        self.audit.record(cause, tool, detail)
        resp: Dict[str, Any] = {'request_state': 'accepted',
                                'public_facts': [],
                                'public_message': GENERIC_MESSAGE,
                                'continuation': CONTINUATION}
        if echo_ref is not None:
            resp['request_ref'] = echo_ref
        return resp

    def _ok(self, receipt: str, public_facts: Tuple[str, ...],
            state: str = 'accepted') -> Dict[str, Any]:
        return {'request_state': state,
                'request_ref': receipt,
                'public_facts': list(public_facts),
                'public_message': GENERIC_MESSAGE,
                'continuation': CONTINUATION}

    # -- tools -----------------------------------------------------------------
    def prepare_day_brief(self, tenant: str, owner: str, day: str,
                          timezone: str, request_key: str,
                          facts: Tuple[Fact, ...], now: float) -> Dict[str, Any]:
        tool = 'prepare_day_brief'
        try:
            date.fromisoformat(day)
        except ValueError:
            return self._deny(tool, 'invalid_date')
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            return self._deny(tool, 'invalid_timezone')
        if not (16 <= len(request_key) <= 128):
            return self._deny(tool, 'bad_request_key')
        fingerprint = f'{day}|{timezone}'
        seen = self._keys.get((tenant, owner, request_key))
        if seen is not None and seen != fingerprint:
            # C2: conflicting reuse rejected with the opaque shape, not an oracle.
            return self._deny(tool, 'conflicting_key_reuse')
        self._keys[(tenant, owner, request_key)] = fingerprint

        receipt = self.k.accept(tenant, owner, request_key, facts, now)['receipt']
        public_facts = Kernel.public_projection(facts)
        self._tasks[receipt] = {'state': 'pending', 'external_effect': False,
                                'tenant': tenant, 'owner': owner}
        return self._ok(receipt, public_facts)

    def resolve_day_change(self, tenant: str, owner: str, request_ref: str,
                           facts: Tuple[Fact, ...], now: float) -> Dict[str, Any]:
        tool = 'resolve_day_change'
        task = self._tasks.get(request_ref)
        if task is None or task['tenant'] != tenant or task['owner'] != owner:
            return self._deny(tool, 'unknown_request_ref', echo_ref=request_ref)
        if task['state'] == 'canceled':
            return self._deny(tool, 'request_canceled', echo_ref=request_ref)
        # The adaptation is computed against private facts, but the public
        # projection may only carry facts whose labels already allow it.
        # (Declassification of derivatives is a typed, reviewed operation;
        #  this facade releases nothing derived from private facts.)
        public_facts = Kernel.public_projection(facts)
        return self._ok(request_ref, public_facts)

    def continue_on_personal_device(self, tenant: str, owner: str,
                                    request_ref: str, now: float) -> Dict[str, Any]:
        tool = 'continue_on_personal_device'
        task = self._tasks.get(request_ref)
        if task is None or task['tenant'] != tenant or task['owner'] != owner:
            # Dossier: acknowledging enqueue is not acknowledging delivery;
            # unknown refs get the same opaque shape (no oracle).
            return self._deny(tool, 'unknown_request_ref', echo_ref=request_ref)
        # Never claim 'delivered' — only that the delivery request was accepted.
        resp = self._ok(request_ref, ())
        resp['public_message'] = 'Delivery request accepted.'
        return resp

    def withdraw_request(self, tenant: str, owner: str,
                         request_ref: str, now: float) -> Dict[str, Any]:
        tool = 'withdraw_request'
        task = self._tasks.get(request_ref)
        if task is None or task['tenant'] != tenant or task['owner'] != owner:
            return self._deny(tool, 'unknown_request_ref', echo_ref=request_ref)
        try:
            self.k.revoke(request_ref, tenant, owner)
        except PermissionError:
            return self._deny(tool, 'revoke_failed', echo_ref=request_ref)
        # C4: cancellation is not undo. In-flight external effects enter
        # reconciliation; the public surface never says 'undone'.
        if task['external_effect']:
            task['state'] = 'reconciling'
            public_state = 'reconciling'
        else:
            task['state'] = 'canceled'
            public_state = 'canceled'
        resp = self._ok(request_ref, (), state=public_state)
        return resp

    # -- test seam: mark a task as having an in-flight external effect ---------
    def _mark_external_effect(self, request_ref: str) -> None:
        self._tasks[request_ref]['external_effect'] = True


# --- shared fixtures ----------------------------------------------------------

def make_fixtures(owner: str = 'owner:priya'):
    private = Fact('appt', 'Prenatal visit at St. Mary clinic 15:40',
                   Label(frozenset({owner}), frozenset({'health'})))
    public = Fact('groceries', 'Collect groceries after 6.',
                  Label(frozenset({PUBLIC}), frozenset()))
    return (private, public)


SECRET_STRINGS = ('Prenatal', 'St. Mary', '15:40', 'clinic', 'owner:priya')

TENANT = 'tenant:demo-house'
OWNER = 'owner:priya'


def make_ctx(audience=frozenset({'owner:priya'}), epoch=1, observed_at=100.0,
             evidence_valid=True, coverage_assumed=True,
             controlled_renderer=True, policy_version=7) -> Context:
    return Context(TENANT, OWNER, audience, epoch, observed_at,
                   evidence_valid, coverage_assumed, controlled_renderer,
                   policy_version)
