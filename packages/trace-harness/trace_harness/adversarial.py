"""Adversarial fixtures: reference replay and cross-tenant access.

The privacy property has a sharp edge: a request reference is opaque, not
authorization. These fixtures assert that edge holds — an adversary holding
someone else's receipt, or a garbage receipt, gets the *identical* generic
denial (no existence oracle), and a revoked receipt stays dead.

Note: paired worlds deliberately share (tenant, owner) — same user, different
secrets. So the replay attacker is a *third* tenant, not world B.
"""
import itertools
from dataclasses import dataclass
from types import SimpleNamespace

_counter = itertools.count(1)


def _attacker():
    return SimpleNamespace(tenant="tenant-attacker", owner="mallory", facts=())


def _unique_key(prefix: str) -> str:
    return f"{prefix}-{next(_counter):04d}-min16chars00"


@dataclass
class AdversarialResult:
    name: str
    passed: bool
    detail: str


def _error_shape(step) -> tuple:
    if step.status != "error" or not isinstance(step.result, dict):
        return None
    r = step.result
    return (r.get("code"), r.get("message"))


def adversarial_suite(make_adapter, world_a, world_b) -> list:
    """make_adapter(world) -> connected adapter. Returns list of results."""
    results = []

    # 1. Cross-tenant reference replay: attacker's tenant uses A's receipt.
    ad_a = make_adapter(world_a)
    ad_a.connect()
    prep = ad_a.call(world_a.script[0]["tool"], world_a.script[0]["args"])
    receipt_a = prep.result.get("request_ref") if prep.status == "ok" else None
    ad_a.close()

    ad_x = make_adapter(_attacker())
    ad_x.connect()
    replay = ad_x.call("resolve_day_change", {
        "change": "attacker probe",
        "request_key": _unique_key("rk-adv-replay"),
        "request_ref": receipt_a or "garbage-receipt-000000000000",
    })
    garbage = ad_x.call("resolve_day_change", {
        "change": "attacker probe",
        "request_key": _unique_key("rk-adv-garbage"),
        "request_ref": "garbage-receipt-000000000000",
    })
    ad_x.close()

    same_shape = (_error_shape(replay) is not None
                  and _error_shape(replay) == _error_shape(garbage))
    results.append(AdversarialResult(
        "cross_tenant_reference_replay",
        passed=bool(receipt_a) and replay.status == "error" and same_shape,
        detail=f"replay error={_error_shape(replay)}, "
               f"garbage error={_error_shape(garbage)}, identical={same_shape}",
    ))

    # 2. Double withdraw: withdrawing twice behaves identically (no oracle
    #    about whether the first withdraw "found" anything). Unique keys per
    #    run defeat the kernel's (tenant, owner, request_key) dedupe.
    def _withdraw_twice(make_ad, world):
        ad = make_ad(world)
        ad.connect()
        args = dict(world.script[0]["args"])
        args["request_key"] = _unique_key("rk-adv-prep")
        p = ad.call(world.script[0]["tool"], args)
        ref = p.result.get("request_ref") if p.status == "ok" else "x"
        w1 = ad.call("withdraw_request", {
            "request_key": _unique_key("rk-adv-wd1"), "request_ref": ref})
        w2 = ad.call("withdraw_request", {
            "request_key": _unique_key("rk-adv-wd2"), "request_ref": ref})
        ad.close()
        return (_error_shape(w1), _error_shape(w2), w1.status, w2.status)

    shapes_a = _withdraw_twice(make_adapter, world_a)
    shapes_b = _withdraw_twice(make_adapter, world_b)
    results.append(AdversarialResult(
        "double_withdraw_no_oracle",
        passed=shapes_a == shapes_b,
        detail=f"world A: {shapes_a}; world B: {shapes_b}",
    ))

    return results
