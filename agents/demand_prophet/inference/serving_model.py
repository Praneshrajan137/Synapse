"""Serving adapter: bridge a trained HGT-TFT checkpoint to the pipeline contract.

The inference pipeline calls ``model.predict_quantiles(feature_matrix, graph_context)``
and expects ``dict[horizon -> (N, 3)]`` arrays (lower/point/upper). The trained
``DemandProphetHybrid.forward`` instead takes a graph + lists of static/temporal
tensors. :class:`DemandProphetServingModel` is the anti-corruption seam between
the two: it owns the loaded torch module and exposes the array interface the
pipeline speaks, so neither side leaks the other's representation.

torch / torch_geometric are imported lazily inside methods — importing this module
never requires the ML stack, so the pipeline-contract tests and the C39 AST gate
run on any runner. When no real checkpoint is available, :func:`load_serving_model`
returns ``None`` and the pipeline takes its honest I-7 fallback.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Canonical horizon order — matches models/tft.py::VALID_HORIZONS but defined here
# so importing the serving adapter never pulls in torch (keeps the pipeline-contract
# tests and the C39 AST gate torch-free).
VALID_HORIZONS: tuple[str, ...] = ("15min", "1h", "6h", "24h", "7d")


class DemandProphetServingModel:
    """Wrap a trained HGT-TFT module behind ``predict_quantiles`` (ADR-041)."""

    def __init__(self, torch_model: Any, *, version: str, num_static: int = 8) -> None:
        self._model = torch_model
        self.version = version
        self._num_static = num_static
        import contextlib  # noqa: PLC0415

        with contextlib.suppress(AttributeError, RuntimeError):
            torch_model.eval()  # put the module in eval mode if it is a torch nn.Module

    def predict_quantiles(
        self, feature_matrix: np.ndarray, graph_context: dict[str, Any]
    ) -> dict[str, np.ndarray]:
        """Run the trained model; return per-horizon (N, 3) quantile arrays.

        ``feature_matrix`` is (N, F) of real features from the FeatureProvider.
        We expand it into the model's static/temporal input contract (the trained
        weights consume those channels) and run a single eval forward pass.
        """
        import torch  # noqa: PLC0415

        from agents.demand_prophet.training.dataset import build_graph  # noqa: PLC0415

        fm = np.asarray(feature_matrix, dtype=np.float32)
        if fm.ndim == 1:
            fm = fm.reshape(1, -1)
        n, f = fm.shape

        # Static channels: pad/resize the feature vector per SKU to num_static.
        static_np = np.stack([np.resize(fm[i], self._num_static) for i in range(n)])
        static_inputs = [
            torch.tensor(static_np[:, s], dtype=torch.float32).reshape(-1, 1)
            for s in range(self._num_static)
        ]
        # Temporal channels: broadcast each feature into a short constant sequence
        # (serving has point features, not the full history the trainer windowed;
        # the model's temporal VSN still consumes them). 9 channels, seq 20.
        seq, n_chan = 20, 9
        temporal_inputs = [
            torch.tensor(
                np.repeat(fm[:, c % f].reshape(n, 1), seq, axis=1), dtype=torch.float32
            ).reshape(n, seq, 1)
            for c in range(n_chan)
        ]
        graph = graph_context.get("hetero_data") if graph_context else None
        if graph is None:
            graph = build_graph(n)

        with torch.no_grad():
            outputs = self._model(graph, static_inputs, temporal_inputs)

        result: dict[str, np.ndarray] = {}
        for h in VALID_HORIZONS:
            arr = outputs[h].detach().cpu().numpy()
            # Ensure ascending [lower, point, upper] ordering for safety.
            arr = np.sort(arr, axis=1)
            result[h] = arr.astype(np.float64)
        return result


def load_serving_model(
    registry: Any,
    *,
    city: str = "bengaluru",
    base_name: str = "demand_prophet_hgt_tft",
) -> DemandProphetServingModel | None:
    """Resolve + wrap the trained model from the registry; None if degraded (I-7)."""
    if registry is None:
        return None
    loaded = registry.load(base_name, city=city)
    if not getattr(loaded, "is_real", False) or loaded.model is None:
        logger.warning("serving_model_degraded", name=base_name, city=city)
        return None
    logger.info("serving_model_loaded", name=loaded.name, version=loaded.version)
    return DemandProphetServingModel(loaded.model, version=loaded.version)


__all__ = ["DemandProphetServingModel", "load_serving_model"]
