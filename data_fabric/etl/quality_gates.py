"""ETL data-quality gates — Great-Expectations-style assertions, zero-cost.

Implements the ADR-026 quality contract: every ETL row passes a battery of
gates before reaching the Parquet store. Failures are written to
`data_fabric/quarantine/<dt>/<topic>.parquet` (not silently dropped) and
emit a lineage event into the audit ledger.

Implementation uses only `pyarrow` + stdlib (no Great Expectations or other
heavyweight dependency) — preserves I-1 (zero cost).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)

QUARANTINE_ROOT = Path("data_fabric/quarantine")


@dataclass(frozen=True)
class GateResult:
    """Outcome of running one gate against one row."""

    gate: str
    passed: bool
    detail: str = ""


@dataclass
class GateRegistry:
    """Composable battery of gates. Run order is registration order."""

    gates: list[tuple[str, Callable[[dict[str, Any]], GateResult]]] = field(
        default_factory=list
    )

    def register(self, name: str, fn: Callable[[dict[str, Any]], GateResult]) -> None:
        self.gates.append((name, fn))

    def run(self, row: dict[str, Any]) -> list[GateResult]:
        return [fn(row) for _, fn in self.gates]


# ---------- Built-in gates -------------------------------------------------


def gate_no_nulls(required: list[str]) -> Callable[[dict[str, Any]], GateResult]:
    """Reject rows missing any of `required`."""
    name = f"no_nulls({','.join(required)})"

    def _fn(row: dict[str, Any]) -> GateResult:
        missing = [f for f in required if row.get(f) is None]
        if missing:
            return GateResult(name, False, f"missing={missing}")
        return GateResult(name, True)

    return _fn


def gate_range(field_: str, lo: float, hi: float) -> Callable[[dict[str, Any]], GateResult]:
    """Reject rows whose `field_` falls outside `[lo, hi]`."""
    name = f"range({field_},{lo},{hi})"

    def _fn(row: dict[str, Any]) -> GateResult:
        value = row.get(field_)
        if value is None:
            return GateResult(name, False, f"{field_} missing")
        try:
            v = float(value)
        except (TypeError, ValueError):
            return GateResult(name, False, f"{field_} not numeric: {value!r}")
        if not (lo <= v <= hi):
            return GateResult(name, False, f"{field_}={v} out of [{lo},{hi}]")
        return GateResult(name, True)

    return _fn


def gate_freshness(timestamp_field: str, max_age_seconds: float) -> Callable[
    [dict[str, Any]], GateResult
]:
    """Reject rows whose timestamp is older than `max_age_seconds`."""
    name = f"freshness({timestamp_field},<{max_age_seconds}s)"

    def _fn(row: dict[str, Any]) -> GateResult:
        ts = row.get(timestamp_field)
        if ts is None:
            return GateResult(name, False, f"{timestamp_field} missing")
        try:
            if isinstance(ts, str):
                # Accept ISO-8601 with Z or offset
                clean = ts.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean)
            elif isinstance(ts, datetime):
                dt = ts
            else:
                return GateResult(name, False, f"{timestamp_field} unparseable")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - dt).total_seconds()
            if age > max_age_seconds:
                return GateResult(name, False, f"age={age:.0f}s")
            return GateResult(name, True)
        except (ValueError, TypeError) as exc:
            return GateResult(name, False, f"{exc}")

    return _fn


def gate_schema(schema_name: str) -> Callable[[dict[str, Any]], GateResult]:
    """Validate row against a registered JSON Schema (ADR-025)."""
    name = f"schema({schema_name})"

    def _fn(row: dict[str, Any]) -> GateResult:
        from synapse_common.schema_registry import SchemaViolation, get_registry

        try:
            get_registry().validate(row, schema_name)
        except SchemaViolation as exc:
            return GateResult(name, False, "; ".join(exc.errors))
        except KeyError:
            return GateResult(name, False, f"unknown schema {schema_name}")
        return GateResult(name, True)

    return _fn


# ---------- Quarantine + lineage --------------------------------------------


def quarantine(row: dict[str, Any], topic: str, reasons: list[GateResult]) -> Path:
    """Write a single rejected row to disk. Path: quarantine/<YYYYMMDD>/<topic>.jsonl."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    target_dir = QUARANTINE_ROOT / today
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{topic}.jsonl"
    record = {
        "row": row,
        "rejected_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "reasons": [
            {"gate": r.gate, "detail": r.detail} for r in reasons if not r.passed
        ],
    }
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    return target


def evaluate(row: dict[str, Any], registry: GateRegistry, topic: str) -> bool:
    """Run every gate. Quarantine on any failure. Return True iff all passed."""
    results = registry.run(row)
    failures = [r for r in results if not r.passed]
    if failures:
        path = quarantine(row, topic, results)
        logger.warning(
            "etl_row_quarantined",
            topic=topic,
            failures=[r.gate for r in failures],
            path=str(path),
        )
        return False
    return True


__all__ = [
    "GateRegistry",
    "GateResult",
    "QUARANTINE_ROOT",
    "evaluate",
    "gate_freshness",
    "gate_no_nulls",
    "gate_range",
    "gate_schema",
    "quarantine",
]
