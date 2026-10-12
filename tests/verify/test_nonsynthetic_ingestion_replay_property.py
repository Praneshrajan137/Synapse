# ruff: noqa: E501 - the Property 29 tag comment is required verbatim and is 122 characters
# wide; every other line in this file is kept inside the 100-column limit.
"""Property-based test for faithful non-synthetic ingestion and deterministic replay.

Feature: purpose-achievement-audit, Property 29: Non-synthetic input is ingested faithfully
and replays deterministically

    *For any* demand record that did not originate from a seeded generator, the perceived
    state incorporates the published quantity unchanged within one clock step; and *for
    any* non-synthetic input trace, replaying it convenes the same set of decision
    identifiers in the same order.

Why this file exists. Requirement 4's finding was that the closed autonomy loop had only
ever run on its own seeded simulation. Task 10.11 built the missing hop
(``ExternalFeedSource``) and task 10.12 proved the *flag* derives from the active source.
Neither states the thing R4.1 and R4.6 actually ask for, which is a statement about the
**composition**: that a record an operator published reaches a decision *as published* -
no coercion, no substitution, no seeded padding - and that replaying the same input
convenes the same decisions in the same order. That composition is what this file drives,
end to end, in one flow: published records -> ``ExternalFeedSource`` -> ``WorldRuntime``
tick -> the real ``SupplyChainSimulation`` -> ``perceive()`` -> ``SensorLoop`` -> a
convened decision -> an append-only provenance row.

What the three siblings already cover, and what this file therefore does not restate
------------------------------------------------------------------------------------

* ``tests/verify/test_world_provenance_derivation_property.py`` (Property 28, pure) -
  ``is_synthetic`` is a function of the active source and of nothing else; a stub is a stub
  however it is named; a configured-but-unreachable feed degrades with zero arrivals over
  six failure modes; classification is total over generated implementations. It never boots
  the twin (it *parses* the two twin modules). So this file asserts nothing about
  classification, about the unreachable feed, or about the absent-inventory degradation:
  its subject is the reachable feed whose records must survive the whole way to a decision.
* ``packages/tests/test_external_feed_source.py`` (the four wiring states, by example) -
  unconfigured, unreachable, reachable-and-quiet, reachable-with-records, plus the
  inventory cases, the boolean-quantity rejection, and a zero-length horizon. Its
  quantity claim is two records with two quantities; this file quantifies the same claim
  over arbitrary record streams *and* carries it through the twin, which an example cannot.
* ``digital_twin/tests/test_world_provenance.py`` (four concrete runtime states) - a real
  manual-tick ``WorldRuntime`` over a seeded world, a feed-driven world with opening stock,
  a feed-driven world with absent stock, and a stub-driven world. It stops at
  ``perceive()``. This file starts there and continues into the sensor loop, which is where
  "the value that reaches a decision" becomes checkable at all.

How the feed is driven without opening a socket (I-0)
-----------------------------------------------------

Through the ``FeedConsumer`` protocol seam. ``ExternalFeedSource`` takes a
``consumer_factory``, and an injected factory *is* a configuration, so the source under
test is the real one, taking the real retry path, mapping records with the real
``_to_events``. The broker fake hands over one published batch per drain call and nothing
else. No Kafka, no Postgres, no container, no port: I-0 forbids standing up a service
locally, and the real-broker proof belongs to an integration workload. Three seams stand in
for production, each for a stated reason:

* the **broker** - a socket (category 1 under I-0);
* the **consensus runner** - the real four-tier ``ConsensusProtocol`` needs eight agent
  endpoints; what Property 29 needs from it is only *that* it was convened, with what, and
  in what order, so the fake derives its decision id from the canonical request bytes. A
  drawn or random id would make a replay incomparable, which is the trap R4.6 names;
* the **provenance table** - Postgres. ``build_provenance`` is pure and is the real one;
  only the INSERT is replaced by an in-memory ledger.

The twin, the feed, the runtime and the sensor loop are the shipped objects. This follows
``orchestrator/tests/test_real_actuation_e2e.py``: the world is the oracle, the transport
is not the subject.

Cost and routing
----------------

``@pytest.mark.slow``: every example boots a real SimPy world, advances its clock, and runs
the sensor loop's perception cycle. Owned by ``.github/workflows/ci.yml``'s
``uplift-verify`` job, which runs ``pytest tests/uplift tests/verify -m "slow"`` at
``HYPOTHESIS_PROFILE=heavy`` (100 examples - the minimum the spec obligation requires).
Locally, ``-m "not slow"`` excludes it by design; it is never run on the development
laptop. ``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000). The retry
budget is fractions of a millisecond because ADR-016's backoff policy is proven in
``packages/tests/test_retry.py`` and this property must not pay real seconds for it.

This property carries **no numeric threshold**, so it reads nothing from
``infrastructure/quality/``: every assertion is an exact equality, an independently
recomputed value, or an ordering. The one float constant is IEEE-754 slack avoidance, and
it is avoided structurally instead - published stock levels are whole units, so every
inventory subtraction below is exact.

Disclosed bounds, and the two gaps this file pins rather than repairs
--------------------------------------------------------------------

Both are cross-cutting findings reported upward, not edited here (the production tree is
not this task's to change):

1. ``WorldRuntime.tick`` calls ``self._sim.inject_orders(len(arrivals))``, so the twin
   creates **one order per record regardless of the units that record published**. The
   published quantity survives unchanged on the arrival - that half of R4.1 holds exactly
   and is asserted below - but it does not scale the twin's demand, so a 7-unit order and a
   1-unit order move the world identically. The collapse is *pinned* below, so the day the
   twin becomes unit-aware this property fails and gets revisited instead of quietly
   generalising.
2. ``ExternalFeedSource.feed_revision()`` computes a water mark and ``WorldState`` carries
   no field for it, so ``build_provenance`` finds no ``feed_revision`` key and every
   provenance row filed from a real feed records ``NULL``. The audit trail therefore cannot
   name *which* published record a decision was convened from. Also pinned below.

``as_of`` (and ``WorldEvent.ts``) are wall-clock observability stamps and are excluded from
every replay comparison, for the same reason ``SimWorldSource``'s own docstring excludes
them: R4.6 is a claim about the decisions a replay convenes, not about the instant the
replay happened.

**Validates: Requirements 4.1, 4.6**
"""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final
from uuid import NAMESPACE_URL, uuid5

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from synapse_common.world.models import SourceProvenance, WorldEventKind
from synapse_common.world.source import (
    DEMAND_TOPIC,
    INVENTORY_TOPIC,
    RECORDS_REJECTED,
    ExternalFeedSource,
)

from digital_twin.config import TwinConfig
from digital_twin.simulation.engine import SupplyChainSimulation
from digital_twin.world.runtime import WorldRuntime
from orchestrator.sensor.loop import SensorLoop

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable, Mapping, Sequence

    from synapse_common.world.models import WorldEvent

    from orchestrator.audit.models import DecisionDataProvenance

#: The city every published record and every world in this file belongs to.
CITY: Final[str] = "bengaluru"

#: A city whose records are not ours. A record for it must reach the world as *nothing*,
#: and must not be counted as a rejection either - it is simply not this world's.
OTHER_CITY: Final[str] = "mumbai"

#: SKU ids a seeded scenario can never produce. ``SupplyChainSimulation.start`` substitutes
#: ``{f"sku_{i}": 100.0 for i in range(10)}`` when no opening stock is supplied, so a
#: ``sku_``-prefixed key surfacing in a perceived inventory here would be padding rather
#: than published stock. That is what makes the "no seeded padding" clause of R4.1 sharp
#: instead of a coincidence of naming.
FEED_SKUS: Final[tuple[str, ...]] = ("ext_sku_alpha", "ext_sku_beta", "ext_sku_gamma")

#: A SKU orders may reference that the opening snapshot never stocked. A real feed is not
#: ours to constrain, so demand for an unstocked SKU must be ingested, not repaired.
UNSTOCKED_SKU: Final[str] = "ext_sku_delta"

#: The prefix the engine's literal opening stock uses (``engine.py``'s ``start``).
SEEDED_SKU_PREFIX: Final[str] = "sku_"

#: Keys a demand record may carry its unit count under, in the precedence order
#: ``ExternalFeedSource`` documents. Restated rather than imported so the acceptance
#: recompute below is an independent second implementation, not a mirror of the first.
QUANTITY_KEYS: Final[tuple[str, ...]] = ("quantity", "qty", "units")

#: Sentinel a drawn record carries to say "give me an order id"; stripped before publishing.
_WITH_ORDER_ID: Final[str] = "__with_order_id"


# ---------------------------------------------------------------------------
# Canonical serialisation and the independent acceptance recompute
# ---------------------------------------------------------------------------
def _canonical(payload: object) -> str:
    """Canonical JSON: sorted keys, no whitespace (the repo's one serialisation form)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def published_quantity(record: Mapping[str, Any]) -> float | None:
    """Units the record published, or ``None`` if it published none readably.

    An independent restatement of ``ExternalFeedSource._first_numeric``'s rules: the first
    key in :data:`QUANTITY_KEYS` holding a finite real number, with ``bool`` excluded
    because ``True`` is an ``int`` in Python and a feed that sent ``quantity: true`` must be
    rejected rather than read as one unit.
    """
    for key in QUANTITY_KEYS:
        value = record.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def _is_usable(record: Mapping[str, Any]) -> bool:
    """Whether this world can read the record: a positive quantity and a named SKU."""
    quantity = published_quantity(record)
    sku = record.get("sku_id")
    return quantity is not None and quantity > 0.0 and isinstance(sku, str) and bool(sku)


def accepted_records(records: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    """The records that must become arrivals, in published order.

    Recomputed here rather than read back off the source, so a test comparing the two is
    comparing two implementations instead of one.
    """
    return tuple(r for r in records if r.get("city") == CITY and _is_usable(r))


def rejected_count(records: Sequence[Mapping[str, Any]]) -> int:
    """Records for *this* city that the world could not read.

    A foreign-city record is deliberately not a rejection: the source filters by city
    before it judges a payload, so a record that is not ours is not a fault of ours.
    """
    return sum(1 for r in records if r.get("city") == CITY and not _is_usable(r))


# ---------------------------------------------------------------------------
# The published trace
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    """One published input trace plus the world it is published into.

    ``demand_batches`` is one batch per clock step, which is what a broker actually hands a
    poll: the world's clock owns progress, so a trace is a sequence of what was available
    at each tick rather than one undifferentiated pile.
    """

    seed: int
    reorder_point: float
    opening: tuple[tuple[str, float], ...]
    foreign_stock: bool
    demand_batches: tuple[tuple[Mapping[str, Any], ...], ...]

    @property
    def opening_stock(self) -> dict[str, float]:
        """The opening stock the snapshot publishes, in published order."""
        return dict(self.opening)

    def inventory_records(self) -> list[dict[str, Any]]:
        """The snapshot batch as it lands on ``synapse.inventory.state``."""
        records: list[dict[str, Any]] = [
            {"city": CITY, "sku_id": sku, "level": level} for sku, level in self.opening
        ]
        if self.foreign_stock:
            # Another city's stock on the same topic: it must not enter this world at all.
            records.append({"city": OTHER_CITY, "sku_id": "ext_sku_omega", "level": 999.0})
        return records

    def accepted(self, batch_index: int) -> tuple[Mapping[str, Any], ...]:
        return accepted_records(self.demand_batches[batch_index])

    def rejected(self, batch_index: int) -> int:
        return rejected_count(self.demand_batches[batch_index])

    @property
    def ticks(self) -> int:
        return len(self.demand_batches)


@st.composite
def demand_records(draw: st.DrawFn) -> dict[str, Any]:
    """One record shaped like an operator order on ``synapse.orders.demand``.

    Records the world must reject are drawn on purpose - a blank SKU, a zero quantity, a
    boolean quantity, an absent quantity, a foreign city. "Ingested faithfully" is as much
    a claim about substitution as about arithmetic: an unreadable record must arrive as
    *nothing*, never as a plausible default (I-7).
    """
    quantity = draw(
        st.one_of(
            st.floats(min_value=0.25, max_value=250.0, allow_nan=False, allow_infinity=False),
            st.integers(min_value=1, max_value=250),
            st.just(0.0),
            st.booleans(),
            st.none(),
        )
    )
    return {
        # CITY twice so most drawn records are ours and the accepted path is well covered.
        "city": draw(st.sampled_from((CITY, CITY, OTHER_CITY))),
        "store_id": "store_001",
        "sku_id": draw(st.sampled_from((*FEED_SKUS, UNSTOCKED_SKU, ""))),
        "quantity": quantity,
        "timestamp": "2026-01-01T00:00:00Z",
        _WITH_ORDER_ID: draw(st.booleans()),
    }


@st.composite
def scenarios(draw: st.DrawFn, *, max_ticks: int = 3) -> Scenario:
    """A published trace guaranteed to breach the reorder point.

    Two deliberate constraints:

    * ``reorder_point`` is a half-integer and every published level is a whole unit, so
      ``level < reorder_point`` is never a float coin-flip and the low set an independent
      recompute produces is exactly the one the sensor produces.
    * one published level is guaranteed strictly below the reorder point, so every example
      convenes at least one decision. A replay-equality property over two empty sequences
      would be vacuously true, which is the failure mode R4.6 is worth stating against.
    """
    reorder_point = float(draw(st.integers(min_value=20, max_value=200))) + 0.5
    skus = draw(st.lists(st.sampled_from(FEED_SKUS), min_size=1, max_size=3, unique=True))
    # Whole units: a store counts stock in units, and it keeps every inventory subtraction
    # below exact, so the assertions need no floating-point slack.
    levels = {sku: float(draw(st.integers(min_value=0, max_value=400))) for sku in skus}
    levels[skus[0]] = float(draw(st.integers(min_value=0, max_value=int(reorder_point))))

    raw_batches = draw(
        st.lists(
            st.lists(demand_records(), max_size=3),
            min_size=1,
            max_size=max_ticks,
        )
    )
    # Order ids are assigned across the whole trace so they are unique, which is what makes
    # the arrival-identity injectivity claim below meaningful.
    batches: list[tuple[Mapping[str, Any], ...]] = []
    index = 0
    for raw_batch in raw_batches:
        batch: list[Mapping[str, Any]] = []
        for raw in raw_batch:
            record = dict(raw)
            if record.pop(_WITH_ORDER_ID, False):
                record["order_id"] = f"ord-{index:04d}"
            index += 1
            batch.append(record)
        batches.append(tuple(batch))

    return Scenario(
        seed=draw(st.integers(min_value=1, max_value=2**16)),
        reorder_point=reorder_point,
        opening=tuple(levels.items()),
        foreign_stock=draw(st.booleans()),
        demand_batches=tuple(batches),
    )


# ---------------------------------------------------------------------------
# Broker fakes over the FeedConsumer protocol seam (no socket, I-0)
# ---------------------------------------------------------------------------
class _BatchConsumer:
    """One reachable-broker session over a queue of published batches.

    ``ExternalFeedSource`` builds and closes a consumer per poll, so the read cursor lives
    in the queue this session was handed, not in the session. Each drain yields fresh dicts
    the way a deserialising consumer would, so nothing downstream can reach back into the
    published trace.
    """

    def __init__(self, pending: list[list[Mapping[str, Any]]]) -> None:
        self._pending = pending
        self.drains = 0

    def reachable_topics(self, timeout: float = 5.0) -> tuple[str, ...]:
        return (DEMAND_TOPIC, INVENTORY_TOPIC)

    def drain(self, *, max_records: int = 1000, timeout: float = 1.0) -> list[dict[str, Any]]:
        self.drains += 1
        if not self._pending:
            return []  # reachable and quiet: zero orders is a fact, not a fault
        return [dict(record) for record in self._pending.pop(0)[:max_records]]

    def close(self) -> None:
        return None


def _broker_factory(scenario: Scenario) -> Callable[[str], _BatchConsumer]:
    """A reachable broker serving this scenario: demand per tick, one inventory snapshot."""
    demand: list[list[Mapping[str, Any]]] = [list(batch) for batch in scenario.demand_batches]
    inventory: list[list[Mapping[str, Any]]] = [list(scenario.inventory_records())]

    def factory(topic: str) -> _BatchConsumer:
        return _BatchConsumer(demand if topic == DEMAND_TOPIC else inventory)

    return factory


class _RecordedFeed:
    """The real ``ExternalFeedSource``, with every arrival it produced kept for inspection.

    A pure observer: every method delegates and no method decides anything. It exists so
    one run can be examined at both ends - what the feed published and what the world
    perceived - instead of inferring the middle from a second, separately built source.
    """

    def __init__(self, feed: ExternalFeedSource) -> None:
        self._feed = feed
        self.name = feed.name
        self.polls: list[tuple[WorldEvent, ...]] = []

    def poll_arrivals(self, now_sim_min: float, horizon_min: float) -> list[WorldEvent]:
        events = self._feed.poll_arrivals(now_sim_min, horizon_min)
        self.polls.append(tuple(events))
        return events

    def provenance(self) -> SourceProvenance:
        return self._feed.provenance()

    def initial_inventory(self) -> dict[str, float] | None:
        return self._feed.initial_inventory()

    def degradation(self) -> str | None:
        return self._feed.degradation()

    @property
    def arrivals(self) -> tuple[WorldEvent, ...]:
        """Every arrival from every poll, in poll order."""
        return tuple(event for batch in self.polls for event in batch)


# ---------------------------------------------------------------------------
# Perception transport, consensus, and the provenance ledger
# ---------------------------------------------------------------------------
class _TwinPerceptionClient:
    """The sensor's ``WorldClient``, wired straight to the runtime.

    Mirrors ``digital_twin/inference/serve.py::_world_state_response`` exactly -
    ``runtime.perceive().model_dump(mode="json")`` - with the HTTP hop removed. Keeps every
    payload the sensor actually consumed, because "the value that reaches a decision" is a
    claim about that payload and not about a second perceive taken beside it.
    """

    def __init__(self, runtime: WorldRuntime) -> None:
        self._runtime = runtime
        self.payloads: list[dict[str, Any]] = []

    async def world_state(self, city: str) -> dict[str, Any] | None:
        payload: dict[str, Any] = self._runtime.perceive().model_dump(mode="json")
        assert payload["city"] == city
        self.payloads.append(payload)
        return payload


@dataclass(frozen=True)
class _Convened:
    """One convening: the decision id issued, and the request it was issued for."""

    decision_id: str
    request: dict[str, Any]


@dataclass(frozen=True)
class _Decision:
    """The slice of a ``ConsensusDecision`` the sensor reads back (``decision_id``)."""

    decision_id: str


class _RecordingConsensus:
    """A ``ConsensusRunner`` that records what it was convened with, in order.

    The decision id is a UUID5 over the canonical request bytes, deliberately: R4.6 is a
    claim about identifiers, so an id drawn at random would make a replay incomparable and
    an id equal to a constant would make the claim vacuous. Deriving it from the request
    means an id difference cannot hide a payload difference, and a payload difference cannot
    hide behind a stable id.
    """

    def __init__(self) -> None:
        self.convened: list[_Convened] = []

    async def run_consensus(self, decision_request: dict[str, Any]) -> _Decision:
        request = json.loads(_canonical(decision_request))
        decision_id = str(uuid5(NAMESPACE_URL, _canonical(request)))
        self.convened.append(_Convened(decision_id=decision_id, request=request))
        return _Decision(decision_id=decision_id)


class _ProvenanceLedger:
    """In-memory stand-in for the append-only ``decision_data_provenance`` table.

    Only the INSERT is replaced; ``build_provenance`` - where every honesty decision lives -
    is the real one, and I-0 keeps Postgres out of this loop.
    """

    def __init__(self) -> None:
        self.rows: list[DecisionDataProvenance] = []

    def __call__(self, row: DecisionDataProvenance) -> bool:
        self.rows.append(row)
        return True


# ---------------------------------------------------------------------------
# The composed harness
# ---------------------------------------------------------------------------
@dataclass
class Harness:
    """The assembled composition, with the two ends and the middle observable."""

    sim: SupplyChainSimulation
    source: _RecordedFeed
    runtime: WorldRuntime
    client: _TwinPerceptionClient
    consensus: _RecordingConsensus
    ledger: _ProvenanceLedger
    loop: SensorLoop


def _build(scenario: Scenario) -> Harness:
    """Assemble a real twin on a real external feed behind a real sensor loop."""
    config = TwinConfig()
    sim = SupplyChainSimulation(config=config, seed=scenario.seed)
    feed = ExternalFeedSource(
        city=CITY,
        # An injected factory IS the configuration. The empty address keeps the source from
        # reading SYNAPSE_KAFKA_BOOTSTRAP / KAFKA_BOOTSTRAP_SERVERS, so a runner with either
        # set cannot change what this property measures.
        bootstrap_servers="",
        consumer_factory=_broker_factory(scenario),
        poll_timeout_s=0.01,
        max_retries=1,
        retry_base_delay_s=1e-4,
    )
    source = _RecordedFeed(feed)
    runtime = WorldRuntime(city=CITY, sim=sim, source=source, config=config, step_hours=1.0)
    client = _TwinPerceptionClient(runtime)
    consensus = _RecordingConsensus()
    ledger = _ProvenanceLedger()
    loop = SensorLoop(
        consensus,
        client,
        cities=[CITY],
        reorder_point=scenario.reorder_point,
        # A wall-clock debounce would make a replay depend on how fast the machine ran it,
        # so every breach fires. The debounce itself is the sensor suite's subject.
        debounce_s=0.0,
        # Disabled: a heartbeat is a liveness signal, not an ingestion of anything.
        heartbeat_idle_polls=0,
        provenance_recorder=ledger,
    )
    return Harness(
        sim=sim,
        source=source,
        runtime=runtime,
        client=client,
        consensus=consensus,
        ledger=ledger,
        loop=loop,
    )


async def _drive(harness: Harness, *, ticks: int) -> None:
    """Advance the world ``ticks`` steps, letting the sensor perceive after each one."""
    for _ in range(ticks):
        harness.runtime.tick()
        await harness.loop.poll_once()


def _state_fingerprint(payload: Mapping[str, Any]) -> str:
    """Canonical JSON of a perceived state, minus the wall-clock stamp (see module docs)."""
    return _canonical({key: value for key, value in payload.items() if key != "as_of"})


@dataclass(frozen=True)
class ReplayObservation:
    """Everything one run of the composed loop makes observable to a replay comparison."""

    order_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    requests: tuple[str, ...]
    states: tuple[str, ...]
    arrivals: tuple[tuple[str, str | None, float | None], ...]
    provenance: tuple[tuple[str, bool, str | None], ...]


def _replay(scenario: Scenario, *, ticks: int) -> ReplayObservation:
    """Run the whole composition once from freshly built objects, and observe it."""
    harness = _build(scenario)
    harness.runtime.start(run_clock=False)
    try:
        asyncio.run(_drive(harness, ticks=ticks))
    finally:
        harness.runtime.stop()
    return ReplayObservation(
        order_ids=tuple(str(c.request["order_id"]) for c in harness.consensus.convened),
        decision_ids=tuple(c.decision_id for c in harness.consensus.convened),
        requests=tuple(_canonical(c.request) for c in harness.consensus.convened),
        states=tuple(_state_fingerprint(payload) for payload in harness.client.payloads),
        arrivals=tuple(
            (event.event_id, event.sku_id, event.quantity) for event in harness.source.arrivals
        ),
        provenance=tuple(
            (row.source_class, row.is_synthetic, row.feed_revision) for row in harness.ledger.rows
        ),
    )


# ---------------------------------------------------------------------------
# Clause 1: a published record is ingested faithfully, within one clock step
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 29: Non-synthetic input is ingested faithfully and replays deterministically
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(scenario=scenarios())
def test_a_published_record_reaches_the_world_unchanged_within_one_clock_step(
    scenario: Scenario,
) -> None:
    """R4.1: the incorporated quantity is the published quantity, one step after publication."""
    harness = _build(scenario)
    accepted = scenario.accepted(0)
    rejected = scenario.rejected(0)
    opening = scenario.opening_stock

    harness.runtime.start(run_clock=False)
    try:
        before = harness.runtime.perceive()

        # The world opens on the published snapshot: not the engine's literal stock, and not
        # another city's. Nothing has been ingested yet, so "within one clock step" below is
        # a statement about the tick rather than about the boot.
        assert before.source_class is SourceProvenance.EXTERNAL
        assert before.is_synthetic is False
        assert before.inventory == opening
        assert before.degraded is False
        assert before.degraded_reason is None
        assert harness.sim.metrics.orders_created == 0

        harness.runtime.tick()

        assert len(harness.source.polls) == 1
        arrivals = harness.source.polls[0]

        # -- faithfulness: same records, same order, same numbers, nothing invented -------
        assert [(event.sku_id, event.quantity) for event in arrivals] == [
            (record["sku_id"], published_quantity(record)) for record in accepted
        ]
        assert len(arrivals) == len(accepted)
        assert all(event.kind is WorldEventKind.DEMAND_ARRIVAL for event in arrivals)
        assert all(event.city == CITY for event in arrivals)
        # Stamped at the poll instant. The record carries a wall-clock timestamp, not a
        # simulation minute, so spreading arrivals across the window would invent precision.
        assert all(event.sim_time_min == 0.0 for event in arrivals)

        # -- identity is derived from the record, which is what makes a replay comparable --
        for event, record in zip(arrivals, accepted, strict=True):
            order_id = record.get("order_id")
            if isinstance(order_id, str) and order_id:
                assert event.event_id == f"ext:{order_id}"
            else:
                # No published id: the source digests the record's canonical bytes. The
                # digest is not recomputed here (that would restate the implementation);
                # its stability across replays is asserted by the replay clause.
                assert event.event_id.startswith("ext:")
        # Responsive, not constant: distinct records get distinct identities, and two
        # byte-identical records legitimately share one.
        assert len({event.event_id for event in arrivals}) == len(
            {_canonical(dict(record)) for record in accepted}
        )

        after = harness.runtime.perceive()

        # -- the record reached the world within that one step ----------------------------
        # Disclosed bound, and this equality is the pin for it: `WorldRuntime.tick` hands
        # `len(arrivals)` to `inject_orders`, so the twin creates one order per *record* and
        # a 7-unit order moves the world exactly as a 1-unit order does. The published units
        # survive unchanged on the arrival (asserted above); they stop at the twin's door.
        # Reported upward as a cross-cutting finding rather than repaired here - and a twin
        # that became unit-aware would create `sum(units)` orders and fail this line, which
        # is the point of asserting the record count rather than asserting nothing.
        assert harness.sim.metrics.orders_created == len(accepted)
        # R4.1 names `perceive()` specifically, so the ingestion is witnessed through the
        # perceived state as well as through the engine's counter: one step after publication
        # every accepted record is either still in flight or already delivered, and none has
        # been dropped on the way into the snapshot the sensor will read.
        assert after.pending_orders + harness.sim.metrics.orders_delivered == len(accepted)

        # -- no seeded padding, and stock only moves the way a delivery moves it ----------
        assert set(after.inventory) == set(opening)
        assert not [sku for sku in after.inventory if sku.startswith(SEEDED_SKU_PREFIX)]
        delivered = harness.sim.metrics.orders_delivered
        for sku, level in after.inventory.items():
            assert level <= opening[sku]
            # Exact: published levels are whole units and a delivery decrements exactly one.
            assert (opening[sku] - level) <= float(delivered)
        drop = sum(opening.values()) - sum(after.inventory.values())
        assert 0.0 <= drop <= float(delivered)

        # -- I-7: a record that could not be read is reported, never repaired -------------
        assert after.degraded is (rejected > 0)
        assert after.degraded_reason == (RECORDS_REJECTED if rejected else None)
        assert after.is_synthetic is False
        assert after.source_class is SourceProvenance.EXTERNAL
    finally:
        harness.runtime.stop()


# ---------------------------------------------------------------------------
# Clause 2: the value that reaches the decision is the value that was published
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 29: Non-synthetic input is ingested faithfully and replays deterministically
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(scenario=scenarios())
def test_the_decision_the_sensor_convenes_carries_the_published_values(
    scenario: Scenario,
) -> None:
    """R4.1: the values a decision is convened on are the published ones, unpadded."""
    harness = _build(scenario)
    opening = scenario.opening_stock

    harness.runtime.start(run_clock=False)
    try:
        asyncio.run(_drive(harness, ticks=1))

        # The payload the sensor actually consumed - not a second perceive taken beside it.
        assert len(harness.client.payloads) == 1
        payload = harness.client.payloads[0]
        inventory: dict[str, float] = payload["inventory"]
        expected_low = sorted(
            sku for sku, level in inventory.items() if level < scenario.reorder_point
        )
        # Guaranteed by construction: an empty low set would make every clause below vacuous.
        assert expected_low

        assert harness.loop.decisions_triggered == 1
        assert len(harness.consensus.convened) == 1
        request = harness.consensus.convened[0].request

        # -- the perceived values reach the decision unaltered -----------------------------
        assert request["world_inventory"] == inventory
        assert request["sku_ids"] == expected_low
        assert [item["sku_id"] for item in request["items"]] == expected_low
        # Every level in the decision traces back to a published one, depleted only by the
        # world. No key the snapshot never published, and no `sku_` literal padding.
        assert set(request["world_inventory"]) == set(opening)
        assert not [sku for sku in request["world_inventory"] if sku.startswith(SEEDED_SKU_PREFIX)]
        for sku, level in request["world_inventory"].items():
            assert level <= opening[sku]

        # -- what the feed does NOT decide, stated so the claim is not over-read -----------
        # The reorder size is the sensor's own rule (`reorder_point * 4`), not a published
        # value. Pinned here to keep "the published value reached the decision" from being
        # read as "the feed chose the order quantity".
        assert [item["quantity"] for item in request["items"]] == [
            int(scenario.reorder_point * 4)
        ] * len(expected_low)

        # -- the decision is self-initiated and filed as externally sourced ----------------
        assert request["city"] == CITY
        assert request["trigger"] == "reorder_point"
        assert request["disruption_active"] is False
        assert request["order_id"] == f"auto-{CITY}-reorder_point-1"

        assert harness.loop.provenance_recorded == 1
        assert len(harness.ledger.rows) == 1
        row = harness.ledger.rows[0]
        assert row.source_class == "EXTERNAL"
        assert row.is_synthetic is False
        assert str(row.decision_id) == harness.consensus.convened[0].decision_id
        # Disclosed gap, pinned: `ExternalFeedSource.feed_revision()` computes a water mark
        # and `WorldState` carries no field for it, so the provenance row cannot name which
        # published record this decision was convened from. Reported, not repaired here.
        assert row.feed_revision is None
    finally:
        harness.runtime.stop()


# ---------------------------------------------------------------------------
# Clause 3: replaying the trace convenes the same decisions in the same order
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 29: Non-synthetic input is ingested faithfully and replays deterministically
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(scenario=scenarios())
def test_replaying_the_same_trace_convenes_the_same_decisions_in_the_same_order(
    scenario: Scenario,
) -> None:
    """R4.6: the same non-synthetic trace replays to the same decisions, in order."""
    ticks = scenario.ticks

    first = _replay(scenario, ticks=ticks)
    second = _replay(scenario, ticks=ticks)

    # Non-vacuous before it is equal: something was convened, and every tick was perceived.
    assert first.decision_ids
    assert len(first.states) == ticks
    assert len(set(first.order_ids)) == len(first.order_ids)

    # R4.6 verbatim: the same set, in the same order. Both are asserted - a set equality
    # alone would accept a reordering, and a sequence equality alone reads less like the
    # requirement it discharges.
    assert set(first.decision_ids) == set(second.decision_ids)
    assert first.decision_ids == second.decision_ids
    assert first.order_ids == second.order_ids

    # The identifiers are equal because the payloads are, not because the identifiers are
    # constant: the fake derives each id from the canonical request bytes.
    assert first.requests == second.requests
    # The world the decisions were convened from replayed too, wall-clock stamps excluded.
    assert first.states == second.states
    # And so did the ingestion: the same arrivals, with the same identities and the same
    # published quantities, including the digest-derived ids the first clause left open.
    assert first.arrivals == second.arrivals
    assert first.provenance == second.provenance
    assert all(source_class == "EXTERNAL" for source_class, _, _ in first.provenance)
    assert not [flag for _, flag, _ in first.provenance if flag]
