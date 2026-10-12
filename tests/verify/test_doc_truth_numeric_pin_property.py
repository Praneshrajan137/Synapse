"""Property-based test for the declarative numeric pins (design E1.3 / AD-3).

Feature: purpose-achievement-audit, Property 5: A documented value equals its
mechanical source

    *For any* pin in the pin table, the value extracted from the named document
    equals the value extracted from the named mechanical source, extraction is
    idempotent (re-running it on the same inputs yields the same value), and any
    difference fails naming the document line, the source, and both values.

Why the property is shaped this way. AD-3 replaced one bespoke claim function per
number with one data row per number, precisely so Requirement 7's eight-number sweep
became affordable. That trade only pays if resolution is **total** over the row space:
a bespoke function could be reviewed line by line, whereas a table row is reviewed by
the resolver that reads it. So the property quantifies over the whole row space the
table can express - the three extractor families, the four pin kinds, both scales -
rather than over the rows that happen to be committed today.

Three clauses, each asserted separately below:

* **agreement** - an agreeing (document, source) pair resolves ``ok``; a drifting pair
  resolves ``fail`` naming ``document:line``, the source path, and both raw values, so
  a CI log says *which* number moved rather than only that one did (R7.5, R7.10).
* **idempotence** - resolution is a function of its two text arguments. This is what
  makes the pin table trustworthy as data: a row's verdict cannot depend on evaluation
  order, on how many times the gate ran, or on anything outside the two file bodies.
* **scale is load-bearing** - the strategy generates the real ``percent_of_fraction``
  case (the document states ``80``, the source stores ``0.80``) as *agreeing*, so a
  checker that dropped the conversion is caught by this test rather than accommodated
  by it. The converse is asserted too: with the conversion forced off, the same pair
  fails.
* **all four kinds resolve** - ``threshold`` and ``flag`` pin against a configuration
  or workflow value, but ``blocking-gate`` pins against the generated
  ``docs/state/GATE_SURFACE.md`` record (R11.8) and ``required-job`` against
  ``infrastructure/quality/required-checks.yaml`` (R14.3). Those two carry the
  ``count`` and ``string`` comparisons rather than ``numeric``, so they are generated
  and asserted separately below; without them the property would cover half the row
  space the table can express.

Subject: the pure seam ``doc_truth.resolve_pin_texts(pin, document_text, source_text)``,
which resolves one pin against two **in-memory** file bodies. ``resolve_pin`` (reads
the tree) is driven only by the two static assertions at the bottom, and ``evaluate()``
is never driven at all - it spawns the ``verify_claims`` suite under a 900s budget,
which I-0 forbids on this machine.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 7.5, 7.10, 11.8, 14.3**
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit.doc_truth import (
    PIN_TABLE,
    ROOT,
    ClaimResult,
    NumericPin,
    documented_value,
    extract_source_values,
    load_pins,
    resolve_pin_texts,
)
from tests.verify.strategies import EXTRACTOR_KINDS, PIN_KINDS, PinCase, pin_cases

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The claim vocabulary a pin can report. ``skip`` is honest degradation, never a pass.
PIN_STATUSES: Final[tuple[str, ...]] = ("ok", "fail", "skip")

#: Relative tolerance the resolver compares numerics with (doc_truth._REL_TOL).
REL_TOL: Final[float] = 1e-9


def _build(case: PinCase) -> NumericPin:
    """Validate one generated row into the model the resolver consumes."""
    return NumericPin.model_validate(dict(case.pin))


def _expected_line(case: PinCase) -> int:
    """The 1-based line the anchor must report: the decoys, then the anchored line."""
    pattern = re.compile(str(case.pin["anchor"]))
    hits = [
        number
        for number, line in enumerate(case.document_text.splitlines(), start=1)
        if pattern.search(line) is not None
    ]
    assert len(hits) == 1, "the strategy must plant exactly one anchored line"
    return hits[0]


def _assert_well_formed(result: ClaimResult, pin: NumericPin) -> None:
    """Invariants a resolution owes whichever clause decided it."""
    # Total: one of three statuses, reported under the pin's own id, with the row's
    # `required` flag carried through so the aggregate can refuse to mask it (R1.6).
    assert result.status in PIN_STATUSES
    assert result.name == pin.id
    assert result.required is pin.required
    assert result.detail


# Feature: purpose-achievement-audit, Property 5: A documented value equals its
# mechanical source
@given(case=pin_cases())
def test_a_pin_resolves_to_the_generated_ground_truth(case: PinCase) -> None:
    """R7.5, R7.10: agreement resolves ``ok``; drift resolves ``fail`` naming both sides."""
    pin = _build(case)
    result = resolve_pin_texts(pin, case.document_text, case.source_text)

    _assert_well_formed(result, pin)

    # Never unresolved: both texts are well formed and the anchor matches one line, so
    # a `skip` here would mean the resolver could not read a table row it declares
    # supported - the exact hole AD-3's data-driven shape would open if it existed.
    assert result.status != "skip"
    assert result.status == ("ok" if case.agrees else "fail")

    location = f"{pin.document}:{_expected_line(case)}"
    assert location in result.detail
    assert pin.source in result.detail
    assert case.document_value in result.detail
    assert case.source_value in result.detail

    if not case.agrees:
        # The two values are genuinely different numbers, so the FAIL is not an
        # artefact of formatting: it is drift.
        documented = float(case.document_value)
        scaled = documented / 100.0 if pin.scale == "percent_of_fraction" else documented
        assert not math.isclose(scaled, float(case.source_value), rel_tol=REL_TOL, abs_tol=0.0)


@given(case=pin_cases())
def test_extraction_is_idempotent(case: PinCase) -> None:
    """Property 5's round-trip clause: resolution is a function of its two texts."""
    pin = _build(case)

    first = resolve_pin_texts(pin, case.document_text, case.source_text)
    second = resolve_pin_texts(pin, case.document_text, case.source_text)
    third = resolve_pin_texts(pin, case.document_text, case.source_text)

    assert first == second == third

    # And so is each half, independently - which is why the whole is idempotent
    # rather than incidentally stable.
    assert documented_value(pin, case.document_text) == documented_value(pin, case.document_text)
    assert extract_source_values(pin.extractor, case.source_text) == extract_source_values(
        pin.extractor, case.source_text
    )

    # An identical row validated twice is the same pin, so two tables that differ only
    # by row order resolve identically (frozen model, value equality).
    assert _build(case) == pin
    assert resolve_pin_texts(_build(case), case.document_text, case.source_text) == first


@given(case=pin_cases())
def test_a_checker_that_forgot_the_scale_conversion_is_caught(case: PinCase) -> None:
    """The ``percent_of_fraction`` case is generated as *agreeing*, so scale must bite.

    ``80`` in prose against ``0.80`` in configuration is the real shape of the
    tier-routing floor pin. A resolver that compared the raw numbers would call that
    drift; a resolver that ignored scale entirely on the drifting rows would call drift
    agreement. Both directions are asserted here.
    """
    pin = _build(case)
    result = resolve_pin_texts(pin, case.document_text, case.source_text)

    unscaled = pin.model_copy(update={"scale": "identity"})
    naive = resolve_pin_texts(unscaled, case.document_text, case.source_text)

    documented = float(case.document_value)
    source = float(case.source_value)
    agrees_unscaled = math.isclose(documented, source, rel_tol=REL_TOL, abs_tol=0.0)

    # The scale-blind checker is exactly the checker that compares raw numbers.
    assert naive.status == ("ok" if agrees_unscaled else "fail")

    if pin.scale == "percent_of_fraction" and case.agrees and not agrees_unscaled:
        # Forgetting the conversion turns a true claim into a reported failure.
        assert result.status == "ok"
        assert naive.status == "fail"
        assert case.document_value in naive.detail
        assert case.source_value in naive.detail
    if pin.scale == "identity":
        # With nothing to convert, the two resolvers are the same resolver.
        assert naive == result


@given(case=pin_cases())
def test_resolution_is_total_over_degraded_inputs(case: PinCase) -> None:
    """Every unreadable shape degrades to ``skip`` naming the cause - never to a pass.

    Requirement 7.5 is only total if the resolver has no input on which it raises or
    quietly reports agreement. The four shapes below are the ones a real edit produces:
    a reworded governance sentence, a duplicated sentence, a truncated source, and a
    corrupt source.
    """
    pin = _build(case)
    anchor = re.compile(pin.anchor)
    lines = case.document_text.splitlines()
    anchored = [line for line in lines if anchor.search(line) is not None]

    reworded = "\n".join(line for line in lines if anchor.search(line) is None) + "\n"
    duplicated = case.document_text + anchored[0] + "\n"

    degraded: tuple[tuple[str, str], ...] = (
        (reworded, case.source_text),
        (duplicated, case.source_text),
        (case.document_text, ""),
        (case.document_text, "::: not a document ["),
    )

    for document_text, source_text in degraded:
        result = resolve_pin_texts(pin, document_text, source_text)
        _assert_well_formed(result, pin)
        assert result.status == "skip"
        assert result.status != "ok"
        # The skip is attributable: it names the document or the source it could not
        # read, so an operator is told what to fix (I-7).
        assert pin.document in result.detail or pin.source in result.detail


# ---------------------------------------------------------------------------
# The two kinds whose mechanical source is a GENERATED RECORD rather than a
# configuration file: `blocking-gate` -> docs/state/GATE_SURFACE.md (R11.8) and
# `required-job` -> infrastructure/quality/required-checks.yaml (R14.3).
#
# `pin_cases` covers the numeric row space (three extractor families, both scales).
# These two kinds are separate because they compare differently: a blocking-gate pin
# counts DISTINCT matching rows in the surface record against a count spelled in prose
# ("two BLOCKING verify steps"), and a required-job pin asserts MEMBERSHIP of a
# documented job name in the declared required set. Both shapes are reproduced here as
# the committed table declares them, so the property covers the table's whole row
# space rather than only its numeric half.
# ---------------------------------------------------------------------------

GATE_SURFACE: Final[str] = "docs/state/GATE_SURFACE.md"
REQUIRED_CHECKS: Final[str] = "infrastructure/quality/required-checks.yaml"

#: Governance prose spells small counts as words, so a `count` pin accepts either
#: spelling on the document side (doc_truth._NUMBER_WORDS). Index == value.
COUNT_WORDS: Final[tuple[str, ...]] = ("zero", "one", "two", "three", "four", "five")

#: The committed `cd-gcp-blocking-verify-steps` row's anchor and extractor, verbatim.
#: The extractor reads the `Declared-blocking anchors` section's Step and Note cells and
#: deliberately NOT the `Propagates` column - see that row's comment in the pin table.
BLOCKING_ANCHOR: Final[str] = r"ends with (?P<value>\w+) BLOCKING verify steps"
BLOCKING_EXTRACTOR: Final[str] = (
    r"regex:\| (?P<value>Verify deploy truth [^|]*verify_live\.py[^|]*) "
    r"\| [^|]* \| declared blocking"
)

#: The pending `mutation-fast-required-job` row's anchor and extractor, verbatim.
REQUIRED_JOB_ANCHOR: Final[str] = r"via `(?P<value>[\w-]+)` job \(C30\)"
REQUIRED_JOB_EXTRACTOR: Final[str] = "yaml_path:required[].job"

#: Governance lines that must NOT satisfy either anchor. A pin that matched one of
#: these would be guarding a sentence nobody meant it to guard.
_KIND_DECOY_DOC_LINES: Final[tuple[str, ...]] = (
    "- NEVER make these steps warn-only.",
    "- Superseded: the deploy ended with one BLOCKING verify step (Sprint 8).",
    "- Superseded: enforced via `mutation` job (C29).",
    "A SKIP is not a PASS, and absence of proof is never a pass.",
)

_RENDERED_TRIGGERS: Final[tuple[str, ...]] = ("push:main", "pull_request", "tag:v*")

#: The `Propagates` cell renders reachability and propagation jointly (E1.6).
_PROPAGATES_CELLS: Final[tuple[str, ...]] = ("yes", "CONDITIONAL", "NOT EXECUTED")

_DEPLOY_JOB: Final[str] = ".github/workflows/cd-gcp.yml::deploy-to-vm"


def _render_surface(rows: Sequence[tuple[str, str, str, str, str]]) -> str:
    """Render a ``GATE_SURFACE.md``-shaped table: trigger, job, step, propagates, note."""
    header = (
        "## Declared-blocking anchors\n\n"
        "| Trigger | Job | Step | Propagates | Note |\n"
        "|---|---|---|---|---|\n"
    )
    body = "".join(f"| {' | '.join(cells)} |\n" for cells in rows)
    return header + body


def _spell(count: int, *, as_word: bool) -> str:
    """Render a count the way a governance sentence would."""
    return COUNT_WORDS[count] if as_word and count < len(COUNT_WORDS) else str(count)


@st.composite
def blocking_gate_cases(draw: st.DrawFn) -> PinCase:
    """A ``blocking-gate`` pin against a gate-surface-shaped record (R11.8).

    Two decoy row classes make the extractor's two conditions load-bearing rather than
    incidental: a declared-blocking step that is not a verify step (fails the Step
    condition) and a verify step whose Note is advisory (fails the Note condition).
    Neither may be counted, so a pin that counted every row - or every verify row -
    is caught here.
    """
    step_words = draw(
        st.lists(
            st.sampled_from(("containers", "external", "decision-probe", "expect-sha")),
            min_size=1,
            max_size=4,
            unique=True,
        )
    )
    steps = tuple(f"Verify deploy truth ({word}) [scripts/deploy/verify_live.py]" for word in step_words)
    triggers = draw(
        st.lists(st.sampled_from(_RENDERED_TRIGGERS), min_size=1, max_size=3, unique=True)
    )

    rows: list[tuple[str, str, str, str, str]] = []
    for trigger in triggers:
        for step in steps:
            # The same step renders once per selected trigger, so the DISTINCT step
            # count - not the row count - is what the prose claims.
            rows.append(
                (trigger, _DEPLOY_JOB, step, draw(st.sampled_from(_PROPAGATES_CELLS)),
                 "declared blocking (R1.8)")
            )
        rows.append(
            (trigger, ".github/workflows/ci.yml::quality-gates", "Ruff lint", "yes",
             "declared blocking (R1.8)")
        )
        rows.append(
            (trigger, _DEPLOY_JOB,
             "Verify deploy truth (advisory-probe) [scripts/deploy/verify_live.py]",
             "no", "advisory (named)")
        )

    actual = len(steps)
    agrees = draw(st.booleans())
    claimed = (
        actual
        if agrees
        else draw(st.integers(min_value=0, max_value=5).filter(lambda value: value != actual))
    )
    document_value = _spell(claimed, as_word=draw(st.booleans()))

    document_line = f"- Every cd-gcp deploy ends with {document_value} BLOCKING verify steps (C47)."
    decoys = draw(st.lists(st.sampled_from(_KIND_DECOY_DOC_LINES), max_size=3, unique=True))

    return PinCase(
        pin={
            "id": "cd-gcp-blocking-verify-steps",
            "kind": "blocking-gate",
            "required": draw(st.booleans()),
            "document": "CLAUDE.md",
            "anchor": BLOCKING_ANCHOR,
            "source": GATE_SURFACE,
            "extractor": BLOCKING_EXTRACTOR,
            "compare": "count",
            "scale": "identity",
        },
        document_text="\n".join([*decoys, document_line, ""]),
        source_text=_render_surface(rows),
        document_value=document_value,
        # For a `count` pin the mechanical value IS the number of distinct entries,
        # which is what the resolver quotes on both sides of its verdict.
        source_value=str(actual),
        agrees=claimed == actual,
    )


@st.composite
def required_job_cases(draw: st.DrawFn) -> PinCase:
    """A ``required-job`` pin against a required-checks-shaped declaration (R14.3).

    The disagreeing case draws its documented job from ``ineligible:`` /
    ``candidates:`` - jobs that ARE in the file but are NOT declared required. That is
    the shape R14.3 is about: a governance document calling a gate blocking when the
    declaration does not require it. A checker that searched the whole file for the
    name would pass those examples.
    """
    declared = draw(
        st.lists(
            st.sampled_from(("quality-gates", "uplift-verify", "truth-gates")),
            max_size=3,
            unique=True,
        )
    )
    present_but_not_required = draw(
        st.lists(
            st.sampled_from(("mutation-fast", "twin-oracle", "audit-immutability")),
            min_size=1,
            max_size=3,
            unique=True,
        )
    )
    agrees = bool(declared) and draw(st.booleans())
    job = draw(st.sampled_from(declared if agrees else present_but_not_required))

    source_text = yaml.safe_dump(
        {
            "version": 1,
            "branch": "main",
            "required": [
                {"job": name, "workflow": ".github/workflows/ci.yml"} for name in declared
            ],
            "candidates": [{"job": present_but_not_required[0], "reason": "not called blocking"}],
            "ineligible": [
                {"job": name, "reason": "path-filtered"} for name in present_but_not_required
            ],
        },
        sort_keys=True,
    )

    document_line = f"- Python mutation testing is PR-blocking via `{job}` job (C30)."
    decoys = draw(st.lists(st.sampled_from(_KIND_DECOY_DOC_LINES), max_size=3, unique=True))

    return PinCase(
        pin={
            "id": "mutation-fast-required-job",
            "kind": "required-job",
            "required": draw(st.booleans()),
            "document": "CLAUDE.md",
            "anchor": REQUIRED_JOB_ANCHOR,
            "source": REQUIRED_CHECKS,
            "extractor": REQUIRED_JOB_EXTRACTOR,
            "compare": "string",
            "scale": "identity",
        },
        document_text="\n".join([*decoys, document_line, ""]),
        source_text=source_text,
        document_value=job,
        source_value=",".join(declared),
        agrees=job in declared,
    )


# Feature: purpose-achievement-audit, Property 5: A documented value equals its
# mechanical source
@given(case=blocking_gate_cases())
def test_a_blocking_gate_pin_resolves_against_the_gate_surface_record(case: PinCase) -> None:
    """R11.8: a prose blocking claim is pinned to the generated gate-surface record."""
    pin = _build(case)
    result = resolve_pin_texts(pin, case.document_text, case.source_text)

    _assert_well_formed(result, pin)
    assert pin.kind == "blocking-gate"
    assert pin.source == GATE_SURFACE

    # A `count` pin never degrades on an empty extraction: zero matching rows is the
    # honest count 0, which FAILs a non-zero claim instead of skipping past it.
    assert result.status != "skip"
    assert result.status == ("ok" if case.agrees else "fail")

    location = f"{pin.document}:{_expected_line(case)}"
    assert location in result.detail
    assert pin.source in result.detail
    assert case.document_value in result.detail
    assert case.source_value in result.detail

    # Independent recount: only rows whose Step is a verify step AND whose Note declares
    # blocking are counted, and identical step names across triggers count once.
    distinct = tuple(dict.fromkeys(extract_source_values(pin.extractor, case.source_text)))
    assert len(distinct) == int(case.source_value)
    assert all("verify_live.py" in name for name in distinct)
    assert not any("advisory" in name for name in distinct)

    # Round-trip clause, on this kind too.
    assert resolve_pin_texts(pin, case.document_text, case.source_text) == result


@given(case=required_job_cases())
def test_a_required_job_pin_resolves_against_the_declared_required_set(case: PinCase) -> None:
    """R14.3: a job a document calls blocking must be in the declared required set."""
    pin = _build(case)
    result = resolve_pin_texts(pin, case.document_text, case.source_text)

    _assert_well_formed(result, pin)
    assert pin.kind == "required-job"
    assert pin.source == REQUIRED_CHECKS

    # Recomputed from the declaration itself, not from the resolver's own extractor.
    declaration = yaml.safe_load(case.source_text)
    declared = tuple(entry["job"] for entry in declaration["required"])

    if not declared:
        # An empty `required:` gives the pin nothing to compare against. That is
        # unavailable-naming-the-source, never a pass (I-7).
        assert result.status == "skip"
        assert pin.source in result.detail
        assert resolve_pin_texts(pin, case.document_text, case.source_text) == result
        return

    assert result.status != "skip"
    assert result.status == ("ok" if case.document_value in declared else "fail")

    assert f"{pin.document}:{_expected_line(case)}" in result.detail
    assert pin.source in result.detail
    assert case.document_value in result.detail

    if result.status == "fail":
        # Both sides are named: the job the document claims, and every job the
        # declaration actually requires.
        for name in declared:
            assert name in result.detail
        # And the documented job is present in the file, just not required - so the
        # FAIL is about the declaration, not about a typo.
        assert case.document_value in {
            entry["job"] for entry in declaration["ineligible"]
        } | {entry["job"] for entry in declaration["candidates"]}

    assert resolve_pin_texts(pin, case.document_text, case.source_text) == result


# ---------------------------------------------------------------------------
# The committed table. Static reads only - no gate is executed here (I-0).
# ---------------------------------------------------------------------------


def test_the_committed_pin_table_loads_and_validates() -> None:
    """Every committed row is a valid ``NumericPin`` with a usable anchor.

    ``load_pins`` reads only ``pins:``. ``pending_pins:`` and ``drift:`` are records,
    not suppressions - a pin listed under ``drift:`` still resolves and still fails.
    """
    pins = load_pins(PIN_TABLE.read_text(encoding="utf-8"))

    assert pins
    assert len({pin.id for pin in pins}) == len(pins)

    for pin in pins:
        assert pin.kind in PIN_KINDS
        assert pin.extractor.split(":", 1)[0] in EXTRACTOR_KINDS
        pattern = re.compile(pin.anchor)
        assert "value" in pattern.groupindex, f"{pin.id} anchor has no (?P<value>...) group"

    raw = yaml.safe_load(PIN_TABLE.read_text(encoding="utf-8"))
    pinned_ids = {pin.id for pin in pins}
    for pending in raw.get("pending_pins") or []:
        # A pending row must not also be live, or it would be evaluated under a
        # decision nobody has taken.
        assert pending["id"] not in pinned_ids


def test_every_recorded_drift_entry_is_still_mechanically_real() -> None:
    """The ``drift:`` record is honest: each entry names a pin that FAILs right now.

    The committed table records one live drift - ``stryker-break``: CLAUDE.md states
    ``break: 26`` while ``frontend/stryker.conf.json`` ships ``50`` (audit finding
    R7.8, remediated by task 12.1). This test asserts that recorded state rather than
    pretending it is resolved: the entry must name a pin that is *live* in ``pins:``
    (recording drift never suppresses it) and must resolve to ``fail`` quoting exactly
    the two values the record claims. When task 12.1 corrects CLAUDE.md and the ratchet
    constant, the ``drift:`` entry is removed and this test is satisfied vacuously,
    which is the correct coupling: the record and the mechanism move together.
    """
    text = PIN_TABLE.read_text(encoding="utf-8")
    pins = {pin.id: pin for pin in load_pins(text)}
    raw = yaml.safe_load(text)
    entries = raw.get("drift") or []

    for entry in entries:
        pin = pins.get(entry["pin"])
        assert pin is not None, f"drift entry {entry['pin']!r} names no live pin"

        document = Path(ROOT / pin.document).read_text(encoding="utf-8")
        source = Path(ROOT / pin.source).read_text(encoding="utf-8")
        result = resolve_pin_texts(pin, document, source)

        assert result.status == "fail", f"{pin.id} is recorded as drifting but resolved {result.status}"
        assert str(entry["document_value"]) in result.detail
        assert str(entry["source_value"]) in result.detail
        assert entry["remediation"], "a recorded drift must name its remediation"


def test_the_recorded_stryker_drift_matches_the_shipped_configuration() -> None:
    """The specific recorded pair, read from the two files it spans.

    Named separately so the drift is greppable from the test names, not only from the
    YAML: 26 in the narrative, 50 in the shipped Stryker configuration.
    """
    text = PIN_TABLE.read_text(encoding="utf-8")
    entries = {entry["pin"]: entry for entry in yaml.safe_load(text).get("drift") or []}
    if "stryker-break" not in entries:
        return  # task 12.1 landed; the record was removed with the drift.

    shipped = json.loads((ROOT / "frontend" / "stryker.conf.json").read_text(encoding="utf-8"))
    assert shipped["thresholds"]["break"] == entries["stryker-break"]["source_value"]

    pin = {pin.id: pin for pin in load_pins(text)}["stryker-break"]
    documented, _line = documented_value(pin, (ROOT / pin.document).read_text(encoding="utf-8"))
    assert int(documented) == entries["stryker-break"]["document_value"]


def test_the_committed_blocking_gate_pin_resolves_against_the_gate_surface() -> None:
    """R11.8, at the committed shape: the prose blocking claim against the record.

    The generated property above covers the row space; this asserts the one live
    ``blocking-gate`` row actually resolves against ``docs/state/GATE_SURFACE.md`` as
    committed, with the verdict recomputed here from the two files rather than taken
    from the resolver. Static reads only - ``gate_surface.py`` is not executed (I-0).
    """
    committed = {row.id: row for row in load_pins(PIN_TABLE.read_text(encoding="utf-8"))}
    pin = committed["cd-gcp-blocking-verify-steps"]
    assert pin.kind == "blocking-gate"
    assert pin.source == GATE_SURFACE
    assert pin.compare == "count"

    document = (ROOT / pin.document).read_text(encoding="utf-8")
    source = (ROOT / pin.source).read_text(encoding="utf-8")

    documented, line = documented_value(pin, document)
    claimed = COUNT_WORDS.index(documented) if documented in COUNT_WORDS else int(documented)
    distinct = tuple(dict.fromkeys(extract_source_values(pin.extractor, source)))

    result = resolve_pin_texts(pin, document, source)
    assert result.status == ("ok" if claimed == len(distinct) else "fail")
    assert f"{pin.document}:{line}" in result.detail
    assert pin.source in result.detail

    # The committed state: CLAUDE.md claims two BLOCKING verify steps and the generated
    # record shows exactly those two, each rendered once per trigger.
    assert claimed == len(distinct) == 2
    assert result.status == "ok"
    assert all("verify_live.py" in name for name in distinct)


def test_the_pending_required_job_row_resolves_against_the_declaration() -> None:
    """R14.3, at the committed shape: the ``required-job`` kind is mechanically real.

    ``mutation-fast-required-job`` sits under ``pending_pins:`` because activating it
    before task 2.17 would turn a documented, attributable gap into an unattributable
    red gate (the pin table records that reasoning). What is asserted here is that the
    row is a *resolvable* pin and not an aspiration: it validates as a ``NumericPin``,
    its extractor reads the declaration, and its verdict is the membership verdict
    recomputed from the two committed files.
    """
    raw = yaml.safe_load(PIN_TABLE.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in raw.get("pending_pins") or []}
    row = rows.get("mutation-fast-required-job")
    if row is None:  # task 2.17 landed and the row graduated into `pins:`.
        assert "mutation-fast-required-job" in {
            pin.id for pin in load_pins(PIN_TABLE.read_text(encoding="utf-8"))
        }
        return

    pin = NumericPin.model_validate(
        {key: value for key, value in row.items() if key != "activates_after"}
    )
    assert pin.kind == "required-job"
    assert pin.source == REQUIRED_CHECKS
    assert pin.compare == "string"
    assert row["activates_after"], "a pending row must name what activates it"

    document = (ROOT / pin.document).read_text(encoding="utf-8")
    source = (ROOT / pin.source).read_text(encoding="utf-8")
    declaration = yaml.safe_load(source)
    declared = tuple(entry["job"] for entry in declaration["required"])
    assert declared, "the declaration must declare a required set for the pin to resolve"

    anchor = re.compile(pin.anchor)
    hits = [line for line in document.splitlines() if anchor.search(line) is not None]
    result = resolve_pin_texts(pin, document, source)

    if len(hits) != 1:
        # The governance sentence moved. Unresolved naming the document, never a pass.
        assert result.status == "skip"
        assert pin.document in result.detail
        return

    documented, _line = documented_value(pin, document)
    assert result.status == ("ok" if documented in declared else "fail")

    if result.status == "fail":
        # The gap is attributable: the job the document calls blocking is recorded as
        # ineligible with its reason, which is why the row is pending rather than live.
        ineligible = {entry["job"]: entry for entry in declaration["ineligible"]}
        assert documented in ineligible
        assert ineligible[documented]["detail"]
        for name in declared:
            assert name in result.detail
