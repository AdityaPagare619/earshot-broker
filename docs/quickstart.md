# Quickstart — from `git clone` to a real MCP call in ~2 minutes

**You need:** Python 3.10+, `git`, ~2 minutes. No other dependencies —
the package is stdlib-only. Works on Windows, macOS, and Linux.

## 1. Install (60 seconds)

```bash
git clone https://github.com/AdityaPagare619/earshot.git
cd earshot
pip install -e .
```

Verify:

```bash
earshot-demo --help
```

> **Windows (PowerShell):** use `py -m pip install -e .` if `pip` isn't on
> your PATH. `curl.exe` ships with Windows 10+ — the commands below work,
> but replace the `\` line-continuations with a backtick `` ` `` or join each
> command into one line. Everything else is shown in both forms where it
> differs.

## 2. Run the demo (30 seconds)

```bash
earshot-demo --lang en
```

You should see five beats of a sealed day-briefing play out — a private
secret, a room with a changing audience, the spoken answer reshaping while
the phone stays unchanged — ending in:

```
ALL 5 BEATS PASSED  [SIMULATOR] [FIXTURE]
```

Try `--lang hi` for the Hindi/Hinglish pack. The labels are honest: this is
fixture data on an independent simulator, not a live Alexa+ device.

## 3. Talk to the real MCP server (60 seconds)

Start the gateway (Streamable HTTP, MCP spec **2025-11-25** pinned):

```bash
# Terminal 1
earshot-server --port 8000
```

The server prints dev bearer <redacted> at startup (non-production, restart
reseeds). For a reproducible token, pin your own instead:

```bash
# macOS / Linux
EARSHOT_DEV_TOKENS='{"demotoken123": ["house-a", "priya"]}' earshot-server --port 8000
```

```powershell
# Windows PowerShell
$env:EARSHOT_DEV_TOKENS = '{"demotoken123": ["house-a", "priya"]}'
earshot-server --port 8000
```

Then, in a second terminal, speak MCP. Every request needs the bearer <redacted>

```bash
# Terminal 2 — initialize (use your token from the server's startup log)
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer demotoken123" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
       "params":{"protocolVersion":"2025-11-25","capabilities":{},
                 "clientInfo":{"name":"quickstart","version":"1.0"}}}'
```

Copy the `Mcp-Session-Id` from the response headers, then list the tools:

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer demotoken123" \
  -H "Mcp-Session-Id: <paste-session-id>" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

Six tools: `prepare_day_brief`, `resolve_day_change`,
`continue_on_personal_device`, `withdraw_request`, `room`, `keep_secret`.
Call one — identity comes from your token, never from arguments:

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer demotoken123" \
  -H "Mcp-Session-Id: <paste-session-id>" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call",
       "params":{"name":"prepare_day_brief",
                 "arguments":{"request_key":"quickstart-demo-0001",
                              "date":"2026-10-19",
                              "timezone":"Asia/Kolkata"}}}'
```

You'll get a sealed response: a `speak` line safe for the room, marked
`verbatim_no_elaboration`, with the rest held for the owner's phone. That
is the whole product in one call.

## 4. Open the simulator (30 seconds)

```bash
earshot-sim --port 8734
```

Open <http://127.0.0.1:8734/> — an Echo-class web UI driving the same sealed
pipeline. The banner always reads *"Independent simulator — not a live
Alexa+ device"*. Try the audience toggle: the spoken answer reshapes, the
phone doesn't.

## 5. Run the tests (optional, ~30 seconds)

```bash
pip install -e ".[test]"
python -m pytest
```

640 tests, one invocation, zero environment variables. See
[`../evidence/`](../evidence/) for what the numbers mean.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `earshot-demo: command not found` | install step missed, or shell PATH stale | re-run `pip install -e .`; open a new terminal |
| `OSError: [Errno 98] Address already in use` | another server on that port (or a second checkout's test run) | `earshot-server --port 8001` — any free port works |
| `401` / `{"error": "unknown or revoked token"}` | missing or wrong bearer token | copy the token from the server's startup log, or pin one via `EARSHOT_DEV_TOKENS` |
| `400` after `initialize` | session header missing | pass `Mcp-Session-Id` (from initialize's response headers) and `MCP-Protocol-Version: 2025-11-25` on every later request |
| `UnicodeEncodeError` on Windows | legacy console encoding | fixed in-app; if you still see it, `set PYTHONUTF8=1` (cmd) or `$env:PYTHONUTF8 = "1"` (PowerShell) |
| `python` / `pip` not found (Windows) | Python installed without PATH | use `py -m pip` / `py -m pytest` — the `py` launcher always works |

**Python version:** 3.10+ required (`requires-python = ">=3.10"` in
`pyproject.toml`). Check with `python3 --version` / `py --version`.

**What this is not:** the demo and simulator use fixture data and a labeled
independent simulator. There is no live Alexa+ device here — the
competition's Alexa+ builder tooling is partner-gated, and we don't pretend
otherwise. See [honesty.md](honesty.md) before citing any number.
