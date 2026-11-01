"""Property-based test for the module-liveness classification (design E3.5).

Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
baseline-consistent

    *For any* first-party module graph, every module is classified alive, tooling, test,
    seam-exempt, or dead; only modules carrying a machine-readable seam marker are exempt;
    a dead set exceeding the named baseline fails naming each module added over it;
    removing a name from the baseline while the module remains imported by no non-test
    module fails naming it; a property test whose target no non-test module imports is
    reported as validating a model; and a symbol encoding an invariant precondition or
    postcondition that only tests invoke fails naming the symbol and the invariant.

Why the property is shaped this way. Requirement 13's finding is not that dormant code is
wrong - several dormant modules are deliberate seams, and two of them are the honest
predicates that would close Requirements 2 and 5. The finding is that property counts and
test counts are cited as capability evidence *without distinguishing "verified and
reachable" from "verified and dormant"*. A gate that draws that line is only worth
anything if it draws it over **every** module: a classifier that silently omitted what it
could not decide would satisfy every naming obligation below and still license the exact
claim the audit charges. So the load-bearing statement here is totality, and it is
quantified over a synthesised fact space rather than over the shapes the tree happens to
have today.

Four separate claims carry the property:

1. **The five classes partition any fact set** (R13.1). Cardinality, disjointness, and
   membership are each recomputed from an independently written cascade
   (:func:`expected_class`), so the test compares two implementations rather than one. A
   duplicated path is rejected as a broken partition, and the *empty* fact set is rejected
   too: a scan that found nothing has nothing to partition, and vacuous totality would
   read as a pass over zero evidence (I-7).
2. **The in-source marker is the only exemption, and it must parse** (R13.2). Markers are
   extracted by the subject from *real files* written to a temporary directory, so what is
   exercised is the tokenised comment scan - not a restatement of the regex. A malformed
   marker exempts nothing and is itself a finding; the same text in a docstring or a string
   literal is prose and yields no marker at all; a marker on a reachable module is inert
   and reported as inert rather than silently decorative.
3. **The named baseline fixes a count and can never over-permit** (R13.9). A name never
   changes a module's class. A committed name whose module has become reachable is
   *reported* (and never punished - discharging the obligation must not fail the gate),
   and dropping a name while its module is still dormant fails naming that module.
4. **Both projections fire on the shapes they describe** (R13.3, R13.7). The R13.7
   projection FAILs naming the symbol **and** the invariant text it encodes, from both of
   its subject sources - a ``deal`` contract discovered mechanically, and a declared
   baseline row whose reachability is recomputed from the graph rather than trusted from
   the record. The R13.3 projection reports the *symbol* when the target module is
   production-reachable and the *module* when nothing outside tests imports it, which is
   the distinction that keeps ``virtual-window.ts`` from being a false positive.

**I-0 routing.** Nothing here executes the gate over the repository tree: a full tree walk
per generated example is exactly the local-compute problem
``.kiro/steering/local-compute-budget.md`` forbids. Every generated example drives the
module's pure seams (``classify_facts``, ``judge_against_baseline``,
``ReferrerIndex.from_edges``, ``judge_invariant_symbols``) or parses a handful of small
files inside a ``tempfile.TemporaryDirectory`` that is removed on the way out. No
synthesised module is ever imported - it is parsed. One test reads the *committed*
baseline, which is the only way to confirm that ``baseline:`` is the projection of its own
names and that C44 is registered so the gate can bite. No test carries ``@pytest.mark.slow``
because no test needs a runner: this file is pure data and AST work.

Strategies are local rather than in ``tests/verify/strategies.py``, following Property 30's
precedent (``test_actuation_classification_property.py``): nothing in the shared module
models a module graph, a seam marker, or a symbol-reachability edge set, and a generator
used by one property is clearer beside it.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

One note on the subject, recorded because it is load-bearing for the last clause of the
property: ``_assert_total`` previously accepted the empty module set, so an empty scan
produced a PASS over no evidence. That is the shape I-7 refuses, and the shape
``agency_truth.evaluate_actuation([])`` already reports ``unavailable``. A guard was added
there so the empty set raises ``ClassificationError``, which ``evaluate`` already maps to
``UNAVAILABLE`` (exit 2).

**Validates: Requirements 13.1, 13.2, 13.3, 13.7, 13.9**
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import module_liveness as ml
from scripts.audit import registry_gate
from scripts.audit.module_liveness import (
    ADR_ID_RE,
    CLASS_ORDER,
    CONTRACT_DECORATORS,
    DEAD_BASELINE,
    DEAD_MODULES_FILE,
    WHOLE_MODULE,
    ClassificationError,
    Clause,
    DeadModulesBaseline,
    DormantRecord,
    InvariantSymbol,
    LivenessClass,
    ModuleFacts,
    Outcome,
    ReferrerIndex,
    SeamMarker,
    Unavailable,
    classify_facts,
    declared_invariant_symbols,
    find_contract_symbols,
    judge_against_baseline,
    judge_invariant_symbols,
    load_baseline,
    scan_seam_markers,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from scripts.audit.module_liveness import BaselineVerdict

# ---------------------------------------------------------------------------
# The synthesised module space
# ---------------------------------------------------------------------------

#: Repo-relative module paths the generated fact sets draw from. Shaped like the real
#: tree's so a generated path is indistinguishable from a scanned one to the code under
#: test, and deliberately including a name this repository has never had - the property is
#: a claim about any module graph, not about today's.
_MODULE_PATHS: Final[tuple[str, ...]] = (
    "orchestrator/consensus/protocol.py",
    "orchestrator/guardrails/rules.py",
    "orchestrator/audit/anchorer.py",
    "agents/pricing_oracle/a2a/handler.py",
    "agents/demand_prophet/inference/serve.py",
    "api/routers/firehose.py",
    "digital_twin/world/runtime.py",
    "packages/synapse_common/contracts.py",
    "data_fabric/etl/backfill.py",
    "ml_pipelines/ab_test/runner.py",
    "scripts/audit/module_liveness.py",
    "orchestrator/tests/test_deal_contracts.py",
    "a_module_this_repository_has_never_had.py",
)

#: Names a baseline can carry for a module that is not in the graph at all. Both are real
#: removals recorded in ``infrastructure/quality/dead-modules.yaml``'s header, so the
#: "named but no longer dormant" case is generated from history rather than invented.
_PHANTOM_PATHS: Final[tuple[str, ...]] = (
    "api/workers/celery_app.py",
    "api/routers/demo.py",
)

#: Seam-marker justifications: ASCII, comma-free and paren-free, so the bare (unquoted)
#: marker form stays parseable and the property is about the marker rule, not quoting.
_SEAM_REASONS: Final[tuple[str, ...]] = (
    "deliberate future seam",
    "kept for the recovery path",
    "wired by the next sprint",
)

#: ADR ids a marker can carry, well-formed and not. ``ADR_ID_RE`` decides which is which.
_ADR_IDS: Final[tuple[str, ...]] = ("ADR-036", "ADR-047", "ADR-47", "047", "adr-047", "")

#: Details a marker can carry. Drawn independently of ``valid`` on purpose (see below).
_MARKER_DETAILS: Final[tuple[str, ...]] = (
    "",
    "empty reason",
    "adr 'ADR-47' is not of the form ADR-0NN",
)

#: Non-test modules a symbol can be invoked from, and the test modules that are not
#: credit. Disjoint by construction, so a generated caller is one or the other.
_PRODUCTION_MODULES: Final[tuple[str, ...]] = (
    "orchestrator/consensus/protocol.py",
    "scripts/audit/uplift_truth.py",
    "api/routers/decisions.py",
)
_TEST_MODULES: Final[tuple[str, ...]] = (
    "tests/dbc/test_guardrails_contracts.py",
    "orchestrator/tests/test_deal_contracts.py",
    "tests/uplift/test_uplift_floor_data_gate.py",
)

#: R13.7 subjects, shaped like the three the audit traced.
_INVARIANT_SYMBOLS: Final[tuple[str, ...]] = (
    "synapse_common.contracts.validate_audit_insertion",
    "orchestrator.guardrails.rules.execute_consensus",
    "uplift.uplift_floor.is_proven_uplift",
)

#: The invariant text a FAIL must name beside the symbol. No quotes, so the text can be
#: embedded verbatim in a generated ``message=`` keyword.
_INVARIANT_TEXTS: Final[tuple[str, ...]] = (
    "I-4 -- an audit row is only ever appended",
    "I-5 -- dispatch requires the confidence gate",
    "R2.4 -- the gate verdict must derive from this predicate",
)

#: Frontend bindings the R13.3 projection attributes per symbol.
_FRONTEND_BINDINGS: Final[tuple[str, ...]] = (
    "computeWindow",
    "ROW_OVERSCAN",
    "reconcile",
    "backoffDelay",
)


def expected_class(fact: ModuleFacts) -> LivenessClass:
    """The class design E3.5's cascade mandates, written out rather than imported.

    First match wins, deliberately restated so the test compares two implementations:

    1. reachable from a live entrypoint          -> ``ALIVE``
    2. a test module by path/filename convention -> ``TEST``
    3. reachable from tooling or referenced by it-> ``TOOLING``
    4. carries at least one VALID seam marker    -> ``SEAM_EXEMPT`` (R13.2)
    5. otherwise                                 -> ``DEAD``

    Clause 4 sits below clauses 1-3 on purpose: R13.2 exempts a module that would
    otherwise be dead, so a marker on a reachable module can only ever be inert.
    """
    if fact.alive:
        return LivenessClass.ALIVE
    if fact.test:
        return LivenessClass.TEST
    if fact.tooling:
        return LivenessClass.TOOLING
    if any(marker.valid for marker in fact.markers):
        return LivenessClass.SEAM_EXEMPT
    return LivenessClass.DEAD


def clauses_of(verdict: BaselineVerdict) -> frozenset[Clause]:
    """The clauses a verdict raised, so a failure names its own rule."""
    return frozenset(finding.clause for finding in verdict.findings)


def baseline_naming(paths: Sequence[str], *, recorded: int | None) -> DeadModulesBaseline:
    """A named baseline over ``paths``, with ``baseline:`` committed as ``recorded``.

    ``recorded`` is passed rather than derived so the R13.9 agreement clause - the
    committed key must equal ``len(dormant)`` - has a way to be violated.
    """
    return DeadModulesBaseline(
        version=1,
        dormant=tuple(
            DormantRecord(path=path, since="2026-01-01", rationale="synthesised")
            for path in paths
        ),
        baseline=recorded,
    )


@st.composite
def seam_marker_records(
    draw: st.DrawFn,
    path: str,
    *,
    allow_valid: bool = True,
) -> tuple[SeamMarker, ...]:
    """Markers already extracted from a module's comments, valid and not.

    ``valid`` is drawn independently of ``reason`` and ``adr``, so combinations the real
    parser cannot emit (a valid marker beside a malformed ADR id) are admitted:
    the classification's totality is a claim about its *input space*, not about the inputs
    that arise today. Parser fidelity is a separate claim, asserted over real files in
    :func:`test_only_a_wellformed_in_source_marker_exempts_a_dormant_module`.

    Lines are unique per module so a marker can be identified by ``(path, line)`` after
    the classification resolves it.
    """
    lines = draw(st.lists(st.integers(min_value=1, max_value=200), unique=True, max_size=2))
    markers: list[SeamMarker] = []
    for line in sorted(lines):
        markers.append(
            SeamMarker(
                path=path,
                line=line,
                reason=draw(st.sampled_from(_SEAM_REASONS)),
                adr=draw(st.sampled_from(_ADR_IDS)),
                valid=False if not allow_valid else draw(st.booleans()),
                detail=draw(st.sampled_from(_MARKER_DETAILS)),
            )
        )
    return tuple(markers)


@st.composite
def module_facts(
    draw: st.DrawFn,
    *,
    path: str | None = None,
    dormant: bool = False,
) -> ModuleFacts:
    """One module's gathered facts, drawn over the whole field space.

    Every reachability flag is drawn independently, so no clause of the cascade is
    unreachable by construction and combinations the real gather cannot produce (alive and
    tooling at once) are still classified - which is what totality means.

    ``dormant=True`` pins the module into the DEAD class: no reachability of any kind and
    no valid marker. The baseline clauses need a dead module to exist.
    """
    chosen = path if path is not None else draw(st.sampled_from(_MODULE_PATHS))
    alive = False if dormant else draw(st.booleans())
    test = False if dormant else draw(st.booleans())
    tooling = False if dormant else draw(st.booleans())
    return ModuleFacts(
        path=chosen,
        dotted=draw(st.none() | st.just(chosen.removesuffix(".py").replace("/", "."))),
        loc=draw(st.integers(min_value=0, max_value=1200)),
        alive=alive,
        test=test,
        tooling=tooling,
        markers=draw(seam_marker_records(chosen, allow_valid=not dormant)),
    )


@st.composite
def module_fact_sets(
    draw: st.DrawFn,
    *,
    min_size: int = 1,
    max_size: int = 6,
    dormant_min: int = 0,
) -> tuple[ModuleFacts, ...]:
    """A scan of the tree: one fact per distinct module path.

    Distinct paths because that is the scan's own contract - one record per file. A
    duplicate is a defect injected deliberately (see the duplicate test) rather than a
    background condition every example carries.
    """
    paths = draw(
        st.lists(
            st.sampled_from(_MODULE_PATHS),
            min_size=max(min_size, dormant_min),
            max_size=max_size,
            unique=True,
        )
    )
    facts = [draw(module_facts(path=path)) for path in paths]
    for index in range(dormant_min):
        facts[index] = draw(module_facts(path=paths[index], dormant=True))
    return tuple(facts)


# ---------------------------------------------------------------------------
# Synthesised source files: seam markers, and one deal contract
# ---------------------------------------------------------------------------

#: How a generated marker is spelled, and whether that spelling exempts anything.
#: ``detail_hint`` is the substring the subject must give as its reason for rejecting a
#: marker, so a malformed marker is not merely rejected but *explained*.
_MARKER_MODES: Final[tuple[tuple[str, bool, str], ...]] = (
    ("quoted", True, ""),
    ("bare", True, ""),
    ("spaced", True, ""),
    ("empty_reason", False, "empty reason"),
    ("blank_reason", False, "empty reason"),
    ("adr_two_digits", False, "adr"),
    ("adr_no_prefix", False, "adr"),
    ("adr_lowercase", False, "adr"),
    ("adr_missing", False, "does not parse"),
    ("no_arguments", False, "does not parse"),
    ("swapped", False, "does not parse"),
)

#: Where the marker text is written. Only a real ``#`` comment is a marker; the same text
#: in a docstring or a string literal is prose, and the subject tokenises rather than
#: line-matches precisely so prose cannot exempt anything.
_MARKER_CARRIERS: Final[tuple[str, ...]] = ("own_line", "inline", "docstring", "string")


@dataclass(frozen=True)
class MarkerCase:
    """One spelling of a seam marker, in one carrier, with its ground truth."""

    mode: str
    carrier: str
    reason: str
    adr: str
    body: str
    well_formed: bool
    detail_hint: str

    @property
    def is_comment(self) -> bool:
        return self.carrier in ("own_line", "inline")

    @property
    def marker_count(self) -> int:
        """Markers the subject must find: a comment carries one, prose carries none."""
        return 1 if self.is_comment else 0

    @property
    def exempts(self) -> bool:
        """Whether a dormant module carrying this would be ``SEAM_EXEMPT``."""
        return self.is_comment and self.well_formed


def _marker_body(mode: str, reason: str, adr: str) -> str:
    """The marker text as written, for one spelling."""
    if mode == "quoted":
        return f'synapse: seam(reason="{reason}", adr="{adr}")'
    if mode == "bare":
        return f"synapse: seam(reason={reason}, adr={adr})"
    if mode == "spaced":
        return f'synapse:  seam ( reason = "{reason}" , adr = "{adr}" )'
    if mode == "empty_reason":
        return f'synapse: seam(reason="", adr="{adr}")'
    if mode == "blank_reason":
        return f'synapse: seam(reason="   ", adr="{adr}")'
    if mode in ("adr_two_digits", "adr_no_prefix", "adr_lowercase"):
        return f'synapse: seam(reason="{reason}", adr="{adr}")'
    if mode == "adr_missing":
        return f'synapse: seam(reason="{reason}")'
    if mode == "no_arguments":
        return "synapse: seam()"
    if mode == "swapped":
        return f'synapse: seam(adr="{adr}", reason="{reason}")'
    raise AssertionError(f"unknown marker mode: {mode}")  # pragma: no cover


def _adr_for(mode: str) -> st.SearchStrategy[str]:
    """The ADR id a mode needs: well-formed unless the mode is about the id itself."""
    if mode == "adr_two_digits":
        return st.just("ADR-47")
    if mode == "adr_no_prefix":
        return st.just("047")
    if mode == "adr_lowercase":
        return st.just("adr-047")
    return st.sampled_from(("ADR-036", "ADR-047"))


@st.composite
def marker_cases(draw: st.DrawFn) -> MarkerCase:
    """One (spelling, carrier) pair over the whole marker space."""
    mode, well_formed, detail_hint = draw(st.sampled_from(_MARKER_MODES))
    reason = draw(st.sampled_from(_SEAM_REASONS))
    adr = draw(_adr_for(mode))
    return MarkerCase(
        mode=mode,
        carrier=draw(st.sampled_from(_MARKER_CARRIERS)),
        reason=reason,
        adr=adr,
        body=_marker_body(mode, reason, adr),
        well_formed=well_formed,
        detail_hint=detail_hint,
    )


def render_marked_module(case: MarkerCase) -> str:
    """A small module carrying ``case``'s marker text in ``case``'s carrier."""
    docstring = '"""A synthesised module for the seam-marker property."""'
    body_line = "VALUE = 1"
    extra: list[str] = []
    if case.carrier == "own_line":
        extra.append(f"# {case.body}")
    elif case.carrier == "inline":
        body_line = f"VALUE = 1  # {case.body}"
    elif case.carrier == "string":
        extra.append(f"SEAM_FORM = '# {case.body}'")
    else:  # docstring: prose that quotes the form without carrying it
        docstring = f'"""Prose quoting the form # {case.body} without carrying it."""'
    return "\n".join(
        [
            docstring,
            "",
            *extra,
            body_line,
            "",
            "",
            "def value() -> int:",
            "    return VALUE",
            "",
        ]
    )


def markers_of(case: MarkerCase, *, path: str) -> tuple[SeamMarker, ...]:
    """Extract ``case``'s markers with the subject, from a real file it reads itself.

    The file is written into a throwaway directory and removed on the way out, so no
    example leaves anything behind (I-0). The extracted markers are re-pathed onto the
    repo-relative ``path`` the fact set uses, so a finding names the module a reader would
    look for rather than a temporary directory.
    """
    with tempfile.TemporaryDirectory(prefix="module-liveness-seam-") as tmp:
        source = Path(tmp) / "synthetic_seam.py"
        source.write_text(render_marked_module(case), encoding="utf-8")
        found = scan_seam_markers(source)
    return tuple(marker.model_copy(update={"path": path}) for marker in found)


def render_contract_module(kind: str, message: str, function: str) -> str:
    """A module whose function carries one ``deal`` contract naming its invariant."""
    return "\n".join(
        [
            '"""A synthesised module carrying one deal contract."""',
            "",
            "import deal",
            "",
            "",
            f'@deal.{kind}(lambda value: value >= 0, message="{message}")',
            f"def {function}(value: int) -> int:",
            "    return value",
            "",
        ]
    )


def contract_symbols_of(kind: str, message: str, function: str) -> tuple[InvariantSymbol, ...]:
    """Run the mechanical R13.7 subject discovery over one synthesised module.

    The module is parsed, never imported - ``deal`` is not called and no contract is
    evaluated, so this stays a static read (I-0).
    """
    with tempfile.TemporaryDirectory(prefix="module-liveness-contract-") as tmp:
        source = Path(tmp) / "synthetic_contract.py"
        source.write_text(render_contract_module(kind, message, function), encoding="utf-8")
        return find_contract_symbols((source,))


# ---------------------------------------------------------------------------
# Symbol-level reachability, driven from generated edges
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReachabilityCase:
    """One R13.7 subject, its recorded caller count, and who actually refers to it."""

    symbol: str
    invariant: str
    recorded: int | None
    production: tuple[str, ...]
    tests: tuple[str, ...]
    style: str

    @property
    def drifts(self) -> bool:
        """The record claims callers the graph does not have (``ratchet_truth`` precedent)."""
        return not self.production and self.recorded is not None and self.recorded > 0

    def index(self) -> ReferrerIndex:
        """A referrer index over generated edges - no file is read."""
        module, _, name = self.symbol.rpartition(".")
        edges: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
        for path in (*self.production, *self.tests):
            if self.style == "from-import":
                edges[path] = (frozenset({module, self.symbol}), frozenset())
            else:  # `import module` + `module.name` attribute access
                edges[path] = (frozenset({module}), frozenset({name}))
        return ReferrerIndex.from_edges(edges, tests=self.tests)

    def declared(self) -> InvariantSymbol:
        """The subject as the named baseline declares it (never as an allowlist)."""
        return InvariantSymbol(
            symbol=self.symbol,
            invariant=self.invariant,
            source="declared",
            defined_in=None,
            recorded_callers=self.recorded,
            wired_by=None,
        )


@st.composite
def reachability_cases(draw: st.DrawFn) -> ReachabilityCase:
    """A subject paired with an arbitrary referrer set and an arbitrary record."""
    return ReachabilityCase(
        symbol=draw(st.sampled_from(_INVARIANT_SYMBOLS)),
        invariant=draw(st.sampled_from(_INVARIANT_TEXTS)),
        recorded=draw(st.none() | st.integers(min_value=0, max_value=3)),
        production=tuple(
            draw(st.lists(st.sampled_from(_PRODUCTION_MODULES), unique=True, max_size=2))
        ),
        tests=tuple(draw(st.lists(st.sampled_from(_TEST_MODULES), unique=True, max_size=2))),
        style=draw(st.sampled_from(("from-import", "attribute"))),
    )


# ---------------------------------------------------------------------------
# R13.1 / R13.2 - the classification is total
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(facts=module_fact_sets())
def test_the_classification_is_total_over_any_synthesised_module_set(
    facts: tuple[ModuleFacts, ...],
) -> None:
    """R13.1, R13.2: five classes partition the scan, and nothing is dropped."""
    classification = classify_facts(facts)

    # Cardinality: one record per scanned module, in scan order.
    assert len(classification.modules) == len(facts)
    assert tuple(record.path for record in classification.modules) == tuple(
        fact.path for fact in facts
    )

    buckets = {liveness: classification.of(liveness) for liveness in CLASS_ORDER}
    assert set(buckets) == set(LivenessClass)
    assert sum(len(members) for members in buckets.values()) == len(facts)

    by_path = {record.path: record for record in classification.modules}
    for fact in facts:
        record = by_path[fact.path]
        # Exactly one class, and the class the declared cascade mandates.
        assert record.liveness is expected_class(fact)
        landed = [
            liveness
            for liveness, members in buckets.items()
            if any(member.path == fact.path for member in members)
        ]
        assert landed == [record.liveness], f"{fact.path} is in {len(landed)} classes"
        # The record echoes the facts it rests on rather than re-deriving them.
        assert record.dotted == fact.dotted
        assert record.loc == fact.loc

    # The counts and line totals are projections of that one partition, not an
    # independent tally that could disagree with it.
    assert classification.counts == {
        liveness.value: len(buckets[liveness]) for liveness in CLASS_ORDER
    }
    assert sum(classification.counts.values()) == classification.total == len(facts)
    assert classification.lines == {
        liveness.value: sum(member.loc for member in buckets[liveness])
        for liveness in CLASS_ORDER
    }

    # Dormancy is DEAD plus SEAM_EXEMPT: a marker exempts a module from the FAIL, it does
    # not make the module reachable. R13.9 measures a dropped name against this set.
    assert classification.dead_paths == tuple(
        fact.path for fact in facts if expected_class(fact) is LivenessClass.DEAD
    )
    assert classification.unreachable_paths == frozenset(
        fact.path
        for fact in facts
        if expected_class(fact) in (LivenessClass.DEAD, LivenessClass.SEAM_EXEMPT)
    )

    # A function of its input: the seam reads no file and holds no state.
    assert classify_facts(facts) == classification


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(facts=module_fact_sets())
def test_a_seam_marker_is_effective_only_where_it_exempts_and_visible_everywhere_else(
    facts: tuple[ModuleFacts, ...],
) -> None:
    """R13.2: the marker is the only exemption, and a stale marker is never silent."""
    classification = classify_facts(facts)
    by_path = {record.path: record for record in classification.modules}
    resolved = {(marker.path, marker.line): marker for marker in classification.markers}

    # Every marker found anywhere is reported - the inert and the malformed included.
    assert len(resolved) == len(classification.markers)
    assert len(resolved) == sum(len(fact.markers) for fact in facts)

    for fact in facts:
        record = by_path[fact.path]
        exempted = record.liveness is LivenessClass.SEAM_EXEMPT
        for marker in fact.markers:
            got = resolved[(marker.path, marker.line)]
            assert got.valid is marker.valid
            # Effective iff the marker is what kept the module out of the dead set.
            assert got.effective is (exempted and marker.valid)
            if not exempted:
                # Reported as inert rather than silently decorative, so a marker on a
                # reachable module is visible to a reader.
                assert not got.effective
                assert got.detail

        # The record's seam is the first VALID marker, or nothing at all: a malformed
        # marker never becomes the justification of record.
        first_valid = next((marker for marker in fact.markers if marker.valid), None)
        assert (record.seam is None) is (first_valid is None)
        if first_valid is not None and record.seam is not None:
            assert record.seam.line == first_valid.line
            assert record.seam.valid

        # And the exemption is exactly "would be dead, and carries a valid marker".
        assert exempted is (
            not fact.alive
            and not fact.test
            and not fact.tooling
            and any(marker.valid for marker in fact.markers)
        )


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(case=marker_cases(), dormant=st.booleans())
def test_only_a_wellformed_in_source_marker_exempts_a_dormant_module(
    case: MarkerCase,
    dormant: bool,
) -> None:
    """R13.2: the marker must be a real comment and must parse, or it exempts nothing."""
    path = "orchestrator/synthetic/seam.py"
    markers = markers_of(case, path=path)

    # A comment carries a marker; the same text as prose carries none. The subject
    # tokenises rather than line-matches, which is what makes that distinction possible.
    assert len(markers) == case.marker_count
    if markers:
        marker = markers[0]
        assert marker.valid is case.well_formed
        if case.well_formed:
            assert marker.reason == case.reason
            assert marker.adr == case.adr
            assert ADR_ID_RE.match(marker.adr)
            assert not marker.detail
        else:
            # A malformed marker says why it was rejected: an unparseable justification
            # is not a justification (I-7).
            assert case.detail_hint in marker.detail

    fact = ModuleFacts(
        path=path,
        dotted="orchestrator.synthetic.seam",
        loc=12,
        alive=not dormant,
        test=False,
        tooling=False,
        markers=markers,
    )
    record = classify_facts((fact,)).modules[0]

    if dormant:
        assert record.liveness is (
            LivenessClass.SEAM_EXEMPT if case.exempts else LivenessClass.DEAD
        )
    else:
        # A marker on a reachable module changes nothing: R13.2 exempts a module that
        # would otherwise be dead.
        assert record.liveness is LivenessClass.ALIVE


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(case=marker_cases())
def test_a_malformed_marker_is_a_finding_no_baseline_name_can_suppress(
    case: MarkerCase,
) -> None:
    """R13.2 / I-7: a marker that does not parse fails, and a name does not excuse it."""
    path = "orchestrator/synthetic/seam.py"
    markers = markers_of(case, path=path)
    fact = ModuleFacts(path=path, dotted=None, loc=9, markers=markers)
    classification = classify_facts((fact,))

    # Named in the baseline AND recorded consistently, so the only clause left that can
    # fire is the marker one.
    verdict = judge_against_baseline(classification, baseline_naming((path,), recorded=1))

    malformed = tuple(marker for marker in classification.markers if not marker.valid)
    assert (Clause.SEAM_MARKER in clauses_of(verdict)) is bool(malformed)
    if malformed:
        finding = next(f for f in verdict.findings if f.clause is Clause.SEAM_MARKER)
        for marker in malformed[:5]:
            assert f"{marker.path}:{marker.line}" in finding.detail
        assert "exempt" in finding.detail
    else:
        assert not verdict.findings


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(fact=module_facts())
def test_a_repeated_path_breaks_the_partition_and_yields_no_verdict(
    fact: ModuleFacts,
) -> None:
    """R13.1 / I-7: a partition that does not partition can never read as a pass."""
    with pytest.raises(ClassificationError) as raised:
        classify_facts((fact, fact))

    message = str(raised.value)
    assert "disjoint" in message
    assert fact.path in message


def test_an_empty_module_set_is_unavailable_rather_than_a_pass() -> None:
    """I-7: an empty scan has nothing to partition, so it proves nothing.

    ``evaluate`` maps :class:`ClassificationError` to ``UNAVAILABLE`` (exit 2), so this is
    the pure-seam statement of "vacuous totality is not a pass". The same discipline as
    ``agency_truth.evaluate_actuation([])``, which reports ``unavailable`` on an empty
    sweep.
    """
    with pytest.raises(ClassificationError) as raised:
        classify_facts(())
    assert "never a pass" in str(raised.value)

    # The other absent input is the baseline itself, and it is unavailable on every
    # unreadable shape rather than defaulting to a number.
    with tempfile.TemporaryDirectory(prefix="module-liveness-baseline-") as tmp:
        path = Path(tmp) / "dead-modules.yaml"
        with pytest.raises(Unavailable):
            load_baseline(path)

        path.write_text("dormant: [\n", encoding="utf-8")
        with pytest.raises(Unavailable):
            load_baseline(path)

        path.write_text("- not: a mapping\n", encoding="utf-8")
        with pytest.raises(Unavailable):
            load_baseline(path)

        path.write_text("version: 1\nbaseline: not-a-number\n", encoding="utf-8")
        with pytest.raises(Unavailable):
            load_baseline(path)


# ---------------------------------------------------------------------------
# R13.9 - the named baseline fixes a count and cannot over-permit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaselineCase:
    """A generated scan paired with a generated baseline over (and beyond) it."""

    facts: tuple[ModuleFacts, ...]
    named: tuple[str, ...]
    recorded: int | None


@st.composite
def baseline_cases(draw: st.DrawFn) -> BaselineCase:
    """A scan, an arbitrary set of dormant names, and an arbitrary committed count.

    Names are drawn from the whole scanned set plus paths that are not in the graph at
    all, so a stale name, a name for a live module, and a name for a module that no longer
    exists are all reachable - each of which R13.9 must *report* rather than accept.
    """
    facts = draw(module_fact_sets())
    candidates = [*(fact.path for fact in facts), *_PHANTOM_PATHS]
    named = tuple(
        draw(st.lists(st.sampled_from(candidates), unique=True, max_size=len(candidates)))
    )
    recorded = draw(
        st.one_of(st.none(), st.just(len(named)), st.integers(min_value=0, max_value=6))
    )
    return BaselineCase(facts=facts, named=named, recorded=recorded)


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(case=baseline_cases())
def test_the_named_baseline_fixes_a_count_and_can_never_over_permit(
    case: BaselineCase,
) -> None:
    """R13.9, R13.1: the count is a projection of the names, and a name grants nothing."""
    classification = classify_facts(case.facts)
    baseline = baseline_naming(case.named, recorded=case.recorded)
    verdict = judge_against_baseline(classification, baseline)

    # The baseline is `len(dormant)`, never an independent number.
    assert verdict.dead_baseline == baseline.derived_baseline == len(case.named)
    assert verdict.recorded_baseline == case.recorded

    dead = classification.dead_paths
    named = set(case.named)
    expected_orphans = tuple(path for path in dead if path not in named)
    assert verdict.new_orphans == expected_orphans
    assert verdict.dropped_dormant == (
        expected_orphans if len(case.named) < len(dead) else ()
    )

    # A committed name whose module is no longer dormant is REPORTED, so the baseline
    # cannot silently over-permit; and being resolved is never itself a finding.
    assert verdict.resolved_dormant == tuple(
        path for path in baseline.dormant_paths if path not in classification.unreachable_paths
    )
    for path in verdict.resolved_dormant:
        assert path not in classification.unreachable_paths

    expected_clauses: set[Clause] = set()
    if case.recorded is not None and case.recorded != len(case.named):
        expected_clauses.add(Clause.BASELINE_DRIFT)
    if expected_orphans:
        expected_clauses.add(Clause.NEW_ORPHAN)
    if verdict.dropped_dormant:
        expected_clauses.add(Clause.BASELINE_DROP)
    if any(not marker.valid for marker in classification.markers):
        expected_clauses.add(Clause.SEAM_MARKER)
    assert clauses_of(verdict) == expected_clauses

    # Naming a module never changes its class: the classification is decided before any
    # baseline is consulted, which is what makes the name a count and not a suppression.
    assert classify_facts(case.facts).dead_paths == dead

    # Every finding names its own subjects, so a reader can act on it without the gate.
    for finding in verdict.findings:
        assert finding.detail
        if finding.clause is Clause.NEW_ORPHAN:
            for path in expected_orphans[:8]:
                assert path in finding.detail
        elif finding.clause is Clause.BASELINE_DROP:
            for path in verdict.dropped_dormant[:8]:
                assert path in finding.detail
        elif finding.clause is Clause.BASELINE_DRIFT:
            assert str(case.recorded) in finding.detail


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(facts=module_fact_sets(dormant_min=1))
def test_dropping_a_name_while_the_module_is_still_dormant_fails_naming_it(
    facts: tuple[ModuleFacts, ...],
) -> None:
    """R13.9: the baseline is not a place a dormant module can be quietly forgotten."""
    classification = classify_facts(facts)
    dead = classification.dead_paths
    assert dead, "the fact set is generated with at least one dormant module"

    honest = judge_against_baseline(classification, baseline_naming(dead, recorded=len(dead)))
    assert not honest.new_orphans
    assert not honest.dropped_dormant
    assert Clause.NEW_ORPHAN not in clauses_of(honest)
    assert Clause.BASELINE_DROP not in clauses_of(honest)
    assert Clause.BASELINE_DRIFT not in clauses_of(honest)

    for dropped in dead:
        kept = tuple(path for path in dead if path != dropped)
        after = judge_against_baseline(
            classification, baseline_naming(kept, recorded=len(kept))
        )

        assert dropped in after.new_orphans
        assert dropped in after.dropped_dormant
        assert Clause.BASELINE_DROP in clauses_of(after)
        finding = next(f for f in after.findings if f.clause is Clause.BASELINE_DROP)
        assert dropped in finding.detail

        # Removing the name never made the module reachable - it is still dead, which is
        # exactly why the removal is the failure.
        assert dropped in classification.dead_paths
        assert dropped in classification.unreachable_paths


# ---------------------------------------------------------------------------
# R13.7 - a symbol encoding an invariant that only tests invoke
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(case=reachability_cases())
def test_an_invariant_symbol_only_tests_invoke_fails_naming_symbol_and_invariant(
    case: ReachabilityCase,
) -> None:
    """R13.7: reachability is recomputed from the graph, never trusted from the record."""
    rows = judge_invariant_symbols((case.declared(),), case.index())
    assert len(rows) == 1
    row = rows[0]

    assert row.symbol == case.symbol
    assert row.invariant == case.invariant
    assert row.production_callers == tuple(sorted(case.production))
    assert row.test_callers == tuple(sorted(case.tests))
    assert row.recorded_callers == case.recorded

    # Total over two outcomes, each with a reason. Nothing is ever left unjudged.
    assert row.outcome in (Outcome.PASS, Outcome.FAIL)
    assert row.detail

    if case.production and not case.drifts:
        assert row.outcome is Outcome.PASS
        assert not row.record_drift
        # Landing the production caller discharges the obligation; a stale `0` in the
        # record is a maintenance line, never a punishment.
        assert row.resolved is (case.recorded == 0)
    else:
        assert row.outcome is Outcome.FAIL
        assert row.record_drift is case.drifts
        # The FAIL names the symbol AND the invariant it encodes - that pairing is the
        # whole of R13.7's obligation.
        assert case.symbol in row.detail
        assert case.invariant in row.detail
        if case.drifts:
            assert str(case.recorded) in row.detail
        elif not case.tests:
            assert "no caller at all" in row.detail

    # The single variable that moves the verdict is a non-test caller: same record, one
    # production referrer added, and the obligation is discharged.
    wired = ReachabilityCase(
        symbol=case.symbol,
        invariant=case.invariant,
        recorded=case.recorded,
        production=(_PRODUCTION_MODULES[0],),
        tests=case.tests,
        style=case.style,
    )
    assert judge_invariant_symbols((wired.declared(),), wired.index())[0].outcome is Outcome.PASS


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(
    kind=st.sampled_from(CONTRACT_DECORATORS),
    message=st.sampled_from(_INVARIANT_TEXTS),
    function=st.sampled_from(("enforce_bound", "validate_audit_insertion", "execute_consensus")),
)
def test_a_deal_contract_is_detected_mechanically_and_carries_its_invariant_text(
    kind: str,
    message: str,
    function: str,
) -> None:
    """R13.7: the subject set is derived from the tree, so a new contract lands at once."""
    symbols = contract_symbols_of(kind, message, function)
    assert len(symbols) == 1
    symbol = symbols[0]

    assert symbol.symbol.endswith(f".{function}")
    assert symbol.source == "contract-decorator"
    assert symbol.defined_in is not None
    assert symbol.defined_in.endswith("synthetic_contract.py")
    # The invariant text is the decorator's own `message=`, which is why a FAIL can name
    # the invariant rather than only the symbol.
    assert message in symbol.invariant
    assert f"deal.{kind}" in symbol.invariant

    test_path = "tests/verify/test_synthetic_contract_property.py"
    only_tests = ReferrerIndex.from_edges(
        {test_path: (frozenset({symbol.symbol}), frozenset())}, tests=(test_path,)
    )
    row = judge_invariant_symbols((symbol,), only_tests)[0]
    assert row.outcome is Outcome.FAIL
    assert symbol.symbol in row.detail
    assert message in row.detail
    assert row.test_callers == (test_path,)
    assert row.production_callers == ()

    live = "orchestrator/consensus/protocol.py"
    wired = ReferrerIndex.from_edges(
        {
            test_path: (frozenset({symbol.symbol}), frozenset()),
            live: (frozenset({symbol.symbol}), frozenset()),
        },
        tests=(test_path,),
    )
    discharged = judge_invariant_symbols((symbol,), wired)[0]
    assert discharged.outcome is Outcome.PASS
    assert discharged.production_callers == (live,)


def test_a_function_without_a_contract_is_not_an_invariant_subject() -> None:
    """Non-vacuity: the detector reads contracts, not decorations in general."""
    source = "\n".join(
        [
            '"""A synthesised module with a decorator that is not a contract."""',
            "",
            "import functools",
            "",
            "",
            "@functools.cache",
            "def cheap(value: int) -> int:",
            "    return value",
            "",
        ]
    )
    with tempfile.TemporaryDirectory(prefix="module-liveness-nocontract-") as tmp:
        path = Path(tmp) / "synthetic_plain.py"
        path.write_text(source, encoding="utf-8")
        assert find_contract_symbols((path,)) == ()


def test_an_intra_module_call_site_is_a_production_call_site() -> None:
    """R13.7: a contract invoked only from its own non-test module is on the path.

    ``ConsensusProtocol._append_context`` is exactly this shape. Excluding the defining
    file would report it as test-only, which is false - and a false FAIL erodes the gate
    just as surely as a false PASS.
    """
    defining = "orchestrator/consensus/protocol.py"
    symbol = InvariantSymbol(
        symbol="orchestrator.consensus.protocol._append_context",
        invariant="I-14 -- context is append-only",
        source="contract-decorator",
        defined_in=defining,
    )
    index = ReferrerIndex.from_edges(
        {defining: (frozenset(), frozenset({"_append_context"}))}
    )

    row = judge_invariant_symbols((symbol,), index)[0]
    assert row.production_callers == (defining,)
    assert row.outcome is Outcome.PASS


# ---------------------------------------------------------------------------
# R13.3 - a property test whose target no non-test module imports
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(
    top=st.sampled_from(("orchestrator", "agents", "uplift", "digital_twin")),
    tail=st.sampled_from(("synthetic_seam", "synthetic_model.bounds")),
    name=st.sampled_from(("compute_bound", "is_within_bound")),
    production_imports=st.booleans(),
)
def test_a_property_test_whose_target_no_non_test_module_imports_is_reported_as_a_model(
    top: str,
    tail: str,
    name: str,
    production_imports: bool,
) -> None:
    """R13.3: reported, and reported about the symbol the test actually exercises."""
    dotted = f"{top}.{tail}"
    symbol = f"{dotted}.{name}"
    source = "\n".join(
        [
            '"""A synthesised property test."""',
            "",
            f"from {dotted} import {name}",
            "",
            "",
            "def test_it() -> None:",
            f"    assert {name} is not None",
            "",
        ]
    )
    live = "orchestrator/consensus/protocol.py"
    edges: dict[str, tuple[frozenset[str], frozenset[str]]] = (
        {live: (frozenset({dotted, symbol}), frozenset())} if production_imports else {}
    )

    with tempfile.TemporaryDirectory(prefix="module-liveness-model-") as tmp:
        path = Path(tmp) / "test_synthetic_model_property.py"
        path.write_text(source, encoding="utf-8")
        rows = ml._python_model_projections((path,), ReferrerIndex.from_edges(edges))

    if production_imports:
        # A target the shipped code imports is not a model of anything - reporting it
        # would be the false positive R13.3 must not produce.
        assert rows == ()
        return

    assert len(rows) == 1
    row = rows[0]
    assert row.subject == symbol
    assert row.scope == "symbol"
    assert row.language == "python"
    assert row.target == dotted
    assert row.production_importers == ()
    assert symbol in row.detail
    assert "MODEL" in row.detail


# Feature: purpose-achievement-audit, Property 27: Liveness classification is total and
# baseline-consistent
@given(
    test_bindings=st.lists(
        st.sampled_from(_FRONTEND_BINDINGS), min_size=1, max_size=3, unique=True
    ).map(tuple),
    production_bindings=st.lists(
        st.sampled_from(_FRONTEND_BINDINGS), max_size=3, unique=True
    ).map(tuple),
)
def test_the_model_projection_reports_the_symbol_when_the_module_itself_is_reachable(
    test_bindings: tuple[str, ...],
    production_bindings: tuple[str, ...],
) -> None:
    """R13.3: symbol-first resolution - ``virtual-window.ts`` is not a dead module.

    Named bindings only on the production side: a namespace or default import attributes
    no single export, so it says nothing about which symbol is exercised.
    """
    live = "frontend/src/lib/synthetic-window.ts"
    dormant = "frontend/src/lib/synthetic-reconcile.ts"
    surface = "frontend/src/surfaces/operations/SyntheticSurface.tsx"
    spec = "frontend/src/lib/__tests__/synthetic-window.property.test.ts"

    modules = (
        ml._TsModule(path=live, is_test=False, edges={}),
        ml._TsModule(path=dormant, is_test=False, edges={}),
        ml._TsModule(
            path=surface,
            is_test=False,
            edges={live: production_bindings} if production_bindings else {},
        ),
        ml._TsModule(
            path=spec,
            is_test=True,
            edges={live: test_bindings, dormant: (WHOLE_MODULE,)},
        ),
    )
    rows = {row.subject: row for row in ml._frontend_model_projections(modules)}

    # Nothing outside tests imports the dormant module, so the MODULE is the subject.
    assert dormant in rows
    assert rows[dormant].scope == "module"
    assert rows[dormant].production_importers == ()
    assert "MODEL" in rows[dormant].detail

    symbol_subjects = {subject for subject in rows if subject.startswith(f"{live}::")}
    if production_bindings:
        expected = {
            f"{live}::{binding}"
            for binding in test_bindings
            if binding not in production_bindings
        }
        assert symbol_subjects == expected
        for subject in expected:
            assert rows[subject].scope == "symbol"
            assert surface in rows[subject].production_importers
            assert rows[subject].target == live
        # The reachable file is never itself reported - only the test-only symbol is.
        assert live not in rows
    else:
        assert live in rows
        assert rows[live].scope == "module"
        assert not symbol_subjects


# ---------------------------------------------------------------------------
# The committed tree, read once and statically
# ---------------------------------------------------------------------------


def test_the_committed_baseline_is_a_projection_of_its_names_and_the_gate_can_bite() -> None:
    """R13.9 / R13.3 / R13.7, as committed. No number in this test - all of them are read.

    Three facts are confirmed here and nowhere else, because they are properties of the
    repository rather than of the algorithm:

    * ``baseline:`` equals ``len(dormant)`` and ``DEAD_BASELINE`` is derived from it, so
      the count cannot be nudged independently of the names (R13.9).
    * the declared ``test_only_reachable`` obligations are recorded with an invariant each
      (R13.7) and the R13.3 rows are recorded without one - a shape distinction the two
      projections rely on.
    * the clause vocabulary gates R13.7 and does *not* gate R13.3, whose criterion says
      "SHALL be reported"; and C44 is registered, so all of it can actually bite.
    """
    baseline = load_baseline()

    assert DEAD_MODULES_FILE.is_file()
    assert DEAD_MODULES_FILE.parent.name == "quality"
    assert baseline.baseline == baseline.derived_baseline == len(baseline.dormant)
    assert DEAD_BASELINE == baseline.derived_baseline
    assert len(set(baseline.dormant_paths)) == len(baseline.dormant_paths)
    for path in baseline.dormant_paths:
        assert "\\" not in path
        assert not path.startswith("/")

    declared = declared_invariant_symbols(baseline)
    assert declared, "R13.7's recorded obligations must not silently disappear"
    for row in declared:
        assert row.invariant
        assert row.source == "declared"
        assert row.symbol
    # The R13.3 rows carry no invariant - they are labels about reachability, not
    # contracts - and at least one is recorded.
    assert any(record.invariant is None for record in baseline.test_only_reachable)

    # R13.7 has a gating clause; R13.3 has none, which is what "reported, not gating"
    # means mechanically.
    assert set(Clause) == {
        Clause.TOTALITY,
        Clause.SEAM_MARKER,
        Clause.NEW_ORPHAN,
        Clause.BASELINE_DROP,
        Clause.BASELINE_DRIFT,
        Clause.INVARIANT_SYMBOL,
        Clause.RECORD_DRIFT,
    }
    assert set(Outcome) == {Outcome.PASS, Outcome.FAIL, Outcome.REPORT, Outcome.UNAVAILABLE}

    # Registered, so the gate has a call site that can fail (R1: an unenforced check is
    # not a gate). The registry is read, not re-derived.
    assert "C44" in registry_gate.registered_ids()
