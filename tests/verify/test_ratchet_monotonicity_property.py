"""Property-based test for the ratchet gate (design E1.8; R2.10, R7.4, R7.8).

Feature: purpose-achievement-audit, Property 6: Ratchets are monotone, config-agreeing,
and data-gated

    *For any* sequence of committed threshold values, a value below the highest
    previously committed value is rejected naming threshold, previous, and proposed;
    *for any* (ratchet constant, shipped configuration value) pair, a difference fails
    naming both files and both values; and *for any* (previous, proposed, proof) triple,
    a raise is admitted only when it is monotone **and** the proof is powered, complete,
    within-fidelity-bound, and measures at least the proposed value.

Why a property and not examples. A ratchet is a statement about *histories*, not about
today's number. Any single example pins the value that happened to be committed the day
it was written, and the audit's finding is precisely that a threshold can be moved to a
weaker value between commits with nothing objecting. So the driver is a commit history:
``tests/verify/strategies.py::threshold_sequences`` is deliberately unsorted, which makes
a regression reachable rather than assumed, and the walk below re-evaluates the gate after
every commit and after every ``--apply`` maintenance step. Both ratchet directions are
generated: ``up`` (``bound`` is the highest-ever committed value, a *lower* commit is the
regression) and ``down`` (``bound`` is a ceiling that only tightens, a *higher* commit is
the regression). Getting the second one backwards would leave every mutation-survival and
baseline ceiling in the file unguarded, and no ``up``-only example would notice.

Ground truth. Each expectation is recomputed here from the generated case with plain
comparisons - the regression rule, the agreement rule, and R2.10's four admission
conditions are restated rather than imported, so the test compares two implementations of
the same rule instead of asking the gate to agree with itself. The data-gate clause is
additionally cross-checked against ``uplift.uplift_floor.ratchet_to_measured``, the
function R2.10 names as the only admission path.

Hermetic roots, per the pattern task 2.11 established. ``ratchet_truth.evaluate`` and
``apply_improvements`` both take ``ratchets_file`` and ``root``, so every generated case
writes its own ``ratchets.json``, its own shipped configuration, and its own guard-constant
module into a ``tempfile.TemporaryDirectory`` and is removed on the way out. No module
global is patched and no generated path can bind to a committed file. All three extractor
forms the gate implements (``yaml_path``, ``json_path``, ``regex``) are exercised, because
a ratchet that cannot read its own configuration is unavailable, not passing.

R7.8's live hole is CLOSED, and the closure is pinned rather than the hole. The committed
``stryker-break`` row recorded ``agrees_with_shipped: false`` - shipped ``50`` against a
guard constant frozen at ``26``, so a regression 50 -> 26 passed C16 - and this file
asserted that the gate detected it. The remediation landed (``ratchets.json`` now records
``50``/``50``), so the committed-file test now re-derives agreement from the two files it
governs and asserts the row PASSes. **The gate's ability to fail is unaffected and is
asserted where it belongs:** ``test_a_guard_constant_differing_from_its_shipped_config_
fails_naming_both`` constructs the disagreement over generated trees, so detection is
proved by construction instead of by a live defect the repo is obliged to keep.

I-0: this test reads and writes small files. It runs no coverage, no mutation sweep, and
no suite. ``max_examples`` is never set here - the budget comes from the root
``conftest.py`` profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500,
``nightly``=5000).

**Validates: Requirements 2.10, 7.4, 7.8**
"""

from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
import json
import math
import re
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import ratchet_truth as rt
from tests.verify.strategies import named_threshold_sequences, threshold_sequences

#: One recorded measurement date. The value is immaterial; that it is *recorded* is what
#: separates a ratchet with a measurement behind it from a declared bound (I-7).
RECORDED_AT: Final[str] = "2026-05-30"

#: The ratchet id every single-row generated case uses.
IDENTIFIER: Final[str] = "generated-ratchet"

#: The three extractor forms the gate implements. A ratchet is only as good as its
#: ability to re-read the configuration it guards, so all three are generated.
EXTRACTOR_KINDS: Final[tuple[str, ...]] = ("yaml_path", "json_path", "regex")

#: The symbol name every generated guard-constant module declares.
GUARD_SYMBOL: Final[str] = "GENERATED_GUARD"

#: The admission path R2.10 names. Recorded on data-gated rows exactly as the committed
#: ``uplift-floor`` row records it.
ADMISSION: Final[str] = (
    "uplift.uplift_floor.ratchet_to_measured against a PoweredProof from an artifact "
    "regenerated in the same job"
)

#: Exit status per aggregate outcome. ``2`` covers both unavailable and unmeasured:
#: neither is a pass (I-7).
EXPECTED_EXIT: Final[Mapping[rt.Outcome, int]] = {
    rt.Outcome.PASS: rt.EXIT_PASS,
    rt.Outcome.FAIL: rt.EXIT_FAIL,
    rt.Outcome.SKIP: rt.EXIT_UNAVAILABLE,
    rt.Outcome.UNAVAILABLE: rt.EXIT_UNAVAILABLE,
}


# ---------------------------------------------------------------------------
# The real uplift admission path, without the heavyweight package import
# ---------------------------------------------------------------------------


def _load_uplift_floor() -> ModuleType:
    """Load ``uplift/uplift_floor.py`` without importing the ``uplift`` package.

    ``uplift/__init__.py`` re-exports the harness, which imports ``digital_twin``
    (simpy) and ``scipy`` - CI-only dependencies that are absent on this box under I-0.
    ``uplift_floor`` itself is deliberately dependency-free (its own docstring says so),
    so loading it by path yields the real ``PoweredProof`` and ``ratchet_to_measured``
    as the data-gate oracle without dragging the twin in. Skipping instead would leave
    R2.10 unasserted, and an absent assertion is not a pass.

    The module is registered in ``sys.modules`` *before* execution, per the importlib
    recipe: ``PoweredProof`` is a dataclass whose fields carry bare-identifier
    annotations, and ``dataclasses._is_type`` resolves those through
    ``sys.modules.get(cls.__module__).__dict__`` with no guard, so an unregistered
    module raises ``AttributeError`` at class-creation time.
    """
    name = "synapse_uplift_floor_under_test"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = Path(rt.ROOT) / "uplift" / "uplift_floor.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


_UPLIFT_FLOOR: Final[ModuleType] = _load_uplift_floor()

#: ``uplift.uplift_floor.PoweredProof`` - the artifact a data-gated raise must carry.
PoweredProof: Final[Any] = _UPLIFT_FLOOR.PoweredProof
#: Replicates per arm a proof must record to count as powered (INV-TW-002).
MIN_POWERED_REPLICATES: Final[int] = int(_UPLIFT_FLOOR.MIN_POWERED_REPLICATES)
#: Raised by ``ratchet_to_measured`` when a raise carries no supporting proof.
UnprovenFloorRaiseError: Final[Any] = _UPLIFT_FLOOR.UnprovenFloorRaiseError


# ---------------------------------------------------------------------------
# The generated case
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RatchetDraft:
    """One row of a generated ``ratchets.json``, plus the tree it describes.

    ``bound`` is what the file records; ``committed`` is what the generated shipped
    configuration actually holds. Everything the gate compares is therefore reachable
    from the draft alone, which is what makes the recompute below independent.
    """

    identifier: str = IDENTIFIER
    kind: str = "generated-threshold"
    direction: str = rt.DIRECTION_UP
    bound: float = 0.0
    committed: float = 0.0
    extractor_kind: str = "json_path"
    guard_value: float | None = None
    #: What the row *claims* about agreement. ``None`` records the truth.
    agrees_override: bool | None = None
    #: What the row *claims* the shipped file holds. ``None`` records the truth.
    recorded_shipped: float | None = None
    status: str = rt.STATUS_MEASURED
    measured_at: str | None = RECORDED_AT
    data_gated: bool = False

    @property
    def slug(self) -> str:
        """A filesystem-safe stem, so two rows never collide on one generated file."""
        return re.sub(r"[^A-Za-z0-9]+", "_", self.identifier).strip("_")

    @property
    def recorded_shipped_value(self) -> float:
        return self.committed if self.recorded_shipped is None else self.recorded_shipped

    @property
    def agrees(self) -> bool:
        if self.agrees_override is not None:
            return self.agrees_override
        return self.guard_value is None or same(self.guard_value, self.committed)


def fmt(value: float) -> str:
    """Render a threshold the way the gate names it: ``50`` not ``50.0``."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def _shipped(draft: RatchetDraft) -> tuple[str, str, str]:
    """``(repo-relative path, extractor, file body)`` for a draft's shipped config."""
    value = draft.committed
    if draft.extractor_kind == "yaml_path":
        body = yaml.safe_dump({"packages": {"generated/pkg": {"line": value}}}, sort_keys=True)
        return f"generated/{draft.slug}/thresholds.yaml", (
            "yaml_path:packages['generated/pkg'].line"
        ), body
    if draft.extractor_kind == "json_path":
        body = json.dumps({"thresholds": {"break": value}}, indent=2) + "\n"
        return f"generated/{draft.slug}/config.json", "json_path:$.thresholds.break", body
    body = f"GENERATED_FLOOR: float = {fmt(value)}\n"
    return (
        f"generated/{draft.slug}/floor.py",
        r"regex:^GENERATED_FLOOR: float = (?P<value>[\d.]+)$",
        body,
    )


def write_case(root: Path, drafts: Sequence[RatchetDraft]) -> Path:
    """Write every draft's shipped config, guard module, and the ``ratchets.json``.

    Returns the path to the generated ratchets file. Called repeatedly inside one
    temporary root so a commit history can be walked without re-creating the tree.
    """
    records: dict[str, object] = {}
    for draft in drafts:
        shipped_rel, extractor, body = _shipped(draft)
        shipped_path = root / shipped_rel
        shipped_path.parent.mkdir(parents=True, exist_ok=True)
        shipped_path.write_text(body, encoding="utf-8")

        guard: dict[str, object] | None = None
        if draft.guard_value is not None:
            guard_rel = f"generated/{draft.slug}/guard.py"
            guard_path = root / guard_rel
            guard_path.parent.mkdir(parents=True, exist_ok=True)
            guard_path.write_text(
                f"{GUARD_SYMBOL} = {fmt(draft.guard_value)}  # generated guard constant\n",
                encoding="utf-8",
            )
            guard = {
                "file": guard_rel,
                "symbol": GUARD_SYMBOL,
                "value": draft.guard_value,
            }

        record: dict[str, object] = {
            "kind": draft.kind,
            "direction": draft.direction,
            "bound": draft.bound,
            "unit": "generated",
            "shipped": {
                "file": shipped_rel,
                "extractor": extractor,
                "value": draft.recorded_shipped_value,
            },
            "guard_constant": guard,
            "agrees_with_shipped": draft.agrees,
            "status": draft.status,
            "measured_at": draft.measured_at,
            "source_run": None,
            "data_gated": draft.data_gated,
        }
        if draft.data_gated:
            record["admission"] = ADMISSION
        records[draft.identifier] = record

    ratchets_file = root / "ratchets.json"
    ratchets_file.write_text(
        json.dumps({"version": 1, "ratchets": records}, indent=2) + "\n", encoding="utf-8"
    )
    return ratchets_file


@contextlib.contextmanager
def rendered(drafts: Sequence[RatchetDraft]) -> Iterator[tuple[Path, Path]]:
    """Yield ``(ratchets_file, root)`` for *drafts* inside a temporary directory."""
    with tempfile.TemporaryDirectory(prefix="ratchet-truth-") as tmp:
        root = Path(tmp)
        yield write_case(root, drafts), root


def report_of(
    drafts: Sequence[RatchetDraft], *, proof: Any | None = None
) -> rt.RatchetTruthReport:
    """Evaluate *drafts* against their own generated tree."""
    with rendered(drafts) as (ratchets_file, root):
        return rt.evaluate(ratchets_file, root=root, proof=proof)


def row_of(report: rt.RatchetTruthReport, identifier: str) -> rt.RatchetReport:
    """The single row for *identifier*; the gate must emit exactly one."""
    rows = [row for row in report.ratchets if row.id == identifier]
    assert len(rows) == 1, f"expected one row for {identifier}, got {len(rows)}"
    return rows[0]


def clauses_of(row: rt.RatchetReport) -> frozenset[rt.Clause]:
    return frozenset(finding.clause for finding in row.findings)


def detail_for(row: rt.RatchetReport, clause: rt.Clause) -> str:
    """The finding text for *clause*, which is where the naming obligation lands."""
    for finding in row.findings:
        if finding.clause is clause:
            return finding.detail
    raise AssertionError(f"{row.id} carries no {clause.value} finding: {row.findings}")


def without_recorded_measurement(document: Mapping[str, Any]) -> frozenset[str]:
    """Ids in *document* that have no measurement behind them - I-7's SKIP domain.

    ``status: unmeasured`` is the honest spelling and sixteen committed rows use it. Six
    more say ``status: measured`` with ``measured_at: null``, which is the same condition
    wearing a different label: a row claiming a measurement it cannot date has none. Both
    committed-file tests below read this ONE predicate, so the SKIP set they assert against
    cannot drift apart - and the twenty-two are derived here rather than counted in a
    docstring, because a literal count in a test is a second source of truth.
    """
    ratchets = document["ratchets"]
    assert isinstance(ratchets, dict)
    return frozenset(
        identifier
        for identifier, raw in ratchets.items()
        if raw.get("measured_at") is None or raw.get("status") != rt.STATUS_MEASURED
    )


# ---------------------------------------------------------------------------
# The independent recompute: the three clauses, restated
# ---------------------------------------------------------------------------


def regressed(direction: str, bound: float, committed: float) -> bool:
    """R7.4: is *committed* on the wrong side of *bound*?

    ``up``: ``bound`` is the highest-ever committed value, so a lower commit regresses.
    ``down``: ``bound`` is a ceiling that only tightens, so a higher commit regresses.
    """
    if same(bound, committed):
        return False
    return committed < bound if direction == rt.DIRECTION_UP else committed > bound


def improved(direction: str, bound: float, committed: float) -> bool:
    """Does *committed* strictly tighten the ratchet past *bound*?"""
    if same(bound, committed):
        return False
    return committed > bound if direction == rt.DIRECTION_UP else committed < bound


def extreme(direction: str, values: Sequence[float]) -> float:
    """The highest-ever (``up``) or lowest-ever (``down``) value in a commit history."""
    return max(values) if direction == rt.DIRECTION_UP else min(values)


def proof_admits(proof: Any | None, proposed: float) -> bool:
    """R2.10's four conditions, restated from the proof's fields.

    A raise is admissible only against a proof that is *powered*
    (``replicates >= MIN_POWERED_REPLICATES``), *complete*, *within the fidelity bound*,
    and that *measures at least the proposed value*. Restated rather than delegated to
    ``PoweredProof.supports`` so the gate is compared against the requirement, not
    against the helper it happens to call.
    """
    if proof is None:
        return False
    if proof.replicates < MIN_POWERED_REPLICATES or proof.incomplete:
        return False
    if proof.within_fidelity_bound is not True:
        return False
    if not math.isfinite(proof.headline_uplift) or proof.headline_uplift <= 0.0:
        return False
    return 0.0 < proposed <= proof.headline_uplift


def expected_clauses(draft: RatchetDraft, *, proof: Any | None = None) -> frozenset[rt.Clause]:
    """Every clause *draft* violates, recomputed from the draft alone."""
    found: set[rt.Clause] = set()
    if not same(draft.recorded_shipped_value, draft.committed):
        found.add(rt.Clause.RECORD_DRIFT)
    if regressed(draft.direction, draft.bound, draft.committed):
        found.add(rt.Clause.MONOTONICITY)
    if draft.data_gated and improved(draft.direction, draft.bound, draft.committed):
        if not proof_admits(proof, draft.committed):
            found.add(rt.Clause.DATA_GATE)
    truthful_agreement = draft.guard_value is None or same(draft.guard_value, draft.committed)
    if not truthful_agreement:
        found.add(rt.Clause.CONFIG_AGREEMENT)
    if truthful_agreement != draft.agrees:
        found.add(rt.Clause.RECORD_DRIFT)
    return frozenset(found)


def expected_outcome(draft: RatchetDraft, *, proof: Any | None = None) -> rt.Outcome:
    """The verdict E1.8 mandates for one row. A skip never outranks a real breach."""
    if expected_clauses(draft, proof=proof):
        return rt.Outcome.FAIL
    measured = draft.status == rt.STATUS_MEASURED and draft.measured_at is not None
    return rt.Outcome.PASS if measured else rt.Outcome.SKIP


# ---------------------------------------------------------------------------
# Clause 1 - monotonicity, walked over a commit history, in both directions
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 6: Ratchets are monotone, config-agreeing,
# and data-gated
@given(
    history=threshold_sequences(min_size=2),
    direction=st.sampled_from(rt.DIRECTIONS),
    extractor_kind=st.sampled_from(EXTRACTOR_KINDS),
)
def test_a_commit_on_the_wrong_side_of_its_bound_is_named_and_never_ratchets_the_record(
    history: tuple[float, ...], direction: str, extractor_kind: str
) -> None:
    """R7.4: a regression FAILs naming threshold, previous, and proposed - either way.

    The whole history is walked, so the recorded bound is whatever the *previous*
    commits left it at rather than a value chosen to make the assertion work. Two
    obligations are checked at every step: the gate's verdict on this commit, and that
    the ``--apply`` maintenance step only ever moves the bound in the ratcheting
    direction. The second is what makes the first durable - a gate that failed correctly
    but let the bound drift down to the regression would pass once and never again bite.
    """
    base = RatchetDraft(direction=direction, extractor_kind=extractor_kind)
    with tempfile.TemporaryDirectory(prefix="ratchet-history-") as tmp:
        root = Path(tmp)
        bound = history[0]
        seen: list[float] = [history[0]]

        for committed in history[1:]:
            draft = dataclasses.replace(base, bound=bound, committed=committed)
            ratchets_file = write_case(root, (draft,))
            row = row_of(rt.evaluate(ratchets_file, root=root), IDENTIFIER)

            assert row.committed is not None and same(row.committed, committed), (
                "the gate must re-read the value the shipped file actually holds, not the "
                "one the record claims"
            )
            assert clauses_of(row) == expected_clauses(draft)
            assert row.outcome is expected_outcome(draft)

            if regressed(direction, bound, committed):
                assert row.outcome is rt.Outcome.FAIL
                detail = detail_for(row, rt.Clause.MONOTONICITY)
                # R7.4's naming obligation: the id, the recorded bound, the commit.
                assert IDENTIFIER in detail
                assert f"previous {fmt(bound)}" in detail
                assert f"proposed {fmt(committed)}" in detail
                assert direction in detail

            rt.apply_improvements(ratchets_file, root=root)
            ratcheted = json.loads(ratchets_file.read_text(encoding="utf-8"))
            new_bound = float(ratcheted["ratchets"][IDENTIFIER]["bound"])

            # Monotone by construction: the record only ever tightens.
            assert not regressed(direction, bound, new_bound)
            assert same(new_bound, committed if improved(direction, bound, committed) else bound)
            bound = new_bound
            seen.append(committed)

        # The bound the walk arrived at is the extreme of every value ever committed.
        assert same(bound, extreme(direction, seen))


@given(named=named_threshold_sequences(), extractor_kind=st.sampled_from(EXTRACTOR_KINDS))
def test_the_file_verdict_fails_iff_some_recorded_ratchet_regressed(
    named: Mapping[str, tuple[float, ...]], extractor_kind: str
) -> None:
    """R7.4 across the whole file: one regression is enough, and it is named.

    The single-row walk above cannot catch an aggregation bug - a gate that found the
    breach but summed its rows to ``PASS`` would satisfy every assertion there. Each
    ratchet's recorded bound is the extreme of its earlier commits and the last value in
    its history is the commit under judgement, which is exactly the shape a real
    ``ratchets.json`` has after any number of PRs.
    """
    drafts: list[RatchetDraft] = []
    for identifier, history in named.items():
        direction = rt.DIRECTION_UP if len(identifier) % 2 == 0 else rt.DIRECTION_DOWN
        prior = history[:-1] if len(history) > 1 else history
        drafts.append(
            RatchetDraft(
                identifier=identifier,
                direction=direction,
                bound=extreme(direction, prior),
                committed=history[-1],
                extractor_kind=extractor_kind,
            )
        )

    report = report_of(drafts)
    assert {row.id for row in report.ratchets} == {draft.identifier for draft in drafts}

    expected_failing = {
        draft.identifier
        for draft in drafts
        if regressed(draft.direction, draft.bound, draft.committed)
    }
    failing = {row.id for row in report.ratchets if row.outcome is rt.Outcome.FAIL}
    assert failing == expected_failing

    assert report.outcome is (rt.Outcome.FAIL if expected_failing else rt.Outcome.PASS)
    assert report.exit_code == EXPECTED_EXIT[report.outcome]

    text = "\n".join(rt.format_report(report))
    for identifier in expected_failing:
        assert identifier in text
        assert "previous" in text and "proposed" in text


# ---------------------------------------------------------------------------
# Clause 2 - config agreement (R7.8)
# ---------------------------------------------------------------------------


@given(
    shipped=threshold_sequences(min_size=1, max_size=1),
    drift=st.floats(min_value=-40.0, max_value=40.0).map(lambda value: round(value, 2)),
    extractor_kind=st.sampled_from(EXTRACTOR_KINDS),
    claims_agreement=st.booleans(),
)
def test_a_guard_constant_differing_from_its_shipped_config_fails_naming_both(
    shipped: tuple[float, ...],
    drift: float,
    extractor_kind: str,
    claims_agreement: bool,
) -> None:
    """R7.8: a ratchet constant that is not the value it guards cannot catch a regression.

    The guard constant is re-read from its own generated module, so the comparison is
    file-against-file rather than record-against-record. ``claims_agreement`` varies what
    the row *says* about the pair: a row that claims agreement while the two files
    disagree is doubly wrong, and the record-drift finding is what stops the flag from
    becoming a way to silence the clause.
    """
    committed = shipped[0]
    guard_value = round(max(0.0, committed + drift), 2)
    draft = RatchetDraft(
        bound=committed,
        committed=committed,
        extractor_kind=extractor_kind,
        guard_value=guard_value,
        agrees_override=claims_agreement,
    )

    row = row_of(report_of((draft,)), IDENTIFIER)
    assert clauses_of(row) == expected_clauses(draft)
    assert row.outcome is expected_outcome(draft)

    if same(guard_value, committed):
        # Agreeing files are the passing case; the clause must not fire on them.
        assert rt.Clause.CONFIG_AGREEMENT not in clauses_of(row)
        assert (row.outcome is rt.Outcome.PASS) is claims_agreement
        return

    assert row.outcome is rt.Outcome.FAIL
    detail = detail_for(row, rt.Clause.CONFIG_AGREEMENT)
    shipped_rel, _extractor, _body = _shipped(draft)
    # Both files and both values, which is the whole of R7.8's naming obligation.
    assert shipped_rel in detail
    assert f"generated/{draft.slug}/guard.py" in detail
    assert GUARD_SYMBOL in detail
    assert fmt(guard_value) in detail
    assert fmt(committed) in detail
    assert draft.extractor_kind in detail
    # Claiming agreement over a disagreeing pair is itself a detected drift.
    assert (rt.Clause.RECORD_DRIFT in clauses_of(row)) is claims_agreement


# ---------------------------------------------------------------------------
# Clause 3 - the data gate (R2.10)
# ---------------------------------------------------------------------------


@st.composite
def data_gate_cases(draw: st.DrawFn) -> tuple[float, float, Any | None]:
    """A ``(previous, proposed, proof)`` triple in which both verdicts are reachable.

    Drawn so a *supporting* proof is not vanishingly rare: an unconstrained proof
    generator would almost never measure at least the proposed value, and the admitted
    branch of R2.10 would go unexercised while the test still passed.
    """
    previous = round(draw(st.floats(min_value=0.0, max_value=5.0)), 2)
    proposed = round(previous + round(draw(st.floats(min_value=0.01, max_value=10.0)), 2), 2)
    if draw(st.booleans()):
        return previous, proposed, None

    supportive = draw(st.booleans())
    margin = round(draw(st.floats(min_value=0.0, max_value=5.0)), 2)
    proof = PoweredProof(
        headline_uplift=round(proposed + margin if supportive else proposed - margin - 0.01, 2),
        replicates=(
            MIN_POWERED_REPLICATES
            if supportive
            else draw(st.sampled_from((0, 1, 999, MIN_POWERED_REPLICATES)))
        ),
        incomplete=False if supportive else draw(st.booleans()),
        within_fidelity_bound=(
            True if supportive else draw(st.sampled_from((True, False, None)))
        ),
    )
    return previous, proposed, proof


@given(case=data_gate_cases())
def test_a_data_gated_raise_is_admitted_only_by_a_powered_same_run_proof(
    case: tuple[float, float, Any | None],
) -> None:
    """R2.10: ``UPLIFT_FLOOR`` may only be raised against a supporting powered proof.

    Three things must agree: this file's restatement of the four admission conditions,
    the gate's verdict, and ``uplift.uplift_floor.ratchet_to_measured`` - the function
    R2.10 names as the only admission path, and the one the audit found no production
    caller for. If the gate and that function ever disagree about the same triple, one of
    them is not enforcing the requirement.
    """
    previous, proposed, proof = case
    admitted = proof_admits(proof, proposed)
    draft = RatchetDraft(
        bound=previous,
        committed=proposed,
        data_gated=True,
        status=rt.STATUS_UNMEASURED,
        measured_at=None,
    )

    with rendered((draft,)) as (ratchets_file, root):
        row = row_of(rt.evaluate(ratchets_file, root=root, proof=proof), IDENTIFIER)
        assert clauses_of(row) == expected_clauses(draft, proof=proof)
        assert (rt.Clause.DATA_GATE in clauses_of(row)) is not admitted

        if not admitted:
            detail = detail_for(row, rt.Clause.DATA_GATE)
            assert IDENTIFIER in detail
            assert f"raise from {fmt(previous)} to {fmt(proposed)}" in detail
            assert "ratchet_to_measured" in detail
            assert row.outcome is rt.Outcome.FAIL
        else:
            # Admitted: no data-gate finding, and the row is a SKIP because the record
            # itself still carries no measurement. A skip is not a pass (I-7).
            assert row.outcome is rt.Outcome.SKIP

        # The maintenance step honours the same gate: an unproven raise is withheld.
        messages = rt.apply_improvements(ratchets_file, root=root, proof=proof)
        bumped = json.loads(ratchets_file.read_text(encoding="utf-8"))
        new_bound = float(bumped["ratchets"][IDENTIFIER]["bound"])
        assert same(new_bound, proposed if admitted else previous)
        if not admitted:
            assert any("withheld" in message for message in messages)

    # The independent oracle: the only admission path R2.10 recognises.
    if admitted:
        assert _UPLIFT_FLOOR.ratchet_to_measured(previous, proposed, proof) == proposed
    else:
        with pytest.raises(UnprovenFloorRaiseError):
            _UPLIFT_FLOOR.ratchet_to_measured(previous, proposed, proof)


@given(case=data_gate_cases())
def test_a_data_gated_row_needs_no_proof_to_hold_or_to_tighten_below_its_bound(
    case: tuple[float, float, Any | None],
) -> None:
    """R2.10 is a gate on *raises* only; holding a floor asserts nothing new.

    Without this the data gate would be indistinguishable from "a data-gated row can
    never pass", which would make the clause unfalsifiable. The lowered case is the
    converse: it fails on monotonicity whatever the proof says, so a proof can never buy
    a regression.
    """
    previous, proposed, proof = case
    held = RatchetDraft(
        bound=previous,
        committed=previous,
        data_gated=True,
        status=rt.STATUS_MEASURED,
        measured_at=RECORDED_AT,
    )
    row = row_of(report_of((held,), proof=proof), IDENTIFIER)
    assert row.findings == ()
    assert row.outcome is rt.Outcome.PASS

    lowered = dataclasses.replace(
        held, bound=proposed, committed=previous, direction=rt.DIRECTION_UP
    )
    row = row_of(report_of((lowered,), proof=proof), IDENTIFIER)
    assert clauses_of(row) == {rt.Clause.MONOTONICITY}
    assert row.outcome is rt.Outcome.FAIL


# ---------------------------------------------------------------------------
# I-7 - an unmeasured row is never a pass
# ---------------------------------------------------------------------------


@given(
    shipped=threshold_sequences(min_size=1, max_size=1),
    status=st.sampled_from((rt.STATUS_MEASURED, rt.STATUS_UNMEASURED)),
    measured_at=st.sampled_from((None, RECORDED_AT)),
    direction=st.sampled_from(rt.DIRECTIONS),
)
def test_a_row_with_no_recorded_measurement_is_a_skip_and_never_a_pass(
    shipped: tuple[float, ...], status: str, measured_at: str | None, direction: str
) -> None:
    """I-7: ``measured_at: null`` / ``status: unmeasured`` is a declared bound, not proof.

    Every clause holds in these cases - the commit sits exactly on its bound - so the
    only thing separating them is whether a measurement backs the number. Both halves
    matter: an unmeasured row must not read as a pass, and it must not read as a failure
    either, because measuring it is a CI workload this machine is forbidden to run (I-0).
    """
    committed = shipped[0]
    draft = RatchetDraft(
        direction=direction,
        bound=committed,
        committed=committed,
        status=status,
        measured_at=measured_at,
    )
    report = report_of((draft,))
    row = row_of(report, IDENTIFIER)
    assert row.findings == ()

    if status == rt.STATUS_MEASURED and measured_at is not None:
        assert row.outcome is rt.Outcome.PASS
        assert report.exit_code == rt.EXIT_PASS
        return

    assert row.outcome is rt.Outcome.SKIP
    assert row.outcome is not rt.Outcome.PASS
    assert report.outcome is rt.Outcome.SKIP
    assert report.exit_code == rt.EXIT_UNAVAILABLE
    assert "no measurement recorded" in row.detail
    assert "not a pass" in "\n".join(rt.format_report(report))


@given(
    shipped=threshold_sequences(min_size=1, max_size=1),
    gap=st.floats(min_value=0.01, max_value=20.0).map(lambda value: round(value, 2)),
)
def test_a_real_regression_outranks_an_unmeasured_row_in_the_aggregate(
    shipped: tuple[float, ...], gap: float
) -> None:
    """An absent measurement must never mask a breach in the file-level verdict."""
    committed = shipped[0]
    unmeasured = RatchetDraft(
        identifier="unmeasured-row",
        bound=committed,
        committed=committed,
        status=rt.STATUS_UNMEASURED,
        measured_at=None,
    )
    regressing = RatchetDraft(
        identifier="regressing-row",
        bound=round(committed + gap, 2),
        committed=committed,
        extractor_kind="yaml_path",
    )
    report = report_of((unmeasured, regressing))
    assert row_of(report, "unmeasured-row").outcome is rt.Outcome.SKIP
    assert row_of(report, "regressing-row").outcome is rt.Outcome.FAIL
    assert report.outcome is rt.Outcome.FAIL
    assert report.exit_code == rt.EXIT_FAIL


# ---------------------------------------------------------------------------
# The committed file: the recorded Stryker hole, and the baselines
# ---------------------------------------------------------------------------


def test_the_committed_stryker_break_row_now_agrees_with_the_config_it_guards() -> None:
    """R7.8's live example is CLOSED, and this pins the closure rather than the hole.

    A static read of the committed tree - no mutation run (I-0).

    **This is a precondition correction, not an assertion weakening (R2.10).** What
    changed is the subject, not the standard. Until session 1 of `decision-quality-proof`
    the committed row recorded ``agrees_with_shipped: false`` - shipped ``break: 50``
    against a guard constant frozen at ``26`` - so a regression ``50 -> 26`` passed C16,
    and this test asserted that the gate FAILed naming both files and both values. The
    remediation then landed: ``ratchets.json`` now records ``50``/``50`` and
    ``agrees_with_shipped: true``, ``ratchet_truth`` reports the row PASS with no findings,
    and asserting the old FAIL is asserting a defect that no longer exists.

    **The repair was a coordinated change across four sites and only two of them moved,
    which is why this surfaced as a red rather than as a review comment.**
    ``scripts/audit/verify_claims.py``'s own C16 docstring still describes the hole as live
    ("**Expected FAIL on landing**") and names this module as one of the sites its repair
    must touch. That prose is another spec's and is read by ``doc_truth``, so it is
    recorded rather than edited here: an unmeasurable prose edit does not belong in the
    same diff as a mechanical one.

    **Agreement is re-derived from the two committed files, never from the record.** A row
    that only agreed with itself would be the defect one layer up: the record could then
    outrun its subject in either direction. The gate's ability to *detect* a disagreement
    is asserted generically and by construction in
    :func:`test_a_guard_constant_differing_from_its_shipped_config_fails_naming_both`, over
    generated trees - so nothing is lost by this file no longer needing a live breach.
    """
    shipped_config = json.loads(
        (rt.ROOT / "frontend" / "stryker.conf.json").read_text(encoding="utf-8")
    )
    shipped_value = float(shipped_config["thresholds"]["break"])

    guard_text = (rt.ROOT / "scripts" / "audit" / "verify_claims.py").read_text(
        encoding="utf-8"
    )
    guard_match = re.search(r"^STRYKER_BREAK_NOW = (?P<value>[\d.]+)", guard_text, re.M)
    assert guard_match is not None, "STRYKER_BREAK_NOW is no longer declared"
    guard_value = float(guard_match.group("value"))

    # The two files agree, read independently of anything ratchets.json claims.
    assert same(shipped_value, guard_value)

    document = rt.load_ratchets()
    recorded = document["ratchets"]["stryker-break"]
    # And the record agrees with that derivation, so the flag cannot outrun its subject.
    assert recorded["agrees_with_shipped"] is True
    assert same(float(recorded["shipped"]["value"]), shipped_value)
    assert same(float(recorded["guard_constant"]["value"]), guard_value)

    report = rt.evaluate()
    row = row_of(report, "stryker-break")
    assert row.outcome is rt.Outcome.PASS
    assert row.findings == ()
    assert rt.Clause.CONFIG_AGREEMENT not in clauses_of(row)

    # No committed ratchet breaches its bound or its configuration. Asserted with the row
    # set pinned non-empty: an empty report would satisfy "nothing failed" vacuously.
    assert report.ratchets, "the committed ratchets file records no ratchet at all"
    assert {row.id for row in report.ratchets if row.outcome is rt.Outcome.FAIL} == set()

    # The file verdict is SKIP, and that is the gate working. Rows with no measurement behind
    # them cannot be read as passes (I-7), so the aggregate is non-passing while any remain.
    # The skipped set is DERIVED from the document through the same predicate the sibling
    # test uses, never counted here: a literal in a test is a second source of truth.
    unmeasured = without_recorded_measurement(document)
    skipped = {row.id for row in report.ratchets if row.outcome is rt.Outcome.SKIP}
    assert unmeasured, "no row lacks a measurement, so the SKIP below would be unexplained"
    assert skipped == unmeasured
    assert report.outcome is rt.Outcome.SKIP
    assert report.exit_code == rt.EXIT_UNAVAILABLE


def test_every_committed_ratchet_can_re_read_the_configuration_it_guards() -> None:
    """A ratchet that cannot read its own subject asserts nothing (I-7).

    Static, and it is the precondition for every other clause: a rotted extractor would
    turn the whole file into a row of ``[??]`` markers that no aggregate could call a
    pass, but also into a gate that never compares anything.
    """
    report = rt.evaluate()
    unavailable = {
        row.id: row.detail
        for row in report.ratchets
        if row.outcome is rt.Outcome.UNAVAILABLE
    }
    assert unavailable == {}, f"a recorded ratchet lost its subject: {unavailable}"
    assert report.ratchets, "the committed ratchets file records no ratchet at all"


def test_committed_rows_with_no_measurement_are_never_reported_as_a_pass() -> None:
    """I-7 over the real file: ``measured_at: null`` never reads as proof.

    Several committed rows are honestly unmeasured - the zero coverage floors (CF-3), the
    mutation-survival ceilings whose sweep is CI-only, the replay floors that task 4.5 will
    first measure, and the data-gated uplift floor. Each must be a SKIP. How many there are
    is derived by :func:`without_recorded_measurement` rather than stated here: the docstring
    used to say "twelve" and the file had grown past it, which is the drift this suite exists
    to catch, one level up.
    """
    document = rt.load_ratchets()
    outcomes = {row.id: row.outcome for row in rt.evaluate().ratchets}

    unmeasured = without_recorded_measurement(document)
    assert unmeasured, "the committed file records no unmeasured row; CF-3 expects several"
    for identifier in unmeasured:
        assert outcomes[identifier] is not rt.Outcome.PASS, (
            f"{identifier} has no recorded measurement yet reads as a pass"
        )


def test_a_baseline_ratchet_agrees_with_the_named_list_it_projects() -> None:
    """R13.9 seam: a baseline count is the length of its named list, not a free number.

    ``dead-modules-baseline`` ratchets ``infrastructure/quality/dead-modules.yaml``, whose
    ``baseline`` is committed explicitly *and* declared to equal ``len(dormant)``. If the
    two ever disagree the ratchet is guarding a number nobody derived, so the ratcheted
    value, the committed count, and the list length are all compared here.
    """
    document = rt.load_ratchets()
    recorded = document["ratchets"]["dead-modules-baseline"]
    listed = Path(rt.ROOT) / recorded["shipped"]["file"]
    dead_modules = yaml.safe_load(listed.read_text(encoding="utf-8"))

    assert dead_modules["baseline"] == len(dead_modules["dormant"]), (
        "dead-modules.yaml commits a baseline that is not the length of its own list"
    )
    assert recorded["shipped"]["value"] == dead_modules["baseline"]
    assert recorded["bound"] == dead_modules["baseline"]
    # A ceiling: a new orphan raises the count, and raising it is the regression.
    assert recorded["direction"] == rt.DIRECTION_DOWN
    assert regressed(rt.DIRECTION_DOWN, recorded["bound"], recorded["bound"] + 1)

    row = row_of(rt.evaluate(), "dead-modules-baseline")
    assert row.outcome is not rt.Outcome.FAIL
    assert row.committed is not None and same(row.committed, float(dead_modules["baseline"]))
