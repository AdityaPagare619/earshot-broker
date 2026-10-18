# SEAT VERDICT — S6: Household Pack & Integration

**Lens:** "Does the kernel really never fork, and does the story actually run
end-to-end?" I am the last seat. My job is to prove the two claims the whole
architecture rests on — (1) customization is data, never code, and (2) S1→S2→S3→S4
is one runnable path, not four documents stapled together. If either claim is
theater, the architecture is a pitch.

## What's strong (keep)

1. **The frozen contracts are genuinely sufficient.** The five dataclasses
   (Item, SecrecyEdge, GeneralizationChain, TableRow, BeliefState) plus the three
   seam contracts are a complete interface for my work. I can build the pack and
   the integration without reading a line of sibling-seat code. That's the point
   of contracts — and it holds.
2. **The pack/data split is the right Type-1 decision.** IAM's lesson (engine
   universal, policy as data) is correctly applied: taxonomy, lexicons, role
   defaults, templates are all data-shaped problems. Nothing in the pack needs
   Turing-completeness.
3. **The 5-beat demo is the right integration test.** Beat 4 ("can you tell?")
   is a *computable* claim: two briefings, different hidden content, structurally
   identical shape. If my demo can't assert that in code, it's theater.

## What breaks (brutal, specific)

1. **"Packs are data" is one Python import away from being a lie.** The easiest
   way to build packs is Python dicts in `.py` files — which makes them code with
   a data costume. A household in Nairobi editing a `.py` file is not
   "customizing from data." If the pack format is executable, the kernel/data
   split is fiction. **Fix: packs are inert text (YAML-subset), parsed by a dumb
   parser, schema-validated. No imports. No evaluation. Ever.**
2. **The language-blind claim is unproven until Hindi actually runs.** It's easy
   to claim the hot path "operates on integers" while the demo quietly branches
   on `lang == "hi"` somewhere. The Hindi pack must exercise a genuinely different
   script (Devanagari) *and* romanized Hinglish, and the pipeline code path must
   be provably identical across languages. **Fix: a test that runs the same beat
   under en and hi packs and asserts identical depth decisions with different
   strings — plus a source-level assertion that hot-path modules contain no
   language-conditional logic.**
3. **Sibling seats haven't landed — my integration could become a second
   implementation competing with theirs.** If I build a "real" slow lane / hot
   lane, S1/S2's arrival creates two competing implementations and a merge war.
   **Fix: my stage implementations are explicitly FIXTURES — thin, deterministic,
   contract-faithful, labeled `fixture` in every module docstring — with a
   documented port interface (`ports.py`) so real seat modules drop in. I implement
   the minimum that makes the story run; I do not compete on depth.**
4. **The demo is the highest theater risk in the wave.** A scripted demo that
   prints canned strings proves nothing. **Fix: the demo runner computes every
   beat through the pipeline fixtures and asserts beat properties in code
   (beat-4 shape equality is a test, not a narration). Narration is honest labels
   + computed values, never pre-written outcomes.**
5. **Scope creep into S3/S4's lane.** The `room`/`keep_secret` tools belong to S4;
   the simulator wiring belongs to S3. If I extend the MCP server or the
   simulator, I create merge conflicts and own code outside my mandate.
   **Fix: I do not touch `services/gateway/mcp/` or `apps/simulator/`. My
   integration demonstrates tool *semantics* at the contract level; S3/S4 wire
   the real thing. Disagree-and-commit, staying in lane.**

## Residual risks I'm accepting

- My fixtures are behavioral sketches, not the real seats' mechanisms. The
  integration proves the *story* runs; S1–S5 prove the *mechanisms* hold. Both
  are needed; neither substitutes for the other.
- The YAML-subset parser is a new (tiny) surface. It's ~80 lines, fully tested,
  and strictly dumber than YAML — that dumbness is the feature.
- Beat 4's existence-AUC chart is S5's measurement; my demo asserts structural
  shape equality, which is the necessary (not sufficient) condition.

## Verdict

**CONDITIONAL PASS on the current state:** the contracts support the work, but
both headline claims (data-not-code, end-to-end story) are currently unproven.
They become proven by what I build now: inert packs + schema gate, a Hindi pack
that runs through identical code, fixtures with documented ports, and a demo
runner whose beats are computed and asserted, not narrated. Confidence 80%.

**Kill conditions for my own seat:** if the Hindi pack requires any code change
outside `packs/hi/`, the language-blind claim dies and I report it as dead; if
any demo beat's key property can't be asserted in code, that beat gets cut, not
faked.
