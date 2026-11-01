"""Access modes (ADR-057): open preview now, authenticated sign-in dormant until activation.

Finding 89: the deployed console signed every visitor in as ``admin`` with a development
credential compiled into the public bundle. Two environment variables now decide who can hold
a token at all, and nothing about either one ships to the browser.

``SYNAPSE_ACCESS_MODE``
    ``open`` (the default) or ``authenticated``. Any other value -- an empty one included --
    refuses startup: ``api.main`` resolves it at import, so a misconfigured gateway exits
    non-zero instead of serving a guessed posture.
``SYNAPSE_OPEN_AUTHORITY``
    ``view`` (the default, least privilege) or ``act``. Read only in open mode; in
    authenticated mode every role comes from the operator store (``api.operators``).

In open mode the only credential the gateway issues is a *preview grant*: a one-hour access
token for the synthetic operator ``preview``, signed with the same RS256 keys, issuer and
audience as a sign-in token, so every existing ``RequireRole`` dependency judges it unchanged.
Its role is VIEWER (``view``) or OPS (``act``) and never higher, and it carries
``"preview": true`` so that activating authenticated mode retires every outstanding grant
(``api.middleware.jwt.verify_access_token``).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, TypeVar

from jose import jwt as jose_jwt
from pydantic import BaseModel, ConfigDict, model_validator
from synapse_common.auth import OperatorContext, Role, RS256Manager

if TYPE_CHECKING:
    from collections.abc import Mapping

ACCESS_MODE_ENV: Final = "SYNAPSE_ACCESS_MODE"
OPEN_AUTHORITY_ENV: Final = "SYNAPSE_OPEN_AUTHORITY"

#: The synthetic operator every preview grant names. Reserved: the operator store refuses it.
PREVIEW_SUBJECT: Final = "preview"
#: The claim that marks a preview grant. Sign-in tokens never carry it.
PREVIEW_CLAIM: Final = "preview"
#: How long one preview grant lives. The console asks for a fresh grant before it lapses.
PREVIEW_TTL: Final = timedelta(hours=1)


class AccessMode(StrEnum):
    """Who may hold a token: every visitor (``open``) or signed-in operators only."""

    OPEN = "open"
    AUTHENTICATED = "authenticated"


class OpenAuthority(StrEnum):
    """What an open-mode visitor may do: read (``view``) or also mutate (``act``)."""

    VIEW = "view"
    ACT = "act"


class AccessConfigError(RuntimeError):
    """An access setting the gateway refuses to start with."""


class AccessSettings(BaseModel):
    """The resolved access posture. ``authority`` is set exactly when the mode is open."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: AccessMode
    authority: OpenAuthority | None

    @model_validator(mode="after")
    def _authority_only_in_open_mode(self) -> AccessSettings:
        if (self.mode is AccessMode.OPEN) != (self.authority is not None):
            raise ValueError("authority is set exactly when the access mode is open")
        return self


_Choice = TypeVar("_Choice", bound=StrEnum)


def _choice(environ: Mapping[str, str], name: str, kind: type[_Choice], unset: _Choice) -> _Choice:
    """Read one enumerated setting; ``unset`` applies only when the variable is absent."""
    raw = environ.get(name)
    if raw is None:
        return unset
    try:
        return kind(raw.strip())
    except ValueError:
        allowed = " or ".join(repr(member.value) for member in kind)
        raise AccessConfigError(
            f"{name}={raw!r} is not an access setting this gateway knows. Set {allowed}, "
            f"or leave it unset for {unset.value!r}. Refusing to start (ADR-057)."
        ) from None


def load_access_settings(environ: Mapping[str, str]) -> AccessSettings:
    """Resolve the access posture from ``environ``; raise ``AccessConfigError`` on doubt.

    ``SYNAPSE_OPEN_AUTHORITY`` is not read at all in authenticated mode, so a stale value left
    behind at activation can neither widen nor block anything.
    """
    mode = _choice(environ, ACCESS_MODE_ENV, AccessMode, AccessMode.OPEN)
    if mode is AccessMode.AUTHENTICATED:
        return AccessSettings(mode=mode, authority=None)
    authority = _choice(environ, OPEN_AUTHORITY_ENV, OpenAuthority, OpenAuthority.VIEW)
    return AccessSettings(mode=mode, authority=authority)


def current_access_settings() -> AccessSettings:
    """FastAPI dependency: the posture this process runs under, read from its environment."""
    return load_access_settings(os.environ)


def preview_role(authority: OpenAuthority) -> Role:
    """``act`` grants OPS and ``view`` grants VIEWER; no authority reaches ENGINEER."""
    if authority is OpenAuthority.ACT:
        return Role.OPS
    return Role.VIEWER


def preview_ceiling(settings: AccessSettings) -> Role | None:
    """The highest role a preview grant may carry under ``settings``; ``None`` retires them all.

    Verification re-reads this on every request (``api.middleware.jwt.verify_access_token``),
    so lowering ``act`` to ``view`` caps the OPS grants already issued, and activating
    authenticated mode refuses every outstanding grant at once.
    """
    if settings.authority is None:
        return None
    return preview_role(settings.authority)


def sign_preview_access(mgr: RS256Manager, role: Role) -> tuple[str, datetime]:
    """Mint a preview grant with the sign-in token's keys, issuer, audience and claim set.

    The claims are exactly ``RS256Manager.sign_access``'s plus ``"preview": true``, with a
    one-hour lifetime. ``api/tests/test_access_modes.py::
    test_a_preview_grant_carries_every_sign_in_claim_plus_the_preview_marker`` pins that
    equality, so the two claim sets cannot drift apart. A role at or above ENGINEER is
    refused here, at the one place a preview token is signed.
    """
    if role.satisfies(Role.ENGINEER):
        raise ValueError(f"a preview grant never carries {role.value!r}; its ceiling is 'ops'")
    if not mgr.current_kid:
        raise RuntimeError("RS256Manager has no current signing key")
    issued = datetime.now(UTC)
    expires = issued + PREVIEW_TTL
    claims: dict[str, Any] = {
        "sub": PREVIEW_SUBJECT,
        "role": role.value,
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": mgr.issuer,
        "aud": mgr.audience,
        "type": "access",
        PREVIEW_CLAIM: True,
    }
    token: str = jose_jwt.encode(
        claims,
        mgr.private_keys[mgr.current_kid],
        algorithm="RS256",
        headers={"kid": mgr.current_kid},
    )
    return token, expires


def is_preview_grant(ctx: OperatorContext) -> bool:
    """True when a verified access token is a preview grant rather than an operator sign-in."""
    return ctx.raw_claims.get(PREVIEW_CLAIM) is True
