"""SYNAPSE World substrate — typed models for the standing agentic loop (ADR-052).

These are the payloads that cross the perceive/act boundary between the digital-twin
``WorldRuntime`` (the standing, ticking world) and the orchestrator's ``SensorLoop`` +
the agents' ``execute()`` actuation. Every one validates against
``proto/domain/world_{event,action}.schema.json`` (I-3) and serialises deterministically
via ``SynapseBaseModel`` (I-13).

Honesty premise (ADR-052): no downstream surface may mistake a simulated reading for a
real-store one. Until the purpose-achievement audit, that premise was carried by
``WorldState.is_synthetic`` being *pinned* to ``True`` — a self-declaration that could
not become false even if the world were genuinely externally driven, and that therefore
proved nothing either way. Design **AD-11** replaces the pin: ``is_synthetic`` is now
**derived** from :class:`SourceProvenance`, the declared class of the active
``WorldSource`` (R4.2). The flag can only say "real" when a source that actually reads
an external feed is driving the world.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, computed_field

from synapse_common.models import SynapseBaseModel


class SourceProvenance(StrEnum):
    """Where a ``WorldSource``'s arrivals come from — the origin of world truth (AD-11).

    Defined here rather than in ``synapse_common.world.source`` (its documented home in
    the design's data-model table) purely to keep the import graph acyclic: ``source.py``
    already imports this module, so the enum lives with the model that derives from it and
    ``source.py`` **re-exports it**. Every import path — ``from synapse_common.world.source
    import SourceProvenance`` included — therefore works. This is the same arrangement
    ``synapse_common.models`` / ``synapse_common.provenance`` uses for the output-provenance
    value objects, and the reason is recorded there too.

    The three values are the committed tuple ``orchestrator.audit.models.SOURCE_CLASSES``
    (task 7.8) and the ``CHECK`` constraint in
    ``orchestrator/audit/migrations/0007_decision_data_provenance.sql``. They must not
    drift: a fourth class here would be rejected by Postgres at INSERT time.

    * ``SEEDED``   — a deterministic generator (``SimWorldSource``). Synthetic.
    * ``EXTERNAL`` — arrivals genuinely read off an external feed. Not synthetic.
    * ``STUB``     — a source that cannot produce arrivals at all (an unconditionally
      empty ``poll_arrivals``, R4.8). Neither real nor a simulation of anything: a stub
      world carries no demand, which is why a stub-driven runtime degrades rather than
      presenting an empty world as a healthy one.
    """

    SEEDED = "SEEDED"
    EXTERNAL = "EXTERNAL"
    STUB = "STUB"


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
    source_class: SourceProvenance = Field(
        default=SourceProvenance.SEEDED,
        description="Declared class of the WorldSource that produced this state (AD-11).",
    )
    degraded: bool = Field(
        default=False,
        description="True ⇒ this reading is incomplete; see degraded_reason (I-7).",
    )
    degraded_reason: str | None = Field(
        default=None,
        description="Why the state is degraded (unreachable feed, absent inventory, ...).",
    )
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_synthetic(self) -> bool:
        """Whether this reading came from a seeded generator — **derived, never pinned**.

        AD-11 / R4.2 / Property 28: ``is_synthetic`` is true *iff* the active source is
        ``SEEDED``. It is a computed field rather than a stored one precisely so no caller
        can assert it: there is no ``is_synthetic=`` keyword to pass, so the only way to
        make the world report "not synthetic" is to drive it with a source that declares a
        non-seeded provenance. The previous literal ``True`` default made the honest case
        unrepresentable; a literal ``False`` would have made the dishonest case free.

        ``STUB`` reports false because a stub is not a seeded generator — and a stub-driven
        runtime is always ``degraded``, so "not synthetic" can never be read as "real
        demand" without also reading the degradation that sits next to it.

        The default ``source_class`` is ``SEEDED``, the conservative direction: a caller
        that declares nothing gets the *synthetic* claim, never the real one.
        """
        return self.source_class is SourceProvenance.SEEDED
