"""Owner onboarding state machine — dossier §4.1 as runnable steps.

Seven steps, each producing a recorded decision in the profile. Non-interactive
by default (safe guided defaults); --interactive prompts at every step.
Profile schema is versioned; v1 is frozen.
"""
import json
import time
from pathlib import Path

PROFILE_VERSION = 1
PROFILE_FILENAME = ".earshot-profile.json"

SAFE_DEFAULTS = {
    "tenant": "house-a",
    "owner": "priya",
    "source_uri": "fixture:calendar:priya",
    "new_data": "private",
    "public_ack": True,
    "declassify": {
        "existence": False,
        "busy_times": True,
        "leave_by": False,
        "reminders": False,
        "sounds": False,
    },
    "destination_kind": "local-inbox",
    "lock_screen_previews": False,
}


def profile_path(directory: str = ".") -> str:
    return str(Path(directory) / PROFILE_FILENAME)


def _ask(prompt: str, default: str) -> str:
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def _ask_yes_no(prompt: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def run_onboarding(directory: str = ".", interactive: bool = False,
                   defaults: dict | None = None) -> tuple[dict, list[str]]:
    """Run the 7 onboarding steps. Returns (profile, step_summaries)."""
    d = {**SAFE_DEFAULTS, **(defaults or {})}
    ask = _ask if interactive else (lambda p, df: df)
    ask_yn = _ask_yes_no if interactive else (lambda p, df: df)
    log: list[str] = []

    # 1 — connect a source with explicit scopes.
    source_uri = ask("Connect calendar source URI", d["source_uri"])
    if not source_uri.startswith("fixture:"):
        raise ValueError(
            f"Refusing non-fixture source {source_uri!r}: this demo build only "
            "connects fixture sources. Production needs OAuth/PKCE.")
    source = {
        "uri": source_uri,
        "provider": "fixture-calendar",
        "scopes": ["read:busy", "read:events"],
        "label_default": "private",
        "freshness": "manual-refresh",
    }
    log.append(f"1. source connected: {source_uri} (scopes: read:busy, read:events)")

    # 2 — private by default.
    new_data = ask("New data starts as (private/public)", d["new_data"])
    log.append(f"2. new data defaults to: {new_data}")

    # 3 — public acknowledgements acceptable?
    public_ack = ask_yn("Allow identical public acknowledgements for every request?", d["public_ack"])
    log.append(f"3. public acknowledgements: {'allowed (identical for all requests)' if public_ack else 'disabled'}")

    # 4 — per-field declassification, each a separate choice.
    decl: dict[str, bool] = {}
    for field, default in d["declassify"].items():
        decl[field] = ask_yn(f"May '{field}' be public?", default)
        log.append(f"4. declassify {field}: {'yes' if decl[field] else 'no'}")

    # 5 — register the personal destination; lock-screen previews off.
    lock_off = ask_yn("Disable sensitive lock-screen previews?", not d["lock_screen_previews"])
    destination = {"kind": d["destination_kind"], "lock_screen_previews": not lock_off}
    log.append(f"5. personal destination: {destination['kind']}; "
               f"lock-screen previews: {'on' if destination['lock_screen_previews'] else 'off'}")

    # 6 — scope explanation (recorded as acknowledged).
    log.append("6. scope acknowledged: EARSHOT protects its connected workflow, "
               "not all Alexa data")

    # 7 — runtime profiles explained (recorded as acknowledged).
    log.append("7. profiles acknowledged: A = public-persistent host (durable public "
               "facts only, even alone); B = controlled host demo (audience-scoped, "
               "leases, explicitly labeled)")

    profile = {
        "profile_version": PROFILE_VERSION,
        "tenant": d["tenant"],
        "owner": d["owner"],
        "created_at": time.time(),
        "sources": [source],
        "defaults": {"new_data": new_data},
        "public_ack": public_ack,
        "declassify": decl,
        "destination": destination,
        "session": None,
    }
    path = profile_path(directory)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, sort_keys=True)
    return profile, log


def load_profile(directory: str = ".") -> dict:
    path = profile_path(directory)
    if not Path(path).exists():
        raise FileNotFoundError(
            f"No profile at {path}. Run onboarding first: earshot personal-quickstart")
    with open(path, encoding="utf-8") as fh:
        profile = json.load(fh)
    if profile.get("profile_version") != PROFILE_VERSION:
        raise ValueError(
            f"Profile version {profile.get('profile_version')} != {PROFILE_VERSION}; "
            "migrate or delete the profile.")
    return profile


def save_profile(profile: dict, directory: str = ".") -> None:
    with open(profile_path(directory), "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, sort_keys=True)
