"""Constant-shape assembly tests — Seam 3 (S3).

Two layers:
  1. Unit: shape.py's pure functions — the assembler's invariants hold by
     construction (no counts, no ordinals, fixed suffix always, probe
     constant, chunking pure).
  2. Wire: the full HTTP path — digest always queued silently, chunked turns
     with the honest mid-conversation collapse, probe resistance across
     worlds, and the response contract on every tool.
"""
import json
import unittest

from earshot.gateway.mcp import shape as shape_mod
from earshot.gateway.mcp.shape import (
    AssemblyInput,
    PlannedItem,
    assemble,
    new_plan_id,
    probe_speak,
    take_chunk,
    terminal_assembly,
    FIXED_SUFFIX,
    CHUNK_SIZE,
)

from earshot.gateway.mcp.tests.harness import start_server, stop_server  # noqa: E402

PORT = 8900
DATE = "2026-10-19"
TZ = "Asia/Kolkata"


def _item(iid, depth=4, text="Some item text", action="SPEAK"):
    return PlannedItem(iid, depth, text if depth > 0 else "", action, 1)


def _input(items, **kw):
    d = dict(items=tuple(items), mode="cover", plan_id=new_plan_id(),
             table_version=1, screen_depth=4,
             followups=("next", "continue_on_personal_device"),
             continuation_ref="esh_" + "r" * 40)
    d.update(kw)
    return AssemblyInput(**d)


class AssembleTests(unittest.TestCase):
    def test_fixed_suffix_always_appended(self):
        # Even when nothing is spoken / nothing withheld.
        r = assemble(_input([]))
        self.assertTrue(r["speak"].endswith(FIXED_SUFFIX))
        r = assemble(_input([_item("a")]))
        self.assertTrue(r["speak"].endswith(FIXED_SUFFIX))

    def test_no_counts_no_ordinals(self):
        r = assemble(_input([_item("a", text="Alpha"),
                             _item("b", text="Beta"),
                             _item("c", text="Gamma")]))
        speak = r["speak"].lower()
        for banned in ("3 items", "three", "first", "second", "third",
                       "1.", "2.", "3."):
            self.assertNotIn(banned, speak)
        # wrapper introduces no digits of its own
        self.assertNotIn("3 flexible", speak)

    def test_canonical_order_structural(self):
        items = [_item("z", text="Zed"), _item("a", text="Aye"),
                 _item("m", text="Em")]
        r = assemble(_input(items))
        self.assertLess(r["speak"].index("Aye"), r["speak"].index("Em"))
        self.assertLess(r["speak"].index("Em"), r["speak"].index("Zed"))

    def test_only_planned_text_crosses(self):
        # A wrapper-introduced leak word (not from any item text) fails fast.
        with self.assertRaises(AssertionError):
            shape_mod._assert_wrapper_clean(
                "Here's today: Real text. One private item here. " + FIXED_SUFFIX,
                ["Real text"])
        # ...while item-sourced words pass.
        shape_mod._assert_wrapper_clean(
            "Here's today: Real text. " + FIXED_SUFFIX, ["Real text"])

    def test_depth_zero_carries_no_text(self):
        with self.assertRaises(ValueError):
            assemble(_input([PlannedItem("a", 0, "oops", "SPEAK", 1)]))

    def test_non_speak_carries_no_text(self):
        with self.assertRaises(ValueError):
            assemble(_input([PlannedItem("a", 4, "oops", "PHONE", 1)]))

    def test_contract_fields(self):
        r = assemble(_input([_item("a")], mode="open",
                            followups=("continue_on_personal_device",)))
        self.assertEqual(r["speak_policy"], "verbatim_no_elaboration")
        self.assertEqual(r["mode"], "open")
        self.assertEqual(r["followups"], ["continue_on_personal_device"])
        self.assertEqual(r["_meta"]["earshot/table_version"], 1)

    def test_nothing_withheld_still_suffix(self):
        # The whole point: the suffix is not a signal.
        r1 = assemble(_input([_item("a", text="Alpha")]))
        r2 = assemble(_input([]))
        self.assertTrue(r1["speak"].endswith(FIXED_SUFFIX))
        self.assertTrue(r2["speak"].endswith(FIXED_SUFFIX))


class ProbeTests(unittest.TestCase):
    def test_probe_is_constant(self):
        self.assertEqual(probe_speak(), "I'll put anything about that on your phone.")
        self.assertEqual(probe_speak(), probe_speak())

    def test_probe_takes_no_data(self):
        import inspect
        self.assertEqual(len(inspect.signature(probe_speak).parameters), 0)


class ChunkTests(unittest.TestCase):
    def test_take_chunk_pure(self):
        items = tuple(_item(f"i{i}") for i in range(5))
        c1, rest = take_chunk(items, 2)
        self.assertEqual([p.item_id for p in c1], ["i0", "i1"])
        c2, rest = take_chunk(rest, 2)
        self.assertEqual([p.item_id for p in c2], ["i2", "i3"])
        c3, rest = take_chunk(rest, 2)
        self.assertEqual([p.item_id for p in c3], ["i4"])
        self.assertEqual(rest, ())

    def test_take_chunk_canonical_order(self):
        items = (_item("z"), _item("a"))
        c, _ = take_chunk(items, 1)
        self.assertEqual(c[0].item_id, "a")

    def test_terminal_is_constant(self):
        r = terminal_assembly(new_plan_id(), 1, "cover", "esh_" + "r" * 40)
        self.assertIn("That's everything I can share out loud.", r["speak"])
        self.assertTrue(r["speak"].endswith(FIXED_SUFFIX))
        self.assertEqual(r["followups"], ["continue_on_personal_device"])


class WireTests(unittest.TestCase):
    """Full HTTP path: chunked turns, silent digest, honest collapse."""

    @classmethod
    def setUpClass(cls):
        cls.srv, cls.c = start_server(PORT)
        cls.c.initialize()
        cls.srv.broker.set_fixture_audience(["priya"])

    @classmethod
    def tearDownClass(cls):
        stop_server(cls.srv)

    def _brief(self, key, **kw):
        args = {"date": DATE, "timezone": TZ, "request_key": key}
        args.update(kw)
        return self.c.tool("prepare_day_brief", args)["result"]

    def test_digest_always_queued_silently(self):
        """Every brief queues the phone digest; the wire body never varies
        with it (constant followups)."""
        r = self._brief("cs-digest-00000001")
        sc = r["structuredContent"]
        broker = self.srv.broker
        digests = [e for (o, k), e in broker._outbox.items()
                   if e.get("kind") == "digest"]
        self.assertTrue(digests)
        # ...but the response carries no signal of it
        self.assertEqual(sc["followups"],
                         ["next", "continue_on_personal_device"])

    def test_chunked_turns_then_terminal(self):
        r = self._brief("cs-chunk-00000002")
        sc = r["structuredContent"]
        ref = sc["request_ref"]
        self.assertIn("next", sc["followups"])
        seen = [r["content"][0]["text"]]
        for i in range(6):
            if "next" not in sc["followups"]:
                break
            r = self._brief(f"cs-chunk-00000002-n{i}", continuation_ref=ref)
            sc = r["structuredContent"]
            seen.append(r["content"][0]["text"])
        # terminal: the "next" after the last chunk
        r = self._brief("cs-chunk-00000002-t", continuation_ref=ref)
        terminal = r["content"][0]["text"]
        self.assertIn("That's everything I can share out loud.", terminal)
        # every chunk is constant-shape
        for s in seen:
            self.assertTrue(s.endswith(FIXED_SUFFIX))

    def test_next_replay_is_idempotent(self):
        """Replaying the same key returns the stored chunk — no advance,
        no double exposure commit."""
        r = self._brief("cs-replay-00000003")
        ref = r["structuredContent"]["request_ref"]
        args = {"date": DATE, "timezone": TZ,
                "request_key": "cs-replay-00000003-n",
                "continuation_ref": ref}
        n1 = self.c.tool("prepare_day_brief", args)["result"]
        n2 = self.c.tool("prepare_day_brief", args)["result"]
        self.assertEqual(n1["structuredContent"]["speak"],
                         n2["structuredContent"]["speak"])
        self.assertEqual(n1["structuredContent"]["request_ref"],
                         n2["structuredContent"]["request_ref"])

    def test_honest_mid_conversation_collapse(self):
        """Mom walks in between turns: the next chunk re-plans against
        fresh belief and collapses to cover-mode shape."""
        r = self._brief("cs-collapse-000004")
        ref = r["structuredContent"]["request_ref"]
        first = r["content"][0]["text"]
        # Mom enters mid-brief.
        self.srv.broker.set_fixture_audience(["priya", "mom"])
        try:
            r2 = self._brief("cs-collapse-000004-n", continuation_ref=ref)
        finally:
            self.srv.broker.set_fixture_audience(["priya"])
        sc2 = r2["structuredContent"]
        self.assertEqual(sc2["mode"], "cover")
        blob = json.dumps(r2)
        for token in ("Prenatal", "City Clinic", "930"):
            self.assertNotIn(token, blob)

    def test_withdraw_drops_chunk_state(self):
        r = self._brief("cs-wdchunk-000005")
        ref = r["structuredContent"]["request_ref"]
        self.c.tool("withdraw_request",
                    {"request_ref": ref, "request_key": "cs-wdchunk-000005-w"})
        # "next" after withdraw: the capsule is revoked, so the continuation
        # ref is unusable -> identical "unavailable", no oracle, no chunk.
        b = self.c.tool("prepare_day_brief",
                        {"date": DATE, "timezone": TZ,
                         "request_key": "cs-wdchunk-000005-n",
                         "continuation_ref": ref})
        self.assertEqual(b["error"]["message"], "Unavailable")
        for token in ("Prenatal", "City Clinic"):
            self.assertNotIn(token, json.dumps(b))

    def test_every_tool_returns_the_contract(self):
        r = self._brief("cs-contract-000006")
        ref = r["structuredContent"]["request_ref"]
        calls = [
            ("resolve_day_change",
             {"request_ref": ref, "request_key": "cs-c-resolve-0001",
              "change": {"kind": "add_flexible_block", "duration_minutes": 20,
                         "window_start": "2026-10-19T14:00:00+05:30",
                         "window_end": "2026-10-19T18:00:00+05:30"}}),
            ("continue_on_personal_device",
             {"request_ref": ref, "request_key": "cs-c-continue-001"}),
            ("room", {"declaration": "Mom's here", "request_key": "cs-c-room-000001"}),
            ("keep_secret", {"instruction": "Keep work from guests",
                             "request_key": "cs-c-keepsecret-01"}),
        ]
        for name, args in calls:
            b = self.c.tool(name, args)["result"]
            sc = b["structuredContent"]
            for field in ("speak", "speak_policy", "mode", "followups",
                          "screen_depth", "request_ref", "request_state",
                          "_meta"):
                self.assertIn(field, sc, f"{name} missing {field}")
            self.assertEqual(sc["speak_policy"], "verbatim_no_elaboration")
            self.assertNotIn("public_facts", sc)
            self.assertEqual(b["content"][0]["text"], sc["speak"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
