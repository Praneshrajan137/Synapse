"""The recursion guard's verdict is provable without executing the Check_Registry.

Feature: decision-quality-proof, task 4.4. Requirement **R4.9**: "WHEN the
recursion-guard environment flag is set, THE headline-counts claim SHALL report a
non-passing, ``required`` status naming the guard as the cause, and an automated test
SHALL assert that status without executing the Check_Registry suite."

**Why this file exists, precisely.** The guard itself has always been correct:
``doc_truth::_claim_readme_headline_counts`` executes ``verify_claims`` as a subprocess
and the child carries ``SYNAPSE_DOC_TRUTH_NESTED=1``, so the child's copy of this one
claim self-excludes and the recursion is bounded at depth one. What was missing is a
*proof of the guard's verdict*. The claim is REQUIRED, so its guarded ``skip`` is what
drives the whole ``doc_truth`` aggregate to ``unavailable`` (exit 2, non-passing) - and
that consequence had no test at all. The only two tests that so much as mention the flag
(``tests/verify/test_headline_count_pin_property.py`` and
``tests/verify/test_headline_pin_skip_property.py``) ``delenv`` it, i.e. they deliberately
put the guard *outside* their scope. So the plan's claim that nothing in the test tree
references the guard is slightly off - two files reference it in order to switch it off -
but its conclusion is right: nothing asserted what it does.

**No Check_Registry execution happens here, and that is a hard requirement of the test,
not a preference.** Executing the suite is a 900s-bounded subprocess that shells out to
git and docker probes - a category-2/3 workload under I-0 that belongs to CI. The subject
is therefore :func:`scripts.audit.doc_truth.headline_claim_under_guard`, a pure function
of the environment mapping it is handed, plus :func:`doc_truth.evaluate_claims`, the pure
aggregate seam. Both read no file, spawn no process and hold no process state. As a
belt-and-braces guard against a future refactor reintroducing a shell-out on this path,
``doc_truth.subprocess`` is replaced, in every test here, with a stand-in that fails loudly
if anything reaches for it - except in the one test that must inspect the child's
environment, where it is replaced by a recorder that captures the call and returns a canned
payload instead of spawning anything.

**The guard is asserted end to end, in three links, because any one of them alone proves
less than it appears to.** (1) The flag fires the guard - a ``required`` ``skip`` naming
the cause. (2) The flag the *parent* injects into the child process is that same flag:
without this link the test would prove a guard fires on a variable nothing sets, and
``headline_claim_under_guard`` takes its mapping as an argument precisely so this can be
checked. It is established by recording ``subprocess.run``'s ``env`` kwarg, never by
letting the call through. (3) The guarded skip translates, through
``verify_claims.GATE_STATUS``, into the nested ``SKIP`` for the comparing check that
``readme_gen`` states the R4.8 compensation from - which is why ``README.md`` reads
51/3/0/10/64 where ``docs/state/CURRENT.md`` reads 52/3/0/9/64 (AD-21). Every identifier,
status literal and env-var name in those links is imported from the module that owns it
(``dt._NESTED_ENV``, ``dt.HEADLINE_CLAIM_NAME``, ``dt._VERIFY_CLAIMS_MENTION``,
``readme_gen.GUARD_*``, ``verify_claims.GATE_STATUS``), so this file adds nothing new that
can drift (AD-13).

Plain assertions, no Hypothesis: the guard's input space is "the flag is set to something
truthy" and "it is not", which is enumerated here exhaustively rather than sampled. There
is consequently no example budget to inherit and no ``max_examples`` anywhere in this file
(I-0's authoring rule).

**Validates: Requirement 4.9** (and pins R4.6 / R4.7 as regressions on this path).
"""

from __future__ import annotations

import json
import os
import subprocess
from types import SimpleNamespace
from typing import Any, Final

import pytest

from scripts.audit import doc_truth as dt
from scripts.audit import readme_gen, verify_claims

#: Values of ``SYNAPSE_DOC_TRUTH_NESTED`` that must all fire the guard. ``verify_claims``
#: is spawned with the flag set to ``"1"``, but the guard is a truthiness test, so any
#: non-empty value must be honoured - a child that set it to ``"true"`` must not recurse.
_TRUTHY_FLAGS = ("1", "true", "yes", "0", "anything")

#: The empty string is the one value that must NOT fire the guard: ``os.environ`` cannot
#: hold ``None``, and an empty value is how a shell exports "unset but present".
_FALSY_FLAGS = ("",)

#: The real function, captured before any fixture can replace the module attribute. One
#: test drives ``nested_suite_counts`` itself - to read the environment it hands the child
#: - and must therefore reach past the autouse stand-in that protects every other test.
#: The subprocess seam is still stubbed there, so no suite is executed either way.
_REAL_NESTED_SUITE_COUNTS: Final = dt.nested_suite_counts


def _stub_payload() -> str:
    """A minimal, parseable ``verify_claims --json`` payload.

    The counts are zero and deliberately meaningless: the test that uses this asserts on
    the *environment* the child is given, not on any number. It has to parse only so that
    ``nested_suite_counts`` returns a verdict, which is what proves the recorder
    intercepted the real call path rather than the test passing on a failure branch.
    """
    return json.dumps(
        {
            "summary": {category.lower(): 0 for category in dt._HEADLINE_CATEGORIES},
            "checks": [
                {
                    "cid": readme_gen.GUARD_CHECK_ID,
                    "title": "documented numbers agree with their mechanical source",
                    "status": readme_gen.GUARD_STATUS_NESTED,
                    "detail": "recursion guard",
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _aggregate_with_passing_siblings(claim: dt.ClaimResult) -> dt.DocProbe:
    """``claim`` aggregated against a deliberately large set of passing siblings.

    The count matters: the defect R4.6 / R4.7 record as discharged returned ``ok`` as soon
    as *any* claim was ``ok``, so a single sibling would have masked the guarded skip.
    """
    siblings = tuple(
        dt.ClaimResult(name=f"pin-{index}", status="ok", required=True, detail="agrees")
        for index in range(12)
    )
    return dt.evaluate_claims((*siblings, claim))


@pytest.fixture(autouse=True)
def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if anything on this path tries to execute the suite (I-0)."""

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "the recursion-guard test must never execute the Check_Registry suite; "
            "the guarded verdict is a pure function of the environment"
        )

    monkeypatch.setattr(
        dt,
        "subprocess",
        SimpleNamespace(run=_boom, SubprocessError=subprocess.SubprocessError),
    )
    monkeypatch.setattr(dt, "nested_suite_counts", _boom)


@pytest.mark.parametrize("flag", _TRUTHY_FLAGS)
def test_guard_reports_a_non_passing_required_status_naming_the_guard(flag: str) -> None:
    """R4.9: set the flag, and the claim reports a required, non-passing, named skip."""
    claim = dt.headline_claim_under_guard({dt._NESTED_ENV: flag})

    assert claim is not None, f"{dt._NESTED_ENV}={flag!r} must fire the recursion guard"

    # Non-passing. `skip` is the claim vocabulary's non-passing state, and the point of
    # asserting it is that the status is NOT `ok`, because absence of proof is never a
    # pass (I-7). A second `!= "ok"` assertion is deliberately NOT written here: mypy
    # narrows the status to `Literal["skip"]` after the line above and reports the
    # comparison as non-overlapping, so the redundant guard would fail the type check
    # while proving nothing the equality does not already prove.
    assert claim.status == "skip", claim.detail

    # REQUIRED is the load-bearing half. An optional skip would be absorbed by any
    # passing sibling, which is the exact masking defect R4.6/R4.7 record as discharged.
    assert claim.required is True

    # The cause is named, and named specifically enough to act on: the environment
    # variable itself and the mechanism, not just "skipped".
    assert claim.name == dt.HEADLINE_CLAIM_NAME
    assert dt._NESTED_ENV in claim.detail
    assert "recursion guard" in claim.detail.lower()


@pytest.mark.parametrize("flag", _FALSY_FLAGS)
def test_an_empty_flag_does_not_fire_the_guard(flag: str) -> None:
    """The guard must not self-exclude on an empty value, or C56 could never pass."""
    assert dt.headline_claim_under_guard({dt._NESTED_ENV: flag}) is None


def test_an_absent_flag_does_not_fire_the_guard() -> None:
    """A top-level run has no flag at all, and must proceed to the real comparison."""
    assert dt.headline_claim_under_guard({}) is None


def test_the_guarded_claim_forces_the_aggregate_to_unavailable() -> None:
    """The consequence R4.6 / R4.7 pin: a guarded skip is reported, never masked.

    Driven through ``evaluate_claims`` - the pure aggregate - with a deliberately large
    set of passing siblings, because the defect this replaced returned ``ok`` as soon as
    *any* claim was ``ok``. The verdict must be ``unavailable`` (exit 2) and must name
    the guarded claim.
    """
    guarded = dt.headline_claim_under_guard({dt._NESTED_ENV: "1"})
    assert guarded is not None

    probe = _aggregate_with_passing_siblings(guarded)

    assert probe.status == "unavailable"
    assert probe.passing is False
    assert dt._EXIT_CODES[probe.status] == dt.EXIT_UNAVAILABLE
    assert guarded.name in probe.detail
    assert dt._NESTED_ENV in probe.detail


def test_the_claim_function_returns_the_guarded_verdict_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The claim delegates to the guard rather than carrying a second copy of it.

    Without this, ``headline_claim_under_guard`` could drift from the branch actually
    taken by ``_claim_readme_headline_counts`` and the assertions above would be proving
    something about an unused function. ``README.md`` is never read on this path: the
    guard branch precedes the read, which is also why this test costs nothing.
    """
    monkeypatch.setenv(dt._NESTED_ENV, "1")
    monkeypatch.setattr(
        dt,
        "_read",
        lambda _path: pytest.fail("the guard must return before README.md is read"),
    )

    assert dt._claim_readme_headline_counts() == dt.headline_claim_under_guard(
        {dt._NESTED_ENV: "1"}
    )


def test_the_child_execution_is_handed_the_flag_that_fires_the_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second link: the flag the parent injects is the flag the guard reads.

    Without this the file would prove that a guard fires on a variable, and separately
    that a claim skips when that variable is set, while never establishing that anything
    sets it - the recursion would be unbounded and every assertion above would still pass.

    The suite is not executed. ``doc_truth.subprocess`` is replaced by a recorder that
    captures the ``env`` mapping and returns a canned payload, so the 900s
    ``subprocess.run`` is never reached. The real ``nested_suite_counts`` is called through
    the reference captured at import, deliberately stepping around the autouse stand-in;
    that is safe *because* the subprocess seam beneath it is stubbed, and it is necessary
    because the environment is built inside that function.
    """
    monkeypatch.delenv(dt._NESTED_ENV, raising=False)
    recorded_env: dict[str, str] = {}
    recorded_argv: list[str] = []

    def _record(argv: list[str], **kwargs: Any) -> SimpleNamespace:
        recorded_argv.extend(argv)
        recorded_env.update(kwargs["env"])
        return SimpleNamespace(stdout=_stub_payload(), stderr="", returncode=0)

    monkeypatch.setattr(
        dt,
        "subprocess",
        SimpleNamespace(run=_record, SubprocessError=subprocess.SubprocessError),
    )

    verdict, error = _REAL_NESTED_SUITE_COUNTS()

    # The recorder was on the real path: a verdict came back and nothing was reported
    # unresolved, so the assertions below read a genuinely constructed child environment.
    assert error == ""
    assert verdict is not None

    # The child runs the suite whose claim self-excludes - matched with doc_truth's own
    # pattern rather than a restated module path.
    assert any(dt._VERIFY_CLAIMS_MENTION.search(arg) for arg in recorded_argv), recorded_argv

    # ...and it carries a flag that fires the guard. Asserted by feeding the recorded
    # mapping to the guard itself, which is stronger than comparing it to "1": whatever
    # the parent sets, the child's copy of the claim must self-exclude on it.
    assert dt._NESTED_ENV in recorded_env
    assert dt.headline_claim_under_guard(recorded_env) is not None

    # And the parent's own environment is untouched. A guard that leaked into os.environ
    # would make every later top-level claim self-exclude in the same process - C56 would
    # stop comparing anything at all and report SKIP forever.
    assert dt._NESTED_ENV not in os.environ


def test_the_guarded_aggregate_is_the_nested_skip_the_readme_compensation_states() -> None:
    """The third link: ``unavailable`` becomes the nested ``SKIP`` for the comparing check.

    This is the AD-21 delta, and it is the reason the two published headlines differ. The
    translation lives in ``verify_claims.GATE_STATUS`` and ``readme_gen`` renders R4.8's
    compensation from the nested status; if the two ever disagreed, the README would
    disclose a compensation the registry does not apply. Both sides are imported.
    """
    guarded = dt.headline_claim_under_guard({dt._NESTED_ENV: "1"})
    assert guarded is not None

    nested_status = verify_claims.GATE_STATUS[_aggregate_with_passing_siblings(guarded).status]

    assert nested_status == readme_gen.GUARD_STATUS_NESTED
    assert nested_status in verify_claims.STATUSES

    # Non-passing, derived rather than restated: whatever PASS is spelled as, an
    # unavailable aggregate must not map onto it (I-7).
    assert nested_status != verify_claims.GATE_STATUS["ok"]

    # The delta AD-21 exists to explain is a real delta, not a tautology.
    assert readme_gen.GUARD_STATUS_NESTED != readme_gen.GUARD_STATUS_TOP_LEVEL
