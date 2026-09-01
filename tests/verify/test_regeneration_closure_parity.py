"""The regeneration job's dependency closure is identical to the truth-gates job's.

Feature: decision-quality-proof, session 2q, parent task 26.

WHY THIS PIN EXISTS. ``regenerate-truth-docs.yml::regenerate`` runs ``ledger_gen --write``
and ``readme_gen --write`` -- the REPAIR half of the three generators, which
``truth-gates.yml`` can only ``--check``. Both jobs execute the entire Check_Registry, and
several registered checks import an optional dependency inside a try/except and report SKIP
when it is absent (C45 needs torch, C46 the published-checkpoint stack, C58 synapse_common).
The README headline counts ``doc_truth`` pins were measured in the ``truth-gates`` closure.

So a THINNER closure in the regeneration job does not merely fail: it turns a PASS into a
SKIP, changes the counts, and then WRITES those wrong counts into ``docs/state/CURRENT.md``
and the README headline -- the two documents the job exists to correct. The artifact would
look like a successful regeneration. That is the failure mode this file forecloses.

WHY DUPLICATION PLUS A PIN, RATHER THAN AN EXTRACTED SHARED SCRIPT. Hoisting the closure
into a shell script both jobs call would remove the duplication, but it would also edit the
steps of a REQUIRED status-check workflow (``truth-gates`` is declared ``required`` in
``infrastructure/quality/required-checks.yaml``) to save a copy. Duplication that is
mechanically compared is cheaper than a refactor of the enforcement spine. The precedent for
reading an install closure before trusting it is HANDOFF defect 14: ``uplift/contract.py``
imports ``scipy``, which ``uplift.yml::twin-regret`` does not install, so routing one float
through the validating reader would have crashed the measurement at import inside the job
that exists to run it -- found by reading the closures, not by paying for a CI round trip.

WHAT THIS FILE DELIBERATELY DOES NOT DUPLICATE. Whether either job's steps propagate their
exit status is ``scripts/audit/workflow_shape_truth.py``'s answer, re-derived from the
workflow tree on every run against ``blocking-steps.yaml``'s declaration. Restating it here
would be a second model of one fact.

No ``max_examples`` is set: these are example-class facts about two committed files, not a
property over generated inputs, so there is no Hypothesis budget to inherit. Not
``slow``-marked -- it reads two small YAML files and spawns nothing. Locus is
``ci.yml::uplift-verify``'s fast step, which collects ``tests/uplift tests/verify``.

**CI DISCHARGE IS OWED, NOT HELD.** ``uplift-verify`` needs ``quality-gates`` to succeed and
``quality-gates`` fails at ``mypy --strict orchestrator/``, so this test has never executed
in CI. It is locally executed and CI-undischarged; parent task 27 is what unblocks it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

_INSTALL_STEP: Final[str] = "Install dependencies"

#: (workflow path, job id) for the two jobs whose closures must agree.
_REFERENCE: Final[tuple[str, str]] = (".github/workflows/truth-gates.yml", "truth-gates")
_MIRROR: Final[tuple[str, str]] = (".github/workflows/regenerate-truth-docs.yml", "regenerate")


def _install_command(workflow: str, job: str) -> str:
    """The ``run:`` body of ``job``'s install step, or fail naming what was missing.

    Every absence raises rather than returning a falsy value. Two jobs that both resolve to
    ``""`` would compare equal and report a closure parity nothing had checked -- the
    ``None == None`` hole C75 exists to close.
    """
    path = REPO_ROOT / workflow
    assert path.is_file(), f"{workflow} does not exist"

    document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{workflow} does not parse to a mapping"

    jobs = document.get("jobs")
    assert isinstance(jobs, dict), f"{workflow} declares no jobs mapping"
    assert job in jobs, f"{workflow} declares no job {job!r}"

    steps = jobs[job].get("steps")
    assert isinstance(steps, list), f"{workflow}::{job} declares no steps list"

    matching = [s for s in steps if isinstance(s, dict) and s.get("name") == _INSTALL_STEP]
    assert len(matching) == 1, (
        f"{workflow}::{job} holds {len(matching)} step(s) named {_INSTALL_STEP!r}; "
        "the closure pin resolves exactly one on each side, so a rename must fail here "
        "rather than silently comparing nothing"
    )

    command = matching[0].get("run")
    assert isinstance(command, str) and command.strip(), (
        f"{workflow}::{job}'s {_INSTALL_STEP!r} step has no non-empty `run:` body"
    )
    return command


def _normalise(command: str) -> tuple[str, ...]:
    """Line-ending- and indentation-insensitive form, preserving order.

    Order is preserved because pip resolution order is part of the closure: the
    ``truth-gates`` block deliberately upgrades ``pathspec`` and constrains ``starlette``
    AFTER the bulk installs, and reordering those would change what is resolved.
    """
    lines = command.replace("\r\n", "\n").split("\n")
    return tuple(stripped for line in lines if (stripped := line.strip()))


def test_the_two_install_closures_are_identical() -> None:
    """The load-bearing assertion: same commands, same order, on both sides."""
    reference = _normalise(_install_command(*_REFERENCE))
    mirror = _normalise(_install_command(*_MIRROR))

    assert mirror == reference, (
        "the regeneration job's dependency closure has drifted from "
        f"{_REFERENCE[0]}::{_REFERENCE[1]}'s.\n"
        f"  reference ({len(reference)} command(s)): {reference}\n"
        f"  mirror    ({len(mirror)} command(s)): {mirror}\n"
        "A thinner or reordered closure turns a registered check's PASS into a SKIP, "
        "changes the counts, and writes the wrong numbers into docs/state/CURRENT.md and "
        "the README headline. Copy the reference block verbatim; do not adjust this test."
    )


def test_neither_closure_is_vacuous() -> None:
    """A parity test over two empty strings would pass while checking nothing.

    Asserted as a shape, not as a count: ``pip install`` must appear, and there must be more
    than one command. The number of commands is deliberately NOT pinned -- that is a total,
    and a legitimate addition to the reference closure would fail on the total rather than on
    the parity the file is about (CF-13).
    """
    for workflow, job in (_REFERENCE, _MIRROR):
        commands = _normalise(_install_command(workflow, job))
        assert len(commands) > 1, f"{workflow}::{job}'s closure is a single command"
        assert any("pip install" in c for c in commands), (
            f"{workflow}::{job}'s closure installs nothing with pip"
        )


def test_a_missing_job_is_refused_rather_than_read_as_agreement() -> None:
    """The refusal path, proven by construction rather than by never being triggered.

    "No case exercised it" is not evidence that a guard works. If ``_install_command``
    returned a falsy value for an absent job instead of raising, a renamed or deleted job
    would make both sides ``""`` and the parity assertion above would report agreement having
    compared nothing. Both absences are exercised here against the real files: a job that is
    not declared, and a step name that is not present in a job that is.
    """
    with pytest.raises(AssertionError, match="declares no job"):
        _install_command(_MIRROR[0], "no-such-job")

    with pytest.raises(AssertionError, match="does not exist"):
        _install_command(".github/workflows/no-such-workflow.yml", "regenerate")


def test_a_drifted_closure_is_reported_as_inequality() -> None:
    """The comparison itself discriminates, which the passing case cannot show.

    ``_normalise`` is order-preserving on purpose -- the reference block upgrades
    ``pathspec`` and constrains ``starlette`` after the bulk installs -- so a REORDERED
    closure must compare unequal, not merely a thinner one. Both are checked against the real
    reference block rather than against invented strings.
    """
    reference = _normalise(_install_command(*_REFERENCE))

    thinned = reference[:-1]
    assert thinned != reference, "dropping a command must not compare equal"

    reordered = (reference[-1], *reference[:-1])
    assert reordered != reference, "reordering commands must not compare equal"
