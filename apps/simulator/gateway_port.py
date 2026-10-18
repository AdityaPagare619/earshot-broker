"""GatewayPort: one tool-call interface, two honest backends.

- "mcp" (primary): the real MCP client (mcp_client.py) speaking Streamable
  HTTP to the gateway URL from EARSHOT_GATEWAY_URL.
- "kernel_direct" (labeled demo fallback): the REAL broker in-process
  (services/gateway/mcp/broker.py) — the same code as the MCP server,
  minus the HTTP. Single-sourced seam: there is no second implementation
  to drift.

Backend selection: EARSHOT_GATEWAY_URL set -> "mcp"; unset -> "kernel_direct".
A failed MCP backend surfaces as a visible degraded state, never a silent
fallback (dossier: no silent failures).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Kernel lives in packages/kernel (imported as top-level `kernel` there);
# the broker lives in services/gateway/mcp (imports as top-level `broker`,
# `fixtures`, `shape` there).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (_REPO_ROOT / "packages" / "kernel",
           _REPO_ROOT / "services" / "gateway" / "mcp",
           Path(__file__).resolve().parent):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from mcp_client import McpClient, McpError  # noqa: E402
from kernel import Kernel  # noqa: E402  (arbiter seal mechanics)

PUBLIC = "*"

# The tool surface, mirrored from packages/contracts/API_CONTRACTS.json.
TOOLS = ("prepare_day_brief", "resolve_day_change",
         "continue_on_personal_device", "withdraw_request",
         "room", "keep_secret")


class GatewayPort:
    """Uniform call_tool() across backends. Reports which backend is live."""

    def __init__(self, gateway_url: str | None = None,
                 tenant: str = "house-a", owner: str = "priya"):
        self.tenant = tenant
        self.owner = owner
        self.gateway_url = gateway_url or os.environ.get("EARSHOT_GATEWAY_URL")
        self.backend = "mcp" if self.gateway_url else "kernel_direct"
        self._client: McpClient | None = None
        self._kernel = Kernel()  # arbiter seal mechanics (not the tool path)
        self._broker = None      # real Broker, built lazily in-process
        self._degraded: str | None = None

    # ---- the in-process broker (kernel_direct) ------------------------------

    def _get_broker(self):
        """The REAL broker — same class the MCP server runs. Lazy so the
        mcp backend never pays for it."""
        if self._broker is None:
            from broker import Broker  # noqa: E402
            self._broker = Broker()
        return self._broker

    def set_fixture_audience(self, listeners) -> None:
        """Fixture sensing channel -> the in-process broker. No-op on the mcp
        path (the real gateway owns belief there; the demo drives it via the
        `room` tool instead)."""
        if self.backend == "kernel_direct":
            self._get_broker().set_fixture_audience(listeners)

    # ---- lifecycle ---------------------------------------------------------

    def connect(self) -> dict:
        """Establish the backend. Returns a status dict for the UI banner."""
        if self.backend == "mcp":
            try:
                self._client = McpClient(self.gateway_url).connect()
                tools = [t["name"] for t in self._client.list_tools()]
                return {"backend": "mcp", "url": self.gateway_url,
                        "tools": tools, "degraded": None}
            except McpError as e:
                self._degraded = str(e)
                return {"backend": "mcp", "url": self.gateway_url,
                        "tools": [], "degraded": self._degraded}
        return {"backend": "kernel_direct", "url": None,
                "tools": list(TOOLS), "degraded": None}

    @property
    def degraded(self) -> str | None:
        return self._degraded

    # ---- the uniform tool surface -------------------------------------------

    def call_tool(self, name: str, arguments: dict) -> dict:
        if self.backend == "mcp" and self._client is not None:
            started = time.time()
            try:
                result = self._client.call_tool(name, arguments)
            except McpError as e:
                self._degraded = str(e)
                raise
            result["_round_trip_ms"] = (time.time() - started) * 1000
            return result
        return self._call_kernel_direct(name, arguments)

    # ---- kernel_direct: the same 6 tools, in-process -------------------------

    def _kernel_direct(self, name: str, arguments: dict) -> dict:
        started = time.time()
        broker = self._get_broker()
        handler = getattr(broker, name, None)
        if handler is None or name not in TOOLS:
            raise McpError(f"unknown tool: {name}")
        out = handler(self.tenant, self.owner, arguments)
        out["_round_trip_ms"] = (time.time() - started) * 1000
        out["_backend"] = "kernel_direct"
        return out

    def _call_kernel_direct(self, name: str, arguments: dict) -> dict:
        return self._kernel_direct(name, arguments)

    # ---- personal surface (owner-authenticated; separate session) --------------

    def open_personal(self, request_ref: str, authenticated: bool) -> dict:
        """The phone panel. Owner-authenticated; reads the broker's capsule
        (the same kernel the brief was planned from — never a second copy).

        `authenticated` is the caller's assertion of an owner-authenticated
        session (the demo's /api/phone gate checks phone_unlocked first).
        """
        if not authenticated:
            return {"ok": False, "error": "Unavailable"}
        if self.backend == "mcp":
            # The real gateway exposes personal facts only over the owner
            # channel, not MCP: the demo phone panel is a kernel_direct
            # affordance. Honest label, not a silent gap.
            return {"ok": False, "error": "personal surface is local-only"}
        try:
            facts = self._get_broker().personal_facts(
                request_ref, self.tenant, self.owner)
        except Exception:
            return {"ok": False, "error": "Unavailable"}
        return {"ok": True, "facts": facts}
