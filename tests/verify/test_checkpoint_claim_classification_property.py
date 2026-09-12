"""Property-based test for honest published-checkpoint claim classification (E5.2).

Feature: purpose-achievement-audit, Property 17: Checkpoint claims are classified honestly

    *For any* published-checkpoint registry payload and sidecar, the check reports
    exactly one of absent, smoke, or real with a distinguishing detail; reports ``SKIP``
    under its registered identifier while no validated non-placeholder entry exists;
    exits non-zero when held-out ``coverage_p90`` is below the declared floor or a
    recorded ``final_crps`` deviates from its recompute beyond tolerance, reporting
    measured and expected values; and fails naming any task record that asserts a landed
    entry the registry does not hold.

Subjects, and which surface each test drives
--------------------------------------------

``scripts/audit/published_checkpoint_truth.py`` deliberately exposes **two projections
over one set of clause helpers**:

* :func:`~scripts.audit.published_checkpoint_truth.assess` - the hardened six-clause
  gate (``policy``, ``registry``, ``fetch``, ``classification``, ``coverage``,
  ``sha-pin``, ``crps-recompute``), outcomes ``pass``/``fail``/``skip``/``unavailable``,
  exit codes ``0``/``1``/``2``/``2``. **This is the subject of this file.**
* :func:`~scripts.audit.published_checkpoint_truth.evaluate` - the narrower legacy probe
  C46 calls, whose ``ok``/``fail``/``skip`` triad is already pinned by
  ``tests/verify/test_published_checkpoint_gate_property.py`` (Property 16). Not touched
  here.

``scripts/audit/task_claim_truth.py`` exposes the pure
:func:`~scripts.audit.task_claim_truth.judge` seam - no filesystem, no network - which is
what the R3.6 half of this property drives.

What the two existing tests already cover, and what is left to this one
----------------------------------------------------------------------

``test_published_checkpoint_gate_property.py`` (Property 16) covers the **legacy triad on
``evaluate()``**: with the registry populated and the remote reachable, ``ok`` iff
non-smoke (by the sidecar flag alone) AND coverage at-or-above the floor AND the recorded
sha appears in the published version. It never sees ``assess()``, so it never sees the
three-way classification, the ``indeterminate`` state, the ``final_crps`` recompute, the
local-substitution refusal, the four-state outcome vocabulary, or the exit codes.

``test_published_checkpoint_registry.py`` covers the **record schema and the serving
path** by example: ``validate_entry`` / ``registry_status`` over a well-formed record and
one broken key at a time, the committed file being an honest placeholder, and a
locally-published artifact loading non-degraded through ``ModelRegistry`` ->
``load_serving_model`` (transport and adapter only, per R3.8). It never reaches the
classification, the coverage comparison's reporting obligation, the recompute, or the
refusal.

This file asserts the uncovered part, and only that:

1. the three-way **absent / smoke / real** classification is *total* and each class is
   told apart by a distinguishing detail - a smoke artifact is never reported real, and
   an unmarked artifact is ``indeterminate`` and is never promoted (R3.1, R3.4);
2. the ``coverage_p90`` comparison reports **both** the measured value and the floor on
   *every* branch, including the branch where nothing was measured (R3.3);
3. a ``final_crps`` recompute that cannot be performed is ``unavailable`` and never a
   pass, while a recompute that *can* be performed decides ``pass``/``fail`` on the
   declared allowance (R3.9);
4. an unfetchable recorded sha is ``unavailable`` and **names the local candidate it
   REFUSED** to substitute (R3.7 via the ``fetch`` clause);
5. a task record marked complete asserting a landed registry entry **FAILs naming the
   record** while the registry holds no validated non-placeholder entry (R3.6).

Why a property and not examples. The audit's finding is not "one sidecar was
misclassified"; it is that the space of (record, artifact) pairs contains states the gate
had no verdict for, and that silence read as a pass. Totality over that space is the
claim, so it has to be quantified over the space. The expected classification, the
expected coverage verdict, and the expected recompute are all restated here from the raw
fields - the test states the rule rather than echoing the gate's branch order.

Every floor, marker, tolerance, filename template and claim pattern is read from
``infrastructure/quality/checkpoint-truth.yaml`` through the parsed
:class:`~scripts.audit.published_checkpoint_truth.CheckpointPolicy` (AD-13). There is no
threshold literal in this file.

I-0 and $0. Nothing is trained, built, or fetched. ``assess()`` takes an injectable
``fetch_sidecar=``, ``registry=``, ``checkpoint_policy=``, ``root=`` and ``env=``
precisely so the whole gate can be driven with no socket; every example writes at most
one small JSON file into a module-scoped ``tmp_path`` and the committed
``published_checkpoints.json`` is read but never written. Not slow-marked, because
nothing here touches the network.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 3.1, 3.3, 3.4, 3.6, 3.9**
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from scripts.audit.published_checkpoint_truth import (
    POLICY_FILE,
    REQUIRED_ENTRY_KEYS,
    ROOT,
    ArtifactClass,
    CheckpointPolicy,
    Clause,
    Outcome,
    RegistryStatus,
    assess,
    classify,
    compare_coverage,
    policy,
    recompute_final_crps,
    refused_local_candidates,
    registry_status,
    validate_entry,
)
from scripts.audit.task_claim_truth import (
    RULES,
    ClaimOutcome,
    TaskRecord,
    judge,
)
from scripts.audit.task_claim_truth import (
    evaluate as evaluate_task_claims,
)

if TYPE_CHECKING:
    from scripts.audit.published_checkpoint_truth import (
        CoverageFloorPolicy,
        CrpsTolerancePolicy,
    )

# ---------------------------------------------------------------------------
# Everything below is read from the committed policy. No threshold literals.
# ---------------------------------------------------------------------------

POLICY: Final[CheckpointPolicy] = policy()
SOURCE: Final = POLICY.source
MARKERS: Final = POLICY.classification
FLOOR: Final[CoverageFloorPolicy] = POLICY.floors.coverage_p90
TOLERANCE: Final[CrpsTolerancePolicy] = POLICY.tolerances.final_crps
NAME: Final[str] = POLICY.serving_name
FLAG: Final[str] = MARKERS.smoke.sidecar_flag
LEVELS: Final[tuple[float, ...]] = TOLERANCE.quantile_levels
SIDECAR_FILENAME: Final[str] = SOURCE.sidecar_filename.format(name=NAME)

#: Every declared version prefix, either marker set. An "unmarked" artifact is one whose
#: version starts with none of these, so the strategy filters against exactly this set
#: rather than against a hand-picked string.
DECLARED_PREFIXES: Final[tuple[str, ...]] = (
    *MARKERS.smoke.version_prefixes,
    *MARKERS.real.version_prefixes,
)

#: The committed registry payload, read (never written) so the "placeholder" state under
#: test is the real committed one rather than a re-authored imitation of it.
COMMITTED_REGISTRY: Final[Mapping[str, Any]] = json.loads(
    (ROOT / POLICY.registry_file).read_text(encoding="utf-8")
)

#: The full outcome vocabulary. Totality is asserted against this set: an outcome outside
#: it would mean the gate has a state this property does not describe.
OUTCOMES: Final[frozenset[Outcome]] = frozenset(Outcome)
#: I-7: only PASS is a pass. A SKIP is not a PASS and neither is UNAVAILABLE.
NON_PASSING: Final[frozenset[Outcome]] = OUTCOMES - {Outcome.PASS}

#: The exit code each outcome must carry, restated here rather than imported.
EXPECTED_EXIT: Final[dict[Outcome, int]] = {
    Outcome.PASS: 0,
    Outcome.FAIL: 1,
    Outcome.SKIP: 2,
    Outcome.UNAVAILABLE: 2,
}

#: Sentinel: the key is absent from the sidecar entirely, as opposed to present-and-null.
_MISSING: Final[Any] = object()

#: Values that are *not* the boolean smoke flag. ``1 is True`` is false in Python, so an
#: integral 1 must not read as a smoke declaration - only a literal ``true`` may.
NON_TRUE_FLAGS: Final[tuple[Any, ...]] = (False, None, _MISSING, 1, "true", "yes")


# ---------------------------------------------------------------------------
# Independent restatements of the rules under test
# ---------------------------------------------------------------------------


def expected_class(sidecar: Mapping[str, Any] | None) -> ArtifactClass:
    """The classification R3.1/R3.4 mandate, recomputed from the raw sidecar fields.

    Written out rather than imported, so the test compares two implementations of the
    same rule. Smoke is decided before real on purpose: that ordering *is* the "a smoke
    artifact is never reported real" obligation.
    """
    if sidecar is None:
        return ArtifactClass.ABSENT
    if sidecar.get(FLAG) is True:
        return ArtifactClass.SMOKE
    version = str(sidecar.get("version", ""))
    if any(version.startswith(prefix) for prefix in MARKERS.smoke.version_prefixes):
        return ArtifactClass.SMOKE
    if any(version.startswith(prefix) for prefix in MARKERS.real.version_prefixes):
        return ArtifactClass.REAL
    return ArtifactClass.INDETERMINATE


def expected_coverage_holds(raw: Any) -> bool:
    """R3.3's comparison, restated: a finite measurement at or above the committed floor.

    A boolean is not a number here, and neither is a numeric string: an artifact that
    declares no usable held-out coverage is uncalibrated *as published*.
    """
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return False
    return float(raw) >= FLOOR.value


def pinball_mean(errors: Sequence[float], level: float) -> float:
    """Mean pinball loss at one quantile level - the training loss's own definition."""
    total = 0.0
    for error in errors:
        total += level * error if error >= 0.0 else (level - 1.0) * error
    return total / len(errors)


def expected_crps(
    horizons: Mapping[str, tuple[Sequence[Sequence[float]], Sequence[float]]],
    levels: Sequence[float],
) -> float:
    """Mean pinball loss over the quantile levels, then the mean over horizons.

    Summed in sorted-horizon order, matching the subject, so the two floats agree to
    within representation noise rather than only to within the declared tolerance.
    """
    per_horizon: list[float] = []
    for name in sorted(horizons):
        predictions, actuals = horizons[name]
        per_level = [
            pinball_mean(
                [actual - row[index] for row, actual in zip(predictions, actuals, strict=True)],
                level,
            )
            for index, level in enumerate(levels)
        ]
        per_horizon.append(sum(per_level) / len(per_level))
    return sum(per_horizon) / len(per_horizon)


def is_claim(text: str) -> bool:
    """R3.6's both-halves rule, restated: an assertion pattern **and** a subject marker.

    Both halves are required so a record that merely *discusses* the registry (this
    spec's own task 10.8, and this very file) is not swept up as a claim about it.
    """
    matched = any(
        re.compile(declared.pattern, re.IGNORECASE).search(text) is not None
        for declared in POLICY.task_claims.assertion_patterns
    )
    lowered = text.lower()
    mentioned = any(marker.lower() in lowered for marker in POLICY.task_claims.subject_markers)
    return matched and mentioned


# ---------------------------------------------------------------------------
# Building sidecars and registry records
# ---------------------------------------------------------------------------


def set_dotted(payload: dict[str, Any], dotted: str, value: Any) -> None:
    """Write *value* at the policy's dotted read path, creating intermediate mappings."""
    parts = dotted.split(".")
    cursor: dict[str, Any] = payload
    for part in parts[:-1]:
        nested = cursor.get(part)
        if not isinstance(nested, dict):
            nested = {}
            cursor[part] = nested
        cursor = nested
    cursor[parts[-1]] = value


def build_sidecar(
    *,
    version: str,
    flag: Any = _MISSING,
    coverage: Any = _MISSING,
    heldout: Any = _MISSING,
) -> dict[str, Any]:
    """A published serving sidecar carrying only the fields the caller asked for."""
    sidecar: dict[str, Any] = {"version": version, "arch": {}}
    if flag is not _MISSING:
        sidecar[FLAG] = flag
    if coverage is not _MISSING:
        set_dotted(sidecar, FLOOR.sidecar_path, coverage)
    if heldout is not _MISSING:
        sidecar[TOLERANCE.sidecar_block] = heldout
    return sidecar


def heldout_rows(count: int) -> tuple[list[list[float]], list[float]]:
    """A held-out block whose pinball loss is small, positive, and level-symmetric.

    Predictions straddle the actual by one unit per level, so the recompute is stable
    across any declared level count rather than assuming three quantiles.
    """
    actuals = [float(index) for index in range(count)]
    centre = (len(LEVELS) - 1) / 2.0
    predictions = [
        [actual + (index - centre) for index in range(len(LEVELS))] for actual in actuals
    ]
    return predictions, actuals


def flat_heldout(
    predictions: Sequence[Sequence[float]],
    actuals: Sequence[float],
    *,
    declare_levels: bool,
) -> dict[str, Any]:
    """The single-horizon shape the policy accepts, reported under the horizon name ``*``.

    **The two bound lists were added in session 9 (task 18.1/18.2) and this is a
    PRECONDITION correction, not an assertion weakening.** ``assess`` gained
    ``Clause.COVERAGE_RECOMPUTE``, which recomputes empirical coverage from the published
    actuals against the published **conformal-adjusted** bounds and reports
    ``UNAVAILABLE`` when the block is absent or shorter than the committed minimum. A
    fixture carrying ``predictions`` and ``actuals`` alone therefore cannot reach ``PASS``
    at all -- so without these two lists the three PASS-expecting properties in this file
    would be asserting against an artifact the gate now, correctly, refuses.

    The standard got **stricter**, which is the test R2.10 turns on: the gate demands a
    recomputable block where it previously accepted a recorded number, and this fixture
    now supplies one. The bounds bracket every actual by construction, so the recomputed
    coverage is ``1.0`` and lands above the ``0.85`` floor -- the PASS case is genuine
    rather than tolerated. This is same-commit coupling 3: a schema change and every
    fixture that carries it.
    """
    rows = [list(row) for row in predictions]
    values = list(actuals)
    block: dict[str, Any] = {
        "predictions": rows,
        "actuals": values,
        # The conformal-adjusted 90% band, NOT the raw 80% quantile span the declared
        # `quantile_levels` [0.1, 0.5, 0.9] describe. INV-DP-002 is about the adjusted
        # band, and conflating the two is the distinction task 18.1 names explicitly.
        "lower_90": [value - 1.0 for value in values],
        "upper_90": [value + 1.0 for value in values],
    }
    if declare_levels:
        block["quantile_levels"] = list(LEVELS)
    return block


#: One clean, recomputable held-out block plus the value a recompute must land on. Built
#: once because the classification and fetch properties vary the *artifact class*, not
#: the calibration evidence.
CLEAN_PREDICTIONS, CLEAN_ACTUALS = heldout_rows(TOLERANCE.min_samples)
CLEAN_HELDOUT: Final[dict[str, Any]] = flat_heldout(
    CLEAN_PREDICTIONS, CLEAN_ACTUALS, declare_levels=True
)
CLEAN_CRPS: Final[float] = expected_crps({"*": (CLEAN_PREDICTIONS, CLEAN_ACTUALS)}, LEVELS)


def landed_entry(
    *,
    repo: str,
    sha: str,
    coverage: float,
    final_crps: float,
    trained_at: str,
    rows: int,
) -> dict[str, Any]:
    """A registry record of the shape the runbook's step-5 output produces.

    Keyed by :data:`REQUIRED_ENTRY_KEYS` so a key added to the policy's required set
    cannot silently stop being supplied here.
    """
    entry: dict[str, Any] = {
        "repo": repo,
        "sha": sha,
        "coverage_p90": coverage,
        "final_crps": final_crps,
        "trained_at": trained_at,
        "rows": rows,
    }
    assert set(entry) == set(REQUIRED_ENTRY_KEYS)
    # Every record this file calls "landed" really is one, so a `populated` registry
    # state under test is populated rather than merely asserted to be.
    assert validate_entry(entry, coverage_floor=FLOOR.value) == []
    return entry


#: A deterministic, valid landed record, for the states that need "the registry holds a
#: validated non-placeholder entry" without varying it.
LANDED: Final[dict[str, Any]] = landed_entry(
    repo="example-owner/synapse-demand-prophet",
    sha="a1b2c3d",
    coverage=FLOOR.value,
    final_crps=CLEAN_CRPS,
    trained_at=f"{date(2026, 6, 1).isoformat()}T12:00:00Z",
    rows=1,
)


# ---------------------------------------------------------------------------
# Injected fetchers - the seam that keeps this file off the network
# ---------------------------------------------------------------------------

Fetcher = Callable[[str, str], str]


def sidecar_fetcher(directory: Path, payload: Mapping[str, Any], *, expect_repo: str) -> Fetcher:
    """A ``fetch_sidecar=`` that serves *payload* and asserts what was asked for."""

    def fetch(repo_id: str, filename: str) -> str:
        # The gate must ask the recorded repo for the serving-name sidecar, nothing else.
        assert repo_id == expect_repo, repo_id
        assert filename == SIDECAR_FILENAME, filename
        path = directory / filename
        path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
        return str(path)

    return fetch


def unfetchable(directory: Path, mode: str) -> Fetcher:
    """A ``fetch_sidecar=`` standing in for a recorded sha that cannot be resolved.

    All three modes surface through the gate's own fetch-failure path (an unreadable or
    non-object payload), so no private exception type has to be reached into.
    """

    def fetch(repo_id: str, filename: str) -> str:
        assert repo_id
        if mode == "absent":
            return str(directory / "never-written" / filename)
        path = directory / f"{mode}-{filename}"
        if mode == "not-json":
            path.write_text("<html>404</html>", encoding="utf-8")
        else:  # "not-object": valid JSON, wrong shape
            path.write_text(json.dumps([]), encoding="utf-8")
        return str(path)

    return fetch


def never_fetched(repo_id: str, filename: str) -> str:
    """A ``fetch_sidecar=`` that fails the test if the gate reaches for the remote."""
    message = f"the gate must not fetch {repo_id}/{filename} for an unlanded record"
    raise AssertionError(message)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_HEX = "0123456789abcdef"
_WORD = "abcdefghijklmnopqrstuvwxyz0123456789-"

#: A checkpoint sha of the shape ``validate_entry`` accepts.
shas: Final[st.SearchStrategy[str]] = st.text(alphabet=_HEX, min_size=7, max_size=12)

#: An ``owner/name`` repo id.
repos: Final[st.SearchStrategy[str]] = st.builds(
    lambda owner, name: f"{owner}/{name}",
    st.text(alphabet=_WORD, min_size=1, max_size=10),
    st.text(alphabet=_WORD, min_size=1, max_size=10),
)

trained_ats: Final[st.SearchStrategy[str]] = st.dates(
    min_value=date(2024, 1, 1), max_value=date(2030, 12, 31)
).map(lambda day: f"{day.isoformat()}T12:00:00Z")

#: A version prefix that matches none of the declared marker prefixes, so the artifact
#: is *unmarked* rather than smoke or real.
unmarked_prefixes: Final[st.SearchStrategy[str]] = st.one_of(
    st.just(""),
    st.text(alphabet="ghijklmnpqrtuvwxyz", min_size=1, max_size=4),
).filter(lambda prefix: not any(prefix.startswith(p) for p in DECLARED_PREFIXES))

#: A coverage measurement, weighted onto the floor boundary and onto the values that are
#: syntactically present but not usable numbers.
coverages: Final[st.SearchStrategy[Any]] = st.one_of(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.sampled_from(
        (
            None,
            _MISSING,
            True,
            "0.9",
            0.0,
            1.0,
            FLOOR.value,
            FLOOR.value - 1e-9,
            FLOOR.value + 1e-9,
        )
    ),
)


@dataclass(frozen=True)
class ArtifactCase:
    """One (record, artifact) pair plus the class it must be told apart as."""

    sidecar: dict[str, Any]
    entry: dict[str, Any]
    expected: ArtifactClass


@st.composite
def artifact_cases(draw: st.DrawFn) -> ArtifactCase:
    """Draw a landed record and a fetchable artifact of each of the three classes.

    Every clause other than ``classification`` is held clean - coverage at or above the
    floor, the recorded sha present in the published version, a recomputable
    ``final_crps`` - so the artifact class alone decides the verdict. That is what makes
    "a smoke artifact is never reported real" an assertion about the gate's verdict and
    not only about a string it printed.
    """
    kind = draw(st.sampled_from(("flagged-smoke", "prefixed-smoke", "real", "unmarked")))
    sha = draw(shas)
    coverage = draw(
        st.floats(min_value=FLOOR.value, max_value=1.0, allow_nan=False, allow_infinity=False)
    )

    if kind == "flagged-smoke":
        prefix = draw(st.one_of(st.sampled_from(DECLARED_PREFIXES), unmarked_prefixes))
        flag: Any = True
    elif kind == "prefixed-smoke":
        prefix = draw(st.sampled_from(MARKERS.smoke.version_prefixes))
        flag = draw(st.sampled_from(NON_TRUE_FLAGS))
    elif kind == "real":
        prefix = draw(st.sampled_from(MARKERS.real.version_prefixes))
        flag = draw(st.sampled_from(NON_TRUE_FLAGS))
    else:
        prefix = draw(unmarked_prefixes)
        flag = draw(st.sampled_from(NON_TRUE_FLAGS))

    # The recorded sha is a suffix of the version, so the `sha-pin` clause always holds
    # and cannot be what a classification failure is actually reporting.
    version = f"{prefix}{sha}"
    assume(sha in version)

    sidecar = build_sidecar(
        version=version, flag=flag, coverage=coverage, heldout=CLEAN_HELDOUT
    )
    entry = landed_entry(
        repo=draw(repos),
        sha=sha,
        coverage=coverage,
        final_crps=CLEAN_CRPS,
        trained_at=draw(trained_ats),
        rows=draw(st.integers(min_value=1, max_value=2_000_000)),
    )
    return ArtifactCase(sidecar=sidecar, entry=entry, expected=expected_class(sidecar))


@dataclass(frozen=True)
class RecordDraft:
    """One generated task record, before it becomes a :class:`TaskRecord`."""

    spec: str
    task_id: str
    checked: bool
    text: str


#: Claim text, drawn from the policy's own quotations of the records it was written
#: against (``task_claims.must_resolve[].note``). Sourcing the text from the policy is
#: what keeps this file free of an assertion-pattern literal.
CLAIM_TEXTS: Final[tuple[str, ...]] = tuple(
    entry.note.strip() for entry in POLICY.task_claims.must_resolve
)

record_texts: Final[st.SearchStrategy[str]] = st.one_of(
    st.sampled_from(CLAIM_TEXTS),
    # A record that names the subject but asserts nothing about it - not a claim.
    st.sampled_from(POLICY.task_claims.subject_markers),
    # Prose that neither asserts nor names - not a claim.
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=48),
)


@st.composite
def record_drafts(draw: st.DrawFn) -> list[RecordDraft]:
    """Draw a set of task records with distinct (spec, task id) keys."""
    return draw(
        st.lists(
            st.builds(
                RecordDraft,
                spec=st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=12),
                task_id=st.builds(
                    lambda major, minor: f"{major}" if minor is None else f"{major}.{minor}",
                    st.integers(min_value=1, max_value=40),
                    st.one_of(st.none(), st.integers(min_value=1, max_value=20)),
                ),
                checked=st.booleans(),
                text=record_texts,
            ),
            min_size=1,
            max_size=6,
            unique_by=lambda draft: (draft.spec, draft.task_id),
        )
    )


def as_task_records(drafts: Sequence[RecordDraft]) -> tuple[TaskRecord, ...]:
    """Materialise generated drafts as the records ``judge()`` consumes."""
    return tuple(
        TaskRecord(
            spec=draft.spec,
            task_id=draft.task_id,
            checked=draft.checked,
            title=draft.text,
            body=(),
            source=f"{POLICY.task_claims.specs_dir}/{draft.spec}/"
            f"{POLICY.task_claims.tasks_filename}",
            line=index + 1,
        )
        for index, draft in enumerate(drafts)
    )


#: The four registry states R3.1 and R3.6 both partition over, each built through the
#: real ``registry_status`` rather than by asserting a status string into existence.
REGISTRY_PAYLOADS: Final[dict[str, Mapping[str, Any]]] = {
    "placeholder": COMMITTED_REGISTRY,
    "missing": {},
    "invalid": {NAME: {}},
    "populated": {NAME: LANDED},
}


def status_for(state: str) -> RegistryStatus:
    """The :class:`RegistryStatus` for one named registry state."""
    return registry_status(
        dict(REGISTRY_PAYLOADS[state]), name=NAME, coverage_floor=FLOOR.value
    )


#: A policy whose anti-vacuity ``must_resolve`` list is empty, so the R3.6 property can
#: quantify over *generated* records without the committed-record clause firing. The
#: committed list is asserted separately, where it belongs.
JUDGE_POLICY: Final[CheckpointPolicy] = POLICY.model_copy(
    update={"task_claims": POLICY.task_claims.model_copy(update={"must_resolve": ()})}
)


@pytest.fixture(scope="module")
def hub(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A scratch dir standing in for the zero-cost source's cache (no network)."""
    return tmp_path_factory.mktemp("checkpoint_claims_hub")


@pytest.fixture(scope="module")
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A scratch tree root carrying a *present* local candidate, so the refusal is real.

    ``ModelRegistry._resolve_checkpoint_path`` prefers a local checkpoint over the
    remote, which is exactly the evidence swap R3.7 forbids. Placing the pair here means
    the gate is refusing something that exists rather than reporting an absence.
    """
    root = tmp_path_factory.mktemp("checkpoint_claims_tree")
    candidates = root / SOURCE.local_candidate_dir
    candidates.mkdir(parents=True, exist_ok=True)
    for template in (SOURCE.checkpoint_filename, SOURCE.sidecar_filename):
        (candidates / template.format(name=NAME)).write_text(
            "locally built by the CI smoke job - never a published artifact\n",
            encoding="utf-8",
        )
    return root


# ---------------------------------------------------------------------------
# R3.1, R3.4 - the three-way classification is total and told apart
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 17: Checkpoint claims are classified honestly
@given(case=artifact_cases())
def test_the_three_way_classification_is_total_and_each_class_is_told_apart(
    case: ArtifactCase, hub: Path, tree: Path
) -> None:
    """R3.1, R3.4: exactly one of absent / smoke / real, each with a deciding detail.

    Totality first, because a gate that quietly promoted anything it could not classify
    would satisfy every naming assertion below while asserting nothing - which is the
    failure mode the audit found. With every other clause held clean, the class alone
    decides the verdict, so ``SMOKE -> FAIL``, ``INDETERMINATE -> UNAVAILABLE`` and
    ``REAL -> PASS`` are statements about the gate's consequence rather than about its
    prose.

    **Validates: Requirements 3.1, 3.4**
    """
    repo = str(case.entry["repo"])
    report = assess(
        checkpoint_policy=POLICY,
        registry={NAME: case.entry},
        fetch_sidecar=sidecar_fetcher(hub, case.sidecar, expect_repo=repo),
        root=tree,
        env={},
    )

    # Total: one class, drawn from the declared vocabulary, agreeing with the rule.
    assert report.classification in set(ArtifactClass)
    assert report.classification is case.expected
    assert report.registry_state == "populated"
    assert report.outcome in OUTCOMES
    assert report.exit_code == EXPECTED_EXIT[report.outcome]

    # The clause helper and the gate's projection of it agree, so the verdict below is
    # about the same classification a caller of `classify` would get.
    direct_class, direct_detail = classify(case.sidecar, MARKERS)
    assert direct_class is case.expected
    assert direct_detail.startswith(f"{case.expected.value.upper()}:")

    # Told apart: the detail leads with the class it decided, and names the marker that
    # decided it, so a reader distinguishes the three without opening the gate source.
    detail = report.classification_detail
    assert detail.startswith(f"{case.expected.value.upper()}:")
    assert FLAG in detail
    assert repr(str(case.sidecar["version"])) in detail

    classification_findings = [
        finding for finding in report.findings if finding.clause is Clause.CLASSIFICATION
    ]

    if case.expected is ArtifactClass.SMOKE:
        # A smoke artifact is never reported as a real one, and never as a pass.
        assert report.classification is not ArtifactClass.REAL
        assert report.outcome is Outcome.FAIL
        assert report.exit_code == 1
        assert [finding.outcome for finding in classification_findings] == [Outcome.FAIL]
        assert classification_findings[0].requirement == "R3.4"
        assert classification_findings[0].detail == detail
    elif case.expected is ArtifactClass.INDETERMINATE:
        # An unmarked artifact is not promoted: it is UNAVAILABLE, which is not a pass.
        assert report.classification is not ArtifactClass.REAL
        assert report.outcome is Outcome.UNAVAILABLE
        assert report.outcome in NON_PASSING
        assert report.exit_code == 2
        assert [finding.outcome for finding in classification_findings] == [
            Outcome.UNAVAILABLE
        ]
        assert classification_findings[0].requirement == "R3.1"
        # It names both marker sets it failed to match, so the repair is obvious.
        for prefix in DECLARED_PREFIXES:
            assert repr(prefix) in detail
    else:
        assert case.expected is ArtifactClass.REAL
        assert classification_findings == []
        assert report.outcome is Outcome.PASS
        assert report.exit_code == 0
        assert report.findings == ()
        assert NAME in report.detail and repo in report.detail

    # The persisted payload is canonical and round-trips the class it reported.
    payload = report.canonical_json()
    document = json.loads(payload)
    assert document["classification"] == case.expected.value
    assert payload == json.dumps(document, sort_keys=True, separators=(",", ":"))


# Feature: purpose-achievement-audit, Property 17: Checkpoint claims are classified honestly
@given(state=st.sampled_from(("placeholder", "missing", "invalid")))
def test_a_registry_holding_no_validated_entry_is_classified_absent_and_never_passes(
    state: str, tree: Path
) -> None:
    """R3.1: while nothing is landed the gate is SKIP / UNAVAILABLE, never a pass.

    The absent class must be told apart from the other two, so the detail says the
    artifact was never fetched rather than that it was judged. And the gate must not
    reach for the remote at all: ``never_fetched`` fails the test if it does, which is
    what makes "absent" the absence of evidence rather than an unread answer.

    **Validates: Requirements 3.1**
    """
    status = status_for(state)
    assert status.status == state
    assert status.ok is False

    report = assess(
        checkpoint_policy=POLICY,
        registry=dict(REGISTRY_PAYLOADS[state]),
        fetch_sidecar=never_fetched,
        root=tree,
        env={},
    )

    expected = {
        "placeholder": Outcome.SKIP,
        "missing": Outcome.UNAVAILABLE,
        "invalid": Outcome.FAIL,
    }[state]
    assert report.outcome is expected
    assert report.outcome in NON_PASSING
    assert report.exit_code == EXPECTED_EXIT[expected]
    assert report.exit_code != 0

    assert report.registry_state == state
    assert report.classification is ArtifactClass.ABSENT
    assert report.classification_detail.startswith(f"{ArtifactClass.ABSENT.value.upper()}:")
    # Nothing was measured, so nothing is reported as measured.
    assert report.coverage is None
    assert report.crps is None
    assert report.version is None

    registry_findings = [
        finding for finding in report.findings if finding.clause is Clause.REGISTRY
    ]
    assert [finding.outcome for finding in registry_findings] == [expected]
    assert POLICY.registry_file in registry_findings[0].detail
    assert NAME in registry_findings[0].detail
    assert state in registry_findings[0].detail


# ---------------------------------------------------------------------------
# R3.3 - the coverage comparison reports BOTH numbers on every branch
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 17: Checkpoint claims are classified honestly
@given(coverage=coverages, sha=shas, repo=repos)
def test_the_coverage_comparison_reports_both_the_measured_value_and_the_floor(
    coverage: Any, sha: str, repo: str, hub: Path, tree: Path
) -> None:
    """R3.3: measured *and* floor, on the pass branch, the fail branch, and the null one.

    The audit's complaint about floor gates was that a red result said nothing about
    what was compared against what. So the obligation is the reporting, not only the
    verdict: on every branch the detail has to carry both numbers, including the branch
    where the artifact declared no held-out coverage at all.

    **Validates: Requirements 3.3**
    """
    holds = expected_coverage_holds(coverage)
    sidecar = build_sidecar(
        version=f"{MARKERS.real.version_prefixes[0]}{sha}",
        coverage=coverage,
        heldout=CLEAN_HELDOUT,
    )

    # The helper, directly: this is the surface that owes both numbers.
    comparison = compare_coverage(sidecar, FLOOR)
    assert comparison.holds is holds
    assert comparison.floor == FLOOR.value
    assert comparison.sidecar_path == FLOOR.sidecar_path
    assert str(FLOOR.value) in comparison.detail
    assert FLOOR.invariant in comparison.detail
    if holds:
        assert comparison.measured == float(coverage)
        assert str(comparison.measured) in comparison.detail
    else:
        # Either below the floor or not a usable number - both report what was seen.
        assert ("null" in comparison.detail) is (comparison.measured is None)
        if comparison.measured is not None:
            assert str(comparison.measured) in comparison.detail

    # The null branch is a branch: no artifact at all still reports the floor it would
    # have compared against.
    absent = compare_coverage(None, FLOOR)
    assert absent.measured is None
    assert absent.holds is False
    assert "null" in absent.detail
    assert str(FLOOR.value) in absent.detail

    # And through the whole gate: the comparison is surfaced, and decides the verdict.
    entry = landed_entry(
        repo=repo,
        sha=sha,
        coverage=FLOOR.value,
        final_crps=CLEAN_CRPS,
        trained_at=str(LANDED["trained_at"]),
        rows=1,
    )
    report = assess(
        checkpoint_policy=POLICY,
        registry={NAME: entry},
        fetch_sidecar=sidecar_fetcher(hub, sidecar, expect_repo=repo),
        root=tree,
        env={},
    )
    assert report.coverage is not None
    assert report.coverage.holds is holds
    assert report.coverage.detail == comparison.detail
    assert str(FLOOR.value) in report.coverage.detail

    coverage_findings = [
        finding for finding in report.findings if finding.clause is Clause.COVERAGE
    ]
    if holds:
        assert coverage_findings == []
        assert report.outcome is Outcome.PASS
    else:
        assert [finding.outcome for finding in coverage_findings] == [Outcome.FAIL]
        assert coverage_findings[0].requirement == "R3.3"
        assert report.outcome is Outcome.FAIL
        assert report.exit_code == 1
        assert str(FLOOR.value) in report.detail


# ---------------------------------------------------------------------------
# R3.9 - a recompute that cannot be performed is unavailable, never a pass
# ---------------------------------------------------------------------------

#: The ways a published sidecar can fail to support a recompute. Each is a real shape a
#: partially-published artifact takes, not a synthetic corruption.
UNRECOMPUTABLE: Final[tuple[str, ...]] = (
    "no-block",
    "block-not-object",
    "block-empty",
    "no-horizons",
    "length-mismatch",
    "value-not-a-number",
    "too-few-samples",
)


def unrecomputable_heldout(mode: str) -> Any:
    """The ``heldout`` value for one unrecomputable mode (``_MISSING`` = key absent)."""
    predictions, actuals = heldout_rows(TOLERANCE.min_samples)
    if mode == "no-block":
        return _MISSING
    if mode == "block-not-object":
        return [1, 2, 3]
    if mode == "block-empty":
        return {}
    if mode == "no-horizons":
        return {"horizons": {}}
    if mode == "length-mismatch":
        return {"predictions": [list(row) for row in predictions], "actuals": actuals[:-1]}
    if mode == "value-not-a-number":
        tainted: list[list[Any]] = [list(row) for row in predictions]
        tainted[0][0] = "not-a-number"
        return {"predictions": tainted, "actuals": list(actuals)}
    short = max(TOLERANCE.min_samples - 1, 1)
    return flat_heldout(predictions[:short], actuals[:short], declare_levels=False)


# Feature: purpose-achievement-audit, Property 17: Checkpoint claims are classified honestly
@given(mode=st.sampled_from(UNRECOMPUTABLE), sha=shas, repo=repos)
def test_a_final_crps_recompute_that_cannot_be_performed_is_unavailable_never_a_pass(
    mode: str, sha: str, repo: str, hub: Path, tree: Path
) -> None:
    """R3.9, I-7: a recorded number nobody recomputed is not evidence.

    Every clause other than ``crps-recompute`` is held clean, so the whole gate's outcome
    is the recompute's. UNAVAILABLE rather than FAIL is the honest verdict here - the
    number is not known to be wrong, it is not known at all - and UNAVAILABLE must never
    collapse into a pass.

    **Validates: Requirements 3.9**
    """
    sidecar = build_sidecar(
        version=f"{MARKERS.real.version_prefixes[0]}{sha}",
        coverage=FLOOR.value,
        heldout=unrecomputable_heldout(mode),
    )

    recompute = recompute_final_crps(sidecar, TOLERANCE, recorded=CLEAN_CRPS)
    assert recompute.outcome is Outcome.UNAVAILABLE
    assert recompute.outcome in NON_PASSING
    assert recompute.recomputed is None
    assert recompute.difference is None
    assert recompute.recorded == CLEAN_CRPS
    if mode == "too-few-samples":
        # It names the shortfall against the declared minimum, not just "too few".
        assert str(TOLERANCE.min_samples) in recompute.detail

    # A recorded value that is absent is equally unrecomputable, and says so.
    assert recompute_final_crps(sidecar, TOLERANCE, recorded=None).outcome is (
        Outcome.UNAVAILABLE
    )
    # As is an artifact that was never fetched.
    assert recompute_final_crps(None, TOLERANCE, recorded=CLEAN_CRPS).outcome is (
        Outcome.UNAVAILABLE
    )

    entry = landed_entry(
        repo=repo,
        sha=sha,
        coverage=FLOOR.value,
        final_crps=CLEAN_CRPS,
        trained_at=str(LANDED["trained_at"]),
        rows=1,
    )
    report = assess(
        checkpoint_policy=POLICY,
        registry={NAME: entry},
        fetch_sidecar=sidecar_fetcher(hub, sidecar, expect_repo=repo),
        root=tree,
        env={},
    )
    assert report.crps is not None
    assert report.crps.outcome is Outcome.UNAVAILABLE
    assert report.outcome is Outcome.UNAVAILABLE
    assert report.outcome in NON_PASSING
    assert report.exit_code == 2
    assert report.exit_code != 0

    crps_findings = [
        finding for finding in report.findings if finding.clause is Clause.CRPS_RECOMPUTE
    ]
    assert [finding.outcome for finding in crps_findings] == [Outcome.UNAVAILABLE]
    assert crps_findings[0].requirement == "R3.9"
    # The finding carries the recompute's own reason, unabridged, so the report says what
    # was missing rather than only that something was.
    assert crps_findings[0].detail == report.crps.detail
    if mode == "too-few-samples":
        assert str(TOLERANCE.min_samples) in crps_findings[0].detail
    else:
        assert TOLERANCE.sidecar_block in crps_findings[0].detail


# Feature: purpose-achievement-audit, Property 17: Checkpoint claims are classified honestly
@given(
    recorded=st.floats(min_value=0.0, max_value=4.0, allow_nan=False, allow_infinity=False),
    rows=st.integers(min_value=0, max_value=6),
    horizon_names=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=3),
        min_size=1,
        max_size=2,
        unique=True,
    ),
    declare_levels=st.booleans(),
    sha=shas,
    repo=repos,
)
def test_a_recompute_that_can_be_performed_decides_on_the_declared_allowance(
    recorded: float,
    rows: int,
    horizon_names: list[str],
    declare_levels: bool,
    sha: str,
    repo: str,
    hub: Path,
    tree: Path,
) -> None:
    """R3.9: the recompute is real - it recomputes, and it reports both numbers.

    The counterpart to the UNAVAILABLE property above: without this, "always
    UNAVAILABLE" would satisfy it. Here the recompute runs against an independently
    computed reference, and the verdict is the declared allowance
    ``max(absolute, relative * |recorded|)`` and nothing else. Examples within a hair of
    the allowance are assumed away so floating-point noise cannot decide the verdict.

    **Validates: Requirements 3.9**
    """
    count = TOLERANCE.min_samples + rows
    predictions, actuals = heldout_rows(count)
    horizons = {name: (predictions, actuals) for name in horizon_names}
    reference = expected_crps(horizons, LEVELS)

    allowance = TOLERANCE.allowance(recorded)
    assume(abs(abs(reference - recorded) - allowance) > 1e-6)
    expected_outcome = (
        Outcome.PASS if abs(reference - recorded) <= allowance else Outcome.FAIL
    )

    inner = flat_heldout(predictions, actuals, declare_levels=declare_levels)
    block: dict[str, Any] = (
        dict(inner)
        if len(horizon_names) == 1
        else {"horizons": {name: dict(inner) for name in horizon_names}}
    )
    if declare_levels:
        block["quantile_levels"] = list(LEVELS)

    sidecar = build_sidecar(
        version=f"{MARKERS.real.version_prefixes[0]}{sha}",
        coverage=FLOOR.value,
        heldout=block,
    )

    recompute = recompute_final_crps(sidecar, TOLERANCE, recorded=recorded)
    assert recompute.outcome is expected_outcome
    assert recompute.recomputed is not None
    assert recompute.recomputed == pytest.approx(reference, abs=1e-9)
    assert recompute.allowance == allowance
    assert recompute.samples == count * len(horizon_names)
    assert recompute.quantile_levels == LEVELS
    # It names the horizons it recomputed over; the flat single-horizon form is "*".
    assert recompute.horizons == (
        ("*",) if len(horizon_names) == 1 else tuple(sorted(horizon_names))
    )
    assert recompute.method == TOLERANCE.method
    # Both numbers, on both branches: recorded and recomputed, plus the allowance.
    assert str(recorded) in recompute.detail
    assert f"{recompute.recomputed:.6f}" in recompute.detail
    assert f"{allowance:.6f}" in recompute.detail

    entry = landed_entry(
        repo=repo,
        sha=sha,
        coverage=FLOOR.value,
        final_crps=recorded,
        trained_at=str(LANDED["trained_at"]),
        rows=1,
    )
    report = assess(
        checkpoint_policy=POLICY,
        registry={NAME: entry},
        fetch_sidecar=sidecar_fetcher(hub, sidecar, expect_repo=repo),
        root=tree,
        env={},
    )
    assert report.crps is not None
    assert report.crps.outcome is expected_outcome
    assert report.outcome is expected_outcome
    assert report.exit_code == EXPECTED_EXIT[expected_outcome]


# ---------------------------------------------------------------------------
# R3.7 - an unfetchable recorded sha names the local candidate it refused
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 17: Checkpoint claims are classified honestly
@given(mode=st.sampled_from(("absent", "not-json", "not-object")), sha=shas, repo=repos)
def test_an_unfetchable_recorded_sha_is_unavailable_and_names_the_candidate_it_refused(
    mode: str, sha: str, repo: str, hub: Path, tree: Path
) -> None:
    """R3.7, I-7: the gate refuses to resolve a local build in a published sha's place.

    A locally built pair *exists* under the injected tree root, so this is a refusal and
    not a report of absence. The gate must say so, name what it refused, and land on
    UNAVAILABLE - resolving the local artifact would certify the CI smoke build as the
    published model, which is the exact evidence swap R3.7 forbids.

    **Validates: Requirements 3.1, 3.4** (via the absent class) **and R3.7**
    """
    entry = landed_entry(
        repo=repo,
        sha=sha,
        coverage=FLOOR.value,
        final_crps=CLEAN_CRPS,
        trained_at=str(LANDED["trained_at"]),
        rows=1,
    )
    report = assess(
        checkpoint_policy=POLICY,
        registry={NAME: entry},
        fetch_sidecar=unfetchable(hub, mode),
        root=tree,
        env={},
    )

    assert report.outcome is Outcome.UNAVAILABLE
    assert report.outcome in NON_PASSING
    assert report.exit_code == 2
    assert report.exit_code != 0
    assert report.registry_state == "populated"

    # Nothing was fetched, so nothing was classified and nothing was measured.
    assert report.classification is ArtifactClass.ABSENT
    assert report.coverage is None
    assert report.crps is None
    assert report.version is None

    fetch_findings = [finding for finding in report.findings if finding.clause is Clause.FETCH]
    assert [finding.outcome for finding in fetch_findings] == [Outcome.UNAVAILABLE]
    finding = fetch_findings[0]
    assert finding.requirement == "R3.7"
    assert repr(sha) in finding.detail
    assert repo in finding.detail
    assert SIDECAR_FILENAME in finding.detail

    # The refusal is named, candidate by candidate, and the candidates really are there.
    expected_refused = refused_local_candidates(SOURCE, NAME, root=tree)
    assert report.refused_local_candidates == expected_refused
    assert expected_refused
    for candidate in expected_refused:
        assert candidate in finding.detail
        assert SOURCE.local_candidate_dir in candidate
        assert "(present)" in candidate
    # And it is named as a pinned policy decision rather than an incidental one.
    assert SOURCE.allow_local_substitution is False
    assert "allow_local_substitution" in finding.detail
    assert report.detail == finding.detail


def test_the_committed_policy_pins_the_two_flags_that_make_the_refusal_binding() -> None:
    """I-1 and R3.7: the refusal cannot be configured away.

    A single read of the committed policy - no gate execution. ``zero_cost`` false or
    ``allow_local_substitution`` true is itself a ``policy``-clause FAIL, so these two
    booleans are the reason the ``fetch`` clause above is a refusal rather than a
    preference.
    """
    assert SOURCE.zero_cost is True, POLICY_FILE
    assert SOURCE.allow_local_substitution is False, POLICY_FILE
    assert SOURCE.local_candidate_dir
    assert "{name}" in SOURCE.sidecar_filename
    assert "{name}" in SOURCE.checkpoint_filename


# ---------------------------------------------------------------------------
# R3.6 - a complete task record may not claim an entry the registry does not hold
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 17: Checkpoint claims are classified honestly
@given(drafts=record_drafts(), state=st.sampled_from(tuple(REGISTRY_PAYLOADS)))
def test_a_complete_task_record_claiming_a_landed_entry_fails_naming_the_record(
    drafts: list[RecordDraft], state: str
) -> None:
    """R3.6: FAIL naming the record, iff the record is checked and nothing is landed.

    Driven through the pure ``judge()`` seam with injected records, so the property does
    not depend on the committed tree (which is asserted separately, as the honest FAIL it
    is). Four things have to hold together for the rule to mean anything: a claim needs
    both halves of the definition, an unchecked claim is pending rather than false, a
    landed registry clears every claim, and the failure names the record precisely enough
    to find it.

    **Validates: Requirements 3.6**
    """
    records = as_task_records(drafts)
    status = status_for(state)
    report = judge(
        records,
        active=JUDGE_POLICY,
        registry=status,
        specs_dir=POLICY.task_claims.specs_dir,
        scanned=(),
        scan_problems=(),
    )

    expected_claims = tuple(record for record in records if is_claim(record.haystack()))
    expected_unlanded = (
        ()
        if status.ok
        else tuple(record.name for record in expected_claims if record.checked)
    )
    expected_pending = tuple(
        record.name for record in expected_claims if not record.checked
    )

    # Claim detection is the both-halves rule, and nothing wider.
    assert tuple(claim.name for claim in report.claims) == tuple(
        record.name for record in expected_claims
    )
    assert report.records_scanned == len(records)
    assert report.registry_state == state

    assert report.unlanded == expected_unlanded
    assert report.pending == expected_pending

    expected_outcome = ClaimOutcome.FAIL if expected_unlanded else ClaimOutcome.PASS
    assert report.outcome is expected_outcome
    assert report.exit_code == (1 if expected_unlanded else 0)

    findings = [finding for finding in report.findings if finding.rule == "unlanded-claim"]
    assert [finding.subject for finding in findings] == sorted(expected_unlanded)
    assert "unlanded-claim" in RULES

    for finding in findings:
        assert finding.outcome is ClaimOutcome.FAIL
        assert finding.requirement == "R3.6"
        # Named well enough to act on: file, line, spec, task id, the record's own words.
        record = next(item for item in expected_claims if item.name == finding.subject)
        assert record.source in finding.detail
        assert str(record.line) in finding.detail
        assert record.spec in finding.detail
        assert record.task_id in finding.detail
        assert record.title in finding.detail
        # And the registry state that made the claim false.
        assert JUDGE_POLICY.registry_file in finding.detail
        assert status.status in finding.detail
        assert NAME in finding.detail

    # A pending claim is never a finding: an open task asserting nothing yet is not a lie.
    assert not any(finding.subject in expected_pending for finding in report.findings)
    if status.ok:
        # The converse: a landed, validated entry clears every claim, which is what makes
        # the failures above the registry state biting rather than the text.
        assert report.outcome is ClaimOutcome.PASS
        assert report.unlanded == ()


def test_the_claim_scanner_goes_unavailable_when_it_stops_seeing_its_own_records() -> None:
    """R3.6 anti-vacuity: a scanner that matches nothing is not a passing scanner.

    Driven with the *committed* ``must_resolve`` list and an empty record set, so the
    clause that keeps this gate from silently becoming a no-op is exercised without
    touching the tree. UNAVAILABLE, not PASS - the split between "a task lies" and "the
    scanner went blind" is what tells an operator which repair to make.
    """
    assert POLICY.task_claims.must_resolve, POLICY_FILE

    report = judge(
        (),
        active=POLICY,
        registry=status_for("placeholder"),
        specs_dir=POLICY.task_claims.specs_dir,
    )

    assert report.outcome is ClaimOutcome.UNAVAILABLE
    assert report.exit_code == 2
    assert report.unlanded == ()
    unresolved = [finding for finding in report.findings if finding.rule == "unresolved-record"]
    assert len(unresolved) == len(POLICY.task_claims.must_resolve)
    for required, finding in zip(
        POLICY.task_claims.must_resolve, sorted(unresolved, key=lambda f: f.subject), strict=True
    ):
        assert required.spec in finding.subject
        assert required.task_id in finding.subject
        assert finding.outcome is ClaimOutcome.UNAVAILABLE


# ---------------------------------------------------------------------------
# The committed tree, asserted as the honest findings it currently is
# ---------------------------------------------------------------------------


def test_the_committed_registry_is_a_placeholder_so_the_gate_skips_without_fetching() -> None:
    """R3.1: while no operator has published, the gate SKIPs. A SKIP is not a PASS.

    A read of the committed ``published_checkpoints.json`` plus one in-process gate call
    with a fetcher that fails the test if it is used. This is the state
    ``test_published_checkpoint_registry.py`` asserts for the legacy probe; asserted here
    for the hardened gate's four-state vocabulary and its exit code, which that test
    never sees.
    """
    status = registry_status(dict(COMMITTED_REGISTRY), name=NAME, coverage_floor=FLOOR.value)
    assert status.status == "placeholder", status.problems

    report = assess(
        checkpoint_policy=POLICY,
        registry=dict(COMMITTED_REGISTRY),
        fetch_sidecar=never_fetched,
        env={},
    )
    assert report.outcome is Outcome.SKIP
    assert report.outcome in NON_PASSING
    assert report.exit_code == 2
    assert report.classification is ArtifactClass.ABSENT
    # No entry for the serving name has landed, which is why the SKIP is honest.
    assert NAME not in COMMITTED_REGISTRY


def test_the_committed_task_records_are_the_honest_fail_r3_6_makes_mechanical() -> None:
    """R3.6 against the committed tree: this FAILs today, and that is the finding.

    ``core-purpose-uplift`` tasks 9 and 9.1 are marked ``[x]`` while
    ``infrastructure/ml/published_checkpoints.json`` still holds only
    ``__placeholder__``. The audit's Requirement 3 reported that; this asserts it
    mechanically. It is a file scan only - no process, no network. If the operator lands
    a validated entry, or unchecks the records, this test tells us by failing, which is
    the correct signal in either direction.
    """
    report = evaluate_task_claims()

    assert report.outcome is ClaimOutcome.FAIL
    assert report.exit_code == 1
    assert report.registry_state == "placeholder"
    assert report.unlanded

    for required in POLICY.task_claims.must_resolve:
        assert any(
            required.spec in name and f"task {required.task_id} " in name
            for name in report.unlanded
        ), (required.spec, required.task_id, report.unlanded)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
