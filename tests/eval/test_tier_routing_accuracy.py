"""Tier-routing accuracy gate (Sprint 8 WS-5 §M8, I-10).

Asserts that ``TierRouter.classify`` returns each golden trace's
``expected_tier``. Per-city accuracy must clear the Sprint-8 floor
(≥75%); Sprint 9 tightens to 80% once 200 traces ship and the dataset
mirrors production volume.

The eval suite is curated for tier-classification coverage, not as a
production-traffic mix — so we test classifier *accuracy*, not the
returned-tier distribution. Sprint 9 adds the distribution gate against
production-mirrored traces.
"""

from __future__ import annotations

import pytest

from tests.eval.run import run_suite


@pytest.mark.eval
def test_tier_routing_overall_accuracy() -> None:
    _, summary = run_suite()
    accuracy = summary["correct"] / summary["total"]
    # Sprint 9 tightens to 80% against the 200-trace dataset (I-10).
    assert accuracy >= 0.80, (
        f"Tier-routing accuracy {accuracy:.2%} below Sprint-9 floor (80%); summary={summary}"
    )


@pytest.mark.eval
def test_tier_routing_per_city_accuracy() -> None:
    _, summary = run_suite()
    failures: list[str] = []
    for city, bucket in summary["per_city"].items():
        if bucket["accuracy"] < 0.80:
            failures.append(f"{city}: {bucket['accuracy']:.2%}")
    assert not failures, "Per-city tier-routing accuracy below 80% floor (Sprint 9): " + ", ".join(
        failures
    )


@pytest.mark.eval
def test_eval_suite_covers_all_tiers() -> None:
    _, summary = run_suite()
    # Each tier must appear at least once in the dataset; otherwise the
    # accuracy gate can be gamed by a dataset that only contains easy traces.
    from tests.eval.run import load_traces

    seen = {trace.expected_tier.value for trace in load_traces()}
    expected = {"tier_1", "tier_2", "tier_3", "tier_4"}
    assert expected.issubset(seen), f"Missing tiers in dataset: {expected - seen}"
