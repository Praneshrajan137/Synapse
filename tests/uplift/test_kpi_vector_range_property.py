"""Property-based tests for ``KpiExtractor`` KpiVector range invariants.

Feature: decision-integrity-uplift-proof
Property 7: Every recorded KPI_Vector satisfies its range invariants.

    *For any* completed scenario run — any twin ``SimulationMetrics`` plus any
    ``AppliedDecisions`` the extractor could see, including adversarial or degenerate
    inputs (negative or huge counts, ``nan``/``inf`` rates) — the derived
    ``KpiVector`` has ``fill_rate``/``spoilage_rate``/``stockout_rate`` in the closed
    interval ``[0.0, 1.0]``, ``avg_delivery_time_min >= 0`` and finite, and
    ``margin``/``co2_estimate`` finite.

Carried to Metric_Contract v2 (decision-quality-proof task 29.4), and STRICTER. The vector also
carries ``avg_on_hand_units``, asserted non-negative, finite and equal to the engine's read, and
the committed ``objective``, asserted finite and equal to ``RegretObjective.cost`` of the five
unclamped engine reads. An input with no admissible objective -- a negative or non-finite
on-hand mean, or a non-finite cost -- is REFUSED with ``ObjectiveUnavailableError`` rather than
clamped, because a clamped cost of 0.0 is the best cost there is. The harness records that
refusal as a failed run, so it never becomes a completed run's vector. The refusal is asserted
to happen on exactly those inputs, and proven by construction for each engine read.

Validates: Requirements 2.3
"""
from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from uplift.kpi import (
    AppliedDecisions,
    DeliveredOrder,
    KpiExtractor,
    ObjectiveUnavailableError,
    committed_objective,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from digital_twin.simulation.engine import SimulationMetrics

    from uplift.interfaces import KpiVector

#: The committed objective the harness prices every replicate with (read once per process).
_OBJECTIVE = committed_objective()

#: The twin clock at the end of a run, in minutes: the horizon ``avg_on_hand_units`` averages
#: over. ``extract`` requires it; the double below answers the same mean at any horizon.
_HORIZON_MIN = 240.0


@dataclasses.dataclass(frozen=True)
class _EngineReads:
    """Exactly what ``KpiExtractor.extract`` reads off ``SimulationMetrics``, held directly.

    On the real ``SimulationMetrics`` the rates are *derived* properties that can never carry
    ``nan``/``inf``, but Property 7 must hold for *any* value the extractor could plausibly
    read, so this double exposes them as plain fields that can carry adversarial values. The
    reads v2 added are the engine's ``stockout_rate`` and ``fill_rate`` (which the objective
    prices, unclamped) and ``avg_on_hand_units(sim_time_min)``, answered with ``on_hand_mean``.
    """

    orders_created: int
    orders_delivered: int
    spoilage_rate: float
    avg_delivery_time_min: float
    stockout_rate: float
    fill_rate: float
    on_hand_mean: float

    def avg_on_hand_units(self, sim_time_min: float) -> float:
        """The engine's on-hand mean over ``sim_time_min``; this double has no clock."""
        return self.on_hand_mean

    def as_metrics(self) -> SimulationMetrics:
        """This double, typed as the engine metrics it stands in for at ``extract``."""
        return cast("SimulationMetrics", self)


def _committed_cost(reads: _EngineReads) -> float:
    """The committed objective of the five unclamped engine reads: the oracle for ``objective``."""
    return _OBJECTIVE.cost(
        stockout_rate=reads.stockout_rate,
        spoilage_rate=reads.spoilage_rate,
        fill_rate=reads.fill_rate,
        avg_on_hand_units=reads.on_hand_mean,
        avg_delivery_time_min=reads.avg_delivery_time_min,
    )


def _is_priceable(reads: _EngineReads) -> bool:
    """Whether an admissible objective exists: on-hand non-negative and finite, cost finite."""
    if not math.isfinite(reads.on_hand_mean) or reads.on_hand_mean < 0.0:
        return False
    return math.isfinite(_committed_cost(reads))


#: One float read replaced, per read the objective depends on; typed so no field is guessed.
_POISON: dict[str, Callable[[_EngineReads, float], _EngineReads]] = {
    "stockout_rate": lambda reads, value: dataclasses.replace(reads, stockout_rate=value),
    "spoilage_rate": lambda reads, value: dataclasses.replace(reads, spoilage_rate=value),
    "fill_rate": lambda reads, value: dataclasses.replace(reads, fill_rate=value),
    "avg_delivery_time_min": lambda reads, value: dataclasses.replace(
        reads, avg_delivery_time_min=value
    ),
    "on_hand_mean": lambda reads, value: dataclasses.replace(reads, on_hand_mean=value),
}


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Counts: include negatives, zero, and huge magnitudes.
_counts = st.integers(min_value=-(10**18), max_value=10**18)

# Rates the extractor consumes directly: include in-range, out-of-range,
# negative, huge, and non-finite (nan/inf) values.
_adversarial_floats = st.floats(allow_nan=True, allow_infinity=True)

# Prices/costs for delivered orders: allow non-finite so margin summation is
# exercised on degenerate inputs too.
_price_or_cost = st.floats(allow_nan=True, allow_infinity=True)

# Finite reads bounded far inside the range where the weighted cost could overflow, and an
# on-hand mean that is non-negative: the domain on which an admissible objective must exist.
_bounded_floats = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)
_admissible_on_hand = st.floats(
    min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False
)


def _engine_reads(
    rates: st.SearchStrategy[float], on_hand: st.SearchStrategy[float]
) -> st.SearchStrategy[_EngineReads]:
    return st.builds(
        _EngineReads,
        orders_created=_counts,
        orders_delivered=_counts,
        spoilage_rate=rates,
        avg_delivery_time_min=rates,
        stockout_rate=rates,
        fill_rate=rates,
        on_hand_mean=on_hand,
    )


#: Any engine read at all, adversarial ones included.
_any_reads = _engine_reads(_adversarial_floats, _adversarial_floats)

#: Engine reads from which an admissible objective exists.
_priceable_reads = _engine_reads(_bounded_floats, _admissible_on_hand)


_delivered_orders = st.lists(
    st.builds(DeliveredOrder, applied_price=_price_or_cost, unit_cost=_price_or_cost),
    max_size=8,
).map(tuple)


def _applied_strategy() -> st.SearchStrategy[AppliedDecisions]:
    return st.builds(
        AppliedDecisions,
        delivered_orders=_delivered_orders,
        unmet_demand_events=_counts,
        demand_events=st.none() | _counts,
        delivered_volume=st.none() | _adversarial_floats,
    )


def _extract(reads: _EngineReads, applied: AppliedDecisions) -> KpiVector:
    """Run the shared extractor exactly as the harness does, with the committed objective."""
    extractor = KpiExtractor(objective=_OBJECTIVE)
    return extractor.extract(reads.as_metrics(), applied, sim_time_min=_HORIZON_MIN)


def _assert_range_invariants(kpis: KpiVector, reads: _EngineReads) -> None:
    """Every clause of Property 7, plus the two v2 fields."""
    # Fractional KPIs must lie in the closed interval [0.0, 1.0].
    for fraction in (kpis.fill_rate, kpis.spoilage_rate, kpis.stockout_rate):
        assert math.isfinite(fraction)
        assert 0.0 <= fraction <= 1.0

    # Delivery time is a non-negative, finite number of minutes.
    assert math.isfinite(kpis.avg_delivery_time_min)
    assert kpis.avg_delivery_time_min >= 0.0

    # Margin and CO2 estimate are numeric and finite.
    assert math.isfinite(kpis.margin)
    assert math.isfinite(kpis.co2_estimate)

    # The on-hand mean is the engine's read, non-negative and finite -- never clamped.
    assert math.isfinite(kpis.avg_on_hand_units)
    assert kpis.avg_on_hand_units >= 0.0
    assert kpis.avg_on_hand_units == reads.on_hand_mean

    # The objective is finite and is the committed cost of the five unclamped engine reads.
    assert math.isfinite(kpis.objective)
    assert kpis.objective == _committed_cost(reads)


# ---------------------------------------------------------------------------
# Property 7: derived KpiVector always satisfies its range invariants (R2.3)
# ---------------------------------------------------------------------------
@given(reads=_any_reads, applied=_applied_strategy())
def test_kpi_vector_satisfies_range_invariants(
    reads: _EngineReads, applied: AppliedDecisions
) -> None:
    """Every derived KpiVector honours the design's range invariants (Property 7).

    A vector is produced exactly when an admissible objective exists. Otherwise the extractor
    refuses, which the harness records as a failed run, never as a completed one.
    """
    if not _is_priceable(reads):
        with pytest.raises(ObjectiveUnavailableError):
            _extract(reads, applied)
        return
    _assert_range_invariants(_extract(reads, applied), reads)


@given(reads=_priceable_reads, applied=_applied_strategy())
def test_a_priceable_run_is_never_refused(
    reads: _EngineReads, applied: AppliedDecisions
) -> None:
    """With admissible engine reads, extraction always yields a vector meeting every invariant."""
    assert _is_priceable(reads)
    _assert_range_invariants(_extract(reads, applied), reads)


@given(
    reads=_priceable_reads,
    applied=_applied_strategy(),
    read=st.sampled_from(sorted(_POISON)),
    value=st.sampled_from((math.nan, math.inf, -math.inf)),
)
def test_a_non_finite_engine_read_is_refused_never_clamped(
    reads: _EngineReads, applied: AppliedDecisions, read: str, value: float
) -> None:
    """One non-finite read the objective depends on leaves no admissible cost: refused."""
    unpriceable = _POISON[read](reads, value)

    with pytest.raises(ObjectiveUnavailableError):
        _extract(unpriceable, applied)


@given(
    reads=_priceable_reads,
    applied=_applied_strategy(),
    on_hand=st.floats(min_value=-1e12, max_value=-1e-12, allow_nan=False, allow_infinity=False),
)
def test_a_negative_on_hand_mean_is_refused_never_clamped(
    reads: _EngineReads, applied: AppliedDecisions, on_hand: float
) -> None:
    """A negative on-hand mean prices no holding cost, so the replicate has no objective."""
    unpriceable = dataclasses.replace(reads, on_hand_mean=on_hand)

    with pytest.raises(ObjectiveUnavailableError, match="avg_on_hand_units"):
        _extract(unpriceable, applied)
