"""Property-based test for reported check identity (design AD-14 / E1.2).

Feature: purpose-achievement-audit, Property 10: A check reports the identifier it is
registered under

    *For any* check function and *any* return path it takes - normal return, import
    failure, raised exception, wrong return type - the emitted identifier equals the
    registered identifier, and any mismatch is coerced to ``FAIL`` naming both
    identifiers.

Why the property is shaped this way. The concrete defect it closes is C46's SKIP
branch returning ``cid="C43"`` (``verify_claims.py:1163``): an unavailable
published-checkpoint probe landed on *another* check's row, and left the row it was
registered under with no result at all. Both halves of that are silent. A status moved
onto a foreign row is a status the Truth_Ledger attributes to the wrong claim (R10.5),
and a registered id with no result is a claim nobody evaluated - which the registry
gate can only detect if the emitted id set is trustworthy in the first place. So the
guard has to be *total*: it cannot be a spot-fix on C46, it must hold for every check
and every return path, including the paths that are themselves already coerced (a
raise, a wrong return type, an out-of-vocabulary status).

The mismatching id is drawn from **both** the other registered ids and ids that were
never registered, because the real defect reported under a *registered* id - the case
that actually corrupts a row - while a foreign id is the case that would slip past a
naive "is this a known check?" filter.

The real 53-check registry is never executed here: it shells out to git/docker probes
under a 900s budget, which I-0 forbids on this machine. ``_run_check`` takes its
``(cid, title, fn)`` triple as arguments, so the coercion can be driven over synthetic
registrations built from the shared strategies; the one assertion about the real
registry is *static* (it reads C46's source, it does not run it).

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 10.5**
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import verify_claims as vc
from tests.verify.strategies import check_ids, check_results, registry_scenarios

if TYPE_CHECKING:
    from collections.abc import Callable

#: Return paths a registered check can take. ``match`` and ``mismatch`` are the honest
#: and defective identity paths; the remaining four are the paths ``_run_check``
#: already coerced before AD-14 landed, included so the identity guard is shown to
#: hold *over* those coercions rather than beside them.
_BEHAVIOURS: Final[tuple[str, ...]] = (
    "match",
    "mismatch",
    "raises",
    "import_failure",
    "wrong_type",
    "bad_status_match",
    "bad_status_mismatch",
)

_EXCEPTIONS: Final[dict[str, type[Exception]]] = {
    exc.__name__: exc for exc in (RuntimeError, ValueError, KeyError, OSError, ZeroDivisionError)
}

#: Values a check might return instead of a ``CheckResult``.
_WRONG_RETURNS: Final[tuple[object, ...]] = (None, "PASS", 42, (), {"status": "PASS"})

#: Statuses outside ``vc.STATUSES`` - near-misses plus outright nonsense.
_BAD_STATUSES: Final[tuple[str, ...]] = ("", "pass", "Pass", "PASSED", "OK", "WARN", "UNKNOWN")


@dataclass(frozen=True)
class IdentityCase:
    """One registration paired with the return path its check function takes.

    ``registered_cid`` / ``registered_title`` are what ``@register`` declared;
    ``returned`` is what the check hands back, and its ``cid`` is free to diverge -
    that divergence is the whole subject of R10.5.
    """

    registered_cid: str
    registered_title: str
    behaviour: str
    returned: vc.CheckResult | None = None
    wrong_return: object = None
    exception_name: str = "RuntimeError"

    @property
    def reported_cid(self) -> str | None:
        """The identifier the check itself reported, when it returned a result."""
        return None if self.returned is None else self.returned.cid

    @property
    def identity_diverges(self) -> bool:
        """Whether the reported identifier differs from the registered one."""
        return self.returned is not None and self.returned.cid != self.registered_cid

    def as_check(self) -> Callable[[], vc.CheckResult]:
        """Build the check callable this case describes."""
        if self.behaviour == "raises":
            exc = _EXCEPTIONS[self.exception_name]

            def _boom() -> vc.CheckResult:
                raise exc("synthetic check failure")

            return _boom
        if self.behaviour == "import_failure":

            def _import_failure() -> vc.CheckResult:
                raise ImportError("No module named 'scripts.audit.synthetic_probe'")

            return _import_failure
        if self.behaviour == "wrong_type":
            wrong = self.wrong_return
            return cast("Callable[[], vc.CheckResult]", lambda: wrong)
        returned = self.returned
        assert returned is not None, self.behaviour
        return lambda: returned


@st.composite
def identity_cases(draw: st.DrawFn) -> tuple[IdentityCase, ...]:
    """One synthetic registry: every registered id paired with a return path.

    The registration list and the ids in play come from
    :func:`tests.verify.strategies.registry_scenarios`, so the shapes are not
    re-derived here: ``as_registry()`` supplies the ``(cid, title)`` pairs
    ``_run_check`` is called with, the scenario's own results supply the honest
    ``CheckResult`` bodies, and ``foreign_ids`` supplies ids that were never
    registered.
    """
    scenario = draw(registry_scenarios(modes=("complete", "foreign")))
    registered = scenario.registered_ids
    emitted = {result.cid: result for result in scenario.results}

    # An id no registration declared. The ``foreign`` divergence mode supplies one
    # directly; on a ``complete`` draw one is generated so both mismatch flavours -
    # another live row, and an unknown row - stay reachable on every example.
    foreign = scenario.foreign_ids or draw(
        check_ids(min_size=1, max_size=2).filter(
            lambda ids: all(cid not in registered for cid in ids)
        )
    )

    cases: list[IdentityCase] = []
    for cid, title, _placeholder in scenario.as_registry():
        behaviour = draw(st.sampled_from(_BEHAVIOURS))
        # The C46/C43 case first: reporting under a *registered* id corrupts a live
        # row. A never-registered id is the other half of the same defect.
        others = tuple(other for other in registered if other != cid) + tuple(foreign)
        other = draw(st.sampled_from(others))

        if behaviour == "match":
            returned = emitted.get(cid) or draw(check_results(cid=cid))
        elif behaviour == "mismatch":
            returned = emitted.get(other) or draw(check_results(cid=other))
        elif behaviour in {"bad_status_match", "bad_status_mismatch"}:
            base_cid = cid if behaviour == "bad_status_match" else other
            base = emitted.get(base_cid) or draw(check_results(cid=base_cid))
            returned = dataclasses.replace(base, status=draw(st.sampled_from(_BAD_STATUSES)))
        else:
            returned = None

        cases.append(
            IdentityCase(
                registered_cid=cid,
                registered_title=title,
                behaviour=behaviour,
                returned=returned,
                wrong_return=draw(st.sampled_from(_WRONG_RETURNS)),
                exception_name=draw(st.sampled_from(tuple(_EXCEPTIONS))),
            )
        )
    return tuple(cases)


# Feature: purpose-achievement-audit, Property 10: A check reports the identifier it is
# registered under
@given(cases=identity_cases())
def test_a_check_reports_the_identifier_it_is_registered_under(
    cases: tuple[IdentityCase, ...],
) -> None:
    """R10.5 / AD-14: emitted identity is the registered identity, on every path."""
    for case in cases:
        result = vc._run_check(case.registered_cid, case.registered_title, case.as_check())

        # Total: whatever the check did, exactly one result comes back, it carries a
        # status from the emitted vocabulary, and it is emitted under the id that was
        # registered - never under the id the check chose to report.
        assert isinstance(result, vc.CheckResult)
        assert result.cid == case.registered_cid
        assert result.status in vc.STATUSES

        if case.identity_diverges:
            # The coercion: a mismatch is a FAIL naming *both* ids, so a log reader
            # can see which row was corrupted and which check corrupted it.
            assert result.status == "FAIL"
            assert result.title == case.registered_title
            assert case.registered_cid in result.detail
            assert repr(case.reported_cid) in result.detail
            # The status the check reported is disclosed, not laundered into the
            # coerced FAIL: a mismatching PASS must not read as a self-reported FAIL.
            assert case.returned is not None
            if case.returned.status in vc.STATUSES:
                assert case.returned.status in result.detail
        elif case.behaviour == "match":
            # A matching id passes through untouched - same object, same status,
            # same detail. The guard adds no cost to the honest path.
            assert result is case.returned
        else:
            # Every other return path was already a FAIL before AD-14, and stays one.
            assert result.status == "FAIL"


@given(cases=identity_cases())
def test_the_existing_raise_type_and_status_coercions_are_unchanged(
    cases: tuple[IdentityCase, ...],
) -> None:
    """The three pre-AD-14 coercions still name their own defect (R8.7 preserved).

    The identity guard runs last and over the status coercion's output, so a result
    carrying *both* defects must disclose both: it is emitted under the registered id
    and its detail still names the out-of-vocabulary status.
    """
    for case in cases:
        result = vc._run_check(case.registered_cid, case.registered_title, case.as_check())

        if case.behaviour in {"raises", "import_failure"}:
            expected = (
                "ImportError" if case.behaviour == "import_failure" else case.exception_name
            )
            assert result.status == "FAIL"
            assert "check raised" in result.detail
            assert expected in result.detail
            assert result.title == case.registered_title
        elif case.behaviour == "wrong_type":
            assert result.status == "FAIL"
            assert "expected CheckResult" in result.detail
            assert type(case.wrong_return).__name__ in result.detail
        elif case.behaviour in {"bad_status_match", "bad_status_mismatch"}:
            assert case.returned is not None
            assert result.status == "FAIL"
            assert repr(case.returned.status) in result.detail
            assert "unknown status" in result.detail


@given(cases=identity_cases())
def test_a_registry_execution_emits_one_result_per_registered_id(
    cases: tuple[IdentityCase, ...],
) -> None:
    """R10.5 at registry scope: the emitted id set *is* the registered id set.

    This is the second half of the C46 defect - the row that was left with no result.
    With the coercion in place, ``collect_results`` is a bijection onto the
    registration list whatever the checks report, which is precisely the invariant the
    registry gate's id-totality rule (R1.7) relies on being sound.
    """
    registry = [
        (case.registered_cid, case.registered_title, case.as_check()) for case in cases
    ]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(vc, "_CHECKS", registry)
        results = vc.collect_results()
        counts = vc.status_counts(results)

    assert [result.cid for result in results] == [case.registered_cid for case in cases]
    assert sum(counts.values()) == len(results) == len(cases)

    # No result reports an id it was not registered under, so no foreign id can reach
    # the ledger and no registered id can be missing from it.
    registered = {case.registered_cid for case in cases}
    assert {result.cid for result in results} == registered

    # Every divergent case is attributed to FAIL under its own registered id.
    for case, result in zip(cases, results, strict=True):
        if case.identity_diverges:
            assert (result.cid, result.status) == (case.registered_cid, "FAIL")


def test_the_real_c46_registration_reports_c46_on_every_branch() -> None:
    """The defect this property closes, pinned statically (``verify_claims.py:1163``).

    Read, not run: executing C46 would drive the published-checkpoint probe, and the
    point here is the literal identifier in every ``CheckResult`` the function
    constructs. The coercion is the guard; this is the fix.
    """
    registered = {cid: fn for cid, _title, fn in vc._CHECKS}
    assert "C46" in registered, "C46 is no longer registered"

    tree = ast.parse(inspect.getsource(registered["C46"]))
    reported = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CheckResult"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert reported, "C46 constructs no CheckResult with a literal identifier"
    assert set(reported) == {"C46"}, f"C46 reports under {sorted(set(reported))}"
