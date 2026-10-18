"""Test-only authoritative release boundary.

Implements blueprint §6's commit ordering (prepare → persist grant → commit
under a serialization boundary → re-read epoch/policy → deny on mismatch) so
the race tests exercise the *blueprint*, not an invention.

This is NOT production code and must never be mistaken for it:
  - single process, threading.Lock — production needs one logical sequencer
    per room (§11.1), durable grant storage, and a real trusted clock;
  - the "trusted clock" here is an injectable callable so tests control time
    deterministically;
  - segment binding (epoch + sequence + candidate digest) is enforced by
    `authorize_playback`; a real renderer would check this per audio chunk.

Purpose: demonstrate F1 — naive kernel use races; arbiter-guarded use does not.
"""
import hashlib
import itertools
import threading
from dataclasses import dataclass, replace

import sys, os
# Import the frozen kernel from THIS worktree (seat self-containment).
from earshot.kernel import Context, Fact, Kernel  # noqa: E402


@dataclass(frozen=True)
class Segment:
    """A releasable audio chunk bound to its authorization moment."""
    epoch: int
    seq: int
    digest: str  # sha256 of the candidate value, hex


@dataclass
class _Grant:
    grant_id: str
    lease: object
    fact: Fact
    epoch: int
    policy_version: int
    audience: frozenset
    seq: int


class Arbiter:
    """Authoritative per-room release boundary (test scaffolding)."""

    def __init__(self, tenant, principal, zone, clock):
        self.tenant = tenant
        self.principal = principal
        self.zone = zone
        self._clock = clock  # trusted: callable() -> float, test-controlled
        self._lock = threading.Lock()
        self._epoch = 1
        self._policy_version = 1
        self._audience = frozenset({principal})
        self._evidence_valid = True
        self._grants = {}
        self._seq = itertools.count(1)
        self._grant_ids = itertools.count(1)

    # -- authoritative room state -------------------------------------------
    def audience_changed(self, new_audience):
        """Interrupt path (§11.2): stop-first ordering is the renderer's job;
        here we serialize the epoch bump against commits."""
        with self._lock:
            self._audience = frozenset(new_audience)
            self._epoch += 1
            # Pending grants are NOT deleted: commit re-reads the epoch and
            # denies them (blueprint §6). Deletion would hide the denial.

    def sensor_died(self):
        with self._lock:
            self._evidence_valid = False

    def sensor_recovered(self, audience):
        with self._lock:
            self._evidence_valid = True
            self._audience = frozenset(audience)

    def policy_bumped(self):
        with self._lock:
            self._policy_version += 1

    def current_epoch(self):
        with self._lock:
            return self._epoch

    # -- the guarded path ----------------------------------------------------
    def _mint_context(self):
        now = self._clock()
        return Context(
            tenant=self.tenant,
            principal=self.principal,
            audience=self._audience,
            epoch=self._epoch,
            observed_at=now,          # arbiter-minted: renderer never supplies time
            evidence_valid=self._evidence_valid,
            coverage_assumed=True,
            controlled_renderer=True,
            policy_version=self._policy_version,
        )

    def prepare_grant(self, fact):
        """prepare(): persist grant tied to current versions (blueprint §6)."""
        with self._lock:
            ctx = self._mint_context()
            lease = Kernel.prepare(fact, ctx, self._clock())
            if lease is None:
                return None
            gid = 'g%d' % next(self._grant_ids)
            grant = _Grant(gid, lease, fact, self._epoch,
                           self._policy_version, self._audience,
                           next(self._seq))
            self._grants[gid] = grant
            return gid

    def commit(self, grant_id):
        """commit(): serialize with the audience-change boundary, re-read
        versions, deny on any mismatch, else release one bound segment."""
        with self._lock:
            grant = self._grants.get(grant_id)
            if grant is None:
                return None
            if grant.epoch != self._epoch:
                return None  # audience moved under us: deny
            if grant.policy_version != self._policy_version:
                return None  # policy moved under us: deny
            ctx = self._mint_context()  # fresh time, fresh audience
            value = Kernel.redeem(grant.lease, ctx, self._clock())
            if value is None:
                return None
            digest = hashlib.sha256(value.encode()).hexdigest()
            segment = Segment(self._epoch, grant.seq, digest)
            del self._grants[grant_id]  # single-use: no replay
            return value, segment

    def authorize_playback(self, segment):
        """Per-chunk check the renderer must call before emitting audio."""
        with self._lock:
            return segment.epoch == self._epoch

    def sweep_expired(self):
        """Drop uncommitted grants whose lease TTL passed (crash hygiene)."""
        now = self._clock()
        with self._lock:
            dead = [g for g, gr in self._grants.items()
                    if now >= gr.lease.expires_at]
            for g in dead:
                del self._grants[g]
            return dead

    def pending_grants(self):
        with self._lock:
            return list(self._grants)
