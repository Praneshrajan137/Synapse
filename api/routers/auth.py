"""Auth router (ADR-057): the access posture, preview grants, and sign-in kept dormant.

Finding 89: the console used to sign every visitor in as ``admin`` against a plaintext
operator table compiled into this module, with the matching password compiled into the public
frontend bundle. The posture is now an explicit setting (``api.access``):

``GET /mode``
    Public. ``{"mode": "open", "authority": "view" | "act"}`` or
    ``{"mode": "authenticated", "authority": null}``. It carries no secret; the console reads
    it on boot to decide how to enter.
``POST /preview``
    Public while the gateway runs open: a one-hour grant for the synthetic operator
    ``preview`` at VIEWER (``view``) or OPS (``act``), never higher. In authenticated mode the
    route does not exist (404).
``POST /login``
    Authenticated mode only, against the operator store (``api.operators``): scrypt entries
    in ``SYNAPSE_OPERATORS_JSON``, or the plaintext development table behind
    ``SYNAPSE_DEV_OPERATORS_INSECURE=1``. Derivations run in worker threads, two at a time; a
    sign-in waits for a slot on the event loop and gets 503 after five seconds. In open mode
    sign-in is dormant: a 404 that says so, answered by a route dependency before FastAPI
    validates the body (``sign_in_is_active``).
``POST /refresh``
    Authenticated mode only, and dormant in open mode the same way. A preview grant carries
    no refresh token; the console asks for a fresh grant instead.
``POST /logout`` and ``GET /.well-known/jwks.json`` are unchanged.

I-1: zero paid auth providers. RS256 keys and the standard library's scrypt, nothing else.
"""

from __future__ import annotations

import functools
import math
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, Final

import structlog
from anyio import CapacityLimiter, move_on_after, to_thread
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from synapse_common.auth import Role, TokenError

from api.access import (
    AccessMode,
    AccessSettings,
    OpenAuthority,
    current_access_settings,
    preview_role,
    sign_preview_access,
)
from api.middleware.jwt import manager
from api.operators import DERIVATION_SLOTS, OperatorConfigError, operator_source

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)
router = APIRouter()

#: The 404 detail of ``/login`` and ``/refresh`` while the console runs open.
SIGN_IN_DORMANT: Final = (
    "sign-in is not activated: this console runs in open preview access (ADR-057)"
)
#: The 404 detail of ``/preview`` once authenticated mode is active.
PREVIEW_UNAVAILABLE: Final = (
    "preview access is not available: this gateway requires sign-in (ADR-057)"
)
#: How long one sign-in waits on the event loop for a derivation slot before it gets 503.
DERIVATION_WAIT_SECONDS: Final = 5.0
#: The 503 detail of a sign-in that found every derivation slot busy for the whole wait.
SIGN_IN_BUSY: Final = "sign-in is busy: try again in a few seconds"

Settings = Annotated[AccessSettings, Depends(current_access_settings)]


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


class AccessModeResponse(BaseModel):
    """The posture ``GET /mode`` publishes. ``authority`` is ``None`` exactly when signed-in."""

    mode: AccessMode
    authority: OpenAuthority | None


class PreviewResponse(BaseModel):
    """A preview grant, shaped like a sign-in response so the console stores it the same way."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds
    role: str
    operator_token_ref: str
    authority: OpenAuthority


def _seconds_until(moment: datetime) -> int:
    return int((moment - datetime.now(UTC)).total_seconds())


# ─────────────────────────────────────────────────────────────────────────────
# Sign-in plumbing: the dormant 404, and derivations off the event loop
# ─────────────────────────────────────────────────────────────────────────────


async def sign_in_is_active(settings: Settings) -> None:
    """Route dependency of ``/login`` and ``/refresh``: in open mode, the dormant 404.

    FastAPI resolves a route's dependencies before it validates the request body, so open mode
    answers every body FastAPI can decode with this same 404, never with a 422 that names the
    sign-in fields. (A body sent as JSON that does not parse is refused earlier, while FastAPI
    decodes it, with a 422 that names no field.)
    """
    if settings.mode is AccessMode.OPEN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SIGN_IN_DORMANT)


@functools.cache
def derivation_limiter() -> CapacityLimiter:
    """The gateway's derivation slots. Built on first use, inside the running event loop."""
    return CapacityLimiter(DERIVATION_SLOTS)


async def verify_with_bounded_wait(
    verify: Callable[[str, str], Role | None],
    operator_id: str,
    password: str,
    limiter: CapacityLimiter,
    wait_seconds: float,
) -> Role | None:
    """Run ``verify`` in a worker thread once ``limiter`` admits it, or answer 503.

    The wait for a slot happens on the event loop, so a queued sign-in holds no worker thread
    and cannot starve the threadpool that every sync dependency shares (``_require_token``,
    ``current_access_settings``). A sign-in still waiting after ``wait_seconds`` gets 503 with
    ``Retry-After``. A derivation that has started is never interrupted: anyio runs its worker
    thread shielded from cancellation, so its slot is always returned.
    """
    with move_on_after(wait_seconds):
        return await to_thread.run_sync(verify, operator_id, password, limiter=limiter)
    logger.warning("sign_in_busy", wait_seconds=wait_seconds, slots=limiter.total_tokens)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=SIGN_IN_BUSY,
        headers={"Retry-After": str(math.ceil(wait_seconds))},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/mode", response_model=AccessModeResponse)
async def access_mode(settings: Settings) -> AccessModeResponse:
    """Public: the access posture this gateway runs under. It names no operator or secret."""
    return AccessModeResponse(mode=settings.mode, authority=settings.authority)


@router.post("/preview", response_model=PreviewResponse)
async def preview(settings: Settings) -> PreviewResponse:
    """Public while open: a one-hour grant at the open authority's role (VIEWER or OPS)."""
    authority = settings.authority
    if settings.mode is not AccessMode.OPEN or authority is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PREVIEW_UNAVAILABLE)
    role = preview_role(authority)
    mgr = manager()
    access_token, expires = sign_preview_access(mgr, role)
    grant = mgr.verify(access_token, expected_type="access")
    logger.info(
        "preview_grant_issued",
        role=role.value,
        authority=authority.value,
        operator_token_ref=grant.token_ref,
    )
    return PreviewResponse(
        access_token=access_token,
        expires_in=_seconds_until(expires),
        role=role.value,
        operator_token_ref=grant.token_ref,
        authority=authority,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(sign_in_is_active)],
)
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    try:
        source = operator_source(os.environ)
    except OperatorConfigError as exc:
        # api.main refuses to start with this configuration, so reaching it means the
        # environment changed under a running process. Fail closed, never open.
        logger.error("operator_store_unavailable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="operator store unavailable",
        ) from None
    # scrypt is deliberately slow: derive in a worker thread, two at a time, and wait for a
    # slot on the event loop, so queued sign-ins never hold the shared threadpool.
    role = await verify_with_bounded_wait(
        source.authenticate,
        body.operator_id,
        body.password,
        derivation_limiter(),
        DERIVATION_WAIT_SECONDS,
    )
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
        max_age=_seconds_until(refresh_exp),
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
        expires_in=_seconds_until(access_exp),
        role=role.value,
        operator_token_ref=op_ctx.token_ref,
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    dependencies=[Depends(sign_in_is_active)],
)
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
        expires_in=_seconds_until(access_exp),
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
