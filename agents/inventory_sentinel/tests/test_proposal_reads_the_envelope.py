"""Finding 112 through the protocol's real envelope: the Sentinel decides on its request.

The consensus protocol sends a proposal agent ``params={"decision_context": request}``
(``orchestrator/consensus/protocol.py:1040``). Every test here sends that envelope to
``handle_request`` over the real pipeline. Flat params are what hid the defect: a handler that
reads its keys one level too shallow passes a test that sends them (E-DQP-02). Requests are keyed
as ``uplift/consensus_arm.py::observation_to_decision_request`` keys them for E5 (ADR-058).
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agents.inventory_sentinel.a2a.handler import DEFAULT_SKU_IDS, InventorySentinelA2AHandler
from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline
from agents.inventory_sentinel.inference.request_state import (
    LEAD_TIME_PRIOR_MIN,
    REVIEW_PERIOD_MIN,
    forecast_from_request,
    reading_trace,
)
from agents.inventory_sentinel.models.newsvendor import newsvendor_quantity

#: The primary cell's SKUs and the supplier each is ordered from, as its requests name them.
_SUPPLIER_OF: dict[str, str] = {
    f"sku_{index}": ("sup_a", "sup_b", "sup_c")[index % 3] for index in range(10)
}


def _hour_six_request(skus: list[str], position: float = 30.0) -> dict[str, Any]:
    """Hour 6 of a primary-cell run: 17 events per SKU, and ``sup_c`` has landed no order yet."""
    stocked = sorted(skus)
    return {
        "sku_ids": skus,
        "inventory": {sku: int(position) for sku in stocked},
        "unit_costs": {sku: 1.0 for sku in stocked},
        "sim_time": 360.0,
        "delivery_count": 0,
        "spoilage_count": 0,
        "stockout_count": 0,
        "disruption_active": False,
        "requires_twin_simulation": False,
        "on_order": {},
        "inventory_position": {sku: position for sku in stocked},
        "demand_to_date": {sku: 17 for sku in stocked},
        "supplier_lead_time_history": {"sup_a": [190.0], "sup_b": [284.0], "sup_c": []},
        "sku_supplier": {sku: _SUPPLIER_OF[sku] for sku in stocked},
        "start_weekday": 2,
    }


def _envelope(request: dict[str, Any]) -> dict[str, Any]:
    """The JSON-RPC request the protocol sends a proposal agent."""
    return {
        "jsonrpc": "2.0",
        "method": "proposal",
        "params": {"decision_context": request},
        "id": "t",
    }


def _result(request: dict[str, Any]) -> dict[str, Any]:
    """The proposal the Sentinel returns for ``request``, sent through the real envelope."""
    response = InventorySentinelA2AHandler().handle_request(_envelope(request))
    assert "error" not in response, response.get("error")
    result: dict[str, Any] = response["result"]
    return result


def _actions(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Each proposed action, by SKU."""
    return {action["sku_id"]: action for action in _result(request)["payload"]["actions"]}


@given(skus=st.lists(st.sampled_from(sorted(_SUPPLIER_OF)), min_size=1, unique=True))
def test_a_proposal_names_exactly_the_skus_its_request_names_and_never_the_default(
    skus: list[str],
) -> None:
    actions = _result(_hour_six_request(skus))["payload"]["actions"]
    assert [action["sku_id"] for action in actions] == skus
    assert not set(DEFAULT_SKU_IDS) & {action["sku_id"] for action in actions}


def test_a_sku_whose_position_covers_its_window_demand_orders_nothing() -> None:
    """``sku_0`` expects about 12 events over 190 + 60 minutes and holds 900, so it orders none."""
    request = _hour_six_request(["sku_0", "sku_2"])
    request.update(
        inventory={"sku_0": 900, "sku_2": 0}, inventory_position={"sku_0": 900.0, "sku_2": 0.0}
    )
    actions = _actions(request)
    assert actions["sku_0"]["quantity"] == 0.0
    # sku_2's supplier has landed nothing, so its window is the prior plus R, at its own rate.
    mean = 17 / 360.0 * (LEAD_TIME_PRIOR_MIN + REVIEW_PERIOD_MIN)
    expected = newsvendor_quantity(mean, math.sqrt(mean))
    assert actions["sku_2"]["quantity"] == pytest.approx(expected, abs=0.01)


def test_stock_in_transit_counts_toward_the_position_an_order_is_sized_against() -> None:
    """The pathway probe's ``on_order`` contrast (``uplift/dispatch.py::withhold_input``)."""
    request = _hour_six_request(["sku_1"])
    request.update(
        inventory={"sku_1": 4}, on_order={"sku_1": 20.0}, inventory_position={"sku_1": 24.0}
    )
    withheld = {**request, "on_order": {}, "inventory_position": {"sku_1": 4.0}}
    mean = 17 / 360.0 * (284.0 + REVIEW_PERIOD_MIN)
    target = newsvendor_quantity(mean, math.sqrt(mean))
    in_transit = _actions(request)["sku_1"]["quantity"]
    told_nothing = _actions(withheld)["sku_1"]["quantity"]
    assert in_transit == pytest.approx(max(0.0, target - 24.0), abs=0.01)
    assert told_nothing == pytest.approx(target - 4.0, abs=0.01)
    assert told_nothing > in_transit


def test_confidence_is_the_poisson_spread_of_the_window_demand() -> None:
    """For a window of at least one event the confidence is ``1 - 0.5 / sqrt(mean)``.

    ``decide()`` computes ``1 - 0.5 * std / max(mean, 1)`` and the mapping sets
    ``std = sqrt(mean)``: the formula ADR-058 projects E5's escalations with, read off a real
    proposal.
    """
    action = _actions(_hour_six_request(["sku_0"]))["sku_0"]
    mean = 17 / 360.0 * (190.0 + REVIEW_PERIOD_MIN)
    assert action["confidence"] == pytest.approx(1.0 - 0.5 / math.sqrt(mean), abs=5e-4)


@pytest.mark.parametrize(
    "params",
    [
        pytest.param(_hour_six_request(["sku_0"]), id="the-request-sent-flat"),
        pytest.param({"decision_context": ["sku_0"]}, id="a-context-that-is-not-a-mapping"),
    ],
)
def test_params_without_the_envelope_are_refused_with_an_error_naming_decision_context(
    params: dict[str, Any],
) -> None:
    response = InventorySentinelA2AHandler().handle_request(
        {"jsonrpc": "2.0", "method": "proposal", "params": params, "id": "t"}
    )
    assert "result" not in response
    assert response["id"] == "t"
    assert response["error"]["code"] == -32602
    assert "decision_context" in response["error"]["message"]


def test_a_live_request_keeps_the_default_forecast_and_now_names_its_own_store() -> None:
    """``DecisionRequest.model_dump()`` (``orchestrator/inference/serve.py``) carries no state.

    So the action is the one ``decide()`` returns with no forecast, for the default SKU. Only the
    store is new: it is the request's, where the one-level-too-shallow read always gave the
    default.
    """
    live = {
        "order_id": "synthetic-1-1",
        "store_id": "STORE_MUM_001",
        "items": [{"sku_id": "SKU_BEV_001", "quantity": 2}],
        "agents_involved": [],
        "disruption_active": False,
        "requires_twin_simulation": False,
    }
    result = _result(live)
    today = InventorySentinelPipeline().decide(list(DEFAULT_SKU_IDS), "STORE_MUM_001")
    assert result["payload"]["actions"] == [action.model_dump(mode="json") for action in today]
    assert reading_trace(None, list(DEFAULT_SKU_IDS)) in result["justification_trace"]


def test_a_request_with_state_says_in_its_trace_that_the_state_was_read() -> None:
    request = _hour_six_request(["sku_0", "sku_2"])
    trace = _result(request)["justification_trace"]
    assert reading_trace(forecast_from_request(request), request["sku_ids"]) in trace
    assert any(line.startswith("Request state read") for line in trace)
