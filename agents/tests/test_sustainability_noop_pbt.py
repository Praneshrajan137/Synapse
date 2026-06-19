"""Property-based test for the sustainability Honest No-Op (ADR-052, R6.1/R6.2).

Implementation under test: ``SustainabilityAgentA2AHandler.execute`` in
``agents/sustainability_agent/a2a/handler.py``. The ``carbon_efficiency`` objective
has **no** natural world-mutation lever in the standing ``WorldRuntime``, so the
handler is an *Honest No-Op*: it constructs no fabricated effect, never returns
``"executed"``, applies nothing to the world, and only event-sources a truthful
record of the no-op through Kafka.

This module implements **Property 16** from the design document:

  * Property 16 — Honest No-Op leaves the world unchanged
    (Validates: Requirements 6.1, 6.2)

The example budget is inherited from the active Hypothesis profile (see the root
``conftest.py``): ``dev`` (10), ``default``/``ci`` (500), ``nightly`` (5_000).
Select one with ``HYPOTHESIS_PROFILE=dev`` or ``--hypothesis-profile=nightly``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError:  # hypothesis is optional in some environments
    pytest.skip("hypothesis not installed", allow_module_level=True)

# Lazy import: importing the handler pulls in the sustainability package. Guard it
# so an environment missing an optional serving dependency skips rather than errors.
try:
    from agents.sustainability_agent.a2a.handler import (
        CARBON_TOPIC,
        SustainabilityAgentA2AHandler,
    )
except ImportError as exc:  # pragma: no cover - optional dependency guard
    pytest.skip(f"sustainability handler unavailable: {exc}", allow_module_level=True)

if TYPE_CHECKING:
    from hypothesis.strategies import DrawFn

    from agents.sustainability_agent.inference.pipeline import SustainabilityPipeline


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
class _SpyProducer:
    """A fake Kafka producer that records every event-source ``produce`` call.

    The handler's only side-effect channel is this producer; recording the calls
    lets the property assert that the *only* thing emitted is an honest no-op
    record (never a world mutation).
    """

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def produce(self, topic: str, *, value: dict[str, Any], key: str | None = None) -> None:
        self.messages.append({"topic": topic, "value": value, "key": key})


class _FakePipeline:
    """A truthy stand-in for ``SustainabilityPipeline``.

    ``execute()`` never touches the pipeline (it is an Honest No-Op), so passing a
    lightweight fake keeps the test free of the real pipeline's serving model and
    any optional inference dependency.
    """


def _fake_pipeline() -> SustainabilityPipeline:
    """A ``_FakePipeline`` typed as the real pipeline (never used by ``execute()``)."""
    return cast("SustainabilityPipeline", _FakePipeline())


def _make_handler() -> tuple[SustainabilityAgentA2AHandler, _SpyProducer]:
    producer = _SpyProducer()
    handler = SustainabilityAgentA2AHandler(_fake_pipeline(), kafka_producer=producer)
    return handler, producer


# ---------------------------------------------------------------------------
# Strategies — arbitrary valid consensus_action inputs
# ---------------------------------------------------------------------------
_city_st = st.one_of(
    st.sampled_from(["bengaluru", "mumbai", "delhi", "chennai", "unknown_city", ""]),
    st.text(max_size=12),
)
_decision_id_st = st.one_of(
    st.builds(lambda: str(uuid4())),
    st.text(min_size=1, max_size=16),
    st.integers(min_value=0, max_value=10_000),
)
_json_scalar_st = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(max_size=8),
    st.booleans(),
    st.none(),
)


@st.composite
def _consensus_actions(draw: DrawFn) -> dict[str, Any]:
    """A consensus_action dict with optional ``decision_id``/``city`` plus noise keys.

    Covers present/absent identity fields and arbitrary extra payload entries so the
    property exercises the no-op across the realistic input space (R6.1/R6.2).
    """
    action: dict[str, Any] = {}
    if draw(st.booleans()):
        action["decision_id"] = draw(_decision_id_st)
    if draw(st.booleans()):
        action["city"] = draw(_city_st)
    # Arbitrary extra keys — a carbon lever does not exist, so none of these can
    # ever cause a world mutation or an "executed" status.
    extra = draw(st.dictionaries(st.text(min_size=1, max_size=8), _json_scalar_st, max_size=4))
    action.update(extra)
    return action


# ---------------------------------------------------------------------------
# Property 16: Honest No-Op leaves the world unchanged
# Validates: Requirements 6.1, 6.2
# ---------------------------------------------------------------------------
@given(action=_consensus_actions())
@settings()
def test_property16_honest_noop_leaves_world_unchanged(action: dict[str, Any]) -> None:
    """For any valid consensus_action, the sustainability ``execute()``:

    * never returns status ``"executed"`` — it is always ``"diverged"`` (R6.2),
    * reports an empty ``world_effects`` (no fabricated world change, R6.1),
    * reports ``reason == "no_carbon_lever"``,
    * exposes **no** actuator/world seam that could mutate the standing world, and
    * emits only an honest no-op event-source record (never a world action).
    """
    handler, producer = _make_handler()

    # There is no actuation seam at all: the handler holds no actuator/world client,
    # so it is structurally incapable of mutating the standing WorldRuntime (R6.1).
    assert getattr(handler, "_actuator", None) is None

    result = handler.execute(action)

    # Honest status: always diverged, never executed (R6.2).
    assert result["status"] == "diverged"
    assert result["status"] != "executed"

    # No fabricated world effect — the world observed via perceive() is unchanged (R6.1).
    assert result["world_effects"] == []

    # Honest divergence reason for the missing carbon lever (R6.2).
    assert result["reason"] == "no_carbon_lever"
    assert result["agent"] == "sustainability_agent"

    # The only side effect is a truthful event-source record: it targets the carbon
    # topic and itself reports the no-op (empty world_effects, diverged) — never a
    # world mutation. With a working producer the produce really happened (R5.7).
    assert result["kafka_published"] is True
    assert len(producer.messages) == 1
    record = producer.messages[0]
    assert record["topic"] == CARBON_TOPIC
    assert record["value"]["status"] == "diverged"
    assert record["value"]["world_effects"] == []
    assert record["value"]["reason"] == "no_carbon_lever"


# ---------------------------------------------------------------------------
# Example-based edge cases (complement the property above)
# ---------------------------------------------------------------------------
def test_noop_with_empty_action_diverges_honestly() -> None:
    """An empty consensus_action still yields an honest no-op (defaults applied)."""
    handler, producer = _make_handler()

    result = handler.execute({})

    assert result["status"] == "diverged"
    assert result["world_effects"] == []
    assert result["reason"] == "no_carbon_lever"
    # decision_id/city are defaulted, not fabricated into a world effect.
    assert "decision_id" in result
    assert result["city"] == ""
    assert len(producer.messages) == 1


def test_noop_without_producer_is_still_honest() -> None:
    """With no Kafka producer the no-op holds: diverged, empty effect, no exception.

    ``kafka_published`` degrades honestly to ``False`` (no produce happened) and the
    world is still untouched (R6.1, honest degradation I-7).
    """
    handler = SustainabilityAgentA2AHandler(_fake_pipeline(), kafka_producer=None)

    result = handler.execute({"decision_id": "d-1", "city": "bengaluru"})

    assert result["status"] == "diverged"
    assert result["world_effects"] == []
    assert result["reason"] == "no_carbon_lever"
    assert result["kafka_published"] is False


def test_noop_survives_kafka_outage_without_raising() -> None:
    """A producer that raises on ``produce`` degrades to ``kafka_published=False``.

    The world is never mutated and the exception never propagates (I-7); the result
    is still an honest divergence.
    """

    class _BrokenProducer:
        def produce(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("kafka down")

    handler = SustainabilityAgentA2AHandler(_fake_pipeline(), kafka_producer=_BrokenProducer())

    result = handler.execute({"decision_id": "d-2", "city": "mumbai"})

    assert result["status"] == "diverged"
    assert result["world_effects"] == []
    assert result["reason"] == "no_carbon_lever"
    assert result["kafka_published"] is False
