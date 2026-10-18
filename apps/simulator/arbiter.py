"""Local output arbiter for the controlled host (blueprint §6, §11.2).

Implements the precise commit ordering:

    prepare(candidate):   read versions, validate, persist an epoch-bound grant
    commit(grant):        under the serialization lock, re-read epoch / policy /
                         data versions; deny on missing|revoked|expired|mismatch,
                         else append COMMITTED and release one bounded segment
    audience_changed(ev): STOP OUTPUT FIRST, validate the event, then — under
                         the same lock — advance the epoch and invalidate
                         pending grants. Private task state is untouched.

The linearization point orders *observed software events* (blueprint §6): a
person may have entered before the sensor noticed — that residual is stated,
not hidden. Belt-and-suspenders: every segment carries (epoch, seq, digest)
and the renderer must call is_segment_playable() at play time; a late segment
from an older epoch is rejected locally even if it was committed before stop.

Label/audience semantics reuse the reference kernel (packages/kernel) so the
security boundary is exercised against real code, not reimplemented.
"""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any, Optional

UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AudienceEvent:
    """A room-observation event from the (simulated) sensor pipeline."""
    seq: int
    observed_at: float
    received_at: float
    listeners: frozenset
    source: str  # "manual" | "scripted" — always labeled, never a real camera
    zone: str = "living-room"


@dataclass(frozen=True)
class Grant:
    grant_id: str
    task_id: str
    epoch: int
    policy_version: int
    data_version: int
    audience: frozenset
    channel: str
    expires_at: float
    fact_key: str
    revoked: bool = False


@dataclass(frozen=True)
class Segment:
    epoch: int
    seq: int
    digest: str
    text: str
    grant_id: str


@dataclass
class ArbiterEvent:
    kind: str
    at: float
    detail: dict = field(default_factory=dict)


class Arbiter:
    """Single-room output arbiter. One instance per controlled renderer."""

    EVIDENCE_TTL = 5.0  # seconds; stale evidence -> UNKNOWN (dossier §6.6)

    def __init__(self, kernel, tenant: str, owner: str,
                 policy_version: int = 1, data_version: int = 1,
                 channel: str = "controlled_speaker"):
        self._kernel = kernel
        self._tenant = tenant
        self._owner = owner
        self._policy_version = policy_version
        self._data_version = data_version
        self._channel = channel
        self._lock = threading.Lock()
        self._epoch = 0
        self._listeners: frozenset = frozenset({owner})
        self._observed_at = time.time()
        self._evidence_valid = True
        self._coverage_assumed = True
        self._last_seq = 0
        self._output_stopped = False
        self._grants: dict[str, Grant] = {}
        self._fact_cache: dict[str, Any] = {}
        self._grant_seq = 0
        self._segment_seq = 0
        self._log: list[ArbiterEvent] = []
        # Private task state survives audience changes (dossier §4.3).
        self._task_state: dict[str, Any] = {}

    # ---- introspection -------------------------------------------------

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def output_stopped(self) -> bool:
        return self._output_stopped

    def event_log(self) -> list[ArbiterEvent]:
        with self._lock:
            return list(self._log)

    def _record(self, kind: str, **detail):
        self._log.append(ArbiterEvent(kind, time.time(), detail))

    # ---- audience ------------------------------------------------------

    def _effective_audience(self, now: float) -> frozenset:
        if (not self._evidence_valid or not self._coverage_assumed
                or now < self._observed_at
                or now - self._observed_at > self.EVIDENCE_TTL):
            return self._listeners | frozenset({UNKNOWN})
        return self._listeners

    def _kernel_context(self, now: float):
        from earshot.kernel import Context
        # Single source of truth for audience semantics: the arbiter computes
        # the effective audience ONCE (freshness TTL, UNKNOWN on stale). The
        # Context is then built so the kernel's own effective_audience()
        # agrees with it (observed_at=now, valid flags), instead of
        # re-deriving with its own 1s TTL and disagreeing with commit().
        # The kernel still enforces label.allows() and lease epoch/policy
        # binding — its real job.
        aud = self._effective_audience(now)
        return Context(
            tenant=self._tenant, principal=self._owner,
            audience=aud, epoch=self._epoch,
            observed_at=now,
            evidence_valid=True,
            coverage_assumed=True,
            controlled_renderer=True,
            policy_version=self._policy_version,
        )

    def audience_changed(self, event: AudienceEvent) -> dict:
        """Interrupt path. Stop output FIRST, then serialize version changes."""
        # 1. Stop local output before anything else (blueprint §11.2).
        #    No awaits, no model, no network on this path.
        self._output_stopped = True
        now = time.time()
        with self._lock:
            # 2. Validate the event: sequence must advance, timestamps sane.
            if event.seq <= self._last_seq:
                self._record("EVENT_REJECTED_SEQ",
                             seq=event.seq, last=self._last_seq)
                return {"accepted": False, "reason": "stale_sequence"}
            if event.received_at < event.observed_at or event.observed_at > now + 1:
                self._record("EVENT_REJECTED_TIME", seq=event.seq)
                return {"accepted": False, "reason": "bad_timestamp"}
            # 3. Serialize with the commit boundary: advance epoch, invalidate.
            self._last_seq = event.seq
            self._epoch += 1
            self._listeners = frozenset(event.listeners)
            self._observed_at = event.observed_at
            self._evidence_valid = True
            invalidated = 0
            for gid, g in self._grants.items():
                if not g.revoked and g.epoch < self._epoch:
                    self._grants[gid] = replace(g, revoked=True)
                    invalidated += 1
            self._record("AUDIENCE_CHANGED", epoch=self._epoch,
                         listeners=sorted(self._listeners),
                         invalidated=invalidated, source=event.source)
            # 4. Private task state is kept intact (dossier §4.3).
            return {"accepted": True, "epoch": self._epoch,
                    "invalidated": invalidated}

    def sensor_heartbeat_lost(self) -> None:
        """Heartbeat stops -> evidence invalid -> UNKNOWN -> restricted output."""
        with self._lock:
            self._evidence_valid = False
            self._output_stopped = True
            self._record("HEARTBEAT_LOST", epoch=self._epoch)

    def resume_after_retrust(self, listeners: frozenset) -> dict:
        """No automatic sensitive replay (blueprint §9: no autoplay_after_retrust).
        Returns the arbiter to service for NEW grants only."""
        with self._lock:
            self._epoch += 1
            self._listeners = frozenset(listeners)
            self._observed_at = time.time()
            self._evidence_valid = True
            self._output_stopped = False
            self._record("RETRUSTED", epoch=self._epoch,
                         listeners=sorted(self._listeners))
            return {"epoch": self._epoch}

    # ---- prepare / commit ----------------------------------------------

    def prepare(self, task_id: str, fact, now: Optional[float] = None) -> Optional[Grant]:
        """Mint an epoch-bound grant for one releasable fact (one segment)."""
        now = time.time() if now is None else now
        with self._lock:
            if self._output_stopped:
                self._record("PREPARE_DENIED_STOPPED", task_id=task_id)
                return None
            ctx = self._kernel_context(now)
            audience = ctx.effective_audience(now)
            if not fact.label.allows(audience):
                self._record("PREPARE_DENIED_LABEL", task_id=task_id,
                             fact=fact.key)
                return None
            lease = self._kernel.prepare(fact, ctx, now)
            if lease is None:
                self._record("PREPARE_DENIED_KERNEL", task_id=task_id)
                return None
            self._grant_seq += 1
            grant = Grant(
                grant_id=f"g{self._grant_seq}", task_id=task_id,
                epoch=self._epoch, policy_version=self._policy_version,
                data_version=self._data_version, audience=audience,
                channel=self._channel, expires_at=now + 0.25,
                fact_key=fact.key)
            self._grants[grant.grant_id] = grant
            self._fact_cache[grant.grant_id] = fact
            self._record("PREPARED", grant=grant.grant_id, task_id=task_id,
                         epoch=self._epoch)
            return grant

    def commit(self, grant: Grant, now: Optional[float] = None) -> Optional[Segment]:
        """Release one bounded segment, or deny. Serialized vs invalidation."""
        now = time.time() if now is None else now
        with self._lock:
            live = self._grants.get(grant.grant_id)
            if live is None or live.revoked or live != grant:
                self._record("COMMIT_DENIED", grant=grant.grant_id,
                             reason="missing_or_revoked")
                return None
            if self._output_stopped or now >= grant.expires_at:
                self._record("COMMIT_DENIED", grant=grant.grant_id,
                             reason="stopped_or_expired")
                return None
            # Re-read versions at commit (blueprint §6): epoch, policy, data.
            if (grant.epoch != self._epoch
                    or grant.policy_version != self._policy_version
                    or grant.data_version != self._data_version):
                self._record("COMMIT_DENIED", grant=grant.grant_id,
                             reason="version_mismatch")
                return None
            fact = self._fact_cache.get(grant.grant_id)
            if fact is None:
                self._record("COMMIT_DENIED", grant=grant.grant_id,
                             reason="fact_gone")
                return None
            audience = self._effective_audience(now)
            if audience != grant.audience or not fact.label.allows(audience):
                self._record("COMMIT_DENIED", grant=grant.grant_id,
                             reason="audience_changed")
                return None
            self._segment_seq += 1
            digest = hashlib.sha256(
                f"{grant.grant_id}:{self._segment_seq}:{fact.value}".encode()
            ).hexdigest()[:16]
            seg = Segment(epoch=self._epoch, seq=self._segment_seq,
                          digest=digest, text=fact.value,
                          grant_id=grant.grant_id)
            # Single-use grant: a grant releases exactly one bounded segment.
            self._grants[grant.grant_id] = replace(grant, revoked=True)
            self._record("COMMITTED", grant=grant.grant_id,
                         segment=seg.seq, epoch=seg.epoch)
            return seg

    def is_segment_playable(self, segment: Segment) -> bool:
        """Renderer-side gate: reject late/older-epoch segments locally."""
        with self._lock:
            ok = (not self._output_stopped
                  and segment.epoch == self._epoch)
            if not ok:
                self._record("SEGMENT_REJECTED", segment=segment.seq,
                             seg_epoch=segment.epoch, epoch=self._epoch)
            return ok

    # ---- task state (private, survives audience change) ------------------

    def put_task_state(self, task_id: str, state: Any) -> None:
        with self._lock:
            self._task_state[task_id] = state

    def get_task_state(self, task_id: str) -> Any:
        with self._lock:
            return self._task_state.get(task_id)

    # ---- policy/data version bumps (invalidate future releases) ---------

    def bump_policy(self, new_version: int) -> None:
        with self._lock:
            self._policy_version = new_version
            for gid, g in self._grants.items():
                if not g.revoked:
                    self._grants[gid] = replace(g, revoked=True)
            self._record("POLICY_BUMPED", version=new_version)
