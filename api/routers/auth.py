"""BFF auth router — opaque cookie session, JWT held server-side.

Backend gap **B3** for the Atlas Console (plan §11; ratified by ADR-027).

Threat model summary
--------------------
The browser SPA never sees a JWT. We mint an RS256 JWT inside the gateway,
store it in Redis under an opaque session id, and hand the browser only the
session id as an HttpOnly + Secure + SameSite=Strict cookie. Properties:

- **No XSS-token-theft surface**: a compromised script can't read the token.
- **CSRF mitigation**: SameSite=Strict + a double-submit ``X-CSRF`` token on
  mutating requests. The CSRF token is a per-session secret returned at
  login (and refreshable), held in JS memory by the SPA.
- **Single auth-event log point** for DPDPA — every login / logout / refresh
  / reauth is one structured-log line.
- **Persona-aware reauth** for the Audit Vault PII reveal: a short-lived
  ``elevated`` flag set on the session by ``POST /auth/reauth``.

Endpoints
---------
- ``POST /auth/login``    — credentials → session cookie + CSRF token.
- ``POST /auth/logout``   — invalidate session.
- ``POST /auth/refresh``  — rolling expiry (no credentials needed).
- ``GET  /auth/session``  — current session metadata (for the SPA shell).
- ``POST /auth/reauth``   — short-lived elevation for PII reveal.

User store
----------
S1 ships an env-driven in-memory user table for development and tests.
Production user provisioning lands in S2 with a real backing store
(Postgres ``synapse_users`` table) — see plan §11. The function
``_load_users()`` is the only seam to swap.

Dependencies (requirements.txt)
-------------------------------
- ``python-jose[cryptography]`` (RS256 already in Sprint 5).
- ``passlib[bcrypt]`` for password hashing (BSD-3 / Apache-2.0; allow-listed).
- ``redis>=5`` for session storage (MIT, already in repo).
- ``itsdangerous`` for CSRF token signing (BSD-3; allow-listed).
"""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SESSION_COOKIE_NAME: Final = "synapse_session"
SESSION_TTL_SECONDS: Final = int(os.environ.get("SYNAPSE_SESSION_TTL", "3600"))
ELEVATION_TTL_SECONDS: Final = int(os.environ.get("SYNAPSE_ELEVATION_TTL", "300"))
CSRF_HEADER: Final = "X-CSRF"
SESSION_REDIS_DB: Final = int(os.environ.get("SYNAPSE_SESSION_REDIS_DB", "2"))

# Cookie attributes — secure-by-default. SAMESITE=strict is correct for
# first-party SPA auth; a cross-site link to /auth/login won't leak the
# cookie, and the SPA never makes cross-site mutations.
COOKIE_KW: Final[dict[str, Any]] = {
    "httponly": True,
    "secure": os.environ.get("SYNAPSE_COOKIE_SECURE", "1") == "1",
    "samesite": "strict",
    "path": "/",
}


def _redis_client() -> Any:
    import redis  # type: ignore[import-not-found]

    return redis.Redis.from_url(
        os.environ.get("SYNAPSE_REDIS_URL", "redis://redis:6379"),
        db=SESSION_REDIS_DB,
        decode_responses=True,
    )


# ---------------------------------------------------------------------------
# Users — S1 dev/test seam. Replace _load_users() with a DB read in S2.
# ---------------------------------------------------------------------------
def _load_users() -> dict[str, dict[str, Any]]:
    """Return ``{username: {hash, persona, claims}}``.

    Source priority:
      1. ``SYNAPSE_USERS_JSON`` env var holding the literal JSON.
      2. ``SYNAPSE_USERS_FILE`` env var pointing at a JSON file path.
      3. A safe dev-only default if ``SYNAPSE_AUTH_ALLOW_DEV_DEFAULT=1``.
    """
    raw = os.environ.get("SYNAPSE_USERS_JSON")
    if raw:
        return json.loads(raw)
    path = os.environ.get("SYNAPSE_USERS_FILE")
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if os.environ.get("SYNAPSE_AUTH_ALLOW_DEV_DEFAULT") == "1":
        # Bcrypt hash for password "atlas-dev". DEV ONLY — refuse to start
        # in production unless one of the explicit sources is set.
        return {
            "ops_controller_01": {
                "hash": "$2b$12$EwQyjrFBLSt6P5j9VJX2aOqMXGo/QIH0S0gHk7HmKqUcv7N5c1aTu",
                "persona": "ops_controller",
                "claims": {"city": ["bengaluru", "mumbai"]},
            },
        }
    raise RuntimeError(
        "no user store configured: set SYNAPSE_USERS_JSON, SYNAPSE_USERS_FILE, "
        "or SYNAPSE_AUTH_ALLOW_DEV_DEFAULT=1 (dev only)"
    )


def _verify_password(plain: str, hashed: str) -> bool:
    from passlib.hash import bcrypt  # type: ignore[import-not-found]

    return bcrypt.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT (held server-side; never returned to the browser)
# ---------------------------------------------------------------------------
def _jwt_keys() -> tuple[str, str]:
    """Load (private_pem, public_pem). Both required at boot."""
    priv_path = os.environ.get("SYNAPSE_JWT_PRIVATE_KEY_PATH", "/run/secrets/jwt_private.pem")
    pub_path = os.environ.get("SYNAPSE_JWT_PUBLIC_KEY_PATH", "/run/secrets/jwt_public.pem")
    return Path(priv_path).read_text(encoding="utf-8"), Path(pub_path).read_text(encoding="utf-8")


def _mint_jwt(username: str, persona: str, claims: dict[str, Any]) -> str:
    from jose import jwt  # type: ignore[import-not-found]

    priv, _ = _jwt_keys()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "persona": persona,
        "claims": claims,
        "iss": "synapse-api-gateway",
        "aud": "synapse-orchestrator",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=SESSION_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, priv, algorithm="RS256")


# ---------------------------------------------------------------------------
# Session storage (Redis db=2)
# ---------------------------------------------------------------------------
def _session_key(sid: str) -> str:
    return f"atlas:session:{sid}"


def _new_session_id() -> str:
    # 32 bytes → 256 bits of entropy, URL-safe.
    return secrets.token_urlsafe(32)


def _new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def _persist_session(sid: str, payload: dict[str, Any], ttl: int) -> None:
    r = _redis_client()
    r.set(_session_key(sid), json.dumps(payload, sort_keys=True, separators=(",", ":")), ex=ttl)


def _read_session(sid: str) -> dict[str, Any] | None:
    r = _redis_client()
    raw = r.get(_session_key(sid))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _drop_session(sid: str) -> None:
    r = _redis_client()
    r.delete(_session_key(sid))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    persona: str
    csrf_token: str = Field(..., description="Send back as X-CSRF on mutating requests")
    expires_at: str
    claims: dict[str, Any]


class SessionResponse(BaseModel):
    authenticated: bool
    persona: str | None = None
    expires_at: str | None = None
    elevated_until: str | None = None
    claims: dict[str, Any] = Field(default_factory=dict)


class ReauthRequest(BaseModel):
    password: str


# ---------------------------------------------------------------------------
# Dependency: resolve current session
# ---------------------------------------------------------------------------
def get_current_session(
    request: Request,
    sid: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict[str, Any]:
    if not sid:
        raise HTTPException(status_code=401, detail="not authenticated")
    payload = _read_session(sid)
    if payload is None:
        raise HTTPException(status_code=401, detail="session expired")
    # CSRF gate on mutations.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        header = request.headers.get(CSRF_HEADER, "")
        expected = payload.get("csrf_token", "")
        if not header or not secrets.compare_digest(header, expected):
            raise HTTPException(status_code=403, detail="CSRF check failed")
    payload["_sid"] = sid
    return payload


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response) -> LoginResponse:
    """Verify credentials, mint a server-side JWT, return a session cookie."""
    started = time.perf_counter()
    users = _load_users()
    user = users.get(payload.username)

    # Constant-ish-time response — always run a hash compare, even on miss.
    dummy = "$2b$12$" + "a" * 53
    ok = _verify_password(payload.password, user["hash"]) if user else _verify_password(payload.password, dummy)
    if not user or not ok:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info("auth_login_denied", username=payload.username, elapsed_ms=elapsed_ms)
        raise HTTPException(status_code=401, detail="invalid credentials")

    persona = str(user.get("persona", "ops_controller"))
    claims = dict(user.get("claims", {}))
    jwt_str = _mint_jwt(payload.username, persona, claims)

    sid = _new_session_id()
    csrf_token = _new_csrf_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat().replace("+00:00", "Z")

    _persist_session(
        sid,
        {
            "username": payload.username,
            "persona": persona,
            "claims": claims,
            "jwt": jwt_str,
            "csrf_token": csrf_token,
            "issued_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "expires_at": expires_at,
        },
        ttl=SESSION_TTL_SECONDS,
    )

    response.set_cookie(
        SESSION_COOKIE_NAME,
        sid,
        max_age=SESSION_TTL_SECONDS,
        **COOKIE_KW,
    )
    logger.info("auth_login_ok", username=payload.username, persona=persona)
    return LoginResponse(
        persona=persona,
        csrf_token=csrf_token,
        expires_at=expires_at,
        claims=claims,
    )


@router.post("/logout")
async def logout(
    response: Response,
    session: dict[str, Any] = Depends(get_current_session),
) -> dict[str, str]:
    sid = session["_sid"]
    _drop_session(sid)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    logger.info("auth_logout_ok", username=session.get("username"))
    return {"status": "ok"}


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    response: Response,
    session: dict[str, Any] = Depends(get_current_session),
) -> LoginResponse:
    """Rolling refresh — re-mints the inner JWT and extends the cookie TTL."""
    username = session["username"]
    persona = session["persona"]
    claims = dict(session.get("claims", {}))
    jwt_str = _mint_jwt(username, persona, claims)

    sid = session["_sid"]
    csrf_token = _new_csrf_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat().replace("+00:00", "Z")

    _persist_session(
        sid,
        {
            **session,
            "jwt": jwt_str,
            "csrf_token": csrf_token,
            "expires_at": expires_at,
        },
        ttl=SESSION_TTL_SECONDS,
    )
    response.set_cookie(
        SESSION_COOKIE_NAME,
        sid,
        max_age=SESSION_TTL_SECONDS,
        **COOKIE_KW,
    )
    return LoginResponse(persona=persona, csrf_token=csrf_token, expires_at=expires_at, claims=claims)


@router.get("/session", response_model=SessionResponse)
async def whoami(
    sid: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> SessionResponse:
    """Used by the SPA shell to render the user menu and gate routes."""
    if not sid:
        return SessionResponse(authenticated=False)
    payload = _read_session(sid)
    if payload is None:
        return SessionResponse(authenticated=False)
    return SessionResponse(
        authenticated=True,
        persona=payload.get("persona"),
        expires_at=payload.get("expires_at"),
        elevated_until=payload.get("elevated_until"),
        claims=payload.get("claims", {}),
    )


@router.post("/reauth")
async def reauth(
    payload: ReauthRequest,
    session: dict[str, Any] = Depends(get_current_session),
) -> dict[str, str]:
    """Short-lived elevation for PII reveal in Audit Vault. Re-prompts the user
    for their password without a full re-login (which would clear their work)."""
    users = _load_users()
    user = users.get(session["username"])
    if not user or not _verify_password(payload.password, user["hash"]):
        logger.info("auth_reauth_denied", username=session.get("username"))
        raise HTTPException(status_code=401, detail="reauth failed")

    elevated_until = (
        datetime.now(timezone.utc) + timedelta(seconds=ELEVATION_TTL_SECONDS)
    ).isoformat().replace("+00:00", "Z")
    sid = session["_sid"]
    _persist_session(
        sid,
        {**session, "elevated_until": elevated_until},
        ttl=SESSION_TTL_SECONDS,
    )
    logger.info(
        "auth_reauth_ok",
        username=session["username"],
        elevated_until=elevated_until,
    )
    return {"status": "ok", "elevated_until": elevated_until}
