# Feature: decision-quality-proof, Property 69: Real-feed ingestion is provenanced and records what
# it consumed
"""Property 69 -- real-feed ingestion is provenanced and records what it consumed.

Feature: decision-quality-proof, task 19.3. Requirements **R8.3**, **R8.17**.

The trap this file was written to avoid, stated first
-----------------------------------------------------

Task 19.3 names it: the predecessor's Property 29 "currently passes over a stub", because
``ExternalFeedSource.poll_arrivals`` returned ``[]``. A property whose conclusion is "nothing
bad was produced" is satisfied perfectly by a source that produces nothing, and that is the
same vacuity as ``None == None`` agreeing in a dead pin extractor.

**Every property here therefore asserts NON-EMPTINESS before it asserts anything else.** The
feed strategy generates at least one usable record, the ingestion fixture writes at least one
data row, and each property asserts the produced count is positive *and* equals the count the
input implies. A stub returning ``[]`` fails these on the first assertion rather than passing
them all.

**Conflict surfaced, not resolved.** ``tasks.md`` 19.3 states the stub as present tense. On disk
it is not: ``packages/synapse_common/world/source.py`` records that task 10.11 built the real
hop, ``poll_arrivals`` drains through the ``FeedConsumer`` seam, and
``scripts/audit/feed_provenance.py`` classifies an unconditionally-empty body as ``STUB``
whatever the class declares. So the task's *instruction* is discharged here (assert
non-emptiness, drive a source that yields rows) while its *premise* is stale. Recorded rather
than quietly corrected -- the reader who next opens 19.3 needs to know which of the two is true.

The straddle, which this file must not collapse
----------------------------------------------

R8.17 and R8.3 govern **two unrelated ingestion paths**, and conflating them is the failure mode
the licence register's own note warns about:

* **The training-row path** -- ``data_fabric/ingest/m5.py::record_ingestion``. Records dataset
  identity, dataset revision and rows consumed (R8.17). It carries **no** ``source_class``, and
  :func:`test_the_training_row_record_carries_no_source_class` asserts that absence, so a future
  edit cannot quietly add a fourth provenance value here.
* **The world seam** -- ``ExternalFeedSource``. Declares ``SourceProvenance.EXTERNAL`` when the
  real feed drives the twin (R8.3). Only this path carries ``source_class``.

``SourceProvenance`` is a closed set of exactly ``SEEDED``, ``EXTERNAL`` and ``STUB``, pinned by
``orchestrator.audit.models.SOURCE_CLASSES`` and by a SQL ``CHECK`` in
``0007_decision_data_provenance.sql``. Nothing here adds a fourth, and
:func:`test_the_declared_class_is_one_of_the_three_committed_values` asserts the closure by
reading the committed tuple rather than a local literal.

Why the world-seam half drives the real class
---------------------------------------------

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

**Validates: Requirements 8.3, 8.17.**
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.world.models import SourceProvenance
from synapse_common.world.source import DEMAND_TOPIC, ExternalFeedSource

from data_fabric.ingest.m5 import (
    IngestionRefusedError,
    M5IngestRecord,
    digest_file,
    record_ingestion,
)
from data_fabric.licence import artifact_digest
from orchestrator.audit.models import SOURCE_CLASSES

if TYPE_CHECKING:  # annotation-only
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.slow

CITY: Final[str] = "fixture-city"
DATASET: Final[str] = "fixture-dataset"
REVISION: Final[str] = "rev-1"
_FIXED_TIME: Final[datetime] = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


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


# ---------------------------------------------------------------------------
# R8.17 -- the training-row path records what it consumed
# ---------------------------------------------------------------------------


def _licence(path: Path) -> Path:
    """A confirmed licence artifact for ``DATASET`` at ``REVISION``.

    Deliberately fictional. Exercising the *admitted* branch with a real dataset's identity
    would put a plausible licence record in the test tree where a future reader could mistake it
    for the real one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "datasets": [
                    {
                        "dataset_id": DATASET,
                        "licence_id": "FIXTURE-LICENCE-1.0",
                        "licence_text_uri": "https://example.invalid/fixture/licence.txt",
                        "read_date": "2026-09-01",
                        "permitted_use": "fixture use only; this describes no real dataset",
                        "dataset_revision": REVISION,
                        "redistribution": "permitted",
                        "confirmation": {
                            "confirmed": True,
                            "confirmed_by": "fixture-operator",
                            "procedure": "fixture: no terms were read",
                        },
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _csv(path: Path, rows: int) -> Path:
    """A sales fixture with ``rows`` data rows behind one header row."""
    lines = ["id,d_1", *[f"series-{index},{index}" for index in range(1, rows + 1)]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@given(rows=st.integers(min_value=1, max_value=40))
def test_the_ingestion_record_states_identity_revision_and_rows_consumed(
    tmp_path: Path, rows: int
) -> None:
    """R8.17: identity, revision and rows consumed, with rows equal to what was read.

    ``rows`` is drawn from **1** upward, never 0. A record reporting ``rows: 0`` would satisfy
    "the ingestion recorded the number of rows consumed" while consuming nothing, which is the
    tally-shaped version of the stub. The equality against ``digest_file``'s own count is what
    makes the number a measurement rather than a copy of the parameter: two independent readers
    of the same bytes must agree.
    """
    licence = _licence(tmp_path / "dataset-licences.yaml")
    data = _csv(tmp_path / "sales.csv", rows)

    record = record_ingestion(
        dataset_id=DATASET,
        dataset_revision=REVISION,
        files=[data],
        ingested_at=_FIXED_TIME,
        licence_path=licence,
    )

    assert record.rows > 0, "an ingestion that consumed nothing is not an ingestion"
    assert record.rows == rows
    assert record.rows == digest_file(data).data_rows
    assert record.dataset_id == DATASET
    assert record.dataset_revision == REVISION
    assert record.files, "the consumed files must be enumerated, not summarised"
    assert record.files[0].sha256.startswith("sha256:")
    assert record.licence_artifact_digest == artifact_digest(licence)
    # Canonical JSON, so two records over the same facts are byte-identical.
    assert record.canonical_json() == M5IngestRecord.model_validate(
        record.model_dump(mode="json")
    ).canonical_json()


@given(rows=st.integers(min_value=1, max_value=40))
def test_the_training_row_record_carries_no_source_class(tmp_path: Path, rows: int) -> None:
    """The straddle, asserted structurally: only the world seam carries ``source_class``.

    R8.17's training-row path and R8.3's world seam are two unrelated ingestion paths. Asserting
    the *absence* of the field is what stops a later edit adding a fourth ``SourceProvenance``
    value here to make the two paths look uniform -- the three values are pinned by
    ``SOURCE_CLASSES`` and by a SQL ``CHECK``, and a fourth would be rejected by the database
    after passing every test that did not look.
    """
    licence = _licence(tmp_path / "dataset-licences.yaml")
    data = _csv(tmp_path / "sales.csv", rows)

    record = record_ingestion(
        dataset_id=DATASET,
        dataset_revision=REVISION,
        files=[data],
        ingested_at=_FIXED_TIME,
        licence_path=licence,
    )

    fields = set(M5IngestRecord.model_fields)
    assert "source_class" not in fields
    assert "provenance" not in fields
    assert "source_class" not in record.canonical_json()
    # And the record does carry the binding that IS its provenance: which terms were in force.
    assert {"licence_artifact", "licence_artifact_digest", "licence_id"} <= fields


@given(
    rows=st.integers(min_value=1, max_value=8),
    wrong_revision=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=10
    ),
)
def test_an_unlicensed_or_mismatched_ingestion_cannot_be_recorded_at_all(
    tmp_path: Path, rows: int, wrong_revision: str
) -> None:
    """The refusal path, proven by construction rather than by inspection.

    R8.16 is enforceable only if an unlicensed ingestion cannot be recorded, so the assertion is
    that ``record_ingestion`` **raises** rather than returning a record with a flag on it. A
    ``refused: true`` row would leave something a later reader could mistake for evidence that
    the data was ingested under known terms.

    ``wrong_revision`` is filtered against the licensed revision inside the body rather than by a
    Hypothesis ``assume``: the equal case is not an uninteresting draw to be discarded, it is the
    admitted case, and asserting it succeeds is what proves the refusal is discriminating rather
    than total.
    """
    licence = _licence(tmp_path / "dataset-licences.yaml")
    data = _csv(tmp_path / "sales.csv", rows)

    if wrong_revision == REVISION:
        admitted = record_ingestion(
            dataset_id=DATASET,
            dataset_revision=wrong_revision,
            files=[data],
            ingested_at=_FIXED_TIME,
            licence_path=licence,
        )
        assert admitted.rows == rows
    else:
        with pytest.raises(IngestionRefusedError, match=REVISION):
            record_ingestion(
                dataset_id=DATASET,
                dataset_revision=wrong_revision,
                files=[data],
                ingested_at=_FIXED_TIME,
                licence_path=licence,
            )

    with pytest.raises(IngestionRefusedError, match="declares no licence entry"):
        record_ingestion(
            dataset_id=f"{DATASET}-undeclared",
            dataset_revision=REVISION,
            files=[data],
            ingested_at=_FIXED_TIME,
            licence_path=licence,
        )
