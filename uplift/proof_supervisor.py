"""Run the E5 proof command under a wall-clock bound, and NAME how it ended (R7.2).

Feature: decision-quality-proof, task 22.1. Requirement R7.2: when the harness "fails to start,
exits non-zero, exceeds that job's wall-clock bound, or produces no artifact at the declared
path", the generating job records a non-passing result "naming which of those four states
occurred". Four failure states, four distinct messages; "the run failed" is not one of them.

Run::

    python -m uplift.proof_supervisor --wall-clock-seconds 13500 \\
        --expect-artifact artifacts/uplift/result.json \\
        --status-out artifacts/uplift/supervisor-status.json \\
        -- python -m uplift.cli --full ...

**Five states, classified in a fixed precedence.** :func:`classify_run` is pure and returns
exactly one of ``failed_to_start`` > ``exceeded_wall_clock`` > ``exited_nonzero`` >
``no_artifact`` > ``completed``. The order matters because failures co-occur -- a killed command
also exits non-zero, and a command that exits non-zero may still have written a file -- and the
record must name the one that explains the others. ``completed`` is what remains when no
failure holds: an exit status of 0 is not enough, and only an artifact this run produced at the
declared path makes a run complete.

**The recorded state is derived, never asserted.** :class:`SupervisorStatus` re-classifies its
own facts and refuses a ``state`` or ``message`` they contradict, so the canonical JSON written
at ``--status-out`` cannot say ``completed`` beside ``artifact_present: false``. The exit status
is 0 iff ``completed``; each failure state has its own code (:data:`EXIT_CODES`), none of them 1
(an uncaught crash) or 2 (a usage error), so the job log names the state as well.

**An artifact already present is refused before the command starts** (``failed_to_start``): a
file this run did not write cannot evidence it, and deleting it would destroy whatever it is.

**At the bound the whole process group is killed.** The command starts in its own session
(POSIX ``start_new_session``) and ``os.killpg`` sends ``SIGKILL`` to that group, so harness
workers do not outlive the bound. Windows has no equivalent here: only the direct child is
killed, a warning is logged, and the record says ``kill_scope: process_only`` -- grandchildren
may survive. A signal that kills the supervisor itself (a cancelled job) leaves no record;
GitHub reports that run as cancelled, which is non-passing but is not one of these states.

Never run locally with a real proof command (I-0: the E5 run is a category-4 workload). Logs go
through ``structlog``; the CLI writes one ASCII summary line to stdout.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import structlog
from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: The five ways a supervised run can end. Exactly one is recorded per run.
RunState = Literal[
    "completed",
    "failed_to_start",
    "exited_nonzero",
    "exceeded_wall_clock",
    "no_artifact",
]

#: What the supervisor killed at the bound: nothing, the command's process group (POSIX), or
#: the command alone (Windows -- the honest degradation).
KillScope = Literal["none", "process_group", "process_only"]

#: Every state in classification precedence, strongest first. ``completed`` is last because it
#: is what remains when no failure holds.
RUN_STATES: Final[tuple[RunState, ...]] = (
    "failed_to_start",
    "exceeded_wall_clock",
    "exited_nonzero",
    "no_artifact",
    "completed",
)

#: One message per state. Each begins with its state's name and names no other state, so a
#: reader of the job log or of the status record is never left to infer which state occurred.
STATE_MESSAGES: Final[Mapping[RunState, str]] = {
    "failed_to_start": (
        "failed_to_start: the proof command was never started, so nothing was measured"
    ),
    "exceeded_wall_clock": (
        "exceeded_wall_clock: the proof command was still running at the wall-clock bound and "
        "was killed; a partial run is not a measurement"
    ),
    "exited_nonzero": (
        "exited_nonzero: the proof command ended with a non-zero or missing exit status, so the "
        "run it was meant to perform did not succeed"
    ),
    "no_artifact": (
        "no_artifact: the proof command exited 0 but wrote nothing at the declared artifact "
        "path, so there is no evidence to read"
    ),
    "completed": (
        "completed: the proof command exited 0 and wrote its artifact at the declared path "
        "in this run"
    ),
}

#: The supervisor's exit status per state: 0 only for ``completed``. Codes 1 and 2 are left to
#: an uncaught crash and to ``argparse``'s usage error, so no state can be mistaken for either.
EXIT_CODES: Final[Mapping[RunState, int]] = {
    "completed": 0,
    "failed_to_start": 3,
    "exceeded_wall_clock": 4,
    "exited_nonzero": 5,
    "no_artifact": 6,
}

#: How long to wait for a killed command to be reaped. ``SIGKILL`` cannot be caught, so this is
#: a bound on bookkeeping rather than a grace period; an unreaped command records no exit status.
REAP_SECONDS: Final[float] = 30.0

_LOG = structlog.get_logger(__name__)

__all__ = [
    "EXIT_CODES",
    "REAP_SECONDS",
    "RUN_STATES",
    "STATE_MESSAGES",
    "KillScope",
    "RunState",
    "SupervisorStatus",
    "classify_run",
    "main",
    "supervise",
]


def classify_run(
    *,
    spawn_error: str | None,
    returncode: int | None,
    timed_out: bool,
    artifact_present: bool,
) -> RunState:
    """The one state a run's facts describe, in :data:`RUN_STATES` precedence (R7.2).

    Any ``spawn_error`` -- including an empty one -- means the command never ran. A missing
    exit status (``None``) is not a zero one, so it classifies as ``exited_nonzero``.
    """
    if spawn_error is not None:
        return "failed_to_start"
    if timed_out:
        return "exceeded_wall_clock"
    if returncode != 0:
        return "exited_nonzero"
    if not artifact_present:
        return "no_artifact"
    return "completed"


class SupervisorStatus(BaseModel):
    """What one supervised run did, written as canonical JSON at ``--status-out``.

    ``state`` and ``message`` are derived from the facts beside them and validated against
    them, so the record cannot claim a state its own facts contradict.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: RunState
    message: str
    returncode: int | None
    elapsed_seconds: float = Field(ge=0.0, allow_inf_nan=False)
    wall_clock_seconds: float = Field(gt=0.0, allow_inf_nan=False)
    command: tuple[str, ...] = Field(min_length=1)
    artifact_path: str
    artifact_present: bool
    spawn_error: str | None
    timed_out: bool
    kill_scope: KillScope

    @model_validator(mode="after")
    def _state_is_derived_from_the_facts(self) -> SupervisorStatus:
        derived = classify_run(
            spawn_error=self.spawn_error,
            returncode=self.returncode,
            timed_out=self.timed_out,
            artifact_present=self.artifact_present,
        )
        if self.state != derived:
            raise ValueError(
                f"state {self.state!r} contradicts the recorded facts, which classify as "
                f"{derived!r}"
            )
        if self.message != STATE_MESSAGES[derived]:
            raise ValueError(f"message is not the message of state {derived!r}")
        if (self.kill_scope != "none") is not self.timed_out:
            raise ValueError(
                f"kill_scope {self.kill_scope!r} contradicts timed_out={self.timed_out}: the "
                "supervisor kills the command at the bound and at no other time"
            )
        return self

    @classmethod
    def from_facts(
        cls,
        *,
        command: Sequence[str],
        artifact_path: str,
        wall_clock_seconds: float,
        elapsed_seconds: float,
        spawn_error: str | None,
        returncode: int | None,
        timed_out: bool,
        artifact_present: bool,
        kill_scope: KillScope,
    ) -> SupervisorStatus:
        """Build the record, deriving ``state`` and ``message`` through :func:`classify_run`."""
        state = classify_run(
            spawn_error=spawn_error,
            returncode=returncode,
            timed_out=timed_out,
            artifact_present=artifact_present,
        )
        return cls(
            state=state,
            message=STATE_MESSAGES[state],
            returncode=returncode,
            elapsed_seconds=elapsed_seconds,
            wall_clock_seconds=wall_clock_seconds,
            command=tuple(command),
            artifact_path=artifact_path,
            artifact_present=artifact_present,
            spawn_error=spawn_error,
            timed_out=timed_out,
            kill_scope=kill_scope,
        )

    def canonical_json(self) -> str:
        """The record in this repository's one canonical JSON form."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _kill(process: subprocess.Popen[bytes]) -> KillScope:
    """Kill the command's whole process group (POSIX) or the command alone (Windows)."""
    if sys.platform == "win32":
        _LOG.warning(
            "proof_supervisor.kill_degraded",
            pid=process.pid,
            reason=(
                "no process-group kill on Windows: only the direct child is killed, so any "
                "process it started may survive the bound"
            ),
        )
        process.kill()
        return "process_only"
    else:
        # `start_new_session=True` made the command the leader of its own process group, so
        # its pid IS the group id. A group that is already gone has nothing left to kill.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        return "process_group"


def _reap(process: subprocess.Popen[bytes]) -> int | None:
    """The killed command's exit status, or ``None`` when it was not reaped in time."""
    try:
        return process.wait(timeout=REAP_SECONDS)
    except subprocess.TimeoutExpired:
        return None


def supervise(
    command: Sequence[str],
    *,
    wall_clock_seconds: float,
    expect_artifact: Path,
    status_out: Path,
) -> SupervisorStatus:
    """Run ``command`` under the bound, name how it ended, and write the canonical record.

    Raises:
        ValueError: ``command`` is empty, or the bound is not a finite number of seconds
            above zero -- a run that could not be bounded could not be named.
    """
    argv = tuple(command)
    if not argv:
        raise ValueError("no command to supervise")
    if not math.isfinite(wall_clock_seconds) or wall_clock_seconds <= 0.0:
        raise ValueError(
            f"the wall-clock bound must be a finite number of seconds above 0, got "
            f"{wall_clock_seconds!r}"
        )

    spawn_error: str | None = None
    returncode: int | None = None
    timed_out = False
    ran = False
    kill_scope: KillScope = "none"
    started = time.monotonic()

    if expect_artifact.exists():
        spawn_error = (
            f"an artifact already exists at {expect_artifact.as_posix()} before the run "
            "started; a file this run did not write cannot evidence it, so the command was "
            "not started"
        )
    else:
        _LOG.info(
            "proof_supervisor.start",
            command=list(argv),
            wall_clock_seconds=wall_clock_seconds,
            expect_artifact=expect_artifact.as_posix(),
        )
        try:
            process = subprocess.Popen(list(argv), start_new_session=True)
        except (OSError, ValueError) as error:
            spawn_error = f"{type(error).__name__}: {error}"
        else:
            ran = True
            try:
                returncode = process.wait(timeout=wall_clock_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                kill_scope = _kill(process)
                returncode = _reap(process)
            except BaseException:
                # Interrupted while waiting (KeyboardInterrupt): never leave the run behind.
                _kill(process)
                _reap(process)
                raise

    elapsed = time.monotonic() - started
    record = SupervisorStatus.from_facts(
        command=argv,
        artifact_path=expect_artifact.as_posix(),
        wall_clock_seconds=wall_clock_seconds,
        elapsed_seconds=round(elapsed, 3),
        spawn_error=spawn_error,
        returncode=returncode,
        timed_out=timed_out,
        artifact_present=ran and expect_artifact.is_file(),
        kill_scope=kill_scope,
    )
    status_out.parent.mkdir(parents=True, exist_ok=True)
    status_out.write_text(record.canonical_json() + "\n", encoding="utf-8")
    _LOG.info(
        "proof_supervisor.finished",
        state=record.state,
        returncode=record.returncode,
        elapsed_seconds=record.elapsed_seconds,
        kill_scope=record.kill_scope,
        status_out=status_out.as_posix(),
    )
    return record


def _ascii(text: str) -> str:
    """Escape non-ASCII for the Windows console (ASCII-only output contract, E-S13-07)."""
    return text if text.isascii() else text.encode("unicode_escape").decode("ascii")


def _summary_line(record: SupervisorStatus) -> str:
    return _ascii(
        f"proof-supervisor: state={record.state} returncode={record.returncode} "
        f"elapsed_seconds={record.elapsed_seconds} artifact={record.artifact_path} - "
        f"{record.message}"
    )


def _bound_seconds(text: str) -> float:
    """``--wall-clock-seconds``: a finite number of seconds above zero, or a usage error."""
    try:
        value = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"not a number of seconds: {text!r}") from error
    if not math.isfinite(value) or value <= 0.0:
        raise argparse.ArgumentTypeError(
            f"the wall-clock bound must be a finite number of seconds above 0, got {text!r}"
        )
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m uplift.proof_supervisor",
        usage=(
            "%(prog)s --wall-clock-seconds N --expect-artifact PATH --status-out PATH "
            "-- COMMAND [ARG ...]"
        ),
        description=(
            "Run the proof command under a wall-clock bound and record which of five states "
            "it ended in (R7.2). Exit 0 only for 'completed'."
        ),
    )
    parser.add_argument("--wall-clock-seconds", type=_bound_seconds, required=True)
    parser.add_argument("--expect-artifact", type=Path, required=True)
    parser.add_argument("--status-out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns :data:`EXIT_CODES` of the state the run ended in."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    # The command is split off at the first literal `--` BEFORE argparse sees anything, so a
    # flag of the supervised command (`--full`, `--output`) can never be read as one of ours.
    if "--" in arguments:
        split = arguments.index("--")
        options, command = arguments[:split], arguments[split + 1 :]
    else:
        options, command = arguments, []
    parser = _parser()
    args = parser.parse_args(options)
    if not command:
        parser.error("the command to supervise must follow a literal '--'")

    # Mirrors `uplift.regret.main` and `uplift.cost_probe.main`: CLI-only, process-global, and
    # to stderr, so stdout carries the summary line and the supervised command's own output.
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))

    wall_clock_seconds: float = args.wall_clock_seconds
    expect_artifact: Path = args.expect_artifact
    status_out: Path = args.status_out
    record = supervise(
        command,
        wall_clock_seconds=wall_clock_seconds,
        expect_artifact=expect_artifact,
        status_out=status_out,
    )
    sys.stdout.write(_summary_line(record) + "\n")
    sys.stdout.flush()
    return EXIT_CODES[record.state]


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
