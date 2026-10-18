"""Personal-surface CLI.

    python3 -m personal.cli onboard [--interactive]
    python3 -m personal.cli inbox
    python3 -m personal.cli open <request_ref>
    python3 -m personal.cli preview <request_ref> [--html out.html]
    python3 -m personal.cli approve <request_ref>
    python3 -m personal.cli prove <request_ref>
    python3 -m personal.cli settings [--set busy_times=no]
"""
import argparse
import sys

from . import auth, preview as preview_mod, profile as profile_mod, report
from .inbox import PersonalSurface


def _surface(directory: str) -> PersonalSurface:
    return PersonalSurface(profile_mod.load_profile(directory), directory)


def _token(surface: PersonalSurface) -> str:
    session = surface.profile.get("session")
    if not session:
        raise SystemExit("No owner session. Run: python3 quickstart.py")
    return session["token"]


def cmd_onboard(args) -> None:
    _profile, log = profile_mod.run_onboarding(args.dir, interactive=args.interactive)
    print("\n".join(log))
    print(f"\nProfile written. {auth.auth_label()}.")


def cmd_inbox(args) -> None:
    surface = _surface(args.dir)
    requests = surface.list_requests(_token(surface))
    if not requests:
        print("Inbox empty. Prepare a day brief first: python3 quickstart.py")
        return
    for r in requests:
        print(f"{r['request_ref'][:16]}…  {r['request_state']} — {r['public_message']}")
    print(f"\n{auth.auth_label()}.")


def cmd_open(args) -> None:
    surface = _surface(args.dir)
    try:
        facts, plan = surface.open_request(_token(surface), args.request_ref)
    except PermissionError:
        raise SystemExit("Unavailable")
    print("— exact plan (owner only) —")
    for key, value in plan.items():
        print(f"  {key}: {value}")
    print("— sealed facts —")
    for f in facts:
        readers = "*" if "*" in f.label.readers else ",".join(sorted(f.label.readers))
        print(f"  [{readers}] {f.value}")
    print(f"\n{auth.auth_label()}.")


def cmd_preview(args) -> None:
    surface = _surface(args.dir)
    try:
        data = preview_mod.preview(surface, _token(surface), args.request_ref)
    except PermissionError:
        raise SystemExit("Unavailable")
    print("— what each recipient sees —")
    print(f"  public (anyone, any host): {data['public'] or ['(nothing released)']}")
    print(f"  room, uncontrolled host (Profile A): {data['room_uncontrolled_host'] or ['(nothing released)']}")
    print(f"  room, controlled host, 'alone' assumed (Profile B demo): {data['room_assumed_alone'] or ['(nothing released)']}")
    print(f"  personal (owner only): {data['personal_full']}")
    print("— assumptions (stated, not proven) —")
    for a in data["assumptions"]:
        print(f"  · {a}")
    if args.html:
        proof = preview_mod.prove(surface, _token(surface), args.request_ref)
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(report.render(data, proof))
        print(f"\nReport written to {args.html}")


def cmd_approve(args) -> None:
    surface = _surface(args.dir)
    try:
        result = surface.approve(_token(surface), args.request_ref)
    except PermissionError:
        raise SystemExit("Unavailable")
    print(f"Approved plan digest {result['approved_plan_digest'][:16]}…")
    print("Bound to this plan revision only — a changed plan needs a new approval.")


def cmd_settings(args) -> None:
    surface = _surface(args.dir)
    _token(surface)  # owner session required to view or change settings
    profile = surface.profile
    if args.set:
        field, _, value = args.set.partition("=")
        if field not in profile["declassify"] or value not in ("yes", "no"):
            raise SystemExit(f"usage: settings --set <field>=yes|no, field in {sorted(profile['declassify'])}")
        profile["declassify"][field] = (value == "yes")
        profile_mod.save_profile(profile, args.dir)
        print(f"declassify {field}: {value} (takes effect on the next prepared brief)")
        return
    print("— declassification choices (onboarding step 4; change with --set field=yes|no) —")
    for field, allowed in profile["declassify"].items():
        print(f"  {field}: {'yes' if allowed else 'no'}")
    print(f"  new data default: {profile['defaults']['new_data']}")
    print(f"  public acknowledgements: {'allowed' if profile['public_ack'] else 'disabled'}")


def cmd_prove(args) -> None:
    surface = _surface(args.dir)
    try:
        result = preview_mod.prove(surface, _token(surface), args.request_ref)
    except PermissionError:
        raise SystemExit("Unavailable")
    print("— counterfactual proof —")
    print(f"  baseline public: {result['baseline_public']}")
    for name, variant in result["variants"].items():
        mark = "identical ✓" if variant["identical_to_baseline"] else "CHANGED ✗"
        print(f"  hidden -> {name}: public projection {mark}")
    print("BOUNDARY HOLDS" if result["counterfactual_ok"] else "BOUNDARY FAILED")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="personal", description="Earshot personal surface")
    parser.add_argument("--dir", default=".", help="working directory for profile + server state")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("onboard"); p.add_argument("--interactive", action="store_true"); p.set_defaults(fn=cmd_onboard)
    p = sub.add_parser("inbox"); p.set_defaults(fn=cmd_inbox)
    p = sub.add_parser("open"); p.add_argument("request_ref"); p.set_defaults(fn=cmd_open)
    p = sub.add_parser("preview"); p.add_argument("request_ref"); p.add_argument("--html"); p.set_defaults(fn=cmd_preview)
    p = sub.add_parser("approve"); p.add_argument("request_ref"); p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("prove"); p.add_argument("request_ref"); p.set_defaults(fn=cmd_prove)
    p = sub.add_parser("settings"); p.add_argument("--set", metavar="field=yes|no"); p.set_defaults(fn=cmd_settings)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    sys.path.insert(0, ".")
    main()
