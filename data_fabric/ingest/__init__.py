"""External-dataset ingestion records and the statistics derived from them (design E4a.3).

Feature: decision-quality-proof, task 7.3 + 7.4.

**The straddle this package sits on, stated once and up front.** SYNAPSE has two unrelated
"ingestion" paths and only one of them carries a provenance field:

* **The world seam.** ``packages/synapse_common/world/source.py::ExternalFeedSource`` reads
  **Kafka topics** into ``WorldState``. That path carries ``WorldState.source_class``, typed
  ``SourceProvenance`` and declared by ``WorldSource.provenance()``: ``SimWorldSource`` ->
  ``SEEDED``, ``ExternalFeedSource`` -> ``EXTERNAL``, overridden to ``STUB`` by
  ``scripts/audit/feed_provenance.py`` when ``poll_arrivals`` is unconditionally empty.
  R8.3 is satisfied there and only there.
* **The training-row path.** This package. It reads committed dataset files, records what
  was consumed, and derives aggregate statistics. It carries **no** provenance field and
  adds none.

Nothing here touches ``SourceProvenance``, which is a closed set of exactly ``SEEDED``,
``EXTERNAL`` and ``STUB``, pinned by ``orchestrator.audit.models.SOURCE_CLASSES`` and by a
SQL ``CHECK`` constraint in the decision-data-provenance migration. Nothing here touches
``Provenance.feature_source`` either: it is a closed ``StrEnum`` of ``FEAST``, ``FALLBACK``
and ``DIRECT`` describing where *features* were fetched, and
``scripts/audit/runtime_substance.py`` fails the demand_prophet probe unless it reads
``FEAST``. A fourth value in either enum would break a gate and a database constraint to
express something neither field is about.

The two paths are kept separate here deliberately rather than unified for tidiness. R8's own
refinement notes record the straddle as real; a shared abstraction over them would put a
Kafka-shaped provenance value on a file-shaped ingestion and make both harder to audit.
"""

from __future__ import annotations

from data_fabric.ingest.m5 import (
    DEFAULT_COLUMNS,
    DEFAULT_DISCOUNT_THRESHOLD,
    FileDigest,
    IngestionRefusedError,
    M5AggregateStatistics,
    M5Columns,
    M5IngestRecord,
    ShapeEstimate,
    day_of_week_shape,
    digest_file,
    extract_statistics,
    intra_day_intensity_shape,
    promotion_uplift_shape,
    record_ingestion,
)

__all__ = [
    "DEFAULT_COLUMNS",
    "DEFAULT_DISCOUNT_THRESHOLD",
    "FileDigest",
    "IngestionRefusedError",
    "M5AggregateStatistics",
    "M5Columns",
    "M5IngestRecord",
    "ShapeEstimate",
    "day_of_week_shape",
    "digest_file",
    "extract_statistics",
    "intra_day_intensity_shape",
    "promotion_uplift_shape",
    "record_ingestion",
]
