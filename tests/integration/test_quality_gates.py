"""Tests for `data_fabric.etl.quality_gates` — Layer 4 (Metamorphic) + SDD.

Covers ADR-026: idempotency, commutativity of independent gates, and the
quarantine path (no silent drops).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from data_fabric.etl.quality_gates import (
    GateRegistry,
    GateResult,
    evaluate,
    gate_freshness,
    gate_no_nulls,
    gate_range,
    quarantine,
)


@pytest.fixture(autouse=True)
def _quarantine_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "data_fabric.etl.quality_gates.QUARANTINE_ROOT", tmp_path / "quarantine"
    )


def test_no_nulls_passes_when_complete() -> None:
    gate = gate_no_nulls(["a", "b"])
    assert gate({"a": 1, "b": 2}).passed


def test_no_nulls_fails_on_missing_field() -> None:
    gate = gate_no_nulls(["a", "b"])
    result = gate({"a": 1})
    assert not result.passed
    assert "b" in result.detail


def test_range_rejects_out_of_bounds() -> None:
    gate = gate_range("temp", 0.0, 30.0)
    assert gate({"temp": 15.0}).passed
    assert not gate({"temp": -1.0}).passed
    assert not gate({"temp": 100.0}).passed


def test_range_rejects_non_numeric() -> None:
    gate = gate_range("temp", 0.0, 30.0)
    assert not gate({"temp": "hot"}).passed


def test_freshness_passes_recent_row() -> None:
    gate = gate_freshness("ts", max_age_seconds=60.0)
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    assert gate({"ts": now_iso}).passed


def test_freshness_rejects_stale_row() -> None:
    gate = gate_freshness("ts", max_age_seconds=10.0)
    stale = (datetime.now(UTC) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    assert not gate({"ts": stale}).passed


def test_evaluate_quarantines_failures(tmp_path: Path) -> None:
    reg = GateRegistry()
    reg.register("range", gate_range("temp", 0.0, 30.0))

    bad = {"temp": 100.0}
    assert evaluate(bad, reg, topic="weather") is False

    good = {"temp": 22.0}
    assert evaluate(good, reg, topic="weather") is True


def test_metamorphic_independent_gates_commute() -> None:
    """If two gates inspect disjoint fields the order of registration doesn't change outcome."""
    reg_a = GateRegistry()
    reg_a.register("range_a", gate_range("a", 0.0, 1.0))
    reg_a.register("range_b", gate_range("b", 0.0, 1.0))

    reg_b = GateRegistry()
    reg_b.register("range_b", gate_range("b", 0.0, 1.0))
    reg_b.register("range_a", gate_range("a", 0.0, 1.0))

    row = {"a": 0.5, "b": 0.5}
    a = [r.passed for r in reg_a.run(row)]
    b = [r.passed for r in reg_b.run(row)]
    assert sorted(a) == sorted(b)


def test_idempotent_quarantine_appends() -> None:
    """Same bad row quarantined twice produces two records — append-only, never overwrite."""
    reasons = [GateResult("g", False, "bad"), GateResult("h", True)]
    p1 = quarantine({"x": 1}, "test_topic", reasons)
    p2 = quarantine({"x": 1}, "test_topic", reasons)
    assert p1 == p2
    lines = p1.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
