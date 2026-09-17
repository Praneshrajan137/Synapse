"""Teeth for the topic->service agreement gate (audit R4.7, task 10.15, C62).

``scripts/audit/topic_service_truth.py`` (task 10.14) enforces the half of R4.7 that
nothing enforced before: a topic recorded in ``infrastructure/kafka/topics.json`` with
real ``consumers`` must resolve to a service in the deployed compose file, because a
subscribe call site in a module nothing deploys is code, not a consumer.

These are example-class checks, not properties: the subject reads two committed files
and one sibling gate, so the interesting inputs are the real repository plus a small
number of hand-built degradations. Hypothesis would add cost and no coverage.

Four things are proven here, and the last three are the honesty half of R4.7:

1. Every topic recorded with ``consumers`` resolves to a deployed service **today**
   (the gate is green on the real tree), and the set of bindings the gate builds is
   exactly the recorded set.
2. ``consumers_planned`` is **not** enforced, and that is deliberate rather than
   vacuous: ``ml_pipeline`` is planned on ``synapse.demand.drift_alert`` and has no
   deployable service at all, so promoting the field would turn the registry's
   honesty about intent into a red gate.
3. ``topic_consumer_truth.HONEST_ABSENCES`` are exempt from the deployment leg, are
   named with their count in the verdict detail, and are **not** promoted by a
   coincidental name match - ``audit_logger`` resolves to ``orchestrator`` by glob and
   is still reported as unproven.
4. ``unavailable`` is distinct from both ``ok`` and ``fail`` and never passes, at the
   gate and at the C62 registry row (I-7). An empty-but-readable stack FAILs; an
   unreadable one degrades.
"""

from __future__ import annotations

from functools import partial
from typing import Literal

import pytest

from scripts.audit import topic_service_truth as tst
from scripts.audit import verify_claims as vc
from scripts.audit.topic_consumer_truth import CONSUMER_LOCATIONS, HONEST_ABSENCES
from scripts.audit.topic_service_truth import (
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_UNAVAILABLE,
    SourceLeg,
    TopicRegistry,
    TopicServiceProbe,
    candidate_services,
    compose_services,
    evaluate,
    source_leg,
)

_Status = Literal["ok", "fail", "unavailable"]

#: A source leg that already passed, so the deployment-leg tests below are hermetic
#: (no subscribe-site grep) and cannot be reported green by the wrong leg.
_SOURCE_OK = SourceLeg(exit_code=EXIT_PASS, topics_with_missing=())


def _synthetic(status: _Status) -> TopicServiceProbe:
    return TopicServiceProbe(status=status, detail="synthetic")


def _registry() -> TopicRegistry:
    return TopicRegistry.model_validate_json(tst.TOPICS_FILE.read_text(encoding="utf-8"))


def _recorded_pairs() -> set[tuple[str, str]]:
    """(topic, consumer) pairs the registry records as real - the enforced surface."""
    reg = _registry()
    return {(t.name, c) for t in reg.topics for c in t.consumers}


def _planned_pairs() -> set[tuple[str, str]]:
    """(topic, consumer) pairs the registry records as intent - never enforced."""
    reg = _registry()
    return {(t.name, c) for t in reg.topics for c in t.consumers_planned}


@pytest.fixture(scope="module")
def probe() -> TopicServiceProbe:
    """The real verdict, computed once - it runs the sibling gate's grep."""
    return evaluate()


@pytest.fixture(scope="module")
def services() -> tuple[str, ...]:
    found = compose_services()
    assert found is not None, f"{tst.COMPOSE_FILE.name} must be readable to mean anything"
    return found


# ---------------------------------------------------------------------------
# 1. The contract holds on the real tree
# ---------------------------------------------------------------------------
def test_every_recorded_consumer_resolves_to_a_deployed_service(
    probe: TopicServiceProbe, services: tuple[str, ...]
) -> None:
    """R4.7 proper. Each enforced binding names a service that the stack declares."""
    enforced = [b for b in probe.bindings if not b.declared_absence]
    assert enforced, "a gate with nothing to enforce cannot fail; the registry lost its consumers"
    unresolved = [b for b in enforced if b.resolved_service is None]
    assert unresolved == [], f"recorded consumers with no deployed service: {unresolved}"
    for binding in enforced:
        assert binding.resolved_service in services
        assert binding.resolved_service in binding.services_considered
    assert probe.status == "ok"
    assert probe.exit_code == EXIT_PASS
    assert probe.unresolved == ()


def test_the_bindings_are_exactly_the_recorded_consumers_and_nothing_planned(
    probe: TopicServiceProbe,
) -> None:
    """The gate's enforced surface is derived from ``consumers`` alone."""
    built = {(b.topic, b.consumer) for b in probe.bindings}
    assert built == _recorded_pairs()
    assert built.isdisjoint(_planned_pairs() - _recorded_pairs())


def test_the_source_leg_is_carried_not_reinvented() -> None:
    """A second copy of the subscribe-site scan could disagree with the first."""
    leg = source_leg()
    assert leg is not None, "topic_consumer_truth must be executable; unproven is not passed"
    assert leg.exit_code == EXIT_PASS
    assert leg.topics_with_missing == ()


def test_c62_is_registered_so_the_verdict_can_fail_something() -> None:
    """The audit's finding was reachability: the check ran from Makefile:22 and nowhere else."""
    assert [cid for cid, _title, _fn in vc._CHECKS if cid == "C62"] == ["C62"]


# ---------------------------------------------------------------------------
# 2. consumers_planned is not enforced, and that exemption is not vacuous
# ---------------------------------------------------------------------------
def test_planned_consumers_are_recorded_intent_and_are_never_enforced(
    probe: TopicServiceProbe,
) -> None:
    planned_only = _planned_pairs() - _recorded_pairs()
    assert planned_only, "the registry must still distinguish intent from fact"
    assert {(b.topic, b.consumer) for b in probe.bindings}.isdisjoint(planned_only)
    assert "consumers_planned not enforced" in probe.detail


def test_promoting_a_planned_consumer_would_fail_so_the_exemption_protects_honesty(
    services: tuple[str, ...], probe: TopicServiceProbe
) -> None:
    """``ml_pipeline`` is planned, has no deployable service, and the gate is still green.

    That is the point of R4.7's wording: enforcing ``consumers_planned`` would punish
    the registry for being truthful about what it has not built yet.
    """
    assert ("synapse.demand.drift_alert", "ml_pipeline") in _planned_pairs()
    candidates = candidate_services("ml_pipeline", CONSUMER_LOCATIONS["ml_pipeline"])
    assert candidates, "the resolver must at least try"
    assert set(candidates).isdisjoint(services)
    assert probe.status == "ok"


def test_candidate_services_are_derived_from_the_consumer_s_own_source_globs() -> None:
    """No second hand-maintained table: every mirror in this repo has drifted once."""
    assert candidate_services("api_firehose", CONSUMER_LOCATIONS["api_firehose"]) == (
        "api-firehose",
        "api",
    )
    assert candidate_services("demand_prophet", ["agents/demand_prophet/**/*.py"]) == (
        "demand-prophet",
    )
    assert candidate_services("orchestrator", ["orchestrator/**/*.py"]) == ("orchestrator",)
    assert candidate_services("x", ["digital_twin/**/*.py"]) == ("x", "digital-twin")
    assert candidate_services("y", ["**/*", "*"]) == ("y",)


# ---------------------------------------------------------------------------
# 3. Declared absences are exempt, named, counted, and never promoted
# ---------------------------------------------------------------------------
def test_declared_absences_are_exempt_from_the_deployment_leg(
    probe: TopicServiceProbe,
) -> None:
    for binding in probe.bindings:
        assert binding.declared_absence is (binding.consumer in HONEST_ABSENCES)
    absent = [b for b in probe.bindings if b.declared_absence]
    assert absent, "the exemption must be exercised, or this gate proves more than it says"
    assert all(b not in probe.unresolved for b in absent)


def test_the_verdict_names_the_declared_absences_with_their_count(
    probe: TopicServiceProbe,
) -> None:
    """A PASS must not be readable as proof about bindings the gate skipped (I-7)."""
    absent = [b for b in probe.bindings if b.declared_absence]
    assert f"{len(absent)} declared-absence binding(s) exempt and unproven" in probe.detail
    for name in {b.consumer for b in absent}:
        assert name in probe.detail
    assert "unproven" in probe.detail


def test_a_coincidental_service_match_does_not_promote_a_declared_absence(
    probe: TopicServiceProbe,
) -> None:
    """``audit_logger``'s globs include ``orchestrator/audit/**``, so it resolves to the
    ``orchestrator`` service by name. There is still no audit-logger consumer process;
    the exemption is applied before resolution so the verdict cannot contradict
    ``topic_consumer_truth``.
    """
    logger_bindings = [b for b in probe.bindings if b.consumer == "audit_logger"]
    assert logger_bindings, "audit_logger is the worked example; the registry must still record it"
    assert {b.resolved_service for b in logger_bindings} == {"orchestrator"}
    assert all(b.declared_absence for b in logger_bindings)
    enforced = {(b.topic, b.consumer) for b in probe.bindings if not b.declared_absence}
    assert enforced.isdisjoint({(b.topic, b.consumer) for b in logger_bindings})


# ---------------------------------------------------------------------------
# 4. fail vs unavailable vs pass
# ---------------------------------------------------------------------------
def test_the_three_outcomes_have_three_distinct_exit_codes() -> None:
    statuses: tuple[_Status, ...] = ("ok", "fail", "unavailable")
    codes = {status: _synthetic(status).exit_code for status in statuses}
    assert codes == {"ok": EXIT_PASS, "fail": EXIT_FAIL, "unavailable": EXIT_UNAVAILABLE}
    assert len(set(codes.values())) == 3
    assert codes["unavailable"] != EXIT_PASS


def test_an_empty_but_readable_stack_fails_and_names_only_recorded_consumers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deployment leg has teeth: no services means every enforced binding is unresolved."""
    monkeypatch.setattr(tst, "compose_services", lambda: ())
    monkeypatch.setattr(tst, "source_leg", lambda: _SOURCE_OK)
    verdict = evaluate()
    assert verdict.status == "fail"
    assert verdict.exit_code == EXIT_FAIL
    expected = {(t, c) for (t, c) in _recorded_pairs() if c not in HONEST_ABSENCES}
    assert {(b.topic, b.consumer) for b in verdict.unresolved} == expected
    assert all(not b.declared_absence for b in verdict.unresolved)
    assert "no consuming service" in verdict.detail
    assert "recorded consumer" in verdict.detail
    assert any(topic in verdict.detail for topic, _consumer in expected)


def test_an_unreadable_stack_is_unavailable_rather_than_fail_or_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreadable deployment establishes nothing about the deployment (I-7)."""
    monkeypatch.setattr(tst, "compose_services", lambda: None)
    monkeypatch.setattr(tst, "source_leg", lambda: _SOURCE_OK)
    verdict = evaluate()
    assert verdict.status == "unavailable"
    assert verdict.exit_code == EXIT_UNAVAILABLE
    assert tst.COMPOSE_FILE.name in verdict.detail
    assert verdict.bindings == ()


def test_an_unexecutable_source_leg_is_unavailable_not_a_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tst, "source_leg", lambda: None)
    verdict = evaluate()
    assert verdict.status == "unavailable"
    assert verdict.exit_code == EXIT_UNAVAILABLE
    assert "unproven" in verdict.detail


def test_a_failing_source_leg_fails_the_whole_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployed service that subscribes to nothing is not a consumer either."""
    monkeypatch.setattr(
        tst,
        "source_leg",
        lambda: SourceLeg(exit_code=EXIT_FAIL, topics_with_missing=("synapse.demand.forecast",)),
    )
    verdict = evaluate()
    assert verdict.status == "fail"
    assert verdict.exit_code == EXIT_FAIL
    assert "synapse.demand.forecast" in verdict.detail
    assert "no subscribe site" in verdict.detail


def test_c62_maps_unavailable_to_skip_and_fail_to_fail_never_to_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registry row must carry the degradation through, not launder it (I-7)."""
    cases: tuple[tuple[_Status, str], ...] = (
        ("unavailable", "SKIP"),
        ("fail", "FAIL"),
        ("ok", "PASS"),
    )
    for status, expected in cases:
        monkeypatch.setattr(tst, "evaluate", partial(_synthetic, status))
        result = vc.check_topic_service_truth()
        assert result.cid == "C62"
        assert result.status == expected
        assert result.status in vc.STATUSES
        assert result.detail == "synthetic"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
