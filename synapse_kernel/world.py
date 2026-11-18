"""The world a twin runs: demand shape (structure 1) and supply with lead times (structure 3).

Ported from ``digital_twin/simulation/world.py`` (truth program session 3): the dataclasses and
their rules are the legacy ones, verbatim, so a world built here obeys exactly the rules a legacy
world does. What is left out is the YAML reader and the experiment grid (``CellSpec``,
``WorldSpec``): the kernel reads an already-resolved world from JSON (:func:`world_from_document`),
so it needs no YAML parser, and :data:`LEGACY_PRIMARY` is E5's primary cell exported from the
legacy reader (``scripts/kernel/export_legacy_world.py``; ``tests/kernel`` pins the two equal).

**Pure.** No engine import, no RNG, no clock, no environment.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping, Sequence

__all__ = [
    "DAYS_PER_WEEK",
    "HOURS_PER_DAY",
    "HOURS_PER_WEEK",
    "MINUTES_PER_DAY",
    "MINUTES_PER_HOUR",
    "START_WEEKDAY_RULE",
    "LEGACY_PRIMARY",
    "DemandShape",
    "Promotion",
    "ResolvedWorld",
    "SupplierSpec",
    "SupplyStructure",
    "load_world",
    "start_weekday",
    "world_from_document",
    "world_to_document",
]

MINUTES_PER_HOUR: Final[int] = 60
HOURS_PER_DAY: Final[int] = 24
DAYS_PER_WEEK: Final[int] = 7
MINUTES_PER_DAY: Final[int] = MINUTES_PER_HOUR * HOURS_PER_DAY
HOURS_PER_WEEK: Final[int] = HOURS_PER_DAY * DAYS_PER_WEEK

#: The only start-weekday rule implemented. The reader refuses any other: a second rule would move
#: every seeded run to another weekday -- and so change every seeded demand path -- without one
#: line of physics changing.
START_WEEKDAY_RULE: Final[str] = "seed_mod_7"

#: ``world.cells`` reserves this key for the block's own provenance, so no cell may be named it.
_CELLS_PROVENANCE_KEY: Final[str] = "provenance"

_WORLD_KEYS: Final[frozenset[str]] = frozenset(
    {"structure_1", "structure_3", "cells", "primary_cell"}
)
_STRUCTURE_1_KEYS: Final[frozenset[str]] = frozenset(
    {"provenance", "hourly", "weekday", "promotions", "start_weekday_rule"}
)
_PROMOTION_KEYS: Final[frozenset[str]] = frozenset({"weekday", "start_hour", "hours", "multiplier"})
_STRUCTURE_3_KEYS: Final[frozenset[str]] = frozenset(
    {
        "provenance",
        "suppliers",
        "sku_supplier",
        "daily_autocorrelation",
        "demand_coupling",
        "coupling_floor",
        "min_lead_time_min",
    }
)
_SUPPLIER_KEYS: Final[frozenset[str]] = frozenset({"mean_lead_time_min", "log_sd"})
_CELL_KEYS: Final[frozenset[str]] = frozenset(
    {"structure_1", "structure_3", "amplitude_scale", "lead_time_scale"}
)
_PROVENANCE_BLOCKS: Final[tuple[str, ...]] = ("structure_1", "structure_3", "cells")

#: Hours :meth:`DemandShape.next_arrival` walks before refusing (about 114 simulated years). Every
#: intensity is > 0 by rule, so every walk ends; a mass needing more hours than this is refused,
#: naming the state, rather than walked on without bound.
_MAX_INTENSITY_PIECES: Final[int] = 10**6


def start_weekday(seed: int | None) -> int:
    """The weekday hour 0 of a run falls on (0 = Monday), under ``seed_mod_7``; 0 when unseeded."""
    if seed is None:
        return 0
    return int(seed) % DAYS_PER_WEEK


def _hour_index(t_min: float) -> int:
    """Whole hours elapsed at ``t_min``, by floor division, so no boundary is rounded across."""
    if not math.isfinite(t_min):
        raise ValueError(f"a simulated time must be finite, got {t_min!r}")
    return int(t_min // MINUTES_PER_HOUR)


def _is_positive_finite(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


def _exact_mean(values: Sequence[float]) -> Fraction:
    """The mean over the decimals the values state -- ``Fraction(str(v))`` -- with no rounding."""
    return sum((Fraction(str(value)) for value in values), Fraction(0)) / len(values)


def _require_int_in(value: object, name: str, low: int, high: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} = {value!r} must be an integer in [{low}, {high}]")


# ---------------------------------------------------------------------------
# Structure 1 -- when demand arrives
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Promotion:
    """A weekly window in which demand intensity is multiplied (R5.12).

    Opens at ``start_hour`` on ``weekday`` (0 = Monday) and lasts ``hours`` whole hours,
    wrapping past midnight and from Sunday into Monday; overlapping windows multiply. A promotion
    ADDS volume (``multiplier > 1`` by rule), so it is the one part of structure 1 that is not
    volume-neutral. The two profiles are.
    """

    weekday: int
    start_hour: int
    hours: int
    multiplier: float

    def __post_init__(self) -> None:
        _require_int_in(self.weekday, "weekday", 0, DAYS_PER_WEEK - 1)
        _require_int_in(self.start_hour, "start_hour", 0, HOURS_PER_DAY - 1)
        # Bounded by the week it repeats in: a longer window would overlap itself, and under the
        # modular rule in `covers` it would silently saturate at one full week.
        _require_int_in(self.hours, "hours", 1, HOURS_PER_WEEK)
        if not (math.isfinite(self.multiplier) and self.multiplier > 1.0):
            raise ValueError(f"multiplier = {self.multiplier!r} must be finite and > 1")

    def covers(self, hour_of_week: int) -> bool:
        """Whether the window is open during ``hour_of_week`` (0 = Monday 00:00-01:00)."""
        opens = self.weekday * HOURS_PER_DAY + self.start_hour
        return (hour_of_week - opens) % HOURS_PER_WEEK < self.hours


@dataclasses.dataclass(frozen=True)
class DemandShape:
    """Structure 1: when demand arrives, as a multiplier on the flat rate (R5.11, R5.12).

    ``hourly`` holds 24 values (index 0 = 00:00-01:00) and ``weekday`` 7 (index 0 = Monday). Each
    is finite, strictly positive and has mean EXACTLY one over its stated decimals, so each profile
    moves demand between the hours or days of its own period and adds none. Over any whole week
    the two together integrate to exactly the flat week; ``promotions`` are what add volume.
    """

    hourly: tuple[float, ...]
    weekday: tuple[float, ...]
    promotions: tuple[Promotion, ...]

    def __post_init__(self) -> None:
        profiles = (
            ("hourly", self.hourly, HOURS_PER_DAY),
            ("weekday", self.weekday, DAYS_PER_WEEK),
        )
        for name, values, period in profiles:
            if len(values) != period:
                raise ValueError(f"{name} must hold exactly {period} values, got {len(values)}")
            for index, value in enumerate(values):
                if not _is_positive_finite(value):
                    raise ValueError(
                        f"{name}[{index}] = {value!r} is not a finite, strictly positive intensity"
                    )
            mean = _exact_mean(values)
            if mean != 1:
                raise ValueError(
                    f"{name} has mean {mean} over its stated decimals, not exactly one, so it "
                    "would change demand's volume and not only its shape"
                )

    def promotion_factor(self, hour_of_week: int) -> float:
        """The product of the multipliers of every promotion open during ``hour_of_week``."""
        factor = 1.0
        for promotion in self.promotions:
            if promotion.covers(hour_of_week):
                factor *= promotion.multiplier
        return factor

    def hour_intensity(self, hour_index: int, start_weekday: int) -> float:
        """Intensity throughout whole hour ``hour_index`` of a run whose hour 0 is 00:00 on
        ``start_weekday`` (0 = Monday)."""
        if isinstance(start_weekday, bool) or not 0 <= start_weekday < DAYS_PER_WEEK:
            raise ValueError(f"start_weekday = {start_weekday!r} must lie in [0, 6]")
        hour_of_day = hour_index % HOURS_PER_DAY
        day_of_week = (start_weekday + hour_index // HOURS_PER_DAY) % DAYS_PER_WEEK
        factor = self.promotion_factor(day_of_week * HOURS_PER_DAY + hour_of_day)
        return self.hourly[hour_of_day] * self.weekday[day_of_week] * factor

    def intensity(self, t_min: float, start_weekday: int) -> float:
        """``hourly[h] * weekday[(start_weekday + day) % 7] * promotion factor`` at ``t_min``.

        ``h = floor(t_min / 60) % 24`` and ``day = floor(t_min / 1440)``, by floor division.
        Piecewise constant per whole hour, which is what makes :meth:`expected_units` a finite sum.
        """
        return self.hour_intensity(_hour_index(t_min), start_weekday)

    @staticmethod
    def hour_boundaries(t0_min: float, t1_min: float) -> tuple[float, ...]:
        """``t0``, every whole-hour instant strictly inside ``(t0, t1)``, then ``t1``."""
        if not (math.isfinite(t0_min) and math.isfinite(t1_min)) or t1_min < t0_min:
            raise ValueError(f"need finite t0 <= t1, got t0={t0_min!r}, t1={t1_min!r}")
        inner = (
            float(hour * MINUTES_PER_HOUR)
            for hour in range(_hour_index(t0_min) + 1, _hour_index(t1_min) + 1)
        )
        return (t0_min, *(instant for instant in inner if instant < t1_min), t1_min)

    def expected_units(
        self, t0_min: float, t1_min: float, start_weekday: int, rate_per_min: float
    ) -> float:
        """Expected demand over ``[t0, t1)`` at a flat ``rate_per_min`` shaped by this profile.

        The integral of a piecewise-constant function is a finite sum, so this is exact over the
        reals; in floats each piece is one rounded product and the pieces meet in ``math.fsum``.
        """
        if not (math.isfinite(rate_per_min) and rate_per_min >= 0.0):
            raise ValueError(f"rate_per_min = {rate_per_min!r} must be finite and >= 0")
        pieces = [
            self.intensity(left, start_weekday) * (right - left)
            for left, right in itertools.pairwise(self.hour_boundaries(t0_min, t1_min))
        ]
        return rate_per_min * math.fsum(pieces)

    def next_arrival(
        self, t_min: float, mass: float, start_weekday: int, rate_per_min: float
    ) -> float:
        """The instant at which :meth:`expected_units` from ``t_min`` reaches ``mass``.

        Time-rescaling (Lewis & Shedler 1979, NRLQ 26(3):403-413, section 1(i)): for ``mass`` a
        standard exponential, this is the first arrival after ``t_min`` of the Poisson process of
        intensity ``rate_per_min`` shaped by this profile; ``rate_per_min`` already carries any
        demand multiplier. The cumulative intensity is piecewise linear, so the inverse is exact
        over the reals: whole hours are walked forward, each spending its mass, and the hour the
        mass runs out in is solved in closed form.

        In floats the result is clamped to the hour that solved it, so rounding never carries an
        arrival into an hour whose intensity it was not solved with; the clamp is also what keeps
        the result non-decreasing in ``mass`` in IEEE 754, not only over the reals. Property 93
        states the precision and the domain it holds over.

        Raises:
            ValueError: If ``t_min`` is not finite, ``mass`` is not finite and >= 0,
                ``rate_per_min`` is not finite and > 0, or ``start_weekday`` is outside [0, 6].
            RuntimeError: If ``_MAX_INTENSITY_PIECES`` hours do not spend ``mass``; refused,
                naming the state, rather than walked on.
        """
        if not (math.isfinite(mass) and mass >= 0.0):
            raise ValueError(f"mass = {mass!r} must be finite and >= 0")
        if not _is_positive_finite(rate_per_min):
            raise ValueError(f"rate_per_min = {rate_per_min!r} must be finite and > 0")
        hour = _hour_index(t_min)
        left = t_min
        remaining = mass
        for _ in range(_MAX_INTENSITY_PIECES):
            right = float((hour + 1) * MINUTES_PER_HOUR)
            rate_here = rate_per_min * self.hour_intensity(hour, start_weekday)
            piece = rate_here * (right - left)
            if remaining <= piece:
                return min(left + remaining / rate_here, right)
            remaining -= piece
            left = right
            hour += 1
        raise RuntimeError(
            f"next_arrival walked {_MAX_INTENSITY_PIECES} hours from t_min={t_min!r} "
            f"(start_weekday={start_weekday!r}, rate_per_min={rate_per_min!r}) and "
            f"{remaining!r} of mass={mass!r} is unspent at t={left!r}; refused, not walked on"
        )

    def with_amplitude(self, scale: float) -> DemandShape:
        """Both profiles moved toward flat: every value ``p`` becomes ``1 + k (p - 1)``.

        The mean stays exactly one, because the mean of ``1 + k (p - 1)`` is ``1 + k (mean - 1)``,
        and every value stays positive for ``0 < k <= 1``, because it equals ``(1 - k) + k p``.
        Both are facts about the rationals, so the rescale runs over the stated decimals and is
        rounded ONCE; ``__post_init__`` then re-checks the rounded result, and a scale whose
        rounding broke the exact mean is refused. Promotions are unchanged.
        """
        if not (math.isfinite(scale) and 0.0 < scale <= 1.0):
            raise ValueError(f"amplitude_scale = {scale!r} must lie in (0, 1]")
        k = Fraction(str(scale))

        def rescale(values: tuple[float, ...]) -> tuple[float, ...]:
            return tuple(float(1 + k * (Fraction(str(value)) - 1)) for value in values)

        return DemandShape(
            hourly=rescale(self.hourly),
            weekday=rescale(self.weekday),
            promotions=self.promotions,
        )


# ---------------------------------------------------------------------------
# Structure 3 -- how long an order takes
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SupplierSpec:
    """One supplier's daily lead time: lognormal with mean ``mean_lead_time_min`` (minutes) and
    log-scale standard deviation ``log_sd``."""

    mean_lead_time_min: float
    log_sd: float

    def __post_init__(self) -> None:
        if not _is_positive_finite(self.mean_lead_time_min):
            raise ValueError(
                f"mean_lead_time_min = {self.mean_lead_time_min!r} must be finite and > 0"
            )
        if not (math.isfinite(self.log_sd) and self.log_sd >= 0.0):
            raise ValueError(f"log_sd = {self.log_sd!r} must be finite and >= 0")


@dataclasses.dataclass(frozen=True)
class SupplyStructure:
    """Structure 3: who supplies each SKU, and how long a delivery takes (R5.21-R5.23).

    ``daily_autocorrelation`` is the AR(1) coefficient of each supplier's daily log-scale shock;
    ``demand_coupling`` (kappa) stretches a lead time in busy hours by ``1 + kappa (I - 1)``,
    floored at ``coupling_floor``; no piece is shorter than ``min_lead_time_min``. The mappings
    are read-only by convention -- a frozen dataclass is shallow.
    """

    suppliers: Mapping[str, SupplierSpec]
    sku_supplier: Mapping[str, str]
    daily_autocorrelation: float
    demand_coupling: float
    coupling_floor: float
    min_lead_time_min: float

    def __post_init__(self) -> None:
        if not self.suppliers:
            raise ValueError("suppliers must declare at least one supplier")
        if not self.sku_supplier:
            raise ValueError("sku_supplier must map at least one SKU")
        for sku, supplier in self.sku_supplier.items():
            if supplier not in self.suppliers:
                raise ValueError(
                    f"sku_supplier.{sku} names {supplier!r}, which is not a declared supplier"
                )
        phi = self.daily_autocorrelation
        if not (math.isfinite(phi) and 0.0 <= phi < 1.0):
            raise ValueError(f"daily_autocorrelation = {phi!r} must lie in [0, 1)")
        if not (math.isfinite(self.demand_coupling) and self.demand_coupling >= 0.0):
            raise ValueError(f"demand_coupling = {self.demand_coupling!r} must be finite and >= 0")
        if not (math.isfinite(self.coupling_floor) and 0.0 < self.coupling_floor <= 1.0):
            raise ValueError(f"coupling_floor = {self.coupling_floor!r} must lie in (0, 1]")
        if not _is_positive_finite(self.min_lead_time_min):
            raise ValueError(
                f"min_lead_time_min = {self.min_lead_time_min!r} must be finite and > 0"
            )
        for supplier, spec in self.suppliers.items():
            if not spec.mean_lead_time_min > self.min_lead_time_min:
                raise ValueError(
                    f"suppliers.{supplier}.mean_lead_time_min = {spec.mean_lead_time_min!r} "
                    f"must exceed min_lead_time_min = {self.min_lead_time_min!r}"
                )

    def with_lead_time_scale(self, scale: float) -> SupplyStructure:
        """Every supplier's mean lead time multiplied by ``scale`` (> 0); everything else kept."""
        if not _is_positive_finite(scale):
            raise ValueError(f"lead_time_scale = {scale!r} must be finite and > 0")
        scaled = {
            supplier: dataclasses.replace(spec, mean_lead_time_min=spec.mean_lead_time_min * scale)
            for supplier, spec in self.suppliers.items()
        }
        return dataclasses.replace(self, suppliers=scaled)


# ---------------------------------------------------------------------------
# The experiment grid
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ResolvedWorld:
    """One cell resolved: the demand shape and the supply structure an engine runs.

    ``demand is None`` means structure 1 is off and ``supply is None`` that structure 3 is off.
    With both ``None`` the engine is byte-identical to an engine given no world at all.
    """

    cell: str
    demand: DemandShape | None
    supply: SupplyStructure | None

    @property
    def structure_1_on(self) -> bool:
        return self.demand is not None

    @property
    def structure_3_on(self) -> bool:
        return self.supply is not None


#: E5's primary cell, exported from the legacy reader (both structures on).
LEGACY_PRIMARY: Final[Path] = Path(__file__).resolve().parent / "worlds" / "legacy_primary.json"


def world_to_document(world: ResolvedWorld) -> dict[str, Any]:
    """A resolved world as JSON-ready data; floats survive ``json`` exactly (shortest repr)."""
    demand = world.demand
    supply = world.supply
    return {
        "schema": 1,
        "cell": world.cell,
        "demand": None
        if demand is None
        else {
            "hourly": list(demand.hourly),
            "weekday": list(demand.weekday),
            "promotions": [dataclasses.asdict(p) for p in demand.promotions],
        },
        "supply": None
        if supply is None
        else {
            "suppliers": {k: dataclasses.asdict(v) for k, v in supply.suppliers.items()},
            "sku_supplier": dict(supply.sku_supplier),
            "daily_autocorrelation": supply.daily_autocorrelation,
            "demand_coupling": supply.demand_coupling,
            "coupling_floor": supply.coupling_floor,
            "min_lead_time_min": supply.min_lead_time_min,
        },
    }


def world_from_document(document: Mapping[str, Any]) -> ResolvedWorld:
    """The inverse of :func:`world_to_document`; every legacy rule re-checked on construction.

    Raises:
        ValueError: The document is not schema 1, or a value breaks a world rule.
    """
    if document.get("schema") != 1:
        raise ValueError(f"world document: unknown schema {document.get('schema')!r}")
    raw_demand = document.get("demand")
    raw_supply = document.get("supply")
    demand = None
    if raw_demand is not None:
        demand = DemandShape(
            hourly=tuple(float(v) for v in raw_demand["hourly"]),
            weekday=tuple(float(v) for v in raw_demand["weekday"]),
            promotions=tuple(Promotion(**p) for p in raw_demand["promotions"]),
        )
    supply = None
    if raw_supply is not None:
        supply = SupplyStructure(
            suppliers={k: SupplierSpec(**v) for k, v in raw_supply["suppliers"].items()},
            sku_supplier=dict(raw_supply["sku_supplier"]),
            daily_autocorrelation=float(raw_supply["daily_autocorrelation"]),
            demand_coupling=float(raw_supply["demand_coupling"]),
            coupling_floor=float(raw_supply["coupling_floor"]),
            min_lead_time_min=float(raw_supply["min_lead_time_min"]),
        )
    return ResolvedWorld(cell=str(document["cell"]), demand=demand, supply=supply)


def load_world(path: Path = LEGACY_PRIMARY) -> ResolvedWorld:
    """Read a resolved world from a JSON document (default: E5's primary cell)."""
    return world_from_document(json.loads(path.read_text(encoding="utf-8")))
