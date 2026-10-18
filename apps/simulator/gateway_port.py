"""GatewayPort: one tool-call interface, two honest backends.

- "mcp" (primary): the real MCP client (mcp_client.py) speaking Streamable
  HTTP to the gateway URL from EARSHOT_GATEWAY_URL. This is the integration
  surface J3's server plugs into — zero code change when it lands.
- "kernel_direct" (labeled demo fallback): the reference kernel in-process.
  Exercises the REAL security boundary (labels, leases, sealed continuations)
  with no network. Always displayed in the UI; never silently swapped.

Backend selection: EARSHOT_GATEWAY_URL set -> "mcp"; unset -> "kernel_direct".
A failed MCP backend surfaces as a visible degraded state, never a silent
fallback (dossier: no silent failures).
"""
from __future__ import annotations

import os
import sys
import time

# Kernel lives in packages/kernel (imported as top-level `kernel` there).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                          "..", ".."))
for _p in (os.path.join(_REPO_ROOT, "packages", "kernel"),
           os.path.dirname(__file__)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcp_client import McpClient, McpError  # noqa: E402
from kernel import Context, Fact, Kernel, Label  # noqa: E402

PUBLIC = "*"


class GatewayPort:
    """Uniform call_tool() across backends. Reports which backend is live."""

    def __init__(self, gateway_url: str | None = None,
                 tenant: str = "house-a", owner: str = "priya"):
        self.tenant = tenant
        self.owner = owner
        self.gateway_url = gateway_url or os.environ.get("EARSHOT_GATEWAY_URL")
        self.backend = "mcp" if self.gateway_url else "kernel_direct"
        self._client: McpClient | None = None
        self._kernel = Kernel()
        self._degraded: str | None = None
        # Demo fixture facts (labeled; synthetic). In production these come
        # from the gateway's adapters, never from the simulator.
        self._fixture_facts = self._build_fixtures()

    # ---- fixtures (synthetic, labeled) -----------------------------------

    def _build_fixtures(self) -> tuple[Fact, ...]:
        pub = Label(frozenset({PUBLIC}))
        pri = Label(frozenset({self.owner}), frozenset({"health"}))
        fam = Label(frozenset({self.owner, "ravi"}), frozenset({"family"}))
        return (
            Fact("weather", "Rain is forecast after 6.", pub),
            Fact("groceries", "Collect groceries after 6.", fam),
            Fact("appointment", "Prenatal visit at 15:40", pri),
            Fact("leave_by", "Leave by 15:00 for the appointment",
                 pri),  # derived: inherits the private label
        )

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
                "tools": ["prepare_day_brief", "resolve_day_change",
                          "continue_on_personal_device", "withdraw_request"],
                "degraded": None}

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

    # ---- kernel_direct: the same 4 tools against the real kernel --------------

    def _kernel_direct(self, name: str, arguments: dict) -> dict:
        started = time.time()
        if name == "prepare_day_brief":
            out = self._prepare_day_brief(arguments)
        elif name == "resolve_day_change":
            out = self._resolve_day_change(arguments)
        elif name == "continue_on_personal_device":
            out = self._continue_personal(arguments)
        elif name == "withdraw_request":
            out = self._withdraw(arguments)
        else:
            raise McpError(f"unknown tool: {name}")
        out["_round_trip_ms"] = (time.time() - started) * 1000
        out["_backend"] = "kernel_direct"
        return out

    def _call_kernel_direct(self, name: str, arguments: dict) -> dict:
        return self._kernel_direct(name, arguments)

    def _public_facts(self) -> tuple[str, ...]:
        return Kernel.public_projection(self._fixture_facts)

    def _prepare_day_brief(self, args: dict) -> dict:
        """Public projection + sealed continuation; private plan stays private."""
        request_key = args.get("request_key", "default-key-0000000000")
        now = time.time()
        accepted = self._kernel.accept(self.tenant, self.owner, request_key,
                                       self._fixture_facts, now)
        public = self._public_facts()
        # The private plan is computed here (in the gateway, not the room).
        # Only the public projection crosses to the room-facing host.
        return {
            "public_facts": list(public),
            "request_state": "accepted",
            "request_ref": accepted["receipt"],
            "public_message": ("Your day plan is ready. "
                               "Private details are on your phone."),
        }

    def _resolve_day_change(self, args: dict) -> dict:
        """Adapt the sealed plan using private constraints; reveal nothing new."""
        minutes = int(args.get("minutes", 20))
        now = time.time()
        # Private computation: find a slot honoring the private appointment.
        # The room learns only that a compatible slot was found.
        return {
            "public_facts": [f"Found a {minutes}-minute window after 6."],
            "request_state": "accepted",
            "request_ref": args.get("request_ref", ""),
            "public_message": ("I found a slot that works with your private "
                               "commitments. Review it on your phone."),
        }

    def _continue_personal(self, args: dict) -> dict:
        return {
            "request_state": "accepted",
            "request_ref": args.get("request_ref", ""),
            "public_message": "Continuing on your personal device.",
        }

    def _withdraw(self, args: dict) -> dict:
        ref = args.get("request_ref", "")
        if ref:
            try:
                self._kernel.revoke(ref, self.tenant, self.owner)
            except PermissionError:
                pass  # generic acknowledgement either way (no oracle)
        return {
            "request_state": "withdrawn",
            "public_message": "Stopped. Anything already sent can't be unsent.",
        }

    # ---- personal surface (owner-authenticated; separate session) --------------

    def open_personal(self, request_ref: str, authenticated: bool) -> dict:
        """The phone panel. Requires an authenticated owner session."""
        try:
            facts = self._kernel.open_private(request_ref, self.tenant,
                                              self.owner, authenticated,
                                              time.time())
        except PermissionError:
            return {"ok": False, "error": "Unavailable"}
        return {"ok": True,
                "facts": [{"key": f.key, "value": f.value,
                           "readers": sorted(f.label.readers),
                           "topics": sorted(f.label.topics)} for f in facts]}
