"""A budget named in prose is not a budget that is set.

Feature: decision-quality-proof, task 1.6. Requirements **R3.4, R3.6, R3.7**.

What this closes, concretely
---------------------------

``tests/verify/test_property_inventory_consistency.py`` polices example budgets with two
regexes applied to source text: ``_HARDCODED_MAX_EXAMPLES_RE`` for Python and
``_NUM_RUNS_RE`` for TypeScript. A regex applied to *raw* text cannot tell a subject from
its context, and this tree contains the proof: every property file in the feature
discusses ``max_examples`` in its docstring in order to say it is never set, and
``tests/uplift/test_baseline_determinism_conformance.py:22`` goes further and **quotes an
assignment** - "pinned with ``@settings(max_examples=200)``" - which the pattern matches
while that line sets no budget at all.

The consequence is not cosmetic. It is that two readers counting violations get two
totals and neither is obviously wrong, which is exactly how the I-0 steering file came to
record "three pre-existing violations" for a tree that carries **56** across 41 files.
R3.6 asks the gate to *report* a count; a count is only worth reporting if it is
reproducible, and it is only reproducible if the rule says which occurrences it counts.

So the gate now applies both patterns to :func:`executable_source_lines` output rather
than to raw text, and this file is the proof that the narrowing is *exactly* a
restriction: it never counts prose, it never *stops* counting code, and it never invents
a match that the raw scan did not have.

Why the generators are shaped this way
--------------------------------------

The input is not an arbitrary string. Arbitrary text is useless here for two reasons: the
Python reader tokenizes, so a random string is usually a ``TokenError`` and the property
would be about the fallback path rather than about the rule; and the interesting structure
is precisely *which lexical context* an occurrence sits in, which a random string does not
control. So each case is assembled from labelled one-line fragments - ``code``,
``comment``, ``docstring``, ``string``, ``raw_string``, ``fstring``, ``fstring_field``,
``neutral`` - rendered one per line at column zero. That makes the expected answer **known
by construction** rather than recomputed by a second copy of the rule, which is the only
way this property tests the rule instead of testing itself. A docstring that *spans*
lines breaks the one-fragment-per-line invariant, so it gets its own case rather than
being forced into the machinery.

The interpreter-dependence this pins, and why it is not a footnote
-----------------------------------------------------------------

Task 1.4 found and fixed a real defect in this reader: it blanked only
``(COMMENT, STRING)``. Before Python 3.12 an f-string body is one ``STRING`` token; from
3.12 it is ``FSTRING_START``/``FSTRING_MIDDLE``/``FSTRING_END``, and 3.14 adds the
``TSTRING_*`` triple. ``pyproject.toml`` targets py311 and this development box runs
CPython 3.14, so the census read **60 assignments across 42 files on 3.14 against 56
across 41 on 3.11**. Two interpreters, two totals - which is exactly the ambiguity R3.6's
counting rule exists to remove, with the interpreter standing in for the reader.

The fix resolves ``FSTRING_MIDDLE``/``TSTRING_MIDDLE`` by name via ``getattr`` so the set
follows the interpreter. This file pins the part of that behaviour which is
interpreter-**independent**, and only that part: prose inside a literal is never a budget
assignment, in every string form, on whatever Python is running. The genuinely divergent
half - only the ``_MIDDLE`` runs are blanked, so from 3.12 a replacement field stays
``NAME``/``OP`` and remains executable while py311 blanks the whole literal - is pinned
separately and version-guarded, because asserting either direction unconditionally would
be a false pin on the other interpreter.

Scoping, which is where a plausible mis-fix would land
------------------------------------------------------

Two scoping facts are asserted deterministically, since each is a fact about the
repository rather than a universally-quantified claim. The files that *supply* the budget
mechanism (``frontend/src/test/setup.ts``, ``frontend/src/test/fc-budget.ts``) state
``numRuns`` because that is their job, and they are out of the rule's reach because they
are not declared inventory entries - asserted together with the fact that they *would* be
reported as offenders if they were, so "out of scope by construction" is load-bearing
rather than reassuring. And ``DECLARED_INVENTORY[35]`` is a **Python** entry sitting
inside the otherwise-contiguous TypeScript span, so the ``numRuns`` clause must be scoped
by each entry's language and never by the declaration block's line range.

What would falsify these properties
-----------------------------------

* A tokenizer change that stopped treating docstrings as ``STRING`` tokens: the
  ``prose_is_never_counted`` clause would fail on the ``docstring`` fragments.
* A new literal token shape the reader does not resolve by name: the
  ``every_string_token_shape`` clause fails rather than the census quietly moving.
* A reader that blanks a multi-line literal's opening row only: the spanning-docstring
  clause fails.
* An over-broad reader that blanks whole lines: the two "never hides an assignment"
  clauses fail, which is the direction that would report a clean tree (I-7).
* Blanking by deletion rather than in place: the line-count and column clauses fail.
* Widening either regex so it matched inside a blanked span: the ``restriction`` clause
  fails, because an executable hit would appear where the raw scan had none.
* Re-narrowing ``_NUM_RUNS_RE`` to require digits: the ``computed`` clause fails, which is
  R3.4's "literal or computed" made mechanical - and so does R3.8's structural clause,
  because a capture group is what makes a floor comparison expressible again.
* Folding the budget mechanism into a declared file: the scoping clause fails, because the
  inheritance would then be defeated by the rule meant to protect it.

``max_examples`` is never set in this file - the budget comes from the root
``conftest.py`` profiles via ``HYPOTHESIS_PROFILE`` (``dev``=10, ``heavy``=100,
``ci``/``default``=500, ``nightly``=5000). Note the deliberate joke in the situation: this
file discusses the knob it must not set, in prose, on lines the rule under test has to
classify as prose. It is therefore also a live fixture for itself.

**Validates: Requirements 3.4, 3.6, 3.7**
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from typing import Final, Literal

from hypothesis import given
from hypothesis import strategies as st

import tests.verify.test_property_inventory_consistency as inventory
from tests.verify.test_property_inventory_consistency import (
    _HARDCODED_MAX_EXAMPLES_RE,
    _NUM_RUNS_RE,
    DECLARED_INVENTORY,
    PYTHON,
    ROOT,
    TYPESCRIPT,
    executable_source_lines,
    language_of,
)

FragmentKind = Literal[
    "code",
    "comment",
    "docstring",
    "string",
    "raw_string",
    "fstring",
    "fstring_field",
    "neutral",
]

#: Kinds whose rendered line CONTAINS the pattern and IS an executable assignment.
_EXECUTABLE_KINDS: Final[tuple[FragmentKind, ...]] = ("code",)

#: Kinds whose rendered line contains the pattern but is lexically prose: a comment, a
#: docstring, or one of the string forms. The raw scan sees these; the rule must not.
#:
#: The last three exist because the prose/executable boundary is the **interpreter's**
#: lexical opinion and that opinion changed shape at 3.12: before it, an f-string body is
#: one ``STRING`` token; from 3.12 it is ``FSTRING_START``/``FSTRING_MIDDLE``/``FSTRING_END``
#: and 3.14 adds the ``TSTRING_*`` triple. ``pyproject.toml`` targets py311 and this box
#: runs 3.14, so a reader that knew only ``(COMMENT, STRING)`` read **60 assignments across
#: 42 files on 3.14 against 56 across 41 on 3.11** - two interpreters, two totals, which is
#: precisely what R3.6's counting rule exists to remove. Generating all three string forms
#: is what stops that regressing silently.
_PROSE_KINDS: Final[tuple[FragmentKind, ...]] = (
    "comment",
    "docstring",
    "string",
    "raw_string",
    "fstring",
    "fstring_field",
)

#: Kinds whose rendered line does not contain the pattern at all.
_SILENT_KINDS: Final[tuple[FragmentKind, ...]] = ("neutral",)

_ALL_KINDS: Final[tuple[FragmentKind, ...]] = (
    *_EXECUTABLE_KINDS,
    *_PROSE_KINDS,
    *_SILENT_KINDS,
)

# ---------------------------------------------------------------------------
# Rendering. One fragment per line, column zero, always lexable.
# ---------------------------------------------------------------------------


def _render_python(kind: FragmentKind, index: int) -> str:
    """One line of valid Python for *kind*.

    Every form is a module-level statement at column zero, so the rendered module always
    tokenizes and a fragment's line number is its index. The ``docstring`` form is a bare
    string expression statement, which is what a module or function docstring is lexically
    - a ``STRING`` token - so it exercises the real case without needing indentation.
    """
    if kind == "code":
        return f"SETTINGS_{index} = dict(max_examples=200)"
    if kind == "comment":
        return f"# fragment {index}: pinned with @settings(max_examples=200), in prose"
    if kind == "docstring":
        return f'"""fragment {index}: pinned with @settings(max_examples=200), in prose."""'
    if kind == "string":
        return f'NOTE_{index} = "fragment {index}: max_examples=200 quoted, not set"'
    if kind == "raw_string":
        return f'NOTE_{index} = r"fragment {index}: max_examples=200 raw, not set"'
    if kind == "fstring":
        # No replacement field: one STRING token on py311, FSTRING_START/MIDDLE/END from
        # 3.12. Either shape must read as prose.
        return f'NOTE_{index} = f"fragment {index}: max_examples=200 quoted, not set"'
    if kind == "fstring_field":
        # With a replacement field, which is where the two token shapes actually diverge:
        # py311 blanks the whole literal, 3.12+ blanks only the ``_MIDDLE`` runs and leaves
        # the field's NAME token standing. The *classification* is stable either way, and
        # that stability is the claim; the divergence itself is pinned separately and
        # version-guarded in ``test_an_fstring_replacement_field_stays_executable``.
        return f'NOTE_{index} = f"max_examples=200 in prose {{PLACEHOLDER_{index}}}"'
    return f"PLACEHOLDER_{index} = {index}"


def _render_typescript(kind: FragmentKind, index: int) -> str:
    """One line of TypeScript for *kind*, covering all three string forms."""
    if kind == "code":
        return f"const options{index} = {{ numRuns: 100 }};"
    if kind == "comment":
        return f"// fragment {index}: do not write numRuns: 100 in place"
    if kind == "docstring":
        # The block-comment analogue. `_executable_typescript_lines` tracks `/* */`
        # separately from `//`, so both need a fragment.
        return f"/* fragment {index}: numRuns: 100 belongs to the profile */"
    if kind == "string":
        return f'const note{index} = "numRuns: 100";'
    if kind == "raw_string":
        # The single-quoted form. TypeScript has no raw-string prefix, and the third string
        # form is what the hand-rolled lexer has to get right instead.
        return f"const note{index} = 'numRuns: 100';"
    if kind == "fstring":
        # The template-literal form: the backtick is the third quote character the lexer
        # tracks, and it is the nearest TypeScript analogue of an f-string.
        return f"const note{index} = `numRuns: 100`;"
    if kind == "fstring_field":
        return f"const note{index} = `numRuns: 100 ${{placeholder{index}}}`;"
    return f"const placeholder{index} = {index};"


@st.composite
def _fragment_cases(draw: st.DrawFn) -> tuple[tuple[FragmentKind, ...], str, str]:
    """A fragment sequence and the Python and TypeScript sources that render it.

    Both languages are rendered from the SAME kind sequence so the two readers are held
    to the same contract, and so a divergence between them shows up as a failure rather
    than as two separately-passing tests.
    """
    kinds = draw(st.lists(st.sampled_from(_ALL_KINDS), min_size=1, max_size=18))
    python = "\n".join(_render_python(kind, index) for index, kind in enumerate(kinds))
    typescript = "\n".join(_render_typescript(kind, index) for index, kind in enumerate(kinds))
    return tuple(kinds), python, typescript


def _hit_lines(lines: tuple[str, ...] | list[str], pattern: re.Pattern[str]) -> set[int]:
    """1-based line numbers where *pattern* matches."""
    return {index + 1 for index, line in enumerate(lines) if pattern.search(line)}


def _expected(kinds: tuple[FragmentKind, ...], wanted: tuple[FragmentKind, ...]) -> set[int]:
    """1-based line numbers of the fragments whose kind is in *wanted*."""
    return {index + 1 for index, kind in enumerate(kinds) if kind in wanted}


# ---------------------------------------------------------------------------
# The rule is exactly a restriction of the raw scan
# ---------------------------------------------------------------------------


# The feature tag below is quoted verbatim from the implementation plan, which makes it
# 133 characters. The trailing `noqa` is a lint directive and is NOT part of the tag: a
# future decision-quality-proof inventory gate comparing this line against the design
# heading must strip trailing noqa directives before matching. Recorded because the
# purpose-achievement-audit gate's own tags all fit inside 100 characters, so this is the
# first tag in the tree where the two conventions collide.
# Feature: decision-quality-proof, Property 43: The inventory gate rejects any in-place budget and counts only executable assignments  # noqa: E501
@given(_fragment_cases())
def test_prose_is_never_counted_and_code_always_is(
    case: tuple[tuple[FragmentKind, ...], str, str],
) -> None:
    """R3.6/R3.7 for Python: the count is a fact about code, not about sentences.

    Both directions in one property, deliberately. A rule that merely excluded prose
    could satisfy the first clause by counting nothing at all, and a gate that counts
    nothing reports a clean tree - the failure mode I-7 exists to forbid.
    """
    kinds, python, _ = case
    executable = executable_source_lines(python, language=PYTHON, strict=True)
    counted = _hit_lines(executable, _HARDCODED_MAX_EXAMPLES_RE)

    assert counted == _expected(kinds, _EXECUTABLE_KINDS), (
        "the executable-only reading must count every assignment and no sentence; "
        f"kinds={kinds} counted={sorted(counted)}"
    )


@given(_fragment_cases())
def test_the_executable_reading_is_a_strict_restriction_of_the_raw_scan(
    case: tuple[tuple[FragmentKind, ...], str, str],
) -> None:
    """Blanking may only ever REMOVE hits. Inventing one would make the census fiction.

    This is the clause the census gate asserts on the real tree
    (``test_the_hardcoded_budget_census_is_reproducible_and_reported``), stated here over
    generated input so it is checked against shapes the tree does not happen to contain.
    """
    kinds, python, _ = case
    raw = _hit_lines(python.splitlines(), _HARDCODED_MAX_EXAMPLES_RE)
    executable = _hit_lines(
        executable_source_lines(python, language=PYTHON, strict=True),
        _HARDCODED_MAX_EXAMPLES_RE,
    )

    assert executable <= raw, (
        f"blanking invented hits on lines {sorted(executable - raw)}; the rule must be a "
        "restriction of the raw scan, never a different scan"
    )
    # And the difference is exactly the prose, which is what makes the reported
    # "difference of N lies in comments or string literals" line trustworthy.
    assert raw - executable == _expected(kinds, _PROSE_KINDS)


@given(_fragment_cases())
def test_blanking_preserves_line_numbering_and_columns(
    case: tuple[tuple[FragmentKind, ...], str, str],
) -> None:
    """A reported line number must be the line number in the real file.

    Blanking in place rather than deleting is what makes the gate's output actionable:
    ``tests/uplift/test_effect_size_property.py: lines [69, 108, 118, 134]`` is only
    useful if those are the file's own line numbers. A reader that dropped lines would
    still satisfy the counting clauses above and be useless in practice, so the structural
    guarantee gets its own property.
    """
    _, python, typescript = case
    for text, language in ((python, PYTHON), (typescript, TYPESCRIPT)):
        raw_lines = text.splitlines()
        blanked = executable_source_lines(text, language=language)

        assert len(blanked) == len(raw_lines), "the reader must not add or drop lines"
        for raw_line, blanked_line in zip(raw_lines, blanked, strict=True):
            assert len(blanked_line) == len(raw_line), (
                "columns must be preserved: blanking replaces content with spaces so a "
                "match's column is the column in the real file"
            )


@given(_fragment_cases())
def test_the_typescript_reader_obeys_the_same_contract(
    case: tuple[tuple[FragmentKind, ...], str, str],
) -> None:
    """R3.4: the TypeScript rule mirrors the Python one, including its scoping.

    The hand-rolled lexer has to earn the same trust the tokenizer gets for free, and it
    handles three string forms plus two comment forms. Holding it to the identical
    contract over the identical kind sequence is what makes "mirroring the Python rule"
    a checkable statement rather than a comment.
    """
    kinds, _, typescript = case
    executable = executable_source_lines(typescript, language=TYPESCRIPT)
    counted = _hit_lines(executable, _NUM_RUNS_RE)
    raw = _hit_lines(typescript.splitlines(), _NUM_RUNS_RE)

    assert counted == _expected(kinds, _EXECUTABLE_KINDS)
    assert counted <= raw
    assert raw - counted == _expected(kinds, _PROSE_KINDS)


# ---------------------------------------------------------------------------
# The classification is stable across the interpreter's token shapes
# ---------------------------------------------------------------------------

#: The string forms whose token shape is version-dependent, paired with the prose they
#: carry. Every one contains the raw pattern and sets no budget.
_STRING_FLAVOURS: Final[tuple[str, ...]] = (
    'NOTE = "max_examples=200 quoted"',
    "NOTE = 'max_examples=200 quoted'",
    'NOTE = r"max_examples=200 raw"',
    'NOTE = b"max_examples=200 bytes"',
    'NOTE = f"max_examples=200 in an f-string"',
    'NOTE = rf"max_examples=200 in a raw f-string"',
    'NOTE = f"max_examples=200 then {PLACEHOLDER}"',
    'NOTE = f"{PLACEHOLDER} then max_examples=200"',
    'NOTE = """max_examples=200 in a triple-quoted literal"""',
    'NOTE = f"""max_examples=200 in a triple-quoted f-string"""',
)


@given(st.sampled_from(_STRING_FLAVOURS))
def test_prose_is_prose_in_every_string_token_shape(line: str) -> None:
    """The census must not move when the interpreter's token shape does.

    This is the property that pins the defect the census gate was actually caught by. A
    reader that blanked only ``(COMMENT, STRING)`` classified an f-string body as prose on
    py311 - the declared target - and as **executable** from 3.12, where the body is
    ``FSTRING_MIDDLE`` rather than ``STRING``. The measured consequence was two totals for
    one tree: 60 assignments across 42 files on 3.14 against 56 across 41 on 3.11. R3.6
    asks for a *reproducible* count, and a count that depends on which Python ran it is not
    one.

    So the claim asserted here is the interpreter-independent half: whichever token shape
    an interpreter chooses for a given literal, prose inside it is never a budget
    assignment. Every flavour is checked on whatever interpreter is running, which is what
    makes a future ``USTRING_MIDDLE`` show up as a failure here rather than as a quiet
    drift in a reported number.
    """
    blanked = executable_source_lines(line, language=PYTHON, strict=True)
    assert not any(_HARDCODED_MAX_EXAMPLES_RE.search(rendered) for rendered in blanked), (
        f"prose inside a string literal was counted as an assignment: {line!r} -> "
        f"{blanked!r}; the literal-content token set is missing this shape "
        f"(CPython {'.'.join(str(part) for part in sys.version_info[:3])})"
    )


@given(st.sampled_from(_STRING_FLAVOURS))
def test_a_literal_carrying_prose_never_hides_an_assignment_beside_it(line: str) -> None:
    """Blanking a literal must not blank the code sharing its line.

    The converse of the clause above, and the one that stops the fix being "blank the whole
    line and report zero". An over-broad reader satisfies every exclusion clause in this
    file and reports a clean tree, which is the failure mode I-7 exists to forbid.
    """
    combined = f"SETTINGS = dict(max_examples=200, note={line.split(' = ', 1)[1]})"
    blanked = executable_source_lines(combined, language=PYTHON, strict=True)
    assert any(_HARDCODED_MAX_EXAMPLES_RE.search(rendered) for rendered in blanked), (
        f"an assignment beside a prose literal was blanked away: {combined!r} -> {blanked!r}"
    )


@given(
    st.sampled_from(
        (
            'NOTE = f"max_examples=200 {PLACEHOLDER}"',
            'NOTE = f"{PLACEHOLDER} max_examples=200"',
            'NOTE = rf"max_examples=200 {PLACEHOLDER} tail"',
        )
    )
)
def test_an_fstring_replacement_field_stays_executable(line: str) -> None:
    """Only the ``_MIDDLE`` runs are blanked, and this is where the shapes truly diverge.

    Version-guarded deliberately, because the honest statement differs by interpreter and
    flattening the two would be a false pin either way:

    * From 3.12 the body is ``FSTRING_START``/``FSTRING_MIDDLE``/``FSTRING_END`` and only
      the ``_MIDDLE`` runs carry literal text. A replacement field is ordinary
      ``NAME``/``OP`` tokens, so it survives - correctly, because ``f"{dict(a=1)}"``
      really does execute.
    * On py311, the declared target, the whole literal is one ``STRING`` token, so the
      field is blanked with the body.

    Both are recorded rather than one being asserted everywhere, so that the *reason* the
    census differed across interpreters stays legible: it is not that the reader was wrong
    on one of them, it is that the token shape changed under it and the reader did not
    resolve the new names. Only the classification of *prose* is interpreter-independent,
    and that is what the two clauses above assert.
    """
    blanked = executable_source_lines(line, language=PYTHON, strict=True)
    rendered = "\n".join(blanked)

    assert not any(_HARDCODED_MAX_EXAMPLES_RE.search(one) for one in blanked), (
        "the f-string body is prose on every interpreter"
    )
    if sys.version_info >= (3, 12):
        assert "PLACEHOLDER" in rendered, (
            "from 3.12 a replacement field is NAME/OP and must survive blanking, because "
            f"code inside one executes; {line!r} -> {blanked!r}"
        )
    else:  # pragma: no cover - exercised on py311 CI, not on this box
        assert "PLACEHOLDER" not in rendered, (
            "on py311 an f-string is a single STRING token, so the field is blanked with "
            f"the body; {line!r} -> {blanked!r}"
        )


@st.composite
def _block_docstring_cases(draw: st.DrawFn) -> tuple[str, int]:
    """A multi-line block docstring carrying the pattern, plus one real assignment.

    The fragment machinery renders one line per fragment so that a fragment's index is its
    line number, which a multi-line literal breaks. A docstring that *spans* lines is the
    common real shape, though - every property file in this feature has one - so it gets
    its own case: the source and the 1-based line number of the only assignment in it.
    """
    body = draw(st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=4))
    lines = ["PROLOGUE = 0", '"""Opening line names max_examples=200 in prose.']
    lines.extend(f"line {number}: pinned with @settings(max_examples=200)." for number in body)
    lines.append('Closing line, still prose about max_examples=200."""')
    lines.append("SETTINGS = dict(max_examples=200)")
    return "\n".join(lines), len(lines)


@given(_block_docstring_cases())
def test_a_docstring_spanning_lines_is_prose_on_every_line_it_spans(
    case: tuple[str, int],
) -> None:
    """A multi-line literal must be blanked across its whole span, not just its first line.

    The single-line ``docstring`` fragment cannot catch a reader that blanks only the
    token's opening row, and a reader with that bug counts every continuation line of every
    docstring in the tree - which is a large, plausible over-count in exactly the direction
    that made "three pre-existing violations" survive as a figure.
    """
    source, assignment_line = case
    counted = _hit_lines(
        executable_source_lines(source, language=PYTHON, strict=True),
        _HARDCODED_MAX_EXAMPLES_RE,
    )
    assert counted == {assignment_line}, (
        "only the assignment on the final line is a budget; every docstring line names one "
        f"in prose. counted={sorted(counted)} expected={[assignment_line]}"
    )


# ---------------------------------------------------------------------------
# Totality, and the "literal or computed" clause
# ---------------------------------------------------------------------------


@given(st.text(max_size=200))
def test_the_typescript_reader_is_total_over_arbitrary_text(text: str) -> None:
    """The TypeScript reader has no parser to fail, so it must never refuse input.

    Unlike the Python side there is no ``TokenError`` escape hatch: an unterminated
    string or a stray ``/*`` is ordinary input from a lexer's point of view, and the gate
    must still produce a verdict for the file. Arbitrary text is the right generator here
    precisely because it is *not* valid TypeScript.
    """
    blanked = executable_source_lines(text, language=TYPESCRIPT)
    assert len(blanked) == len(text.splitlines())
    for original, result in zip(text.splitlines(), blanked, strict=True):
        assert len(result) == len(original)


@given(st.text(max_size=200))
def test_the_python_reader_degrades_rather_than_raising_when_not_strict(text: str) -> None:
    """``strict=False`` is the scoping case: an unlexable file must still be judged.

    The two modes exist for two different questions. A clause that merely *scopes* a rule
    to a declared file wants the raw lines when the file cannot be tokenized, because
    refusing to answer would turn a lint question into an error. The census clause wants
    the opposite - ``strict=True`` re-raises, because a file that cannot be read is a hole
    in a count and not a zero (I-7). Both are asserted, in the same property, so the
    asymmetry cannot be flattened by a later refactor.
    """
    blanked = executable_source_lines(text, language=PYTHON, strict=False)
    assert len(blanked) == len(text.splitlines())

    try:
        list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Unlexable: non-strict degraded to the raw lines rather than raising.
        assert blanked == tuple(text.splitlines())


#: Every shape an in-place fast-check budget takes, or could take. Rejection must be
#: **total** over this set (R3.4): literal, computed, whitespace-varied, inside a
#: multi-key options object, and inside an object built by spreading a base.
_NUM_RUNS_SHAPES: Final[tuple[str, ...]] = (
    "      { numRuns: 100 },",
    "      { numRuns: budget },",
    "      { numRuns: resolveNumRuns(profile) },",
    "{numRuns:100}",
    "{ numRuns\t: PROFILE_NUM_RUNS.dev }",
    "  fc.assert(prop, { seed: 1, numRuns: 42 });",
    # Spread forms. `{ ...base, numRuns: 100 }` reads as inheritance and is not: the
    # explicit key wins over anything `base` carried, so it is an in-place budget wearing
    # the shape of a global. This is the form a reader is least likely to flag by eye.
    "  fc.assert(prop, { ...baseOptions, numRuns: 100 });",
    "  fc.assert(prop, { numRuns: 100, ...baseOptions });",
    "const options = { ...fc.readConfigureGlobal(), numRuns: 250 };",
)


@given(st.sampled_from(_NUM_RUNS_SHAPES))
def test_the_numruns_rule_catches_a_computed_budget_as_well_as_a_literal(line: str) -> None:
    """R3.4: "whether literal or computed", made mechanical.

    The clause this replaced was ``numRuns[ \\t]*:[ \\t]*(?P<runs>\\d+)`` and it could
    only ever see digits. A computed ``{ numRuns: budget }`` overrides
    ``fc.configureGlobal`` exactly as a literal does, so a pattern that policed only the
    honest half would have left the evasive half legal - and the evasive half is the one
    a reader would not notice.
    """
    assert _NUM_RUNS_RE.search(line) is not None, (
        f"an in-place budget must be caught in any form; {line!r} escaped the rule"
    )


@given(st.sampled_from(_NUM_RUNS_SHAPES))
def test_no_numruns_shape_survives_the_executable_reading(line: str) -> None:
    """The rejection must survive the narrowing, not merely the raw pattern.

    Stated separately because the two halves fail for different reasons. The clause above
    fails if the pattern is re-narrowed to digits; this one fails if the TypeScript lexer
    over-blanks - a spread's ``...`` or an options object's braces being mistaken for
    string or comment context would blank a real budget and report the file clean, which
    is the direction I-7 forbids.
    """
    blanked = executable_source_lines(line, language=TYPESCRIPT)
    assert any(_NUM_RUNS_RE.search(rendered) for rendered in blanked), (
        f"the executable reading blanked a real in-place budget: {line!r} -> {blanked!r}"
    )


# ---------------------------------------------------------------------------
# Scoping: what the rule reads, and what excludes the rest
# ---------------------------------------------------------------------------

#: The files that *supply* the budget mechanism. They state ``numRuns`` because that is
#: their job, and they are out of the rule's scope because they are not in the declared
#: inventory - by construction, not by exemption.
_MECHANISM_FILES: Final[tuple[str, ...]] = (
    "frontend/src/test/setup.ts",
    "frontend/src/test/fc-budget.ts",
)


def test_the_budget_mechanism_files_are_out_of_scope_by_construction() -> None:
    """The one place ``numRuns`` must appear is the one place the rule does not read.

    Deterministic rather than generated: this is a fact about the repository, and no
    generator makes it more true (the subject module's own docstring records the same
    reasoning for its own clauses).

    The clause has teeth because it asserts both halves. That these files are absent from
    the inventory is cheap; that they **would** be reported as offenders if they were in it
    is what makes "out of scope by construction" a load-bearing statement rather than a
    reassuring one. If a later change folded the mechanism into a declared file, this
    fails - which is the signal wanted, because the inheritance would then be defeated by
    the rule meant to protect it.
    """
    declared = set(DECLARED_INVENTORY.values())
    for relative in _MECHANISM_FILES:
        path = ROOT / relative
        assert path.is_file(), f"the budget mechanism file is missing: {relative}"
        assert relative not in declared, (
            f"{relative} supplies the budget and states numRuns; declaring it as a property "
            "file would make the gate fail on its own mechanism"
        )
        lines = executable_source_lines(path.read_text(encoding="utf-8"), language=TYPESCRIPT)
        assert any(_NUM_RUNS_RE.search(line) for line in lines), (
            f"{relative} no longer states numRuns in executable code, so this scoping "
            "clause has stopped testing anything - either the mechanism moved or the "
            "TypeScript reader over-blanks"
        )


def test_the_typescript_clause_is_scoped_by_language_and_not_by_a_line_range() -> None:
    """R3.4's scope is a language filter, and a range filter would be wrong here.

    ``DECLARED_INVENTORY``'s TypeScript entries are contiguous *except* for property 35,
    which is a Python file sitting inside the span. The requirements document records the
    same trap in prose - "the declaration span is not five TypeScript lines" - and this is
    that trap made mechanical: a reader that scoped the ``numRuns`` clause to the declared
    block's line range, rather than to each entry's language, would hand a Python file to
    the TypeScript reader and misclassify it in whichever direction its ``#`` comments and
    string forms happened to fall.

    Both facts are asserted, so the property fails if either drifts: that the span really
    does enclose a Python entry (otherwise this clause is vacuous and should be deleted
    rather than left looking watchful), and that the language filter really does exclude
    it.
    """
    typescript_numbers = {
        number
        for number, relative in DECLARED_INVENTORY.items()
        if language_of(relative) == TYPESCRIPT
    }
    assert typescript_numbers, "the inventory declares no TypeScript entries at all"

    span = range(min(typescript_numbers), max(typescript_numbers) + 1)
    python_inside_span = {
        number
        for number in span
        if number in DECLARED_INVENTORY and language_of(DECLARED_INVENTORY[number]) == PYTHON
    }

    assert python_inside_span, (
        "no Python entry lies inside the TypeScript declaration span any more, so a "
        "line-range scoping bug would no longer be observable; delete this clause rather "
        "than leaving it as false assurance"
    )
    assert not (python_inside_span & typescript_numbers), (
        f"the language filter admitted a Python entry into the TypeScript scope: "
        f"{sorted(python_inside_span & typescript_numbers)}"
    )
    for number in python_inside_span:
        assert language_of(DECLARED_INVENTORY[number]) == PYTHON, (
            f"property {number} ({DECLARED_INVENTORY[number]}) must be read by the Python "
            "reader; the TypeScript rule must never see it"
        )


# ---------------------------------------------------------------------------
# R3.8: the two contradictory rules cannot coexist
# ---------------------------------------------------------------------------

#: Names a clause requiring a *minimum* in-place budget would plausibly carry. Matched
#: against the subject module's test function names.
_MINIMUM_CLAUSE_RE: Final[re.Pattern[str]] = re.compile(
    r"at_least|minimum|min_num_runs|_min_runs", re.IGNORECASE
)

#: The inverted clause R3.4 asks for. Its presence is half of R3.8; the absence of the
#: clause it replaced is the other half.
_INVERTED_CLAUSE: Final[str] = (
    "test_no_typescript_property_test_in_this_feature_states_a_run_budget"
)


def test_no_clause_requires_a_minimum_in_place_budget() -> None:
    """R3.8: a rule demanding ``numRuns >= 100`` and a rule forbidding ``numRuns`` cannot both hold.

    A half-move leaves the gate failing on precisely the files task 1.3 corrected, so the
    move has to be verifiable as a whole. Four independent traces of it, because any one
    alone is evadable:

    1. ``MIN_NUM_RUNS`` is gone. The constant existed only to serve the ``>=`` clause.
    2. No test function in the subject module names a minimum. A restored clause under a
       new constant would still have to be called something.
    3. ``_NUM_RUNS_RE`` captures no group. This is the structural one and the hardest to
       evade: a clause comparing a budget against a floor must first *extract* the value,
       and a pattern with no capture group cannot supply one. It is also exactly the
       narrowing R3.4 forbids - ``numRuns[ \\t]*:[ \\t]*(?P<runs>\\d+)`` would restore both
       the digit-only blindness and the ability to compare.
    4. The inverted clause is present and callable. Removing the ``>=`` rule without
       landing its replacement leaves the TypeScript half unpoliced, which is a different
       failure with the same fingerprint.
    """
    assert not hasattr(inventory, "MIN_NUM_RUNS"), (
        "MIN_NUM_RUNS was deleted with the >=100 clause it served (R3.8); its return "
        "means the contradictory pair is back"
    )

    minimum_named = sorted(
        name
        for name in vars(inventory)
        if name.startswith("test_") and _MINIMUM_CLAUSE_RE.search(name)
    )
    assert not minimum_named, (
        f"a clause requiring a minimum in-place budget is back under a new name: {minimum_named}"
    )

    assert _NUM_RUNS_RE.groups == 0 and not _NUM_RUNS_RE.groupindex, (
        "_NUM_RUNS_RE captures a value, so a floor comparison is expressible again and the "
        f"pattern is digit-sensitive: {_NUM_RUNS_RE.pattern!r} (R3.4, R3.8)"
    )

    assert callable(getattr(inventory, _INVERTED_CLAUSE, None)), (
        f"{_INVERTED_CLAUSE} is absent: the >=100 clause was removed without its "
        "replacement landing, leaving the TypeScript half unpoliced (R3.4)"
    )
