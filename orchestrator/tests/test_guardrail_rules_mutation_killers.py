"""Deterministic mutation killers for the hard-guardrail engine (I-6, I-11, I-5, R5.3).

The mutants of ``orchestrator/guardrails/rules.py`` that survive ``test_guardrails.py`` sit
in four paths none of its examples can steer: the configuration-totality seam (R5.3), the
I-11 privacy scan, the threshold provider (ADR-054 D4) and the I-5 dispatch predicate. Each
test below pins one documented behaviour there with a hand-built input and an exact expected
value - the refusal texts and rule ids, the scan's paths and its node budget at equality,
the log events - and the mutation runner names this file first so ``-x`` ends a killed
mutant's run here.

Killed by collection, not by an assertion: altering either key in the ``HARD_GUARDRAILS``
lookup that defines ``DEFAULT_CONFIDENCE_FLOOR`` raises ``KeyError`` at import.
mutmut 2.5 counts only pytest exit status 1 as a kill, and a collection error in a one-file
run exits 2, so both read as survivors; with this file first under ``-x``, the next file's
collection stops the session as failed (exit 1).

No Hypothesis, no network, no sleep, no production change. The I-11 field names are spelled
out rather than imported, so a name dropped from a committed table turns this file red
instead of silently shrinking what it checks.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

import pytest
import structlog
from structlog.testing import capture_logs
from synapse_common.models import ConsensusDecision, DecisionTier

from orchestrator.guardrails.rules import (
    BLOCKING_ENFORCEMENTS,
    CROSS_STORE_RECIPIENT_FIELDS,
    DEFAULT_CONFIDENCE_FLOOR,
    HARD_GUARDRAILS,
    RAW_DEMAND_FIELDS,
    STORE_IDENTITY_FIELDS,
    GuardrailConfigurationError,
    GuardrailEngine,
    PrivacyScan,
    check_method_name,
    satisfies_confidence_floor,
    scan_privacy_boundary,
    unimplemented_guardrails,
    validate_guardrail_configuration,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from structlog.typing import EventDict

#: A confidence above the committed 0.7 floor, so I-5 never decides a test about another rule.
ABOVE_THE_FLOOR: Final[float] = 0.85

#: Fields that name a store: two distinct values put an action across a store boundary.
STORE_FIELDS: Final[tuple[str, ...]] = (
    "store_id",
    "source_store_id",
    "origin_store_id",
    "from_store_id",
    "target_store_id",
    "destination_store_id",
    "to_store_id",
    "recipient_store_id",
    "peer_store_id",
)

#: Fields whose presence alone declares a send to another store.
RECIPIENT_FIELDS: Final[tuple[str, ...]] = (
    "share_with",
    "shared_with",
    "recipients",
    "broadcast_to",
    "peer_stores",
    "target_stores",
    "destination_stores",
)

#: Raw, store-local demand: only derived quantities may leave a store (I-11, DPDPA 2023).
RAW_FIELDS: Final[tuple[str, ...]] = (
    "raw_data",
    "raw_demand",
    "raw_demand_series",
    "raw_orders",
    "order_history",
    "order_ids",
    "customer_id",
    "customer_ids",
    "customer_orders",
    "demand_history",
    "transactions",
    "basket_history",
)

#: The refusal for an action the scan could not finish: unverifiable is blocked, never clean.
TRUNCATION_REFUSAL: Final[str] = (
    "Privacy boundary BLOCKED: selected action exceeded the 10000-node scan budget; "
    "cross-store raw demand could not be ruled out"
)


# ---------------------------------------------------------------------------
# Fixtures and builders
# ---------------------------------------------------------------------------


@pytest.fixture
def captured_events() -> Iterator[list[EventDict]]:
    """Every structlog event emitted during the test, whatever the ambient configuration.

    The capture ``packages/tests/test_chain_walk_mutation_killers.py`` uses: an unfiltered
    wrapper for the test, and the caller's configuration restored afterwards.
    """
    saved = structlog.get_config()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        cache_logger_on_first_use=False,
    )
    try:
        with capture_logs() as events:
            yield events
    finally:
        structlog.configure(**saved)


class _MovableBoundary:
    """A threshold provider whose value a configuration reload can move (ADR-054 D4)."""

    def __init__(self, value: float) -> None:
        self.value = value

    def current(self) -> float:
        return self.value

    def reload(self) -> None:
        """Nothing to re-read: the test moves ``value`` itself."""


def _decision(
    action: dict[str, Any],
    *,
    confidence: float = ABOVE_THE_FLOOR,
    escalated: bool = False,
) -> ConsensusDecision:
    """A decision whose only free parts are the selected action and the I-5 inputs."""
    return ConsensusDecision(
        tier=DecisionTier.TIER_2,
        proposals=[],
        selected_action=action,
        pareto_weights={"demand_accuracy": 1.0},
        confidence=confidence,
        escalated_to_human=escalated,
        audit_trace=["test"],
    )


# ---------------------------------------------------------------------------
# R5.3: every declared rule resolves to a check, or the table is refused
# ---------------------------------------------------------------------------


def test_each_rule_without_a_check_is_reported_sorted_with_its_declared_enforcement() -> None:
    """By default EVERY declared rule needs a check - stricter than the blocking subset.

    The enforcement is reported as declared, normalised; a rule that declares none is
    reported with an empty one rather than a guessed one.
    """
    config = {
        "zeta_rule": {"enforcement": "BLOCK"},
        "alpha_rule": {"enforcement": " clip "},
        "mid_rule": {"rule": "declares no enforcement"},
        "checked_rule": {"enforcement": "REJECT"},
    }
    assert unimplemented_guardrails(config, frozenset({"_check_checked_rule"})) == (
        ("alpha_rule", "CLIP"),
        ("mid_rule", ""),
        ("zeta_rule", "BLOCK"),
    )


def test_the_blocking_subset_needs_a_check_only_where_a_violation_withholds_dispatch() -> None:
    """``BLOCKING_ENFORCEMENTS`` narrows totality to BLOCK, REJECT and ESCALATE rules."""
    config = {
        "a_clip_rule": {"enforcement": "CLIP"},
        "b_block_rule": {"enforcement": "BLOCK"},
        "c_reject_rule": {"enforcement": "REJECT"},
        "d_escalate_rule": {"enforcement": "ESCALATE"},
        "e_undeclared_rule": {"rule": "declares no enforcement"},
    }
    assert frozenset({"BLOCK", "REJECT", "ESCALATE"}) == BLOCKING_ENFORCEMENTS
    narrowed = unimplemented_guardrails(
        config,
        frozenset(),
        enforcements_requiring_check=BLOCKING_ENFORCEMENTS,
    )
    assert narrowed == (
        ("b_block_rule", "BLOCK"),
        ("c_reject_rule", "REJECT"),
        ("d_escalate_rule", "ESCALATE"),
    )
    every_rule = unimplemented_guardrails(config, frozenset())
    assert [rule for rule, _ in every_rule] == sorted(config)


def test_a_table_that_is_not_total_is_refused_naming_every_unenforceable_rule() -> None:
    """The refusal names each rule, its declared enforcement and the check it expected.

    ``service_level_minimum`` resolves through its alias to ``_check_service_level``.
    """
    config = {
        "service_level_minimum": {"enforcement": "ESCALATE"},
        "shadow_rule": {"enforcement": "BLOCK"},
        "silent_rule": {"rule": "declares no enforcement"},
    }
    with pytest.raises(GuardrailConfigurationError) as refused:
        validate_guardrail_configuration(config, frozenset({"_check_service_level"}))

    expected = (
        "Guardrail configuration is not total: 2 declared rule(s) have no check function: "
        "shadow_rule (enforcement=BLOCK, expected _check_shadow_rule()); "
        "silent_rule (enforcement=UNDECLARED, expected _check_silent_rule())"
    )
    assert refused.value.unimplemented == (("shadow_rule", "BLOCK"), ("silent_rule", ""))
    assert str(refused.value) == expected


def test_an_engine_is_never_built_over_a_rule_it_cannot_enforce() -> None:
    """R5.3 at construction: a guardrail that cannot bite is refused, not a silent no-op."""
    with pytest.raises(GuardrailConfigurationError) as refused:
        GuardrailEngine(
            guardrails={
                "privacy_boundary": {"enforcement": "BLOCK"},
                "unenforceable_rule": {"enforcement": "REJECT"},
            },
        )
    assert refused.value.unimplemented == (("unenforceable_rule", "REJECT"),)


def test_the_committed_table_and_the_engine_declare_the_same_checks() -> None:
    """Each committed rule resolves to exactly one implemented check, read off the class.

    ``available_check_functions`` is a classmethod, so a candidate table can be judged
    before any engine exists, and it names check functions and nothing else.
    """
    checks = frozenset(
        {
            "_check_confidence_floor",
            "_check_essential_price_cap",
            "_check_privacy_boundary",
            "_check_rider_shift_limit",
            "_check_service_level",
        },
    )
    assert GuardrailEngine.available_check_functions() == checks
    assert frozenset(check_method_name(rule) for rule in HARD_GUARDRAILS) == checks


# ---------------------------------------------------------------------------
# I-11: what the privacy scan reads, and what it reports
# ---------------------------------------------------------------------------


def test_each_named_store_field_places_the_action_in_the_store_it_names() -> None:
    """A store identity may sit under any of the nine store fields, and each one is read."""
    assert frozenset(STORE_FIELDS) == STORE_IDENTITY_FIELDS
    placed = {name: scan_privacy_boundary({name: "store-a"}).store_ids for name in STORE_FIELDS}
    assert placed == dict.fromkeys(STORE_FIELDS, ("store-a",))


def test_only_a_non_empty_string_under_a_store_field_names_a_store() -> None:
    """An empty or non-string store value names no store, and other strings are not stores."""
    scan = scan_privacy_boundary(
        {
            "store_id": "store-a",
            "peer_store_id": "",
            "to_store_id": 7,
            "note": "restock",
            "sku_id": "SKU001",
        },
    )
    assert scan.store_ids == ("store-a",)


def test_each_named_recipient_field_declares_a_send_to_another_store() -> None:
    """A recipient field crosses a boundary even when no second store identity appears."""
    assert frozenset(RECIPIENT_FIELDS) == CROSS_STORE_RECIPIENT_FIELDS
    sends = {name: scan_privacy_boundary({name: ["store-b"]}) for name in RECIPIENT_FIELDS}
    declared = {name: scan.recipient_paths for name, scan in sends.items()}
    assert declared == {name: (name,) for name in RECIPIENT_FIELDS}
    assert all(scan.crosses_store_boundary for scan in sends.values())


def test_each_named_raw_demand_field_marks_a_raw_payload() -> None:
    """Each of the twelve raw-demand names is reported, at the path where it sits."""
    assert frozenset(RAW_FIELDS) == RAW_DEMAND_FIELDS
    found = {name: scan_privacy_boundary({name: [1]}).raw_demand_paths for name in RAW_FIELDS}
    assert found == {name: (name,) for name in RAW_FIELDS}


def test_none_and_empty_containers_carry_no_payload_and_any_other_value_does() -> None:
    """``_is_present``: an absent or empty value is not a payload; a scalar, even 0, is one."""
    values: dict[str, object] = {
        "None": None,
        "empty str": "",
        "empty bytes": b"",
        "empty list": [],
        "empty tuple": (),
        "empty dict": {},
        "empty set": set(),
        "empty frozenset": frozenset(),
        "one-item list": [5],
        "one-character str": "x",
        "zero": 0,
    }
    reported = {
        case: (
            scan_privacy_boundary({"raw_demand": value}).raw_demand_paths,
            scan_privacy_boundary({"share_with": value}).recipient_paths,
        )
        for case, value in values.items()
    }
    absent: tuple[tuple[str, ...], tuple[str, ...]] = ((), ())
    present: tuple[tuple[str, ...], tuple[str, ...]] = (("raw_demand",), ("share_with",))
    assert reported == {
        "None": absent,
        "empty str": absent,
        "empty bytes": absent,
        "empty list": absent,
        "empty tuple": absent,
        "empty dict": absent,
        "empty set": absent,
        "empty frozenset": absent,
        "one-item list": present,
        "one-character str": present,
        "zero": present,
    }


def test_raw_demand_violates_the_boundary_only_when_it_crosses_one() -> None:
    """I-11 forbids raw demand CROSSING a store boundary; inside one store it is not blocked.

    Two distinct store values, or any declared recipient, cross; derived figures may cross.
    """
    actions: dict[str, dict[str, Any]] = {
        "raw demand inside one store": {"store_id": "store-a", "raw_demand": [5]},
        "one store named twice": {
            "store_id": "store-a",
            "peer_store_id": "store-a",
            "raw_demand": [5],
        },
        "raw demand between two stores": {
            "source_store_id": "store-a",
            "target_store_id": "store-b",
            "raw_demand": [5],
        },
        "raw demand sent to a recipient": {"raw_demand": [5], "share_with": ["store-b"]},
        "derived figures between two stores": {
            "source_store_id": "store-a",
            "target_store_id": "store-b",
            "forecast": [10.5],
        },
    }
    scans = {case: scan_privacy_boundary(action) for case, action in actions.items()}
    verdicts = {
        case: (scan.crosses_store_boundary, scan.violates_privacy_boundary)
        for case, scan in scans.items()
    }
    assert verdicts == {
        "raw demand inside one store": (False, False),
        "one store named twice": (False, False),
        "raw demand between two stores": (True, True),
        "raw demand sent to a recipient": (True, True),
        "derived figures between two stores": (True, False),
    }


def test_a_scan_reports_each_payload_where_it_sits_through_nested_mappings_and_lists() -> None:
    """Paths join mapping keys with ``.`` and list positions with ``[i]``, from the root."""
    scan = scan_privacy_boundary(
        {
            "store_id": "store-a",
            "transfers": [{"to_store_id": "store-b", "order_history": [5]}],
            "plan": {"recipients": ["store-c"]},
        },
    )
    assert scan == PrivacyScan(
        store_ids=("store-a", "store-b"),
        raw_demand_paths=("transfers[0].order_history",),
        recipient_paths=("plan.recipients",),
        truncated=False,
    )


def test_a_scan_reads_exactly_its_budget_of_nodes_and_is_unfinished_one_node_past_it() -> None:
    """Each node read costs one: the budget-th node is still read, the next one is not.

    An unfinished scan fails closed: it violates the boundary with nothing found (I-7).
    """
    # Nodes: the mapping, its list, then one per number.
    assert scan_privacy_boundary({"forecast": [1, 2]}, max_nodes=4).truncated is False
    unfinished = scan_privacy_boundary({"forecast": [1, 2, 3]}, max_nodes=4)
    assert unfinished.truncated is True
    assert unfinished.violates_privacy_boundary is True


def test_the_default_budget_judges_ten_thousand_nodes_and_refuses_one_more(
    captured_events: list[EventDict],
) -> None:
    """The 10,000-node default: at it the action is judged, one node past it is refused."""
    engine = GuardrailEngine()
    # Nodes: the mapping, its list, then one per reading.
    at_the_budget = _decision({"readings": [0] * 9_998})
    one_past_it = _decision({"readings": [0] * 9_999})

    assert engine.validate_decision(at_the_budget) == (True, [])
    assert engine.validate_decision(one_past_it) == (False, [TRUNCATION_REFUSAL])
    assert captured_events == [
        {
            "event": "privacy_boundary_unverifiable",
            "log_level": "error",
            "scan_budget": 10_000,
            "enforcement": "BLOCK",
        },
    ]


def test_cross_store_raw_demand_is_blocked_naming_its_paths_stores_and_recipients(
    captured_events: list[EventDict],
) -> None:
    """The refusal and its log name where the raw payload sits and how it crosses.

    Each list is joined in sorted order, and ``none`` stands in for an empty one.
    """
    engine = GuardrailEngine()
    between_stores = _decision(
        {
            "source_store_id": "store-a",
            "target_store_id": "store-b",
            "raw_demand": [12, 7],
            "transactions": [{"sku_id": "SKU001"}],
        },
    )
    to_recipients = _decision(
        {
            "forecast": {"raw_orders": [3]},
            "share_with": ["store-c"],
            "broadcast_to": ["store-d"],
        },
    )
    between_refusal = (
        "Privacy boundary BLOCKED: raw demand payload at raw_demand, transactions "
        "crosses a store boundary (stores=store-a, store-b; recipients=none)"
    )
    recipients_refusal = (
        "Privacy boundary BLOCKED: raw demand payload at forecast.raw_orders "
        "crosses a store boundary (stores=none; recipients=broadcast_to, share_with)"
    )

    assert engine.validate_decision(between_stores) == (False, [between_refusal])
    assert engine.validate_decision(to_recipients) == (False, [recipients_refusal])
    assert captured_events == [
        {
            "event": "privacy_boundary_violation",
            "log_level": "error",
            "raw_demand_paths": ["raw_demand", "transactions"],
            "store_ids": ["store-a", "store-b"],
            "recipient_paths": [],
            "enforcement": "BLOCK",
        },
        {
            "event": "privacy_boundary_violation",
            "log_level": "error",
            "raw_demand_paths": ["forecast.raw_orders"],
            "store_ids": [],
            "recipient_paths": ["broadcast_to", "share_with"],
            "enforcement": "BLOCK",
        },
    ]


def test_a_blocked_action_is_refused_alone_before_any_rule_can_clip_it() -> None:
    """R5.2: BLOCK is evaluated first and returns alone, so a refused action is never mutated.

    Both actions also price rice above the 1.3x essential cap; had the price rule run, it
    would have clipped the multiplier and added a violation of its own.
    """
    engine = GuardrailEngine()
    unverifiable = _decision(
        {
            "readings": [0] * 10_000,
            "pricing_actions": [{"category": "rice", "multiplier": 1.5}],
        },
    )
    crossing = _decision(
        {
            "store_id": "store-a",
            "peer_store_id": "store-b",
            "raw_demand": [4],
            "pricing_actions": [{"category": "rice", "multiplier": 1.5}],
        },
    )
    crossing_refusal = (
        "Privacy boundary BLOCKED: raw demand payload at raw_demand crosses a store boundary "
        "(stores=store-a, store-b; recipients=none)"
    )

    assert engine.validate_decision(unverifiable) == (False, [TRUNCATION_REFUSAL])
    assert engine.validate_decision(crossing) == (False, [crossing_refusal])
    for decision in (unverifiable, crossing):
        assert decision.selected_action["pricing_actions"][0]["multiplier"] == 1.5


# ---------------------------------------------------------------------------
# I-5: the escalation boundary, read per validation, and the dispatch predicate
# ---------------------------------------------------------------------------


def test_the_default_engine_escalates_below_seven_tenths_and_passes_at_it() -> None:
    """The committed default boundary is 0.7: equality passes, and a refusal states both."""
    engine = GuardrailEngine()
    assert engine.confidence_threshold == 0.7
    assert engine.validate_decision(_decision({}, confidence=0.7)) == (True, [])
    assert engine.validate_decision(_decision({}, confidence=0.69)) == (
        False,
        ["Confidence 0.690 below threshold 0.7"],
    )


def test_the_boundary_is_read_from_its_provider_on_every_validation() -> None:
    """ADR-054 D4 / R5.4: moving the bound provider moves the gate, with no new engine."""
    boundary = _MovableBoundary(0.8)
    engine = GuardrailEngine(confidence_threshold=boundary)
    decision = _decision({}, confidence=0.75)
    assert engine.threshold_provider is boundary
    assert engine.validate_decision(decision) == (
        False,
        ["Confidence 0.750 below threshold 0.8"],
    )

    boundary.value = 0.7
    assert engine.confidence_threshold == 0.7
    assert engine.validate_decision(decision) == (True, [])


def test_dispatch_needs_the_floor_or_a_human_and_the_floor_defaults_to_the_table() -> None:
    """I-5's precondition: at or above the floor, or already escalated to a human.

    With no floor stated, the floor is the committed table's default, read from the table.
    """
    assert HARD_GUARDRAILS["confidence_floor"]["default_threshold"] == DEFAULT_CONFIDENCE_FLOOR
    assert DEFAULT_CONFIDENCE_FLOOR == 0.7
    verdicts = {
        "at the default floor": satisfies_confidence_floor(_decision({}, confidence=0.7)),
        "above it": satisfies_confidence_floor(_decision({}, confidence=0.9)),
        "below it": satisfies_confidence_floor(_decision({}, confidence=0.69)),
        "below it, escalated to a human": satisfies_confidence_floor(
            _decision({}, confidence=0.69, escalated=True),
        ),
        "at a stated floor": satisfies_confidence_floor(
            _decision({}, confidence=0.8),
            confidence_floor=0.8,
        ),
        "under a stated floor": satisfies_confidence_floor(
            _decision({}, confidence=0.75),
            confidence_floor=0.8,
        ),
    }
    assert verdicts == {
        "at the default floor": True,
        "above it": True,
        "below it": False,
        "below it, escalated to a human": True,
        "at a stated floor": True,
        "under a stated floor": False,
    }
