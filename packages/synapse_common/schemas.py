"""
SYNAPSE handler-boundary schema validator (I-3, WS-2 §4).

Every agent A2A handler MUST validate its output payload against the
matching ``proto/domain/*.schema.json`` before returning. This module is
the single seam — each agent imports the schema name once and calls
``validate_handler_input``.

Design:
- Schemas are loaded lazily from disk on first access and cached.
- Names are exposed as constants so handler code is greppable.
- Failures raise ``HandlerSchemaError`` (subclass of ``ValueError``);
  the A2A handler maps it to JSON-RPC error -32602 (Invalid params).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped,unused-ignore]
import structlog

logger = structlog.get_logger(__name__)


SCHEMA_DIR: Path = Path(__file__).resolve().parents[2] / "proto" / "domain"


# Canonical schema names — every handler imports the one(s) it owns.
DEMAND_FORECAST_SCHEMA = "demand_forecast"
ROUTE_PLAN_SCHEMA = "route_plan"
INVENTORY_ACTION_SCHEMA = "inventory_action"
FRESHNESS_ALERT_SCHEMA = "freshness_alert"
PRICING_DECISION_SCHEMA = "pricing_decision"
PRICING_UPDATE_SCHEMA = "pricing_update"
DISRUPTION_ALERT_SCHEMA = "disruption_alert"
SUPPLIER_SCORE_SCHEMA = "supplier_score"
CARBON_REPORT_SCHEMA = "carbon_report"
CONSENSUS_DECISION_SCHEMA = "consensus_decision"
TWIN_STATE_SCHEMA = "twin_state"
ORDER_REQUEST_SCHEMA = "order_request"


class HandlerSchemaError(ValueError):
    """Raised when a handler output fails ``proto/domain`` validation."""

    def __init__(self, schema_name: str, detail: str) -> None:
        super().__init__(f"schema '{schema_name}' validation failed: {detail}")
        self.schema_name = schema_name
        self.detail = detail


@lru_cache(maxsize=32)
def load_schema(schema_name: str) -> dict[str, Any]:
    """Load and cache a JSON schema by its short name (without ``.schema.json``)."""
    path = SCHEMA_DIR / f"{schema_name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"schema not found: {path}")
    with path.open(encoding="utf-8") as fp:
        schema: dict[str, Any] = json.load(fp)
    return schema


def validate_handler_input(schema_name: str, payload: dict[str, Any]) -> None:
    """Validate ``payload`` against the named schema. Raises ``HandlerSchemaError``.

    Use at every A2A handler boundary after the response payload is built
    and before it is returned. Failures are logged at ``error`` with the
    schema name and the path of the offending property.
    """
    try:
        schema = load_schema(schema_name)
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path) or "<root>"
        detail = f"at {location}: {exc.message}"
        logger.error(
            "handler_schema_validation_failed",
            schema=schema_name,
            location=location,
            message=exc.message,
        )
        raise HandlerSchemaError(schema_name, detail) from exc
    except FileNotFoundError as exc:
        logger.error("handler_schema_missing", schema=schema_name, path=str(exc))
        raise HandlerSchemaError(schema_name, f"schema file missing: {exc}") from exc
