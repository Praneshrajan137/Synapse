"""
SYNAPSE Centralized Schema Validation (WS-2 / I-3).

Loads every JSON schema under ``proto/domain/`` into a registry keyed by
``$id``. Provides a single ``validate_payload(name, payload)`` entry point
that every agent A2A handler calls before returning, so we cannot ship an
output that fails its own contract.

The registry is built once on import and then becomes immutable. Schemas
must be present at process startup; ImportError-time failure is preferable
to silent run-time misvalidation.

Schemas live next to the code; this module discovers them by walking
``proto/domain/`` relative to the repo root. The repo root is detected by
walking parents until a marker (``pyproject.toml``) is found.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
from jsonschema import Draft7Validator  # type: ignore[import-untyped]

logger = structlog.get_logger(__name__)


class SchemaValidationError(ValueError):
    """Raised when an agent payload fails schema validation."""

    def __init__(self, schema_name: str, errors: list[str]) -> None:
        super().__init__(
            f"Payload failed schema '{schema_name}' validation:\n  - " + "\n  - ".join(errors)
        )
        self.schema_name = schema_name
        self.errors = errors


def _find_schema_dir() -> Path:
    """Walk parents from this file until we find ``proto/domain/``.

    There are multiple ``pyproject.toml`` files in the tree (root + one per
    package), so we anchor on the schema directory itself.
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        target = candidate / "proto" / "domain"
        if target.is_dir():
            return target
    raise RuntimeError(
        "could not find proto/domain/ in any ancestor of "
        f"{here}. The schema registry cannot start without it."
    )


def _load_schemas(schema_dir: Path) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        with path.open("r", encoding="utf-8") as fh:
            schema = json.load(fh)
        schema_id = schema.get("$id") or path.stem.replace(".schema", "")
        short_name = path.stem.replace(".schema", "")
        registry[schema_id] = schema
        registry[short_name] = schema
        logger.debug("schema_loaded", id=schema_id, file=str(path.name))
    return registry


_SCHEMA_DIR = _find_schema_dir()
_REGISTRY: dict[str, dict[str, Any]] = _load_schemas(_SCHEMA_DIR)
_VALIDATORS: dict[str, Draft7Validator] = {
    name: Draft7Validator(schema) for name, schema in _REGISTRY.items()
}


def known_schemas() -> tuple[str, ...]:
    """Return the registered schema short-names (e.g. 'demand_forecast')."""
    return tuple(sorted(name for name in _REGISTRY if "." not in name))


def get_schema(name: str) -> dict[str, Any]:
    """Return the raw schema dict by short-name or $id."""
    schema = _REGISTRY.get(name)
    if schema is None:
        raise KeyError(f"no schema registered for '{name}'. Known: {', '.join(known_schemas())}")
    return schema


def validate_payload(name: str, payload: dict[str, Any]) -> None:
    """Raise ``SchemaValidationError`` if ``payload`` doesn't match.

    Args:
        name: schema short-name (e.g. ``"demand_forecast"``) or full $id.
        payload: dict already converted to JSON-compatible types
            (e.g. via ``model.model_dump(mode='json')``).
    """
    validator = _VALIDATORS.get(name)
    if validator is None:
        raise KeyError(f"no schema registered for '{name}'. Known: {', '.join(known_schemas())}")
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda e: e.absolute_path,
    )
    if errors:
        formatted = [
            f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
            for err in errors
        ]
        raise SchemaValidationError(name, formatted)


# ---------------------------------------------------------------------------
# Agent proposal-payload validation (Sprint 7, WS-2 / I-3).
#
# Every A2A handler must validate its outgoing payload against the schema
# registered in ``proto/domain/`` before returning. Per-agent payload
# shapes are heterogeneous, so the mapping below tells the helper which
# schema to apply to which sub-object.
#
# Each entry is ``(schema_name, payload_path)`` where ``payload_path`` is
# either:
#     * an empty tuple ``()`` -- validate the payload object itself, or
#     * a tuple of (key, ...) -- validate each item under
#       ``payload[key]`` (when the key resolves to a list, validate each
#       list element; when it resolves to a dict, validate the dict).
# ---------------------------------------------------------------------------

_AgentPath = tuple[str, str | None]
"""(schema_name, list_key_or_None). list_key=None means validate the payload itself."""

# All eight agents emit handler payloads whose shape matches the
# registered schema in proto/domain/. Strict I-3 enforcement now applies
# to every agent's A2A boundary.
AGENT_PAYLOAD_SCHEMAS: dict[str, list[_AgentPath]] = {
    "demand_prophet": [("demand_forecast", "forecasts")],
    "routing_navigator": [("route_plan", "routes")],
    "inventory_sentinel": [("inventory_action", "actions")],
    "pricing_oracle": [("pricing_update", "updates")],
    "freshness_guardian": [("freshness_alert", "alerts")],
    "disruption_shield": [("disruption_alert", None)],
    "supplier_trust": [("supplier_score", None)],
    "sustainability_agent": [("carbon_report", None)],
}

# Reserved for any future agent additions whose schema reconciliation is
# not yet complete. Keeping the constant in place lets the test suite
# continue to assert "every agent is either strictly enforced or
# documented as pending" without per-merge churn.
PENDING_AGENT_PAYLOAD_SCHEMAS: dict[str, list[_AgentPath]] = {}


def validate_agent_payload(agent_name: str, payload: dict[str, Any]) -> None:
    """Validate every sub-object in an A2A proposal payload (I-3).

    Each agent's payload has a known shape. We look up the agent's
    schema bindings and validate the matching parts of the payload. If
    the agent has no bindings registered, the call is a no-op (the
    ``known_agents`` test below ensures every agent IS bound).

    Raises:
        SchemaValidationError: any sub-object failed its schema.
    """
    bindings = AGENT_PAYLOAD_SCHEMAS.get(agent_name)
    if not bindings:
        return
    for schema_name, list_key in bindings:
        if list_key is None:
            validate_payload(schema_name, payload)
            continue
        items = payload.get(list_key)
        if items is None:
            # Missing key is *not* a schema violation here -- the caller's
            # schema for the proposal-envelope is responsible for that.
            continue
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    validate_payload(schema_name, item)
        elif isinstance(items, dict):
            validate_payload(schema_name, items)


def known_agents() -> tuple[str, ...]:
    """Return the agents with registered payload-schema bindings."""
    return tuple(sorted(AGENT_PAYLOAD_SCHEMAS.keys()))
