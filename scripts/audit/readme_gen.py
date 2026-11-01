"""Generate the README's headline-counts region (design E0.5 / AD-21).

Feature: decision-quality-proof, task 4.2. Requirements R4.4, R4.5, R4.8, R4.11.

``README.md`` states the project's headline verdict - "Today it reports **51 PASS / 3
FAIL / 0 PARTIAL / 10 SKIP / 64 TOTAL**" - and until this module existed **no code path
wrote that line**. The defect is narrower and stranger than "the README is
hand-maintained". ``scripts/audit/ledger_gen.py`` already *renders a README headline*:
its ``render_region`` emits ``f"`README.md` headline counts, from this same execution
(R10.9): **{headline}**"`` at ``ledger_gen.py:324`` - into ``docs/state/CURRENT.md``'s
own generated region, at ``CURRENT.md:119``. The remaining step was literally a human
copying ``CURRENT.md:119`` into ``README.md:24``.

**And the two lines are not the same number, for a correct reason.** ``README.md:24``
reads 51/3/0/10/64; ``CURRENT.md:119`` reads 52/3/0/9/64. They are **two different
executions**:

* ``doc_truth::_claim_readme_headline_counts`` - the check (C56) that *enforces* the
  README line - compares it against a **nested** ``verify_claims`` execution carrying
  ``SYNAPSE_DOC_TRUTH_NESTED=1``. Under that flag the nested copy of this very claim
  self-excludes (``skip``, ``required``), the nested ``doc_truth`` aggregate is
  therefore ``unavailable``, and nested **C56 is SKIP**. That is the recursion guard,
  and it bounds the recursion at depth one.
* ``ledger_gen`` renders from the **top-level** verdict, in which C56 is evaluated
  normally.

So a generator that projected the top-level counts into ``README.md`` would make C56
**FAIL by exactly the guard delta** - the gate would be broken by the automation meant
to serve it. This module therefore projects the *nested* execution, obtained through the
same function the gate calls: :func:`scripts.audit.doc_truth.nested_suite_counts`. One
execution semantics, one implementation, no second model of the guard.

AD-21 also names the tempting alternative and rejects it as **unsound, not merely
inelegant**: derive the nested counts from the top-level verdict by applying the guard's
known one-check delta. The delta is not a fixed ``+1 PASS / -1 SKIP``; it is
``+1 <top-level C56 status> / -1 SKIP``, and at ``--write`` time the README has not yet
been updated, so top-level C56 is FAIL. The compensation would be computed from a status
the write is about to change - a model of a mechanism compared against itself.

**Two constraints on the rendered text, both mechanically checked here rather than
trusted.**

1. The counts line must keep matching ``doc_truth._VERIFY_CLAIMS_MENTION``
   (``verify[-_]claims``), or ``_readme_headline_line`` returns ``None`` and C56
   silently **skips** - a generated headline that dropped the phrase would disable the
   gate it exists to serve. The pattern is *imported*, never restated.
2. R4.8's compensation sentence must not out-rank the counts line.
   ``_readme_headline_line`` picks the candidate with the most extractable counts and
   ``_extract_count`` needs a digit *adjacent* to the category word, so the compensation
   is rendered **in words** ("one more PASS and one fewer SKIP") and never with a digit
   beside a status category. It is not digit-free - it names check ``C56`` - and
   "carries no digits" would therefore be the wrong check to write; the check written is
   the one that matters. :func:`headline_candidates` re-derives the ranking, and
   :func:`_constraint_violation` refuses the write unless **no other line of the region**
   is a candidate at all *and* the counts line is the **unique richest** candidate in the
   document about to be written.

Marker discipline is ``ledger_gen``'s, imported rather than reimplemented: the literals
are owned by ``scripts/audit/gate_surface.py``, and
:func:`~scripts.audit.ledger_gen.generated_region_bounds` (via its
``_standalone_marker_offsets``) recognises a marker only when it **owns its line**, so
prose that quotes a marker is documentation and not a second region. Zero markers, more
than one, or the two out of order raise
:class:`~scripts.audit.ledger_gen.LedgerMarkersError` -> ``unavailable`` -> exit ``2``
with the document left byte-identical (R4.11). Every byte outside the region survives a
write (R4.5), and ``--write`` never creates the document.

Run::

    python -m scripts.audit.readme_gen                      # regenerate + diff (default)
    python -m scripts.audit.readme_gen --check              # explicit form of the default
    python -m scripts.audit.readme_gen --write              # rewrite the region
    python -m scripts.audit.readme_gen --check --counts-json PATH

``--counts-json`` reads a payload a previous ``verify_claims --json`` execution emitted -
in CI, the one ``doc_truth --check --emit-nested-json`` just produced - so one nested
execution serves both steps and ``truth-gates.yml``'s ``timeout-minutes: 25`` still
covers a single registry pass. The two steps are ordered and the ordering is
load-bearing; it is recorded in ``infrastructure/quality/blocking-steps.yaml``.

Exit codes: ``0`` in agreement, ``1`` drift (a unified diff is printed), ``2``
unavailable - the markers are unusable, the nested execution could not be read, or the
rendered region would not satisfy a constraint above. ``2`` is non-passing: absence of
proof is never a pass (I-7).

Every read uses ``encoding='utf-8'`` (E-S13-07) and every printed byte is ASCII, so a
Windows console can render a diff.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]

# Ensure the repo root is importable when run as a bare script (not -m), mirroring
# ledger_gen. Kept before the local imports below for the same reason it is there.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit import doc_truth  # noqa: E402

# The marker convention has exactly one definition in this repository: the gate-surface
# generator (E1.6) owns the literals and ledger_gen (E1.4) owns the region arithmetic.
# Both are imported, not restated - a second copy of either is a second thing to drift.
from scripts.audit.gate_surface import GENERATED_BEGIN, GENERATED_END  # noqa: E402
from scripts.audit.ledger_gen import (  # noqa: E402
    LedgerMarkersError,
    generated_region_bounds,
)

#: The document this generator owns. It owns the delimited region of it and nothing else.
DOCUMENT: Final[Path] = ROOT / "README.md"

#: The registered identifier of the check that both enforces the headline line and is
#: counted inside it - `verify_claims.py`'s `@register("C56", ...)`. Stated once here and
#: then *required to be present* in the nested payload: a renumbering cannot silently
#: produce a wrong compensation sentence, it produces exit 2 naming the absent id.
GUARD_CHECK_ID: Final[str] = "C56"

#: The status the guard's self-exclusion produces for :data:`GUARD_CHECK_ID` in the
#: nested execution. `doc_truth`'s aggregate is `unavailable` there because the headline
#: claim is a required skip, and `verify_claims.GATE_STATUS["unavailable"]` is `"SKIP"`.
GUARD_STATUS_NESTED: Final[str] = "SKIP"

#: The status a top-level run reports for :data:`GUARD_CHECK_ID` when this document
#: agrees with the execution the check compares it against. Derived, and derivable only
#: from the nested status being :data:`GUARD_STATUS_NESTED`: `evaluate_claims` reports
#: `fail` before it reports `unavailable`, so a nested SKIP is itself the evidence that
#: no sibling `doc_truth` claim drifted in that execution. The rendered sentence stays
#: **conditional** on the check passing rather than asserting that it does, because this
#: module cannot observe a top-level run from inside a nested one (AD-21).
GUARD_STATUS_TOP_LEVEL: Final[str] = "PASS"

#: The value rendered when the derivation above does not apply.
UNKNOWN_STATUS: Final[str] = "unknown"

ReadmeStatus = Literal["ok", "fail", "unavailable"]

_EXIT_CODES: Final[dict[ReadmeStatus, int]] = {"ok": 0, "fail": 1, "unavailable": 2}

_USAGE: Final[str] = (
    "usage: python -m scripts.audit.readme_gen [--check | --write] [--counts-json PATH]\n"
    "  (no flag) / --check : regenerate in memory and diff against the committed README\n"
    "  --write             : rewrite the generated region of README.md\n"
    "  --counts-json PATH  : read a nested verify_claims --json payload instead of\n"
    "                        executing the suite (produced by `doc_truth --check\n"
    "                        --emit-nested-json PATH`, which must run first)\n"
)

__all__ = [
    "DOCUMENT",
    "GENERATED_BEGIN",
    "GENERATED_END",
    "GUARD_CHECK_ID",
    "GUARD_STATUS_NESTED",
    "GUARD_STATUS_TOP_LEVEL",
    "HeadlineProjection",
    "ReadmeProbe",
    "compose",
    "counts_line",
    "diff_readme",
    "evaluate",
    "headline_candidates",
    "main",
    "probe_text",
    "project",
    "project_payload",
    "render_region",
    "run",
]


class HeadlineProjection(BaseModel):
    """The README region's body, projected from ONE nested Check_Registry execution.

    ``guard_status_top_level`` is a derivation, not an observation, and is
    :data:`UNKNOWN_STATUS` whenever the derivation does not hold - see
    :data:`GUARD_STATUS_TOP_LEVEL`. The rendered sentence says less when this is
    unknown; it never says more (I-7).
    """

    model_config = ConfigDict(frozen=True)

    counts: Mapping[str, int]
    guard_check: str
    guard_status_nested: str
    guard_status_top_level: str

    @property
    def headline(self) -> str:
        """The five counts as the README states them: ``51 PASS / 3 FAIL / ...``.

        Ordered by ``doc_truth._HEADLINE_CATEGORIES``, the same tuple the extractor
        walks, so the rendered order and the checked order cannot diverge.
        """
        return " / ".join(
            f"{self.counts[category]} {category}" for category in doc_truth._HEADLINE_CATEGORIES
        )

    @property
    def guard_self_excluded(self) -> bool:
        """True when the guard is what made the comparing check non-passing (R4.8)."""
        return self.guard_status_nested == GUARD_STATUS_NESTED


class ReadmeProbe(BaseModel):
    """Whether the committed README matches the region its execution projects."""

    model_config = ConfigDict(frozen=True)

    status: ReadmeStatus
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


# ---------------------------------------------------------------------------
# Projection. One nested execution in, one projection out.
# ---------------------------------------------------------------------------


def project_payload(verdict: doc_truth.NestedVerdict) -> tuple[HeadlineProjection | None, str]:
    """Project one nested execution, or say why it cannot be projected.

    The guard row is **required**. Without it this module would have to assume the
    nested status of :data:`GUARD_CHECK_ID`, and an assumed status is exactly the second
    model of the guard AD-21 exists to remove. An absent row is reported, not inferred.
    """
    missing = [
        category for category in doc_truth._HEADLINE_CATEGORIES if category not in verdict.counts
    ]
    if missing:
        return None, (
            "the nested verify_claims payload reports no count for "
            f"{', '.join(missing)}, so the headline cannot be projected from it"
        )
    nested_status = verdict.status_of(GUARD_CHECK_ID)
    if nested_status is None:
        return None, (
            f"the nested verify_claims payload carries no row for {GUARD_CHECK_ID}, the check "
            "that both enforces this headline and is counted inside it, so the "
            "recursion-guard compensation (R4.8) cannot be stated from that execution"
        )
    top_level = GUARD_STATUS_TOP_LEVEL if nested_status == GUARD_STATUS_NESTED else UNKNOWN_STATUS
    return (
        HeadlineProjection(
            counts={
                category: verdict.counts[category] for category in doc_truth._HEADLINE_CATEGORIES
            },
            guard_check=GUARD_CHECK_ID,
            guard_status_nested=nested_status,
            guard_status_top_level=top_level,
        ),
        "",
    )


def _read_counts_json(path: Path) -> tuple[doc_truth.NestedVerdict | None, str]:
    """Parse a previously emitted ``verify_claims --json`` payload.

    Parsed by ``doc_truth``'s own parser, so a payload accepted here is a payload the
    gate would accept - there is one reader of that shape in this repository.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"--counts-json {path} could not be read: {exc!r}"
    verdict = doc_truth._parse_suite_summary(text)
    if verdict is None:
        return None, (
            f"--counts-json {path} holds no parseable verify_claims summary; it must be the "
            "payload of `python -m scripts.audit.verify_claims --json` as emitted by "
            "`doc_truth --check --emit-nested-json PATH`"
        )
    return verdict, ""


def project(counts_json: Path | None = None) -> tuple[HeadlineProjection | None, str]:
    """The projection this repository's nested execution supports, or the reason not.

    ``counts_json`` short-circuits the 900s suite by reading a payload a previous step
    emitted. It is not a weaker source: the payload IS a nested execution's output, and
    the ordering that makes it available is declared in ``blocking-steps.yaml``.
    """
    if counts_json is not None:
        verdict, error = _read_counts_json(counts_json)
    else:
        verdict, error = doc_truth.nested_suite_counts()
    if verdict is None:
        return None, error
    return project_payload(verdict)


# ---------------------------------------------------------------------------
# Rendering. Exactly two content lines, and both are constrained.
# ---------------------------------------------------------------------------

#: The identifier appears once in this module (:data:`GUARD_CHECK_ID`) and is
#: interpolated everywhere it is rendered, here included - a second literal would be a
#: second thing to keep in sync with `verify_claims.py`'s registration.
_PREAMBLE: Final[tuple[str, ...]] = (
    "<!-- Generated by `python -m scripts.audit.readme_gen --write` from ONE nested",
    f"     `scripts.audit.verify_claims` execution - the same execution check {GUARD_CHECK_ID}'s",
    "     headline-counts claim compares this line against (design E0.5 / AD-21;",
    "     R4.4, R4.5, R4.8, R4.11). Do not hand-edit: `--check` prints a unified diff",
    "     and fails on drift, and hand edits inside these markers are overwritten.",
    "     Prose outside them survives. The counts are the NESTED run's, which is why",
    "     they differ by one check from `docs/state/CURRENT.md`'s - see below. -->",
)


def counts_line(projection: HeadlineProjection) -> str:
    """The one line C56 reads: it names the suite and carries all five counts.

    The wording is deliberately the wording the README already carried, because the
    sentence has to remain a human instruction ("run this command") as well as a
    machine-checked claim.
    """
    return (
        f"Run `make verify-claims` for the live truth. Today it reports **{projection.headline}**."
    )


def _compensation_line(projection: HeadlineProjection) -> str:
    """R4.8's disclosure, in words, so it can never out-rank the counts line.

    No digit may sit adjacent to a status category word here: ``_extract_count`` reads
    ``(\\d+)\\s*PASS`` and ``PASS\\s*[=:]\\s*(\\d+)``, and a candidate line's rank is the
    number of categories it yields. This sentence must rank zero.

    The top-level clause is **conditional** ("whenever that check passes") rather than
    an assertion. This module runs a nested execution; it cannot observe a top-level one,
    and the write it is about to perform is what would make that check pass. Asserting
    the outcome would be the compensation-from-a-status-about-to-change error AD-21
    rejects.
    """
    check = projection.guard_check
    if not projection.guard_self_excluded:
        return (
            f"Those are the counts of the nested execution that check {check} compares this "
            f"line against. In that execution {check} did not report the self-exclusion the "
            "recursion guard produces, so the usual one-check compensation does not apply "
            f"here and a top-level headline may state the same counts; read {check}'s own "
            "detail for what it reported."
        )
    return (
        f"Those are the counts of the nested execution that check {check} compares this line "
        f"against: {check} is the check that validates this very line by executing the suite, "
        "so the nested run self-excludes it to bound the recursion at depth one and counts it "
        f"as a skip. A top-level `make verify-claims` evaluates {check} instead, so whenever "
        "that check passes the top-level headline carries one more PASS and one fewer SKIP "
        "than the line above. That asymmetry is the recursion guard, not a discrepancy."
    )


def render_region(projection: HeadlineProjection) -> str:
    """The generated region's body: the preamble, the counts line, the disclosure.

    Exactly two content lines (design E0.5). Everything else is an HTML comment, so the
    rendered README is visually what it was before this module existed.
    """
    return "\n".join(
        [
            *_PREAMBLE,
            "",
            counts_line(projection),
            "",
            _compensation_line(projection),
        ]
    )


def compose(projection: HeadlineProjection, previous: str) -> str:
    """The full README text ``projection`` implies, given the committed text.

    Only the delimited region changes; every byte before ``<!-- generated:begin -->``
    and after ``<!-- generated:end -->`` is carried through unmodified - including prose
    that quotes those markers, which :func:`generated_region_bounds` deliberately does
    not read as a region (R4.5). Idempotent by construction, which is what ``--check``
    relies on.

    Raises:
        LedgerMarkersError: the markers are absent, duplicated, or out of order (R4.11).
    """
    begin, end = generated_region_bounds(previous)
    head = previous[:begin]
    tail = previous[end + len(GENERATED_END) :]
    region = render_region(projection)
    return f"{head}{GENERATED_BEGIN}\n{region}\n{GENERATED_END}{tail}"


# ---------------------------------------------------------------------------
# The two mechanical constraints on the rendered text (AD-21), as four clauses
# ---------------------------------------------------------------------------


def headline_candidates(text: str) -> tuple[tuple[int, str], ...]:
    """Every line C56 would consider a headline candidate, with its rank.

    Re-derives ``doc_truth._readme_headline_line``'s selection rule from the imported
    pattern and the imported extractor: a candidate names the suite and yields at least
    one count, and the richest candidate wins. Returned ranked, because the rule this
    module has to guarantee is *uniqueness of the maximum*, which the upstream helper
    does not expose - it returns the winner and says nothing about a tie.
    """
    ranked: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if doc_truth._VERIFY_CLAIMS_MENTION.search(raw) is None:
            continue
        found = sum(
            1
            for category in doc_truth._HEADLINE_CATEGORIES
            if doc_truth._extract_count(raw, category) is not None
        )
        if found:
            ranked.append((found, raw.strip()))
    return tuple(ranked)


def _constraint_violation(projection: HeadlineProjection, generated: str) -> str | None:
    """Why the generated document would break C56, or ``None`` if it would not.

    Checked against the text that would actually be written, not against the renderer's
    intent. Every clause is AD-21's, and every one is a failure of *this* generator
    rather than of the document, so they report ``unavailable`` and leave the file
    untouched.

    Four clauses, narrowing from the line to the region to the document:

    1. the counts line matches the imported ``_VERIFY_CLAIMS_MENTION`` - otherwise
       ``_readme_headline_line`` returns ``None`` and C56 **skips**, which is the worst
       available outcome because it looks like nothing is wrong;
    2. the counts line yields an extractable count for **every** category - a category
       the generator states unextractably reads to C56 as ``absent`` and drifts;
    3. no *other* line of the rendered region is a candidate at all. This is R4.8's
       words-not-digits rule checked directly rather than through its consequence: the
       compensation sentence names a check identifier (``C56``) and so does carry
       digits, but none adjacent to a status category word, and ``_extract_count`` needs
       adjacency. Scoped to the region on purpose - a low-ranking verify-claims line
       elsewhere in the document is legitimate prose and C56 still picks the richest;
    4. the counts line is the unique richest candidate in the whole document, and
       ``doc_truth``'s own selector agrees.
    """
    expected = counts_line(projection)
    if doc_truth._VERIFY_CLAIMS_MENTION.search(expected) is None:
        return (
            "the rendered counts line does not match doc_truth's headline pattern "
            f"({doc_truth._VERIFY_CLAIMS_MENTION.pattern!r}), so C56 would find no headline "
            "line and skip - the gate would be silently disabled by its own generator"
        )
    unextractable = [
        category
        for category in doc_truth._HEADLINE_CATEGORIES
        if doc_truth._extract_count(expected, category) is None
    ]
    if unextractable:
        return (
            "the rendered counts line yields no extractable count for "
            f"{', '.join(unextractable)}, so C56 would read that category as absent from "
            "the README and report drift against a count this generator did state"
        )
    region_extras = [
        line
        for _rank, line in headline_candidates(render_region(projection))
        if line != expected.strip()
    ]
    if region_extras:
        return (
            "the generated region carries a headline candidate other than the counts line, "
            "so R4.8's compensation has acquired a digit adjacent to a status category word "
            "where it must stay in words: " + " | ".join(region_extras)
        )
    candidates = headline_candidates(generated)
    if not candidates:
        return "the generated README carries no verify-claims headline candidate at all"
    best = max(rank for rank, _line in candidates)
    winners = [line for rank, line in candidates if rank == best]
    if len(winners) != 1:
        return (
            f"{len(winners)} lines tie as the richest headline candidate "
            f"({best} extractable count(s) each), so which line C56 pins is ambiguous: "
            + " | ".join(winners)
        )
    if winners[0] != expected.strip():
        return (
            "the richest headline candidate in the generated README is not the generated "
            f"counts line; C56 would pin {winners[0]!r} instead of {expected.strip()!r}"
        )
    selected = doc_truth._readme_headline_line(generated)
    if selected != expected.strip():
        return (
            "doc_truth would select "
            f"{selected!r} rather than the generated counts line {expected.strip()!r}"
        )
    return None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def diff_readme(committed: str, generated: str, *, label: str = "README.md") -> str:
    """A unified diff of the committed README against the generated one."""
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
    projection: HeadlineProjection,
    committed: str | None,
    *,
    label: str = "README.md",
) -> ReadmeProbe:
    """Compare one projection against committed text. Pure: no file IO, no subprocess."""
    if committed is None:
        return ReadmeProbe(
            status="unavailable",
            detail=(
                f"{label} is missing or unreadable; this generator owns only the delimited "
                "region and will not create the document"
            ),
        )
    try:
        generated = compose(projection, committed)
    except LedgerMarkersError as exc:
        return ReadmeProbe(
            status="unavailable",
            detail=(
                f"{label} has no usable generated region ({exc}); add {GENERATED_BEGIN} / "
                f"{GENERATED_END} around the headline counts line, then run --write. The "
                "document is left byte-identical (R4.11)"
            ),
        )
    violation = _constraint_violation(projection, generated)
    if violation is not None:
        return ReadmeProbe(
            status="unavailable",
            detail=f"the region this generator would write would break C56: {violation}",
        )
    if committed == generated:
        return ReadmeProbe(
            status="ok",
            detail=(
                f"{label}'s generated region matches the nested verify_claims execution it "
                f"reports ({projection.headline}); {projection.guard_check} is "
                f"{projection.guard_status_nested} in that execution, as the recursion guard "
                "requires"
            ),
        )
    return ReadmeProbe(
        status="fail",
        detail=(
            f"{label}'s generated region differs from the nested verify_claims execution it "
            "claims to report; regenerate it in the same change "
            "(python -m scripts.audit.readme_gen --write)"
        ),
        diff=diff_readme(committed, generated, label=label),
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


def evaluate(*, path: Path = DOCUMENT, counts_json: Path | None = None) -> ReadmeProbe:
    """Project one nested execution and compare the committed README against it."""
    projection, error = project(counts_json)
    if projection is None:
        return ReadmeProbe(status="unavailable", detail=error)
    return probe_text(projection, _read(path), label=_relative(path))


# ---------------------------------------------------------------------------
# CLI. `print` is acceptable here and nowhere else in this module.
# ---------------------------------------------------------------------------


def _echo(text: str = "", *, end: str = "\n") -> None:
    """ASCII-only output, honouring the Windows-console contract even for a diff.

    The document may legitimately hold non-ASCII (README.md uses em dashes), so the
    transliteration belongs on the way out rather than on the way in - the same split
    ``ledger_gen`` makes for registry titles it must reproduce verbatim.
    """
    print(text.encode("ascii", "backslashreplace").decode("ascii"), end=end)


def run(
    *,
    write: bool = False,
    check: bool = False,
    counts_json: Path | None = None,
    path: Path = DOCUMENT,
) -> int:
    """CLI entry point. ``0`` in agreement, ``1`` drift, ``2`` unavailable."""
    label = _relative(path)
    projection, error = project(counts_json)
    if projection is None:
        # I-7: no execution means no verdict, and no write. Never a pass, and the
        # document is left byte-identical.
        _echo(f"[??] readme-gen: UNAVAILABLE - {error}")
        return _EXIT_CODES["unavailable"]

    committed = _read(path)
    probe = probe_text(projection, committed, label=label)

    if not write:
        if probe.diff:
            _echo(probe.diff, end="")
        symbol = {"ok": "[OK]", "fail": "[XX]", "unavailable": "[??]"}[probe.status]
        _echo(f"{symbol} readme-gen: {probe.status.upper()} - {probe.detail}")
        if not check and probe.status != "ok":
            _echo()
            _echo(
                "(regenerate with `python -m scripts.audit.readme_gen --write`; the nested "
                "verify_claims execution is the only source of these counts.)"
            )
        return probe.exit_code

    # --write. Refuse on exactly the conditions --check reports unavailable for: a
    # README with no usable markers is a hand-written document this generator must not
    # create or overwrite, and a region that would break C56 must not be written at all.
    if probe.status == "unavailable":
        _echo(f"[??] readme-gen: UNAVAILABLE - {probe.detail}")
        return probe.exit_code

    assert committed is not None  # probe_text reports unavailable otherwise
    generated = compose(projection, committed)
    path.write_text(generated, encoding="utf-8", newline="\n")
    state = "unchanged" if committed == generated else "rewritten"
    _echo(
        f"[OK] readme-gen: {label} {state} - {projection.headline} "
        f"({projection.guard_check}={projection.guard_status_nested} nested)"
    )
    return _EXIT_CODES["ok"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="readme_gen",
        description=(
            "Project README.md's headline counts from the nested Check_Registry execution "
            "that check C56 compares them against (R4.4, R4.5, R4.8, R4.11)."
        ),
        add_help=True,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate in memory and diff against the committed README (the default)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite the generated region; never creates the document",
    )
    parser.add_argument(
        "--counts-json",
        metavar="PATH",
        default=None,
        help=(
            "read a nested verify_claims --json payload instead of executing the suite; "
            "produced by `doc_truth --check --emit-nested-json PATH`, which must run first"
        ),
    )
    args = parser.parse_args(argv)
    if args.write and args.check:
        _echo(_USAGE, end="")
        return _EXIT_CODES["unavailable"]
    counts_json = Path(args.counts_json) if args.counts_json else None
    return run(write=bool(args.write), check=bool(args.check), counts_json=counts_json)


if __name__ == "__main__":
    sys.exit(main())
