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
from dataclasses import dataclass
from typing import Any

import structlog

from synapse_common.provenance import DEGRADED_VERSION

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LoadedModel:
    """A resolved model handle with the version/sha needed for provenance."""

    model: Any
    name: str
    version: str
    sha: str
    stage: str
    degraded: bool

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
    ) -> None:
        self._client = mlflow_client
        self._tracking_uri = tracking_uri
        self._default_stage = default_stage

    def load(
        self,
        base_name: str,
        *,
        city: str = "bengaluru",
        stage: str | None = None,
        coldstart: bool = False,
    ) -> LoadedModel:
        """Resolve + load a model. Never raises — degrades instead (I-7)."""
        name = resolve_name(base_name, city=city, coldstart=coldstart)
        stage = stage or self._default_stage

        if self._client is None:
            return self._degraded(name, stage, reason="no_mlflow_client")

        try:
            model, version, sha = self._load_from_mlflow(name, stage)
        except Exception as exc:  # noqa: BLE001 — any registry failure degrades (I-7)
            logger.warning("model_registry_unreachable", name=name, stage=stage, error=str(exc))
            # Fall back to the cold-start baseline once before fully degrading.
            if not coldstart:
                logger.info("model_registry_trying_coldstart", name=name)
                return self.load(base_name, city=city, stage=stage, coldstart=True)
            return self._degraded(name, stage, reason=str(exc))

        if model is None:
            return self._degraded(name, stage, reason="model_uri_returned_none")

        logger.info("model_loaded", name=name, version=version, stage=stage)
        return LoadedModel(
            model=model, name=name, version=version, sha=sha, stage=stage, degraded=False
        )

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
