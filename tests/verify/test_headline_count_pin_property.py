"""Property-based test for the C56 README headline-count pin.

Feature: core-purpose-uplift, Property 23: The headline-count pin passes iff every count
matches, else fails naming each drift.

    *For any* README headline counts and ``verify_claims`` suite summary, the C56
    headline-count claim passes iff all five counts (PASS, FAIL, PARTIAL, SKIP, TOTAL)
    match the suite-derived counts, and otherwise fails with a detail that names each
    drifted category together with its README-claimed value and the suite-reported
    value; the "actual" values are derived from the suite output at evaluation time,
    not from any constant.

    Requirement 8.1: the README headline reports counts that each equal the
    corresponding value in the suite summary.
    Requirement 8.2: the C56 claim pins each README count to the suite-derived value,
    obtained at evaluation time rather than hardcoded.
    Requirement 8.3: any differing count fails, naming each drifted category with its
    claimed and suite-reported values.

Both sides of the comparison are generated: the README text is injected through
``doc_truth._read`` and the suite summary through ``doc_truth._suite_counts``, so the
real ``verify_claims`` suite (which shells out to git/docker probes and takes minutes)
is never executed. ``doc_truth.subprocess`` is replaced with a booby-trapped stand-in so
an accidental shell-out fails the test loudly instead of running for minutes.

**Validates: Requirements 8.1, 8.2, 8.3**
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scripts.audit import doc_truth as dt

_CATEGORIES = dt._HEADLINE_CATEGORIES  # ("PASS", "FAIL", "PARTIAL", "SKIP", "TOTAL")

# Per-category README rendering modes:
#   match  -> the README states exactly the suite-reported count (no drift)
#   drift  -> the README states a different non-negative count (drift)
#   absent -> the README omits the category entirely (drift, claimed == "absent")
_MODES = ("match", "drift", "absent")

# A decoy line that names the suite but carries no count, plus surrounding prose, so
# the claim's headline-line selection is exercised rather than assumed.
_PREAMBLE = (
    "# SYNAPSE",
    "",
    "Mechanical verification: a SKIP is not a PASS, and verify-claims never fabricates.",
    "",
)
_EPILOGUE = ("", "See docs/ for the full gate registry.", "")


def _readme(headline: str) -> str:
    return "\n".join([*_PREAMBLE, headline, *_EPILOGUE])


@st.composite
def _pin_cases(draw: st.DrawFn) -> tuple[dict[str, int], dict[str, int | None]]:
    """Draw a (suite summary, README-claimed counts) pair.

    The suite summary is a totalled partition (PASS+FAIL+PARTIAL+SKIP == TOTAL, R8.7);
    the README side independently matches, drifts, or omits each category.
    """
    parts = {cat: draw(st.integers(min_value=0, max_value=99)) for cat in _CATEGORIES[:-1]}
    actual: dict[str, int] = {**parts, "TOTAL": sum(parts.values())}

    modes = {cat: draw(st.sampled_from(_MODES)) for cat in _CATEGORIES}
    if all(mode == "absent" for mode in modes.values()):
        # An all-absent README has no extractable count at all, which the claim treats
        # as "no headline line" -> skip (that is Property 24's territory, not 23), so
        # keep at least one category on the line.
        modes[_CATEGORIES[0]] = draw(st.sampled_from(("match", "drift")))

    claimed: dict[str, int | None] = {}
    for cat in _CATEGORIES:
        mode = modes[cat]
        if mode == "absent":
            claimed[cat] = None
        elif mode == "match":
            claimed[cat] = actual[cat]
        else:
            delta = draw(st.integers(min_value=1, max_value=20))
            down = draw(st.booleans())
            subtract = down and actual[cat] >= delta
            claimed[cat] = actual[cat] - delta if subtract else actual[cat] + delta
    return actual, claimed


def _exploding_subprocess() -> SimpleNamespace:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the property test must never execute the real suite")

    return SimpleNamespace(run=_boom, SubprocessError=subprocess.SubprocessError)


# Feature: core-purpose-uplift, Property 23: The headline-count pin passes iff every
# count matches, else fails naming each drift.
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_pin_cases())
def test_headline_pin_passes_iff_every_count_matches_else_names_each_drift(
    case: tuple[dict[str, int], dict[str, int | None]],
) -> None:
    """The C56 claim is ok IFF no count drifted; otherwise it fails naming every drift."""
    actual, claimed = case
    headline = "- `verify-claims` suite headline: " + " / ".join(
        f"{claimed[cat]} {cat}" for cat in _CATEGORIES if claimed[cat] is not None
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv(dt._NESTED_ENV, raising=False)
        mp.setattr(dt, "_read", lambda _path: _readme(headline))
        mp.setattr(dt, "_suite_counts", lambda: (dict(actual), ""))
        mp.setattr(dt, "subprocess", _exploding_subprocess())
        result = dt._claim_readme_headline_counts()

    drifted = [cat for cat in _CATEGORIES if claimed[cat] != actual[cat]]

    if not drifted:
        # R8.1/R8.2: every count matches -> pass, and the pass detail reports the
        # suite-derived values (which vary per example, so they cannot be constants).
        assert result.status == "ok", result.detail
        for cat in _CATEGORIES:
            assert f"{cat}={actual[cat]}" in result.detail
        return

    # R8.3: any drift -> failure, never a pass.
    assert result.status == "fail", result.detail
    for cat in drifted:
        entry = (
            f"{cat} (README claims {'absent' if claimed[cat] is None else claimed[cat]}, "
            f"suite reports {actual[cat]})"
        )
        assert entry in result.detail, f"{cat} drift not named: {result.detail}"
    for cat in _CATEGORIES:
        if cat not in drifted:
            assert f"{cat} (README claims" not in result.detail, (
                f"{cat} matched but was reported as drifted: {result.detail}"
            )
