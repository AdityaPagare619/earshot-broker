"""Personal surface: sealed inbox over the real kernel.

Listings expose receipt references only — never private content. Opening a
request requires the owner session; the kernel enforces tenant/owner binding
and answers everything else with the generic 'Unavailable'.
"""
import hashlib
import json
import os
import time

from kernel import Context, Fact, Kernel, Label

from . import auth
from . import planner
from .fixture_calendar import FixtureCalendar

SERVER_FILENAME = ".earshot-server.json"
PUBLIC_WEATHER = Fact("weather", "Rain is forecast after 17:00.", Label(frozenset({"*"})))


def _label_from_event(event: dict) -> Label:
    return Label(frozenset(event["readers"]), frozenset(event["topics"]))


def _fact_from_event(event: dict) -> Fact:
    return Fact(f"event:{event['id']}",
                f"{event['title']} {event['start']}",
                _label_from_event(event))


class ServerStore:
    """Demo server state: sealed capsules + private plans. File-backed so the
    CLI works across invocations. Access is ONLY via PersonalSurface, which
    enforces the owner session before touching private material."""

    def __init__(self, directory: str = "."):
        self.path = os.path.join(directory, SERVER_FILENAME)
        self.kernel = Kernel()
        self._plans: dict[str, dict] = {}
        self._approvals: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        for receipt, capsule in data.get("capsules", {}).items():
            facts = tuple(
                Fact(f["key"], f["value"],
                     Label(frozenset(f["readers"]), frozenset(f["topics"])))
                for f in capsule["facts"])
            self.kernel._capsules[receipt] = {
                "tenant": capsule["tenant"], "owner": capsule["owner"],
                "facts": facts, "expires": capsule["expires"], "revoked": False,
            }
            self.kernel._requests[(capsule["tenant"], capsule["owner"],
                                   capsule["request_key"])] = receipt
        self._plans = data.get("plans", {})
        self._approvals = data.get("approvals", {})

    def save(self) -> None:
        capsules = {}
        for receipt, c in self.kernel._capsules.items():
            key = next(k for k, v in self.kernel._requests.items() if v == receipt)
            capsules[receipt] = {
                "tenant": c["tenant"], "owner": c["owner"], "request_key": key[2],
                "expires": c["expires"],
                "facts": [{"key": f.key, "value": f.value,
                           "readers": sorted(f.label.readers),
                           "topics": sorted(f.label.topics)} for f in c["facts"]],
            }
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"capsules": capsules, "plans": self._plans,
                       "approvals": self._approvals}, fh, indent=2, sort_keys=True)


class PersonalSurface:
    """The owner's private surface. Every private method requires a session."""

    def __init__(self, profile: dict, directory: str = "."):
        self.profile = profile
        self.directory = directory
        self.store = ServerStore(directory)

    def _owner(self, token: str) -> tuple[str, str]:
        return auth.check_session(self.profile, token)

    def prepare_day_brief(self, token: str, date: str = "2026-10-19",
                          request_key: str = "quickstart-day-brief-v1") -> dict:
        tenant, owner = self._owner(token)
        calendar = FixtureCalendar(self.profile["sources"][0]["uri"])
        facts = (PUBLIC_WEATHER,) + tuple(_fact_from_event(e) for e in calendar.events())
        now = time.time()
        result = self.store.kernel.accept(tenant, owner, request_key, facts, now)
        receipt = result["receipt"]
        plan = planner.build_day_plan(calendar, owner)
        self.store._plans[receipt] = plan
        self.store.save()
        return {"request_ref": receipt, "request_state": result["state"],
                "public_message": result["public_message"],
                "plan_digest": _digest(plan)}

    def list_requests(self, token: str) -> list[dict]:
        tenant, owner = self._owner(token)
        out = []
        for (t, o, _key), receipt in self.store.kernel._requests.items():
            if (t, o) == (tenant, owner):
                out.append({"request_ref": receipt, "request_state": "accepted",
                            "public_message": "Your request is queued."})
        return out

    def _resolve_ref(self, token: str, ref_or_prefix: str) -> str:
        """Resolve a full receipt or a unique prefix. Ambiguous/unknown → PermissionError('Unavailable')."""
        tenant, owner = self._owner(token)
        matches = [receipt for (t, o, _key), receipt in self.store.kernel._requests.items()
                   if (t, o) == (tenant, owner) and receipt.startswith(ref_or_prefix)]
        if len(matches) != 1:
            raise PermissionError("Unavailable")
        return matches[0]

    def open_request(self, token: str, request_ref: str) -> tuple[tuple[Fact, ...], dict]:
        tenant, owner = self._owner(token)
        receipt = self._resolve_ref(token, request_ref)
        facts = self.store.kernel.open_private(receipt, tenant, owner, True, time.time())
        return facts, self.store._plans.get(receipt, {})

    def approve(self, token: str, request_ref: str) -> dict:
        tenant, owner = self._owner(token)
        receipt = self._resolve_ref(token, request_ref)
        self.store.kernel.open_private(receipt, tenant, owner, True, time.time())
        plan = self.store._plans.get(receipt)
        if plan is None:
            raise PermissionError("Unavailable")
        digest = _digest(plan)
        self.store._approvals[receipt] = {
            "plan_digest": digest, "owner": owner, "at": time.time(),
            "scope": "this plan revision only; a changed plan needs a new approval",
        }
        self.store.save()
        return {"request_ref": receipt, "approved_plan_digest": digest,
                "note": "bound to this plan digest, recipients and source versions"}

    def approval_valid(self, token: str, request_ref: str) -> bool:
        self._owner(token)
        receipt = self._resolve_ref(token, request_ref)
        approval = self.store._approvals.get(receipt)
        plan = self.store._plans.get(receipt)
        return bool(approval and plan and approval["plan_digest"] == _digest(plan))


def _digest(plan: dict) -> str:
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def controlled_context(profile: dict, audience: frozenset, now: float) -> Context:
    """Controlled-renderer context WITH explicit, stated assumptions."""
    return Context(
        tenant=profile["tenant"], principal=profile["owner"],
        audience=audience, epoch=1, observed_at=now,
        evidence_valid=True, coverage_assumed=True,
        controlled_renderer=True, policy_version=1)


def uncontrolled_context(profile: dict, now: float) -> Context:
    return Context(
        tenant=profile["tenant"], principal=profile["owner"],
        audience=frozenset({profile["owner"]}), epoch=1, observed_at=now,
        evidence_valid=True, coverage_assumed=True,
        controlled_renderer=False, policy_version=1)
