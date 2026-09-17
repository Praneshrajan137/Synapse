"""Property-based test for coverage floor non-vacuity (design E1.8, CF-3).

Feature: purpose-achievement-audit, Property 7: Coverage floors are non-vacuous and
named on failure

    *For any* (coverage report, floors file) pair, the gate exits non-zero naming the
    package, its measured value, and its floor whenever a measured value is below its
    floor; a gated package whose floor is zero and whose ``measured_at`` is recorded
    also fails naming it; and a gated package whose floor is zero with no
    ``measured_at`` is reported ``SKIP - unmeasured``, never ``PASS``.

Why a property and not examples. The audit finding is not "one floor is wrong", it is
that the floors table *as a shape* can satisfy its gate while asserting nothing: nine of
twelve packages carry ``line: 0.0``, and C28 only checks ``floor >= 0``. A fixed example
pins the nine packages that happened to be zero on the day the audit ran. What has to
hold is a statement about the whole (floors, measured) space: every row lands on exactly
one verdict, the verdict is decided by the row, and no row reaches ``PASS`` without a
measurement above a positive floor.

Ground truth. ``tests/verify/strategies.py`` derives ``below_floor``, ``vacuous`` and
``unmeasured`` from the generated case itself. The gate reads only the rendered
``coverage.xml`` and floors YAML, so agreement between the two is the gate
rediscovering a partition it was not handed.

Encoding the measured number exactly. Cobertura carries no percentage the gate trusts -
it re-derives ``100 * (lines_covered + branches_covered) / (lines_total +
branches_total)``. One ``<line hits="0" condition-coverage="... (c/9999)">`` therefore
gives a denominator of ``1 + 9999`` and a numerator of ``c``, so a two-decimal target
``m`` is encoded bit-for-bit by ``c = round(m * 100)`` in a single XML element. That
keeps every example a few hundred bytes instead of ten thousand ``<line>`` nodes, which
matters because this file is the only thing standing in for a coverage run: a real
repo-wide ``pytest --cov`` is a CI-only workload under I-0 and is never run here. Each
example writes its report, its floors file and its source tree into a
``tempfile.TemporaryDirectory`` and removes them on the way out; both scripts already
take ``--xml`` / ``--floors`` (and ``evaluate(xml_path, floors_path)``), so no module
global is patched and no root parameter had to be added.

Subject: ``scripts/coverage_per_package.py --require-measured-floors`` and
``scripts/coverage_ratchet.py --apply`` (task 4.1). The ratchet half is what makes R7.9
mechanically visible: the provenance it writes is precisely what turns an honest
``SKIP-UNMEASURED`` into either a real floor or a named vacuity failure.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 7.1, 7.2, 7.9**
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import sys
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts import coverage_per_package as cpp
from scripts import coverage_ratchet as ratchet
from tests.verify.strategies import CoverageCase, FloorEntry, coverage_cases

#: One recorded measurement timestamp. The value is immaterial; that it is *recorded* is
#: the whole of R7.2's condition.
RECORDED_AT: Final[str] = "2026-05-30T09:14:00Z"

#: Branch denominator used to encode a two-decimal percentage in one XML element.
#: ``1`` line + ``BRANCH_TOTAL`` branches = 10000, so ``c/100`` is exact.
BRANCH_TOTAL: Final[int] = 9999
LINE_DENOMINATOR: Final[int] = 1 + BRANCH_TOTAL

#: The module name every generated package is given. Deliberately absent from the real
#: tree so the gate's source-root resolution can never bind a generated path to a
#: committed file.
GENERATED_MODULE: Final[str] = "generated_module.py"

#: The full status vocabulary. Totality is asserted against this set: a verdict outside
#: it would mean the gate has a state the property does not describe.
STATUSES: Final[frozenset[str]] = frozenset(
    {
        cpp.STATUS_PASS,
        cpp.STATUS_FAIL,
        cpp.STATUS_UNMEASURED,
        cpp.STATUS_VACUOUS,
        cpp.STATUS_SKIP_UNMEASURED,
    }
)

#: Statuses that are not a pass. I-7: a SKIP is not a PASS, and neither is "no number".
NON_PASSING: Final[frozenset[str]] = STATUSES - {cpp.STATUS_PASS}


# ---------------------------------------------------------------------------
# Rendering a generated case into a throwaway tree
# ---------------------------------------------------------------------------


def _branch_hits(measured_pct: float) -> int:
    """The covered-branch count that encodes *measured_pct* exactly."""
    return round(measured_pct * 100)


def write_report(root: Path, measured: Mapping[str, float]) -> Path:
    """Write a Cobertura report under *root* encoding each package's measured value.

    The source root is the temporary directory and the module files are created, so the
    gate's existence-based source resolution runs the same branch it runs in CI rather
    than the synthetic fallback.
    """
    parts: list[str] = [
        '<?xml version="1.0" ?>',
        '<coverage version="7.0" line-rate="0.5" branch-rate="0.5">',
        "  <sources>",
        f"    <source>{root.as_posix()}</source>",
        "  </sources>",
        "  <packages>",
    ]
    for package, value in sorted(measured.items()):
        filename = f"{package}/{GENERATED_MODULE}"
        module = root / filename
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text("# generated for a coverage report\n", encoding="utf-8")
        condition = f"{value:.2f}% ({_branch_hits(value)}/{BRANCH_TOTAL})"
        parts += [
            f'    <package name="{package.replace("/", ".")}">',
            "      <classes>",
            f'        <class name="{GENERATED_MODULE}" filename="{filename}">',
            "          <lines>",
            f'            <line number="1" hits="0" branch="true" '
            f'condition-coverage="{condition}"/>',
            "          </lines>",
            "        </class>",
            "      </classes>",
            "    </package>",
        ]
    parts += ["  </packages>", "</coverage>"]
    path = root / "coverage.xml"
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


@contextlib.contextmanager
def rendered(case: CoverageCase) -> Iterator[tuple[Path, Path]]:
    """Yield ``(xml_path, floors_path)`` for *case* inside a temporary directory."""
    with tempfile.TemporaryDirectory(prefix="coverage-floors-") as tmp:
        root = Path(tmp)
        floors_path = root / "coverage-floors.yaml"
        floors_path.write_text(case.floors_yaml(), encoding="utf-8")
        yield write_report(root, case.measured), floors_path


def results_of(
    case: CoverageCase, *, require_measured_floors: bool
) -> dict[str, cpp.PackageResult]:
    """Evaluate *case* and key the results by package."""
    with rendered(case) as (xml_path, floors_path):
        results = cpp.evaluate(
            xml_path, floors_path, require_measured_floors=require_measured_floors
        )
    return {result.package: result for result in results}


def run_cli(
    case: CoverageCase, *, require_measured_floors: bool, as_json: bool = False
) -> tuple[int, str]:
    """Run the gate's ``main()`` in-process over *case*, returning (exit code, stdout).

    In-process rather than as a subprocess: the exit code and the naming obligation are
    both observable here, and I-0 gets no extra process out of it.
    """
    with rendered(case) as (xml_path, floors_path):
        argv = [
            "coverage_per_package.py",
            "--xml",
            str(xml_path),
            "--floors",
            str(floors_path),
        ]
        if require_measured_floors:
            argv.append("--require-measured-floors")
        if as_json:
            argv.append("--json")
        buffer = io.StringIO()
        original = sys.argv
        sys.argv = argv
        try:
            with contextlib.redirect_stdout(buffer):
                code = cpp.main()
        finally:
            sys.argv = original
    return code, buffer.getvalue()


# ---------------------------------------------------------------------------
# The independent recompute
# ---------------------------------------------------------------------------


def expected_status(case: CoverageCase, package: str, *, require_measured_floors: bool) -> str:
    """The verdict E1.8 mandates for one row, recomputed from the generated case.

    Written out rather than imported from the gate, so the test compares two
    implementations of the same rule. The zero-floor branches are keyed off the
    strategy's own ``vacuous`` / ``unmeasured`` partitions.
    """
    entry = case.floors[package]
    if require_measured_floors and entry.line == 0.0:
        return cpp.STATUS_VACUOUS if package in case.vacuous else cpp.STATUS_SKIP_UNMEASURED
    if package not in case.measured:
        return cpp.STATUS_UNMEASURED
    return cpp.STATUS_FAIL if package in case.below_floor else cpp.STATUS_PASS


def single_case(
    package: str,
    *,
    floor: float,
    measured: float | None,
    measured_at: str | None,
    source_run: str | None = None,
) -> CoverageCase:
    """A one-row case, for the three verdicts that need to be reachable every example."""
    return CoverageCase(
        floors={
            package: FloorEntry(
                line=floor, target=84.0, measured_at=measured_at, source_run=source_run
            )
        },
        measured={} if measured is None else {package: measured},
    )


def sole_package(case: CoverageCase) -> str:
    """The package name of a single-row generated case."""
    (package,) = case.floors
    return package


# ---------------------------------------------------------------------------
# Totality over the generated (floors, measured) space
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 7: Coverage floors are non-vacuous and
# named on failure
@given(case=coverage_cases(), require_measured_floors=st.booleans())
def test_the_classification_is_total_over_the_generated_floors_and_reports(
    case: CoverageCase, require_measured_floors: bool
) -> None:
    """R7.1, R7.2, R7.9: every gated row gets exactly one verdict, decided by the row.

    Totality first, because a gate that quietly returned ``PASS`` for anything it could
    not classify would satisfy every naming assertion below while asserting nothing -
    which is the exact failure mode the audit found in C28.
    """
    results = results_of(case, require_measured_floors=require_measured_floors)

    # Exactly the gated rows, once each, each on a known verdict.
    assert set(results) == set(case.floors)
    assert {result.status for result in results.values()} <= STATUSES

    for package, result in results.items():
        assert result.status == expected_status(
            case, package, require_measured_floors=require_measured_floors
        )
        # The encoder is faithful: the gate re-derived the number the case declared.
        if package in case.measured:
            assert result.measured_combined_pct == round(case.measured[package], 2)
        else:
            # No number for this package. Never a pass, whatever the floor says.
            assert result.status in NON_PASSING
        # Provenance survives the YAML round-trip, so the R7.2 branch is decidable.
        assert (result.measured_at is None) is (case.floors[package].measured_at is None)

    if require_measured_floors:
        failing = {p for p, r in results.items() if r.status in cpp.FAILING_STATUSES}
        assert failing == {p for p in case.below_floor if case.floors[p].line > 0.0} | set(
            case.vacuous
        )
        assert {
            p for p, r in results.items() if r.status == cpp.STATUS_SKIP_UNMEASURED
        } == set(case.unmeasured)
        # A SKIP is not a PASS (I-7) and does not become one by being tallied.
        assert all(results[p].status in NON_PASSING for p in case.unmeasured)

    code, output = run_cli(case, require_measured_floors=require_measured_floors)
    expected_fail = any(r.status in cpp.FAILING_STATUSES for r in results.values())
    assert code == (1 if expected_fail else 0)
    # Every non-passing row is named with its verdict in the findings section, so the
    # report says which package and why rather than only that something was red.
    for package, result in results.items():
        if result.status != cpp.STATUS_PASS:
            assert f"{result.status}: {package}" in output


# ---------------------------------------------------------------------------
# R7.1 - below floor fails naming package, measured value, and floor
# ---------------------------------------------------------------------------


@given(
    case=coverage_cases(max_packages=1),
    floor=st.floats(min_value=10.0, max_value=95.0).map(lambda value: round(value, 1)),
    gap=st.floats(min_value=0.1, max_value=9.0).map(lambda value: round(value, 2)),
    require_measured_floors=st.booleans(),
)
def test_a_below_floor_package_fails_naming_it_its_measurement_and_its_floor(
    case: CoverageCase, floor: float, gap: float, require_measured_floors: bool
) -> None:
    """R7.1: the gate exits non-zero and names all three values it compared.

    Naming is the requirement, not a nicety: the audit's complaint about the aggregate
    ``--cov-fail-under`` was that a red build said nothing about *which* package
    regressed. The flag is varied because R7.1 holds with or without it - non-vacuity
    enforcement must not be what makes a real regression bite.
    """
    package = sole_package(case)
    measured = round(floor - gap, 2)
    below = single_case(package, floor=floor, measured=measured, measured_at=None)

    assert below.below_floor == (package,)
    results = results_of(below, require_measured_floors=require_measured_floors)
    assert results[package].status == cpp.STATUS_FAIL
    assert results[package].measured_combined_pct == measured

    code, output = run_cli(below, require_measured_floors=require_measured_floors)
    assert code == 1
    assert package in output
    assert f"{measured:.2f}" in output
    assert f"{floor:.1f}" in output

    # The converse: the same package measured at its floor is a pass, so the failure
    # above is the comparison biting rather than the row being rejected on sight.
    at_floor = single_case(package, floor=floor, measured=floor, measured_at=None)
    assert at_floor.below_floor == ()
    assert (
        results_of(at_floor, require_measured_floors=require_measured_floors)[package].status
        == cpp.STATUS_PASS
    )


# ---------------------------------------------------------------------------
# R7.2 - a measured zero floor is vacuous and fails naming the package
# ---------------------------------------------------------------------------


@given(
    case=coverage_cases(max_packages=1),
    measured=st.floats(min_value=0.0, max_value=100.0).map(lambda value: round(value, 2)),
    source_run=st.integers(min_value=1, max_value=9_999).map(lambda run: f"gh-run-{run}"),
)
def test_a_zero_floor_with_a_recorded_measurement_fails_naming_the_package(
    case: CoverageCase, measured: float, source_run: str
) -> None:
    """R7.2: a floor of zero beside a recorded measurement is a named failure.

    This is the audit's central finding for R7 - a gate that runs and asserts a floor of
    zero. The measured value is drawn across the whole range on purpose: no measurement,
    however high, may excuse the zero floor, because the floor is what the *next* commit
    is held to. The no-flag branch documents the pre-4.1 behaviour: the same row passes,
    which is why the flag exists.
    """
    package = sole_package(case)
    vacuous = single_case(
        package,
        floor=0.0,
        measured=measured,
        measured_at=RECORDED_AT,
        source_run=source_run,
    )
    assert vacuous.vacuous == (package,)
    assert vacuous.unmeasured == ()

    result = results_of(vacuous, require_measured_floors=True)[package]
    assert result.status == cpp.STATUS_VACUOUS
    assert result.status in cpp.FAILING_STATUSES
    assert result.status in NON_PASSING

    code, output = run_cli(vacuous, require_measured_floors=True)
    assert code == 1
    assert f"{cpp.STATUS_VACUOUS}: {package}" in output
    assert RECORDED_AT in output
    assert source_run in output

    _, payload = run_cli(vacuous, require_measured_floors=True, as_json=True)
    assert json.loads(payload)["vacuous_floors"] == [package]

    # Without the flag the vacuous floor still passes - the untouched CI step (CF-3).
    assert results_of(vacuous, require_measured_floors=False)[package].status == cpp.STATUS_PASS


# ---------------------------------------------------------------------------
# R7.2 / CF-3 - an unmeasured zero floor is a SKIP, never a PASS
# ---------------------------------------------------------------------------


@given(
    case=coverage_cases(max_packages=1),
    measured=st.one_of(
        st.none(),
        st.floats(min_value=0.0, max_value=100.0).map(lambda value: round(value, 2)),
    ),
)
def test_an_unmeasured_zero_floor_is_reported_skip_and_is_never_a_pass(
    case: CoverageCase, measured: float | None
) -> None:
    """R7.2, CF-3, I-7: no run has measured it, so there is no floor to enforce.

    The honest state for the nine zero floors before the seeding run lands. It must not
    fail (that would red CI for work I-0 forbids doing locally) and it must not pass
    (absence of proof is never a pass). ``SKIP-UNMEASURED`` is the only remaining
    verdict, and it has to name the package to be actionable.
    """
    package = sole_package(case)
    unmeasured = single_case(package, floor=0.0, measured=measured, measured_at=None)
    assert unmeasured.unmeasured == (package,)
    assert unmeasured.vacuous == ()

    result = results_of(unmeasured, require_measured_floors=True)[package]
    assert result.status == cpp.STATUS_SKIP_UNMEASURED
    assert result.status not in cpp.FAILING_STATUSES
    assert result.status in NON_PASSING
    assert result.status != cpp.STATUS_PASS

    code, output = run_cli(unmeasured, require_measured_floors=True)
    assert code == 0
    assert package in output
    assert cpp.STATUS_SKIP_UNMEASURED in output
    assert "not a PASS" in output

    _, payload = run_cli(unmeasured, require_measured_floors=True, as_json=True)
    document = json.loads(payload)
    assert document["unmeasured_floors"] == [package]
    assert document["vacuous_floors"] == []


@given(case=coverage_cases(max_packages=1), floor=st.floats(min_value=1.0, max_value=95.0))
def test_a_package_absent_from_the_report_never_reads_as_a_pass(
    case: CoverageCase, floor: float
) -> None:
    """A gated package the runner produced no number for is UNMEASURED, not PASS.

    The silent-hole case: floors name a package, the coverage run never reached it. Under
    a gate that treated "no rows" as full coverage this would be the cheapest way to
    launder a floor.
    """
    package = sole_package(case)
    absent = single_case(package, floor=round(floor, 1), measured=None, measured_at=None)

    for require_measured_floors in (False, True):
        result = results_of(absent, require_measured_floors=require_measured_floors)[package]
        assert result.status == cpp.STATUS_UNMEASURED
        assert result.status in NON_PASSING


# ---------------------------------------------------------------------------
# R7.9 - the ratchet writes the provenance that makes the floor decidable
# ---------------------------------------------------------------------------


@given(
    case=coverage_cases(max_packages=1),
    measured=st.floats(min_value=20.0, max_value=95.0).map(lambda value: round(value, 2)),
    source_run=st.integers(min_value=1, max_value=9_999).map(lambda run: f"gh-run-{run}"),
)
def test_the_ratchet_writes_the_provenance_that_decides_the_zero_floor(
    case: CoverageCase, measured: float, source_run: str
) -> None:
    """R7.9: the first run that measures a package writes its floor, provenance and all.

    Both halves of the criterion, in one pass over the same generated row. The ratchet's
    ``--apply`` edit turns an honest ``SKIP-UNMEASURED`` into an enforced floor; and if
    the floor is left at zero after that run measured the package, the gate must FAIL
    naming it. Without the second half the provenance write would be the cheapest way to
    keep a zero floor forever.
    """
    package = sole_package(case)
    unmeasured = single_case(package, floor=0.0, measured=measured, measured_at=None)
    provenance = ratchet.resolve_provenance(source_run=source_run)

    with rendered(unmeasured) as (xml_path, floors_path):
        # Before: no floor to enforce, so the honest verdict is a SKIP.
        assert (
            cpp.evaluate(xml_path, floors_path, require_measured_floors=True)[0].status
            == cpp.STATUS_SKIP_UNMEASURED
        )

        proposals = ratchet.propose_bumps(xml_path, floors_path, margin=2.0)
        assert [name for name, _old, _new in proposals] == [package]
        _, old_floor, new_floor = proposals[0]
        assert old_floor == 0.0
        assert 0.0 < new_floor <= measured

        text = floors_path.read_text(encoding="utf-8")
        floors_path.write_text(
            ratchet.rewrite_floor_entry(text, package, new_floor, provenance),
            encoding="utf-8",
        )
        bumped = cpp.evaluate(xml_path, floors_path, require_measured_floors=True)[0]

        # After: a real floor, attributed to the run that measured it.
        assert bumped.floor == new_floor
        assert bumped.measured_at == provenance.measured_at
        assert bumped.source_run == provenance.source_run
        assert bumped.status == cpp.STATUS_PASS

        # The other half of R7.9: still zero after a measuring run is a named failure.
        floors_path.write_text(
            ratchet.rewrite_floor_entry(text, package, 0.0, provenance), encoding="utf-8"
        )
        still_zero = cpp.evaluate(xml_path, floors_path, require_measured_floors=True)[0]

    assert still_zero.floor == 0.0
    assert still_zero.package == package
    assert still_zero.status == cpp.STATUS_VACUOUS
    assert still_zero.status in cpp.FAILING_STATUSES
    assert provenance.measured_at in still_zero.detail
    assert provenance.source_run in still_zero.detail


def test_the_committed_floors_table_is_read_the_same_way() -> None:
    """The committed floors file parses under both provenance readings.

    A static read of ``infrastructure/quality/coverage-floors.yaml`` - no coverage run
    (I-0). The committed table is expected to hold zero floors today, and CF-3 says so:
    what must hold before the seeding run is that every one of them reads as
    ``measured_at: null``, i.e. as an honest SKIP rather than as a vacuous pass waiting
    to be discovered.
    """
    floors_path = Path(cpp.ROOT) / "infrastructure" / "quality" / "coverage-floors.yaml"
    assert floors_path.is_file()

    document = yaml.safe_load(floors_path.read_text(encoding="utf-8"))
    packages = document.get("packages", {})
    assert packages

    for package, config in packages.items():
        if float(config.get("line", 0.0)) != 0.0:
            continue
        recorded = config.get("measured_at")
        # Read exactly as the gate reads it: a blank string records no measurement, and
        # PyYAML resolves an unquoted timestamp to a datetime.
        assert recorded is None or not str(recorded).strip(), (
            f"{package} carries a zero floor with measured_at={recorded!r}; that is the "
            "R7.2 vacuity the gate must FAIL on, not a committable state"
        )


@given(
    case=coverage_cases(max_packages=1),
    floor=st.floats(min_value=1.0, max_value=80.0).map(lambda value: round(value, 1)),
)
def test_dataclass_replacement_of_a_floor_moves_the_verdict_and_nothing_else(
    case: CoverageCase, floor: float
) -> None:
    """A positive floor is enforced the moment it is recorded, with no other change.

    The minimal pair behind R7.2: the same row, the same measurement, the same
    provenance - only the floor moves off zero. If the verdict did not move with it, the
    floor would not be the thing being enforced.
    """
    package = sole_package(case)
    entry = FloorEntry(
        line=0.0, target=84.0, measured_at="2026-05-30T09:14:00Z", source_run="gh-run-7"
    )
    measured = round(floor / 2.0, 2)

    vacuous = CoverageCase(floors={package: entry}, measured={package: measured})
    enforced = CoverageCase(
        floors={package: dataclasses.replace(entry, line=floor)},
        measured={package: measured},
    )

    assert results_of(vacuous, require_measured_floors=True)[package].status == (
        cpp.STATUS_VACUOUS
    )
    assert results_of(enforced, require_measured_floors=True)[package].status == cpp.STATUS_FAIL
