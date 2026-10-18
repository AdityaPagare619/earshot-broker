"""EARSHOT personal surface: owner onboarding + private inbox over the kernel.

Stdlib only. The kernel is imported as `earshot.kernel`; nothing here modifies
it. Demo-grade auth and fixture sources are labeled as such at every surface
that uses them.

Installed as part of the `earshot` package (`earshot.personal`). Entry points:
`earshot-personal` and `earshot personal ...` / `earshot personal-quickstart`.
"""

__all__ = ["profile", "fixture_calendar", "auth", "planner", "inbox", "preview", "report", "cli"]
