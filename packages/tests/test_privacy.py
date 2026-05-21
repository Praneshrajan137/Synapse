"""Tests for synapse_common.privacy — Layer 7 (Security) + Layer 1 (SDD)."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import BaseModel

from synapse_common.privacy import (
    TOKEN_PREFIX,
    redact_freetext,
    tokenize,
    tokenize_payload,
)


@pytest.fixture(autouse=True)
def _set_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPSE_PII_KEY", "test-key-do-not-use-in-production")


def test_tokenize_is_deterministic() -> None:
    a = tokenize("9876543210")
    b = tokenize("9876543210")
    assert a == b
    assert a is not None and a.startswith(TOKEN_PREFIX)


def test_tokenize_distinct_inputs_distinct_outputs() -> None:
    assert tokenize("9876543210") != tokenize("9876543211")


def test_tokenize_idempotent_on_already_tokenized() -> None:
    once = tokenize("user@example.com")
    twice = tokenize(once)
    assert once == twice


def test_tokenize_none_passes_through() -> None:
    assert tokenize(None) is None


def test_redact_phone_in_freetext() -> None:
    out = redact_freetext("call me on 9876543210 thanks")
    assert "9876543210" not in out
    assert TOKEN_PREFIX in out


def test_redact_email_in_freetext() -> None:
    out = redact_freetext("write to alice@example.com")
    assert "alice@example.com" not in out


def test_redact_aadhaar_in_freetext() -> None:
    out = redact_freetext("aadhaar 1234 5678 9012 attached")
    assert "1234 5678 9012" not in out


def test_tokenize_payload_walks_pii_fields() -> None:
    class Order(BaseModel):
        __pii_fields__: ClassVar[tuple[str, ...]] = ("phone", "email")
        phone: str
        email: str
        sku: str

    raw = {"phone": "9876543210", "email": "a@b.co", "sku": "x1"}
    out = tokenize_payload(raw, model=Order)
    assert out["phone"].startswith(TOKEN_PREFIX)
    assert out["email"].startswith(TOKEN_PREFIX)
    assert out["sku"] == "x1"


def test_tokenize_payload_redacts_freetext_in_address() -> None:
    raw = {"address": "near 9876543210, MG Road"}
    out = tokenize_payload(raw)
    assert "9876543210" not in out["address"]


def test_tokenize_refuses_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYNAPSE_PII_KEY", raising=False)
    with pytest.raises(RuntimeError):
        tokenize("any value")
