"""The feature's declared property inventory is real (design R1.2, task 12.3).

Feature: purpose-achievement-audit, task 12.3.

The design says "**Exactly one property-based test per property** above, 37 in total",
that every one of them "carries the tag comment
``Feature: purpose-achievement-audit, Property {N}: {property text}``", and that
``max_examples`` is "**never** hardcoded". Until now those were three sentences in a
document. This file makes them mechanical, which is R1.2's actual point: a documented
design-to-test correspondence that nothing checks is a correspondence that drifts.

Why a deterministic test and not a property test
------------------------------------------------

The claim is "this declared inventory matches this filesystem and that design
document". That is a *fact about the repository*, not a universally-quantified
statement over generated inputs - there is exactly one repository to check and no
generator would make the answer more true. Driving it through 500 generated examples
would burn a Hypothesis budget to re-read the same 37 files, which is the anti-pattern
I-0 forbids. So: plain asserts, no ``@given``, no ``@settings``, and consequently no
``max_examples`` to hardcode. A check that forbids a hardcoded budget while hardcoding
its own would be exactly the defect this feature exists to catch.

A declared mapping, not a bare count
------------------------------------

``DECLARED_INVENTORY`` maps each design property number to the one file that carries
it. ``assert len(files) == 37`` fails with an arithmetic complaint; this fails with the
name of the property that went missing and the path that was supposed to hold it. It
also makes the design-to-test correspondence readable in one place, which is the thing
R1.2 asks for. The count is *derived* from that mapping and cross-checked against the
``### Property {N}:`` headings in the design document - no expected-count literal appears
in any assertion below, so the design and the inventory have to agree with each other
rather than both agreeing with a number somebody typed.

The tag convention this file enforces
-------------------------------------

The tag is a **whole-line comment** - ``#`` in Python, ``//`` in TypeScript - whose
text begins ``Feature: purpose-achievement-audit, Property {N}: {design title}``. Three
real complications shape the matcher:

1. **The tag is not reliably one line.** ``test_module_liveness_classification_property``
   wraps Property 27's tag across two ``#`` lines, ``test_oracle_membership_property``
   wraps Property 37's, and several others wrap too, because ruff's
   ``line-length = 100`` does not fit every title. A single-line regex under-counts, so
   ``tag_blocks`` joins a tag line with the comment lines immediately following it and
   collapses whitespace before comparing. Property 29's tag is 122 characters and its
   file carries a documented file-level ``# ruff: noqa: E501`` instead of wrapping; the
   same matcher accepts both shapes, so neither file has to be rewritten to satisfy this
   check.
2. **The comparison is a prefix, not an equality.** A tag may be followed by unrelated
   commentary (``# max_examples is deliberately NOT hardcoded ...``) and a tag line may be
   preceded by section rules (``# ---------``). Anchoring on the tag line and requiring
   the joined block to *start with* the expected text tolerates both without accepting a
   wrong title.
3. **The design marks six titles ``(slow)``; the tags do not repeat it.** Properties 15,
   16, 22, 26, 29 and 30 carry ``(slow)`` in their design heading and not in their tag.
   That is the established convention, so the marker is stripped from the design title
   before comparison rather than demanded of the tags.

A trailing comment on a code line is deliberately **not** accepted: the tag sits on its
own line, immediately above the decorated test, in all 37 files today.

Five of the inventory are TypeScript
------------------------------------

Properties 31, 32, 33, 34 and 36 are fast-check tests under ``frontend/``, tagged with
``//`` and containing no ``max_examples`` at all. A matcher globbing only
``tests/**/*.py`` would find none of them and would report the inventory as 32 files
while calling itself complete. The language is derived from each declared path's suffix
so both halves are covered, and the clauses that are language-specific say so out loud.

How the ``max_examples`` clause is scoped, and why
--------------------------------------------------

**It applies to this feature's declared Python files only.** Hardcoded budgets exist
elsewhere in the tree and are not this feature's debt:
``tests/uplift/test_headline_artifact_roundtrip_property.py`` (200, twice),
``tests/uplift/test_arm_aggregate_property.py`` (200 and 50),
``tests/verify/test_published_checkpoint_gate_property.py`` (250),
``tests/verify/test_headline_count_pin_property.py``,
``tests/verify/test_headline_pin_skip_property.py`` and
``tests/verify/test_verify_claims_status_partition_property.py`` (200 each) - and roughly
fifty more values across ``tests/uplift``. A check born red for another feature's debt
gets disabled, and a disabled check is worse than no check, so the scope is the declared
inventory and nothing else. The scope is stated here rather than hidden in a glob: a
reader can see what is covered without reverse-engineering a pattern. Widening it is a
deliberate decision with a repair cost attached, not an accident of matching.

The TypeScript half now inherits too, and the clause is inverted (R3.4, R3.8)
--------------------------------------------------------------------------

This file used to require every declared ``numRuns`` to be **at least 100**, and that was
the right rule for the world it was written in: fast-check's equivalent of
``max_examples`` is ``numRuns``, fast-check had no profile mechanism in this repository to
inherit it from, so all five files stated ``{ numRuns: 100 }`` in place and requiring it
was the honest analogue of the Python profile rather than a silent exemption (I-7).

``frontend/src/test/fc-budget.ts`` supplies the missing mechanism and
``frontend/src/test/setup.ts`` applies it through ``fc.configureGlobal``, resolved from the
same ``HYPOTHESIS_PROFILE`` variable ``conftest.py`` reads. That inverts the rule: a
per-call ``numRuns`` **overrides** the global, so an in-place budget now defeats the
inheritance it used to stand in for, and pins the local cost to the CI cost -- the thing
I-0 forbids. The clause below therefore fails on **any** declared ``numRuns``, literal or
computed, exactly mirroring the Python ``max_examples`` rule. Per R3.8 the two clauses may
never coexist: one requires what the other forbids.

One asymmetry is deliberate and is not a bug. Python resolves an unset profile to
``default`` (500); the fast-check resolver resolves it to ``dev`` (10). An unset variable
is the local case, and under I-0 the local case must be the cheap one. CI sets it
explicitly, which is what keeps R3.5's >=100 effective count true where it matters.

The census clause, and why it asserts no total
----------------------------------------------

``test_the_hardcoded_budget_census_is_reproducible_and_reported`` counts ``max_examples``
assignments under ``tests/uplift/`` and ``tests/verify/`` and **reports** them (R3.6,
R3.7). It pins no total, because the "three pre-existing violations" figure in the I-0
steering file is carried by A-2 as *unverified*, and a gate asserting a number nobody
re-derived would launder an assumption into a fact. What it does assert is that the count
is reproducible: every file in scope parses, and the executable-only reading is a strict
restriction of the raw pattern scan. That matters because the raw pattern matches a
*sentence* in ``tests/uplift/test_baseline_determinism_conformance.py:22``, so two readers
counting by hand get two totals and neither is obviously wrong. The reading is normalised
across interpreters for the same reason: an f-string body is one ``STRING`` token on py311
(the declared target) and an ``FSTRING_MIDDLE`` token from 3.12, so a reader that only knew
``(COMMENT, STRING)`` would count prose inside an f-string as an assignment on one
interpreter and as prose on the other. Same defect, interpreter in place of the reader.

What "exactly 37" means here
----------------------------

Three clauses together: the design headings and the inventory keys are the same set,
each inventory path is distinct, and no file under the first-party search roots carries
a tag for this feature that the inventory does not declare. The last one is what stops
the inventory from silently going stale in the *additive* direction. Its scope is
``SEARCH_ROOTS`` - the first-party source and test trees - which provably contains every
declared path (asserted below). A tagged file outside those roots would escape it; that
is a stated limit, not an implied guarantee.

I-0: this test reads Markdown and source text. It starts no browser, spawns no
subprocess, drives no twin and runs no suite, so it is deliberately **not**
``slow``-marked and runs in ``ci.yml::uplift-verify`` alongside the property suites.
Every read is ``encoding='utf-8'`` (E-S13-07) and every assertion message is ASCII.

**Validates: Requirements 1.2**
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator

# ---------------------------------------------------------------------------
# Where the feature's documents live
# ---------------------------------------------------------------------------

ROOT: Final = Path(__file__).resolve().parents[2]

FEATURE: Final[str] = "purpose-achievement-audit"

#: The spec root agrees with ``infrastructure/quality/checkpoint-truth.yaml``'s
#: ``task_claims.specs_dir``, which is the path ``scripts.audit.task_claim_truth``
#: already reads spec documents from - so this is a committed, gate-read location, not a
#: convenience path invented here.
DESIGN_DOC: Final = ROOT / ".kiro" / "specs" / FEATURE / "design.md"

# ---------------------------------------------------------------------------
# The declared inventory: design property number -> the one file that carries it
# ---------------------------------------------------------------------------

DECLARED_INVENTORY: Final[dict[int, str]] = {
    1: "tests/verify/test_registry_gate_verdict_property.py",
    2: "tests/verify/test_doc_truth_claim_masking_property.py",
    3: "tests/verify/test_declared_falsification_property.py",
    4: "tests/verify/test_workflow_shape_propagation_property.py",
    5: "tests/verify/test_doc_truth_numeric_pin_property.py",
    6: "tests/verify/test_ratchet_monotonicity_property.py",
    7: "tests/verify/test_coverage_floor_nonvacuity_property.py",
    8: "tests/verify/test_replay_metric_threshold_property.py",
    9: "tests/verify/test_ledger_gen_property.py",
    10: "tests/verify/test_verify_claims_check_identity_property.py",
    11: "tests/verify/test_gate_surface_property.py",
    12: "tests/verify/test_required_checks_resolution_property.py",
    13: "tests/uplift/test_uplift_admissibility_property.py",
    14: "tests/uplift/test_uplift_artifact_canonical_roundtrip_property.py",
    15: "tests/uplift/test_uplift_harness_cross_process_determinism_property.py",
    16: "tests/uplift/test_uplift_null_arm_property.py",
    17: "tests/verify/test_checkpoint_claim_classification_property.py",
    18: "packages/tests/test_chain_walk_perturbation_property.py",
    19: "packages/tests/test_anchor_commitment_property.py",
    20: "tests/verify/test_command_path_resolution_property.py",
    21: "packages/tests/test_canonical_row_append_only_property.py",
    22: "orchestrator/tests/consensus/test_confidence_gate_universality_property.py",
    23: "orchestrator/tests/test_guardrail_totality_property.py",
    24: "orchestrator/tests/test_threshold_reload_property.py",
    25: "orchestrator/tests/test_timeout_record_property.py",
    26: "orchestrator/tests/consensus/test_selection_and_twin_consequence_property.py",
    27: "tests/verify/test_module_liveness_classification_property.py",
    28: "tests/verify/test_world_provenance_derivation_property.py",
    29: "tests/verify/test_nonsynthetic_ingestion_replay_property.py",
    30: "tests/verify/test_actuation_classification_property.py",
    31: "frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts",
    32: "frontend/spec/effectiveness/__tests__/scorecard-completeness.property.test.ts",
    33: "frontend/spec/effectiveness/__tests__/ratchet-sensitivity.property.test.ts",
    34: (
        "frontend/spec/effectiveness/__tests__/"
        "interruption-precision-responsiveness.property.test.ts"
    ),
    35: "tests/verify/test_fe_invariant_attestation_property.py",
    36: "frontend/spec/effectiveness/__tests__/baseline-measurement.property.test.ts",
    37: "tests/verify/test_oracle_membership_property.py",
}

# ---------------------------------------------------------------------------
# Language facts, derived from the declared path so nothing is declared twice
# ---------------------------------------------------------------------------

PYTHON: Final[str] = "python"
TYPESCRIPT: Final[str] = "typescript"

#: Suffix -> language. Also the set of suffixes the undeclared-tag scan reads.
_LANGUAGES: Final[dict[str, str]] = {
    ".py": PYTHON,
    ".ts": TYPESCRIPT,
    ".tsx": TYPESCRIPT,
}

#: The whole-line comment marker the tag takes in each language.
_COMMENT_MARKERS: Final[dict[str, str]] = {PYTHON: "#", TYPESCRIPT: "//"}

#: The construct that makes a file a property test in each language. A tagged file that
#: generates nothing is a tag, not a property.
_RUNNER_TOKENS: Final[dict[str, str]] = {PYTHON: "@given(", TYPESCRIPT: "fc.assert("}

# ---------------------------------------------------------------------------
# Matchers
# ---------------------------------------------------------------------------

#: Composed from ``FEATURE`` so the feature name is written once, and so no comment line
#: in this file is itself a tag the scan below would have to special-case.
TAG_PREFIX: Final[str] = f"Feature: {FEATURE}, Property "

_TAG_NUMBER_RE: Final[re.Pattern[str]] = re.compile(rf"^{re.escape(TAG_PREFIX)}(?P<number>\d+):")

_DESIGN_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^###[ \t]+Property[ \t]+(?P<number>\d+):[ \t]+(?P<title>\S.*?)[ \t]*$"
)

#: Six design headings carry this; no tag repeats it. Stripped before comparison.
_SLOW_SUFFIX: Final[str] = " (slow)"

#: An *assignment* of a Hypothesis budget. Deliberately not a bare ``max_examples``
#: search: every file in this feature discusses ``max_examples`` in its docstring to say
#: it is never set, and a check that failed on those sentences would be uninterpretable.
#: The negative lookahead keeps ``==`` comparisons out of it.
#:
#: **The pattern alone is not the rule.** A docstring may quote an assignment rather than
#: merely name the knob -- ``tests/uplift/test_baseline_determinism_conformance.py:22``
#: reads "pinned with ``@settings(max_examples=200)``", which this pattern matches while
#: no budget is set on that line. So every use below applies the pattern to
#: :func:`executable_source_lines` output rather than to raw text, which is what makes the
#: census reproducible: two readers counting by eye get two totals, and one of them is
#: counting a sentence (R3.6, R3.7).
_HARDCODED_MAX_EXAMPLES_RE: Final[re.Pattern[str]] = re.compile(r"max_examples[ \t]*=(?!=)")

#: fast-check's in-place budget, in **any** form. Not ``numRuns[ \t]*:[ \t]*(?P<runs>\d+)``
#: any more: a computed value (``{ numRuns: budget }``) overrides ``configureGlobal``
#: exactly as a literal does, so a pattern that only saw digits would police the honest
#: half of the failure mode and miss the other (R3.4).
_NUM_RUNS_RE: Final[re.Pattern[str]] = re.compile(r"numRuns[ \t]*:")

# ---------------------------------------------------------------------------
# The scan scope for undeclared tags
# ---------------------------------------------------------------------------

#: First-party source and test trees. Top-level names only, which keeps vendored and
#: generated trees (``frontend/node_modules``) and the in-repo git worktree copy under
#: ``.gl_scratch/`` out by construction rather than by pattern.
SEARCH_ROOTS: Final[tuple[str, ...]] = (
    "agents",
    "api",
    "data_fabric",
    "digital_twin",
    "frontend/spec",
    "frontend/src",
    "orchestrator",
    "packages",
    "scripts",
    "tests",
)

_SKIP_DIR_NAMES: Final[frozenset[str]] = frozenset(
    {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "dist-e2e",
        "node_modules",
        "venv",
    }
)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


@cache
def read_text(path: Path) -> str:
    """Text of one declared file, always UTF-8 (E-S13-07).

    Cached because several clauses re-read the same declared files and the design doc.
    The undeclared-tag scan deliberately does **not** go through here: caching the whole
    first-party tree would hold tens of megabytes for the rest of the session, which is
    not a cost a consistency check gets to impose (I-0).
    """
    return path.read_text(encoding="utf-8")


def language_of(relative_path: str) -> str:
    """The language a declared path is written in, derived from its suffix."""
    return _LANGUAGES[Path(relative_path).suffix]


def declared_paths() -> dict[int, Path]:
    """Property number -> absolute path, in property order."""
    return {number: ROOT / relative for number, relative in sorted(DECLARED_INVENTORY.items())}


def existing_declared_texts() -> dict[int, str]:
    """Text of every declared file that exists.

    A missing file is left out rather than raising, so the existence clause reports it
    once by name instead of every other clause erroring on the same absence.
    """
    texts: dict[int, str] = {}
    for number, path in declared_paths().items():
        if path.is_file():
            texts[number] = read_text(path)
    return texts


@cache
def design_headings() -> tuple[tuple[int, str], ...]:
    """Every ``### Property {N}: {title}`` heading in the design, in document order."""
    headings: list[tuple[int, str]] = []
    for line in read_text(DESIGN_DOC).splitlines():
        match = _DESIGN_HEADING_RE.match(line)
        if match is not None:
            headings.append((int(match.group("number")), match.group("title")))
    return tuple(headings)


def design_titles() -> dict[int, str]:
    """Property number -> design title."""
    return dict(design_headings())


def expected_tag(number: int) -> str:
    """The tag text the file claiming ``number`` must start with.

    The design's ``(slow)`` marker is stripped: it records where a property runs, and no
    tag in the inventory repeats it.
    """
    title = design_titles()[number]
    if title.endswith(_SLOW_SUFFIX):
        title = title[: -len(_SLOW_SUFFIX)]
    return f"{TAG_PREFIX}{number}: {title}"


# ---------------------------------------------------------------------------
# Tag extraction
# ---------------------------------------------------------------------------


def comment_payload(line: str, marker: str) -> str | None:
    """The comment text of a whole-line comment, or ``None`` for any other line.

    A trailing comment on a code line returns ``None`` on purpose: the tag convention is
    a comment line of its own.
    """
    stripped = line.strip()
    if not stripped.startswith(marker):
        return None
    return stripped[len(marker) :].strip()


def tag_blocks(text: str, *, marker: str) -> tuple[str, ...]:
    """Every tag in ``text``, each normalised to one whitespace-collapsed line.

    A tag that wraps is joined with the comment lines that immediately follow it, which
    is the only shape a wrapped tag takes in this feature. Callers compare with
    ``startswith``, so trailing commentary that happens to share the block is harmless.
    """
    payloads: list[str | None] = [comment_payload(line, marker) for line in text.splitlines()]
    blocks: list[str] = []
    for index, payload in enumerate(payloads):
        if payload is None or not payload.startswith(TAG_PREFIX):
            continue
        parts = [payload]
        cursor = index + 1
        while cursor < len(payloads):
            following = payloads[cursor]
            if following is None:
                break
            parts.append(following)
            cursor += 1
        blocks.append(" ".join(" ".join(parts).split()))
    return tuple(blocks)


def tagged_property_numbers(text: str, *, marker: str) -> tuple[int, ...]:
    """The property number each tag in ``text`` claims, in file order."""
    numbers: list[int] = []
    for block in tag_blocks(text, marker=marker):
        match = _TAG_NUMBER_RE.match(block)
        if match is not None:
            numbers.append(int(match.group("number")))
    return tuple(numbers)


def iter_source_files() -> Iterator[Path]:
    """Every first-party Python and TypeScript source file under ``SEARCH_ROOTS``."""
    for root in SEARCH_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in _LANGUAGES:
                continue
            if any(part in _SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.is_file():
                yield path


def relative_to_root(path: Path) -> str:
    """``path`` as a repo-relative POSIX string, for messages that a reader can paste."""
    return path.resolve().relative_to(ROOT).as_posix()


def _bullets(lines: list[str]) -> str:
    """An ASCII bullet list for an assertion message."""
    return "\n  - " + "\n  - ".join(lines)


# ---------------------------------------------------------------------------
# Executable-only reading: a budget written in prose is not a budget that is set
# ---------------------------------------------------------------------------


def _blank_span(line: str, start: int, end: int) -> str:
    """``line`` with ``[start, end)`` replaced by spaces, preserving every column."""
    stop = min(end, len(line))
    if stop <= start:
        return line
    return line[:start] + " " * (stop - start) + line[stop:]


#: Optional token types that carry *literal text* on the Pythons that emit them. Before
#: 3.12 an f-string is one ``STRING`` token; from 3.12 it is
#: ``FSTRING_START``/``FSTRING_MIDDLE``/``FSTRING_END``, and 3.14 adds the ``TSTRING_*``
#: triple for t-strings. Only the ``_MIDDLE`` members carry literal text - the replacement
#: fields inside them are ordinary ``NAME``/``OP`` tokens and stay executable, which is the
#: distinction this reader needs.
_OPTIONAL_LITERAL_TOKEN_NAMES: Final[tuple[str, ...]] = ("FSTRING_MIDDLE", "TSTRING_MIDDLE")


def _literal_content_token_types() -> frozenset[int]:
    """Token types whose text is prose about code rather than code.

    Resolved by name at import time rather than written as a literal tuple, because the set
    is **version-dependent** and this gate runs on more than one interpreter: py311 is the
    declared target (``pyproject.toml``) and the dev box here is 3.14. A hardcoded
    ``(COMMENT, STRING)`` counts an f-string's text as executable on 3.12+ and as prose on
    3.11, which is the same defect class the module docstring records for the raw pattern
    scan -- a checker that reads a literal textually cannot tell a subject from prose about
    it -- with the reader replaced by the interpreter. Two interpreters, two totals.
    """
    types = {tokenize.COMMENT, tokenize.STRING}
    for name in _OPTIONAL_LITERAL_TOKEN_NAMES:
        value = getattr(tokenize, name, None)
        if isinstance(value, int):
            types.add(value)
    return frozenset(types)


_LITERAL_CONTENT_TOKENS: Final[frozenset[int]] = _literal_content_token_types()


def _executable_python_lines(text: str, *, strict: bool) -> tuple[str, ...]:
    """Python source with comment and string-literal *content* blanked out.

    Uses :mod:`tokenize`, so the answer is the language's own lexical opinion rather than a
    heuristic: docstrings are ``STRING`` tokens like any other string, and f-string and
    t-string bodies are blanked through :data:`_LITERAL_CONTENT_TOKENS`, which resolves the
    interpreter-dependent token names so the count does not move with the Python running it.

    Column positions are preserved by blanking in place rather than deleting, so a hit's
    reported line number is the line number in the real file.

    ``strict=False`` returns the raw lines when the text does not tokenize, which is the
    right answer for a clause that is only *scoping* a rule; ``strict=True`` re-raises, for
    the census clause, where a file that cannot be read is a hole in a count.
    """
    lines = text.splitlines()
    blanked = list(lines)
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        if strict:
            raise
        return tuple(lines)
    for token in tokens:
        if token.type not in _LITERAL_CONTENT_TOKENS:
            continue
        (start_row, start_col), (end_row, end_col) = token.start, token.end
        for row in range(start_row, end_row + 1):
            index = row - 1
            if not 0 <= index < len(blanked):
                continue
            line = blanked[index]
            begin = start_col if row == start_row else 0
            finish = end_col if row == end_row else len(line)
            blanked[index] = _blank_span(line, begin, finish)
    return tuple(blanked)


def _executable_typescript_lines(text: str) -> tuple[str, ...]:
    """TypeScript source with ``//`` and ``/* */`` comments and string bodies blanked out.

    A hand-rolled scanner, because there is no TypeScript tokenizer in this test
    environment and adding one to satisfy a gate would be a dependency for a lexical
    question. It tracks line comments, block comments, and the three string forms
    (``'``, ``"``, `````) including backslash escapes.

    **Stated limit:** a regex literal is treated as division, so ``/numRuns:/`` inside a
    regex would read as executable. That is the safe direction -- it can only produce a
    false *offender*, which a human reads and corrects, never a false clean bill. No
    declared file contains one today.
    """
    lines = text.splitlines()
    blanked: list[str] = []
    in_block_comment = False
    for raw in lines:
        line = raw
        index = 0
        quote: str | None = None
        while index < len(line):
            char = line[index]
            if in_block_comment:
                if line.startswith("*/", index):
                    line = _blank_span(line, index, index + 2)
                    in_block_comment = False
                    index += 2
                else:
                    line = _blank_span(line, index, index + 1)
                    index += 1
                continue
            if quote is not None:
                if char == "\\":
                    line = _blank_span(line, index, index + 2)
                    index += 2
                    continue
                if char == quote:
                    quote = None
                else:
                    line = _blank_span(line, index, index + 1)
                index += 1
                continue
            if line.startswith("//", index):
                line = _blank_span(line, index, len(line))
                break
            if line.startswith("/*", index):
                line = _blank_span(line, index, index + 2)
                in_block_comment = True
                index += 2
                continue
            if char in "'\"`":
                quote = char
                index += 1
                continue
            index += 1
        blanked.append(line)
    return tuple(blanked)


def executable_source_lines(text: str, *, language: str, strict: bool = False) -> tuple[str, ...]:
    """``text`` split into lines, with comment and string-literal content blanked out.

    The counting rule R3.6 and R3.7 ask for: a budget *named* in a docstring is prose, a
    budget *assigned* in code is a violation, and a pattern applied to raw text cannot tell
    them apart. Line numbering and column positions are preserved.
    """
    if language == PYTHON:
        return _executable_python_lines(text, strict=strict)
    if language == TYPESCRIPT:
        return _executable_typescript_lines(text)
    message = f"no executable-line reader for language {language!r}"
    raise ValueError(message)


# ---------------------------------------------------------------------------
# The inventory agrees with the design
# ---------------------------------------------------------------------------


def test_the_design_document_is_present_and_declares_properties() -> None:
    """The design is the authority every other clause reads; name it if it is not there.

    Asserted first and separately so a moved or renamed spec directory reports itself,
    rather than surfacing as an unreadable traceback inside five unrelated clauses.
    """
    assert DESIGN_DOC.is_file(), (
        f"the design document is missing: {relative_to_root(DESIGN_DOC.parent)}/"
        f"{DESIGN_DOC.name} - this check cannot verify the inventory without it"
    )
    assert design_headings(), (
        f"{relative_to_root(DESIGN_DOC)} contains no '### Property {{N}}: {{title}}' "
        "heading - either the design moved its property section or the heading "
        "convention changed, and this check has stopped seeing what it reads"
    )


def test_the_design_document_declares_each_property_number_once() -> None:
    """A duplicated heading number would let two designs share one test slot."""
    seen: dict[int, int] = {}
    for number, _title in design_headings():
        seen[number] = seen.get(number, 0) + 1
    duplicated = sorted(number for number, count in seen.items() if count > 1)
    assert not duplicated, (
        f"{relative_to_root(DESIGN_DOC)} declares these property numbers more than once: "
        f"{duplicated}"
    )


def test_the_design_and_the_inventory_declare_the_same_properties() -> None:
    """The count is derived from both sides, never asserted as a literal."""
    designed = {number for number, _title in design_headings()}
    declared = set(DECLARED_INVENTORY)

    unclaimed = sorted(designed - declared)
    undesigned = sorted(declared - designed)

    problems: list[str] = []
    if unclaimed:
        problems.append(f"design properties with no test declared for them: {unclaimed}")
    if undesigned:
        problems.append(f"inventory entries with no matching design property: {undesigned}")

    assert not problems, (
        f"{relative_to_root(DESIGN_DOC)} declares {len(designed)} properties and the "
        f"inventory declares {len(declared)} tests -{_bullets(problems)}"
    )


def test_the_inventory_declares_one_distinct_file_per_property() -> None:
    """One property per file, one file per property - the design's 'exactly one'."""
    by_path: dict[str, list[int]] = {}
    for number, relative in sorted(DECLARED_INVENTORY.items()):
        by_path.setdefault(relative, []).append(number)
    shared = [
        f"{path} is declared for properties {numbers}"
        for path, numbers in sorted(by_path.items())
        if len(numbers) > 1
    ]
    assert not shared, f"one path may carry only one property -{_bullets(shared)}"


def test_every_declared_path_lies_inside_a_search_root() -> None:
    """The undeclared-tag scan only covers ``SEARCH_ROOTS``, so the inventory must too.

    Without this, a declared path outside the roots would be checked by the clauses that
    read it by name while being invisible to the clause that looks for strays - and the
    'exactly N' claim would quietly hold over a smaller tree than it appears to.
    """
    outside = [
        relative
        for relative in sorted(DECLARED_INVENTORY.values())
        if not any(relative.startswith(f"{root}/") for root in SEARCH_ROOTS)
    ]
    assert not outside, f"declared paths outside SEARCH_ROOTS {SEARCH_ROOTS} -{_bullets(outside)}"


# ---------------------------------------------------------------------------
# The declared files exist, and are tagged with the property they claim
# ---------------------------------------------------------------------------


def test_every_declared_property_test_file_exists() -> None:
    """A declared inventory whose files are absent is a document, not an inventory."""
    missing = [
        f"Property {number}: {DECLARED_INVENTORY[number]}"
        for number, path in declared_paths().items()
        if not path.is_file()
    ]
    assert not missing, f"declared property tests that do not exist -{_bullets(missing)}"


def test_every_declared_file_carries_the_tag_of_the_property_it_claims() -> None:
    """The tag is matched after normalising wrapped comment lines (see module docstring)."""
    untagged: list[str] = []
    for number, text in existing_declared_texts().items():
        relative = DECLARED_INVENTORY[number]
        marker = _COMMENT_MARKERS[language_of(relative)]
        expected = expected_tag(number)
        blocks = tag_blocks(text, marker=marker)
        if any(block.startswith(expected) for block in blocks):
            continue
        found = "; ".join(blocks) if blocks else "no tag comment at all"
        untagged.append(f"{relative} expected '{marker} {expected}' but found: {found}")
    assert not untagged, f"declared property tests missing their tag -{_bullets(untagged)}"


def test_no_declared_file_tags_a_property_it_does_not_claim() -> None:
    """A tag naming another property is a file filed under the wrong design entry."""
    foreign: list[str] = []
    for number, text in existing_declared_texts().items():
        relative = DECLARED_INVENTORY[number]
        marker = _COMMENT_MARKERS[language_of(relative)]
        tagged = tagged_property_numbers(text, marker=marker)
        others = sorted({claimed for claimed in tagged if claimed != number})
        if others:
            foreign.append(f"{relative} is declared for Property {number} but also tags {others}")
    assert not foreign, f"property tags that do not match their declaration -{_bullets(foreign)}"


def test_no_file_outside_the_inventory_carries_a_feature_property_tag() -> None:
    """The additive half of 'exactly N': no tagged stray the inventory does not declare.

    A file that cannot be read is named, never skipped - absence of proof is not a pass
    (I-7).
    """
    declared = set(DECLARED_INVENTORY.values())
    # This file composes TAG_PREFIX as data, so excluding it keeps the scan from
    # reporting the scanner. No comment line here is itself a tag.
    scanner = relative_to_root(Path(__file__))
    strays: list[str] = []
    unreadable: list[str] = []
    for path in iter_source_files():
        relative = relative_to_root(path)
        if relative == scanner:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            unreadable.append(f"{relative}: {error}")
            continue
        marker = _COMMENT_MARKERS[_LANGUAGES[path.suffix]]
        numbers = tagged_property_numbers(text, marker=marker)
        if numbers and relative not in declared:
            strays.append(f"{relative} tags properties {sorted(set(numbers))}")

    assert not unreadable, f"files the scan could not read -{_bullets(unreadable)}"
    assert not strays, (
        "files carrying this feature's property tag without an inventory entry - add them "
        f"to DECLARED_INVENTORY or remove the tag -{_bullets(strays)}"
    )


def test_every_declared_file_uses_its_language_property_runner() -> None:
    """A tag over no generator is a label, not a property test."""
    inert: list[str] = []
    for number, text in existing_declared_texts().items():
        relative = DECLARED_INVENTORY[number]
        token = _RUNNER_TOKENS[language_of(relative)]
        if token not in text:
            inert.append(f"{relative} (Property {number}) contains no '{token}'")
    assert not inert, f"declared property tests that generate nothing -{_bullets(inert)}"


# ---------------------------------------------------------------------------
# Example budgets: inherited in Python, stated in place in TypeScript
# ---------------------------------------------------------------------------


def test_no_python_property_test_in_this_feature_hardcodes_max_examples() -> None:
    """Scoped to the declared Python files - see the module docstring for why.

    A hardcoded value overrides the root ``conftest.py`` profile in both directions: it
    makes a local run heavier than I-0 allows and a CI run lighter than the
    >=100-iteration obligation requires.
    """
    offenders: list[str] = []
    for number, text in existing_declared_texts().items():
        relative = DECLARED_INVENTORY[number]
        if language_of(relative) != PYTHON:
            continue
        # Executable lines only (R3.6, R3.7). Every file in this feature discusses
        # ``max_examples`` in its docstring to say it is never set, and a docstring that
        # quotes an assignment must not fail the file that disowns it.
        hits = [
            index + 1
            for index, line in enumerate(executable_source_lines(text, language=PYTHON))
            if _HARDCODED_MAX_EXAMPLES_RE.search(line)
        ]
        if hits:
            offenders.append(f"{relative} (Property {number}) sets max_examples on lines {hits}")
    assert not offenders, (
        "max_examples must come from the root conftest.py profiles (dev=10, heavy=100, "
        f"ci/default=500, nightly=5000) -{_bullets(offenders)}"
    )


def test_no_typescript_property_test_in_this_feature_states_a_run_budget() -> None:
    """The exact mirror of the Python rule above, now that there *is* a profile to inherit.

    This clause replaces ``..._states_a_run_budget_of_at_least_100``, and the replacement is
    a reversal, not a tightening. The old clause was right for the world it was written in:
    fast-check had no profile mechanism in this repository, so stating ``{ numRuns: 100 }``
    in place was the only way to express the >=100-iteration obligation, and requiring it was
    the honest analogue of the Python profile rather than a silent exemption.

    ``frontend/src/test/fc-budget.ts`` plus the ``fc.configureGlobal`` call in
    ``frontend/src/test/setup.ts`` supply the missing mechanism, which inverts the rule: a
    per-call ``numRuns`` **overrides** the global, so an in-place budget now defeats the very
    inheritance it used to substitute for. It pins the local cost to the CI cost, which is
    what I-0 forbids.

    R3.8 is why the two clauses may never coexist: one requires what the other forbids, so a
    half-move leaves this gate failing on the files task 1.3 has just corrected.
    """
    offenders: list[str] = []
    for number, text in existing_declared_texts().items():
        relative = DECLARED_INVENTORY[number]
        if language_of(relative) != TYPESCRIPT:
            continue
        lines = executable_source_lines(text, language=TYPESCRIPT)
        hits = [index + 1 for index, line in enumerate(lines) if _NUM_RUNS_RE.search(line)]
        if hits:
            offenders.append(f"{relative} (Property {number}) states numRuns on lines {hits}")
    assert not offenders, (
        "numRuns must come from HYPOTHESIS_PROFILE via fc.configureGlobal in "
        "frontend/src/test/setup.ts (see frontend/src/test/fc-budget.ts: dev=10, heavy=100, "
        f"default/ci=500, nightly=5000); a per-call value overrides it -{_bullets(offenders)}"
    )


def test_the_hardcoded_budget_census_is_reproducible_and_reported() -> None:
    """R3.6/R3.7: report the count, name every offender, assert no total.

    Why no total is asserted (CF-13). The I-0 steering file records "three pre-existing
    violations" under ``tests/uplift/`` and ``tests/verify/``, and A-2 carries that number
    forward marked *unverified* rather than asserted. Pinning any total here would either
    bless a number nobody re-derived or make this gate fail on a count that moves for
    reasons unrelated to this feature. So the census is **reported** and only its
    *reproducibility* is asserted:

    1. every file in scope parses, because a file the tokenizer cannot read is a hole in the
       count and not a zero (I-7); and
    2. every raw pattern hit is accounted for as either executable or lexically
       non-executable, so the difference between the two totals is explained rather than
       merely observed.

    The report names the interpreter that produced it, because the executable/prose boundary
    is the interpreter's lexical opinion: see :func:`_literal_content_token_types` for the
    f-string token shape that changed at 3.12 and is normalised there.

    Clause 2 is the one with teeth. The raw pattern matches a *sentence* in
    ``tests/uplift/test_baseline_determinism_conformance.py:22`` -- prose describing a
    budget, not setting one -- so a reader counting raw hits and a reader counting real
    assignments get different totals and neither is obviously wrong. Excluding comment and
    string tokens makes the count a fact about code.

    The census is printed rather than asserted. ``print`` is deliberate here: this is a
    test's report channel, not application logging, so the ``structlog``-not-``print``
    convention does not apply. Read it with ``-s`` or ``-rP``.
    """
    scope = ("tests/uplift", "tests/verify")
    unparseable: list[str] = []
    unexplained: list[str] = []
    census: dict[str, list[int]] = {}
    raw_total = 0

    for root in scope:
        base = ROOT / root
        if not base.is_dir():
            unparseable.append(f"{root}: not a directory")
            continue
        for path in sorted(base.rglob("*.py")):
            relative = relative_to_root(path)
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                unparseable.append(f"{relative}: {error}")
                continue
            raw_lines = text.splitlines()
            raw_hits = {
                index + 1
                for index, line in enumerate(raw_lines)
                if _HARDCODED_MAX_EXAMPLES_RE.search(line)
            }
            raw_total += len(raw_hits)
            try:
                executable = executable_source_lines(text, language=PYTHON, strict=True)
            except tokenize.TokenError as error:
                unparseable.append(f"{relative}: {error}")
                continue
            executable_hits = {
                index + 1
                for index, line in enumerate(executable)
                if _HARDCODED_MAX_EXAMPLES_RE.search(line)
            }
            if executable_hits:
                census[relative] = sorted(executable_hits)
            # Clause 2: an executable hit that is not a raw hit would mean the blanking
            # *introduced* a match, which would make the census an artefact of this helper.
            invented = sorted(executable_hits - raw_hits)
            if invented:
                unexplained.append(f"{relative}: blanking invented hits on lines {invented}")

    assert not unparseable, (
        f"files in the census scope that could not be counted -{_bullets(unparseable)}"
    )
    assert not unexplained, (
        f"the executable-only counting rule is not a restriction of the raw scan "
        f"-{_bullets(unexplained)}"
    )

    executable_total = sum(len(lines) for lines in census.values())
    interpreter = ".".join(str(part) for part in sys.version_info[:3])
    report = [
        f"hardcoded max_examples census over {', '.join(scope)}",
        f"  read by CPython {interpreter}",
        f"  executable assignments: {executable_total} across {len(census)} file(s)",
        f"  raw pattern hits:       {raw_total} "
        f"(difference of {raw_total - executable_total} lies in comments or string literals)",
        "  offenders:",
        *(f"    {relative}: lines {lines}" for relative, lines in sorted(census.items())),
    ]
    print("\n".join(report))  # noqa: T201 - a test's report channel, see the docstring
