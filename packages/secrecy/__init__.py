"""S4 — Household Secrecy Graph & Monotone Gate.

Law 1 (every secret has a non-audience) + Law 6 (the model may make you more
private, never less), executable. Stdlib only.

Public surface:
    edges:        SecrecyEdge (trusted), EdgeProposal (untrusted), Confirmation
    gate:         MonotoneGate — the ONLY SecrecyEdge mint
    store:        EdgeStore — proposals in, gated edges kept; no direct writes
    inference:    Proposer, HeuristicProposer, FixtureLLMProposer, InferenceInput
    declarations: Declaration, DeclarationLog, parse_declaration, classify
    overrides:    effective_clearance — the hot-patch overlay (min-only)
    parse:        parse_keep_secret — one sentence → TIGHTEN proposals
"""
