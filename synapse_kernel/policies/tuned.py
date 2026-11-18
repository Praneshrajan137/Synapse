"""The legacy tuned rule, arm E: one ``(s, S)`` per supplier group (``uplift/tuned_static.py``).

Order ``S - position`` when ``position <= s``, else nothing, with ``position`` the observed (whole)
on-hand units plus the units on order. One pair serves every SKU of a supplier, which against
skewed items is a strawman (truth finding F-29; PLAN section 5.2): the release's incumbent is tuned
per item and part of the day, and sealed before any result. This port exists for parity.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Final

from synapse_kernel.observation import Observation, PolicyAction

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from synapse_kernel.world import ResolvedWorld

#: The group every SKU shares when the world declares no suppliers (``uplift.tuned_static``).
ALL_SKUS_GROUP: Final[str] = "all"


@dataclasses.dataclass(frozen=True)
class Levels:
    """One ``(s, S)`` pair: reorder point and order-up-to level, whole units, ``0 <= s < S``."""

    s: int
    S: int

    def __post_init__(self) -> None:
        if self.s < 0 or not self.s < self.S:
            raise ValueError(f"levels need 0 <= s < S, got s={self.s}, S={self.S}")


def sku_groups(world: ResolvedWorld | None, skus: Iterable[str]) -> dict[str, str]:
    """Each SKU's group: its supplier with structure 3 on, else :data:`ALL_SKUS_GROUP`.

    Raises:
        ValueError: No SKU, or a SKU with no supplier while structure 3 is on.
    """
    names = sorted(set(skus))
    if not names:
        raise ValueError("no SKUs to group: an arm over no SKU decides nothing")
    supply = None if world is None else world.supply
    if supply is None:
        return dict.fromkeys(names, ALL_SKUS_GROUP)
    unmapped = [sku for sku in names if sku not in supply.sku_supplier]
    if unmapped:
        raise ValueError(f"SKU(s) {', '.join(unmapped)} have no supplier in the world")
    return {sku: supply.sku_supplier[sku] for sku in names}


class GroupParLevelReorder:
    """``(s, S)`` per group (``uplift.tuned_static.GroupParLevelReorder.decide``)."""

    def __init__(self, levels: Mapping[str, Levels], sku_group: Mapping[str, str]) -> None:
        untuned = sorted({group for group in sku_group.values() if group not in levels})
        if untuned:
            raise ValueError(f"no levels for group(s) {', '.join(untuned)}")
        self._levels = dict(levels)
        self._sku_group = dict(sku_group)

    def decide(self, obs: Observation) -> PolicyAction:
        """Per-SKU quantities under the group's pair."""
        reorder_quantities: dict[str, float] = {}
        for sku, level in obs.inventory.items():
            group = self._sku_group.get(sku)
            if group is None:
                raise KeyError(f"observed SKU {sku!r} has no group in this arm")
            point = self._levels[group]
            position = level + obs.on_order.get(sku, 0.0)
            if position <= point.s:
                reorder_quantities[sku] = float(point.S - position)
            else:
                reorder_quantities[sku] = 0.0
        return PolicyAction(reorder_quantities=reorder_quantities)
