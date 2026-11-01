# Feature: decision-quality-proof, Property 98: Every way the proof run can fail is named, and
# only a produced artifact is a completed run
"""Every way the E5 proof run can fail is named, and only a produced artifact completes it.

Subject: ``uplift/proof_supervisor.py`` (decision-quality-proof task 22.1; R7.2). When the
harness fails to start, exits non-zero, exceeds its wall-clock bound or produces no artifact,
the generating job must record a non-passing result "naming which of those four states
occurred". This file holds the supervisor to that, and to the converse the property's title
states: an exit status of 0 is not a completed run unless the artifact was produced.

**Fast and pure.** :func:`classify_run`, the state vocabulary, the exit codes, the status record
and the command line's refusals run in-process and spawn nothing. Each precedence clause gets
its own generated precondition, so no assertion sits behind an ``if`` the strategy might never
satisfy, and the one ``completed`` point is pinned by a direct example so the iff cannot hold
vacuously. The pre-existing-artifact refusal is fast too: it is refused before anything spawns,
and the child it would have run leaves a marker if it ever ran.

**Slow, one real child per state.** Each ``@pytest.mark.slow`` clause runs the real CLI over a
``sys.executable -c`` child -- or, for ``failed_to_start``, a program that does not exist -- and
reads the canonical status record back. They spawn processes, so they are selected by
``ci.yml::uplift-verify``'s slow step, whose path list includes ``tests/uplift``; the longest
waits five seconds for a bound to expire.

Budget inherited from the root ``conftest.py`` profile: no example count is set or asserted.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import structlog
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from uplift.proof_supervisor import (
    EXIT_CODES,
    RUN_STATES,
    STATE_MESSAGES,
    SupervisorStatus,
    classify_run,
    main,
    supervise,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from uplift.proof_supervisor import RunState


@pytest.fixture(autouse=True)
def _restore_structlog_configuration() -> Iterator[None]:
    """Undo ``main``'s process-global ``structlog.configure`` after every test.

    Without this, a clause that exercises the CLI would reroute logging for every test that
    runs after it in the same session -- contamination that presents as an unrelated failure.
    """
    saved: dict[str, Any] = dict(structlog.get_config())
    try:
        yield
    finally:
        structlog.configure(**saved)


# ---------------------------------------------------------------------------
# Strategies over the four facts `classify_run` reads
# ---------------------------------------------------------------------------
#: Any text is a spawn error, the empty string included: only ``None`` means "it started".
_SPAWN_ERRORS = st.text(max_size=40)
_ANY_CODE = st.integers(min_value=-(2**31), max_value=2**31 - 1)
#: Exit statuses as the OS reports them (negative for a signal), ``None`` for one never reaped,
#: and a separately weighted 0 so the clean-exit cases are generated rather than hoped for.
_RETURN_CODES = st.one_of(st.just(0), st.none(), _ANY_CODE)
_NONZERO_OR_MISSING = st.one_of(st.none(), _ANY_CODE.filter(lambda code: code != 0))


def _record(
    *,
    spawn_error: str | None,
    returncode: int | None,
    timed_out: bool,
    artifact_present: bool,
) -> SupervisorStatus:
    """A status record over the given facts, with the kill the supervisor would have made."""
    return SupervisorStatus.from_facts(
        command=("python", "-m", "uplift.cli", "--full"),
        artifact_path="artifacts/uplift/result.json",
        wall_clock_seconds=13500.0,
        elapsed_seconds=1.5,
        spawn_error=spawn_error,
        returncode=returncode,
        timed_out=timed_out,
        artifact_present=artifact_present,
        kill_scope="process_group" if timed_out else "none",
    )


# ---------------------------------------------------------------------------
# Fast: the classification, one precedence clause per test
# ---------------------------------------------------------------------------
@given(
    spawn_error=_SPAWN_ERRORS,
    returncode=_RETURN_CODES,
    timed_out=st.booleans(),
    artifact_present=st.booleans(),
)
def test_a_command_that_never_started_is_failed_to_start_whatever_else_is_true(
    spawn_error: str, returncode: int | None, timed_out: bool, artifact_present: bool
) -> None:
    state = classify_run(
        spawn_error=spawn_error,
        returncode=returncode,
        timed_out=timed_out,
        artifact_present=artifact_present,
    )
    assert state == "failed_to_start"


@given(returncode=_RETURN_CODES, artifact_present=st.booleans())
def test_a_command_still_running_at_the_bound_is_exceeded_wall_clock_whatever_it_returned(
    returncode: int | None, artifact_present: bool
) -> None:
    state = classify_run(
        spawn_error=None,
        returncode=returncode,
        timed_out=True,
        artifact_present=artifact_present,
    )
    assert state == "exceeded_wall_clock"


@given(returncode=_NONZERO_OR_MISSING, artifact_present=st.booleans())
def test_a_nonzero_or_missing_exit_status_is_exited_nonzero_even_beside_an_artifact(
    returncode: int | None, artifact_present: bool
) -> None:
    state = classify_run(
        spawn_error=None,
        returncode=returncode,
        timed_out=False,
        artifact_present=artifact_present,
    )
    assert state == "exited_nonzero"


def test_a_clean_exit_that_wrote_nothing_is_no_artifact() -> None:
    state = classify_run(spawn_error=None, returncode=0, timed_out=False, artifact_present=False)
    assert state == "no_artifact"


def test_a_clean_exit_that_produced_the_artifact_is_completed() -> None:
    state = classify_run(spawn_error=None, returncode=0, timed_out=False, artifact_present=True)
    assert state == "completed"


@given(
    spawn_error=st.one_of(st.none(), _SPAWN_ERRORS),
    returncode=_RETURN_CODES,
    timed_out=st.booleans(),
    artifact_present=st.booleans(),
)
def test_exactly_one_state_is_named_and_it_is_completed_only_for_a_produced_artifact(
    spawn_error: str | None, returncode: int | None, timed_out: bool, artifact_present: bool
) -> None:
    state = classify_run(
        spawn_error=spawn_error,
        returncode=returncode,
        timed_out=timed_out,
        artifact_present=artifact_present,
    )
    assert state in RUN_STATES
    produced = spawn_error is None and not timed_out and returncode == 0 and artifact_present
    assert (state == "completed") is produced


# ---------------------------------------------------------------------------
# Fast: the vocabulary, the messages and the exit codes
# ---------------------------------------------------------------------------
def test_the_four_failure_states_and_completed_each_carry_a_distinct_self_naming_message() -> None:
    assert set(RUN_STATES) == {
        "completed",
        "failed_to_start",
        "exited_nonzero",
        "exceeded_wall_clock",
        "no_artifact",
    }
    assert len(set(RUN_STATES)) == len(RUN_STATES)
    assert set(STATE_MESSAGES) == set(RUN_STATES)
    messages = [STATE_MESSAGES[state] for state in RUN_STATES]
    assert len(set(messages)) == len(messages)
    for state in RUN_STATES:
        message = STATE_MESSAGES[state]
        assert message.isascii()
        assert message.startswith(f"{state}: ")
        assert [named for named in RUN_STATES if named in message] == [state]


def test_only_a_completed_run_exits_zero_and_each_failure_state_has_its_own_code() -> None:
    assert set(EXIT_CODES) == set(RUN_STATES)
    assert EXIT_CODES["completed"] == 0
    failure_codes = [EXIT_CODES[state] for state in RUN_STATES if state != "completed"]
    assert failure_codes
    assert len(set(failure_codes)) == len(failure_codes)
    # 0 is success, 1 an uncaught crash, 2 argparse's usage error: a state may be none of them.
    assert not {0, 1, 2} & set(failure_codes)


# ---------------------------------------------------------------------------
# Fast: the status record states only what its own facts classify as
# ---------------------------------------------------------------------------
@given(
    facts=st.fixed_dictionaries(
        {
            "spawn_error": st.one_of(st.none(), _SPAWN_ERRORS),
            "returncode": _RETURN_CODES,
            "timed_out": st.booleans(),
            "artifact_present": st.booleans(),
        }
    )
)
def test_the_status_record_states_only_what_its_own_facts_classify_as(
    facts: dict[str, Any],
) -> None:
    record = _record(**facts)
    derived = classify_run(**facts)
    assert record.state == derived
    assert record.message == STATE_MESSAGES[derived]

    # The refusal path, by construction: every other state is refused for these facts.
    contradicting = [state for state in RUN_STATES if state != derived]
    assert contradicting
    for state in contradicting:
        with pytest.raises(ValidationError):
            SupervisorStatus(
                **{**record.model_dump(), "state": state, "message": STATE_MESSAGES[state]}
            )

    text = record.canonical_json()
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    assert SupervisorStatus.model_validate_json(text) == record


def test_the_record_refuses_a_foreign_message_and_a_kill_without_a_timeout() -> None:
    record = _record(spawn_error=None, returncode=0, timed_out=False, artifact_present=True)
    assert record.state == "completed"
    with pytest.raises(ValidationError):
        SupervisorStatus(**{**record.model_dump(), "message": STATE_MESSAGES["no_artifact"]})
    with pytest.raises(ValidationError):
        SupervisorStatus(**{**record.model_dump(), "kill_scope": "process_group"})


# ---------------------------------------------------------------------------
# Fast: what is refused before anything is started
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bound", ["0", "-5", "nan", "inf", "soon"])
def test_a_bound_that_is_not_a_finite_positive_number_of_seconds_is_a_usage_error(
    bound: str, tmp_path: Path
) -> None:
    status = tmp_path / "status.json"
    argv = [
        "--wall-clock-seconds",
        bound,
        "--expect-artifact",
        str(tmp_path / "result.json"),
        "--status-out",
        str(status),
        "--",
        sys.executable,
        "-c",
        "pass",
    ]
    with pytest.raises(SystemExit) as raised:
        main(argv)
    assert raised.value.code == 2
    assert not status.exists()


@pytest.mark.parametrize("separator", [(), ("--",)], ids=["no-separator", "nothing-after-it"])
def test_a_command_line_without_a_separated_command_is_a_usage_error(
    separator: tuple[str, ...], tmp_path: Path
) -> None:
    status = tmp_path / "status.json"
    argv = [
        "--wall-clock-seconds",
        "5",
        "--expect-artifact",
        str(tmp_path / "result.json"),
        "--status-out",
        str(status),
        *separator,
    ]
    with pytest.raises(SystemExit) as raised:
        main(argv)
    assert raised.value.code == 2
    assert not status.exists()


def test_a_run_that_has_no_command_or_cannot_be_bounded_is_refused_before_it_starts(
    tmp_path: Path,
) -> None:
    status = tmp_path / "status.json"
    with pytest.raises(ValueError, match="no command"):
        supervise(
            [], wall_clock_seconds=5.0, expect_artifact=tmp_path / "r.json", status_out=status
        )
    for bound in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="wall-clock bound"):
            supervise(
                [sys.executable, "-c", "pass"],
                wall_clock_seconds=bound,
                expect_artifact=tmp_path / "r.json",
                status_out=status,
            )
    assert not status.exists()


def test_an_artifact_present_before_the_run_is_refused_and_the_child_never_runs(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "evidence" / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")
    marker = tmp_path / "the-child-ran"
    script = "import pathlib, sys; pathlib.Path(sys.argv[2]).write_text('ran', encoding='utf-8')"

    code, record = _supervise(tmp_path, [sys.executable, "-c", script, str(artifact), str(marker)])

    _assert_named(code, record, "failed_to_start")
    assert not marker.exists(), "the refused child ran anyway"
    assert record["artifact_present"] is False
    assert "already exists" in record["spawn_error"]


# ---------------------------------------------------------------------------
# Slow: one real child per state, through the real CLI
# ---------------------------------------------------------------------------
_WRITE_ARTIFACT = (
    "import pathlib, sys; target = pathlib.Path(sys.argv[1]); "
    "target.parent.mkdir(parents=True, exist_ok=True); target.write_text('{}', encoding='utf-8')"
)

#: The child starts a grandchild, records its pid, and outlives the bound with it.
_SPAWN_GRANDCHILD = (
    "import pathlib, subprocess, sys, time\n"
    "grandchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "pathlib.Path(sys.argv[2]).write_text(str(grandchild.pid), encoding='utf-8')\n"
    "time.sleep(120)\n"
)


def _supervise(
    tmp_path: Path, command: list[str], *, bound: float = 60.0
) -> tuple[int, dict[str, Any]]:
    """Run the real CLI over ``command``; return its exit code and its status record."""
    status = tmp_path / "evidence" / "supervisor-status.json"
    code = main(
        [
            "--wall-clock-seconds",
            str(bound),
            "--expect-artifact",
            str(tmp_path / "evidence" / "result.json"),
            "--status-out",
            str(status),
            "--",
            *command,
        ]
    )
    return code, _read_canonical(status)


def _child(tmp_path: Path, script: str, *extra: str) -> list[str]:
    """A ``sys.executable -c`` child whose first argument is the declared artifact path."""
    return [sys.executable, "-c", script, str(tmp_path / "evidence" / "result.json"), *extra]


def _read_canonical(status: Path) -> dict[str, Any]:
    """The status record, asserted to be one canonical JSON document and a valid record."""
    text = status.read_text(encoding="utf-8")
    assert text.endswith("\n")
    body = text[:-1]
    payload: dict[str, Any] = json.loads(body)
    assert body == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    SupervisorStatus.model_validate(payload)
    return payload


def _assert_named(code: int, record: dict[str, Any], state: RunState) -> None:
    assert record["state"] == state
    assert record["message"] == STATE_MESSAGES[state]
    assert code == EXIT_CODES[state]


def _no_longer_running(pid: int) -> bool:
    """Whether ``pid`` is gone, or a zombie awaiting its reaper (which runs nothing)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return True  # the pid now belongs to another user's process: ours is gone
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return False
    fields = stat.rsplit(")", 1)[-1].split()
    return bool(fields) and fields[0] in {"Z", "X"}


@pytest.mark.slow
def test_a_child_that_exits_zero_and_writes_the_artifact_is_a_completed_run(
    tmp_path: Path,
) -> None:
    code, record = _supervise(tmp_path, _child(tmp_path, _WRITE_ARTIFACT))
    _assert_named(code, record, "completed")
    assert (tmp_path / "evidence" / "result.json").is_file()
    assert record["artifact_present"] is True
    assert record["returncode"] == 0


@pytest.mark.slow
def test_a_child_that_exits_zero_without_the_artifact_is_named_no_artifact(
    tmp_path: Path,
) -> None:
    code, record = _supervise(tmp_path, _child(tmp_path, "pass"))
    _assert_named(code, record, "no_artifact")
    assert not (tmp_path / "evidence" / "result.json").exists()
    assert record["returncode"] == 0


@pytest.mark.slow
def test_a_child_that_writes_the_artifact_and_exits_nonzero_is_named_exited_nonzero(
    tmp_path: Path,
) -> None:
    code, record = _supervise(tmp_path, _child(tmp_path, f"{_WRITE_ARTIFACT}; raise SystemExit(3)"))
    _assert_named(code, record, "exited_nonzero")
    # The file is there and still does not complete the run.
    assert (tmp_path / "evidence" / "result.json").is_file()
    assert record["artifact_present"] is True
    assert record["returncode"] == 3


@pytest.mark.slow
def test_a_child_still_running_at_the_bound_is_killed_and_named_exceeded_wall_clock(
    tmp_path: Path,
) -> None:
    started = time.monotonic()
    code, record = _supervise(tmp_path, _child(tmp_path, "import time; time.sleep(120)"), bound=1.0)
    waited = time.monotonic() - started

    _assert_named(code, record, "exceeded_wall_clock")
    assert record["timed_out"] is True
    expected_scope = "process_only" if sys.platform == "win32" else "process_group"
    assert record["kill_scope"] == expected_scope
    # Killed, not waited out: the child would have slept for 120 seconds.
    assert waited < 60.0
    assert record["elapsed_seconds"] < 60.0


@pytest.mark.slow
def test_a_program_that_cannot_be_executed_is_named_failed_to_start(tmp_path: Path) -> None:
    code, record = _supervise(tmp_path, [str(tmp_path / "no-such-program")])
    _assert_named(code, record, "failed_to_start")
    assert record["spawn_error"]
    assert record["returncode"] is None
    assert record["artifact_present"] is False


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX; see kill_scope")
def test_the_bound_kills_the_childs_whole_process_group(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    code, record = _supervise(
        tmp_path, _child(tmp_path, _SPAWN_GRANDCHILD, str(pid_file)), bound=5.0
    )
    _assert_named(code, record, "exceeded_wall_clock")
    assert record["kill_scope"] == "process_group"
    assert pid_file.is_file(), "the child never started its grandchild inside the bound"

    pid = int(pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 10.0
    while not _no_longer_running(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    survived = not _no_longer_running(pid)
    if sys.platform != "win32" and survived:
        # Never leak a process (I-0's sweep), even from a failing clause.
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)
    assert not survived, f"grandchild {pid} outlived the bound: only the direct child was killed"
