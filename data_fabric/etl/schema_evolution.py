"""Schema evolution checks for the ETL ↔ Kafka boundary (ADR-026).

Wraps `synapse_common.schema_registry` with an evolution policy: a *new*
schema version must be backwards-compatible with every persisted Parquet
partition. Compatibility rules (Avro-style):

  * Adding an optional field is OK.
  * Removing a required field breaks consumers and is REJECTED.
  * Narrowing a type (e.g. number → integer) breaks consumers.
  * Tightening enum sets breaks consumers.

Run before applying a migration: ``python -m data_fabric.etl.schema_evolution
domain.inventory_action --against proposed.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import structlog

from synapse_common.schema_registry import get_registry

logger = structlog.get_logger(__name__)


class IncompatibleEvolution(ValueError):
    """Raised when a proposed schema breaks consumers."""


def _required(schema: dict[str, Any]) -> set[str]:
    return set(schema.get("required", []))


def _properties(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return dict(schema.get("properties", {}))


def check_backward_compat(
    current: dict[str, Any], proposed: dict[str, Any]
) -> list[str]:
    """Return a list of compatibility violations. Empty list = compatible."""
    violations: list[str] = []

    required_now = _required(current)
    required_next = _required(proposed)

    added_required = required_next - required_now
    if added_required:
        violations.append(
            f"new required fields: {sorted(added_required)} — old payloads break"
        )

    props_now = _properties(current)
    props_next = _properties(proposed)
    removed = set(props_now) - set(props_next)
    for f in removed:
        if f in required_now:
            violations.append(f"required field removed: {f!r}")

    for name, before in props_now.items():
        after = props_next.get(name)
        if after is None:
            continue
        # Type narrowing: e.g. number → integer.
        before_type = before.get("type")
        after_type = after.get("type")
        if before_type and after_type and before_type != after_type:
            if not _type_widens(before_type, after_type):
                violations.append(
                    f"{name}: type {before_type!r} → {after_type!r} narrows"
                )
        # Enum tightening.
        before_enum = set(before.get("enum") or [])
        after_enum = set(after.get("enum") or [])
        if before_enum and after_enum and not before_enum.issubset(after_enum):
            removed_values = before_enum - after_enum
            violations.append(
                f"{name}: enum values removed: {sorted(removed_values)}"
            )

    return violations


def _type_widens(before: str, after: str) -> bool:
    """Heuristic: integer → number widens; everything else is identity-or-narrow."""
    return (before, after) == ("integer", "number")


def assert_compatible(schema_name: str, proposed_path: Path) -> None:
    current = get_registry().schema(schema_name)
    proposed = json.loads(proposed_path.read_text(encoding="utf-8"))
    violations = check_backward_compat(current, proposed)
    if violations:
        raise IncompatibleEvolution(
            f"{schema_name} is not backwards-compatible:\n  - "
            + "\n  - ".join(violations)
        )
    logger.info("schema_evolution_compatible", schema=schema_name, path=str(proposed_path))


def _cli() -> int:
    if len(sys.argv) != 4 or sys.argv[2] != "--against":
        print(
            "usage: python -m data_fabric.etl.schema_evolution <schema_name> --against <proposed.json>",
            file=sys.stderr,
        )
        return 2
    try:
        assert_compatible(sys.argv[1], Path(sys.argv[3]))
    except IncompatibleEvolution as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"OK — {sys.argv[1]} is backwards-compatible")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())


__all__ = [
    "IncompatibleEvolution",
    "assert_compatible",
    "check_backward_compat",
]
