"""SYNAPSE WorldSource — the pluggable origin of demand for the standing world (ADR-052).

The whole point of the seam is that the downstream loop — SensorLoop -> consensus ->
actuation -> outcome scoring — is **identical regardless of where demand comes from**.

  * ``SimWorldSource``: deterministic Poisson demand the simulation drives. A real,
    seeded, unit-testable generator. Declares ``SourceProvenance.SEEDED``.
  * ``ExternalFeedSource``: drains real orders off ``synapse.orders.demand`` through
    ``synapse_common.kafka_client``, with jittered retries from ``synapse_common.retry``
    (ADR-016). Declares ``SourceProvenance.EXTERNAL``.

What changed in this increment (purpose-achievement-audit task 10.11, design E5.3)
---------------------------------------------------------------------------------

The audit's Requirement 4 finding was that the closed autonomy loop had only ever run on
its own simulation, and that ``WorldState.is_synthetic`` was **pinned** ``True`` rather
than derived — so the honesty flag could not distinguish the two cases it existed to
distinguish. Two things follow:

1. :meth:`WorldSource.provenance` makes each implementation *declare* its class, and
   ``WorldState.is_synthetic`` is computed from that declaration (AD-11). Nobody asserts
   the flag any more.
2. ``ExternalFeedSource.poll_arrivals`` genuinely polls. It was an honest stub — it never
   pretended to be wired — but an honest stub is still not a feed, and
   ``scripts/audit/feed_provenance.py`` now classifies an unconditionally empty
   ``poll_arrivals`` as ``STUB`` regardless of what the class is called (R4.8). A
   declaration cannot outrun the implementation.

The three honesty rules this module must not break (I-7)
--------------------------------------------------------

* **A configured-but-unreachable feed never falls back to the seeded generator** (R4.5).
  ``ExternalFeedSource`` holds no generator and imports none: the fallback is not
  suppressed by a flag, it is structurally absent. Unreachable means zero arrivals plus a
  degradation reason, and the runtime degrades on that reason.
* **An unconfigured feed is not a reachable feed.** With no bootstrap servers, the source
  reports ``external_feed_not_configured`` and polls nothing — it does not silently pass.
* **Absent inventory degrades** rather than substituting a literal default (R4.9), which
  is why :meth:`WorldSource.initial_inventory` may return ``None`` and the runtime treats
  ``None`` from a non-seeded source as a degradation.

Swapping the source must never require touching the sensor, consensus, or actuation.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable

import structlog

from synapse_common.retry import retry_with_jitter
from synapse_common.world.models import SourceProvenance, WorldEvent, WorldEventKind

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable, Mapping, Sequence

logger = structlog.get_logger(__name__)

#: The ingress topic real operator orders already land on (``api/routers/orders.py``,
#: ADR-029, ``proto/domain/order_request.schema.json``).
DEMAND_TOPIC: Final[str] = "synapse.orders.demand"

#: Where a non-seeded world reads its opening stock from. Separate from the demand topic
#: because inventory is a snapshot and demand is a stream; R4.9 needs the snapshot.
INVENTORY_TOPIC: Final[str] = "synapse.inventory.state"

#: Environment keys consulted for broker addresses, in order. Configuration is explicit:
#: absent means *unconfigured*, which is a distinct, reported state from *unreachable*.
BOOTSTRAP_ENV_KEYS: Final[tuple[str, ...]] = (
    "SYNAPSE_KAFKA_BOOTSTRAP",
    "KAFKA_BOOTSTRAP_SERVERS",
)

#: Degradation reasons this module can report. Named constants because the runtime, the
#: console, and the property tests all match on them.
NOT_CONFIGURED: Final[str] = "external_feed_not_configured"
UNREACHABLE: Final[str] = "external_feed_unreachable"
RECORDS_REJECTED: Final[str] = "external_feed_records_rejected"
INVENTORY_ABSENT: Final[str] = "external_inventory_absent"
STUB_SOURCE: Final[str] = "world_source_is_stub"

_MAX_RETRIES: Final[int] = 3
_BASE_DELAY_S: Final[float] = 0.5
_RETRY_CAP_S: Final[float] = 8.0
_METADATA_TIMEOUT_S: Final[float] = 5.0

#: Keys a demand record may carry its unit count under, in precedence order. The
#: canonical ingress payload (``api/routers/orders.py:70``,
#: ``proto/domain/order_request.schema.json``) uses ``quantity``; the others are
#: accepted because a real feed is not ours to rename.
_QUANTITY_KEYS: Final[tuple[str, ...]] = ("quantity", "qty", "units")

#: Keys an inventory-snapshot record may carry its stock level under.
_LEVEL_KEYS: Final[tuple[str, ...]] = ("level", "on_hand", "quantity")

__all__ = [
    "BOOTSTRAP_ENV_KEYS",
    "DEMAND_TOPIC",
    "INVENTORY_ABSENT",
    "INVENTORY_TOPIC",
    "NOT_CONFIGURED",
    "RECORDS_REJECTED",
    "STUB_SOURCE",
    "UNREACHABLE",
    "ExternalFeedSource",
    "FeedConsumer",
    "FeedUnreachableError",
    "SimWorldSource",
    "SourceProvenance",
    "WorldSource",
]


class FeedUnreachableError(RuntimeError):
    """The configured feed could not be reached within the retry budget (ADR-016).

    Raised inside the source and handled there: it becomes a degradation reason plus zero
    arrivals, never an exception that reaches the clock loop and never a fallback.
    """


@runtime_checkable
class FeedConsumer(Protocol):
    """The slice of ``synapse_common.kafka_client.SynapseConsumer`` this module needs.

    A structural protocol rather than a concrete import so (a) ``confluent_kafka`` stays
    off the digital twin's import path until a feed is actually configured, and (b) the
    property tests for Property 28/29 can drive a reachable, an unreachable, and a quiet
    feed without a broker — the pure seam tasks 10.12/10.13 need.
    """

    def reachable_topics(self, timeout: float = ...) -> tuple[str, ...]:
        """Broker-advertised topics, or raise if the cluster cannot be reached."""
        ...

    def drain(self, *, max_records: int = ..., timeout: float = ...) -> list[dict[str, Any]]:
        """Read the currently-available records, stopping at the first empty poll."""
        ...

    def close(self) -> None:
        """Release the consumer's broker connections."""
        ...


def _bootstrap_from_env() -> str | None:
    """First non-empty broker address in :data:`BOOTSTRAP_ENV_KEYS`, else ``None``.

    ``None`` means *unconfigured*, which is reported as its own degradation reason. It is
    deliberately not treated as "reachable with nothing on it": an unconfigured feed that
    reported a healthy empty world would be the silent-success failure R4.5 forbids.
    """
    for key in BOOTSTRAP_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def _default_consumer_factory(bootstrap: str, group_id: str) -> Callable[[str], FeedConsumer]:
    """Build the production :class:`FeedConsumer` factory over ``synapse_common.kafka_client``.

    The import is deferred to call time (not module import) so that constructing an
    ``ExternalFeedSource``, and importing this module at all, never requires the Kafka
    client library. Direct ``confluent_kafka`` use is a PR rejection; every broker call
    below goes through ``SynapseConsumer``.
    """

    def factory(topic: str) -> FeedConsumer:
        from synapse_common.kafka_client import KafkaConfig, SynapseConsumer

        config = KafkaConfig(
            bootstrap_servers=bootstrap,
            group_id=group_id,
            auto_offset_reset="earliest",
            # The world's clock owns progress, not the broker's commit timer: an
            # auto-commit racing a tick could acknowledge arrivals the world never saw.
            enable_auto_commit=False,
        )
        return SynapseConsumer(config, [topic])

    return factory


@runtime_checkable
class WorldSource(Protocol):
    """Origin of demand-arrival events for one city's world."""

    name: str

    def poll_arrivals(self, now_sim_min: float, horizon_min: float) -> list[WorldEvent]:
        """Return the demand-arrival ``WorldEvent``s in ``[now, now+horizon)``."""
        ...

    def provenance(self) -> SourceProvenance:
        """Declare this source's class (AD-11). Drives ``WorldState.is_synthetic``.

        A declaration is a claim, not proof: ``scripts/audit/feed_provenance.py`` reads
        ``poll_arrivals`` statically and FAILs a source whose body does not support what
        this method declares (R4.8).
        """
        ...

    def initial_inventory(self) -> dict[str, float] | None:
        """Opening stock this source supplies, or ``None`` if it supplies none (R4.9).

        ``None`` from a non-seeded source is a **degradation**, not a licence to fall back
        to the simulation's literal ``{sku_i: 100.0}`` default.
        """
        ...

    def degradation(self) -> str | None:
        """Why this source's last poll was incomplete, or ``None`` if it was complete."""
        ...


class SimWorldSource:
    """Deterministic Poisson demand generator over a fixed store/SKU catalog.

    Seeded so a given (seed, catalog, lambda) replays the same arrival stream — this is the
    determinism the SensorLoop tests rely on. Stateful: successive ``poll_arrivals``
    calls advance the RNG and an arrival counter, so two polls over disjoint windows do
    not collide. ``ts`` is wall-clock (observability only); replay equality is over
    ``(kind, store_id, sku_id, sim_time_min, quantity)``.
    """

    def __init__(
        self,
        *,
        city: str,
        store_ids: list[str],
        sku_ids: list[str],
        arrival_rate_per_min: float = 2.0,
        seed: int = 0xC0FFEE,
    ) -> None:
        if arrival_rate_per_min <= 0.0:
            raise ValueError("arrival_rate_per_min must be > 0")
        if not store_ids or not sku_ids:
            raise ValueError("SimWorldSource needs a non-empty store/SKU catalog")
        self.name = f"sim:{city}"
        self._city = city
        self._stores = list(store_ids)
        self._skus = list(sku_ids)
        self._lambda = float(arrival_rate_per_min)
        self._rng = random.Random(seed)
        self._seq = 0

    def provenance(self) -> SourceProvenance:
        """``SEEDED``: every arrival comes from ``self._rng``, so the world is synthetic."""
        return SourceProvenance.SEEDED

    def initial_inventory(self) -> dict[str, float] | None:
        """``None`` — a seeded world's opening stock is part of the seed, not of the feed.

        This is not the R4.9 degradation case: R4.9 scopes the obligation to a source that
        is *not* a seeded generator. The simulation's literal opening stock is a declared
        component of a seeded scenario, and the runtime keeps using it for ``SEEDED`` only.
        """
        return None

    def degradation(self) -> str | None:
        """``None`` — a local seeded generator has nothing to be unreachable."""
        return None

    def poll_arrivals(self, now_sim_min: float, horizon_min: float) -> list[WorldEvent]:
        """Draw Poisson(lambda*horizon) arrivals, each at a uniform instant in the window."""
        if horizon_min <= 0.0:
            return []
        n = self._poisson(self._lambda * horizon_min)
        events: list[WorldEvent] = []
        for _ in range(n):
            self._seq += 1
            offset = self._rng.random() * horizon_min
            events.append(
                WorldEvent(
                    event_id=f"{self.name}-{self._seq:08d}",
                    kind=WorldEventKind.DEMAND_ARRIVAL,
                    city=self._city,
                    sim_time_min=round(now_sim_min + offset, 4),
                    store_id=self._rng.choice(self._stores),
                    sku_id=self._rng.choice(self._skus),
                    quantity=float(self._rng.randint(1, 5)),
                )
            )
        events.sort(key=lambda e: e.sim_time_min)
        return events

    def _poisson(self, lam: float) -> int:
        """Knuth's Poisson sampler on the source's own seeded RNG (deterministic)."""
        if lam <= 0.0:
            return 0
        target = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= self._rng.random()
            if p <= target:
                return k - 1


class ExternalFeedSource:
    """Demand read off ``synapse.orders.demand`` — the non-synthetic world (R4.1, R4.5).

    Real operator orders have reached Kafka since ADR-029 (``api/routers/orders.py:37``
    writes them through the outbox); until this increment nothing turned them into world
    arrivals, so every decision the loop ever convened came from ``SimWorldSource``. This
    class is that missing hop, and nothing downstream changes: the SensorLoop, consensus,
    actuation and outcome scoring see ``WorldEvent``s exactly as they do from the seeded
    generator. What changes is what ``WorldState.is_synthetic`` derives to (AD-11).

    Honest degradation, stated precisely (I-7, R4.5)
    -----------------------------------------------

    * **Unconfigured** (no broker address, no injected factory): reports
      :data:`NOT_CONFIGURED`, polls nothing, returns ``[]``.
    * **Configured but unreachable** (no broker answers within the ADR-016 retry budget,
      or the topic it was told to read does not exist): reports :data:`UNREACHABLE` and
      returns ``[]`` — a **degraded state with zero arrivals**.
    * **Reachable and quiet**: returns ``[]`` and reports **no** degradation. Zero real
      orders is a fact about the world, not a fault.
    * **Reachable with unusable records**: incorporates the usable ones and reports
      :data:`RECORDS_REJECTED`, naming the count in the log. It never substitutes a
      plausible value for a record it could not read.

    There is **no fallback to the seeded generator** in any of those branches. That is
    structural, not a policy: this class holds no RNG, no catalog, and no ``SimWorldSource``
    reference, so there is nothing here to fall back *to*. A future edit that added one
    would have to add the generator too, which is a visible diff rather than a silent flag.

    Determinism (R4.6). Arrivals are emitted in broker order and each is stamped at the
    poll instant ``now_sim_min`` — the source does not spread them across the window with
    an RNG, because inventing sub-minute arrival times for records that carry none would
    be fabricated precision. ``event_id`` is derived from the record's ``order_id`` (or, if
    it carries none, a digest of its canonical bytes), so replaying a trace produces the
    same identifiers in the same order.
    """

    def __init__(
        self,
        *,
        city: str,
        bootstrap_servers: str | None = None,
        group_id: str = "synapse-world-feed",
        demand_topic: str = DEMAND_TOPIC,
        inventory_topic: str = INVENTORY_TOPIC,
        poll_timeout_s: float = 1.0,
        max_records: int = 5000,
        max_retries: int = _MAX_RETRIES,
        retry_base_delay_s: float = _BASE_DELAY_S,
        consumer_factory: Callable[[str], FeedConsumer] | None = None,
    ) -> None:
        self.name = f"external:{city}"
        self._city = city
        self._bootstrap = (
            bootstrap_servers.strip() if bootstrap_servers is not None else _bootstrap_from_env()
        )
        self._demand_topic = demand_topic
        self._inventory_topic = inventory_topic
        self._poll_timeout_s = float(poll_timeout_s)
        self._max_records = int(max_records)
        self._max_retries = max(1, int(max_retries))
        self._retry_base_delay_s = max(1e-6, float(retry_base_delay_s))
        # An injected factory is itself a configuration: the tests and the integration
        # workload supply one, and a bare address is the production route.
        if consumer_factory is not None:
            self._factory: Callable[[str], FeedConsumer] | None = consumer_factory
        elif self._bootstrap:
            self._factory = _default_consumer_factory(self._bootstrap, group_id)
        else:
            self._factory = None
        self._degradation: str | None = None if self._factory is not None else NOT_CONFIGURED
        self._revision: str | None = None

    # ── declarations ────────────────────────────────────────────────────

    def provenance(self) -> SourceProvenance:
        """``EXTERNAL``: arrivals are read off a broker, not drawn from a generator.

        The declaration is checked against the implementation:
        ``scripts/audit/feed_provenance.py`` reads :meth:`poll_arrivals` statically and
        classifies an unconditionally empty body as ``STUB`` no matter what this method
        returns (R4.8). Declaring ``EXTERNAL`` therefore costs a real implementation.
        """
        return SourceProvenance.EXTERNAL

    def degradation(self) -> str | None:
        """Why the last poll was incomplete, or ``None`` if it was complete.

        Set on every poll, so a feed that recovers stops reporting degraded — and one that
        was never configured reports from construction rather than waiting for a first poll
        to fail.
        """
        return self._degradation

    def feed_revision(self) -> str | None:
        """Identity of the last record incorporated — this source's observed water mark.

        Not a broker offset: ``drain`` hands over values, not offsets. It is the last
        record's own ``order_id``, which is what the audit trail can actually check a claim
        against. ``None`` until a record has been incorporated.
        """
        return self._revision

    # ── perceive ────────────────────────────────────────────────────────

    def poll_arrivals(self, now_sim_min: float, horizon_min: float) -> list[WorldEvent]:
        """Drain real demand records and return them as ``DEMAND_ARRIVAL`` events."""
        if self._factory is None:
            self._degradation = NOT_CONFIGURED
            logger.warning(
                "external_feed_not_configured",
                topic=self._demand_topic,
                env_keys=list(BOOTSTRAP_ENV_KEYS),
            )
            return []
        if horizon_min <= 0.0:
            return []
        try:
            records = self._drain_with_retry(self._demand_topic)
        except FeedUnreachableError as exc:
            # Zero arrivals + a degradation reason. No seeded generator is consulted;
            # this class does not hold one (R4.5).
            self._degradation = UNREACHABLE
            logger.error(
                "external_feed_unreachable",
                topic=self._demand_topic,
                arrivals=0,
                fell_back_to_seeded=False,
                error=str(exc),
            )
            return []
        events, rejected = self._to_events(records, now_sim_min)
        self._degradation = RECORDS_REJECTED if rejected else None
        if events:
            self._revision = events[-1].event_id
        logger.info(
            "external_feed_polled",
            topic=self._demand_topic,
            records=len(records),
            arrivals=len(events),
            rejected=rejected,
            revision=self._revision,
        )
        return events

    def initial_inventory(self) -> dict[str, float] | None:
        """Opening stock from the inventory snapshot topic, or ``None`` if it supplies none.

        ``None`` is the R4.9 degradation signal. ``WorldRuntime`` starts the world with an
        **empty** inventory and a degraded reading rather than substituting the
        simulation's literal ``{sku_i: 100.0}`` default, because a real store's opening
        stock is not something this system is entitled to guess.
        """
        if self._factory is None:
            self._degradation = NOT_CONFIGURED
            logger.warning("external_inventory_not_configured", topic=self._inventory_topic)
            return None
        try:
            records = self._drain_with_retry(self._inventory_topic)
        except FeedUnreachableError as exc:
            self._degradation = UNREACHABLE
            logger.error(
                "external_inventory_unreachable",
                topic=self._inventory_topic,
                error=str(exc),
            )
            return None
        levels: dict[str, float] = {}
        for record in records:
            if not self._is_for_city(record):
                continue
            sku = record.get("sku_id")
            level = self._first_numeric(record, _LEVEL_KEYS)
            if isinstance(sku, str) and sku and level is not None and level >= 0.0:
                levels[sku] = level  # later snapshot for a SKU supersedes an earlier one
        if not levels:
            logger.warning(
                "external_inventory_absent",
                topic=self._inventory_topic,
                records=len(records),
                substituted_default=False,
            )
            return None
        logger.info("external_inventory_loaded", topic=self._inventory_topic, skus=len(levels))
        return levels

    # ── broker access ───────────────────────────────────────────────────

    def _drain_with_retry(self, topic: str) -> list[dict[str, Any]]:
        """:meth:`_drain_once` under Full Jitter retries (ADR-016).

        The backoff is ``synapse_common.retry.retry_with_jitter``; there is no hand-rolled
        sleep loop anywhere in this module. It is applied at call time rather than as a
        class-level decorator so the budget stays an instance setting: a class-level
        decorator captures the module constants at import, which would force every test of
        the unreachable path to pay seconds of real backoff (I-0). When the budget is
        exhausted the wrapper re-raises :class:`FeedUnreachableError` and the callers turn
        it into a degraded reading with zero arrivals.
        """
        wrapped = retry_with_jitter(
            max_retries=self._max_retries,
            base_delay=self._retry_base_delay_s,
            cap=_RETRY_CAP_S,
            retryable_exceptions=(FeedUnreachableError,),
        )(self._drain_once)
        drained: Any = wrapped(topic)
        records: list[dict[str, Any]] = drained
        return records

    def _drain_once(self, topic: str) -> list[dict[str, Any]]:
        """One reachability probe plus one drain. Raises on an unreachable feed."""
        factory = self._factory
        if factory is None:  # pragma: no cover - callers check first; belt and braces
            raise FeedUnreachableError(NOT_CONFIGURED)
        try:
            consumer = factory(topic)
        except Exception as exc:  # noqa: BLE001 - a client that cannot be built is unreachable
            raise FeedUnreachableError(f"consumer for {topic} could not be created: {exc}") from exc
        try:
            topics = consumer.reachable_topics(_METADATA_TIMEOUT_S)
            if topic not in topics:
                # Reachable cluster, absent stream. Reported as unreachable because the
                # feed this world was told to read does not exist, so no arrival can ever
                # come from it - the honest reading is degraded, not healthy-and-quiet.
                logger.warning("external_feed_topic_absent", topic=topic, advertised=len(topics))
                raise FeedUnreachableError(f"topic {topic} is not advertised by the cluster")
            return consumer.drain(max_records=self._max_records, timeout=self._poll_timeout_s)
        except FeedUnreachableError:
            raise
        except Exception as exc:  # noqa: BLE001 - any client failure is an unreachable feed
            raise FeedUnreachableError(f"{topic}: {exc}") from exc
        finally:
            try:
                consumer.close()
            except Exception as exc:  # noqa: BLE001 - a failed close must not mask the read
                logger.warning("external_feed_consumer_close_failed", topic=topic, error=str(exc))

    # ── record mapping ──────────────────────────────────────────────────

    def _to_events(
        self, records: Sequence[Mapping[str, Any]], now_sim_min: float
    ) -> tuple[list[WorldEvent], int]:
        """Map broker records to arrivals, returning ``(events, rejected_count)``.

        Pure given its arguments (no clock, no I/O, no RNG) so the ingestion property in
        task 10.13 can assert R4.1's quantity equality without a broker.
        """
        events: list[WorldEvent] = []
        rejected = 0
        for record in records:
            if not self._is_for_city(record):
                continue
            quantity = self._first_numeric(record, _QUANTITY_KEYS)
            sku = record.get("sku_id")
            store = record.get("store_id")
            if quantity is None or quantity <= 0.0 or not isinstance(sku, str) or not sku:
                rejected += 1
                logger.warning(
                    "external_feed_record_rejected",
                    topic=self._demand_topic,
                    reason="missing_or_non_positive_quantity_or_sku",
                )
                continue
            events.append(
                WorldEvent(
                    event_id=self._event_id(record),
                    kind=WorldEventKind.DEMAND_ARRIVAL,
                    city=self._city,
                    # Stamped at the observation instant: the record carries a wall-clock
                    # timestamp, not a simulation minute, and translating one into the
                    # other would invent precision the feed never supplied.
                    sim_time_min=round(max(0.0, now_sim_min), 4),
                    store_id=store if isinstance(store, str) and store else None,
                    sku_id=sku,
                    quantity=float(quantity),
                )
            )
        if rejected:
            logger.warning(
                "external_feed_records_rejected",
                topic=self._demand_topic,
                rejected=rejected,
                accepted=len(events),
            )
        return events, rejected

    def _is_for_city(self, record: Mapping[str, Any]) -> bool:
        """Whether the record belongs to this world. A record with no city is not assumed."""
        return record.get("city") == self._city

    @staticmethod
    def _first_numeric(record: Mapping[str, Any], keys: Sequence[str]) -> float | None:
        """First key in ``keys`` holding a real number, coerced to ``float``; else ``None``.

        ``bool`` is excluded deliberately: ``True`` is an ``int`` in Python, and a feed
        that sent ``quantity: true`` must be rejected rather than read as one unit.
        """
        for key in keys:
            value = record.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                return float(value)
        return None

    @staticmethod
    def _event_id(record: Mapping[str, Any]) -> str:
        """Deterministic identity for a record: its ``order_id``, else a digest of its bytes.

        Deterministic because R4.6 requires a replayed trace to convene the same decision
        identifiers in the same order; a random id would make a replay incomparable.
        """
        order_id = record.get("order_id")
        if isinstance(order_id, str) and order_id:
            return f"ext:{order_id}"
        canonical = json.dumps(dict(record), sort_keys=True, separators=(",", ":"), default=str)
        return f"ext:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"
