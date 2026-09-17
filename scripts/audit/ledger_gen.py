"""Generate the Truth_Ledger's check matrix and summary counts (design E1.4 / AD-2).

Feature: purpose-achievement-audit, task 2.8. Requirements R10.1, R10.2, R10.3,
R10.4, R10.6, R10.7, R10.8, R10.9.

``docs/state/CURRENT.md`` declares itself "the single source of truth for what is
actually wired together in this repository". It was hand-maintained, and the audit
measured the consequence: the summary claimed 48 checks against a registry of 53;
rows C1-C6, C8-C13 and C16-C21 still read FAIL with a "(Resolved by WS-n)" note
while the corresponding checks assert the resolved state; three substance rows were
off by three from the registry (doc ``C42`` is code ``C45``, doc ``C43`` is code
``C46``, and code ``C43`` is a different check entirely); six rows named no check and
five checks had no row. Both over- and under-statement in the same table, which is
the signature of manual maintenance rather than of bias.

This module removes the class of defect rather than the instances. Every row and
every count is projected from **one** :class:`~scripts.audit.registry_gate.RegistryVerdict`
- one in-process Check_Registry execution - so the requirements hold *structurally*:

* **R10.1** the summary counts are that execution's counts; there is no second
  arithmetic to disagree with.
* **R10.2 / R10.3** the row set is exactly ``verdict.registered_ids``, so a
  registered check cannot lack a row and a row cannot cite an unregistered id.
* **R10.4** each row's status is the status that execution reported for that id.
* **R10.6** a newly registered check appears as a row on the next regeneration, and
  until it does, ``--check`` fails with the diff.
* **R10.8** each row's subject is the title the check is ``@register``-ed under,
  verbatim.
* **R10.9** the ``README.md`` headline counts are rendered from the same verdict, so
  the two documents cannot state different numbers for one execution.

The design is explicit that these must stay structural: **do not** reintroduce a
second recomputation (a re-read of the registry, a second execution, a parse of the
committed table) to "verify" any of them. There is nothing to cross-check against
when both sides are projections of the same execution, and a second source is
exactly how the drift got in.

Two consequences worth stating plainly, both honest rather than convenient (I-7):

* **A PASS row carries no detail.** ``RegistryVerdict`` holds ``CheckResult``s only
  for the checks that failed or were unproven, so the detail column reads ``-`` for
  a passing row. Re-running a check to fetch its prose would be a second execution,
  and a second execution is a second truth.
* **A registered check that emitted no result renders ``NOT EXECUTED``**, never a
  blank and never a pass. ``registry_gate`` already fails the build for it (R1.7);
  this document must not disagree.

Run::

    python -m scripts.audit.ledger_gen            # regenerate in memory, diff (default)
    python -m scripts.audit.ledger_gen --check    # explicit form of the default
    python -m scripts.audit.ledger_gen --write    # rewrite the generated region

Exit codes: ``0`` in sync, ``1`` drift (a unified diff is printed, R10.7), ``2``
unavailable - nothing is registered, the ledger is missing, or its generated markers
are absent. ``2`` is non-passing: absence of proof is never a pass.

Hand-authored prose outside the ``<!-- generated:begin -->`` /
``<!-- generated:end -->`` markers survives every rewrite, and the markers are the
only region this module will touch. It never creates the document: if the markers
are missing it reports unavailable rather than overwrite a hand-written ledger.

A marker delimits that region only when it **owns its line**
(:func:`generated_region_bounds`). Prose that quotes a marker mid-sentence - which
``docs/state/CURRENT.md`` does while explaining this very mechanism - is not a second
region. Counting the literals textually made documenting the format break the
generator, and it broke it in the least useful direction: a real drift verdict became
``unavailable``, which under I-7 is non-passing but says "nothing was checked" rather
than "the document disagrees with its registry".

Every read uses ``encoding='utf-8'`` (E-S13-07). The document keeps registry titles
verbatim (R10.8), which means it may contain the non-ASCII characters those titles
contain; everything this module *prints* is transliterated to ASCII first, so a
Windows console can render a diff of them.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:  # annotation-only names; PEP 563 defers every annotation here
    from collections.abc import Mapping

    from scripts.audit.registry_gate import RegistryVerdict

ROOT = Path(__file__).resolve().parents[2]

# Ensure the repo root is importable when run as a bare script (not -m).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit import registry_gate, verify_claims  # noqa: E402

# The marker convention has exactly one definition in this repository; the
# gate-surface generator (E1.6) owns it and this generator reuses it (AD-2).
from scripts.audit.gate_surface import GENERATED_BEGIN, GENERATED_END  # noqa: E402

#: The Truth_Ledger itself.
LEDGER_DOC: Final[Path] = ROOT / "docs" / "state" / "CURRENT.md"

#: Status rendered for a registered check that emitted no result (never a blank,
#: never a pass). ``registry_gate`` fails the build for the same condition (R1.7).
NOT_EXECUTED: Final[str] = "NOT EXECUTED"

#: Detail rendered for a passing row - see the module docstring on why the verdict
#: carries no prose for a check that passed.
NO_DETAIL: Final[str] = "-"

#: Summary categories, in the order the README headline states them (R10.9).
SUMMARY_CATEGORIES: Final[tuple[str, ...]] = ("PASS", "FAIL", "PARTIAL", "SKIP", "TOTAL")

LedgerStatus = Literal["ok", "fail", "unavailable"]

_EXIT_CODES: Final[Mapping[LedgerStatus, int]] = {"ok": 0, "fail": 1, "unavailable": 2}

#: Transliterations applied before printing, so the console stays ASCII on Windows
#: while the document keeps registry titles verbatim (R10.8).
_ASCII_MAP: Final[Mapping[str, str]] = {
    "\u2192": "->",
    "\u2190": "<-",
    "\u2194": "<->",
    "\u21d2": "=>",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u2260": "!=",
    "\u00d7": "x",
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u00a0": " ",
}

_USAGE: Final[str] = (
    "usage: python -m scripts.audit.ledger_gen [--check | --write]\n"
    "  (no flag) / --check : regenerate in memory and diff against the committed ledger\n"
    "  --write             : rewrite the generated region of docs/state/CURRENT.md\n"
)

__all__ = [
    "GENERATED_BEGIN",
    "GENERATED_END",
    "LEDGER_DOC",
    "NOT_EXECUTED",
    "NO_DETAIL",
    "SUMMARY_CATEGORIES",
    "LedgerMarkersError",
    "LedgerProbe",
    "diff_ledger",
    "evaluate",
    "generated_region_bounds",
    "main",
    "probe_text",
    "registered_titles",
    "render",
    "render_region",
    "row_details",
    "row_statuses",
    "run",
]


class LedgerMarkersError(RuntimeError):
    """The ledger carries no usable generated region.

    Raised rather than repaired: this generator owns the delimited region and
    nothing else, so a document without markers is a document it must not rewrite.
    """


class LedgerProbe(BaseModel):
    """Whether the committed ledger matches the ledger its registry projects."""

    model_config = ConfigDict(frozen=True)

    status: LedgerStatus
    detail: str
    diff: str = ""

    @property
    def exit_code(self) -> int:
        """The process exit status this probe mandates (0 / 1 / 2)."""
        return _EXIT_CODES[self.status]

    @property
    def passing(self) -> bool:
        """True only for ``ok``. ``unavailable`` is not a pass (I-7)."""
        return self.status == "ok"


def registered_titles() -> dict[str, str]:
    """The title each identifier is ``@register``-ed under, in registration order.

    Read straight from the registration list so the row subject is the registry's
    subject verbatim (R10.8). ``CheckResult.title`` is deliberately *not* used: a
    handful of checks return a shortened title (C2 registers "OutboxDispatcher
    started in orchestrator lifespan" and returns "OutboxDispatcher running"), and a
    row must describe the check as registered.
    """
    return {cid: title for cid, title, _fn in verify_claims._CHECKS}


def row_statuses(verdict: RegistryVerdict) -> dict[str, str]:
    """The status to render per registered id, derived from ``verdict`` alone.

    ``RegistryVerdict`` partitions one execution: ``missing_ids`` are registered
    checks that emitted nothing, ``failures`` holds every FAIL (plus any result
    carrying a status outside the emitted four), and ``unproven`` holds PARTIAL and
    SKIP. A registered id in none of the three executed and neither failed nor went
    unproven, so it passed. That is the whole derivation - no second execution, and
    no status is invented for an id the verdict does not describe.
    """
    reported = {result.cid: result.status for result in (*verdict.failures, *verdict.unproven)}
    missing = set(verdict.missing_ids)
    return {
        cid: (NOT_EXECUTED if cid in missing else reported.get(cid, "PASS"))
        for cid in verdict.registered_ids
    }


def row_details(verdict: RegistryVerdict) -> dict[str, str]:
    """The detail to render per registered id, for the ids the verdict details."""
    details = {result.cid: result.detail for result in (*verdict.failures, *verdict.unproven)}
    missing = set(verdict.missing_ids)
    unemitted = "no result was emitted for this registered check"
    return {
        cid: (unemitted if cid in missing else details.get(cid, NO_DETAIL))
        for cid in verdict.registered_ids
    }


def _cell(text: str) -> str:
    """One markdown table cell: single-line, pipe-escaped, never empty."""
    flattened = " ".join(text.split())
    escaped = flattened.replace("|", "\\|")
    return escaped or NO_DETAIL


def _ascii(text: str) -> str:
    """Transliterate for console output; the document keeps its text verbatim."""
    for source, replacement in _ASCII_MAP.items():
        text = text.replace(source, replacement)
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _echo(text: str = "", *, end: str = "\n") -> None:
    """ASCII-safe ``print``. This module's only output call, CLI-only."""
    print(_ascii(text), end=end)


_PREAMBLE: Final[tuple[str, ...]] = (
    "<!-- Generated by `python -m scripts.audit.ledger_gen --write` from ONE",
    "     `scripts.audit.registry_gate` execution (design E1.4 / AD-2; R10.1-R10.4,",
    "     R10.6-R10.9). Do not hand-edit: `--check` prints a unified diff and fails on",
    "     drift, and hand edits inside these markers are overwritten. Prose outside",
    "     them survives. -->",
    "",
    "Every row and every count below is projected from a single Check_Registry",
    "execution, which is what makes this table trustworthy rather than merely tidy: the",
    "row set **is** the registered identifier set (R10.2, R10.3), each status **is** the",
    "status that execution reported (R10.4), each subject **is** the title the check is",
    "registered under (R10.8), and the counts **are** that execution's counts (R10.1,",
    "R10.9). A check registered without a row, or a row for a check nobody registered,",
    "cannot be represented here (R10.6).",
    "",
    "A `-` in Detail means the check passed: the verdict carries prose only for checks",
    "that failed or were left unproven, and re-running a check to fetch a sentence would",
    "be a second execution and therefore a second truth. `NOT EXECUTED` means the check",
    "is registered but emitted no result - not a pass, and already a build failure",
    "(R1.7).",
)


def render_region(verdict: RegistryVerdict, *, titles: Mapping[str, str] | None = None) -> str:
    """The generated region's body: verdict line, one row per check, counts, headline.

    ``titles`` defaults to the live registration list and exists so a property test
    can drive the projection without executing the real registry (I-0).
    """
    title_map = registered_titles() if titles is None else dict(titles)
    statuses = row_statuses(verdict)
    details = row_details(verdict)
    counts = verdict.counts

    lines: list[str] = list(_PREAMBLE)
    lines.append("")
    lines.append(f"**Registry verdict:** `{verdict.verdict.upper()}` - {_cell(verdict.reason)}")
    lines.append("")
    lines.append("| # | Subject (as registered) | Status | Detail |")
    lines.append("| --- | --- | --- | --- |")
    for cid in verdict.registered_ids:
        title = title_map.get(cid, "(no registered title)")
        lines.append(
            f"| {_cell(cid)} | {_cell(title)} | {_cell(statuses[cid])} | {_cell(details[cid])} |"
        )

    lines.append("")
    lines.append("### Summary counts - one Check_Registry execution")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("| --- | --- |")
    for category in SUMMARY_CATEGORIES:
        lines.append(f"| {category} | {counts.get(category, 0)} |")
    lines.append(f"| REGISTERED | {len(verdict.registered_ids)} |")
    lines.append(f"| {NOT_EXECUTED} | {len(verdict.missing_ids)} |")
    lines.append("")
    lines.append(
        "`TOTAL` is the number of results this execution emitted; `REGISTERED` is the "
        "number of `@register` declarations. They differ only when a registered check "
        "emits nothing, which is a failure, never a rounding difference."
    )
    lines.append("")
    headline = " / ".join(
        f"{counts.get(category, 0)} {category}" for category in SUMMARY_CATEGORIES
    )
    lines.append(f"`README.md` headline counts, from this same execution (R10.9): **{headline}**")

    registered = set(verdict.registered_ids)
    unregistered = tuple(
        cid for cid in dict.fromkeys(verdict.executed_ids) if cid not in registered
    )
    if unregistered:
        lines.append("")
        lines.append(
            "**Results reported under an unregistered identifier:** "
            + ", ".join(f"`{_cell(cid)}`" for cid in unregistered)
            + ". These have no row - a row may only cite a registered identifier "
            "(R10.3) - and are recorded here so no result is silently dropped. "
            "`verify_claims` coerces such a result to FAIL naming both identifiers "
            "(AD-14, R10.5)."
        )
    if verdict.missing_ids:
        lines.append("")
        lines.append(
            "**Registered but not executed:** "
            + ", ".join(f"`{_cell(cid)}`" for cid in verdict.missing_ids)
            + "."
        )

    return "\n".join(lines)


def _standalone_marker_offsets(text: str, marker: str) -> tuple[int, ...]:
    """Character offsets of every ``marker`` that stands alone on its own line.

    A marker delimits the region only when it occupies a line by itself, which is
    exactly how :func:`render` writes it. Prose that *quotes* a marker mid-sentence -
    which ``docs/state/CURRENT.md`` does, inside backticks, while explaining the
    mechanism - is documentation, not a second region, and is skipped here.
    """
    offsets: list[int] = []
    position = 0
    for line in text.splitlines(keepends=True):
        if line.strip() == marker:
            offsets.append(position + line.index(marker))
        position += len(line)
    return tuple(offsets)


def generated_region_bounds(text: str) -> tuple[int, int]:
    """The offsets of the one generated region's opening and closing markers.

    Why the marker is recognised per line rather than counted textually. The counter
    this replaced was ``text.count(GENERATED_BEGIN)``, and ``docs/state/CURRENT.md``'s
    "How to regenerate" section documents the marker convention by quoting both
    markers in a sentence. The count was therefore 2 and 2, the region was reported
    unusable, and ``--check`` exited ``2`` (unavailable) instead of ``1`` (drift) -
    a real drift verdict replaced by "nothing could be checked", which under I-7 is
    the worst of the three outcomes to be wrong about. Escaping that one sentence
    would have restored the verdict and left the trap armed: the next person to
    document the format re-breaks the generator, and the failure names the document
    rather than the counter. Recognising only a marker that owns its line removes the
    class - a generated region is a block-level construct, and prose about it is not.

    Returns:
        ``(begin, end)`` character offsets of the two delimiting markers.

    Raises:
        LedgerMarkersError: no such region, more than one, or the two out of order.
    """
    begins = _standalone_marker_offsets(text, GENERATED_BEGIN)
    ends = _standalone_marker_offsets(text, GENERATED_END)
    if len(begins) != 1 or len(ends) != 1:
        raise LedgerMarkersError(
            f"expected exactly one line containing only {GENERATED_BEGIN} and one "
            f"containing only {GENERATED_END}; found {len(begins)} and {len(ends)} "
            "(a marker quoted inside prose is not a region delimiter)"
        )
    if ends[0] < begins[0]:
        raise LedgerMarkersError(f"{GENERATED_END} precedes {GENERATED_BEGIN}")
    return begins[0], ends[0]


def render(
    verdict: RegistryVerdict,
    previous: str,
    *,
    titles: Mapping[str, str] | None = None,
) -> str:
    """The full ledger text ``verdict`` projects, given the committed text.

    Only the delimited region changes; every byte of hand-authored prose before
    ``<!-- generated:begin -->`` and after ``<!-- generated:end -->`` is carried
    through unmodified - including prose that quotes those markers, which
    :func:`generated_region_bounds` deliberately does not read as a region.
    Idempotent by construction: rendering the output again with the same verdict
    returns it unchanged, which is what ``--check`` relies on.

    Raises:
        LedgerMarkersError: the markers are absent, duplicated, or out of order.
    """
    begin, end = generated_region_bounds(previous)
    head = previous[:begin]
    tail = previous[end + len(GENERATED_END) :]
    region = render_region(verdict, titles=titles)
    return f"{head}{GENERATED_BEGIN}\n{region}\n{GENERATED_END}{tail}"


def diff_ledger(committed: str, generated: str, *, label: str = "docs/state/CURRENT.md") -> str:
    """A unified diff of the committed ledger against the generated one (R10.7)."""
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
    verdict: RegistryVerdict,
    committed: str | None,
    *,
    titles: Mapping[str, str] | None = None,
    label: str = "docs/state/CURRENT.md",
) -> LedgerProbe:
    """Compare one verdict's projection against committed text. Pure: no file IO."""
    if not verdict.registered_ids:
        return LedgerProbe(
            status="unavailable",
            detail=(
                "no checks are registered, so there is no matrix to project; "
                "the ledger cannot be generated from an empty registry"
            ),
        )
    if committed is None:
        return LedgerProbe(
            status="unavailable",
            detail=(
                f"{label} is missing or unreadable; this generator owns only the "
                "delimited region and will not create the Truth_Ledger"
            ),
        )
    try:
        generated = render(verdict, committed, titles=titles)
    except LedgerMarkersError as exc:
        return LedgerProbe(
            status="unavailable",
            detail=(
                f"{label} has no usable generated region ({exc}); add "
                f"{GENERATED_BEGIN} / {GENERATED_END} around the check matrix, then "
                "run --write"
            ),
        )
    if committed == generated:
        return LedgerProbe(
            status="ok",
            detail=(
                f"{label} matches the {len(verdict.registered_ids)}-check registry "
                f"execution it reports ({verdict.counts.get('PASS', 0)} PASS, "
                f"{verdict.counts.get('FAIL', 0)} FAIL, "
                f"{verdict.counts.get('PARTIAL', 0)} PARTIAL, "
                f"{verdict.counts.get('SKIP', 0)} SKIP)"
            ),
        )
    return LedgerProbe(
        status="fail",
        detail=(
            f"{label}'s generated region differs from the registry execution it "
            "claims to report; regenerate it in the same change "
            "(python -m scripts.audit.ledger_gen --write)"
        ),
        diff=diff_ledger(committed, generated, label=label),
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


def evaluate(*, path: Path = LEDGER_DOC) -> LedgerProbe:
    """Execute the Check_Registry once and compare the ledger against its verdict."""
    verdict = registry_gate.evaluate()
    return probe_text(verdict, _read(path), label=_relative(path))


def run(*, write: bool = False, check: bool = False, path: Path = LEDGER_DOC) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module."""
    label = _relative(path)
    verdict = registry_gate.evaluate()
    committed = _read(path)

    if not write:
        probe = probe_text(verdict, committed, label=label)
        if probe.diff:
            _echo(probe.diff, end="")
        symbol = {"ok": "[OK]", "fail": "[XX]", "unavailable": "[??]"}[probe.status]
        _echo(f"{symbol} ledger-gen: {probe.status.upper()} - {probe.detail}")
        if not check and probe.status != "ok":
            _echo()
            _echo(
                "(regenerate with `python -m scripts.audit.ledger_gen --write`; the "
                "registry execution is the only source of the rows and counts.)"
            )
        return probe.exit_code

    # --write. Refuse on the same conditions --check reports unavailable for: an
    # empty registry has no matrix to project, and a ledger with no markers is a
    # hand-written document this generator must not overwrite.
    probe = probe_text(verdict, committed, label=label)
    if probe.status == "unavailable":
        _echo(f"[??] ledger-gen: UNAVAILABLE - {probe.detail}")
        return probe.exit_code

    assert committed is not None  # probe_text reports unavailable otherwise
    generated = render(verdict, committed)
    path.write_text(generated, encoding="utf-8", newline="\n")
    state = "unchanged" if committed == generated else "rewritten"
    _echo(
        f"[OK] ledger-gen: {label} {state} - {len(verdict.registered_ids)} row(s), "
        f"verdict={verdict.verdict.upper()}"
    )
    return _EXIT_CODES["ok"]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    known = {"--check", "--write", "--help", "-h"}
    unknown = [arg for arg in args if arg not in known]
    if unknown or "--help" in args or "-h" in args:
        _echo(_USAGE, end="")
        return 0 if not unknown else 2
    if "--write" in args and "--check" in args:
        _echo(_USAGE, end="")
        return 2
    return run(write="--write" in args, check="--check" in args)


if __name__ == "__main__":
    sys.exit(main())
