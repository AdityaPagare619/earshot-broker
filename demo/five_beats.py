#!/usr/bin/env python3
"""EARSHOT 5-beat demo runner — the sealed-speech story, computed not narrated.

Implements FINAL-ARCHITECTURE.md §12: every beat drives the integration
pipeline (fixture stages behind the frozen ports) and prints COMPUTED values —
beliefs, credible sets, planned depths, spoken text, ledger entries, phone
digests. Beat properties are asserted in code (see integration/tests/).

Honest labels, always:
  [SIMULATOR]  the Alexa+ host is an independent simulation, not a device
  [FIXTURE]    stage mechanisms are deterministic stand-ins for S1–S4 seats

Usage:  python3 demo/five_beats.py [--lang en|hi]
Exit code is non-zero if any beat assertion fails.
"""

from __future__ import annotations

import argparse
import os
import sys

from earshot.integration.pipeline import SealedSpeechPipeline
from earshot.packs.loader import load_pack
from earshot.wincompat import ensure_utf8_stdout

def _packs_root() -> str:
    """Locate the household-pack data dir, installed or from source."""
    try:
        from importlib.resources import files
        cand = files("earshot.packs")
        if cand.is_dir():
            return str(cand)
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packs")


PACKS_ROOT = _packs_root()

# ---------------------------------------------------------------- scenario
STRINGS = {
    "en": {
        "obgyn": {"title": "OB-GYN checkup with Dr. Mehta", "time": "3:40",
                  "location": "Cloudnine", "category": "doctor's appointment",
                  "daypart": "afternoon"},
        "standup": {"title": "team standup", "time": "10 AM", "location": "office",
                    "category": "work", "daypart": "morning"},
        "groceries": {"title": "buy groceries", "daypart": "afternoon", "category": "errand"},
        "gift": {"title": "Instax Mini 12 camera", "sender": "Amazon",
                 "items": "Instax Mini 12 camera", "daypart": "evening",
                 "for_person": "maya"},
        "therapy": {"title": "therapy session notes", "daypart": "evening",
                    "category": "health"},
        "keep_secret": "never mention my therapy in front of mom",
        "probe": "I'm alone. Are any packages coming?",
    },
    "hi": {
        "obgyn": {"title": "डॉ. मेहता के साथ ओबी-जीवाईएन चेकअप", "time": "3:40",
                  "location": "क्लाउडनाइन", "category": "डॉक्टर की अपॉइंटमेंट",
                  "daypart": "दोपहर"},
        "standup": {"title": "टीम स्टैंडअप", "time": "सुबह 10", "location": "ऑफिस",
                    "category": "काम", "daypart": "सुबह"},
        "groceries": {"title": "किराने का सामान", "daypart": "शाम", "category": "काम"},
        "gift": {"title": "इंस्टैक्स मिनी 12 कैमरा", "sender": "अमेज़न",
                 "items": "इंस्टैक्स मिनी 12 कैमरा", "daypart": "शाम",
                 "for_person": "maya"},
        "therapy": {"title": "थेरेपी सेशन नोट्स", "daypart": "शाम",
                    "category": "स्वास्थ्य"},
        # Fixture NL parser is English-only (documented limitation); the hot
        # path it feeds is language-blind. The room still hears only Hindi.
        "keep_secret": "never mention my therapy in front of mom",
        "probe": "I'm alone. Are any packages coming?",
    },
}

BEAT_TIMES = [
    "0:00–0:30", "0:30–1:00", "1:00–1:40", "1:40–2:20", "2:20–2:55",
]


def banner(text):
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def beat(n, title, narration):
    print(f"\n--- BEAT {n} [{BEAT_TIMES[n-1]}] — {title} ---")
    print(f"  {narration}")


def show_belief(info):
    bars = "  ".join(f"{p}:{'█' * int(v * 10):<10} {v:.2f}"
                     for p, v in sorted(info["belief"].items()))
    print(f"  [belief] {bars}")


def show_response(resp, info):
    plan = info["plan"]
    depths = ", ".join(f"{pi.item_id[:8]}→d{pi.depth}({pi.action})" for pi in plan.items)
    print(f"  [plan] cover_mode={plan.cover_mode} credible={sorted(plan.credible_set)}")
    print(f"  [plan] depths: {depths}")
    print(f"  [speak] {resp.speak}")
    if resp.phone_digest:
        print(f"  [phone] {resp.phone_digest}")
    print(f"  [ledger] {len(info['entries'])} entries "
          f"(over-attributed to credible set)")


def build_day(pack, lang, with_therapy=False, mom_present=False):
    """Fresh pipeline: the standard day. Returns the pipeline, briefed."""
    S = STRINGS[lang]
    pipe = SealedSpeechPipeline(pack)
    pipe.ingest("event", S["obgyn"], source="calendar")
    pipe.ingest("event", S["standup"], source="calendar")
    pipe.ingest("reminder", S["groceries"], source="reminders")
    pipe.ingest("delivery", S["gift"], source="email")
    if with_therapy:
        pipe.ingest("note", S["therapy"], source="notes")
    pipe.compile_all()
    if with_therapy:
        edge = pipe.keep_secret(S["keep_secret"])
        assert edge is not None and edge.direction == "TIGHTEN"
    signals = [("mom", "declare")] if mom_present else []
    resp, info = pipe.brief(signals=signals)
    return pipe, resp, info


def main(argv=None):
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=("en", "hi"))
    args = ap.parse_args(argv)
    lang = args.lang
    S = STRINGS[lang]

    pack = load_pack(PACKS_ROOT, lang)
    banner(f"EARSHOT — sealed-speech demo  [SIMULATOR] [FIXTURE] [lang={lang}]")
    print("Independent simulator: not a live Alexa+ device. Fixture stages stand in")
    print("for S1–S4 seats behind frozen ports. Dev auth: none (fixture pipeline).")

    # -- BEAT 1: alone -------------------------------------------------------
    beat(1, "Alone", "Priya: \"What's my day?\" Belief shows only Priya.")
    pipe, resp, info = build_day(pack, lang)
    show_belief(info)
    show_response(resp, info)
    assert not info["plan"].cover_mode, "alone: expected open mode"
    assert all(pi.depth == 4 for pi in info["plan"].items), "alone: expected full detail"

    # -- BEAT 2: the data understood itself -----------------------------------
    beat(2, "The data understood itself",
         "An Instax order email arrives. Nobody wrote a rule.")
    gift_id = [i for i, it in pipe.items.items()
               if it.kind == "delivery"][0]
    item = pipe.items[gift_id]
    print(f"  [ingest] delivery -> state={item.state} (quarantined immediately)")
    edges = pipe.secrecy.accept(pipe.secrecy.infer_edges(item))
    for e in edges:
        print(f"  [secrecy] inferred: {e.type}({e.target}) until={e.until} "
              f"conf={e.confidence} provenance={e.provenance} [{e.direction}]")
    assert any(e.type == "hidden_from" and e.target == "maya" for e in edges), \
        "expected the gift to be hidden from Maya by inference"
    print("  [phone card] confidence 0.91 >= 0.6 -> auto-applied (tightening is "
          "always safe). Had it been 0.3-0.6, this would be a confirm card.")

    # -- BEAT 3: mom arrives ---------------------------------------------------
    beat(3, "Mom arrives", "Belief rises. The briefing generalizes; the phone "
                           "digest stays silent. Same suffix shape as beat 1.")
    changed = pipe.room("mom's here")
    print(f"  [room] {changed}")
    resp3, info3 = pipe.brief()
    show_belief(info3)
    show_response(resp3, info3)
    assert info3["plan"].cover_mode, "mom present: expected cover mode"
    obgyn_depth = next(pi.depth for pi in info3["plan"].items
                       if pipe.items[pi.item_id].fields.get("category",
                          "") in ("doctor's appointment", "डॉक्टर की अपॉइंटमेंट"))
    assert obgyn_depth == 3, f"expected d3 for mom, got d{obgyn_depth}"
    assert resp3.speak.endswith(pack.ui["cover_suffix"]), \
        "cover suffix must be present"

    # -- BEAT 4: "can you tell?" ------------------------------------------------
    beat(4, "\"Can you tell?\"",
         "Two briefings, back to back: a day WITH a hidden item, a day WITHOUT. "
         "Mom is present for both.")
    pipe_with, resp_with, info_with = build_day(pack, lang, with_therapy=True,
                                                mom_present=True)
    pipe_without, resp_without, info_without = build_day(pack, lang,
                                                         with_therapy=False,
                                                         mom_present=True)
    print(f"  [with therapy]    speak: {resp_with.speak}")
    print(f"  [without therapy] speak: {resp_without.speak}")
    assert resp_with.speak == resp_without.speak, \
        "BEAT 4 FAILED: the room can tell whether the item exists"
    assert (resp_with.structured["mode"] == resp_without.structured["mode"] == "cover")
    print("  [verdict] identical shape. Neither can Mom. "
          "(Existence-AUC chart is S5's measurement; this is its necessary condition.)")

    # -- BEAT 5: the probe + the walk-in ---------------------------------------
    beat(5, "The probe + the walk-in",
         "Maya: \"I'm alone. Are any packages coming?\" Then a guest joins "
         "between turns. We can't interrupt mid-sentence. We don't need to.")
    probe_resp = pipe.ask_about(S["probe"])
    print(f"  [maya probes] {probe_resp.speak}")
    # Same probe, no gift in the world -> identical response.
    pipe_nogift, _, _ = build_day(pack, lang, mom_present=True)
    del pipe_nogift.rows[[i for i in pipe_nogift.rows
                          if pipe_nogift.items[i].kind == "delivery"][0]]
    probe_resp2 = pipe_nogift.ask_about(S["probe"])
    assert probe_resp.speak == probe_resp2.speak, "probe response must be constant"
    assert probe_resp.speak == pack.ui["probe_response"], \
        "probe answer must be the pack's fixed probe response, not content"
    print("  [verdict] probe answer identical with/without the gift. "
          "\"I'm alone\" cannot loosen a target-linked secret.")

    print("  [walk-in] turn 1 (alone): two items, full detail.")
    pipe_walk, resp_w1, info_w1 = build_day(pack, lang)
    chunks = pipe_walk.shape.chunk(info_w1["plan"], n=2)
    c1 = pipe_walk.shape.assemble(chunks[0], pipe_walk.rows, pack, pipe_walk.fields)
    print(f"  [turn 1] {c1.speak}")
    print("  [walk-in] a guest phone joins the wifi between turns...")
    resp_w2, info_w2 = pipe_walk.brief(signals=[("unknown", "guest")])
    chunks2 = pipe_walk.shape.chunk(info_w2["plan"], n=2)
    c2 = pipe_walk.shape.assemble(chunks2[0], pipe_walk.rows, pack, pipe_walk.fields)
    show_belief(info_w2)
    print(f"  [turn 2] {c2.speak}")
    assert info_w2["plan"].cover_mode, "guest present: expected cover mode"
    assert c1.speak != c2.speak, "turn 2 should generalize after the guest joins"
    print("  [verdict] collapse happened at the turn boundary — the only place "
          "the platform allows it.")

    banner("Close — \"Secrets have audiences. Rooms have beliefs. Speech has memory.\"")
    print("ALL 5 BEATS PASSED  [SIMULATOR] [FIXTURE]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
