"""Property-based test for the generated Truth_Ledger (design E1.4 / AD-2).

Feature: purpose-achievement-audit, Property 9: The generated ledger round-trips
against its registry execution

    *For any* registry execution, rendering the Truth_Ledger's generated region and
    then re-rendering from that region's inputs is byte-identical; every registered
    identifier has exactly one row whose status, title, and detail equal that
    execution's values; every row cites a registered identifier; the rendered summary
    counts and the rendered README headline counts equal that execution's counts; and
    any edit to the generated region is detected with a printed difference.

Why a property and not examples. Requirement 10 is a *drift* finding, and drift is
not a fixed shape: the committed ledger simultaneously overstated (48 checks against
a registry of 53, six rows citing no check) and understated (fifteen rows reading
FAIL against checks that assert the resolved state), with three substance rows off by
three because a de-confliction reached the code and not the table. Pinning today's
53 identifiers as examples would test the instance that has already been fixed. The
class of defect is "a row set, a status column, or a count that is not a projection
of the execution the document claims to report", so the property quantifies over
generated (registration, execution) pairs and asserts the projection is **total**
there: exactly one row per registered id, no row without one, and every rendered
number traceable to that one execution.

Ground truth. ``tests/verify/strategies.registry_scenarios`` supplies the
(registered ids, emitted results) pair; ``RegistryScenario.status_counts`` recomputes
the four counts plus ``TOTAL`` from the results independently of the gate's own
tally, and the row expectations below are rebuilt from the drafted results rather
than read back out of ``ledger_gen.row_statuses`` / ``row_details``. Even the
markdown cell normalisation is re-derived (:func:`cell`) instead of imported, so an
agreement is two implementations meeting rather than one helper agreeing with itself.

Two honest asymmetries this test pins rather than papers over, both consequences of
projecting from exactly one execution (I-7, and the module docstring of the subject):

* a **PASS row carries no detail** - ``RegistryVerdict`` holds ``CheckResult``s only
  for checks that failed or went unproven, and re-running a check to fetch a sentence
  would be a second execution and therefore a second truth;
* a **registered check that emitted no result renders ``NOT EXECUTED``**, never a
  blank and never a pass - ``registry_gate`` already fails the build for it (R1.7).

The real 53-check registry is never executed here. It shells out to git and docker
probes and takes minutes, which I-0 forbids on this machine; ``render`` /
``render_region`` / ``probe_text`` are pure by design and take their titles as a
parameter precisely so the projection can be driven from synthetic verdicts. The
``run`` cases replace ``registry_gate.evaluate`` with a pre-computed verdict and
write inside a ``tempfile.TemporaryDirectory``, so no process is started and
``docs/state/CURRENT.md`` is never rewritten. The one test that reads the committed
ledger reads it statically and asserts only about its markers and its prose.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.6, 10.7, 10.8, 10.9**
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given

from scripts.audit import ledger_gen, registry_gate
from scripts.audit.ledger_gen import (
    GENERATED_BEGIN,
    GENERATED_END,
    NOT_EXECUTED,
    NO_DETAIL,
    SUMMARY_CATEGORIES,
)
from tests.verify.strategies import RegistryScenario, check_results, registry_scenarios

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from collections.abc import Mapping

    from pytest import CaptureFixture

    from scripts.audit.registry_gate import RegistryVerdict

#: Divergence modes in which every registered id is reported at most once, so "the
#: status that execution reported for that id" (R10.4) has exactly one answer. A
#: duplicated id is spec-silent - ``registry_gate`` compares id *sets*, so it does not
#: even make the verdict fail - and inventing a tie-break here would test this test's
#: guess rather than the requirement. The round-trip and drift cases below quantify
#: over every mode, duplicates included.
UNAMBIGUOUS_MODES: Final[tuple[str, ...]] = ("complete", "missing", "foreign", "empty")

#: Detail rendered for a registered check that emitted nothing (subject-side wording).
UNEMITTED_DETAIL: Final[str] = "no result was emitted for this registered check"

#: Hand-authored prose that must survive every regeneration (AD-2).
_HEAD: Final[str] = (
    "# Current State (synthetic fixture)\n\n"
    "Hand-authored prose above the markers. A generator that ate this would be\n"
    "abandoned rather than trusted.\n\n## Verification Matrix\n\n"
)
_TAIL: Final[str] = "\n\n## How to regenerate\n\nHand-authored prose below the markers.\n"

#: The committed ledger's own placeholder shape: markers present, nothing projected.
_UNGENERATED: Final[str] = "<!-- NOT YET GENERATED. Run --write. -->"

#: Splits a markdown table row on unescaped pipes only, so a cell carrying an escaped
#: ``\|`` stays one cell.
_CELL_SPLIT: Final[re.Pattern[str]] = re.compile(r"(?<!\\)\|")

_MATRIX_HEADER: Final[str] = "| # | Subject (as registered) | Status | Detail |"
_SUMMARY_HEADER: Final[str] = "| Category | Count |"


# ---------------------------------------------------------------------------
# Independent re-derivations: the document, read back
# ---------------------------------------------------------------------------


def cell(text: str) -> str:
    """One markdown cell as the renderer must have written it.

    Deliberately re-derived rather than imported from ``ledger_gen._cell``: a row
    assertion that normalised its expectation through the renderer's own helper would
    agree with it by construction, including on a bug in the escaping.
    """
    flattened = " ".join(text.split())
    return flattened.replace("|", "\\|") or NO_DETAIL


def cells(line: str) -> tuple[str, ...]:
    """The cells of one table row, unescaped pipes only, each stripped."""
    return tuple(part.strip() for part in _CELL_SPLIT.split(line)[1:-1])


def region_of(text: str) -> str:
    """The body between the generated markers, exclusive."""
    _, _, rest = text.partition(GENERATED_BEGIN)
    body, _, _ = rest.partition(GENERATED_END)
    return body.strip("\n")


def _table_after(region: str, header: str) -> tuple[tuple[str, ...], ...]:
    """Rows of the table whose header line is ``header`` (separator dropped)."""
    lines = region.splitlines()
    start = lines.index(header) + 2  # header + `| --- | ... |` separator
    rows: list[tuple[str, ...]] = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        rows.append(cells(line))
    return tuple(rows)


def matrix_rows(region: str) -> tuple[tuple[str, ...], ...]:
    """Every check-matrix row: ``(id, subject, status, detail)``."""
    return _table_after(region, _MATRIX_HEADER)


def summary_counts(region: str) -> dict[str, str]:
    """The rendered summary table as ``category -> count`` strings."""
    return {row[0]: row[1] for row in _table_after(region, _SUMMARY_HEADER)}


def headline_counts(region: str) -> str:
    """The rendered ``README.md`` headline line's bold payload (R10.9)."""
    prefix = "`README.md` headline counts"
    line = next(one for one in region.splitlines() if one.startswith(prefix))
    return line.split("**")[1]


# ---------------------------------------------------------------------------
# Independent re-derivations: what the execution mandates
# ---------------------------------------------------------------------------


def verdict_of(scenario: RegistryScenario) -> RegistryVerdict:
    """One registry verdict for a drafted execution. Pure - no check is run."""
    return registry_gate.evaluate_results(scenario.registered_ids, scenario.results)


def titles_of(scenario: RegistryScenario) -> dict[str, str]:
    """``id -> registered title``, taken from the drafted registration list (R10.8)."""
    return {cid: title for cid, title, _fn in scenario.as_registry()}


def expected_matrix(scenario: RegistryScenario) -> tuple[tuple[str, ...], ...]:
    """The rows this execution mandates, rebuilt from the drafted results.

    One row per registered id in registration order (R10.2, R10.3), carrying the
    registered title (R10.8) and the status that execution reported (R10.4). Detail
    follows the two asymmetries named in the module docstring: a pass has none, and an
    unemitted registered check says so.
    """
    by_id = {result.cid: result for result in scenario.results}
    rows: list[tuple[str, ...]] = []
    for cid in scenario.registered_ids:
        result = by_id.get(cid)
        if result is None:
            status, detail = NOT_EXECUTED, UNEMITTED_DETAIL
        elif result.status == "PASS":
            status, detail = "PASS", NO_DETAIL
        else:
            status, detail = result.status, result.detail
        rows.append((cell(cid), cell(titles_of(scenario)[cid]), cell(status), cell(detail)))
    return tuple(rows)


def document(body: str) -> str:
    """A ledger carrying ``body`` inside the markers and prose on both sides."""
    return f"{_HEAD}{GENERATED_BEGIN}\n{body}\n{GENERATED_END}{_TAIL}"


# ---------------------------------------------------------------------------
# R10.1 - R10.4, R10.8, R10.9: the projection
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 9: The generated ledger round-trips
# against its registry execution
@given(scenario=registry_scenarios(modes=UNAMBIGUOUS_MODES))
def test_the_generated_ledger_round_trips_against_its_registry_execution(
    scenario: RegistryScenario,
) -> None:
    """R10.1-R10.4, R10.8, R10.9: every row and every number is one execution's.

    The clauses are asserted together because they are one obligation: the document
    *is* the projection. Splitting them would let a row set agree while the counts
    beneath it came from somewhere else, which is precisely the drift Requirement 10
    records.
    """
    verdict = verdict_of(scenario)
    titles = titles_of(scenario)
    generated = ledger_gen.render(verdict, document(_UNGENERATED), titles=titles)
    region = region_of(generated)

    # Byte-identical re-rendering, both from the verdict and back through the
    # document it produced: `--check` is exactly this comparison, so a non-idempotent
    # renderer would report drift against its own output on every second CI run.
    assert ledger_gen.render_region(verdict, titles=titles) == region
    assert ledger_gen.render(verdict, generated, titles=titles) == generated

    # R10.2, R10.3, R10.4, R10.8: one row per registered id, in registration order,
    # carrying that execution's status and the registered subject.
    rows = matrix_rows(region)
    assert rows == expected_matrix(scenario)
    assert tuple(row[0] for row in rows) == scenario.registered_ids
    assert len(rows) == len(set(row[0] for row in rows)) == len(scenario.registered_ids)

    # R10.3, stated as the negative: an id nobody registered gets no row. It is still
    # named in the region, so no emitted result is silently dropped.
    for cid in scenario.foreign_ids:
        assert cid not in {row[0] for row in rows}
        assert cid in region

    # R10.1: the summary counts are that execution's counts, checked against the
    # strategy's independent tally rather than against `verdict.counts`.
    counts = summary_counts(region)
    independent = scenario.status_counts
    assert {category: counts[category] for category in SUMMARY_CATEGORIES} == {
        category: str(independent[category]) for category in SUMMARY_CATEGORIES
    }
    assert counts["REGISTERED"] == str(len(scenario.registered_ids))
    assert counts[NOT_EXECUTED] == str(len(scenario.missing_ids))

    # R10.9: the README headline counts come from the same execution, so the two
    # documents cannot state different numbers for one run.
    assert headline_counts(region) == " / ".join(
        f"{independent[category]} {category}" for category in SUMMARY_CATEGORIES
    )

    # I-7: no row invents a pass. A check that emitted nothing reads NOT EXECUTED and
    # never blank, and the PASS cells are exactly the results that reported PASS.
    assert {row[0] for row in rows if row[2] == NOT_EXECUTED} == set(scenario.missing_ids)
    assert sum(1 for row in rows if row[2] == "PASS") == independent["PASS"]
    assert all(row[2] and row[3] for row in rows)


@given(scenario=registry_scenarios())
def test_rendering_preserves_every_byte_of_prose_outside_the_markers(
    scenario: RegistryScenario,
) -> None:
    """AD-2: the generator owns the delimited region and nothing else.

    Quantified over every divergence mode, duplicates included: whatever the
    execution looked like, the hand-authored halves are carried through unmodified
    and the markers stay singular so the next ``--check`` can still find the region.
    """
    verdict = verdict_of(scenario)
    titles = titles_of(scenario)
    previous = document(_UNGENERATED)
    generated = ledger_gen.render(verdict, previous, titles=titles)

    assert generated.startswith(_HEAD)
    assert generated.endswith(_TAIL)
    assert generated.count(GENERATED_BEGIN) == generated.count(GENERATED_END) == 1
    assert _UNGENERATED not in generated
    # Idempotent through a second document, which is what `--write` twice must be.
    assert ledger_gen.render(verdict, generated, titles=titles) == generated


# ---------------------------------------------------------------------------
# R10.7: drift is detected, and the difference is printed
# ---------------------------------------------------------------------------


@given(scenario=registry_scenarios())
def test_an_edit_inside_the_generated_region_is_reported_with_a_difference(
    scenario: RegistryScenario,
) -> None:
    """R10.7: a hand edit inside the markers fails, naming what moved.

    Three mutations, failing for three reasons. A fabricated row is the
    overstatement Requirement 10 records - a row citing a check nobody registered. A
    flipped status is the quieter direction: the ledger's own status column drifting
    away from the checks it claims to define. A deleted last line is silent loss of
    coverage. All three must be reported ``fail`` with a unified diff carrying the
    offending text, never merely flagged.
    """
    verdict = verdict_of(scenario)
    titles = titles_of(scenario)
    clean = ledger_gen.render(verdict, document(_UNGENERATED), titles=titles)

    assert ledger_gen.probe_text(verdict, clean, titles=titles).status == "ok"
    assert ledger_gen.probe_text(verdict, clean, titles=titles).passing

    fabricated = "| C999 | Fabricated subject | PASS | - |"
    mutations = [
        clean.replace(GENERATED_END, f"{fabricated}\n{GENERATED_END}", 1),
        clean.replace(f"\n{GENERATED_END}", "", 1),
    ]
    flipped = clean.replace("| PASS |", "| FAIL |", 1)
    if flipped != clean:
        mutations.append(flipped)

    for mutated in mutations:
        assert mutated != clean
        probe = ledger_gen.probe_text(verdict, mutated, titles=titles)
        assert probe.status == "fail"
        assert not probe.passing
        assert probe.exit_code == 1
        # A diff, not a bare verdict: the reader is told what moved.
        assert "@@" in probe.diff
        assert "(committed)" in probe.diff and "(regenerated)" in probe.diff

    assert fabricated in ledger_gen.probe_text(verdict, mutations[0], titles=titles).diff


@given(scenario=registry_scenarios(modes=("complete",)))
def test_the_cli_writes_the_region_and_then_prints_the_diff_on_drift(
    scenario: RegistryScenario,
    capsys: CaptureFixture[str],
) -> None:
    """R10.7 through the CLI: ``--write`` then ``--check``, and drift exits ``1``.

    The exit status is the point. ``--check`` is what a workflow step runs, so a
    ledger that drifted must make that step non-zero and must print the difference to
    stdout where the CI log will carry it. Both forms - bare and ``--check`` - return
    the verdict-derived code, because a default invocation that cannot fail is the
    hole this feature exists to close.
    """
    verdict = verdict_of(scenario)
    with tempfile.TemporaryDirectory(prefix="ledger-gen-") as tmp:
        path = Path(tmp) / "CURRENT.md"
        path.write_text(document(_UNGENERATED), encoding="utf-8", newline="\n")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(registry_gate, "evaluate", lambda: verdict)

            capsys.readouterr()
            assert ledger_gen.run(write=True, path=path) == 0
            written = path.read_text(encoding="utf-8")
            assert written.startswith(_HEAD) and written.endswith(_TAIL)

            # In sync, in both non-write forms.
            assert ledger_gen.run(path=path) == 0
            assert ledger_gen.run(check=True, path=path) == 0
            # A second --write is a no-op on the bytes (idempotence, again via IO).
            assert ledger_gen.run(write=True, path=path) == 0
            assert path.read_text(encoding="utf-8") == written

            path.write_text(
                written.replace(GENERATED_END, f"| C999 | Fabricated | PASS | - |\n{GENERATED_END}"),
                encoding="utf-8",
                newline="\n",
            )
            capsys.readouterr()
            assert ledger_gen.run(check=True, path=path) == 1
            printed = capsys.readouterr().out
            assert "@@" in printed
            assert "C999" in printed
            assert "ledger-gen: FAIL" in printed


# ---------------------------------------------------------------------------
# R10.6: a newly registered check has a row, or the build stops
# ---------------------------------------------------------------------------


@given(
    scenario=registry_scenarios(modes=("complete",)),
    newcomer=check_results(cid="C777", status="PASS"),
)
def test_a_newly_registered_check_fails_the_ledger_until_it_is_regenerated(
    scenario: RegistryScenario,
    newcomer: object,
) -> None:
    """R10.6: registering a check without regenerating the ledger cannot pass.

    The mechanism is the same comparison R10.7 uses, but the direction is the one
    that let the committed ledger fall five checks behind its registry: the change
    that adds ``@register`` adds no row, so the projection grows and the committed
    document does not. Until it is regenerated, the check fails naming the new
    identifier; afterwards the row exists and carries the newcomer's own status.
    """
    assert isinstance(newcomer, ledger_gen.verify_claims.CheckResult)
    if newcomer.cid in scenario.registered_ids:  # pragma: no cover - ids are C1..C99
        return

    before = verdict_of(scenario)
    titles = titles_of(scenario)
    committed = ledger_gen.render(before, document(_UNGENERATED), titles=titles)
    assert ledger_gen.probe_text(before, committed, titles=titles).status == "ok"

    grown = RegistryScenario(
        registered_ids=(*scenario.registered_ids, newcomer.cid),
        results=(*scenario.results, newcomer),
    )
    after = verdict_of(grown)
    grown_titles = titles_of(grown)

    stale = ledger_gen.probe_text(after, committed, titles=grown_titles)
    assert stale.status == "fail"
    assert not stale.passing
    assert newcomer.cid in stale.diff

    regenerated = ledger_gen.render(after, committed, titles=grown_titles)
    assert ledger_gen.probe_text(after, regenerated, titles=grown_titles).status == "ok"
    rows = matrix_rows(region_of(regenerated))
    assert tuple(row[0] for row in rows) == grown.registered_ids
    assert rows[-1][0] == newcomer.cid
    assert rows[-1][2] == "PASS"


# ---------------------------------------------------------------------------
# I-7: nothing this generator cannot project reads as a pass
# ---------------------------------------------------------------------------


@given(scenario=registry_scenarios(modes=("complete",)))
def test_an_unprojectable_ledger_is_unavailable_and_never_a_pass(
    scenario: RegistryScenario,
) -> None:
    """I-7 / R10.7: no registry, no document, or no markers is exit ``2``.

    ``2`` is a *non-passing* status, and the distinction from ``1`` is what lets a CI
    log tell "the ledger drifted" from "the ledger could not be projected". A
    generator that reported ok because it found nothing to compare would be the
    absence-of-proof-as-proof failure this repository refuses.
    """
    verdict = verdict_of(scenario)
    titles = titles_of(scenario)
    clean = ledger_gen.render(verdict, document(_UNGENERATED), titles=titles)
    empty_registry = registry_gate.evaluate_results((), ())

    unprojectable: tuple[tuple[RegistryVerdict, str | None], ...] = (
        (empty_registry, clean),  # nothing registered: no matrix to project
        (verdict, None),  # document missing or unreadable
        (verdict, clean.replace(GENERATED_BEGIN, "", 1)),  # begin marker gone
        (verdict, clean.replace(GENERATED_END, "", 1)),  # end marker gone
        (verdict, f"{clean}\n{GENERATED_BEGIN}\n{GENERATED_END}\n"),  # duplicated
        (verdict, f"{_HEAD}{GENERATED_END}\nbody\n{GENERATED_BEGIN}{_TAIL}"),  # inverted
    )
    for probed, committed in unprojectable:
        probe = ledger_gen.probe_text(probed, committed, titles=titles)
        assert probe.status == "unavailable"
        assert not probe.passing
        assert probe.exit_code == 2
        assert probe.detail
        assert probe.diff == ""

    # And `--write` refuses on the same conditions rather than overwriting a
    # hand-written ledger it cannot project.
    with tempfile.TemporaryDirectory(prefix="ledger-gen-") as tmp:
        markerless = Path(tmp) / "CURRENT.md"
        body = f"{_HEAD}A hand-written ledger with no generated region.\n"
        markerless.write_text(body, encoding="utf-8", newline="\n")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(registry_gate, "evaluate", lambda: verdict)
            assert ledger_gen.run(write=True, path=markerless) == 2
        assert markerless.read_text(encoding="utf-8") == body


# ---------------------------------------------------------------------------
# The committed ledger, read statically
# ---------------------------------------------------------------------------


def test_prose_that_quotes_the_markers_is_not_a_second_region() -> None:
    """A document that *documents* the marker convention stays projectable.

    The regression this pins is a real one and it failed in the least useful
    direction. ``render`` used to count marker literals textually; the committed
    ledger's "How to regenerate" section quotes both markers in a sentence while
    explaining the mechanism, so the count was 2 and 2, the region was reported
    unusable, and ``--check`` exited ``2`` (unavailable) rather than ``1`` (drift).
    Both are non-passing, but ``unavailable`` says "nothing was checked" where the
    truth was "the document disagrees with its registry" - and it blocked ``--write``
    on a document whose region was perfectly well formed.

    Escaping that one sentence would have restored the verdict and left the trap
    armed for the next person who writes about the format. So the delimiter rule is
    structural instead: a marker delimits only when it owns its line. This test is
    the universal statement of that - prose quoting the markers, anywhere outside the
    region, changes nothing - rather than a snapshot of the committed document's
    current wording.
    """
    documented = (
        f"{_TAIL}Prose outside the `{GENERATED_BEGIN}` / `{GENERATED_END}` markers is "
        "never touched by either form.\n"
    )
    ledger = f"{_HEAD}{GENERATED_BEGIN}\n{_UNGENERATED}\n{GENERATED_END}{documented}"
    verdict = registry_gate.evaluate_results(
        ("C1",),
        (ledger_gen.verify_claims.CheckResult(cid="C1", title="t", status="PASS", detail="d"),),
    )
    titles = {"C1": "synthetic check C1"}

    begin, end = ledger_gen.generated_region_bounds(ledger)
    assert begin < end

    projected = ledger_gen.render(verdict, ledger, titles=titles)
    assert projected.startswith(_HEAD)
    assert projected.endswith(documented)
    assert "| C1 | synthetic check C1 | PASS |" in region_of(projected)

    # The verdict is a real one: drift, then in-sync. Never `unavailable`.
    drifted = ledger_gen.probe_text(verdict, ledger, titles=titles)
    assert drifted.status == "fail"
    assert drifted.exit_code == 1
    assert drifted.diff
    assert ledger_gen.probe_text(verdict, projected, titles=titles).status == "ok"


def test_the_committed_ledger_has_one_generated_region_whose_prose_survives() -> None:
    """R10.7 against the real document: the region exists and is delimited once.

    A static read - the Check_Registry is *not* executed, because executing it drives
    git and docker probes for minutes (I-0). What that leaves verifiable here is the
    part that has to hold before any CI run can compare anything: the committed
    ledger carries exactly one generated region, and projecting a verdict into it
    changes nothing outside the markers. Whether the region's contents match a live
    execution is asserted by ``truth-gates.yml::truth-gates`` running
    ``python -m scripts.audit.ledger_gen --check``.

    "Delimited once" counts markers that own their line, not marker literals: the
    document's own "How to regenerate" prose quotes both, and a textual count of that
    is what made the generator report the region unusable (see the test above).
    """
    committed = ledger_gen.LEDGER_DOC.read_text(encoding="utf-8")
    begin, end = ledger_gen.generated_region_bounds(committed)
    assert begin < end

    head = committed[:begin]
    tail = committed[end + len(GENERATED_END) :]
    verdict = registry_gate.evaluate_results(
        ("C1",),
        (ledger_gen.verify_claims.CheckResult(cid="C1", title="t", status="PASS", detail="d"),),
    )
    projected = ledger_gen.render(verdict, committed, titles={"C1": "synthetic check C1"})
    projected_begin, projected_end = ledger_gen.generated_region_bounds(projected)
    assert projected[:projected_begin] == head
    assert projected[projected_end + len(GENERATED_END) :] == tail


def test_the_registered_title_map_is_the_registration_list_verbatim() -> None:
    """R10.8: a row's subject is the title ``@register`` declared, not the returned one.

    Importing ``verify_claims`` executes no check - the registration list is built at
    import time - so this is free under I-0 and it pins the one place the subject
    column could quietly start coming from ``CheckResult.title``, which several checks
    shorten.
    """
    titles = ledger_gen.registered_titles()
    registration = {cid: title for cid, title, _fn in ledger_gen.verify_claims._CHECKS}

    assert titles == registration
    assert len(titles) == len(registration) == len(ledger_gen.verify_claims._CHECKS)
    assert all(title for title in titles.values())
