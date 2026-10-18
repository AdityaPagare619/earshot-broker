# DESIGN — J6: paired-world + adversarial test suites

Owner: J6 (single-threaded). Type-2 decision (reversible test code), but the
threat-model document is Type-1-adjacent: other seats will build against its
stated boundaries. Reviewed against the six principal skills before code.

## Problem

The dossier (§14.3, §14.4) specifies paired-world invariance tests and an
adversarial suite, but the repo contains only the 24 unit tests. Unit tests
prove the kernel obeys its API; they do not prove the *security properties* —
that a protected difference is unobservable from the public surface, or that
named attackers fail. My suite closes that gap by testing properties, not
examples.

## Decisions

**D1. Test the real kernel through its public API. No mocks, no forks.**
Every test imports `packages/kernel/kernel.py` as-is. If the kernel changes,
my tests re-verify the properties against the new code. A mock would test my
imagination.

**D2. Paired-world harness: `World` builder + `PublicView` observer.**
A `World` fixes the public request, public facts, policy, and permissions, then
varies exactly one protected dimension (title, existence, count, order,
location, error-vs-nomatch). `PublicView.capture()` records everything an
adversary at the public surface can observe: projected text tuple, receipt
public shape (minus the random receipt), key sets, byte length, timing samples,
and any log lines the harness emits. Invariance is asserted over the *view*,
not just the string. (Dossier: "Observe more than the spoken string.")

**D3. Receipts: shape-invariant, value-independent — never byte-identical.**
The dossier is explicit: "Random request references should be independent of
secret data, not identical." So paired tests assert (a) the public shape
`{state, public_message}` is byte-identical across worlds, (b) receipts are
valid `token_urlsafe` of constant length/charset, and (c) receipt *streams*
across worlds are statistically independent (no shared prefix structure, no
length signal). I do NOT assert receipts differ — asserting randomness
properties of a CSPRNG output is theater; I assert the absence of a signal.

**D4. Timing: measure and report, assert only against gross regression.**
The kernel is not constant-time (dossier admits it). My harness collects timing
samples per world into `evidence/j06-timing-report.json` and the test asserts
only that both worlds complete and that median latency ratio stays within an
order of magnitude — a tripwire for accidental algorithmic blowup (e.g. someone
makes projection O(n²)), not a constant-time proof. The residual risk register
names timing as uncovered.

**D5. Adversaries as named personas with explicit capabilities.**
Each adversarial test names the attacker, what they hold (receipt? token?
sensor access?), and what they attempt. E.g. `MomAlone` holds no auth;
`Impersonator` holds the right strings but `authenticated=False`;
`Injector` controls event *text* but not labels; `ReplayAttacker` holds a
stale sensor event; `CrossTenant` holds a valid receipt from tenant B.
This makes coverage reason-about-able: a new attacker is a new persona, not a
new assertion lost in a file.

**D6. Boundary-demonstration tests for what the kernel does NOT enforce.**
F2 (label provenance) and F3 (control-flow taint) cannot be "fixed" by tests —
so I write tests that *demonstrate the boundary* and pass by documenting it:
e.g. a PUB-labeled fact with a secret-bearing key IS released, proving label
assignment is the adapter's trust root. These tests are fenced in
`test_boundaries.py` with docstrings stating the residual risk they pin.

**D7. stdlib only: `unittest`, no new dependencies.**
Matches the kernel's test style, runs with `python3 -m unittest`, ₹0, no
install. Timing statistics use hand-rolled percentiles (no numpy).

**D8. Frozen contract with other seats.**
My tests import only `packages/kernel/kernel.py` public names
(`Kernel, Context, Fact, Label, PUBLIC`). If J3/J2 need fixtures, they live in
`tests/paired_world/worlds.py` as documented builders — reusable, not coupled.
I will not modify `packages/kernel/` (J10/red-team may propose; I only report).

## Rejected alternatives

**R1. pytest + hypothesis.**
Property-based testing would be lovely for the paired worlds (generate random
fact tuples, assert projection invariance). Rejected: pytest isn't installed,
hypothesis adds a dependency and nondeterminism into a security suite where
reproducibility is the point. The monotonicity-style exhaustive lattice walk
(kernel's own test_finite_audience_monotonicity) gives 80% of the value with
stdlib. Revisit if the repo standardizes on pytest.

**R2. String-only paired assertions.**
Comparing only the projected text tuple. Rejected: the dossier explicitly
demands observing keys, status, sizes, timing, metadata, logs. A leak through
`len()` or a status code is still a leak. (This is also why F4 exists.)

**R3. Asserting byte-identical receipts across worlds.**
Tempting ("invariance!"). Rejected: the dossier forbids it — random references
must be *independent* of secret data, not identical. Byte-identical receipts
would actually prove the RNG is broken or mocked.

**R4. A separate mock "adversary simulator" framework.**
Rejected as over-engineering: named persona classes with 3–5 lines each inside
the test modules are clearer than a framework, and every future reader can see
the attack in the test.

## Failure modes of this suite (pre-mortem)

1. **Flaky timing assertions** on a loaded box → mitigated by D4 (order-of-
   magnitude tripwire only; raw samples in evidence for humans).
2. **Tests rot as the kernel evolves** → mitigated by D1 (tests import the real
   kernel; a kernel change that breaks a property fails loudly, which is the
   point).
3. **Boundary tests misread as "passing despite a leak"** → mitigated by D6
   (separate file, docstrings name the residual risk, threat-model cross-refs).
4. **My harness becomes the de-facto spec and diverges from the dossier** →
   mitigated: every test cites the dossier section (§14.3/§14.4/F1–F8).

## Honest boundaries

- These tests prove properties of the *reference kernel*, not production
  security. No sensors, no network, no real auth, no audio.
- Paired-world invariance is tested over a finite, synthetic corpus. Zero
  observed leaks ≠ zero-leak guarantee (dossier §14.2: rule of three).
- Timing analysis is descriptive, not a proof.

## Kill conditions

- If the kernel API changes incompatibly mid-build, I re-pin to the frozen
  names and report — I do not fork the kernel.
- If any paired-world test reveals the kernel *violating* a dossier guarantee
  (not just a boundary), I stop and report to Petu immediately (andon) rather
  than papering over it.
