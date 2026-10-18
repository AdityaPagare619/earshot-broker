# Security Policy

EARSHOT is a research/hackathon project maintained on a best-effort basis.
This policy states plainly what we protect, how to report, and what is
explicitly out of scope — honesty over posture.

## Reporting a vulnerability

**Use [GitHub Security Advisories](https://github.com/AdityaPagare619/earshot-broker/security/advisories/new)
(private report).** Please do not open a public issue for a suspected
vulnerability.

Include:

- What you did (steps to reproduce, minimal if possible)
- What you expected vs. what happened
- Which trust boundary you believe is crossed (see below)
- Your OS and Python version, and whether the simulator or fixture data was involved

We aim to **acknowledge within 7 days** and to keep you updated until the report
is resolved or closed as out of scope. If the report is accepted, we will
credit you in the fix (unless you prefer anonymity) and cut a patch release.

## Scope — what the security claims cover

The guarantees this project makes are stated narrowly in
[docs/threat-model.md](docs/threat-model.md). Anything not listed there as
guaranteed is not guaranteed. In particular, the kernel's privacy properties
hold **only under three stated assumptions**:

1. Label assignment is correct (adapters label private fields correctly);
2. Audience evidence is authentic (sensors report who is in the room truthfully);
3. The `authenticated` flag is bound by a real auth layer (the dev bearer-token
   auth in this repo is a **development stand-in, not production authentication**).

A report demonstrating a privacy violation *within* those assumptions is in
scope and taken seriously. A report demonstrating that one of the assumptions
can be violated is also in scope — it attacks the stated trust boundary — but
the fix may be documentation and hardening guidance rather than a code change,
because some assumptions (e.g. sensor honesty) cannot be fixed in software alone.
Known-unfixable-here risks are tracked openly in
[docs/residual-risks.md](docs/residual-risks.md).

## Out of scope

Please do not report these as vulnerabilities:

- **The simulator** (`apps/simulator/`): it is an explicitly labeled independent
  simulator, not a security boundary. Breaking the demo UI is a bug, not a vuln.
- **Fixture / demo data**: anything under `demo/`, `packs/` fixtures, or the
  trace-harness world pairs is synthetic by design. "I extracted the fixture
  secret" is the harness working as intended — that is what the negative
  controls prove.
- **Dev bearer-token auth**: known development stand-in (see above). A report
  that amounts to "the dev token scheme is not production auth" will be closed
  as known.
- **Dependency vulnerabilities**: the package has **zero dependencies**
  (stdlib only) — there is nothing to audit upstream. CI pins `pytest` for the
  test job only; it is not shipped.
- **Social engineering / physical access**: the threat model covers a casual
  overhearing adversary, not an attacker with the owner's devices or credentials.

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x: (pre-release prototypes, superseded) |

Security fixes go to the latest 1.0.x patch release and are noted in
[CHANGELOG.md](CHANGELOG.md) under a `Security` heading.
