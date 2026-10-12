# Feature: decision-quality-proof, Property 69: Real-feed ingestion is provenanced and records what
# it consumed
"""Property 69 -- real-feed ingestion is provenanced (its R8.3 clause; R8.17 is withdrawn).

Feature: decision-quality-proof, task 19.3. Requirement **R8.3**.

Scope since 2026-10-01
----------------------

Property 69 had two clauses over two unrelated ingestion paths. The training-row clause
(R8.17: every ingestion records the dataset identity, revision and rows consumed) quantified
over ``data_fabric/ingest/m5.py::record_ingestion``. M5 was declined on 2026-09-29 and that
module was removed as dead code (C44), so the clause has no subject left: it is WITHDRAWN in
the design, and its three properties were deleted with the module. The world-seam clause
(R8.3) is untouched -- ``ExternalFeedSource`` is production code -- and its three properties
below are kept. Deleting them would have weakened coverage of live code, and two of their
assertions exist nowhere else in the tree: the ``external_feed_records_rejected`` degradation
under unusable records, and the closure of ``SOURCE_CLASSES`` at three values.

The trap this file was written to avoid, stated first
-----------------------------------------------------

Task 19.3 names it: the predecessor's Property 29 "currently passes over a stub", because
``ExternalFeedSource.poll_arrivals`` returned ``[]``. A property whose conclusion is "nothing
bad was produced" is satisfied perfectly by a source that produces nothing, and that is the
same vacuity as ``None == None`` agreeing in a dead pin extractor.

**Every property here therefore asserts NON-EMPTINESS before it asserts anything else.** The
feed strategy generates at least one usable record, and each property asserts the produced
count is positive *and* equals the count the input implies. A stub returning ``[]`` fails
these on the first assertion rather than passing them all.

**Conflict surfaced, not resolved.** ``tasks.md`` 19.3 states the stub as present tense. On disk
it is not: ``packages/synapse_common/world/source.py`` records that task 10.11 built the real
hop, ``poll_arrivals`` drains through the ``FeedConsumer`` seam, and
``scripts/audit/feed_provenance.py`` classifies an unconditionally-empty body as ``STUB``
whatever the class declares. So the task's *instruction* is discharged here (assert
non-emptiness, drive a source that yields rows) while its *premise* is stale. Recorded rather
than quietly corrected -- the reader who next opens 19.3 needs to know which of the two is true.

The world seam is the only path that carries a source class
-----------------------------------------------------------

``ExternalFeedSource`` declares ``SourceProvenance.EXTERNAL`` when the real feed drives the twin
(R8.3), and only this path carries ``source_class``. ``SourceProvenance`` is a closed set of
exactly ``SEEDED``, ``EXTERNAL`` and ``STUB``, pinned by
``orchestrator.audit.models.SOURCE_CLASSES`` and by a SQL ``CHECK`` in
``0007_decision_data_provenance.sql``. Nothing here adds a fourth, and
:func:`test_the_declared_class_is_one_of_the_three_committed_values` asserts the closure by
reading the committed tuple rather than a local literal. If a training-row ingestion path is
ever admitted again, it is a different path and must not gain a fourth value to look uniform.

Why the properties drive the real class
---------------------------------------

Through the ``FeedConsumer`` protocol seam, exactly as
``tests/verify/test_nonsynthetic_ingestion_replay_property.py`` does: ``ExternalFeedSource``
takes a ``consumer_factory``, and an injected factory **is** a configuration, so the source
under test is the production one taking the production retry path and the production record
mapping. No broker, no container, no port -- the seam is what makes a category-1 workload into
a pure one.

Budget and locus
----------------

``@pytest.mark.slow``, selected by ``ci.yml::uplift-verify``'s slow step (``-m "slow"``,
``HYPOTHESIS_PROFILE=heavy``, ``tests/verify`` in that step's path list). ``max_examples`` is
**inherited from the profile** and appears nowhere in this file (I-0's authoring rule). The retry
budget is set to fractions of a millisecond: ADR-016's backoff policy is proven in
``packages/tests/test_retry.py`` and this property must not pay real backoff.

**Validates: Requirements 8.3.**
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.world.models import SourceProvenance
from synapse_common.world.source import DEMAND_TOPIC, ExternalFeedSource

from orchestrator.audit.models import SOURCE_CLASSES

if TYPE_CHECKING:  # annotation-only
    from collections.abc import Callable

pytestmark = pytest.mark.slow

CITY: Final[str] = "fixture-city"


# ---------------------------------------------------------------------------
# The world seam: a consumer that actually hands over records
# ---------------------------------------------------------------------------


class _YieldingConsumer:
    """A ``FeedConsumer`` that advertises its topic and drains real records.

    Structurally a ``FeedConsumer`` and nothing more, so the source exercises its production
    path. It exists because the alternative -- a consumer that drains ``[]`` -- is precisely the
    stub whose vacuity this file was written to refuse.
    """

    def __init__(self, topic: str, records: list[dict[str, Any]]) -> None:
        self._topic = topic
        self._records = records
        self.drained = 0
        self.closed = 0

    def reachable_topics(self, timeout: float = 5.0) -> tuple[str, ...]:
        return (self._topic,)

    def drain(self, *, max_records: int = 5000, timeout: float = 1.0) -> list[dict[str, Any]]:
        self.drained += 1
        return list(self._records[:max_records])

    def close(self) -> None:
        self.closed += 1


def _factory(records: list[dict[str, Any]]) -> Callable[[str], _YieldingConsumer]:
    """A consumer factory that hands every topic the same non-empty record batch."""

    def build(topic: str) -> _YieldingConsumer:
        return _YieldingConsumer(topic, records)

    return build


def _feed(records: list[dict[str, Any]]) -> ExternalFeedSource:
    """A *configured*, *reachable* external feed that yields ``records``.

    The retry budget is fractions of a millisecond: ADR-016's policy is proven in
    ``packages/tests/test_retry.py`` and this property must not pay real backoff (I-0).
    """
    return ExternalFeedSource(
        city=CITY,
        consumer_factory=_factory(records),
        demand_topic=DEMAND_TOPIC,
        poll_timeout_s=0.01,
        max_retries=1,
        retry_base_delay_s=1e-4,
    )


#: A usable demand record: this city, a non-empty SKU, a strictly positive quantity. Every
#: field the source requires is present, so the batch cannot be silently emptied by rejection
#: -- which would reintroduce the vacuity through the back door.
_usable_record = st.builds(
    lambda sku, store, quantity, order: {
        "city": CITY,
        "sku_id": sku,
        "store_id": store,
        "quantity": quantity,
        "order_id": order,
    },
    sku=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=12),
    store=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=12),
    quantity=st.integers(min_value=1, max_value=500),
    order=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=16),
)

#: **At least one.** The single most important line in this file.
_usable_batch = st.lists(_usable_record, min_size=1, max_size=12)


# ---------------------------------------------------------------------------
# R8.3 -- the world seam is provenanced, and it yields something
# ---------------------------------------------------------------------------


@given(records=_usable_batch)
def test_the_real_feed_yields_every_usable_record_as_a_provenanced_arrival(
    records: list[dict[str, Any]],
) -> None:
    """R8.3: a real feed driving the twin produces arrivals and declares ``EXTERNAL``.

    Three assertions in the order that matters. **First** that the arrival list is non-empty --
    a stub fails here and never reaches the rest. **Then** that its length equals the number of
    usable records supplied, so the source cannot pass by yielding one arrival out of twelve.
    **Then** the declaration, which is only meaningful once there is something to declare over:
    ``EXTERNAL`` beside an empty poll is the ``STUB`` case ``feed_provenance.py`` exists to
    catch.

    The quantity equality is asserted per arrival because R8.3's point is that a record reaches
    the world *as published* -- no coercion, no substitution, no seeded padding.
    """
    source = _feed(records)

    events = source.poll_arrivals(now_sim_min=0.0, horizon_min=5.0)

    assert events, "a real feed that yields nothing is a stub, whatever the class declares"
    assert len(events) == len(records)
    assert source.provenance() is SourceProvenance.EXTERNAL
    assert source.degradation() is None, "a reachable feed with usable records is not degraded"
    for event, record in zip(events, records, strict=True):
        assert event.quantity == float(record["quantity"])
        assert event.sku_id == record["sku_id"]
        assert event.city == CITY
    assert source.feed_revision() == events[-1].event_id, (
        "the water mark must name the last record actually incorporated, or the audit trail "
        "cannot check a claim about what was consumed"
    )


@given(records=_usable_batch)
def test_the_declared_class_is_one_of_the_three_committed_values(
    records: list[dict[str, Any]],
) -> None:
    """``SourceProvenance`` is closed at three, read from the committed tuple.

    Read from ``orchestrator.audit.models.SOURCE_CLASSES`` rather than a local literal, so a
    fourth class added to the model is caught here instead of being covered automatically. The
    tuple is also pinned by a SQL ``CHECK`` in ``0007_decision_data_provenance.sql``: a fourth
    value would be rejected by the database after passing every test that used a literal.
    """
    source = _feed(records)

    declared = source.provenance()

    assert declared.value in SOURCE_CLASSES
    assert len(SOURCE_CLASSES) == 3, (
        "SourceProvenance is a closed set of SEEDED / EXTERNAL / STUB; a fourth value needs the "
        "SQL CHECK constraint changed too, and this assertion is where that conversation starts"
    )
    assert declared is SourceProvenance.EXTERNAL


@given(records=_usable_batch, extra=st.integers(min_value=1, max_value=6))
def test_unusable_records_are_rejected_and_reported_never_substituted(
    records: list[dict[str, Any]], extra: int
) -> None:
    """An unreadable record is dropped and *counted*, never given a plausible value.

    The complement of the non-emptiness clause, and it needs the same care: a source that
    silently coerced ``quantity: null`` to ``1.0`` would satisfy every count assertion above
    while fabricating demand. So the batch is padded with records the source must refuse, and
    the assertion is that the arrivals equal the **usable** count exactly -- neither padded nor
    emptied -- with the degradation reason reported.
    """
    unusable: list[dict[str, Any]] = [
        {"city": CITY, "sku_id": "unusable", "store_id": "s", "quantity": None}
        for _ in range(extra)
    ]
    source = _feed([*records, *unusable])

    events = source.poll_arrivals(now_sim_min=0.0, horizon_min=5.0)

    assert events, "the usable records must still arrive"
    assert len(events) == len(records), "a rejected record must not become a fabricated arrival"
    assert source.degradation() == "external_feed_records_rejected"
    assert source.provenance() is SourceProvenance.EXTERNAL
