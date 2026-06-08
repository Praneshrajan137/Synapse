"""Tests for the runtime-substance per-agent probe registry (ADR-043, C42).

Torch-free: exercises the registry dispatch + aggregation contract with synthetic
probes, and asserts the real demand_prophet probe degrades to SKIP (never FAIL,
never a fabricated PASS) when torch / the smoke checkpoint are absent — which is
exactly the local dev reality. The behavioural proof (a real checkpoint → OK)
lives in the CI training-smoke job where torch + the artifact exist.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

from scripts.audit import runtime_substance as rs
from scripts.audit.runtime_substance import RuntimeProbe, evaluate, evaluate_each


@contextlib.contextmanager
def _temp_probes(**probes: object) -> Iterator[None]:
    """Register synthetic probes for the duration of a test, then restore."""
    saved = dict(rs.PROBES)
    try:
        for name, fn in probes.items():
            rs.PROBES[name] = fn  # type: ignore[assignment]
        yield
    finally:
        rs.PROBES.clear()
        rs.PROBES.update(saved)


def test_demand_prophet_probe_is_registered() -> None:
    # INV-RS-001: every wired agent contributes exactly one runtime probe.
    assert "demand_prophet" in rs.PROBES
    assert callable(rs.PROBES["demand_prophet"])


def test_real_demand_prophet_probe_skips_or_passes_never_fails_locally() -> None:
    # The reference probe must SKIP (torch/checkpoint absent locally) or PASS
    # (CI). It must NEVER FAIL absent a real regression and NEVER fabricate a pass.
    probe = rs.PROBES["demand_prophet"]()
    assert probe.status in {"skip", "ok"}
    assert probe.detail


def test_aggregate_any_fail_makes_aggregate_fail() -> None:
    # INV-RS-002: a single failing probe turns the whole gate RED.
    with _temp_probes(
        _a=lambda: RuntimeProbe("ok", "real"),
        _b=lambda: RuntimeProbe("fail", "regressed"),
        _c=lambda: RuntimeProbe("skip", "no artifact"),
    ):
        agg = evaluate(["_a", "_b", "_c"])
        assert agg.status == "fail"
        assert "_b" in agg.detail


def test_aggregate_ok_beats_skip() -> None:
    # INV-RS-003: at least one real agent + the rest skipped → OK (progress).
    with _temp_probes(
        _a=lambda: RuntimeProbe("ok", "real"),
        _c=lambda: RuntimeProbe("skip", "no artifact"),
    ):
        agg = evaluate(["_a", "_c"])
        assert agg.status == "ok"
        assert "skipped" in agg.detail


def test_aggregate_all_skip_is_skip() -> None:
    # INV-RS-004: no prerequisites anywhere → SKIP, never a fabricated PASS.
    with _temp_probes(
        _a=lambda: RuntimeProbe("skip", "no torch"),
        _c=lambda: RuntimeProbe("skip", "no artifact"),
    ):
        agg = evaluate(["_a", "_c"])
        assert agg.status == "skip"


def test_unregistered_agent_skips_not_crashes() -> None:
    # Asking for an agent with no probe yet SKIPs honestly (ratchet-safe).
    agg = evaluate(["__nonexistent_agent__"])
    assert agg.status == "skip"


def test_evaluate_each_returns_per_agent_results() -> None:
    with _temp_probes(_a=lambda: RuntimeProbe("ok", "real")):
        per = evaluate_each(["_a"])
        assert set(per) == {"_a"}
        assert per["_a"].status == "ok"


def test_run_check_returns_one_only_on_real_failure() -> None:
    with _temp_probes(_b=lambda: RuntimeProbe("fail", "regressed")):
        assert rs.run(check=True, agents=["_b"]) == 1
    with _temp_probes(_a=lambda: RuntimeProbe("skip", "no artifact")):
        assert rs.run(check=True, agents=["_a"]) == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
