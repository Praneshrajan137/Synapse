"""The world structures' committed specification and its reader (ADR-055 D2.8).

Feature: decision-quality-proof, task 13.1 -- session 11's re-cut of R5.8-R5.14 (structure 1, the
shape of demand) and R5.21-R5.23 (structure 3, supply with lead times). The values live in
``policy.yaml`` section 5 (``world:``); this module is the only reader of that block.

**Nothing is defaulted.** Required keys resolve through :func:`require`, so a missing one raises
:class:`PolicyUnavailableError` naming it. Every rule is a refusal naming the key it refuses, and
an UNKNOWN key is refused too: contract 1 of ``policy.yaml`` says every value there is read, and a
key this reader skipped would be a committed value nothing uses -- a typo such as
``amplitude_scal`` would otherwise run its cell unscaled and say nothing.

**Refusal by construction.** The rules live in the dataclasses' ``__post_init__``, not in the
reader, so a world built by hand -- in a test, or by the next wave -- obeys exactly the rules a
world read from the file does. The reader adds only what a dataclass cannot know: the key path.

**Where exactness holds (R2.10).** A profile's mean is checked over
``fractions.Fraction(str(value))`` -- the decimal the YAML states -- where it is EXACTLY one.
:meth:`DemandShape.intensity` multiplies floats, so a week of it averages one over the reals and
within rounding in IEEE 754. :meth:`DemandShape.with_amplitude` rescales in exact rational
arithmetic and rounds once, and the result passes the same ``__post_init__``, so a scale whose
rounding broke the exact mean is refused rather than resolved.

**Pure.** No engine import, no RNG, no clock.
"""

from __future__ import annotations

import dataclasses
import itertools
import math
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Final

from digital_twin.simulation.policy import (
    POLICY_PATH,
    PolicyUnavailableError,
    load_policy,
    require,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping, Sequence
    from pathlib import Path

__all__ = [
    "DAYS_PER_WEEK",
    "HOURS_PER_DAY",
    "HOURS_PER_WEEK",
    "MINUTES_PER_DAY",
    "MINUTES_PER_HOUR",
    "START_WEEKDAY_RULE",
    "CellSpec",
    "DemandShape",
    "Promotion",
    "ResolvedWorld",
    "SupplierSpec",
    "SupplyStructure",
    "WorldSpec",
    "load_world",
    "start_weekday",
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
class CellSpec:
    """One cell of the grid: which structures are on, and the one lever it scales, if any.

    An absent scale is ``None`` and means the cell runs that structure as committed -- a declared
    meaning, not a substituted number. A scale on a structure that is off is refused: it would
    scale nothing and read as if it had.
    """

    structure_1: bool
    structure_3: bool
    amplitude_scale: float | None
    lead_time_scale: float | None

    def __post_init__(self) -> None:
        for name, flag in (("structure_1", self.structure_1), ("structure_3", self.structure_3)):
            if not isinstance(flag, bool):
                raise ValueError(f"{name} = {flag!r} must be a boolean")
        if self.amplitude_scale is not None:
            if not self.structure_1:
                raise ValueError("amplitude_scale is declared but structure_1 is off")
            if not (math.isfinite(self.amplitude_scale) and 0.0 < self.amplitude_scale <= 1.0):
                raise ValueError(f"amplitude_scale = {self.amplitude_scale!r} must lie in (0, 1]")
        if self.lead_time_scale is not None:
            if not self.structure_3:
                raise ValueError("lead_time_scale is declared but structure_3 is off")
            if not _is_positive_finite(self.lead_time_scale):
                raise ValueError(f"lead_time_scale = {self.lead_time_scale!r} must be > 0")


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


@dataclasses.dataclass(frozen=True)
class WorldSpec:
    """The committed world: both structures, the cell grid and the primary cell (ADR-055 D2.8).

    ``provenance`` records per block (``structure_1``, ``structure_3``, ``cells``) where its values
    came from. Session 11's are ``chosen:`` defaults pending research (operator decision Q3=c), so
    an artifact that runs a world can carry that flag instead of letting a default read as a
    calibration. Every cell is resolved once at construction, so a cell that cannot be resolved is
    refused when the world is loaded, not midway through the run that first reaches it.
    """

    structure_1: DemandShape
    structure_3: SupplyStructure
    cells: Mapping[str, CellSpec]
    primary_cell: str
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.cells:
            raise ValueError("cells must declare at least one cell")
        if _CELLS_PROVENANCE_KEY in self.cells:
            raise ValueError(f"no cell may be named {_CELLS_PROVENANCE_KEY!r} (reserved key)")
        primary = self.cells.get(self.primary_cell)
        if primary is None:
            known = ", ".join(sorted(self.cells))
            raise ValueError(f"primary_cell = {self.primary_cell!r} is no cell (known: {known})")
        if not (primary.structure_1 and primary.structure_3):
            raise ValueError(
                f"primary_cell = {self.primary_cell!r} must have both structures on; the primary "
                "cell is the world the headline is measured in"
            )
        for block in _PROVENANCE_BLOCKS:
            stated = self.provenance.get(block)
            if not isinstance(stated, str) or not stated.strip():
                raise ValueError(f"{block} carries no provenance; say where its values came from")
        for name in self.cells:
            self.resolve(name)

    def resolve(self, cell: str) -> ResolvedWorld:
        """The world ``cell`` runs: each structure on or ``None``, with the cell's scale applied.

        Raises:
            ValueError: If ``cell`` is not declared, or its scale cannot be applied -- naming it.
        """
        spec = self.cells.get(cell)
        if spec is None:
            known = ", ".join(sorted(self.cells))
            raise ValueError(f"world.cells declares no cell {cell!r} (known: {known})")
        demand = self.structure_1 if spec.structure_1 else None
        supply = self.structure_3 if spec.structure_3 else None
        try:
            if demand is not None and spec.amplitude_scale is not None:
                demand = demand.with_amplitude(spec.amplitude_scale)
            if supply is not None and spec.lead_time_scale is not None:
                supply = supply.with_lead_time_scale(spec.lead_time_scale)
        except ValueError as error:
            raise ValueError(
                f"world.cells.{cell} cannot be resolved (amplitude_scale="
                f"{spec.amplitude_scale!r}, lead_time_scale={spec.lead_time_scale!r}): {error}"
            ) from error
        return ResolvedWorld(cell=cell, demand=demand, supply=supply)


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------


def load_world(path: Path = POLICY_PATH) -> WorldSpec:
    """Read ``world:`` from the committed policy, or raise naming exactly what is wrong.

    Raises:
        PolicyUnavailableError: On a missing key, an unknown key, a value of the wrong kind, or a
            value breaking any rule of the dataclasses above -- always naming the key.
    """
    document = load_policy(path)
    world = _mapping(require(document, "world", path=path), "world", path)
    _only_keys(world, _WORLD_KEYS, "world", path)
    demand = _read_structure_1(document, path)
    supply = _read_structure_3(document, path)
    cells = _read_cells(document, path)
    primary = require(document, "world.primary_cell", path=path)
    if not isinstance(primary, str):
        raise _inadmissible(path, "world.primary_cell", f"{primary!r} is not a cell name")
    provenance = {
        block: _provenance(document, f"world.{block}", path) for block in _PROVENANCE_BLOCKS
    }
    try:
        return WorldSpec(
            structure_1=demand,
            structure_3=supply,
            cells=cells,
            primary_cell=primary,
            provenance=provenance,
        )
    except ValueError as error:
        raise _inadmissible(path, "world", error) from error


def _read_structure_1(document: dict[str, Any], path: Path) -> DemandShape:
    key = "world.structure_1"
    block = _mapping(require(document, key, path=path), key, path)
    _only_keys(block, _STRUCTURE_1_KEYS, key, path)
    rule = require(document, f"{key}.start_weekday_rule", path=path)
    if rule != START_WEEKDAY_RULE:
        reason = f"{rule!r} is not implemented; only {START_WEEKDAY_RULE!r} is"
        raise _inadmissible(path, f"{key}.start_weekday_rule", reason)
    promotions: list[Promotion] = []
    raw_promotions = require(document, f"{key}.promotions", path=path)
    for index, raw in enumerate(_sequence(raw_promotions, f"{key}.promotions", path)):
        entry_key = f"{key}.promotions[{index}]"
        entry = _mapping(raw, entry_key, path)
        _only_keys(entry, _PROMOTION_KEYS, entry_key, path)
        weekday = _whole(_field(entry, "weekday", entry_key, path), f"{entry_key}.weekday", path)
        start = _whole(
            _field(entry, "start_hour", entry_key, path), f"{entry_key}.start_hour", path
        )
        hours = _whole(_field(entry, "hours", entry_key, path), f"{entry_key}.hours", path)
        multiplier = _real(
            _field(entry, "multiplier", entry_key, path), f"{entry_key}.multiplier", path
        )
        try:
            promotions.append(
                Promotion(weekday=weekday, start_hour=start, hours=hours, multiplier=multiplier)
            )
        except ValueError as error:
            raise _inadmissible(path, entry_key, error) from error
    hourly = _reals(require(document, f"{key}.hourly", path=path), f"{key}.hourly", path)
    weekdays = _reals(require(document, f"{key}.weekday", path=path), f"{key}.weekday", path)
    try:
        return DemandShape(hourly=hourly, weekday=weekdays, promotions=tuple(promotions))
    except ValueError as error:
        raise _inadmissible(path, key, error) from error


def _read_structure_3(document: dict[str, Any], path: Path) -> SupplyStructure:
    key = "world.structure_3"
    block = _mapping(require(document, key, path=path), key, path)
    _only_keys(block, _STRUCTURE_3_KEYS, key, path)
    raw_suppliers = require(document, f"{key}.suppliers", path=path)
    suppliers: dict[str, SupplierSpec] = {}
    for supplier, raw in _mapping(raw_suppliers, f"{key}.suppliers", path).items():
        entry_key = f"{key}.suppliers.{supplier}"
        entry = _mapping(raw, entry_key, path)
        _only_keys(entry, _SUPPLIER_KEYS, entry_key, path)
        mean = _real(
            _field(entry, "mean_lead_time_min", entry_key, path),
            f"{entry_key}.mean_lead_time_min",
            path,
        )
        log_sd = _real(_field(entry, "log_sd", entry_key, path), f"{entry_key}.log_sd", path)
        try:
            suppliers[supplier] = SupplierSpec(mean_lead_time_min=mean, log_sd=log_sd)
        except ValueError as error:
            raise _inadmissible(path, entry_key, error) from error
    raw_map = require(document, f"{key}.sku_supplier", path=path)
    sku_supplier: dict[str, str] = {}
    for sku, supplier in _mapping(raw_map, f"{key}.sku_supplier", path).items():
        if not isinstance(supplier, str):
            raise _inadmissible(path, f"{key}.sku_supplier.{sku}", f"{supplier!r} is not an id")
        sku_supplier[sku] = supplier

    def scalar(name: str) -> float:
        return _real(require(document, f"{key}.{name}", path=path), f"{key}.{name}", path)

    try:
        return SupplyStructure(
            suppliers=suppliers,
            sku_supplier=sku_supplier,
            daily_autocorrelation=scalar("daily_autocorrelation"),
            demand_coupling=scalar("demand_coupling"),
            coupling_floor=scalar("coupling_floor"),
            min_lead_time_min=scalar("min_lead_time_min"),
        )
    except ValueError as error:
        raise _inadmissible(path, key, error) from error


def _read_cells(document: dict[str, Any], path: Path) -> dict[str, CellSpec]:
    key = "world.cells"
    cells: dict[str, CellSpec] = {}
    for name, raw in _mapping(require(document, key, path=path), key, path).items():
        if name == _CELLS_PROVENANCE_KEY:
            continue
        cell_key = f"{key}.{name}"
        entry = _mapping(raw, cell_key, path)
        _only_keys(entry, _CELL_KEYS, cell_key, path)
        flags = {
            flag: _flag(_field(entry, flag, cell_key, path), f"{cell_key}.{flag}", path)
            for flag in ("structure_1", "structure_3")
        }
        try:
            cells[name] = CellSpec(
                structure_1=flags["structure_1"],
                structure_3=flags["structure_3"],
                amplitude_scale=_optional_real(entry, "amplitude_scale", cell_key, path),
                lead_time_scale=_optional_real(entry, "lead_time_scale", cell_key, path),
            )
        except ValueError as error:
            raise _inadmissible(path, cell_key, error) from error
    return cells


def _inadmissible(path: Path, key: str, reason: object) -> PolicyUnavailableError:
    return PolicyUnavailableError(
        f"{path.as_posix()} declares an inadmissible {key}: {reason}. Refused, not repaired: a "
        "clamped or defaulted world is a world nobody committed"
    )


def _field(entry: dict[str, Any], name: str, key: str, path: Path) -> Any:
    """``entry[name]``, or raise naming ``key.name`` -- ``require`` for entries inside a list."""
    if name not in entry:
        raise PolicyUnavailableError(
            f"{path.as_posix()} declares no value at {key}.{name}. This is NOT defaulted: a "
            "default would substitute an unreviewed number for a committed one"
        )
    return entry[name]


def _mapping(raw: object, key: str, path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict) or not all(isinstance(name, str) for name in raw):
        raise _inadmissible(path, key, f"a {type(raw).__name__}, not a mapping keyed by names")
    return raw


def _sequence(raw: object, key: str, path: Path) -> list[Any]:
    if not isinstance(raw, list):
        raise _inadmissible(path, key, f"a {type(raw).__name__}, not a list")
    return raw


def _real(raw: object, key: str, path: Path) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float) or not math.isfinite(raw):
        raise _inadmissible(path, key, f"{raw!r} is not a finite real number")
    return float(raw)


def _reals(raw: object, key: str, path: Path) -> tuple[float, ...]:
    values = _sequence(raw, key, path)
    return tuple(_real(value, f"{key}[{index}]", path) for index, value in enumerate(values))


def _whole(raw: object, key: str, path: Path) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise _inadmissible(path, key, f"{raw!r} is not an integer")
    return raw


def _flag(raw: object, key: str, path: Path) -> bool:
    if not isinstance(raw, bool):
        raise _inadmissible(path, key, f"{raw!r} is not a boolean (write true or false)")
    return raw


def _optional_real(entry: dict[str, Any], name: str, key: str, path: Path) -> float | None:
    """A declared scale, or ``None`` when the cell declares none (the cell runs unscaled)."""
    if name not in entry:
        return None
    return _real(entry[name], f"{key}.{name}", path)


def _provenance(document: dict[str, Any], key: str, path: Path) -> str:
    stated = require(document, f"{key}.provenance", path=path)
    if not isinstance(stated, str) or not stated.strip():
        raise _inadmissible(path, f"{key}.provenance", "provenance must be a non-empty string")
    return stated


def _only_keys(block: dict[str, Any], allowed: frozenset[str], key: str, path: Path) -> None:
    unknown = sorted(set(block) - allowed)
    if unknown:
        raise _inadmissible(
            path,
            key,
            f"unknown key(s) {', '.join(unknown)} -- a value no reader reads is a committed "
            "number that nothing runs",
        )
