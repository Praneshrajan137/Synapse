"""
``Static_Pricing`` — the static / cost-plus pricing baseline policy (R1.1, R1.3, R1.12).

Plain-language rule (the control representing operation *without* SYNAPSE):

    Price every unit at a fixed markup over its unit cost:  ``price = unit_cost × markup``.
    The markup factor is a fixed configured constant ``≥ 1.0``, so the policy never
    prices below cost. This is "what a competent operator does without SYNAPSE": a
    transparent, static cost-plus rule that ignores demand, competition, and freshness.

Edge / error behavior:

    A negative unit cost is invalid input. ``Static_Pricing`` rejects it with the typed
    :class:`NegativeUnitCostError` and produces **no** price (R1.12) — it never fabricates
    a price for a nonsensical cost.

Determinism (R1.9): the policy is a pure function of ``(unit_cost, markup)`` and holds no
hidden global state, so identical inputs yield identical decisions across runs. It accepts
an optional ``seed`` purely for interface symmetry with the seeded baseline suite; the
pricing rule itself is deterministic and does not consume the seed.
"""
from __future__ import annotations

import dataclasses

from uplift.interfaces import Observation, PolicyAction


class StaticPricingError(ValueError):
    """Base class for all ``Static_Pricing`` input/configuration errors."""


class InvalidMarkupError(StaticPricingError):
    """Raised when ``Static_Pricing`` is configured with a markup factor below ``1.0``.

    A markup ``< 1.0`` would price below cost, violating the cost-plus contract (R1.3).
    """


class NegativeUnitCostError(StaticPricingError):
    """Raised when ``Static_Pricing`` receives a negative unit cost (R1.12).

    A negative unit cost is rejected and no price is produced.
    """


@dataclasses.dataclass(frozen=True)
class Static_Pricing:
    """Static cost-plus pricing baseline implementing the ``DecisionPolicy`` protocol.

    Configuration:
        markup: the fixed markup factor applied over unit cost; MUST be ``>= 1.0`` so the
            policy never prices below cost (R1.3).
        seed: accepted for interface symmetry with the seeded baseline suite (R1.9); the
            pricing rule is deterministic and does not consume the seed.

    The policy returns a :class:`PolicyAction` that sets only ``price`` (a partial action);
    all other actuation levers are left at their neutral defaults.
    """

    markup: float
    seed: int | None = None
    name: str = "static_pricing"

    def __post_init__(self) -> None:
        # Validate the configured markup up front (R1.3): a markup below 1.0 would
        # violate the never-price-below-cost contract.
        if not (self.markup >= 1.0):
            raise InvalidMarkupError(
                f"markup must be >= 1.0 (cost-plus, never below cost); got {self.markup!r}"
            )

    def price_for(self, unit_cost: float) -> float:
        """Return the cost-plus price for a single ``unit_cost``.

        ``price = unit_cost × markup`` for any non-negative ``unit_cost`` (R1.3). Because
        ``markup >= 1.0``, the returned price is always ``>= unit_cost``.

        Raises:
            NegativeUnitCostError: if ``unit_cost`` is negative — the input is rejected and
                no price is produced (R1.12).
        """
        if unit_cost < 0:
            raise NegativeUnitCostError(
                f"unit cost must be non-negative; got {unit_cost!r}"
            )
        return unit_cost * self.markup

    def decide(self, obs: Observation) -> PolicyAction:
        """Produce a pricing decision for the current twin observation (R1.6, R2.2).

        The policy prices a representative unit cost derived from the observation's
        per-SKU ``unit_costs`` (their arithmetic mean — a deterministic reduction to the
        single scalar ``PolicyAction.price``). When no unit costs are present there is
        nothing to price, so a neutral (empty) ``PolicyAction`` is returned.

        Raises:
            NegativeUnitCostError: if the representative unit cost is negative (R1.12).
        """
        if not obs.unit_costs:
            return PolicyAction()
        costs = tuple(obs.unit_costs.values())
        representative_cost = sum(costs) / len(costs)
        return PolicyAction(price=self.price_for(representative_cost))


# Idiomatic PascalCase alias for callers preferring it over the glossary term.
StaticPricing = Static_Pricing
