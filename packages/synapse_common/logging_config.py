"""
SYNAPSE Structured Logging — All agents use structlog.
NEVER use print() for logging. NEVER use bare except.

Sprint 9 §M-life-4 (ADR-035) adds ``redact_pii``: a structlog processor
that scrubs phone, email, postal-code, and Aadhaar-style 12-digit
patterns before the log record is serialised. Each scrub increments
``synapse_pii_redaction_total{field}`` so ops can detect when a
log line nearly leaked PII.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

from synapse_common.metrics import PII_REDACTION_TOTAL

REDACTED = "[REDACTED]"

# Sprint 9 scrubber regexes — kept tight to avoid false positives on UUIDs
# and SKU ids that happen to be ten digits long.
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # +91-9XXXXXXXXX or 9XXXXXXXXX (Indian mobile numbers — E.164-ish)
    "phone": re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b"),
    # Aadhaar = 12 digits, often grouped as XXXX XXXX XXXX
    "aadhaar": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    # Indian PIN code = 6 digits standalone
    "pin_code": re.compile(r"(?<!\d)\d{6}(?!\d)"),
}


def _scrub_value(value: str) -> tuple[str, list[str]]:
    """Return (redacted_value, list_of_fields_scrubbed) for one string."""
    scrubbed: list[str] = []
    for field, pattern in PII_PATTERNS.items():
        if pattern.search(value):
            value = pattern.sub(REDACTED, value)
            scrubbed.append(field)
    return value, scrubbed


def redact_pii(
    logger: Any,  # noqa: ANN401
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> Mapping[str, Any]:
    """Structlog processor that redacts PII from string values in ``event_dict``."""
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            new_value, fields = _scrub_value(value)
            if fields:
                event_dict[key] = new_value
                for field in fields:
                    PII_REDACTION_TOTAL.labels(field=field).inc()
        elif isinstance(value, dict):
            event_dict[key] = _scrub_dict(value)
        elif isinstance(value, list):
            event_dict[key] = [_scrub_any(item) for item in value]
    return event_dict


def _scrub_dict(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        out[k] = _scrub_any(v)
    return out


def _scrub_any(value: Any) -> Any:  # noqa: ANN401
    if isinstance(value, str):
        new_value, fields = _scrub_value(value)
        for field in fields:
            PII_REDACTION_TOTAL.labels(field=field).inc()
        return new_value
    if isinstance(value, dict):
        return _scrub_dict(value)
    if isinstance(value, list):
        return [_scrub_any(item) for item in value]
    return value


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
) -> None:
    """Configure structlog for SYNAPSE. Call once at application startup."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        redact_pii,  # Sprint 9 — runs early so downstream processors see scrubbed strings.
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer(
            sort_keys=True,
        )
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper()))
