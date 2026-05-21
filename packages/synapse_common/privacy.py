"""SYNAPSE PII tokenization — deterministic HMAC-SHA256 at API ingress.

Every Pydantic model that surfaces user-supplied fields can declare a
class-level `__pii_fields__` tuple. The middleware (`tokenize_payload`) walks
a request body, replaces those fields with stable HMAC tokens, and forwards
the redacted payload downstream. Reversal lives only inside the audit
service (out of scope here) — agents and Kafka topics never see raw PII.

ADR-031. Honours I-1 (data sovereignty) and I-9 (privacy boundary).

Design choices:
  * **Deterministic** — same input + same key → same token. Enables join
    semantics across topics without exposing raw values.
  * **HMAC-SHA256** — keyed hash; pre-image attacks need the key, which lives
    in Vault. Bare SHA-256 would let attackers brute-force common values
    (phone numbers, postcodes) in seconds.
  * **Format-preserving** for length-sensitive fields (phone, postcode) is
    out of scope; tokens are 32-hex strings.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

DEFAULT_KEY_ENV = "SYNAPSE_PII_KEY"
TOKEN_PREFIX = "pii_"

# Regexes for PII embedded in free-text fields. Conservative — false-positives
# are acceptable; false-negatives (raw PII slipping through) are not.
_INDIA_PHONE = re.compile(r"\b(?:\+?91[\s-]?)?[6-9]\d{9}\b")
_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")


def _key() -> bytes:
    raw = os.environ.get(DEFAULT_KEY_ENV, "")
    if not raw:
        # Fail loud rather than silently producing reversible-by-anyone tokens.
        raise RuntimeError(
            f"{DEFAULT_KEY_ENV} is unset — refusing to tokenize PII without a "
            "Vault-managed key. Production refuses to start."
        )
    return raw.encode("utf-8")


def tokenize(value: str | None) -> str | None:
    """HMAC-SHA256 a single PII string. None passes through."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if value.startswith(TOKEN_PREFIX):
        return value  # already tokenized — idempotent
    digest = hmac.new(_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{TOKEN_PREFIX}{digest[:32]}"


def redact_freetext(text: str) -> str:
    """Tokenize embedded PII patterns inside an unstructured string field."""
    out = _INDIA_PHONE.sub(lambda m: tokenize(m.group(0)) or "", text)
    out = _EMAIL.sub(lambda m: tokenize(m.group(0)) or "", out)
    out = _AADHAAR.sub(lambda m: tokenize(m.group(0)) or "", out)
    return out


def _pii_fields(model: type[BaseModel]) -> tuple[str, ...]:
    return tuple(getattr(model, "__pii_fields__", ()))


def tokenize_payload(payload: dict[str, Any], model: type[BaseModel] | None = None) -> dict[str, Any]:
    """Walk `payload` and tokenize every key listed in `model.__pii_fields__`.

    Free-text fields named `note`, `description`, `comment`, `address` are
    additionally scanned for embedded patterns even when the model does not
    list them.
    """
    fields = _pii_fields(model) if model else ()
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if k in fields:
            out[k] = tokenize(v) if isinstance(v, str | type(None)) else v
        elif isinstance(v, str) and k in {"note", "description", "comment", "address"}:
            out[k] = redact_freetext(v)
        elif isinstance(v, dict):
            out[k] = tokenize_payload(v, model=None)
        elif isinstance(v, list):
            out[k] = [
                tokenize_payload(i, model=None) if isinstance(i, dict) else i for i in v
            ]
        else:
            out[k] = v
    return out


__all__ = [
    "DEFAULT_KEY_ENV",
    "TOKEN_PREFIX",
    "tokenize",
    "redact_freetext",
    "tokenize_payload",
]
