"""Shared auth primitives (RS256 JWT + RBAC roles).

P1 promotes the test-only RS256Manager (``tests/security/test_jwt_rs256.py``)
into a production module so the API gateway, orchestrator, and any future
service can share one source of truth.

I-1 holds: python-jose[cryptography] is Apache-2.0.
"""

from .jwt_manager import (
    KeyPair,
    OperatorContext,
    Role,
    RS256Manager,
    TokenError,
    generate_keypair,
)

__all__ = [
    "KeyPair",
    "OperatorContext",
    "Role",
    "RS256Manager",
    "TokenError",
    "generate_keypair",
]
