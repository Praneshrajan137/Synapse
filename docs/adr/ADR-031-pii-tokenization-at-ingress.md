# ADR-031: Deterministic HMAC PII tokenization at API ingress

## Status
Accepted (Sprint 7)

## Context
DPDPA (India's data-protection law) and platform privacy goals require
that raw PII — phone numbers, emails, Aadhaar, free-text addresses — never
reaches downstream agents, Kafka topics, or Parquet snapshots. The
existing FastAPI surface forwarded raw bodies. I-1 (data sovereignty)
and I-9 (privacy boundary) were declared but not enforced.

## Decision
Implement deterministic tokenization at the API gateway:

- **`synapse_common.privacy.tokenize`** — HMAC-SHA256 with key from Vault
  (`infrastructure/vault/policies/pii.hcl`). Deterministic so cross-topic
  joins still work; keyed so brute-force pre-image attacks need the key.
- **`tokenize_payload(payload, model)`** — walks a Pydantic model's
  `__pii_fields__` registry and replaces matched keys.
- **`redact_freetext(text)`** — pattern-scans free-text fields (`note`,
  `description`, `comment`, `address`) for embedded phone / email /
  Aadhaar; tokens replace matches.

The tokenizer **refuses to start without a key** (`SYNAPSE_PII_KEY` env
var) — never silently produces reversible-by-anyone tokens.

## Consequences
- Honours DPDPA's purpose-limitation principle: agents only see
  pseudonymised data.
- Deterministic tokens preserve foreign-key joinability across topics.
- Reversal lives only in the audit service (out of scope here) — quarterly
  key rotation keeps old tokens reversible while new ones use the new key.
- Layer-7 security tests grep agent logs and Kafka payloads for PII regex;
  must return zero hits.

## Alternatives Rejected
- **AES-encrypted columns** — not joinable across topics; defeats analytics.
- **Format-preserving encryption (FPE)** — overkill for our field set.
- **Plain SHA-256** — pre-image search for common phone numbers is seconds.
- **Skip free-text scanning** — naïve users put PII in `note` fields all
  the time. Conservative scanning is mandatory.
