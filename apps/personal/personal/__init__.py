"""J5 personal surface: owner onboarding + private inbox over the EARSHOT kernel.

Stdlib only. The kernel is imported from the repo's packages/kernel/; nothing
here modifies it. Demo-grade auth and fixture sources are labeled as such at
every surface that uses them.
"""
import sys
from pathlib import Path


def _bootstrap() -> None:
    here = Path(__file__).resolve().parent                # apps/personal/personal
    apps_personal = here.parent                            # apps/personal
    repo_root = apps_personal.parent.parent
    kernel_dir = repo_root / "packages" / "kernel"
    for path in (kernel_dir, apps_personal):
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


_bootstrap()

__all__ = ["profile", "fixture_calendar", "auth", "planner", "inbox", "preview", "report", "cli"]
