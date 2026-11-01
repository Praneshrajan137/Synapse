# Feature: decision-quality-proof, Property 86: The Power_Report is monotone, distinct in kind,
# revision-bound and floor-respecting
"""The Power_Report states what the harness can see, and refuses every number it cannot support.

Task 17.4 (R6.5-R6.9, R6.16). Subjects: ``uplift/power.py`` and
``uplift/uplift_floor.py::powered_replicate_floor``.

**Clauses, each asserted unconditionally.**

1. **Monotone (R6.5, R6.8).** The minimum detectable effect falls strictly as replicates rise and
   rises strictly with the variance; the derived requirement never falls as the variance rises
   and never rises as the margin widens. The strict forms are asserted where binary64 rounding
   cannot merge two values -- replicate counts in ``[2, 10**7]``, variances in ``[1e-6, 1e6]``
   scaled by at least ``1 + 1e-6``. The non-strict forms are asserted over variances in
   ``[1e-12, 1e12]`` and margins in ``[1e-6, 1e6]``, because every operation the requirement
   composes is correctly rounded and therefore monotone. Both are also held to the formula
   computed here, independently of the module.
2. **Re-derived (R6.5).** Every derived field, tampered, is refused by the model and through the
   reader, while the untampered payload is accepted -- so the refusal is about the edit. A drift
   inside ``REDERIVATION_REL_TOL`` is accepted: the declared cross-platform allowance, stated
   rather than hidden.
3. **Distinct in kind (R6.6).** ``kind`` is ``"power-report"``. No result artifact can carry it
   (that model forbids extra keys and declares no ``kind``), and a payload without it, with
   another kind, shaped as a result artifact, or carrying any key only a result artifact
   declares is refused. The result reader refuses a report, and ``PoweredProof`` recovers no
   proof from one. The committed path is not ignored, so it can be committed; the result path
   is ignored. A report that does not name its run, or names it unattributed, is refused.
4. **Revision-bound (R6.7).** One changed byte, or one renamed file, moves the digest; CRLF
   against LF, file creation order, pattern order, overlapping patterns and a file under
   ``__pycache__`` do not. A source set that cannot be read refuses rather than digesting less,
   and ``describes_revision`` follows the digest. Every pattern of ``POWER_SOURCE_SET`` selects a
   file in this tree.
5. **Floor-respecting (R6.9, R6.16).** ``inv_tw_002_binding`` holds exactly when the requirement
   is below ``MIN_SCENARIOS``. The effective floor is never below ``MIN_SCENARIOS`` or the
   requirement, and is the requirement whenever that exceeds ``MIN_POWERED_REPLICATES`` -- stated
   against the constant, so the clause stays true if R6.9 ever raises it. Both sides of each
   boundary are built by construction in every example.
6. **Against arm E only (ADR-055 D2.7).** Any comparator but ``tuned_static`` is refused, and the
   same inputs naming ``tuned_static`` are accepted.
7. **Refused, never repaired; persisted canonically.** An input outside the formulas' domain
   yields no report at all. The committed form is the repo's canonical JSON and reads back as the
   same report; an absent report reads as ``None`` and a present malformed one raises.

**Pure.** Files are written only under pytest's temporary directories; the repository is read,
never written. No twin, no arm, no subprocess. Budget inherited from ``HYPOTHESIS_PROFILE``.
Locus: ``ci.yml::uplift-verify`` fast step.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, fields, replace
from pathlib import Path
from statistics import NormalDist
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from digital_twin.simulation.monte_carlo import MIN_SCENARIOS
from scripts.audit.uplift_truth import RESULT_ARTIFACT, is_git_ignored
from uplift.harness import UNATTRIBUTED, UpliftArtifact
from uplift.power import (
    INV_TW_002_FLOOR,
    POWER_REPORT_KIND,
    POWER_REPORT_PATH,
    POWER_SOURCE_SET,
    REDERIVATION_REL_TOL,
    PowerQuantities,
    PowerReport,
    PowerReportError,
    build_power_report,
    declared_source_files,
    derived_replicate_requirement,
    describes_revision,
    minimum_detectable_effect,
    power_quantities,
    read_power_report,
    source_set_digest,
    write_power_report,
)
from uplift.regret import ARM_LABELS
from uplift.tuned_static import TUNED_STATIC_ARM
from uplift.uplift_floor import MIN_POWERED_REPLICATES, PoweredProof, powered_replicate_floor

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_CONTENT_DIGEST: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")
_SHA: Final[str] = "a" * 40
_RUN_ID: Final[str] = "run-35125443185"
_VARIANCE_SOURCE: Final[str] = "per-replicate paired objective difference against tuned_static"

#: The one-file instrument most reports are built over, and the glob the revision clauses use.
_INSTRUMENT: Final[tuple[str, ...]] = ("instrument.py",)
_GLOB: Final[tuple[str, ...]] = ("pkg/**/*.py",)

#: Every field a report derives, read off the one function both sides of the model use.
_DERIVED_FIELDS: Final[tuple[str, ...]] = tuple(field.name for field in fields(PowerQuantities))
_EFFECT_FIELDS: Final[tuple[str, ...]] = (
    "minimum_detectable_effect",
    "detectable_effect_at_min_powered",
)

#: Keys a result artifact declares and a Power_Report does not.
_RESULT_ONLY_KEYS: Final[tuple[str, ...]] = tuple(
    sorted(set(UpliftArtifact.model_fields) - set(PowerReport.model_fields))
)


@dataclass(frozen=True)
class _Inputs:
    """Everything a report is derived from, apart from its instrument and its provenance."""

    replicates_per_arm: int
    observed_variance: float
    alpha: float
    detection_probability: float
    materiality_margin: float


_VALID: Final[_Inputs] = _Inputs(
    replicates_per_arm=MIN_POWERED_REPLICATES,
    observed_variance=4.0,
    alpha=0.05,
    detection_probability=0.8,
    materiality_margin=0.4,
)

_ALPHAS = st.floats(min_value=1e-4, max_value=0.5)
_POWERS = st.floats(min_value=0.5, max_value=0.999)
_VARIANCES = st.floats(min_value=1e-6, max_value=1e6)
_INPUTS = st.builds(
    _Inputs,
    replicates_per_arm=st.integers(min_value=2, max_value=10**7),
    observed_variance=_VARIANCES,
    alpha=_ALPHAS,
    detection_probability=_POWERS,
    materiality_margin=st.floats(min_value=1e-3, max_value=1e3),
)

#: File names over an alphabet without ``z``, so appending one renames without a collision.
_NAMES = st.text(alphabet="abcdefgh_", min_size=1, max_size=8)
_LINES = st.lists(st.text(alphabet="abc xyz=#:'0123456789", max_size=16), min_size=1, max_size=5)


@st.composite
def _trees(draw: st.DrawFn) -> dict[str, bytes]:
    """Repo-relative POSIX path -> LF bytes; every file ends in a newline, so CRLF moves bytes."""
    names = draw(st.lists(_NAMES, min_size=1, max_size=4, unique=True))
    return {f"pkg/{name}.py": ("\n".join(draw(_LINES)) + "\n").encode("ascii") for name in names}


def _z_sum(alpha: float, detection_probability: float) -> float:
    """``z_alpha + z_beta``, computed here rather than read from the module under test."""
    standard = NormalDist()
    return standard.inv_cdf(1.0 - alpha / 2.0) + standard.inv_cdf(detection_probability)


def _margin_for(inputs: _Inputs, requirement: float) -> float:
    """The margin at which ``inputs`` need ``requirement`` replicates (squared ratio)."""
    sigma = math.sqrt(inputs.observed_variance)
    return _z_sum(inputs.alpha, inputs.detection_probability) * sigma / math.sqrt(requirement)


def _quantities(inputs: _Inputs) -> PowerQuantities:
    return power_quantities(
        replicates_per_arm=inputs.replicates_per_arm,
        observed_variance=inputs.observed_variance,
        alpha=inputs.alpha,
        detection_probability=inputs.detection_probability,
        materiality_margin=inputs.materiality_margin,
    )


def _build(root: Path, source_set: Sequence[str], inputs: _Inputs, comparator: str) -> PowerReport:
    """A report built exactly as production builds one; every argument is stated."""
    return build_power_report(
        root=root,
        source_set=source_set,
        source_run_id=_RUN_ID,
        source_revision_sha=_SHA,
        replicates_per_arm=inputs.replicates_per_arm,
        observed_variance=inputs.observed_variance,
        variance_source=_VARIANCE_SOURCE,
        alpha=inputs.alpha,
        detection_probability=inputs.detection_probability,
        materiality_margin=inputs.materiality_margin,
        comparator=comparator,
    )


def _canonical(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _materialise(root: Path, tree: Mapping[str, bytes], order: Sequence[str]) -> Path:
    """Write ``tree`` under ``root`` in ``order``, byte for byte (no newline translation)."""
    for relative in order:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(tree[relative])
    return root


@pytest.fixture(scope="module")
def instrument(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A one-file instrument, for reports whose revision is not the clause under test."""
    root = tmp_path_factory.mktemp("power-instrument")
    (root / _INSTRUMENT[0]).write_bytes(b"MEASURED_AGAINST = 'tuned_static'\n")
    return root


# ---------------------------------------------------------------------------
# Clause 1 -- monotone
# ---------------------------------------------------------------------------
@given(
    alpha=_ALPHAS,
    power=_POWERS,
    variance=_VARIANCES,
    fewer=st.integers(min_value=2, max_value=10**7 - 1),
    more_by=st.integers(min_value=1, max_value=10**7),
    factor=st.floats(min_value=1.0 + 1e-6, max_value=1e3),
)
def test_the_detectable_effect_falls_strictly_with_replicates_and_rises_strictly_with_variance(
    alpha: float, power: float, variance: float, fewer: int, more_by: int, factor: float
) -> None:
    """R6.5: a larger run sees a smaller effect, and a noisier contrast needs a larger one."""
    more = min(fewer + more_by, 10**7)

    def mde(of_variance: float, replicates: int) -> float:
        return minimum_detectable_effect(
            variance=of_variance, replicates=replicates, alpha=alpha, detection_probability=power
        )

    assert fewer < more
    assert mde(variance, fewer) > mde(variance, more)
    assert mde(variance, fewer) < mde(variance * factor, fewer)
    independent = _z_sum(alpha, power) * math.sqrt(variance) / math.sqrt(fewer)
    assert math.isclose(mde(variance, fewer), independent, rel_tol=REDERIVATION_REL_TOL)


@given(
    alpha=_ALPHAS,
    power=_POWERS,
    variances=st.lists(st.floats(min_value=1e-12, max_value=1e12), min_size=2, max_size=2),
    margins=st.lists(st.floats(min_value=1e-6, max_value=1e6), min_size=2, max_size=2),
)
def test_the_requirement_never_falls_as_variance_rises_nor_rises_as_the_margin_widens(
    alpha: float, power: float, variances: list[float], margins: list[float]
) -> None:
    """A noisier contrast, or a finer margin, never needs fewer replicates."""
    quiet, noisy = sorted(variances)
    fine, coarse = sorted(margins)

    def required(variance: float, margin: float) -> int:
        return derived_replicate_requirement(
            variance=variance, margin=margin, alpha=alpha, detection_probability=power
        )

    assert required(quiet, fine) <= required(noisy, fine)
    assert required(quiet, coarse) <= required(noisy, coarse)
    assert required(quiet, coarse) <= required(quiet, fine)
    assert required(noisy, coarse) <= required(noisy, fine)
    assert required(quiet, coarse) >= 1
    ratio = _z_sum(alpha, power) * math.sqrt(noisy) / fine
    squared = ratio * ratio
    assert squared * (1.0 - 1e-12) <= required(noisy, fine) <= squared * (1.0 + 1e-12) + 1.0


# ---------------------------------------------------------------------------
# Clause 2 -- re-derived, never trusted
# ---------------------------------------------------------------------------
@given(
    inputs=_INPUTS,
    shift=st.sampled_from((-3, -2, -1, 1, 2, 3)),
    scale=st.floats(min_value=1e3 * REDERIVATION_REL_TOL, max_value=0.5),
    sign=st.sampled_from((-1.0, 1.0)),
)
def test_a_tampered_derived_field_is_refused_and_the_formulas_own_value_is_not(
    inputs: _Inputs,
    shift: int,
    scale: float,
    sign: float,
    instrument: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Each derived field is recomputed on read; a value its formula does not give is refused."""
    report = _build(instrument, _INSTRUMENT, inputs, TUNED_STATIC_ARM)
    payload = report.model_dump(mode="json")
    assert PowerReport.model_validate(payload) == report

    tampered: dict[str, object] = {
        name: payload[name] * (1.0 + sign * scale) for name in _EFFECT_FIELDS
    }
    tampered["derived_replicate_requirement"] = payload["derived_replicate_requirement"] + shift
    tampered["inv_tw_002_binding"] = not payload["inv_tw_002_binding"]
    assert sorted(tampered) == sorted(_DERIVED_FIELDS)

    root = tmp_path_factory.mktemp("tampered")
    for index, name in enumerate(sorted(tampered)):
        edited = {**payload, name: tampered[name]}
        refusal = rf"{name}=\S+ but the formula gives"
        with pytest.raises(ValidationError, match=refusal):
            PowerReport.model_validate(edited)
        path = root / f"edit-{index}.json"
        path.write_text(_canonical(edited), encoding="utf-8")
        with pytest.raises(PowerReportError, match=refusal):
            read_power_report(path)

    for name in _EFFECT_FIELDS:
        drifted = {**payload, name: payload[name] * (1.0 + REDERIVATION_REL_TOL / 10.0)}
        assert drifted[name] != payload[name]
        assert PowerReport.model_validate(drifted).model_dump(mode="json") == drifted


# ---------------------------------------------------------------------------
# Clause 3 -- distinct in kind
# ---------------------------------------------------------------------------
_JSON_SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10, max_value=10),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=8),
)


@given(
    inputs=_INPUTS,
    other_kind=st.text(max_size=16).filter(lambda kind: kind != POWER_REPORT_KIND),
    grafted=_JSON_SCALARS,
)
def test_a_result_artifact_payload_is_refused_and_a_report_is_never_read_as_a_result(
    inputs: _Inputs,
    other_kind: str,
    grafted: object,
    instrument: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """R6.6: the two artifact classes cannot be mistaken for each other, in either direction."""
    report = _build(instrument, _INSTRUMENT, inputs, TUNED_STATIC_ARM)
    payload = report.model_dump(mode="json")
    assert report.kind == POWER_REPORT_KIND == payload["kind"] == "power-report"

    # No result artifact can carry the discriminator, and this model requires it.
    assert "kind" not in UpliftArtifact.model_fields
    assert UpliftArtifact.model_config.get("extra") == "forbid"
    assert _RESULT_ONLY_KEYS
    refused: list[dict[str, object]] = [
        {key: value for key, value in payload.items() if key != "kind"},
        {**payload, "kind": other_kind},
        {key: payload.get(key, grafted) for key in UpliftArtifact.model_fields},
        *({**payload, key: grafted} for key in _RESULT_ONLY_KEYS),
    ]
    root = tmp_path_factory.mktemp("kinds")
    for index, candidate in enumerate(refused):
        with pytest.raises(ValidationError):
            PowerReport.model_validate(candidate)
        path = root / f"candidate-{index}.json"
        path.write_text(_canonical(candidate), encoding="utf-8")
        with pytest.raises(PowerReportError):
            read_power_report(path)

    # The other direction: the result reader refuses a report, and no proof comes from one.
    with pytest.raises(ValidationError):
        UpliftArtifact.model_validate(payload)
    assert PoweredProof.from_payload(payload) is None


def test_the_committed_report_path_is_committable_and_is_not_the_result_artifact_path() -> None:
    """R6.6: the report is committed with the tree; R2.8: the result artifact never is."""
    committed = _ROOT / POWER_REPORT_PATH
    assert not is_git_ignored(committed)
    assert is_git_ignored(RESULT_ARTIFACT)
    assert committed.resolve() != RESULT_ARTIFACT.resolve()
    assert "artifacts" not in Path(POWER_REPORT_PATH).parts


_UNNAMED: Final[str] = "does not name the run that produced this report"
_NOT_A_COMMIT: Final[str] = "is not a full lowercase git object name"
_NOT_A_DIGEST: Final[str] = "is not a sha256 content digest"
_UNNAMED_PROVENANCE: Final[tuple[tuple[str, str, str], ...]] = (
    ("source_run_id", UNATTRIBUTED, _UNNAMED),
    ("source_run_id", "", _UNNAMED),
    ("source_run_id", "   ", _UNNAMED),
    ("source_run_id", " run-1", _UNNAMED),
    ("source_revision_sha", "abc1234", _NOT_A_COMMIT),
    ("source_revision_sha", "A" * 40, _NOT_A_COMMIT),
    ("source_revision_sha", "HEAD", _NOT_A_COMMIT),
    ("harness_revision", "a" * 40, _NOT_A_DIGEST),
    ("harness_revision", "A" * 64, _NOT_A_DIGEST),
)


@pytest.mark.parametrize(("name", "value", "refusal"), _UNNAMED_PROVENANCE)
def test_a_report_that_does_not_name_its_run_and_revision_is_refused(
    name: str, value: str, refusal: str, instrument: Path
) -> None:
    """R6.6: a report's inputs name the run that produced it -- never blank, never unattributed.

    The first row is ``uplift.harness.UNATTRIBUTED`` itself, which pins the module's local mirror
    of that sentinel by the refusal it drives.
    """
    payload = _build(instrument, _INSTRUMENT, _VALID, TUNED_STATIC_ARM).model_dump(mode="json")
    with pytest.raises(ValidationError, match=refusal):
        PowerReport.model_validate({**payload, name: value})


# ---------------------------------------------------------------------------
# Clause 4 -- revision-bound
# ---------------------------------------------------------------------------
@given(tree=_trees(), data=st.data())
def test_the_revision_moves_with_one_byte_or_one_name_and_with_nothing_else(
    tree: dict[str, bytes], data: st.DataObject, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """R6.7: the digest is the instrument's content, so only a change to it supersedes a report."""
    names = sorted(tree)
    assert names
    lf = _materialise(tmp_path_factory.mktemp("lf"), tree, names)
    digest = source_set_digest(lf, _GLOB)
    assert _CONTENT_DIGEST.fullmatch(digest)
    report = _build(lf, _GLOB, _VALID, TUNED_STATIC_ARM)
    assert report.harness_revision == digest

    # Line endings, creation order, location, pattern order, overlap, __pycache__: no move.
    crlf_tree = {path: content.replace(b"\n", b"\r\n") for path, content in tree.items()}
    assert all(crlf_tree[path] != tree[path] for path in names)
    crlf = _materialise(tmp_path_factory.mktemp("crlf"), crlf_tree, names[::-1])
    decoy = crlf / "pkg" / "__pycache__" / "decoy.py"
    decoy.parent.mkdir()
    decoy.write_bytes(b"NEVER_DIGESTED = True\n")
    literals = tuple(data.draw(st.permutations(names)))
    assert declared_source_files(crlf, _GLOB) == tuple(names)
    assert source_set_digest(crlf, _GLOB) == digest
    assert source_set_digest(crlf, literals) == digest
    assert source_set_digest(lf, (*literals, *_GLOB)) == digest
    assert describes_revision(report, crlf, _GLOB)

    # One changed byte moves it.
    target = data.draw(st.sampled_from(names))
    content = tree[target]
    index = data.draw(st.integers(min_value=0, max_value=len(content) - 1))
    offset = data.draw(st.integers(min_value=1, max_value=255))
    changed = bytes([(content[index] + offset) % 256])
    edited_tree = {**tree, target: content[:index] + changed + content[index + 1 :]}
    edited = _materialise(tmp_path_factory.mktemp("edited"), edited_tree, names)
    assert source_set_digest(edited, _GLOB) != digest
    assert not describes_revision(report, edited, _GLOB)

    # And so does one renamed file.
    renamed_path = target.removesuffix(".py") + "z.py"
    renamed_tree = {(renamed_path if path == target else path): body for path, body in tree.items()}
    renamed = _materialise(tmp_path_factory.mktemp("renamed"), renamed_tree, sorted(renamed_tree))
    assert source_set_digest(renamed, _GLOB) != digest


@given(tree=_trees(), missing=_NAMES)
def test_a_source_set_that_cannot_be_read_refuses_rather_than_digesting_less(
    tree: dict[str, bytes], missing: str, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A source set naming nothing readable names no revision, so nothing answers for it."""
    root = _materialise(tmp_path_factory.mktemp("unmatched"), tree, sorted(tree))
    skipped = root / "pkg" / "__pycache__" / "only.py"
    skipped.parent.mkdir()
    skipped.write_bytes(b"SKIPPED = True\n")
    report = _build(root, _GLOB, _VALID, TUNED_STATIC_ARM)
    absent = f"absent/{missing}.py"
    unmatched: tuple[tuple[str, ...], ...] = (
        (absent,),
        (*_GLOB, absent),
        (absent, *_GLOB),
        ("pkg",),
        ("pkg/__pycache__/*.py",),
    )
    for source_set in unmatched:
        with pytest.raises(PowerReportError, match="matches no file"):
            source_set_digest(root, source_set)
        with pytest.raises(PowerReportError, match="matches no file"):
            declared_source_files(root, source_set)
        with pytest.raises(PowerReportError, match="matches no file"):
            describes_revision(report, root, source_set)
        with pytest.raises(PowerReportError, match="matches no file"):
            _build(root, source_set, _VALID, TUNED_STATIC_ARM)

    malformed: tuple[tuple[Sequence[str], str], ...] = (
        ((), "empty source set"),
        ("pkg/**/*.py", "one string"),
        (("../outside.py",), "not repo-relative"),
        (("/absolute.py",), "not repo-relative"),
        (("pkg\\a.py",), "backslash"),
    )
    for declared, refusal in malformed:
        with pytest.raises(PowerReportError, match=refusal):
            source_set_digest(root, declared)


def test_every_declared_source_pattern_selects_a_file_in_this_tree() -> None:
    """The production source set is readable here, so a production revision can be named."""
    for pattern in POWER_SOURCE_SET:
        assert declared_source_files(_ROOT, (pattern,))
    selected = declared_source_files(_ROOT, POWER_SOURCE_SET)
    instrument_files = {
        "uplift/power.py",
        "uplift/uplift_floor.py",
        "digital_twin/simulation/monte_carlo.py",
    }
    assert instrument_files <= set(selected)
    assert not [path for path in selected if "__pycache__" in path]
    assert _CONTENT_DIGEST.fullmatch(source_set_digest(_ROOT, POWER_SOURCE_SET))


# ---------------------------------------------------------------------------
# Clause 5 -- floor-respecting
# ---------------------------------------------------------------------------
@given(
    inputs=_INPUTS,
    below=st.floats(min_value=1.5, max_value=MIN_SCENARIOS - 1.5),
    above=st.floats(min_value=MIN_SCENARIOS + 0.5, max_value=100.0 * MIN_SCENARIOS),
)
def test_inv_tw_002_is_binding_exactly_when_the_requirement_is_below_min_scenarios(
    inputs: _Inputs, below: float, above: float
) -> None:
    """R6.16: a requirement below the floor is recorded as binding, never as a lower constant."""
    assert INV_TW_002_FLOOR == MIN_SCENARIOS
    arbitrary = _quantities(inputs)
    under = _quantities(replace(inputs, materiality_margin=_margin_for(inputs, below)))
    over = _quantities(replace(inputs, materiality_margin=_margin_for(inputs, above)))

    assert under.derived_replicate_requirement < MIN_SCENARIOS < over.derived_replicate_requirement
    for quantities in (arbitrary, under, over):
        binding = quantities.derived_replicate_requirement < MIN_SCENARIOS
        assert quantities.inv_tw_002_binding is binding
    assert under.inv_tw_002_binding
    assert not over.inv_tw_002_binding


@given(
    inputs=_INPUTS,
    below=st.floats(min_value=1.5, max_value=MIN_POWERED_REPLICATES - 1.5),
    above=st.floats(
        min_value=MIN_POWERED_REPLICATES + 0.5, max_value=100.0 * MIN_POWERED_REPLICATES
    ),
)
def test_the_floor_is_never_below_min_scenarios_and_is_the_requirement_above_the_constant(
    inputs: _Inputs, below: float, above: float, instrument: Path
) -> None:
    """R6.9: a larger requirement replaces the constant; R6.16: a smaller one never lowers it."""
    assert MIN_POWERED_REPLICATES >= MIN_SCENARIOS
    assert powered_replicate_floor(None) == MIN_POWERED_REPLICATES
    arbitrary = _build(instrument, _INSTRUMENT, inputs, TUNED_STATIC_ARM)
    lower = replace(inputs, materiality_margin=_margin_for(inputs, below))
    higher = replace(inputs, materiality_margin=_margin_for(inputs, above))
    under = _build(instrument, _INSTRUMENT, lower, TUNED_STATIC_ARM)
    over = _build(instrument, _INSTRUMENT, higher, TUNED_STATIC_ARM)

    for report in (arbitrary, under, over):
        floor = powered_replicate_floor(report)
        assert floor >= MIN_SCENARIOS
        assert floor >= MIN_POWERED_REPLICATES
        assert floor >= report.derived_replicate_requirement
        assert floor in (MIN_POWERED_REPLICATES, report.derived_replicate_requirement)
    assert under.derived_replicate_requirement < MIN_POWERED_REPLICATES
    assert powered_replicate_floor(under) == MIN_POWERED_REPLICATES
    assert over.derived_replicate_requirement > MIN_POWERED_REPLICATES
    assert powered_replicate_floor(over) == over.derived_replicate_requirement


# ---------------------------------------------------------------------------
# Clause 6 -- against arm E only
# ---------------------------------------------------------------------------
#: Every other arm label, the incumbent, near-misses of the accepted name, and free text with no
#: digit -- so no generated name can contain the ADR citation the refusal is matched on.
_REFUSED_COMPARATORS = st.one_of(
    st.sampled_from(
        (
            *(label for label in ARM_LABELS if label != TUNED_STATIC_ARM),
            "Par_Level_Reorder",
            "consensus",
            "pooled:Par_Level_Reorder",
            "Tuned_Static",
            "tuned-static",
            " tuned_static",
            "tuned_static ",
            "",
        )
    ),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_ :", max_size=16).filter(
        lambda name: name != TUNED_STATIC_ARM
    ),
)


@given(inputs=_INPUTS, comparator=_REFUSED_COMPARATORS)
def test_a_comparator_other_than_the_tuned_control_is_refused(
    inputs: _Inputs, comparator: str, instrument: Path
) -> None:
    """ADR-055 D2.7: a power statement against any other arm describes the wrong contrast."""
    accepted = _build(instrument, _INSTRUMENT, inputs, TUNED_STATIC_ARM)
    assert accepted.comparator == TUNED_STATIC_ARM == "tuned_static"
    with pytest.raises(PowerReportError, match="ADR-055 D2.7"):
        _build(instrument, _INSTRUMENT, inputs, comparator)
    payload = accepted.model_dump(mode="json")
    with pytest.raises(ValidationError, match="ADR-055 D2.7"):
        PowerReport.model_validate({**payload, "comparator": comparator})


# ---------------------------------------------------------------------------
# Clause 7 -- refused, never repaired; persisted canonically
# ---------------------------------------------------------------------------
_OUTSIDE_THE_DOMAIN: Final[tuple[tuple[str, _Inputs], ...]] = (
    ("zero-variance", replace(_VALID, observed_variance=0.0)),
    ("negative-variance", replace(_VALID, observed_variance=-1.0)),
    ("infinite-variance", replace(_VALID, observed_variance=math.inf)),
    ("nan-variance", replace(_VALID, observed_variance=math.nan)),
    ("boolean-variance", replace(_VALID, observed_variance=True)),
    ("zero-margin", replace(_VALID, materiality_margin=0.0)),
    ("negative-margin", replace(_VALID, materiality_margin=-0.4)),
    ("infinite-margin", replace(_VALID, materiality_margin=math.inf)),
    ("nan-margin", replace(_VALID, materiality_margin=math.nan)),
    ("alpha-at-zero", replace(_VALID, alpha=0.0)),
    ("alpha-at-one", replace(_VALID, alpha=1.0)),
    ("nan-alpha", replace(_VALID, alpha=math.nan)),
    ("detection-at-zero", replace(_VALID, detection_probability=0.0)),
    ("detection-at-one", replace(_VALID, detection_probability=1.0)),
    ("detection-above-one", replace(_VALID, detection_probability=1.5)),
    ("detection-not-above-half-alpha", replace(_VALID, detection_probability=0.01)),
    ("one-replicate", replace(_VALID, replicates_per_arm=1)),
    ("boolean-replicates", replace(_VALID, replicates_per_arm=True)),
)


@pytest.mark.parametrize(
    "inputs",
    [inputs for _, inputs in _OUTSIDE_THE_DOMAIN],
    ids=[label for label, _ in _OUTSIDE_THE_DOMAIN],
)
def test_an_input_outside_the_formulas_domain_is_refused_and_never_repaired(
    inputs: _Inputs, instrument: Path
) -> None:
    """No input is clamped or defaulted: outside the domain there is no report at all (I-7)."""
    assert _quantities(_VALID).derived_replicate_requirement >= 1
    with pytest.raises(PowerReportError):
        _quantities(inputs)
    with pytest.raises(PowerReportError):
        _build(instrument, _INSTRUMENT, inputs, TUNED_STATIC_ARM)


@given(inputs=_INPUTS)
def test_the_committed_form_is_canonical_and_reads_back_as_the_same_report(
    inputs: _Inputs, instrument: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The write is the repo's canonical JSON, so regenerating an unchanged report is no diff."""
    report = _build(instrument, _INSTRUMENT, inputs, TUNED_STATIC_ARM)
    written = write_power_report(report, tmp_path_factory.mktemp("committed") / POWER_REPORT_PATH)
    raw = written.read_bytes()
    assert raw == report.to_canonical_json().encode("ascii")
    assert raw.decode("ascii") == _canonical(json.loads(raw))
    assert not raw.endswith(b"\n")
    reread = read_power_report(written)
    assert reread is not None
    assert reread == report
    write_power_report(reread, written)
    assert written.read_bytes() == raw


def test_an_absent_report_reads_as_none_and_a_present_malformed_one_raises(tmp_path: Path) -> None:
    """Absence is a state the caller reports (R6.7); a file claiming a report must be one."""
    assert read_power_report(tmp_path / "absent.json") is None
    bodies = (b"{not json", b"[]", b'{"kind":"power-report"}', b"\xff\xfe\xfd", b"")
    for index, body in enumerate(bodies):
        path = tmp_path / f"malformed-{index}.json"
        path.write_bytes(body)
        with pytest.raises(PowerReportError):
            read_power_report(path)
    directory = tmp_path / "a-directory.json"
    directory.mkdir()
    with pytest.raises(PowerReportError):
        read_power_report(directory)
