"""The ledger census classifies every record, or reports that it could not.

Feature: decision-quality-proof, session-protocol revision.

Locus: ``ci.yml::uplift-verify`` fast step, which runs
``pytest tests/uplift tests/verify -m "not slow"``. These tests are pure string and
``Path`` work, so they are deliberately **not** slow-marked: a slow marker here would move
them to the slow step and buy nothing.

The three cases that matter are the three the predecessor one-liner got wrong: a leaf
nested deeper than two spaces, a childless checkpoint parent, and a CI-gated task that
must not be offered as authorable work.
"""

from __future__ import annotations

from pathlib import Path

from scripts.audit.spec_ledger_census import (
    DEFAULT_BATCH,
    CensusOutcome,
    LedgerRecord,
    census,
    evaluate,
    extract_paths,
    format_report,
    parse_records,
)

# --- fixtures ---------------------------------------------------------------

_LEDGER = """# Plan

- [x] 1. Parent whose children are all done
  - [x] 1.1 First child
    - _Requirements: 1.1_
  - [x] 1.2 Second child
    - _Requirements: 1.2_

- [ ] 2. Checkpoint with no children at all
  - Ensure all tests pass.
  - discharge: uplift.yml::twin-regret

- [ ] 3. Parent with mixed children
  - [~] 3.1 Authored, discharge owed
    - File: `uplift/regret.py`
    - discharge: ci.yml::uplift-verify slow step
  - [ ] 3.2 Open and authorable
    - Files: `digital_twin/simulation/engine.py`
  - [ ] 3.3 Open but CI-gated
    - **discharge:** `uplift.yml::uplift-proof`

- [ ] 4. Deeply nested leaf
    - [ ] 4.1 Indented four spaces, not two
      - _Requirements: 4.1_
"""


def _records() -> tuple[LedgerRecord, ...]:
    return parse_records(_LEDGER)


# --- leaf derivation -------------------------------------------------------


def test_leaf_status_comes_from_the_id_tree_not_indentation() -> None:
    """Task 2 is a leaf because nothing is named ``2.<n>``; task 1 is not."""
    by_id = {record.task_id: record for record in _records()}
    assert by_id["2"].is_leaf is True
    assert by_id["1"].is_leaf is False
    assert by_id["3"].is_leaf is False


def test_a_leaf_indented_four_spaces_is_still_counted() -> None:
    """The predecessor one-liner required exactly two spaces and silently dropped this."""
    by_id = {record.task_id: record for record in _records()}
    assert "4.1" in by_id
    assert by_id["4.1"].is_leaf is True

    report = census(_records(), spec="fixture", source="fixture")
    assert "4.1" in report.authorable


def test_counts_partition_the_leaves() -> None:
    """done + pending + open equals the leaf total, with no record double-counted."""
    report = census(_records(), spec="fixture", source="fixture")
    assert report.leaves == 7  # 1.1 1.2 2 3.1 3.2 3.3 4.1
    assert report.parents == 3  # 1 3 4
    assert report.done == 2
    assert report.pending == 1
    assert report.open_count == 4
    assert report.done + report.pending + report.open_count == report.leaves


# --- the three marks -------------------------------------------------------


def test_pending_is_not_counted_as_done() -> None:
    """``[~]`` is authored-and-owed. Reporting it as a pass is the I-7 violation."""
    report = census(_records(), spec="fixture", source="fixture")
    assert report.pending == 1
    assert "3.1 -> ci.yml::uplift-verify slow step" in report.pending_discharges
    assert "3.1" not in report.authorable


def test_an_undefined_mark_is_unavailable_not_a_guess() -> None:
    """A mark outside the vocabulary makes the census non-passing, never approximate."""
    report = census(parse_records("- [?] 9. Mystery mark\n"), spec="fixture", source="fixture")
    assert report.outcome is CensusOutcome.UNAVAILABLE
    assert report.exit_code == 2
    assert [finding.rule for finding in report.findings] == ["unknown-mark"]


def test_a_duplicated_task_id_is_unavailable() -> None:
    """Two records under one id mean a count over ids is not a count over records."""
    text = "- [ ] 5. First\n- [ ] 5. Second\n"
    report = census(parse_records(text), spec="fixture", source="fixture")
    assert report.outcome is CensusOutcome.UNAVAILABLE
    assert [finding.rule for finding in report.findings] == ["duplicate-id"]


# --- gating is derived, not declared ---------------------------------------


def test_a_gated_open_leaf_is_never_offered_as_authorable() -> None:
    """This replaces the hardcoded GATED set that disagreed with the prose beside it."""
    report = census(_records(), spec="fixture", source="fixture")
    assert "2" not in report.authorable
    assert "3.3" not in report.authorable
    assert report.gated == ("2 -> uplift.yml::twin-regret", "3.3 -> uplift.yml::uplift-proof")


def test_discharge_survives_markdown_emphasis() -> None:
    """``- **discharge:** `job``` is the same declaration as ``- discharge: job``."""
    by_id = {record.task_id: record for record in _records()}
    assert by_id["3.3"].discharge == "uplift.yml::uplift-proof"
    assert by_id["2"].discharge == "uplift.yml::twin-regret"
    assert by_id["3.2"].discharge is None


def test_authorable_preserves_ledger_order() -> None:
    """A batch is the next N in the order the plan states, not sorted lexically."""
    report = census(_records(), spec="fixture", source="fixture")
    assert report.authorable == ("3.2", "4.1")
    assert report.next_batch(1) == ("3.2",)


# --- barriers: what a batch steps OVER -------------------------------------


def test_a_batch_reports_the_gated_leaf_it_steps_over() -> None:
    """A checkpoint that can cancel the work behind it must not be crossed silently.

    ``next_batch`` filters gated leaves out, so before this existed a batch large enough
    to span one reported nothing about it. At the old batch of 10 that was satisfied by
    accident; at 30 the offered batch reaches past checkpoint B, whose own task says
    "the consensus experiment ... must NOT be run. Do not proceed to E3."
    """
    report = census(_records(), spec="fixture", source="fixture")
    # `3.2` sits after gated `2`, so even a one-task batch crosses one barrier.
    assert report.barriers_crossed(1) == ("2",)
    # Widening to `4.1` steps over gated `3.3` as well, and both are named in ledger order.
    assert report.barriers_crossed(2) == ("2", "3.3")


def test_an_empty_batch_crosses_nothing() -> None:
    """No offered work cannot step over anything -- absence is not a crossing."""
    report = census(_records(), spec="fixture", source="fixture")
    assert report.barriers_crossed(0) == ()


def test_a_barrier_is_advisory_and_still_leaves_the_batch_offered() -> None:
    """Ledger order is not execution order, so a crossing informs and never blocks.

    Session 2r's own batch (27.2-27.5) legitimately sat after checkpoint A's task 11 and
    did not depend on it. Truncating on ledger position alone would have refused correct
    work, so the derivation names the crossing and leaves the judgement to the reader.
    """
    report = census(_records(), spec="fixture", source="fixture")
    assert report.next_batch(2) == ("3.2", "4.1")
    assert report.barriers_crossed(2), "the batch does cross barriers"
    assert report.outcome is CensusOutcome.PASS
    assert report.exit_code == 0


def test_the_report_names_every_barrier_the_batch_crosses() -> None:
    """The human report must surface the crossing, not just the model."""
    report = census(_records(), spec="fixture", source="fixture")
    text = "\n".join(format_report(report, batch=2))
    assert "[!!] barrier" in text
    assert "uplift.yml::twin-regret" in text
    assert "Ledger order is not execution order" in text


def test_the_default_batch_is_thirty() -> None:
    """The cap lives in ONE place. Three documents used to transcribe it by hand."""
    assert DEFAULT_BATCH == 30


# --- path extraction -------------------------------------------------------


def test_extract_paths_reads_backticked_repository_paths() -> None:
    body = ("File: `uplift/regret.py`, `digital_twin/simulation/policy.yaml`",)
    assert extract_paths(body) == ("uplift/regret.py", "digital_twin/simulation/policy.yaml")


def test_extract_paths_strips_line_and_job_suffixes() -> None:
    """``frontend/vitest.config.ts:26`` and ``a/b.yml::job`` name files, not locations."""
    body = ("wired at `frontend/vitest.config.ts:26` and `.github/workflows/ci.yml::quality`",)
    assert extract_paths(body) == ("frontend/vitest.config.ts", ".github/workflows/ci.yml")


def test_extract_paths_ignores_prose_and_bare_module_names() -> None:
    """A backticked identifier is not a path; requiring ``/`` and a suffix is the rule."""
    body = ("`fill_rate` fell, `MIN_SCENARIOS` held, `uplift.yml` is a workflow name",)
    assert extract_paths(body) == ()


# --- the real ledger -------------------------------------------------------


def test_the_committed_ledger_classifies_cleanly() -> None:
    """The spec this census was written for must itself be classifiable.

    Anti-vacuity, in the shape ``task_claim_truth`` uses: a census that cannot read the
    ledger it was written against is not a passing census. This asserts no total, because
    the total is the thing that moves every session (CF-13's discipline).
    """
    report = evaluate(spec="decision-quality-proof")
    assert report.outcome is CensusOutcome.PASS, report.detail
    assert report.leaves > 0
    assert report.done + report.pending + report.open_count == report.leaves


def test_disk_observations_are_informational_only() -> None:
    """``--files`` never changes the verdict: some named paths exist to be rejected."""
    root = Path(__file__).resolve().parents[2]
    plain = evaluate(spec="decision-quality-proof", root=root, check_files=False)
    with_files = evaluate(spec="decision-quality-proof", root=root, check_files=True)
    assert plain.outcome is with_files.outcome
    assert plain.observations == ()



def test_human_report_is_ascii_only_even_when_the_ledger_is_not() -> None:
    """The ledger uses em dashes; Windows consoles do not. The record keeps the truth."""
    text = "- [ ] 8. Checkpoint \u2014 read the survivor list\n"
    parsed = parse_records(text)
    assert "\u2014" in parsed[0].title, "the parsed record must preserve the source text"

    rendered = "\n".join(format_report(census(parsed, spec="fixture", source="fixture")))
    assert rendered.isascii()
    assert "\u2014" not in rendered


def test_a_path_declared_new_is_reported_before_a_modify_in_place_path(tmp_path: Path) -> None:
    """Signal, not volume: an open task's ``(new)`` file existing is the real finding."""
    spec_dir = tmp_path / ".kiro" / "specs" / "s"
    spec_dir.mkdir(parents=True)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "already.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "engine.py").write_text("", encoding="utf-8")
    (spec_dir / "tasks.md").write_text(
        "- [ ] 1. Modify something\n"
        "  - File: `pkg/engine.py`\n"
        "- [ ] 2. Create something\n"
        "  - File: `pkg/already.py` (new)\n",
        encoding="utf-8",
    )
    report = evaluate(spec="s", root=tmp_path, check_files=True)
    seen = [(item.task_id, item.path) for item in report.observations]
    assert seen[0] == ("2", "pkg/already.py"), seen
    assert ("1", "pkg/engine.py") in seen
