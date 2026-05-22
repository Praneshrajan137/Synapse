"""RS256 JWT manager with kid-based key rotation.

Extracted from ``tests/security/test_jwt_rs256.py`` (Sprint 5 hardening work)
and promoted to a shared package so every service uses the same verifier.
Key rotation works because the verifier accepts any ``kid`` it knows about
while the signer always uses ``current_kid`` — in-flight tokens remain
valid for one TTL after rotation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, ClassVar

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt
from jose.exceptions import JWTError


class Role(str, Enum):
    """RBAC roles. The integer ``rank`` lets dependencies declare a minimum."""

    VIEWER = "viewer"
    OPS = "ops"
    ENGINEER = "engineer"
    ADMIN = "admin"

    _RANK: ClassVar[dict[str, int]]

    @property
    def rank(self) -> int:
        return self._RANK[self.value]

    @classmethod
    def coerce(cls, value: str | Role) -> Role:
        if isinstance(value, cls):
            return value
        return cls(value)

    def satisfies(self, minimum: Role) -> bool:
        return self.rank >= minimum.rank


Role._RANK = {
    Role.VIEWER.value: 10,
    Role.OPS.value: 20,
    Role.ENGINEER.value: 30,
    Role.ADMIN.value: 40,
}


class TokenError(Exception):
    """Raised when an inbound token is malformed, expired, or unknown-kid."""


@dataclass(frozen=True)
class OperatorContext:
    """Verified claims of an authenticated operator.

    ``token_ref`` is a short hash suitable for audit display (FE-INV-019);
    the FE never sees the raw subject.
    """

    subject: str
    role: Role
    token_ref: str
    issued_at: datetime
    expires_at: datetime
    raw_claims: dict[str, Any]


@dataclass
class KeyPair:
    kid: str
    private_pem: bytes
    public_pem: bytes


def generate_keypair(kid: str, key_size: int = 2048) -> KeyPair:
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return KeyPair(kid=kid, private_pem=private_pem, public_pem=public_pem)


@dataclass
class RS256Manager:
    """RS256 JWT manager with kid-based key rotation.

    Mirrors the design verified by ``tests/security/test_jwt_rs256.py``.
    """

    issuer: str = "synapse-api-gateway"
    audience: str = "synapse-console"
    access_ttl: timedelta = timedelta(minutes=15)
    refresh_ttl: timedelta = timedelta(hours=12)
    private_keys: dict[str, bytes] = field(default_factory=dict)
    public_keys: dict[str, bytes] = field(default_factory=dict)
    current_kid: str = ""

    def add_keypair(self, kp: KeyPair, *, make_current: bool = True) -> None:
        self.private_keys[kp.kid] = kp.private_pem
        self.public_keys[kp.kid] = kp.public_pem
        if make_current:
            self.current_kid = kp.kid

    def retire_kid(self, kid: str) -> None:
        self.public_keys.pop(kid, None)
        self.private_keys.pop(kid, None)

    def jwks(self) -> dict[str, Any]:
        """Public JWKS document (FE consumes this at /.well-known/jwks.json)."""
        from base64 import urlsafe_b64encode

        keys: list[dict[str, Any]] = []
        for kid, pem in self.public_keys.items():
            pub = serialization.load_pem_public_key(pem)
            numbers = pub.public_numbers()  # type: ignore[attr-defined]
            n = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
            e = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
            keys.append(
                {
                    "kty": "RSA",
                    "alg": "RS256",
                    "use": "sig",
                    "kid": kid,
                    "n": urlsafe_b64encode(n).rstrip(b"=").decode("ascii"),
                    "e": urlsafe_b64encode(e).rstrip(b"=").decode("ascii"),
                }
            )
        return {"keys": keys}

    def sign_access(self, subject: str, role: Role) -> tuple[str, datetime]:
        if not self.current_kid:
            raise RuntimeError("RS256Manager has no current signing key")
        now = datetime.now(UTC)
        exp = now + self.access_ttl
        payload: dict[str, Any] = {
            "sub": subject,
            "role": role.value,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "iss": self.issuer,
            "aud": self.audience,
            "type": "access",
        }
        token = jose_jwt.encode(
            payload,
            self.private_keys[self.current_kid],
            algorithm="RS256",
            headers={"kid": self.current_kid},
        )
        return token, exp

    def sign_refresh(self, subject: str, role: Role) -> tuple[str, datetime]:
        if not self.current_kid:
            raise RuntimeError("RS256Manager has no current signing key")
        now = datetime.now(UTC)
        exp = now + self.refresh_ttl
        payload: dict[str, Any] = {
            "sub": subject,
            "role": role.value,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "iss": self.issuer,
            "aud": self.audience,
            "type": "refresh",
        }
        token = jose_jwt.encode(
            payload,
            self.private_keys[self.current_kid],
            algorithm="RS256",
            headers={"kid": self.current_kid},
        )
        return token, exp

    def verify(self, token: str, *, expected_type: str = "access") -> OperatorContext:
        try:
            unverified_header = jose_jwt.get_unverified_header(token)
        except JWTError as exc:
            raise TokenError(f"malformed token: {exc}") from exc
        kid = unverified_header.get("kid")
        if kid not in self.public_keys:
            raise TokenError(f"unknown kid: {kid!r}")
        try:
            claims = jose_jwt.decode(
                token,
                self.public_keys[kid],
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
            )
        except JWTError as exc:
            raise TokenError(str(exc)) from exc
        if claims.get("type") != expected_type:
            raise TokenError(
                f"expected {expected_type} token, got {claims.get('type')!r}"
            )
        return OperatorContext(
            subject=str(claims["sub"]),
            role=Role.coerce(claims["role"]),
            token_ref=_token_ref(token),
            issued_at=datetime.fromtimestamp(int(claims["iat"]), tz=UTC),
            expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
            raw_claims=claims,
        )


def _token_ref(token: str) -> str:
    """Short, stable, non-reversible reference for audit display (FE-INV-019)."""
    from hashlib import sha256

    digest = sha256(token.encode("utf-8")).hexdigest()
    return digest[:16]
