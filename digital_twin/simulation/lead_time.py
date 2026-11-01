"""Structure 3's lead-time path: one deterministic function of seed, supplier and time.

Feature: decision-quality-proof, task 13.1 (R5.21-R5.23; ADR-055 D2.8; findings 66 and 67).

**Why here and not in ``_restock``.** Finding 66: every measured arm restocks through
``add_stock`` with the engine's own ``_restock`` loop switched off (``uplift/harness.py``
``_build_twin``), so a lead time placed in ``_restock`` delays nothing any arm does. The delay
lives where arms order -- ``SupplyChainSimulation.place_order`` -- and is read from this path.

**Why a function of time alone.** The path depends on the engine's seed, the supplier and the
placement time, and NEVER on which orders were placed. Every arm at one seed therefore faces the
identical supply world, and a hindsight arm can read it in advance.

The model, per supplier ``j`` (parameters: ``policy.yaml`` ``world.structure_3``):

* daily log-scale AR(1): ``z_0 ~ N(0, 1)``, ``z_d = phi z_{d-1} + sqrt(1 - phi^2) eps_d``, drawn
  lazily in day order from ``j``'s own generator, so no value depends on query order;
* ``L0(j, d) = mean_j exp(sd_j z_d - sd_j^2 / 2)`` -- lognormal with mean exactly ``mean_j``;
* ``L(j, h) = max(min_lead, L0(j, h // 24) max(floor, 1 + kappa (I(h) - 1)))`` for whole hour
  ``h``, ``I(h)`` being demand intensity at the start of hour ``h`` (1.0 with structure 1 off);
* ``A(j, t, m) = sup over s <= t of s + m L(j, piece(s))``, ``m`` the engine's shock multiplier.

**Non-crossing, and its domain.** ``A`` is a running maximum of a quantity increasing in ``s``
within each piece, so it is non-decreasing in ``t``: at a fixed ``m`` an order placed later never
arrives earlier, and every arrival is at least ``m * min_lead`` after its placement. Lowering
``m`` mid-run can let a later order overtake an earlier one, as a supplier that speeds up does.
That is not repaired, because repairing it would make arrivals depend on order history -- and so
differ between arms.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from digital_twin.simulation.world import HOURS_PER_DAY, MINUTES_PER_HOUR

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

    from digital_twin.simulation.world import DemandShape, SupplyStructure

__all__ = ["LeadTimePath"]


class LeadTimePath:
    """Every supplier's arrival function for one engine (task 13.1).

    Args:
        supply: Structure 3's parameters.
        demand: Structure 1's shape, or ``None`` when structure 1 is off (intensity 1.0).
        start_weekday: The weekday hour 0 falls on (0 = Monday); read only when ``demand`` is set.
        seeds: One non-negative integer per declared supplier. The engine draws them once, from
            its ``restock`` substream, in sorted supplier-id order.

    Raises:
        ValueError: If ``seeds`` does not name exactly the declared suppliers.
    """

    def __init__(
        self,
        *,
        supply: SupplyStructure,
        demand: DemandShape | None,
        start_weekday: int,
        seeds: Mapping[str, int],
    ) -> None:
        declared = sorted(supply.suppliers)
        if sorted(seeds) != declared:
            raise ValueError(
                f"seeds name {sorted(seeds)} but the declared suppliers are {declared}; the "
                "contract is one independent generator per supplier"
            )
        self._supply = supply
        self._demand = demand
        self._start_weekday = start_weekday
        self._phi = supply.daily_autocorrelation
        self._innovation = math.sqrt(1.0 - self._phi * self._phi)
        self._rngs = {
            supplier: np.random.default_rng(int(seeds[supplier])) for supplier in declared
        }
        self._shocks: dict[str, list[float]] = {supplier: [] for supplier in declared}
        self._pieces: dict[str, list[float]] = {supplier: [] for supplier in declared}
        self._prefix: dict[tuple[str, float], list[float]] = {}

    @property
    def suppliers(self) -> tuple[str, ...]:
        """Declared supplier ids, sorted: the order the engine draws their seeds in."""
        return tuple(self._rngs)

    def daily_shock(self, supplier: str, day: int) -> float:
        """``z_d``: ``supplier``'s standardised log-scale shock on day ``day`` (day 0 = hour 0)."""
        shocks = self._require(supplier, self._shocks)
        if day < 0:
            raise ValueError(f"day must be >= 0, got {day}")
        generator = self._rngs[supplier]
        while len(shocks) <= day:
            innovation = float(generator.standard_normal())
            if shocks:
                shocks.append(self._phi * shocks[-1] + self._innovation * innovation)
            else:
                shocks.append(innovation)
        return shocks[day]

    def base_lead_time(self, supplier: str, day: int) -> float:
        """``L0(j, d) = mean_j exp(sd_j z_d - sd_j^2 / 2)``, minutes; its mean is ``mean_j``."""
        shock = self.daily_shock(supplier, day)
        spec = self._supply.suppliers[supplier]
        sd = spec.log_sd
        return spec.mean_lead_time_min * math.exp(sd * shock - sd * sd / 2.0)

    def piece_lead_time(self, supplier: str, hour_index: int) -> float:
        """``L(j, h)``: the lead time of an order placed during whole hour ``hour_index``.

        Generated in hour order whatever is asked, so the value is a function of the index alone.
        """
        pieces = self._require(supplier, self._pieces)
        if hour_index < 0:
            raise ValueError(f"hour_index must be >= 0, got {hour_index}")
        supply = self._supply
        while len(pieces) <= hour_index:
            hour = len(pieces)
            intensity = (
                1.0
                if self._demand is None
                else self._demand.hour_intensity(hour, self._start_weekday)
            )
            coupling = max(supply.coupling_floor, 1.0 + supply.demand_coupling * (intensity - 1.0))
            base = self.base_lead_time(supplier, hour // HOURS_PER_DAY)
            pieces.append(max(supply.min_lead_time_min, base * coupling))
        return pieces[hour_index]

    def arrival_time(self, supplier: str, t_min: float, mult: float) -> float:
        """``A(j, t, m)``: when an order placed with ``supplier`` at ``t_min`` arrives.

        Past pieces contribute their END plus their lead time; the current piece contributes
        ``t_min`` plus its own. The running maximum is what makes arrivals non-crossing.
        """
        if not (math.isfinite(t_min) and t_min >= 0.0):
            raise ValueError(f"a placement time must be finite and >= 0, got {t_min!r}")
        if not (math.isfinite(mult) and mult > 0.0):
            raise ValueError(f"a lead-time multiplier must be finite and > 0, got {mult!r}")
        hour = int(t_min // MINUTES_PER_HOUR)
        current = t_min + mult * self.piece_lead_time(supplier, hour)
        return max(self._past_maximum(supplier, hour, mult), current)

    def _past_maximum(self, supplier: str, hour: int, mult: float) -> float:
        """``max over h < hour of (end of piece h) + m L(j, h)``; ``-inf`` before any piece."""
        prefix = self._prefix.setdefault((supplier, mult), [-math.inf])
        while len(prefix) <= hour:
            finished = len(prefix) - 1
            end = float((finished + 1) * MINUTES_PER_HOUR)
            prefix.append(max(prefix[-1], end + mult * self.piece_lead_time(supplier, finished)))
        return prefix[hour]

    def _require(self, supplier: str, table: dict[str, list[float]]) -> list[float]:
        values = table.get(supplier)
        if values is None:
            raise ValueError(
                f"{supplier!r} is not a declared supplier (declared: {', '.join(self._rngs)})"
            )
        return values
