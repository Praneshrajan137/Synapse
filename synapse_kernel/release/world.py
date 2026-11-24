"""The release world's declared parameters: items, suppliers, demand shape, and their sources.

A :class:`ReleaseWorld` is cell N's world (PREREG-1 section 6). Every parameter group carries a
:class:`Provenance` ("fitted" to FreshRetailNet-50K, "cited", or "chosen" with its reason, as
section 5 requires of freeze W), and the constructor refuses a world that breaks a rule: a demand
profile whose mean is not exactly one over its stated decimals, an item without a supplier, a
delivery hour outside the day, a shelf life or lead time that is not a positive whole number of
hours.

Pure: no RNG, no clock, no environment. Read from JSON (:func:`load_release_world`); written by the
fit script ``scripts/world/fit_release_world.py``.
"""

from __future__ import annotations

import dataclasses
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "HOURS_PER_DAY",
    "HOURS_PER_WEEK",
    "MEASURED_DAYS",
    "PROVENANCE_KINDS",
    "RELEASE_WORLD",
    "REQUIRED_PROVENANCE",
    "Item",
    "Provenance",
    "ReleaseWorld",
    "Supplier",
    "load_release_world",
    "world_from_document",
    "world_to_document",
]

HOURS_PER_DAY: Final[int] = 24
HOURS_PER_WEEK: Final[int] = 168
#: PREREG-1 section 1: one store, a warm-up, then 7 measured days.
MEASURED_DAYS: Final[int] = 7
PROVENANCE_KINDS: Final[frozenset[str]] = frozenset({"fitted", "cited", "chosen"})
#: The frozen release world, written by the fit script.
RELEASE_WORLD: Final[Path] = (
    Path(__file__).resolve().parent.parent / "worlds" / "release_world.json"
)


#: The parameter groups every world must give a provenance for (PREREG-1 section 5).
REQUIRED_PROVENANCE: Final[tuple[str, ...]] = (
    "items.rate_per_day",
    "items.profile",
    "items.shelf_life_hours",
    "items.price",
    "items.supplier",
    "profiles",
    "day_item_factors",
    "day_store_factors",
    "pair_share",
    "suppliers.delivery_hours",
    "suppliers.lead_time_hours",
    "item_count",
)


def _exact_mean(values: Sequence[float]) -> Fraction:
    return sum((Fraction(str(v)) for v in values), Fraction(0)) / len(values)


def _whole_hours(value: object, name: str, low: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ValueError(f"{name} = {value!r} must be a whole number of hours >= {low}")
    return value


@dataclasses.dataclass(frozen=True)
class Provenance:
    """Where a parameter came from: a :data:`PROVENANCE_KINDS` kind, and its source or reason."""

    kind: str
    source: str

    def __post_init__(self) -> None:
        if self.kind not in PROVENANCE_KINDS:
            raise ValueError(
                f"provenance kind {self.kind!r} is not one of {sorted(PROVENANCE_KINDS)}"
            )
        if not self.source.strip():
            raise ValueError("a provenance needs its source (cited/fitted) or its reason (chosen)")


@dataclasses.dataclass(frozen=True)
class Supplier:
    """A supplier: the hours of day its deliveries land, and the lead time from order to delivery.

    The order cut-off for a delivery at hour ``h`` is ``h - lead_time_hours`` (on an earlier day
    when negative); an order placed at a cut-off rides that delivery.
    """

    name: str
    delivery_hours: tuple[int, ...]
    lead_time_hours: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a supplier needs a name")
        hours = self.delivery_hours
        if not hours or list(hours) != sorted(set(hours)):
            raise ValueError(
                f"{self.name}: delivery hours must be distinct and sorted, got {hours}"
            )
        for hour in hours:
            if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour < HOURS_PER_DAY:
                raise ValueError(f"{self.name}: delivery hour {hour!r} is not an hour of the day")
        _whole_hours(self.lead_time_hours, f"{self.name}.lead_time_hours", 1)

    @property
    def cutoff_hours(self) -> tuple[int, ...]:
        """The hours of day at which this supplier takes orders, sorted."""
        return tuple(
            sorted((h - self.lead_time_hours) % HOURS_PER_DAY for h in self.delivery_hours)
        )

    @property
    def review_hours(self) -> int:
        """The longest gap between consecutive deliveries, in hours (a day if there is one)."""
        hours = self.delivery_hours
        gaps = [
            (hours[(k + 1) % len(hours)] - hours[k]) % HOURS_PER_DAY or HOURS_PER_DAY
            for k in range(len(hours))
        ]
        return max(gaps)


@dataclasses.dataclass(frozen=True)
class Item:
    """One item: its supplier, its mean demand, its demand profile and its shelf life at receipt."""

    name: str
    supplier: str
    rate_per_day: float
    profile: str
    shelf_life_hours: int
    price: float = 1.0

    def __post_init__(self) -> None:
        if not (math.isfinite(self.rate_per_day) and self.rate_per_day > 0.0):
            raise ValueError(
                f"{self.name}: rate_per_day = {self.rate_per_day!r} must be finite and > 0"
            )
        _whole_hours(self.shelf_life_hours, f"{self.name}.shelf_life_hours", 12)
        if not (math.isfinite(self.price) and self.price > 0.0):
            raise ValueError(f"{self.name}: price = {self.price!r} must be finite and > 0")


@dataclasses.dataclass(frozen=True)
class ReleaseWorld:
    """Cell N's world, every parameter declared (PREREG-1 sections 5 and 6)."""

    name: str
    items: tuple[Item, ...]
    suppliers: tuple[Supplier, ...]
    profiles: Mapping[str, tuple[float, ...]]
    day_item_factors: tuple[float, ...]
    day_store_factors: tuple[float, ...]
    pair_share: float
    provenance: Mapping[str, Provenance]
    attribution: str

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("a world needs items")
        names = [item.name for item in self.items]
        if len(set(names)) != len(names):
            raise ValueError("item names must be unique")
        supplier_names = {s.name for s in self.suppliers}
        if len(supplier_names) != len(self.suppliers):
            raise ValueError("supplier names must be unique")
        for item in self.items:
            if item.supplier not in supplier_names:
                raise ValueError(f"{item.name}: supplier {item.supplier!r} is not declared")
            if item.profile not in self.profiles:
                raise ValueError(f"{item.name}: profile {item.profile!r} is not declared")
        for name, values in self.profiles.items():
            if len(values) != HOURS_PER_WEEK:
                raise ValueError(f"profile {name!r} must hold {HOURS_PER_WEEK} values")
            if any(not (math.isfinite(v) and v > 0.0) for v in values):
                raise ValueError(f"profile {name!r} holds a value that is not finite and > 0")
            if _exact_mean(values) != 1:
                raise ValueError(f"profile {name!r} does not have mean exactly one")
        for label, table in (
            ("day_item_factors", self.day_item_factors),
            ("day_store_factors", self.day_store_factors),
        ):
            if not table or any(not (math.isfinite(v) and v > 0.0) for v in table):
                raise ValueError(f"{label} must be non-empty, finite and > 0")
            if _exact_mean(table) != 1:
                raise ValueError(f"{label} does not have mean exactly one")
        if not (math.isfinite(self.pair_share) and 0.0 <= self.pair_share < 1.0):
            raise ValueError(f"pair_share = {self.pair_share!r} must lie in [0, 1)")
        missing = [key for key in REQUIRED_PROVENANCE if key not in self.provenance]
        if missing:
            raise ValueError(f"no provenance for {missing}")
        if not self.attribution.strip():
            raise ValueError("a world fitted to a licensed dataset carries its attribution")

    # -- derived quantities -------------------------------------------------------------

    @property
    def supplier_by_name(self) -> dict[str, Supplier]:
        return {s.name: s for s in self.suppliers}

    @property
    def warmup_days(self) -> int:
        """PREREG-1 section 1: the largest shelf life plus the largest lead time, whole days."""
        longest_life = max(item.shelf_life_hours for item in self.items)
        longest_lead = max(s.lead_time_hours for s in self.suppliers)
        return math.ceil((longest_life + longest_lead) / HOURS_PER_DAY)

    @property
    def horizon_hours(self) -> int:
        return (self.warmup_days + MEASURED_DAYS) * HOURS_PER_DAY

    @property
    def measured_start_hour(self) -> int:
        return self.warmup_days * HOURS_PER_DAY


def world_to_document(world: ReleaseWorld) -> dict[str, Any]:
    """A world as JSON-ready data (floats survive ``json`` exactly)."""
    return {
        "schema": 1,
        "name": world.name,
        "attribution": world.attribution,
        "items": [dataclasses.asdict(item) for item in world.items],
        "suppliers": [
            {
                "name": s.name,
                "delivery_hours": list(s.delivery_hours),
                "lead_time_hours": s.lead_time_hours,
            }
            for s in world.suppliers
        ],
        "profiles": {name: list(values) for name, values in sorted(world.profiles.items())},
        "day_item_factors": list(world.day_item_factors),
        "day_store_factors": list(world.day_store_factors),
        "pair_share": world.pair_share,
        "provenance": {k: dataclasses.asdict(v) for k, v in sorted(world.provenance.items())},
    }


def world_from_document(document: Mapping[str, Any]) -> ReleaseWorld:
    """The inverse of :func:`world_to_document`; every rule re-checked on construction.

    Raises:
        ValueError: An unknown schema, or a value that breaks a world rule.
    """
    if document.get("schema") != 1:
        raise ValueError(f"release world: unknown schema {document.get('schema')!r}")
    return ReleaseWorld(
        name=str(document["name"]),
        items=tuple(
            Item(
                name=str(raw["name"]),
                supplier=str(raw["supplier"]),
                rate_per_day=float(raw["rate_per_day"]),
                profile=str(raw["profile"]),
                shelf_life_hours=int(raw["shelf_life_hours"]),
                price=float(raw.get("price", 1.0)),
            )
            for raw in document["items"]
        ),
        suppliers=tuple(
            Supplier(
                name=str(raw["name"]),
                delivery_hours=tuple(int(h) for h in raw["delivery_hours"]),
                lead_time_hours=int(raw["lead_time_hours"]),
            )
            for raw in document["suppliers"]
        ),
        profiles={
            str(k): tuple(float(v) for v in vals) for k, vals in document["profiles"].items()
        },
        day_item_factors=tuple(float(v) for v in document["day_item_factors"]),
        day_store_factors=tuple(float(v) for v in document["day_store_factors"]),
        pair_share=float(document["pair_share"]),
        provenance={str(k): Provenance(**v) for k, v in document["provenance"].items()},
        attribution=str(document["attribution"]),
    )


def load_release_world(path: Path = RELEASE_WORLD) -> ReleaseWorld:
    """Read a release world from JSON (default: the frozen release world)."""
    return world_from_document(json.loads(path.read_text(encoding="utf-8")))
