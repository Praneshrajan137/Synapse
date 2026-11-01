"""Example-class facts for the FE-INV attestation gate (design E2.4, R8.7 / R12.4).

The universal property lives in the companion property test (design Property 35).
What is pinned here are the four concrete shapes the audit finding was made of:

* a listed test FILE existing is not an assertion running;
* an all-skipped run of that file is not a pass either;
* a missing reporter record is ``unavailable``, never a pass (I-7);
* the committed out-of-suite declaration cannot shadow an invariant that owns an
  executable suite file - which is what keeps ``FE-INV-056`` failing until the
  browser harness lands (task 11.1).

And the shape finding 90 measured on Frontend CI. Playwright writes every ``file``
relative to the record's own ``config.rootDir``, which is ``<checkout>/frontend/tests/e2e``
for both committed configs, so a top-level spec is the one-segment ``smoke.spec.ts``. The
gate resolves that spelling against ``rootDir`` before attributing it, and refuses a record
with no usable ``rootDir``. The Playwright fixtures below are spelled the way Playwright
writes them. The ``tests/e2e/...`` spelling they used before is one Playwright never emits,
which is why these tests passed while CI failed.

The gate lives at ``frontend/spec/check_fe_invariants.py``, outside any Python
package (its path is referenced by ``fe_invariants.yaml`` and
``.github/workflows/frontend.yml``), so it is loaded by path rather than imported.
"""

from __future__ import annotations

import importlib.util
import json
import posixpath
import re
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

#: Where both committed Playwright configs root their JSON record. Playwright sets
#: ``config.rootDir`` to the top-level ``testDir`` resolved against the config's directory,
#: and both configs set ``testDir: "./tests/e2e"``. Pinned against the configs by
#: ``test_both_playwright_configs_root_their_records_at_the_e2e_tree``.
E2E_DIR = "frontend/tests/e2e"
#: A GitHub-hosted runner's workspace for this repository (``/home/runner/work/<repo>/<repo>``).
CI_CHECKOUT = "/home/runner/work/Synapse/Synapse"
#: ``config.rootDir`` as Playwright writes it on that runner.
CI_ROOT_DIR = f"{CI_CHECKOUT}/{E2E_DIR}"

PLAYWRIGHT_REPORT = "frontend/artifacts/test-reports/playwright.json"
VITEST_REPORT = "frontend/artifacts/test-reports/vitest.json"

SUITE_FILE = f"{E2E_DIR}/task-completion.jtbd.spec.ts"
REPORTED_FILE = "task-completion.jtbd.spec.ts"  # as Playwright spells it: relative to rootDir
RESOLVED_FILE = f"{CI_ROOT_DIR}/{REPORTED_FILE}"  # what the gate resolves it to on the runner

SMOKE_SPEC = f"{E2E_DIR}/smoke.spec.ts"
VISUAL_SPEC = f"{E2E_DIR}/visual/visual-regression.spec.ts"

#: A unit test as the registry lists it, and as Vitest's JSON reporter names it (absolute).
UNIT_TEST = "frontend/src/x/__tests__/a.test.ts"
UNIT_TEST_NAME = f"{CI_CHECKOUT}/{UNIT_TEST}"

#: The two committed Playwright configs, each of which roots its own run record.
PLAYWRIGHT_CONFIGS = ("frontend/playwright.config.ts", "frontend/playwright.harness.config.ts")

#: A top-level ``testDir:`` assignment in a Playwright config, single- or double-quoted.
_TEST_DIR_RE = re.compile(r"""^\s*testDir:\s*["']([^"']+)["']""", re.MULTILINE)

#: Collapsed case status -> (``tests[].status``, ``results[].status``) as Playwright writes them.
_PLAYWRIGHT_STATUS: dict[str, tuple[str, str]] = {
    "passed": ("expected", "passed"),
    "failed": ("unexpected", "failed"),
    "skipped": ("skipped", "skipped"),
}


def _declaration(*entries: Any) -> Any:
    return fe.AttestationDeclaration(
        suite_extensions=(".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"),
        out_of_suite=tuple(entries),
    )


def _test(
    status: str,
    *,
    title: str = "resolve an escalation",
    file: str = RESOLVED_FILE,
    report: str = PLAYWRIGHT_REPORT,
) -> Any:
    """One normalised case, its file spelled as the gate's parsers produce it.

    A Playwright case carries its ``file`` resolved against ``config.rootDir``; a Vitest
    case carries the absolute ``name`` Vitest wrote.
    """
    return fe.ExecutedTest(
        report=report,
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


def _playwright_record(
    root_dir: str,
    reported: str,
    *,
    title: str = "reaches the terminal outcome",
    status: str = "passed",
    describe: str | None = None,
) -> dict[str, Any]:
    """One spec in Playwright's JSON reporter shape, spelled as Playwright 1.60 writes it.

    ``config.rootDir`` is the resolved ``testDir``. The file suite's ``title`` and every
    ``file`` are ``path.relative(rootDir, spec)``, and a ``describe`` block is a nested
    suite that carries the same ``file``.
    """
    test_status, result_status = _PLAYWRIGHT_STATUS[status]
    spec = {
        "title": title,
        "file": reported,
        "tests": [{"status": test_status, "results": [{"status": result_status}]}],
    }
    file_suite: dict[str, Any] = {"title": reported, "file": reported, "specs": []}
    if describe is None:
        file_suite["specs"] = [spec]
    else:
        file_suite["suites"] = [{"title": describe, "file": reported, "specs": [spec]}]
    return {"config": {"rootDir": root_dir}, "suites": [file_suite]}


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
        file=f"{CI_CHECKOUT}/frontend/src/surfaces/steering/__tests__/Steering.test.tsx",
        report=VITEST_REPORT,
    )
    attestation = fe.classify("FE-INV-033", "enforced", (), (tagged,), _declaration())
    assert attestation.classification == "attested"


def test_paths_match_needs_more_than_a_basename() -> None:
    """Two shared trailing segments are required, so a bare basename attributes nothing.

    The second assertion is why the gate resolves Playwright's spelling before matching:
    the unresolved ``task-completion.jtbd.spec.ts`` shares one segment with the registry
    path and is refused, which is how FE-INV-056 read ``not_executed`` while its cases were
    in the record (finding 90). Wrong if the matcher accepted one segment (two unrelated
    ``smoke.spec.ts`` files would then collide) or refused the resolved absolute spelling.
    """
    assert fe.paths_match(SUITE_FILE, RESOLVED_FILE)
    assert not fe.paths_match(SUITE_FILE, REPORTED_FILE)
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
        (f"{VITEST_REPORT}: no reporter output at this path",),
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
        (PLAYWRIGHT_REPORT,),
        (),
        (),
    )
    assert verdict.verdict == "unavailable"
    assert verdict.exit_code == fe.EXIT_UNAVAILABLE


def test_an_unattested_enforced_invariant_fails_the_gate() -> None:
    verdict = fe.evaluate_reports(
        (
            _invariant("FE-INV-056"),
            _invariant("FE-INV-033", tests=(UNIT_TEST,)),
        ),
        _declaration(),
        (
            _test("skipped"),
            _test("passed", title="a", file=UNIT_TEST_NAME, report=VITEST_REPORT),
        ),
        (PLAYWRIGHT_REPORT, VITEST_REPORT),
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
            _invariant("FE-INV-033", tests=(UNIT_TEST,)),
        ),
        _declaration(),
        (_test("passed", title="a", file=UNIT_TEST_NAME, report=VITEST_REPORT),),
        (VITEST_REPORT,),
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
    """`test.skip(true, ...)` inside the body is a skip, whatever the file says.

    The record is spelled as the harness job's is, so the skip is attributed to FE-INV-056
    and reads ``skipped_only``: an observed skip, not ``not_executed``. Wrong if the skip
    collapsed to a pass, or if the spelling left the case unattributed (finding 90's
    ``not_executed``).
    """
    payload = _playwright_record(
        CI_ROOT_DIR,
        REPORTED_FILE,
        title="resolve an escalation reaches the correct terminal outcome",
        status="skipped",
    )
    parsed = fe.parse_report(payload, PLAYWRIGHT_REPORT)
    assert len(parsed) == 1
    assert parsed[0].status == "skipped"
    assert parsed[0].executed is False
    attestation = fe.classify("FE-INV-056", "enforced", (SUITE_FILE,), parsed, _declaration())
    assert attestation.classification == "skipped_only"


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


def test_a_top_level_playwright_spec_attributes_to_its_registry_path() -> None:
    """A one-segment spec under ``config.rootDir`` attributes to its repo-relative path.

    The record is spelled as the e2e job's is: ``rootDir`` at the e2e tree, the spec as
    ``smoke.spec.ts``. Every committed invariant listing ``frontend/tests/e2e/smoke.spec.ts``
    is attested by the case that ran, and the record's listing names the same resolved file,
    so neither the FE-INV clause nor a declared-suite verdict can miss it on spelling. Wrong
    if the gate compared the unresolved spelling (one shared segment, refused by the
    two-segment rule: the ``not_executed`` FE-INV-010 and FE-INV-011 lines of Frontend CI
    run 41298456048), or resolved it against any base but the record's own ``rootDir``.
    """
    listing = tuple(
        inv for inv in fe.load_invariants(fe.SPEC) if SMOKE_SPEC in (inv.get("tests") or ())
    )
    assert listing, f"no committed invariant lists {SMOKE_SPEC}, so this test has no subject"

    payload = _playwright_record(
        CI_ROOT_DIR, "smoke.spec.ts", title="route / renders and is a11y-clean @a11y"
    )
    parsed = fe.parse_report(payload, PLAYWRIGHT_REPORT)

    resolved = f"{CI_CHECKOUT}/{SMOKE_SPEC}"
    assert [case.suite_file for case in parsed] == [resolved]
    assert fe.recorded_suite_files(payload) == (resolved,)
    for inv in listing:
        listed = tuple(str(path) for path in inv.get("tests") or ())
        attestation = fe.classify(str(inv.get("id")), "enforced", listed, parsed, _declaration())
        assert attestation.classification == "attested", f"{inv.get('id')}: {attestation.detail}"


@pytest.mark.parametrize(
    ("root_dir", "reported", "resolved"),
    [
        pytest.param(
            CI_ROOT_DIR,
            "visual/visual-regression.spec.ts",
            f"{CI_CHECKOUT}/{VISUAL_SPEC}",
            id="runner",
        ),
        pytest.param(
            "C:/dev/synapse/frontend/tests/e2e",
            "visual/visual-regression.spec.ts",
            f"C:/dev/synapse/{VISUAL_SPEC}",
            id="windows-checkout",
        ),
        pytest.param(
            "C:\\dev\\synapse\\frontend\\tests\\e2e",
            "visual\\visual-regression.spec.ts",
            f"C:/dev/synapse/{VISUAL_SPEC}",
            id="backslash-separators",
        ),
        pytest.param(
            f"{CI_ROOT_DIR}/a11y",
            "../visual/visual-regression.spec.ts",
            f"{CI_CHECKOUT}/{VISUAL_SPEC}",
            id="spec-outside-root-dir",
        ),
        pytest.param(
            "C:/dev/synapse/frontend/tests/e2e",
            f"D:/mirror/{VISUAL_SPEC}",
            f"D:/mirror/{VISUAL_SPEC}",
            id="spec-on-another-drive",
        ),
    ],
)
def test_a_nested_playwright_spec_resolves_against_root_dir(
    root_dir: str, reported: str, resolved: str
) -> None:
    """``visual/visual-regression.spec.ts`` resolves under ``rootDir`` and attests FE-INV-067.

    The runner row is the visual job's record. The others pin the rest of the resolution
    rule: Playwright writes ``rootDir`` with forward slashes on Windows too, a backslash is
    a separator as it is in the matcher, ``path.relative`` climbs with ``..`` for a spec
    outside ``rootDir`` (left unresolved, that segment would block the match), and it
    returns the spec's own absolute path across Windows drives, which is kept as written.
    The composed title keeps the ``describe`` block and drops the file suite's title.
    Wrong if resolution kept the raw spelling, took only a basename, joined against a base
    other than ``rootDir``, left ``..`` in place, or rewrote an absolute path; or if the
    file suite's title leaked into the test title once the file was resolved.
    """
    payload = _playwright_record(
        root_dir, reported, title="override-cockpit dark", describe="Visual_Regression_Gate"
    )
    parsed = fe.parse_report(payload, PLAYWRIGHT_REPORT)

    assert [(case.suite_file, case.title) for case in parsed] == [
        (resolved, "Visual_Regression_Gate > override-cockpit dark")
    ]
    assert fe.recorded_suite_files(payload) == (resolved,)
    attestation = fe.classify("FE-INV-067", "enforced", (VISUAL_SPEC,), parsed, _declaration())
    assert attestation.classification == "attested", attestation.detail


@pytest.mark.parametrize(
    ("config", "names"),
    [
        pytest.param(None, "no 'config' object", id="no-config"),
        pytest.param([CI_ROOT_DIR], "no 'config' object", id="config-not-an-object"),
        pytest.param({}, "no 'config.rootDir'", id="no-root-dir"),
        pytest.param({"rootDir": None}, "not a path string: got NoneType", id="null-root-dir"),
        pytest.param({"rootDir": 42}, "not a path string: got int", id="numeric-root-dir"),
        pytest.param({"rootDir": "  "}, "'config.rootDir' is empty", id="blank-root-dir"),
        pytest.param({"rootDir": "tests/e2e"}, "is not an absolute path", id="relative-root-dir"),
    ],
)
def test_a_playwright_record_without_a_usable_root_dir_is_refused(
    config: object, names: str
) -> None:
    """No usable ``config.rootDir``: both readers refuse, and the refusal names what is missing.

    The record is otherwise one passing case from FE-INV-056's suite file. Wrong if either
    reader fell back to the unresolved spelling or to an assumed base (the assumption
    finding 90 measured), or if the listing returned ``()``, which would claim the record
    listed no file at all.
    """
    payload = _playwright_record(CI_ROOT_DIR, REPORTED_FILE)
    if config is None:
        del payload["config"]
    else:
        payload["config"] = config

    with pytest.raises(fe.ReportFormatError, match=re.escape(names)) as refused:
        fe.parse_report(payload, PLAYWRIGHT_REPORT)
    assert "config.rootDir" in str(refused.value)
    with pytest.raises(fe.ReportFormatError, match=re.escape(names)):
        fe.recorded_suite_files(payload)


def test_a_playwright_record_without_a_root_dir_is_unavailable_never_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal reaches the verdict as ``unavailable`` (exit 2), and the record earns nothing.

    Read from disk through ``load_reports``, as the CI step reads it. The record would
    attest FE-INV-056 if its ``file`` were placed under a guessed base, so a pass here would
    be a pass bought by an assumption. Wrong if the record's case or listing reached the
    verdict, if the refusal did not name the record and ``config.rootDir``, or if the verdict
    were anything but ``unavailable``.
    """
    payload = _playwright_record(CI_ROOT_DIR, REPORTED_FILE)
    del payload["config"]["rootDir"]
    record = tmp_path / PLAYWRIGHT_REPORT
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    monkeypatch.setattr(fe, "ROOT", tmp_path)

    tests, recorded, read, unavailable = fe.load_reports((PLAYWRIGHT_REPORT,))

    assert (tests, recorded, read) == ((), (), ())
    assert len(unavailable) == 1
    assert unavailable[0].startswith(f"{PLAYWRIGHT_REPORT}: ")
    assert "config.rootDir" in unavailable[0]

    verdict = fe.evaluate_reports(
        (_invariant("FE-INV-056"),),
        _declaration(),
        tests,
        read,
        unavailable,
        (),
        recorded_files=recorded,
    )
    assert verdict.verdict == "unavailable"
    assert verdict.exit_code == fe.EXIT_UNAVAILABLE
    assert not verdict.passing
    assert "config.rootDir" in verdict.reason
    assert verdict.reason.isascii()


def test_both_playwright_configs_root_their_records_at_the_e2e_tree() -> None:
    """Each committed config sets one ``testDir`` that resolves to ``frontend/tests/e2e``.

    Playwright's ``config.rootDir`` is that ``testDir`` resolved against the config's
    directory, so this is what makes ``E2E_DIR``, the spelling the fixtures above encode,
    and the claim in ``paths_match``'s docstring the real layout rather than an assumption.
    Wrong if a config moved or dropped its ``testDir`` (without one, ``rootDir`` is the
    config's own directory and a top-level spec is reported as ``tests/e2e/smoke.spec.ts``).
    The gate would still resolve correctly, because it reads ``rootDir`` from the record,
    but these fixtures and that docstring would describe a layout that no longer exists.
    """
    for config in PLAYWRIGHT_CONFIGS:
        declared = _TEST_DIR_RE.findall((ROOT / config).read_text(encoding="utf-8"))
        assert len(declared) == 1, f"{config}: expected one top-level testDir, found {declared}"
        root = posixpath.normpath(posixpath.join(posixpath.dirname(config), declared[0]))
        assert root == E2E_DIR, f"{config}: testDir {declared[0]!r} roots the record at {root}"
