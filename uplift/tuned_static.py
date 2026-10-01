"""Arm E's policy class: ``Par_Level_Reorder``'s rule with one ``(s, S)`` per supplier group.

Feature: decision-quality-proof, leaf 13.7a (task 13.7's re-scope: arm E re-derived per world
cell). ``uplift/tuning.py::tune_group_levels`` chooses the levels; this module holds what it
chooses (:class:`GroupLevels`), which SKUs share a pair (:func:`sku_groups`), and the policy that
acts on them (:class:`GroupParLevelReorder`).

**Why per group.** Arm E must be the best STATIC policy for the world under measurement, because
checkpoint B-prime judges the information ceiling ``E - D`` and a weak E inflates it -- the unsafe
direction, a false "room to win". With structure 3 on, suppliers' lead times differ, so one
``(s, S)`` shared by every SKU over-stocks the fast supplier's SKUs or starves the slow one's, and
is not the best static policy. So each supplier's SKUs share one pair, tuned for that supplier.
With structure 3 off there is one group, :data:`ALL_SKUS_GROUP`, and the policy decides exactly as
``Par_Level_Reorder`` does -- Property 81 asserts that equivalence rather than assuming it.

**Why the rule is not new.** Arm E differs from the incumbent arm B only in where its integers come
from and how many there are. The decision rule is ``Par_Level_Reorder``'s, applied per group, so no
new policy needs review and the tuning gap ``B - E`` measures tuning alone.

Pure: no engine import, no RNG draw, no clock.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from uplift.interfaces import PolicyAction
from uplift.tuning import GridPoint, TuningUnavailableError

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from collections.abc import Iterable, Mapping

    from digital_twin.simulation.world import ResolvedWorld
    from uplift.interfaces import Observation

__all__ = [
    "ALL_SKUS_GROUP",
    "TUNED_STATIC_ARM",
    "GroupLevels",
    "GroupParLevelReorder",
    "sku_groups",
]

#: The single group every SKU belongs to when structure 3 is off: no supplier differs, so one pair.
ALL_SKUS_GROUP: Final[str] = "all"

#: Arm E's label -- the same string ``uplift/regret.py::ARM_LABELS`` names it by.
TUNED_STATIC_ARM: Final[str] = "tuned_static"


@dataclasses.dataclass(frozen=True)
class GroupLevels:
    """The tuned ``(s, S)`` of every group: the recorded result of the search.

    Holds a sorted, read-only COPY of the mapping it is given. A frozen dataclass is shallow, so
    without the copy a caller mutating its own dict afterwards could move the levels a selection
    reported; with it, the record is as immutable as it claims, and hashable.
    """

    levels: Mapping[str, GridPoint]

    def __post_init__(self) -> None:
        if not self.levels:
            raise TuningUnavailableError("GroupLevels names no group, so it tunes nothing")
        for group, point in self.levels.items():
            if not isinstance(group, str) or not group.strip():
                raise TuningUnavailableError(f"group name {group!r} is not a non-blank string")
            if not isinstance(point, GridPoint):
                raise TuningUnavailableError(f"group {group!r} carries {point!r}, not a GridPoint")
        object.__setattr__(self, "levels", MappingProxyType(dict(sorted(self.levels.items()))))

    def __hash__(self) -> int:
        return hash(tuple((group, point.s, point.S) for group, point in self.levels.items()))

    def for_group(self, group: str) -> GridPoint:
        """The pair tuned for ``group``.

        Raises:
            KeyError: If ``group`` was not tuned -- naming it and every group that was.
        """
        try:
            return self.levels[group]
        except KeyError:
            known = ", ".join(self.levels)
            raise KeyError(f"no tuned levels for group {group!r} (tuned: {known})") from None

    def as_dict(self) -> dict[str, dict[str, int]]:
        """``{group: {"S": S, "s": s}}`` -- canonical: JSON-safe, groups and keys sorted."""
        return {group: {"S": point.S, "s": point.s} for group, point in self.levels.items()}


def sku_groups(world: ResolvedWorld | None, skus: Iterable[str]) -> dict[str, str]:
    """Which group each SKU's levels come from: its supplier with structure 3 on, else ``"all"``.

    Sorted by SKU. Refuses rather than guessing, in :class:`TuningUnavailableError` -- the refusal
    ``uplift/regret.py`` already turns into an ``unavailable`` measurement:

    Raises:
        TuningUnavailableError: If ``skus`` is empty (an arm over no SKUs decides nothing), or if
            structure 3 is on and a SKU has no supplier in ``world.structure_3.sku_supplier`` --
            the engine refuses to place an order for one, so no level for it could ever act.
    """
    names = sorted(set(skus))
    if not names:
        raise TuningUnavailableError("no SKUs to group: an arm over no SKU decides nothing")
    supply = None if world is None else world.supply
    if supply is None:
        return dict.fromkeys(names, ALL_SKUS_GROUP)
    unmapped = [sku for sku in names if sku not in supply.sku_supplier]
    if unmapped:
        raise TuningUnavailableError(
            f"SKU(s) {', '.join(unmapped)} have no supplier in world.structure_3.sku_supplier, so "
            "no supplier group can be tuned for them"
        )
    return {sku: supply.sku_supplier[sku] for sku in names}


class GroupParLevelReorder:
    """``Par_Level_Reorder``'s rule with one ``(s, S)`` per group; implements ``DecisionPolicy``.

    For each observed SKU: ``position = on_hand + on_order`` (absent from ``on_order`` means
    nothing in transit); ``(s, S) = levels.for_group(sku_group[sku])``; order ``S - position``
    when ``position <= s``, else ``0.0``. The same expression ``Par_Level_Reorder.decide``
    evaluates, so on one group the two decide identically, to the bit.

    Args:
        levels: The tuned pair of every group.
        sku_group: Which group each SKU belongs to (see :func:`sku_groups`).
        seed: The deterministic construction seed every arm is built with. The rule draws nothing;
            the seed is held so the arm shares the suite's construction contract (R1.9).

    Raises:
        TuningUnavailableError: If ``sku_group`` maps no SKU.
        KeyError: If ``sku_group`` names a group ``levels`` has no pair for -- at construction,
            not at the first decision of a CI-only run.
    """

    #: Stable policy identifier: arm E's label.
    name: str = TUNED_STATIC_ARM

    def __init__(self, levels: GroupLevels, sku_group: Mapping[str, str], *, seed: int) -> None:
        if not sku_group:
            raise TuningUnavailableError("sku_group maps no SKU, so the arm would decide nothing")
        untuned = sorted({group for group in sku_group.values() if group not in levels.levels})
        if untuned:
            raise KeyError(
                f"sku_group names group(s) {', '.join(untuned)} with no tuned levels "
                f"(tuned: {', '.join(levels.levels)})"
            )
        self._levels = levels
        self._sku_group: Mapping[str, str] = MappingProxyType(dict(sku_group))
        self._seed = seed

    @property
    def levels(self) -> GroupLevels:
        """The tuned pair of every group."""
        return self._levels

    @property
    def sku_group(self) -> Mapping[str, str]:
        """Which group each SKU belongs to (read-only)."""
        return self._sku_group

    @property
    def seed(self) -> int:
        """The deterministic construction seed."""
        return self._seed

    def decide(self, obs: Observation) -> PolicyAction:
        """Per-SKU reorder quantities under ``Par_Level_Reorder``'s rule, at each group's pair.

        Raises:
            KeyError: If an observed SKU has no group -- the arm was built for another SKU set,
                and deciding it with some other SKU's levels would be a guess.
        """
        reorder_quantities: dict[str, float] = {}
        for sku, level in obs.inventory.items():
            group = self._sku_group.get(sku)
            if group is None:
                raise KeyError(f"observed SKU {sku!r} has no group in this arm's sku_group")
            point = self._levels.for_group(group)
            position = level + obs.on_order.get(sku, 0.0)
            if position <= point.s:
                reorder_quantities[sku] = float(point.S - position)
            else:
                reorder_quantities[sku] = 0.0
        return PolicyAction(reorder_quantities=reorder_quantities)
