# EARSHOT examples

Three single-file scripts. Each one **proves** a load-bearing claim — run it,
read the final `OK:` line, and check the assertion behind it in the source.

| File | Claim it proves | Run |
|---|---|---|
| `mcp_tool_call.py` | The MCP server is real: genuine 2025-11-25 handshake + `prepare_day_brief` over HTTP returns a sealed constant-shape response | `python3 examples/mcp_tool_call.py` |
| `sealed_pipeline.py` | One secret through all three seams: quarantined → mom walks in → spoken depth drops, title never in speech, private content routed to the phone | `python3 examples/sealed_pipeline.py` |
| `custom_pack.py` | The household pack is data: one `roles.yaml` value changes what the room hears, zero code touched | `python3 examples/custom_pack.py` |

All stdlib-only, Windows/macOS/Linux-safe. Any assertion failure exits non-zero —
these are executable specifications, not narrations.
