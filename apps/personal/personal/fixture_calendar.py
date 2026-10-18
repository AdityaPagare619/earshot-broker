"""Fixture calendar adapter — implements the blueprint §3 adapter contract.

A fixture *source*, not a mock: it declares provider identity, scopes, schemas,
ownership, field labels with private defaults, and freshness semantics, exactly
as a production adapter must. It only serves fixture data and refuses to stand
in for a real provider.
"""
from earshot.kernel import Fact, Label

PROVIDER_ID = "fixture-calendar"
ALLOWLIST = ("fixture://calendar",)
SCOPES = ("read:busy", "read:events")

# Fixture day: one private appointment, one public lunch. Labeled, not secret.
FIXTURE_EVENTS = (
    {
        "id": "evt-1",
        "title": "Prenatal checkup — City Clinic",
        "start": "2026-10-19T15:00:00",
        "end": "2026-10-19T16:00:00",
        "readers": ("priya",),
        "topics": ("health",),
        "owner": "priya",
        "subjects": ("priya",),
    },
    {
        "id": "evt-2",
        "title": "Team lunch",
        "start": "2026-10-19T12:30:00",
        "end": "2026-10-19T13:30:00",
        "readers": ("*",),
        "topics": ("social",),
        "owner": "priya",
        "subjects": ("priya",),
    },
)


def contract() -> dict:
    """The §3 adapter contract, as declared data (auditable, not prose)."""
    return {
        "provider": PROVIDER_ID,
        "endpoint_allowlist": list(ALLOWLIST),
        "scopes": list(SCOPES),
        "record_schema": ["id", "title", "start", "end", "owner", "subjects"],
        "field_labels": {
            "title": "per-event label; private by default",
            "start/end": "busy-interval label; declassifiable per onboarding step 4",
        },
        "private_defaults": True,
        "transformations": ["expand_day_range", "busy_intervals"],
        "external_recipients_of_mutation": [],
        "idempotency": "event ids are stable; reads are side-effect free",
        "freshness": "manual-refresh; no deletion propagation in fixture",
        "fixture": True,
    }


class FixtureCalendar:
    """Read-only fixture calendar. Refuses to impersonate a real provider."""

    def __init__(self, source_uri: str):
        if not source_uri.startswith("fixture:"):
            raise ValueError(
                f"FixtureCalendar refuses {source_uri!r}: not a fixture source.")
        self.source_uri = source_uri

    def events(self) -> tuple[dict, ...]:
        return self._events_or_default()

    def busy_intervals(self) -> tuple[tuple[str, str], ...]:
        return tuple((e["start"], e["end"]) for e in self._events_or_default())

    def to_facts(self, owner: str) -> tuple[Fact, ...]:
        facts = []
        for e in self._events_or_default():
            label = Label(frozenset(e["readers"]), frozenset(e["topics"]))
            facts.append(Fact(f"event:{e['id']}", f"{e['title']} {e['start']}", label))
        return tuple(facts)

    def with_title_swapped(self, event_id: str, new_title: str | None) -> "FixtureCalendar":
        """Counterfactual variant: same labels, different (or removed) secret.

        Used by the prove-it check: the public projection must not move when
        only the private *content* changes.
        """
        clone = FixtureCalendar.__new__(FixtureCalendar)
        clone.source_uri = self.source_uri + "#counterfactual"
        events = []
        for e in FIXTURE_EVENTS:
            e2 = dict(e)
            if e["id"] == event_id:
                if new_title is None:
                    continue  # removed entirely
                e2["title"] = new_title
            events.append(e2)
        clone._events = tuple(events)
        return clone

    def _events_or_default(self) -> tuple[dict, ...]:
        return getattr(self, "_events", FIXTURE_EVENTS)
