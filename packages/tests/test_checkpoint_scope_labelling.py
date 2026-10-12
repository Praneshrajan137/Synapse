"""R3.8 - the tmp-dir serving proofs are scoped, and no gate counts them as publication.

Feature: purpose-achievement-audit, task 10.10 (design E5.2; R3.8).

The audit's finding (Requirement 3): the serving-path proof "builds a checkpoint in
``tmp_path`` ... so it validates the *transport and adapter*, not a published model."
That is true and the proof is worth keeping - what was missing is a *mechanism*. The
proof's own docstring could be reworded, or a future reader could cite a green
tmp-dir proof as evidence that a checkpoint is published, and nothing in the
repository would object.

``ModelRegistry._resolve_checkpoint_path`` is why this matters concretely: it prefers
a local checkpoint over the remote. A locally built artifact therefore resolves
exactly like a published one, so "it resolved" can never be the evidence that
something was published.

This module makes the scope label fail-if-removed, in four independent ways:

1. **The label is declared, not inferred.** ``infrastructure/quality/checkpoint-scope.yaml``
   lists every proof that must carry a scope label, the scope vocabulary, and the
   exact tokens each scope's statement must contain (AD-13: declared in committed
   config, never a literal in the checker).
2. **Prose and constant must agree.** Each listed proof must contain every required
   token verbatim *and* expose ``SERVING_PROOF_SCOPE`` / ``PUBLICATION_EVIDENCE``.
   Deleting the sentence fails; deleting the constant fails; softening one without
   the other fails.
3. **The label must be accurate.** For a ``transport-and-adapter-only`` proof, every
   test that asserts a real / non-degraded resolution must take ``tmp_path`` and the
   module must configure no published source. A proof that quietly started reading
   the real serving directory could not keep the label.
4. **The registry cannot go vacuous.** A scan of the test trees finds any module that
   resolves a checkpoint from a directory and asserts a non-degraded resolution.
   Anything discovered that is neither listed nor carried in the dated allowlist is a
   failure naming the file, so a new tmp-dir serving proof cannot skip the label by
   simply not being listed.

Plus the second half of R3.8 - **no published-checkpoint gate counts it**: with a
perfect, production-looking checkpoint sitting in the gate's own
``local_candidate_dir``, ``published_checkpoint_truth.assess`` is still non-passing
(SKIP while nothing is recorded; UNAVAILABLE when a record cannot be fetched), its
classification stays ``absent``, and it names the local candidates it refused.

I-0: this module reads committed files and imports test modules. It trains nothing,
loads no weights, needs no torch, and touches no network.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from scripts.audit.published_checkpoint_truth import (
    ArtifactClass,
    Outcome,
    assess,
    evaluate,
    policy,
    refused_local_candidates,
    registry_status,
)

if TYPE_CHECKING:
    from types import ModuleType

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCOPE_POLICY_FILE: Final[Path] = ROOT / "infrastructure" / "quality" / "checkpoint-scope.yaml"

#: The shortest a required scope token may be. A one-word token could be satisfied by
#: an unrelated sentence, which would make the label decorative again.
_MIN_TOKEN_LEN: Final[int] = 12


# --------------------------------------------------------------------------- #
# The committed policy
# --------------------------------------------------------------------------- #
class ScopeVocabulary(BaseModel):
    """One declared scope: the constant's value plus the tokens its prose must carry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    required_tokens: tuple[str, ...]
    description: str


class LabelledProof(BaseModel):
    """A proof module that must carry a scope label."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    scope: str
    note: str | None = None


class Discovery(BaseModel):
    """How an unlabelled tmp-dir serving proof is found."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    roots: tuple[str, ...]
    filename_glob: str
    all_of: tuple[str, ...]
    any_of: tuple[str, ...]
    exclude_paths: tuple[str, ...] = ()


class UnlabelledEntry(BaseModel):
    """Disclosed, dated debt - the C61 ratchet shape, never a silent exemption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    rules: tuple[str, ...]
    rationale: str
    dated: str
    removal_condition: str


class ScopePolicy(BaseModel):
    """``infrastructure/quality/checkpoint-scope.yaml``, parsed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    requirement: str
    scope_constant: str
    evidence_constant: str
    scopes: tuple[ScopeVocabulary, ...]
    labelled_proofs: tuple[LabelledProof, ...]
    discovery: Discovery
    unlabelled_allowlist: tuple[UnlabelledEntry, ...]

    def scope_for(self, proof: LabelledProof) -> ScopeVocabulary:
        for scope in self.scopes:
            if scope.id == proof.scope:
                return scope
        raise AssertionError(
            f"{proof.path} declares scope {proof.scope!r}, which the policy's scope "
            f"vocabulary {[s.id for s in self.scopes]} does not define"
        )


def _load_scope_policy(path: Path = SCOPE_POLICY_FILE) -> ScopePolicy:
    """Read + parse the committed scope policy. An unreadable policy is never a pass."""
    if not path.is_file():
        raise AssertionError(
            f"the committed scope policy is missing: {path}. Without it there is nothing "
            "declared to hold the R3.8 label to, and an absent policy is not a pass (I-7)."
        )
    document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"{path} is not a YAML mapping")
    try:
        return ScopePolicy.model_validate(document)
    except ValidationError as error:  # pragma: no cover - a malformed policy fails loudly
        raise AssertionError(f"{path} does not parse into a scope policy: {error}") from error


POLICY: Final[ScopePolicy] = _load_scope_policy()


def _load_module(rel_path: str) -> ModuleType:
    """Import a proof module by path, under a synthetic name (no collection clash)."""
    target = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(f"_scope_probe_{Path(rel_path).stem}", target)
    if spec is None or spec.loader is None:  # pragma: no cover - unimportable path
        raise AssertionError(f"cannot import the declared proof module {rel_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# 1. The declared label registry is well-formed and non-vacuous
# --------------------------------------------------------------------------- #
def test_scope_policy_declares_a_non_vacuous_label_registry() -> None:
    """A registry with no proofs, no tokens, or a trivial token could not hold a label."""
    assert POLICY.version == 1
    assert POLICY.requirement == "3.8"
    assert POLICY.labelled_proofs, "no proof is required to carry a scope label (vacuous)"
    assert POLICY.scopes, "the scope vocabulary is empty"

    for scope in POLICY.scopes:
        assert scope.required_tokens, f"scope {scope.id!r} requires no token (vacuous)"
        for token in scope.required_tokens:
            assert len(token) >= _MIN_TOKEN_LEN, (
                f"scope {scope.id!r} token {token!r} is shorter than {_MIN_TOKEN_LEN} chars; "
                "a token that short can be satisfied by an unrelated sentence"
            )
        # Every scope must deny publication evidence - that denial is the requirement.
        assert any("published" in token for token in scope.required_tokens), (
            f"scope {scope.id!r} states no non-publication claim, so satisfying it would "
            "not satisfy R3.8"
        )

    for proof in POLICY.labelled_proofs:
        POLICY.scope_for(proof)  # raises naming the proof if the scope is undeclared


def test_every_allowlist_entry_is_dated_reasoned_and_removable() -> None:
    """Disclosed debt carries rules, a dated rationale, and a removal condition."""
    for entry in POLICY.unlabelled_allowlist:
        assert entry.rules, f"{entry.path} excuses nothing named"
        assert entry.rationale.strip(), f"{entry.path} carries no rationale"
        assert entry.removal_condition.strip(), f"{entry.path} states no removal condition"
        # An unparseable date is not a date; the entry must be auditable by age.
        date.fromisoformat(entry.dated)
        assert (ROOT / entry.path).is_file(), (
            f"allowlist entry {entry.path} names a file that no longer exists; a stale "
            "excuse is not an excuse"
        )


# --------------------------------------------------------------------------- #
# 2. Prose and constant must both be present, and must agree
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("proof", POLICY.labelled_proofs, ids=lambda p: p.path)
def test_labelled_proof_carries_its_scope_statement(proof: LabelledProof) -> None:
    """Remove the statement or either constant and this fails naming the proof."""
    target = ROOT / proof.path
    assert target.is_file(), f"declared proof {proof.path} does not exist"
    source = target.read_text(encoding="utf-8")

    scope = POLICY.scope_for(proof)
    missing = [token for token in scope.required_tokens if token not in source]
    assert not missing, (
        f"{proof.path} no longer carries its R3.8 scope statement: missing {missing}. "
        f"The proof is scoped {scope.id!r} and must say so in its own text."
    )

    module = _load_module(proof.path)
    declared = getattr(module, POLICY.scope_constant, None)
    assert declared == scope.id, (
        f"{proof.path}::{POLICY.scope_constant} is {declared!r}, expected {scope.id!r} - the "
        "machine-readable scope must match the declared one"
    )
    evidence = getattr(module, POLICY.evidence_constant, "<absent>")
    assert evidence is False, (
        f"{proof.path}::{POLICY.evidence_constant} is {evidence!r}; R3.8 requires this proof "
        "to declare that it is NOT evidence that a checkpoint is published"
    )


# --------------------------------------------------------------------------- #
# 3. The label must be accurate, not merely asserted
# --------------------------------------------------------------------------- #
_TRANSPORT_SCOPE: Final[str] = "transport-and-adapter-only"


@pytest.mark.parametrize(
    "proof",
    [p for p in POLICY.labelled_proofs if p.scope == _TRANSPORT_SCOPE],
    ids=lambda p: p.path,
)
def test_transport_scoped_proof_really_only_resolves_from_a_temporary_directory(
    proof: LabelledProof,
) -> None:
    """A transport-scoped proof that started reading the real serving source would lie.

    So the label is checked against behaviour: every test asserting a real /
    non-degraded resolution takes the ``tmp_path`` fixture, and the module configures
    no published source (no ``hf_repo``) and reads no committed registry record.
    """
    module = _load_module(proof.path)
    markers = POLICY.discovery.any_of

    checked = 0
    for name, obj in vars(module).items():
        if not name.startswith("test_") or not callable(obj):
            continue
        body = inspect.getsource(obj)
        if not any(marker in body for marker in markers):
            continue
        checked += 1
        params = inspect.signature(obj).parameters
        assert "tmp_path" in params, (
            f"{proof.path}::{name} asserts a real resolution without the tmp_path fixture, "
            f"so the {_TRANSPORT_SCOPE!r} label no longer describes it"
        )
    assert checked > 0, (
        f"{proof.path} asserts no real resolution any more ({markers}); a transport proof "
        "that proves no resolution is not the proof this label was written for"
    )

    source = (ROOT / proof.path).read_text(encoding="utf-8")
    assert "hf_repo" not in source, (
        f"{proof.path} configures a published source; a proof that reaches the declared "
        f"zero-cost source is not {_TRANSPORT_SCOPE!r}"
    )
    assert policy().registry_file not in source, (
        f"{proof.path} reads {policy().registry_file}; a transport proof must not consult "
        "the published-checkpoint record"
    )


# --------------------------------------------------------------------------- #
# 4. The registry cannot go vacuous by omission
# --------------------------------------------------------------------------- #
def _discover_tmp_dir_serving_proofs() -> set[str]:
    """Every test module that resolves a checkpoint from a dir AND asserts it is real."""
    discovery = POLICY.discovery
    excluded = set(discovery.exclude_paths)
    found: set[str] = set()
    for root_name in discovery.roots:
        root = ROOT / root_name
        if not root.is_dir():
            continue
        for candidate in sorted(root.rglob(discovery.filename_glob)):
            rel = candidate.relative_to(ROOT).as_posix()
            if rel in excluded:
                continue
            text = candidate.read_text(encoding="utf-8")
            if all(token in text for token in discovery.all_of) and any(
                token in text for token in discovery.any_of
            ):
                found.add(rel)
    return found


def test_no_tmp_dir_serving_proof_escapes_the_scope_label() -> None:
    """A new tmp-dir serving proof cannot avoid the label by not being listed."""
    discovered = _discover_tmp_dir_serving_proofs()
    labelled = {proof.path for proof in POLICY.labelled_proofs}
    allowlisted = {entry.path for entry in POLICY.unlabelled_allowlist}

    unlabelled = sorted(discovered - labelled - allowlisted)
    assert not unlabelled, (
        "these modules resolve a checkpoint from a directory and assert it is real, but "
        f"carry no R3.8 scope label: {unlabelled}. Add each to `labelled_proofs` in "
        f"{SCOPE_POLICY_FILE.name} with its scope statement, or disclose it in "
        "`unlabelled_allowlist` with a dated rationale and a removal condition."
    )

    # Anti-vacuity in the other direction: the scan must still see what it excuses.
    stale = sorted(allowlisted - discovered)
    assert not stale, (
        f"allowlist entries no longer matched by the scan: {stale}. Either the proof was "
        "repaired (move it to `labelled_proofs`) or the scan stopped seeing it (a scanner "
        "that has stopped looking is not a passing scanner)."
    )

    # The proof R3.8 was written about must still be one of the discovered modules.
    assert "packages/tests/test_model_registry_checkpoint.py" in discovered, (
        "the tmp-dir serving proof named by audit Requirement 3 is no longer discovered by "
        "the scan; the label mechanism would then be guarding nothing"
    )


# --------------------------------------------------------------------------- #
# 5. No published-checkpoint gate counts a locally built checkpoint (R3.8, R3.7)
# --------------------------------------------------------------------------- #
def _nothing_published(_repo_id: str, _filename: str) -> str:
    """A fetcher that resolves to a path holding nothing, so no test here uses a socket."""
    return str(ROOT / "build" / "audit" / "no-such-published-sidecar.json")


def _plant_local_candidate(root: Path) -> None:
    """Write a production-LOOKING checkpoint pair into the gate's local candidate dir.

    Deliberately as favourable as a local artifact can be: a ``full_`` version, the
    smoke flag false, coverage above the committed floor. If the gate could be moved
    by a local file at all, this is the file that would move it.
    """
    source = policy().source
    name = policy().serving_name
    directory = root / source.local_candidate_dir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / source.checkpoint_filename.format(name=name)).write_bytes(b"not-weights")
    sidecar = (
        '{"calibrator":{"last_coverage_p90":0.93},"smoke":false,"version":"full_deadbeefdeadbeef"}'
    )
    (directory / source.sidecar_filename.format(name=name)).write_text(
        sidecar, encoding="utf-8"
    )


def test_gate_never_counts_a_locally_built_checkpoint_as_publication(tmp_path: Path) -> None:
    """The tmp-dir artifact is never the evidence, however perfect it looks.

    Two states, one conclusion. With nothing recorded the gate SKIPs; with a record it
    cannot fetch it reports UNAVAILABLE while naming the local candidate it refused.
    Neither is a PASS, and in both the classification stays ``absent`` - a local file
    is never promoted to a published artifact.
    """
    _plant_local_candidate(tmp_path)
    calls: list[tuple[str, str]] = []

    def _unfetchable(repo_id: str, filename: str) -> str:
        calls.append((repo_id, filename))
        return str(tmp_path / "nothing-was-published.json")

    name = policy().serving_name
    placeholder = assess(
        registry={"__placeholder__": {"status": "unpublished"}},
        fetch_sidecar=_unfetchable,
        root=tmp_path,
        env={},
    )
    assert placeholder.outcome is Outcome.SKIP
    assert placeholder.classification is ArtifactClass.ABSENT, placeholder.classification_detail
    assert not calls, "nothing is recorded, so the gate had no artifact to fetch"

    landed = assess(
        registry={
            name: {
                "repo": "example-owner/synapse-demand-prophet",
                "sha": "deadbeefdeadbeef",
                "coverage_p90": 0.93,
                "final_crps": 0.42,
                "trained_at": "2026-06-01T12:00:00Z",
                "rows": 1_125_000,
            }
        },
        fetch_sidecar=_unfetchable,
        root=tmp_path,
        env={},
    )
    assert landed.outcome is Outcome.UNAVAILABLE
    assert landed.classification is ArtifactClass.ABSENT, landed.classification_detail
    assert landed.version is None, "no version was published, so none may be reported"
    assert "REFUSED" in landed.detail

    expected_refusal = refused_local_candidates(policy().source, name, root=tmp_path)
    for report in (placeholder, landed):
        assert report.refused_local_candidates == expected_refusal
        assert report.outcome is not Outcome.PASS
    # The refusal is auditable: it names the files, and says they were there.
    assert all("(present)" in item for item in expected_refusal), expected_refusal


def test_c46s_probe_stays_non_passing_while_nothing_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check the Check_Registry actually calls cannot pass off a local artifact.

    ``verify_claims.py::check_published_checkpoint`` (C46) calls
    ``published_checkpoint_truth.evaluate``. While the committed registry holds no
    validated non-placeholder entry it reports ``skip`` - even with the source
    configured and a checkpoint sitting in ``artifacts/checkpoints`` - and a SKIP is
    not a PASS (I-7). No network is reached on this path: the placeholder is detected
    before any fetch.
    """
    committed = registry_status()
    assert committed.status in {"placeholder", "populated"}, committed.problems
    if committed.status == "populated":
        # An operator has landed a record. Confirming that record against the remote is a
        # fetching gate's job (C46, in CI). The strongest network-free statement is that
        # the gate still refuses to resolve a local candidate in the remote's place - so
        # this branch asserts that rather than skipping, because a skip reads as a pass.
        report = assess(fetch_sidecar=_nothing_published, env={})
        assert report.outcome is not Outcome.PASS
        assert "REFUSED" in report.detail
        return

    monkeypatch.setenv(policy().source.env_var, "example-owner/synapse-demand-prophet")
    probe = evaluate()
    assert probe.status == "skip", probe.detail
    assert "placeholder" in probe.detail


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
