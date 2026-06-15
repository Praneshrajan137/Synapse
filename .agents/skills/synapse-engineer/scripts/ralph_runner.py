"""Python wrapper around the Ralph loop (ADR-020).

This is a thin orchestrator over `scripts/ralph/ralph.sh` that makes the
Ralph workflow easier to invoke from a Claude session. It:

1. Validates that `spec.yaml` exists for the target agent.
2. Invokes `scripts/ralph/ralph.sh <agent> <max_iterations>`.
3. Streams the last N lines of `progress_<agent>.txt` back to stdout after
   the loop exits so the caller can see what happened.

Usage:
    python .claude/skills/synapse-engineer/scripts/ralph_runner.py <agent> [max_iter]

The Ralph loop itself runs `claude` CLI with `scripts/ralph/PROMPT.md` as
input and exits on `<promise>COMPLETE</promise>` or `max_iter` iterations.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def tail(path: Path, n: int = 40) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[-n:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", help="snake_case agent name under agents/")
    parser.add_argument("max_iter", nargs="?", type=int, default=20)
    args = parser.parse_args()

    spec = Path("agents") / args.agent / "spec.yaml"
    if not spec.exists():
        print(f"ERROR: {spec} not found — run spec_gen.py first", file=sys.stderr)
        return 1

    script = Path("scripts/ralph/ralph.sh")
    if not script.exists():
        print(f"ERROR: {script} missing (ADR-020 broken)", file=sys.stderr)
        return 1

    print(f"Launching Ralph loop: {args.agent}, max_iter={args.max_iter}")
    rc = subprocess.call(
        ["bash", str(script), args.agent, str(args.max_iter)],
    )

    progress = Path("scripts/ralph") / f"progress_{args.agent}.txt"
    print()
    print(f"── tail of {progress} ──")
    for line in tail(progress, 40):
        print(line)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
