"""Run a CI step's own ``run:`` text as a pre-commit hook, so a duplicated check has one definition.

A hook that checks what a CI job already checks runs that job's step, read from the workflow file
when the hook runs (truth session 5, stage E; TRUTH-MAP F-34). Editing the step changes the hook
with it; renaming or deleting the step fails the hook, and ``tests/hooks``, by name.

Usage::

    python scripts/hooks/run_ci_step.py <workflow> <job> <step name> [<step name> ...]
    python scripts/hooks/run_ci_step.py --mirrors [<config>]  # ids of the hooks that mirror a step
    python scripts/hooks/run_ci_step.py --check [<config>]    # every mirrored step resolves

The step runs under ``bash -e`` (GitHub's default shell for ``run:`` on Linux) from the repository
root, with the step's literal ``env`` added. A step that is an action (``uses:``), sets a
``working-directory``, or uses a ``${{ }}`` expression is refused: it cannot run outside CI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CONFIG: Final[Path] = ROOT / ".pre-commit-config.yaml"
SELF: Final[str] = "scripts/hooks/run_ci_step.py"


class StepError(Exception):
    """A mirrored step cannot be found or cannot run outside CI."""


def find_step(workflow: Path, job: str, name: str) -> dict[str, Any]:
    """The one step named ``name`` in ``job`` of ``workflow``, checked to be runnable here."""
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    jobs = doc.get("jobs") or {}
    where = f"{workflow.as_posix()}::{job}"
    if job not in jobs:
        raise StepError(f"{workflow.as_posix()}: no job {job!r}")
    found = [step for step in jobs[job].get("steps") or [] if step.get("name") == name]
    if len(found) != 1:
        raise StepError(f"{where}: {len(found)} steps named {name!r}, not 1")
    step: dict[str, Any] = found[0]
    run = step.get("run")
    if not isinstance(run, str):
        raise StepError(f"{where}::{name} has no run: text (an action cannot run as a hook)")
    if "working-directory" in step:
        raise StepError(f"{where}::{name} sets a working-directory")
    env = step.get("env") or {}
    if "${{" in run or any("${{" in str(value) for value in env.values()):
        raise StepError(f"{where}::{name} uses a ${{{{ }}}} expression")
    return step


def mirrors(config: Path = CONFIG) -> list[tuple[str, list[str]]]:
    """``(hook id, [workflow, job, step name, ...])`` for every hook whose entry is this script."""
    doc = yaml.safe_load(config.read_text(encoding="utf-8"))
    out: list[tuple[str, list[str]]] = []
    for repo in doc.get("repos") or []:
        for hook in repo.get("hooks") or []:
            if str(hook.get("entry", "")).split()[-1:] == [SELF]:
                args = [str(arg) for arg in hook.get("args") or []]
                if len(args) < 3:
                    raise StepError(f"hook {hook.get('id')!r}: args must be workflow, job, step...")
                out.append((str(hook["id"]), args))
    return out


def _bash() -> str:
    """Git for Windows' bash on Windows (not WSL's launcher in System32), else bash on PATH."""
    if os.name == "nt":
        git = shutil.which("git")
        if git is not None:
            for parent in Path(git).resolve().parents:
                candidate = parent / "bin" / "bash.exe"
                if candidate.is_file():
                    return str(candidate)
    found = shutil.which("bash")
    if found is None:
        raise StepError("bash is not on PATH")
    return found


def run_steps(workflow: str, job: str, names: list[str]) -> int:
    """Run each named step in order; stop at the first that fails and return its exit status."""
    bash = _bash()
    for name in names:
        step = find_step(ROOT / workflow, job, name)
        env = {**os.environ, **{str(k): str(v) for k, v in (step.get("env") or {}).items()}}
        print(f"-- {workflow}::{job}::{name}", flush=True)
        code = subprocess.run([bash, "-e", "-c", step["run"]], cwd=ROOT, env=env, check=False)
        if code.returncode != 0:
            return code.returncode
    return 0


def check(config: Path = CONFIG) -> int:
    """Resolve every mirrored step; return the number of steps checked."""
    count = 0
    for _hook, (workflow, job, *names) in mirrors(config):
        for name in names:
            find_step(ROOT / workflow, job, name)
            count += 1
    return count


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["--mirrors"]:
            config = Path(argv[1]) if len(argv) > 1 else CONFIG
            print(",".join(hook for hook, _ in mirrors(config)))
            return 0
        if argv[:1] == ["--check"]:
            config = Path(argv[1]) if len(argv) > 1 else CONFIG
            print(f"OK {check(config)} mirrored CI steps resolve")
            return 0
        if len(argv) < 3:
            print(__doc__)
            return 2
        return run_steps(argv[0], argv[1], argv[2:])
    except StepError as exc:
        print(f"FAIL {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
