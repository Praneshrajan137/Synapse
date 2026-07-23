"""
SYNAPSE Decision-Integrity Uplift Proof — the adversarial scenario suite (R4.1).

Defines exactly four seeded, replayable :class:`~uplift.interfaces.Scenario`s via
``ShockParams``, expressing the design "AdversarialSuite (R4)" realizations:

======================  ==========================================================
Scenario                Realization
======================  ==========================================================
demand-spike            ``ShockParams(demand_multiplier=2.0)``
supplier-default        ``ShockParams(lead_time_multiplier=2.0,
                        failure_rate_multiplier=3.0)``
monsoon-disruption      ``ShockParams(spoilage_rate_multiplier > 1,
                        lead_time_multiplier > 1)``
cold-start-city         empty initial inventory / freshness (``cold_start=True``)
======================  ==========================================================

Each ``Scenario`` carries a distinct fixed seed so the suite is deterministically
replayable: an identical seed produces an identical demand realization + shock across
every arm (the attribution guarantee, R2.1/R2.5/R4.2). The suite is exposed as the
immutable tuple :data:`ADVERSARIAL_SUITE` and via the :func:`adversarial_suite`
factory for callers that want a fresh copy.
"""
from __future__ import annotations

from digital_twin.simulation.monte_carlo import ShockParams

from uplift.interfaces import Scenario

# ---------------------------------------------------------------------------
# Distinct fixed seeds — one per scenario, so the suite is replayable and each
# scenario's demand realization is stable and independent (R4.1).
# ---------------------------------------------------------------------------
DEMAND_SPIKE_SEED = 4001
SUPPLIER_DEFAULT_SEED = 4002
MONSOON_DISRUPTION_SEED = 4003
COLD_START_CITY_SEED = 4004


# ---------------------------------------------------------------------------
# The four adversarial scenarios (design "AdversarialSuite (R4)" realizations).
# ---------------------------------------------------------------------------

#: Sudden surge in customer demand: order arrival doubles (R4.1).
DEMAND_SPIKE = Scenario(
    name="demand-spike",
    seed=DEMAND_SPIKE_SEED,
    shock=ShockParams(demand_multiplier=2.0),
)

#: A supplier defaults: lead times double and the failure rate triples (R4.1).
SUPPLIER_DEFAULT = Scenario(
    name="supplier-default",
    seed=SUPPLIER_DEFAULT_SEED,
    shock=ShockParams(lead_time_multiplier=2.0, failure_rate_multiplier=3.0),
)

#: Monsoon disruption: elevated spoilage AND elevated lead time (both > 1) (R4.1).
MONSOON_DISRUPTION = Scenario(
    name="monsoon-disruption",
    seed=MONSOON_DISRUPTION_SEED,
    shock=ShockParams(spoilage_rate_multiplier=2.0, lead_time_multiplier=1.5),
)

#: A brand-new city with no warm history: empty initial inventory / freshness (R4.1).
COLD_START_CITY = Scenario(
    name="cold-start-city",
    seed=COLD_START_CITY_SEED,
    shock=ShockParams(),
    cold_start=True,
)


# ---------------------------------------------------------------------------
# The suite — exactly four scenarios, exposed as an immutable tuple (R4.1).
# ---------------------------------------------------------------------------
ADVERSARIAL_SUITE: tuple[Scenario, ...] = (
    DEMAND_SPIKE,
    SUPPLIER_DEFAULT,
    MONSOON_DISRUPTION,
    COLD_START_CITY,
)


def adversarial_suite() -> tuple[Scenario, ...]:
    """Return the four-entry adversarial scenario suite (R4.1).

    ``Scenario`` is a frozen dataclass, so the returned tuple can be shared safely;
    the factory exists so callers can obtain the suite without importing the module
    constant directly.
    """
    return ADVERSARIAL_SUITE


__all__ = [
    "ADVERSARIAL_SUITE",
    "COLD_START_CITY",
    "COLD_START_CITY_SEED",
    "DEMAND_SPIKE",
    "DEMAND_SPIKE_SEED",
    "MONSOON_DISRUPTION",
    "MONSOON_DISRUPTION_SEED",
    "SUPPLIER_DEFAULT",
    "SUPPLIER_DEFAULT_SEED",
    "adversarial_suite",
]
