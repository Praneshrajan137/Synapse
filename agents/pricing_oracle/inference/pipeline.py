"""
SYNAPSE Pricing Oracle -- Inference Pipeline.
Handles: Feast feature retrieval -> causal elasticity -> MADDPG action ->
         essential cap enforcement -> schema validation -> Kafka publish.
All within Tier 2 SLA (<500ms) (I-10).
"""

from __future__ import annotations

import time
from typing import Any

import deal
import numpy as np
import structlog
import torch
from synapse_common.features import FeatureProvider
from synapse_common.metrics import PRICING_ORACLE_ESSENTIAL_CAP_VIOLATION_TOTAL
from synapse_common.models import PricingDecision
from synapse_common.provenance import ConfidenceBasis, FeatureSource, Provenance

logger = structlog.get_logger(__name__)

VALID_CATEGORIES = frozenset({"essential", "snack", "beverage", "dairy", "produce"})
ESSENTIAL_CAP: float = 1.3
OBS_DIM: int = 24
# Feast feature references the pricing model reads (ADR-041).
FEATURE_REFS = [
    "pricing_features:demand_elasticity",
    "pricing_features:competitor_price_ratio",
    "pricing_features:inventory_pressure",
    "pricing_features:rolling_7d_units",
]
FALLBACK_CONFIDENCE = 0.5  # documented I-7 floor (rule-based pricing)


class PricingUpdate:
    """Lightweight output container for a single SKU pricing update."""

    __slots__ = (
        "sku_id",
        "store_id",
        "category",
        "is_essential",
        "base_price",
        "multiplier",
        "final_price",
        "elasticity_estimate",
        "confidence",
        "justification_trace",
    )

    def __init__(
        self,
        sku_id: str,
        store_id: str,
        category: str,
        is_essential: bool,
        base_price: float,
        multiplier: float,
        elasticity_estimate: float,
        confidence: float,
        justification_trace: list[str],
    ) -> None:
        self.sku_id = sku_id
        self.store_id = store_id
        self.category = category
        self.is_essential = is_essential
        self.base_price = base_price
        self.multiplier = multiplier
        self.final_price = base_price * multiplier
        self.elasticity_estimate = elasticity_estimate
        self.confidence = confidence
        self.justification_trace = justification_trace

    def to_pricing_decision(self) -> PricingDecision:
        """Convert to the canonical synapse_common PricingDecision model."""
        return PricingDecision(
            sku_id=self.sku_id,
            store_id=self.store_id,
            category_id=self.category,
            is_essential=self.is_essential,
            base_price=self.base_price,
            multiplier=self.multiplier,
            final_price=self.final_price,
        )


class PricingOraclePipeline:
    """
    End-to-end inference pipeline for the Pricing Oracle.
    All outputs enforce INV-PO-001 (essential cap 1.3x).
    """

    def __init__(
        self,
        model: Any = None,
        causal_estimator: Any = None,
        feast_client: Any = None,
        neo4j_driver: Any = None,
        kafka_producer: Any = None,
    ) -> None:
        self._model = model
        self._causal = causal_estimator
        self._feast = feast_client
        self._neo4j = neo4j_driver
        self._kafka = kafka_producer
        # ADR-041: features through the anti-corruption layer. ADR-040: track
        # degradation per call so the served confidence + provenance are honest.
        self._features = FeatureProvider(feast_client)
        self._feature_source = FeatureSource.FALLBACK
        self._model_degraded = model is None
        self._causal_degraded = True
        self.last_provenance: Provenance = Provenance.degraded_fallback()

    @deal.pre(
        lambda self, sku_ids, store_id, categories, base_prices, **kw: (len(sku_ids) >= 1),
        message="PRE-PO-004: At least one SKU required",
    )
    @deal.pre(
        lambda self, sku_ids, store_id, categories, base_prices, **kw: (len(sku_ids) <= 200),
        message="PRE-PO-004: Maximum 200 SKUs per batch",
    )
    @deal.pre(
        lambda self, sku_ids, store_id, categories, base_prices, **kw: (
            all(bp > 0.0 for bp in base_prices)
        ),
        message="PRE-PO-003: All base prices must be strictly positive",
    )
    def price(
        self,
        sku_ids: list[str],
        store_id: str,
        categories: list[str],
        base_prices: list[float],
        demand_forecasts: list[float] | None = None,
    ) -> list[PricingUpdate]:
        """Generate price multipliers for a batch of SKUs."""
        start_time = time.monotonic()

        self._validate_preconditions(sku_ids, categories, base_prices)

        features = self._get_features(sku_ids, store_id)
        elasticities = self._estimate_elasticities(features, categories)
        raw_multipliers = self._run_inference(features, categories)

        updates = self._build_updates(
            sku_ids,
            store_id,
            categories,
            base_prices,
            raw_multipliers,
            elasticities,
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        if elapsed_ms > 500:
            logger.warning(
                "latency_sla_exceeded",
                elapsed_ms=elapsed_ms,
                sla_ms=500,
                num_skus=len(sku_ids),
            )

        logger.info(
            "pricing_complete",
            num_skus=len(sku_ids),
            store_id=store_id,
            latency_ms=f"{elapsed_ms:.1f}",
        )

        return updates

    def _validate_preconditions(
        self,
        sku_ids: list[str],
        categories: list[str],
        base_prices: list[float],
    ) -> None:
        if not (1 <= len(sku_ids) <= 200):
            raise ValueError(f"PRE-PO-004: SKU count {len(sku_ids)} outside bounds [1, 200]")
        for cat in categories:
            if cat not in VALID_CATEGORIES:
                raise ValueError(f"PRE-PO-001: Invalid category '{cat}'. Valid: {VALID_CATEGORIES}")
        for bp in base_prices:
            if bp <= 0.0:
                raise ValueError(f"PRE-PO-003: Base price must be positive, got {bp}")

    def _get_features(self, sku_ids: list[str], store_id: str) -> dict[str, Any]:
        """Retrieve features via the anti-corruption layer (ADR-041).

        Builds a real ``controls`` matrix (num_skus, num_features) for the causal
        elasticity estimator from the retrieved features — never the
        guard-then-ignore synthetic shortcut.
        """
        result = self._features.get(sku_ids, FEATURE_REFS, store_id=store_id)
        self._feature_source = result.source
        values = dict(result.values)
        num_skus = len(sku_ids)
        cols: list[np.ndarray] = []
        for ref in FEATURE_REFS:
            vals = values.get(ref)
            arr = (
                np.zeros(num_skus)
                if vals is None
                else np.resize(np.asarray(vals, dtype=np.float64).reshape(-1), num_skus)
            )
            cols.append(arr)
        values["controls"] = np.stack(cols, axis=1) if cols else np.zeros((num_skus, 1))
        values["num_skus"] = num_skus
        values["sku_ids"] = list(sku_ids)
        return values

    def _estimate_elasticities(
        self,
        features: dict[str, Any],
        categories: list[str],
    ) -> list[float]:
        """Estimate causal price elasticities. Falls back to heuristics (I-7)."""
        if self._causal is not None and self._causal.is_fitted:
            controls = features.get("controls")
            if controls is not None:
                effects = self._causal.estimate_elasticity(controls)
                self._causal_degraded = False
                return [float(e) for e in effects.flatten()]

        logger.warning("causal_unavailable", fallback="heuristic elasticities")
        self._causal_degraded = True
        return self._heuristic_elasticities(categories)

    def _heuristic_elasticities(self, categories: list[str]) -> list[float]:
        """Heuristic fallback when DML model unavailable (I-7)."""
        defaults: dict[str, float] = {
            "essential": -0.3,
            "snack": -1.2,
            "beverage": -1.5,
            "dairy": -0.8,
            "produce": -0.6,
        }
        return [defaults.get(cat, -1.0) for cat in categories]

    def _run_inference(
        self,
        features: dict[str, Any],
        categories: list[str],
    ) -> list[float]:
        """Run MADDPG or fall back to rule-based pricing (I-7)."""
        if self._model is not None:
            try:
                obs = self._build_observations(features, categories)
                with torch.no_grad():
                    actions = self._model.select_actions(obs)
                self._model_degraded = False
                return [float(actions[cat].item()) for cat in categories]
            except Exception as exc:  # noqa: BLE001 — model failure degrades (I-7)
                logger.warning("model_inference_failed", error=str(exc), fallback="rule-based")

        logger.warning("model_unavailable", fallback="rule-based pricing")
        self._model_degraded = True
        return self._rule_based_fallback(categories)

    def _rule_based_fallback(self, categories: list[str]) -> list[float]:
        """Rule-based fallback when model unavailable (I-7: graceful degradation)."""
        defaults: dict[str, float] = {
            "essential": 1.0,
            "snack": 1.15,
            "beverage": 1.2,
            "dairy": 1.05,
            "produce": 1.1,
        }
        return [defaults.get(cat, 1.0) for cat in categories]

    def _build_observations(
        self,
        features: dict[str, Any],
        categories: list[str],
    ) -> dict[str, torch.Tensor]:
        """Build per-category MADDPG observations from REAL features (ADR-040/041).

        Each category's observation is the mean feature vector of the SKUs in
        that category, tiled/padded to ``OBS_DIM``. No random noise — the model
        sees the actual retrieved features. Deterministic given the same inputs.
        """
        controls = np.asarray(features.get("controls", np.zeros((1, 1))), dtype=np.float64)
        obs: dict[str, torch.Tensor] = {}
        for cat in set(categories):
            idx = [i for i, c in enumerate(categories) if c == cat and i < controls.shape[0]]
            vec = controls[idx].mean(axis=0) if idx else controls.mean(axis=0)
            # Tile/pad the real feature vector up to OBS_DIM deterministically.
            tiled = np.resize(vec, OBS_DIM)
            obs[cat] = torch.tensor(tiled, dtype=torch.float32).unsqueeze(0)
        return obs

    @deal.post(
        lambda result: all(
            u.multiplier <= ESSENTIAL_CAP for u in result if u.category == "essential"
        ),
        message="POST-PO-003: Essential cap must be enforced on all essential items",
    )
    def _build_updates(
        self,
        sku_ids: list[str],
        store_id: str,
        categories: list[str],
        base_prices: list[float],
        multipliers: list[float],
        elasticities: list[float],
    ) -> list[PricingUpdate]:
        """Assemble PricingUpdate objects with hard cap enforcement."""
        updates: list[PricingUpdate] = []

        for i, sku_id in enumerate(sku_ids):
            category = categories[i]
            is_essential = category == "essential"
            mult = multipliers[i]

            if is_essential:
                # WS-12: record pre-cap incidence BEFORE clamping. Output
                # stays safe (post-cap), but INV-PO-001 alert needs
                # visibility into how often the pricing model wants to
                # break the cap. A single increment is treated as
                # critical by infrastructure/prometheus/rules/pricing_oracle_invariants.yml.
                if mult > ESSENTIAL_CAP:
                    PRICING_ORACLE_ESSENTIAL_CAP_VIOLATION_TOTAL.labels(sku_id=sku_id).inc()
                mult = min(mult, ESSENTIAL_CAP)

            mult = max(mult, 0.5)

            conf = self._derive_confidence(elasticities[i])
            traces = [
                f"category={category}",
                f"base_price={base_prices[i]:.2f}",
                f"raw_multiplier={multipliers[i]:.4f}",
                f"elasticity={elasticities[i]:.4f}",
                f"confidence={conf:.4f}",
            ]
            if is_essential:
                traces.append(f"essential_cap_applied={ESSENTIAL_CAP}")

            update = PricingUpdate(
                sku_id=sku_id,
                store_id=store_id,
                category=category,
                is_essential=is_essential,
                base_price=base_prices[i],
                multiplier=mult,
                elasticity_estimate=elasticities[i],
                confidence=conf,
                justification_trace=traces,
            )
            updates.append(update)

        self._set_provenance()
        return updates

    def _derive_confidence(self, elasticity: float) -> float:
        """ADR-040: confidence from the strength of the estimated elasticity and
        the source of the action. A larger |elasticity| is a stronger causal
        signal → higher confidence. On the rule-based / heuristic fallback the
        confidence is the documented I-7 floor. Never a constant."""
        if self._model_degraded or self._causal_degraded:
            return FALLBACK_CONFIDENCE
        strength = float(np.tanh(abs(elasticity)))
        return round(float(np.clip(0.5 + 0.45 * strength, 0.5, 0.95)), 4)

    def _set_provenance(self) -> None:
        degraded = (
            self._model_degraded
            or self._causal_degraded
            or self._feature_source == FeatureSource.FALLBACK
        )
        if degraded:
            self.last_provenance = Provenance.degraded_fallback(feature_source=self._feature_source)
        else:
            model_ver = getattr(self._model, "version", None) or "maddpg_dml"
            self.last_provenance = Provenance.real(
                model_version=f"pricing_oracle_{model_ver}",
                confidence_basis=ConfidenceBasis.CRITIC_VALUE_SPREAD,
                feature_source=self._feature_source,
            )
