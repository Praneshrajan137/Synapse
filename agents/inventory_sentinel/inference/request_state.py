"""What the Inventory Sentinel reads from the state its decision request carries (ADR-058).

Finding 112: the protocol sends ``params={"decision_context": request}``
(``orchestrator/consensus/protocol.py:1040``), and the handler read the request's keys one level
too shallow, so the Sentinel decided for ``SKU001`` on ``decide()``'s missing-entry forecast
whatever the request said. Decision S13.3=a: read the state the request already carries --
inventory position, demand rate and lead time -- and name every assumption.

:func:`forecast_from_request` turns a decision context into ``decide()``'s ``demand_forecast``
(``inference/pipeline.py``), one entry per SKU the request's stock mappings name, in sorted order:

* ``on_hand`` -- ``inventory_position[s]`` (on hand plus on order), else ``inventory[s]``;
* ``rate`` -- ``demand_to_date[s] / sim_time``: demand events per minute since the run began;
* ``L`` -- the mean of ``supplier_lead_time_history[sku_supplier[s]]``, in minutes, which holds
  landed orders only; :data:`LEAD_TIME_PRIOR_MIN` while that supplier has landed none;
* ``mean = rate * (L + R)``: the demand expected before an order placed now and the next order
  can both land, ``R`` being :data:`REVIEW_PERIOD_MIN`; ``std = sqrt(mean)``, the Poisson spread;
* ``lead_time_days = L / MINUTES_PER_DAY``.

The function is pure: it reads its argument, mutates nothing and keeps no state, so equal
contexts give equal forecasts. It reads nothing about the world except what the request carries;
the constants below are its only other inputs. ADR-058 records each with its provenance, and
``tests/test_request_state.py`` pins that record to the values here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

from agents.inventory_sentinel.inference import pipeline

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "LEAD_TIME_PRIOR_MIN",
    "MINUTES_PER_DAY",
    "MIN_EVENTS_FOR_RATE",
    "REVIEW_PERIOD_MIN",
    "forecast_from_request",
    "reading_trace",
]

#: Definitional: ``decide()`` takes a lead time in days, and the request reports minutes.
MINUTES_PER_DAY: Final[float] = 1440.0

#: Chosen: the review period ``R``, in minutes. An order placed now must cover demand until the
#: next order can land, ``L + R`` from now, and the request carries no review period. 60 is the
#: cadence of E5, the only caller whose requests carry state (one decision an hour,
#: ``uplift/e5_suite.py::E5_LOOP``); arm O is given the same value as ``review_min``.
REVIEW_PERIOD_MIN: Final[float] = 60.0

#: Chosen: the lead time planned for a supplier none of whose orders has landed, in minutes. It is
#: the agent's own ``DEFAULT_LEAD_TIME_DAYS``, read from ``pipeline.py`` rather than restated, so
#: it says nothing about any world. A prior that is too long over-stocks, and the agent's own
#: costs (``cost_under = 8`` against ``cost_over = 1``, ``models/newsvendor.py``) make
#: over-stocking the cheaper error.
LEAD_TIME_PRIOR_MIN: Final[float] = pipeline.DEFAULT_LEAD_TIME_DAYS * MINUTES_PER_DAY

#: Chosen: the fewest demand events a SKU's rate is estimated from. With none -- no exposure yet
#: (``sim_time`` 0) or no event observed -- the estimate is 0 with a Poisson spread of 0, which
#: ``decide()`` would report at its highest confidence, 0.99, from no evidence. Such a SKU gets no
#: ``mean`` and no ``std``, so ``decide()`` applies the forecast it applied before ADR-058, on the
#: request's own position and lead time.
MIN_EVENTS_FOR_RATE: Final[int] = 1


def forecast_from_request(ctx: Mapping[str, Any]) -> dict[str, dict[str, float]] | None:
    """``decide()``'s ``demand_forecast`` from the state ``ctx`` carries; ``None`` without state.

    ``None`` when ``ctx`` carries neither ``inventory_position`` nor ``inventory``: the request
    reports no stock, so there is nothing to plan against, and the caller keeps ``decide()``'s
    defaults. ADR-058 records refusing such a request as an open decision. Otherwise there is one
    entry per SKU either stock mapping names, in sorted order. A SKU with fewer than
    :data:`MIN_EVENTS_FOR_RATE` observed events carries ``on_hand`` and ``lead_time_days`` only.

    Raises:
        ValueError: If a state key is present but malformed: a mapping that is not one, a stock
            level that is negative or not finite, a ``sim_time`` that is negative or not finite,
            a demand count that is not a non-negative integer, a supplier that is not a non-empty
            string, a landed lead time that is not finite and > 0, or a forecast that overflows.
            A malformed state is a defect in its producer, and defaults would hide it.
    """
    positions = _stock(ctx, "inventory_position")
    on_hand = _stock(ctx, "inventory")
    if positions is None and on_hand is None:
        return None
    stock = {**(on_hand or {}), **(positions or {})}
    exposure_min = _exposure_min(ctx)
    events = _event_counts(ctx)
    suppliers = _suppliers(ctx)
    landed = _landed_lead_times(ctx)
    forecast: dict[str, dict[str, float]] = {}
    for sku in sorted(stock):
        lead_time_min = _lead_time_min(sku, suppliers, landed)
        entry: dict[str, float] = {
            "on_hand": stock[sku],
            "lead_time_days": lead_time_min / MINUTES_PER_DAY,
        }
        observed = events.get(sku, 0.0)
        if exposure_min is not None and exposure_min > 0.0 and observed >= MIN_EVENTS_FOR_RATE:
            mean = observed / exposure_min * (lead_time_min + REVIEW_PERIOD_MIN)
            entry["mean"] = mean
            entry["std"] = math.sqrt(mean)
        if not all(math.isfinite(value) for value in entry.values()):
            raise ValueError(
                f"the forecast for {sku!r} overflows ({entry!r}); the request's state is refused "
                "rather than planned against"
            )
        forecast[sku] = entry
    return forecast


def reading_trace(
    forecast: Mapping[str, Mapping[str, float]] | None, sku_ids: Sequence[str]
) -> str:
    """The justification-trace line: whether the request's state was read, and for which SKUs.

    With state, each requested SKU falls in one of three lists: read (position, demand rate and
    lead time), unrated (position and lead time read, but too few observed events for a rate,
    so ``decide()``'s own forecast applies), and unstocked (no position in the request, so
    ``decide()``'s defaults apply in full).
    """
    if forecast is None:
        return (
            "Request state absent (ADR-058): decide()'s default forecast for every SKU "
            f"{list(sku_ids)}"
        )
    read = [sku for sku in sku_ids if "mean" in forecast.get(sku, {})]
    unrated = [sku for sku in sku_ids if sku in forecast and "mean" not in forecast[sku]]
    unstocked = [sku for sku in sku_ids if sku not in forecast]
    return (
        f"Request state read (ADR-058): position, demand rate and lead time for {read}; "
        f"position and lead time on decide()'s default forecast for {unrated}; "
        f"decide()'s defaults with no position for {unstocked}"
    )


# ---------------------------------------------------------------------------
# Reading one key each. Absent is None (or empty); present and malformed is refused.
# ---------------------------------------------------------------------------


def _mapping(ctx: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    """``ctx[key]`` when present, which must be a mapping; ``None`` when absent."""
    value = ctx.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(
            f"decision_context.{key} must be a mapping, got {type(value).__name__}; a malformed "
            "state is refused, never read as absent"
        )
    return value


def _number(value: object, where: str) -> float:
    """``value`` as a finite float. Booleans, non-numbers and non-finite values are refused."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{where} must be a number, got {value!r}")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{where} = {value!r} does not fit in a float") from exc
    if not math.isfinite(number):
        raise ValueError(f"{where} must be finite, got {value!r}")
    return number


def _stock(ctx: Mapping[str, Any], key: str) -> dict[str, float] | None:
    """A per-SKU stock mapping, every level finite and >= 0; ``None`` when absent."""
    levels = _mapping(ctx, key)
    if levels is None:
        return None
    out: dict[str, float] = {}
    for sku, level in levels.items():
        where = f"decision_context.{key}[{sku!r}]"
        units = _number(level, where)
        if units < 0.0:
            raise ValueError(f"{where} = {level!r} is negative")
        out[sku] = units
    return out


def _exposure_min(ctx: Mapping[str, Any]) -> float | None:
    """``sim_time``: minutes since the run began, finite and >= 0; ``None`` when absent."""
    value = ctx.get("sim_time")
    if value is None:
        return None
    minutes = _number(value, "decision_context.sim_time")
    if minutes < 0.0:
        raise ValueError(f"decision_context.sim_time = {value!r} is negative")
    return minutes


def _event_counts(ctx: Mapping[str, Any]) -> dict[str, float]:
    """``demand_to_date``: demand events per SKU, each a non-negative integer; ``{}`` when absent.

    A SKU it does not name has no observed event. The twin adds a SKU on its first event
    (``digital_twin/simulation/engine.py::_record_demand``), and a request that reports no demand
    observes none for any SKU; in both cases the SKU gets no rate (:data:`MIN_EVENTS_FOR_RATE`).
    """
    counts = _mapping(ctx, "demand_to_date")
    if counts is None:
        return {}
    out: dict[str, float] = {}
    for sku, count in counts.items():
        where = f"decision_context.demand_to_date[{sku!r}]"
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{where} = {count!r} is not a count of demand events")
        out[sku] = _number(count, where)
    return out


def _suppliers(ctx: Mapping[str, Any]) -> dict[str, str]:
    """``sku_supplier``: the supplier each SKU is ordered from; ``{}`` when absent."""
    named = _mapping(ctx, "sku_supplier")
    if named is None:
        return {}
    out: dict[str, str] = {}
    for sku, supplier in named.items():
        if not isinstance(supplier, str) or not supplier:
            raise ValueError(
                f"decision_context.sku_supplier[{sku!r}] = {supplier!r} names no supplier"
            )
        out[sku] = supplier
    return out


def _landed_lead_times(ctx: Mapping[str, Any]) -> dict[str, tuple[float, ...]]:
    """``supplier_lead_time_history``: each supplier's landed lead times, in minutes, each > 0.

    Every supplier's history is checked, not only those a requested SKU uses: a malformed record
    is a defect in its producer wherever it sits.
    """
    history = _mapping(ctx, "supplier_lead_time_history")
    if history is None:
        return {}
    out: dict[str, tuple[float, ...]] = {}
    for supplier, times in history.items():
        where = f"decision_context.supplier_lead_time_history[{supplier!r}]"
        if not isinstance(times, list | tuple):
            raise ValueError(f"{where} must be a list of lead times, got {type(times).__name__}")
        landed = tuple(_number(minutes, where) for minutes in times)
        if any(minutes <= 0.0 for minutes in landed):
            raise ValueError(
                f"{where} holds a lead time <= 0 minutes, but a landed order took a positive time"
            )
        out[supplier] = landed
    return out


def _lead_time_min(
    sku: str, suppliers: Mapping[str, str], landed: Mapping[str, tuple[float, ...]]
) -> float:
    """The mean landed lead time of ``sku``'s supplier, or :data:`LEAD_TIME_PRIOR_MIN`.

    The prior also covers a SKU whose supplier the request does not name: the request then says
    nothing about how long its orders take.
    """
    supplier = suppliers.get(sku)
    times = () if supplier is None else landed.get(supplier, ())
    if not times:
        return LEAD_TIME_PRIOR_MIN
    return math.fsum(times) / len(times)
