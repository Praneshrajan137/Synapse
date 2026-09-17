"""Property-based test for task-record claims judged against the declared registry (E4).

Feature: decision-quality-proof, Property 74: A task record asserting a landed registry
entry fails when the registry holds none

    *For any* set of task records and any state of the Published_Checkpoint_Registry, the
    task-completion check reads the registry file the active policy declares -- resolved
    against the tree root it was given, not a constant bound at import -- and fails naming
    every record that is marked complete while asserting a landed entry that file does not
    hold; an unchecked claim is reported pending and is never a finding; and a validated
    non-placeholder entry clears every claim.

Why this file exists when Property 17 already covers R3.6
---------------------------------------------------------

``tests/verify/test_checkpoint_claim_classification_property.py`` (purpose-achievement-audit
Property 17) drives the **pure** :func:`~scripts.audit.task_claim_truth.judge` seam with an
already-computed :class:`RegistryStatus` injected, plus one example against the committed
tree. It therefore asserts the *rule* and never the *read*. That is precisely the surface
where R9.10's defect lived: :func:`~scripts.audit.task_claim_truth.evaluate` accepted an
injected policy and an injected ``root`` but resolved the registry through the module-level
``published_checkpoint_truth.REGISTRY`` constant, bound at import from the *committed*
policy. A caller pointed at another tree got a verdict about **this** repository's
registry, in both directions:

* a constructed registry holding a landed entry would still have been judged against the
  committed ``__placeholder__`` and reported a false FAIL; and, the dangerous direction,
* a constructed placeholder would have been judged against a landed committed file and
  reported a **PASS** for a claim nothing backed.

Fail-open by construction, and invisible, because every existing assertion about this gate
either injected the status or ran against the one tree where the constant happened to be
right. This file quantifies over the reading path.

Facet 5 is the load-bearing one. It asserts a PASS from an injected registry **while
separately asserting that the committed registry is still a placeholder**, so the only way
the verdict can be PASS is that the read followed the declaration. Reading the committed
file (never writing it) is what makes that contrast real rather than stipulated.

What is universally quantified
------------------------------

Two spaces, crossed:

  1. **Record sets** -- claim texts taken from the committed policy's own quotations of the
     records it was written against (``task_claims.must_resolve[].note``), mixed with
     subject-only and prose-only texts that are NOT claims, each independently checked or
     unchecked. Sourcing the claim text from the policy is what keeps this file free of an
     assertion-pattern literal (AD-13).
  2. **Registry states** -- landed, placeholder, an empty object, an entry that fails
     validation, an absent file, and a file that is not JSON. The last two are reachable
     only through the reading path, which is the point: they are states
     :func:`registry_status` alone cannot produce.

Non-vacuity is asserted, not hoped for: facet 1 enumerates the exact generated domain and
asserts it reaches claims and non-claims, checked and unchecked, and both a passing and a
non-passing registry state. Without that, every "fails when" facet below could pass because
its interesting branch was never drawn.

I-0 and $0: Markdown and one small JSON file per example, written into a module-scoped
``tmp_path``. No network, no process, no torch. Not slow-marked.

``max_examples`` is never set here -- the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 9.10**
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit.published_checkpoint_truth import (
    REQUIRED_ENTRY_KEYS,
    ROOT,
    policy,
    registry_status,
    validate_entry,
)
from scripts.audit.task_claim_truth import (
    RULES,
    ClaimOutcome,
    evaluate,
    read_registry,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from scripts.audit.published_checkpoint_truth import CheckpointPolicy

POLICY: Final[CheckpointPolicy] = policy()
NAME: Final[str] = POLICY.serving_name
FLOOR: Final[float] = POLICY.floors.coverage_p90.value

#: The specs root and the registry file the INJECTED policy declares, both relative to the
#: injected tree root. Deliberately different from the committed values so a read that
#: ignored the declaration would resolve somewhere else and be caught.
INJECTED_SPECS_DIR: Final[str] = "injected-specs"
INJECTED_REGISTRY_FILE: Final[str] = "injected-registry/published_checkpoints.json"

#: Claim text, quoted by the committed policy itself. No pattern literal lives here.
CLAIM_TEXTS: Final[tuple[str, ...]] = tuple(
    " ".join(entry.note.split()) for entry in POLICY.task_claims.must_resolve
)

#: Text that names a subject but asserts nothing, and text that does neither. Both must be
#: read as non-claims, or the "fails naming the record" facets would be measuring nothing.
NON_CLAIM_TEXTS: Final[tuple[str, ...]] = (
    *POLICY.task_claims.subject_markers,
    "Write the property test for this gate and record the result",
    "Read the runbook before proposing a change to the serving path",
)

#: A validated, landed record of the shape the runbook's step-5 output produces. Keyed by
#: REQUIRED_ENTRY_KEYS so a key added to the policy cannot silently stop being supplied,
#: and asserted valid at import so "landed" really is landed.
LANDED: Final[dict[str, Any]] = {
    "repo": "example-owner/synapse-demand-prophet",
    "sha": "a1b2c3d",
    "coverage_p90": FLOOR,
    "final_crps": 0.25,
    "trained_at": f"{date(2026, 6, 1).isoformat()}T12:00:00Z",
    "rows": 1_125_000,
}

#: Every registry state, and whether it is the ONE landed state. The two file-level states
#: are reachable only through the reading path R9.10 repairs.
REGISTRY_STATES: Final[tuple[str, ...]] = (
    "landed",
    "placeholder",
    "empty-object",
    "invalid-entry",
    "absent-file",
    "not-json",
)
LANDED_STATE: Final[str] = "landed"


@dataclass(frozen=True)
class RecordDraft:
    """One generated task record, before it is written into a ``tasks.md``."""

    spec: str
    task_id: str
    checked: bool
    text: str


def is_claim_text(text: str) -> bool:
    """R3.6/R9.10's both-halves rule, restated: an assertion pattern AND a subject.

    Restated from the committed policy rather than imported from the gate, so the
    expectation and the subject are two implementations of one rule.
    """
    matched = any(
        re.compile(declared.pattern, re.IGNORECASE).search(text) is not None
        for declared in POLICY.task_claims.assertion_patterns
    )
    lowered = text.lower()
    mentioned = any(marker.lower() in lowered for marker in POLICY.task_claims.subject_markers)
    return matched and mentioned


record_texts: Final[st.SearchStrategy[str]] = st.one_of(
    st.sampled_from(CLAIM_TEXTS),
    st.sampled_from(NON_CLAIM_TEXTS),
)


@st.composite
def record_drafts(draw: st.DrawFn) -> list[RecordDraft]:
    """Draw a set of task records with distinct (spec, task id) keys."""
    return draw(
        st.lists(
            st.builds(
                RecordDraft,
                spec=st.sampled_from(("alpha-spec", "beta-spec")),
                task_id=st.builds(
                    lambda major, minor: str(major) if minor is None else f"{major}.{minor}",
                    st.integers(min_value=1, max_value=30),
                    st.one_of(st.none(), st.integers(min_value=1, max_value=9)),
                ),
                checked=st.booleans(),
                text=record_texts,
            ),
            min_size=1,
            max_size=5,
            unique_by=lambda draft: (draft.spec, draft.task_id),
        )
    )


# ---------------------------------------------------------------------------
# The injected tree
# ---------------------------------------------------------------------------


def injected_policy() -> CheckpointPolicy:
    """The committed policy with the specs root, registry file and vacuity list swapped.

    ``must_resolve`` is emptied so the anti-vacuity clause -- which is about the COMMITTED
    tree -- does not fire over generated records. That clause is asserted where it
    belongs, against the committed policy, by Property 17.
    """
    claims = POLICY.task_claims.model_copy(
        update={"specs_dir": INJECTED_SPECS_DIR, "must_resolve": ()}
    )
    return POLICY.model_copy(
        update={"registry_file": INJECTED_REGISTRY_FILE, "task_claims": claims}
    )


ACTIVE: Final[CheckpointPolicy] = injected_policy()


def write_records(root: Path, drafts: Sequence[RecordDraft]) -> dict[tuple[str, str], int]:
    """Write one ``tasks.md`` per spec, one record per line, and return each record's line.

    One record per line so the expected line number is the record's position, which is
    what lets the naming facet assert the exact coordinate the gate reports rather than
    merely that it reported some number.
    """
    specs_root = root / ACTIVE.task_claims.specs_dir
    by_spec: dict[str, list[RecordDraft]] = {}
    for draft in drafts:
        by_spec.setdefault(draft.spec, []).append(draft)

    # Every spec directory is rewritten from scratch each example, so a record left by a
    # previous iteration can never be counted here.
    existing = sorted(specs_root.glob("*")) if specs_root.is_dir() else []
    for stale in existing:
        (stale / ACTIVE.task_claims.tasks_filename).unlink(missing_ok=True)

    lines_by_key: dict[tuple[str, str], int] = {}
    for spec, spec_drafts in by_spec.items():
        directory = specs_root / spec
        directory.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for index, draft in enumerate(spec_drafts):
            mark = "x" if draft.checked else " "
            lines.append(f"  - [{mark}] {draft.task_id} {draft.text}")
            lines_by_key[(spec, draft.task_id)] = index + 1
        (directory / ACTIVE.task_claims.tasks_filename).write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    return lines_by_key


def write_registry(root: Path, state: str) -> Path:
    """Materialise one registry state at the path the INJECTED policy declares."""
    path = root / ACTIVE.registry_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    if state == "absent-file":
        return path
    if state == "not-json":
        path.write_text("<html>404 not found</html>\n", encoding="utf-8")
        return path
    payloads: dict[str, dict[str, Any]] = {
        "landed": {NAME: LANDED},
        "placeholder": {"__placeholder__": {"status": "unpublished"}},
        "empty-object": {},
        "invalid-entry": {NAME: {}},
    }
    path.write_text(
        json.dumps(payloads[state], sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    return path


@pytest.fixture(scope="module")
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A scratch tree root the injected policy's relative paths resolve against."""
    return tmp_path_factory.mktemp("task_claim_registry")


# ---------------------------------------------------------------------------
# Facet 1 - non-vacuity of the generated domain and of the fixtures
# ---------------------------------------------------------------------------


# Feature: decision-quality-proof, Property 74: A task record asserting a landed registry entry
# fails when the registry holds none
def test_the_generated_domain_reaches_claims_non_claims_and_both_registry_verdicts() -> None:
    """Anti-vacuity: every branch the facets below discriminate on is reachable.

    Enumeration rather than sampling, because a probabilistic guard against vacuity is
    itself a way to pass vacuously.
    """
    assert CLAIM_TEXTS, POLICY.task_claims.must_resolve
    assert all(is_claim_text(text) for text in CLAIM_TEXTS)
    assert NON_CLAIM_TEXTS
    assert not any(is_claim_text(text) for text in NON_CLAIM_TEXTS)

    # The landed fixture really is landed, and it is the ONLY payload state that clears a
    # claim. Asserted through the real classifier, so "landed" is not stipulated here.
    assert set(LANDED) == set(REQUIRED_ENTRY_KEYS)
    assert validate_entry(LANDED, coverage_floor=FLOOR) == []
    assert registry_status({NAME: LANDED}, name=NAME, coverage_floor=FLOOR).ok is True
    non_landed_payloads: dict[str, dict[str, Any]] = {
        "placeholder": {"__placeholder__": {"status": "unpublished"}},
        "empty-object": {},
        "invalid-entry": {NAME: {}},
    }
    for state, payload in non_landed_payloads.items():
        assert state in REGISTRY_STATES
        assert registry_status(payload, name=NAME, coverage_floor=FLOOR).ok is False, state
    assert LANDED_STATE in REGISTRY_STATES
    # The two file-level states exist only on the reading path, which is facet 3's subject.
    assert {"absent-file", "not-json"}.issubset(set(REGISTRY_STATES))
    assert "unlanded-claim" in RULES

    # The injected declaration differs from the committed one in both coordinates, which
    # is what makes facet 5's contrast a real test of the read rather than a coincidence.
    assert ACTIVE.registry_file != POLICY.registry_file
    assert ACTIVE.task_claims.specs_dir != POLICY.task_claims.specs_dir


# ---------------------------------------------------------------------------
# Facet 2 - the verdict, in both directions, over both spaces
# ---------------------------------------------------------------------------


@given(drafts=record_drafts(), state=st.sampled_from(REGISTRY_STATES))
def test_a_checked_claim_fails_naming_the_record_unless_the_registry_holds_an_entry(
    drafts: list[RecordDraft], state: str, tree: Path
) -> None:
    """R9.10: FAIL iff a record is checked, is a claim, and nothing validated is landed.

    Driven through :func:`evaluate` -- the reading path -- rather than through ``judge``,
    so the file the gate opened is part of what is under test. The expectation is derived
    from the drafts and the state, never read back from the report.

    **Validates: Requirements 9.10**
    """
    lines_by_key = write_records(tree, drafts)
    write_registry(tree, state)

    report = evaluate(checkpoint_policy=ACTIVE, root=tree)

    expected_claims = [draft for draft in drafts if is_claim_text(draft.text)]
    landed = state == LANDED_STATE
    expected_unlanded = [
        draft for draft in expected_claims if draft.checked and not landed
    ]
    expected_pending = [draft for draft in expected_claims if not draft.checked]

    assert report.records_scanned == len(drafts)
    assert len(report.claims) == len(expected_claims)
    assert len(report.unlanded) == len(expected_unlanded)
    assert len(report.pending) == len(expected_pending)

    expected_outcome = ClaimOutcome.FAIL if expected_unlanded else ClaimOutcome.PASS
    assert report.outcome is expected_outcome
    assert report.exit_code == (1 if expected_unlanded else 0)

    findings = [finding for finding in report.findings if finding.rule == "unlanded-claim"]
    assert len(findings) == len(expected_unlanded)
    for finding in findings:
        assert finding.outcome is ClaimOutcome.FAIL
        assert finding.requirement == "R3.6"
        # Named well enough to act on: the file, the line, the spec, the task id, the
        # record's own words, the declared registry file, and the state that made the
        # claim false. Every one of those is what "fails naming the task record" means.
        assert ACTIVE.task_claims.tasks_filename in finding.detail
        assert ACTIVE.registry_file in finding.detail
        assert NAME in finding.detail
        draft = next(
            item
            for item in expected_unlanded
            if item.spec in finding.subject and f"task {item.task_id} " in finding.subject
        )
        assert draft.text in finding.detail
        expected_line = lines_by_key[(draft.spec, draft.task_id)]
        assert f":{expected_line} {draft.spec} " in finding.subject

    # A pending claim is never a finding: an open task asserting nothing yet is not a lie.
    for draft in expected_pending:
        assert not any(
            draft.spec in finding.subject and f"task {draft.task_id} " in finding.subject
            for finding in report.findings
        )


# ---------------------------------------------------------------------------
# Facets 3 and 4 - the two file-level states, reachable only through the read
# ---------------------------------------------------------------------------


@given(state=st.sampled_from(("absent-file", "not-json")))
def test_an_unreadable_declared_registry_is_non_passing_and_names_the_path(
    state: str, tree: Path
) -> None:
    """R9.10 + I-7: a file that cannot be read holds no validated entry, and says so.

    These two states are reachable only through the reading path, which is why they had
    no assertion before: ``registry_status`` takes a payload, so an absent file and a
    file of HTML both arrived as ``None`` and were indistinguishable from "no injection".
    The detail must name the resolved path, because "no entry is landed" and "the file
    the declaration names is not there" are different repairs.

    **Validates: Requirements 9.10**
    """
    claim = RecordDraft(spec="alpha-spec", task_id="9.1", checked=True, text=CLAIM_TEXTS[0])
    write_records(tree, [claim])
    path = write_registry(tree, state)

    payload, problem = read_registry(path)
    assert payload is None
    assert problem
    assert path.name in problem

    report = evaluate(checkpoint_policy=ACTIVE, root=tree)
    assert report.outcome is ClaimOutcome.FAIL
    assert report.exit_code == 1
    assert report.registry_state == "missing"
    assert report.unlanded
    assert any(path.name in problem for problem in report.registry_problems)


# ---------------------------------------------------------------------------
# Facet 5 - the read follows the declaration, not a constant bound at import
# ---------------------------------------------------------------------------


@given(drafts=record_drafts())
def test_the_verdict_comes_from_the_declared_registry_and_not_the_committed_one(
    drafts: list[RecordDraft], tree: Path
) -> None:
    """R9.10: the gate reads the registry it is TOLD about.

    The committed registry is a placeholder -- asserted here, read and never written --
    so a gate resolving a module-level constant would report FAIL for every checked
    claim. The injected registry holds a validated entry, so the only verdict consistent
    with the declaration being honoured is PASS. This is the assertion that fails on the
    pre-repair code, in the fail-open direction as well as the fail-closed one.

    **Validates: Requirements 9.10**
    """
    committed = json.loads((ROOT / POLICY.registry_file).read_text(encoding="utf-8"))
    assert (
        registry_status(committed, name=NAME, coverage_floor=FLOOR).ok is False
    ), "the committed registry has landed; facet 5's contrast is no longer a contrast"

    write_records(tree, drafts)
    write_registry(tree, LANDED_STATE)

    report = evaluate(checkpoint_policy=ACTIVE, root=tree)
    assert report.registry_file == INJECTED_REGISTRY_FILE
    assert report.registry_state == "populated"
    assert report.outcome is ClaimOutcome.PASS
    assert report.exit_code == 0
    assert report.unlanded == ()

    # And the converse over the same tree: swap only the registry contents and the same
    # records now fail, so the verdict tracks the declared file's state and nothing else.
    write_registry(tree, "placeholder")
    swapped = evaluate(checkpoint_policy=ACTIVE, root=tree)
    assert swapped.registry_state == "placeholder"
    checked_claims = [
        draft for draft in drafts if draft.checked and is_claim_text(draft.text)
    ]
    if checked_claims:
        assert swapped.outcome is ClaimOutcome.FAIL
        assert len(swapped.unlanded) == len(checked_claims)
    else:
        assert swapped.outcome is ClaimOutcome.PASS
        assert swapped.unlanded == ()
