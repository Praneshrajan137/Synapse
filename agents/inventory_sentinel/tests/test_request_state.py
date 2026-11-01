"""ADR-058: the Inventory Sentinel plans on the state its decision request carries.

Each test states one claim of ``agents/inventory_sentinel/inference/request_state.py`` in the
domain's words. The Hypothesis example budget is the active profile's (root ``conftest.py``);
no test here sets one.
"""

from __future__ import annotations

import copy
import math
import re
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agents.inventory_sentinel.inference import pipeline, request_state
from agents.inventory_sentinel.inference.request_state import (
    LEAD_TIME_PRIOR_MIN,
    MINUTES_PER_DAY,
    REVIEW_PERIOD_MIN,
    forecast_from_request,
)

if TYPE_CHECKING:
    from hypothesis.strategies import DrawFn

_SKUS = tuple(f"sku_{index}" for index in range(10))
_SUPPLIERS = ("sup_a", "sup_b", "sup_c")
_MINUTES = st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False)
_LEVELS = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)

#: A context that reports stock and nothing else, for the refusal cases below.
_STOCKED: dict[str, Any] = {"inventory_position": {"sku_0": 1.0}}

#: ADR-058, whose table of constants the last test pins to this module.
_ADR_058 = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "adr"
    / "ADR-058-inventory-sentinel-reads-the-request.md"
)
_CONSTANT_ROW = re.compile(
    r"^\| `(?P<name>[A-Z_]+)` \| (?P<value>[0-9.]+) \| (?P<provenance>[a-z]+) \|", re.MULTILINE
)


@st.composite
def _rated_contexts(draw: DrawFn) -> dict[str, Any]:
    """A context keyed as ``observation_to_decision_request`` keys one, every SKU rated.

    Every SKU has at least one demand event over a positive exposure, and a supplier with at
    least one landed order. The bounds keep every intermediate a normal, finite float: the domain
    the float-precision claim is stated over.
    """
    skus = sorted(draw(st.sets(st.sampled_from(_SKUS), min_size=1)))
    supplier_of = {sku: draw(st.sampled_from(_SUPPLIERS)) for sku in skus}
    return {
        "sku_ids": skus,
        "sim_time": draw(_MINUTES),
        "inventory": {sku: draw(st.integers(min_value=0, max_value=10**6)) for sku in skus},
        "inventory_position": {sku: draw(_LEVELS) for sku in skus},
        "demand_to_date": {sku: draw(st.integers(min_value=1, max_value=10**7)) for sku in skus},
        "sku_supplier": supplier_of,
        "supplier_lead_time_history": {
            supplier: draw(st.lists(_MINUTES, min_size=1, max_size=6))
            for supplier in sorted(set(supplier_of.values()))
        },
    }


@st.composite
def _any_contexts(draw: DrawFn) -> dict[str, Any]:
    """Any well-formed context with stock: unrated SKUs, unnamed suppliers, empty histories."""
    skus = sorted(draw(st.sets(st.sampled_from(_SKUS), min_size=1)))
    with_supplier = sorted(draw(st.sets(st.sampled_from(skus))))
    ctx: dict[str, Any] = {
        "sku_ids": skus,
        "inventory_position": {sku: draw(_LEVELS) for sku in skus},
        "sku_supplier": {sku: draw(st.sampled_from(_SUPPLIERS)) for sku in with_supplier},
        "supplier_lead_time_history": {
            supplier: draw(st.lists(_MINUTES, max_size=6)) for supplier in _SUPPLIERS
        },
    }
    if draw(st.booleans()):
        ctx["sim_time"] = draw(st.one_of(st.just(0.0), _MINUTES))
    if draw(st.booleans()):
        counted = sorted(draw(st.sets(st.sampled_from(skus))))
        ctx["demand_to_date"] = {
            sku: draw(st.integers(min_value=0, max_value=10**7)) for sku in counted
        }
    return ctx


@pytest.mark.parametrize(
    "ctx",
    [
        pytest.param({}, id="an-empty-context"),
        pytest.param({"sku_ids": ["sku_0"], "store_id": "STORE_MUM_001"}, id="skus-and-a-store"),
        pytest.param(
            {"sim_time": 60.0, "demand_to_date": {"sku_0": 7}, "sku_supplier": {"sku_0": "sup_a"}},
            id="demand-and-suppliers-but-no-stock",
        ),
        # orchestrator/inference/serve.py::DecisionRequest.model_dump(), the live HTTP path.
        pytest.param(
            {
                "order_id": "synthetic-1-1",
                "store_id": "STORE_BLR_002",
                "items": [{"sku_id": "SKU_BEV_001", "quantity": 2}],
                "agents_involved": [],
                "disruption_active": False,
                "requires_twin_simulation": False,
            },
            id="the-live-http-request",
        ),
        # orchestrator/sensor/loop.py::_build_request reports on-hand stock as
        # `world_inventory`, a key the mapping does not read (ADR-058 open decision O3).
        pytest.param(
            {"store_id": "store_001", "sku_ids": ["sku_3"], "world_inventory": {"sku_3": 12.0}},
            id="the-sensor-loop-request",
        ),
    ],
)
def test_a_request_that_reports_no_stock_carries_no_state_to_plan_against(
    ctx: dict[str, Any],
) -> None:
    assert forecast_from_request(ctx) is None


@given(ctx=_any_contexts())
def test_the_mapping_is_pure_leaving_its_request_unchanged_and_sharing_no_state(
    ctx: dict[str, Any],
) -> None:
    before = copy.deepcopy(ctx)
    first = forecast_from_request(ctx)
    assert ctx == before
    assert first is not None
    snapshot = copy.deepcopy(first)
    for entry in first.values():
        entry["on_hand"] = -1.0  # a caller editing one result must not reach the next call
    assert forecast_from_request(ctx) == snapshot
    assert forecast_from_request(copy.deepcopy(before)) == snapshot


@given(ctx=_rated_contexts())
def test_the_forecast_mean_is_the_observed_rate_over_the_protection_window(
    ctx: dict[str, Any],
) -> None:
    """``mean = demand_to_date / sim_time * (mean landed lead time + R)``, to float precision.

    The oracle is exact rational arithmetic, so it shares no rounding with the code under test.
    The float path rounds at most six times, about 7e-16 relative in all, so ``rel_tol=1e-14``
    leaves a factor of about fifteen and no room for a different formula.
    """
    forecast = forecast_from_request(ctx)
    assert forecast is not None
    for sku in ctx["sku_ids"]:
        landed = ctx["supplier_lead_time_history"][ctx["sku_supplier"][sku]]
        lead_time = sum((Fraction(minutes) for minutes in landed), Fraction(0)) / len(landed)
        rate = Fraction(ctx["demand_to_date"][sku]) / Fraction(ctx["sim_time"])
        mean = rate * (lead_time + Fraction(REVIEW_PERIOD_MIN))
        entry = forecast[sku]
        assert math.isclose(entry["mean"], float(mean), rel_tol=1e-14)
        assert math.isclose(entry["std"], math.sqrt(float(mean)), rel_tol=1e-14)
        assert math.isclose(
            entry["lead_time_days"], float(lead_time / Fraction(MINUTES_PER_DAY)), rel_tol=1e-14
        )


@given(ctx=_rated_contexts())
def test_on_hand_is_the_requests_inventory_position_not_its_shelf_stock(
    ctx: dict[str, Any],
) -> None:
    """Stock in transit counts: the position is on hand plus on order, and it outranks shelf stock.

    The generator draws ``inventory`` independently of ``inventory_position``, so a mapping that
    read the shelf instead would fail here.
    """
    forecast = forecast_from_request(ctx)
    assert forecast is not None
    assert {sku: entry["on_hand"] for sku, entry in forecast.items()} == ctx["inventory_position"]


def test_a_sku_with_no_position_is_planned_on_its_shelf_stock() -> None:
    shelf_only = forecast_from_request({"inventory": {"sku_0": 40, "sku_1": 0}})
    assert shelf_only is not None
    assert {sku: entry["on_hand"] for sku, entry in shelf_only.items()} == {
        "sku_0": 40.0,
        "sku_1": 0.0,
    }
    mixed = forecast_from_request(
        {"inventory": {"sku_0": 40, "sku_1": 3}, "inventory_position": {"sku_1": 23.0}}
    )
    assert mixed is not None
    assert {sku: entry["on_hand"] for sku, entry in mixed.items()} == {
        "sku_0": 40.0,
        "sku_1": 23.0,
    }


@given(ctx=_any_contexts())
def test_every_forecast_value_is_finite_and_non_negative(ctx: dict[str, Any]) -> None:
    forecast = forecast_from_request(ctx)
    assert forecast is not None
    values = [value for entry in forecast.values() for value in entry.values()]
    assert values
    assert all(math.isfinite(value) and value >= 0.0 for value in values)


@pytest.mark.parametrize(
    "demand",
    [
        pytest.param({"sim_time": 0.0, "demand_to_date": {}}, id="the-first-decision-of-a-run"),
        pytest.param({"sim_time": 0.0, "demand_to_date": {"sku_0": 4}}, id="events-no-exposure"),
        pytest.param({"sim_time": 300.0, "demand_to_date": {}}, id="exposure-but-no-event"),
        pytest.param({"sim_time": 300.0, "demand_to_date": {"sku_0": 0}}, id="a-zero-count"),
        pytest.param({"sim_time": 300.0}, id="no-demand-reported"),
        pytest.param({"demand_to_date": {"sku_0": 4}}, id="no-clock-reported"),
    ],
)
def test_a_sku_with_no_observed_demand_gets_no_rate_so_decide_keeps_its_own_forecast(
    demand: dict[str, Any],
) -> None:
    """Cold start: the position and the lead time are read, and no mean or std is invented."""
    ctx = {"inventory_position": {"sku_0": 37.5}, **demand}
    assert forecast_from_request(ctx) == {
        "sku_0": {"on_hand": 37.5, "lead_time_days": pipeline.DEFAULT_LEAD_TIME_DAYS}
    }


@pytest.mark.parametrize(
    "supply",
    [
        pytest.param({}, id="no-supply-state"),
        pytest.param({"sku_supplier": {"sku_0": "sup_a"}}, id="a-supplier-but-no-history"),
        pytest.param(
            {"sku_supplier": {"sku_0": "sup_a"}, "supplier_lead_time_history": {"sup_a": []}},
            id="nothing-landed-yet",
        ),
        pytest.param(
            {"sku_supplier": {"sku_0": "sup_a"}, "supplier_lead_time_history": {"sup_b": [200.0]}},
            id="only-another-supplier-landed",
        ),
        pytest.param(
            {"sku_supplier": {}, "supplier_lead_time_history": {"sup_a": [200.0]}},
            id="the-skus-supplier-unnamed",
        ),
    ],
)
def test_a_supplier_with_no_landed_order_is_planned_at_the_agents_own_default_lead_time(
    supply: dict[str, Any],
) -> None:
    """The prior is ``pipeline.DEFAULT_LEAD_TIME_DAYS``, which reads nothing about the world."""
    ctx = {
        "inventory_position": {"sku_0": 0.0},
        "sim_time": 60.0,
        "demand_to_date": {"sku_0": 6},
        **supply,
    }
    forecast = forecast_from_request(ctx)
    assert forecast is not None
    entry = forecast["sku_0"]
    assert entry["lead_time_days"] == pipeline.DEFAULT_LEAD_TIME_DAYS
    window = LEAD_TIME_PRIOR_MIN + REVIEW_PERIOD_MIN
    assert math.isclose(entry["mean"], 6 / 60.0 * window, rel_tol=1e-14)


@pytest.mark.parametrize(
    ("ctx", "key"),
    [
        pytest.param({"inventory_position": [10.0]}, "inventory_position", id="not-a-mapping"),
        pytest.param({"inventory_position": {"sku_0": -1.0}}, "inventory_position", id="negative"),
        pytest.param({"inventory_position": {"sku_0": math.inf}}, "inventory_position", id="inf"),
        pytest.param({"inventory_position": {"sku_0": True}}, "inventory_position", id="a-bool"),
        pytest.param({"inventory": {"sku_0": "ten"}}, "inventory", id="shelf-not-a-number"),
        pytest.param({**_STOCKED, "sim_time": -60.0}, "sim_time", id="a-negative-clock"),
        pytest.param({**_STOCKED, "sim_time": math.nan}, "sim_time", id="a-nan-clock"),
        pytest.param(
            {**_STOCKED, "demand_to_date": {"sku_0": 2.5}}, "demand_to_date", id="a-fraction"
        ),
        pytest.param({**_STOCKED, "sku_supplier": {"sku_0": 7}}, "sku_supplier", id="unnamed"),
        pytest.param(
            {**_STOCKED, "supplier_lead_time_history": {"sup_a": [0.0]}},
            "supplier_lead_time_history",
            id="a-zero-lead-time",
        ),
        pytest.param(
            {**_STOCKED, "supplier_lead_time_history": {"sup_a": 240.0}},
            "supplier_lead_time_history",
            id="a-history-not-a-list",
        ),
        pytest.param(
            {**_STOCKED, "sim_time": 1e-300, "demand_to_date": {"sku_0": 10**7}},
            "overflows",
            id="a-forecast-that-overflows",
        ),
    ],
)
def test_a_malformed_state_is_refused_naming_its_key_rather_than_read_as_absent(
    ctx: dict[str, Any], key: str
) -> None:
    with pytest.raises(ValueError, match=key):
        forecast_from_request(ctx)


def test_adr_058_records_every_constant_the_mapping_reads_with_its_value_and_provenance() -> None:
    """The ADR's table and the module agree, so a change to either cannot skip the other."""
    recorded = {
        row["name"]: (float(row["value"]), row["provenance"])
        for row in _CONSTANT_ROW.finditer(_ADR_058.read_text(encoding="utf-8"))
    }
    constants = {
        name: float(value)
        for name, value in vars(request_state).items()
        if name.isupper()
        and not name.startswith("_")
        and isinstance(value, int | float)
        and not isinstance(value, bool)
    }
    assert constants, "the module states no constant, so this pin would compare nothing"
    assert {name: value for name, (value, _) in recorded.items()} == constants
    assert {provenance for _, provenance in recorded.values()} <= {"chosen", "read", "definitional"}
