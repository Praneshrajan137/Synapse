"""C60 -- the SYNAPSE decision-integrity uplift gate (ADR-042, AD-9, R2).

The other honesty gates prove SYNAPSE is honest, trained, calibrated, and auditable.
None of them proves it is *intelligent* -- that its four-tier consensus decisions
actually beat a transparent baseline policy on business KPIs. The ``uplift`` harness
(``python -m uplift.cli``) runs that closed-loop counterfactual experiment and persists
an :class:`~uplift.harness.UpliftArtifact`; this gate decides whether that artifact is
admissible evidence and, if so, what verdict it supports.

What this gate used to do, and why it was wrong
-----------------------------------------------
The previous implementation read a single field -- ``headline_uplift`` -- and compared it
to :data:`~uplift.uplift_floor.UPLIFT_FLOOR`. With a committed floor of ``0.0`` and a
committed artifact carrying ``{"headline_uplift": 0.0, "incomplete": true,
"fidelity": {"within_fidelity_bound": null}}`` the comparison was ``0.0 < 0.0 -> false``,
so the gate reported PASS on an artifact that *self-declares the measurement did not
complete*. The purpose-achievement audit's Requirement 2 is that finding, and this module
is its remediation.

The verdict path now has two halves, both pure and separately testable
---------------------------------------------------------------------
:func:`admit` decides whether an artifact is admissible evidence *at all*, and names
every reason it is not (R2.1, R2.2, R2.8). :func:`verdict` derives the exit code from
:func:`uplift.uplift_floor.is_proven_uplift` -- the predicate that was written to prevent
exactly this failure and had, until now, no production caller (R2.4). A floor raise is
admitted only through :func:`uplift.uplift_floor.ratchet_to_measured` against a proof
from the *same run* (R2.10).

Exit codes (unchanged, and each still distinct):

  * :data:`EXIT_PASS` (``0``)        -- ``is_proven_uplift`` holds against the floor.
  * :data:`EXIT_REGRESSION` (``1``)  -- a powered, complete, in-bound measurement that
    is strictly below the committed floor.
  * :data:`EXIT_UNAVAILABLE` (``2``) -- everything else. Inadmissible evidence, an
    out-of-bound or unavailable fidelity irrespective of headline magnitude, and a
    powered in-bound run whose headline is not a positive gain all land here. Absence of
    proof is never a pass (I-7).

Trigger awareness (AD-9, CF-4)
------------------------------
R2.7 requires the harness to be regenerated in the job that evaluates the gate; R2.8
forbids evaluating an artifact read from version control. A 1000-replicate-per-arm run
cannot sit on the PR path, so the check is *trigger-aware*: only a caller that declares
itself the generating job (``--require-fresh-run``) gets a PASS/FAIL verdict. Everywhere
else :func:`admit` returns the ``skip`` outcome, which R2.9 requires to be excluded from
the published PASS count. ``artifacts/uplift/result.json`` is no longer in version
control and is git-ignored; an in-repo artifact that is *not* ignored is treated as
version-controlled and rejected outright.

Run::

    python -m scripts.audit.uplift_truth                       # human summary
    python -m scripts.audit.uplift_truth --json                # machine JSON
    python -m scripts.audit.uplift_truth --check               # SKIP outside the run job
    python -m scripts.audit.uplift_truth --check --require-fresh-run
    python -m scripts.audit.uplift_truth --check --require-fresh-run --propose-floor 2.5
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

ROOT = Path(__file__).resolve().parents[2]

# Ensure the repo root is importable when run as a bare script (not -m).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uplift.uplift_floor import (  # noqa: E402
    MIN_POWERED_REPLICATES,
    UPLIFT_FLOOR,
    FloorRatchetError,
    PoweredProof,
    is_proven_uplift,
    ratchet_to_measured,
)

if TYPE_CHECKING:  # pragma: no cover -- typing only; the runtime import is deferred.
    from uplift.harness import UpliftArtifact

# Persisted harness result artifact. `uplift.cli` writes the canonical artifact here and
# the gate reads it. NOT under version control (R2.8): `.gitignore` covers `artifacts/`
# and names this path explicitly, and :func:`artifact_is_version_controlled` fails the
# gate if that ever stops being true.
RESULT_ARTIFACT = ROOT / "artifacts" / "uplift" / "result.json"

#: The ignore declaration consulted by :func:`is_git_ignored`.
GITIGNORE = ROOT / ".gitignore"

# Distinct exit codes (R2.1, R2.2, R2.4, R2.8).
EXIT_PASS = 0
EXIT_REGRESSION = 1
EXIT_UNAVAILABLE = 2

#: Mirrors :data:`uplift.harness.UNATTRIBUTED`. Declared locally so this gate does not
#: import the harness (and therefore numpy/SimPy/the twin) just to read a sentinel.
UNATTRIBUTED: Final[str] = "unknown"

#: Environment variables consulted for the evaluating job's source revision.
_REVISION_ENV_KEYS: Final[tuple[str, ...]] = ("SYNAPSE_REVISION", "GITHUB_SHA")

#: Environment variables consulted for the evaluating job's run identifier.
_RUN_ID_ENV_KEYS: Final[tuple[str, ...]] = ("SYNAPSE_RUN_ID", "GITHUB_RUN_ID")

#: ``admitted`` -- admissible evidence; ``skip`` -- not the generating job (AD-9);
#: ``unavailable`` -- evidence exists but is inadmissible, or does not exist.
Outcome = Literal["admitted", "skip", "unavailable"]


def _display(path: Path) -> str:
    """Repo-relative POSIX path when possible, for ASCII-only reporting."""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _from_env(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


# ---------------------------------------------------------------------------
# R2.8 -- "was this artifact read from version control?"
# ---------------------------------------------------------------------------
def _gitignore_patterns(gitignore: Path = GITIGNORE) -> tuple[str, ...]:
    """The ignore patterns declared by ``.gitignore`` (``encoding='utf-8'``, E-S13-07).

    Negations (``!pattern``) are skipped rather than interpreted: a re-inclusion of the
    artifact path is precisely the state this gate must not treat as ignored, so
    ignoring the negation makes the check conservative in the safe direction.
    """
    try:
        text = gitignore.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ()
    return tuple(
        line
        for line in (raw.strip() for raw in text.splitlines())
        if line and not line.startswith("#") and not line.startswith("!")
    )


def is_git_ignored(path: Path, *, gitignore: Path = GITIGNORE) -> bool:
    """Whether ``path`` is covered by a declared ignore pattern.

    A deliberately narrow matcher: the repo-relative path and every ancestor directory
    are tested against each pattern, with and without a trailing separator. That covers
    the two forms this gate cares about -- a directory rule (``artifacts/``) and an
    explicit file rule (``artifacts/uplift/result.json``). It is not a full gitignore
    implementation and does not need to be: no process may be spawned to ask git
    (I-0), so the *declaration* is the authority, and losing the declaration is exactly
    the change that would let the artifact be committed again.
    """
    try:
        rel = Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return False
    parts = rel.split("/")
    candidates = [rel]
    for index in range(1, len(parts)):
        ancestor = "/".join(parts[:index])
        candidates.append(ancestor)
        candidates.append(ancestor + "/")
    for pattern in _gitignore_patterns(gitignore):
        bare = pattern.rstrip("/")
        for candidate in candidates:
            if fnmatch.fnmatch(candidate, pattern) or fnmatch.fnmatch(candidate, bare):
                return True
            if pattern.endswith("/") and candidate.startswith(pattern):
                return True
    return False


def artifact_is_version_controlled(
    artifact: Path = RESULT_ARTIFACT,
    *,
    tracked: bool | None = None,
    gitignore: Path = GITIGNORE,
) -> bool:
    """Whether ``artifact`` must be treated as read from version control (R2.8).

    An in-repo path that no ignore rule covers is treated as version-controlled, because
    that is the condition under which it can be (and previously was) committed. A path
    outside the repository cannot be tracked by this repository, so it is not.
    ``tracked`` lets a caller supply a fact it established another way (a CI step that
    ran ``git ls-files``), which then wins over the derivation.
    """
    if tracked is not None:
        return tracked
    try:
        Path(artifact).resolve().relative_to(ROOT)
    except ValueError:
        return False
    return not is_git_ignored(artifact, gitignore=gitignore)


# ---------------------------------------------------------------------------
# The evaluating job's identity
# ---------------------------------------------------------------------------
class RunContext(BaseModel):
    """Who is asking the gate for a verdict (R2.7, R2.8, AD-9).

    Attributes:
        revision: The source revision the evaluating job is running at, or
            :data:`UNATTRIBUTED` when it could not be resolved.
        run_id: The evaluating job's run identifier, or :data:`UNATTRIBUTED`.
        generating_job: True only when this job also *ran the harness* in this run
            (``--require-fresh-run``). False makes the check report SKIP (AD-9, CF-4).
        artifact_tracked: True when the artifact must be treated as read from version
            control, which is inadmissible irrespective of its contents (R2.8).
        expected_seeds: The scenario base seed set the evaluating job's harness
            invocation used, when the caller knows it. ``None`` adopts the artifact's own
            set -- the seed set is not independently knowable by the gate, and it is the
            ``run_id`` equality check that makes the artifact same-run.
        expected_arms: As ``expected_seeds``, for the arm identifiers.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    revision: str = UNATTRIBUTED
    run_id: str = UNATTRIBUTED
    generating_job: bool = False
    artifact_tracked: bool = False
    expected_seeds: tuple[int, ...] | None = None
    expected_arms: tuple[str, ...] | None = None

    @property
    def is_attributed(self) -> bool:
        """True iff both the revision and the run identifier actually resolved."""
        return (
            bool(self.revision)
            and bool(self.run_id)
            and self.revision != UNATTRIBUTED
            and self.run_id != UNATTRIBUTED
        )


def resolve_run_context(
    *,
    generating_job: bool = False,
    artifact: Path = RESULT_ARTIFACT,
    tracked: bool | None = None,
) -> RunContext:
    """Build a :class:`RunContext` from the environment, recording absence honestly.

    ``revision`` falls back to ``$SYNAPSE_REVISION`` then ``$GITHUB_SHA``; ``run_id`` to
    ``$SYNAPSE_RUN_ID`` then ``$GITHUB_RUN_ID``. When neither resolves the field records
    :data:`UNATTRIBUTED`, and an unattributed evaluating job can never satisfy R2.8 --
    which is the honest outcome for a run taken outside a CI job (I-7).
    """
    return RunContext(
        revision=_from_env(_REVISION_ENV_KEYS) or UNATTRIBUTED,
        run_id=_from_env(_RUN_ID_ENV_KEYS) or UNATTRIBUTED,
        generating_job=generating_job,
        artifact_tracked=artifact_is_version_controlled(artifact, tracked=tracked),
    )


# ---------------------------------------------------------------------------
# Admissibility (R2.1, R2.2, R2.8)
# ---------------------------------------------------------------------------
class Admission(BaseModel):
    """The gate's decision about whether an artifact is admissible evidence.

    ``reasons`` is empty iff ``outcome == "admitted"``. Every reason is printed verbatim
    by :func:`run`, so an ``EXIT_UNAVAILABLE`` always names why the measurement was
    treated as unavailable (R2.1, R2.2, R2.8).

    ``proof`` is populated *only* on an admitted artifact. That is what makes R2.10's
    "same-run proof" requirement structural rather than a convention: a floor raise reads
    the proof off this model, and an inadmissible artifact simply has none to offer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    artifact_path: str
    outcome: Outcome
    reasons: tuple[str, ...] = ()
    proof: PoweredProof | None = None
    headline_uplift: float | None = None
    replicates_per_arm: int | None = None
    provenance_revision: str | None = None
    provenance_run_id: str | None = None
    version_controlled: bool = False
    generating_job: bool = False

    @property
    def admitted(self) -> bool:
        """True iff this artifact may be used as evidence for a verdict."""
        return self.outcome == "admitted"


def _read_artifact(artifact: Path) -> tuple["UpliftArtifact | None", str | None]:
    """Read and shape-validate the artifact, or return the reason it is unusable.

    The :class:`~uplift.harness.UpliftArtifact` import is deferred: the harness pulls in
    numpy, the twin, and the consensus arm, and this gate must stay cheap enough for
    ``verify_claims`` to call on a fresh clone. An import failure is reported as an
    unavailable reason rather than raised, because a gate that cannot read its input has
    no measurement -- not a pass (I-7).
    """
    try:
        from uplift.harness import UpliftArtifact as _Artifact
    except Exception as exc:  # noqa: BLE001 -- any import failure is "no measurement"
        return None, f"the uplift artifact model could not be imported: {exc}"

    path = Path(artifact)
    display = _display(path)
    if not path.is_file():
        return None, (
            f"no artifact at {display}: no uplift run wrote one in this job "
            "(run `python -m uplift.cli --full --replicates "
            f"{MIN_POWERED_REPLICATES}` first)"
        )
    try:
        return _Artifact.read(path), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"artifact at {display} is unreadable: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"artifact at {display} is not valid JSON: {exc}"
    except ValidationError as exc:
        return None, (
            f"artifact at {display} does not carry the required shape "
            f"(R2.1 boolean `incomplete`, R2.2 integral replicates-per-arm, R2.3 finite "
            f"`headline_uplift` and a provenance record): {exc}"
        )
    except ValueError as exc:  # pragma: no cover -- defensive; JSON/pydantic subclass it
        return None, f"artifact at {display} is malformed: {exc}"


def _provenance_reasons(artifact: "UpliftArtifact", run: RunContext) -> tuple[str, ...]:
    """Every way the artifact's provenance fails to match this job's run (R2.8)."""
    recorded = artifact.provenance
    if not run.is_attributed:
        return (
            f"the evaluating job is unattributed (revision={run.revision!r}, "
            f"run_id={run.run_id!r}): an artifact cannot be matched to a run that does "
            "not name itself, so set SYNAPSE_REVISION/GITHUB_SHA and "
            "SYNAPSE_RUN_ID/GITHUB_RUN_ID in the job that runs the harness (R2.8)",
        )

    from uplift.harness import UpliftProvenance

    expected = UpliftProvenance(
        arms=run.expected_arms if run.expected_arms is not None else recorded.arms,
        replicates_per_arm=recorded.replicates_per_arm,
        revision=run.revision,
        run_id=run.run_id,
        seeds=run.expected_seeds if run.expected_seeds is not None else recorded.seeds,
        written_at=recorded.written_at,
    )

    reasons: list[str] = []
    if not recorded.matches(expected):
        reasons.append(
            "provenance does not match the run performed in this job (R2.8): artifact "
            f"revision={recorded.revision!r} seeds={recorded.seeds} "
            f"arms={recorded.arms}; job revision={expected.revision!r} "
            f"seeds={expected.seeds} arms={expected.arms}"
        )
    if recorded.run_id != run.run_id:
        reasons.append(
            "the artifact was not produced by this run (R2.8): artifact "
            f"run_id={recorded.run_id!r}, evaluating run_id={run.run_id!r}"
        )
    return tuple(reasons)


def admit(
    artifact: Path = RESULT_ARTIFACT,
    run: RunContext | None = None,
) -> Admission:
    """Decide whether ``artifact`` is admissible evidence for a C60 verdict.

    Rejection order (first match wins), each with the reason recorded for printing:

    1. The artifact is under version control -> ``unavailable`` (R2.8). Checked first and
       irrespective of trigger, because a committed measurement is a defect in the tree
       that every run should surface, not one the scheduled job alone can see.
    2. The caller is not the generating job -> ``skip`` (AD-9, CF-4). Whatever is on disk
       was not produced in this run, so there is nothing to certify; R2.9 excludes the
       SKIP from the published PASS count.
    3. The artifact is absent, unreadable, not JSON, or does not satisfy the shape the
       harness is required to write -> ``unavailable`` (R2.1, R2.2, R2.3).
    4. The artifact states it is not a completed, powered, in-bound, attributed run ->
       ``unavailable``, naming each of :attr:`UpliftArtifact.unavailable_reasons`
       verbatim (R2.1 ``incomplete``, R2.2 ``< MIN_POWERED_REPLICATES``, fidelity).
    5. The provenance does not match the run performed in this job -> ``unavailable``
       (R2.8).
    6. The payload cannot evidence its own power at all -> ``unavailable`` (R2.2).

    Anything surviving all six is ``admitted`` and carries the
    :class:`~uplift.uplift_floor.PoweredProof` :func:`verdict` derives from.
    """
    context = run if run is not None else resolve_run_context(artifact=artifact)
    display = _display(Path(artifact))

    if context.artifact_tracked:
        return Admission(
            artifact_path=display,
            outcome="unavailable",
            version_controlled=True,
            generating_job=context.generating_job,
            reasons=(
                f"no ignore rule covers {display}, so the C60 evidence path is under "
                "version control: a committed measurement is not evidence of a run, and "
                "R2.8 rejects an artifact read from version control. Restore the "
                "`.gitignore` entry for this path.",
            ),
        )

    if not context.generating_job:
        return Admission(
            artifact_path=display,
            outcome="skip",
            version_controlled=False,
            generating_job=False,
            reasons=(
                "no uplift run was performed in this job: C60 returns PASS/FAIL only in "
                "the job that produced its evidence in this run (AD-9, CF-4), so this "
                "check reports SKIP and is excluded from the published PASS count "
                "(R2.9). A SKIP is not a PASS.",
            ),
        )

    parsed, error = _read_artifact(Path(artifact))
    if parsed is None:
        return Admission(
            artifact_path=display,
            outcome="unavailable",
            version_controlled=False,
            generating_job=True,
            reasons=(error or f"artifact at {display} is unavailable",),
        )

    reasons = tuple(parsed.unavailable_reasons) + _provenance_reasons(parsed, context)
    proof = parsed.as_powered_proof()
    if proof is None:
        reasons += (
            "the artifact cannot evidence its own power: no usable headline/replicate "
            "pair was recoverable from the payload (R2.2)",
        )
    return Admission(
        artifact_path=display,
        outcome="unavailable" if reasons else "admitted",
        version_controlled=False,
        generating_job=True,
        reasons=reasons,
        proof=None if reasons else proof,
        headline_uplift=parsed.headline_uplift,
        replicates_per_arm=parsed.replicates_per_arm,
        provenance_revision=parsed.provenance.revision,
        provenance_run_id=parsed.provenance.run_id,
    )


# ---------------------------------------------------------------------------
# The verdict (R2.4)
# ---------------------------------------------------------------------------
def verdict(proof: PoweredProof | None, *, floor: float = UPLIFT_FLOOR) -> int:
    """Derive the exit code from :func:`uplift.uplift_floor.is_proven_uplift` (R2.4).

    ``EXIT_PASS`` iff ``is_proven_uplift(proof, floor)``. Otherwise ``EXIT_REGRESSION``
    only for a powered, complete, within-fidelity-bound measurement that is strictly
    below the floor -- the one case where a real measurement says the system got worse --
    and ``EXIT_UNAVAILABLE`` for everything else.

    Two consequences are worth stating because they are the whole point of R2.4:

      * ``within_fidelity_bound in (None, False)`` is non-zero *irrespective of headline
        magnitude*. A large gain measured in a twin that drifted out of bound is not a
        gain that has been shown.
      * A powered, complete, in-bound run measuring ``0.0`` against a floor of ``0.0``
        exits ``EXIT_UNAVAILABLE``, not ``EXIT_PASS``. ``is_proven_uplift`` requires a
        strictly positive headline, so "at least zero" is no longer spelled "proven".
        That is the exact artifact the audit found this gate passing.

    Replacing ``is_proven_uplift`` with a stub returning the opposite verdict changes the
    code this function returns, which is R2.4's falsification clause.
    """
    if is_proven_uplift(proof, floor):
        return EXIT_PASS
    if proof is None:
        return EXIT_UNAVAILABLE
    if not proof.is_powered or proof.incomplete or proof.within_fidelity_bound is not True:
        return EXIT_UNAVAILABLE
    if not math.isfinite(proof.headline_uplift):
        return EXIT_UNAVAILABLE
    if proof.headline_uplift < floor:
        return EXIT_REGRESSION
    return EXIT_UNAVAILABLE


def verdict_reason(
    proof: PoweredProof | None, code: int, *, floor: float = UPLIFT_FLOOR
) -> str:
    """One ASCII line explaining ``code``, for the gate's printed report."""
    if code == EXIT_PASS and proof is not None:
        return (
            f"proven uplift {proof.headline_uplift} pp >= floor {floor} over "
            f"{proof.replicates} replicates/arm, complete and within the twin fidelity "
            "bound"
        )
    if code == EXIT_REGRESSION and proof is not None:
        return (
            f"REGRESSION - measured uplift {proof.headline_uplift} pp < floor {floor} "
            f"over {proof.replicates} replicates/arm"
        )
    if proof is None:
        return "no measurement was available, so no uplift is proven"
    if not proof.is_powered:
        return (
            f"under-powered: {proof.replicates} replicates per arm, "
            f"{MIN_POWERED_REPLICATES} required (INV-TW-002)"
        )
    if proof.incomplete:
        return "the run is incomplete, so its headline number is not a measurement"
    if proof.within_fidelity_bound is not True:
        return (
            "not within the twin fidelity bound "
            f"(within_fidelity_bound={proof.within_fidelity_bound!r}); the headline "
            f"magnitude {proof.headline_uplift} pp does not change that"
        )
    return (
        f"measured uplift {proof.headline_uplift} pp is not a proven gain: "
        f"is_proven_uplift requires a strictly positive headline at or above floor "
        f"{floor}"
    )


# ---------------------------------------------------------------------------
# R2.10 -- a floor raise is admitted only against a same-run powered proof
# ---------------------------------------------------------------------------
def admit_floor_raise(
    proposed: float,
    admission: Admission,
    *,
    previous: float = UPLIFT_FLOOR,
) -> float:
    """Return the floor ``proposed`` may be committed at, or raise (R2.10).

    Delegates to :func:`uplift.uplift_floor.ratchet_to_measured`, which rejects a lower
    value outright and admits a raise only against a powered, complete,
    within-fidelity-bound proof measuring at least ``proposed``. The proof is taken from
    ``admission`` and is ``None`` unless the artifact was admitted, so a raise can never
    be backed by an artifact this gate rejected -- which is what makes "a proof from the
    same job" mechanical instead of procedural.

    Raises:
        FloorRatchetError: The proposal would lower the committed floor.
        UnprovenFloorRaiseError: The raise has no supporting same-run proof.
    """
    return ratchet_to_measured(
        previous, proposed, admission.proof if admission.admitted else None
    )


# ---------------------------------------------------------------------------
# Check_Registry projection (AD-9, R2.9)
# ---------------------------------------------------------------------------
def registry_status(admission: Admission, code: int) -> tuple[str, str]:
    """The ``(status, detail)`` C60 reports into the Check_Registry.

    Only an admitted artifact whose verdict is :data:`EXIT_PASS` yields ``PASS``, so the
    published PASS count can never include a measurement nobody took (R2.9, I-7):

      * a version-controlled artifact -> ``FAIL``: a committed measurement is a defect in
        the tree, visible on every run rather than only in the scheduled job;
      * not the generating job -> ``SKIP`` (AD-9, CF-4);
      * inadmissible evidence in the generating job -> ``FAIL``: the job whose purpose
        was to measure did not deliver an admissible measurement;
      * admitted and below the floor -> ``FAIL`` (a real regression);
      * admitted with no proven gain -> ``SKIP``: an honest non-success, excluded from
        the PASS count, and not a defect.
    """
    detail = "; ".join(admission.reasons)
    if admission.version_controlled:
        return "FAIL", detail
    if admission.outcome == "skip":
        return "SKIP", detail
    if admission.outcome == "unavailable":
        return ("FAIL" if admission.generating_job else "SKIP"), detail
    reason = verdict_reason(admission.proof, code)
    if code == EXIT_PASS:
        return "PASS", reason
    if code == EXIT_REGRESSION:
        return "FAIL", reason
    return "SKIP", reason


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _payload(admission: Admission, code: int, floor: float) -> dict[str, object]:
    proof = admission.proof
    return {
        "admitted": admission.admitted,
        "artifact": admission.artifact_path,
        "exit_code": code,
        "generating_job": admission.generating_job,
        "headline_uplift": admission.headline_uplift,
        "is_proven_uplift": is_proven_uplift(proof, floor),
        "outcome": admission.outcome,
        "reasons": list(admission.reasons),
        "registry_status": registry_status(admission, code)[0],
        "replicates_per_arm": admission.replicates_per_arm,
        "required_replicates_per_arm": MIN_POWERED_REPLICATES,
        "uplift_floor": floor,
        "verdict_reason": verdict_reason(proof, code, floor=floor),
        "version_controlled": admission.version_controlled,
        "within_fidelity_bound": None if proof is None else proof.within_fidelity_bound,
    }


def run(
    *,
    as_json: bool = False,
    check: bool = False,
    require_fresh_run: bool = False,
    propose_floor: float | None = None,
    artifact: Path | None = None,
) -> int:
    """Evaluate the gate and report. Returns the exit code when ``check`` is set.

    Without ``--check`` this is a reporting run and always returns :data:`EXIT_PASS`,
    matching the other audit gates' summary mode.
    """
    target = RESULT_ARTIFACT if artifact is None else Path(artifact)
    context = resolve_run_context(generating_job=require_fresh_run, artifact=target)
    admission = admit(target, context)
    # A skip and an inadmissible artifact are both EXIT_UNAVAILABLE for the *step*: a
    # SKIP is not a PASS (I-7). The registry projection is what distinguishes them
    # (:func:`registry_status`), so a PR-path run reports SKIP rather than reddening CI.
    code = verdict(admission.proof) if admission.admitted else EXIT_UNAVAILABLE

    raise_error: str | None = None
    if propose_floor is not None:
        try:
            admit_floor_raise(propose_floor, admission)
        except FloorRatchetError as exc:
            raise_error = str(exc)

    if as_json:
        payload = _payload(admission, code, UPLIFT_FLOOR)
        payload["proposed_floor"] = propose_floor
        payload["floor_raise_rejected"] = raise_error
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status, detail = registry_status(admission, code)
        marker = {"PASS": "[OK]", "FAIL": "[XX]", "SKIP": "[??]"}[status]
        print(f"{marker} uplift-truth: {status} - {detail}")
        for reason in admission.reasons:
            print(f"     - {reason}")
        if admission.admitted:
            print(f"     floor {UPLIFT_FLOOR}; exit code {code}")
        if raise_error is not None:
            print(f"[XX] uplift-truth: floor raise rejected - {raise_error}")
        elif propose_floor is not None:
            print(f"[OK] uplift-truth: floor may be raised to {propose_floor}")

    if check:
        if raise_error is not None:
            return EXIT_UNAVAILABLE
        return code
    return EXIT_PASS


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="uplift_truth",
        description="C60 - the SYNAPSE decision-integrity uplift gate (R2).",
    )
    parser.add_argument("--json", dest="as_json", action="store_true", help="machine JSON")
    parser.add_argument(
        "--check", action="store_true", help="exit 0 pass / 1 regression / 2 unavailable"
    )
    parser.add_argument(
        "--require-fresh-run",
        action="store_true",
        help=(
            "declare this the job that ran the harness; without it the check reports "
            "SKIP (AD-9, CF-4)"
        ),
    )
    parser.add_argument(
        "--propose-floor",
        type=float,
        default=None,
        metavar="PP",
        help="check whether UPLIFT_FLOOR may be raised to PP against this run's proof",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    sys.exit(
        run(
            as_json=args.as_json,
            check=args.check,
            require_fresh_run=args.require_fresh_run,
            propose_floor=args.propose_floor,
        )
    )


__all__ = [
    "EXIT_PASS",
    "EXIT_REGRESSION",
    "EXIT_UNAVAILABLE",
    "GITIGNORE",
    "MIN_POWERED_REPLICATES",
    "RESULT_ARTIFACT",
    "UNATTRIBUTED",
    "UPLIFT_FLOOR",
    "Admission",
    "Outcome",
    "RunContext",
    "admit",
    "admit_floor_raise",
    "artifact_is_version_controlled",
    "is_git_ignored",
    "registry_status",
    "resolve_run_context",
    "run",
    "verdict",
    "verdict_reason",
]
