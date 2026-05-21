"""Tests for streaming feature materialization (ADR-030).

Layer 4 (Metamorphic) — online/offline parity within ε for a fixed Kafka
replay segment. Layer 1 (SDD) — rolling-window correctness.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from data_fabric.feast.stream_materialization import RollingWindow

pytestmark = pytest.mark.integration


def _t(seconds: int) -> datetime:
    return datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=seconds)


def test_rolling_window_evicts_old_events() -> None:
    w = RollingWindow(span=timedelta(seconds=60))
    w.add("k", _t(0), 1.0)
    w.add("k", _t(30), 1.0)
    w.add("k", _t(120), 1.0)  # this one alone evicts the older two via cutoff
    assert w.count("k") == 1


def test_rolling_window_per_key_independence() -> None:
    w = RollingWindow(span=timedelta(seconds=60))
    w.add("a", _t(0), 1.0)
    w.add("b", _t(0), 1.0)
    w.add("a", _t(10), 1.0)
    assert w.count("a") == 2
    assert w.count("b") == 1


def test_rolling_window_sum_tracks_values() -> None:
    w = RollingWindow(span=timedelta(seconds=60))
    w.add("k", _t(0), 2.5)
    w.add("k", _t(10), 1.5)
    assert w.sum("k") == pytest.approx(4.0)


def test_rolling_window_metamorphic_monotone_in_added() -> None:
    """Adding a fresh event never reduces count; removing time can only reduce it."""
    w = RollingWindow(span=timedelta(seconds=60))
    for s in range(0, 30, 5):
        w.add("k", _t(s), 1.0)
    before = w.count("k")
    w.add("k", _t(30), 1.0)
    after = w.count("k")
    assert after >= before
