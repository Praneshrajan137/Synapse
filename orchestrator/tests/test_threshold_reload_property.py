"""Property-based test for the reloadable I-5 escalation boundary (task 8.2, design E3).

Feature: purpose-achievement-audit, Property 24: Escalation tracks the configured threshold

    *For any* sequence of configured confidence thresholds, after each reload the
    escalation boundary equals the newly configured value on every tier, no process
    restart or source-file change is required, and raising the threshold never decreases
    the escalation count over a fixed request corpus.

Why the property is shaped this way
-----------------------------------

The finding behind Requirement 5.4 is that the boundary was a float captured once at
construction (``rules.py:57``, injected once at ``orchestrator/inference/serve.py:98``),
so moving it needed a process restart. Task 8.1 replaced the float with
``ConfidenceThresholdProvider`` and made ``GuardrailEngine`` read ``current()`` on every
validation. An example test can show that *one* reload is observed; it cannot exclude the
two failure modes that matter, both of which are invisible at a single value:

1. **A stale capture that happens to agree.** A cached float agrees with the configured
   value until the two diverge, and diverges in only one direction per confidence. The
   property therefore drives a *sequence* of configured values against a fixed
   confidence and asserts, at every step, that the observed verdict is the one the
   currently configured boundary implies and is **not** the one any earlier value in the
   sequence implies. A cache that refreshed lazily - on the second validation after a
   reload, say - is excluded separately by driving exactly one validation immediately
   after each reload, so "observable on the very next validation" is asserted rather than
   assumed.

2. **An off-by-one boundary.** ``_check_confidence_floor`` compares ``<``, so the
   threshold itself must pass and the largest representable value below it must escalate.
   The property pins both sides with ``math.nextafter`` instead of an epsilon, so the
   boundary is exact rather than approximately right, and asserts the pair falls on
   opposite sides at every configured value and on every tier.

Two supporting obligations are asserted alongside, because a reload that achieved the
right verdict by the wrong means would still be a defect:

* **No settings instance is written to.** ``reload()`` must build a *new*
  ``OrchestratorConfig`` and rebind it, never mutate the instance it held - a caller
  holding a reference must observe no change. Canonical bytes
  (``json.dumps(..., sort_keys=True, separators=(',', ':'))``) of *every* instance the
  provider ever bound are snapshotted and re-compared after the whole sequence. Note
  honestly that ``OrchestratorConfig`` is a ``BaseSettings`` and is not itself frozen, so
  byte-stability is asserted rather than delegated to Pydantic; ``ConsensusDecision``
  *is* frozen (``SynapseBaseModel``) and is asserted unchanged across validation,
  including its mutable ``selected_action`` payload.
* **No source-file change is required.** The source-declared default in
  ``HARD_GUARDRAILS['confidence_floor']['default_threshold']`` is read once and asserted
  unchanged, while the effective boundary moves away from it and back. The declaration
  stays put; the boundary is elsewhere. **I-13 is unaffected**: the boundary is read only
  by the deterministic rule engine and never interpolated into a system prompt, so
  nothing here perturbs the KV-cache stable prefix.

Every threshold in this file comes from configuration - ``OrchestratorConfig`` instances
built by the strategies, read back through ``provider.current()`` - and the source
default is read from the committed table. No threshold literal appears in the assertions,
so relaxing the shipped default cannot leave this property passing for the wrong reason.

Scope, and the cross-cutting conflict this property routes around
-----------------------------------------------------------------

The subject is the threshold provider plus ``GuardrailEngine.validate_decision``. The
real ``ConsensusProtocol`` is never constructed, no dispatch is attempted, and the SimPy
twin is never driven: the tier-universal statement about dispatch is Property 22 (task
8.6), which is ``@pytest.mark.slow`` and runs in ``ci.yml::uplift-verify``. "On every
tier" is asserted here in the sense the guardrail engine can carry it - the verdict is
identical for all four ``DecisionTier`` values, so the boundary is not a property of a
route. Nothing here needs Postgres, a browser, or a subprocess, so this test is not slow.

``guardrails.rules.execute_consensus`` is deliberately never called. Its ``@deal.pre``
contract used to hardcode ``0.7`` while task 8.1 had made the boundary reloadable, so a
reload *below* ``0.7`` let a decision in ``[threshold, 0.7)`` pass ``validate_decision``
and then trip ``PreContractError`` inside the choke point - fail-closed, but raised after
the audit append. Task 12.1a repaired that: the precondition takes the boundary in force
as a parameter and the same predicate runs as a pre-flight before the append. This
property was already drawing thresholds from the whole closed unit interval, so its
generated range needed no change and none was made; what it asserts in the sub-``0.7``
region is what it always asserted, that the *engine* tracks the configured boundary,
which is R5.4's obligation. The statement about the choke point in that region is
Property 22's (task 8.6), and after the repair that property generates over the same full
interval.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 5.4**
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any, Final

from hypothesis import given
from hypothesis import strategies as st
from synapse_common.models import ConsensusDecision, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.guardrails.rules import HARD_GUARDRAILS, GuardrailEngine
from orchestrator.guardrails.thresholds import (
    ConfidenceThresholdProvider,
    ConfigConfidenceThresholdProvider,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# --------------------------------------------------------------------------- constants

#: I-5 is stated without qualification, so the verdict must not depend on the route.
TIERS: Final[tuple[DecisionTier, ...]] = tuple(DecisionTier)

#: The guardrail whose boundary R5.4 makes reloadable.
CONFIDENCE_FLOOR_RULE: Final[str] = "confidence_floor"

#: The boundary the source *declares*. Read, never written, and never compared to a
#: literal: the point is that it stays put while the effective boundary moves.
SOURCE_DECLARED_DEFAULT: Final[Any] = HARD_GUARDRAILS[CONFIDENCE_FLOOR_RULE][
    "default_threshold"
]


# ----------------------------------------------------------------------------- oracles


def escalates(confidence: float, threshold: float) -> bool:
    """The I-5 verdict, restated here so the property has an independent oracle.

    ``_check_confidence_floor`` compares ``confidence < threshold``; restating that
    comparison rather than importing it means the property compares two implementations
    instead of asserting the subject agrees with itself.
    """
    return confidence < threshold


def canonical(settings: OrchestratorConfig) -> str:
    """Canonical bytes of a settings instance (repo convention: sorted, compact)."""
    payload: dict[str, Any] = settings.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def decision(confidence: float, tier: DecisionTier) -> ConsensusDecision:
    """A decision whose only reachable guardrail is the confidence floor.

    ``selected_action`` is empty, so the privacy scan finds nothing, there is no pricing
    action to clip, no rider shift to reject and no fill rate to report. Any violation
    observed is therefore attributable to the boundary under test.
    """
    return ConsensusDecision(
        tier=tier,
        proposals=[],
        selected_action={},
        pareto_weights={"demand_accuracy": 1.0},
        confidence=confidence,
        audit_trace=["property-24"],
    )


# -------------------------------------------------------------------------- test doubles


class SettingsSequence:
    """A settings factory that walks a configured sequence, one instance per reload.

    Each configured value gets its own ``OrchestratorConfig``, so the "no instance is
    written to" obligation can be checked against every instance the provider ever bound
    rather than only the most recent one.
    """

    __slots__ = ("_index", "instances")

    def __init__(self, configured: Sequence[float]) -> None:
        self.instances: tuple[OrchestratorConfig, ...] = tuple(
            OrchestratorConfig(confidence_threshold=value) for value in configured
        )
        self._index: int = 0

    def __call__(self) -> OrchestratorConfig:
        """Return the instance for the next reload, clamped at the last configured one."""
        self._index += 1
        return self.instances[min(self._index, len(self.instances) - 1)]


class CountingThresholdProvider:
    """A provider that records how often the boundary was read.

    Wraps a real provider instead of reimplementing one, so the counts are evidence about
    the *engine's* read pattern and not about a stand-in.
    """

    __slots__ = ("_inner", "reads", "reloads")

    def __init__(self, inner: ConfidenceThresholdProvider) -> None:
        self._inner: ConfidenceThresholdProvider = inner
        self.reads: int = 0
        self.reloads: int = 0

    def current(self) -> float:
        self.reads += 1
        return self._inner.current()

    def reload(self) -> None:
        self.reloads += 1
        self._inner.reload()


# -------------------------------------------------------------------------- strategies


def thresholds() -> st.SearchStrategy[float]:
    """Any configurable boundary in the closed unit interval.

    The full range is generated on purpose, including the sub-``0.7`` region: R5.4 puts
    no lower bound on operator policy, and the subject here is the provider and the
    engine, neither of which has ever carried a literal floor.
    """
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


def confidences() -> st.SearchStrategy[float]:
    """Any confidence a ``ConsensusDecision`` admits (the model pins ``0 <= c <= 1``)."""
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@st.composite
def straddled_reloads(draw: st.DrawFn) -> tuple[float, float, float]:
    """``(lower, upper, confidence)`` with ``lower <= confidence < upper``.

    The confidence is strictly inside the half-open interval, so configuring ``lower``
    must pass and configuring ``upper`` must escalate. Every example is therefore a
    verdict *flip*, which is what makes "observable on the very next validation"
    falsifiable rather than vacuously satisfied.
    """
    lower = draw(
        st.floats(
            min_value=0.0,
            max_value=1.0,
            exclude_max=True,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    upper = draw(
        st.floats(
            min_value=lower,
            max_value=1.0,
            exclude_min=True,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    confidence = draw(
        st.floats(
            min_value=lower,
            max_value=upper,
            exclude_max=True,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    return lower, upper, confidence


def engine_over(configured: Sequence[float]) -> tuple[
    GuardrailEngine,
    ConfigConfidenceThresholdProvider,
    SettingsSequence,
]:
    """One engine, constructed once, whose boundary walks *configured* on reload.

    The engine is never reconstructed by any test in this file: that is how "without a
    process restart" is expressed mechanically.
    """
    sequence = SettingsSequence(configured)
    provider = ConfigConfidenceThresholdProvider(
        sequence.instances[0],
        settings_factory=sequence,
    )
    return GuardrailEngine(confidence_threshold=provider), provider, sequence


# -------------------------------------------------------------------------- properties


# Feature: purpose-achievement-audit, Property 24: Escalation tracks the configured threshold
@given(configured=st.lists(thresholds(), min_size=1, max_size=6), confidence=confidences())
def test_the_boundary_is_the_currently_configured_value_on_every_tier(
    configured: list[float],
    confidence: float,
) -> None:
    """R5.4: each reload moves the boundary on every tier, and no earlier value survives."""
    engine, provider, sequence = engine_over(configured)
    snapshots = [canonical(instance) for instance in sequence.instances]

    for index, current in enumerate(configured):
        if index:
            provider.reload()

        # No reconstruction, and the boundary reported is the one configured now.
        assert engine.threshold_provider is provider
        assert engine.confidence_threshold == current

        expected = escalates(confidence, current)
        observed: set[bool] = set()

        for tier in TIERS:
            target = decision(confidence, tier)
            passed, violations = engine.validate_decision(target)
            observed.add(not passed)

            assert (not passed) is expected
            if expected:
                # The message names the boundary in force, not a construction-time one.
                assert any(f"below threshold {current}" in v for v in violations)
            else:
                assert violations == []

            # The frozen decision is not written to, payload included.
            assert target.selected_action == {}
            assert target.confidence == confidence
            assert target.escalated_to_human is False

        # I-5 is not a property of a route: all four tiers agree.
        assert observed == {expected}

        # Whenever a previously configured value would have decided differently, the
        # observed verdict is not that value's verdict. A stale capture fails here.
        for earlier in configured[:index]:
            stale = escalates(confidence, earlier)
            if stale is not expected:
                assert stale not in observed

    # A reload rebinds; it never writes to a settings instance the provider held.
    for instance, snapshot in zip(sequence.instances, snapshots, strict=True):
        assert canonical(instance) == snapshot

    # And no source file had to change for any of the above.
    assert HARD_GUARDRAILS[CONFIDENCE_FLOOR_RULE]["default_threshold"] == SOURCE_DECLARED_DEFAULT


# Feature: purpose-achievement-audit, Property 24: Escalation tracks the configured threshold
@given(
    case=straddled_reloads(),
    raise_first=st.booleans(),
    tier=st.sampled_from(TIERS),
)
def test_a_reload_is_observable_on_the_very_next_validation(
    case: tuple[float, float, float],
    raise_first: bool,
    tier: DecisionTier,
) -> None:
    """R5.4: exactly one validation separates the reload from the changed verdict.

    Both directions are driven. Raising the boundary must start escalating a decision
    that passed; lowering it must stop escalating one that did not - a lazily refreshed
    cache would lag by one validation in either direction.
    """
    lower, upper, confidence = case
    first, second = (lower, upper) if raise_first else (upper, lower)
    engine, provider, _ = engine_over([first, second])

    passed_before, _ = engine.validate_decision(decision(confidence, tier))
    provider.reload()
    passed_after, violations = engine.validate_decision(decision(confidence, tier))

    assert (not passed_before) is escalates(confidence, first)
    assert (not passed_after) is escalates(confidence, second)
    assert passed_before is not passed_after
    assert engine.confidence_threshold == second
    if not passed_after:
        assert any(f"below threshold {second}" in v for v in violations)


# Feature: purpose-achievement-audit, Property 24: Escalation tracks the configured threshold
@given(
    configured=st.lists(thresholds(), min_size=1, max_size=4),
    tier=st.sampled_from(TIERS),
)
def test_the_decision_boundary_is_exactly_the_configured_threshold(
    configured: list[float],
    tier: DecisionTier,
) -> None:
    """R5.4: the threshold passes and the value immediately below it escalates.

    ``math.nextafter`` rather than an epsilon, so the boundary is pinned exactly. Where
    the configured boundary is ``0.0`` there is no admissible confidence below it
    (``ConsensusDecision`` pins ``confidence >= 0``), which is stated rather than
    silently skipped: only the inclusive side is checkable there.
    """
    engine, provider, _ = engine_over(configured)

    for index, current in enumerate(configured):
        if index:
            provider.reload()

        at_boundary, at_violations = engine.validate_decision(decision(current, tier))
        assert at_boundary is True
        assert at_violations == []

        just_below = math.nextafter(current, 0.0)
        if current == 0.0:
            assert just_below == current
            continue

        assert just_below < current
        below_passed, below_violations = engine.validate_decision(decision(just_below, tier))
        assert below_passed is False
        assert any(f"below threshold {current}" in v for v in below_violations)


# Feature: purpose-achievement-audit, Property 24: Escalation tracks the configured threshold
@given(
    corpus=st.lists(confidences(), min_size=1, max_size=8),
    first=thresholds(),
    second=thresholds(),
    tier=st.sampled_from(TIERS),
)
def test_raising_the_threshold_never_decreases_the_escalation_count(
    corpus: list[float],
    first: float,
    second: float,
    tier: DecisionTier,
) -> None:
    """R5.4: over a fixed corpus, a raise is monotone in the escalation count."""
    lower, upper = sorted((first, second))
    engine, provider, _ = engine_over([lower, upper])

    escalated_low = sum(1 for c in corpus if not engine.validate_decision(decision(c, tier))[0])
    provider.reload()
    escalated_high = sum(1 for c in corpus if not engine.validate_decision(decision(c, tier))[0])

    assert escalated_low == sum(1 for c in corpus if escalates(c, lower))
    assert escalated_high == sum(1 for c in corpus if escalates(c, upper))
    assert escalated_high >= escalated_low


# Feature: purpose-achievement-audit, Property 24: Escalation tracks the configured threshold
@given(
    threshold=thresholds(),
    confidence=confidences(),
    validations=st.integers(min_value=1, max_value=5),
)
def test_the_engine_reads_the_boundary_once_per_validation_and_captures_none(
    threshold: float,
    confidence: float,
    validations: int,
) -> None:
    """R5.4: the boundary is read per validation, not captured at construction.

    The anti-capture assertion is ``reads == 0`` after construction: a constructor that
    cached a float would have to read the provider to do it, and a cached float is
    exactly the defect R5.4 names.
    """
    provider = CountingThresholdProvider(
        ConfigConfidenceThresholdProvider(OrchestratorConfig(confidence_threshold=threshold)),
    )
    assert isinstance(provider, ConfidenceThresholdProvider)

    engine = GuardrailEngine(confidence_threshold=provider)
    assert provider.reads == 0

    for _ in range(validations):
        passed = engine.validate_decision(decision(confidence, DecisionTier.TIER_1))[0]
        assert (not passed) is escalates(confidence, threshold)

    assert provider.reads == validations
    assert provider.reloads == 0
