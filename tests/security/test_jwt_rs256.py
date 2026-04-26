"""Sprint-7 elevation -- RS256 JWT with key rotation (R8).

CLAUDE.md error pattern E-S5-08 calls for python-jose ``[cryptography]``
to support RS256, but the existing ``test_jwt.py`` only exercises HS256
with a shared symmetric secret. Production needs RS256:

* signing key (private) lives behind a vault/KMS,
* verifying key (public) is embedded in services + rotated via a ``kid``
  header,
* the asymmetric split allows the gateway to grant short-lived tokens
  without giving every downstream agent the secret.

This module adds an RS256 manager + key rotation test, keeping HS256 in
``test_jwt.py`` untouched for back-compat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jose import jwt as jose_jwt

    HAS_CRYPTO = True
except ImportError:  # pragma: no cover
    HAS_CRYPTO = False

pytestmark = pytest.mark.skipif(
    not HAS_CRYPTO,
    reason="python-jose[cryptography] not installed",
)


@dataclass
class _KeyPair:
    kid: str
    private_pem: bytes
    public_pem: bytes


def _generate_keypair(kid: str) -> _KeyPair:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return _KeyPair(kid=kid, private_pem=private_pem, public_pem=public_pem)


@dataclass
class RS256Manager:
    """RS256 JWT manager with kid-based key rotation.

    The signer always uses ``current_kid``; the verifier accepts any ``kid``
    in ``public_keys`` so a freshly-rotated signing key does not invalidate
    in-flight tokens issued under the previous key.
    """

    issuer: str = "synapse-api-gateway"
    audience: str = "synapse-agents"
    private_keys: dict[str, bytes] = field(default_factory=dict)
    public_keys: dict[str, bytes] = field(default_factory=dict)
    current_kid: str = ""
    access_ttl: timedelta = timedelta(minutes=15)

    def add_keypair(self, kp: _KeyPair, *, make_current: bool = True) -> None:
        self.private_keys[kp.kid] = kp.private_pem
        self.public_keys[kp.kid] = kp.public_pem
        if make_current:
            self.current_kid = kp.kid

    def retire_kid(self, kid: str) -> None:
        """Drop a key from the verifier set after its tokens have expired."""
        self.public_keys.pop(kid, None)
        self.private_keys.pop(kid, None)

    def sign(self, subject: str, roles: list[str] | None = None) -> str:
        if not self.current_kid:
            raise RuntimeError("RS256Manager has no current signing key")
        payload: dict[str, Any] = {
            "sub": subject,
            "exp": datetime.now(UTC) + self.access_ttl,
            "iss": self.issuer,
            "aud": self.audience,
            "roles": roles or ["viewer"],
            "type": "access",
        }
        return jose_jwt.encode(
            payload,
            self.private_keys[self.current_kid],
            algorithm="RS256",
            headers={"kid": self.current_kid},
        )

    def verify(self, token: str) -> dict[str, Any]:
        unverified_header = jose_jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if kid not in self.public_keys:
            raise jose_jwt.JWTError(f"unknown kid: {kid!r}")
        return jose_jwt.decode(
            token,
            self.public_keys[kid],
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
        )


@pytest.fixture()
def manager() -> RS256Manager:
    mgr = RS256Manager()
    mgr.add_keypair(_generate_keypair("kid-2026-04"))
    return mgr


class TestRs256Roundtrip:
    def test_sign_and_verify(self, manager: RS256Manager) -> None:
        token = manager.sign("user@synapse.ai", roles=["admin"])
        payload = manager.verify(token)
        assert payload["sub"] == "user@synapse.ai"
        assert payload["roles"] == ["admin"]

    def test_kid_in_header(self, manager: RS256Manager) -> None:
        token = manager.sign("user@synapse.ai")
        header = jose_jwt.get_unverified_header(token)
        assert header["kid"] == "kid-2026-04"
        assert header["alg"] == "RS256"


class TestKeyRotation:
    def test_old_tokens_still_verify_after_rotation(self, manager: RS256Manager) -> None:
        old_token = manager.sign("user@synapse.ai")
        manager.add_keypair(_generate_keypair("kid-2026-05"))
        # Old token still verifies because the old public key is retained.
        payload = manager.verify(old_token)
        assert payload["sub"] == "user@synapse.ai"

    def test_new_tokens_signed_with_new_kid(self, manager: RS256Manager) -> None:
        manager.add_keypair(_generate_keypair("kid-2026-05"))
        token = manager.sign("user@synapse.ai")
        header = jose_jwt.get_unverified_header(token)
        assert header["kid"] == "kid-2026-05"

    def test_retired_kid_rejects_old_token(self, manager: RS256Manager) -> None:
        old_token = manager.sign("user@synapse.ai")
        manager.add_keypair(_generate_keypair("kid-2026-05"))
        manager.retire_kid("kid-2026-04")
        with pytest.raises(jose_jwt.JWTError):
            manager.verify(old_token)


class TestAlgorithmConfusion:
    def test_hs256_token_rejected_by_rs256_verifier(
        self, manager: RS256Manager,
    ) -> None:
        """An attacker MUST NOT be able to sign with HS256 and have the
        RS256 verifier accept it (the classic 'alg confusion' attack).

        We forge a token claiming alg=HS256 but signed with the public key
        as the HMAC secret -- the manager's hard-coded ``algorithms=["RS256"]``
        whitelist must reject it.
        """
        public_pem = manager.public_keys[manager.current_kid]
        forged = jose_jwt.encode(
            {
                "sub": "attacker",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iss": manager.issuer,
                "aud": manager.audience,
            },
            public_pem.decode(),
            algorithm="HS256",
            headers={"kid": manager.current_kid},
        )
        with pytest.raises(jose_jwt.JWTError):
            manager.verify(forged)
