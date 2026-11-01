"""Six console per-file verdicts, one of which is a pass, and absence is not a zero.

Feature: decision-quality-proof, task 2.3. Requirements **R2.6, R2.7, R2.8, R2.9, R2.14,
R2.16**.

The property title says "five per-file verdicts". The subject now has **six**
--------------------------------------------------------------------------

The tag below is quoted verbatim from the design's property index and from the plan, and
it is left verbatim on purpose: the inventory gate matches the tag as a string, so
"correcting" it here would silently unfile the property. What the tag counts is stale.
``SuiteClassification`` carried five states when the property was named and carries six
now -- ``partially_skipped`` was added by task 2.2 once R2.14 was read as it is written,
on **any** skipped or todo case rather than on a wholly skipped file. The count is
therefore asserted mechanically below (``{executed}`` union ``FAILING_SUITE_CLASSES``
union ``UNAVAILABLE_SUITE_CLASSES`` is the whole of ``get_args(SuiteClassification)``)
rather than as a literal, so the partition stays pinned while the prose count does not
pretend to be the mechanism. Reported rather than resolved by editing either side.

The defect, and why it is narrower than "the console has no coverage"
--------------------------------------------------------------------

The machine-readable run record already existed as a *configuration*:
``frontend/vitest.config.ts`` sets ``reporters: ["default","json"]`` writing
``artifacts/test-reports/vitest.json``, and ``frontend.yml::quality`` uploads it on
success and on failure. What was missing was a **reader with an ``unavailable`` state**.

The subtlety that forced the split is this: a file that matches no ``include`` pattern,
or that throws while being collected, produces **no entry in the record at all** rather
than an entry with a zero count. Those are different facts, and a checker that asks "is
the executed count >= 1" cannot tell them apart - nor can it tell either from a file that
was deleted. So R2.8 is stated against the *record*, not against the config, and
:func:`evaluate_declared_suites` returns one of six states per declared file, of which
exactly one is a pass.

This is not a hypothetical distinction. ``baseline-measurement.property.test.ts``
(Property 36) matched the include pattern, was declared in the inventory, was tracked as
authored - and had **never executed**. ``check-baseline.ts`` resolved its roots at import
time with ``fileURLToPath(new URL("../../", import.meta.url))``, which raises
``ERR_INVALID_URL_SCHEME`` under vitest because Vite serves imported modules from an
``http:`` origin. The suite died during collection and reported "0 test". Existence,
declaration, and a green-looking job were all true at once while the property had never
run. ``absent`` is the state that says so.

``no_cases`` is the other half of that distinction and it needs a second input
------------------------------------------------------------------------------

``absent`` and ``no_cases`` cannot both be decided from the reported cases, because a
record block whose case list is empty yields **no case**: from the cases alone, a file the
runner collected and reported nothing for is indistinguishable from a file the record
never mentioned. So the subject takes the record's own **file listing** as a separate
keyword-only argument (``recorded_files``, from ``recorded_suite_files`` reading Vitest's
``testResults[].name`` and Playwright's suite/spec ``file``). It defaults to ``()``, which
resolves every caseless declaration to ``absent`` -- the weaker, safer claim -- and
:func:`test_listing_decides_only_the_caseless_declarations` states that default as a
property rather than trusting it. Before that input existed the ``no_cases`` branch was
**unreachable**, and this file did not generate the state at all; it does now.

Why the generators are shaped this way
--------------------------------------

The subject is a **pure** function of (declarations, reported cases, recorded file
listing), so the generator produces exactly those three things and nothing else - no
files, no reporter JSON, no subprocess. That is deliberate under I-0 as well as for speed:
the whole point of pushing the judgement into a pure function was that its properties can
be checked without running a browser or a test runner.

Every expected classification, every skipped title and every counterexample is decided
**by construction** from the mix the generator chose, never recomputed by a second copy of
the rule - otherwise the property would compare the implementation against itself.

Reported paths are generated in **both** spellings the runners actually emit - the
repository-relative one and the ``frontend/``-stripped one - plus an absolute one, because
``paths_match`` exists precisely to absorb that difference and a property that only ever
fed it matching spellings would not notice if it stopped absorbing them.

What would falsify these properties
-----------------------------------

* Folding ``absent`` into ``no_cases``, in either direction: the differential clause in
  :func:`test_absent_and_no_cases_are_never_conflated` fails - same declarations, same
  (empty) case list, one input apart, two different labels and two different repairs.
* Deciding ``no_cases`` from anything other than the record's listing: the same clause
  fails, and so does :func:`test_listing_decides_only_the_caseless_declarations`.
* Treating a skipped case as evidence: the ``skipped_only`` clause fails, and so does
  ``.attested``.
* Reading R2.14 as "every case skipped" rather than "any case skipped": both the
  ``partially_skipped`` arm and :func:`test_any_skipped_case_is_non_passing_and_named`
  fail. A file with four passes and one ``it.skip`` has not proven its fifth obligation,
  and only that state says so without lying in either direction.
* Counting skipped cases instead of naming them: the ``skipped_titles`` clause fails. A
  count tells a reader that something did not run and not which thing (R2.14).
* Letting a passing case outrank a failing one in the same file: the ``violated`` clause
  fails. A file with 11 passes and 1 failure has not proven its property.
* Dropping the runner's failure text, or eliding a failure the record carried no message
  for: the counterexample clause fails, which is R2.9 - a shrunk counterexample has to
  name the file, the property title and the minimal failing input, the input exists only
  in the runner's message, and an empty string would read as "no counterexample", which is
  a stronger claim than "the record did not carry one" (I-7). ``NO_FAILURE_MESSAGE`` is
  what the subject carries instead, and the pairing with ``failing_titles`` stays
  positional and exact (``strict=True`` zip semantics).
* Returning fewer verdicts than there are declarations: the ``one_verdict_each`` clause
  fails. A silently dropped declaration is how a file stops being watched.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles via ``HYPOTHESIS_PROFILE`` (``dev``=10, ``heavy``=100, ``ci``/``default``=500,
``nightly``=5000).

``frontend/spec/check_fe_invariants.py`` is loaded **by path**, the same way the sibling
example test and property test load it: it is a CI script rather than an importable
package member, and inventing a package for it would change the thing under test.

**Validates: Requirements 2.6, 2.7, 2.8, 2.9, 2.14, 2.16**
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Final, NamedTuple, get_args

from hypothesis import given
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[2]
_GATE_PATH = ROOT / "frontend" / "spec" / "check_fe_invariants.py"

_spec = importlib.util.spec_from_file_location("check_fe_invariants", _GATE_PATH)
assert _spec is not None and _spec.loader is not None
fe = importlib.util.module_from_spec(_spec)
# Registered in ``sys.modules`` BEFORE ``exec_module``, which importlib's own
# documentation recommends and which is load-bearing here rather than tidy. The gate's
# models are Pydantic classes under ``from __future__ import annotations``, so their
# field annotations are strings; Pydantic resolves a name like ``TestStatus`` by looking
# the defining module up in ``sys.modules[cls.__module__]``. A module executed without
# being registered is absent from that mapping, so on an interpreter that defers
# annotation evaluation (Python 3.14, PEP 649) every model raises
# ``PydanticUserError: `ExecutedTest` is not fully defined``. On 3.11 - which is what CI
# pins - resolution happens at class-definition time from the frame globals and the
# omission is invisible. Registering makes the loader correct on both.
sys.modules[_spec.name] = fe
_spec.loader.exec_module(fe)

#: The five declared console property files, as `fe-invariant-attestation.yaml` names
#: them. Read from the committed declaration rather than restated, so this property is
#: about the real subject and a declaration change cannot leave it testing a fiction.
_COMMITTED = fe.load_declaration(fe.DECLARATION)

#: The one passing classification. Named here so the partition below is asserted against
#: a single source of truth rather than a repeated literal.
_PASSING: Final[str] = "executed"

_ALL_CLASSIFICATIONS: Final[tuple[str, ...]] = get_args(fe.SuiteClassification)

#: The six arms the generator can put a declared file in. Every classification the subject
#: can return is reachable from this list, which is what stops a state being dead code in
#: the property the way ``no_cases`` was dead code in the subject before task 2.2.
_MIXES: Final[tuple[str, ...]] = (
    "absent",
    "no_cases",
    "executed",
    "violated",
    "partially_skipped",
    "skipped_only",
)


class _Expected(NamedTuple):
    """What the generator decided one declared file must be judged as, by construction.

    Every field is what the generator *built*, not what a second copy of the subject's
    rule would compute from it.
    """

    path: str
    classification: str
    skipped_titles: tuple[str, ...]
    failing_titles: tuple[str, ...]
    counterexamples: tuple[str, ...]


class _Scenario(NamedTuple):
    """One generated run record: the three inputs the subject takes, plus the answer."""

    declared: tuple[Any, ...]
    cases: tuple[Any, ...]
    recorded_files: tuple[str, ...]
    expected: tuple[_Expected, ...]


def _suite(path: str, number: int) -> Any:
    """One declared suite. Fields mirror the committed declaration's shape."""
    return fe.DeclaredSuite(
        path=path,
        property_number=number,
        title=f"generated property {number}",
        type_check_project="frontend/tsconfig.spec.json",
    )


def _test(
    suite_file: str,
    status: str,
    *,
    title: str = "a case",
    failure_detail: str = "",
) -> Any:
    """One reported test case, as a reporter would have emitted it."""
    return fe.ExecutedTest(
        report="artifacts/test-reports/vitest.json",
        suite_file=suite_file,
        title=title,
        status=status,
        tags=(),
        failure_detail=failure_detail,
    )


#: The two spellings a runner actually emits for the same file, plus the stripped form
#: `paths_match` has to absorb. Generated rather than fixed so the matcher is exercised
#: on both arms of the behaviour it exists for.
def _reported_spellings(declared: str) -> st.SearchStrategy[str]:
    stripped = declared[len("frontend/") :] if declared.startswith("frontend/") else declared
    return st.sampled_from((declared, stripped, f"/abs/repo/{declared}"))


@st.composite
def _scenarios(draw: st.DrawFn) -> _Scenario:
    """Declarations, reported cases, the record's file listing, and the answer.

    The expected classification is decided **by construction** from the case mix the
    generator chose, not recomputed by a second copy of the rule - otherwise the property
    would be comparing the implementation against itself.
    """
    count = draw(st.integers(min_value=1, max_value=5))
    declared = tuple(
        _suite(f"frontend/spec/effectiveness/__tests__/generated-{index}.property.test.ts", index)
        for index in range(count)
    )

    cases: list[Any] = []
    recorded: list[str] = []
    expected: list[_Expected] = []
    for suite in declared:
        mix = draw(st.sampled_from(_MIXES))
        spelling = draw(_reported_spellings(suite.path))

        if mix == "absent":
            # Not listed and no case: the record never mentioned this file. This is what a
            # collection-time throw produces, and it is the ONLY arm that leaves the
            # listing alone.
            expected.append(_Expected(suite.path, "absent", (), (), ()))
            continue

        # Every other arm is LISTED: a runner that reports a case for a file has also
        # listed it, and `no_cases` is exactly the listing without the case.
        recorded.append(spelling)
        if mix == "no_cases":
            expected.append(_Expected(suite.path, "no_cases", (), (), ()))
            continue

        passed = 0 if mix == "skipped_only" else draw(st.integers(min_value=1, max_value=4))
        failed = draw(st.integers(min_value=1, max_value=3)) if mix == "violated" else 0
        # R2.14 reads on ANY case reported skipped or todo, not only on a wholly skipped
        # file, so the `executed` arm is the one with NO skips: a file that passed four
        # cases and skipped one is `partially_skipped`, which is non-passing. The
        # `violated` arm still draws skips freely, because a failure outranks a skip and
        # that precedence is worth generating rather than assuming.
        skipped = 0
        if mix in {"partially_skipped", "skipped_only"}:
            skipped = draw(st.integers(min_value=1, max_value=3))
        elif mix == "violated":
            skipped = draw(st.integers(min_value=0, max_value=3))

        for index in range(passed):
            cases.append(_test(spelling, "passed", title=f"pass {index}"))

        failing_titles: list[str] = []
        counterexamples: list[str] = []
        for index in range(failed):
            title = f"fail {index}"
            # Half the failures carry no message. A record can report a failed case with
            # no text - a collection-level throw, a reporter that dropped it - and R2.9
            # then has no minimal failing input to name. The subject must SAY that rather
            # than emit an empty counterexample, so the expectation is built here.
            detail = f"Counterexample: [{index}]" if draw(st.booleans()) else ""
            cases.append(_test(spelling, "failed", title=title, failure_detail=detail))
            failing_titles.append(title)
            counterexamples.append(detail or fe.NO_FAILURE_MESSAGE)

        skipped_titles = tuple(f"skip {index}" for index in range(skipped))
        for title in skipped_titles:
            cases.append(_test(spelling, "skipped", title=title))

        expected.append(
            _Expected(
                suite.path,
                mix,
                skipped_titles,
                tuple(failing_titles),
                tuple(counterexamples),
            )
        )

    # Unrelated noise: cases from files nobody declared, and listings for files nobody
    # declared, must not change any verdict in either direction.
    for index in range(draw(st.integers(min_value=0, max_value=3))):
        noisy = f"frontend/src/lib/__tests__/unrelated-{index}.test.ts"
        cases.append(_test(noisy, "passed"))
        recorded.append(noisy)
        recorded.append(f"frontend/src/lib/__tests__/silent-{index}.test.ts")

    return _Scenario(declared, tuple(cases), tuple(dict.fromkeys(recorded)), tuple(expected))


def _judge(scenario: _Scenario) -> tuple[Any, ...]:
    """The subject, called with all three of its inputs. Returns verdicts in order."""
    verdicts: tuple[Any, ...] = fe.evaluate_declared_suites(
        scenario.declared, scenario.cases, recorded_files=scenario.recorded_files
    )
    return verdicts


# The feature tag below is quoted verbatim from the implementation plan; the trailing
# `noqa` is a lint directive and not part of the tag. It says "five" and the subject has
# six states - see the module docstring, where the discrepancy is recorded rather than
# resolved by editing the tag or the code.
# Feature: decision-quality-proof, Property 44: The console run record decides five per-file verdicts, and absence is non-passing  # noqa: E501
@given(_scenarios())
def test_every_declaration_gets_exactly_one_verdict_from_the_declared_partition(
    scenario: _Scenario,
) -> None:
    """R2.6: totality. One verdict per declared file, drawn from the declared states.

    The count clause is the one with teeth. A reader that silently dropped a declaration
    it could not match would report a shorter list and a clean bill, and the file would
    stop being watched without anything going red - which is the failure mode the whole
    per-file design replaces.
    """
    verdicts = _judge(scenario)

    assert len(verdicts) == len(scenario.declared), "a declaration must never be dropped"
    assert [v.path for v in verdicts] == [s.path for s in scenario.declared], (
        "verdicts are returned in declaration order so a reader can diff them"
    )
    for verdict in verdicts:
        assert verdict.classification in _ALL_CLASSIFICATIONS


@given(_scenarios())
def test_the_classification_is_the_one_the_case_mix_implies(scenario: _Scenario) -> None:
    """R2.8: the five non-passing states are kept apart, and each means what it says."""
    for verdict, expected in zip(_judge(scenario), scenario.expected, strict=True):
        assert verdict.path == expected.path
        assert verdict.classification == expected.classification, (
            f"{verdict.path}: expected {expected.classification}, got "
            f"{verdict.classification} ({verdict.detail})"
        )


@given(_scenarios())
def test_only_executed_is_a_pass(scenario: _Scenario) -> None:
    """I-7 at per-file scope: a skip is not a pass, and neither is an absence.

    ``attested`` is the single predicate the aggregate consumes, so the whole honesty
    contract for this clause reduces to it being true for exactly one classification -
    and, in the other direction, to that classification implying a case ran, none failed
    and none was skipped.
    """
    for verdict in _judge(scenario):
        assert verdict.attested == (verdict.classification == _PASSING), (
            f"{verdict.path}: {verdict.classification} must "
            f"{'' if verdict.classification == _PASSING else 'not '}be attested"
        )
        if verdict.attested:
            assert verdict.executed >= 1, "a pass with nothing executed is a false pass"
            assert verdict.failed == 0
            assert verdict.skipped == 0, "R2.14: any skip is non-passing"


@given(_scenarios())
def test_any_skipped_case_is_non_passing_and_named(scenario: _Scenario) -> None:
    """R2.14 stated directly on "any skip", not only via the case-mix arms.

    The reading this clause pins down is the one the subject got wrong before task 2.2:
    ``skipped_only`` was reached only when ``executed == 0``, so a file with four passes
    and one ``it.skip`` classified as ``executed`` and **passed**. R2.14 reads on **any**
    test reported skipped or todo in a declared file. Stated as its own property rather
    than left to the mix sampler, because the sampler could stop generating the arm and
    nothing would notice.

    The second half is the naming obligation: a count tells a reader that something did
    not run and not which thing, so every skipped title survives into the verdict.
    """
    for verdict, expected in zip(_judge(scenario), scenario.expected, strict=True):
        if verdict.skipped:
            assert not verdict.attested, f"{verdict.path}: a skip is never a pass (I-7)"
            assert verdict.classification != _PASSING
            assert verdict.classification in fe.FAILING_SUITE_CLASSES, (
                f"{verdict.path}: a skip was observed, so the record was read and the "
                f"state is a failure rather than an absence; got {verdict.classification}"
            )
            assert verdict.skipped_titles == expected.skipped_titles, (
                f"{verdict.path}: R2.14 obliges the gate to name each skipped case"
            )
            assert len(verdict.skipped_titles) == verdict.skipped
        else:
            assert verdict.skipped_titles == ()


@given(_scenarios())
def test_a_failing_case_outranks_any_number_of_passing_ones(scenario: _Scenario) -> None:
    """A file with 11 passes and 1 failure has not proven its property.

    Stated separately from the classification clause because the tempting implementation
    - "did anything pass?" - satisfies every other property in this file and is wrong.
    A failure also outranks a skip: the ``violated`` arm draws skips freely.
    """
    for verdict in _judge(scenario):
        if verdict.failed:
            assert verdict.classification == "violated"
            assert not verdict.attested


@given(_scenarios())
def test_a_violated_suite_carries_the_runners_counterexample(scenario: _Scenario) -> None:
    """R2.9: the shrunk counterexample survives into the verdict, paired with its title.

    For a fast-check property the minimal failing input exists **only** in the runner's
    failure message. A verdict that recorded "1 failed" and dropped the text would name
    the file and the property and lose the one thing needed to act on it.

    Three clauses, and the last two are what task 2.2 added:

    * one entry per failing case, so ``zip(failing_titles, counterexamples, strict=True)``
      - which the printer uses - cannot raise;
    * the pairing is **positional**, not best-effort: the message paired with a title
      belongs to that case;
    * a failure the record carried no message for is **stated** as such, never elided into
      an empty counterexample, because an empty string reads as "no counterexample" and
      that is a stronger claim than "the record did not carry one" (I-7).
    """
    for verdict, expected in zip(_judge(scenario), scenario.expected, strict=True):
        if verdict.classification != "violated":
            assert verdict.counterexamples == ()
            assert verdict.failing_titles == ()
            continue

        assert len(verdict.counterexamples) == verdict.failed
        assert len(verdict.failing_titles) == verdict.failed
        assert verdict.failing_titles == expected.failing_titles
        assert verdict.counterexamples == expected.counterexamples

        for title, text in zip(verdict.failing_titles, verdict.counterexamples, strict=True):
            assert text, "an empty counterexample would read as 'no counterexample'"
            if text == fe.NO_FAILURE_MESSAGE:
                continue
            index = title.removeprefix("fail ")
            assert f"[{index}]" in text, (
                f"{verdict.path}: {title!r} is paired with a message from another case, "
                "so R2.9's triple cannot be reconstructed from the verdict"
            )


@given(_scenarios())
def test_listing_decides_only_the_caseless_declarations(scenario: _Scenario) -> None:
    """The record's file listing is the ONLY thing it decides, and its default is safe.

    Two clauses, both about ``recorded_files``:

    * a declaration that reported at least one case gets the same verdict with or without
      the listing - the listing is not a second, weaker route to a pass;
    * with the listing withheld, every caseless declaration resolves to ``absent``. That
      is the documented default (``recorded_files=()``) and it is the weaker, safer claim:
      "no entry" says less than "the runner looked and produced nothing", and claiming the
      stronger one without the listing to support it would be the I-7 failure in
      miniature.
    """
    listed = _judge(scenario)
    unlisted = fe.evaluate_declared_suites(scenario.declared, scenario.cases)

    for actual, without in zip(listed, unlisted, strict=True):
        if actual.executed or actual.skipped:
            assert actual == without, (
                f"{actual.path}: the record's listing must not change the verdict for a "
                "file that reported cases"
            )
        else:
            assert without.classification == "absent", (
                f"{actual.path}: with no listing, a caseless declaration must resolve to "
                f"the weaker claim; got {without.classification}"
            )
            assert actual.classification in fe.UNAVAILABLE_SUITE_CLASSES
            assert not actual.attested
            assert not without.attested


@given(_scenarios())
def test_undeclared_reported_files_change_no_verdict(scenario: _Scenario) -> None:
    """A green suite elsewhere in the console must never attest a declared file.

    This is the per-file analogue of the FE-INV defect that started all of this: proof by
    proximity. The record contains hundreds of passing cases and lists hundreds of files;
    none of them is evidence about a file that did not run. Both inputs are filtered, so
    an undeclared **listing** is covered as well as an undeclared case - a reader that
    matched listings loosely could turn a stranger's entry into a ``no_cases`` verdict on
    a declared file, which reads as "the runner looked" when it did not.
    """
    only_declared_cases = tuple(
        case
        for case in scenario.cases
        if any(fe.paths_match(suite.path, case.suite_file) for suite in scenario.declared)
    )
    only_declared_files = tuple(
        recorded
        for recorded in scenario.recorded_files
        if any(fe.paths_match(suite.path, recorded) for suite in scenario.declared)
    )

    assert _judge(scenario) == fe.evaluate_declared_suites(
        scenario.declared, only_declared_cases, recorded_files=only_declared_files
    ), "verdicts must be a function of the declared files' own cases and listings"
    assert {e.classification for e in scenario.expected} <= set(_ALL_CLASSIFICATIONS)


@given(st.integers(min_value=1, max_value=4))
def test_absent_and_no_cases_are_never_conflated(count: int) -> None:
    """The distinction R2.8 exists for, asserted as a differential.

    Same declarations, same (empty) case list, **one input apart**: with the record's file
    listing withheld the answer is ``absent``, with it supplied the answer is
    ``no_cases``. That is the whole of R2.8's central claim, and it is stated as a
    difference rather than as two separate assertions because the failure mode is
    conflation, not either label alone.

    ``absent``: the record has no entry for the file - what a collection-time throw
    produces, and what Property 36 sat in while reading as fine. ``no_cases``: the record
    lists the file and reports nothing - the runner looked and produced nothing. Both are
    non-passing and both are ``unavailable`` to the aggregate, but they are different
    defects with different repairs, and a reader that returned one label for both would
    send someone to fix the wrong thing.
    """
    declared = tuple(
        _suite(f"frontend/spec/effectiveness/__tests__/g-{index}.property.test.ts", index)
        for index in range(count)
    )
    absent = fe.evaluate_declared_suites(declared, ())
    no_cases = fe.evaluate_declared_suites(
        declared, (), recorded_files=tuple(suite.path for suite in declared)
    )

    assert {v.classification for v in absent} == {"absent"}
    assert {v.classification for v in no_cases} == {"no_cases"}, (
        "a listed file with no case is not the same fact as an unlisted one (R2.8)"
    )

    for verdict, listed in zip(absent, no_cases, strict=True):
        for state in (verdict, listed):
            assert state.executed == 0
            assert state.passed == 0
            assert state.failed == 0
            assert state.skipped == 0
            assert not state.attested
            assert state.classification in fe.UNAVAILABLE_SUITE_CLASSES
            # R2.12: neither state may be described as verified anywhere.
            assert "AUTHORED BUT NOT EXECUTED" in state.detail
            # R2.13: a local editor probe is inconclusive, and the verdict says so rather
            # than leaving a reader to infer that a clean editor means a green property.
            assert "inconclusive" in state.detail
        assert verdict.detail != listed.detail, (
            f"{verdict.path}: the two states need different repairs, so they cannot share "
            "one message"
        )

    # The partition is exhaustive, the passing state is outside both non-passing sets, and
    # the count is derived from the subject rather than restated - the property title says
    # five and the subject carries six (see the module docstring).
    assert set(fe.UNAVAILABLE_SUITE_CLASSES) == {"absent", "no_cases"}
    assert set(fe.FAILING_SUITE_CLASSES) == {
        "violated",
        "partially_skipped",
        "skipped_only",
    }
    assert set(_ALL_CLASSIFICATIONS) == {
        _PASSING,
        *fe.FAILING_SUITE_CLASSES,
        *fe.UNAVAILABLE_SUITE_CLASSES,
    }
    assert len(_ALL_CLASSIFICATIONS) == 1 + len(fe.FAILING_SUITE_CLASSES) + len(
        fe.UNAVAILABLE_SUITE_CLASSES
    ), "one state in two sets, or a state in neither, would make the partition a lie"
    # Every state the subject can return is reachable from the generator's arms, so none
    # of them is dead code in this property the way `no_cases` was dead code in the
    # subject before task 2.2.
    assert set(_MIXES) == set(_ALL_CLASSIFICATIONS)


def test_the_committed_declaration_names_the_five_files_the_inventory_declares() -> None:
    """R2.16: the declaration and the inventory must describe the same five files.

    Not a property - a single committed fact with a single answer. It is here rather than
    in the inventory gate because the two documents are maintained separately: the
    inventory is the feature's own list and the attestation declaration is what CI reads,
    and a file present in one and absent from the other is invisible to both.
    """
    from tests.verify.test_property_inventory_consistency import (
        DECLARED_INVENTORY,
        TYPESCRIPT,
        language_of,
    )

    inventory_ts = {path for path in DECLARED_INVENTORY.values() if language_of(path) == TYPESCRIPT}
    declared = {suite.path for suite in _COMMITTED.declared_suites}

    assert declared == inventory_ts, (
        "fe-invariant-attestation.yaml's declared_suites and the property inventory's "
        f"TypeScript entries disagree; only in declaration: {sorted(declared - inventory_ts)}, "
        f"only in inventory: {sorted(inventory_ts - declared)}"
    )
    assert len(declared) == 5

    for suite in _COMMITTED.declared_suites:
        assert suite.title, f"{suite.path} declares no property title"
        assert suite.type_check_project, (
            f"{suite.path} names no type-check project, so R2.15's 'not type-checked' "
            "report would have no subject"
        )
