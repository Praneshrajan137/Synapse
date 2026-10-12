"""Property-based test for C60's admissibility gate (task 10.4, design E5).

Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence

    *For any* result artifact payload and *any* run context, the gate returns the
    unavailable code - never a pass - when ``incomplete`` is anything other than boolean
    ``false``, when no integral replicates-per-arm value at or above
    ``MIN_POWERED_REPLICATES`` is recorded, when ``within_fidelity_bound`` is null or
    false, when ``headline_uplift`` is absent or non-finite, or when the artifact's
    provenance revision, seed set, or arm identifiers differ from the evaluating run; and
    its verdict otherwise equals ``is_proven_uplift`` applied to the artifact's proof.

**Validates: Requirements 2.1, 2.2, 2.4, 2.8**

What the retargeted sibling suites already cover, and what is therefore not restated
-----------------------------------------------------------------------------------

Task 10.3 rewrote :mod:`scripts.audit.uplift_truth` into two halves - :func:`admit`
(is this evidence admissible?) and :func:`verdict` (what does admissible evidence
support?) - and retargeted three existing suites onto the new shape:

* ``tests/uplift/test_uplift_truth_gate_property.py`` (Property 21) pins the *floor
  mapping* of :func:`~scripts.audit.uplift_truth.verdict` over a generated
  :class:`~uplift.uplift_floor.PoweredProof` and a generated floor: pass at or above,
  regression strictly below, unavailable otherwise, plus the three audit examples (a
  zero headline on a zero floor, the previously committed incomplete artifact, and a
  large gain measured out of the fidelity bound). It never constructs an artifact and
  never calls ``admit``.
* ``tests/uplift/test_c60_three_way_exit_property.py`` (Property 15) drives
  ``gate.run(check=True, require_fresh_run=True)`` over the on-disk artifact surface and
  asserts the *exit code* is a total three-way mapping: missing file, directory in the
  way, undecodable bytes, malformed JSON, a non-object, a missing-shape object, a
  proof-grade run, and nine honest shortfalls. It asserts that *something* was printed
  on an unavailable outcome (``out.strip()``); it does not assert that what was printed
  names the cause. Its one non-exit-code assertion is that a proof-grade artifact still
  skips outside the generating job.
* ``tests/uplift/test_preserved_baseline_regression.py`` contributes one example: a
  proof-grade artifact exits ``EXIT_PASS`` without touching a socket, a paid client, or
  a real-data file.

So the exit-code surface is covered and the *admissibility* surface is not. Nothing in
the repository calls :func:`~scripts.audit.uplift_truth.admit`,
:func:`~scripts.audit.uplift_truth.registry_status`,
:func:`~scripts.audit.uplift_truth.admit_floor_raise`,
:func:`~scripts.audit.uplift_truth.artifact_is_version_controlled`, or
:func:`~scripts.audit.uplift_truth.is_git_ignored` from a test. This file asserts the
five things that leaves unpinned:

1. **Each inadmissible class is rejected with a reason that names its cause.** R2.1 and
   R2.2 require the gate to *print the reason*, and R2.2 specifically to print the
   recorded count and the required count. An exit code of ``2`` with an unhelpful string
   satisfies the sibling property and not the requirement.
2. **The version-controlled class, which no sibling reaches.** Every sibling artifact
   lives under ``tmp_path``, i.e. outside the repository, so
   ``artifact_is_version_controlled`` is trivially false for all of them and the branch
   that fires when C60's evidence path stops being git-ignored is never exercised. That
   branch is the whole of R2.8's "read from version control" clause and it is the one
   that would catch the artifact being committed again.
3. **Admissibility is independent of the measurement.** An admissible artifact is
   admitted whether it measures a gain, nothing, or a regression - the value is the
   verdict's business, not admission's. Conflating the two is how the audited gate came
   to read a headline number out of a run that declared it never finished.
4. **The verdict derives from ``is_proven_uplift``, not from ``headline_uplift``.**
   Asserted two ways that a fixed set of examples cannot give: metamorphically (artifacts
   carrying the *same* headline and differing only in completeness, power, or fidelity
   reach different verdicts, so the verdict is not a function of the headline) and by
   R2.4's own falsification clause (substituting the predicate changes the code).
5. **A floor raise cannot be backed by evidence this gate rejected**, and a SKIP outside
   the generating job is excluded from the PASS count on every artifact class, not just
   on a proof-grade one.

Independent oracle
------------------

The expected outcome of every example is a property of *how the example was built*: each
case carries the class it belongs to, the substrings that must appear in the printed
reasons, and (for the under-power class) the two integers R2.2 requires. Nothing is
compared against a re-run of the subject's own predicates. Two places deliberately go
the other way and say so: the inversion test substitutes
:func:`uplift.uplift_floor.is_proven_uplift` to assert *sensitivity* - that the code the
gate returns is a function of that predicate - which is R2.4's stated falsification
experiment, not a simulated verdict; and the same-run floor-raise test calls
:func:`~uplift.uplift_floor.ratchet_to_measured` directly on the rejected artifact's own
proof to establish that the raise was refused because of the run binding and *not*
because the measurement fell short.

``MIN_POWERED_REPLICATES`` and ``UPLIFT_FLOOR`` are imported from committed
configuration, never written as literals, so a change to either moves this test with it.

Cost, and why this is not slow-marked
-------------------------------------

The harness is never run. Every artifact is constructed field by field through
:class:`~uplift.harness.UpliftArtifact` and written under ``tmp_path``, so the repo's own
``artifacts/uplift/result.json`` path is never read or written, no SimPy twin is stepped,
no ``ConsensusProtocol`` is built, no socket is opened, and no ``MIN_SCENARIOS``-scale
replicate loop exists anywhere in this file. A powered 1000-replicate-per-arm run belongs
to the scheduled ``.github/workflows/uplift.yml`` (task 10.5) and is forbidden on the dev
laptop by I-0. ``max_examples`` is inherited from the root ``conftest.py`` profiles.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import uplift_truth as gate
from scripts.audit.uplift_truth import (
    EXIT_PASS,
    EXIT_REGRESSION,
    EXIT_UNAVAILABLE,
    RESULT_ARTIFACT,
    Admission,
    RunContext,
    admit,
    admit_floor_raise,
    artifact_is_version_controlled,
    is_git_ignored,
    registry_status,
    verdict,
)
from uplift.harness import (
    UNATTRIBUTED,
    ArtifactFidelity,
    UpliftArtifact,
    UpliftProvenance,
)
from uplift.uplift_floor import (
    MIN_POWERED_REPLICATES,
    UPLIFT_FLOOR,
    FloorRatchetError,
    UnprovenFloorRaiseError,
    is_proven_uplift,
    ratchet_to_measured,
)

ROOT = Path(gate.__file__).resolve().parents[2]

# The identity the *evaluating job* declares. An artifact either carries it or does not.
_REVISION = "9a8b7c6d5e4f"
_RUN_ID = "run-20260215-13"
_SEEDS: tuple[int, ...] = (4001, 4002)
_ARMS: tuple[str, ...] = ("baseline-par-level", "consensus")

# A seed set and an arm set that are disjoint from the recorded ones, so a mismatch is a
# mismatch of sets rather than of ordering (``UpliftProvenance`` canonicalises both).
_FOREIGN_SEEDS: tuple[int, ...] = (9001, 9002)
_FOREIGN_ARMS: tuple[str, ...] = ("baseline-static-price", "shadow")

_ALL_STATUSES = ("PASS", "FAIL", "SKIP")

#: Headlines that clear the *committed* floor, so "would pass if it were admissible" stays
#: true after a future ratchet. The bounds are offsets from ``UPLIFT_FLOOR``, never a
#: literal threshold.
_gainful = st.floats(
    min_value=UPLIFT_FLOOR + 1e-3,
    max_value=UPLIFT_FLOOR + 1e6,
    allow_nan=False,
    allow_infinity=False,
)
_negative = st.floats(
    min_value=-1e6, max_value=-1e-3, allow_nan=False, allow_infinity=False
)
#: Measurements spanning a gain, no movement, and a regression. Admissibility must not
#: depend on which of the three an artifact carries.
_measurements = st.one_of(_gainful, st.just(0.0), _negative)
_powered = st.integers(
    min_value=MIN_POWERED_REPLICATES, max_value=MIN_POWERED_REPLICATES * 2
)
_unpowered = st.integers(min_value=0, max_value=MIN_POWERED_REPLICATES - 1)


# ---------------------------------------------------------------------------
# Artifact construction (no harness run: every field is supplied)
# ---------------------------------------------------------------------------
def _artifact(
    *,
    headline: float,
    replicates: int = MIN_POWERED_REPLICATES,
    incomplete: bool = False,
    kl_divergence: float | None = 0.02,
    within: bool | None = True,
    revision: str = _REVISION,
    run_id: str = _RUN_ID,
    seeds: tuple[int, ...] = _SEEDS,
    arms: tuple[str, ...] = _ARMS,
) -> UpliftArtifact:
    """A parseable artifact with the requested honesty profile."""
    return UpliftArtifact(
        headline_uplift=headline,
        primary_kpi="fill_rate",
        noise_tolerance_pp=1.0,
        incomplete=incomplete,
        all_wins_warning=False,
        replicates_per_arm=replicates,
        fidelity=ArtifactFidelity(
            kl_divergence=kl_divergence,
            threshold=0.1,
            confidence="high" if within else "unknown",
            within_fidelity_bound=within,
            fidelity_bound_statement="bounded by twin fidelity",
        ),
        provenance=UpliftProvenance(
            arms=arms,
            replicates_per_arm=replicates,
            revision=revision,
            run_id=run_id,
            seeds=seeds,
            written_at="2026-02-15T00:00:00Z",
        ),
    )


def _bytes(artifact: UpliftArtifact) -> bytes:
    return artifact.to_canonical_json().encode("utf-8")


def _mutated(mutate: dict[str, Any] | None, drop: tuple[str, ...] = ()) -> bytes:
    """A payload that parses as JSON but not as an :class:`UpliftArtifact`.

    Built by mutating a proof-grade payload so exactly one shape obligation is broken -
    R2.3's finite ``headline_uplift``, the replicate/provenance agreement, or the
    presence of the provenance record itself. ``allow_nan=True`` is deliberate: the
    ``NaN``/``Infinity`` tokens are how a non-finite headline reaches a reader, and R2.3
    requires the artifact to be rejected rather than read.
    """
    payload = _artifact(headline=0.5).to_payload()
    for key in drop:
        payload.pop(key, None)
    payload.update(mutate or {})
    return json.dumps(payload, allow_nan=True).encode("utf-8")


# ---------------------------------------------------------------------------
# Cases: an on-disk state, the class it belongs to, and what its reason must name
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Case:
    """One artifact state plus the admissibility outcome the rule requires for it."""

    kind: str
    #: ``None`` means "do not create the file" (the absent-artifact class).
    payload: bytes | None = None
    #: R2.8: the evaluating job established that this path is under version control.
    tracked: bool = False
    expected_seeds: tuple[int, ...] | None = None
    expected_arms: tuple[str, ...] | None = None
    #: Substrings that must appear (case-insensitively) in the printed reasons.
    tokens: tuple[str, ...] = ()
    #: R2.2: integers that must appear together in one reason line.
    power_numbers: tuple[int, ...] = field(default_factory=tuple)
    headline: float | None = None

    def materialise(self, root: Path) -> Path:
        path = root / uuid.uuid4().hex / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.payload is not None:
            path.write_bytes(self.payload)
        return path

    def context(self, *, generating_job: bool) -> RunContext:
        return RunContext(
            revision=_REVISION,
            run_id=_RUN_ID,
            generating_job=generating_job,
            artifact_tracked=self.tracked,
            expected_seeds=self.expected_seeds,
            expected_arms=self.expected_arms,
        )


# -- R2.1: the run did not complete ----------------------------------------------
@st.composite
def _incomplete(draw: st.DrawFn) -> _Case:
    headline = draw(_measurements)
    return _Case(
        kind="incomplete",
        payload=_bytes(_artifact(headline=headline, incomplete=True)),
        tokens=("incomplete",),
        headline=headline,
    )


# -- R2.2: fewer than MIN_POWERED_REPLICATES per arm ------------------------------
@st.composite
def _under_powered(draw: st.DrawFn) -> _Case:
    replicates = draw(_unpowered)
    headline = draw(_measurements)
    return _Case(
        kind=f"under-powered:{replicates}",
        payload=_bytes(_artifact(headline=headline, replicates=replicates)),
        tokens=("powered",),
        power_numbers=(replicates, MIN_POWERED_REPLICATES),
        headline=headline,
    )


# -- R2.4: fidelity unavailable or out of bound, whatever the magnitude ------------
@st.composite
def _out_of_fidelity(draw: st.DrawFn) -> _Case:
    headline = draw(_measurements)
    absent = draw(st.booleans())
    return _Case(
        kind="fidelity-absent" if absent else "fidelity-out-of-bound",
        payload=_bytes(
            _artifact(
                headline=headline,
                kl_divergence=None if absent else 0.9,
                within=None if absent else False,
            )
        ),
        tokens=("fidelity",),
        headline=headline,
    )


# -- R2.8: the provenance is not this job's run -----------------------------------
@st.composite
def _provenance_mismatch(draw: st.DrawFn) -> _Case:
    flaw = draw(
        st.sampled_from(("revision", "run-id", "seed-set", "arms", "unattributed"))
    )
    headline = draw(_gainful)
    foreign_revision = "deadbeefcafe"
    foreign_run = "run-somewhere-else"

    if flaw == "revision":
        return _Case(
            kind="foreign-revision",
            payload=_bytes(_artifact(headline=headline, revision=foreign_revision)),
            tokens=("provenance", foreign_revision, _REVISION),
            headline=headline,
        )
    if flaw == "run-id":
        return _Case(
            kind="foreign-run-id",
            payload=_bytes(_artifact(headline=headline, run_id=foreign_run)),
            tokens=("run", foreign_run, _RUN_ID),
            headline=headline,
        )
    if flaw == "seed-set":
        # The evaluating job knows which seed set its own harness invocation used, so a
        # replayed artifact from a different seed set is caught even at the same revision.
        return _Case(
            kind="foreign-seed-set",
            payload=_bytes(_artifact(headline=headline, seeds=_SEEDS)),
            expected_seeds=_FOREIGN_SEEDS,
            tokens=("provenance", str(_SEEDS), str(_FOREIGN_SEEDS)),
            headline=headline,
        )
    if flaw == "arms":
        return _Case(
            kind="foreign-arms",
            payload=_bytes(_artifact(headline=headline, arms=_ARMS)),
            expected_arms=_FOREIGN_ARMS,
            tokens=("provenance", str(_ARMS), str(tuple(sorted(_FOREIGN_ARMS)))),
            headline=headline,
        )
    return _Case(
        kind="unattributed",
        payload=_bytes(
            _artifact(headline=headline, revision=UNATTRIBUTED, run_id=UNATTRIBUTED)
        ),
        tokens=("unattributed", UNATTRIBUTED),
        headline=headline,
    )


# -- R2.8: the evidence path is under version control ------------------------------
@st.composite
def _version_controlled(draw: st.DrawFn) -> _Case:
    """A *proof-grade* artifact on a tracked path: content cannot rescue it.

    This is the class no sibling suite reaches, and the direction of the assertion is
    what matters - a committed measurement is rejected however good it looks, because a
    file in the tree is not evidence that a run happened.
    """
    return _Case(
        kind="version-controlled",
        payload=_bytes(_artifact(headline=draw(_gainful))),
        tracked=True,
        tokens=("version control", "result.json"),
    )


# -- R2.1/R2.2/R2.3: the payload does not carry the required shape ------------------
_shape_broken = st.sampled_from(
    (
        _Case(
            kind="headline-absent",
            payload=_mutated(None, drop=("headline_uplift",)),
            tokens=("result.json", "headline"),
        ),
        _Case(
            kind="headline-nan",
            payload=_mutated({"headline_uplift": float("nan")}),
            tokens=("result.json", "headline"),
        ),
        _Case(
            kind="headline-infinite",
            payload=_mutated({"headline_uplift": float("inf")}),
            tokens=("result.json", "headline"),
        ),
        _Case(
            kind="headline-null",
            payload=_mutated({"headline_uplift": None}),
            tokens=("result.json", "headline"),
        ),
        _Case(
            kind="headline-not-a-number",
            payload=_mutated({"headline_uplift": "not a number"}),
            tokens=("result.json", "headline"),
        ),
        # R2.1 names two states beyond ``incomplete: true``: the field omitted, and the
        # field carrying a non-boolean. "maybe" is outside the boolean vocabulary a lax
        # parser would coerce, so it reaches the shape check rather than becoming False.
        _Case(
            kind="incomplete-absent",
            payload=_mutated(None, drop=("incomplete",)),
            tokens=("result.json", "incomplete"),
        ),
        _Case(
            kind="incomplete-not-boolean",
            payload=_mutated({"incomplete": "maybe"}),
            tokens=("result.json", "incomplete"),
        ),
        _Case(
            kind="provenance-absent",
            payload=_mutated(None, drop=("provenance",)),
            tokens=("result.json", "provenance"),
        ),
        _Case(
            kind="replicates-disagree-with-provenance",
            payload=_mutated({"replicates_per_arm": MIN_POWERED_REPLICATES + 1}),
            tokens=("result.json",),
        ),
        _Case(
            kind="undeclared-field",
            payload=_mutated({"measured_by": "an undeclared writer"}),
            tokens=("result.json",),
        ),
    )
)

#: The absent artifact: the generating job ran and wrote nothing.
_absent = st.just(_Case(kind="absent", payload=None, tokens=("result.json",)))

_inadmissible = st.one_of(
    _incomplete(),
    _under_powered(),
    _out_of_fidelity(),
    _provenance_mismatch(),
    _version_controlled(),
    _shape_broken,
    _absent,
)


# -- admissible: complete, powered, in-bound, and attributed to this run ------------
@st.composite
def _admissible(draw: st.DrawFn) -> _Case:
    headline = draw(_measurements)
    return _Case(
        kind="admissible",
        payload=_bytes(
            _artifact(headline=headline, replicates=draw(_powered), incomplete=False)
        ),
        expected_seeds=draw(st.sampled_from((None, _SEEDS))),
        expected_arms=draw(st.sampled_from((None, _ARMS))),
        headline=headline,
    )


_any_case = st.one_of(_inadmissible, _admissible())


# ---------------------------------------------------------------------------
# Helpers over the subject's report
# ---------------------------------------------------------------------------
def _joined(admission: Admission) -> str:
    return " || ".join(admission.reasons)


def _integers_in(line: str) -> set[int]:
    return {int(match) for match in re.findall(r"\d+", line)}


def _gate_exit(admission: Admission) -> int:
    """The exit code ``run()`` derives from an admission, without re-deriving it.

    ``run()`` computes ``verdict(admission.proof) if admission.admitted else
    EXIT_UNAVAILABLE`` - an inadmissible artifact never reaches the verdict at all, which
    is what makes "the gate cannot read a headline out of a rejected run" structural.
    """
    return verdict(admission.proof) if admission.admitted else EXIT_UNAVAILABLE


# ---------------------------------------------------------------------------
# 1. Every inadmissible class is rejected, with a reason that names the cause
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(case=_inadmissible)
def test_each_inadmissible_class_is_rejected_with_a_reason_naming_its_cause(
    case: _Case, tmp_path: Path
) -> None:
    """R2.1, R2.2, R2.8: rejected, never a pass, and the reason names why."""
    path = case.materialise(tmp_path)
    assert path != RESULT_ARTIFACT  # the repo's own evidence path is never touched

    admission = admit(path, case.context(generating_job=True))
    reasons = _joined(admission)

    assert admission.outcome == "unavailable", case.kind
    assert not admission.admitted, case.kind
    # No proof survives an inadmissible artifact, so no downstream caller can read a
    # headline number out of a run this gate rejected (R2.10's structural half).
    assert admission.proof is None, case.kind
    assert admission.reasons, case.kind
    assert reasons.isascii(), case.kind  # ASCII-only console output

    for token in case.tokens:
        assert token.lower() in reasons.lower(), (case.kind, token, reasons)

    # R2.2: the recorded count *and* the required count, together, in one line.
    if case.power_numbers:
        power_lines = [line for line in admission.reasons if "powered" in line.lower()]
        assert power_lines, (case.kind, reasons)
        assert any(
            set(case.power_numbers) <= _integers_in(line) for line in power_lines
        ), (case.kind, case.power_numbers, power_lines)

    # I-7: an inadmissible artifact is a non-zero, non-pass outcome and is never counted
    # as a PASS by the Check_Registry.
    code = _gate_exit(admission)
    assert code == EXIT_UNAVAILABLE
    assert code not in (EXIT_PASS, EXIT_REGRESSION)
    status, detail = registry_status(admission, code)
    assert status in _ALL_STATUSES
    assert status != "PASS", (case.kind, status)
    assert detail.isascii()
    # The generating job's purpose was to measure; failing to deliver an admissible
    # measurement is that job's defect, and a committed artifact is the tree's defect.
    assert status == "FAIL", (case.kind, status)
    assert admission.version_controlled is case.tracked


# ---------------------------------------------------------------------------
# 2. Admissibility is a property of the evidence, not of the measurement
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(case=_admissible())
def test_a_complete_powered_in_bound_same_run_artifact_is_admitted(
    case: _Case, tmp_path: Path
) -> None:
    """A gain, no movement, and a regression are all admissible *evidence* (R2.1-R2.8).

    Admission answers "may this be used", not "what does it say". The audited gate
    collapsed the two, which is how a run declaring ``incomplete: true`` came to supply a
    headline number.
    """
    path = case.materialise(tmp_path)
    admission = admit(path, case.context(generating_job=True))

    assert admission.outcome == "admitted", (case.kind, _joined(admission))
    assert admission.admitted
    assert admission.reasons == ()
    assert admission.proof is not None
    assert admission.proof.replicates >= MIN_POWERED_REPLICATES
    assert admission.proof.incomplete is False
    assert admission.proof.within_fidelity_bound is True
    assert admission.headline_uplift == case.headline
    assert admission.provenance_revision == _REVISION
    assert admission.provenance_run_id == _RUN_ID
    assert admission.version_controlled is False

    # The verdict is the only thing the measurement decides, and PASS is reserved for a
    # proven gain (R2.4, I-7).
    code = _gate_exit(admission)
    assert code in (EXIT_PASS, EXIT_REGRESSION, EXIT_UNAVAILABLE)
    assert (code == EXIT_PASS) is is_proven_uplift(admission.proof, UPLIFT_FLOOR)
    assert (registry_status(admission, code)[0] == "PASS") is (code == EXIT_PASS)


# ---------------------------------------------------------------------------
# 3. The verdict derives from is_proven_uplift, not from headline_uplift (R2.4)
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(headline=_gainful, replicates=_powered, degradation=st.integers(0, 3))
def test_the_same_headline_reaches_different_verdicts(
    headline: float, replicates: int, degradation: int, tmp_path: Path
) -> None:
    """One headline, four artifacts, two verdicts: the headline is not the verdict.

    The proof-grade artifact and its degraded twin carry a byte-identical
    ``headline_uplift``. If the verdict were a function of that field they would agree.
    They must not: only the artifact that also completed, reached
    ``MIN_POWERED_REPLICATES``, and stayed inside the twin fidelity bound may pass.
    """
    proof_grade = _artifact(headline=headline, replicates=replicates)
    twins = (
        _artifact(headline=headline, replicates=replicates, incomplete=True),
        _artifact(headline=headline, replicates=MIN_POWERED_REPLICATES - 1),
        _artifact(headline=headline, replicates=replicates, within=False),
        _artifact(
            headline=headline, replicates=replicates, kl_divergence=None, within=None
        ),
    )
    degraded = twins[degradation]
    assert degraded.headline_uplift == proof_grade.headline_uplift

    context = RunContext(
        revision=_REVISION, run_id=_RUN_ID, generating_job=True, artifact_tracked=False
    )

    def _code(artifact: UpliftArtifact, name: str) -> int:
        path = tmp_path / uuid.uuid4().hex / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_bytes(artifact))
        return _gate_exit(admit(path, context))

    assert _code(proof_grade, "result.json") == EXIT_PASS
    assert _code(degraded, "result.json") != EXIT_PASS


# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(case=_admissible())
def test_substituting_the_proven_uplift_predicate_changes_the_exit_code(
    case: _Case, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2.4's falsification clause: the verdict is a function of ``is_proven_uplift``.

    The substituted symbol is the gate's *dependency*, not its evaluator: nothing here
    fakes a verdict or asserts that a stub produced one. The claim is sensitivity - if
    the code the gate returns did not derive from the predicate (if it still compared a
    headline to a floor, as the audited version did), inverting the predicate would leave
    the code unchanged.
    """
    path = case.materialise(tmp_path)
    admission = admit(path, case.context(generating_job=True))
    assert admission.admitted
    baseline = verdict(admission.proof)

    original = gate.is_proven_uplift
    monkeypatch.setattr(
        gate,
        "is_proven_uplift",
        lambda proof, floor=UPLIFT_FLOOR: not original(proof, floor),
    )
    inverted = verdict(admission.proof)

    assert inverted != baseline, (case.kind, baseline, inverted)
    assert (baseline == EXIT_PASS) or (inverted == EXIT_PASS)


# ---------------------------------------------------------------------------
# 4. A floor raise is admitted only through ratchet_to_measured, against this run
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(case=_inadmissible, proposed=_gainful)
def test_no_floor_raise_survives_an_inadmissible_artifact(
    case: _Case, proposed: float, tmp_path: Path
) -> None:
    """R2.10: rejected evidence offers no proof, so it can back no raise."""
    path = case.materialise(tmp_path)
    admission = admit(path, case.context(generating_job=True))
    assert admission.proof is None

    with pytest.raises(UnprovenFloorRaiseError):
        admit_floor_raise(proposed, admission)


# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(headline=_gainful, replicates=_powered)
def test_a_raise_is_bounded_by_the_measurement_and_never_lowers_the_floor(
    headline: float, replicates: int, tmp_path: Path
) -> None:
    """R2.10: ``0 < proposed <= measured`` from an admitted run, and never a decrease."""
    path = tmp_path / "result.json"
    path.write_bytes(_bytes(_artifact(headline=headline, replicates=replicates)))
    admission = admit(
        path,
        RunContext(
            revision=_REVISION,
            run_id=_RUN_ID,
            generating_job=True,
            artifact_tracked=False,
        ),
    )
    assert admission.admitted

    # The measurement is the ceiling: it may be locked in exactly, and no further.
    assert admit_floor_raise(headline, admission) == headline
    with pytest.raises(UnprovenFloorRaiseError):
        admit_floor_raise(headline + 1.0, admission)

    # Lowering is refused by the ratchet itself, before any proof is consulted.
    with pytest.raises(FloorRatchetError) as lowered:
        admit_floor_raise(UPLIFT_FLOOR - 1.0, admission)
    assert not isinstance(lowered.value, UnprovenFloorRaiseError)


# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(headline=_gainful, replicates=_powered)
def test_a_raise_needs_a_same_run_proof_not_merely_a_supporting_measurement(
    headline: float, replicates: int, tmp_path: Path
) -> None:
    """R2.8 + R2.10: the run binding, not the number, is what refuses this raise.

    The artifact measures a gain that *would* support the proposal - asserted here by
    calling :func:`~uplift.uplift_floor.ratchet_to_measured` on the artifact's own proof,
    which accepts it. The gate still refuses, because the measurement was taken in a
    different run.
    """
    artifact = _artifact(
        headline=headline, replicates=replicates, run_id="run-from-another-job"
    )
    path = tmp_path / "result.json"
    path.write_bytes(_bytes(artifact))

    standalone_proof = artifact.as_powered_proof()
    assert standalone_proof is not None
    assert ratchet_to_measured(UPLIFT_FLOOR, headline, standalone_proof) == headline

    admission = admit(
        path,
        RunContext(
            revision=_REVISION,
            run_id=_RUN_ID,
            generating_job=True,
            artifact_tracked=False,
        ),
    )
    assert not admission.admitted
    assert admission.proof is None
    with pytest.raises(UnprovenFloorRaiseError):
        admit_floor_raise(headline, admission)


# ---------------------------------------------------------------------------
# 5. SKIP outside the generating job: excluded from the PASS count, never a PASS
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(case=_any_case)
def test_outside_the_generating_job_no_artifact_class_can_pass(
    case: _Case, tmp_path: Path
) -> None:
    """AD-9, CF-4, R2.9, I-7: a SKIP is not a PASS, on every artifact class.

    A committed artifact is the one class that stays a FAIL here rather than a SKIP: a
    measurement in version control is a defect in the tree that every run should surface,
    not one the scheduled job alone can see.
    """
    path = case.materialise(tmp_path)
    admission = admit(path, case.context(generating_job=False))
    code = _gate_exit(admission)
    status, detail = registry_status(admission, code)

    assert admission.generating_job is False
    assert admission.admitted is False
    assert admission.proof is None
    assert code == EXIT_UNAVAILABLE
    assert code != EXIT_PASS
    assert status in _ALL_STATUSES
    assert status != "PASS", (case.kind, status)
    assert status == ("FAIL" if case.tracked else "SKIP"), (case.kind, status)
    assert admission.reasons
    assert detail.isascii()
    if not case.tracked:
        assert admission.outcome == "skip"
        assert "skip is not a pass" in detail.lower()


# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(case=_any_case)
def test_the_reported_status_says_pass_only_for_a_proven_same_run_measurement(
    case: _Case,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """R2.9: the published PASS count can only contain a measurement someone took.

    Driven through ``run()`` so the printed report is asserted too - R2.1 and R2.2 require
    the gate to *print* why it treated a measurement as unavailable, and a silent ``2`` is
    a code the operator cannot act on.

    The comparison admission is built through :func:`resolve_run_context`, exactly as
    ``run()`` builds its own, so the two agree on the facts ``run()`` derives from the
    environment and the tree rather than from the artifact (the tracked flag, and the
    absence of a caller-supplied expected seed set). The case's own ``tracked`` and
    ``expected_*`` fields are therefore not in play here; they are exercised at the
    :func:`admit` level above.
    """
    monkeypatch.setenv("SYNAPSE_REVISION", _REVISION)
    monkeypatch.setenv("SYNAPSE_RUN_ID", _RUN_ID)
    path = case.materialise(tmp_path)

    exit_code = gate.run(check=True, require_fresh_run=True, artifact=path)
    printed = capsys.readouterr().out

    admission = admit(path, gate.resolve_run_context(generating_job=True, artifact=path))
    code = _gate_exit(admission)
    status = registry_status(admission, code)[0]

    assert exit_code == code
    assert printed.strip()
    assert printed.isascii()
    assert status in printed
    if status == "PASS":
        assert exit_code == EXIT_PASS
        assert admission.admitted
        assert is_proven_uplift(admission.proof, UPLIFT_FLOOR)
    else:
        assert exit_code != EXIT_PASS
        for reason in admission.reasons:
            assert reason in printed


# ---------------------------------------------------------------------------
# The version-controlled derivation, and the committed declaration behind it
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 13: The uplift gate rejects inadmissible evidence
@given(
    covering=st.sampled_from(
        (
            "artifacts/",
            "artifacts/uplift/result.json",
            "artifacts/uplift/*.json",
        )
    ),
    unrelated=st.sampled_from(("node_modules/", "*.log", "# a comment", "")),
)
def test_version_control_is_derived_from_the_declared_ignore_rules(
    covering: str, unrelated: str, tmp_path: Path
) -> None:
    """R2.8: an in-repo path no ignore rule covers is treated as version-controlled.

    The declaration is the authority - no process may be spawned to ask git (I-0) - so
    losing the rule is exactly the change that lets the artifact be committed again, and
    it must flip this derivation.
    """
    in_repo = ROOT / "artifacts" / "uplift" / "result.json"
    outside = tmp_path / "artifacts" / "uplift" / "result.json"

    declared = tmp_path / "declared.gitignore"
    declared.write_text(f"{unrelated}\n{covering}\n", encoding="utf-8")
    silent = tmp_path / "silent.gitignore"
    silent.write_text(f"{unrelated}\n", encoding="utf-8")
    # A negation with nothing covering the path is not an ignore rule: git would track
    # the file, and so must this derivation.
    negated = tmp_path / "negated.gitignore"
    negated.write_text("!artifacts/uplift/result.json\n", encoding="utf-8")

    assert is_git_ignored(in_repo, gitignore=declared) is True
    assert artifact_is_version_controlled(in_repo, gitignore=declared) is False
    assert artifact_is_version_controlled(in_repo, gitignore=silent) is True
    assert artifact_is_version_controlled(in_repo, gitignore=negated) is True
    # A path outside the repository cannot be tracked by this repository.
    assert artifact_is_version_controlled(outside, gitignore=silent) is False
    # An explicit fact established another way (a CI ``git ls-files`` step) wins.
    assert artifact_is_version_controlled(in_repo, tracked=True, gitignore=declared)
    assert not artifact_is_version_controlled(in_repo, tracked=False, gitignore=silent)


def test_the_committed_declaration_still_ignores_the_c60_evidence_path() -> None:
    """AD-9/CF-4: ``artifacts/uplift/result.json`` is out of version control (R2.8).

    An example, not a property: this is one read of one committed file. If the ignore
    rule is ever dropped, every C60 run reports FAIL naming the path - which is the
    behaviour the property above pins, and this asserts the precondition it protects.
    """
    assert is_git_ignored(RESULT_ARTIFACT) is True
    assert artifact_is_version_controlled(RESULT_ARTIFACT) is False
