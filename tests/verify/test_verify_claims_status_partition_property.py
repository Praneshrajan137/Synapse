"""Property-based test for the ``verify_claims`` status partition.

Feature: core-purpose-uplift, Property 25: The verify_claims status partition is
exhaustive and disjoint

    *For any* execution of the ``verify_claims`` suite, every registered check is
    assigned exactly one status in ``{PASS, FAIL, PARTIAL, SKIP}``, and the four
    category counts sum to the reported TOTAL, which equals the number of registered
    checks — no check is silently omitted.

    Requirement 8.7: while the suite executes, every registered check lands in exactly
    one emitted category, the four counts sum to the reported TOTAL, and no check is
    silently dropped from the count.

The real 53-check suite shells out to git/docker probes and takes minutes, so it is
never executed per example. Instead synthetic registries are generated — well-behaved
checks, checks that raise, checks that return the wrong type, and checks that report an
out-of-vocabulary status — and ``collect_results`` / ``status_counts`` / ``run`` are
driven over them. The real registry is covered once by an example test that stubs the
probe callables while keeping the real registration list.

**Validates: Requirements 8.7**
"""
from __future__ import annotations

import contextlib
import io
import re
from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scripts.audit import verify_claims as vc

if TYPE_CHECKING:
    from collections.abc import Callable

# Behaviours a registered check can exhibit. Only "good" keeps its own status; the
# other three are defects that must still occupy exactly one category (an explicit
# FAIL) rather than aborting the run or vanishing from the counts.
_GOOD, _RAISES, _WRONG_TYPE, _BAD_STATUS = "good", "raises", "wrong_type", "bad_status"

_EXC_TYPES = (RuntimeError, ValueError, KeyError, OSError, ZeroDivisionError)
_WRONG_RETURNS = (None, "PASS", 42, (), {"status": "PASS"}, ["PASS"])
# Statuses outside vc.STATUSES: near-misses (case/tense) plus outright nonsense.
_BAD_STATUSES = ("", "pass", "Pass", "PASSED", "OK", "FAILED", "WARN", "UNKNOWN", "None")

_SUMMARY = re.compile(
    r"Summary: PASS=(?P<PASS>\d+) FAIL=(?P<FAIL>\d+) PARTIAL=(?P<PARTIAL>\d+) "
    r"SKIP=(?P<SKIP>\d+) TOTAL=(?P<TOTAL>\d+)"
)


@st.composite
def _check_specs(draw: st.DrawFn) -> tuple[str, str]:
    """Draw one check behaviour: (kind, payload)."""
    kind = draw(st.sampled_from([_GOOD, _RAISES, _WRONG_TYPE, _BAD_STATUS]))
    if kind == _GOOD:
        return kind, draw(st.sampled_from(vc.STATUSES))
    if kind == _RAISES:
        return kind, draw(st.sampled_from([e.__name__ for e in _EXC_TYPES]))
    if kind == _WRONG_TYPE:
        return kind, draw(st.sampled_from([repr(v) for v in _WRONG_RETURNS]))
    return kind, draw(st.sampled_from(_BAD_STATUSES))


def _make_check(cid: str, title: str, kind: str, payload: str) -> Callable[[], object]:
    if kind == _GOOD:
        return lambda: vc.CheckResult(cid, title, payload, "synthetic well-behaved check")
    if kind == _RAISES:
        exc = next(e for e in _EXC_TYPES if e.__name__ == payload)

        def _boom() -> object:
            raise exc("synthetic failure")

        return _boom
    if kind == _WRONG_TYPE:
        value = next(v for v in _WRONG_RETURNS if repr(v) == payload)
        return lambda: value
    return lambda: vc.CheckResult(cid, title, payload, "synthetic out-of-vocabulary status")


def _registry(
    specs: list[tuple[str, str]],
) -> list[tuple[str, str, Callable[[], object]]]:
    return [
        (f"S{i}", f"synthetic check {i}", _make_check(f"S{i}", f"synthetic check {i}", kind, load))
        for i, (kind, load) in enumerate(specs)
    ]


# Feature: core-purpose-uplift, Property 25: The verify_claims status partition is
# exhaustive and disjoint
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(specs=st.lists(_check_specs(), max_size=12))
def test_status_partition_is_exhaustive_and_disjoint(specs: list[tuple[str, str]]) -> None:
    """R8.7: one status per registered check, four counts summing to TOTAL."""
    registry = _registry(specs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(vc, "_CHECKS", registry)
        results = vc.collect_results()
        counts = vc.status_counts(results)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = vc.run(as_json=False)

    # Exhaustive: one result per registered check, in registration order — a check that
    # raises or misbehaves is coerced, never dropped.
    assert len(results) == len(registry)
    assert [r.cid for r in results] == [cid for cid, _t, _f in registry]

    # Every result carries exactly one status from the emitted vocabulary.
    assert all(r.status in vc.STATUSES for r in results)

    # Disjoint: each category counts exactly its own members, and the four categories
    # are the whole vocabulary.
    assert set(counts) == set(vc.STATUSES)
    for status in vc.STATUSES:
        assert counts[status] == sum(1 for r in results if r.status == status)

    # The four counts sum to TOTAL == number of registered checks.
    assert sum(counts.values()) == len(results) == len(registry)

    # Defective checks are attributed to FAIL, not omitted; well-behaved checks keep
    # their reported status.
    expected = {status: 0 for status in vc.STATUSES}
    for kind, load in specs:
        expected[load if kind == _GOOD else "FAIL"] += 1
    assert counts == expected

    # The reported headline reproduces the same partition, and a FAIL (including a
    # coerced one) is what drives the non-zero exit code.
    match = _SUMMARY.search(stdout.getvalue())
    assert match is not None, stdout.getvalue()
    reported = {k: int(v) for k, v in match.groupdict().items()}
    assert reported["TOTAL"] == len(registry)
    assert sum(reported[s] for s in vc.STATUSES) == reported["TOTAL"]
    for status in vc.STATUSES:
        assert reported[status] == counts[status]
    assert exit_code == (1 if counts["FAIL"] else 0)


def test_real_registry_total_equals_registered_check_count() -> None:
    """R8.7 on the real suite: TOTAL == len(_CHECKS), with unique cids.

    The registered probes are stubbed (they shell out to git/docker and take minutes),
    but the real registration list drives the count, so a check registered twice or
    dropped from the summary would be caught.
    """
    real = list(vc._CHECKS)
    cids = [cid for cid, _t, _f in real]
    assert len(cids) == len(set(cids)), "duplicate check ids in the registry"
    assert all(callable(fn) for _c, _t, fn in real)

    stubbed = [
        (cid, title, (lambda c=cid, t=title: vc.CheckResult(c, t, "PASS", "stubbed probe")))
        for cid, title, _fn in real
    ]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(vc, "_CHECKS", stubbed)
        results = vc.collect_results()
        counts = vc.status_counts(results)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            vc.run(as_json=False)

    match = _SUMMARY.search(stdout.getvalue())
    assert match is not None, stdout.getvalue()
    assert int(match.group("TOTAL")) == len(real) == sum(counts.values())
