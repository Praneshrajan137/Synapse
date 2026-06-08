"""SYNAPSE model anti-corruption layer (ADR-041).

``ModelRegistry`` is the single published-language path between an agent's
inference pipeline and MLflow. It resolves a logical model name (+ optional city
+ stage) to the registered checkpoint, loads it, and returns a
:class:`LoadedModel` carrying the concrete ``version``/``sha`` that feeds output
:class:`~synapse_common.provenance.Provenance` (and thus the I-4 audit trail).

Naming conventions are enforced here, not scattered across agents:

  * Mumbai transfer-learned models live under ``mumbai_<name>`` (E-S6-07).
  * Cold-start baselines live under ``coldstart_<name>`` / ``mumbai_coldstart_<name>``
    (E-S6-14).

When the model is absent or MLflow is unreachable the registry returns a
``LoadedModel`` with ``model=None`` and ``degraded=True`` — it never raises. The
pipeline then takes its documented I-7 fallback and stamps a degraded provenance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from synapse_common.provenance import DEGRADED_VERSION

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LoadedModel:
    """A resolved model handle with the version/sha needed for provenance.

    ``local_path`` / ``meta`` are populated only by the $0 checkpoint source
    (ADR-043): ``local_path`` is the resolved ``.pt`` on disk and ``meta`` carries
    the deterministic serving sidecar (architecture dims + fitted calibrator state).
    The MLflow path leaves both at their defaults — MLflow owns deserialization, so
    the agent needs nothing extra from us.
    """

    model: Any
    name: str
    version: str
    sha: str
    stage: str
    degraded: bool
    local_path: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_real(self) -> bool:
        return self.model is not None and not self.degraded


def resolve_name(base_name: str, *, city: str = "bengaluru", coldstart: bool = False) -> str:
    """Apply the SYNAPSE model-naming conventions (E-S6-07, E-S6-14).

    >>> resolve_name("demand_prophet_hgt_tft", city="mumbai")
    'mumbai_demand_prophet_hgt_tft'
    >>> resolve_name("demand_prophet_hgt_tft", city="mumbai", coldstart=True)
    'mumbai_coldstart_demand_prophet_hgt_tft'
    >>> resolve_name("demand_prophet_hgt_tft")
    'demand_prophet_hgt_tft'
    """
    name = base_name
    if coldstart:
        name = f"coldstart_{name}"
    if city and city != "bengaluru":
        name = f"{city}_{name}"
    return name


class ModelRegistry:
    """Anti-corruption layer over the MLflow model registry (ADR-041)."""

    def __init__(
        self,
        mlflow_client: Any = None,
        *,
        tracking_uri: str | None = None,
        default_stage: str = "Production",
        checkpoint_dir: Path | str | None = None,
        hf_repo: str | None = None,
        model_builder: Callable[[Any, dict[str, Any]], Any] | None = None,
    ) -> None:
        self._client = mlflow_client
        self._tracking_uri = tracking_uri
        self._default_stage = default_stage
        # $0 serving source (ADR-043): a checkpoint resolved from a local dir
        # and/or HF Hub, built into a concrete model by an agent-injected builder.
        # The registry stays architecture-agnostic — it never imports an agent.
        self._checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self._hf_repo = hf_repo
        self._model_builder = model_builder

    def _has_checkpoint_source(self) -> bool:
        return self._checkpoint_dir is not None or self._hf_repo is not None

    def load(
        self,
        base_name: str,
        *,
        city: str = "bengaluru",
        stage: str | None = None,
        coldstart: bool = False,
    ) -> LoadedModel:
        """Resolve + load a model. Never raises — degrades instead (I-7).

        Resolution order: the MLflow registry (lineage path) when a client is
        present, then the $0 checkpoint source (local file / HF Hub) as the
        serving path, then the cold-start baseline once, then honest degradation.
        """
        name = resolve_name(base_name, city=city, coldstart=coldstart)
        stage = stage or self._default_stage

        if self._client is None and not self._has_checkpoint_source():
            return self._degraded(name, stage, reason="no_mlflow_client")

        # 1. MLflow lineage path (when a client is configured).
        if self._client is not None:
            try:
                model, version, sha = self._load_from_mlflow(name, stage)
                if model is not None:
                    logger.info("model_loaded", name=name, version=version, stage=stage)
                    return LoadedModel(
                        model=model,
                        name=name,
                        version=version,
                        sha=sha,
                        stage=stage,
                        degraded=False,
                    )
                logger.warning("model_uri_returned_none", name=name, stage=stage)
            except Exception as exc:  # noqa: BLE001 — any registry failure degrades (I-7)
                logger.warning("model_registry_unreachable", name=name, stage=stage, error=str(exc))

        # 2. $0 checkpoint serving source (local file or HF Hub).
        loaded = self._load_from_checkpoint(name, stage)
        if loaded is not None:
            return loaded

        # 3. Cold-start baseline once, then degrade.
        if not coldstart:
            logger.info("model_registry_trying_coldstart", name=name)
            return self.load(base_name, city=city, stage=stage, coldstart=True)
        return self._degraded(name, stage, reason="no_model_in_registry_or_checkpoint")

    def _load_from_checkpoint(self, name: str, stage: str) -> LoadedModel | None:
        """Resolve ``{name}.pt`` (+ ``{name}.serving.json`` sidecar) from disk or HF.

        Returns a real :class:`LoadedModel` or ``None`` so the caller degrades.
        Never raises (I-7).
        """
        if not self._has_checkpoint_source():
            return None
        try:
            ckpt_path = self._resolve_checkpoint_path(name)
            if ckpt_path is None or not ckpt_path.is_file():
                return None
            from synapse_common.training_contract import load_checkpoint  # noqa: PLC0415

            artifact = load_checkpoint(ckpt_path)
            meta = self._read_sidecar(name, ckpt_path)
            model = self._model_builder(artifact, meta) if self._model_builder else artifact
            if model is None:
                return None
            version = str(meta.get("version") or "checkpoint")
            sha = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()[:16]
            logger.info(
                "model_loaded_from_checkpoint", name=name, version=version, path=str(ckpt_path)
            )
            return LoadedModel(
                model=model,
                name=name,
                version=version,
                sha=sha,
                stage=stage,
                degraded=False,
                local_path=str(ckpt_path),
                meta=meta,
            )
        except Exception as exc:  # noqa: BLE001 — a corrupt/missing artifact degrades (I-7)
            logger.warning("checkpoint_load_failed", name=name, error=str(exc))
            return None

    def _resolve_checkpoint_path(self, name: str) -> Path | None:
        """Local dir first; fall back to a (cached) HF Hub download. None if absent."""
        if self._checkpoint_dir is not None:
            local = self._checkpoint_dir / f"{name}.pt"
            if local.is_file():
                return local
        if self._hf_repo is not None:
            try:
                import contextlib  # noqa: PLC0415

                from huggingface_hub import hf_hub_download  # noqa: PLC0415

                # Pull the sidecar too (best-effort) so it sits next to the .pt.
                with contextlib.suppress(Exception):
                    hf_hub_download(repo_id=self._hf_repo, filename=f"{name}.serving.json")
                got = hf_hub_download(repo_id=self._hf_repo, filename=f"{name}.pt")
                return Path(got)
            except Exception as exc:  # noqa: BLE001 — HF unreachable/absent degrades (I-7)
                logger.warning("hf_download_failed", repo=self._hf_repo, name=name, error=str(exc))
        return None

    @staticmethod
    def _read_sidecar(name: str, ckpt_path: Path) -> dict[str, Any]:
        """Read ``{name}.serving.json`` sitting next to the checkpoint. {} if absent."""
        sidecar = ckpt_path.parent / f"{name}.serving.json"
        if not sidecar.is_file():
            return {}
        try:
            parsed: dict[str, Any] = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("sidecar_unreadable", path=str(sidecar), error=str(exc))
            return {}
        return parsed

    def _load_from_mlflow(self, name: str, stage: str) -> tuple[Any, str, str]:
        """Load via the injected MLflow client. Duck-typed for testability."""
        # The client exposes get_latest_versions(name, [stage]) -> [ModelVersion]
        versions = self._client.get_latest_versions(name, [stage])
        if not versions:
            raise LookupError(f"no '{stage}' version registered for {name!r}")
        mv = versions[0]
        version = str(getattr(mv, "version", "0"))
        source = str(getattr(mv, "source", name))
        model = self._client.load_model(source)
        sha = hashlib.sha256(f"{name}:{version}:{source}".encode()).hexdigest()[:16]
        return model, version, sha

    @staticmethod
    def _degraded(name: str, stage: str, *, reason: str) -> LoadedModel:
        logger.warning("model_registry_degraded", name=name, stage=stage, reason=reason)
        return LoadedModel(
            model=None,
            name=name,
            version=DEGRADED_VERSION,
            sha=DEGRADED_VERSION,
            stage=stage,
            degraded=True,
        )


__all__ = ["LoadedModel", "ModelRegistry", "resolve_name"]
