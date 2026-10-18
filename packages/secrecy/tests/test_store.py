"""EdgeStore: the choke point holds; expiry is absence (S4)."""
import unittest

from earshot.secrecy.edges import EdgeProposal
from earshot.secrecy.store import EdgeStore


def prop(**kw):
    base = dict(type="hidden_from", target="mom", until=None,
                confidence=0.9, direction="TIGHTEN", reason="t")
    base.update(kw)
    return EdgeProposal(**base)


class StoreTest(unittest.TestCase):
    def test_add_returns_accepted_edge(self):
        s = EdgeStore()
        e = s.add("itm_1", prop())
        self.assertIsNotNone(e)
        self.assertEqual(e.target, "mom")

    def test_rejected_proposal_stores_nothing(self):
        s = EdgeStore()
        self.assertIsNone(s.add("itm_1", prop(confidence=0.1)))
        self.assertEqual(s.active_edges("itm_1", now=1_700_000_000.0), ())

    def test_no_direct_edge_write_api(self):
        # The security property: there is no public path that writes an edge
        # without the gate. If someone adds add_edge(), this fails.
        s = EdgeStore()
        self.assertFalse(hasattr(s, "add_edge"))
        self.assertFalse(hasattr(s, "insert"))
        self.assertFalse(hasattr(s, "put"))
        public = [n for n in dir(s) if not n.startswith("_")]
        self.assertEqual(sorted(public),
                         ["active_edges", "add", "all_edges", "item_ids"])

    def test_expiry_is_absence(self):
        s = EdgeStore()
        s.add("itm_1", prop(until="2026-10-01"))
        # Before expiry: visible.
        self.assertEqual(len(s.active_edges("itm_1", now=1789862400.0)), 1)
        # After expiry: invisible to decisions...
        self.assertEqual(s.active_edges("itm_1", now=1791417600.0), ())
        # ...but retained for audit.
        self.assertEqual(len(s.all_edges("itm_1")), 1)

    def test_unparseable_until_never_expires(self):
        s = EdgeStore()
        s.add("itm_1", prop(until="not-a-date"))
        self.assertEqual(len(s.active_edges("itm_1", now=9_999_999_999.0)), 1)

    def test_loosen_without_confirmation_never_lands(self):
        s = EdgeStore()
        e = s.add("itm_1", prop(direction="LOOSEN", confidence=0.99),
                  owner="priya")
        self.assertIsNone(e)
        self.assertEqual(s.active_edges("itm_1", now=1_700_000_000.0), ())


if __name__ == "__main__":
    unittest.main()
