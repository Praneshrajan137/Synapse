"""The benchmark document's region is generated from the record, not transcribed (R8.8, R8.12,
R8.13).

Feature: decision-quality-proof, task 19.5. Renders the one generated region of
``docs/benchmarks/m5-uncertainty.md`` from ``benchmark_truth``'s committed record.

Why a generator rather than a hand-written page
----------------------------------------------

Three of this requirement's clauses are obligations on **every** document reporting a
feed-derived score, and a hand-written page satisfies them exactly once -- on the day it is
written. R8.8 forbids an unconfirmed published value being asserted as fact; R8.12 requires the
domain gap to accompany every feed-derived claim; R8.13 requires the two domains to be described
as distinct in every such document. Transcribing a record into prose puts the second copy one
edit away from disagreeing with the first, and this repository's own lesson is that "consensus
across documents is not evidence -- it is usually one unchecked claim copied forward". So the
region is a projection, and ``--check`` is what makes the projection binding.

**An unconfirmed baseline cannot be rendered as a number, and that is structural.** The renderer
reads :attr:`~scripts.audit.benchmark_truth.UnconfirmedBaseline.renderable_value`, which is typed
``None``. There is no branch here that could print a number for an unconfirmed entry, because
there is no number to reach: R8.8 holds by construction rather than by this module remembering.

One mechanism, not a second
---------------------------

The marker literals come from ``gate_surface`` (which owns them, AD-2) and the region arithmetic
from ``ledger_gen.generated_region_bounds`` (task 4.2). Neither is restated here. A second copy
of either would be a second thing to drift, and ``generated_region_bounds``' own docstring
records what that cost last time: a marker quoted inside prose was counted as a region
delimiter, ``--check`` reported "nothing could be checked" instead of a real drift verdict, and
under I-7 that is the worst of the three outcomes to be wrong about.

The three rules on writing
--------------------------

* ``--check`` is the **default**. Running the module with no flag compares and exits ``1`` on a
  diff, so a stale document is a failure rather than a silent inconsistency.
* ``--write`` **never creates the document.** An absent page is ``unavailable``, not an
  invitation: this generator owns the delimited region and nothing else, and a page it invented
  would carry a header nobody reviewed. Same rule as ``readme_gen``.
* **Every byte outside the region survives.** Head and tail are carried through verbatim,
  including prose that quotes the markers.

Run::

    python -m scripts.audit.benchmark_gen            # == --check; diffs and exits 1
    python -m scripts.audit.benchmark_gen --check    # exit-code oriented
    python -m scripts.audit.benchmark_gen --write    # rewrite the region only

Exit codes: ``0`` in agreement, ``1`` drift, ``2`` unavailable. Every read uses
``encoding='utf-8'`` (E-S13-07) and all console output is ASCII.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:  # importable when run as a bare script
    sys.path.insert(0, str(ROOT))

from scripts.audit import benchmark_truth  # noqa: E402 - after the sys.path guard

# The marker convention has exactly one definition in this repository; the gate-surface
# generator (E1.6) owns the literals and ledger_gen (E1.4) owns the region arithmetic. Both
# are imported, not restated - a second copy of either is a second thing to drift (AD-2).
from scripts.audit.gate_surface import GENERATED_BEGIN, GENERATED_END  # noqa: E402
from scripts.audit.ledger_gen import (  # noqa: E402
    LedgerMarkersError,
    generated_region_bounds,
)

#: The document this generator owns the region of.
DOCUMENT: Final[Path] = ROOT / "docs" / "benchmarks" / "m5-uncertainty.md"

ProbeStatus = Literal["ok", "fail", "unavailable"]

_EXIT_CODES: Final[dict[str, int]] = {"ok": 0, "fail": 1, "unavailable": 2}
_SYMBOLS: Final[dict[str, str]] = {"ok": "[OK]", "fail": "[XX]", "unavailable": "[??]"}

#: Rendered in place of a baseline number while the published value is unconfirmed. A word,
#: not a placeholder digit: a reader scanning for a number must find prose, and a formatter
#: that later coerced this to a float would fail loudly rather than print ``0``.
UNCONFIRMED_RENDERING: Final[str] = "not confirmed - no value recorded"

#: Rendered in place of a score while no scoring run has executed.
UNSCORED_RENDERING: Final[str] = "not measured - no scoring run has executed"

__all__ = [
    "DOCUMENT",
    "GENERATED_BEGIN",
    "GENERATED_END",
    "UNCONFIRMED_RENDERING",
    "UNSCORED_RENDERING",
    "BenchmarkDocProbe",
    "compose",
    "diff_document",
    "evaluate",
    "main",
    "probe_text",
    "render_region",
    "run",
]


class BenchmarkDocProbe(BaseModel):
    """Whether the committed document matches the record it reports."""

    model_config = ConfigDict(frozen=True)

    status: ProbeStatus
    detail: str
    diff: str = ""

    @property
    def exit_code(self) -> int:
        return _EXIT_CODES[self.status]

    @property
    def passing(self) -> bool:
        """True only for ``ok``. ``unavailable`` is not a pass (I-7)."""
        return self.status == "ok"


def _bullets(items: tuple[str, ...], *, empty: str) -> list[str]:
    """One bullet per item, or a single line stating the emptiness.

    ``empty`` is required rather than defaulted: a rendered empty list would leave a heading
    with nothing under it, and a reader cannot tell an empty list from a rendering bug.
    """
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items]


def render_region(record: benchmark_truth.BenchmarkRecord, label: str) -> str:
    """The generated region for one :class:`BenchmarkRecord`.

    Pure: a total function of its two arguments. No file IO, no git, no clock -- so the
    property test that drives every branch costs nothing under I-0, and two runs over the same
    record are byte-identical, which is what ``--check`` relies on.

    ``label`` says what the record *is* -- a scored run, or the comparison as set up -- so a
    reader cannot mistake a configured comparison for a measured result. That distinction is
    R8.7's limitation clause applied to the document rather than to the record.
    """
    metric = record.metric
    baseline = record.baseline
    gap = record.domain_gap
    score = (
        f"`{record.score}`"
        if record.score is not None
        else f"{UNSCORED_RENDERING} ({record.score_absent_reason})"
    )
    baseline_value = (
        f"`{baseline.renderable_value}`"
        if baseline.renderable_value is not None
        else UNCONFIRMED_RENDERING
    )
    intervals = ", ".join(str(level) for level in metric.quantile_levels) or "none declared"
    rank = (
        str(record.comparability.rank)
        if record.comparability.rank is not None
        else "none - see comparability"
    )
    read = "yes" if metric.defining_document_confirmed else "NO"
    defined_by = f"`{metric.defining_document_id}` ({metric.defining_document_uri})"

    lines: list[str] = [
        "## What is recorded",
        "",
        f"Subject: **{label}**.",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Score | {score} |",
        f"| Direction | {record.direction} |",
        f"| Metric scored | `{metric.metric_id}` -- {metric.metric_name} |",
        f"| Metric defined by | {defined_by} |",
        f"| Defining document read | {read} |",
        f"| Split | {metric.split_id} |",
        f"| Aggregation level | {metric.aggregation_level} |",
        f"| Interval family scored | {intervals} |",
        f"| Published baseline | {baseline_value} |",
        f"| Leaderboard comparability | **{record.comparability.status}** |",
        f"| Rank | {rank} |",
        "",
        "How the metric identity was obtained: " + metric.provenance,
        "",
        "## The published baseline, and why no number appears above",
        "",
    ]

    if isinstance(baseline, benchmark_truth.UnconfirmedBaseline):
        lines.extend(
            [
                "The published baseline is **explicitly unconfirmed**. R8.7 requires that "
                "limitation to be stated and R8.8 forbids the value being asserted as fact, so "
                "no number is rendered here -- there is none in the record to render.",
                "",
                f"- **Blocked on:** {baseline.blocked_on}",
                f"- **Limitation:** {baseline.limitation}",
                f"- **To confirm it:** {baseline.procedure}",
            ]
        )
    else:
        lines.extend(
            [
                "The published baseline is **confirmed**, with the provenance that makes it "
                "checkable:",
                "",
                f"- **Value:** `{baseline.value}`",
                f"- **Source:** {baseline.source_title} ({baseline.source_uri})",
                f"- **Read on:** {baseline.read_date} by {baseline.read_by}",
            ]
        )

    lines.extend(
        [
            "",
            "## Leaderboard comparability (R8.18)",
            "",
        ]
    )
    if record.comparability.comparable:
        lines.append(
            "The split, the aggregation level and the metric definition match the published "
            "competition's, so this result is comparable to the published field."
        )
    else:
        lines.extend(
            [
                "This result is **not leaderboard-comparable**, and that is the honest report "
                "rather than a worse position. R8.18: a differing split, aggregation level or "
                "metric definition makes a rank a category error dressed as a measurement. The "
                "differences, each named:",
                "",
                *_bullets(
                    record.comparability.differences,
                    empty="no difference is named, which the record model refuses",
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## The domain gap (R8.12, R8.13)",
            "",
            "The Real_Data_Feed's domain and this system's domain are **distinct domains**. "
            "Every claim on this page derived from the feed carries that gap.",
            "",
            f"- **Feed domain:** {gap.feed_domain}",
            f"- **This system's domain:** {gap.system_domain}",
            "",
            gap.statement,
            "",
            f"**Evidence for the gap, not an assertion of it:** {gap.evidence}",
        ]
    )
    return "\n".join(lines)


def compose(record: benchmark_truth.BenchmarkRecord, label: str, previous: str) -> str:
    """The full document text ``record`` implies, given the committed text.

    Only the delimited region changes; every byte before ``<!-- generated:begin -->`` and after
    ``<!-- generated:end -->`` is carried through unmodified -- including prose that quotes
    those markers, which :func:`generated_region_bounds` deliberately does not read as a region.
    Idempotent by construction, which is what ``--check`` relies on.

    Raises:
        LedgerMarkersError: the markers are absent, duplicated, or out of order.
    """
    begin, end = generated_region_bounds(previous)
    head = previous[:begin]
    tail = previous[end + len(GENERATED_END) :]
    region = render_region(record, label)
    return f"{head}{GENERATED_BEGIN}\n{region}\n{GENERATED_END}{tail}"


def diff_document(
    committed: str, generated: str, *, label: str = "docs/benchmarks/m5-uncertainty.md"
) -> str:
    """A unified diff of the committed document against the generated one."""
    return "".join(
        difflib.unified_diff(
            committed.splitlines(keepends=True),
            generated.splitlines(keepends=True),
            fromfile=f"{label} (committed)",
            tofile=f"{label} (regenerated)",
            n=2,
        )
    )


def probe_text(
    record: benchmark_truth.BenchmarkRecord | None,
    label: str,
    committed: str | None,
    *,
    document_label: str = "docs/benchmarks/m5-uncertainty.md",
) -> BenchmarkDocProbe:
    """Compare one record against committed text. Pure: no file IO, no subprocess.

    ``record is None`` is ``unavailable`` rather than "render an empty page": a document that
    described no record would still be a document a reader could cite.
    """
    if record is None:
        return BenchmarkDocProbe(
            status="unavailable",
            detail=(
                f"no benchmark record is available to render ({label}), so the region has no "
                f"subject; {document_label} is left byte-identical"
            ),
        )
    if committed is None:
        return BenchmarkDocProbe(
            status="unavailable",
            detail=(
                f"{document_label} is missing or unreadable; this generator owns only the "
                "delimited region and will not create the document"
            ),
        )
    try:
        generated = compose(record, label, committed)
    except LedgerMarkersError as exc:
        return BenchmarkDocProbe(
            status="unavailable",
            detail=(
                f"{document_label} has no usable generated region ({exc}); add "
                f"{GENERATED_BEGIN} / {GENERATED_END} on their own lines, then run --write. "
                "The document is left byte-identical"
            ),
        )
    if committed == generated:
        return BenchmarkDocProbe(
            status="ok",
            detail=(
                f"{document_label}'s generated region matches the committed benchmark record "
                f"({label})"
            ),
        )
    return BenchmarkDocProbe(
        status="fail",
        detail=(
            f"{document_label}'s generated region differs from the benchmark record it claims "
            "to report; regenerate it in the same change "
            "(python -m scripts.audit.benchmark_gen --write)"
        ),
        diff=diff_document(committed, generated, label=document_label),
    )


def _read(path: Path) -> str | None:
    """Read one file as UTF-8 (E-S13-07), or ``None`` when it cannot be read."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _subject() -> tuple[benchmark_truth.BenchmarkRecord | None, str]:
    """The record to render and its label, or ``(None, reason)``.

    Reads through ``benchmark_truth.load_run_record`` rather than parsing the artifact again:
    one reader, so the generator and the gate cannot disagree about what the record says.
    """
    loaded = benchmark_truth.load_run_record()
    if isinstance(loaded, benchmark_truth.BenchmarkTruthReport):
        return None, f"the run record could not be read: {loaded.reason}"
    return loaded.renderable_record()


def evaluate(*, path: Path = DOCUMENT) -> BenchmarkDocProbe:
    """Read the record and the document, and compare. Used by the registry row."""
    record, label = _subject()
    return probe_text(record, label, _read(path), document_label=_relative(path))


# ---------------------------------------------------------------------------
# CLI. `print` is acceptable here and nowhere else in this module.
# ---------------------------------------------------------------------------


def _echo(text: str = "", *, end: str = "\n") -> None:
    """ASCII-only output, honouring the Windows-console contract even for a diff.

    The document may legitimately hold non-ASCII, so the transliteration belongs on the way
    out rather than on the way in -- the same split ``ledger_gen`` makes for registry titles.
    """
    print(text.encode("ascii", "backslashreplace").decode("ascii"), end=end)


def run(*, write: bool = False, check: bool = False, path: Path = DOCUMENT) -> int:
    """CLI entry point. ``0`` in agreement, ``1`` drift, ``2`` unavailable."""
    label_path = _relative(path)
    record, label = _subject()
    committed = _read(path)
    probe = probe_text(record, label, committed, document_label=label_path)

    if not write:
        if probe.diff:
            _echo(probe.diff, end="")
        _echo(f"{_SYMBOLS[probe.status]} benchmark-gen: {probe.status.upper()} - {probe.detail}")
        if not check and probe.status != "ok":
            _echo()
            _echo(
                "  Regenerate with: python -m scripts.audit.benchmark_gen --write "
                "(the region only; every byte outside the markers survives)"
            )
        return probe.exit_code

    # --write. Three refusals before any byte is written, and each leaves the file untouched.
    if record is None or committed is None or probe.status == "unavailable":
        _echo(f"[??] benchmark-gen: UNAVAILABLE - {probe.detail}")
        _echo("  Nothing was written. This generator never creates the document.")
        return _EXIT_CODES["unavailable"]
    if probe.status == "ok":
        _echo(f"[OK] benchmark-gen: {label_path} is already current; nothing written")
        return _EXIT_CODES["ok"]

    generated = compose(record, label, committed)
    try:
        path.write_text(generated, encoding="utf-8", newline="\n")
    except OSError as error:
        _echo(f"[??] benchmark-gen: UNAVAILABLE - {label_path} could not be written: {error}")
        return _EXIT_CODES["unavailable"]
    _echo(f"[OK] benchmark-gen: rewrote the generated region of {label_path}")
    return _EXIT_CODES["ok"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark_gen",
        description=(
            "Render the generated region of docs/benchmarks/m5-uncertainty.md from the "
            "committed benchmark record. --check is the default; --write rewrites the region "
            "only and never creates the document."
        ),
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write and args.check:
        parser.error("--write and --check are mutually exclusive")
    return run(write=bool(args.write), check=bool(args.check))


if __name__ == "__main__":
    sys.exit(main())
