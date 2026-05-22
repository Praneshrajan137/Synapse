"""Tests for synapse_common.auth.jwt_manager — RS256 JWT manager (Sprint 5)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from synapse_common.auth.jwt_manager import (
    OperatorContext,
    Role,
    RS256Manager,
    TokenError,
    generate_keypair,
)


def _manager(**kwargs: object) -> RS256Manager:
    """A manager pre-loaded with one signing keypair."""
    mgr = RS256Manager(**kwargs)  # type: ignore[arg-type]
    mgr.add_keypair(generate_keypair("kid-1"))
    return mgr


class TestRole:
    def test_rank_is_strictly_ordered(self) -> None:
        assert Role.VIEWER.rank < Role.OPS.rank < Role.ENGINEER.rank < Role.ADMIN.rank

    def test_coerce_from_string(self) -> None:
        assert Role.coerce("ops") is Role.OPS

    def test_coerce_from_role_is_identity(self) -> None:
        assert Role.coerce(Role.ADMIN) is Role.ADMIN

    def test_coerce_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            Role.coerce("superuser")

    def test_satisfies_minimum(self) -> None:
        assert Role.ADMIN.satisfies(Role.OPS)
        assert Role.OPS.satisfies(Role.OPS)
        assert not Role.VIEWER.satisfies(Role.ENGINEER)


class TestKeypair:
    def test_generate_keypair(self) -> None:
        kp = generate_keypair("kid-x")
        assert kp.kid == "kid-x"
        assert b"PRIVATE KEY" in kp.private_pem
        assert b"PUBLIC KEY" in kp.public_pem


class TestSignAndVerify:
    def test_access_token_round_trip(self) -> None:
        mgr = _manager()
        token, exp = mgr.sign_access("operator-1", Role.OPS)
        ctx = mgr.verify(token)
        assert isinstance(ctx, OperatorContext)
        assert ctx.subject == "operator-1"
        assert ctx.role is Role.OPS
        assert ctx.token_ref and len(ctx.token_ref) == 16
        assert ctx.expires_at > ctx.issued_at
        assert exp > ctx.issued_at

    def test_refresh_token_round_trip(self) -> None:
        mgr = _manager()
        token, _ = mgr.sign_refresh("operator-2", Role.ADMIN)
        ctx = mgr.verify(token, expected_type="refresh")
        assert ctx.subject == "operator-2"
        assert ctx.role is Role.ADMIN

    def test_wrong_token_type_rejected(self) -> None:
        mgr = _manager()
        access, _ = mgr.sign_access("operator-3", Role.VIEWER)
        with pytest.raises(TokenError, match="expected refresh"):
            mgr.verify(access, expected_type="refresh")

    def test_malformed_token_rejected(self) -> None:
        mgr = _manager()
        with pytest.raises(TokenError, match="malformed"):
            mgr.verify("not-a-jwt")

    def test_unknown_kid_rejected(self) -> None:
        signer = _manager()
        token, _ = signer.sign_access("operator-4", Role.OPS)
        other = RS256Manager()
        other.add_keypair(generate_keypair("kid-other"))
        with pytest.raises(TokenError, match="unknown kid"):
            other.verify(token)

    def test_expired_token_rejected(self) -> None:
        mgr = _manager(access_ttl=timedelta(seconds=-1))
        token, _ = mgr.sign_access("operator-5", Role.OPS)
        with pytest.raises(TokenError):
            mgr.verify(token)

    def test_sign_without_current_key_raises(self) -> None:
        with pytest.raises(RuntimeError, match="no current signing key"):
            RS256Manager().sign_access("operator-6", Role.OPS)
        with pytest.raises(RuntimeError, match="no current signing key"):
            RS256Manager().sign_refresh("operator-6", Role.OPS)


class TestKeyRotation:
    def test_old_token_valid_after_rotation(self) -> None:
        mgr = _manager()
        old_token, _ = mgr.sign_access("operator-7", Role.ENGINEER)
        # Rotate to a new current key — the old kid stays accepted.
        mgr.add_keypair(generate_keypair("kid-2"))
        assert mgr.current_kid == "kid-2"
        ctx = mgr.verify(old_token)
        assert ctx.subject == "operator-7"

    def test_retired_kid_rejected(self) -> None:
        mgr = _manager()
        token, _ = mgr.sign_access("operator-8", Role.OPS)
        mgr.add_keypair(generate_keypair("kid-2"))
        mgr.retire_kid("kid-1")
        with pytest.raises(TokenError, match="unknown kid"):
            mgr.verify(token)

    def test_add_keypair_without_make_current(self) -> None:
        mgr = _manager()
        mgr.add_keypair(generate_keypair("kid-standby"), make_current=False)
        assert mgr.current_kid == "kid-1"
        assert "kid-standby" in mgr.public_keys


class TestJwks:
    def test_jwks_document_shape(self) -> None:
        mgr = _manager()
        mgr.add_keypair(generate_keypair("kid-2"))
        doc = mgr.jwks()
        assert set(doc) == {"keys"}
        assert len(doc["keys"]) == 2
        for entry in doc["keys"]:
            assert entry["kty"] == "RSA"
            assert entry["alg"] == "RS256"
            assert entry["use"] == "sig"
            assert entry["kid"] in {"kid-1", "kid-2"}
            assert entry["n"] and entry["e"]
