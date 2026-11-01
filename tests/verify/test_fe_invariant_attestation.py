"""Example-class facts for the FE-INV attestation gate (design E2.4, R8.7 / R12.4).

The universal property lives in the companion property test (design Property 35).
What is pinned here are the four concrete shapes the audit finding was made of:

* a listed test FILE existing is not an assertion running;
* an all-skipped run of that file is not a pass either;
* a missing reporter record is ``unavailable``, never a pass (I-7);
* the committed out-of-suite declaration cannot shadow an invariant that owns an
  executable suite file - which is what keeps ``FE-INV-056`` failing until the
  browser harness lands (task 11.1).

The gate lives at ``frontend/spec/check_fe_invariants.py``, outside any Python
package (its path is referenced by ``fe_invariants.yaml`` and
``.github/workflows/frontend.yml``), so it is loaded by path rather than imported.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_GATE_PATH = ROOT / "frontend" / "spec" / "check_fe_invariants.py"

_spec = importlib.util.spec_from_file_location("check_fe_invariants", _GATE_PATH)
assert _spec is not None and _spec.loader is not None
fe = importlib.util.module_from_spec(_spec)
# Registered before ``exec_module`` (importlib's documented pattern). The gate's models
# are Pydantic classes under ``from __future__ import annotations``, so Pydantic resolves
# a field annotation like ``TestStatus`` through ``sys.modules[cls.__module__]``. A module
# executed without being registered is not in that mapping, so on an interpreter that
# defers annotation evaluation (Python 3.14, PEP 649) every model in this file raises
# ``PydanticUserError: ... is not fully defined``. CI pins Python 3.11, where resolution
# happens at class-definition time and the omission is invisible - which is exactly why
# it went unnoticed. One line, correct on both.
sys.modules[_spec.name] = fe
_spec.loader.exec_module(fe)

SUITE_FILE = "frontend/tests/e2e/task-completion.jtbd.spec.ts"
REPORTED_FILE = "tests/e2e/task-completion.jtbd.spec.ts"  # as Playwright spells it


def _declaration(*entries: Any) -> Any:
    return fe.AttestationDeclaration(
        suite_extensions=(".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"),
        out_of_suite=tuple(entries),
    )


def _test(status: str, *, title: str = "resolve an escalation", file: str = REPORTED_FILE) -> Any:
    return fe.ExecutedTest(
        report="frontend/artifacts/test-reports/playwright.json",
        suite_file=file,
        title=title,
        status=status,
        tags=fe.tags_in(title),
    )


def _invariant(
    inv_id: str,
    *,
    status: str = "enforced",
    tests: tuple[str, ...] = (SUITE_FILE,),
) -> dict[str, Any]:
    return {
        "id": inv_id,
        "status": status,
        "implementations": ["frontend/src/app/Shell.tsx"],
        "tests": list(tests),
    }


def test_listed_file_without_a_reported_assertion_is_not_executed() -> None:
    """File existence is rejected: nothing ran, so nothing is attested (R8.7)."""
    attestation = fe.classify("FE-INV-056", "enforced", (SUITE_FILE,), (), _declaration())
    assert attestation.classification == "not_executed"
    assert not attestation.attested
    assert SUITE_FILE in attestation.detail


def test_all_skipped_run_is_rejected() -> None:
    """An all-skipped run of the listed file is rejected too (R8.7, I-7)."""
    attestation = fe.classify(
        "FE-INV-056", "enforced", (SUITE_FILE,), (_test("skipped"),), _declaration()
    )
    assert attestation.classification == "skipped_only"
    assert not attestation.attested
    assert attestation.skipped == ("resolve an escalation",)


def test_one_executed_non_skipped_assertion_attests() -> None:
    attestation = fe.classify(
        "FE-INV-056",
        "enforced",
        (SUITE_FILE,),
        (_test("skipped"), _test("passed", title="reaches the terminal outcome")),
        _declaration(),
    )
    assert attestation.classification == "attested"
    assert attestation.attested


def test_a_failed_assertion_is_a_violation_not_an_attestation() -> None:
    attestation = fe.classify(
        "FE-INV-056", "enforced", (SUITE_FILE,), (_test("failed"),), _declaration()
    )
    assert attestation.classification == "violated"
    assert not attestation.attested


def test_a_title_tag_attributes_a_test_from_any_file() -> None:
    """The design's stated attribution route: an FE-INV-### tag in the title."""
    tagged = _test(
        "passed",
        title="shows the audit note documenting FE-INV-033",
        file="src/surfaces/steering/__tests__/Steering.test.tsx",
    )
    attestation = fe.classify("FE-INV-033", "enforced", (), (tagged,), _declaration())
    assert attestation.classification == "attested"


def test_paths_match_needs_more_than_a_basename() -> None:
    assert fe.paths_match(SUITE_FILE, REPORTED_FILE)
    relative = "frontend/src/lib/__tests__/replay.test.ts"
    assert fe.paths_match(relative, str(ROOT / relative))
    assert not fe.paths_match("frontend/a/smoke.spec.ts", "other/b/smoke.spec.ts")
    assert not fe.paths_match("smoke.spec.ts", "smoke.spec.ts")


def test_missing_reporter_output_is_unavailable_never_a_pass() -> None:
    verdict = fe.evaluate_reports(
        (_invariant("FE-INV-056"),),
        _declaration(),
        (),
        (),
        ("frontend/artifacts/test-reports/vitest.json: no reporter output at this path",),
        (),
    )
    assert verdict.verdict == "unavailable"
    assert verdict.exit_code == fe.EXIT_UNAVAILABLE
    assert not verdict.passing


def test_a_run_in_which_nothing_executed_is_unavailable() -> None:
    verdict = fe.evaluate_reports(
        (_invariant("FE-INV-056"),),
        _declaration(),
        (_test("skipped"),),
        ("frontend/artifacts/test-reports/playwright.json",),
        (),
        (),
    )
    assert verdict.verdict == "unavailable"
    assert verdict.exit_code == fe.EXIT_UNAVAILABLE


def test_an_unattested_enforced_invariant_fails_the_gate() -> None:
    verdict = fe.evaluate_reports(
        (
            _invariant("FE-INV-056"),
            _invariant("FE-INV-033", tests=("frontend/src/x/__tests__/a.test.ts",)),
        ),
        _declaration(),
        (
            _test("skipped"),
            _test("passed", title="a", file="src/x/__tests__/a.test.ts"),
        ),
        ("frontend/artifacts/test-reports/playwright.json",),
        (),
        (),
    )
    assert verdict.verdict == "fail"
    assert verdict.exit_code == fe.EXIT_FAIL
    assert "FE-INV-056=skipped_only" in verdict.reason


def test_scheduled_invariants_owe_no_assertion_yet() -> None:
    verdict = fe.evaluate_reports(
        (
            _invariant("FE-INV-060", status="scheduled_p3"),
            _invariant("FE-INV-033", tests=("frontend/src/x/__tests__/a.test.ts",)),
        ),
        _declaration(),
        (_test("passed", title="a", file="src/x/__tests__/a.test.ts"),),
        ("frontend/artifacts/test-reports/vitest.json",),
        (),
        (),
    )
    assert verdict.verdict == "pass"
    assert verdict.by_class("not_enforced")[0].invariant_id == "FE-INV-060"


def test_declaration_cannot_shadow_a_suite_backed_invariant() -> None:
    """The rule that makes "allowlist FE-INV-056 away" mechanically impossible."""
    entry = fe.OutOfSuiteEntry(
        invariant_id="FE-INV-056",
        workflow=".github/workflows/frontend.yml",
        job="e2e-harness",
        rationale="r",
        dated="2026-06-17",
        removal_condition="c",
    )
    declaration = _declaration(entry)
    errors = fe.declaration_hygiene(
        declaration, (_invariant("FE-INV-056"),), declaration.suite_extensions
    )
    assert any("cannot be declared out-of-suite" in error for error in errors)


def test_declaration_rejects_a_job_that_does_not_exist() -> None:
    entry = fe.OutOfSuiteEntry(
        invariant_id="FE-INV-031",
        workflow=".github/workflows/frontend.yml",
        job="a11y",  # frontend.yml defines no a11y job
        rationale="r",
        dated="2026-06-17",
        removal_condition="c",
    )
    declaration = _declaration(entry)
    errors = fe.declaration_hygiene(
        declaration,
        (_invariant("FE-INV-031", tests=(".github/workflows/frontend.yml",)),),
        declaration.suite_extensions,
    )
    assert any("defines no such job" in error for error in errors)


def test_committed_declaration_resolves_and_never_shadows_fe_inv_056() -> None:
    """The committed declaration must name real jobs and leave FE-INV-056 alone."""
    invariants = fe.load_invariants(fe.SPEC)
    declaration = fe.load_declaration(fe.DECLARATION)
    assert declaration.entry_for("FE-INV-056") is None
    assert fe.declaration_hygiene(declaration, invariants, declaration.suite_extensions) == ()


def test_playwright_runtime_skip_collapses_to_skipped() -> None:
    """`test.skip(true, ...)` inside the body is a skip, whatever the file says."""
    payload = {
        "suites": [
            {
                "title": "tests/e2e/task-completion.jtbd.spec.ts",
                "file": "tests/e2e/task-completion.jtbd.spec.ts",
                "specs": [
                    {
                        "title": "resolve an escalation reaches the correct terminal outcome",
                        "file": "tests/e2e/task-completion.jtbd.spec.ts",
                        "tests": [{"status": "skipped", "results": [{"status": "skipped"}]}],
                    }
                ],
            }
        ]
    }
    parsed = fe.parse_report(payload, "playwright.json")
    assert len(parsed) == 1
    assert parsed[0].status == "skipped"
    assert parsed[0].executed is False


def test_vitest_report_is_normalised() -> None:
    payload = {
        "testResults": [
            {
                "name": str(ROOT / "frontend/src/lib/__tests__/replay.test.ts"),
                "assertionResults": [
                    {
                        "ancestorTitles": ["replay"],
                        "title": "gates per-phase visibility",
                        "fullName": "replay > gates per-phase visibility",
                        "status": "passed",
                    },
                    {"ancestorTitles": [], "title": "todo case", "status": "todo"},
                ],
            }
        ]
    }
    parsed = fe.parse_report(payload, "vitest.json")
    assert [t.status for t in parsed] == ["passed", "skipped"]


def test_an_unknown_reporter_shape_raises_rather_than_reading_as_empty() -> None:
    """An unrecognised reporter file must not read as "nothing to attest"."""
    with pytest.raises(fe.ReportFormatError):
        fe.parse_report({"results": []}, "mystery.json")
