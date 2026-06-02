"""
SYNAPSE Demand Prophet -- Inference Pipeline.
Handles: Feast feature retrieval -> Neo4j graph query -> model inference ->
         conformal intervals -> schema validation -> Kafka publish.
All within Tier 2 SLA (<500ms) (I-10).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import numpy as np
import structlog
from synapse_common.features import FeatureProvider
from synapse_common.metrics import (
    DEMAND_PROPHET_COVERAGE_P90,
    DEMAND_PROPHET_NEGATIVE_HORIZON_TOTAL,
)
from synapse_common.models import DemandForecast
from synapse_common.provenance import ConfidenceBasis, FeatureSource, Provenance

logger = structlog.get_logger(__name__)

VALID_HORIZONS = frozenset({"15min", "1h", "6h", "24h", "7d"})
# Feast feature references this agent reads (view:feature). These MUST match the
# registered FeatureView `sku_demand_signals` in data_fabric/feast/features/
# demand_features.py — a mismatched ref makes real Feast reject the request and the
# FeatureProvider degrade to FALLBACK forever (ADR-043 seam). When Feast is
# unreachable the FeatureProvider synthesises these deterministically (ADR-041).
FEATURE_REFS = [
    "sku_demand_signals:rolling_mean_7d",
    "sku_demand_signals:rolling_std_7d",
    "sku_demand_signals:trend_slope",
    "sku_demand_signals:seasonality_idx",
]
FALLBACK_CONFIDENCE = 0.5  # documented I-7 floor when no calibrated model is present


class DemandProphetPipeline:
    """
    End-to-end inference pipeline for the Demand Prophet.
    All outputs are DemandForecast Pydantic models (I-3).
    """

    def __init__(
        self,
        model: Any = None,
        conformal_calibrator: Any = None,
        feast_client: Any = None,
        neo4j_driver: Any = None,
        kafka_producer: Any = None,
    ) -> None:
        self._model = model
        self._calibrator = conformal_calibrator
        self._feast = feast_client
        self._neo4j = neo4j_driver
        self._kafka = kafka_producer
        # ADR-041: features flow through the anti-corruption layer, never Feast
        # directly. ADR-040: provenance/degradation tracked per call.
        self._features = FeatureProvider(feast_client)
        self._feature_source = FeatureSource.FALLBACK
        self._model_degraded = model is None
        self.last_provenance: Provenance = Provenance.degraded_fallback()

    def predict(
        self,
        sku_ids: list[str],
        store_id: str,
        horizons: set[str] | None = None,
        include_uncertainty: bool = True,
    ) -> list[DemandForecast]:
        """Generate demand forecasts for a batch of SKUs."""
        start_time = time.monotonic()

        if horizons is None:
            horizons = set(VALID_HORIZONS)

        self._validate_preconditions(sku_ids, store_id, horizons)

        features = self._get_features(sku_ids, store_id)
        graph_context = self._get_graph_context(sku_ids, store_id)
        raw_predictions = self._run_inference(features, graph_context)

        intervals = None
        if include_uncertainty and self._calibrator is not None:
            try:
                intervals = self._calibrator.predict_intervals(raw_predictions)
            except Exception as exc:  # noqa: BLE001 — an unfit/failed calibrator degrades (I-7)
                # Without this guard a real model paired with an unfit calibrator
                # raises RuntimeError on the FIRST real-path request → unhandled 500.
                # Honest degradation: serve point + raw bands, stamp degraded.
                logger.warning(
                    "calibrator_unavailable", error=str(exc), fallback="raw model bands"
                )
                intervals = None
        if intervals is not None:
            # WS-12: surface empirical coverage so INV-DP-002 alert fires
            # against a real metric. `coverage_meta` is the calibrator's
            # measured fraction-in-interval on the latest holdout slice;
            # absent the meta key, we fall back to NaN-skip (no update).
            coverage = (
                getattr(self._calibrator, "last_coverage_p90", None)
                if hasattr(self._calibrator, "last_coverage_p90")
                else None
            )
            if coverage is not None and 0.0 <= float(coverage) <= 1.0:
                city = self._city() if hasattr(self, "_city") else "unknown"
                DEMAND_PROPHET_COVERAGE_P90.labels(city=city).set(float(coverage))

        forecasts = self._build_forecasts(sku_ids, store_id, raw_predictions, intervals)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        if elapsed_ms > 500:
            logger.warning(
                "latency_sla_exceeded",
                elapsed_ms=elapsed_ms,
                sla_ms=500,
                num_skus=len(sku_ids),
            )

        logger.info(
            "prediction_complete",
            num_skus=len(sku_ids),
            store_id=store_id,
            latency_ms=f"{elapsed_ms:.1f}",
        )

        return forecasts

    def _validate_preconditions(
        self,
        sku_ids: list[str],
        store_id: str,
        horizons: set[str],
    ) -> None:
        if not (1 <= len(sku_ids) <= 500):
            raise ValueError(f"PRE-DP-001: SKU count {len(sku_ids)} outside bounds [1, 500]")
        if not horizons.issubset(VALID_HORIZONS):
            invalid = horizons - VALID_HORIZONS
            raise ValueError(f"PRE-DP-004: Invalid horizons {invalid}. Valid: {VALID_HORIZONS}")

    def _get_features(self, sku_ids: list[str], store_id: str) -> dict[str, Any]:
        """Retrieve features via the anti-corruption layer (ADR-041).

        Real features when Feast is reachable; deterministic fallback otherwise,
        with ``degraded`` propagated into provenance — never the guard-then-ignore
        shape that returned synthetic data even with a live store.
        """
        result = self._features.get(sku_ids, FEATURE_REFS, store_id=store_id)
        self._feature_source = result.source
        # Preserve the sku list + count for the deterministic EMA fallback.
        values = dict(result.values)
        values.setdefault("sku_ids", list(sku_ids))
        values.setdefault("num_skus", len(sku_ids))
        return values

    def _get_graph_context(self, sku_ids: list[str], store_id: str) -> dict[str, Any]:
        if self._neo4j is None:
            logger.warning("neo4j_unavailable", fallback="empty graph context")
            return {"node_features": {}, "edge_index": {}}
        return self._query_graph(sku_ids, store_id)

    def _query_graph(self, sku_ids: list[str], store_id: str) -> dict[str, Any]:
        """Query the Neo4j supply network for SKU adjacency features (ADR-005).

        Degrades to empty context on any driver failure (I-7) rather than taking
        the agent down.
        """
        try:
            with self._neo4j.session() as session:  # type: ignore[union-attr]
                rows = session.run(
                    "MATCH (s:SKU)-[:STOCKED_AT]->(st:Store {store_id: $store_id}) "
                    "WHERE s.sku_id IN $sku_ids RETURN s.sku_id AS sku_id, "
                    "s.substitution_degree AS deg",
                    sku_ids=list(sku_ids),
                    store_id=store_id,
                )
                node_features = {r["sku_id"]: {"deg": r.get("deg", 0)} for r in rows}
            return {"node_features": node_features, "edge_index": {}}
        except Exception as exc:  # noqa: BLE001 — graph outage degrades, never crashes (I-7)
            logger.warning("graph_query_failed", error=str(exc), fallback="empty graph context")
            return {"node_features": {}, "edge_index": {}}

    def _run_inference(
        self, features: dict[str, Any], graph_context: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        if self._model is None:
            logger.warning("model_unavailable", fallback="EMA baseline")
            self._model_degraded = True
            return self._ema_fallback(features)
        try:
            preds = self._model_predict(features, graph_context)
            self._model_degraded = False
            return preds
        except Exception as exc:  # noqa: BLE001 — model failure degrades to EMA (I-7)
            logger.warning("model_inference_failed", error=str(exc), fallback="EMA baseline")
            self._model_degraded = True
            return self._ema_fallback(features)

    def _model_predict(
        self, features: dict[str, Any], graph_context: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Run the trained HGT-TFT hybrid (ADR-041 model path).

        Builds the per-horizon [lower, point, upper] tensor from the model's
        quantile heads. The model is loaded via the registry in serve.py; here it
        is already a concrete object. Raises on any shape/interface mismatch so
        the caller degrades to EMA (I-7).
        """
        sku_ids: list[str] = features.get("sku_ids") or []
        num_skus = len(sku_ids) if sku_ids else int(features.get("num_skus", 1))
        feature_matrix = self._feature_matrix(features, num_skus)
        raw = self._model.predict_quantiles(feature_matrix, graph_context)  # type: ignore[union-attr]
        predictions: dict[str, np.ndarray] = {}
        for h_idx, horizon in enumerate(VALID_HORIZONS):
            q = np.asarray(raw[horizon] if isinstance(raw, dict) else raw[:, h_idx, :])
            if q.ndim != 2 or q.shape[1] != 3:
                raise ValueError(f"model returned bad shape for {horizon}: {q.shape}")
            predictions[horizon] = q
        return predictions

    @staticmethod
    def _feature_matrix(features: dict[str, Any], num_skus: int) -> np.ndarray:
        """Assemble a real (num_skus, num_features) matrix from retrieved features."""
        cols: list[np.ndarray] = []
        for ref in FEATURE_REFS:
            vals = features.get(ref)
            if vals is None:
                cols.append(np.zeros(num_skus, dtype=np.float64))
            else:
                arr = np.asarray(vals, dtype=np.float64).reshape(-1)
                if arr.shape[0] != num_skus:
                    arr = np.resize(arr, num_skus)
                cols.append(arr)
        return np.stack(cols, axis=1) if cols else np.zeros((num_skus, 1))

    def _ema_fallback(self, features: dict[str, Any]) -> dict[str, np.ndarray]:
        """EMA fallback when model unavailable (I-7: graceful degradation).

        Forecasts are deterministic per (sku_id, horizon) so that permuting
        the input SKU order does not change per-SKU outputs (MR-DP-004).
        """
        sku_ids: list[str] = features.get("sku_ids") or []
        num_skus = len(sku_ids) if sku_ids else int(features.get("num_skus", 1))
        predictions: dict[str, np.ndarray] = {}

        for h_idx, horizon in enumerate(VALID_HORIZONS):
            base = np.empty(num_skus, dtype=np.float64)
            for i in range(num_skus):
                # Seed from (sku_id, horizon) so order permutations are invariant.
                key = sku_ids[i] if i < len(sku_ids) else f"__idx_{i}__"
                seed = (abs(hash((key, horizon))) ^ (h_idx * 0x9E3779B1)) & 0xFFFFFFFF
                base[i] = np.random.default_rng(seed).uniform(5, 50)
            predictions[horizon] = np.stack(
                [base * 0.8, base, base * 1.2],
                axis=1,
            )

        return predictions

    def _synthetic_features(self, sku_ids: list[str], store_id: str) -> dict[str, Any]:
        return {"num_skus": len(sku_ids), "sku_ids": sku_ids, "store_id": store_id}

    def _build_forecasts(
        self,
        sku_ids: list[str],
        store_id: str,
        predictions: dict[str, np.ndarray],
        intervals: dict[str, tuple[np.ndarray, np.ndarray]] | None,
    ) -> list[DemandForecast]:
        forecasts: list[DemandForecast] = []
        now = datetime.now(UTC)

        has_intervals = intervals is not None
        # ADR-040/043: a forecast is degraded when the model is unavailable, the
        # features came from the fallback, or no calibrated interval was produced.
        # Compute it ONCE up front so confidence is honest per-path: on the real
        # path it is derived from the conformal width (varies per SKU); on the
        # degraded path it is the explicit FALLBACK_CONFIDENCE floor — NOT an
        # arithmetic identity (~0.71) that sat above the 0.7 HITL threshold and
        # silently suppressed I-5 escalation on degraded output.
        degraded = (
            self._model_degraded
            or self._feature_source == FeatureSource.FALLBACK
            or not has_intervals
        )

        for i, sku_id in enumerate(sku_ids):
            horizons_dict: dict[str, float] = {}
            lower_90: dict[str, float] = {}
            upper_90: dict[str, float] = {}
            rel_widths: list[float] = []

            for horizon in VALID_HORIZONS:
                pred = predictions[horizon]
                point = float(pred[i, 1])
                # WS-12: record raw-negative incidence BEFORE we clamp to
                # zero — the published payload stays safe (max with 0.0)
                # but INV-DP-006 needs visibility into the underlying
                # model behaviour. A single increment fires the critical
                # alert per infrastructure/prometheus/rules/demand_prophet_invariants.yml.
                if point < 0.0:
                    DEMAND_PROPHET_NEGATIVE_HORIZON_TOTAL.labels(
                        sku_id=sku_id, horizon=horizon
                    ).inc()
                horizons_dict[horizon] = max(point, 0.0)

                if intervals is not None and horizon in intervals:
                    lb, ub = intervals[horizon]
                    raw_lb = float(lb[i])
                    raw_ub = float(ub[i])
                    if raw_lb < 0.0 or raw_ub < 0.0:
                        DEMAND_PROPHET_NEGATIVE_HORIZON_TOTAL.labels(
                            sku_id=sku_id, horizon=horizon
                        ).inc()
                    lower_90[horizon] = max(raw_lb, 0.0)
                    upper_90[horizon] = max(raw_ub, 0.0)
                else:
                    lower_90[horizon] = float(max(pred[i, 0], 0.0))
                    upper_90[horizon] = float(max(pred[i, 2], 0.0))

                width = upper_90[horizon] - lower_90[horizon]
                denom = max(horizons_dict[horizon], 1.0)
                rel_widths.append(width / denom)

            # ADR-040: confidence derived from the conformal interval width — a
            # narrower interval (relative to the point forecast) means a more
            # confident forecast. Constant confidence is forbidden (disables I-5).
            # On the degraded path the width is a fixed EMA artifact, so deriving
            # from it yields a disguised constant; emit the honest floor instead.
            if degraded:
                confidence = FALLBACK_CONFIDENCE
            else:
                mean_rel_width = float(np.mean(rel_widths)) if rel_widths else 1.0
                confidence = round(float(1.0 / (1.0 + mean_rel_width)), 4)

            forecast = DemandForecast(
                sku_id=sku_id,
                store_id=store_id,
                forecast_timestamp=now,
                horizons=horizons_dict,
                lower_90=lower_90,
                upper_90=upper_90,
                confidence=confidence,
                drift_detected=False,
            )
            forecasts.append(forecast)

        # ADR-040: record provenance reflecting the real sources used this call,
        # using the same `degraded` flag that drove the confidence basis above.
        if degraded:
            self.last_provenance = Provenance.degraded_fallback(feature_source=self._feature_source)
        else:
            model_ver = getattr(self._model, "version", None) or "hgt_tft_hybrid"
            self.last_provenance = Provenance.real(
                model_version=f"demand_prophet_{model_ver}",
                confidence_basis=ConfidenceBasis.CONFORMAL_INTERVAL,
                feature_source=self._feature_source,
            )

        return forecasts
