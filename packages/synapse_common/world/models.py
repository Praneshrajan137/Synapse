"""SYNAPSE World substrate — typed models for the standing agentic loop (ADR-052).

These are the payloads that cross the perceive/act boundary between the digital-twin
``WorldRuntime`` (the standing, ticking world) and the orchestrator's ``SensorLoop`` +
the agents' ``execute()`` actuation. Every one validates against
``proto/domain/world_{event,action}.schema.json`` (I-3) and serialises deterministically
via ``SynapseBaseModel`` (I-13).

Honesty premise (ADR-052): the world is a *simulation*. ``WorldState.is_synthetic`` is
always set so no downstream surface can mistake a simulated reading for a real-store one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from synapse_common.models import SynapseBaseModel


class WorldEventKind(StrEnum):
    """What the world is reporting. Drives the SensorLoop's condition detectors."""

    DEMAND_ARRIVAL = "demand_arrival"
    STOCKOUT_RISK = "stockout_risk"
    SPOILAGE_RISK = "spoilage_risk"
    DISRUPTION = "disruption"
    RESTOCK = "restock"


class WorldActionKind(StrEnum):
    """What an agent is doing to the world on ``execute()`` (actuation)."""

    SET_POLICY = "set_policy"  # dispatch_speed / restock_threshold / order_qty_mult levers
    REORDER = "reorder"  # inject stock for a SKU
    SET_PRICE_MULT = "set_price_mult"  # scale demand via the price lever
    INJECT_DISRUPTION = "inject_disruption"  # failure / lead-time / spoilage shock


class WorldEvent(SynapseBaseModel):
    """One thing the world reports — a demand arrival, a stockout risk, a disruption.

    ``event_id`` is set explicitly by the producer (deterministic for ``SimWorldSource``)
    rather than randomly, so a seeded source replays identically (the determinism the
    sensor's tests rely on).
    """

    event_id: str
    kind: WorldEventKind
    city: str
    sim_time_min: float = Field(ge=0.0, description="Simulation clock minute the event occurred.")
    store_id: str | None = None
    sku_id: str | None = None
    quantity: float | None = Field(default=None, description="Units (demand / restock amount).")
    severity: float = Field(default=0.0, ge=0.0, le=1.0, description="0=informational, 1=critical.")
    detail: dict[str, float] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorldAction(SynapseBaseModel):
    """A concrete mutation an agent applies to the world (the actuation payload)."""

    action_id: str
    kind: WorldActionKind
    city: str
    store_id: str | None = None
    sku_id: str | None = None
    params: dict[str, float] = Field(default_factory=dict)
    decision_id: str | None = Field(default=None, description="Correlates the act to a decision.")


class WorldState(SynapseBaseModel):
    """A perceive snapshot of one city's world — what the SensorLoop and agents read.

    Vocabulary mirrors ``SupplyChainGymEnv._get_obs`` + ``SimulationMetrics.to_dict`` so the
    standing world and the offline RL env describe the same world the same way.
    """

    city: str
    sim_time_min: float = Field(ge=0.0)
    inventory: dict[str, float] = Field(default_factory=dict, description="Per-SKU stock level.")
    pending_orders: int = Field(default=0, ge=0)
    fill_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    spoilage_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_delivery_min: float = Field(default=0.0, ge=0.0)
    restocks_triggered: int = Field(default=0, ge=0)
    demand_rate: float = Field(default=0.0, ge=0.0, description="Poisson λ, orders/min.")
    clock_advancing: bool = Field(default=True, description="False ⇒ degraded (I-7).")
    is_synthetic: bool = Field(default=True, description="Always true — the world is a sim.")
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))
