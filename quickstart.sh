#!/usr/bin/env bash
#
# EARSHOT quickstart — clone → one command → demo + live MCP server, < 2 min.
#
#   ./quickstart.sh [--fresh] [--port 8000]
#
# What it proves (every step asserts real behavior, not just exit codes):
#   1. `pip install -e .` works from a plain clone (stdlib only — no wheels).
#   2. `earshot-demo` runs the 5-beat sealed-speech demo end to end.
#   3. `earshot-server` answers a real MCP 2025-11-25 handshake over HTTP:
#      initialize → 200, notifications/initialized → 202, tools/list → 200.
#
# Fails LOUDLY on the first broken expectation: each `die` names what was
# expected and what was seen. No silent fallbacks, no swallowed errors.
#
# Windows: see quickstart.ps1 (same steps, PowerShell).
#
set -euo pipefail

die() { echo "QUICKSTART FAILED: $*" >&2; exit 1; }
step() { echo "==> $*"; }

PORT="${PORT:-8000}"
FRESH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --fresh) FRESH=1; shift ;;
    --port) PORT="${2:?--port needs a value}"; shift 2 ;;
    --port=*) PORT="${1#--port=}"; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) die "unknown arg: $1 (see --help)" ;;
  esac
done

# --- repo root: this script lives there -------------------------------------
cd "$(dirname "$0")"
ROOT="$PWD"

START=$(date +%s)
VENV="$ROOT/.venv-quickstart"
PY="$VENV/bin/python"

# --- 0. preflight ------------------------------------------------------------
step "[0/7] preflight"
command -v python3 >/dev/null || die "python3 not found on PATH"
command -v curl >/dev/null || die "curl not found on PATH"
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
case "$PYVER" in
  3.10|3.11|3.12|3.13|3.14) ;;
  *) die "Python >= 3.10 required, found $PYVER" ;;
esac
echo "    python3 $PYVER, curl OK"

# --- 1. venv (reused on re-runs unless --fresh) -------------------------------
step "[1/7] virtualenv"
if [ "$FRESH" = 1 ]; then
  rm -rf "$VENV"
fi
if [ -x "$PY" ] && "$PY" -c "import earshot" 2>/dev/null; then
  echo "    reusing $VENV (pass --fresh to rebuild)"
else
  rm -rf "$VENV"
  python3 -m venv "$VENV" || die "venv creation failed"
  echo "    created $VENV"
fi

# --- 2. install ---------------------------------------------------------------
step "[2/7] pip install -e ."
"$PY" -m pip install -q -e "$ROOT" || die "pip install -e . failed"
"$PY" -c "import earshot; print('    earshot', earshot.__version__ if hasattr(earshot,'__version__') else 'importable', 'OK')"

# --- 3. demo ------------------------------------------------------------------
step "[3/7] earshot-demo (5-beat sealed-speech demo)"
DEMO_OUT=$("$VENV/bin/earshot-demo" 2>&1) || die "earshot-demo exited non-zero"
echo "$DEMO_OUT" | grep -q "ALL 5 BEATS PASSED" \
  || die "demo did not report ALL 5 BEATS PASSED. Output was: $DEMO_OUT"
echo "    ALL 5 BEATS PASSED"

# --- 4. server -----------------------------------------------------------------
step "[4/7] earshot-server on port $PORT"
if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/mcp"; then
  die "port $PORT already answers — another server running? stop it first"
fi
SRV_ERR=$(mktemp)
"$VENV/bin/earshot-server" --port "$PORT" 2>"$SRV_ERR" &
SRV_PID=$!
trap 'kill $SRV_PID 2>/dev/null; wait $SRV_PID 2>/dev/null; rm -f "$SRV_ERR"' EXIT
# wait for the socket (≤15s)
for _ in $(seq 1 30); do
  if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$PORT/mcp"; then break; fi
  sleep 0.5
done
curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/mcp" \
  || { echo "--- server stderr ---" >&2; cat "$SRV_ERR" >&2; die "server did not open port $PORT"; }
echo "    server up (pid $SRV_PID)"

# dev bearer <redacted> the server prints at startup (dev-only by design; restart reseeds)
TOKEN=$(grep -o 'token=esh_dev_[^[:space:]]*' "$SRV_ERR" | head -1 | cut -d= -f2)
[ -n "$TOKEN" ] || { cat "$SRV_ERR" >&2; die "no dev token in server stderr"; }
echo "    dev token acquired (not shown)"

# --- 5. MCP initialize ----------------------------------------------------------
step "[5/7] MCP initialize handshake (spec 2025-11-25)"
HDR=$(mktemp); BODY=$(mktemp)
CODE=$(curl -s -D "$HDR" -o "$BODY" -w "%{http_code}" --max-time 10 \
  -X POST "http://127.0.0.1:$PORT/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"quickstart","version":"1"}}}')
[ "$CODE" = "200" ] || { cat "$BODY" >&2; die "initialize: expected HTTP 200, got $CODE"; }
grep -q "2025-11-25" "$BODY" || { cat "$BODY" >&2; die "initialize: protocolVersion 2025-11-25 not in response"; }
SESSION=$(grep -i '^mcp-session-id:' "$HDR" | tr -d '\r' | awk '{print $2}')
[ -n "$SESSION" ] || die "initialize: no Mcp-Session-Id response header"
echo "    200 OK, protocol 2025-11-25, session established"

# --- 6. notifications/initialized + tools/list -----------------------------------
step "[6/7] notifications/initialized + tools/list"
CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
  -X POST "http://127.0.0.1:$PORT/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Mcp-Session-Id: $SESSION" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}')
[ "$CODE" = "202" ] || die "notifications/initialized: expected HTTP 202, got $CODE"
CODE=$(curl -s -o "$BODY" -w "%{http_code}" --max-time 10 \
  -X POST "http://127.0.0.1:$PORT/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Mcp-Session-Id: $SESSION" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')
[ "$CODE" = "200" ] || { cat "$BODY" >&2; die "tools/list: expected HTTP 200, got $CODE"; }
for tool in prepare_day_brief resolve_day_change continue_on_personal_device withdraw_request room keep_secret; do
  grep -q "$tool" "$BODY" || { cat "$BODY" >&2; die "tools/list: missing tool $tool"; }
done
echo "    202 + 200 OK, all 6 tools listed"
rm -f "$HDR" "$BODY"

# --- 7. shutdown -----------------------------------------------------------------
step "[7/7] shutdown"
kill $SRV_PID 2>/dev/null
wait $SRV_PID 2>/dev/null || true
trap - EXIT
rm -f "$SRV_ERR"

END=$(date +%s)
echo ""
echo "======================================================================"
echo "QUICKSTART SUCCESS in $((END - START))s"
echo "  pip install ......... OK (stdlib only)"
echo "  earshot-demo ........ ALL 5 BEATS PASSED"
echo "  earshot-server ...... MCP 2025-11-25 handshake OK, 6 tools live"
echo "======================================================================"
