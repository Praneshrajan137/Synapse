"""$0 checkpoint-source tests for ModelRegistry (ADR-043).

The MLflow path (test_honesty_contract.py) proves lineage resolution. These prove
the *serving* path the free-tier VM actually uses: a checkpoint resolved from a
local dir (or HF Hub), built into a concrete model by an injected builder, with
the architecture + fitted calibrator carried in the sidecar meta. torch-free — a
JSON artifact + a sentinel builder stand in for the trained module.

Scope (R3.8) — TRANSPORT AND ADAPTER VALIDATION ONLY. Every proof below writes its
checkpoint into a pytest ``tmp_path`` and resolves it from that temporary directory,
so what is validated is the checkpoint *transport* (local dir -> loader -> sidecar)
and the *adapter* (injected builder -> ``LoadedModel``). This module is deliberately
**not evidence that a checkpoint is published**: ``ModelRegistry._resolve_checkpoint_path``
prefers a local file over the remote, which is exactly why a locally built artifact
must never be counted as publication evidence, and no published-checkpoint gate reads
this module (``scripts/audit/published_checkpoint_truth.py`` fetches the remote
sidecar directly and names the local candidates it REFUSED).

The label is mechanical, not decorative: ``packages/tests/test_checkpoint_scope_labelling.py``
enforces the statement above and the two constants below against the committed
``infrastructure/quality/checkpoint-scope.yaml``. Deleting either fails that test.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

import pytest
from synapse_common.model_registry import LoadedModel, ModelRegistry
from synapse_common.provenance import DEGRADED_VERSION
from synapse_common.training_contract import save_checkpoint

if TYPE_CHECKING:
    from pathlib import Path

NAME = "demand_prophet_hgt_tft"

#: R3.8 scope label. Read by packages/tests/test_checkpoint_scope_labelling.py.
SERVING_PROOF_SCOPE: Final[str] = "transport-and-adapter-only"
#: This module is never counted as evidence that a checkpoint is published (I-7).
PUBLICATION_EVIDENCE: Final[bool] = False


def _write_artifact(tmp: Path, *, sidecar: dict | None = None) -> str:
    sha = save_checkpoint({"w": [1.0, 2.0, 3.0]}, tmp / f"{NAME}.pt")
    if sidecar is not None:
        (tmp / f"{NAME}.serving.json").write_text(
            json.dumps(sidecar, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
    return sha


def test_checkpoint_source_loads_local_and_carries_meta(tmp_path: Path) -> None:
    _write_artifact(
        tmp_path,
        sidecar={"version": "smoke_abc", "arch": {"hgt_hidden_dim": 32}, "calibrator": {"k": 1}},
    )
    seen: dict = {}

    def builder(artifact: object, meta: dict) -> str:
        seen["artifact"] = artifact
        seen["meta"] = meta
        return f"MODEL[{meta.get('version')}]"

    reg = ModelRegistry(None, checkpoint_dir=tmp_path, model_builder=builder)
    loaded = reg.load(NAME)

    assert isinstance(loaded, LoadedModel)
    assert loaded.is_real is True
    assert loaded.model == "MODEL[smoke_abc]"
    assert loaded.version == "smoke_abc"
    assert loaded.meta["calibrator"] == {"k": 1}
    assert loaded.local_path is not None and loaded.local_path.endswith(f"{NAME}.pt")
    assert loaded.sha != DEGRADED_VERSION
    # The builder received the deserialized artifact + the sidecar meta.
    assert seen["artifact"] == {"w": [1.0, 2.0, 3.0]}
    assert seen["meta"]["arch"] == {"hgt_hidden_dim": 32}


def test_checkpoint_source_without_sidecar_still_real(tmp_path: Path) -> None:
    _write_artifact(tmp_path, sidecar=None)
    reg = ModelRegistry(None, checkpoint_dir=tmp_path, model_builder=lambda a, _m: a)
    loaded = reg.load(NAME)
    assert loaded.is_real is True
    assert loaded.version == "checkpoint"  # no sidecar version → default
    assert loaded.meta == {}


def test_checkpoint_absent_degrades(tmp_path: Path) -> None:
    reg = ModelRegistry(None, checkpoint_dir=tmp_path, model_builder=lambda a, _m: a)
    loaded = reg.load(NAME)  # nothing written
    assert loaded.degraded is True
    assert loaded.model is None
    assert loaded.is_real is False


def test_no_source_and_no_client_degrades_immediately() -> None:
    """The ModelRegistry(None) form used in tests/serve must still degrade."""
    loaded = ModelRegistry(None).load(NAME)
    assert loaded.degraded is True
    assert loaded.version == DEGRADED_VERSION


def test_builder_failure_degrades_not_raises(tmp_path: Path) -> None:
    """A corrupt artifact / failing builder degrades honestly (I-7), never raises."""
    _write_artifact(tmp_path, sidecar={"version": "v1"})

    def boom(_artifact: object, _meta: dict) -> object:
        raise ValueError("bad weights")

    reg = ModelRegistry(None, checkpoint_dir=tmp_path, model_builder=boom)
    loaded = reg.load(NAME)
    assert loaded.degraded is True
    assert loaded.model is None


def test_mlflow_takes_precedence_then_falls_through_to_checkpoint(tmp_path: Path) -> None:
    """An unreachable MLflow client must fall through to the checkpoint source."""
    _write_artifact(tmp_path, sidecar={"version": "ckpt_v"})

    class BrokenMlflow:
        def get_latest_versions(self, name, stages):  # noqa: ANN001, ANN202
            raise ConnectionError("mlflow down")

    reg = ModelRegistry(
        BrokenMlflow(), checkpoint_dir=tmp_path, model_builder=lambda a, _m: a
    )
    loaded = reg.load(NAME)
    assert loaded.is_real is True
    assert loaded.version == "ckpt_v"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
