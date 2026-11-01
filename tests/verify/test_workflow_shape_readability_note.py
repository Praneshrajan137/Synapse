"""A propagating step that reads as if it does not is disclosed, never labelled.

Feature: decision-quality-proof, task 3.1. Requirement **R4.12**.

Subject: ``scripts/audit/workflow_shape_truth``'s R4.12 disclosure -
:func:`~scripts.audit.workflow_shape_truth.masked_nonterminal_constructs` and the
``ShapeReport.notes`` it feeds. The reading correction itself (only the final list
element decides a step's exit status) is covered by
``tests/verify/test_workflow_shape_rule_disjunction_property.py`` and is not repeated
here. What these cases pin is the *disposition*: R4.12 asks for such a step to be
reported as a shape defect to be made readable **rather than one to be labelled**, so
the note must exist, must not be a finding, and must not move the verdict.

Why both halves matter. The correction is silent by construction: once ``cd-gcp.yml``
``deploy-to-vm``::"Pull + restart stack" reads as propagating, a gate that only removes
the finding says nothing at all about a step whose exit status can be worked out only by
joining seven physical lines. And the opposite failure is worse: promoting the note to a
finding would re-create the false positive the correction removed, one rule to the left,
and the only way to clear it would be an ``ADVISORY`` marker on a step that does
propagate - a false label (I-7).

The narrowness is deliberate and is asserted, not assumed. Only a logical line a
*continuation* built is noted. ``frontend.yml`` ``e2e-visual``::"Generate + commit Linux
baselines if none are committed yet" is the case that must stay silent: its ``|| true``
sits on its own visible line inside an ``if`` block and the script's last effective line
is ``fi``. Widening the class to every incidental ``|| true`` would turn a disclosure
into noise.

These are example-based unit tests on purpose - no ``@given``, no new property. Each
writes a small workflow tree into a ``tempfile.TemporaryDirectory`` and calls
``evaluate`` with every root pointed inside it, so the verdict is a statement about the
generated tree and nothing else. No workflow is executed, no subprocess is spawned and
no build runs: pure file reads, so this belongs in ``ci.yml::uplift-verify``'s fast step
and is deliberately not ``slow``-marked.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

from scripts.audit import workflow_shape_truth as wst

#: One continuation-joined remote command whose four housekeeping steps are best-effort
#: and whose FINAL command decides the step's status. This is the ``cd-gcp.yml`` shape,
#: reduced to what the reading depends on.
_CONTINUATION_JOINED: Final[str] = """\
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy-to-vm:
    runs-on: ubuntu-latest
    steps:
      - name: Pull + restart stack
        run: |
          ssh host \\
            --command="set -e; cd app && \\
                       compose down --remove-orphans || true && \\
                       docker image prune -af || true && \\
                       compose pull && \\
                       compose up -d --force-recreate"
"""

#: The mirror case: a discard on its own physical line inside an ``if`` block, whose last
#: effective line is a block terminator. Readable as written, so never noted.
_OWN_LINE_DISCARD: Final[str] = """\
name: Visual
on:
  push:
    branches: [main]
jobs:
  e2e-visual:
    runs-on: ubuntu-latest
    steps:
      - name: Generate + commit Linux baselines if none are committed yet
        run: |
          if [ -d baselines ]; then
            pnpm test:visual:update || true
          fi
"""

#: A genuinely non-propagating, unlabelled step: a finding, and never a note.
_TERMINAL_DISCARD: Final[str] = """\
name: Quality
on:
  push:
    branches: [main]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - name: Size budget
        run: |
          node scripts/size-budget.mjs || true
"""


def _evaluate(workflow_yaml: str, *, job: str, declared_step: str) -> wst.ShapeReport:
    """Run the gate over one workflow in a throwaway tree.

    ``declared_step`` names the step the generated ``blocking-steps.yaml`` declares. The
    declaration must resolve to something: an empty ``steps:`` list makes the gate
    ``unavailable``, and a name the tree does not carry is a ``blocking-unresolved``
    finding - neither of which is what these cases are about.
    """
    with tempfile.TemporaryDirectory(prefix="shape-note-") as tmp:
        root = Path(tmp)
        directory = root / "workflows"
        directory.mkdir()
        workflow_path = directory / "generated.yml"
        workflow_path.write_text(workflow_yaml, encoding="utf-8")
        workflow_key = wst.workflow_relative_path(workflow_path)

        declaration_path = root / "blocking-steps.yaml"
        declaration_path.write_text(
            "steps:\n"
            f"  - workflow: {workflow_key}\n"
            f"    job: {job}\n"
            "    step_names:\n"
            f'      - "{declared_step}"\n'
            "    requirement: R1.8\n",
            encoding="utf-8",
        )

        return wst.evaluate(
            directory=directory,
            declaration_path=declaration_path,
            makefile=None,
            frontend_src=root / "frontend" / "src",
            frontend_dist=root / "frontend" / "dist",
        )


def test_a_masked_intermediate_discard_is_reported_as_a_note_and_not_as_a_finding() -> None:
    """R4.12 on the live instance's shape, end to end through ``evaluate``.

    The step is *declared blocking* here on purpose. It propagates, so it is not a
    ``blocking-discards`` finding; and it is still noted, which is the point - the
    disclosure is about how the step reads, not about what it is declared to be.
    """
    report = _evaluate(
        _CONTINUATION_JOINED,
        job="deploy-to-vm",
        declared_step="Pull + restart stack",
    )

    assert report.verdict == "pass", f"a propagating step is not a violation: {report.reason}"
    assert report.findings == (), "no rule may fire on a step whose final command decides it"

    assert len(report.notes) == 1, f"expected one R4.12 note, got {report.notes}"
    note = report.notes[0]
    assert note.note == wst.READABILITY_NOTE
    assert note.requirement == "R4.12"
    assert note.job == "deploy-to-vm"
    assert note.step_name == "Pull + restart stack"
    # The remedy the note states must be the readable one, never the label.
    assert "|| true" in note.detail
    assert "readable" in note.detail
    assert "do NOT label it advisory" in note.detail
    # And the note is disclosed in the reason C64 reports, so a green row still says it.
    assert "readability (R4.12)" in report.reason


def test_a_discard_on_its_own_line_inside_a_block_is_neither_a_finding_nor_a_note() -> None:
    """The mirror error, and the bound on the disclosure's scope.

    This is the ``frontend.yml::e2e-visual`` shape that the recorded debt list
    over-stated. It propagates (its last effective line is ``fi``) and it is readable as
    written, so widening the note to cover it would trade a false finding for a false
    disclosure.
    """
    report = _evaluate(
        _OWN_LINE_DISCARD,
        job="e2e-visual",
        declared_step="Generate + commit Linux baselines if none are committed yet",
    )

    assert report.verdict == "pass"
    assert report.findings == ()
    assert report.notes == ()


def test_a_terminal_discard_stays_a_finding_and_is_never_softened_into_a_note() -> None:
    """The direction that keeps the gate a gate.

    A step whose final command is ``|| true`` does not propagate. It owes a declaration
    or an honest label, and R4.12 must not offer it a third, quieter option.
    """
    report = _evaluate(_TERMINAL_DISCARD, job="quality", declared_step="Size budget")

    assert report.verdict == "fail"
    assert [finding.rule for finding in report.findings] == ["blocking-discards"]
    assert report.notes == (), "a non-propagating step is a finding, not a disclosure"


def test_only_a_continuation_built_line_is_read_for_masked_discards() -> None:
    """The unit-level statement of the same bound, on the reading itself.

    ``a || true && b`` written on one physical line is a list a reader can see whole, so
    there is nothing to make readable. The identical text spread across a continuation is
    what R4.12 names.
    """
    one_line = 'ssh host --command="a || true && b"'
    continued = 'ssh host \\\n  --command="a || true && \\\n             b"'

    assert wst.masked_nonterminal_constructs(one_line) == ()
    assert wst.masked_nonterminal_constructs(continued) == ("|| true",)
    # Neither reading changes what decides the step's exit status.
    assert wst.terminal_discarding_construct(one_line) is None
    assert wst.terminal_discarding_construct(continued) is None
