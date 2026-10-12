"""Property-based test for C56 unavailable-source / unavailable-suite skip semantics.

Feature: core-purpose-uplift, Property 24: Unavailable pinned source or suite yields
skip, never a pass.

    *For any* pinned C56 claim whose source file is missing/unreadable, or whose
    ``verify_claims`` execution or summary parse fails, the claim reports ``skip``
    naming the absent source or the failure, and never reports a pass.

    Requirement 8.5: a missing or unreadable source file a pinned C56 claim depends on
    yields a skip naming the absent source, never counted as a pass.
    Requirement 8.6: a ``verify_claims`` suite that cannot be executed, or whose emitted
    summary cannot be parsed, yields a skip naming the failure, never a pass.

Every unavailability is injected at a seam: the README through ``doc_truth._read``, the
suite script through ``doc_truth.VERIFY_CLAIMS_PY``, and the suite execution through
``doc_truth.subprocess``. The real ``verify_claims`` suite (minutes of git/docker
probes) is never executed — in the source-unavailability modes ``nested_suite_counts``
and ``subprocess`` are both replaced with booby-trapped stand-ins, so an accidental
shell-out fails the test loudly instead of running the suite.

The execution seam is ``nested_suite_counts`` (public since feature
decision-quality-proof task 4.1, which promoted it out of ``_suite_counts`` so
``scripts/audit/readme_gen.py`` can project the README from the same execution this claim
compares against - AD-21). This test moved with the rename in the same change: a
``monkeypatch`` naming a function that no longer exists raises rather than silently
skipping the protection it provides.

**Validates: Requirements 8.5, 8.6**
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scripts.audit import doc_truth as dt

_CATEGORIES = dt._HEADLINE_CATEGORIES  # ("PASS", "FAIL", "PARTIAL", "SKIP", "TOTAL")

# Unavailability modes. The first three starve the claim of a *source* (R8.5); the last
# two starve it of its *mechanical source of truth*, the suite summary (R8.6).
_MODES = (
    "readme_unreadable",  # README.md missing / OSError on read
    "verify_claims_missing",  # scripts/audit/verify_claims.py absent
    "no_headline_line",  # README readable but states no headline counts
    "suite_exec_failure",  # suite could not be executed (OSError / SubprocessError / timeout)
    "suite_unparseable",  # suite ran but its summary could not be parsed
)

# Prose that must NOT be mistaken for a headline line: it either names the suite without
# carrying a count, or carries counts without naming the suite.
_DECOYS = (
    "A SKIP is not a PASS, and `verify-claims` never fabricates one.",
    "The `verify_claims` suite is the mechanical source of truth for this headline.",
    "- 623 tests pass in the regression floor.",
    "PASS/FAIL/PARTIAL/SKIP are the four verify-claims status categories.",
    "Coverage sits at TOTAL=99 percent for spec-covered modules.",
)

# Payloads the summary parser must reject: no JSON object and no `Summary:` line, a
# truncated JSON summary, non-integer counts, and a `Summary:` line missing a category.
_UNPARSEABLE = (
    "",
    "<no output>",
    "Traceback (most recent call last):\n  ImportError: no module named scripts\n",
    '{"summary": {"pass": 1, "fail": 2}}',
    '{"summary": {"pass": "1", "fail": 2, "partial": 0, "skip": 0, "total": 3}}',
    '{"summary": {"pass": true, "fail": 2, "partial": 0, "skip": 0, "total": 3}}',
    "Summary: PASS=4 FAIL=1 PARTIAL=0 SKIP=2",
    "Summary line intentionally malformed",
)


def _exec_failures() -> tuple[BaseException, ...]:
    """Failure modes ``nested_suite_counts`` must convert into a skip, not a pass."""
    return (
        OSError(2, "No such file or directory"),
        PermissionError(13, "Permission denied"),
        subprocess.SubprocessError("suite crashed before emitting a summary"),
        subprocess.TimeoutExpired(
            cmd=["python", "-m", "scripts.audit.verify_claims"], timeout=dt._SUITE_TIMEOUT_S
        ),
    )


@st.composite
def _unavailability(draw: st.DrawFn) -> dict[str, Any]:
    """Draw one unavailability scenario: the mode plus whatever it needs injected."""
    mode = draw(st.sampled_from(_MODES))
    counts = {cat: draw(st.integers(min_value=0, max_value=99)) for cat in _CATEGORIES}
    decoys = draw(st.lists(st.sampled_from(_DECOYS), min_size=0, max_size=4))

    if mode == "no_headline_line":
        # Readable README with prose only: no line both names the suite and carries a
        # count, so the claim has no pinned source value to compare against.
        body = "\n".join(["# SYNAPSE", "", *decoys, ""])
    else:
        headline = "- `verify-claims` suite headline: " + " / ".join(
            f"{counts[cat]} {cat}" for cat in _CATEGORIES
        )
        body = "\n".join(["# SYNAPSE", "", *decoys, headline, ""])

    return {
        "mode": mode,
        "readme": None if mode == "readme_unreadable" else body,
        "exc": draw(st.sampled_from(_exec_failures())) if mode == "suite_exec_failure" else None,
        "stdout": draw(st.sampled_from(_UNPARSEABLE)) if mode == "suite_unparseable" else "",
        "stderr": draw(st.sampled_from(("", "warning: docker probe unavailable"))),
        "returncode": draw(st.sampled_from((0, 1, 2, -9))),
    }


def _explode(label: str) -> Any:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"the property test must never {label}")

    return _boom


def _subprocess_stub(case: dict[str, Any]) -> SimpleNamespace:
    """A stand-in for ``doc_truth.subprocess`` that never spawns the real suite."""
    if case["mode"] == "suite_exec_failure":

        def _run(*args: Any, **kwargs: Any) -> Any:
            raise case["exc"]

    elif case["mode"] == "suite_unparseable":

        def _run(*args: Any, **kwargs: Any) -> Any:
            return SimpleNamespace(
                stdout=case["stdout"], stderr=case["stderr"], returncode=case["returncode"]
            )

    else:
        _run = _explode("execute the real verify_claims suite")

    return SimpleNamespace(run=_run, SubprocessError=subprocess.SubprocessError)


# Feature: core-purpose-uplift, Property 24: Unavailable pinned source or suite yields
# skip, never a pass.
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_unavailability())
def test_unavailable_source_or_suite_yields_skip_never_a_pass(case: dict[str, Any]) -> None:
    """Any unavailable source or unrunnable/unparseable suite skips, naming the cause."""
    mode = case["mode"]
    suite_reachable = mode in ("suite_exec_failure", "suite_unparseable")

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv(dt._NESTED_ENV, raising=False)
        mp.setattr(dt, "_read", lambda _path: case["readme"])
        mp.setattr(dt, "subprocess", _subprocess_stub(case))
        if mode == "verify_claims_missing":
            absent = Path(dt.ROOT) / "scripts" / "audit" / "__absent__.py"
            mp.setattr(dt, "VERIFY_CLAIMS_PY", absent)
        if not suite_reachable:
            # The claim must short-circuit before reaching for the suite at all.
            mp.setattr(dt, "nested_suite_counts", _explode("reach the suite for an absent source"))
        result = dt._claim_readme_headline_counts()

    # R8.5 / R8.6: skip, and never a pass — an unavailable pin is never credited.
    assert result.status == "skip", f"{mode}: expected skip, got {result.status}: {result.detail}"
    assert result.status != "ok"
    assert result.detail.strip(), f"{mode}: skip must name the cause"

    detail = result.detail.lower()
    if mode == "readme_unreadable":
        assert "readme.md" in detail and ("missing" in detail or "unreadable" in detail)
    elif mode == "verify_claims_missing":
        assert "verify_claims.py" in detail and "missing" in detail
    elif mode == "no_headline_line":
        assert "headline" in detail and "readme.md" in detail
    elif mode == "suite_exec_failure":
        assert "could not be executed" in detail
        assert type(case["exc"]).__name__.lower() in detail
    else:
        assert "could not be parsed" in detail
        assert str(case["returncode"]) in result.detail
