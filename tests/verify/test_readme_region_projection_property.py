"""The README's headline region is a projection of the execution that enforces it.

Feature: decision-quality-proof, task 4.5. Requirements **R4.4, R4.5, R4.8, R4.11**.

An attribution conflict, surfaced rather than resolved
-----------------------------------------------------

The design's cross-cutting AD-13 section states that the pin-extractor-resolution clause
"is Property 47's second clause", while the property index assigns extractor resolution to
**Property 48** (R5.2, R5.11, R5.12, R6.3) and gives Property 47 the README region only.
The implementation plan follows the index and lands extractor resolution in task 8.3.
**This file follows the index too** - it asserts the README region and nothing about pin
extractors. The discrepancy is recorded here rather than silently decided, because a reader
looking for the extractor clause should be told where it went instead of concluding it was
dropped.

What this closes
----------------

``README.md`` states the project's headline verdict, and until ``scripts/audit/readme_gen.py``
existed **no code path wrote that line**. The defect was narrower and stranger than "the
README is hand-maintained": ``ledger_gen`` already renders a README headline - into
``docs/state/CURRENT.md``'s own generated region - so the remaining step was a human
copying one document's line into another.

And the two lines legitimately differ. ``README.md`` reads 51/3/0/10/64 while
``CURRENT.md`` reads 52/3/0/9/64, because they are **two different executions**: check C56
compares the README against a *nested* ``verify_claims`` run in which the recursion guard
makes C56 itself self-exclude (SKIP), while ``ledger_gen`` renders the *top-level* verdict
in which C56 is evaluated normally. A generator that projected the top-level counts into
the README would therefore make C56 FAIL by exactly the guard delta - the gate broken by
the automation meant to serve it.

AD-21 also rejects the tempting shortcut - derive the nested counts from the top-level
verdict by applying the guard's known one-check delta - as **unsound, not merely
inelegant**: at ``--write`` time top-level C56 is FAIL, so the compensation would be
computed from a status the write is about to change. Two clauses below hold that line: an
absent guard row is reported naming the identifier rather than assumed (R4.4), and the
rendered top-level sentence stays **conditional**, because this module runs a nested
execution and cannot observe a top-level one.

The two constraints these properties exist for
----------------------------------------------

Both are ways the generator could silently disable the gate it serves:

1. The rendered counts line must keep matching ``doc_truth._VERIFY_CLAIMS_MENTION``, or
   ``_readme_headline_line`` returns ``None`` and **C56 skips** - green, and checking
   nothing.
2. R4.8's compensation sentence must not out-rank the counts line.
   ``_readme_headline_line`` picks the candidate yielding the most extractable counts, and
   ``_extract_count`` needs a digit *adjacent* to a category word - so the compensation is
   rendered **in words** and must never acquire one. If it out-ranked the counts line, C56
   would pin a sentence instead of a measurement.

   The sentence is **not digit-free** - it names check ``C56`` - so "carries no digits"
   would be the wrong assertion, and a clause below pins that correction by asserting the
   sentence *does* carry a digit while still yielding no extractable count. The rule that
   matters is adjacency, and it is checked through the extractor itself rather than by eye.

Uniqueness, not "probably richest"
----------------------------------

``_readme_headline_line`` returns the richest candidate and says nothing about ties, so
which line C56 pins would otherwise depend on document order. A document carrying a
**tying** rival outside the generated region is therefore generated deliberately and the
generator must *refuse* it (``unavailable``, exit 2) rather than pick a winner; a
lower-ranking ``verify-claims`` line outside the region is legitimate prose and must stay
admissible. Both cases have their own clause below.

Why the subjects are the pure functions and the ``--counts-json`` path only
--------------------------------------------------------------------------

``doc_truth``'s nested suite-counts helper spawns the whole Check_Registry as a subprocess
under a 900-second bound - a category 2/3 workload under invariant I-0, CI-only. **No test
in this file can reach it**, and that is structural rather than promised:

* every property drives ``project_payload`` with a ``NestedVerdict`` constructed here, or
  the pure functions ``compose`` / ``render_region`` / ``counts_line`` /
  ``headline_candidates`` / ``probe_text``;
* every test that touches the CLI passes ``counts_json=``, which short-circuits the suite
  in ``readme_gen.project``, and requests the ``forbid_suite_execution`` fixture, which
  replaces the helper with one that raises. One clause below pins the short-circuit
  itself, so the exemption is a tested fact and not an assumption about a code path;
* ``evaluate()`` and a bare ``project()`` are never called.

The real ``README.md`` is never written either: ``probe_text`` and ``compose`` are pure and
take the committed text as an argument, and the two write-path clauses operate on
``tmp_path`` copies.

``NestedVerdict`` is **unhashable** - its ``counts`` field validates to a ``dict``, so the
generated ``__hash__`` raises ``TypeError``. Nothing here puts one in a set, a dict key, a
``unique=True`` list or a cache; the ``unique`` constraint below applies to check
identifiers, which are strings.

Counts are generated including the awkward cases - zero, all-equal categories, and large
numbers - because the ranking rule counts *how many* categories a line yields, and a
projection where several categories share a value is exactly where a naive extractor might
double-count or tie.

What would falsify these properties
-----------------------------------

* Rewording the counts line so it no longer names the suite: the ``pattern`` clause fails.
* Rendering the compensation with a digit beside a category: the ``compensation`` clause
  fails.
* Composing non-idempotently: the ``idempotent`` clause fails and ``--check`` would
  oscillate.
* Reaching the region with ``str.replace`` or a bare ``.index`` rather than by standalone
  marker offsets: the quoted-marker clauses fail, because a document that documents the
  convention carries the literals in running text *before* the region begins.
* Returning ``ok`` for an unusable marker set, an absent guard row, or a tie: those clauses
  fail, and absence of proof would be reading as a pass (I-7).
* Creating ``README.md`` under ``--write``: the creation clause fails.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles via ``HYPOTHESIS_PROFILE``. No subprocess and no registry execution: not
``slow``-marked, and its locus is ``ci.yml::uplift-verify``'s fast step.

**Validates: Requirements 4.4, 4.5, 4.8, 4.11**
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import doc_truth, readme_gen
from scripts.audit.gate_surface import GENERATED_BEGIN, GENERATED_END
from scripts.audit.ledger_gen import LedgerMarkersError, generated_region_bounds

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Prose fragments. The interesting ones quote a marker MID-LINE.
# ---------------------------------------------------------------------------

#: Prose that MENTIONS the markers without being them. ``_standalone_marker_offsets``
#: recognises a marker only when it owns its line, so this text is documentation and not a
#: second region - it must survive a write untouched (R4.5). This is the shape a naive
#: ``str.replace`` or ``text.index(GENERATED_BEGIN)`` implementation destroys.
_MARKER_QUOTES: Final[tuple[str, ...]] = (
    f"The region between `{GENERATED_BEGIN}` and `{GENERATED_END}` is generated.",
    f"    Do not hand-edit anything after {GENERATED_BEGIN} on this very line.",
    f"A closing `{GENERATED_END}` inside a sentence delimits nothing.",
)

#: A ``verify-claims`` line that yields exactly one count. It IS a headline candidate, and
#: a legitimate one: C56 still picks the richest, so prose recalling an old number must not
#: make the generator refuse. Included in the generated documents so every clause below
#: runs against a document carrying a real, lower-ranking rival.
_QUIET_RIVAL: Final[str] = "An older note said `make verify-claims` reported 3 FAIL."

#: A rival that TIES the counts line: it names the suite and yields all five categories.
#: Five is the maximum rank, so a tie is the strongest attack available - nothing can
#: out-rank the counts line, but an equal candidate makes C56's choice order-dependent.
_TYING_RIVAL: Final[str] = (
    "Historically `make verify-claims` reported 1 PASS / 2 FAIL / 3 PARTIAL / 4 SKIP / 10 TOTAL."
)

_PLAIN_FRAGMENTS: Final[tuple[str, ...]] = (
    "# SYNAPSE",
    "",
    "A multi-agent supply-chain system.",
    "## Truth",
    "> A SKIP is not a PASS.",
    _QUIET_RIVAL,
)

#: Printable ASCII, digits included - surrounding prose is arbitrary as far as R4.5 is
#: concerned, and constraining the alphabet to dodge a clause would be exactly the
#: generator-weakening R2.10 forbids. Newlines are excluded because line structure is
#: assembled explicitly below, not drawn.
_PROSE_CHARS: Final[str] = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,;:!?'\"()[]{}*_#`-/<>|=+"
)

_FREE_TEXT: Final = st.text(alphabet=_PROSE_CHARS, max_size=60)


def _neutralise(line: str) -> str:
    """Keep drawn prose *prose*: a line that IS a marker would be a second region.

    Only the degenerate-marker clause gets to build extra regions, and it builds them
    explicitly. A drawn line that happened to strip to a marker literal would otherwise
    turn a byte-preservation example into a marker-arithmetic example and report the wrong
    failure.
    """
    return f"{line} ." if line.strip() in {GENERATED_BEGIN, GENERATED_END} else line


@st.composite
def _prose_block(draw: st.DrawFn) -> str:
    """Zero to four newline-terminated prose lines, sometimes quoting a marker."""
    lines: list[str] = draw(
        st.lists(
            st.one_of(st.sampled_from(_PLAIN_FRAGMENTS + _MARKER_QUOTES), _FREE_TEXT),
            max_size=4,
        )
    )
    return "".join(f"{_neutralise(line)}\n" for line in lines)


# ---------------------------------------------------------------------------
# Nested executions and the projections they support
# ---------------------------------------------------------------------------

_OTHER_CHECK_IDS: Final[tuple[str, ...]] = ("C01", "C28", "C44", "C64", "C72")


@st.composite
def _nested_verdicts(draw: st.DrawFn) -> doc_truth.NestedVerdict:
    """One nested ``verify_claims --json`` payload, parsed, carrying the guard row.

    ``guard_status_nested`` is drawn from the guard's real value and three alternatives, so
    both branches of the compensation sentence are exercised: the self-excluded case (the
    live one) and the case where the nested run reported something else, where the
    generator must say *less* rather than assert a delta it cannot derive (I-7).

    The guard row's position varies, because ``status_of`` walks the list and a consumer
    must not depend on the row arriving first.
    """
    counts = {
        category: draw(st.integers(min_value=0, max_value=9999))
        for category in doc_truth._HEADLINE_CATEGORIES
    }
    nested_status = draw(
        st.sampled_from((readme_gen.GUARD_STATUS_NESTED, "PASS", "FAIL", "PARTIAL"))
    )
    others = tuple(
        doc_truth.NestedCheck(cid=cid, title=f"check {cid}", status="PASS")
        for cid in draw(st.lists(st.sampled_from(_OTHER_CHECK_IDS), max_size=3, unique=True))
    )
    guard = doc_truth.NestedCheck(
        cid=readme_gen.GUARD_CHECK_ID,
        title="README headline counts match the live verify_claims summary",
        status=nested_status,
    )
    at = draw(st.integers(min_value=0, max_value=len(others)))
    return doc_truth.NestedVerdict(counts=counts, checks=others[:at] + (guard,) + others[at:])


@st.composite
def _projections(draw: st.DrawFn) -> readme_gen.HeadlineProjection:
    """A projection, built the only way the module builds one: from a nested execution.

    Deliberately *not* a direct ``HeadlineProjection(...)`` construction. The derived
    ``guard_status_top_level`` rule lives in ``project_payload``, and a generator that
    restated it could keep agreeing with a renderer after the rule changed.
    """
    verdict = draw(_nested_verdicts())
    projection, error = readme_gen.project_payload(verdict)
    assert projection is not None, f"a verdict with counts and a guard row must project: {error}"
    return projection


def _projection(
    *, nested_status: str = readme_gen.GUARD_STATUS_NESTED
) -> readme_gen.HeadlineProjection:
    """One fixed projection, for the clauses that need a literal document."""
    verdict = doc_truth.NestedVerdict(
        counts=dict(zip(doc_truth._HEADLINE_CATEGORIES, (51, 3, 0, 10, 64), strict=True)),
        checks=(
            doc_truth.NestedCheck(
                cid=readme_gen.GUARD_CHECK_ID,
                title="README headline counts",
                status=nested_status,
            ),
        ),
    )
    projection, error = readme_gen.project_payload(verdict)
    assert projection is not None, error
    return projection


@st.composite
def _documents(draw: st.DrawFn) -> str:
    """A README-shaped document with exactly one well-formed marker pair.

    The head and tail may quote the markers mid-line and may carry a lower-ranking
    ``verify-claims`` line; the region body is whatever a previous write or a hand edit
    left behind, and is the only part a write may touch.
    """
    head = draw(_prose_block())
    stale = draw(_prose_block())
    tail = draw(_prose_block())
    return f"{head}{GENERATED_BEGIN}\n{stale}{GENERATED_END}\n{tail}"


def _outside_lines(text: str) -> tuple[str, ...]:
    """Every line outside the one standalone marker pair, as an independent oracle.

    A deliberately separate, line-level model of "outside the region": it does not call
    ``generated_region_bounds``, so a change to the offset arithmetic cannot make the
    byte-preservation clause agree with itself.
    """
    lines = text.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == GENERATED_BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == GENERATED_END]
    assert len(begins) == 1 and len(ends) == 1, (
        f"expected one standalone marker each, found {len(begins)} and {len(ends)}"
    )
    return tuple(lines[: begins[0]]) + tuple(lines[ends[0] + 1 :])


def _standalone(marker: str, text: str) -> int:
    """How many lines contain nothing but ``marker`` - regions, not literals."""
    return sum(1 for line in text.splitlines() if line.strip() == marker)


# ---------------------------------------------------------------------------
# R4.4: the projection is the nested execution's, and nothing is inferred
# ---------------------------------------------------------------------------


# Feature: decision-quality-proof, Property 47: The README region is a projection of the comparing execution  # noqa: E501
@given(verdict=_nested_verdicts())
def test_the_projection_carries_the_nested_counts_and_derives_nothing_it_cannot_see(
    verdict: doc_truth.NestedVerdict,
) -> None:
    """R4.4. The rendered counts are the comparing execution's, category for category.

    And the top-level status is a *derivation with a stated domain*: it is
    ``GUARD_STATUS_TOP_LEVEL`` only when the nested run reported the self-exclusion the
    recursion guard produces, and ``UNKNOWN_STATUS`` otherwise. There is no third branch
    in which a status is guessed, because this execution cannot observe a top-level one.
    """
    projection, error = readme_gen.project_payload(verdict)

    assert projection is not None, error
    assert error == ""
    assert projection.guard_check == readme_gen.GUARD_CHECK_ID
    for category in doc_truth._HEADLINE_CATEGORIES:
        assert projection.counts[category] == verdict.counts[category]
    assert projection.guard_status_nested == verdict.status_of(readme_gen.GUARD_CHECK_ID)

    self_excluded = projection.guard_status_nested == readme_gen.GUARD_STATUS_NESTED
    assert projection.guard_self_excluded is self_excluded
    assert projection.guard_status_top_level == (
        readme_gen.GUARD_STATUS_TOP_LEVEL if self_excluded else readme_gen.UNKNOWN_STATUS
    )


@given(verdict=_nested_verdicts())
def test_a_payload_with_no_guard_row_is_unavailable_naming_the_identifier(
    verdict: doc_truth.NestedVerdict,
) -> None:
    """R4.4. An absent row is reported, never inferred.

    Without the row this module would have to *assume* the nested status of the check that
    both enforces the headline and is counted inside it - which is the second model of the
    recursion guard AD-21 exists to remove. The reason names the identifier so the repair
    is obvious after a renumbering.
    """
    without_guard = doc_truth.NestedVerdict(
        counts=verdict.counts,
        checks=tuple(check for check in verdict.checks if check.cid != readme_gen.GUARD_CHECK_ID),
    )
    assert without_guard.status_of(readme_gen.GUARD_CHECK_ID) is None

    projection, error = readme_gen.project_payload(without_guard)

    assert projection is None, "a payload with no guard row must not project"
    assert readme_gen.GUARD_CHECK_ID in error, error
    # The compensation is what cannot be stated, and the reason says so rather than
    # reporting a generic parse failure.
    assert "R4.8" in error or "compensation" in error, error


@given(verdict=_nested_verdicts(), dropped=st.sampled_from(doc_truth._HEADLINE_CATEGORIES))
def test_a_payload_missing_a_headline_category_is_unavailable_naming_that_category(
    verdict: doc_truth.NestedVerdict,
    dropped: str,
) -> None:
    """R4.4. Four counts out of five is not a headline, and not a partial one either."""
    partial = doc_truth.NestedVerdict(
        counts={
            category: value for category, value in verdict.counts.items() if category != dropped
        },
        checks=verdict.checks,
    )

    projection, error = readme_gen.project_payload(partial)

    assert projection is None
    assert dropped in error, error


# ---------------------------------------------------------------------------
# R4.5: the region is replaced, everything else survives, and it is idempotent
# ---------------------------------------------------------------------------


@given(projection=_projections(), document=_documents())
def test_composing_is_idempotent_and_agrees_with_itself(
    projection: readme_gen.HeadlineProjection,
    document: str,
) -> None:
    """``--check`` is a diff against ``compose``, so non-idempotence would oscillate.

    A generator whose second application differed from its first would make ``--check``
    fail immediately after ``--write`` succeeded, and the repair loop would never
    terminate.
    """
    once = readme_gen.compose(projection, document)
    twice = readme_gen.compose(projection, once)

    assert twice == once, "compose must be idempotent"

    probe = readme_gen.probe_text(projection, once, label="README.md")
    assert probe.status == "ok", probe.detail
    assert probe.passing is True
    assert probe.exit_code == 0
    assert probe.diff == ""


@given(projection=_projections(), document=_documents())
def test_every_byte_outside_the_region_survives_including_prose_quoting_a_marker(
    projection: readme_gen.HeadlineProjection,
    document: str,
) -> None:
    """R4.5. The generator owns the delimited region and nothing else.

    The quoting-prose case is the interesting one: a document that *documents* the marker
    convention contains the marker literals in running text, sometimes *before* the region
    starts. Treating those as a second region - or reaching the region with ``.index`` or
    ``str.replace`` - would let the generator overwrite the explanation of itself.
    """
    composed = readme_gen.compose(projection, document)

    begin, end = generated_region_bounds(document)
    head = document[:begin]
    tail = document[end + len(GENERATED_END) :]

    assert composed.startswith(head), "bytes before the region must be untouched"
    assert composed.endswith(tail), "bytes after the region must be untouched"
    # Independently of the offset arithmetic: the same lines, in the same order, outside.
    assert _outside_lines(composed) == _outside_lines(document)
    assert composed.endswith("\n") == document.endswith("\n")

    # Exactly one region in, exactly one region out - counted as STANDALONE markers, not
    # as occurrences of the literal. The distinction is the whole point of this clause and
    # the first draft of this test got it wrong: a document that quotes a marker inside a
    # sentence contains the literal twice while owning exactly one region, which is
    # precisely what `_standalone_marker_offsets` implements and what the quoting prose
    # above is here to exercise. Counting raw occurrences would have demanded that the
    # generator destroy the documentation of itself.
    assert _standalone(GENERATED_BEGIN, composed) == 1
    assert _standalone(GENERATED_END, composed) == 1
    # The raw literal may legitimately appear more often, and does whenever the document
    # explains the convention.
    assert composed.count(GENERATED_BEGIN) >= 1


def test_a_marker_quoted_before_the_region_is_prose_and_is_not_the_region() -> None:
    """R4.5's sharpest case, stated as one literal document.

    Here the first *textual* occurrence of each marker is inside a sentence that precedes
    the real region. A ``str.replace``-based or ``text.index``-based generator would edit
    that sentence and leave the region alone - producing a document whose explanation of
    the mechanism has been eaten by the mechanism.
    """
    quoting = f"Content between `{GENERATED_BEGIN}` and `{GENERATED_END}` is generated.\n"
    document = f"# SYNAPSE\n\n{quoting}\n{GENERATED_BEGIN}\nstale\n{GENERATED_END}\n\nTrailing.\n"
    projection = _projection()

    begin, _end = generated_region_bounds(document)
    assert document.index(GENERATED_BEGIN) < begin, (
        "this document must quote the marker before the region, or it tests nothing"
    )

    composed = readme_gen.compose(projection, document)

    assert quoting in composed, "the sentence describing the markers must survive verbatim"
    assert composed.startswith(f"# SYNAPSE\n\n{quoting}\n")
    assert composed.endswith("\n\nTrailing.\n")
    assert "stale" not in composed, "the region body is the one part a write replaces"
    assert _standalone(GENERATED_BEGIN, composed) == 1
    assert _standalone(GENERATED_END, composed) == 1


# ---------------------------------------------------------------------------
# R4.11: marker discipline, total over the degenerate cases
# ---------------------------------------------------------------------------


@given(projection=_projections())
def test_unusable_markers_report_unavailable_and_never_a_pass(
    projection: readme_gen.HeadlineProjection,
) -> None:
    """R4.11: zero, duplicated, unbalanced, out-of-order or quoted-only markers.

    All six are ``unavailable`` (exit 2), non-passing, and the document is left
    byte-identical - the generator refuses rather than guessing which pair was meant. Exit
    2 is not a pass: absence of proof never is (I-7).

    The quoted-only case is the one that ties this clause to R4.5: a document that
    *describes* the convention without ever using it holds two marker literals and no
    region at all, and must be reported as having none rather than have one invented from
    the prose.
    """
    broken = {
        "no markers at all": "# SYNAPSE\n\nNo region here.\n",
        "begin only": f"# SYNAPSE\n{GENERATED_BEGIN}\ncontent\n",
        "end only": f"# SYNAPSE\n{GENERATED_END}\ncontent\n",
        "two begins, one end": (f"{GENERATED_BEGIN}\na\n{GENERATED_BEGIN}\nb\n{GENERATED_END}\n"),
        "two ends, one begin": (f"{GENERATED_BEGIN}\na\n{GENERATED_END}\nb\n{GENERATED_END}\n"),
        "out of order": f"{GENERATED_END}\ncontent\n{GENERATED_BEGIN}\n",
        "duplicated pair": (
            f"{GENERATED_BEGIN}\na\n{GENERATED_END}\n{GENERATED_BEGIN}\nb\n{GENERATED_END}\n"
        ),
        "markers only inside prose": (
            f"# SYNAPSE\n\nWrite between `{GENERATED_BEGIN}` and `{GENERATED_END}` only.\n"
        ),
    }
    for description, text in broken.items():
        probe = readme_gen.probe_text(projection, text, label="README.md")

        assert probe.status == "unavailable", f"{description}: {probe.detail}"
        assert probe.passing is False
        assert probe.exit_code == 2
        # And composing raises rather than inventing a region, which is what keeps the
        # document byte-identical on the --write path.
        with pytest.raises(LedgerMarkersError):
            readme_gen.compose(projection, text)


@given(projection=_projections())
def test_a_missing_document_is_unavailable_and_is_never_created(
    projection: readme_gen.HeadlineProjection,
) -> None:
    """The generator owns a region of a document it does not own.

    ``probe_text(..., None)`` is the "unreadable or absent README" case. It must not be a
    pass and must not be a silent creation: a README this tool invented would carry a
    headline nobody wrote and a gate would then pin it.
    """
    probe = readme_gen.probe_text(projection, None, label="README.md")

    assert probe.status == "unavailable"
    assert probe.passing is False
    assert probe.exit_code == 2
    assert "will not create" in probe.detail


@given(projection=_projections(), document=_documents())
def test_drift_is_reported_as_fail_with_a_diff_not_as_unavailable(
    projection: readme_gen.HeadlineProjection,
    document: str,
) -> None:
    """The three states must stay distinct: agreement, drift, and could-not-tell.

    Drift is exit 1 **with a diff**, because the repair is mechanical and the reader needs
    to see what moved. Collapsing drift into ``unavailable`` would lose that, and
    collapsing it into ``ok`` would be the transcription defect all over again.
    """
    composed = readme_gen.compose(projection, document)
    if composed == document:
        return

    probe = readme_gen.probe_text(projection, document, label="README.md")

    assert probe.status == "fail"
    assert probe.passing is False
    assert probe.exit_code == 1
    assert probe.diff, "a drift verdict must carry the unified diff"


# ---------------------------------------------------------------------------
# AD-21's two constraints on the rendered text
# ---------------------------------------------------------------------------


@given(projection=_projections())
def test_the_counts_line_always_names_the_suite_so_c56_can_never_silently_skip(
    projection: readme_gen.HeadlineProjection,
) -> None:
    """Constraint 1. If the phrase were lost, ``_readme_headline_line`` returns ``None``.

    ``doc_truth`` then reports "no verify-claims headline count line found in README.md"
    as a **skip** - and the gate that exists to pin this number would be passing over a
    document it no longer reads. The pattern is imported from ``doc_truth`` rather than
    restated, so the two cannot drift.
    """
    line = readme_gen.counts_line(projection)

    assert doc_truth._VERIFY_CLAIMS_MENTION.search(line) is not None, (
        f"the counts line must name the suite: {line!r}"
    )
    # And every one of the five categories is extractable from it, since a partial line
    # would let C56 compare fewer categories than it reports on.
    for category in doc_truth._HEADLINE_CATEGORIES:
        extracted = doc_truth._extract_count(line, category)
        assert extracted == projection.counts[category], (
            f"{category}: rendered line yields {extracted}, projection holds "
            f"{projection.counts[category]}"
        )


@given(projection=_projections(), document=_documents())
def test_the_counts_line_is_the_unique_richest_headline_candidate(
    projection: readme_gen.HeadlineProjection,
    document: str,
) -> None:
    """Constraint 2, over the document that would actually be written.

    ``_readme_headline_line`` picks the richest candidate and says nothing about ties, so
    uniqueness has to be asserted here. A tie would make which line C56 pins depend on
    document order, which is not a property anyone should rely on.
    """
    composed = readme_gen.compose(projection, document)
    candidates = readme_gen.headline_candidates(composed)

    assert candidates, "the composed document must carry at least one candidate"
    best = max(rank for rank, _line in candidates)
    winners = [line for rank, line in candidates if rank == best]

    assert len(winners) == 1, f"{len(winners)} lines tie as richest candidate: {winners}"
    assert winners[0] == readme_gen.counts_line(projection).strip()
    # And doc_truth's own selector agrees, which is the only opinion that matters.
    assert doc_truth._readme_headline_line(composed) == winners[0]


def test_a_tying_rival_outside_the_region_is_refused_rather_than_resolved() -> None:
    """Uniqueness is refused into, not picked through.

    Five categories is the maximum rank, so nothing can out-rank the counts line - but an
    *equal* candidate elsewhere in the document makes C56's choice depend on line order.
    The generator reports ``unavailable`` naming the ambiguity instead of writing a
    document whose enforced line is decided by position, and the document is left
    untouched (``probe_text`` is pure; the ``--write`` path refuses on the same condition).
    """
    projection = _projection()
    document = f"# SYNAPSE\n\n{_TYING_RIVAL}\n\n{GENERATED_BEGIN}\nstale\n{GENERATED_END}\n"

    # The rival really does tie: same rank as the counts line, different text.
    rival_rank = next(
        rank for rank, line in readme_gen.headline_candidates(document) if line == _TYING_RIVAL
    )
    assert rival_rank == len(doc_truth._HEADLINE_CATEGORIES)
    assert readme_gen.counts_line(projection).strip() != _TYING_RIVAL

    probe = readme_gen.probe_text(projection, document, label="README.md")

    assert probe.status == "unavailable", probe.detail
    assert probe.passing is False
    assert probe.exit_code == 2
    assert "tie" in probe.detail, probe.detail


def test_a_lower_ranking_verify_claims_line_outside_the_region_stays_legitimate() -> None:
    """The converse, so the refusal above is not over-broad.

    Prose recalling one old number is a candidate of rank one. C56 picks the richest, so
    such a line is legitimate and must not make the generator refuse - the constraint is
    uniqueness of the maximum, not absence of rivals.
    """
    projection = _projection()
    document = f"# SYNAPSE\n\n{_QUIET_RIVAL}\n\n{GENERATED_BEGIN}\nstale\n{GENERATED_END}\n"
    composed = readme_gen.compose(projection, document)

    ranked = {line: rank for rank, line in readme_gen.headline_candidates(composed)}
    assert ranked[_QUIET_RIVAL] == 1, "this document must carry a real rival, or it tests nothing"

    probe = readme_gen.probe_text(projection, composed, label="README.md")

    assert probe.status == "ok", probe.detail
    assert doc_truth._readme_headline_line(composed) == readme_gen.counts_line(projection).strip()


@given(projection=_projections())
def test_the_compensation_sentence_yields_no_count_so_it_cannot_outrank_the_measurement(
    projection: readme_gen.HeadlineProjection,
) -> None:
    """R4.8 rendered in words, checked through the extractor rather than by eye.

    The sentence has to explain a one-check asymmetry - "one more PASS and one fewer SKIP"
    - and the moment that becomes "1 more PASS" it starts yielding an extractable count.
    With enough categories mentioned it could tie the real counts line, and C56 would pin
    an explanation instead of a measurement.

    The rule is **adjacency**, not digit-freedom: the sentence names check ``C56`` and so
    does carry digits. That is asserted here on purpose, because "carries no digits" is
    the assertion a reader expects and it is the wrong one - it would pass today and
    forbid a correct sentence tomorrow.
    """
    region = readme_gen.render_region(projection)
    counts = readme_gen.counts_line(projection).strip()
    compensation = readme_gen._compensation_line(projection)

    assert any(character.isdigit() for character in compensation), (
        "the compensation names a check identifier and is not digit-free; the rule under "
        "test is adjacency to a category word"
    )

    for raw in region.splitlines():
        line = raw.strip()
        if line == counts:
            continue
        extracted = [
            category
            for category in doc_truth._HEADLINE_CATEGORIES
            if doc_truth._extract_count(line, category) is not None
        ]
        assert not extracted, (
            f"only the counts line may yield extractable counts; {line!r} yields {extracted}"
        )


@given(projection=_projections(), document=_documents())
def test_the_guard_compensation_never_asserts_a_status_it_cannot_observe(
    projection: readme_gen.HeadlineProjection,
    document: str,
) -> None:
    """AD-21's soundness clause, in the rendered prose.

    This module runs inside a nested execution and cannot observe a top-level one - and the
    write it is about to perform is what would make the comparing check pass. So the
    top-level clause is **conditional** ("whenever that check passes") in the self-excluded
    case, and in every other case the sentence says the usual compensation does not apply
    rather than inventing a delta. Saying less is the requirement; saying more is the
    compensation-from-a-status-about-to-change error AD-21 rejects.
    """
    composed = readme_gen.compose(projection, document)
    compensation = readme_gen._compensation_line(projection)

    assert projection.guard_check in composed
    if projection.guard_self_excluded:
        assert "whenever" in compensation, (
            "the top-level clause must be conditional, not an assertion about a run this "
            "execution cannot see"
        )
        # Conditional *before* the claim, not appended to it as a caveat.
        assert compensation.index("whenever") < compensation.index("one more PASS")
        assert projection.guard_status_top_level == readme_gen.GUARD_STATUS_TOP_LEVEL
    else:
        assert "does not apply" in compensation
        assert "one more PASS" not in compensation, (
            "with no self-exclusion observed there is no compensation to state"
        )
        assert projection.guard_status_top_level == readme_gen.UNKNOWN_STATUS


# ---------------------------------------------------------------------------
# The CLI paths that touch a file. Never the real README, never the suite.
# ---------------------------------------------------------------------------


@pytest.fixture
def forbid_suite_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make invariant I-0 mechanical for the clauses that call the CLI.

    ``doc_truth``'s nested suite-counts helper spawns the whole Check_Registry under a
    900-second bound. Replacing it with a refusal means a clause below that stopped passing
    ``--counts-json`` would fail loudly instead of quietly costing a laptop 15 minutes.
    """

    def _refuse(**_kwargs: object) -> tuple[doc_truth.NestedVerdict | None, str]:
        raise AssertionError(
            "I-0: no test in this file may execute the Check_Registry suite; pass "
            "counts_json= instead"
        )

    monkeypatch.setattr(doc_truth, "nested_suite_counts", _refuse)


def _payload(
    counts: tuple[int, ...] = (51, 3, 0, 10, 64),
    *,
    guard_status: str | None = readme_gen.GUARD_STATUS_NESTED,
) -> str:
    """A nested ``verify_claims --json`` payload, canonically serialised.

    ``guard_status=None`` omits the guard row - the R4.4 case where the identifier the
    compensation needs is absent from an otherwise well-formed payload.
    """
    summary = {
        category.lower(): value
        for category, value in zip(doc_truth._HEADLINE_CATEGORIES, counts, strict=True)
    }
    checks: list[dict[str, str]] = []
    if guard_status is not None:
        checks.append(
            {
                "cid": readme_gen.GUARD_CHECK_ID,
                "title": "README headline counts",
                "status": guard_status,
                "detail": "",
            }
        )
    return json.dumps({"summary": summary, "checks": checks}, sort_keys=True, separators=(",", ":"))


def _counts_json(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "nested-counts.json"
    path.write_text(text, encoding="utf-8")
    return path


def test_counts_json_short_circuits_the_registry_suite(
    tmp_path: Path,
    forbid_suite_execution: None,
) -> None:
    """The exemption every clause in this file relies on, pinned rather than assumed.

    ``--counts-json`` is not a weaker source: the payload IS a nested execution's output,
    emitted by the ``doc_truth`` step that CI runs first. What is asserted here is only
    that reading it does not *also* execute the suite.
    """
    projection, error = readme_gen.project(counts_json=_counts_json(tmp_path, _payload()))

    assert projection is not None, error
    assert projection.headline.startswith("51 PASS")
    assert projection.guard_status_nested == readme_gen.GUARD_STATUS_NESTED


def test_write_never_creates_the_document(
    tmp_path: Path,
    forbid_suite_execution: None,
) -> None:
    """``--write`` owns a region of a document it does not own (R4.11, I-7).

    An absent README stays absent and the run is ``unavailable`` (exit 2). A created README
    would carry a headline nobody wrote, and the next execution would compare against it.
    """
    absent = tmp_path / "README.md"

    exit_code = readme_gen.run(
        write=True,
        counts_json=_counts_json(tmp_path, _payload()),
        path=absent,
    )

    assert exit_code == 2
    assert not absent.exists(), "--write must never create the document"


def test_write_leaves_a_document_with_unusable_markers_byte_identical(
    tmp_path: Path,
    forbid_suite_execution: None,
) -> None:
    """R4.11 on the write path: refuse, and leave the bytes alone."""
    document = tmp_path / "README.md"
    original = "# SYNAPSE\n\nNo generated region here.\n"
    document.write_text(original, encoding="utf-8")
    before = document.read_bytes()

    exit_code = readme_gen.run(
        write=True,
        counts_json=_counts_json(tmp_path, _payload()),
        path=document,
    )

    assert exit_code == 2
    assert document.read_bytes() == before, "the document must be left byte-identical"


def test_write_then_check_agree_and_leave_the_prose_untouched(
    tmp_path: Path,
    forbid_suite_execution: None,
) -> None:
    """The round trip ``truth-gates.yml`` performs, on a copy.

    ``--write`` rewrites the region, ``--check`` then agrees (exit 0), and the prose either
    side - including a sentence quoting both markers before the region - survives verbatim.
    """
    document = tmp_path / "README.md"
    head = f"# SYNAPSE\n\nBetween `{GENERATED_BEGIN}` and `{GENERATED_END}`, do not edit.\n\n"
    tail = "\nDisclosure prose that must survive.\n"
    document.write_text(
        f"{head}{GENERATED_BEGIN}\nplaceholder\n{GENERATED_END}\n{tail}",
        encoding="utf-8",
    )
    counts_json = _counts_json(tmp_path, _payload())

    assert readme_gen.run(write=True, counts_json=counts_json, path=document) == 0

    written = document.read_text(encoding="utf-8")
    assert written.startswith(head)
    assert written.endswith(tail)
    assert "placeholder" not in written
    assert "51 PASS" in written

    assert readme_gen.run(check=True, counts_json=counts_json, path=document) == 0
    assert document.read_text(encoding="utf-8") == written, "--check must not write"


def test_a_payload_with_no_guard_row_exits_two_without_touching_the_document(
    tmp_path: Path,
    forbid_suite_execution: None,
) -> None:
    """R4.4 end to end: no guard row, no verdict, no write.

    The projection failure precedes the document entirely - the region is not rendered
    from a status that was assumed in the absent row's place.
    """
    document = tmp_path / "README.md"
    document.write_text(
        f"# SYNAPSE\n\n{GENERATED_BEGIN}\nplaceholder\n{GENERATED_END}\n",
        encoding="utf-8",
    )
    before = document.read_bytes()

    exit_code = readme_gen.run(
        write=True,
        counts_json=_counts_json(tmp_path, _payload(guard_status=None)),
        path=document,
    )

    assert exit_code == 2
    assert document.read_bytes() == before


def test_an_unparseable_counts_payload_exits_two(
    tmp_path: Path,
    forbid_suite_execution: None,
) -> None:
    """A payload that is not a nested execution is ``unavailable``, not a fallback.

    Falling back to executing the suite would be the honest-looking repair and the wrong
    one: the ordering that makes the payload available is declared in
    ``blocking-steps.yaml``, and a silent 900-second subprocess is what I-0 forbids.
    """
    document = tmp_path / "README.md"
    document.write_text(
        f"# SYNAPSE\n\n{GENERATED_BEGIN}\nplaceholder\n{GENERATED_END}\n",
        encoding="utf-8",
    )

    exit_code = readme_gen.run(
        check=True,
        counts_json=_counts_json(tmp_path, "not a verify_claims payload\n"),
        path=document,
    )

    assert exit_code == 2


def test_the_committed_readme_region_is_what_the_committed_counts_project() -> None:
    """The live check: the committed README agrees with the committed headline numbers.

    Reads one file and calls pure functions - it does **not** execute the suite, so it
    cannot tell whether those numbers are still true of the tree (that is C56's job, in
    CI). What it does prove is that the committed region is byte-identical to what
    ``render_region`` produces for the counts the region itself states, i.e. that the
    document is a projection rather than a transcription.
    """
    committed = readme_gen.DOCUMENT.read_text(encoding="utf-8")
    headline = doc_truth._readme_headline_line(committed)

    assert headline is not None, "the committed README carries no headline candidate"

    stated: dict[str, int] = {}
    for category in doc_truth._HEADLINE_CATEGORIES:
        value = doc_truth._extract_count(headline, category)
        assert value is not None, f"the committed headline states no {category} count"
        stated[category] = value

    projection, error = readme_gen.project_payload(
        doc_truth.NestedVerdict(
            counts=stated,
            checks=(
                doc_truth.NestedCheck(
                    cid=readme_gen.GUARD_CHECK_ID,
                    title="README headline counts",
                    status=readme_gen.GUARD_STATUS_NESTED,
                ),
            ),
        )
    )
    assert projection is not None, error

    probe = readme_gen.probe_text(projection, committed, label="README.md")

    assert probe.status == "ok", (
        "the committed README region is not the projection of its own stated counts; "
        f"{probe.detail}\n{probe.diff}"
    )
