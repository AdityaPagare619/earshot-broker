"""Personal-surface CLI (installed as `earshot-personal`).

    earshot personal onboard [--interactive]
    earshot personal inbox
    earshot personal open <request_ref>
    earshot personal preview <request_ref> [--html out.html]
    earshot personal approve <request_ref>
    earshot personal prove <request_ref>
    earshot personal settings [--set busy_times=no]

The owner's private window into EARSHOT. Every private command requires the
owner session minted by `earshot personal-quickstart`.
"""
import argparse
import sys

from earshot.wincompat import ensure_utf8_stdout

from . import auth, preview as preview_mod, profile as profile_mod, report
from .inbox import PersonalSurface


def _surface(directory: str) -> PersonalSurface:
    return PersonalSurface(profile_mod.load_profile(directory), directory)


def _token(surface: PersonalSurface) -> str:
    session = surface.profile.get("session")
    if not session:
        raise SystemExit("No owner session. Run: earshot personal-quickstart")
    return session["token"]


def cmd_onboard(args) -> None:
    _profile, log = profile_mod.run_onboarding(args.dir, interactive=args.interactive)
    print("\n".join(log))
    print(f"\nProfile written. {auth.auth_label()}.")


def cmd_inbox(args) -> None:
    surface = _surface(args.dir)
    requests = surface.list_requests(_token(surface))
    if not requests:
        print("Inbox empty. Prepare a day brief first: earshot personal-quickstart")
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
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(
        prog="earshot-personal",
        description="Earshot personal surface — the owner's private window "
                    "(onboard, inbox, open, preview, approve, prove, settings)",
    )
    parser.add_argument("--dir", default=".", help="working directory for profile + server state")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    p = sub.add_parser("onboard", help="run the 7-step owner onboarding")
    p.add_argument("--interactive", action="store_true",
                   help="prompt at every step instead of using safe defaults")
    p.set_defaults(fn=cmd_onboard)
    p = sub.add_parser("inbox", help="list sealed requests (receipts only, never content)")
    p.set_defaults(fn=cmd_inbox)
    p = sub.add_parser("open", help="show the exact plan + sealed facts (owner only)")
    p.add_argument("request_ref", help="request receipt or its unique prefix")
    p.set_defaults(fn=cmd_open)
    p = sub.add_parser("preview", help="show what each audience would hear")
    p.add_argument("request_ref", help="request receipt or its unique prefix")
    p.add_argument("--html", metavar="FILE", help="write the HTML trust report to FILE")
    p.set_defaults(fn=cmd_preview)
    p = sub.add_parser("approve", help="approve a plan digest (bound to this plan revision)")
    p.add_argument("request_ref", help="request receipt or its unique prefix")
    p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("prove", help="counterfactual proof: hidden content changes, public projection must not")
    p.add_argument("request_ref", help="request receipt or its unique prefix")
    p.set_defaults(fn=cmd_prove)
    p = sub.add_parser("settings", help="view or change declassification choices")
    p.add_argument("--set", metavar="field=yes|no", help="e.g. --set busy_times=no")
    p.set_defaults(fn=cmd_settings)

    args = parser.parse_args(argv)
    try:
        args.fn(args)
    except FileNotFoundError as e:
        # No profile yet — the one-line nudge, not a traceback.
        print(f"earshot-personal: {e}", file=sys.stderr)
        raise SystemExit(2)
    except ValueError as e:
        # Profile version mismatch or bad onboarding input.
        print(f"earshot-personal: {e}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
