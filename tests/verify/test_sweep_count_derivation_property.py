"""Every count the sweep reports is computed from what it observed, not read from a file.

Feature: decision-quality-proof, task 5.8. Requirements **R1.6, R1.7, R1.8, R1.9, R1.10,
R1.15**.

The failure mode this closes
---------------------------

``gate-mutations.yaml`` carries two committed numbers about itself --
``completeness.declared_gates`` and ``completeness.registry_size_at_authoring`` -- and its
``sweep_budget`` block carries a worked arithmetic example in a comment. Every one of them
is a *claim*, and the cheapest way to build a green sweep report is to echo a claim back.
A report that said "14 of 64 checks declare a falsification, 14 falsified" by reading the
first number twice would be indistinguishable, at a glance, from one that probed anything.

So the obligation is stated negatively and tested that way: **no reported count is a
function of a declared count.** The declared numbers are perturbed here -- driven up, driven
down, made absurd -- and every derived count is asserted not to move. The only thing a
declared count may produce is the drift *finding* that exists so a hand edit is detectable.

The five clauses
----------------

* **R1.6** -- a check enters the falsified count only when **every operator declared for
  it** reported ``falsified``. Two clauses, and the second is easy to lose: an operator that
  was never probed leaves the check unproven, so a check whose second mutation never ran is
  not falsified by its first. C44 and C56 each declare two operators, so this is a live case
  and not a hypothetical.
* **R1.7** -- the probed count and the declared count in the **same unit**, the operator.
  Asserted by arithmetic: probed + unproven == declared. A report mixing units cannot
  satisfy that identity for any draft with a multi-operator check.
* **R1.8** -- an unprobed declaration is reported **unproven**, and unproven is non-passing.
* **R1.9 / R1.10** -- a registered check declaring no falsification is reported undeclared
  and excluded from PASS-eligibility. The exclusion is asserted in the direction that
  matters: even when a generated sweep hands back a ``falsified`` result for a check listed
  as a reporting tool, that check must not reach the PASS-eligible set.
* **R1.15** -- a complete sweep probes every declared operator; anything less is a FAIL
  naming each shortfall rather than a smaller denominator.

Nothing here starts a process: ``sweep`` is the harness's own orchestrator and substituting
it is how the aggregate is driven at zero process cost (I-0). No gate's evaluator is
replaced (R9.5).

``max_examples`` is never set -- the budget comes from the root ``conftest.py`` profiles.

Locus: ``ci.yml::uplift-verify``'s fast step.

**Validates: Requirements 1.6, 1.7, 1.8, 1.9, 1.10, 1.15**
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import gate_fault_injection as gfi
from scripts.audit.gate_fault_injection import (  # noqa: TC001 - runtime import: typeguard\r
    FaultInjectionReport,  # may resolve test annotations at call time, and a TYPE_CHECKING-only\r
)  # name would then be unresolvable.\r
from tests.verify.sweep_strategies import (
    SWEEP_OUTCOMES,
    SweepDraft,
    patched_sweep,
    probe_result,
    sweep_drafts,
)

REGISTERED_IDS: Final[tuple[str, ...]] = gfi.registered_ids()

#: The rule name the unproven clause raises. Pinned here so a rename in the subject is a
#: test failure rather than a silently unasserted clause.
UNPROVEN_RULE: Final[str] = "declared-operator-unproven"


def _evaluate(
    draft: SweepDraft, results: tuple[gfi.FaultInjectionResult, ...], *, probe: bool = True
) -> FaultInjectionReport:
    """Drive the aggregate over one generated declaration and one generated result set."""
    with tempfile.TemporaryDirectory(prefix="sweep-counts-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep(results):
            return gfi.evaluate(
                declaration_path=declaration_path, schema_path=gfi.SCHEMA_FILE, probe=probe
            )


@st.composite
def complete_sweeps(
    draw: st.DrawFn,
) -> tuple[SweepDraft, tuple[gfi.FaultInjectionResult, ...]]:
    """A declaration plus a result for **every** operator it declares.

    The complete case is drawn separately from the partial one because the two are about
    different clauses: this one is about R1.6's per-check derivation with every operator
    accounted for, and the partial case below is about R1.8's unproven reporting.
    """
    draft = draw(sweep_drafts(registered=REGISTERED_IDS))
    outcomes = draw(
        st.lists(
            st.sampled_from(SWEEP_OUTCOMES),
            min_size=draft.declared_operator_count,
            max_size=draft.declared_operator_count,
        )
    )
    results = tuple(
        probe_result(check, operator_id, outcome)
        for (check, operator_id), outcome in zip(draft.declared_pairs, outcomes, strict=True)
    )
    return draft, results


# Feature: decision-quality-proof, Property 39: The falsified-check count and PASS-eligibility are derived, never asserted  # noqa: E501
@given(case=complete_sweeps())
def test_a_check_is_falsified_only_when_every_operator_declared_for_it_falsified(
    case: tuple[SweepDraft, tuple[gfi.FaultInjectionResult, ...]],
) -> None:
    """R1.6, R1.7: the count is a conjunction over declared operators, recomputed here.

    The conjunction is what makes the count mean something. A disjunction -- "at least one
    of C44's two mutations fired" -- would let a gate that enforces half of what it declares
    report as fully falsified, and the half it does not enforce is precisely the half a
    reader needs to know about.
    """
    draft, results = case
    report = _evaluate(draft, results)

    by_check: dict[str, list[gfi.FaultInjectionResult]] = {}
    for result in results:
        by_check.setdefault(result.check, []).append(result)
    expected = tuple(
        check
        for check in dict.fromkeys(result.check for result in results)
        if all(item.falsified for item in by_check[check])
    )
    assert report.falsified_ids == expected

    # R1.7: same unit, and the identity that proves it. A report counting checks in one term
    # and operators in the other cannot satisfy this for a multi-operator draft.
    assert report.declared_operators == draft.declared_operator_count
    assert report.probed_operators == len(results)
    assert report.probed_operators == report.declared_operators
    assert report.unproven_operator_ids == ()
    assert report.complete_sweep is True
    assert report.probed_operators + len(report.unproven_operator_ids) == (
        report.declared_operators
    )

    # The notes state both counts in words a reader can check, and say "operator(s)" where
    # the unit is the operator. That is the whole of R1.7's reporting half.
    notes = "\n".join(report.notes)
    assert (
        f"{report.probed_operators} of {report.declared_operators} declared operator(s)"
        in notes
    )


@given(case=complete_sweeps(), drift=st.integers(min_value=-9, max_value=9))
def test_no_derived_count_moves_when_the_declared_counts_are_perturbed(
    case: tuple[SweepDraft, tuple[gfi.FaultInjectionResult, ...]], drift: int
) -> None:
    """R1.6, R1.7: the counts are derived, and a perturbed claim proves it.

    ``completeness.declared_gates`` is driven off its true value and every derived count is
    asserted unchanged. Only two things may move: the drift *finding* -- which exists so a
    hand edit to ``gates:`` is itself detectable -- and the verdict it forces. If a derived
    count moved with the claim, the sweep would be reporting the declaration back to itself.
    """
    draft, results = case
    honest = _evaluate(draft, results)

    perturbed_draft = SweepDraft(
        declared=draft.declared,
        operator_counts=draft.operator_counts,
        tools=draft.tools,
        budget=draft.budget,
        declared_gates_override=len(draft.declared) + drift,
    )
    perturbed = _evaluate(perturbed_draft, results)

    assert perturbed.declared_operators == honest.declared_operators
    assert perturbed.probed_operators == honest.probed_operators
    assert perturbed.falsified_ids == honest.falsified_ids
    assert perturbed.pass_eligible_ids == honest.pass_eligible_ids
    assert perturbed.undeclared_ids == honest.undeclared_ids
    assert perturbed.excluded_ids == honest.excluded_ids
    assert perturbed.unproven_operator_ids == honest.unproven_operator_ids

    drift_findings = tuple(
        finding for finding in perturbed.findings if finding.rule == "completeness-count-drift"
    )
    if drift == 0:
        assert drift_findings == ()
    else:
        assert len(drift_findings) == 1
        assert perturbed.verdict == "fail"
        assert str(len(draft.declared)) in drift_findings[0].detail
        assert str(len(draft.declared) + drift) in drift_findings[0].detail


@st.composite
def partial_sweeps(
    draw: st.DrawFn,
) -> tuple[SweepDraft, tuple[gfi.FaultInjectionResult, ...], tuple[tuple[str, str], ...]]:
    """A declaration, a strict subset of its operators probed, and the shortfall."""
    draft = draw(
        sweep_drafts(registered=REGISTERED_IDS, max_checks=3, max_operators=2)
    )
    pairs = draft.declared_pairs
    keep = sorted(
        draw(
            st.lists(
                st.integers(min_value=0, max_value=len(pairs) - 1),
                unique=True,
                max_size=max(0, len(pairs) - 1),
            )
        )
    )
    probed = tuple(pairs[index] for index in keep)
    missing = tuple(pair for pair in pairs if pair not in set(probed))
    results = tuple(
        probe_result(check, operator_id, "falsified") for check, operator_id in probed
    )
    return draft, results, missing


@given(case=partial_sweeps())
def test_an_unprobed_declaration_is_unproven_and_the_run_cannot_pass(
    case: tuple[SweepDraft, tuple[gfi.FaultInjectionResult, ...], tuple[tuple[str, str], ...]],
) -> None:
    """R1.8, R1.15: every declared operator is probed, or the shortfall is named.

    Every probe that *did* run falsified, so the only thing standing between this run and a
    PASS is the shortfall. That is the point: a sweep that quietly narrowed its denominator
    to the operators it managed to run would report a clean sheet over an unknown fraction of
    the declared set, which is absence of proof read as proof (I-7).

    The check-level consequence is asserted too: a check with one falsified operator and one
    unprobed one is **not** in the falsified count, because R1.6's conjunction is over the
    operators declared for it and not over the ones that happened to run.
    """
    draft, results, missing = case
    report = _evaluate(draft, results)

    expected_unproven = tuple(f"{check}/{operator_id}" for check, operator_id in missing)
    assert report.unproven_operator_ids == expected_unproven
    assert report.probed_operators == len(results)
    assert report.declared_operators == draft.declared_operator_count
    assert report.probed_operators + len(missing) == report.declared_operators

    findings = tuple(finding for finding in report.findings if finding.rule == UNPROVEN_RULE)
    assert len(findings) == len(missing)
    assert {(finding.check, finding.operator_id) for finding in findings} == set(missing)
    for finding in findings:
        assert finding.requirement == "R1.7"
        assert "UNPROVEN" in finding.detail
        assert "never a pass" in finding.detail

    assert report.verdict == "fail"
    assert report.passing is False
    assert report.exit_code == gfi.EXIT_FAIL

    # R1.6's second clause: a partially probed check is excluded even though every probe of
    # it falsified.
    partially_probed = {check for check, _operator in missing}
    assert not set(report.falsified_ids) & partially_probed
    assert not set(report.pass_eligible_ids) & partially_probed

    notes = "\n".join(report.notes)
    assert f"{len(missing)} declared operator(s) are UNPROVEN" in notes


@given(case=complete_sweeps())
def test_an_undeclared_or_reporting_tool_check_is_named_and_never_pass_eligible(
    case: tuple[SweepDraft, tuple[gfi.FaultInjectionResult, ...]],
) -> None:
    """R1.9, R1.10 / I-7: an exclusion is a label, never an exemption and never a pass.

    Two directions, and the second is the one that could silently break. A registered check
    that declares nothing must be *named* -- an unnamed gap is not a recorded gap -- and it
    must be absent from PASS-eligibility. The reporting-tool case is asserted with the sweep
    handing back a falsified result for the tool where it overlaps a declared check: that is
    the only way an exclusion could turn into a pass, so it is the case worth generating.
    """
    draft, results = case
    report = _evaluate(draft, results)

    # The registry partitions into declared / reporting-tool / undeclared with nothing lost.
    known = set(draft.declared) | set(draft.tools)
    assert report.undeclared_ids == tuple(cid for cid in REGISTERED_IDS if cid not in known)
    assert not set(report.undeclared_ids) & known
    assert (
        set(report.declared_ids) | set(report.reporting_tool_ids) | set(report.undeclared_ids)
    ) >= set(REGISTERED_IDS)

    # Exclusion is exactly the tools plus the undeclared, deduplicated, tools first.
    assert report.excluded_ids == tuple(dict.fromkeys((*draft.tools, *report.undeclared_ids)))

    # PASS-eligibility is the falsified set minus every reporting tool, and never contains an
    # undeclared check at all.
    assert report.pass_eligible_ids == tuple(
        cid for cid in report.falsified_ids if cid not in set(draft.tools)
    )
    assert not set(report.pass_eligible_ids) & set(report.reporting_tool_ids)
    assert not set(report.pass_eligible_ids) & set(report.undeclared_ids)
    assert set(report.pass_eligible_ids) <= set(report.falsified_ids)

    notes = "\n".join(report.notes)
    assert f"{len(report.undeclared_ids)} undeclared check(s)" in notes
    assert "never a pass" in notes


@given(case=complete_sweeps())
def test_a_suppressed_baseline_empties_the_derived_sets_without_hiding_the_probes(
    case: tuple[SweepDraft, tuple[gfi.FaultInjectionResult, ...]],
) -> None:
    """R1.16 alongside R1.6: the counts go to zero, the observations do not disappear.

    Without an unmutated baseline an already-red gate stays red under mutation and reads as
    ``falsified``, so a report produced that way cannot support any count. What it can still
    do is report what it saw -- that is what the diagnostic mode is for. Both halves are
    asserted, because zeroing the observations too would make ``--no-baseline`` useless and
    keeping the counts would make it dangerous.
    """
    draft, results = case
    with tempfile.TemporaryDirectory(prefix="sweep-counts-nobaseline-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep(results):
            report = gfi.evaluate(
                declaration_path=declaration_path,
                schema_path=gfi.SCHEMA_FILE,
                probe=True,
                with_baseline=False,
            )

    assert report.baseline_suppressed is True
    assert report.verdict == "unavailable"
    assert report.passing is False
    assert report.falsified_ids == ()
    assert report.pass_eligible_ids == ()
    # The observations survive: same count, same identities, in the same order.
    assert len(report.results) == len(results)
    assert tuple((item.check, item.operator_id) for item in report.results) == tuple(
        (item.check, item.operator_id) for item in results
    )
    assert report.probed_operators == len(results)
    assert "baseline" in report.reason
    assert "manufactured proof" in report.reason
