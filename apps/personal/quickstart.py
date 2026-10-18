"""EARSHOT personal quickstart — one command, 90 seconds, stock Python.

    python3 apps/personal/quickstart.py [--dir .] [--html preview.html]

Runs the 7-step onboarding with safe defaults, mints the owner session,
prepares a day brief through the REAL kernel, renders the per-audience
preview, runs the counterfactual proof, and prints elapsed time.

Everything private stays private: fixture data only, demo-grade auth labeled.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # personal/ package + kernel bootstrap via personal/__init__

from personal import auth, preview as preview_mod, profile as profile_mod, report  # noqa: E402
from personal.inbox import PersonalSurface  # noqa: E402

BUDGET_SECONDS = 90


def main() -> int:
    parser = argparse.ArgumentParser(description="Earshot personal quickstart")
    parser.add_argument("--dir", default=".", help="working directory")
    parser.add_argument("--html", default="preview.html", help="write HTML preview report")
    parser.add_argument("--fresh", action="store_true",
                        help="wipe existing profile + server state before running")
    args = parser.parse_args()
    if args.fresh:
        for name in (profile_mod.PROFILE_FILENAME, "preview.html",
                     ".earshot-server.json"):
            path = os.path.join(args.dir, name)
            if os.path.exists(path):
                os.remove(path)
        print("Previous profile + server state wiped (--fresh).\n")
    elif os.path.exists(profile_mod.profile_path(args.dir)):
        print("Reusing existing profile (use --fresh to start over).\n")
    t0 = time.time()
    stamp = lambda: f"{time.time() - t0:5.1f}s"

    print("EARSHOT personal quickstart — fixture data, demo-grade auth\n")

    if os.path.exists(profile_mod.profile_path(args.dir)):
        prof = profile_mod.load_profile(args.dir)
        print(f"[{stamp()}] reusing existing profile for {prof['owner']}@{prof['tenant']}")
    else:
        print(f"[{stamp()}] onboarding (7 steps, safe defaults)…")
        prof, log = profile_mod.run_onboarding(args.dir)
        for line in log:
            print(f"           {line}")

    token = auth.mint_session(prof)
    profile_mod.save_profile(prof, args.dir)
    print(f"[{stamp()}] owner session minted ({auth.auth_label()})")

    surface = PersonalSurface(prof, args.dir)
    print(f"[{stamp()}] preparing day brief through the kernel…")
    brief = surface.prepare_day_brief(token)
    ref = brief["request_ref"]
    print(f"           receipt {ref[:16]}…  state={brief['request_state']} "
          f"— \"{brief['public_message']}\"")
    print(f"           plan digest {brief['plan_digest'][:16]}…")

    print(f"[{stamp()}] per-audience preview…")
    data = preview_mod.preview(surface, token, ref)
    print(f"           public:  {data['public'] or ['(nothing released)']}")
    print(f"           room:    {data['room_assumed_alone'] or ['(nothing released)']}")
    print(f"           personal:{data['personal_full']}")

    print(f"[{stamp()}] counterfactual proof (prenatal → therapy → removed)…")
    proof = preview_mod.prove(surface, token, ref)
    print("           public projection UNCHANGED across all variants ✓"
          if proof["counterfactual_ok"] else "           BOUNDARY FAILED ✗")

    with open(os.path.join(args.dir, args.html), "w", encoding="utf-8") as fh:
        fh.write(report.render(data, proof))
    print(f"[{stamp()}] report written to {args.html}")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s (budget {BUDGET_SECONDS}s) — "
          f"{'WITHIN BUDGET ✓' if elapsed < BUDGET_SECONDS else 'OVER BUDGET ✗'}")
    print("Next: python3 -m personal.cli --dir . inbox   # from apps/personal/")
    return 0 if elapsed < BUDGET_SECONDS and proof["counterfactual_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
