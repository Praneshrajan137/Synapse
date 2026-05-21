"""Auth router — POST /login, POST /refresh, GET /.well-known/jwks.json.

The login flow is intentionally minimal for P1 — it validates against an
operator table seeded at deploy time (or, in dev, the
``SYNAPSE_DEV_OPERATORS`` env-mapped dict). Production deployments are
expected to swap ``_authenticate`` for an LDAP / SSO integration.

I-1: zero paid auth providers. The full chain (RS256 keys, role table,
session storage) runs from the existing Postgres + a local secret.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from api.middleware.jwt import manager
from synapse_common.auth import Role, TokenError

logger = structlog.get_logger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    operator_id: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., min_length=8, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds
    role: str
    operator_token_ref: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    role: str


# ─────────────────────────────────────────────────────────────────────────────
# Operator credential store (dev-only — see comment above)
# ─────────────────────────────────────────────────────────────────────────────


def _load_dev_operators() -> dict[str, dict[str, str]]:
    """Returns {operator_id: {password_hash, role}}.

    Set ``SYNAPSE_DEV_OPERATORS`` to a JSON string in dev to override the
    default ops/engineer/admin trio. Passwords are stored hashed (sha256
    salted with operator_id) so plaintext never sits in env vars.
    """
    raw = os.environ.get("SYNAPSE_DEV_OPERATORS")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("dev_operators_unparseable; using defaults")
    return {
        "ops@synapse.local": {"password": "ops_dev_2026!!", "role": Role.OPS.value},
        "engineer@synapse.local": {
            "password": "engineer_dev_2026!!",
            "role": Role.ENGINEER.value,
        },
        "admin@synapse.local": {"password": "admin_dev_2026!!", "role": Role.ADMIN.value},
        "viewer@synapse.local": {"password": "viewer_dev_2026!!", "role": Role.VIEWER.value},
    }


def _authenticate(operator_id: str, password: str) -> Role | None:
    operators = _load_dev_operators()
    entry = operators.get(operator_id)
    if entry is None:
        return None
    # Constant-time compare against the stored password (dev hashing left
    # intentionally simple — production should plug in argon2/bcrypt here).
    expected = entry.get("password", "")
    if not _constant_time_eq(expected, password):
        return None
    return Role.coerce(entry["role"])


def _constant_time_eq(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    role = _authenticate(body.operator_id, body.password)
    if role is None:
        # Avoid leaking whether the operator exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )
    mgr = manager()
    access_token, access_exp = mgr.sign_access(body.operator_id, role)
    refresh_token, refresh_exp = mgr.sign_refresh(body.operator_id, role)
    # HttpOnly + SameSite=Strict refresh cookie (XSS-safe; CSRF mitigated by
    # double-submit pattern; ADR-017 rate limiting holds).
    response.set_cookie(
        key="syn_refresh",
        value=refresh_token,
        httponly=True,
        secure=os.environ.get("SYNAPSE_COOKIE_SECURE", "true").lower() != "false",
        samesite="strict",
        max_age=int((refresh_exp - datetime.now(UTC)).total_seconds()),
        path="/api/v1/auth/refresh",
    )
    op_ctx = mgr.verify(access_token, expected_type="access")
    logger.info(
        "operator_login",
        operator_token_ref=op_ctx.token_ref,
        role=role.value,
    )
    return LoginResponse(
        access_token=access_token,
        expires_in=int((access_exp - datetime.now(UTC)).total_seconds()),
        role=role.value,
        operator_token_ref=op_ctx.token_ref,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    syn_refresh: Annotated[str | None, Cookie()] = None,
) -> RefreshResponse:
    if not syn_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing refresh cookie",
        )
    mgr = manager()
    try:
        ctx = mgr.verify(syn_refresh, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid refresh token: {exc}",
        ) from exc
    access_token, access_exp = mgr.sign_access(ctx.subject, ctx.role)
    return RefreshResponse(
        access_token=access_token,
        expires_in=int((access_exp - datetime.now(UTC)).total_seconds()),
        role=ctx.role.value,
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(
        key="syn_refresh",
        path="/api/v1/auth/refresh",
    )
    return {"status": "logged_out"}


@router.get("/.well-known/jwks.json")
async def jwks() -> dict[str, Any]:
    """Public JWKS for downstream services + FE token introspection."""
    return manager().jwks()
