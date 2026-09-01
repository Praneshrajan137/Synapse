"""The materiality margin's rule is pre-registered; its value is re-derived, never trusted.

Feature: decision-quality-proof, task 10.4 (first half) -- R5.2, ADR-055 D2.5.

**What these tests defend.** R5.2 forbids pinning the ``(s, S)`` materiality margin before it
has been measured, while every other threshold in this phase is pinned *before* the run judged
against it. Combined naively, those two rules license choosing the margin with the number
already in hand, which decides task 11's verdict by the choice of margin. The repair is to
separate the halves: commit the derivation rule before checkpoint A, instantiate the magnitude
after it.

That separation is only worth anything if the committed value is **checked against the rule**.
Otherwise the pre-registration is decoration and the margin can still be chosen to suit the
number it judges. These tests pin the checking.

Not slow-marked: pure YAML reads and arithmetic, no engine. Locus is
``ci.yml::uplift-verify``'s fast step, which collects ``tests/uplift`` at
``-m "not slow"``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import yaml

from digital_twin.simulation.policy import (
    POLICY_PATH,
    PolicyUnavailableError,
    load_policy,
    materiality_margin,
    materiality_margin_rule,
)
from uplift.regret import classify_regret, load_objective

if TYPE_CHECKING:
    from pathlib import Path

# --- helpers ---------------------------------------------------------------


def _policy_with(tmp_path: Path, **overrides: Any) -> Path:
    """Write the committed policy to a temp file with ``materiality_margin`` overrides."""
    document = load_policy(POLICY_PATH)
    block = dict(document["regret_objective"]["materiality_margin"])
    derivation = dict(block["derivation"])
    for key, value in overrides.items():
        if key in {"value", "must_be_below_measured_headroom"}:
            block[key] = value
        else:
            derivation[key] = value
    block["derivation"] = derivation
    document["regret_objective"]["materiality_margin"] = block

    target = tmp_path / "policy.yaml"
    target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return target


# --- the committed state ---------------------------------------------------


def test_the_rule_is_committed_and_the_value_is_not() -> None:
    """The state checkpoint A must find: rule present, magnitude still owed (R5.2)."""
    rule = materiality_margin_rule()
    assert rule.form == "service_point_equivalent"
    assert rule.weight_term == "unmet_service"
    assert rule.service_points > 0.0

    assert materiality_margin() is None, (
        "the margin's VALUE must still be null before checkpoint A -- a placeholder would be "
        "judged against, which is exactly what R5.2 forbids"
    )


def test_the_rule_reads_its_weight_from_the_objective_not_a_literal() -> None:
    """AD-13: the weight is read from the objective it belongs to, never restated."""
    rule = materiality_margin_rule()
    weights = load_objective().weights
    assert rule.weight == weights[rule.weight_term]
    assert rule.derived == pytest.approx(
        rule.service_points * rule.points_to_fraction * weights[rule.weight_term]
    )


def test_the_derived_margin_is_below_the_measured_comparator_headroom() -> None:
    """ADR-055 D2.5's bracketing, as arithmetic rather than prose.

    The measured headroom is ``11.79 - 2.93 = 8.86`` objective units (session 1, seed 42, 24h).
    A margin at or above it would be unfalsifiable by construction. The lower bracket is the
    incumbent's own shortfall against its newsvendor target: ``8/9 - 0.8556`` is about 3.3
    service points, and a margin below that would call an accepted shortfall material.
    """
    rule = materiality_margin_rule()
    measured_headroom = 11.79 - 2.93
    incumbent_shortfall_points = (8.0 / 9.0 - 0.8556) * 100.0

    assert rule.derived < measured_headroom
    assert rule.service_points > incumbent_shortfall_points


def test_an_unavailable_margin_yields_the_unavailable_verdict() -> None:
    """The honest first-run verdict, and it is not `inconclusive` (I-7)."""
    verdict = classify_regret(3.0, objective=load_objective(), margin=None)
    assert verdict.verdict == "unavailable"
    assert verdict.confirms_finding_4 is False
    assert verdict.falsifies_finding_4 is False


# --- the checking that makes pre-registration binding ----------------------


def test_a_value_that_disagrees_with_its_own_rule_is_refused(tmp_path: Path) -> None:
    """The load-bearing test. A margin chosen to suit the number it judges is refused."""
    rule = materiality_margin_rule()
    target = _policy_with(tmp_path, value=rule.derived * 2.0)

    with pytest.raises(PolicyUnavailableError, match="not the value its own rule produces"):
        materiality_margin(target)


def test_a_value_the_rule_does_produce_is_accepted(tmp_path: Path) -> None:
    """The rule is a constraint, not a prohibition: the derived value passes."""
    rule = materiality_margin_rule()
    target = _policy_with(tmp_path, value=rule.derived)
    assert materiality_margin(target) == pytest.approx(rule.derived)


def test_a_margin_at_or_above_the_measured_headroom_is_refused(tmp_path: Path) -> None:
    """An unfalsifiable margin is refused even when it agrees with its rule.

    Both guards are needed. Agreeing with the rule only proves the value was derived; it does
    not prove the criterion can ever fire.
    """
    rule = materiality_margin_rule()
    target = _policy_with(tmp_path, value=rule.derived)

    with pytest.raises(PolicyUnavailableError, match="unfalsifiable"):
        materiality_margin(target, measured_headroom=rule.derived)

    # Strictly below is admissible; equal is not.
    assert materiality_margin(target, measured_headroom=rule.derived * 1.0001) is not None


def test_the_headroom_guard_is_skipped_when_the_policy_disables_it(tmp_path: Path) -> None:
    """The guard is declared in the policy, not hardcoded in the reader."""
    rule = materiality_margin_rule()
    target = _policy_with(
        tmp_path, value=rule.derived, must_be_below_measured_headroom=False
    )
    assert materiality_margin(target, measured_headroom=0.0) == pytest.approx(rule.derived)


# --- refusals rather than defaults -----------------------------------------


def test_a_missing_rule_raises_rather_than_defaulting(tmp_path: Path) -> None:
    """R5.2 defers the magnitude, not the criterion. No rule means nothing was registered."""
    document = load_policy(POLICY_PATH)
    del document["regret_objective"]["materiality_margin"]["derivation"]
    target = tmp_path / "policy.yaml"
    target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    with pytest.raises(PolicyUnavailableError, match="derivation"):
        materiality_margin_rule(target)


def test_an_unrecognised_form_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    target = _policy_with(tmp_path, form="whatever_the_number_needs")
    with pytest.raises(PolicyUnavailableError, match="unrecognised materiality-margin form"):
        materiality_margin_rule(target)


@pytest.mark.parametrize("field", ["service_points", "points_to_fraction"])
def test_a_non_positive_rule_input_is_refused(tmp_path: Path, field: str) -> None:
    """A zero margin makes every regret material; a negative one is meaningless."""
    target = _policy_with(tmp_path, **{field: 0.0})
    with pytest.raises(PolicyUnavailableError, match="strictly positive"):
        materiality_margin_rule(target)


def test_a_weight_term_absent_from_the_objective_is_refused(tmp_path: Path) -> None:
    """The rule cannot point at a weight the objective does not declare."""
    target = _policy_with(tmp_path, weight_term="not_a_term")
    with pytest.raises(PolicyUnavailableError, match="not_a_term"):
        materiality_margin_rule(target)
