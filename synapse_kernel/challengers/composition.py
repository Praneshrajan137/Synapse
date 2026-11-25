"""SYNAPSE on the release world: the incumbent first, a challenger only where it has earned trust.

PREREG-1 (decisions D-2 and D-4) and truth session 6's gate (items 1, 3, 7 and 16) fix the shape:

1. **The lane** (the Freshness Guardian's job, :mod:`synapse_kernel.challengers.shelf`): per
   replicate, I2-L once a shelf life shorter than declared has been seen, I2-P until then and for
   good once a declared one has. Its order ``q_I`` is SYNAPSE's incumbent and the guard's anchor.
2. **The regime**, per item: *supply* while its supplier has an order older than the declared lead
   time; else *surge* while the store's surge alarm stands and the item is attributed to it; else
   *calm*. Regimes are assessed only when a lane-P entry is trusted (lane L's surge and supply
   entries stay with the incumbent: no exploratory cell shows their effect).
3. **The trust map** sends ``(lane, regime)`` to one decider; an entry it does not name stays with
   the incumbent. Entries: ``L/calm``, ``P/calm``, ``P/surge``, ``P/supply``.
4. **The guard** (D-4(b)): every quantity is clipped to ``[ceil(q_I / 2), 2 q_I]``.
5. **The record**: per decision, each item's lane, regime, decider, ``q_I``, the decider's ``q_c``
   and the order placed, digested in order, with counts per decider of item-decisions and clipped
   ones (the clipped share is reported per cell and decider).

Every decider keeps its own memory and sees every observation, whether or not it decides, so
trusting it changes only where its orders are used, never what it knows. For the ablations (gate
item 16), ``lane_rule = False`` holds lane P throughout (the composition without the Freshness
Guardian); a challenger is ablated by removing its entry from the map.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import numpy.typing as npt

from synapse_kernel.challengers.shelf import LaneIncumbent
from synapse_kernel.challengers.supply import SupplyResponse
from synapse_kernel.challengers.surge import SurgeResponse
from synapse_kernel.release.guard import guard

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from synapse_kernel.release.engine import ReleasePolicy
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["CALM_DECIDERS", "ENTRIES", "REGIMES", "Composition"]

I64 = npt.NDArray[np.int64]
Bools = npt.NDArray[np.bool_]

#: The trust map's entries, in the order the trust rule tests them (gate item 7).
ENTRIES: Final[tuple[str, ...]] = ("L/calm", "P/calm", "P/surge", "P/supply")
#: Regime codes in the record.
REGIMES: Final[tuple[str, ...]] = ("calm", "surge", "supply")
#: Who may decide a calm entry.
CALM_DECIDERS: Final[tuple[str, ...]] = ("sensing", "sentinel_as_built", "sentinel_world")
#: Who may decide each entry (pairs, so no module holds mutable state).
_ALLOWED: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("L/calm", CALM_DECIDERS),
    ("P/calm", CALM_DECIDERS),
    ("P/surge", ("surge_today", "surge_ahead")),
    ("P/supply", ("supply",)),
)


class Composition:
    """The composition, built from the declared world, the frozen tables and its fitted file."""

    name = "synapse"

    def __init__(
        self,
        world: ReleaseWorld,
        tables: Mapping[str, IncumbentTables],
        params: Mapping[str, Any],
        build: Callable[
            [str, ReleaseWorld, Mapping[str, IncumbentTables], Mapping[str, Any]], ReleasePolicy
        ],
    ) -> None:
        normal, short = tables["I2-P"], tables["I2-L"]
        trust = {str(k): str(v) for k, v in dict(params.get("trust", {})).items()}
        allowed = dict(_ALLOWED)
        for entry, decider in trust.items():
            if entry not in allowed:
                raise ValueError(f"no such entry {entry!r}; the entries are {ENTRIES}")
            if decider not in allowed[entry]:
                raise ValueError(f"{decider!r} cannot decide {entry}; allowed {allowed[entry]}")
        self.trust = trust
        self.lane_rule = bool(params.get("lane_rule", True))
        self.base = LaneIncumbent(world, normal, short)
        self.assessing = any(entry.startswith("P/") for entry in trust)
        self.surge: SurgeResponse | None = None
        self.supply: SupplyResponse | None = None
        if self.assessing:
            plan = trust.get("P/surge", "surge_today").removeprefix("surge_")
            kappa = params.get(f"surge_{plan}_kappa")
            self.surge = SurgeResponse(
                world,
                normal,
                short,
                float(params["surge_threshold"]),
                None if kappa is None else np.asarray(kappa, dtype=np.float64),
                plan,
            )
            supply_kappa = params.get("supply_kappa")
            self.supply = SupplyResponse(
                world,
                normal,
                short,
                None if supply_kappa is None else np.asarray(supply_kappa, dtype=np.float64),
            )
        self.calm: dict[str, ReleasePolicy] = {
            entry: build(trust[entry], world, tables, params)
            for entry in ("L/calm", "P/calm")
            if entry in trust
        }
        self.deciders = ("incumbent", *sorted(set(trust.values())))
        self.items = len(world.items)
        self._reset(0)

    def _reset(self, replicates: int) -> None:
        self.digests = [hashlib.sha256() for _ in range(replicates)]
        shape = (replicates, len(self.deciders))
        self.decided = np.zeros(shape, dtype=np.int64)
        self.clipped = np.zeros(shape, dtype=np.int64)
        self.regime_counts = np.zeros((replicates, len(REGIMES)), dtype=np.int64)

    def start(self, replicates: int) -> None:
        self.base.start(replicates)
        if self.surge is not None and self.supply is not None:
            self.surge.start(replicates)
            self.supply.start(replicates)
        for decider in self.calm.values():
            decider.start(replicates)
        self._reset(replicates)

    def decide(self, obs: StoreObservation) -> I64:
        self.base.observe(obs)
        normal = np.asarray(self.base.normal.decide(obs), dtype=np.int64)
        r = normal.shape[0]
        if self.lane_rule:
            short: Bools = self.base.is_short.copy()
            brief = np.asarray(self.base.short.decide(obs), dtype=np.int64)
            incumbent: I64 = np.where(short[:, None], brief, normal)
        else:  # the ablation without the Freshness Guardian: I2-P throughout
            short = np.zeros(r, dtype=bool)
            incumbent = normal
        regime = np.zeros((r, self.items), dtype=np.int8)
        surge_factor = supply_factor = None
        if self.surge is not None and self.supply is not None:
            surged, surge_factor = self.surge.assess(obs)
            flagged, supply_factor = self.supply.assess(obs)
            regime = np.where(flagged, 2, np.where(surged, 1, 0)).astype(np.int8)
        calm_orders = {entry: np.asarray(p.decide(obs)) for entry, p in self.calm.items()}
        wanted = incumbent.copy()
        who = np.zeros((r, self.items), dtype=np.int8)
        for entry, decider in self.trust.items():
            lane, regime_name = entry.split("/")
            in_lane = short if lane == "L" else ~short
            mask = in_lane[:, None] & (regime == REGIMES.index(regime_name)) & obs.deciding[None, :]
            if not bool(mask.any()):
                continue
            if entry in calm_orders:
                orders = calm_orders[entry]
            elif regime_name == "surge" and self.surge is not None and surge_factor is not None:
                orders = self.surge.orders(obs, surge_factor)
            elif self.supply is not None and supply_factor is not None:
                orders = self.supply.orders(obs, supply_factor)
            else:  # pragma: no cover - the constructor builds what the map needs
                raise RuntimeError(f"no decider built for {entry}")
            wanted = np.where(mask, orders, wanted)
            who = np.where(mask, self.deciders.index(decider), who).astype(np.int8)
        placed: I64 = guard(wanted, incumbent)
        self._record(obs, short, regime, who, incumbent, wanted, placed)
        return placed

    def _record(
        self,
        obs: StoreObservation,
        short: Bools,
        regime: npt.NDArray[np.int8],
        who: npt.NDArray[np.int8],
        incumbent: I64,
        wanted: I64,
        placed: I64,
    ) -> None:
        deciding = obs.deciding[None, :]
        for d in range(len(self.deciders)):
            mine = (who == d) & deciding
            self.decided[:, d] += np.count_nonzero(mine, axis=1)
            self.clipped[:, d] += np.count_nonzero(mine & (placed != wanted), axis=1)
        for g in range(len(REGIMES)):
            self.regime_counts[:, g] += np.count_nonzero((regime == g) & deciding, axis=1)
        for k, digest in enumerate(self.digests):
            digest.update(bytes([int(short[k])]))
            for array in (regime[k], who[k], incumbent[k], wanted[k], placed[k]):
                digest.update(np.ascontiguousarray(array, dtype=np.int64).tobytes())

    def report(self) -> dict[str, Any]:
        """Per replicate: the record's digest and the counts by decider and by regime."""
        return {
            "deciders": list(self.deciders),
            "record_digest": [d.hexdigest() for d in self.digests],
            "decided": self.decided.tolist(),
            "clipped": self.clipped.tolist(),
            "regimes": self.regime_counts.tolist(),
            "regimes_assessed": self.assessing,
            "lane_rule": self.lane_rule,
        }
