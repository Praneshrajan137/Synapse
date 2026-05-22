"""FastAPI auth dependencies (RS256, role-gated).

Usage::

    from api.middleware.jwt import RequireRole
    from synapse_common.auth import Role

    @router.post("/override")
    async def override(..., op: OperatorContext = Depends(RequireRole(Role.OPS))):
        ...

The dependency reads ``Authorization: Bearer <token>``, verifies via the
shared ``RS256Manager`` singleton (``api.middleware.jwt.manager()``), and
enforces a minimum role. 401 on missing/invalid, 403 on insufficient role.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from synapse_common.auth import (
    KeyPair,
    OperatorContext,
    RS256Manager,
    Role,
    TokenError,
    generate_keypair,
)


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


def _require_token(authorization: Annotated[str | None, Header()] = None) -> OperatorContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": 'Bearer realm="synapse"'},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return manager().verify(token, expected_type="access")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
            headers={"WWW-Authenticate": 'Bearer realm="synapse"'},
        ) from exc


def RequireRole(minimum: Role):  # noqa: N802 — Depends helpers idiomatically capitalized
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
