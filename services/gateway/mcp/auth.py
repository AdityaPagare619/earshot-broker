"""Development authentication for the EARSHOT MCP gateway (J3).

Honest, explicitly non-production: bearer tokens bound server-side to
(tenant, owner). Tool arguments NEVER carry identity — it comes only from the
verified token. Production would follow the Alexa QuickStart OAuth 2.1 + PKCE
profile (dossier §10.4); no IdP exists in competition scope, and a mock OAuth
flow would be security theater. Labeled accordingly everywhere.
"""
from __future__ import annotations

import json
import os
import secrets


class AuthError(Exception):
    """Transport-level auth failure. Carries no private data."""


class AuthRegistry:
    """Token -> (tenant, owner) binding. In-memory; restart reseeds."""

    def __init__(self) -> None:
        self._tokens: dict[str, tuple[str, str]] = {}
        # Fixture principals. The owner/non-owner split exists so
        # cross-tenant negative tests are real, not asserted.
        self.owner_token = self.add("house-a", "priya")      # the owner
        self.member_token = self.add("house-a", "ravi")      # household, not owner
        self.other_tenant_token = self.add("house-b", "meera")  # other tenant
        # Optional operator-supplied tokens: {"token": [tenant, owner], ...}
        extra = os.environ.get("EARSHOT_DEV_TOKENS")
        if extra:
            try:
                for tok, pair in json.loads(extra).items():
                    self._tokens[str(tok)] = (str(pair[0]), str(pair[1]))
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise AuthError("unparseable EARSHOT_DEV_TOKENS") from exc

    def add(self, tenant: str, owner: str) -> str:
        token = "esh_dev_" + secrets.token_urlsafe(32)
        self._tokens[token] = (tenant, owner)
        return token

    def resolve(self, authorization_header: str | None) -> tuple[str, str]:
        """Return (tenant, owner) or raise AuthError. Nothing secret leaks."""
        if not authorization_header:
            raise AuthError("missing Authorization header: expected 'Bearer <dev-token>'")
        scheme, _, value = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not value:
            raise AuthError("malformed Authorization header: expected 'Bearer <dev-token>'")
        binding = self._tokens.get(value)
        if binding is None:
            raise AuthError("unknown or revoked token")
        return binding

    def describe_for_operator(self) -> str:
        """Dev-only token listing. Printed to stderr at startup, never logged."""
        lines = ["EARSHOT dev tokens (non-production, restart reseeds):"]
        for tok, (tenant, owner) in self._tokens.items():
            if not tok.startswith("esh_dev_"):
                continue
            lines.append(f"  tenant={tenant} owner={owner} token={tok}")
        return "\n".join(lines)
