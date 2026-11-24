"""A small declared world for the release engine's tests: twelve items, two suppliers, one shape.

Not the release world (that is fitted and frozen): a fixture whose every number is chosen for the
tests, so a test reads the engine's behaviour, not the fit's.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from synapse_kernel.release.world import (
    REQUIRED_PROVENANCE,
    Item,
    Provenance,
    ReleaseWorld,
    Supplier,
)

#: A day's shape with mean exactly one over its stated decimals (sums to 24).
DAY_SHAPE: tuple[float, ...] = (
    (0.2,) * 6 + (1.2,) * 4 + (1.6,) * 4 + (1.4,) * 4 + (1.2,) * 4 + (0.6,) * 2
)

SUPPLIERS: tuple[Supplier, ...] = (
    Supplier("produce", (6,), 8),
    Supplier("hub", (6, 15), 4),
)


def small_world(items: int = 12, **overrides: Any) -> ReleaseWorld:
    """``items`` items alternating between the two suppliers, shelf lives from 1 to 5 days."""
    rates = np.round(np.exp(np.linspace(0.5, 3.0, items)), 3)
    fields: dict[str, Any] = {
        "name": "fixture",
        "items": tuple(
            Item(
                name=f"item{k:03d}",
                supplier=SUPPLIERS[k % 2].name,
                rate_per_day=float(rates[k]),
                profile="day",
                shelf_life_hours=24 * (1 + k % 5),
            )
            for k in range(items)
        ),
        "suppliers": SUPPLIERS,
        "profiles": {"day": DAY_SHAPE * 7},
        "day_item_factors": (0.8, 1.0, 1.2),
        "day_store_factors": (0.9, 1.1),
        "pair_share": 0.17,
        "provenance": {key: Provenance("chosen", "test fixture") for key in REQUIRED_PROVENANCE},
        "attribution": "test fixture: no dataset",
    }
    fields.update(overrides)
    return ReleaseWorld(**fields)


class OrderUpTo:
    """A plain base stock for tests: up to ``factor`` times a day and a half of mean demand."""

    def __init__(self, world: ReleaseWorld, factor: float) -> None:
        from synapse_kernel.release.scenario import demand_means

        daily = demand_means(world).sum(axis=0) / 7.0
        self.target = np.ceil(factor * 1.5 * daily).astype(np.int64)
        self.calls = 0

    def start(self, replicates: int) -> None:
        self.calls = 0

    def decide(self, obs: Any) -> np.ndarray:
        self.calls += 1
        position = obs.on_hand.sum(axis=-1) + obs.open_qty.sum(axis=-1)
        out = np.zeros(position.shape, dtype=np.int64)
        out[:, obs.deciding] = np.maximum(0, self.target - position)[:, obs.deciding]
        return out


class Never:
    """Orders nothing, ever."""

    def start(self, replicates: int) -> None:
        return None

    def decide(self, obs: Any) -> np.ndarray:
        return np.zeros(obs.on_hand.shape[:2], dtype=np.int64)
