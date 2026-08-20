"""Property-based test for guardrail configuration totality (task 8.4, design E3).

Feature: purpose-achievement-audit, Property 23: Guardrail configuration is total

    *For any* guardrail configuration map, engine construction succeeds iff every
    declared rule resolves to a check function, and a declared rule with no
    implementation fails construction naming that rule.

Why the property is shaped this way
-----------------------------------

The audit finding behind Requirement 5.3 was quality item 18: ``privacy_boundary`` was
declared with enforcement ``BLOCK`` and had no check function, so the strongest
enforcement in the table was a dictionary entry and nothing else. Two distinct failure
modes have to be excluded, and an example test can only exclude the first for the shapes
it happens to enumerate:

1. **A declaration with no implementation.** The table is data, so its shape is open:
   any future entry can reintroduce the hole. The property therefore drives arbitrary
   table shapes - committed entries, entries re-declared with a different enforcement,
   invented entries, and adversarial names that *nearly* resolve (``"privacy_boundary "``
   with a trailing space) - and asserts the biconditional, not just one direction. A
   construction that succeeds while a declared rule resolves to nothing is the original
   defect; a construction that fails while every rule resolves is a gate that cries wolf.

2. **A silent downgrade.** ``validate_decision`` returns ``all_clipped`` as its verdict
   (``rules.py``), so a *blocking* rule whose violation message happened to contain the
   word "clipped" would report ``passed=True`` - a BLOCK degraded to a clip by wording
   alone. The witness table below violates each declared blocking rule in turn and
   asserts the verdict is ``False``, that the attributable violation is not clip-worded,
   that the action is not mutated into compliance, and that a genuine clip-class
   violation raised alongside cannot rescue it. The declared-to-enforced mapping is
   asserted total: every entry of ``HARD_GUARDRAILS`` must have a witness, so adding a
   rule to the table without an observable enforcement fails this test.

The independent oracle is deliberate. ``expected_check_name`` and ``EXPECTED_BLOCKING``
restate the resolution rule and the blocking vocabulary in this file rather than
importing them, so the test compares two implementations instead of asserting that the
subject agrees with itself. ``BLOCKING_ENFORCEMENTS`` is then pinned against the local
restatement, which is what makes the vocabulary drift-detectable.

Thresholds are read from the committed table (``max_multiplier``, ``max_hours``,
``min_fill_rate``, ``default_threshold``), never written as literals here: a property
that hardcoded ``1.3`` would keep passing after the cap was relaxed.

Scope, and what is deliberately not driven
------------------------------------------

The subject is the guardrail *configuration* and ``validate_decision``. The real
``ConsensusProtocol`` is never constructed and no dispatch is attempted: that is
Property 22's job, it is ``@pytest.mark.slow``, and it runs in ``ci.yml::uplift-verify``.
Nothing here needs the SimPy twin, Postgres, or a subprocess, so this test is not slow.

``guardrails.rules.execute_consensus`` is also never called. Task 12.1a repaired the
conflict this paragraph used to record - its ``@deal.pre`` no longer hardcodes ``0.7``;
the boundary in force is passed in, and the same predicate runs as a pre-flight before
the I-4 append - and Property 22 owns the statement about it, over the whole unit
interval.

What has **not** changed is ``compliant_confidences``'s ``[default_threshold, 1.0]``
range, and that is a constraint rather than a preference. The subject here is the
configuration seam and ``validate_decision``, and every generative clause below needs a
violation to be *attributable* to the rule under test. ``validate_decision`` returns as
soon as the confidence rule fails (``rules.py``), so a sub-threshold confidence would
pre-empt ``_check_service_level`` entirely and the ``service_level_minimum`` witness
would lose its evidence; and ``test_the_declared_clip_stays_a_clip`` needs a verdict of
``True`` from a real engine at the committed boundary, which a sub-threshold confidence
makes impossible. Widening this range to ``0.0`` would therefore turn several clauses red
without adding a statement about anything - the sub-boundary region belongs to Property
22, which drives the choke point, and to Property 24, which drives the reload seam. The
range is read from the committed table, never written as a literal, so it tracks the
default rather than pinning it.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 5.3**
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.models import ConsensusDecision, DecisionTier

from orchestrator.guardrails.rules import (
    BLOCKING_ENFORCEMENTS,
    CROSS_STORE_RECIPIENT_FIELDS,
    ESSENTIAL_CATEGORIES,
    HARD_GUARDRAILS,
    RAW_DEMAND_FIELDS,
    GuardrailConfigurationError,
    GuardrailEngine,
    check_method_name,
    unimplemented_guardrails,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

# --------------------------------------------------------------------------- oracles

#: The enforcements that withhold dispatch, restated independently of the subject.
#: R5.3 names exactly these three; the pin below turns any drift in the module's own
#: ``BLOCKING_ENFORCEMENTS`` into a failure rather than a silent redefinition.
EXPECTED_BLOCKING: Final[frozenset[str]] = frozenset({"BLOCK", "REJECT", "ESCALATE"})

#: The one enforcement that is honestly not a veto: I-6 says "price cap <= 1.3x", and a
#: clip satisfies a cap. It must stay a clip (requirements.md, excluded-perfectionism).
EXPECTED_CLIP: Final[str] = "CLIP"

#: The rule-to-check-function aliases, restated so the resolution rule has an oracle.
EXPECTED_ALIASES: Final[Mapping[str, str]] = {"service_level_minimum": "_check_service_level"}


def expected_check_name(rule_name: str) -> str:
    """The check function *rule_name* must resolve to, computed independently."""
    return EXPECTED_ALIASES.get(rule_name, f"_check_{rule_name}")


def declared_enforcement(spec: Mapping[str, Any]) -> str:
    """Normalise a declared enforcement the way a configuration reader must."""
    return str(spec.get("enforcement", "")).strip().upper()


def expected_missing(
    config: Mapping[str, Mapping[str, Any]],
    available: frozenset[str],
    *,
    blocking_only: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Declared rules resolving to no available check, recomputed from scratch."""
    missing: list[tuple[str, str]] = []
    for rule_name in sorted(config):
        enforcement = declared_enforcement(config[rule_name])
        if blocking_only and enforcement not in EXPECTED_BLOCKING:
            continue
        if expected_check_name(rule_name) not in available:
            missing.append((rule_name, enforcement))
    return tuple(missing)


# ------------------------------------------------------- committed configuration values

#: Every bound below is read from the committed table, never restated as a literal.
CAP: Final[float] = float(HARD_GUARDRAILS["essential_price_cap"]["max_multiplier"])
MAX_SHIFT_HOURS: Final[float] = float(HARD_GUARDRAILS["rider_shift_limit"]["max_hours"])
MIN_FILL_RATE: Final[float] = float(HARD_GUARDRAILS["service_level_minimum"]["min_fill_rate"])
THRESHOLD: Final[float] = float(HARD_GUARDRAILS["confidence_floor"]["default_threshold"])

_ID_ALPHABET: Final[str] = "abcdefghijklmnopqrstuvwxyz0123456789_"

#: Names that resolve to no check function today but read as though they might.
ADVERSARIAL_NAMES: Final[tuple[str, ...]] = (
    "privacy_boundary ",
    " privacy_boundary",
    "PRIVACY_BOUNDARY",
    "check_privacy_boundary",
    "_check_privacy_boundary",
    "service_level",
    "privacy",
)

#: Declared-enforcement variants, including case and whitespace noise (a reader that
#: does not normalise would treat " block " as non-blocking and skip the requirement).
ENFORCEMENT_VARIANTS: Final[tuple[str, ...]] = (
    "BLOCK",
    "block",
    " Block ",
    "REJECT",
    "reject",
    "ESCALATE",
    " escalate",
    EXPECTED_CLIP,
    "clip",
    "WARN",
    "",
)


def decision(action: dict[str, Any], confidence: float) -> ConsensusDecision:
    """A minimal Tier-1 decision carrying *action* - the shape the engine validates."""
    return ConsensusDecision(
        tier=DecisionTier.TIER_1,
        proposals=[],
        selected_action=action,
        pareto_weights={"demand_accuracy": 1.0},
        confidence=confidence,
        audit_trace=["property-23"],
    )


# ------------------------------------------------------------------------- strategies


def rule_names() -> st.SearchStrategy[str]:
    """Rule names spanning implemented, aliased, adversarial, and invented."""
    return st.one_of(
        st.sampled_from(sorted(HARD_GUARDRAILS)),
        st.sampled_from(ADVERSARIAL_NAMES),
        st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=14),
    )


def enforcement_declarations() -> st.SearchStrategy[str | None]:
    """A declared enforcement, or ``None`` meaning the key is absent entirely."""
    return st.one_of(
        st.none(),
        st.sampled_from(ENFORCEMENT_VARIANTS),
        st.text(alphabet=_ID_ALPHABET, max_size=8),
    )


@st.composite
def guardrail_configurations(draw: st.DrawFn) -> dict[str, dict[str, Any]]:
    """An arbitrary ``HARD_GUARDRAILS``-shaped table.

    Built from a subset of the committed entries plus generated entries, so the sample
    space spans the total committed table, a table with a hole, a table whose committed
    entry is re-declared with a different enforcement, and the empty table.
    """
    kept = draw(
        st.lists(
            st.sampled_from(sorted(HARD_GUARDRAILS)),
            unique=True,
            max_size=len(HARD_GUARDRAILS),
        ),
    )
    config: dict[str, dict[str, Any]] = {
        name: dict(HARD_GUARDRAILS[name]) for name in kept
    }

    generated = draw(
        st.lists(
            st.tuples(rule_names(), enforcement_declarations()),
            unique_by=lambda pair: pair[0],
            max_size=4,
        ),
    )
    for name, enforcement in generated:
        spec: dict[str, Any] = {"rule": "generated declaration"}
        if enforcement is not None:
            spec["enforcement"] = enforcement
        config[name] = spec
    return config


class Witness(NamedTuple):
    """An action that violates exactly one declared rule, and how to recognise it."""

    rule: str
    action: dict[str, Any]
    confidence: float
    #: Lowercase tokens the violation attributable to *rule* must all contain.
    evidence: tuple[str, ...]


def compliant_confidences() -> st.SearchStrategy[float]:
    """Confidences at or above the committed boundary - the confidence rule stays quiet."""
    return st.floats(
        min_value=THRESHOLD,
        max_value=1.0,
        allow_nan=False,
        allow_infinity=False,
    )


def store_ids(count: int) -> st.SearchStrategy[list[str]]:
    """Distinct store identifiers that do not contain the ``clip`` token.

    ``validate_decision`` derives its verdict from the *wording* of a violation, and a
    privacy violation interpolates these identifiers into its message. Excluding the
    token keeps the clip/no-clip assertions below about the engine's wording rather
    than about an accident of generated data.
    """
    return st.lists(
        st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=8).filter(
            lambda value: "clip" not in value,
        ),
        min_size=count,
        max_size=count,
        unique=True,
    )


@st.composite
def privacy_witnesses(draw: st.DrawFn) -> Witness:
    """BLOCK: a raw demand payload crossing a store boundary (I-11)."""
    field = draw(st.sampled_from(sorted(RAW_DEMAND_FIELDS)))
    payload = draw(
        st.lists(st.integers(min_value=0, max_value=99), min_size=1, max_size=4),
    )
    action: dict[str, Any] = {"action_type": "transfer", field: payload}
    if draw(st.booleans()):
        source, target = draw(store_ids(2))
        action["source_store_id"] = source
        action["target_store_id"] = target
    else:
        # One store plus a declared recipient is equally a boundary crossing.
        (single,) = draw(store_ids(1))
        recipient_field = draw(st.sampled_from(sorted(CROSS_STORE_RECIPIENT_FIELDS)))
        action["store_id"] = single
        action[recipient_field] = draw(store_ids(1))
    return Witness(
        rule="privacy_boundary",
        action=action,
        confidence=draw(compliant_confidences()),
        evidence=("privacy boundary blocked", field),
    )


@st.composite
def rider_shift_witnesses(draw: st.DrawFn) -> Witness:
    """REJECT: a rider shift longer than the committed maximum."""
    hours = draw(
        st.floats(
            min_value=MAX_SHIFT_HOURS,
            max_value=MAX_SHIFT_HOURS * 10.0,
            exclude_min=True,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    return Witness(
        rule="rider_shift_limit",
        action={"routing_actions": [{"rider_shift_hours": hours}]},
        confidence=draw(compliant_confidences()),
        evidence=("rider shift limit exceeded",),
    )


@st.composite
def service_level_witnesses(draw: st.DrawFn) -> Witness:
    """ESCALATE: a predicted fill rate below the committed minimum."""
    fill_rate = draw(
        st.floats(
            min_value=0.0,
            max_value=MIN_FILL_RATE,
            exclude_max=True,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    return Witness(
        rule="service_level_minimum",
        action={"predicted_fill_rate": fill_rate},
        confidence=draw(compliant_confidences()),
        evidence=("predicted fill rate", "below"),
    )


@st.composite
def confidence_floor_witnesses(draw: st.DrawFn) -> Witness:
    """ESCALATE: confidence below the boundary in force (I-5)."""
    confidence = draw(
        st.floats(
            min_value=0.0,
            max_value=THRESHOLD,
            exclude_max=True,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    return Witness(
        rule="confidence_floor",
        action={"action_type": "reorder"},
        confidence=confidence,
        evidence=("confidence", "below threshold"),
    )


#: One witness strategy per declared blocking rule. Coverage is asserted total by
#: ``test_the_committed_table_is_total_and_every_declaration_is_observable``, so a new
#: BLOCK/REJECT/ESCALATE entry with no observable enforcement fails this module.
BLOCKING_WITNESSES: Final[Mapping[str, st.SearchStrategy[Witness]]] = {
    "privacy_boundary": privacy_witnesses(),
    "rider_shift_limit": rider_shift_witnesses(),
    "service_level_minimum": service_level_witnesses(),
    "confidence_floor": confidence_floor_witnesses(),
}


def blocking_witnesses() -> st.SearchStrategy[Witness]:
    return st.one_of(*[BLOCKING_WITNESSES[name] for name in sorted(BLOCKING_WITNESSES)])


def clip_worded(violation: str) -> bool:
    """True when a violation reads as a clip - the wording ``passed`` is derived from."""
    return "clip" in violation.lower()


def attributable(violations: list[str], witness: Witness) -> list[str]:
    return [v for v in violations if all(token in v.lower() for token in witness.evidence)]


# -------------------------------------------------------------------------- properties


# Feature: purpose-achievement-audit, Property 23: Guardrail configuration is total
@given(config=guardrail_configurations())
def test_construction_succeeds_iff_every_declared_rule_resolves_to_a_check(
    config: dict[str, dict[str, Any]],
) -> None:
    """R5.3: the biconditional, plus the naming obligation on the failing side."""
    available = GuardrailEngine.available_check_functions()

    strict_missing = expected_missing(config, available)
    blocking_missing = expected_missing(config, available, blocking_only=True)

    # The pure seam agrees with the independent recompute, in both readings.
    assert unimplemented_guardrails(config, available) == strict_missing
    assert (
        unimplemented_guardrails(
            config,
            available,
            enforcements_requiring_check=BLOCKING_ENFORCEMENTS,
        )
        == blocking_missing
    )

    # The engine enforces every declared rule, which strictly implies the
    # BLOCK/REJECT/ESCALATE reading R5.3 states. Never the other way round.
    assert set(blocking_missing) <= set(strict_missing)

    if not strict_missing:
        assert blocking_missing == ()
        engine = GuardrailEngine(confidence_threshold=THRESHOLD, guardrails=config)
        # A constructed engine is a usable engine: no partially validated object.
        assert engine.confidence_threshold == THRESHOLD
        passed, violations = engine.validate_decision(decision({}, 1.0))
        assert passed is True
        assert violations == []
        return

    with pytest.raises(GuardrailConfigurationError) as excinfo:
        GuardrailEngine(confidence_threshold=THRESHOLD, guardrails=config)

    error = excinfo.value
    message = str(error)

    # The error carries the offending entries, sorted, with their declarations.
    assert error.unimplemented == strict_missing
    assert f"{len(strict_missing)} declared" in message
    for rule_name, enforcement in strict_missing:
        assert rule_name in message
        assert f"expected {expected_check_name(rule_name)}()" in message
        assert f"enforcement={enforcement or 'UNDECLARED'}" in message
        # The resolution rule the message advertises is the one the module applies.
        assert check_method_name(rule_name) == expected_check_name(rule_name)

    # Every rule refused for a non-blocking declaration is extra strictness, and is
    # explained by the strict reading - it is never an arbitrary refusal.
    for rule_name, enforcement in strict_missing:
        if enforcement not in EXPECTED_BLOCKING:
            assert (rule_name, enforcement) not in blocking_missing


# Feature: purpose-achievement-audit, Property 23: Guardrail configuration is total
@given(
    rule_name=rule_names(),
    enforcement=st.sampled_from(sorted(EXPECTED_BLOCKING)),
    noise=st.sampled_from(["", " ", "  "]),
    lowered=st.booleans(),
)
def test_an_unimplemented_blocking_declaration_always_fails_construction(
    rule_name: str,
    enforcement: str,
    noise: str,
    lowered: bool,
) -> None:
    """R5.3: the declaration is recognised through case and whitespace noise.

    A reader that compared the raw string would treat ``" block "`` as unknown and
    skip the requirement - the exact shape of downgrade this requirement forbids.
    """
    available = GuardrailEngine.available_check_functions()
    declared = f"{noise}{enforcement.lower() if lowered else enforcement}{noise}"
    config: dict[str, dict[str, Any]] = {
        name: dict(spec) for name, spec in HARD_GUARDRAILS.items()
    }
    config[rule_name] = {"rule": "generated declaration", "enforcement": declared}

    if expected_check_name(rule_name) in available:
        # An implemented rule re-declared as blocking stays constructible: the
        # declaration's wording cannot invent a hole where an implementation exists.
        GuardrailEngine(confidence_threshold=THRESHOLD, guardrails=config)
        return

    with pytest.raises(GuardrailConfigurationError) as excinfo:
        GuardrailEngine(confidence_threshold=THRESHOLD, guardrails=config)

    assert (rule_name, enforcement) in excinfo.value.unimplemented
    assert rule_name in str(excinfo.value)
    assert (rule_name, enforcement) in unimplemented_guardrails(
        config,
        available,
        enforcements_requiring_check=BLOCKING_ENFORCEMENTS,
    )


# Feature: purpose-achievement-audit, Property 23: Guardrail configuration is total
@given(witness=blocking_witnesses())
def test_a_declared_blocking_rule_never_degrades_to_a_clip_or_a_no_op(
    witness: Witness,
) -> None:
    """R5.3: a declared veto is observed as a veto, not as a warning or a mutation."""
    engine = GuardrailEngine(confidence_threshold=THRESHOLD)
    before = copy.deepcopy(witness.action)
    target = decision(witness.action, witness.confidence)

    passed, violations = engine.validate_decision(target)

    # Not a no-op: the verdict withholds dispatch and the violation names the rule.
    assert passed is False
    named = attributable(violations, witness)
    assert named, (witness.rule, violations)

    # Not a clip: no attributable violation is clip-worded, so ``all_clipped`` cannot
    # flip the verdict, and at least one violation is non-clip by construction.
    assert not any(clip_worded(violation) for violation in named)
    assert not all(clip_worded(violation) for violation in violations)

    # Not a quiet repair: the action reaches the caller exactly as proposed, so
    # nothing downstream can mistake a blocked action for an adjusted one.
    assert target.selected_action == before
    assert target.execution_confirmations == []

    # The observed enforcement matches the declaration the table makes.
    assert declared_enforcement(HARD_GUARDRAILS[witness.rule]) in EXPECTED_BLOCKING


# Feature: purpose-achievement-audit, Property 23: Guardrail configuration is total
@given(
    witness=blocking_witnesses(),
    category=st.sampled_from(sorted(ESSENTIAL_CATEGORIES)),
    multiplier=st.floats(
        min_value=CAP,
        max_value=CAP * 4.0,
        exclude_min=True,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_a_clip_class_violation_cannot_rescue_a_blocking_violation(
    witness: Witness,
    category: str,
    multiplier: float,
) -> None:
    """R5.3: a clip raised alongside a veto never turns the verdict into a pass.

    ``validate_decision`` returns ``all("clipped" in v)``, so a mixed violation set is
    precisely where a downgrade could hide.
    """
    engine = GuardrailEngine(confidence_threshold=THRESHOLD)
    action = copy.deepcopy(witness.action)
    action["pricing_actions"] = [{"category": category, "multiplier": multiplier}]
    target = decision(action, witness.confidence)

    passed, violations = engine.validate_decision(target)

    assert passed is False
    assert attributable(violations, witness)

    observed = target.selected_action["pricing_actions"][0]["multiplier"]
    if witness.rule == "privacy_boundary":
        # BLOCK is evaluated before any rule that mutates the action (R5.2), so the
        # blocked action is returned untouched rather than partially rewritten and the
        # veto is the only violation reported.
        assert observed == multiplier
        assert len(violations) == 1
    else:
        assert observed == CAP
        assert any(clip_worded(violation) for violation in violations)
        assert not all(clip_worded(violation) for violation in violations)


# Feature: purpose-achievement-audit, Property 23: Guardrail configuration is total
@given(
    category=st.sampled_from(sorted(ESSENTIAL_CATEGORIES)),
    multiplier=st.floats(
        min_value=CAP,
        max_value=CAP * 4.0,
        exclude_min=True,
        allow_nan=False,
        allow_infinity=False,
    ),
    confidence=compliant_confidences(),
)
def test_the_declared_clip_stays_a_clip(
    category: str,
    multiplier: float,
    confidence: float,
) -> None:
    """R5.3 / I-6: the one non-veto declaration is observed as a cap, not a veto.

    Totality runs in both directions. A CLIP silently promoted to a BLOCK would also
    break the declared-to-enforced mapping, and would reject essential pricing the
    invariant explicitly permits once capped.
    """
    engine = GuardrailEngine(confidence_threshold=THRESHOLD)
    target = decision(
        {"pricing_actions": [{"category": category, "multiplier": multiplier}]},
        confidence,
    )

    passed, violations = engine.validate_decision(target)

    assert declared_enforcement(HARD_GUARDRAILS["essential_price_cap"]) == EXPECTED_CLIP
    assert EXPECTED_CLIP not in EXPECTED_BLOCKING
    assert passed is True
    assert violations
    assert all(clip_worded(violation) for violation in violations)
    assert target.selected_action["pricing_actions"][0]["multiplier"] == CAP

    # Re-validating the clipped action adds nothing: the cap is a fixed point, so a
    # second pass through the engine cannot escalate a clip into a violation.
    passed_again, violations_again = engine.validate_decision(target)
    assert passed_again is True
    assert violations_again == []
    assert target.selected_action["pricing_actions"][0]["multiplier"] == CAP


# Feature: purpose-achievement-audit, Property 23: Guardrail configuration is total
@given(
    witness=blocking_witnesses(),
    declared=st.lists(
        st.sampled_from(sorted(HARD_GUARDRAILS)),
        unique=True,
        max_size=len(HARD_GUARDRAILS),
    ),
)
def test_dropping_a_declaration_never_weakens_enforcement(
    witness: Witness,
    declared: list[str],
) -> None:
    """R5.3: no table shape turns an implemented enforcement into a no-op.

    Enforcement lives in ``validate_decision``'s call sequence, not in the table, so
    the table is a declaration surface that can only ever be *stricter* than the
    engine. Recorded rather than assumed: a reader could reasonably expect the map to
    select which checks run, and it does not. Omitting an entry therefore fails closed.
    """
    config = {name: dict(HARD_GUARDRAILS[name]) for name in declared}
    engine = GuardrailEngine(confidence_threshold=THRESHOLD, guardrails=config)

    passed, violations = engine.validate_decision(
        decision(copy.deepcopy(witness.action), witness.confidence),
    )

    assert passed is False
    assert attributable(violations, witness)


def test_the_committed_table_is_total_and_every_declaration_is_observable() -> None:
    """The shipped table is total today, and its vocabulary is pinned.

    The unit companion (``test_guardrail_configuration.py``) already asserts that the
    committed table constructs. What is added here is the vocabulary pin, the
    resolution-rule oracle, the callability of every resolved name, and the witness
    coverage that makes the generative properties above total over the table.
    """
    available = GuardrailEngine.available_check_functions()

    # The blocking vocabulary is the one R5.3 names - not a superset, not a subset.
    assert set(BLOCKING_ENFORCEMENTS) == set(EXPECTED_BLOCKING)

    # Total: every declared rule resolves, by the independently restated rule, to a
    # name that is not merely present in a set but callable on the engine.
    assert expected_missing(HARD_GUARDRAILS, available) == ()
    for rule_name, spec in HARD_GUARDRAILS.items():
        resolved = expected_check_name(rule_name)
        assert check_method_name(rule_name) == resolved
        assert resolved in available
        assert callable(getattr(GuardrailEngine, resolved))
        assert declared_enforcement(spec) in EXPECTED_BLOCKING | {EXPECTED_CLIP}

    for name in available:
        assert callable(getattr(GuardrailEngine, name))

    # Non-vacuous: the table declares at least one veto, so "total" is a claim about
    # enforcement rather than about an all-advisory table.
    blocking_rules = {
        name
        for name, spec in HARD_GUARDRAILS.items()
        if declared_enforcement(spec) in EXPECTED_BLOCKING
    }
    assert blocking_rules

    # The declared-to-observed mapping is total: a witness for every blocking rule,
    # and the clip is the only entry allowed to have none.
    assert set(BLOCKING_WITNESSES) == blocking_rules
    assert set(BLOCKING_WITNESSES) | {"essential_price_cap"} == set(HARD_GUARDRAILS)
