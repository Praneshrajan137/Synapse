"""Property-based tests for universal real actuation across the lever agents (ADR-052).

Implementation under test: the converted ``execute()`` of the five lever agents
(``pricing_oracle``, ``demand_prophet``, ``routing_navigator``, ``disruption_shield``,
``freshness_guardian``) in ``agents/<agent>/a2a/handler.py``. Each builds one
``WorldAction`` per actionable item, applies it through the injected actuator, and
reports the result under the shared *uniform honest status rule* in
``synapse_common.world.actuation``.

This module implements the design's actuation properties:

  * Property 11 — One ``WorldAction`` per actionable item (Validates: Requirements 5.1)
  * Property 12 — Actuation levers stay within the world's accepted range
    (Validates: Requirements 5.2, 5.3, 5.4, 5.5)
  * Property 13 — An applied effect yields an honest ``"executed"`` status
    (Validates: Requirements 5.6)
  * Property 14 — ``kafka_published`` reflects a real produce (Validates: Requirements 5.7)
  * Property 15 — Actuation routes to the request's city (Validates: Requirements 5.8)
  * Property 17 — Unavailable world and Kafka degrade honestly
    (Validates: Requirements 5.9, 5.10, 6.4, 6.5, 7.1, 7.2, 7.4, 10.7)

The properties are parametrized across the lever agents. A recording in-memory actuator
and fake Kafka producers drive deterministic outcomes over schema-valid ratified payloads
built per agent.

The example budget is inherited from the active Hypothesis profile (see the root
``conftest.py``): ``dev`` (10), ``default``/``ci`` (500), ``nightly`` (5_000). Select one
with ``HYPOTHESIS_PROFILE=dev`` or ``--hypothesis-profile=nightly``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError:  # hypothesis is optional in some environments
    pytest.skip("hypothesis not installed", allow_module_level=True)

if TYPE_CHECKING:
    from collections.abc import Callable

    from hypothesis.strategies import DrawFn
    from synapse_common.world.models import WorldAction

# ---------------------------------------------------------------------------
# Lazy handler imports.
#
# Each lever-agent handler is imported independently and guarded: an environment
# missing one agent's optional inference dependency skips *that* agent rather than
# erroring the whole module, while the pure actuation paths of the other agents
# stay covered. ``execute()`` never touches the pipeline, so a lightweight dummy
# pipeline keeps construction free of any heavy serving model.
# ---------------------------------------------------------------------------
_HANDLERS: dict[str, Any] = {}

try:
    from agents.pricing_oracle.a2a.handler import PricingOracleA2AHandler

    _HANDLERS["pricing_oracle"] = PricingOracleA2AHandler
except ImportError:  # pragma: no cover - optional dependency guard
    pass

try:
    from agents.demand_prophet.a2a.handler import DemandProphetA2AHandler

    _HANDLERS["demand_prophet"] = DemandProphetA2AHandler
except ImportError:  # pragma: no cover - optional dependency guard
    pass

try:
    from agents.routing_navigator.a2a.handler import RoutingNavigatorA2AHandler

    _HANDLERS["routing_navigator"] = RoutingNavigatorA2AHandler
except ImportError:  # pragma: no cover - optional dependency guard
    pass

try:
    from agents.disruption_shield.a2a.handler import DisruptionShieldA2AHandler

    _HANDLERS["disruption_shield"] = DisruptionShieldA2AHandler
except ImportError:  # pragma: no cover - optional dependency guard
    pass

try:
    from agents.freshness_guardian.a2a.handler import FreshnessGuardianA2AHandler

    _HANDLERS["freshness_guardian"] = FreshnessGuardianA2AHandler
except ImportError:  # pragma: no cover - optional dependency guard
    pass


# A truthy stand-in: ``execute()`` is pure actuation and never uses the pipeline, so a
# bare object keeps handler construction free of the real serving dependencies.
_DUMMY_PIPELINE: Any = cast("Any", object())


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
class RecordingActuator:
    """In-memory actuator that records every ``WorldAction`` it is asked to apply.

    When ``applied`` is true it echoes the action's params back as a non-empty effect
    (so the uniform honest rule reads a real applied effect → ``"executed"``). When
    false it models an unreachable world the honest way the production ``WorldActuator``
    does — ``{"applied": False, ...}`` with no fabricated effect — and never raises.
    """

    def __init__(self, *, applied: bool = True) -> None:
        self.calls: list[WorldAction] = []
        self._applied = applied

    def apply(self, action: WorldAction) -> dict[str, Any]:
        self.calls.append(action)
        if self._applied:
            return {"applied": True, "result": {"effect": dict(action.params)}}
        return {"applied": False, "error": "world unavailable"}


class SpyProducer:
    """A Kafka producer fake that records every successful ``produce`` call."""

    def __init__(self) -> None:
        self.produced: list[tuple[str, Any, str | None]] = []

    def produce(self, topic: str, value: Any, key: str | None = None, headers: Any = None) -> None:
        self.produced.append((topic, value, key))


class RaisingProducer:
    """A Kafka producer fake whose ``produce`` always raises (a Kafka outage)."""

    def produce(self, *_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("kafka down")


# ---------------------------------------------------------------------------
# Schema-valid payload builders (one actionable item maps to one WorldAction)
# ---------------------------------------------------------------------------
_STORE = "STORE_BLR_001"
_TS = "2025-01-01T00:00:00Z"


def _exec_params(payload: dict[str, Any], city: str | None) -> dict[str, Any]:
    """Wrap a ratified payload in the consensus_action envelope ``execute()`` expects."""
    params: dict[str, Any] = {
        "decision_id": "d1",
        "ratified_proposal": {"payload": payload},
    }
    if city is not None:
        params["city"] = city
    return params


def _pricing_update(sku: str, multiplier: float) -> dict[str, Any]:
    """A schema-valid ``pricing_update`` sub-object (multiplier in [0.5, 2.0] is actionable)."""
    base_price = 100.0
    return {
        "pricing_id": f"pid-{sku}",
        "sku_id": sku,
        "store_id": _STORE,
        "category": "staples",
        "base_price": base_price,
        "multiplier": multiplier,
        "final_price": base_price * multiplier,
        "is_essential": False,
        "elasticity_source": "correlation_fallback",
        "timestamp": _TS,
        "confidence": 0.8,
    }


def _forecast(sku: str, point: float) -> dict[str, Any]:
    """A schema-valid ``demand_forecast`` (positive 15min point demand is actionable)."""
    lower = point / 2.0 if point > 0.0 else 0.0
    return {
        "sku_id": sku,
        "store_id": _STORE,
        "forecast_timestamp": _TS,
        "horizons": {"15min": point},
        "lower_90": {"15min": lower},
        "upper_90": {"15min": point + 1.0},
        "confidence": 0.8,
        "drift_detected": False,
    }


def _route(idx: int, total_time_min: float) -> dict[str, Any]:
    """A schema-valid ``route_plan`` (every route is an actionable dispatch item)."""
    return {
        "route_id": f"rid-{idx}",
        "rider_id": f"R-{idx}",
        "store_id": _STORE,
        "stops": [{"seq": 0}],
        "total_distance_km": 5.0,
        "total_time_min": total_time_min,
    }


def _disruption_payload(alert_level: int) -> dict[str, Any]:
    """A schema-valid ``disruption_alert`` (alert_level 1..10 is a single actionable item)."""
    return {
        "alert_id": "aid-1",
        "alert_level": alert_level,
        "anomaly_scores": {
            "isolation_forest": 0.5,
            "lstm_autoencoder": 0.5,
            "gnn_structural": 0.5,
            "ensemble_weighted": 0.5,
        },
        "affected_nodes": ["node_0"],
        "disruption_type": "supplier_delay",
        "playbook_id": "PB-1",
        "playbook_actions": "reroute",
        "reasoning_chain": "ensemble anomaly above threshold",
        "timestamp": _TS,
        "confidence": 0.7,
    }


def _freshness_alert(sku: str, markdown_applied: bool, markdown_pct: float) -> dict[str, Any]:
    """A schema-valid ``freshness_alert`` (``markdown_applied`` makes it actionable)."""
    return {
        "alert_id": f"aid-{sku}",
        "store_id": _STORE,
        "sku_id": sku,
        "days_to_expiry": 2.0,
        "quality_score": 0.6,
        "markdown_applied": markdown_applied,
        "markdown_pct": markdown_pct,
        "fssai_compliant": True,
        "timestamp": _TS,
        "confidence": 0.7,
    }


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
_city_st = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=10)
_mult_st = st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False)
_point_st = st.floats(min_value=0.5, max_value=100.0, allow_nan=False, allow_infinity=False)
_time_st = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
_pct_st = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


@dataclass(frozen=True)
class Case:
    """One generated actuation scenario: a ratified payload, its city, and its expectations."""

    payload: dict[str, Any]
    actionable: int  # the number of WorldActions the handler should apply
    city: str


@st.composite
def _pricing_case(draw: DrawFn) -> Case:
    city = draw(_city_st)
    mults = draw(st.lists(_mult_st, min_size=1, max_size=4))
    updates = [_pricing_update(f"sku_{i}", round(m, 6)) for i, m in enumerate(mults)]
    return Case({"updates": updates}, len(updates), city)


@st.composite
def _demand_case(draw: DrawFn) -> Case:
    city = draw(_city_st)
    n = draw(st.integers(min_value=1, max_value=4))
    flags = [draw(st.booleans()) for _ in range(n)]
    if not any(flags):  # guarantee at least one actionable forecast
        flags[0] = True
    forecasts: list[dict[str, Any]] = []
    actionable = 0
    for i, active in enumerate(flags):
        point = round(draw(_point_st), 6) if active else 0.0
        forecasts.append(_forecast(f"sku_{i}", point))
        if active:
            actionable += 1
    return Case({"forecasts": forecasts}, actionable, city)


@st.composite
def _routing_case(draw: DrawFn) -> Case:
    city = draw(_city_st)
    times = draw(st.lists(_time_st, min_size=1, max_size=4))
    routes = [_route(i, round(t, 6)) for i, t in enumerate(times)]
    return Case({"routes": routes}, len(routes), city)


@st.composite
def _disruption_case(draw: DrawFn) -> Case:
    city = draw(_city_st)
    level = draw(st.integers(min_value=1, max_value=10))
    return Case(_disruption_payload(level), 1, city)


@st.composite
def _freshness_case(draw: DrawFn) -> Case:
    city = draw(_city_st)
    n = draw(st.integers(min_value=1, max_value=4))
    flags = [draw(st.booleans()) for _ in range(n)]
    if not any(flags):  # guarantee at least one spoilage-relevant (actionable) alert
        flags[0] = True
    alerts: list[dict[str, Any]] = []
    actionable = 0
    for i, applied in enumerate(flags):
        pct = round(draw(_pct_st), 6)
        alerts.append(_freshness_alert(f"sku_{i}", applied, pct))
        if applied:
            actionable += 1
    return Case({"alerts": alerts}, actionable, city)


# ---------------------------------------------------------------------------
# Per-agent specs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AgentSpec:
    """Everything the parametrized properties need to drive one lever agent."""

    name: str
    kind_value: str  # the WorldActionKind.value the agent's actions must carry
    lever_key: str  # the params key the lever value lives under
    in_range: Callable[[float], bool]  # the world's accepted range for that lever
    case: Callable[[], st.SearchStrategy[Case]]
    empty_payload: dict[str, Any]  # a schema-shaped payload with no actionable item


_ALL_SPECS: dict[str, AgentSpec] = {
    "pricing_oracle": AgentSpec(
        "pricing_oracle",
        "set_price_mult",
        "price_mult",
        lambda v: v > 0.0,
        _pricing_case,
        {"updates": []},
    ),
    "demand_prophet": AgentSpec(
        "demand_prophet",
        "set_policy",
        "demand_mult",
        lambda v: v >= 0.01,
        _demand_case,
        {"forecasts": []},
    ),
    "routing_navigator": AgentSpec(
        "routing_navigator",
        "set_policy",
        "dispatch_speed",
        lambda v: v >= 0.1,
        _routing_case,
        {"routes": []},
    ),
    "disruption_shield": AgentSpec(
        "disruption_shield",
        "set_policy",
        "lead_time_mult",
        lambda v: v >= 0.1,
        _disruption_case,
        {},
    ),
    "freshness_guardian": AgentSpec(
        "freshness_guardian",
        "set_policy",
        "dispatch_speed",
        lambda v: v >= 0.1,
        _freshness_case,
        {"alerts": []},
    ),
}

# Only exercise agents whose handler imported in this environment (R: optional deps).
AGENTS: dict[str, AgentSpec] = {k: v for k, v in _ALL_SPECS.items() if k in _HANDLERS}
AGENT_KEYS: list[str] = sorted(AGENTS)

if not AGENT_KEYS:  # pragma: no cover - every lever handler failed to import
    pytest.skip("no lever-agent handlers importable", allow_module_level=True)


def _make_handler(name: str, actuator: Any, producer: Any) -> Any:
    """Construct a lever-agent handler with a dummy pipeline and injected dependencies."""
    return _HANDLERS[name](pipeline=_DUMMY_PIPELINE, actuator=actuator, kafka_producer=producer)


# ---------------------------------------------------------------------------
# Property 11: One WorldAction per actionable item
# Validates: Requirements 5.1
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("agent", AGENT_KEYS)
@given(data=st.data())
@settings()
def test_property11_one_world_action_per_actionable_item(agent: str, data: Any) -> None:
    """The handler applies exactly one mapped ``WorldAction`` per actionable item.

    **Validates: Requirements 5.1**
    """
    spec = AGENTS[agent]
    case = data.draw(spec.case())
    actuator = RecordingActuator(applied=True)
    handler = _make_handler(agent, actuator, SpyProducer())

    handler.execute(_exec_params(case.payload, case.city))

    assert len(actuator.calls) == case.actionable
    assert all(action.kind.value == spec.kind_value for action in actuator.calls)


# ---------------------------------------------------------------------------
# Property 12: Actuation levers stay within the world's accepted range
# Validates: Requirements 5.2, 5.3, 5.4, 5.5
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("agent", AGENT_KEYS)
@given(data=st.data())
@settings()
def test_property12_actuation_lever_within_range(agent: str, data: Any) -> None:
    """Every applied ``WorldAction`` carries its lever within the world's accepted range.

    **Validates: Requirements 5.2, 5.3, 5.4, 5.5**
    """
    spec = AGENTS[agent]
    case = data.draw(spec.case())
    actuator = RecordingActuator(applied=True)
    handler = _make_handler(agent, actuator, SpyProducer())

    handler.execute(_exec_params(case.payload, case.city))

    for action in actuator.calls:
        assert spec.lever_key in action.params
        assert spec.in_range(action.params[spec.lever_key])


# ---------------------------------------------------------------------------
# Property 13: An applied effect yields an honest "executed" status
# Validates: Requirements 5.6
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("agent", AGENT_KEYS)
@given(data=st.data())
@settings()
def test_property13_applied_effect_yields_executed(agent: str, data: Any) -> None:
    """When the world applies a non-empty effect for >=1 item, status is ``"executed"``.

    **Validates: Requirements 5.6**
    """
    spec = AGENTS[agent]
    case = data.draw(spec.case())
    actuator = RecordingActuator(applied=True)
    handler = _make_handler(agent, actuator, SpyProducer())

    result = handler.execute(_exec_params(case.payload, case.city))

    assert result["status"] == "executed"
    # The reported world_effects carry the real applied effect (R7.4).
    assert any(effect.get("applied") for effect in result["world_effects"])


# ---------------------------------------------------------------------------
# Property 14: kafka_published reflects a real produce
# Validates: Requirements 5.7
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("agent", AGENT_KEYS)
@pytest.mark.parametrize("producer_kind", ["working", "absent", "raising"])
@given(data=st.data())
@settings()
def test_property14_kafka_published_reflects_real_produce(
    agent: str, producer_kind: str, data: Any
) -> None:
    """``kafka_published`` is True iff a produce actually succeeded — never a bare True.

    **Validates: Requirements 5.7**
    """
    spec = AGENTS[agent]
    case = data.draw(spec.case())
    actuator = RecordingActuator(applied=True)  # ensures there are applied items to publish

    producer: Any
    if producer_kind == "working":
        producer = SpyProducer()
        expected = True
    elif producer_kind == "absent":
        producer = None
        expected = False
    else:
        producer = RaisingProducer()
        expected = False

    handler = _make_handler(agent, actuator, producer)
    result = handler.execute(_exec_params(case.payload, case.city))

    assert result["kafka_published"] is expected
    if producer_kind == "working":
        assert producer.produced  # a real produce really happened


# ---------------------------------------------------------------------------
# Property 15: Actuation routes to the request's city
# Validates: Requirements 5.8
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("agent", AGENT_KEYS)
@given(data=st.data())
@settings()
def test_property15_actuation_routes_to_city(agent: str, data: Any) -> None:
    """Every ``WorldAction`` the handler builds carries the request's city.

    **Validates: Requirements 5.8**
    """
    spec = AGENTS[agent]
    case = data.draw(spec.case())
    actuator = RecordingActuator(applied=True)
    handler = _make_handler(agent, actuator, SpyProducer())

    result = handler.execute(_exec_params(case.payload, case.city))

    assert result["city"] == case.city
    assert actuator.calls  # at least one action was built
    assert all(action.city == case.city for action in actuator.calls)


# ---------------------------------------------------------------------------
# Property 17: Unavailable world and Kafka degrade honestly (degradation property)
# Validates: Requirements 5.9, 5.10, 6.4, 6.5, 7.1, 7.2, 7.4, 10.7
# ---------------------------------------------------------------------------
_DEGRADE_SCENARIOS = [
    "world_down_no_kafka",  # world unreachable + absent producer (R7.1/R7.2)
    "world_down_kafka_raises",  # world unreachable + Kafka outage (R7.1/R7.2)
    "missing_city",  # no routable World_Runtime (R5.9)
    "no_actionable",  # nothing actionable for the lever (R5.10)
]


@pytest.mark.parametrize("agent", AGENT_KEYS)
@pytest.mark.parametrize("scenario", _DEGRADE_SCENARIOS)
@given(data=st.data())
@settings()
def test_property17_unavailable_world_and_kafka_degrade_honestly(
    agent: str, scenario: str, data: Any
) -> None:
    """A converted ``execute()`` invoked with an unavailable world and Kafka degrades honestly.

    The result is never ``"executed"``, sets ``kafka_published`` to ``False``, reports no
    world effect that did not occur (every reported effect is unapplied and empty), and
    returns without propagating an exception.

    **Validates: Requirements 5.9, 5.10, 6.4, 6.5, 7.1, 7.2, 7.4, 10.7**
    """
    spec = AGENTS[agent]

    actuator: Any
    producer: Any
    if scenario == "world_down_no_kafka":
        case = data.draw(spec.case())
        actuator = RecordingActuator(applied=False)
        producer = None
        params = _exec_params(case.payload, case.city)
    elif scenario == "world_down_kafka_raises":
        case = data.draw(spec.case())
        actuator = RecordingActuator(applied=False)
        producer = RaisingProducer()
        params = _exec_params(case.payload, case.city)
    elif scenario == "missing_city":
        case = data.draw(spec.case())
        actuator = RecordingActuator(applied=True)
        producer = None
        params = _exec_params(case.payload, "")  # R5.9: unroutable / missing city
    else:  # no_actionable
        city = data.draw(_city_st)
        actuator = RecordingActuator(applied=True)
        producer = None
        params = _exec_params(spec.empty_payload, city)  # R5.10: no actionable item

    handler = _make_handler(agent, actuator, producer)

    # The call must complete without propagating an exception (I-7).
    result = handler.execute(params)

    assert result["status"] != "executed"
    assert result["kafka_published"] is False
    # No fabricated world effect: every reported effect is honestly unapplied and empty.
    for effect in result["world_effects"]:
        assert not effect.get("applied")
        assert not effect.get("effect")


# ---------------------------------------------------------------------------
# Example-based edge cases (complement the properties above)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("agent", AGENT_KEYS)
def test_missing_city_never_touches_the_world(agent: str) -> None:
    """A missing city diverges before any ``WorldAction`` is applied (R5.9)."""
    spec = AGENTS[agent]
    actuator = RecordingActuator(applied=True)
    handler = _make_handler(agent, actuator, SpyProducer())

    # An empty-but-shaped payload with an empty city: the city guard fires first.
    result = handler.execute(_exec_params(spec.empty_payload, ""))

    assert result["status"] == "diverged"
    assert actuator.calls == []
    assert result["world_effects"] == []
    assert result["kafka_published"] is False
