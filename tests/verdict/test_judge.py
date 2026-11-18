"""The verdict's judgment rules, tested without running the decision stack.

Each rule of ``scripts.verdict.judge`` has a case that passes when the rule holds and fails when it
is broken: a pass on equal costs, each failure class on its own, the priority between them, and
the exact round trip of the pins through their JSON document.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.verdict.judge import (
    ARMS,
    PRIORITY,
    Measurement,
    Outcome,
    Pins,
    arm_delta,
    judge,
    pins_from_document,
    pins_to_document,
)

SEEDS = (11, 22, 33)
BASE = {"consensus": {11: 3.9, 22: 4.1, 33: 3.7}, "tuned": {11: 2.5, 22: 2.6, 33: 2.4}}
PINS = Pins(seeds=SEEDS, costs=BASE)
SAFE = {"orchestrator": 0, "sentinel+core": 0}
REPO = Path(__file__).resolve().parents[2]


def measured(
    consensus: dict[int, float] | None = None,
    tuned: dict[int, float] | None = None,
    repeats: dict[str, dict[int, float]] | None = None,
    shards: dict[str, int] | None = None,
    failures: tuple[str, ...] = (),
) -> Measurement:
    costs = {
        "consensus": {**BASE["consensus"], **(consensus or {})},
        "tuned": {**BASE["tuned"], **(tuned or {})},
    }
    return Measurement(
        costs=costs,
        repeats=repeats if repeats is not None else {"consensus": {11: costs["consensus"][11]}},
        shard_exit_codes=SAFE if shards is None else shards,
        failures=failures,
    )


def test_equal_costs_safe_shards_and_equal_repeats_pass() -> None:
    verdict = judge(PINS, measured())
    assert verdict.outcome is Outcome.PASS
    assert verdict.findings == ()
    assert all(not d.changed_seeds for d in verdict.deltas.values())


@pytest.mark.parametrize("code", [1, 2, 3, 4, 5, 124])
def test_any_non_zero_shard_exit_is_a_safety_failure(code: int) -> None:
    verdict = judge(PINS, measured(shards={"orchestrator": 0, "sentinel+core": code}))
    assert verdict.outcome is Outcome.SAFETY


def test_no_shard_at_all_is_a_safety_failure() -> None:
    assert judge(PINS, measured(shards={})).outcome is Outcome.SAFETY


def test_a_dearer_consensus_is_worse_and_a_cheaper_one_is_changed() -> None:
    worse = judge(PINS, measured(consensus={22: 4.1 + 1e-9}))
    better = judge(PINS, measured(consensus={22: 4.1 - 1e-9}))
    assert worse.outcome is Outcome.WORSE
    assert better.outcome is Outcome.CHANGED
    assert worse.deltas["consensus"].changed_seeds == (22,)


def test_the_sign_of_the_mean_decides_between_worse_and_changed() -> None:
    mixed = judge(PINS, measured(consensus={11: 3.9 + 0.3, 22: 4.1 - 0.1}))
    assert mixed.outcome is Outcome.WORSE
    assert mixed.deltas["consensus"].worse_seeds == 1
    assert mixed.deltas["consensus"].better_seeds == 1


def test_a_moved_control_outranks_a_consensus_change() -> None:
    verdict = judge(PINS, measured(consensus={11: 5.0}, tuned={11: 2.6}))
    assert verdict.outcome is Outcome.CONTROL_MOVED
    assert any("tuned control moved" in text for text in verdict.findings)
    assert any("consensus decisions changed" in text for text in verdict.findings)


def test_a_repeat_that_differs_is_nondeterminism_even_when_pins_match() -> None:
    verdict = judge(PINS, measured(repeats={"consensus": {11: 3.9 + 1e-12}}))
    assert verdict.outcome is Outcome.NONDETERMINISTIC


def test_missing_seeds_and_reported_failures_are_incomplete() -> None:
    gap = Measurement(
        costs={"consensus": {11: 3.9}, "tuned": dict(BASE["tuned"])},
        repeats={},
        shard_exit_codes=SAFE,
    )
    assert judge(PINS, gap).outcome is Outcome.INCOMPLETE
    assert judge(PINS, measured(failures=("arm exploded",))).outcome is Outcome.INCOMPLETE


def test_priority_order_is_total_and_starts_with_refusal() -> None:
    assert set(PRIORITY) == set(Outcome)
    assert PRIORITY[0] is Outcome.REFUSED_ENV
    assert PRIORITY[-1] is Outcome.PASS
    unsafe_and_worse = judge(PINS, measured(consensus={11: 9.9}, shards={"orchestrator": 1}))
    assert unsafe_and_worse.outcome is Outcome.SAFETY


def test_exit_codes_are_distinct_and_pass_is_zero() -> None:
    assert len({int(o) for o in Outcome}) == len(Outcome)
    assert int(Outcome.PASS) == 0


def test_a_single_seed_has_no_standard_error() -> None:
    assert arm_delta("consensus", {1: 1.0}, {1: 2.0}).standard_error is None
    assert arm_delta("consensus", {1: 1.0, 2: 1.0}, {1: 2.0, 2: 3.0}).standard_error == 0.5


@given(
    st.dictionaries(
        st.integers(min_value=0, max_value=2**32 - 1),
        st.tuples(
            st.floats(min_value=0.0, max_value=1e6, allow_nan=False),
            st.floats(min_value=0.0, max_value=1e6, allow_nan=False),
        ),
        min_size=1,
        max_size=20,
    )
)
def test_pins_round_trip_exactly_through_their_document(
    table: dict[int, tuple[float, float]],
) -> None:
    seeds = tuple(table)
    pins = Pins(
        seeds=seeds,
        costs={
            "consensus": {s: c for s, (c, _) in table.items()},
            "tuned": {s: t for s, (_, t) in table.items()},
        },
    )
    text = json.dumps(pins_to_document(pins, "n"), sort_keys=True, separators=(",", ":"))
    again = pins_from_document(json.loads(text))
    assert again.seeds == seeds
    for arm in ARMS:
        assert all(again.costs[arm][s].hex() == pins.costs[arm][s].hex() for s in seeds)


@given(st.sampled_from(SEEDS), st.floats(min_value=1e-12, max_value=10.0, allow_nan=False))
def test_any_rise_on_any_seed_alone_is_worse(seed: int, rise: float) -> None:
    value = BASE["consensus"][seed] + rise
    assert value != BASE["consensus"][seed]
    verdict = judge(PINS, measured(consensus={seed: value}, repeats={}))
    assert verdict.outcome is Outcome.WORSE


def test_documents_that_do_not_pin_every_seed_are_refused() -> None:
    document = pins_to_document(PINS, "n")
    document["schema"] = 2
    with pytest.raises(ValueError, match="schema"):
        pins_from_document(document)
    document = pins_to_document(PINS, "n")
    costs = document["costs"]
    assert isinstance(costs, dict)
    del costs["tuned"]["22"]
    with pytest.raises(ValueError, match="tuned"):
        pins_from_document(document)


def test_the_committed_pins_are_canonical_and_complete() -> None:
    path = REPO / "infrastructure" / "quality" / "verdict-pins.json"
    text = path.read_text(encoding="utf-8")
    document = json.loads(text)
    assert text == json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    pins = pins_from_document(document)
    assert len(pins.seeds) == len(set(pins.seeds)) == 12
    for arm in ARMS:
        assert all(math.isfinite(cost) and cost > 0 for cost in pins.costs[arm].values())


def test_a_record_that_refuses_the_physics_is_a_moved_control_not_a_gap() -> None:
    nothing = Measurement(
        costs={"consensus": {}, "tuned": {}},
        repeats={},
        shard_exit_codes=SAFE,
        physics_moved=("BprimeRecordError: the physics digest of this tree is 1, not 2",),
    )
    verdict = judge(PINS, nothing)
    assert verdict.outcome is Outcome.CONTROL_MOVED
    assert verdict.deltas == {}
    assert not any("not measured" in text for text in verdict.findings)
