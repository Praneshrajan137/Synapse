"""FastAPI auth dependencies (RS256, role-gated).

Usage::

    from api.middleware.jwt import RequireRole
    from synapse_common.auth import Role

    @router.post("/override")
    async def override(..., op: OperatorContext = Depends(RequireRole(Role.OPS))):
        ...

The dependency reads ``Authorization: Bearer <token>``, verifies it with
``verify_access_token`` -- the shared ``RS256Manager`` singleton
(``api.middleware.jwt.manager()``) plus the access posture of ADR-057 -- and
enforces a minimum role. 401 on missing/invalid, 403 on insufficient role.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Header, HTTPException, status
from synapse_common.auth import (
    KeyPair,
    OperatorContext,
    Role,
    RS256Manager,
    TokenError,
    generate_keypair,
)

from api.access import current_access_settings, is_preview_grant, preview_ceiling

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@lru_cache(maxsize=1)
def manager() -> RS256Manager:
    """Process-wide RS256Manager singleton.

    In dev/test, an ephemeral keypair is generated on first call so login +
    verify work out of the box. In production, set
    ``SYNAPSE_JWT_PRIVATE_PEM`` / ``SYNAPSE_JWT_PUBLIC_PEM`` / ``SYNAPSE_JWT_KID``
    so every replica trusts the same keys.
    """
    mgr = RS256Manager(
        issuer=os.environ.get("SYNAPSE_JWT_ISSUER", "synapse-api-gateway"),
        audience=os.environ.get("SYNAPSE_JWT_AUDIENCE", "synapse-console"),
    )
    private_pem = os.environ.get("SYNAPSE_JWT_PRIVATE_PEM")
    public_pem = os.environ.get("SYNAPSE_JWT_PUBLIC_PEM")
    kid = os.environ.get("SYNAPSE_JWT_KID", "kid-dev")
    if private_pem and public_pem:
        kp = KeyPair(
            kid=kid,
            private_pem=private_pem.encode("utf-8"),
            public_pem=public_pem.encode("utf-8"),
        )
        mgr.add_keypair(kp)
    else:
        # Ephemeral dev keypair — fine for docker-compose / smoke tests.
        mgr.add_keypair(generate_keypair(kid))
    return mgr


def verify_access_token(token: str) -> OperatorContext:
    """Verify ``token`` as an access token under this process's access posture (ADR-057).

    A sign-in token verifies exactly as before. A preview grant (``api.access``) verifies
    only while the gateway runs open, and only up to the open authority's role, both re-read
    on every call: activating authenticated mode retires every outstanding grant at once,
    and lowering ``act`` to ``view`` caps the OPS grants already issued. Each refusal is a
    ``TokenError``, so every caller answers it the way it answers a bad signature: 401.
    """
    ctx = manager().verify(token, expected_type="access")
    if not is_preview_grant(ctx):
        return ctx
    ceiling = preview_ceiling(current_access_settings())
    if ceiling is None:
        raise TokenError("preview grants are retired: this gateway requires sign-in (ADR-057)")
    if not ceiling.satisfies(ctx.role):
        raise TokenError(
            f"preview grant role {ctx.role.value!r} exceeds the open authority's "
            f"{ceiling.value!r} (ADR-057)"
        )
    return ctx


def _require_token(authorization: Annotated[str | None, Header()] = None) -> OperatorContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": 'Bearer realm="synapse"'},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
            headers={"WWW-Authenticate": 'Bearer realm="synapse"'},
        ) from exc


def RequireRole(  # noqa: N802 — Depends helpers idiomatically capitalized
    minimum: Role,
) -> Callable[[OperatorContext], Awaitable[OperatorContext]]:
    """FastAPI dependency factory: requires at least ``minimum`` role."""

    async def _dep(
        ctx: Annotated[OperatorContext, Depends(_require_token)],
    ) -> OperatorContext:
        if not ctx.role.satisfies(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {ctx.role.value!r} insufficient; need {minimum.value!r}",
            )
        return ctx

    return _dep


# Convenience: a "current operator" dependency that any authenticated user satisfies.
CurrentOperator = RequireRole(Role.VIEWER)
