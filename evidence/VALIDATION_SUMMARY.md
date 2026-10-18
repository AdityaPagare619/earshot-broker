# Validation summary — 18 October 2026

## Actual checks

- Python reference kernel: 24 unit tests passed (`kernel-tests.txt`).
- Synthetic scenario trace: persistent-host public projection unchanged by audience, controlled pending lease revoked, owner retrieval succeeds, other-person retrieval denied (`synthetic-scenario-trace.json`).
- Real Streamable HTTP MCP server: Inspector tools/list and tools/call succeeded (`inspector-node22-*.json`).
- Direct initialize: negotiated 2025-11-25; initialized notification returned HTTP 202 (`protocol-handshake.json`).
- Four proposed tool schemas parse as JSON, with extra input properties forbidden. This is schema validation, not runtime implementation.
- HTML: no missing internal anchor targets, no externally loaded scripts/styles/images.
- PDF: 57 pages; text presence checked and sample layouts visually inspected; no blank pages in final render.

## Limits

No performance, sensor, audio, real-device, AI-model, OAuth or cloud-provider integration benchmark was performed. No production security or full MCP conformance assertion is made. The synthetic kernel contains no cryptography or real identity verification.

## Tooling friction

The initial Inspector 2.5.0 npm install failed with an npm dependency-tree error. An additional npx attempt using a locally installed Node runtime failed on npm prefix resolution. An older Inspector launcher 0.21.0 resolved subpackages 0.21.2 and successfully exercised the server; it was rerun directly under Node 22.20.0. Exact component versions are recorded separately. This deprecated line is not a recommendation for production use.
