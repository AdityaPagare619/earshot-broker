"""EARSHOT MCP gateway — Streamable HTTP, MCP spec 2025-11-25 pinned (J3).

Stdlib only, zero dependencies. No MCP SDK is used: the only SDK on this box
negotiates 2026-07-28 exclusively, which would silently violate the pinned
spec (see SEAT_VERDICT.md R1). Every wire behavior here was verified against
the 2025-11-25 transport text, read first-hand:

- single endpoint POST + GET; GET/DELETE -> 405 (no standalone SSE streams,
  no client session termination — both explicitly permitted)
- Accept: application/json + text/event-stream (client MUST; we respond JSON)
- notifications -> 202, empty body
- MCP-Session-Id lifecycle: assign at initialize; 400 if missing afterwards;
  404 if unknown/expired (30 min idle)
- MCP-Protocol-Version header must equal negotiated version, else 400
- Origin validated when present (DNS rebinding), else 403; localhost-only bind
- every request (incl. initialize) requires dev bearer auth -> 401 otherwise

Run:  python3 services/gateway/mcp/server.py --port 8000   (from repo root)
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import secrets
import signal
import socketserver
import sys
import time
import traceback
from earshot.wincompat import ensure_utf8_stdout

from . import auth as auth_mod
from . import broker as broker_mod
from . import fixtures as fixtures_mod

PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "earshot-broker"
SERVER_VERSION = "0.1.0"
MCP_PATH = "/mcp"
MAX_BODY = 1 << 20  # 1 MB
SESSION_TTL = 1800  # 30 min idle
RATE_LIMIT_PER_MIN = 100
ALLOWED_ORIGIN_PREFIXES = ("http://127.0.0.1:", "http://localhost:")

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "..", "..", ".."))
_CONTRACTS_PATH = os.path.join(_REPO_ROOT, "packages", "contracts", "API_CONTRACTS.json")

with open(_CONTRACTS_PATH, encoding="utf-8") as fh:
    _CONTRACTS = json.load(fh)
TOOLS = {t["name"]: t for t in _CONTRACTS["tools"]}
assert _CONTRACTS["protocolVersion"] == PROTOCOL_VERSION, "contracts pin mismatch"


# --------------------------------------------------------------------------
# JSON-Schema subset validator (covers everything API_CONTRACTS.json uses)

def _fail(field: str) -> broker_mod.BrokerError:
    # Field name only — never the value.
    return broker_mod.BrokerError(broker_mod.INVALID_PARAMS, f"invalid params: '{field}'")


def _check_format(value: str, fmt: str, field: str) -> None:
    from datetime import date as _d, datetime as _dt
    try:
        if fmt == "date":
            _d.fromisoformat(value)
        elif fmt == "date-time":
            _dt.fromisoformat(value)
        else:
            raise ValueError(fmt)
    except ValueError:
        raise _fail(field)


def validate_against(value, schema: dict, field: str) -> None:
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            raise _fail(field)
        for req in schema.get("required", []):
            if req not in value:
                raise _fail(f"{field}.{req}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in value:
                if k not in props:
                    raise _fail(f"{field}.{k}")
        for k, subschema in props.items():
            if k in value:
                validate_against(value[k], subschema, f"{field}.{k}")
    elif t == "string":
        if not isinstance(value, str):
            raise _fail(field)
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise _fail(field)
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise _fail(field)
        if "format" in schema:
            _check_format(value, schema["format"], field)
        if "const" in schema and value != schema["const"]:
            raise _fail(field)
        if "enum" in schema and value not in schema["enum"]:
            raise _fail(field)
    elif t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise _fail(field)
        if "minimum" in schema and value < schema["minimum"]:
            raise _fail(field)
        if "maximum" in schema and value > schema["maximum"]:
            raise _fail(field)
        if "enum" in schema and value not in schema["enum"]:
            raise _fail(field)
    elif t == "array":
        if not isinstance(value, list):
            raise _fail(field)
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise _fail(field)
        items = schema.get("items")
        if items:
            for i, item in enumerate(value):
                validate_against(item, items, f"{field}[{i}]")
    elif t == "boolean":
        if not isinstance(value, bool):
            raise _fail(field)
    if "const" in schema and t != "string" and value != schema["const"]:
        raise _fail(field)
    if "enum" in schema and t not in ("string", "integer") and value not in schema["enum"]:
        raise _fail(field)


# --------------------------------------------------------------------------
# JSON-RPC helpers

def rpc_result(req_id, result: dict) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode()


def rpc_error(req_id, code: int, message: str, data=None) -> bytes:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": err}).encode()


# --------------------------------------------------------------------------
# HTTP handler

class MCPHandler(http.server.BaseHTTPRequestHandler):
    server_version = "EarshotBroker/0.1.0"

    # -- small helpers -----------------------------------------------------

    def _send(self, code: int, body: bytes, ctype="application/json", extra=None):
        if getattr(self, "_ctx", None) is not None:
            self._ctx["status"] = code
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _transport_error(self, code: int, message: str):
        # Transport-level failures are plain JSON, not JSON-RPC (no id context).
        self._send(code, json.dumps({"error": message}).encode())

    def log_message(self, fmt, *args):  # quiet; we log structured lines ourselves
        pass

    def _check_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # non-browser clients send none; spec acts only when present
        if origin.startswith(ALLOWED_ORIGIN_PREFIXES):
            return True
        self._transport_error(403, "forbidden Origin")
        return False

    def _check_auth(self):
        header = self.headers.get("Authorization")
        try:
            binding = self.server.auth.resolve(header)
        except auth_mod.AuthError as exc:
            self._transport_error(401, str(exc))
            return None
        # Rate-limit per credential, not per (tenant, owner): two principals
        # sharing a tenant must not share a budget, and a test token must not
        # poison another client's window.
        token = (header or "").partition(" ")[2]
        if not self._check_rate(token):
            return None
        return binding

    def _check_rate(self, token: str) -> bool:
        """Sliding-window rate limit per credential. 429 when exceeded."""
        now = time.monotonic()
        window = self.server.rate_windows.setdefault(token, [])
        while window and now - window[0] > 60:
            window.pop(0)
        if len(window) >= RATE_LIMIT_PER_MIN:
            self._transport_error(429, "rate limited: slow down")
            return False
        window.append(now)
        return True

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return b""
        # Read at most MAX_BODY+1: enough to distinguish "exactly max" from
        # "over" without hanging on a huge Content-Length. Close the
        # connection afterwards so unread bytes can't desync keep-alive.
        data = self.rfile.read(min(length, MAX_BODY + 1))
        if length > MAX_BODY or len(data) > MAX_BODY:
            self.close_connection = True
            self._transport_error(413, "request body too large")
            return None
        return data

    def _check_session(self, session_id: str | None):
        """Returns session dict or sends the spec-mandated HTTP error."""
        if not session_id:
            self._transport_error(400, "missing MCP-Session-Id")
            return None
        sess = self.server.sessions.get(session_id)
        if sess is None or time.time() - sess["last_seen"] > SESSION_TTL:
            self.server.sessions.pop(session_id, None)
            self._transport_error(404, "unknown or expired session")
            return None
        sess["last_seen"] = time.time()
        return sess

    def _check_version_header(self):
        v = self.headers.get("MCP-Protocol-Version")
        if v is not None and v != PROTOCOL_VERSION:
            self._transport_error(400, "unsupported MCP-Protocol-Version")
            return False
        return True

    # -- HTTP verbs ----------------------------------------------------------

    def do_GET(self):
        if self.path != MCP_PATH:
            self._transport_error(404, "not found")
            return
        # No standalone SSE streams offered: 405 is spec-legal.
        self._transport_error(405, "standalone SSE streams not offered")

    def do_DELETE(self):
        if self.path != MCP_PATH:
            self._transport_error(404, "not found")
            return
        # Client-initiated session termination not offered: 405 is spec-legal.
        self._transport_error(405, "client session termination not offered")

    def do_POST(self):
        started = time.perf_counter()
        ctx = {"method": None, "tool": None, "tenant": None, "status": None}
        try:
            self._do_post_inner(started, ctx)
        finally:
            # Structured, redacted access log: never params, never values.
            # EARSHOT_QUIET=1 silences it (test evidence capture).
            if not os.environ.get("EARSHOT_QUIET"):
                sys.stderr.write(
                    f"[{time.strftime('%H:%M:%S')}] POST {ctx['method'] or '-'}"
                    f" tool={ctx['tool'] or '-'} tenant={ctx['tenant'] or '-'}"
                    f" status={ctx['status'] or '-'}"
                    f" {(time.perf_counter() - started) * 1000:.2f}ms\n")
                sys.stderr.flush()

    def _do_post_inner(self, started: float, ctx: dict):
        self._ctx = ctx  # _send records the HTTP status here
        if self.path != MCP_PATH:
            self._transport_error(404, "not found")
            return
        if not self._check_origin():
            return
        binding = self._check_auth()
        if binding is None:
            return
        tenant, owner = binding
        ctx["tenant"] = tenant
        raw = self._read_body()
        if raw is None:
            return
        try:
            msg = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send(200, rpc_error(None, broker_mod.PARSE_ERROR, "Parse error"))
            return
        if not isinstance(msg, dict):
            self._send(200, rpc_error(None, broker_mod.INVALID_REQUEST,
                                     "Invalid Request: batch not supported"))
            return

        method = msg.get("method")
        req_id = msg.get("id")
        is_notification = req_id is None
        ctx["method"] = method if isinstance(method, str) else "-"

        try:
            if method == "initialize":
                self._handle_initialize(msg, req_id)
            else:
                if not self._check_version_header():
                    return
                sess = self._check_session(self.headers.get("Mcp-Session-Id"))
                if sess is None:
                    return
                if method == "notifications/initialized":
                    # Spec: 202 Accepted, no body.
                    self._send(202, b"")
                    return
                if is_notification:
                    self._send(202, b"")
                    return
                if method == "tools/list":
                    self._send(200, rpc_result(req_id, {"tools": list(TOOLS.values())}))
                elif method == "tools/call":
                    ctx["tool"] = (msg.get("params") or {}).get("name")
                    self._handle_call(msg, req_id, tenant, owner, started, sess)
                elif method == "resources/list":
                    self._handle_resources_list(req_id, sess)
                elif method == "resources/read":
                    self._handle_resources_read(msg, req_id, tenant, owner, sess)
                else:
                    self._send(200, rpc_error(req_id, broker_mod.METHOD_NOT_FOUND,
                                             f"Method not found: {method}"))
        except BrokenPipeError:
            pass

    # -- MCP methods -----------------------------------------------------------

    def _handle_initialize(self, msg: dict, req_id):
        params = msg.get("params") or {}
        if not isinstance(params, dict) or not isinstance(params.get("protocolVersion"), str):
            self._send(200, rpc_error(req_id, broker_mod.INVALID_PARAMS,
                                     "invalid params: 'protocolVersion'"))
            return
        # Server's maximum supported version is 2025-11-25; a client asking
        # for newer negotiates down to it (standard version negotiation).
        session_id = "esh_" + secrets.token_urlsafe(24)
        self.server.sessions[session_id] = {"last_seen": time.time()}
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
        self._send(200, rpc_result(req_id, result),
                   extra={"MCP-Session-Id": session_id})

    def _handle_call(self, msg: dict, req_id, tenant: str, owner: str,
                   started: float, sess: dict):
        params = msg.get("params")
        if not isinstance(params, dict):
            self._send(200, rpc_error(req_id, broker_mod.INVALID_PARAMS,
                                     "invalid params: 'params'"))
            return
        name = params.get("name")
        arguments = params.get("arguments", {})
        tool = TOOLS.get(name) if isinstance(name, str) else None
        if tool is None:
            self._send(200, rpc_error(req_id, broker_mod.METHOD_NOT_FOUND,
                                     f"Unknown tool: {name}"))
            return
        try:
            validate_against(arguments, tool["inputSchema"], "arguments")
            handler = getattr(self.server.broker, name)
            result = handler(tenant, owner, arguments)
            validate_against(result, tool["outputSchema"], "result")
        except broker_mod.BrokerError as exc:
            self._send(200, rpc_error(req_id, exc.code, exc.message, exc.data))
            return
        except Exception:  # never leak internals; redacted server-side log
            traceback.print_exc()
            self._send(200, rpc_error(req_id, broker_mod.INTERNAL_ERROR, "Internal error"))
            return
        structured = result
        # S3: the human-readable content block is the speak text VERBATIM —
        # what the room hears is exactly result["speak"], never a summary.
        # structuredContent carries the full sealed-speech contract for
        # machine consumers (policy, followups, screen depth, refs).
        speak_text = structured.get("speak") or json.dumps(structured)
        payload = {
            "content": [{"type": "text", "text": speak_text}],
            "structuredContent": structured,
            "isError": False,
        }
        if name == "prepare_day_brief":
            # The ui:// day card reflects the session's latest accepted brief.
            sess["latest_ref"] = structured["request_ref"]
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.server.latencies.append({"tool": name, "ms": elapsed_ms})
        self._send(200, rpc_result(req_id, payload))

    # -- public-safe resources (no secrets cross, ever) -------------------------

    def _handle_resources_list(self, req_id, sess: dict):
        resources = []
        if sess.get("latest_ref"):
            resources.append({
                "uri": "ui://earshot/day-card",
                "name": "Earshot day card",
                "description": ("Public-safe card for the session's latest accepted "
                                "day brief. Contains only explicitly public facts."),
                "mimeType": "application/json",
            })
        self._send(200, rpc_result(req_id, {"resources": resources}))

    def _handle_resources_read(self, msg: dict, req_id, tenant: str, owner: str,
                               sess: dict):
        params = msg.get("params") or {}
        uri = params.get("uri")
        if uri != "ui://earshot/day-card" or not sess.get("latest_ref"):
            self._send(200, rpc_error(req_id, broker_mod.INVALID_PARAMS,
                                     "invalid params: 'uri'"))
            return
        try:
            card = self.server.broker.day_card(sess["latest_ref"], tenant, owner)
        except broker_mod.BrokerError as exc:
            self._send(200, rpc_error(req_id, exc.code, exc.message, exc.data))
            return
        self._send(200, rpc_result(req_id, {"contents": [{
            "uri": uri, "mimeType": "application/json",
            "text": json.dumps(card)}]}))


class ThreadedMCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run(port: int, host: str = "127.0.0.1", world_factory=None,
        dev_token_json: str | None = None) -> None:
    """Blocking MCP gateway loop (CLI entry; tests construct the server directly)."""
    if dev_token_json is not None:
        # Dev-only token pinning. Uses auth's existing EARSHOT_DEV_TOKENS
        # extension point; auth.py itself is untouched.
        os.environ["EARSHOT_DEV_TOKENS"] = dev_token_json
    server = ThreadedMCPServer((host, port), MCPHandler)
    server.auth = auth_mod.AuthRegistry()
    server.broker = broker_mod.Broker(
        world_factory=world_factory or fixtures_mod.strict_world)
    server.sessions = {}
    server.latencies = []
    server.rate_windows = {}
    sys.stderr.write(
        f"EARSHOT MCP gateway listening on http://{host}:{port}{MCP_PATH} "
        f"protocol={PROTOCOL_VERSION} auth=dev-bearer (dev auth — NOT production)\n")
    sys.stderr.write(server.auth.describe_for_operator() + "\n")
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stderr.write("EARSHOT MCP gateway: shutting down\n")
        sys.stderr.flush()
        server.server_close()


def main(argv=None) -> int:
    """Entry point for the `earshot-server` console script."""
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(prog="earshot-server",
                                 description="EARSHOT MCP gateway (Streamable HTTP, MCP spec 2025-11-25)")
    ap.add_argument("--port", type=int, default=8000,
                    help="TCP port to listen on (default: 8000)")
    ap.add_argument("--host", default="127.0.0.1",
                    help=("Bind address (default: 127.0.0.1). Dev-only: a "
                          "non-loopback bind still faces the localhost-only "
                          "Origin policy for browser clients."))
    ap.add_argument("--dev-token", default=None, metavar="JSON",
                    help=("Dev-only: pin a bearer token, same JSON shape as "
                          "EARSHOT_DEV_TOKENS, e.g. '{\"demo\": [\"house-a\", "
                          "\"priya\"]}'. Overrides the env var. "
                          "Never use in production."))
    args = ap.parse_args(argv)
    if args.dev_token is not None:
        try:
            json.loads(args.dev_token)
        except ValueError:
            ap.error("--dev-token must be JSON like '{\"demo\": [\"house-a\", \"priya\"]}'")
    if sys.platform != "win32":
        # Graceful SIGTERM on POSIX: surface it as KeyboardInterrupt so the
        # shutdown path in run() handles it. Installed here (main thread) —
        # never inside run(): tests run run() on worker threads, where
        # signal.signal would raise ValueError.
        def _on_sigterm(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, _on_sigterm)
    run(args.port, host=args.host, dev_token_json=args.dev_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
