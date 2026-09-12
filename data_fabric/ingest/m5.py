"""M5 ingestion record and aggregate-statistics extraction (design E4a.3; R8.16, R8.17, R5.11).

Feature: decision-quality-proof, task 7.3 + 7.4.

Design **E4a.3** puts the ingestion record and the statistics extraction in **one** module,
and this file follows the design rather than ``tasks.md``'s two-module split
(``data_fabric/etl/m5_ingest.py`` + ``data_fabric/etl/m5_statistics.py``). The reason the
design's shape is the right one here: the statistics are a *product* of an ingestion and
carry the same identity fields, so splitting them puts the dataset revision in two files
that must be kept in step by hand. That is recorded rather than resolved silently -- see the
conflict note at the end of this docstring.

Two halves, and they answer different questions.

**1. The ingestion record (R8.17).** What was consumed: the dataset identity, the dataset
revision, the row count (``rows`` is already a required registry key), a SHA-256 digest per
consumed file, and -- the clause that makes the record more than a tally -- the digest of the
**licence artifact in force at ingestion time**. Without that binding, "we had permission"
is a claim about a file that has since been edited. With it, the exact bytes of the terms
that were in force are recoverable from any ingestion record.

:func:`record_ingestion` **refuses** rather than annotates in three cases, because R8.16's
"the licence check reports on the change that performs the first ingestion" is only
enforceable if an unlicensed ingestion cannot be recorded at all (I-6: a hard guardrail
beats a learned policy):

* the licence artifact declares no entry for ``dataset_id``;
* the entry is not :attr:`~data_fabric.licence.DatasetLicence.confirmed` -- the refusal
  **names every unconfirmed field**, so the message is a work list rather than a verdict;
* the entry's ``dataset_revision`` disagrees with the revision being ingested, so the terms
  that were read and the bytes that were consumed cannot drift apart unnoticed.

**A first ingestion is reported as such.** ``first_ingestion`` is a recorded field, computed
from the dataset identities previously ingested that the caller supplies. It is not derived
from "the record store happens to be empty", because that reading makes a lost store look
like a first ingestion; and it is not omitted, because folding the first ingestion into the
steady-state path is precisely what makes R8.16 unenforceable after the fact.

**2. The aggregate statistics (R5.11, R8.17).** Three shapes, which E2c.2's policy file
consumes so that no demand literal lands in ``engine.py``:

* the **day-of-week** shape -- derivable, and derived;
* the **promotion-uplift** shape -- derivable only through a declared price proxy, and
  labelled as one;
* the **intra-day intensity** shape -- **not derivable from this dataset**, and reported
  ``unavailable``.

That third result is a finding, not a gap in this module. M5's observation columns are
**daily** totals per series; an hour-of-day shape cannot be recovered from daily
aggregates by any amount of arithmetic. R5.11 asks for a shape "calibrated from statistics
derived from the Real_Data_Feed rather than from invented literals", so producing a
plausible intra-day curve here -- a lunch peak and an evening peak, say -- would be the
invention R5.11 forbids while *appearing* to satisfy it. The shape is therefore reported
``unavailable`` with the granularity gap named, and :class:`ShapeEstimate` structurally
forbids an ``unavailable`` shape from carrying values, so no downstream reader can pick up
numbers from it. Whatever calibrates the intra-day shape must come from somewhere else, and
that decision belongs to task 12.1 with the evidence in hand.

This also foreshadows R8.12's documented domain gap: daily grocery demand and 10-minute
quick-commerce demand are distinct domains, and the missing intra-day shape is the sharpest
single piece of evidence for how distinct.

**Execution locus.** :func:`extract_statistics` is a bulk streaming read over roughly 42,000
hierarchical daily series and belongs to ``ci.yml::training-smoke`` -- a category-3/4
workload under **I-0** that must not run on a development machine. The module is written to
be import-safe and testable on a small fixture: nothing runs at import, every path is a
parameter, and every reader streams (no full-file materialisation, no pandas). Correctness
is established on fixtures of a few rows; scale is established in CI.

**Every failure names its subject and yields ``unavailable``.** A missing column, a
non-numeric observation cell, a short row, a degenerate normaliser -- each returns an
``unavailable`` :class:`ShapeEstimate` naming what stopped it. None of them returns a shape
with zeros in it. A zero-filled shape is a measurement claim, and defaulting an unreadable
cell to zero would silently flatten the very shape being measured (I-7).

**Conflict surfaced, not resolved silently.** ``tasks.md`` 7.3 also names an
"ingestion-record block" inside the licence declaration. That is not implemented: the
declaration is a committed statement of terms, and writing runtime ingestion facts back into
it would make the artifact that ingestion is checked against mutable by ingestion. The
binding runs the other way here -- the record pins the artifact's digest. Design E4a.3
supports this reading ("Records ``dataset_id``, ``dataset_revision`` and ``rows``" as a
property of the ingestion, not of the declaration).

Every read uses ``encoding='utf-8'`` (E-S13-07). Nothing here prints; ``structlog`` only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics as stats
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

import structlog
from pydantic import BaseModel, ConfigDict, model_validator

from data_fabric.licence import (
    ARTIFACT_PATH,
    LicenceArtifactError,
    artifact_digest,
    load_licence_document,
)

if TYPE_CHECKING:  # annotation-only: nothing below is constructed at runtime
    from collections.abc import Iterator, Sequence
    from datetime import datetime
    from pathlib import Path

_LOG = structlog.get_logger(__name__)

#: Chunk size for file digests. Bounded so a multi-gigabyte CSV is never held in memory.
_DIGEST_CHUNK: Final[int] = 1 << 20

#: Minimum distinct calendar weeks before a high-versus-low discount split means anything.
#: Four is not a power calculation -- it is the point below which the split has no spread to
#: describe. The uplift estimate is a shape for a simulator, not a hypothesis test; when a
#: powered estimate is needed the requirement that needs it will say so.
MIN_UPLIFT_WEEKS: Final[int] = 4

#: A week's price counts as discounted when it falls this far below that (item, store)
#: pair's own maximum observed price. Declared here, echoed into every estimate's ``basis``,
#: and never inferred from the data: a threshold chosen to make an uplift appear is not a
#: measurement.
DEFAULT_DISCOUNT_THRESHOLD: Final[float] = 0.05

ShapeStatus = Literal["derived", "unavailable"]

__all__ = [
    "DEFAULT_COLUMNS",
    "DEFAULT_DISCOUNT_THRESHOLD",
    "MIN_UPLIFT_WEEKS",
    "FileDigest",
    "IngestionRefusedError",
    "M5AggregateStatistics",
    "M5Columns",
    "M5IngestRecord",
    "ShapeEstimate",
    "ShapeStatus",
    "day_of_week_shape",
    "digest_file",
    "extract_statistics",
    "intra_day_intensity_shape",
    "promotion_uplift_shape",
    "record_ingestion",
]


class IngestionRefusedError(RuntimeError):
    """An ingestion was refused because its licence precondition does not hold.

    Raised, not returned. A refused ingestion has no record to report: producing one with a
    ``refused: true`` field would leave a row that a later reader could mistake for
    evidence that the data was ingested under known terms.
    """


class M5Columns(BaseModel):
    """The column names the readers expect, declared rather than scattered as literals.

    These are **expectations about the source files**, not facts this repository has
    verified -- no M5 file has been read here. That is exactly why they are parameters: when
    a header does not carry one of them, the affected shape reports ``unavailable`` naming
    the missing column, so a wrong expectation surfaces as a named absence instead of a
    silently empty result.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Prefix of the daily observation columns in the sales file (``d_1``, ``d_2``, ...).
    day_prefix: str = "d_"
    #: Calendar column holding the day identifier that matches a sales observation column.
    calendar_day: str = "d"
    #: Calendar column holding the week identifier.
    calendar_week: str = "wm_yr_wk"
    #: Calendar column holding the numeric day-of-week index.
    calendar_wday: str = "wday"
    #: Optional calendar column holding the weekday's name. When present the day-of-week
    #: shape labels itself from the data; when absent it falls back to ``wday=<n>``. Labels
    #: are read rather than asserted, so this module never states which index is Monday.
    calendar_weekday_name: str = "weekday"
    #: Price-file columns.
    price_item: str = "item_id"
    price_store: str = "store_id"
    price_week: str = "wm_yr_wk"
    price_value: str = "sell_price"


DEFAULT_COLUMNS: Final[M5Columns] = M5Columns()


class ShapeEstimate(BaseModel):
    """One aggregate shape, or an explicit record of why it could not be derived.

    The invariant enforced below is the whole point of the type: an ``unavailable`` estimate
    **carries no values**. Without it, a partially computed shape could ship numbers under
    an honest-looking status, and the first consumer to read ``values`` would calibrate
    against them. ``derived`` symmetrically requires at least one value and one label per
    value, so a "derived" shape with nothing in it cannot exist either.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    status: ShapeStatus
    basis: str
    labels: tuple[str, ...]
    values: tuple[float, ...]
    rows_consumed: int
    detail: str

    @model_validator(mode="after")
    def _values_match_status(self) -> ShapeEstimate:
        if self.status == "unavailable" and self.values:
            raise ValueError(
                f"shape {self.name!r} is unavailable but carries {len(self.values)} "
                "value(s): an unavailable shape must carry none, or a consumer will "
                "calibrate against numbers nothing measured (I-7)"
            )
        if self.status == "derived" and not self.values:
            raise ValueError(
                f"shape {self.name!r} claims to be derived but carries no values"
            )
        if len(self.labels) != len(self.values):
            raise ValueError(
                f"shape {self.name!r} carries {len(self.labels)} label(s) for "
                f"{len(self.values)} value(s): an unlabelled value is an uninterpretable "
                "one"
            )
        return self

    @property
    def derived(self) -> bool:
        return self.status == "derived"


class M5AggregateStatistics(BaseModel):
    """The three shapes one extraction produced, bound to the revision they came from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    dataset_revision: str
    rows: int
    intra_day_intensity: ShapeEstimate
    day_of_week: ShapeEstimate
    promotion_uplift: ShapeEstimate
    notes: tuple[str, ...]

    @property
    def shapes(self) -> tuple[ShapeEstimate, ...]:
        return (self.intra_day_intensity, self.day_of_week, self.promotion_uplift)

    @property
    def unavailable_shapes(self) -> tuple[str, ...]:
        """Names of the shapes that could not be derived, so a reader sees them first."""
        return tuple(shape.name for shape in self.shapes if not shape.derived)

    def canonical_json(self) -> str:
        """Canonical JSON: ``sort_keys=True``, no whitespace. Stable across runs."""
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )


class FileDigest(BaseModel):
    """One consumed file: its path, its digest, its size and its data-row count."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    sha256: str
    size_bytes: int
    data_rows: int


class M5IngestRecord(BaseModel):
    """What one ingestion consumed, and under which recorded terms (R8.17).

    ``licence_artifact_digest`` is the field that makes the rest verifiable after the fact:
    the recorded ``licence_id`` and ``licence_read_date`` are copies, and a copy is only as
    trustworthy as the pointer beside it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    dataset_revision: str
    rows: int
    files: tuple[FileDigest, ...]
    licence_artifact: str
    licence_artifact_digest: str
    licence_id: str
    licence_read_date: str
    first_ingestion: bool
    ingested_at: str

    def canonical_json(self) -> str:
        """Canonical JSON: ``sort_keys=True``, no whitespace. Stable across runs."""
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )


@dataclass(frozen=True)
class _CalendarIndex:
    """The calendar joins a sales observation column to a week and a day-of-week.

    Internal, so a plain frozen dataclass rather than a Pydantic model: nothing here is a
    recorded fact that leaves the module, it is a lookup table built and discarded inside
    one extraction.
    """

    wday_by_day: dict[str, int]
    week_by_day: dict[str, str]
    label_by_wday: dict[int, str]
    rows: int


# ---------------------------------------------------------------------------
# Digests and the ingestion record
# ---------------------------------------------------------------------------


def digest_file(path: Path) -> FileDigest:
    """Stream ``path`` once, returning its digest, size and data-row count.

    ``data_rows`` counts newline-delimited lines minus one for the header row, which is the
    shape every file in this dataset family has. A file with no trailing newline still
    counts its last line, because otherwise the row count would silently differ by one
    between two byte-identical exports that disagree only about the final byte.
    """
    if not path.is_file():
        raise IngestionRefusedError(f"consumed file not found: {path.as_posix()}")
    digest = hashlib.sha256()
    size = 0
    newlines = 0
    ends_with_newline = True
    with path.open("rb") as handle:
        while chunk := handle.read(_DIGEST_CHUNK):
            digest.update(chunk)
            size += len(chunk)
            newlines += chunk.count(b"\n")
            ends_with_newline = chunk.endswith(b"\n")
    lines = newlines if ends_with_newline else newlines + 1
    if size == 0:
        lines = 0
    return FileDigest(
        path=path.as_posix(),
        sha256=f"sha256:{digest.hexdigest()}",
        size_bytes=size,
        data_rows=max(lines - 1, 0),
    )


def record_ingestion(
    *,
    dataset_id: str,
    dataset_revision: str,
    files: Sequence[Path],
    ingested_at: datetime,
    licence_path: Path = ARTIFACT_PATH,
    previously_ingested: Sequence[str] = (),
) -> M5IngestRecord:
    """Record one ingestion, or refuse it naming exactly what is missing (R8.16, R8.17).

    Refusal order -- first match wins, and each refusal names its subject:

    0. the licence artifact cannot be read at all -> refuse quoting the read error. "Cannot
       be read" must never collapse into "no restriction found".
    1. the artifact declares no entry for ``dataset_id`` -> refuse naming the identity and
       the artifact. An ingestion of an undeclared dataset is the case R8.16 exists for.
    2. the entry is not confirmed -> refuse **naming every unconfirmed field**, so the
       message is the operator's work list.
    3. the entry's ``dataset_revision`` disagrees with the revision being ingested -> refuse
       naming both. Terms are read against a revision; a different revision is a different
       artifact with the same permission stapled to it.

    ``ingested_at`` must be timezone-aware. A naive timestamp on a record that exists to be
    correlated with a CI run and an artifact digest is a timestamp in an unknown frame, and
    guessing UTC is a fabrication of the cheapest kind.

    ``previously_ingested`` is supplied by the caller rather than discovered here. This
    module has no record store and does not invent one: whichever job owns the store knows
    what it has, and a store this function could not find would otherwise make every
    ingestion look like the first.
    """
    if ingested_at.tzinfo is None or ingested_at.tzinfo.utcoffset(ingested_at) is None:
        raise IngestionRefusedError(
            "ingested_at is timezone-naive; an ingestion timestamp in an unknown frame "
            "cannot be correlated with the CI run that produced it"
        )
    try:
        document = load_licence_document(licence_path)
        licence_digest = artifact_digest(licence_path)
    except LicenceArtifactError as error:
        raise IngestionRefusedError(
            f"the licence artifact could not be read, so no ingestion of {dataset_id!r} "
            f"can be recorded under known terms: {error}"
        ) from error

    entry = document.entry(dataset_id)
    if entry is None:
        # `dataset_id` is nullable in the register (a null asserts "identity not yet
        # established"), so this join must tolerate one rather than raising inside an error
        # path - a refusal that crashes while explaining itself explains nothing.
        declared = (
            ", ".join(
                item.dataset_id if item.dataset_id is not None else "(unnamed entry)"
                for item in document.datasets
            )
            or "(none)"
        )
        raise IngestionRefusedError(
            f"{licence_path.as_posix()} declares no licence entry for {dataset_id!r} "
            f"(declared: {declared}); R8.16 requires the licence check to report on the "
            "change that performs the first ingestion, so an undeclared dataset cannot be "
            "ingested"
        )
    if not entry.confirmed:
        unconfirmed = entry.unconfirmed_fields()
        named = ", ".join(unconfirmed) if unconfirmed else "(none)"
        raise IngestionRefusedError(
            f"the licence entry for {dataset_id!r} is not confirmed: "
            f"{len(unconfirmed)} R8.1 field(s) are still unestablished ({named}). A null "
            "field is an assertion of ignorance, not a permission. Confirming the terms is "
            f"an operator step; see the entry's `confirmation.procedure` block in "
            f"{licence_path.as_posix()}"
        )
    if entry.dataset_revision != dataset_revision:
        raise IngestionRefusedError(
            f"the licence entry for {dataset_id!r} was read against revision "
            f"{entry.dataset_revision!r} but revision {dataset_revision!r} is being "
            "ingested; update the artifact and re-read the terms rather than ingesting a "
            "revision no recorded permission covers"
        )

    digests = tuple(digest_file(path) for path in files)
    # `entry.confirmed` is exactly "every R8.1 field is non-null" (data_fabric.licence
    # derives it from `absent_fields`), and the guard above refused when it was false. These
    # two reads are therefore non-null by that invariant. They are narrowed explicitly
    # rather than with `assert` or a `# type: ignore`, so the dependency on `confirmed` is
    # visible at the point that relies on it: if the definition of `confirmed` is ever
    # widened to admit a null field, this refusal fires instead of a None reaching the
    # record and being serialised as `null` into an ingestion provenance row.
    licence_id = entry.licence_id
    licence_read_date = entry.read_date
    if licence_id is None or licence_read_date is None:  # pragma: no cover - invariant guard
        raise IngestionRefusedError(
            f"the licence entry for {dataset_id!r} reports confirmed while licence_id or "
            "read_date is null; `DatasetLicence.confirmed` and the R8.1 field set have "
            "diverged, and an ingestion must not record a licence term it does not have"
        )
    record = M5IngestRecord(
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
        rows=sum(item.data_rows for item in digests),
        files=digests,
        licence_artifact=licence_path.as_posix(),
        licence_artifact_digest=licence_digest,
        licence_id=licence_id,
        licence_read_date=licence_read_date,
        first_ingestion=dataset_id not in tuple(previously_ingested),
        ingested_at=ingested_at.isoformat(),
    )
    _LOG.info(
        "m5.ingestion_recorded",
        dataset_id=record.dataset_id,
        dataset_revision=record.dataset_revision,
        rows=record.rows,
        files=len(record.files),
        first_ingestion=record.first_ingestion,
        licence_artifact_digest=record.licence_artifact_digest,
    )
    return record


# ---------------------------------------------------------------------------
# CSV reading helpers
# ---------------------------------------------------------------------------


def _read_csv(path: Path) -> Iterator[list[str]]:
    """Stream one CSV row at a time. ``encoding='utf-8'`` (E-S13-07), ``newline=''``."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from csv.reader(handle)


def _to_float(cell: str) -> float | None:
    """Parse one observation cell, or ``None``.

    ``None`` rather than ``0.0``. A cell that cannot be read is not a zero observation, and
    treating it as one would flatten the exact shape being measured while reporting success.
    """
    try:
        return float(cell)
    except ValueError:
        return None


def _unavailable(name: str, basis: str, detail: str, rows: int = 0) -> ShapeEstimate:
    """One constructor for every path that stops before a shape exists."""
    return ShapeEstimate(
        name=name,
        status="unavailable",
        basis=basis,
        labels=(),
        values=(),
        rows_consumed=rows,
        detail=detail,
    )


def _calendar_index(
    calendar_csv: Path, columns: M5Columns
) -> tuple[_CalendarIndex | None, str]:
    """Build the day -> (week, wday) index, or say which column stopped it."""
    if not calendar_csv.is_file():
        return None, f"{calendar_csv.as_posix()} is not a file"
    rows = _read_csv(calendar_csv)
    try:
        header = next(rows)
    except StopIteration:
        return None, f"{calendar_csv.as_posix()} is empty, so it carries no header"
    wanted = (columns.calendar_day, columns.calendar_week, columns.calendar_wday)
    missing = [name for name in wanted if name not in header]
    if missing:
        return None, (
            f"{calendar_csv.as_posix()} header carries no column(s) "
            f"{', '.join(repr(name) for name in missing)}; present: "
            f"{', '.join(header[:12])}"
        )
    day_at = header.index(columns.calendar_day)
    week_at = header.index(columns.calendar_week)
    wday_at = header.index(columns.calendar_wday)
    label_at = (
        header.index(columns.calendar_weekday_name)
        if columns.calendar_weekday_name in header
        else None
    )
    wday_by_day: dict[str, int] = {}
    week_by_day: dict[str, str] = {}
    label_by_wday: dict[int, str] = {}
    count = 0
    for number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            return None, (
                f"{calendar_csv.as_posix()} line {number} has {len(row)} field(s) for a "
                f"{len(header)}-column header"
            )
        raw_wday = _to_float(row[wday_at])
        if raw_wday is None:
            return None, (
                f"{calendar_csv.as_posix()} line {number} column "
                f"{columns.calendar_wday!r} is {row[wday_at]!r}, not a number"
            )
        wday = int(raw_wday)
        wday_by_day[row[day_at]] = wday
        week_by_day[row[day_at]] = row[week_at]
        if label_at is not None and wday not in label_by_wday:
            label_by_wday[wday] = row[label_at]
        count += 1
    if not wday_by_day:
        return None, f"{calendar_csv.as_posix()} carries a header but no data rows"
    return (
        _CalendarIndex(
            wday_by_day=wday_by_day,
            week_by_day=week_by_day,
            label_by_wday=label_by_wday,
            rows=count,
        ),
        f"{count} calendar row(s) indexed from {calendar_csv.as_posix()}",
    )


def _day_columns(header: Sequence[str], columns: M5Columns) -> list[int]:
    """Positions of the daily observation columns, in header order."""
    return [
        index
        for index, name in enumerate(header)
        if name.startswith(columns.day_prefix)
    ]


# ---------------------------------------------------------------------------
# The three shapes
# ---------------------------------------------------------------------------


def intra_day_intensity_shape(
    sales_csv: Path, columns: M5Columns = DEFAULT_COLUMNS
) -> ShapeEstimate:
    """Always ``unavailable`` -- and the reason is read from the file, not asserted.

    This is the honest half of R5.11. The sales file's observation columns are **daily**
    totals, so no sub-daily aggregation exists in the source and an hour-of-day shape cannot
    be recovered from it. Rather than stating that from memory, this function reads the
    header and reports what it found: how many observation columns match the daily prefix,
    and that none carries a finer grain.

    A plausible intra-day curve invented here would satisfy R5.11's letter (a "statistic
    derived from the feed") while inverting its intent, and every consumer downstream would
    treat it as calibration. So: ``unavailable``, with the granularity gap named. It is also
    the sharpest available evidence for R8.12's documented domain gap between daily retail
    demand and 10-minute quick-commerce demand.
    """
    name = "intra_day_intensity"
    basis = (
        "not derivable from this dataset: the source carries one observation per series "
        "per day, and an hour-of-day shape is not recoverable from daily aggregates"
    )
    if not sales_csv.is_file():
        return _unavailable(name, basis, f"{sales_csv.as_posix()} is not a file")
    rows = _read_csv(sales_csv)
    try:
        header = next(rows)
    except StopIteration:
        return _unavailable(
            name, basis, f"{sales_csv.as_posix()} is empty, so it carries no header"
        )
    daily = _day_columns(header, columns)
    if not daily:
        return _unavailable(
            name,
            basis,
            f"{sales_csv.as_posix()} header carries no column starting with "
            f"{columns.day_prefix!r}, so the observation grain could not even be "
            "confirmed as daily",
        )
    return _unavailable(
        name,
        basis,
        f"{len(daily)} observation column(s) in {sales_csv.as_posix()} match the daily "
        f"prefix {columns.day_prefix!r} and none carries a sub-daily grain; the intra-day "
        "shape must be calibrated from another source, and inventing one here would be "
        "the literal R5.11 forbids",
    )


def day_of_week_shape(
    sales_csv: Path,
    calendar_csv: Path,
    columns: M5Columns = DEFAULT_COLUMNS,
) -> ShapeEstimate:
    """Per-weekday demand multipliers, derived by joining sales columns to the calendar.

    Each value is that weekday's mean units per series-day divided by the pooled mean over
    all observed series-days, so the cell-count-weighted mean of the values is exactly 1.0
    by construction -- which is what makes them usable as multipliers on a base intensity
    without a second normalisation step at the consumer.

    Labels are read from the calendar's weekday-name column when it exists, so this module
    never asserts which index is Monday. When the column is absent the labels are
    ``wday=<n>``, which is honest about knowing the index and not the name.
    """
    name = "day_of_week"
    basis = (
        "mean units per series-day for each calendar `wday`, divided by the pooled mean "
        "over all observed series-days; the cell-count-weighted mean of the values is 1.0"
    )
    index, detail = _calendar_index(calendar_csv, columns)
    if index is None:
        return _unavailable(name, basis, detail)
    if not sales_csv.is_file():
        return _unavailable(name, basis, f"{sales_csv.as_posix()} is not a file")

    rows = _read_csv(sales_csv)
    try:
        header = next(rows)
    except StopIteration:
        return _unavailable(
            name, basis, f"{sales_csv.as_posix()} is empty, so it carries no header"
        )
    positions = _day_columns(header, columns)
    if not positions:
        return _unavailable(
            name,
            basis,
            f"{sales_csv.as_posix()} header carries no column starting with "
            f"{columns.day_prefix!r}",
        )
    unknown = [header[at] for at in positions if header[at] not in index.wday_by_day]
    if unknown:
        return _unavailable(
            name,
            basis,
            f"{len(unknown)} observation column(s) in {sales_csv.as_posix()} are absent "
            f"from {calendar_csv.as_posix()} (first: "
            f"{', '.join(repr(item) for item in unknown[:3])}), so they cannot be "
            "attributed to a weekday",
        )

    pairs = [(at, index.wday_by_day[header[at]]) for at in positions]
    totals: dict[int, float] = {}
    cells: Counter[int] = Counter()
    consumed = 0
    for number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            return _unavailable(
                name,
                basis,
                f"{sales_csv.as_posix()} line {number} has {len(row)} field(s) for a "
                f"{len(header)}-column header; a short row cannot be attributed",
                rows=consumed,
            )
        for at, wday in pairs:
            value = _to_float(row[at])
            if value is None:
                return _unavailable(
                    name,
                    basis,
                    f"{sales_csv.as_posix()} line {number} column {header[at]!r} is "
                    f"{row[at]!r}, not a number; an unreadable observation is not a zero "
                    "one",
                    rows=consumed,
                )
            totals[wday] = totals.get(wday, 0.0) + value
            cells[wday] += 1
        consumed += 1

    observed_cells = sum(cells.values())
    if consumed == 0 or observed_cells == 0:
        return _unavailable(
            name,
            basis,
            f"{sales_csv.as_posix()} carries a header but no observation cells",
            rows=consumed,
        )
    pooled = sum(totals.values()) / observed_cells
    if pooled <= 0.0:
        return _unavailable(
            name,
            basis,
            f"the pooled mean over {observed_cells} observation cell(s) is {pooled}, so "
            "no multiplier can be formed without dividing by zero or inverting the sign",
            rows=consumed,
        )
    wdays = sorted(cells)
    return ShapeEstimate(
        name=name,
        status="derived",
        basis=basis,
        labels=tuple(index.label_by_wday.get(wday, f"wday={wday}") for wday in wdays),
        values=tuple(totals[wday] / cells[wday] / pooled for wday in wdays),
        rows_consumed=consumed,
        detail=(
            f"{len(wdays)} weekday(s) over {consumed} series and {observed_cells} "
            f"observation cell(s); {detail}"
        ),
    )


def promotion_uplift_shape(
    sales_csv: Path,
    calendar_csv: Path,
    sell_prices_csv: Path | None,
    columns: M5Columns = DEFAULT_COLUMNS,
    discount_threshold: float = DEFAULT_DISCOUNT_THRESHOLD,
) -> ShapeEstimate:
    """Uplift as a **declared price proxy**, labelled as a proxy in its own ``basis``.

    The dataset carries no promotion flag, so "promotion" here is defined, not observed: a
    (item, store) week is *discounted* when its price is at least ``discount_threshold``
    below that pair's own maximum observed price. Weeks are then split at the median
    discount incidence and the estimate is the ratio of mean weekly units above the median
    to mean weekly units below it.

    Three properties of that construction are stated rather than left for a reader to
    reverse-engineer, because each bounds what the number may be used for:

    * It is a **correlation over a proxy**, not a measured promotional response. Nothing
      here identifies a causal effect, and the ``basis`` says so wherever the value travels.
    * It is **weekly and aggregate**. Prices vary by week in this dataset, so a
      finer-grained split would be reading structure the source does not carry.
    * Only weeks whose full complement of observation columns is present are used, so a
      truncated first or last week cannot depress one arm of the ratio.

    An alternative proxy was available -- the calendar's benefit-programme and event flags --
    and was not taken: those mark a household-income event and a holiday respectively, and
    neither is a price promotion. Recording the choice matters more than the choice.
    """
    name = "promotion_uplift"
    basis = (
        "PROXY, not a measured promotion: a (item, store) week counts as discounted when "
        f"its price is at least {discount_threshold:.0%} below that pair's own maximum "
        "observed price; weeks are split at the median discount incidence and the value is "
        "mean weekly units above the median over mean weekly units below it. A correlation "
        "over a price proxy, aggregate and weekly, with no causal claim"
    )
    if sell_prices_csv is None:
        return _unavailable(
            name,
            basis,
            "no price file was supplied, and this dataset carries no promotion flag, so "
            "there is nothing from which a promotion proxy could be formed",
        )
    if not sell_prices_csv.is_file():
        return _unavailable(name, basis, f"{sell_prices_csv.as_posix()} is not a file")
    index, calendar_detail = _calendar_index(calendar_csv, columns)
    if index is None:
        return _unavailable(name, basis, calendar_detail)

    reference, price_detail = _reference_prices(sell_prices_csv, columns)
    if reference is None:
        return _unavailable(name, basis, price_detail)
    incidence, incidence_detail, price_rows = _discount_incidence(
        sell_prices_csv, columns, reference, discount_threshold
    )
    if incidence is None:
        return _unavailable(name, basis, incidence_detail, rows=price_rows)

    weekly, weekly_detail, sales_rows = _weekly_units(sales_csv, columns, index)
    if weekly is None:
        return _unavailable(name, basis, weekly_detail, rows=price_rows + sales_rows)

    consumed = price_rows + sales_rows
    common = sorted(set(weekly) & set(incidence))
    if len(common) < MIN_UPLIFT_WEEKS:
        return _unavailable(
            name,
            basis,
            f"{len(common)} week(s) carry both a discount incidence and a full complement "
            f"of observations, below the declared minimum of {MIN_UPLIFT_WEEKS}; a split "
            "over fewer has no spread to describe",
            rows=consumed,
        )
    midpoint = stats.median(incidence[week] for week in common)
    high = [weekly[week] for week in common if incidence[week] > midpoint]
    low = [weekly[week] for week in common if incidence[week] <= midpoint]
    if not high or not low:
        return _unavailable(
            name,
            basis,
            f"the median discount incidence ({midpoint:.4f}) does not separate the "
            f"{len(common)} usable week(s) into two non-empty arms -- every week carries "
            "the same incidence, so the proxy has no contrast to measure",
            rows=consumed,
        )
    mean_low = stats.fmean(low)
    if mean_low <= 0.0:
        return _unavailable(
            name,
            basis,
            f"mean weekly units in the low-incidence arm is {mean_low}, so the ratio is "
            "undefined or sign-inverted",
            rows=consumed,
        )
    return ShapeEstimate(
        name=name,
        status="derived",
        basis=basis,
        labels=("units ratio: high-discount-incidence weeks / low-incidence weeks",),
        values=(stats.fmean(high) / mean_low,),
        rows_consumed=consumed,
        detail=(
            f"{len(high)} high-incidence and {len(low)} low-incidence week(s) split at "
            f"median incidence {midpoint:.4f}; {price_detail}; {incidence_detail}; "
            f"{weekly_detail}"
        ),
    )


def _reference_prices(
    sell_prices_csv: Path, columns: M5Columns
) -> tuple[dict[tuple[str, str], float] | None, str]:
    """Maximum observed price per (item, store). One streaming pass, bounded by pair count.

    The maximum is the reference rather than the mean or the mode: a discount is a departure
    from a list price, and among the statistics available in a price series without a list
    price column, the maximum is the one that cannot be pulled down by the discounts it is
    supposed to measure.
    """
    rows = _read_csv(sell_prices_csv)
    try:
        header = next(rows)
    except StopIteration:
        return None, f"{sell_prices_csv.as_posix()} is empty, so it carries no header"
    wanted = (columns.price_item, columns.price_store, columns.price_value)
    missing = [column for column in wanted if column not in header]
    if missing:
        return None, (
            f"{sell_prices_csv.as_posix()} header carries no column(s) "
            f"{', '.join(repr(item) for item in missing)}"
        )
    item_at = header.index(columns.price_item)
    store_at = header.index(columns.price_store)
    value_at = header.index(columns.price_value)
    reference: dict[tuple[str, str], float] = {}
    count = 0
    for number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            return None, (
                f"{sell_prices_csv.as_posix()} line {number} has {len(row)} field(s) for "
                f"a {len(header)}-column header"
            )
        price = _to_float(row[value_at])
        if price is None:
            return None, (
                f"{sell_prices_csv.as_posix()} line {number} column "
                f"{columns.price_value!r} is {row[value_at]!r}, not a number"
            )
        key = (row[item_at], row[store_at])
        current = reference.get(key)
        if current is None or price > current:
            reference[key] = price
        count += 1
    if not reference:
        return None, f"{sell_prices_csv.as_posix()} carries a header but no data rows"
    return reference, f"{len(reference)} (item, store) pair(s) over {count} price row(s)"


def _discount_incidence(
    sell_prices_csv: Path,
    columns: M5Columns,
    reference: dict[tuple[str, str], float],
    discount_threshold: float,
) -> tuple[dict[str, float] | None, str, int]:
    """Fraction of (item, store) pairs discounted, per week. Second streaming pass."""
    rows = _read_csv(sell_prices_csv)
    try:
        header = next(rows)
    except StopIteration:
        return None, f"{sell_prices_csv.as_posix()} is empty on the second pass", 0
    if columns.price_week not in header:
        return (
            None,
            f"{sell_prices_csv.as_posix()} header carries no column "
            f"{columns.price_week!r}",
            0,
        )
    item_at = header.index(columns.price_item)
    store_at = header.index(columns.price_store)
    value_at = header.index(columns.price_value)
    week_at = header.index(columns.price_week)
    discounted: Counter[str] = Counter()
    observed: Counter[str] = Counter()
    count = 0
    for number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            return (
                None,
                f"{sell_prices_csv.as_posix()} line {number} has {len(row)} field(s) for "
                f"a {len(header)}-column header",
                count,
            )
        price = _to_float(row[value_at])
        if price is None:
            return (
                None,
                f"{sell_prices_csv.as_posix()} line {number} column "
                f"{columns.price_value!r} is {row[value_at]!r}, not a number",
                count,
            )
        week = row[week_at]
        peak = reference[(row[item_at], row[store_at])]
        observed[week] += 1
        if peak > 0.0 and price <= peak * (1.0 - discount_threshold):
            discounted[week] += 1
        count += 1
    if not observed:
        return None, f"{sell_prices_csv.as_posix()} carries no price rows", count
    incidence = {week: discounted[week] / total for week, total in observed.items()}
    return (
        incidence,
        f"{len(incidence)} week(s) of discount incidence at a "
        f"{discount_threshold:.0%} threshold",
        count,
    )


def _weekly_units(
    sales_csv: Path, columns: M5Columns, index: _CalendarIndex
) -> tuple[dict[str, float] | None, str, int]:
    """Total units per calendar week, restricted to weeks with a full observation set.

    "Full" is measured against the modal number of observation columns per week rather than
    against a hardcoded seven, so a source whose weeks are a different length is handled by
    reading it instead of by assuming it. A partial week is dropped, not scaled up: scaling
    would invent the missing days.
    """
    rows = _read_csv(sales_csv)
    try:
        header = next(rows)
    except StopIteration:
        return None, f"{sales_csv.as_posix()} is empty, so it carries no header", 0
    positions = _day_columns(header, columns)
    if not positions:
        return (
            None,
            f"{sales_csv.as_posix()} header carries no column starting with "
            f"{columns.day_prefix!r}",
            0,
        )
    unknown = [header[at] for at in positions if header[at] not in index.week_by_day]
    if unknown:
        return (
            None,
            f"{len(unknown)} observation column(s) are absent from the calendar (first: "
            f"{', '.join(repr(item) for item in unknown[:3])}), so they cannot be "
            "attributed to a week",
            0,
        )
    pairs = [(at, index.week_by_day[header[at]]) for at in positions]
    days_per_week = Counter(week for _, week in pairs)
    full = max(days_per_week.values())
    complete = {week for week, days in days_per_week.items() if days == full}
    totals: dict[str, float] = {}
    consumed = 0
    for number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            return (
                None,
                f"{sales_csv.as_posix()} line {number} has {len(row)} field(s) for a "
                f"{len(header)}-column header",
                consumed,
            )
        for at, week in pairs:
            if week not in complete:
                continue
            value = _to_float(row[at])
            if value is None:
                return (
                    None,
                    f"{sales_csv.as_posix()} line {number} column {header[at]!r} is "
                    f"{row[at]!r}, not a number",
                    consumed,
                )
            totals[week] = totals.get(week, 0.0) + value
        consumed += 1
    if not totals:
        return (
            None,
            f"no week in {sales_csv.as_posix()} carries a full complement of {full} "
            "observation column(s)",
            consumed,
        )
    dropped = len(days_per_week) - len(complete)
    return (
        totals,
        f"{len(totals)} complete week(s) of {full} day(s) over {consumed} series "
        f"({dropped} partial week(s) dropped rather than scaled up)",
        consumed,
    )


def extract_statistics(
    *,
    dataset_id: str,
    dataset_revision: str,
    sales_csv: Path,
    calendar_csv: Path,
    sell_prices_csv: Path | None = None,
    columns: M5Columns = DEFAULT_COLUMNS,
    discount_threshold: float = DEFAULT_DISCOUNT_THRESHOLD,
) -> M5AggregateStatistics:
    """The three shapes, bound to the dataset revision they were derived from (R5.11).

    **Not to be run locally.** This is a bulk streaming read over roughly 42,000
    hierarchical daily series, a category-3/4 workload under I-0 whose locus is
    ``ci.yml::training-smoke``. Every input is a parameter and nothing runs at import, so
    correctness is established on small fixtures and scale is established in CI.

    The identity fields are carried on the result rather than left to the caller to staple
    on. A shape with no revision beside it is a shape that will be reused after the dataset
    moves, which is how a calibration becomes a literal again.
    """
    intra_day = intra_day_intensity_shape(sales_csv, columns)
    weekday = day_of_week_shape(sales_csv, calendar_csv, columns)
    uplift = promotion_uplift_shape(
        sales_csv, calendar_csv, sell_prices_csv, columns, discount_threshold
    )
    result = M5AggregateStatistics(
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
        rows=max(weekday.rows_consumed, intra_day.rows_consumed),
        intra_day_intensity=intra_day,
        day_of_week=weekday,
        promotion_uplift=uplift,
        notes=(
            "R5.11: a shape reported `unavailable` here must not be replaced with a "
            "literal downstream. An unavailable ShapeEstimate structurally carries no "
            "values, so there is nothing to pick up by accident.",
            "R8.12/R8.13: this dataset is daily retail demand and the twin models "
            "10-minute quick-commerce demand. They are distinct domains, and the "
            "unavailable intra-day shape is the sharpest single piece of evidence for how "
            "distinct.",
            "The promotion shape is a declared price proxy, not a measured promotional "
            "response; its `basis` states that wherever the value travels.",
        ),
    )
    _LOG.info(
        "m5.statistics_extracted",
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
        rows=result.rows,
        unavailable=result.unavailable_shapes,
    )
    return result
