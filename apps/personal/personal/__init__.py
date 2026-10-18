"""J5 personal surface: owner onboarding + private inbox over the EARSHOT kernel.

Stdlib only. The kernel is imported from the repo's packages/kernel/; nothing
here modifies it. Demo-grade auth and fixture sources are labeled as such at
every surface that uses them.
"""
import os
import sys


def _bootstrap() -> None:
    here = os.path.dirname(os.path.abspath(__file__))      # apps/personal/personal
    apps_personal = os.path.dirname(here)                  # apps/personal
    repo_root = os.path.dirname(os.path.dirname(apps_personal))
    kernel_dir = os.path.join(repo_root, "packages", "kernel")
    for path in (kernel_dir, apps_personal):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


_bootstrap()

__all__ = ["profile", "fixture_calendar", "auth", "planner", "inbox", "preview", "report", "cli"]
