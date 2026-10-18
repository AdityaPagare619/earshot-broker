"""What-each-recipient-sees preview + the counterfactual prove-it check.

The trust artifact of the personal surface: for one sealed request, show the
public projection, the controlled-room projection under STATED assumptions, and
the full personal view side by side. Then prove the boundary holds when the
hidden content changes: prenatal -> therapy -> removed must leave the public
projection byte-identical.
"""
import time

from earshot.kernel import Kernel

from .fixture_calendar import FixtureCalendar
from .inbox import PUBLIC_WEATHER, controlled_context, uncontrolled_context, _fact_from_event


def _facts_for(calendar: FixtureCalendar) -> tuple:
    return (PUBLIC_WEATHER,) + tuple(_fact_from_event(e) for e in calendar.events())


def preview(surface, token: str, request_ref: str) -> dict:
    """Build the per-audience preview for a sealed request."""
    tenant, owner = surface._owner(token)
    receipt = surface._resolve_ref(token, request_ref)
    now = time.time()
    facts = surface.store.kernel.open_private(receipt, tenant, owner, True, now)

    public = Kernel.public_projection(facts)
    room = Kernel.room_projection(
        facts, controlled_context(surface.profile, frozenset({owner}), now), now)
    uncontrolled = Kernel.room_projection(facts, uncontrolled_context(surface.profile, now), now)
    personal = tuple(f.value for f in facts)

    assumptions = [
        "controlled renderer (Profile B demo); audience sample is a stated assumption, not a camera proof",
        "epoch 1, policy version 1, evidence valid, coverage assumed",
        "Profile A (public persistent host) would release the public projection only — even alone",
    ]
    return {
        "request_ref": receipt,
        "public": list(public),
        "room_assumed_alone": list(room),
        "room_uncontrolled_host": list(uncontrolled),
        "personal_full": list(personal),
        "assumptions": assumptions,
        "counterfactual_ok": None,  # filled by prove()
    }


def prove(surface, token: str, request_ref: str) -> dict:
    """Counterfactual privacy: change ONLY the hidden content; the public
    projection must not move — not in text, counts, or shape."""
    tenant, owner = surface._owner(token)
    receipt = surface._resolve_ref(token, request_ref)
    now = time.time()
    facts = surface.store.kernel.open_private(receipt, tenant, owner, True, now)
    baseline = Kernel.public_projection(facts)

    calendar = FixtureCalendar(surface.profile["sources"][0]["uri"])
    variants = {
        "therapy": calendar.with_title_swapped("evt-1", "Therapy session — Downtown"),
        "removed": calendar.with_title_swapped("evt-1", None),
    }
    results = {}
    for name, variant in variants.items():
        projection = Kernel.public_projection(_facts_for(variant))
        results[name] = {
            "public_projection": list(projection),
            "identical_to_baseline": projection == baseline,
        }
    ok = all(r["identical_to_baseline"] for r in results.values())
    return {"request_ref": receipt, "baseline_public": list(baseline),
            "variants": results, "counterfactual_ok": ok}
