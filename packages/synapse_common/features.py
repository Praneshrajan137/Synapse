"""SYNAPSE feature anti-corruption layer (ADR-041).

``FeatureProvider`` is the single published-language path between an agent's
inference pipeline and the Feast/Redis online store. Agents NEVER touch Feast
directly. The provider has exactly one job beyond a thin wrapper: it makes the
fallback **honest**. When the store is reachable it returns real features
(``source=FEAST``); when it is unreachable it returns a *deterministic* synthetic
fallback with ``degraded=True`` — and the caller is contractually obliged to
propagate that flag into the output :class:`~synapse_common.provenance.Provenance`.

Determinism of the fallback matters: features are seeded per entity key so that
permuting the input row order does not change a row's features (the metamorphic
MR-*-004 invariants depend on this). Per-city Redis DB index and the Mumbai
``monsoon_intensity`` column (E-S6-03, E-S6-09) are honored.

Reachability failures use Full-Jitter retry (ADR-016) before degrading.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

from synapse_common.provenance import FeatureSource

logger = structlog.get_logger(__name__)

# Mumbai feature views MUST carry monsoon_intensity; Bengaluru does not (E-S6-09).
_MONSOON_CITIES = frozenset({"mumbai"})


@dataclass(frozen=True)
class FeatureResult:
    """Outcome of a feature fetch — values plus honest provenance signal."""

    values: dict[str, Any]
    source: FeatureSource
    degraded: bool
    entity_keys: tuple[str, ...] = field(default_factory=tuple)

    @property
    def num_entities(self) -> int:
        return len(self.entity_keys)


class FeatureProvider:
    """Anti-corruption layer over the Feast online store (ADR-041)."""

    def __init__(
        self,
        feast_client: Any = None,
        *,
        city: str = "bengaluru",
        max_retries: int = 2,
    ) -> None:
        self._feast = feast_client
        self._city = city
        self._max_retries = max_retries

    @property
    def city(self) -> str:
        return self._city

    def get(
        self,
        entity_keys: list[str],
        feature_refs: list[str],
        *,
        store_id: str | None = None,
    ) -> FeatureResult:
        """Return features for ``entity_keys``. Never raises — degrades instead (I-7).

        Args:
            entity_keys: e.g. SKU ids; one feature vector is produced per key.
            feature_refs: Feast feature references (``view:feature``). When the
                store is unreachable these name the keys synthesised in fallback.
            store_id: optional store context used to seed the deterministic
                fallback so the same (sku, store) yields stable features.
        """
        if self._feast is None:
            return self._fallback(entity_keys, feature_refs, store_id, reason="no_feast_client")

        try:
            values = self._fetch_from_feast(entity_keys, feature_refs)
        except Exception as exc:  # noqa: BLE001 — any store failure degrades, never crashes (I-7)
            logger.warning(
                "feast_unreachable",
                city=self._city,
                error=str(exc),
                fallback="deterministic synthetic features",
            )
            return self._fallback(entity_keys, feature_refs, store_id, reason=str(exc))

        logger.debug("feast_features_retrieved", city=self._city, num_entities=len(entity_keys))
        return FeatureResult(
            values=values,
            source=FeatureSource.FEAST,
            degraded=False,
            entity_keys=tuple(entity_keys),
        )

    def _fetch_from_feast(self, entity_keys: list[str], feature_refs: list[str]) -> dict[str, Any]:
        """Call Feast with bounded Full-Jitter retry (ADR-016)."""
        from synapse_common.retry import full_jitter_delay

        entity_rows = [{"sku_id": k} for k in entity_keys]
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                online = self._feast.get_online_features(
                    features=feature_refs, entity_rows=entity_rows
                )
                # Feast returns an object with .to_dict(); duck-type it.
                values: dict[str, Any] = online.to_dict()
                if self._city in _MONSOON_CITIES and "monsoon_intensity" not in values:
                    raise ValueError("E-S6-09: Mumbai features missing monsoon_intensity")
                return values
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self._max_retries - 1:
                    import time as _time

                    _time.sleep(full_jitter_delay(0.05, attempt, cap=0.5))
        assert last_exc is not None
        raise last_exc

    def _fallback(
        self,
        entity_keys: list[str],
        feature_refs: list[str],
        store_id: str | None,
        *,
        reason: str,
    ) -> FeatureResult:
        """Deterministic synthetic features, seeded per (entity, store) (E-S6-01)."""
        logger.warning(
            "feature_provider_degraded",
            city=self._city,
            reason=reason,
            num_entities=len(entity_keys),
        )
        values: dict[str, list[Any]] = {ref: [] for ref in feature_refs}
        values["sku_id"] = list(entity_keys)
        for key in entity_keys:
            for ref in feature_refs:
                seed_src = f"{key}|{store_id or ''}|{ref}|{self._city}".encode()
                seed = int.from_bytes(hashlib.sha256(seed_src).digest()[:8], "big")
                rng = np.random.default_rng(seed)
                values[ref].append(float(rng.uniform(0.0, 1.0)))
        if self._city in _MONSOON_CITIES and "monsoon_intensity" not in values:
            values["monsoon_intensity"] = [0.5 for _ in entity_keys]
        return FeatureResult(
            values=values,
            source=FeatureSource.FALLBACK,
            degraded=True,
            entity_keys=tuple(entity_keys),
        )


__all__ = ["FeatureProvider", "FeatureResult"]
