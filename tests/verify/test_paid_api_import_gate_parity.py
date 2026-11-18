"""The two I-1 paid-API import greps forbid the same imports over the same trees (finding 53).

Feature: decision-quality-proof, finding 53 (recorded in session 7, repaired in session 13).

I-1 has two CI carriers. ``ci.yml::quality-gates`` runs "No paid API imports (I-1 - BLOCKING)"
on every pull request to ``main``. ``security.yml::security`` runs "No paid API imports (I-1)"
weekly, on manual dispatch, and on pull requests that touch a ``requirements.txt``, a
``package.json`` or a ``Dockerfile``. Finding 53 read the two disagreeing on both axes: the
security copy named three clients where ci.yml names four, and it read three trees, Python
files only, where ci.yml reads eight trees, every file. Two carriers of one rule that forbid
different things tell whoever reads the narrower one that the rule is covered where it is not.

What is asserted, about the committed workflows:

1. Each step resolves exactly once, by its ASCII-folded name, in the job named for it.
2. Each ``run:`` body holds exactly one ``if grep ...; then`` command. It is read with the
   gate's own logical-line reader, ``workflow_shape_truth.effective_command_lines``, so a
   continuation-joined command reads here as it reads in the gate.
3. The two greps are the same words, as the shell splits them, run from the same directory.
   A failure names both steps and every axis that differs: the pattern's alternatives, the
   options and the paths.
4. Neither grep is vacuous. Each recurses; every alternative is ``import <client>\\>`` or
   ``from <client>\\>``, with both forms present for each client; and every path is a
   directory of this tree. A missing directory makes grep exit 2, which ``if`` reads as "no
   match", so the step would pass whatever the other trees hold. The word-end anchor ``\\>``
   is required: without it ``import replicate`` also matched ``import replicate_seed``, a harness
   function, which turned the gate red on ``main`` once #87 and #90 met (truth session 3).

What would make this file wrong. Equal words are stricter than equal behaviour: reordering two
directories in one copy fails here although it forbids nothing new. The repair is to copy the
reference verbatim, which is cheaper than a reader that models grep. The file reads neither a
step's ``if:`` nor its ``continue-on-error``; whether each step runs and propagates is what
``gate_surface`` and ``workflow_shape_truth`` answer. It does not judge WHICH clients I-1
names. That list is CLAUDE.md's, so two greps narrowed alike to one import-shaped client would
pass here, and ``pinecone`` stays off the list by ADR-018 (finding 55). The pre-commit hook
``no-paid-apis`` is a third carrier with a different scope by design, the staged ``.py``
files, and is not read here.

No client's import statement is written out in this file. The ``no-paid-apis`` hook scans
every staged ``.py`` file for exactly those strings, so the rebuilt pre-repair grep below
assembles them from parts.

No ``max_examples`` is set: these are facts about two committed files, not a property over
generated inputs. Not ``slow``-marked: the file reads two YAML files and spawns nothing, so it
runs in ``ci.yml::uplift-verify``'s fast shards, which select ``tests/verify`` by file name.
Every read is ``encoding='utf-8'`` (E-S13-07), through ``load_workflow``, and every assertion
message is ASCII.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from scripts.audit.workflow_shape_truth import (
    effective_command_lines,
    iter_job_steps,
    iter_jobs,
    load_workflow,
    normalize_step_name,
    step_display_name,
    step_run_script,
)

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: One top-level ``if grep ...; then`` command, as ``effective_command_lines`` joins it.
_IF_GREP: Final = re.compile(r"^if\s+(?P<command>grep\s.*?)\s*;\s*then$")
#: grep's basic-regex alternation, which both workflows write inside double quotes.
_ALTERNATION: Final = "\\|"
_IMPORT_FORM: Final = re.compile(
    r"^(?P<form>import|from) (?P<client>[A-Za-z_][A-Za-z0-9_.]*)(?P<anchor>\\>)?$"
)
_BOTH_FORMS: Final = frozenset({"import", "from"})
_RECURSIVE_SHORT: Final = frozenset({"r", "R"})
_RECURSIVE_LONG: Final = frozenset({"--recursive", "--dereference-recursive"})


@dataclass(frozen=True)
class StepRef:
    """Where one carrier of I-1 lives: a workflow file, a job id and a step name."""

    workflow: str
    job: str
    step: str

    @property
    def label(self) -> str:
        """``workflow::job::step``, which a reader can search the tree for."""
        return f"{self.workflow}::{self.job}::{self.step}"


#: The reference: the blocking carrier, which runs on every pull request to ``main``.
CI_STEP: Final = StepRef(
    ".github/workflows/ci.yml", "quality-gates", "No paid API imports (I-1 - BLOCKING)"
)
#: The mirror. Its pull-request trigger is path-filtered, so it mostly does not run.
SECURITY_STEP: Final = StepRef(
    ".github/workflows/security.yml", "security", "No paid API imports (I-1)"
)


def _is_option(word: str) -> bool:
    """A grep option as written; a lone ``-`` is an operand (standard input)."""
    return word.startswith("-") and word != "-"


@dataclass(frozen=True)
class GrepReading:
    """One carrier's grep: its words as the shell passes them, and where it runs."""

    label: str
    words: tuple[str, ...]
    working_directory: str

    @property
    def options(self) -> frozenset[str]:
        """Every word after ``grep`` that is an option, as written."""
        return frozenset(word for word in self.words[1:] if _is_option(word))

    @property
    def operands(self) -> tuple[str, ...]:
        """The pattern, then the paths, in the order the command names them."""
        return tuple(word for word in self.words[1:] if not _is_option(word))

    @property
    def alternatives(self) -> frozenset[str]:
        """The pattern's alternatives. Their order changes nothing grep matches."""
        if not self.operands:
            return frozenset()
        return frozenset(self.operands[0].split(_ALTERNATION))

    @property
    def paths(self) -> frozenset[str]:
        """The trees grep reads, without trailing slashes."""
        return frozenset(path.rstrip("/") for path in self.operands[1:])

    @property
    def recurses(self) -> bool:
        """Whether grep descends into the paths rather than reading them as files."""
        short = {
            letter
            for option in self.options
            if not option.startswith("--")
            for letter in option[1:]
        }
        return bool(short & _RECURSIVE_SHORT or self.options & _RECURSIVE_LONG)


def grep_words(script: str, *, label: str) -> tuple[str, ...]:
    """The words of the one ``if grep ...; then`` command in ``script``, split as the shell does.

    Refuses, naming ``label``, a script with no such command, with more than one, or with
    quoting that does not close. A refusal raises. It never returns an empty reading, which
    would compare equal to another empty reading and report a parity nothing had checked.
    """
    lines = effective_command_lines(script)
    commands = [match for line in lines if (match := _IF_GREP.match(line)) is not None]
    assert len(commands) == 1, (
        f"{label}: expected exactly one `if grep ...; then` command, found {len(commands)} "
        f"among {lines!a}"
    )
    try:
        return tuple(shlex.split(commands[0].group("command")))
    except ValueError as error:
        raise AssertionError(f"{label}: the grep command does not tokenise: {error}") from error


def _defaults_working_directory(container: dict[str, object]) -> str | None:
    """``defaults.run.working-directory`` of a workflow or a job, when it declares one."""
    defaults = container.get("defaults")
    run = defaults.get("run") if isinstance(defaults, dict) else None
    directory = run.get("working-directory") if isinstance(run, dict) else None
    return directory if isinstance(directory, str) else None


def working_directory(
    document: dict[str, object], job: dict[str, object], step: dict[str, object]
) -> str:
    """The directory a step's shell starts in, relative to the checkout.

    GitHub's precedence: the step's own ``working-directory``, then the job's
    ``defaults.run``, then the workflow's, then the checkout root.
    """
    own = step.get("working-directory")
    for candidate in (
        own if isinstance(own, str) else None,
        _defaults_working_directory(job),
        _defaults_working_directory(document),
    ):
        if candidate is not None and candidate.strip():
            return candidate.strip()
    return "."


def resolve(ref: StepRef) -> GrepReading:
    """Read ``ref``'s grep from the committed workflow, or fail naming what is missing."""
    path = REPO_ROOT / ref.workflow
    assert path.is_file(), f"{ref.workflow} does not exist"
    document = load_workflow(path)
    jobs = dict(iter_jobs(document))
    assert ref.job in jobs, f"{ref.workflow} declares no job {ref.job!r}"
    job = jobs[ref.job]
    wanted = normalize_step_name(ref.step)
    steps = [
        step
        for index, step in enumerate(iter_job_steps(job))
        if normalize_step_name(step_display_name(step, index)) == wanted
    ]
    assert len(steps) == 1, (
        f"{ref.label}: {len(steps)} steps carry this name; the pin resolves exactly one on "
        "each side, so a rename fails here rather than comparing nothing"
    )
    return GrepReading(
        label=ref.label,
        words=grep_words(step_run_script(steps[0]), label=ref.label),
        working_directory=working_directory(document, job, steps[0]),
    )


def drift_report(reference: GrepReading, mirror: GrepReading) -> str:
    """Both carriers, and every axis on which the mirror's grep differs from the reference."""
    lines = [f"{mirror.label} does not run the grep {reference.label} runs (finding 53)."]
    axes = (
        ("alternatives", reference.alternatives, mirror.alternatives),
        ("options", reference.options, mirror.options),
        ("paths", reference.paths, mirror.paths),
    )
    for axis, ours, theirs in axes:
        if ours - theirs:
            lines.append(f"  {axis} only in the reference: {sorted(ours - theirs)!a}")
        if theirs - ours:
            lines.append(f"  {axis} only in the mirror: {sorted(theirs - ours)!a}")
    if reference.working_directory != mirror.working_directory:
        lines.append(
            f"  working directory: reference {reference.working_directory!a}, "
            f"mirror {mirror.working_directory!a}"
        )
    if len(lines) == 1:
        lines.append("  no set differs, so the words differ in order or repetition")
    lines.append(f"  reference words: {reference.words!a}")
    lines.append(f"  mirror words:    {mirror.words!a}")
    lines.append("Change the two steps together; do not adjust this test.")
    return "\n".join(lines)


def test_the_two_paid_api_import_greps_forbid_the_same_imports_over_the_same_trees() -> None:
    """The load-bearing parity: the same grep words, run from the same directory.

    Finding 53 is this assertion read false. What would make it wrong is a difference outside
    the grep command, such as a step-level ``if:`` that never runs one copy; this test does not
    read those, and the module docstring names who does.
    """
    reference = resolve(CI_STEP)
    mirror = resolve(SECURITY_STEP)
    assert mirror.words == reference.words, drift_report(reference, mirror)
    assert mirror.working_directory == reference.working_directory, drift_report(reference, mirror)


def test_each_grep_recurses_into_real_trees_and_names_each_client_in_both_forms() -> None:
    """Parity between two vacuous greps would compare two gates that forbid nothing.

    Checked on both carriers, so this test does not lean on the parity test passing. Checked as
    a shape, never as a list: naming the clients stays CLAUDE.md's job. What would make it
    wrong is a grep narrowed to an import-shaped client that is not paid, which no shape check
    can tell from a real one.
    """
    for reading in (resolve(CI_STEP), resolve(SECURITY_STEP)):
        assert reading.recurses, (
            f"{reading.label}: grep does not recurse, so it reads each named tree as one file"
        )
        forms_by_client: dict[str, set[str]] = {}
        for alternative in sorted(reading.alternatives):
            match = _IMPORT_FORM.match(alternative)
            assert match is not None, (
                f"{reading.label}: alternative {alternative!a} is not `import <client>` or "
                "`from <client>`"
            )
            assert match.group("anchor") is not None, (
                f"{reading.label}: alternative {alternative!a} has no word-end anchor, so it also "
                "matches names that only begin with the client's, such as a `replicate_seed` import"
            )
            forms_by_client.setdefault(match.group("client"), set()).add(match.group("form"))
        assert forms_by_client, f"{reading.label}: the pattern names no client"
        half = sorted(client for client, forms in forms_by_client.items() if forms != _BOTH_FORMS)
        assert not half, f"{reading.label}: {half!a} are forbidden in one import form only"

        assert reading.paths, f"{reading.label}: grep names no path"
        base = REPO_ROOT / reading.working_directory
        missing = sorted(path for path in reading.paths if not (base / path).is_dir())
        assert not missing, (
            f"{reading.label}: {missing!a} are not directories of this tree; grep exits 2 on "
            "a missing path, and `if` reads that as no match"
        )


def test_the_pre_repair_security_grep_reads_as_narrower_on_every_axis_finding_53_named() -> None:
    """The comparison can fail, shown on the defect it exists to catch.

    The step security.yml carried at d4f985c is rebuilt from parts and read with the same
    reader. It must differ from the reference on each axis finding 53 named: clients the
    reference forbids and it did not, trees the reference reads and it did not, and an option
    that narrowed it to Python files. A comparison of nothing, or of one axis, would report
    fewer. What would make this wrong is the rebuilt text drifting from that commit's step,
    which ``git show d4f985c:.github/workflows/security.yml`` displays.
    """
    narrowed = ("openai", "anthropic", "cohere")
    pattern = _ALTERNATION.join(
        f"{form} {client}" for client in narrowed for form in ("import", "from")
    )
    script = (
        f'if grep -rn "{pattern}" agents/ orchestrator/ packages/ --include="*.py"; then\n'
        '  echo "FAIL: Paid API import detected"\n'
        "  exit 1\n"
        "fi\n"
        'echo "PASS: No paid API imports found"\n'
    )
    label = "security.yml at d4f985c, rebuilt"
    pre_repair = GrepReading(label, grep_words(script, label=label), ".")
    reference = resolve(CI_STEP)

    assert pre_repair.words != reference.words, "the pre-repair grep must not read as the same"
    assert _forms(reference) > _forms(pre_repair), (
        "the pre-repair pattern must forbid a strict subset of the reference's imports"
    )
    assert reference.paths > pre_repair.paths, (
        "the pre-repair trees must be a strict subset of the reference's"
    )
    assert pre_repair.options - reference.options == {"--include=*.py"}, (
        f"the pre-repair grep's narrowing option is not the one read: {pre_repair.options!a}"
    )
    report = drift_report(reference, pre_repair)
    for expected in (
        CI_STEP.label,
        label,
        "alternatives only in the reference",
        "paths only in the reference",
        "options only in the mirror",
    ):
        assert expected in report, f"the drift report omits {expected!a}:\n{report}"


def _forms(reading: GrepReading) -> frozenset[tuple[str, str]]:
    """The ``(form, client)`` pairs a reading forbids, whether or not each is anchored."""
    pairs = set()
    for alternative in reading.alternatives:
        match = _IMPORT_FORM.match(alternative)
        assert match is not None, f"{reading.label}: unreadable alternative {alternative!a}"
        pairs.add((match.group("form"), match.group("client")))
    return frozenset(pairs)


def _as_python(alternative: str) -> re.Pattern[str]:
    """One committed alternative as Python reads it: grep's ``\\>`` is "no word character next"."""
    match = _IMPORT_FORM.match(alternative)
    assert match is not None, f"unreadable alternative {alternative!a}"
    end = "(?![A-Za-z0-9_])" if match.group("anchor") else ""
    return re.compile(re.escape(f"{match.group('form')} {match.group('client')}") + end)


def test_the_committed_alternatives_flag_paid_imports_and_spare_lookalike_names() -> None:
    """The defect truth session 3 met, as behaviour: a harness function named like a client.

    Each line is assembled from parts so this file holds no client import statement (the
    ``no-paid-apis`` hook scans staged Python files). What would make this wrong is a grep that
    reads ``\\>`` differently from Python's lookahead here: GNU grep treats letters, digits and
    the underscore as word characters, as the lookahead does.
    """
    patterns = [_as_python(a) for a in resolve(CI_STEP).alternatives]
    paid = [
        " ".join(("import", "replicate")),
        " ".join(("from", "replicate", "import", "Client")),
        " ".join(("import", "replicate.client")),
        "    " + " ".join(("from", "anthropic.types", "import", "Message")),
        " ".join(("import", "openai")) + "  # trailing comment",
    ]
    lookalike = [
        " ".join(("from", "uplift.harness", "import", "replicate_seed,", "run_closed_loop")),
        " ".join(("import", "openai_compat")),
        " ".join(("from", "cohere2", "import", "x")),
    ]
    for line in paid:
        assert any(p.search(line) for p in patterns), f"a paid import passes the grep: {line!a}"
    for line in lookalike:
        hits = [p.pattern for p in patterns if p.search(line)]
        assert not hits, f"a lookalike name is flagged as a paid import: {line!a} by {hits!a}"


def test_an_unresolvable_step_or_grep_is_refused_rather_than_read_as_agreement() -> None:
    """Every absence raises, so two absences can never compare equal.

    The parity test cannot show this by passing. What would make it wrong is a reader that
    returned an empty reading for an absent workflow, job, step or command: both sides would
    then be empty and equal, and the parity would report agreement having compared nothing,
    the hole ``test_regeneration_closure_parity.py`` closes for install steps.
    """
    with pytest.raises(AssertionError, match="does not exist"):
        resolve(StepRef(".github/workflows/no-such-workflow.yml", "security", "x"))
    with pytest.raises(AssertionError, match="declares no job"):
        resolve(StepRef(CI_STEP.workflow, "no-such-job", CI_STEP.step))
    with pytest.raises(AssertionError, match="steps carry this name"):
        resolve(StepRef(SECURITY_STEP.workflow, SECURITY_STEP.job, "No such step"))
    with pytest.raises(AssertionError, match="exactly one"):
        grep_words('echo "nothing is searched"\n', label="synthetic")
    with pytest.raises(AssertionError, match="exactly one"):
        grep_words(
            'if grep -rn "a" x/; then\n  exit 1\nfi\nif grep -rn "b" y/; then\n  exit 1\nfi\n',
            label="synthetic",
        )
    with pytest.raises(AssertionError, match="does not tokenise"):
        grep_words('if grep -rn "unclosed x/; then\n  exit 1\nfi\n', label="synthetic")
