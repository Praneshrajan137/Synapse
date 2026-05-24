"""KV-cache hit-rate CI gate (Sprint 8 WS-8 §M17).

Sprint 7's KV-cache fix at ``orchestrator/llm/context_builder.py:73``
stabilised the prompt body across ``msg.status`` flips. This gate asserts
the in-process ``synapse_ollama_cache_hit_rate`` gauge clears the
Sprint-8 floor (≥0.65) when the eval suite finishes.

Sprint 9 tightens to 0.70 once the context_builder fix has stabilised
through one production cycle and we have rolling-window data.

The test reads from the Prometheus default registry by name. When no
``OLLAMA_CACHE_HIT_RATE`` samples exist (e.g., Ollama is offline in CI),
the test is skipped — Sprint 9 ships a live-Ollama integration job that
this test gates against instead.
"""

from __future__ import annotations

import pytest
from synapse_common.metrics import OLLAMA_CACHE_HIT_RATE

from tests.eval.run import run_suite

SPRINT8_FLOOR = 0.65  # retained name for log/diff stability
SPRINT9_FLOOR = 0.70  # Sprint 9: post-context_builder.py:73 stabilisation


@pytest.mark.eval
def test_kv_cache_hit_rate_floor() -> None:
    # First, run the eval suite so any cache observations have happened.
    run_suite()

    samples = []
    for metric in OLLAMA_CACHE_HIT_RATE.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total") or sample.name.endswith("_created"):
                continue
            samples.append(sample)

    if not samples:
        pytest.skip("OLLAMA_CACHE_HIT_RATE has no samples — Ollama offline in CI")

    # Aggregate across labels (model, tier).
    rate = sum(s.value for s in samples) / len(samples)
    # Sprint 9 floor (0.70) — context_builder.py:73 + Sprint-7 fix have stabilised.
    assert rate >= SPRINT9_FLOOR, (
        f"KV-cache hit rate {rate:.3f} below Sprint-9 floor {SPRINT9_FLOOR:.2f}. "
        "Investigate context_builder.py:73 + Sprint-7 KV-cache fix."
    )
