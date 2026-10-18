"""Demo-grade owner sessions.

FIXTURE-GRADE AUTH — every surface that uses this labels it as such.
Production needs real OAuth/PKCE with a verified token; this module exists so
the personal surface can demonstrate owner binding (tenant + owner + session)
against the kernel's open_private without pretending to be production auth.

A device class of "phone" is not authorization: a session requires the token
from the profile, i.e. deliberate local possession, not just a device type.
"""
import secrets
import time

SESSION_TTL_SECONDS = 3600


def mint_session(profile: dict) -> str:
    token = "demo-" + secrets.token_urlsafe(24)
    profile["session"] = {
        "token": token,
        "owner": profile["owner"],
        "tenant": profile["tenant"],
        "minted_at": time.time(),
        "grade": "demo-token (fixture-grade — production needs OAuth/PKCE)",
    }
    return token


def check_session(profile: dict, token: str) -> tuple[str, str]:
    """Validate the session. Returns (tenant, owner) or raises PermissionError."""
    session = profile.get("session")
    if not session or session.get("token") != token:
        raise PermissionError("Unavailable")
    if time.time() - session["minted_at"] > SESSION_TTL_SECONDS:
        raise PermissionError("Unavailable")
    return session["tenant"], session["owner"]


def auth_label() -> str:
    return "auth: demo-token (fixture-grade — production needs OAuth/PKCE)"
