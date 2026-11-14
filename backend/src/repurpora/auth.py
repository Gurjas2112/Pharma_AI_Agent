"""Authentication for the Aegra agent server.

Verifies Supabase-issued access tokens (asymmetric keys, JWKS) sent by the
frontend as ``Authorization: Bearer <jwt>``. Threads are scoped per user via
authorization handlers so one user can never read another's sessions.

Referenced from ``aegra.json``: ``"auth": {"path": "./src/repurpora/auth.py:auth"}``
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import jwt
from langgraph_sdk import Auth

log = logging.getLogger(__name__)
auth = Auth()


@lru_cache(maxsize=1)
def _jwks() -> jwt.PyJWKClient:
    url = os.getenv("SUPABASE_JWKS_URL") or f"{os.getenv('SUPABASE_URL', '').rstrip('/')}/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def verify(token: str) -> dict:
    key = _jwks().get_signing_key_from_jwt(token)
    return jwt.decode(token, key.key, algorithms=["ES256", "RS256", "EdDSA"], audience="authenticated",
                      options={"require": ["exp", "sub"]}, leeway=30)


def user_from_bearer(authorization: str | None) -> str | None:
    """Helper for plain FastAPI routes (mock-api upload). Returns user id or raises."""
    if os.getenv("AUTH_DISABLED", "").lower() == "true":
        return None
    if not authorization or not authorization.lower().startswith("bearer "):
        from fastapi import HTTPException

        raise HTTPException(401, "missing bearer token")
    try:
        return verify(authorization.split(" ", 1)[1])["sub"]
    except Exception as exc:
        from fastapi import HTTPException

        raise HTTPException(401, f"invalid token: {type(exc).__name__}") from exc


@auth.authenticate
async def authenticate(headers: dict) -> dict:
    if os.getenv("AUTH_DISABLED", "").lower() == "true":
        return {"identity": "dev-user", "display_name": "Developer", "permissions": ["dev"]}
    raw = headers.get("authorization") or headers.get("Authorization") or headers.get(b"authorization")
    if isinstance(raw, bytes):
        raw = raw.decode()
    if not raw or not raw.lower().startswith("bearer "):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Missing bearer token")
    try:
        claims = verify(raw.split(" ", 1)[1])
    except Exception as exc:
        log.info("jwt rejected: %s", type(exc).__name__)
        raise Auth.exceptions.HTTPException(status_code=401, detail="Invalid or expired token") from exc
    return {
        "identity": claims["sub"],
        "display_name": claims.get("email", claims["sub"]),
        "email": claims.get("email"),
        "permissions": ["research"],
        "role": claims.get("role", "authenticated"),
    }


@auth.on
async def owner_scope(ctx: Auth.types.AuthContext, value: dict):
    """Stamp ownership on create; filter reads/searches to the caller's resources."""
    filters = {"owner": ctx.user.identity}
    if isinstance(value, dict):
        metadata = value.setdefault("metadata", {}) or {}
        metadata.update(filters)
    return filters
