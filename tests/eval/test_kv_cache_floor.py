"""KV-cache hit-rate floor gate (WS-9).

Asserts that the orchestrator's semantic-cache + KV-cache hit rate over the
golden trace set stays at or above the Sprint 9 floor of 0.70 (CLAUDE.md
"Sprint 9 KV-cache 0.70 floor").

Runs in CI as a non-skippable check IF the eval harness is available; on
environments without the harness (e.g. fresh clones without docker), the
test skips with a clear message.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "tests" / "eval" / "golden"
KV_CACHE_FLOOR = float(os.environ.get("SYNAPSE_KV_CACHE_FLOOR", "0.70"))


pytestmark = pytest.mark.evaluation


def _hit_rate_for(trace_path: Path) -> float | None:
    """Run the trace through the semantic cache and return its hit rate.

    Lazy import so collection-time failures (e.g. orchestrator deps not
    installed) become test skips rather than import errors.
    """
    try:
        from orchestrator.llm.semantic_cache import SemanticDecisionCache  # noqa: F401
    except ImportError:
        return None
    # The full eval pipeline lives in tests/eval/runner.py (Sprint 9). When
    # available we delegate to it; otherwise we mark as None so the test
    # skips cleanly rather than fakes a number.
    try:
        from tests.eval.runner import run_trace  # type: ignore[import-not-found]
    except ImportError:
        return None
    result = run_trace(trace_path)
    return float(result.get("kv_cache_hit_rate", 0.0))


def _collect_trace_paths() -> list[Path]:
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


def test_kv_cache_hit_rate_above_floor() -> None:
    """Average KV-cache hit rate across all golden traces >= floor."""
    traces = _collect_trace_paths()
    if not traces:
        pytest.skip(f"no golden traces at {GOLDEN_DIR}")
    hit_rates: list[float] = []
    for t in traces:
        rate = _hit_rate_for(t)
        if rate is None:
            pytest.skip("eval harness not available in this environment")
        hit_rates.append(rate)
    avg = sum(hit_rates) / len(hit_rates)
    assert avg >= KV_CACHE_FLOOR, (
        f"KV-cache hit rate {avg:.3f} below floor {KV_CACHE_FLOOR:.2f} "
        f"across {len(hit_rates)} traces — KV-cache regression. See "
        f"docs/runbooks/kv_cache_collapse.md"
    )
