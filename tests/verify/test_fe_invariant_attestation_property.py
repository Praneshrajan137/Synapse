"""Property-based test for FE-INV attestation (design E2.4 / RC-3; R8.7, R12.4).

Feature: purpose-achievement-audit, Property 35: An enforced invariant has an executed
assertion

    *For any* (invariant registry, test report) pair, an invariant registered ``enforced``
    is accepted only when the report contains at least one executed, non-skipped assertion
    attributable to it; the existence of a named test file and an all-skipped run of that
    file are both rejected, naming the invariant.

Why a property and not examples. The example-class facts already live beside this file in
``test_fe_invariant_attestation.py``: one listed file that never ran, one all-skipped run,
one missing reporter record, one attempt to declare ``FE-INV-056`` away. Those pin the four
shapes the audit finding was made of. What they cannot state is the rule the repair
actually rests on, which is universal: *whatever* the registry says and *whatever* the
runners reported, credit follows an executed, non-skipped, passing assertion and nothing
else. The old gate was wrong not because it mishandled one entry but because its evidence
- ``Path.exists()`` - was categorically the wrong observation, and a categorical error is
falsified by quantification, not by a longer list of cases.

So the driver is a *generated registry plus generated reporter output*: a sub-registry of
the committed FE-INV ids, each entry owning a Playwright/Vitest suite file or only a
non-executable one, paired with reporter JSON in the two real shapes the gate consumes.
Every knob is ground truth - which invariant a reported case is attributable to, by which
of the two attribution routes, and whether it passed, failed, or skipped - and the gate has
to rediscover all of it from the JSON alone. Reporter output is *synthesised*, never
produced: running Vitest or Playwright here is exactly the workload I-0 forbids, and it
would prove less, because a real run cannot be asked for the counterexample shapes.

Three clauses are kept deliberately apart, because collapsing them is how the original
defect survived review:

* **Existence is not evidence.** ``test_a_listed_file_that_merely_exists_earns_nothing``
  writes every listed implementation and test into a synthetic tree, so the hygiene pass
  that checks existence *succeeds* - and the gate still fails. Existence is necessary and
  never sufficient (R8.7).
* **An all-skipped run is non-passing, not a shorter pass.** A run in which nothing
  executed is ``unavailable`` (exit ``2``), the attested set is empty, and the *only*
  difference between rejection and credit is whether the same attributable assertion ran:
  flipping each skip to a pass moves that invariant from ``skipped_only`` to ``attested``
  and nothing else changes (I-7 - absence of proof is never a pass).
* **Out-of-suite is a disclosed label, not credit.** A declared enforcer resolves only
  when it names a workflow and a job that exist, and even then the invariant is never
  ``attested``. That clause reuses ``workflow_documents`` from ``tests.verify.strategies``
  so the resolution is judged against real workflow-shaped YAML (R12.4, R12.5).

Totality is asserted as firmly as the positive cases: every registry entry yields exactly
one classification drawn from the module's own ``Classification`` vocabulary, the
classifications partition the registry, ``attested`` holds for exactly one class, and the
derivation is deterministic on a fixed input.

Nothing is a literal here. Suite extensions come from
``infrastructure/quality/fe-invariant-attestation.yaml``, reporter paths from the gate's
``DEFAULT_REPORTS``, registry statuses from its ``VALID_STATUS``, exit codes from its
``EXIT_*`` constants, the classification vocabulary from ``typing.get_args`` over its
``Classification`` alias, and invariant ids are drawn from the ids committed in
``frontend/spec/fe_invariants.yaml`` - so a generated registry is a sub-registry of the
real one and a generated id is indistinguishable from a registered one.

Hermetic roots. The gate resolves the registry, the declaration, and every listed file
against module globals (``ROOT`` / ``SPEC`` / ``DECLARATION``), none of which is a
parameter, so :func:`synthetic_tree` rebinds exactly those three for the duration of one
example and restores them in a ``finally``. Nothing is written inside the working tree. The
committed registry and declaration are read once at import time, before any rebinding.

The gate lives at ``frontend/spec/check_fe_invariants.py``, outside any Python package (its
path is referenced by ``fe_invariants.yaml`` and ``.github/workflows/frontend.yml``), so it
is loaded by path rather than imported - the same way the sibling example test loads it.

I-0: this test parses small JSON and YAML documents. It starts no browser, drives no
runner, and runs no subprocess, so it is deliberately **not** ``slow``-marked.
``max_examples`` is never set here - the budget comes from the root ``conftest.py`` profiles
(``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 8.7, 12.4**
"""

from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, get_args

import yaml
from hypothesis import given
from hypothesis import strategies as st

from tests.verify.strategies import workflow_documents

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from tests.verify.strategies import WorkflowDraft

# ---------------------------------------------------------------------------
# Load the gate by path (it is not importable as a module)
# ---------------------------------------------------------------------------

ROOT: Final = Path(__file__).resolve().parents[2]
_GATE_PATH: Final = ROOT / "frontend" / "spec" / "check_fe_invariants.py"

_spec = importlib.util.spec_from_file_location("check_fe_invariants_property", _GATE_PATH)
assert _spec is not None and _spec.loader is not None
fe = importlib.util.module_from_spec(_spec)
# Registered before ``exec_module`` (importlib's documented pattern). Pydantic resolves
# the gate's string annotations through ``sys.modules[cls.__module__]``, so an unregistered
# by-path module raises ``PydanticUserError: ... is not fully defined`` on an interpreter
# that defers annotation evaluation (Python 3.14, PEP 649). CI pins 3.11, where the
# omission is invisible. See the same note in the sibling example test.
sys.modules[_spec.name] = fe
_spec.loader.exec_module(fe)

# ---------------------------------------------------------------------------
# Vocabulary, all of it read from committed configuration or from the gate
# ---------------------------------------------------------------------------

#: Where the gate expects the registry and the declaration, relative to its root. Captured
#: before any rebinding so :func:`synthetic_tree` can reproduce the same layout.
SPEC_REL: Final[str] = fe.SPEC.relative_to(fe.ROOT).as_posix()
DECLARATION_REL: Final[str] = fe.DECLARATION.relative_to(fe.ROOT).as_posix()

#: The committed declaration. Its ``suite_extensions`` decide which listed test a JS runner
#: could ever have executed, so they are read rather than restated (design AD-13).
COMMITTED_DECLARATION: Final = fe.load_declaration(fe.DECLARATION)
SUITE_EXTENSIONS: Final[tuple[str, ...]] = COMMITTED_DECLARATION.suite_extensions

#: Ids committed in ``frontend/spec/fe_invariants.yaml``. Drawing from these makes every
#: generated registry a sub-registry of the real one.
COMMITTED_IDS: Final[tuple[str, ...]] = tuple(
    str(inv.get("id")) for inv in fe.load_invariants(fe.SPEC) if inv.get("id")
)

#: The two reporter files the gate reads by default, identified by runner rather than by
#: position so a reordering of ``DEFAULT_REPORTS`` cannot silently swap them.
VITEST_REPORT: Final[str] = next(path for path in fe.DEFAULT_REPORTS if "vitest" in path)
PLAYWRIGHT_REPORT: Final[str] = next(path for path in fe.DEFAULT_REPORTS if "playwright" in path)
REPORTS: Final[tuple[str, ...]] = (VITEST_REPORT, PLAYWRIGHT_REPORT)

#: Registry statuses, from the gate's own closed set.
ENFORCED: Final[str] = fe.ENFORCED
SCHEDULED_STATUSES: Final[tuple[str, ...]] = tuple(sorted(fe.VALID_STATUS - {ENFORCED}))
ALL_STATUSES: Final[tuple[str, ...]] = (ENFORCED, *SCHEDULED_STATUSES)

#: The classification vocabulary, derived from the gate's ``Classification`` alias so a new
#: class cannot be added without this test seeing it.
CLASSIFICATIONS: Final[frozenset[str]] = frozenset(get_args(fe.Classification))

#: Exit status per verdict. ``2`` is non-passing just as ``1`` is (I-7).
EXPECTED_EXIT: Final[dict[str, int]] = {
    "pass": fe.EXIT_PASS,
    "fail": fe.EXIT_FAIL,
    "unavailable": fe.EXIT_UNAVAILABLE,
}

#: The classifications that owe an assertion and did not get one. Restated here rather than
#: imported, then pinned against the gate's constant in :func:`test_classification_is_total`
#: so a vocabulary drift is a failure instead of a silent agreement.
FAILING_CLASSES: Final[tuple[str, ...]] = ("violated", "skipped_only", "not_executed")

#: The tag form that attributes a reported test to an invariant. Recompiled locally: this
#: test must find the tags itself, not ask the gate where they are.
TAG_RE: Final = re.compile(r"FE-INV-\d{3}")

#: A non-executable listed test - a workflow file. Real shape: several committed entries
#: list exactly this, which is what makes ``out_of_suite`` reachable at all.
DEFAULT_WORKFLOW: Final[str] = ".github/workflows/frontend.yml"

#: A job that exists in that workflow (the gate's own CI job).
DEFAULT_JOB: Final[str] = "fe-invariants"

DATED: Final[str] = "2026-06-17"
RATIONALE: Final[str] = "generated: enforced by a CI job rather than a rendered assertion"
REMOVAL: Final[str] = "generated: delete when a tagged assertion observes this invariant"

Runner = Literal["vitest", "playwright"]
Route = Literal["file", "tag", "orphan"]
Spelling = Literal["repo", "runner", "posix-absolute", "windows-absolute"]
CaseStatus = Literal["passed", "failed", "skipped"]

RUNNERS: Final[tuple[Runner, ...]] = ("vitest", "playwright")
ROUTES: Final[tuple[Route, ...]] = ("file", "tag", "orphan")
SPELLINGS: Final[tuple[Spelling, ...]] = (
    "repo",
    "runner",
    "posix-absolute",
    "windows-absolute",
)
CASE_STATUSES: Final[tuple[CaseStatus, ...]] = ("passed", "failed", "skipped")

#: Reporter spellings that all collapse to "did not execute". ``todo`` and ``pending`` prove
#: exactly as much as ``skip`` does, which is nothing.
SKIP_SPELLINGS: Final[tuple[str, ...]] = ("skipped", "pending", "todo")

#: Describe-block titles a generated case may sit under. Deliberately free of any
#: ``FE-INV-###`` tag, so ancestry never attributes a case by accident.
ANCESTORS: Final[tuple[str, ...]] = ("operator flow", "Task_Completion", "degraded transport")

#: A declared-but-unreadable reporter record, in the exact "<path>: <reason>" shape
#: ``load_reports`` produces. Present so the partial-read downgrade is quantified over.
MISSING_REPORT: Final[str] = (
    "frontend/artifacts/test-reports/playwright-visual.json: no reporter output at this path"
)


def slug_for(invariant_id: str) -> str:
    """``FE-INV-056`` -> ``fe_inv_056``: a unique basename stem per invariant."""
    return invariant_id.lower().replace("-", "_")


def suite_path_for(invariant_id: str) -> str:
    """The Playwright spec a generated invariant owns.

    Every stem is distinct, so no two invariants' suite files can path-match each other and
    no noise file can path-match a suite file: attribution stays exactly as generated.
    """
    return f"frontend/tests/e2e/{slug_for(invariant_id)}.jtbd.spec.ts"


def noise_path_for(index: int) -> str:
    """A suite file no generated registry lists, for cases attributable by tag or not at all."""
    return f"frontend/src/lib/__tests__/case_{index}.test.ts"


def tags_in_title(title: str) -> tuple[str, ...]:
    """Every distinct ``FE-INV-###`` tag in *title*, in first-seen order."""
    return tuple(dict.fromkeys(TAG_RE.findall(title)))


def spell(path: str, spelling: Spelling) -> str:
    """One of the four ways a runner or a registry spells the same file.

    Vitest reports an absolute path (POSIX on the runners, Windows on this dev box),
    Playwright reports one relative to its ``rootDir`` (``frontend/``), and the registry
    lists repo-relative paths. All four must attribute to the same invariant.
    """
    if spelling == "repo":
        return path
    if spelling == "runner":
        return path.removeprefix("frontend/")
    if spelling == "posix-absolute":
        return f"/repo/{path}"
    return "C:\\repo\\" + path.replace("/", "\\")


def canonical(payload: Mapping[str, Any]) -> str:
    """Canonical JSON, per the repo-wide serialisation convention."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# The generated registry and the generated run record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvariantDraft:
    """One generated ``fe_invariants.yaml`` entry, and the truth of what it lists."""

    invariant_id: str
    registry_status: str = ENFORCED
    owns_suite_file: bool = True
    lists_non_suite_file: bool = False
    declared_out_of_suite: bool = False
    non_suite_path: str = DEFAULT_WORKFLOW
    out_of_suite_workflow: str = DEFAULT_WORKFLOW
    out_of_suite_job: str = DEFAULT_JOB

    @property
    def implementations(self) -> tuple[str, ...]:
        return (f"frontend/src/surfaces/{slug_for(self.invariant_id)}/index.tsx",)

    @property
    def listed_tests(self) -> tuple[str, ...]:
        """Never empty: a registry entry listing no test is a separate hygiene defect."""
        listed: list[str] = []
        if self.owns_suite_file:
            listed.append(suite_path_for(self.invariant_id))
        if self.lists_non_suite_file or not self.owns_suite_file:
            listed.append(self.non_suite_path)
        return tuple(listed)

    @property
    def suite_files(self) -> tuple[str, ...]:
        """The listed tests a JS runner could execute - the ground truth for R8.7."""
        return (suite_path_for(self.invariant_id),) if self.owns_suite_file else ()

    def as_registry_entry(self) -> dict[str, Any]:
        return {
            "id": self.invariant_id,
            "title": f"generated invariant {self.invariant_id}",
            "status": self.registry_status,
            "implementations": list(self.implementations),
            "tests": list(self.listed_tests),
        }


@dataclass(frozen=True)
class CaseDraft:
    """One test case a runner reported, and the truth of what it proves.

    ``route`` is the ground truth of attribution: ``file`` means the case came from the
    owner's listed suite file, ``tag`` means its title (or its Playwright tag list) carries
    the owner's id while the file is unrelated, and ``orphan`` means it is attributable to
    nothing in the registry.
    """

    index: int
    runner: Runner
    route: Route
    owner: str | None
    status: CaseStatus
    skip_spelling: str = "skipped"
    spelling: Spelling = "repo"
    ancestor: str | None = None
    declared_tag: bool = False

    @property
    def leaf_title(self) -> str:
        base = f"case {self.index} reaches its declared terminal outcome"
        if self.route == "tag" and self.owner is not None and not self.declared_tag:
            return f"{base} [{self.owner}]"
        return base

    @property
    def full_title(self) -> str:
        """The title the reporter composes: ancestor titles joined with the case title."""
        return f"{self.ancestor} > {self.leaf_title}" if self.ancestor else self.leaf_title

    @property
    def logical_file(self) -> str:
        if self.route == "file" and self.owner is not None:
            return suite_path_for(self.owner)
        return noise_path_for(self.index)

    @property
    def reported_file(self) -> str:
        return spell(self.logical_file, self.spelling)

    @property
    def source_report(self) -> str:
        return VITEST_REPORT if self.runner == "vitest" else PLAYWRIGHT_REPORT

    @property
    def expected_tags(self) -> tuple[str, ...]:
        title_tags = tags_in_title(self.full_title)
        if self.declared_tag and self.owner is not None:
            return tuple(dict.fromkeys((*title_tags, self.owner)))
        return title_tags

    @property
    def executed(self) -> bool:
        return self.status != "skipped"

    @property
    def vitest_status(self) -> str:
        if self.status == "skipped":
            return self.skip_spelling
        return self.status

    def as_vitest_case(self) -> dict[str, Any]:
        return {
            "ancestorTitles": [self.ancestor] if self.ancestor else [],
            "title": self.leaf_title,
            "fullName": self.full_title,
            "status": self.vitest_status,
        }

    def as_playwright_spec(self, spec_file: str) -> dict[str, Any]:
        """One Playwright spec, including the retry/result nesting the collapser reads."""
        if self.status == "passed":
            tests: list[dict[str, Any]] = [
                {"status": "expected", "results": [{"status": "passed"}]}
            ]
        elif self.status == "failed":
            tests = [{"status": "unexpected", "results": [{"status": "failed"}]}]
        elif self.skip_spelling == "skipped":
            tests = [{"status": "skipped", "results": [{"status": "skipped"}]}]
        else:
            # A runtime `test.skip(true, ...)` can leave no result at all - the construct
            # that made FE-INV-056 vacuous. It must still collapse to "did not execute".
            tests = [{"status": "skipped", "results": []}]
        spec: dict[str, Any] = {"title": self.leaf_title, "file": spec_file, "tests": tests}
        if self.declared_tag and self.owner is not None:
            spec["tags"] = [self.owner]
        return spec


@dataclass(frozen=True)
class ScenarioDraft:
    """A generated registry, a generated declaration, and a generated run record."""

    invariants: tuple[InvariantDraft, ...]
    cases: tuple[CaseDraft, ...]
    reports_unavailable: tuple[str, ...] = ()

    # -- projections the gate consumes --------------------------------------

    @property
    def declared_ids(self) -> frozenset[str]:
        return frozenset(
            inv.invariant_id for inv in self.invariants if inv.declared_out_of_suite
        )

    def registry_entries(self) -> tuple[dict[str, Any], ...]:
        return tuple(inv.as_registry_entry() for inv in self.invariants)

    def declaration(self) -> Any:
        return fe.AttestationDeclaration(
            suite_extensions=SUITE_EXTENSIONS,
            out_of_suite=tuple(
                fe.OutOfSuiteEntry(
                    invariant_id=inv.invariant_id,
                    workflow=inv.out_of_suite_workflow,
                    job=inv.out_of_suite_job,
                    rationale=RATIONALE,
                    dated=DATED,
                    removal_condition=REMOVAL,
                )
                for inv in self.invariants
                if inv.declared_out_of_suite
            ),
        )

    def registry_yaml(self) -> str:
        return yaml.safe_dump(
            {"version": 1, "invariants": [inv.as_registry_entry() for inv in self.invariants]},
            sort_keys=True,
            allow_unicode=False,
        )

    def declaration_yaml(self) -> str:
        return yaml.safe_dump(
            {
                "version": 1,
                "suite_extensions": list(SUITE_EXTENSIONS),
                "out_of_suite": [
                    {
                        "id": inv.invariant_id,
                        "workflow": inv.out_of_suite_workflow,
                        "job": inv.out_of_suite_job,
                        "rationale": RATIONALE,
                        "dated": DATED,
                        "removal_condition": REMOVAL,
                    }
                    for inv in self.invariants
                    if inv.declared_out_of_suite
                ],
            },
            sort_keys=True,
            allow_unicode=False,
        )

    def payloads(self) -> dict[str, str]:
        """The two reporter files, in the two real reporter shapes."""
        vitest = tuple(case for case in self.cases if case.runner == "vitest")
        playwright = tuple(case for case in self.cases if case.runner == "playwright")
        return {
            VITEST_REPORT: canonical(vitest_payload(vitest)),
            PLAYWRIGHT_REPORT: canonical(playwright_payload(playwright)),
        }

    # -- ground truth -------------------------------------------------------

    def attributed(self, inv: InvariantDraft) -> tuple[CaseDraft, ...]:
        """Cases attributable to *inv* by construction, not by asking the gate."""
        return tuple(
            case
            for case in self.cases
            if case.owner == inv.invariant_id
            and (case.route == "tag" or (case.route == "file" and inv.owns_suite_file))
        )

    def expected_classification(self, inv: InvariantDraft) -> str:
        """R8.7 and R12.4 restated: credit follows an executed, non-skipped pass."""
        if inv.registry_status != ENFORCED:
            return "not_enforced"
        attributed = self.attributed(inv)
        if any(case.status == "passed" for case in attributed):
            return "attested"
        if any(case.status == "failed" for case in attributed):
            return "violated"
        if any(case.status == "skipped" for case in attributed):
            return "skipped_only"
        if inv.suite_files:
            return "not_executed"
        if inv.invariant_id in self.declared_ids:
            return "out_of_suite"
        return "unattributable"

    @property
    def classifications(self) -> dict[str, str]:
        return {inv.invariant_id: self.expected_classification(inv) for inv in self.invariants}

    @property
    def failing_ids(self) -> tuple[str, ...]:
        return tuple(
            inv.invariant_id
            for inv in self.invariants
            if self.expected_classification(inv) in FAILING_CLASSES
        )

    @property
    def unattributable_ids(self) -> tuple[str, ...]:
        return tuple(
            inv.invariant_id
            for inv in self.invariants
            if self.expected_classification(inv) == "unattributable"
        )

    @property
    def executed_cases(self) -> tuple[CaseDraft, ...]:
        return tuple(case for case in self.cases if case.executed)

    def expected_verdict(self, *, hygiene: bool = False) -> tuple[str, str]:
        """``(verdict, branch)``, restated from the gate's documented precedence.

        Written out here rather than imported, so a disagreement means one of two
        implementations of the same rule is wrong.
        """
        if not self.invariants:
            return "fail", "empty-registry"
        if hygiene:
            return "fail", "hygiene"
        if not self.executed_cases:
            return "unavailable", "all-skipped"
        if self.failing_ids:
            return "fail", "failing"
        if self.unattributable_ids:
            return "unavailable", "unobservable"
        if self.reports_unavailable:
            return "unavailable", "partial-read"
        return "pass", "pass"

    def with_case_status(self, status: CaseStatus) -> ScenarioDraft:
        """The same scenario with every reported case forced to *status*."""
        return dataclasses.replace(
            self,
            cases=tuple(
                dataclasses.replace(case, status=status, skip_spelling=case.skip_spelling)
                for case in self.cases
            ),
        )


def vitest_payload(cases: Sequence[CaseDraft]) -> dict[str, Any]:
    """Vitest's (Jest-shaped) JSON reporter output, grouped by file as the runner emits it."""
    grouped: dict[str, list[CaseDraft]] = {}
    for case in cases:
        grouped.setdefault(case.reported_file, []).append(case)
    return {
        "testResults": [
            {
                "name": reported,
                "assertionResults": [case.as_vitest_case() for case in group],
            }
            for reported, group in grouped.items()
        ]
    }


def playwright_payload(cases: Sequence[CaseDraft]) -> dict[str, Any]:
    """Playwright's JSON reporter output: one outer suite per file, describe blocks nested.

    The outer suite's title is the spec path, exactly as Playwright writes it, so the
    walker must keep it out of the composed test title.
    """
    grouped: dict[str, list[CaseDraft]] = {}
    for case in cases:
        grouped.setdefault(case.reported_file, []).append(case)

    suites: list[dict[str, Any]] = []
    for reported, group in grouped.items():
        direct = [case.as_playwright_spec(reported) for case in group if case.ancestor is None]
        nested: dict[str, list[dict[str, Any]]] = {}
        for case in group:
            if case.ancestor is not None:
                nested.setdefault(case.ancestor, []).append(case.as_playwright_spec(reported))
        node: dict[str, Any] = {"title": reported, "file": reported, "specs": direct}
        if nested:
            node["suites"] = [
                {"title": ancestor, "specs": specs} for ancestor, specs in nested.items()
            ]
        suites.append(node)
    return {"suites": suites}


def parsed_tests(scenario: ScenarioDraft) -> tuple[Any, ...]:
    """Every reported case, normalised by the gate's own reporter parsers."""
    tests: list[Any] = []
    for source, text in scenario.payloads().items():
        tests.extend(fe.parse_report(json.loads(text), source))
    return tuple(tests)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


@st.composite
def scenarios(
    draw: st.DrawFn,
    *,
    min_invariants: int = 1,
    max_invariants: int = 4,
    min_cases: int = 0,
    max_cases: int = 5,
    registry_statuses: Sequence[str] = ALL_STATUSES,
    owns_suite_file: bool | None = None,
    declared_out_of_suite: bool | None = None,
    routes: Sequence[Route] = ROUTES,
    case_statuses: Sequence[CaseStatus] = CASE_STATUSES,
    allow_missing_report: bool = True,
) -> ScenarioDraft:
    """A (registry, declaration, run record) triple.

    Every knob is a *pin*, not a filter: pinning is how one clause is isolated
    (``case_statuses=("skipped",)`` for the all-skipped clause, ``routes=("orphan",)`` for
    the existence clause) without a ``.filter`` that would reject most draws and trip
    Hypothesis' ``filter_too_much`` health check.
    """
    ids = draw(
        st.lists(
            st.sampled_from(COMMITTED_IDS),
            min_size=min_invariants,
            max_size=max_invariants,
            unique=True,
        )
    )
    invariants: list[InvariantDraft] = []
    for invariant_id in ids:
        owns = draw(st.booleans()) if owns_suite_file is None else owns_suite_file
        declared = (
            draw(st.booleans()) if declared_out_of_suite is None else declared_out_of_suite
        )
        invariants.append(
            InvariantDraft(
                invariant_id=invariant_id,
                registry_status=draw(st.sampled_from(tuple(registry_statuses))),
                owns_suite_file=owns,
                lists_non_suite_file=draw(st.booleans()),
                declared_out_of_suite=declared,
            )
        )

    suite_owners = tuple(inv.invariant_id for inv in invariants if inv.owns_suite_file)
    all_ids = tuple(inv.invariant_id for inv in invariants)

    cases: list[CaseDraft] = []
    case_count = draw(st.integers(min_value=min_cases, max_value=max_cases))
    for index in range(case_count):
        route: Route = draw(st.sampled_from(tuple(routes)))
        if route == "file" and not suite_owners:
            # Nothing owns an executable suite file, so no case can have come from one.
            route = "tag"
        owner: str | None = None
        if route == "file":
            owner = draw(st.sampled_from(suite_owners))
        elif route == "tag":
            owner = draw(st.sampled_from(all_ids))
        runner: Runner = draw(st.sampled_from(RUNNERS))
        cases.append(
            CaseDraft(
                index=index,
                runner=runner,
                route=route,
                owner=owner,
                status=draw(st.sampled_from(tuple(case_statuses))),
                skip_spelling=draw(st.sampled_from(SKIP_SPELLINGS)),
                spelling=draw(st.sampled_from(SPELLINGS)),
                ancestor=draw(st.none() | st.sampled_from(ANCESTORS)),
                # The Playwright tag list is the second attribution route; Vitest has no
                # equivalent, so a tagged Vitest case must carry its tag in the title.
                declared_tag=(
                    runner == "playwright" and route == "tag" and draw(st.booleans())
                ),
            )
        )

    unavailable = (
        draw(st.sampled_from(((), (MISSING_REPORT,)))) if allow_missing_report else ()
    )
    return ScenarioDraft(
        invariants=tuple(invariants), cases=tuple(cases), reports_unavailable=unavailable
    )


# ---------------------------------------------------------------------------
# The hermetic tree
# ---------------------------------------------------------------------------


def _placeholder_for(rel: str) -> str:
    """Content for a listed file the tree only needs to *exist*.

    A ``.yml`` placeholder is valid workflow-shaped YAML because a declared out-of-suite
    entry names a workflow the gate parses; everything else only has to be a file.
    """
    if rel.endswith((".yml", ".yaml")):
        return yaml.safe_dump(
            {"jobs": {DEFAULT_JOB: {"runs-on": "ubuntu-latest"}}},
            sort_keys=True,
            allow_unicode=False,
        )
    return "// generated placeholder: this file exists, which proves nothing\n"


@contextlib.contextmanager
def synthetic_tree(
    scenario: ScenarioDraft, extra: Mapping[str, str] | None = None
) -> Iterator[Path]:
    """Render *scenario* into a throwaway tree and point the gate's roots at it.

    ``ROOT``, ``SPEC`` and ``DECLARATION`` are module globals rather than parameters, so
    the only way to evaluate a generated registry *without* writing into the working tree
    is to rebind them for one example. They are restored in a ``finally``, so a failing
    example cannot leak a root into the next test.
    """
    with tempfile.TemporaryDirectory(prefix="fe-invariant-attestation-") as tmp:
        root = Path(tmp)

        def write(rel: str, text: str) -> None:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        for rel, text in (extra or {}).items():
            write(rel, text)
        for inv in scenario.invariants:
            for rel in (*inv.implementations, *inv.listed_tests):
                if not (root / rel).exists():
                    write(rel, _placeholder_for(rel))
        write(SPEC_REL, scenario.registry_yaml())
        write(DECLARATION_REL, scenario.declaration_yaml())
        for rel, text in scenario.payloads().items():
            write(rel, text)

        previous = (fe.ROOT, fe.SPEC, fe.DECLARATION)
        fe.ROOT, fe.SPEC, fe.DECLARATION = root, root / SPEC_REL, root / DECLARATION_REL
        try:
            yield root
        finally:
            fe.ROOT, fe.SPEC, fe.DECLARATION = previous


def attestation_for(verdict: Any, invariant_id: str) -> Any:
    """The single attestation for *invariant_id*; the gate must emit exactly one."""
    matching = [a for a in verdict.attestations if a.invariant_id == invariant_id]
    assert len(matching) == 1, f"expected one attestation for {invariant_id}, got {len(matching)}"
    return matching[0]


def evaluate(scenario: ScenarioDraft) -> Any:
    """Drive the pure verdict path over a generated scenario (no filesystem, no runner)."""
    return fe.evaluate_reports(
        scenario.registry_entries(),
        scenario.declaration(),
        parsed_tests(scenario),
        REPORTS,
        scenario.reports_unavailable,
        (),
    )


# ---------------------------------------------------------------------------
# Property 35
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 35: An enforced invariant has an executed assertion
@given(scenario=scenarios())
def test_credit_requires_an_executed_non_skipped_assertion(scenario: ScenarioDraft) -> None:
    """R8.7 / R12.4: the reporter output is the only thing that can grant credit.

    Three derivations are compared against ground truth at once - what the reporter said
    (parsing), what each invariant earned (classification), and what the gate concluded
    (verdict) - because the audit finding was that the middle one was never performed at
    all. Getting any of them wrong would leave credit resting on something other than an
    executed assertion, which is the whole finding.
    """
    tests = parsed_tests(scenario)

    # The gate rediscovered every reported case: its file (in four spellings), its composed
    # title, its collapsed status, and its tags (title-borne and Playwright-declared).
    assert sorted(
        (test.report, test.suite_file, test.title, test.status, test.tags) for test in tests
    ) == sorted(
        (
            case.source_report,
            case.reported_file,
            case.full_title,
            case.status,
            case.expected_tags,
        )
        for case in scenario.cases
    )

    declaration = scenario.declaration()
    for inv in scenario.invariants:
        attestation = fe.classify(
            inv.invariant_id, inv.registry_status, inv.listed_tests, tests, declaration
        )
        attributed = scenario.attributed(inv)
        assert attestation.classification == scenario.expected_classification(inv)
        assert attestation.suite_files == inv.suite_files
        # `attested` is the credit predicate, and exactly one class carries it.
        assert attestation.attested is (attestation.classification == "attested")
        assert attestation.attested is bool(
            inv.registry_status == ENFORCED
            and any(case.status == "passed" for case in attributed)
        )
        # A listed file, however many there are, buys nothing on its own.
        if inv.registry_status == ENFORCED and not attributed:
            assert not attestation.attested
        assert sorted(attestation.attesting) == sorted(
            case.full_title for case in attributed if case.status == "passed"
        )
        assert sorted(attestation.failed) == sorted(
            case.full_title for case in attributed if case.status == "failed"
        )
        assert sorted(attestation.skipped) == sorted(
            case.full_title for case in attributed if case.status == "skipped"
        )
        # A gate that cannot print its own finding on Windows reports nothing (E-S13-07).
        assert attestation.detail
        assert attestation.detail.isascii()

    verdict = evaluate(scenario)
    expected, branch = scenario.expected_verdict()
    assert verdict.verdict == expected
    assert verdict.exit_code == EXPECTED_EXIT[expected]
    assert verdict.passing is (expected == "pass")
    assert verdict.executed_count == len(scenario.executed_cases)
    assert verdict.skipped_count == len(scenario.cases) - len(scenario.executed_cases)
    assert verdict.reason
    assert verdict.reason.isascii()

    # Naming is half the contract: a finding nobody can locate repairs nothing.
    if branch == "failing":
        for invariant_id in scenario.failing_ids:
            classification = scenario.classifications[invariant_id]
            assert f"{invariant_id}={classification}" in verdict.reason
    if branch == "unobservable":
        for invariant_id in scenario.unattributable_ids:
            assert invariant_id in verdict.reason


@given(
    scenario=scenarios(
        registry_statuses=(ENFORCED,),
        owns_suite_file=True,
        declared_out_of_suite=False,
        routes=("orphan",),
        case_statuses=("passed",),
        min_cases=1,
        allow_missing_report=False,
    )
)
def test_a_listed_file_that_merely_exists_earns_nothing(scenario: ScenarioDraft) -> None:
    """R8.7: existence is necessary and never sufficient - the removed defect, quantified.

    The tree is written so every listed implementation and test *does* exist, which is
    precisely what the old ``.exists()`` gate consulted: the hygiene pass therefore
    reports no defect. The run record is a real, non-empty, all-passing run - it simply
    contains no assertion attributable to any of these invariants. The gate must still
    fail, naming each invariant and the file whose assertion never ran.
    """
    with synthetic_tree(scenario):
        hygiene = fe.registry_hygiene(fe.load_invariants(fe.SPEC))
        verdict = fe.evaluate(REPORTS)

    # Every listed file exists on disk, so the old gate would have been green here.
    assert hygiene == ()
    assert verdict.hygiene_errors == ()
    assert verdict.reports_read == REPORTS
    assert verdict.executed_count == len(scenario.cases)

    assert verdict.verdict == "fail"
    assert verdict.exit_code == fe.EXIT_FAIL
    assert not verdict.passing
    assert not any(attestation.attested for attestation in verdict.attestations)

    for inv in scenario.invariants:
        attestation = attestation_for(verdict, inv.invariant_id)
        assert attestation.classification == "not_executed"
        assert attestation.suite_files == inv.suite_files
        for suite_file in inv.suite_files:
            assert suite_file in attestation.detail
        assert f"{inv.invariant_id}=not_executed" in verdict.reason


@given(
    scenario=scenarios(
        registry_statuses=(ENFORCED,),
        owns_suite_file=True,
        declared_out_of_suite=False,
        routes=("file", "tag"),
        case_statuses=("skipped",),
        min_cases=1,
        allow_missing_report=False,
    )
)
def test_an_all_skipped_run_is_non_passing_not_a_shorter_pass(scenario: ScenarioDraft) -> None:
    """R8.7 / I-7: a run in which nothing executed proves nothing, whatever it covers.

    Every generated case is attributable to an enforced invariant and every one skipped -
    the ``test.skip(true, ...)`` shape, in all three reporter spellings. The gate must
    report ``unavailable`` rather than pass with a smaller attested set.

    The second half is the metamorphic core of Property 35: flipping the *same*
    attributable assertions from skipped to passed - changing nothing else about the
    registry, the declaration, or the files - moves each of those invariants from
    ``skipped_only`` to ``attested``. Execution is the only variable.
    """
    tests = parsed_tests(scenario)
    verdict = evaluate(scenario)

    assert verdict.verdict == "unavailable"
    assert verdict.exit_code == fe.EXIT_UNAVAILABLE
    assert not verdict.passing
    assert verdict.executed_count == 0
    assert verdict.skipped_count == len(scenario.cases)
    assert not any(attestation.attested for attestation in verdict.attestations)

    executed_scenario = scenario.with_case_status("passed")
    executed_tests = parsed_tests(executed_scenario)
    declaration = scenario.declaration()
    for inv in scenario.invariants:
        if not scenario.attributed(inv):
            continue
        before = fe.classify(
            inv.invariant_id, inv.registry_status, inv.listed_tests, tests, declaration
        )
        after = fe.classify(
            inv.invariant_id, inv.registry_status, inv.listed_tests, executed_tests, declaration
        )
        assert before.classification == "skipped_only"
        assert not before.attested
        assert after.classification == "attested"
        assert after.attested


@given(scenario=scenarios(max_invariants=5, max_cases=6))
def test_classification_is_total_and_deterministic(scenario: ScenarioDraft) -> None:
    """Every registry entry gets exactly one classification, from a closed vocabulary.

    Totality is what stops an invariant slipping through unjudged - the failure mode the
    audit found in ``agency_truth``, where an agent matching neither pattern landed in
    neither list. Here the classifications must partition the registry, come from the
    module's own ``Classification`` alias, and be stable on a fixed input.
    """
    assert tuple(fe.FAILING_CLASSES) == FAILING_CLASSES, "the failing vocabulary drifted"

    tests = parsed_tests(scenario)
    verdict = evaluate(scenario)

    assert len(verdict.attestations) == len(scenario.invariants)
    assert tuple(a.invariant_id for a in verdict.attestations) == tuple(
        inv.invariant_id for inv in scenario.invariants
    )

    # One bucket each: the by-class projections partition the attestation set.
    bucketed = sum(len(verdict.by_class(name)) for name in sorted(CLASSIFICATIONS))
    assert bucketed == len(verdict.attestations)
    for attestation in verdict.attestations:
        assert attestation.classification in CLASSIFICATIONS
        assert attestation.registry_status in fe.VALID_STATUS
        assert (attestation.classification == "not_enforced") is (
            attestation.registry_status != ENFORCED
        )

    declaration = scenario.declaration()
    for inv in scenario.invariants:
        first = fe.classify(
            inv.invariant_id, inv.registry_status, inv.listed_tests, tests, declaration
        )
        second = fe.classify(
            inv.invariant_id, inv.registry_status, inv.listed_tests, tests, declaration
        )
        assert first == second, "the derivation is not a function of its inputs"
        assert first == attestation_for(verdict, inv.invariant_id)


@given(
    scenario=scenarios(
        min_invariants=1,
        max_invariants=1,
        registry_statuses=(ENFORCED,),
        owns_suite_file=False,
        declared_out_of_suite=True,
        routes=("orphan",),
        case_statuses=("passed",),
        min_cases=1,
        max_cases=1,
        allow_missing_report=False,
    ),
    workflow=workflow_documents(),
    resolves=st.booleans(),
)
def test_out_of_suite_is_a_disclosed_label_never_credit(
    scenario: ScenarioDraft, workflow: WorkflowDraft, resolves: bool
) -> None:
    """R12.4 / R12.5: a declared enforcer is a label on debt, not an executed assertion.

    An invariant listing nothing a JS runner can execute cannot be attested by a run
    record, so the only honest outcomes are a disclosed, dated declaration or an
    ``unattributable`` finding. This asserts the disclosure never becomes credit: the
    invariant is classified ``out_of_suite`` and ``attested`` stays false, so it is
    excluded from the attested set even when the gate does not fail.

    The declaration is judged against real workflow-shaped YAML generated by
    ``tests.verify.strategies.workflow_documents``: naming a job the workflow does not
    define is itself a defect, which is what stops the declaration becoming an escape
    hatch.
    """
    defined = tuple(job.job_id for job in workflow.jobs)
    job = defined[0] if resolves else "job-absent"
    assert resolves or job not in defined

    declared = dataclasses.replace(
        scenario.invariants[0],
        non_suite_path=workflow.path,
        out_of_suite_workflow=workflow.path,
        out_of_suite_job=job,
    )
    subject = dataclasses.replace(scenario, invariants=(declared,))

    with synthetic_tree(subject, extra={workflow.path: workflow.to_yaml()}):
        verdict = fe.evaluate(REPORTS)

    attestation = attestation_for(verdict, declared.invariant_id)

    if not resolves:
        assert verdict.verdict == "fail"
        assert verdict.exit_code == fe.EXIT_FAIL
        assert any("defines no such job" in error for error in verdict.hygiene_errors)
        assert any(job in error for error in verdict.hygiene_errors)
        assert not attestation.attested
        return

    assert verdict.hygiene_errors == ()
    assert verdict.verdict == "pass"
    assert attestation.classification == "out_of_suite"
    # The label is disclosed and dated - and it is not proof (I-7).
    assert not attestation.attested
    assert not any(other.attested for other in verdict.attestations)
    assert DATED in attestation.detail
    assert workflow.path in attestation.detail
    assert job in attestation.detail
