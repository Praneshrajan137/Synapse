"""Fault proof for the verdict: introduce known faults one at a time and record what it says.

Each case is a fresh ``git archive`` of a commit in a scratch folder, changed there by one exact,
anchored edit (or one environment variable), and judged by ``python -m scripts.verdict`` run from
that copy. Nothing in the repository is touched. An edit whose anchor is not found is reported as
``EDIT-FAILED`` and not run, so a silent no-op cannot pass for a caught fault. The clean copy is
judged three times: a verdict that alarms on a clean tree is as useless as one that misses faults.

Usage: python -m scripts.verdict.fault_proof --scratch DIR --out FILE [--commit REV] [--only NAME]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

REPO: Final[Path] = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Edit:
    """Replace ``old`` with ``new`` on line ``line`` (1-based) of ``path``, which must hold it."""

    path: str
    line: int
    old: str
    new: str


@dataclass(frozen=True)
class Case:
    """One fault: its edits and environment, and the outcomes that count as caught."""

    name: str
    expect: tuple[str, ...]
    edits: tuple[Edit, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    args: tuple[str, ...] = ()


RS = "agents/inventory_sentinel/inference/request_state.py"
PROTOCOL = "orchestrator/consensus/protocol.py"
RATE_LINE = "            mean = observed / exposure_min * (lead_time_min + REVIEW_PERIOD_MIN)"

CASES: Final[tuple[Case, ...]] = (
    Case("clean-1", ("PASS",)),
    Case("clean-2", ("PASS",)),
    Case("clean-3", ("PASS",)),
    Case(
        "F1-confidence-floor-never-fails",
        ("SAFETY",),
        (
            Edit(
                "orchestrator/guardrails/rules.py",
                460,
                "if decision.confidence < threshold:",
                "if False:",
            ),
        ),
    ),
    Case(
        "F2-fast-path-binds-the-lowest-score",
        ("SAFETY", "WORSE", "CHANGED"),
        (Edit(PROTOCOL, 654, "fast_best = max(proposals", "fast_best = min(proposals"),),
    ),
    Case(
        "F3-sentinel-review-period-tripled",
        ("SAFETY", "WORSE", "CHANGED"),
        (
            Edit(
                RS,
                53,
                "REVIEW_PERIOD_MIN: Final[float] = 60.0",
                "REVIEW_PERIOD_MIN: Final[float] = 180.0",
            ),
        ),
    ),
    Case(
        "F4-nothing-is-executed",
        ("SAFETY",),
        (
            Edit(
                PROTOCOL,
                1568,
                "for proposal in decision.proposals:",
                "for proposal in decision.proposals[:0]:",
            ),
        ),
    ),
    Case(
        "F5-guardrail-failure-dispatches-anyway",
        ("SAFETY",),
        (Edit(PROTOCOL, 889, "if not passed or twin_veto:", "if False:"),),
    ),
    Case(
        "Q1-sentinel-demand-rate-halved",
        ("SAFETY", "WORSE", "CHANGED"),
        (Edit(RS, 104, RATE_LINE.strip(), RATE_LINE.strip() + " * 0.5"),),
    ),
    Case(
        "Q3-twin-arrival-rate-changed",
        ("CONTROL_MOVED", "SAFETY"),
        (Edit("digital_twin/config.py", 28, "default=2.0", "default=2.2"),),
    ),
    Case(
        "Q4-unseeded-randomness-in-the-sentinel",
        ("NONDETERMINISTIC", "SAFETY"),
        (
            Edit(
                RS,
                104,
                RATE_LINE.strip(),
                RATE_LINE.strip() + ' * (1.0 + 1e-3 * __import__("random").random())',
            ),
        ),
    ),
    Case(
        # The legacy engine seeds the GLOBAL `random` module with the replicate seed
        # (`_init_env`), so a stray `random.random()` is deterministic and Q4 is caught as a
        # changed decision, not as nondeterminism. A string hash differs per process
        # (PYTHONHASHSEED), so this one is caught by the cross-process repeat.
        "Q4b-process-dependent-hash-in-the-sentinel",
        ("NONDETERMINISTIC", "SAFETY"),
        (
            Edit(
                RS,
                104,
                RATE_LINE.strip(),
                RATE_LINE.strip() + ' * (1.0 + 1e-3 * (hash("synapse") % 1000) / 1000)',
            ),
        ),
    ),
    Case(
        "Q5-tuned-rule-comparison-flipped",
        ("CONTROL_MOVED", "SAFETY"),
        (Edit("uplift/tuned_static.py", 185, "if position <= point.s:", "if position < point.s:"),),
    ),
    Case(
        "Q6-twin-environment-variable-set", ("REFUSED_ENV",), env={"TW_ORDER_ARRIVAL_RATE": "2.2"}
    ),
    Case(
        "Q6b-twin-environment-variable-allowed",
        ("CONTROL_MOVED",),
        env={"TW_ORDER_ARRIVAL_RATE": "2.2"},
        args=("--allow-twin-env",),
    ),
    Case(
        "Q7-objective-weight-changed",
        ("CONTROL_MOVED", "SAFETY"),
        (
            Edit(
                "digital_twin/simulation/policy.yaml",
                75,
                "unmet_service: 8.0",
                "unmet_service: 7.0",
            ),
        ),
    ),
)


def export(commit: str, target: Path) -> None:
    """Write the tree of ``commit`` to ``target`` (``git archive``), replacing what was there."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", str(REPO), "archive", commit], capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(target, filter="data")


def apply(tree: Path, edit: Edit) -> bool:
    """Apply one anchored edit; ``False`` when the anchor is not on the stated line."""
    path = tree / edit.path
    lines = path.read_text(encoding="utf-8").split("\n")
    if edit.line > len(lines) or edit.old not in lines[edit.line - 1]:
        return False
    lines[edit.line - 1] = lines[edit.line - 1].replace(edit.old, edit.new, 1)
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def run_case(case: Case, commit: str, scratch: Path) -> dict[str, object]:
    """Judge one case's copy with the verdict and return what it said."""
    tree = scratch / "tree"
    export(commit, tree)
    for edit in case.edits:
        if not apply(tree, edit):
            return {"case": case.name, "result": "EDIT-FAILED", "edit": edit.path}
    # synapse_common goes on the path from a folder INSIDE the tree: its schema registry finds
    # proto/domain/ by walking up from its own file, so a copy outside the tree cannot start
    # (the consensus arm then refuses to assemble). Not `packages/` itself: its `tests` package
    # would shadow the repository's `tests` namespace (truth session 3, S3-M-18).
    side = tree / ".verdict-pkg"
    shutil.copytree(tree / "packages" / "synapse_common", side / "synapse_common")
    report = scratch / "verdict.json"
    report.unlink(missing_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("TW_")}
    env.update(case.env)
    env["PYTHONPATH"] = os.pathsep.join([str(tree), str(side)])
    started = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "-m", "scripts.verdict", "--json-out", str(report), *case.args],
        cwd=tree,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    seconds = round(time.perf_counter() - started, 1)
    verdict = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    outcome = str(verdict.get("outcome", done.stdout.split()[1] if done.stdout else "NONE"))
    return {
        "case": case.name,
        "expected": list(case.expect),
        "outcome": outcome,
        "exit_code": done.returncode,
        "caught_as_expected": outcome in case.expect,
        "findings": verdict.get("findings", []),
        "seconds": seconds,
    }


def main(argv: list[str] | None = None) -> int:
    """Run every case (or ``--only`` one) and write the results as canonical JSON."""
    parser = argparse.ArgumentParser(prog="python -m scripts.verdict.fault_proof")
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--only")
    args = parser.parse_args(argv)
    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", args.commit],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    results = []
    for case in CASES:
        if args.only and case.name != args.only:
            continue
        result = run_case(case, commit, args.scratch)
        results.append(result)
        print(
            f"{case.name}: {result.get('outcome', result.get('result'))} "
            f"(expected {'/'.join(case.expect)}) {result.get('seconds', '')} s",
            flush=True,
        )
    document = {
        "commit": commit,
        "machine": f"{platform.system()} {platform.release()}, {os.cpu_count()} logical CPUs, "
        f"Python {platform.python_version()}",
        "results": results,
        "all_caught": all(r.get("caught_as_expected") for r in results),
    }
    args.out.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return 0 if document["all_caught"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
