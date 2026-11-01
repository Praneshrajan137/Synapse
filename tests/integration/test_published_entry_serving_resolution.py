"""R3.2 - one recorded entry resolves through the production serving path.

Feature: purpose-achievement-audit, task 10.10 (design E5.2; R3.2).

R3.2: "WHEN an operator publishes a checkpoint and records it in the
Published_Checkpoint_Registry, THE Model_Registry SHALL resolve that checkpoint
through the production serving path and return an object whose ``degraded`` attribute
is ``false`` and whose version string contains the recorded sha."

This is the *resolution contract*. It needs a checkpoint on disk, torch, and the ML
dep stack, so it runs in exactly one place: the ``ci.yml`` ``training-smoke`` job,
which produces ``artifacts/checkpoints/demand_prophet_hgt_tft.pt`` plus its serving
sidecar before any gate reads them. Elsewhere - on a pull request, in
``quality-gates``, and on the development laptop under I-0 - it SKIPs, and a SKIP is
not a PASS (I-7). Until a workflow step runs this file inside that job, R3.2 has no
executed proof at all; the skip is the honest report of that, not a substitute for it.

Scope (R3.8) - SMOKE-ARTIFACT RESOLUTION ONLY. While the committed registry holds
only ``__placeholder__``, the artifact this test resolves is the CI *smoke* artifact,
and the test asserts that the published-checkpoint classifier still calls it ``smoke``.
So a green run here is **not evidence that a checkpoint is published**: it is evidence
that a recorded entry resolves to a real, non-degraded model whose version string
carries its sha. Publication is judged by
``scripts/audit/published_checkpoint_truth.py``, which fetches the declared zero-cost
remote and refuses to substitute any locally built checkpoint (R3.7). The label is
enforced by ``packages/tests/test_checkpoint_scope_labelling.py`` against
``infrastructure/quality/checkpoint-scope.yaml``.

Why the production wiring and not a hand-rolled registry: an independently assembled
``ModelRegistry`` would be a parallel model of serving rather than serving itself -
the self-referential-oracle anti-pattern the audit reports in Requirement 12. This
test calls ``agents.demand_prophet.inference.serve._build_model_registry``, the same
constructor the FastAPI lifespan calls, and resolves exactly once.

Prerequisites inside the proving job are asserted, never skipped: with
``SYNAPSE_SMOKE_RUN`` set, an absent checkpoint or an absent torch is a failure,
because in that job both must be present. Absence of proof is never a pass.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Final

import pytest

from scripts.audit.published_checkpoint_truth import (
    ArtifactClass,
    classify,
    policy,
    registry_status,
    validate_entry,
)

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: R3.8 scope label. Read by packages/tests/test_checkpoint_scope_labelling.py.
SERVING_PROOF_SCOPE: Final[str] = "smoke-artifact-resolution-only"
#: This module is never counted as evidence that a checkpoint is published (I-7).
PUBLICATION_EVIDENCE: Final[bool] = False

#: The ci.yml training-smoke job sets this after running scripts/smoke_train.py. Same
#: convention as scripts/audit/checkpoint_truth.py and calibration_truth.py: outside
#: that job there is no artifact to resolve, so the proof is unavailable rather than
#: failing, and it says which job owns it.
_SMOKE_EXPECTED: Final[bool] = bool(os.environ.get("SYNAPSE_SMOKE_RUN"))

#: A registry-record shape to hang the resolved sha on. The non-sha fields are
#: stand-ins; only the sha clause of R3.2 is asserted from them.
_RECORD_SHAPE: Final[dict[str, Any]] = {
    "repo": "example-owner/synapse-demand-prophet",
    "sha": "",
    "coverage_p90": 0.91,
    "final_crps": 0.42,
    "trained_at": "2026-06-01T12:00:00Z",
    "rows": 1_125_000,
}

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _SMOKE_EXPECTED,
        reason=(
            "R3.2 needs the serving checkpoint that only the ci.yml training-smoke job "
            "produces (SYNAPSE_SMOKE_RUN=1 after scripts/smoke_train.py). SKIPPED here: "
            "this is an unproven claim, not a passing one (I-7)."
        ),
    ),
]


def _sha16(path: Path) -> str:
    """The sha ``save_checkpoint`` records and ``ModelRegistry`` recomputes: sha256[:16].

    Computed here from the file's own bytes so the expected value is independent of
    the sidecar the resolution reports - the recompute is the oracle, not the label.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def test_recorded_entry_resolves_non_degraded_with_its_sha_in_the_version() -> None:
    """One resolution: degraded=false, and the recorded sha is in the version string."""
    source = policy().source
    name = policy().serving_name
    checkpoint_dir = ROOT / source.local_candidate_dir
    checkpoint = checkpoint_dir / source.checkpoint_filename.format(name=name)

    if not checkpoint.is_file():
        pytest.fail(
            f"SYNAPSE_SMOKE_RUN is set but {checkpoint.relative_to(ROOT).as_posix()} is "
            "absent. Inside the training-smoke job the smoke train runs first, so a "
            "missing artifact is a broken job, not an unavailable proof."
        )
    if importlib.util.find_spec("torch") is None:
        pytest.fail(
            "SYNAPSE_SMOKE_RUN is set but torch is absent. The training-smoke job installs "
            "the CPU wheel; a missing prerequisite inside the proving job is a failure, "
            "never a skip (I-7)."
        )

    from agents.demand_prophet.config import DemandProphetConfig
    from agents.demand_prophet.inference import serve

    # The production wiring must be pointed at the directory the policy declares,
    # otherwise this test would prove a resolution no deployed server performs.
    assert Path(serve.SERVING_CHECKPOINT_DIR) == checkpoint_dir

    registry = serve._build_model_registry(DemandProphetConfig())  # noqa: SLF001
    loaded = registry.load(name)  # the ONE resolution this test performs

    assert loaded.local_path is not None, (
        "the resolution did not come from the $0 checkpoint source, so there is no "
        f"artifact whose sha can be compared (version={loaded.version!r})"
    )
    resolved = Path(loaded.local_path)
    resolved_sha = _sha16(resolved)

    # --- the R3.2 clause -------------------------------------------------------
    assert loaded.degraded is False, f"serving degraded instead of resolving {name}"
    assert loaded.is_real is True
    assert resolved_sha in loaded.version, (
        f"the resolved artifact's sha {resolved_sha!r} does not appear in the version "
        f"string {loaded.version!r}, so a record naming that sha could not be pinned to "
        "what serving loaded"
    )
    assert loaded.sha == resolved_sha, (
        f"ModelRegistry reported sha {loaded.sha!r} for an artifact whose bytes hash to "
        f"{resolved_sha!r}"
    )
    entry = {**_RECORD_SHAPE, "sha": resolved_sha}
    sha_problems = [problem for problem in validate_entry(entry) if "sha" in problem]
    assert sha_problems == [], sha_problems

    # --- the I-7 clause: which artifact was this, really? ----------------------
    artifact_class, detail = classify(loaded.meta, policy().classification)
    committed = registry_status()
    if committed.ok:
        recorded = str(
            json.loads((ROOT / policy().registry_file).read_text(encoding="utf-8"))[name]["sha"]
        ).strip()
        assert recorded and resolved_sha.startswith(recorded), (
            f"the serving path resolved {resolved_sha!r} while the committed record names "
            f"{recorded!r}. ModelRegistry._resolve_checkpoint_path prefers a LOCAL "
            "checkpoint over the remote, so a locally built candidate is shadowing the "
            f"published artifact ({resolved.relative_to(ROOT).as_posix()}). R3.2 for a "
            "published entry has to be proven where no local candidate shadows it."
        )
        assert artifact_class is ArtifactClass.REAL, detail
    else:
        assert artifact_class is ArtifactClass.SMOKE, (
            "the committed registry holds no validated entry, so the artifact resolved here "
            f"must be the CI smoke one - the classifier says {artifact_class.value!r}: "
            f"{detail}. A full artifact resolving with nothing recorded is exactly the "
            "evidence swap R3.7 refuses."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
