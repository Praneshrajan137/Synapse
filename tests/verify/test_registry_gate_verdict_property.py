"""Property-based test for the Check_Registry gate verdict (design E1.1 / AD-1).

Feature: purpose-achievement-audit, Property 1: Registry verdict is a total function
of the result set

    *For any* multiset of check results and *any* pair of (registered ids, executed
    ids) sets, the registry gate exits ``1`` iff at least one result is ``FAIL`` or
    the two id sets differ, exits ``2`` iff zero checks ran or every result is
    ``SKIP``, and exits ``0`` otherwise - independently of the
    PASS/FAIL/PARTIAL/SKIP/TOTAL counts being equal to any previously observed
    counts, and naming every failing and every missing identifier.

Why the property is shaped this way. The audit finding behind Requirement 1 is that
the registry's exit code was consumed by nothing, and that the one indirect coupling
that did exist compared *counts* stated in a document. Counts are exactly the wrong
oracle: two checks flipping in opposite directions leave every count identical
(R1.3). So this test never asserts a count against a remembered count - it asserts
that the verdict is a function of the *statuses and identities* in the result set,
that the mapping is total (every result set lands on exactly one of three verdicts),
that it agrees with the declared first-match-wins precedence, and that the exit code
a CI step observes is the verdict's own (R1.8: the default invocation must be able to
fail).

The real 53-check registry is never executed here: it shells out to git/docker probes
and takes minutes, which I-0 forbids on this machine. ``evaluate_results`` is pure by
design precisely so the verdict can be driven over synthetic (registration,
execution) pairs, and ``run`` is driven with ``evaluate`` replaced by a
pre-computed verdict so only the reporting and exit-status path is exercised.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 1.1, 1.3, 1.7, 1.8, 2.9**
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import registry_gate
from scripts.audit.registry_gate import EXIT_FAIL, EXIT_PASS, EXIT_UNAVAILABLE
from scripts.audit.verify_claims import STATUSES, CheckResult
from tests.verify.strategies import (
    RegistryScenario,
    check_ids,
    check_result_multisets,
    check_results,
    registry_scenarios,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The three verdicts the gate may reach, and the exit status each mandates.
EXPECTED_EXIT_CODES: Final[dict[str, int]] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}

#: Verdicts a CI step must not treat as success (I-7: a SKIP is not a PASS).
NON_PASSING: Final[tuple[str, ...]] = ("fail", "unavailable")


def expected_verdict(scenario: RegistryScenario) -> str:
    """The verdict the declared precedence mandates, recomputed independently.

    Design E1.1's rules, first match wins - deliberately written out here rather
    than imported from the gate, so the test compares two implementations instead of
    one:

    1. nothing registered                     -> ``unavailable`` (R1.6)
    2. registered and executed id sets differ -> ``fail`` (R1.7)
    3. every executed check SKIPped           -> ``unavailable`` (R1.6, I-7)
    4. any ``FAIL``                           -> ``fail`` (R1.1, R1.3)
    5. otherwise                              -> ``pass``

    The tally comes from ``RegistryScenario.status_counts``, which recomputes the
    four counts from the results rather than reading the gate's own ``counts``.
    """
    counts = scenario.status_counts
    if not scenario.registered_ids:
        return "unavailable"
    if scenario.missing_ids or scenario.foreign_ids:
        return "fail"
    if counts["TOTAL"] > 0 and counts["SKIP"] == counts["TOTAL"]:
        return "unavailable"
    if any(result.status == "FAIL" for result in scenario.results):
        return "fail"
    return "pass"


# Feature: purpose-achievement-audit, Property 1: Registry verdict is a total function
# of the result set
@given(scenario=registry_scenarios())
def test_registry_verdict_is_a_total_function_of_the_result_set(
    scenario: RegistryScenario,
) -> None:
    """R1.1, R1.3, R1.7, R2.9: one verdict per result set, derived from statuses."""
    verdict = registry_gate.evaluate_results(scenario.registered_ids, scenario.results)

    # Total: exactly one of three verdicts, each mapping to its own exit status, and
    # only ``pass`` is passing - ``unavailable`` (2) is an absence of proof (I-7).
    assert verdict.verdict in EXPECTED_EXIT_CODES
    assert verdict.exit_code == EXPECTED_EXIT_CODES[verdict.verdict]
    assert verdict.passing is (verdict.verdict == "pass")
    assert (verdict.exit_code == EXIT_PASS) is verdict.passing

    # A function: the same (registration, execution) pair yields the same verdict.
    # The gate reads no file and holds no state, so this must hold by construction.
    assert registry_gate.evaluate_results(scenario.registered_ids, scenario.results) == verdict

    # Agrees with the declared precedence, recomputed from an independent tally.
    assert verdict.verdict == expected_verdict(scenario)

    # The gate's own counts agree with that independent recompute (R1.3: the verdict
    # is derived from these statuses, never from a comparison against earlier counts).
    assert dict(verdict.counts) == scenario.status_counts

    # Identity is preserved, not summarised: what executed, and what did not (R1.7).
    assert verdict.executed_ids == scenario.executed_ids
    assert verdict.missing_ids == scenario.missing_ids
    assert verdict.registered_ids == scenario.registered_ids

    # Every failing result is surfaced as a failure, and every unproven one as
    # unproven - the two are disjoint and neither can reach the PASS count.
    assert verdict.failures == tuple(r for r in scenario.results if r.status == "FAIL")
    assert verdict.unproven == tuple(
        r for r in scenario.results if r.status in registry_gate.UNPROVEN_STATUSES
    )
    # Disjoint by construction: a FAIL is never unproven and an unproven is never a
    # failure, so no result can be counted in two buckets.
    assert all(r.status == "FAIL" for r in verdict.failures)
    assert all(r.status in registry_gate.UNPROVEN_STATUSES for r in verdict.unproven)

    # R2.9: a check that did not report PASS is excluded from the published PASS
    # count and is instead named among the failures or the unproven.
    assert verdict.counts["PASS"] == sum(1 for r in scenario.results if r.status == "PASS")
    for result in scenario.results:
        if result.status != "PASS":
            assert result in verdict.failures or result in verdict.unproven

    # Naming: every registered id that did not execute, and every id reported that
    # was never registered, appears in the reason a CI log will carry (R1.7).
    for cid in scenario.missing_ids:
        assert cid in verdict.reason
    for cid in scenario.foreign_ids:
        assert cid in verdict.reason

    # When the FAIL branch is what decided the verdict, each failing id is named
    # with a status distinct from PASS, PARTIAL, and SKIP (R1.1, R1.2).
    if not scenario.missing_ids and not scenario.foreign_ids and verdict.failures:
        assert verdict.verdict == "fail"
        for result in verdict.failures:
            assert f"{result.cid}=FAIL" in verdict.reason


@given(results=check_result_multisets())
def test_a_registry_with_nothing_registered_is_unavailable(
    results: tuple[CheckResult, ...],
) -> None:
    """R1.6: zero registered checks is an absence of proof, never a pass.

    Rule 1 precedes rule 2, so this holds whatever the (nonsensical) result set
    carries: a gate that cannot see a registration list has nothing to gate on.
    """
    verdict = registry_gate.evaluate_results((), results)

    assert verdict.verdict == "unavailable"
    assert verdict.exit_code == EXIT_UNAVAILABLE
    assert not verdict.passing
    assert verdict.verdict in NON_PASSING


@given(scenario=registry_scenarios(modes=("complete",)))
def test_an_all_skip_execution_is_unavailable_rather_than_a_pass(
    scenario: RegistryScenario,
) -> None:
    """R1.6 / I-7: every check SKIPping proves nothing, so it cannot exit 0."""
    skipped = tuple(dataclasses.replace(r, status="SKIP") for r in scenario.results)
    verdict = registry_gate.evaluate_results(scenario.registered_ids, skipped)

    assert verdict.verdict == "unavailable"
    assert verdict.exit_code == EXIT_UNAVAILABLE
    assert not verdict.passing
    assert verdict.counts["PASS"] == 0
    assert verdict.counts["SKIP"] == verdict.counts["TOTAL"] == len(skipped)
    assert len(verdict.unproven) == len(skipped)


@st.composite
def compensating_flip_pairs(
    draw: st.DrawFn,
) -> tuple[tuple[str, ...], tuple[CheckResult, ...], tuple[CheckResult, ...]]:
    """Two executions with identical counts but different failing identifiers.

    This is the blind spot Requirement 1.3 names: one check flips ``PASS``->``FAIL``
    while another flips ``FAIL``->``PASS``, so every count and any headline derived
    from those counts is byte-identical across the two executions.
    """
    ids = draw(check_ids(min_size=2, max_size=6))
    passing_cid, failing_cid = ids[0], ids[1]
    rest = tuple(draw(check_results(cid=cid)) for cid in ids[2:])

    before = (
        draw(check_results(cid=passing_cid, status="PASS")),
        draw(check_results(cid=failing_cid, status="FAIL")),
        *rest,
    )
    after = (
        dataclasses.replace(before[0], status="FAIL"),
        dataclasses.replace(before[1], status="PASS"),
        *rest,
    )
    return ids, before, after


@given(pair=compensating_flip_pairs())
def test_two_compensating_flips_do_not_produce_the_same_verdict(
    pair: tuple[tuple[str, ...], tuple[CheckResult, ...], tuple[CheckResult, ...]],
) -> None:
    """R1.3: the verdict distinguishes executions that the counts cannot."""
    registered, before, after = pair
    first = registry_gate.evaluate_results(registered, before)
    second = registry_gate.evaluate_results(registered, after)

    # The counts - and therefore any document headline pinned to them - are equal.
    assert dict(first.counts) == dict(second.counts)

    # The verdicts are still both failing, and they name different checks.
    assert first.verdict == second.verdict == "fail"
    assert tuple(r.cid for r in first.failures) != tuple(r.cid for r in second.failures)
    assert first.reason != second.reason
    assert f"{before[1].cid}=FAIL" in first.reason
    assert f"{after[0].cid}=FAIL" in second.reason


@given(scenario=registry_scenarios())
def test_run_propagates_the_verdict_exit_code_and_names_the_evidence(
    scenario: RegistryScenario,
) -> None:
    """R1.8: the exit status a CI step observes is the verdict's, in every mode.

    ``--check`` only suppresses the trailing operator note; a gate whose default
    invocation cannot fail is the hole this feature exists to close, so both modes
    must return the same verdict-derived code.
    """
    verdict = registry_gate.evaluate_results(scenario.registered_ids, scenario.results)
    modes: Sequence[tuple[bool, bool]] = (
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    )

    for as_json, check in modes:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(registry_gate, "evaluate", lambda: verdict)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = registry_gate.run(as_json=as_json, check=check)
        text = stdout.getvalue()

        assert code == verdict.exit_code
        assert (code == EXIT_PASS) is verdict.passing

        if as_json:
            payload = json.loads(text)
            # Canonical serialisation: sorted keys, tight separators.
            assert text.strip() == json.dumps(payload, sort_keys=True, separators=(",", ":"))
            assert payload["verdict"] == verdict.verdict
            assert payload["missing_ids"] == list(verdict.missing_ids)
            assert [r["cid"] for r in payload["failures"]] == [r.cid for r in verdict.failures]
        else:
            # The human report names every missing id and every failing check, with a
            # status distinct from PASS, PARTIAL, and SKIP (R1.1, R1.2, R1.7).
            for cid in verdict.missing_ids:
                assert cid in text
            for result in verdict.failures:
                assert result.cid in text
            if verdict.failures:
                assert "[XX]" in text
            assert f"REGISTERED={len(verdict.registered_ids)}" in text


def test_the_status_vocabulary_the_verdict_partitions_is_the_registry_vocabulary() -> None:
    """The gate partitions exactly the statuses the registry can emit.

    A status the gate does not know about would fall through to the ``pass`` branch,
    so this pins the vocabulary the four buckets are drawn from.
    """
    assert set(registry_gate.UNPROVEN_STATUSES) < set(STATUSES)
    assert set(STATUSES) - {"PASS", "FAIL"} == set(registry_gate.UNPROVEN_STATUSES)
    counts = registry_gate.status_counts(())
    assert set(counts) == {*STATUSES, "TOTAL"}
    assert all(value == 0 for value in counts.values())
