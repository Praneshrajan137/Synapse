"""Tests for the Plan-v2 honesty contract (ADR-040 / ADR-041).

Covers provenance.py, features.py, model_registry.py, invariants.py — the
shared anti-corruption layer that makes every agent's serving path honest.
Pure-Python (no torch / Feast / MLflow needed): the providers degrade
gracefully when their backends are absent, which is exactly what these tests
assert.
"""

from __future__ import annotations

import pytest

from synapse_common.features import FeatureProvider, FeatureResult
from synapse_common.invariants import (
    InvariantViolation,
    Postcondition,
    RuntimeValidator,
)
from synapse_common.model_registry import LoadedModel, ModelRegistry, resolve_name
from synapse_common.provenance import (
    DEGRADED_VERSION,
    ConfidenceBasis,
    FeatureSource,
    Provenance,
)

# --------------------------------------------------------------------------- #
# Provenance value object
# --------------------------------------------------------------------------- #


def test_provenance_default_is_degraded() -> None:
    p = Provenance()
    assert p.degraded is True
    assert p.model_version == DEGRADED_VERSION
    assert p.confidence_basis == ConfidenceBasis.FALLBACK_FLOOR


def test_provenance_real_constructor() -> None:
    p = Provenance.real(
        model_version="demand_prophet_hgt_tft:7",
        confidence_basis=ConfidenceBasis.CONFORMAL_INTERVAL,
    )
    assert p.degraded is False
    assert p.feature_source == FeatureSource.FEAST
    assert "model_version=demand_prophet_hgt_tft:7" in p.trace_line()


def test_provenance_real_rejects_constant_confidence() -> None:
    with pytest.raises(ValueError, match="uncertainty-derived"):
        Provenance.real(
            model_version="x:1", confidence_basis=ConfidenceBasis.CONSTANT
        )


def test_provenance_real_rejects_degraded_version() -> None:
    with pytest.raises(ValueError, match="concrete model_version"):
        Provenance.real(
            model_version=DEGRADED_VERSION,
            confidence_basis=ConfidenceBasis.CONFORMAL_INTERVAL,
        )


def test_provenance_is_frozen() -> None:
    p = Provenance()
    with pytest.raises(Exception):  # noqa: B017 — pydantic frozen raises ValidationError/TypeError
        p.degraded = False  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# FeatureProvider — honest degradation
# --------------------------------------------------------------------------- #


def test_feature_provider_no_client_degrades() -> None:
    fp = FeatureProvider(feast_client=None, city="bengaluru")
    result = fp.get(["sku_1", "sku_2"], ["demand:rolling_7d"], store_id="store_a")
    assert isinstance(result, FeatureResult)
    assert result.degraded is True
    assert result.source == FeatureSource.FALLBACK
    assert result.num_entities == 2


def test_feature_provider_fallback_is_deterministic() -> None:
    fp = FeatureProvider(feast_client=None)
    a = fp.get(["sku_1"], ["demand:x"], store_id="s")
    b = fp.get(["sku_1"], ["demand:x"], store_id="s")
    assert a.values["demand:x"] == b.values["demand:x"]


def test_feature_provider_fallback_order_invariant_per_key() -> None:
    """MR-*-004: a key's features must not depend on its position in the batch."""
    fp = FeatureProvider(feast_client=None)
    forward = fp.get(["sku_1", "sku_2"], ["demand:x"], store_id="s")
    reverse = fp.get(["sku_2", "sku_1"], ["demand:x"], store_id="s")
    fwd = dict(zip(forward.entity_keys, forward.values["demand:x"]))
    rev = dict(zip(reverse.entity_keys, reverse.values["demand:x"]))
    assert fwd == rev


def test_feature_provider_mumbai_injects_monsoon() -> None:
    fp = FeatureProvider(feast_client=None, city="mumbai")
    result = fp.get(["sku_1"], ["demand:x"], store_id="s")
    assert "monsoon_intensity" in result.values  # E-S6-09


def test_feature_provider_real_path() -> None:
    class FakeOnline:
        def to_dict(self) -> dict[str, list[float]]:
            return {"sku_id": ["sku_1"], "demand:x": [0.42]}

    class FakeFeast:
        def get_online_features(self, features, entity_rows):  # noqa: ANN001, ANN201
            return FakeOnline()

    fp = FeatureProvider(feast_client=FakeFeast())
    result = fp.get(["sku_1"], ["demand:x"])
    assert result.degraded is False
    assert result.source == FeatureSource.FEAST
    assert result.values["demand:x"] == [0.42]


def test_feature_provider_feast_failure_degrades_not_raises() -> None:
    class BoomFeast:
        def get_online_features(self, features, entity_rows):  # noqa: ANN001, ANN201
            raise ConnectionError("feast down")

    fp = FeatureProvider(feast_client=BoomFeast(), max_retries=1)
    result = fp.get(["sku_1"], ["demand:x"])
    assert result.degraded is True  # I-7: never crashes


# --------------------------------------------------------------------------- #
# ModelRegistry — naming + honest degradation
# --------------------------------------------------------------------------- #


def test_resolve_name_conventions() -> None:
    assert resolve_name("demand_prophet") == "demand_prophet"
    assert resolve_name("demand_prophet", city="mumbai") == "mumbai_demand_prophet"
    assert resolve_name("demand_prophet", coldstart=True) == "coldstart_demand_prophet"
    assert (
        resolve_name("demand_prophet", city="mumbai", coldstart=True)
        == "mumbai_coldstart_demand_prophet"
    )


def test_model_registry_no_client_degrades() -> None:
    reg = ModelRegistry(mlflow_client=None)
    loaded = reg.load("demand_prophet")
    assert isinstance(loaded, LoadedModel)
    assert loaded.degraded is True
    assert loaded.model is None
    assert loaded.version == DEGRADED_VERSION
    assert loaded.is_real is False


def test_model_registry_real_load() -> None:
    class MV:
        version = "7"
        source = "models:/demand_prophet/7"

    class FakeMlflow:
        def get_latest_versions(self, name, stages):  # noqa: ANN001, ANN201
            return [MV()]

        def load_model(self, uri):  # noqa: ANN001, ANN201
            return object()  # a non-None "model"

    reg = ModelRegistry(mlflow_client=FakeMlflow())
    loaded = reg.load("demand_prophet")
    assert loaded.is_real is True
    assert loaded.version == "7"
    assert loaded.sha != DEGRADED_VERSION


def test_model_registry_missing_version_falls_back_then_degrades() -> None:
    class EmptyMlflow:
        def get_latest_versions(self, name, stages):  # noqa: ANN001, ANN201
            return []

        def load_model(self, uri):  # noqa: ANN001, ANN201
            raise AssertionError("should not be called")

    reg = ModelRegistry(mlflow_client=EmptyMlflow())
    loaded = reg.load("demand_prophet")
    assert loaded.degraded is True  # tried coldstart, then degraded — never raised


# --------------------------------------------------------------------------- #
# RuntimeValidator — postconditions lifted to runtime
# --------------------------------------------------------------------------- #


def test_runtime_validator_passes_clean_output() -> None:
    pc = Postcondition("INV-X-001", "value must be non-negative", lambda o: o["v"] >= 0)
    rv = RuntimeValidator("demand_prophet", [pc])
    rv.validate({"v": 5})  # no raise


def test_runtime_validator_raises_on_breach() -> None:
    pc = Postcondition("INV-X-001", "value must be non-negative", lambda o: o["v"] >= 0)
    rv = RuntimeValidator("demand_prophet", [pc])
    with pytest.raises(InvariantViolation) as exc:
        rv.validate({"v": -1})
    assert "INV-X-001" in str(exc.value)
    assert exc.value.agent == "demand_prophet"


def test_runtime_validator_checks_every_item_in_list() -> None:
    pc = Postcondition("INV-X-001", "non-negative", lambda o: o["v"] >= 0)
    rv = RuntimeValidator("demand_prophet", [pc])
    with pytest.raises(InvariantViolation) as exc:
        rv.validate([{"v": 1}, {"v": -2}])
    assert "[1]" in str(exc.value)  # the second item is flagged


def test_runtime_validator_predicate_crash_is_failure() -> None:
    pc = Postcondition("INV-X-002", "needs key", lambda o: o["missing"] > 0)
    rv = RuntimeValidator("demand_prophet", [pc])
    with pytest.raises(InvariantViolation):
        rv.validate({"v": 1})
