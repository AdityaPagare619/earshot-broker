#!/usr/bin/env python3
"""EARSHOT controlled web host (Profile B) — J2 seat.

One-command demo host: serves the Echo-class UI, drives the GatewayPort
(real MCP client or labeled kernel-direct), the local output arbiter
(blueprint §6 ordering), and the audience event source.

Run:  python3 host.py [--port 8734]
Then open http://127.0.0.1:8734/

Honest labels are UI elements, not footnotes: the banner always reads
"Independent simulator — not a live Alexa+ device · Profile B".
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent.parent / "services" / "gateway" / "mcp"))
sys.path.insert(0, str(_HERE.parent.parent))  # repo root: wincompat

from wincompat import ensure_utf8_stdout  # noqa: E402
from gateway_port import GatewayPort  # noqa: E402  (sets kernel sys.path)
from arbiter import Arbiter  # noqa: E402
from audience import AudienceSource, SensorScript  # noqa: E402
from kernel import Fact, Label  # noqa: E402
import shape as shape_mod  # noqa: E402  (constant-shape assembly)

PUBLIC = "*"
HERE = _HERE

# Demo fixtures (dossier §4.3). The briefing LINES are gone: the UI now speaks
# the sealed-speech contract (res["speak"]) verbatim — the fixture never
# authors room-facing text. stopped_line is constant-shape in both modes
# (the old relaxed "One private item — sent to your phone." was a UI-visible
# existence leak — killed). The phone buzz stays: it is owner-visible, on the
# owner's device, never on the room speaker.
FIXTURES = {
    "strict": {
        "label": "Strict — existence protected",
        "stopped_line": "Paused — moved to your phone.",
        "nudge": None,
    },
    "relaxed": {
        "label": "Relaxed — existence releasable",
        "stopped_line": "Paused — moved to your phone.",
        "nudge": "Private day plan ready — tap to review.",
    },
}

# Fixture probe detector (labeled demo routing, not NLU). The RESPONSE is the
# guarantee: shape.probe_speak() is constant — identical whether the probed
# item exists, doesn't exist, or is secret. A real NLU would replace these
# patterns; the response vocabulary must stay a single sentence.
_PROBE_RES = [
    re.compile(r"anything private"),
    re.compile(r"any private"),
    re.compile(r"what.*private"),
    re.compile(r"what are you (hiding|withholding|not telling)"),
    re.compile(r"what'?s (being )?hidden"),
    re.compile(r"what did you (skip|leave out|not (say|tell|mention))"),
    re.compile(r"\bsecrets?\b"),
    re.compile(r"don'?t tell (mom|him|her|them|anyone)"),
]

# "next"-shaped utterances (exact): continue a chunked brief.
_NEXT_UTTERANCES = ("next", "more", "go on", "continue")


def _speak_of(res: dict) -> tuple:
    """Uniform speak extraction across backends.

    mcp: {content, structuredContent: <contract>, ...}; kernel_direct:
    <contract> directly. Returns (speak, contract).
    """
    sc = res.get("structuredContent")
    if isinstance(sc, dict) and "speak" in sc:
        return sc["speak"], sc
    return res.get("speak", ""), res


def _segments_of(speak: str) -> list:
    """Split the contract's speak text into arbiter-gated segments.

    Sentence boundaries only — never rewording, never reordering.
    """
    return [p.strip() for p in speak.split(". ") if p.strip()]


class Host:
    def __init__(self, tenant="house-a", owner="priya"):
        self.port = GatewayPort(tenant=tenant, owner=owner)
        self.status = self.port.connect()
        self.arbiter = Arbiter(self.port._kernel, tenant, owner)
        self.audience = AudienceSource(owner)
        self.tenant, self.owner = tenant, owner
        self.fixture_mode = "strict"
        self.phone_unlocked = False
        self._output: list[dict] = []  # {"segment": Segment, "at": float}
        self._briefing_thread: threading.Thread | None = None
        self._stop_briefing = threading.Event()
        self._trace: list[dict] = []  # last wire/protocol events
        self._round_trips: list[dict] = []  # tool round trips
        self._phone_inbox: list[dict] = []
        self._lock = threading.Lock()
        # Sealed-speech session state: the last brief's continuation ref and
        # its followups (drives "next"). Never secret content.
        self._last_ref: str | None = None
        self._last_followups: tuple = ()

    # ---- briefing pipeline ----------------------------------------------

    def _trace_add(self, kind: str, payload: dict):
        with self._lock:
            self._trace.append({"at": time.time(), "kind": kind,
                                "payload": payload})
            self._trace = self._trace[-50:]

    def start_briefing(self, lines: list[str], task_id: str = "brief"):
        """Release public lines as arbiter-gated segments, paced for speech."""
        self._stop_briefing.set()
        if self._briefing_thread and self._briefing_thread.is_alive():
            self._briefing_thread.join(timeout=2)
        self._stop_briefing.clear()
        self._briefing_thread = threading.Thread(
            target=self._brief_worker, args=(lines, task_id), daemon=True)
        self._briefing_thread.start()

    def _brief_worker(self, lines: list[str], task_id: str):
        pub = Label(frozenset({PUBLIC}))
        for i, line in enumerate(lines):
            if self._stop_briefing.is_set():
                break
            fact = Fact(f"brief-{task_id}-{i}", line, pub)
            grant = self.arbiter.prepare(task_id, fact)
            if grant is None:
                continue  # denied: stopped or label — never force it
            seg = self.arbiter.commit(grant)
            if seg is None:
                continue  # lost the race with an audience change: correct
            with self._lock:
                self._output.append({"segment": seg, "at": time.time()})
            time.sleep(1.4)  # paced for speech; revocation lands between segments

    def poll_output(self, after_seq: int = 0) -> dict:
        """The renderer-side gate: only playable segments are 'spoken'."""
        with self._lock:
            fresh = []
            for item in self._output:
                seg = item["segment"]
                if seg.seq > after_seq and self.arbiter.is_segment_playable(seg):
                    fresh.append({"seq": seg.seq, "text": seg.text,
                                  "epoch": seg.epoch})
            return {"segments": fresh, "stopped": self.arbiter.output_stopped,
                    "epoch": self.arbiter.epoch}

    # ---- utterance routing (labeled demo routing, not NLU) ---------------

    def _sync_audience_to_gateway(self):
        """Fixture sensing -> gateway belief. The demo's AudienceSource is the
        sensing layer; the fixture audience is exhaustive (nobody unmodeled
        is around). Called before every tool call so belief is never stale."""
        listeners = self.audience._last_listeners or frozenset({self.owner})
        self.port.set_fixture_audience(listeners)

    def _fresh_key(self, stem: str) -> str:
        return f"{stem}-{int(time.time() * 1000)}-demo0001"

    def _speak_brief(self, res: dict, tool: str) -> dict:
        """Render a brief-family contract: speak verbatim, sentence-split
        into arbiter-gated segments, phone digest queued silently."""
        speak, contract = _speak_of(res)
        self._last_ref = contract.get("request_ref")
        self._last_followups = tuple(contract.get("followups", ()))
        self._round_trips.append({"tool": tool,
                                  "ms": res.get("_round_trip_ms")})
        self._trace_add("tool_call", {"tool": tool,
                                      "speak": speak,
                                      "mode": contract.get("mode"),
                                      "followups": list(self._last_followups)})
        # A new utterance is new intent (not autoplay): return the speaker
        # to service for NEW grants at the current audience epoch. Stopped
        # segments stay stopped (epoch-bound invalidation).
        listeners = self.audience._last_listeners or frozenset({self.owner})
        self.arbiter.resume_after_retrust(frozenset(listeners))
        self.start_briefing(_segments_of(speak),
                            task_id=(self._last_ref or "brief")[:8])
        self._phone_sync_quiet(self._last_ref)
        return {"tool": tool, "spoken": speak,
                "request_ref": self._last_ref}

    def utter(self, text: str) -> dict:
        low = text.lower()
        # Probe resistance (Seam 3): probe-shaped queries NEVER reach a data
        # path. One constant sentence, whatever the room, whatever exists.
        if any(rx.search(low) for rx in _PROBE_RES):
            self._trace_add("probe", {"utterance": text,
                                      "response": "constant"})
            return {"tool": None, "spoken": shape_mod.probe_speak()}
        # "next": honest mid-conversation collapse — re-plan remaining items
        # against FRESH belief (the audience may have changed mid-brief).
        if low.strip() in _NEXT_UTTERANCES and self._last_ref:
            if "next" not in self._last_followups:
                return {"tool": None,
                        "spoken": "That's everything I can share out loud."}
            self._sync_audience_to_gateway()
            res = self.port.call_tool(
                "prepare_day_brief",
                {"date": "2026-10-18", "timezone": "Asia/Kolkata",
                 "request_key": self._fresh_key("next"),
                 "continuation_ref": self._last_ref})
            return self._speak_brief(res, "prepare_day_brief")
        if "organiz" in low or "afternoon" in low or "day" in low or "brief" in low:
            self._sync_audience_to_gateway()
            res = self.port.call_tool(
                "prepare_day_brief",
                {"date": "2026-10-18", "timezone": "Asia/Kolkata",
                 "request_key": self._fresh_key("brief")})
            return self._speak_brief(res, "prepare_day_brief")
        if "room for" in low or "minute" in low or "call" in low:
            if not self._last_ref:
                return {"tool": None,
                        "spoken": "Ask me to organize your day first."}
            mins = 20
            for tok in low.split():
                if tok.isdigit():
                    mins = int(tok)
            self._sync_audience_to_gateway()
            res = self.port.call_tool(
                "resolve_day_change",
                {"request_ref": self._last_ref,
                 "request_key": self._fresh_key("resolve"),
                 "change": {
                     "kind": "find_alternative_window",
                     "duration_minutes": mins,
                     "window_start": "2026-10-19T09:00:00+05:30",
                     "window_end": "2026-10-19T18:00:00+05:30"}})
            speak, _ = _speak_of(res)
            self._round_trips.append({"tool": "resolve_day_change",
                                      "ms": res.get("_round_trip_ms")})
            self._trace_add("tool_call", {"tool": "resolve_day_change",
                                          "speak": speak, "minutes": mins})
            return {"tool": "resolve_day_change", "spoken": speak}
        if "phone" in low or "privately" in low:
            if not self._last_ref:
                return {"tool": None,
                        "spoken": "Ask me to organize your day first."}
            res = self.port.call_tool(
                "continue_on_personal_device",
                {"request_ref": self._last_ref,
                 "request_key": self._fresh_key("continue")})
            speak, _ = _speak_of(res)
            return {"tool": "continue_on_personal_device", "spoken": speak}
        if low.strip() in ("stop", "cancel", "never mind", "withdraw"):
            self._stop_briefing.set()
            if not self._last_ref:
                return {"tool": None, "spoken": "Stopped."}
            res = self.port.call_tool(
                "withdraw_request",
                {"request_ref": self._last_ref,
                 "request_key": self._fresh_key("withdraw")})
            speak, _ = _speak_of(res)
            self._last_ref = None
            self._last_followups = ()
            return {"tool": "withdraw_request", "spoken": speak}
        return {"tool": None,
                "spoken": ("Try: 'help me organize my afternoon', "
                           "'make room for a twenty-minute call', or 'stop'.")}

    def _phone_sync_quiet(self, request_ref: str | None):
        """The inbox syncs with no secret-dependent signal beyond the fixture
        buzz affordance (owner's device only). Content lives in the broker's
        digest/outbox, read via the phone panel — never hardcoded here."""
        mode = self.fixture_mode
        self._phone_inbox.append({
            "at": time.time(), "kind": "day_plan",
            "text": "Day plan synced — open your phone to review.",
            "buzz": bool(FIXTURES[mode]["nudge"]),
            "badge": bool(FIXTURES[mode]["nudge"]),
        })

    # ---- audience ---------------------------------------------------------

    def audience_action(self, action: str) -> dict:
        if action == "mom_enters":
            ev = self.audience.manual_set(frozenset({self.owner, "mom"}))
        elif action == "mom_leaves":
            ev = self.audience.manual_set(frozenset({self.owner}))
        elif action == "guest_enters":
            ev = self.audience.manual_guest_enters()
        elif action == "guest_leaves":
            ev = self.audience.manual_guest_leaves()
        elif action == "sensor_lost":
            self.arbiter.sensor_heartbeat_lost()
            return {"accepted": True, "note": "heartbeat lost -> UNKNOWN"}
        else:
            return {"accepted": False, "reason": "unknown_action"}
        result = self.arbiter.audience_changed(ev)
        self._trace_add("audience", {"action": action, **result})
        if result.get("accepted"):
            self._stop_briefing.set()
        # Seam 3: the demo's sensing layer is the fixture audience — sync it
        # to gateway belief NOW, so the next turn re-plans against the room
        # as it is (the honest mid-conversation collapse).
        self._sync_audience_to_gateway()
        return result

    # ---- scripted walk-in demo ---------------------------------------------

    def run_walkin_script(self) -> dict:
        """The evangelist beat, on the real path (not theater)."""
        self.audience.load_script([
            SensorScript(4.0, frozenset({self.owner, "mom"}), "Mom enters"),
        ])
        threading.Thread(target=self._walkin_worker, daemon=True).start()
        return {"started": True}

    def _walkin_worker(self):
        self.utter("Help me organize my afternoon.")
        # Scripted sensor events are polled and fed through the real path.
        deadline = time.time() + 12
        while time.time() < deadline:
            for ev in self.audience.poll_script():
                result = self.arbiter.audience_changed(ev)
                self._trace_add("audience", {"action": "script: mom enters",
                                             **result})
                self._stop_briefing.set()
            time.sleep(0.2)

    # ---- status --------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "backend": self.port.backend,
            "gateway_url": self.port.gateway_url,
            "degraded": self.port.degraded,
            "tools": self.status.get("tools", []),
            "epoch": self.arbiter.epoch,
            "listeners": sorted(self.audience._last_listeners or {self.owner}),
            "stopped": self.arbiter.output_stopped,
            "fixture_mode": self.fixture_mode,
            "fixture_label": FIXTURES[self.fixture_mode]["label"],
            "stopped_line": FIXTURES[self.fixture_mode]["stopped_line"],
            "nudge": FIXTURES[self.fixture_mode]["nudge"],
            "phone_unlocked": self.phone_unlocked,
            "round_trips": self._round_trips[-10:],
        }


HOST: Host | None = None


class Handler(BaseHTTPRequestHandler):
    server_version = "EarshotSim/0.1"

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._serve_file("ui/index.html", "text/html")
        elif path.startswith("/ui/"):
            name = Path(path).name
            ctype = {"html": "text/html", "css": "text/css",
                     "js": "application/javascript"}.get(
                         name.rsplit(".", 1)[-1], "application/octet-stream")
            self._serve_file(str(Path("ui") / name), ctype)
        elif path == "/api/status":
            self._json(HOST.get_status())
        elif path == "/api/output":
            q = parse_qs(parsed.query)
            self._json(HOST.poll_output(
                after_seq=int(q.get("after", ["0"])[0])))
        elif path == "/api/events":
            self._json([{"kind": e.kind, "at": e.at, "detail": e.detail}
                        for e in HOST.arbiter.event_log()][-60:])
        elif path == "/api/trace":
            with HOST._lock:
                self._json(list(HOST._trace)[-20:])
        elif path == "/api/phone":
            if not HOST.phone_unlocked:
                self._json({"ok": False, "error": "locked"}, 403)
                return
            q = parse_qs(parsed.query)
            ref = q.get("ref", [""])[0]
            with HOST._lock:
                inbox = list(HOST._phone_inbox)
            personal = HOST.port.open_personal(ref, authenticated=True)
            self._json({"inbox": inbox, "personal": personal})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()
        if path == "/api/utter":
            self._json(HOST.utter(body.get("text", "")))
        elif path == "/api/audience":
            self._json(HOST.audience_action(body.get("action", "")))
        elif path == "/api/script":
            if body.get("name") == "walkin":
                self._json(HOST.run_walkin_script())
            else:
                self._json({"started": False}, 400)
        elif path == "/api/phone/unlock":
            HOST.phone_unlocked = True  # demo stand-in for owner auth
            self._json({"ok": True})
        elif path == "/api/config":
            mode = body.get("fixture_mode")
            if mode in FIXTURES:
                HOST.fixture_mode = mode
                self._json({"ok": True, "mode": mode})
            else:
                self._json({"ok": False}, 400)
        else:
            self._json({"error": "not found"}, 404)

    def _serve_file(self, rel: str, ctype: str):
        full = HERE / rel
        if not full.is_file():
            self._json({"error": "not found"}, 404)
            return
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep demo output clean


def main():
    ensure_utf8_stdout()
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8734)
    args = ap.parse_args()
    global HOST
    HOST = Host()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Earshot controlled host on http://127.0.0.1:{args.port}/")
    print(f"backend={HOST.port.backend}  "
          f"(set EARSHOT_GATEWAY_URL for the real MCP path)")
    print("Independent simulator — not a live Alexa+ device (Profile B).")
    server.serve_forever()


if __name__ == "__main__":
    main()
