"""Property-based test that a smoke artifact is told apart from an absent one.

Feature: decision-quality-proof, Property 72: A smoke artifact is distinguished from an
absent one and never substituted locally

    *For any* published sidecar and *any* registry entry, an artifact produced by a smoke
    run yields a non-passing result whose detail distinguishes a smoke artifact from an
    absent one; a recorded sha that does not appear in the published version yields a
    non-passing result naming both; an unfetchable recorded sha yields a non-passing
    result and no locally built candidate is resolved in its place, with every refused
    local candidate reported; and the mapping from the check's four-valued outcome to a
    published gate status is total, mapping unavailable to a non-passing status and never
    to a pass.

Why "distinguished" is the obligation, not "rejected"
-----------------------------------------------------

Rejecting both a smoke artifact and an absent one is easy and useless: the operator's next
action differs completely. An absent artifact means *publish one* (the runbook). A smoke
artifact means *something published the CI build over the production one*, which is a
different and more alarming problem. A gate that reported "not a production checkpoint" for
both would be honest and unactionable. So the assertions below are about the two details
being **textually distinguishable and self-labelling**, not only about the two verdicts
being non-passing.

The refusal is the other half. ``ModelRegistry._resolve_checkpoint_path`` prefers a local
checkpoint over the remote, and the CI training-smoke job writes exactly such a file into
``checkpoint-truth.yaml::source.local_candidate_dir``. A gate that resolved through it
would certify the smoke build as the published model -- the precise evidence swap R9.7
forbids. So the refusal is proven **by construction**, against a tree where the local
candidate really exists: a refusal asserted over a tree with nothing to refuse is not a
refusal, and the report must name what it declined and say it was present.

I-0 and $0: nothing is trained, fetched or built. The policy, registry, fetcher and tree
root are injected; the committed ``published_checkpoints.json`` is never read and no socket
is opened. Every marker, filename template and floor is read from the committed policy
(AD-13). Budget inherited from the root ``conftest.py`` profile.

**Validates: Requirements 9.2, 9.5, 9.7, 9.11**
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.audit import verify_claims
from scripts.audit.published_checkpoint_truth import (
    SERVING_NAME,
    ArtifactClass,
    CheckpointTruthReport,  # noqa: TC002 - runtime import: typeguard may resolve
    Clause,
    Outcome,
    assess,
    classify,
    policy,
    refused_local_candidates,
)

if TYPE_CHECKING:
    from pathlib import Path

POLICY: Final = policy()
MARKERS: Final = POLICY.classification
FLAG: Final[str] = MARKERS.smoke.sidecar_flag
SMOKE_PREFIX: Final[str] = MARKERS.smoke.version_prefixes[0]
REAL_PREFIX: Final[str] = MARKERS.real.version_prefixes[0]
TOLERANCE: Final = POLICY.tolerances.final_crps
SIDECAR_NAME: Final[str] = POLICY.source.sidecar_filename.format(name=SERVING_NAME)

_REPO: Final[str] = "example-owner/synapse-demand-prophet"
_PLACEHOLDER: Final[str] = "__placeholder__"

#: Only PASS is a pass (I-7).
NON_PASSING: Final[frozenset[Outcome]] = frozenset(Outcome) - {Outcome.PASS}
#: Whatever PASS is spelled as in the published registry -- derived, never restated.
PASSING_STATUS: Final[str] = verify_claims.GATE_STATUS["ok"]

#: The bias on the raw quantile columns and the conformal radius that widens them.
#: Chosen so the RAW band excludes every actual while the ADJUSTED band includes it.
_BIAS: Final[float] = 2.0
_RADIUS: Final[float] = 2.0


# ---------------------------------------------------------------------------
# Fixtures: a published artifact, and a tree that really holds a local candidate
# ---------------------------------------------------------------------------


def heldout_block() -> dict[str, Any]:
    """A fully recomputable held-out block, so no other clause decides the verdict.

    The key names are written as literals rather than imported from the gate: this file
    states what a *published artifact* carries, and a fixture that read its keys from the
    reader could not detect the two drifting apart.

    The raw quantile columns are biased high by :data:`_BIAS` so they exclude every
    actual, while the conformal-adjusted bounds widen them by :data:`_RADIUS` and include
    it. A gate that scored the quantile columns would therefore recompute zero coverage
    and fail this fixture, which is what keeps the 80%/90% distinction observable.
    """
    levels = TOLERANCE.quantile_levels
    centre = (len(levels) - 1) / 2.0
    actuals = [float(index) for index in range(TOLERANCE.min_samples)]
    predictions = [
        [actual + _BIAS + (index - centre) for index in range(len(levels))]
        for actual in actuals
    ]
    return {
        "quantile_levels": list(levels),
        "predictions": predictions,
        "actuals": actuals,
        "lower_90": [max(row[0] - _RADIUS, 0.0) for row in predictions],
        "upper_90": [row[-1] + _RADIUS for row in predictions],
    }


def recorded_crps() -> float:
    """The value :func:`heldout_block`'s quantile columns recompute to.

    Mean pinball loss over the levels, computed here from the block's own construction:
    every row's error at level index ``j`` is ``centre - j - _BIAS``, identically, so the
    loss is ``q * e`` for a non-negative error and ``(q - 1) * e`` otherwise. Restated
    rather than imported, so the record is not the subject's own word.
    """
    levels = TOLERANCE.quantile_levels
    centre = (len(levels) - 1) / 2.0
    per_level: list[float] = []
    for index, level in enumerate(levels):
        error = centre - index - _BIAS
        per_level.append(level * error if error >= 0.0 else (level - 1.0) * error)
    return sum(per_level) / len(per_level)


def build_sidecar(*, flag: Any, version: str) -> dict[str, Any]:
    """A sidecar clean on every clause except the ones under test."""
    sidecar: dict[str, Any] = {
        "version": version,
        "arch": {},
        "calibrator": {"last_coverage_p90": 1.0},
        TOLERANCE.sidecar_block: heldout_block(),
    }
    if flag is not None:
        sidecar[FLAG] = flag
    return sidecar


def landed_entry(sha: str) -> dict[str, Any]:
    """A validated record of the shape the runbook's step-5 output produces."""
    return {
        "repo": _REPO,
        "sha": sha,
        "coverage_p90": 1.0,
        "final_crps": recorded_crps(),
        "trained_at": "2026-06-01T12:00:00Z",
        "rows": 1_125_000,
    }


def local_candidate_tree(root: Path) -> tuple[str, ...]:
    """Write the locally built pair the gate must REFUSE, and return their names.

    Without this the "refusal" below would be a report that nothing was there, which
    proves nothing about R9.7.
    """
    directory = root / POLICY.source.local_candidate_dir
    directory.mkdir(parents=True, exist_ok=True)
    names = (
        POLICY.source.checkpoint_filename.format(name=SERVING_NAME),
        POLICY.source.sidecar_filename.format(name=SERVING_NAME),
    )
    for name in names:
        (directory / name).write_text("locally built smoke artifact", encoding="utf-8")
    return names


def report_for(
    sidecar: dict[str, Any] | None,
    registry: dict[str, Any],
    root: Path,
) -> CheckpointTruthReport:
    """Drive the registered surface. ``sidecar=None`` makes every fetch fail."""
    path = root / SIDECAR_NAME
    if sidecar is not None:
        path.write_text(json.dumps(sidecar, sort_keys=True), encoding="utf-8")

    def _fetch(repo_id: str, filename: str) -> str:
        assert repo_id == _REPO
        assert filename == SIDECAR_NAME
        if sidecar is None:
            raise RuntimeError("remote unreachable: the recorded sha cannot be fetched")
        return str(path)

    # `env={}` deliberately: with no DP_HF_REPO set, a landed record must still be
    # verified from the repo it records (R9.11). The env var is an override, not a
    # precondition, and the SKIP it used to produce was the row R9.11 replaces.
    return assess(
        checkpoint_policy=POLICY,
        registry=registry,
        fetch_sidecar=_fetch,
        root=root,
        env={},
    )


def never_fetched(repo_id: str, filename: str) -> str:
    """A fetcher that fails the test if the gate reaches for the remote at all."""
    raise AssertionError(f"the gate must not fetch {repo_id}/{filename} for an unlanded record")


@pytest.fixture(scope="module")
def hub(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A module-scoped scratch dir standing in for the HF Hub cache (no network).

    Module-scoped rather than per-example: a session-scoped factory called inside a
    property would leave one directory per example behind for no gain.
    """
    return tmp_path_factory.mktemp("smoke_artifact_distinction")


# ---------------------------------------------------------------------------
# Property 72 -- smoke versus absent, told apart
# ---------------------------------------------------------------------------
# Feature: decision-quality-proof, Property 72: A smoke artifact is distinguished from an absent one
# and never substituted locally # noqa: E501
@settings(deadline=None)
@given(
    flag=st.sampled_from([True, False, None]),
    prefix=st.sampled_from(["smoke", "real", "unmarked"]),
    sha=st.text(alphabet="0123456789abcdef", min_size=7, max_size=7),
)
def test_a_smoke_artifact_is_non_passing_and_its_detail_is_not_an_absent_one(
    flag: Any, prefix: str, sha: str, hub: Path
) -> None:
    """R9.5: a smoke artifact fails, and a reader can tell which of the three it was.

    The distinguishing assertion is the load-bearing one: both details are non-passing,
    so verdict equality would be satisfied by a gate that said "not production" twice.
    Here each detail must lead with its own class and the two must not be the same
    string.

    **Validates: Requirements 9.5**
    """
    root = hub
    version = {
        "smoke": f"{SMOKE_PREFIX}{sha}",
        "real": f"{REAL_PREFIX}{sha}",
        "unmarked": f"build-{sha}",
    }[prefix]
    sidecar = build_sidecar(flag=flag, version=version)

    expected = (
        ArtifactClass.SMOKE
        if flag is True or prefix == "smoke"
        else ArtifactClass.REAL
        if prefix == "real"
        else ArtifactClass.INDETERMINATE
    )
    report = report_for(sidecar, {SERVING_NAME: landed_entry(sha)}, root)

    # Total, and agreeing with the helper a caller would reach for.
    assert report.classification is expected
    assert classify(sidecar, MARKERS)[0] is expected
    # Self-labelling: the detail leads with the class it decided, and names the marker.
    assert report.classification_detail.startswith(f"{expected.value.upper()}:")
    assert FLAG in report.classification_detail

    # The absent detail, from the same gate, for the same serving name.
    absent = report_for(None, {_PLACEHOLDER: {}}, root)
    assert absent.classification is ArtifactClass.ABSENT
    assert absent.classification_detail.startswith(f"{ArtifactClass.ABSENT.value.upper()}:")

    # Distinguished: not the same sentence, and neither claims the other's class.
    assert report.classification_detail != absent.classification_detail
    assert ArtifactClass.ABSENT.value.upper() not in report.classification_detail
    assert expected.value.upper() not in absent.classification_detail

    if expected is ArtifactClass.SMOKE:
        # A smoke artifact is never reported as a real one, and never as a pass.
        assert report.classification is not ArtifactClass.REAL
        assert report.outcome is Outcome.FAIL
        assert report.outcome in NON_PASSING
        assert report.exit_code != 0
        findings = [f for f in report.findings if f.clause is Clause.CLASSIFICATION]
        assert [f.outcome for f in findings] == [Outcome.FAIL]
        assert repr(version) in findings[0].detail
    else:
        # And the positive control: a real, fully published artifact does pass, so the
        # clauses above are not satisfied by a gate that refuses everything.
        assert (report.outcome is Outcome.PASS) is (expected is ArtifactClass.REAL), (
            report.detail
        )


@settings(deadline=None)
@given(
    recorded=st.text(alphabet="0123456789abcdef", min_size=7, max_size=7),
    other=st.text(alphabet="0123456789abcdef", min_size=7, max_size=7),
    same=st.booleans(),
)
def test_a_recorded_sha_absent_from_the_published_version_names_both(
    recorded: str, other: str, same: bool, hub: Path
) -> None:
    """R9.2: the record and the remote must name the same artifact, and drift names both.

    Naming both is the actionable half. "Drift" alone leaves the operator comparing two
    values the report declined to state. ``same`` is drawn rather than left to collision:
    two independent seven-hex strings agree about once in 2**28 examples, so without it
    the pinned branch would be asserted by nothing.

    **Validates: Requirements 9.2**
    """
    root = hub
    published = recorded if same else other
    version = f"{REAL_PREFIX}{published}"
    report = report_for(
        build_sidecar(flag=False, version=version), {SERVING_NAME: landed_entry(recorded)}, root
    )

    drift = [f for f in report.findings if f.clause is Clause.SHA_PIN]
    pinned = recorded in version
    assert bool(drift) == (not pinned)
    assert (report.outcome is Outcome.PASS) is pinned, report.detail
    if drift:
        assert drift[0].outcome is Outcome.FAIL
        assert recorded in drift[0].detail
        assert version in drift[0].detail
        assert report.exit_code != 0


# ---------------------------------------------------------------------------
# Property 72 -- the refusal, proven against a tree that holds the candidate
# ---------------------------------------------------------------------------
def test_an_unfetchable_recorded_sha_refuses_a_present_local_candidate_and_names_it(
    tmp_path: Path,
) -> None:
    """R9.7: unavailable, never a locally built stand-in -- and the refusal is auditable.

    The local pair exists on disk here, so this is a refusal rather than a report of
    absence, and the report must say ``present`` for what it declined. Resolving it would
    certify the CI smoke build as the published model.

    **Validates: Requirements 9.7**
    """
    names = local_candidate_tree(tmp_path)
    report = report_for(None, {SERVING_NAME: landed_entry("a1b2c3d")}, tmp_path)

    assert report.outcome is Outcome.UNAVAILABLE
    assert report.outcome in NON_PASSING
    assert report.exit_code != 0
    # Nothing was fetched, so nothing was classified as production.
    assert report.classification is ArtifactClass.ABSENT
    assert report.version is None

    # Non-empty, and every candidate reported -- a "nothing was substituted" clause that
    # an empty list could satisfy would assert nothing at all.
    assert report.refused_local_candidates != ()
    assert len(report.refused_local_candidates) == len(names)
    for name in names:
        assert any(name in candidate for candidate in report.refused_local_candidates)
    assert all("(present)" in candidate for candidate in report.refused_local_candidates)
    assert refused_local_candidates(POLICY.source, SERVING_NAME, root=tmp_path) == (
        report.refused_local_candidates
    )

    fetch = [f for f in report.findings if f.clause is Clause.FETCH]
    assert [f.outcome for f in fetch] == [Outcome.UNAVAILABLE]
    assert "REFUSED" in fetch[0].detail
    for candidate in report.refused_local_candidates:
        assert candidate in fetch[0].detail


@pytest.mark.parametrize(
    ("field", "value"),
    [("allow_local_substitution", True), ("zero_cost", False)],
)
def test_a_flipped_policy_pin_is_a_failure_so_the_refusal_cannot_be_configured_away(
    field: str, value: bool, tmp_path: Path
) -> None:
    """R9.7, I-1: the two pins exist to be pinned, not to be flipped.

    A refusal that a configuration change can switch off is a preference. Both pins are
    therefore clauses of the gate itself, and either flipped is a FAIL naming the file and
    the field -- which is why the committed schema can also pin them ``const``.

    **Validates: Requirements 9.7**
    """
    flipped = POLICY.model_copy(
        update={"source": POLICY.source.model_copy(update={field: value})}
    )
    # An unlanded registry deliberately: no fetch can happen, so the FAIL below is the
    # pin's alone, and it demonstrates the ordering `assess` claims -- a flipped pin
    # outranks an unlanded record rather than being masked by it.
    report = assess(
        checkpoint_policy=flipped,
        registry={_PLACEHOLDER: {}},
        fetch_sidecar=never_fetched,
        root=tmp_path,
        env={},
    )

    policy_findings = [f for f in report.findings if f.clause is Clause.POLICY]
    assert [f.outcome for f in policy_findings] == [Outcome.FAIL]
    assert field in policy_findings[0].detail
    assert report.outcome is Outcome.FAIL
    assert report.outcome in NON_PASSING
    assert report.exit_code == 1
    # A flipped pin outranks an unlanded record, so the headline states the pin.
    assert field in report.detail


# ---------------------------------------------------------------------------
# Property 72 -- the projection into the published gate status is total
# ---------------------------------------------------------------------------
def test_the_outcome_to_gate_status_projection_is_total_and_never_launders_a_gap() -> None:
    """R9.11: C46's row is derived from this map, so the map must cover what it can emit.

    Totality first. An outcome ``GATE_STATUS`` cannot translate raises ``KeyError``, which
    ``_run_check`` coerces to FAIL under the check's own identifier -- moving the published
    counts for a reason that has nothing to do with the checkpoint. Then the direction: the
    two states that established nothing must not share a spelling with the one that
    established something (I-7, R2.9).

    **Validates: Requirements 9.11**
    """
    emitted = {outcome.value for outcome in Outcome}

    assert emitted, "the outcome vocabulary is empty; nothing is being projected"
    untranslatable = emitted - set(verify_claims.GATE_STATUS)
    assert not untranslatable, (
        f"published_checkpoint_truth can report {sorted(untranslatable)}, which "
        "verify_claims.GATE_STATUS cannot translate"
    )
    assert verify_claims.GATE_STATUS[Outcome.UNAVAILABLE.value] != PASSING_STATUS
    assert verify_claims.GATE_STATUS[Outcome.SKIP.value] != PASSING_STATUS
    assert verify_claims.GATE_STATUS[Outcome.FAIL.value] != PASSING_STATUS
    # Exactly one member maps onto the passing spelling, so no gap can share it.
    passing = {value for value in emitted if verify_claims.GATE_STATUS[value] == PASSING_STATUS}
    assert passing == {Outcome.PASS.value}


def test_a_landed_record_is_judged_from_the_artifact_rather_than_from_an_env_var(
    tmp_path: Path,
) -> None:
    """R9.11: the row C46 publishes is derived from the fetched artifact and the record.

    The row this replaces read ``DP_HF_REPO unset - no published model claimed (operator
    step)``. With the environment empty, a landed record must still be verified from the
    repo it records: an unset override is not a reason to leave a claim unchecked.

    **Validates: Requirements 9.11**
    """
    sha = "a1b2c3d"
    report = report_for(
        build_sidecar(flag=False, version=f"{REAL_PREFIX}{sha}"),
        {SERVING_NAME: landed_entry(sha)},
        tmp_path,
    )

    assert report.repo == _REPO
    assert report.outcome is not Outcome.SKIP
    assert POLICY.source.env_var not in report.detail
    assert "unset" not in report.detail
    assert report.registry_state == "populated"
    # Derived from the artifact: the fetched version and the recompute both appear.
    assert report.version == f"{REAL_PREFIX}{sha}"
    assert report.coverage_recompute is not None
    assert report.coverage_recompute.basis == "recompute"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
