from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import structlog

logger = structlog.get_logger()

try:
    from jose import jwt as jose_jwt
except ImportError:
    jose_jwt = None

SYNAPSE_JWT_CONFIG = {
    "algorithm": "HS256",
    "access_token_expire_minutes": 15,
    "refresh_token_expire_days": 7,
    "issuer": "synapse-api-gateway",
    "audience": "synapse-agents",
}

TEST_SECRET_KEY = "test-secret-key-for-sprint5-security-tests-only"


class JWTManager:
    """JWT token management for SYNAPSE API Gateway."""

    def __init__(self, secret_key: str, config: dict | None = None) -> None:
        self.secret_key = secret_key
        self.config = config or SYNAPSE_JWT_CONFIG

    def create_access_token(
        self, subject: str, roles: list[str] | None = None,
    ) -> str:
        expire = datetime.now(UTC) + timedelta(
            minutes=self.config["access_token_expire_minutes"],
        )
        payload = {
            "sub": subject,
            "exp": expire,
            "iss": self.config["issuer"],
            "aud": self.config["audience"],
            "roles": roles or ["viewer"],
            "type": "access",
        }
        return jose_jwt.encode(  # type: ignore[union-attr]
            payload, self.secret_key, algorithm=self.config["algorithm"],
        )

    def create_refresh_token(self, subject: str) -> str:
        expire = datetime.now(UTC) + timedelta(
            days=self.config["refresh_token_expire_days"],
        )
        payload = {
            "sub": subject,
            "exp": expire,
            "iss": self.config["issuer"],
            "type": "refresh",
        }
        return jose_jwt.encode(  # type: ignore[union-attr]
            payload, self.secret_key, algorithm=self.config["algorithm"],
        )

    def verify_token(self, token: str) -> dict:
        return jose_jwt.decode(  # type: ignore[union-attr]
            token,
            self.secret_key,
            algorithms=[self.config["algorithm"]],
            audience=self.config["audience"],
            issuer=self.config["issuer"],
        )


@pytest.mark.skipif(jose_jwt is None, reason="python-jose not installed")
class TestJWT:
    """Security tests for JWT authentication."""

    @pytest.fixture()
    def jwt_manager(self) -> JWTManager:
        return JWTManager(secret_key=TEST_SECRET_KEY)

    def test_access_token_creation(self, jwt_manager: JWTManager) -> None:
        """Access token is created with correct claims."""
        token = jwt_manager.create_access_token(
            "user@synapse.ai", roles=["admin", "operator"],
        )
        payload = jose_jwt.decode(
            token, TEST_SECRET_KEY, algorithms=["HS256"],
            audience="synapse-agents", issuer="synapse-api-gateway",
        )

        assert payload["sub"] == "user@synapse.ai"
        assert payload["type"] == "access"
        assert "admin" in payload["roles"]

    def test_access_token_expires_in_15_minutes(self, jwt_manager: JWTManager) -> None:
        """Access tokens expire within 15-minute window."""
        token = jwt_manager.create_access_token("user@synapse.ai")
        payload = jose_jwt.decode(
            token, TEST_SECRET_KEY, algorithms=["HS256"],
            audience="synapse-agents", issuer="synapse-api-gateway",
        )

        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        delta = exp - datetime.now(UTC)
        assert 14 * 60 <= delta.total_seconds() <= 15 * 60 + 5

    def test_expired_token_rejected(self, jwt_manager: JWTManager) -> None:
        """Expired tokens are rejected."""
        expired_payload = {
            "sub": "user@synapse.ai",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
            "iss": "synapse-api-gateway",
            "aud": "synapse-agents",
            "type": "access",
        }
        expired_token = jose_jwt.encode(
            expired_payload, TEST_SECRET_KEY, algorithm="HS256",
        )

        with pytest.raises(Exception):
            jwt_manager.verify_token(expired_token)

    def test_wrong_secret_rejected(self, jwt_manager: JWTManager) -> None:
        """Tokens signed with wrong key are rejected."""
        wrong_key_token = jose_jwt.encode(
            {
                "sub": "attacker",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iss": "synapse-api-gateway",
                "aud": "synapse-agents",
            },
            "wrong-secret-key",
            algorithm="HS256",
        )

        with pytest.raises(Exception):
            jwt_manager.verify_token(wrong_key_token)

    def test_wrong_issuer_rejected(self, jwt_manager: JWTManager) -> None:
        """Tokens with wrong issuer are rejected."""
        bad_issuer_token = jose_jwt.encode(
            {
                "sub": "user",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iss": "attacker-gateway",
                "aud": "synapse-agents",
            },
            TEST_SECRET_KEY,
            algorithm="HS256",
        )

        with pytest.raises(Exception):
            jwt_manager.verify_token(bad_issuer_token)

    def test_refresh_token_creation(self, jwt_manager: JWTManager) -> None:
        """Refresh token has correct type and 7-day expiry."""
        token = jwt_manager.create_refresh_token("user@synapse.ai")
        payload = jose_jwt.decode(
            token, TEST_SECRET_KEY, algorithms=["HS256"],
            options={"verify_aud": False},
            issuer="synapse-api-gateway",
        )

        assert payload["type"] == "refresh"
        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        delta = exp - datetime.now(UTC)
        assert 6 * 24 * 3600 <= delta.total_seconds() <= 7 * 24 * 3600 + 60

    def test_alg_none_attack_rejected(self, jwt_manager: JWTManager) -> None:
        """Algorithm confusion attack (alg:none) is rejected.

        Attacker forges a token with algorithm set to 'none' to bypass
        signature verification.  The verify call MUST reject this.
        """
        import base64
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload_data = {
            "sub": "attacker",
            "exp": (datetime.now(UTC) + timedelta(hours=1)).timestamp(),
            "iss": "synapse-api-gateway",
            "aud": "synapse-agents",
        }
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload_data).encode()
        ).rstrip(b"=").decode()
        forged_token = f"{header}.{payload_b64}."

        with pytest.raises(Exception):
            jwt_manager.verify_token(forged_token)
