"""Property-based test for behavioural actuation classification (design E2.2 / AD-5).

Feature: purpose-achievement-audit, Property 30: Actuation classification is behavioural
and total

    *For any* discovered agent handler, the classification is derived from whether the
    state read back through ``perceive()`` differs across the invoked ``execute()`` - not
    from source text; an agent whose state is unchanged while it reports ``executed`` is
    classified inert and named; markers appearing only in comments, docstrings, or
    statements unreachable from the invoked path never yield an actuating classification;
    an agent reporting a published event is only credited when its deployed server
    supplies a producer; every discovered agent receives exactly one reported
    classification; and the count reported is the count compared against the baseline.

Why the property is shaped this way. The audit finding behind Requirement 9 is that
"converted" was decided by ``"WorldAction" in src`` - a substring, in a codebase whose own
task list told the implementation which substring to write. So the subject of this test is
never "does the gate find the marker": it is *the marker cannot decide anything*. Three
separate statements carry that:

1. **The classifier is invariant under the marker set** (R9.7). Over the whole observation
   space, replacing ``reachable_markers`` with the empty set, with the world markers, with
   the event markers, or with every marker the gate knows never changes the class. The
   marker survives only in a failure ``detail`` string, where it is evidence for a reader
   and input to nothing.
2. **A marker outside the invoked path is not even collected** (R9.7). Over every marker
   and every unreachable placement - a comment, a docstring, the body of a constant-false
   branch, the ``else`` of a constant-true one, a nested ``def``, a statement after an
   unconditional ``return`` - the pre-filter returns the empty tuple.
3. **The same handler source classifies differently in two different worlds** (R9.1, R9.2,
   slow). An agent observed ``ACTUATING`` against a real ``WorldRuntime`` is re-probed,
   byte-identical, against a world that acknowledges every action and never moves; it is
   then not actuating, and where it still reports ``executed`` it is ``INERT`` and named.
   No source text changed between the two probes, so nothing about source text can be what
   produced the difference.

The pure seam (``classify`` / ``evaluate_actuation``) reads no file, drives no world and
touches no process state, which is why totality (R9.4), the publication-credit rule (R9.6)
and the reported-equals-compared count identity (R9.8) are asserted here without a
simulation - the same seam shape as ``registry_gate.evaluate_results`` and
``doc_truth.evaluate_claims``, and the same reason.

**I-0 routing.** Only the last test drives a real ``WorldRuntime``. It carries
``@pytest.mark.slow``, so ``-m "not slow"`` genuinely excludes it, and it runs in
``ci.yml::uplift-verify`` at ``HYPOTHESIS_PROFILE=heavy`` on a Linux runner - never on the
development laptop (``.kiro/steering/local-compute-budget.md``). ``digital_twin.world`` is
imported *inside* that test so this module still collects on a box without ``simpy``, and
the runtime is manual-tick (``run_clock=False``) and stopped in a ``finally``, so no clock
thread outlives an example. There is no ``importorskip`` guard: in the job that owns this
run the dependency is installed, and a silent SKIP would report absence of proof as proof
(I-7).

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 9.1, 9.2, 9.4, 9.6, 9.7, 9.8**
"""

from __future__ import annotations

import ast
import json
from typing import TYPE_CHECKING, Any, Final

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scripts.audit.agency_truth import (
    ACTUATING_BASELINE,
    ACTUATION_MARKERS,
    AGENT_LEVERS,
    EVENT_MARKERS,
    ROOT,
    WORLD_MARKERS,
    ActuationClass,
    ActuationVerdict,
    AgentProbeObservation,
    Check,
    LeverSpec,
    classify,
    discover_handlers,
    evaluate_actuation,
    observe_agent,
    probe_observations,
    reachable_markers,
    static_observations,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synapse_common.world.models import WorldAction, WorldState

#: The city the probe fixtures are written for (``agency_truth._PROBE_CITY``); the same
#: city ``orchestrator/tests/test_real_actuation_e2e.py`` drives.
PROBE_CITY: Final[str] = "bengaluru"

#: Agents the gate declares a lever for, plus names it has never seen. The undeclared
#: names matter: R9.4 is the requirement that a handler found on disk with no declared
#: lever is classified anyway rather than omitted from every list.
AGENT_NAMES: Final[tuple[str, ...]] = (*AGENT_LEVERS, "newly_added_agent", "vendor_agent")

#: One executable statement per marker the gate matches, used to build synthetic handler
#: sources for the reachability property. Each is written the way the *pre-filter* matches
#: - a bare name call or an attribute chain - not the way a reader would paraphrase it.
MARKER_STATEMENTS: Final[dict[str, str]] = {
    "WorldAction": 'action = WorldAction(city="bengaluru")',
    "self._actuator": "outcome = self._actuator.apply(action)",
    "actuate_items": "outcome = actuate_items(agent_name=self.name, items=items)",
    "self._kafka.produce": 'self._kafka.produce("topic", b"payload")',
    "honest_produce": "published = honest_produce(self._kafka, params)",
}

#: Placements R9.7 names: a marker written here is not evidence that ``execute()`` can
#: reach an actuator, so the pre-filter must not collect it.
UNREACHABLE_PLACEMENTS: Final[tuple[str, ...]] = (
    "comment",
    "docstring",
    "static_false_branch",
    "static_true_else",
    "nested_function",
    "after_return",
)


# ---------------------------------------------------------------------------
# The classification, recomputed independently of the gate
# ---------------------------------------------------------------------------
def expected_class(observation: AgentProbeObservation) -> ActuationClass:
    """The class the declared ordering mandates, written out here rather than imported.

    Design E2.2's rules, first match wins - deliberately restated so the test compares two
    implementations instead of one:

    1. the handler did not parse                  -> ``UNCLASSIFIED``
    2. no lever is declared for the agent         -> ``UNCLASSIFIED`` (R9.4)
    3. the probe did not run, or could not finish -> ``UNCLASSIFIED``
    4. the clock advanced across the two reads    -> ``UNCLASSIFIED`` (unattributable)
    5. ``perceive()`` differed across the call    -> ``ACTUATING`` (R9.1)
    6. the declared lever is not perceivable      -> ``UNCLASSIFIED`` (disclosed bound)
    7. a real publish with a wired producer       -> ``EVENT_ONLY`` (R9.6)
    8. otherwise                                  -> ``INERT`` (R9.2)

    ``reachable_markers`` appears nowhere in this function. That absence is the property:
    the marker set is not an input to the classification, only to its explanation.
    """
    lever = observation.lever
    if not observation.parsed:
        return ActuationClass.UNCLASSIFIED
    if lever is None:
        return ActuationClass.UNCLASSIFIED
    if not observation.probed or observation.probe_error:
        return ActuationClass.UNCLASSIFIED
    if observation.clock_intervened:
        return ActuationClass.UNCLASSIFIED
    if observation.world_delta:
        return ActuationClass.ACTUATING
    if lever.kind is not None and not lever.perceivable:
        return ActuationClass.UNCLASSIFIED
    if observation.reported_kafka_published is True and observation.producer_wired:
        return ActuationClass.EVENT_ONLY
    return ActuationClass.INERT


def named_check(verdict: ActuationVerdict, name: str) -> Check:
    """The single check the verdict reports under ``name`` (absence is itself a defect)."""
    matches = [check for check in verdict.checks if check.name == name]
    assert len(matches) == 1, f"expected exactly one {name!r} check, got {len(matches)}"
    return matches[0]


def digest(observations: Sequence[AgentProbeObservation]) -> str:
    """An ASCII one-line-per-agent summary, so a counterexample names the evidence."""
    return "; ".join(
        f"{observation.agent}: probed={observation.probed} delta={observation.world_delta} "
        f"status={observation.reported_status!r} published={observation.reported_kafka_published} "
        f"wired={observation.producer_wired} class={classify(observation).classification.value} "
        f"error={observation.probe_error!r}"
        for observation in observations
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
def marker_sets() -> st.SearchStrategy[tuple[str, ...]]:
    """A marker subset, ordered the way ``reachable_markers()`` emits one."""
    return st.lists(
        st.sampled_from(ACTUATION_MARKERS),
        unique=True,
        max_size=len(ACTUATION_MARKERS),
    ).map(lambda drawn: tuple(marker for marker in ACTUATION_MARKERS if marker in drawn))


def lever_specs() -> st.SearchStrategy[LeverSpec]:
    """A declared lever: one of the eight committed ones, or a synthetic variant.

    The synthetic variants exist so ``perceivable`` and a ``None`` ``kind`` are both drawn
    independently of the committed table - the disclosed-bound rule (rule 6) must hold for
    a lever this repository has not declared yet, not only for the three it has.
    """
    return st.one_of(
        st.sampled_from(tuple(AGENT_LEVERS.values())),
        st.builds(
            LeverSpec,
            kind=st.none() | st.sampled_from(("reorder", "set_policy", "set_price_mult")),
            lever_key=st.sampled_from(("quantity", "price_mult", "demand_mult", "")),
            perceivable=st.booleans(),
            observed_field=st.sampled_from(("inventory", "demand_rate", "")),
            note=st.just("synthetic lever drawn for the totality quantifier"),
        ),
    )


@st.composite
def actuation_observations(
    draw: st.DrawFn,
    *,
    agent: str | None = None,
) -> AgentProbeObservation:
    """One observation, drawn over the whole field space.

    Deliberately admits combinations the real probe cannot emit - ``probed`` beside a
    ``probe_error``, a marker set on an unparsed handler - because totality is a claim
    about the input space, not about the inputs that happen to arise today. Every field is
    drawn independently, so no clause of the ordering is unreachable by construction.
    """
    name = agent if agent is not None else draw(st.sampled_from(AGENT_NAMES))
    declared = draw(st.booleans())
    return AgentProbeObservation(
        agent=name,
        handler_file=f"agents/{name}/a2a/handler.py",
        parsed=draw(st.booleans()),
        reachable_markers=draw(marker_sets()),
        stub_shape=draw(st.booleans()),
        constant_kafka_published=draw(st.booleans()),
        producer_wired=draw(st.booleans()),
        lever=draw(lever_specs()) if declared else None,
        probed=draw(st.booleans()),
        probe_error=draw(
            st.sampled_from(
                (
                    "",
                    "",
                    "handler could not be constructed: boom",
                    "execute() raised: boom",
                )
            )
        ),
        reported_status=draw(st.sampled_from(("executed", "diverged", "revised", ""))),
        reported_kafka_published=draw(st.none() | st.booleans()),
        world_delta=draw(st.booleans()),
        clock_intervened=draw(st.booleans()),
    )


@st.composite
def observation_sets(
    draw: st.DrawFn,
    *,
    min_size: int = 0,
    max_size: int = 6,
) -> tuple[AgentProbeObservation, ...]:
    """A discovery sweep: one observation per distinct agent name.

    Distinct names because that is the sweep's own contract - one handler file per agent.
    A duplicate is a defect injected deliberately (see the duplicate test) rather than a
    background condition every example carries.
    """
    names = draw(
        st.lists(
            st.sampled_from(AGENT_NAMES),
            min_size=min_size,
            max_size=max_size,
            unique=True,
        )
    )
    return tuple(draw(actuation_observations(agent=name)) for name in names)


# ---------------------------------------------------------------------------
# Synthetic handler sources for the reachability pre-filter (R9.7)
# ---------------------------------------------------------------------------
def handler_source(marker: str, placement: str) -> str:
    """A handler whose ``execute()`` carries ``marker`` at ``placement``.

    Only ``"reachable"`` puts the statement on a path a caller of ``execute()`` executes.
    Every other placement is one R9.7 names by hand.
    """
    statement = MARKER_STATEMENTS[marker]
    honest_return = '        return {"status": "diverged"}'
    body: list[str]
    if placement == "reachable":
        body = [f"        {statement}", '        return {"status": "executed"}']
    elif placement == "comment":
        body = [f"        # {statement}", honest_return]
    elif placement == "docstring":
        body = [f'        """Once used {statement} - no longer."""', honest_return]
    elif placement == "static_false_branch":
        body = ["        if False:", f"            {statement}", honest_return]
    elif placement == "static_true_else":
        body = [
            "        if True:",
            "            pass",
            "        else:",
            f"            {statement}",
            honest_return,
        ]
    elif placement == "nested_function":
        body = ["        def _never_called():", f"            {statement}", honest_return]
    elif placement == "after_return":
        body = [honest_return, f"        {statement}"]
    else:  # pragma: no cover - the placement table is pinned by its own test
        raise AssertionError(f"unknown placement: {placement}")
    return "\n".join(["class GeneratedHandler:", "    def execute(self, params):", *body, ""])


# ---------------------------------------------------------------------------
# The negative control: a world that acknowledges everything and never moves
# ---------------------------------------------------------------------------
class UnmovedWorld:
    """A ``WorldRuntime`` stand-in that accepts every action and changes nothing.

    It mirrors ``WorldRuntime.apply_action``'s envelope faithfully, including a non-empty
    ``effect``, so ``synapse_common.world.actuation.effect_applied`` is satisfied and the
    handler reports ``"executed"`` under the uniform honest status rule. What it does not
    do is move: ``perceive()`` returns the same state every time.

    That combination is the whole point. It is not a fabricated result - nothing here
    claims a world changed - it is the control that separates "the agent says it acted"
    from "the world moved". A classifier reading source text or the agent's own report
    cannot tell this world from the real one; a classifier reading the delta must.
    """

    def __init__(self, state: WorldState) -> None:
        self._state = state
        self.applied: list[WorldAction] = []

    def perceive(self) -> WorldState:
        return self._state.model_copy(deep=True)

    def apply_action(self, action: WorldAction) -> dict[str, Any]:
        self.applied.append(action)
        effect: dict[str, Any] = {"acknowledged": True, **dict(action.params)}
        return {
            "status": "applied",
            "kind": action.kind.value,
            "city": self._state.city,
            "decision_id": action.decision_id,
            "effect": effect,
        }


# ---------------------------------------------------------------------------
# The marker table cannot drift from the gate's marker list
# ---------------------------------------------------------------------------
def test_the_marker_statement_table_covers_every_marker_the_gate_matches() -> None:
    """A marker added to the gate without a statement here would go untested silently."""
    assert set(MARKER_STATEMENTS) == set(ACTUATION_MARKERS)
    assert set(WORLD_MARKERS) | set(EVENT_MARKERS) == set(ACTUATION_MARKERS)
    assert not set(WORLD_MARKERS) & set(EVENT_MARKERS)


# Feature: purpose-achievement-audit, Property 30: Actuation classification is behavioural and total
@given(observation=actuation_observations())
def test_classification_is_total_and_derived_from_the_observed_delta(
    observation: AgentProbeObservation,
) -> None:
    """R9.1, R9.2, R9.4: one class per observation, and only a delta earns ACTUATING."""
    report = classify(observation)

    # Total: exactly one of the four classes, for every observation in the space.
    assert report.classification in set(ActuationClass)
    assert report.classification is expected_class(observation)

    # A function: the pure seam reads no file and holds no state, so this must hold.
    assert classify(observation) == report

    # R9.1: the class ACTUATING is reachable only through an observed world delta, on a
    # probe that finished, with a clock that did not move under it.
    if report.classification is ActuationClass.ACTUATING:
        assert observation.world_delta
        assert observation.probed
        assert not observation.probe_error
        assert not observation.clock_intervened
        assert observation.parsed
        assert observation.lever is not None

    # R9.6: EVENT_ONLY requires a publication the deployed server can actually perform.
    if report.classification is ActuationClass.EVENT_ONLY:
        assert observation.reported_kafka_published is True
        assert observation.producer_wired
        assert not observation.world_delta

    # R9.2: an agent that reports work while the world stood still is INERT, and the
    # report carries the evidence a reader needs rather than a bare verdict.
    if report.classification is ActuationClass.INERT:
        assert not observation.world_delta
        assert observation.probed
    assert report.detail

    # The report echoes the observation it rests on; the agent's own status is recorded as
    # evidence *about the agent* and never substituted for the world reading.
    assert report.agent == observation.agent
    assert report.world_delta is observation.world_delta
    assert report.reported_status == observation.reported_status
    assert report.producer_wired is observation.producer_wired
    assert report.reachable_markers == observation.reachable_markers


@given(observation=actuation_observations())
def test_the_marker_set_never_decides_a_classification(
    observation: AgentProbeObservation,
) -> None:
    """R9.7: the classification is invariant under every marker set the gate can find.

    This is the audit's charge stated as an equation. If any marker set could move the
    class, "converted" would again be decidable by writing a string.
    """
    baseline = classify(observation).classification

    for markers in ((), WORLD_MARKERS, EVENT_MARKERS, ACTUATION_MARKERS):
        variant = observation.model_copy(update={"reachable_markers": markers})
        assert classify(variant).classification is baseline
        assert classify(variant).reachable_markers == markers

    # And the specific direction that matters: every marker present, no delta observed,
    # is never credited as actuating.
    unmoved = observation.model_copy(
        update={"world_delta": False, "reachable_markers": ACTUATION_MARKERS}
    )
    assert classify(unmoved).classification is not ActuationClass.ACTUATING


@given(
    marker=st.sampled_from(ACTUATION_MARKERS),
    placement=st.sampled_from(UNREACHABLE_PLACEMENTS),
)
def test_a_marker_outside_the_invoked_path_is_not_even_collected(
    marker: str,
    placement: str,
) -> None:
    """R9.7: a comment, a docstring, a dead branch or a nested def is not evidence."""
    tree = ast.parse(handler_source(marker, placement))
    assert reachable_markers(tree) == (), f"{marker} collected from a {placement}"

    # The same statement on the invoked path *is* collected - so the empty result above
    # is the placement being excluded, not the statement being unmatchable.
    reachable_tree = ast.parse(handler_source(marker, "reachable"))
    assert marker in reachable_markers(reachable_tree)


@given(observation=actuation_observations())
def test_a_publication_claim_is_credited_only_with_a_deployed_producer(
    observation: AgentProbeObservation,
) -> None:
    """R9.6: an unbacked ``kafka_published`` is never a credit and always a failure."""
    unbacked = observation.model_copy(
        update={
            "parsed": True,
            "probed": True,
            "probe_error": "",
            "clock_intervened": False,
            "world_delta": False,
            "producer_wired": False,
            "reported_kafka_published": True,
            "lever": observation.lever or AGENT_LEVERS["supplier_trust"],
        }
    )
    assert classify(unbacked).classification is not ActuationClass.EVENT_ONLY

    verdict = evaluate_actuation([unbacked], baseline=None)
    wiring = named_check(verdict, "producer_wiring")
    assert not wiring.ok
    assert unbacked.agent in wiring.detail
    assert unbacked.agent in verdict.reason
    assert verdict.verdict == "fail"
    assert not verdict.ok

    # The same claim behind a wired producer is a credit only because the deployment
    # supplies what the claim needs - the metamorphic pair on R9.6's single variable.
    backed = unbacked.model_copy(update={"producer_wired": True})
    assert named_check(evaluate_actuation([backed], baseline=None), "producer_wiring").ok

    # A hardcoded literal ``kafka_published: True`` is unbacked on the same terms, even
    # when the probe reported nothing at all.
    hardcoded = observation.model_copy(
        update={
            "producer_wired": False,
            "constant_kafka_published": True,
            "reported_kafka_published": None,
        }
    )
    hardcoded_check = named_check(evaluate_actuation([hardcoded], baseline=None), "producer_wiring")
    assert not hardcoded_check.ok
    assert hardcoded.agent in hardcoded_check.detail


@given(observations=observation_sets())
def test_every_discovered_agent_gets_exactly_one_reported_classification(
    observations: tuple[AgentProbeObservation, ...],
) -> None:
    """R9.4: the four classes partition the sweep, so no agent lands in neither list."""
    verdict = evaluate_actuation(observations, baseline=None)

    assert len(verdict.reports) == len(observations)
    assert tuple(report.agent for report in verdict.reports) == tuple(
        observation.agent for observation in observations
    )

    buckets = (verdict.actuating, verdict.event_only, verdict.inert, verdict.unclassified)
    assert sum(len(bucket) for bucket in buckets) == len(observations)
    for observation in observations:
        appearances = [bucket for bucket in buckets if observation.agent in bucket]
        assert len(appearances) == 1, f"{observation.agent} is in {len(appearances)} lists"
    assert named_check(verdict, "classification_total").ok

    # An unparsed handler is UNCLASSIFIED *and* a failure that names the file, so an
    # unreadable handler can neither vanish from the sweep nor pass it.
    unparsed = tuple(o.handler_file for o in observations if not o.parsed)
    parseable = named_check(verdict, "handlers_parseable")
    assert parseable.ok is (not unparsed)
    for handler_file in unparsed:
        assert handler_file in parseable.detail

    # A discovered agent with no declared lever is named rather than skipped (R9.4).
    undeclared = tuple(o.agent for o in observations if o.parsed and o.lever is None)
    declared_check = named_check(verdict, "agents_declared")
    assert declared_check.ok is (not undeclared)
    for agent in undeclared:
        assert agent in declared_check.detail

    # I-7: an absence of proof is never a pass. Anything unclassified, and an empty
    # sweep, are both non-passing outcomes with their own reason.
    assert verdict.verdict in {"ok", "fail", "unavailable"}
    assert verdict.ok is (verdict.verdict == "ok")
    if verdict.unclassified or not observations:
        assert not verdict.ok
    assert verdict.reason


@given(observations=observation_sets(), baseline=st.integers(min_value=0, max_value=12))
def test_the_reported_count_is_the_count_compared_against_the_baseline(
    observations: tuple[AgentProbeObservation, ...],
    baseline: int,
) -> None:
    """R9.8: one number is reported and enforced, and the identity is itself checked."""
    verdict = evaluate_actuation(observations, baseline=baseline)

    actuating = tuple(
        report.agent
        for report in verdict.reports
        if report.classification is ActuationClass.ACTUATING
    )
    assert verdict.actuating == actuating
    assert verdict.actuating_count == verdict.compared_count == len(actuating)
    assert named_check(verdict, "count_integrity").ok

    # The number the baseline clause compares is that same number, named in the detail.
    baseline_check = named_check(verdict, "actuating_baseline")
    assert baseline_check.ok is (verdict.compared_count >= baseline)
    assert f"{verdict.compared_count} agent(s) observed actuating" in baseline_check.detail
    assert str(baseline) in baseline_check.detail
    if verdict.compared_count < baseline:
        assert verdict.verdict == "fail"
        assert not verdict.ok
        assert baseline_check.detail in verdict.reason

    # I-7 / CF-3: an unmeasured baseline cannot produce a pass. No number is invented to
    # stand in for the measurement, and the gate says so rather than reporting ok.
    unmeasured = evaluate_actuation(observations, baseline=None)
    assert unmeasured.baseline is None
    assert unmeasured.verdict != "ok"
    assert not unmeasured.ok
    assert named_check(unmeasured, "actuating_baseline").ok


@given(observation=actuation_observations())
def test_an_agent_reporting_executed_with_an_unmoved_world_is_inert_and_named(
    observation: AgentProbeObservation,
) -> None:
    """R9.2: the agent's own report is evidence about the agent, never about the world."""
    lever = observation.lever or AGENT_LEVERS["inventory_sentinel"]
    if lever.kind is not None and not lever.perceivable:
        # Rule 6 would (correctly) withhold a verdict for a lever the perception surface
        # does not expose, so this clause is stated over a lever it does expose.
        lever = AGENT_LEVERS["inventory_sentinel"]
    lying = observation.model_copy(
        update={
            "parsed": True,
            "lever": lever,
            "probed": True,
            "probe_error": "",
            "clock_intervened": False,
            "world_delta": False,
            "reported_status": "executed",
            "reported_kafka_published": None,
            "constant_kafka_published": False,
        }
    )

    report = classify(lying)
    assert report.classification is ActuationClass.INERT
    assert "executed" in report.detail

    verdict = evaluate_actuation([lying], baseline=None)
    check = named_check(verdict, "inert_reports_executed")
    assert not check.ok
    assert lying.agent in check.detail
    assert lying.agent in verdict.reason
    assert verdict.verdict == "fail"

    # The same observation with a delta is ACTUATING and trips nothing: the single
    # variable that moved the verdict is the world reading (R9.1).
    moved = lying.model_copy(update={"world_delta": True})
    assert classify(moved).classification is ActuationClass.ACTUATING
    assert named_check(evaluate_actuation([moved], baseline=None), "inert_reports_executed").ok


@given(observation=actuation_observations())
def test_a_duplicated_agent_report_fails_the_totality_check(
    observation: AgentProbeObservation,
) -> None:
    """R9.4, R9.8: two reports for one agent is a broken partition, not a bigger count."""
    verdict = evaluate_actuation([observation, observation], baseline=None)

    assert not named_check(verdict, "classification_total").ok
    assert verdict.verdict == "fail"
    assert not verdict.ok
    # The count identity still holds - the defect is the partition, and the gate names
    # that rather than silently double-counting an agent towards its baseline.
    assert verdict.actuating_count == verdict.compared_count


def test_an_empty_sweep_is_unavailable_rather_than_a_pass() -> None:
    """I-7: discovering no handler proves nothing about actuation."""
    verdict = evaluate_actuation([], baseline=None)

    assert verdict.verdict == "unavailable"
    assert not verdict.ok
    assert verdict.reports == ()
    assert verdict.actuating_count == verdict.compared_count == 0


def test_the_actuating_baseline_is_unmeasured_in_both_code_and_committed_config() -> None:
    """R9.3 / I-7: no number stands in for a measurement no run has produced.

    The baseline this property enforces is an *input*, never a literal in this test. Today
    it is ``None`` in the gate, and ``infrastructure/quality/ratchets.json`` deliberately
    records no ratchet for the observed-actuating count - its stub-ceiling entry states
    why: "Ratcheting an inferred count would pin the inference, not the behaviour." The
    first ``ci.yml::uplift-verify`` probe seeds it. If the two ever disagree, one of them
    is claiming a measurement that does not exist.
    """
    ratchets = json.loads(
        (ROOT / "infrastructure" / "quality" / "ratchets.json").read_text(encoding="utf-8")
    )["ratchets"]

    # Matched on substance rather than on one exact key, so a future entry named
    # ``actuating-agents-baseline`` or kinded ``actuation-baseline`` is still seen. The
    # stub ceiling is excluded: it ratchets the count of status-dict stubs, not the count
    # of agents observed actuating.
    baselines = {
        name: entry
        for name, entry in ratchets.items()
        if "actuat" in f"{name} {entry.get('kind', '')}".lower()
        and entry.get("kind") != "actuation-ceiling"
    }
    measured = {
        name: entry for name, entry in baselines.items() if entry.get("status") == "measured"
    }

    assert (ACTUATING_BASELINE is None) is (not measured), (
        f"agency_truth.ACTUATING_BASELINE={ACTUATING_BASELINE} disagrees with the committed "
        f"record {sorted(measured)}"
    )


# ---------------------------------------------------------------------------
# The behavioural half: a real world, and a world that does not move (R9.1, R9.2)
# ---------------------------------------------------------------------------
# ``max_examples`` is deliberately NOT hardcoded: every example boots a real SimPy world
# and invokes every discovered agent's real ``execute()`` against it, so the count is
# inherited from the active Hypothesis profile (see the root ``conftest.py``) - ``heavy`` =
# 100 in ``ci.yml::uplift-verify``, which is the minimum the spec obligation requires.
# ``dev`` = 10 exists for the profile's sake only: I-0 forbids running this file's slow
# marker on the development laptop at any budget.
@pytest.mark.slow
@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(min_value=1, max_value=2**16),
    warmup=st.integers(min_value=1, max_value=4),
)
def test_actuation_classification_is_behavioural_against_a_real_world(
    seed: int,
    warmup: int,
) -> None:
    """R9.1, R9.2, R9.4, R9.6, R9.8: the verdict comes from the world, not the source.

    ``perceive()`` -> real ``execute()`` -> ``perceive()`` against a standing
    ``WorldRuntime``, then the identical handlers against a world that acknowledges every
    action and never moves. Nothing about the tree differs between the two sweeps, so any
    difference in classification is attributable to the world alone - which is exactly the
    claim a substring gate could not make.
    """
    from digital_twin.world import WorldRuntime  # noqa: PLC0415 -- CI-only heavy import (I-0)

    runtime = WorldRuntime(city=PROBE_CITY, seed=seed).start(run_clock=False)
    try:
        # Manual tick: the probe must be the only thing that changes the world between
        # its two reads. Warm up so inventory and demand are non-zero and a lever has
        # something to move.
        for _ in range(warmup):
            runtime.tick()

        observed = probe_observations(runtime)
        verdict = evaluate_actuation(observed, baseline=None)

        # The sweep is total over what is on disk, and the probe reached the handlers it
        # discovered - a sweep that classified nothing would prove nothing (I-7).
        assert len(observed) == len(discover_handlers())
        assert named_check(verdict, "handlers_parseable").ok, verdict.reason
        assert named_check(verdict, "agents_declared").ok, verdict.reason
        assert any(o.probed and not o.probe_error for o in observed), digest(observed)

        # R9.1: every classification equals the independent recompute from the observed
        # fields, and ACTUATING is held only where the world actually moved.
        for observation in observed:
            assert classify(observation).classification is expected_class(observation)
        for report in verdict.reports:
            if report.classification is ActuationClass.ACTUATING:
                assert report.world_delta

        # R9.8: the reported count is the compared count, on a real sweep too.
        assert verdict.actuating_count == verdict.compared_count == len(verdict.actuating)
        assert named_check(verdict, "count_integrity").ok

        # R9.6: the publication check reflects what the deployed servers wire, recomputed
        # here rather than read from the gate's own tally.
        unbacked = tuple(
            o.agent
            for o in observed
            if not o.producer_wired
            and (o.reported_kafka_published is True or o.constant_kafka_published)
        )
        wiring = named_check(verdict, "producer_wiring")
        assert wiring.ok is (not unbacked), digest(observed)
        for agent in unbacked:
            assert agent in verdict.reason

        # I-7: an unmeasured baseline plus any unclassified agent is never a pass.
        assert verdict.verdict != "ok"
        if verdict.unclassified:
            assert not verdict.ok

        # Non-vacuity: at least one agent genuinely moved the world. Without this the
        # behavioural claim would be satisfied by a probe that observed nothing, which is
        # the shape I-7 refuses - absence of proof is not proof.
        actuating = {
            report.agent
            for report in verdict.reports
            if report.classification is ActuationClass.ACTUATING
        }
        assert actuating, (
            f"no agent was observed moving the world, so nothing behavioural was proven: "
            f"{digest(observed)}"
        )

        unmoved = UnmovedWorld(runtime.perceive())
        negative = tuple(
            observe_agent(static, unmoved)
            for static in static_observations()
            if static.agent in actuating
        )
    finally:
        runtime.stop()

    # The negative control ran the same handlers against a world that acknowledged every
    # action - so the actuation path executed - and still did not move.
    assert unmoved.applied, "the unmoved world received no action from any actuating agent"
    assert negative
    negative_verdict = evaluate_actuation(negative, baseline=None)
    lying = named_check(negative_verdict, "inert_reports_executed")

    # The core metamorphic claim: the byte-identical handler that was credited against a
    # world that moved is not credited against a world that did not, and every class is
    # still the independent recompute of the observation.
    for observation in negative:
        assert not observation.world_delta, digest(negative)
        report = classify(observation)
        assert report.classification is expected_class(observation)
        assert report.classification is not ActuationClass.ACTUATING, digest(negative)

    # R9.2's clause, stated over the agents an immediate delta can decide. Two exclusions,
    # both the classifier being right rather than the test being lenient: rule 6 withholds
    # a verdict for a lever ``WorldState`` does not expose, and rule 7 credits a real
    # publish through a wired producer as EVENT_ONLY - it did publish, the world simply
    # did not move.
    lying_agents = tuple(
        observation
        for observation in negative
        if observation.reported_status == "executed"
        and observation.lever is not None
        and (observation.lever.kind is None or observation.lever.perceivable)
        and not (observation.reported_kafka_published is True and observation.producer_wired)
    )
    for observation in lying_agents:
        assert classify(observation).classification is ActuationClass.INERT
        assert observation.agent in lying.detail
        assert observation.agent in negative_verdict.reason

    assert lying_agents, (
        f"no agent reported 'executed' through a perceivable lever against the unmoved "
        f"world, so R9.2's clause was not exercised: {digest(negative)}"
    )
    assert not lying.ok
    assert negative_verdict.verdict == "fail"
