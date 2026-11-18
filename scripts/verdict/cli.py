"""``python -m scripts.verdict``: run the safety shards and the E5 miniature at once, then judge.

Usage::

    python -m scripts.verdict                 # judge the working tree; exit code = Outcome
    python -m scripts.verdict --repin         # accept the measured costs as the new pins
    python -m scripts.verdict --json-out FILE # also write the verdict as canonical JSON

The command refuses to run while any ``TW_`` environment variable is set: ``TwinConfig`` is a
pydantic ``BaseSettings`` with that prefix, so such a variable changes every legacy twin run
without changing any file (finding F-33). ``--allow-twin-env`` runs anyway, for demonstrating it.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from scripts.verdict import judge as j
from scripts.verdict import miniature

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
PINS_PATH: Final[str] = "infrastructure/quality/verdict-pins.json"
SEED_COUNT: Final[int] = 12
#: Seeds priced a second time, in other worker processes, to catch nondeterminism.
REPEAT_INDICES: Final[tuple[int, ...]] = (0, SEED_COUNT - 1)
#: Test files under ``tests/uplift`` and ``tests/verify`` that name the decision core's symbols
#: join the safety selection (truth session 2's fault-injection selection, kept as a rule so a
#: new test naming these symbols is selected without an edit here).
CORE_SYMBOLS: Final[re.Pattern[str]] = re.compile(
    r"request_state|REVIEW_PERIOD_MIN|forecast_from_request|_fast_path|fast_best|"
    r"_phase_execute|_ratify_and_dispatch|confidence_floor"
)
#: Needs ``python-jose``, which a fresh local ``.venv`` may lack (truth LOG M-26, D-13 item 6).
JOSE_MODULE: Final[str] = "orchestrator/tests/test_internal_only_routes.py"
SHARD_TIMEOUT_S: Final[float] = 900.0


@dataclass(frozen=True)
class ShardResult:
    """One safety shard's pytest run."""

    name: str
    exit_code: int
    summary: str
    seconds: float


def _core_test_files(root: Path) -> list[str]:
    selected: list[str] = []
    for folder in ("tests/uplift", "tests/verify"):
        for path in sorted((root / folder).glob("test_*.py")):
            if CORE_SYMBOLS.search(path.read_text(encoding="utf-8")):
                selected.append(path.relative_to(root).as_posix())
    return selected


def safety_shards(root: Path) -> tuple[dict[str, list[str]], list[str]]:
    """The two shards' pytest arguments, and notes on anything left out."""
    notes: list[str] = []
    orchestrator = ["orchestrator/tests"]
    if importlib.util.find_spec("jose") is None:
        orchestrator.append(f"--ignore={JOSE_MODULE}")
        notes.append(f"{JOSE_MODULE} left out: python-jose is not installed here")
    sentinel = ["agents/inventory_sentinel/tests", *_core_test_files(root)]
    return {"orchestrator": orchestrator, "sentinel+core": sentinel}, notes


def _launch(root: Path, args: Sequence[str]) -> subprocess.Popen[str]:
    env = dict(os.environ, HYPOTHESIS_PROFILE="dev", PYTHONDONTWRITEBYTECODE="1")
    command = [
        sys.executable,
        "-m",
        "pytest",
        *args,
        "-m",
        "not slow",
        "-q",
        "--tb=line",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=--strict-markers",
    ]
    return subprocess.Popen(
        command,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _run_shard(root: Path, name: str, args: Sequence[str]) -> ShardResult:
    """Run one safety shard to completion (called on a thread, so its time is its own)."""
    started = time.perf_counter()
    process = _launch(root, args)
    try:
        output, _ = process.communicate(timeout=SHARD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        return ShardResult(name, 124, f"timed out after {SHARD_TIMEOUT_S:.0f} s", 0.0)
    lines = [line for line in output.splitlines() if line.strip()]
    summary = next(
        (
            line.strip("= ")
            for line in reversed(lines)
            if re.search(r"\d+ (passed|failed|error)", line)
        ),
        lines[-1] if lines else "no output",
    )
    failed = [line for line in lines if line.startswith(("FAILED", "ERROR"))][:8]
    if failed:
        summary += "\n      " + "\n      ".join(line[:160] for line in failed)
    return ShardResult(name, int(process.returncode), summary, time.perf_counter() - started)


def measure(
    root: Path, seeds: Sequence[int], processes: int = 2
) -> tuple[dict[str, dict[int, float]], dict[str, dict[int, float]], list[str]]:
    """Price every seed for both arms across ``processes`` processes, each importing once.

    Each process pays the agent stack's import once (about 12 s on the laptop) and then prices
    its share in sequence; a pool that hands out single replicates was slower (3 to 8 workers:
    49 to 87 s, measured, truth session 3), because every worker pays the import and they
    contend. Share 0 runs in this process. Each repeat seed is re-priced by a share other than
    the one that priced it first, so it runs in another process with another string-hash seed:
    a result that depends on set or dict iteration order differs there, and is caught.
    """
    count = max(1, min(processes, len(seeds)))
    shares: list[list[tuple[int, str, int]]] = [[] for _ in range(count)]
    owner: dict[int, int] = {}
    for position, seed in enumerate(seeds):
        owner[seed] = position * count // len(seeds)
        shares[owner[seed]] += [(seed, arm, 0) for arm in j.ARMS]
    for index in REPEAT_INDICES:
        if index < len(seeds):
            seed = seeds[index]
            shares[(owner[seed] + 1) % count] += [(seed, arm, 1) for arm in j.ARMS]
    costs: dict[str, dict[int, float]] = {arm: {} for arm in j.ARMS}
    repeats: dict[str, dict[int, float]] = {arm: {} for arm in j.ARMS}
    failures: list[str] = []
    results: list[tuple[int, str, int, float | str]] = []
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max(1, count - 1), initializer=miniature.init_worker, initargs=(str(root),)
    ) as pool:
        remote = [pool.submit(miniature.price_many, share) for share in shares[1:]]
        miniature.init_worker(str(root))
        results += miniature.price_many(shares[0])
        for future in remote:
            try:
                results += future.result()
            except Exception as exc:  # noqa: BLE001 -- a dead worker is reported, never hidden
                failures.append(f"a pricing process failed: {type(exc).__name__}: {exc}")
    for seed, arm, run, outcome in results:
        if isinstance(outcome, str):
            failures.append(f"{arm} at seed {seed}{' (repeat)' if run else ''}: {outcome}")
        else:
            (repeats if run else costs)[arm][seed] = outcome
    return costs, repeats, failures


def _read_pins(root: Path) -> j.Pins | None:
    path = root / PINS_PATH
    if not path.is_file():
        return None
    return j.pins_from_document(json.loads(path.read_text(encoding="utf-8")))


def _write_pins(root: Path, seeds: Sequence[int], costs: Mapping[str, Mapping[int, float]]) -> None:
    pins = j.Pins(seeds=tuple(seeds), costs={arm: dict(costs[arm]) for arm in j.ARMS})
    document = j.pins_to_document(
        pins,
        "E5's first twelve replicate seeds priced by uplift.e5_suite.production_arm_cost for the "
        "consensus arm and the tuned control E; written by `python -m scripts.verdict --repin`.",
    )
    text = json.dumps(document, sort_keys=True, separators=(",", ":"))
    (root / PINS_PATH).write_text(text + "\n", encoding="utf-8")


def _report(
    verdict: j.Verdict,
    shards: Sequence[ShardResult],
    costs: Mapping[str, Mapping[int, float]],
    notes: Sequence[str],
    seconds: float,
) -> str:
    out = [
        f"VERDICT: {verdict.outcome.name} (exit {int(verdict.outcome)}) in {seconds:.1f} s "
        f"on {os.cpu_count()} logical CPUs, {platform.system()}, Python {platform.python_version()}"
    ]
    out += [
        f"  safety  {s.name}: {s.summary} (exit {s.exit_code}, {s.seconds:.1f} s)" for s in shards
    ]
    if all(costs.get(arm) for arm in j.ARMS):
        consensus = sorted(costs["consensus"].items())
        tuned = dict(costs["tuned"])
        diffs = [tuned[seed] - cost for seed, cost in consensus if seed in tuned]
        if diffs:
            mean_c = sum(c for _, c in consensus) / len(consensus)
            mean_t = sum(tuned.values()) / len(tuned)
            out.append(
                f"  quality E5 miniature, {len(consensus)} seeds: consensus {mean_c:.4f}, "
                f"tuned {mean_t:.4f}, difference (tuned - consensus) "
                f"{sum(diffs) / len(diffs):+.4f}, "
                f"consensus worse in {sum(d < 0 for d in diffs)} of {len(diffs)}"
            )
    for delta in verdict.deltas.values():
        state = (
            "unchanged"
            if not delta.changed_seeds
            else (
                f"changed on {len(delta.changed_seeds)} seeds, mean {delta.mean_delta:+.6f}"
                + (f" (standard error {delta.standard_error:.6f})" if delta.standard_error else "")
            )
        )
        out.append(f"  pins    {delta.arm}: {state}")
    out += [f"  finding {text}" for text in verdict.findings]
    out += [f"  note    {text}" for text in notes]
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the verdict; return its outcome as the exit code."""
    parser = argparse.ArgumentParser(prog="python -m scripts.verdict", description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="tree to judge (default: .)")
    parser.add_argument("--repin", action="store_true", help="write the measured costs as pins")
    parser.add_argument("--json-out", type=Path, help="also write the verdict as canonical JSON")
    parser.add_argument("--allow-twin-env", action="store_true", help="run despite TW_ variables")
    parser.add_argument(
        "--processes", type=int, default=2, help="processes pricing the miniature (default 2)"
    )
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()
    started = time.perf_counter()

    twin_env = sorted(name for name in os.environ if name.upper().startswith("TW_"))
    if twin_env and not args.allow_twin_env:
        print(
            f"VERDICT: REFUSED_ENV (exit {int(j.Outcome.REFUSED_ENV)}): {', '.join(twin_env)} "
            "set; TwinConfig reads TW_* variables, which change the twin's physics without "
            "changing any file (finding F-33). Unset them, or pass --allow-twin-env."
        )
        return int(j.Outcome.REFUSED_ENV)

    shard_args, notes = safety_shards(root)
    if twin_env:
        notes.append(f"ran with {', '.join(twin_env)} set (--allow-twin-env)")
    failures: list[str] = []
    physics_moved: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(shard_args)) as threads:
        running = [threads.submit(_run_shard, root, n, a) for n, a in shard_args.items()]
        try:
            seeds = miniature.replicate_seeds(root, SEED_COUNT)
            costs, repeats, failures = measure(root, seeds, args.processes)
        except Exception as exc:  # noqa: BLE001 -- the verdict reports, it does not crash
            seeds, costs, repeats = (), {arm: {} for arm in j.ARMS}, {arm: {} for arm in j.ARMS}
            text = f"{type(exc).__name__}: {exc}"
            if type(exc).__name__ == "BprimeRecordError" and "physics digest" in str(exc):
                physics_moved.append(text)
            else:
                failures = [f"the miniature could not start: {text}"]
        shards = [future.result() for future in running]

    pins = _read_pins(root)
    if pins is None:
        failures.append(f"no pins at {PINS_PATH}; run with --repin to create them")
        pins = j.Pins(seeds=tuple(seeds), costs={arm: {} for arm in j.ARMS})
    elif seeds and tuple(seeds) != pins.seeds:
        failures.append(f"{PINS_PATH} pins other seeds than E5's first {SEED_COUNT}")
    measurement = j.Measurement(
        costs=costs,
        repeats=repeats,
        shard_exit_codes={s.name: s.exit_code for s in shards},
        failures=tuple(failures),
        physics_moved=tuple(physics_moved),
    )
    verdict = j.judge(pins, measurement)

    if args.repin:
        pin_problems = (f"no pins at {PINS_PATH}", f"{PINS_PATH} pins other seeds")
        measured_fully = all(len(costs[arm]) == len(seeds) > 0 for arm in j.ARMS)
        repeats_agree = all(
            costs[arm].get(seed) == again for arm in j.ARMS for seed, again in repeats[arm].items()
        )
        safe = all(s.exit_code == 0 for s in shards)
        clean = all(text.startswith(pin_problems) for text in failures)
        if not (safe and clean and measured_fully and repeats_agree):
            print(_report(verdict, shards, costs, notes, time.perf_counter() - started))
            print("REPIN REFUSED: pins are written only from a safe, complete, deterministic run")
            return int(verdict.outcome)
        _write_pins(root, seeds, costs)
        notes.append(f"pins written to {PINS_PATH} ({verdict.outcome.name} before re-pinning)")
        verdict = j.Verdict(j.Outcome.PASS, (), verdict.deltas)

    seconds = time.perf_counter() - started
    print(_report(verdict, shards, costs, notes, seconds))
    if args.json_out is not None:
        document = {
            "outcome": verdict.outcome.name,
            "exit_code": int(verdict.outcome),
            "findings": list(verdict.findings),
            "notes": notes,
            "seconds": round(seconds, 1),
            "shards": {s.name: {"exit_code": s.exit_code, "summary": s.summary} for s in shards},
            "costs": {
                arm: {str(k): v.hex() for k, v in sorted(costs[arm].items())} for arm in j.ARMS
            },
        }
        args.json_out.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
        )
    return int(verdict.outcome)
