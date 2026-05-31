"""Serving-truth tests for demand_prophet (C39, ADR-042).

Proves serve.py now resolves a model through ModelRegistry (not the old bare
``DemandProphetPipeline()`` with model=None), wraps a real checkpoint behind the
predict_quantiles adapter, and degrades honestly when MLflow is unreachable.
torch-free: a fake LoadedModel stands in for the trained module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synapse_common.model_registry import LoadedModel

from agents.demand_prophet.inference.serving_model import (
    DemandProphetServingModel,
    load_serving_model,
)

if TYPE_CHECKING:
    import pytest


class _FakeTorchModel:
    """Duck-typed stand-in exposing the bits the adapter touches (no torch)."""

    def eval(self) -> None:  # adapter calls .eval()
        pass


class _FakeRegistry:
    def __init__(self, loaded: LoadedModel) -> None:
        self._loaded = loaded
        self.calls: list[tuple] = []

    def load(self, base_name: str, *, city: str = "bengaluru", **_: object) -> LoadedModel:
        self.calls.append((base_name, city))
        return self._loaded


def _real_loaded() -> LoadedModel:
    return LoadedModel(
        model=_FakeTorchModel(),
        name="demand_prophet_hgt_tft",
        version="3",
        sha="abc123",
        stage="Production",
        degraded=False,
    )


def _degraded_loaded() -> LoadedModel:
    return LoadedModel(
        model=None,
        name="demand_prophet_hgt_tft",
        version="degraded",
        sha="degraded",
        stage="Production",
        degraded=True,
    )


def test_load_serving_model_returns_none_without_registry() -> None:
    assert load_serving_model(None) is None


def test_load_serving_model_returns_none_when_degraded() -> None:
    reg = _FakeRegistry(_degraded_loaded())
    assert load_serving_model(reg) is None
    assert reg.calls == [("demand_prophet_hgt_tft", "bengaluru")]


def test_load_serving_model_wraps_real_checkpoint() -> None:
    reg = _FakeRegistry(_real_loaded())
    model = load_serving_model(reg, city="mumbai")
    assert isinstance(model, DemandProphetServingModel)
    assert model.version == "3"
    assert reg.calls == [("demand_prophet_hgt_tft", "mumbai")]


def test_serve_module_wires_modelregistry() -> None:
    """The serve module must reference ModelRegistry + the loader (C39 AST shape)."""
    from agents.demand_prophet.inference import serve

    assert hasattr(serve, "_build_pipeline")
    assert hasattr(serve, "_build_model_registry")
    src = __import__("inspect").getsource(serve)
    assert "ModelRegistry" in src
    assert "load_serving_model" in src


def test_pipeline_degrades_when_unresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the registry resolves no real model, _build_pipeline degrades, not crashes.

    The registry is forced to the no-client (degraded) form so the test never
    touches the network; this exercises the wiring logic deterministically.
    """
    from synapse_common.model_registry import ModelRegistry

    from agents.demand_prophet.config import DemandProphetConfig
    from agents.demand_prophet.inference import serve

    monkeypatch.setattr(serve, "_build_model_registry", lambda _cfg: ModelRegistry(None))

    pipe = serve._build_pipeline(DemandProphetConfig())
    assert pipe._model is None  # no real model resolved → honest fallback
    forecasts = pipe.predict(["sku_1", "sku_2"], "store_a", horizons={"1h"})
    assert len(forecasts) == 2
    assert pipe.last_provenance.degraded is True


def test_pipeline_uses_real_model_when_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the registry returns a real LoadedModel, the pipeline gets a real model."""
    from agents.demand_prophet.config import DemandProphetConfig
    from agents.demand_prophet.inference import serve

    monkeypatch.setattr(serve, "_build_model_registry", lambda _cfg: _FakeRegistry(_real_loaded()))
    pipe = serve._build_pipeline(DemandProphetConfig())
    assert isinstance(pipe._model, DemandProphetServingModel)
    assert pipe._model.version == "3"
