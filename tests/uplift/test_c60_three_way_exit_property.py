"""Property-based test that the C60 gate exit is a total three-way mapping.

Feature: core-purpose-uplift, Property 15: The C60 gate exit is a total three-way mapping.

    *For any* result artifact, the C60 gate lands on exactly one of three mutually
    distinct exit codes -- pass (``0``), regression (``1``), and a distinct unavailable
    code (``2``) -- and the unavailable case never maps to pass.

    Requirement 4.4: an admissible, proven measurement exits pass.
    Requirement 4.5: a real measurement below the floor exits the regression code.
    Requirement 4.6: an unavailable measurement exits a *distinct* non-zero code --
    absence of proof is never a pass.

**Restated for the purpose-achievement-audit R2 remediation.** The original version of
this property derived its expectation from ``headline_uplift`` alone, which is precisely
the read that let the gate report PASS on an artifact declaring ``incomplete: true`` with
fidelity ``unknown``. Under R2.1/R2.2/R2.4/R2.8 an artifact is admissible only when it is
complete, powered at ``MIN_POWERED_REPLICATES``, within the twin fidelity bound, and
attributed to the run being evaluated; the headline is consulted only after that.

The generator walks the whole artifact surface the gate can meet in the wild: the file
absent, present-but-unreadable (a directory at the path, undecodable bytes), malformed
JSON, valid JSON that is not an object, an object missing required fields, and -- for the
shapes that do parse -- a proof-grade run plus every honest way a run falls short
(incomplete, under-powered, fidelity unavailable, fidelity out of bound, unattributed,
produced by a different run). The expected exit code is recomputed from the case
description rather than from the gate's own predicates, so this is an independent
statement of the rule.

All three codes are reachable from an artifact at the committed
:data:`~uplift.uplift_floor.UPLIFT_FLOOR` of ``0.0``: an admissible run with a strictly
positive headline passes, one measuring exactly ``0.0`` is unavailable (a proven gain must
be strictly positive, so "at least zero" is not "proven"), and one measuring a negative
headline is a regression below the floor. The mapping against a *non-zero* floor is pinned
at the :func:`~scripts.audit.uplift_truth.verdict` level in
``test_uplift_truth_gate_property.py``, where the floor is a parameter.

Every artifact is written under ``tmp_path``, so the repo's ``artifacts/uplift/result.json``
path is never read or written. The property is pure and fast: no twin, no arm, no socket, $0.

**Validates: Requirements 4.4, 4.5, 4.6**
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import uplift_truth as gate
from scripts.audit.uplift_truth import (
    EXIT_PASS,
    EXIT_REGRESSION,
    EXIT_UNAVAILABLE,
    RESULT_ARTIFACT,
)
from uplift.harness import (
    UNATTRIBUTED,
    ArtifactFidelity,
    UpliftArtifact,
    UpliftProvenance,
)
from uplift.uplift_floor import MIN_POWERED_REPLICATES

_EXIT_CODES = (EXIT_PASS, EXIT_REGRESSION, EXIT_UNAVAILABLE)

# The identity the evaluating job declares; the artifact either matches it or does not.
_REVISION = "0f1e2d3c4b5a"
_RUN_ID = "run-20260101-01"


# ---------------------------------------------------------------------------
# Artifact surface
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Case:
    """One on-disk artifact state plus the exit code the rule requires for it."""

    kind: str
    expected: int
    payload: bytes | None = None  # ``None`` means "do not create the file"
    as_directory: bool = False

    def materialise(self, root: Path) -> Path:
        path = root / uuid.uuid4().hex / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.as_directory:
            path.mkdir()
        elif self.payload is not None:
            path.write_bytes(self.payload)
        return path


def _artifact(
    *,
    headline: float,
    replicates: int,
    incomplete: bool,
    kl_divergence: float | None,
    within: bool | None,
    revision: str,
    run_id: str,
) -> bytes:
    """Canonical bytes for a parseable artifact with the given honesty profile."""
    return (
        UpliftArtifact(
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
                arms=("baseline-0", "consensus"),
                replicates_per_arm=replicates,
                revision=revision,
                run_id=run_id,
                seeds=(4001, 4002),
                written_at="2026-01-01T00:00:00Z",
            ),
        )
        .to_canonical_json()
        .encode("utf-8")
    )


def _json_bytes(obj: object) -> bytes:
    return json.dumps(obj).encode("utf-8")


def _raw(text: str) -> bytes:
    return text.encode("utf-8")


_positive = st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False)
_negative = st.floats(
    min_value=-1e6, max_value=-1e-6, allow_nan=False, allow_infinity=False
)


# -- admissible and proven: the only shape that may exit pass ---------------------
@st.composite
def _proven(draw) -> _Case:
    return _Case(
        kind="proven",
        expected=EXIT_PASS,
        payload=_artifact(
            headline=draw(_positive),
            replicates=draw(
                st.integers(
                    min_value=MIN_POWERED_REPLICATES, max_value=MIN_POWERED_REPLICATES * 3
                )
            ),
            incomplete=False,
            kl_divergence=0.02,
            within=True,
            revision=_REVISION,
            run_id=_RUN_ID,
        ),
    )


# -- parseable, but honestly not a proof ------------------------------------------
@st.composite
def _not_proven(draw) -> _Case:
    flaw = draw(
        st.sampled_from(
            [
                "incomplete",
                "under-powered",
                "fidelity-absent",
                "out-of-bound",
                "unattributed",
                "foreign-run",
                "foreign-revision",
                "zero-headline",
                "negative-headline",
            ]
        )
    )
    headline = draw(_positive)
    replicates = MIN_POWERED_REPLICATES
    incomplete = False
    kl: float | None = 0.02
    within: bool | None = True
    revision, run_id = _REVISION, _RUN_ID
    # Admissible-but-not-proven and admissible-but-regressed are the two cases where the
    # artifact is fine and the *measurement* is what falls short.
    expected = EXIT_UNAVAILABLE

    if flaw == "incomplete":
        incomplete = True
    elif flaw == "under-powered":
        replicates = draw(st.integers(min_value=0, max_value=MIN_POWERED_REPLICATES - 1))
    elif flaw == "fidelity-absent":
        kl, within = None, None
    elif flaw == "out-of-bound":
        within = False
    elif flaw == "unattributed":
        revision, run_id = UNATTRIBUTED, UNATTRIBUTED
    elif flaw == "foreign-run":
        run_id = "run-somewhere-else"
    elif flaw == "foreign-revision":
        revision = "deadbeefdeadbeef"
    elif flaw == "zero-headline":
        headline = 0.0
    else:
        headline = draw(_negative)
        expected = EXIT_REGRESSION  # below the committed floor of 0.0

    return _Case(
        kind=f"not-proven:{flaw}",
        expected=expected,
        payload=_artifact(
            headline=headline,
            replicates=replicates,
            incomplete=incomplete,
            kl_divergence=kl,
            within=within,
            revision=revision,
            run_id=run_id,
        ),
    )


# -- not even readable as an artifact ---------------------------------------------
_unreadable = st.one_of(
    st.just(_Case(kind="missing", expected=EXIT_UNAVAILABLE, payload=None)),
    st.just(_Case(kind="directory", expected=EXIT_UNAVAILABLE, as_directory=True)),
    st.just(
        _Case(
            kind="undecodable",
            expected=EXIT_UNAVAILABLE,
            payload=b"\xff\xfe\x00not utf-8",
        )
    ),
    st.sampled_from(["not valid json {", "", "   ", "{'headline_uplift': 1.0}", "{,}"]).map(
        lambda text: _Case(kind="malformed", expected=EXIT_UNAVAILABLE, payload=_raw(text))
    ),
    st.sampled_from([[1, 2, 3], "0.5", 12.5, None, True]).map(
        lambda obj: _Case(
            kind="not-object", expected=EXIT_UNAVAILABLE, payload=_json_bytes(obj)
        )
    ),
    # Objects missing the fields R2.1/R2.2/R2.3 require the harness to write: a boolean
    # `incomplete`, an integral replicates-per-arm count, and a provenance record.
    st.sampled_from(
        [
            {},
            {"other": 1.0},
            {"headline_uplift": 0.5},
            {"headline_uplift": 0.5, "incomplete": False},
            {"headline_uplift": 0.5, "incomplete": "no", "replicates_per_arm": 1000},
            {"headline_uplift": 0.5, "incomplete": False, "replicates_per_arm": "1000"},
        ]
    ).map(
        lambda obj: _Case(
            kind="missing-required-shape",
            expected=EXIT_UNAVAILABLE,
            payload=_json_bytes(obj),
        )
    ),
)

_cases = st.one_of(_proven(), _not_proven(), _unreadable)


# ---------------------------------------------------------------------------
# Property 15
# ---------------------------------------------------------------------------
@given(case=_cases)
def test_c60_gate_exit_is_a_total_three_way_mapping(
    case: _Case, tmp_path: Path, monkeypatch, capsys
) -> None:
    """Property 15: pass / regression / distinct-unavailable, and never a false pass.

    **Validates: Requirements 4.4, 4.5, 4.6**
    """
    monkeypatch.setenv("SYNAPSE_REVISION", _REVISION)
    monkeypatch.setenv("SYNAPSE_RUN_ID", _RUN_ID)

    path = case.materialise(tmp_path)
    assert path != RESULT_ARTIFACT  # the repo's own artifact path is never touched

    exit_code = gate.run(check=True, require_fresh_run=True, artifact=path)
    out = capsys.readouterr().out

    # Totality: exactly one of the three declared codes, and the three are distinct.
    assert len(set(_EXIT_CODES)) == 3
    assert exit_code in _EXIT_CODES
    assert exit_code == case.expected

    if case.expected == EXIT_UNAVAILABLE:
        # R4.6 / I-7: a distinct NON-ZERO code that is neither pass nor regression, and
        # the reason it was treated as unavailable is printed (R2.1, R2.2, R2.8).
        assert exit_code != EXIT_PASS
        assert exit_code != EXIT_REGRESSION
        assert exit_code != 0
        assert out.strip()
    elif case.expected == EXIT_REGRESSION:
        # R4.5: a real measurement below the floor is named a regression.
        assert exit_code != 0
        assert "REGRESSION" in out.upper()
    else:
        assert exit_code == 0


# ---------------------------------------------------------------------------
# Trigger awareness (AD-9, CF-4): outside the generating job there is no verdict
# ---------------------------------------------------------------------------
@given(case=_proven())
def test_proof_grade_artifact_still_skips_outside_the_generating_job(
    case: _Case, tmp_path: Path, monkeypatch
) -> None:
    """Even an admissible, proven artifact yields a SKIP when this job did not run the
    harness: C60 returns PASS/FAIL only in the job that produced its evidence (AD-9)."""
    monkeypatch.setenv("SYNAPSE_REVISION", _REVISION)
    monkeypatch.setenv("SYNAPSE_RUN_ID", _RUN_ID)

    path = case.materialise(tmp_path)
    context = gate.resolve_run_context(generating_job=False, artifact=path)
    admission = gate.admit(path, context)

    assert admission.outcome == "skip"
    assert not admission.admitted
    assert admission.proof is None
    assert gate.registry_status(admission, EXIT_UNAVAILABLE)[0] == "SKIP"
