"""
Par_Level_Reorder — the (s, S) reordering baseline policy (R1.1, R1.2, R1.10).

Plain-language rule (the control representing operation *without* SYNAPSE):

    Maintain two reorder points, a low-water mark ``s`` and a target level ``S`` with
    ``0 <= s < S``. For each SKU, when the observed inventory level falls to or below
    ``s``, reorder up to the target: order ``S - projected_level`` units. When the level
    is strictly above ``s``, order nothing (quantity ``0``).

This is the textbook (s, S) inventory policy: a transparent, deterministic control arm
against which SYNAPSE's four-tier consensus reorder decisions are measured. The policy
holds no hidden global state — it is constructed with a deterministic seed and produces
identical decisions for identical inputs across runs (R1.9).
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
        """Emit per-SKU reorder quantities under the (s, S) rule (R1.2, R1.10).

        For each SKU in the observation's inventory: if the projected level is at or
        below ``s``, reorder ``S - projected_level``; otherwise reorder ``0``. The
        projected inventory level is the currently observed inventory level for the SKU.
        """
        reorder_quantities: dict[str, float] = {}
        for sku, projected_level in obs.inventory.items():
            if projected_level <= self._s:
                reorder_quantities[sku] = float(self._S - projected_level)
            else:
                reorder_quantities[sku] = 0.0
        return PolicyAction(reorder_quantities=reorder_quantities)
