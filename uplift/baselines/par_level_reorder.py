"""
Par_Level_Reorder — the (s, S) reordering baseline policy (R1.1, R1.2, R1.10).

Plain-language rule (the control representing operation *without* SYNAPSE):

    Maintain two reorder points, a low-water mark ``s`` and a target level ``S`` with
    ``0 <= s < S``. For each SKU, take the INVENTORY POSITION -- the observed level plus
    what is already on order. When the position falls to or below ``s``, reorder up to the
    target: order ``S - position`` units. When the position is strictly above ``s``, order
    nothing (quantity ``0``).

This is the textbook (s, S) inventory policy: a transparent, deterministic control arm
against which SYNAPSE's four-tier consensus reorder decisions are measured. The policy
holds no hidden global state — it is constructed with a deterministic seed and produces
identical decisions for identical inputs across runs (R1.9).

**Inventory position, not on-hand stock (decision-quality-proof finding 67).** Inventory
position is the textbook (s, S) trigger. Under any supplier lead time an order is in transit,
not on the shelf, so a rule on ON-HAND stock sees the level still at or below ``s`` at the next
cadence and orders ``S - level`` again -- re-ordering the pipeline every cadence until the
first order lands. The position rule is IDENTICAL to the on-hand rule whenever nothing is on
order: with ``obs.on_order`` empty the position is the level. That is every step of every run
measured before task 13.1, because ``place_order`` is ``add_stock`` with structure 3 off.

**Ownership.** This file belongs to ``.kiro/specs/decision-integrity-uplift-proof/``. It was
edited from ``decision-quality-proof`` by operator decision (session 11, Q1=a). Its name, its
constructor signature and its seed contract are unchanged.
"""
from __future__ import annotations

import random

from uplift.interfaces import Observation, PolicyAction


class Par_Level_Reorder:
    """An ``(s, S)`` reorder policy implementing the ``DecisionPolicy`` protocol.

    Args:
        s: The reorder point (low-water mark). Must satisfy ``0 <= s < S``.
        S: The order-up-to target level. Must satisfy ``s < S``.
        seed: Deterministic seed. The policy is deterministic and uses no randomness,
            but a seeded, instance-local RNG is held so the whole baseline suite shares
            the same seed-stable construction contract with no hidden global state.

    Raises:
        ValueError: If the ``0 <= s < S`` invariant is violated.
    """

    #: Stable policy identifier used by the harness to label this arm.
    name: str = "Par_Level_Reorder"

    def __init__(self, s: int, S: int, *, seed: int = 0) -> None:
        if s < 0:
            raise ValueError(f"reorder point s must be non-negative, got s={s}")
        if not s < S:
            raise ValueError(f"require 0 <= s < S, got s={s}, S={S}")
        self._s = s
        self._S = S
        self._seed = seed
        # Instance-local RNG: no hidden global state, deterministic construction (R1.9).
        self._rng = random.Random(seed)

    @property
    def s(self) -> int:
        """The reorder point (low-water mark)."""
        return self._s

    @property
    def S(self) -> int:
        """The order-up-to target level."""
        return self._S

    @property
    def seed(self) -> int:
        """The deterministic construction seed."""
        return self._seed

    def decide(self, obs: Observation) -> PolicyAction:
        """Emit per-SKU reorder quantities under the (s, S) rule on inventory position.

        For each SKU in the observation's inventory, ``position = level + on_order`` (a SKU
        absent from ``obs.on_order`` has nothing in transit). If the position is at or below
        ``s``, reorder ``S - position``; otherwise reorder ``0``. An order is never negative:
        whenever one is placed, ``S - position >= S - s > 0``.
        """
        reorder_quantities: dict[str, float] = {}
        for sku, level in obs.inventory.items():
            position = level + obs.on_order.get(sku, 0.0)
            if position <= self._s:
                reorder_quantities[sku] = float(self._S - position)
            else:
                reorder_quantities[sku] = 0.0
        return PolicyAction(reorder_quantities=reorder_quantities)
