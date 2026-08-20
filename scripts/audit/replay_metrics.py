"""Measure the golden-trace replay floors CLAUDE.md has stated with no gate (R7.6, R7.7).

Audit finding: the KV-cache hit rate (``0.70``) and the tier-routing accuracy
(``0.80``) have been documented in ``CLAUDE.md`` since Sprint 9, and no assertion
for either exists anywhere in ``scripts/**`` or ``.github/workflows/**``. This gate
is the missing measurement. It replays the 200 golden traces produced by
``tests/eval/generate_traces.py`` (seed ``0xCAFEBABE``) through the **existing**
eval harness and compares each measured value against the floor committed in
``infrastructure/quality/replay-floors.yaml``.

Nothing here hardcodes a floor. Both floors, the trace directory, the expected
trace count, and the seed are read from that YAML file (``encoding='utf-8'``,
E-S13-07), so the numbers stay pinnable by ``doc-number-pins.yaml`` and ratchetable
by ``infrastructure/quality/ratchets.json`` (ids ``replay-floor:kv-cache`` and
``replay-floor:tier-routing``).

Reused harness, not a new one:

  * **tier-routing accuracy** -- ``tests.eval.run.run_suite()`` already replays every
    trace in ``tests/eval/golden_traces`` through the real
    ``orchestrator.consensus.tier_router.TierRouter`` and reports ``correct``/``total``.
  * **KV-cache hit rate** -- the replay's cache observations land on the
    ``synapse_ollama_cache_hit_rate`` gauge that
    ``orchestrator/llm/ollama_client.py:152`` sets. The measurement is the mean over
    the gauge's samples, exactly as ``tests/observability/test_kv_cache_hit_rate.py``
    reads it.

**I-7 honest degradation.** When the traces are absent, the harness cannot be
imported, or a metric has no observation to read (Ollama offline, so the cache gauge
carries no samples), that metric is reported ``unavailable`` and the gate exits ``2``.
An ``unavailable`` is never a PASS and no value is ever fabricated to stand in for a
measurement that was not taken. A measured regression outranks an unavailability so an
unrelated absence can never mask a real floor breach.

Outcome mapping::

    any metric measured and below its floor -> exit 1  (fail; measured + floor printed)
    else any metric unavailable             -> exit 2  (unavailable; never a pass)
    else every metric at-or-above its floor -> exit 0  (pass)

CI: this gate is a ``.github/workflows/ci.yml::quality-gates`` step and nothing else.
Replaying 200 traces is a CI workload; under **I-0** it is never run on the
development laptop. So ``evaluate()`` takes two seams with production defaults - a
``root`` for the tree it reads (floors file, trace directory) and a ``measurers``
mapping for where the numbers come from - which lets the verdict be exercised over a
hermetic temporary tree on synthetic measurements without any replay. Nothing in the
gate is monkeypatched to achieve that.

Run::

    python -m scripts.audit.replay_metrics             # human summary
    python -m scripts.audit.replay_metrics --json      # canonical JSON report
    python -m scripts.audit.replay_metrics --check     # exit 0/1/2 per the mapping
    python -m scripts.audit.replay_metrics --check --out build/audit/replay-metrics.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Mapping
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]

# Ensure the repo root is importable when run as a bare script (not -m).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: Path of the committed floors file, relative to a tree root.
FLOORS_RELPATH = ("infrastructure", "quality", "replay-floors.yaml")

FLOORS_FILE = ROOT.joinpath(*FLOORS_RELPATH)

#: A measurer takes no argument and returns ``(measured value, human detail)``, or
#: raises :class:`_Unavailable` when the measurement could not be taken (I-7).
Measurer = Callable[[], tuple[float, str]]

# Distinct exit codes, mirroring scripts/audit/uplift_truth.py.
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNAVAILABLE = 2

# The only floor direction this gate knows how to evaluate. Any other value in the
# committed configuration is a configuration error, not a measurement.
DIRECTION_AT_OR_ABOVE = "at-or-above"

# Floor keys in replay-floors.yaml, in report order.
KV_CACHE_METRIC = "kv_cache_hit_rate"
TIER_ROUTING_METRIC = "tier_routing_accuracy"
METRIC_ORDER = (KV_CACHE_METRIC, TIER_ROUTING_METRIC)


class Outcome(str, Enum):
    """Tri-state metric outcome. ``UNAVAILABLE`` is never a pass (I-7)."""

    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


class MetricReport(BaseModel):
    """One measured (or unmeasurable) replay metric against its committed floor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric: str
    floor: float | None = None
    measured: float | None = None
    direction: str | None = None
    outcome: Outcome
    detail: str


class ReplayReport(BaseModel):
    """The full replay-metrics verdict, persisted canonically."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    floors_file: str
    traces_dir: str | None = None
    seed: str | None = None
    traces_expected: int | None = None
    traces_found: int | None = None
    metrics: tuple[MetricReport, ...] = ()
    outcome: Outcome
    exit_code: int

    def canonical_json(self) -> str:
        """Canonical serialisation for a persisted payload."""
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )


class _Unavailable(Exception):
    """Raised when the configuration or the harness cannot supply a measurement."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _as_finite_float(value: object) -> float | None:
    """Coerce a YAML scalar to a finite float, rejecting bools and non-numerics."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def floors_path(root: Path = ROOT) -> Path:
    """Where the committed floors file lives under ``root``."""
    return root.joinpath(*FLOORS_RELPATH)


def load_config(floors_file: Path | None = None, *, root: Path = ROOT) -> dict[str, Any]:
    """Read ``replay-floors.yaml``.

    Raises :class:`_Unavailable` when the file is missing, unreadable, or not a
    mapping -- the gate must never invent a floor it could not read.
    """
    floors_file = floors_file if floors_file is not None else floors_path(root)
    if not floors_file.is_file():
        raise _Unavailable(f"floors file missing: {_rel(floors_file, root)}")
    try:
        data = yaml.safe_load(floors_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _Unavailable(f"floors file unreadable: {_rel(floors_file, root)}: {exc}") from exc
    if not isinstance(data, dict):
        raise _Unavailable(f"floors file is not a mapping: {_rel(floors_file, root)}")
    return data


def _rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_floor(
    config: dict[str, Any],
    metric: str,
    *,
    floors_file: Path | None = None,
    root: Path = ROOT,
) -> tuple[float, str]:
    """Read one floor value and its direction from the committed configuration."""
    label = _rel(floors_file if floors_file is not None else floors_path(root), root)
    floors = config.get("floors")
    if not isinstance(floors, dict):
        raise _Unavailable(f"no `floors` mapping in {label}")
    entry = floors.get(metric)
    if not isinstance(entry, dict):
        raise _Unavailable(f"no floor recorded for `{metric}` in {label}")
    floor = _as_finite_float(entry.get("value"))
    if floor is None:
        raise _Unavailable(f"floor for `{metric}` is not a finite number")
    direction = entry.get("direction")
    if direction != DIRECTION_AT_OR_ABOVE:
        raise _Unavailable(
            f"floor for `{metric}` declares unsupported direction {direction!r} "
            f"(this gate evaluates {DIRECTION_AT_OR_ABOVE!r} only)"
        )
    return floor, DIRECTION_AT_OR_ABOVE


def resolve_traces(
    config: dict[str, Any],
    *,
    floors_file: Path | None = None,
    root: Path = ROOT,
) -> tuple[Path, int, int, str]:
    """Resolve the trace directory and confirm the committed trace count and seed.

    Returns ``(traces_dir, expected, found, seed)``. Raises :class:`_Unavailable`
    when the traces are absent or the generator's seed does not match the seed the
    configuration says the measurement is taken under.
    """
    label = _rel(floors_file if floors_file is not None else floors_path(root), root)
    replay = config.get("replay")
    if not isinstance(replay, dict):
        raise _Unavailable(f"no `replay` mapping in {label}")

    raw_dir = replay.get("traces_dir")
    if not isinstance(raw_dir, str) or not raw_dir:
        raise _Unavailable(f"no `replay.traces_dir` in {label}")
    traces_dir = root / Path(raw_dir)

    expected = _as_finite_float(replay.get("trace_count"))
    if expected is None or expected != int(expected):
        raise _Unavailable(f"`replay.trace_count` is not an integer in {label}")
    expected_count = int(expected)

    seed = replay.get("seed")
    if not isinstance(seed, str) or not seed:
        raise _Unavailable(f"no `replay.seed` in {label}")

    if not traces_dir.is_dir():
        raise _Unavailable(f"golden traces missing: {_rel(traces_dir, root)} is not a directory")
    found = len(list(traces_dir.glob("*.json")))
    if found == 0:
        raise _Unavailable(f"golden traces missing: no *.json under {_rel(traces_dir, root)}")
    if found != expected_count:
        raise _Unavailable(
            f"golden trace count drift: {found} on disk under {_rel(traces_dir, root)}, "
            f"{expected_count} recorded in {label} -- "
            f"regenerate with `python tests/eval/generate_traces.py`"
        )

    generator_seed = _generator_seed()
    if generator_seed != _parse_seed(seed, label):
        raise _Unavailable(
            f"seed drift: generator SEED is {generator_seed:#x}, {label} records {seed}"
        )
    return traces_dir, expected_count, found, seed


def _parse_seed(seed: str, label: str) -> int:
    """Parse the committed hexadecimal seed, refusing to guess at a malformed one."""
    try:
        return int(seed, 16)
    except ValueError as exc:
        raise _Unavailable(f"`replay.seed` is not hexadecimal in {label}: {seed!r}") from exc


def _generator_seed() -> int:
    """Read the seed from the real generator so config drift is detectable."""
    try:
        from tests.eval.generate_traces import SEED
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise _Unavailable(f"trace generator unavailable: {exc}") from exc
    return int(SEED)


def measure_tier_routing_accuracy() -> tuple[float, str]:
    """Replay every golden trace through the real TierRouter via the eval harness."""
    try:
        from tests.eval.run import run_suite
    except ImportError as exc:
        raise _Unavailable(f"replay harness unavailable: tests.eval.run: {exc}") from exc
    try:
        _results, summary = run_suite()
    except Exception as exc:  # noqa: BLE001 - any harness failure is an unavailability
        raise _Unavailable(f"replay harness failed: {type(exc).__name__}: {exc}") from exc
    total = summary.get("total")
    correct = summary.get("correct")
    if not isinstance(total, int) or not isinstance(correct, int) or total <= 0:
        raise _Unavailable("replay harness reported no classified traces")
    return correct / total, f"{correct}/{total} traces classified into their expected tier"


def measure_kv_cache_hit_rate() -> tuple[float, str]:
    """Mean of the ``synapse_ollama_cache_hit_rate`` gauge after the replay.

    The gauge is set by ``orchestrator/llm/ollama_client.py`` per completion. When
    Ollama is offline the replay takes no cache observation, the gauge carries no
    samples, and this raises :class:`_Unavailable` rather than reporting a zero.
    """
    try:
        from synapse_common.metrics import OLLAMA_CACHE_HIT_RATE
    except ImportError as exc:
        raise _Unavailable(f"metrics registry unavailable: {exc}") from exc
    values: list[float] = []
    for metric in OLLAMA_CACHE_HIT_RATE.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total") or sample.name.endswith("_created"):
                continue
            numeric = _as_finite_float(sample.value)
            if numeric is not None:
                values.append(numeric)
    if not values:
        raise _Unavailable(
            "synapse_ollama_cache_hit_rate has no samples -- the replay took no "
            "cache observation (Ollama offline); no hit rate was measured"
        )
    return sum(values) / len(values), f"mean of {len(values)} gauge sample(s)"


def _judge(
    metric: str, floor: float, direction: str, measured: float, detail: str
) -> MetricReport:
    below = measured < floor
    return MetricReport(
        metric=metric,
        floor=floor,
        measured=measured,
        direction=direction,
        outcome=Outcome.FAIL if below else Outcome.PASS,
        detail=detail,
    )


def _unavailable_metric(metric: str, floor: float | None, detail: str) -> MetricReport:
    return MetricReport(
        metric=metric,
        floor=floor,
        measured=None,
        direction=None,
        outcome=Outcome.UNAVAILABLE,
        detail=detail,
    )


def default_measurers() -> dict[str, Measurer]:
    """The production measurers: the real eval harness and the real cache gauge.

    Exposed as a seam so the verdict logic can be exercised on synthetic
    measurements without replaying the 200 golden traces, which is a CI workload
    (**I-0**). Production callers never pass a substitute.
    """
    return {
        TIER_ROUTING_METRIC: measure_tier_routing_accuracy,
        KV_CACHE_METRIC: measure_kv_cache_hit_rate,
    }


def aggregate(metrics: tuple[MetricReport, ...]) -> Outcome:
    """Fold per-metric outcomes into the gate outcome.

    A measured breach outranks an unavailability, so an unrelated absent measurement
    can never mask a real floor regression; an unavailability outranks a pass, so
    absence of proof is never a pass (I-7). An empty metric set is unavailable.
    """
    if any(metric.outcome is Outcome.FAIL for metric in metrics):
        return Outcome.FAIL
    if not metrics or any(metric.outcome is Outcome.UNAVAILABLE for metric in metrics):
        return Outcome.UNAVAILABLE
    return Outcome.PASS


def exit_code_for(outcome: Outcome) -> int:
    """The process exit code each outcome maps to. ``2`` is non-passing (I-7)."""
    return {
        Outcome.PASS: EXIT_PASS,
        Outcome.FAIL: EXIT_FAIL,
        Outcome.UNAVAILABLE: EXIT_UNAVAILABLE,
    }[outcome]


def evaluate(
    floors_file: Path | None = None,
    *,
    root: Path = ROOT,
    measurers: Mapping[str, Measurer] | None = None,
) -> ReplayReport:
    """Measure both replay metrics and return the tri-state verdict.

    A measured breach (``fail``) outranks an unavailability so an absent measurement
    can never mask a real floor regression.
    """
    floors_file = floors_file if floors_file is not None else floors_path(root)
    try:
        config = load_config(floors_file, root=root)
    except _Unavailable as exc:
        return _report(
            floors_file, None, None, None, None, (), Outcome.UNAVAILABLE, exc.detail, root=root
        )

    floors: dict[str, float | None] = {}
    directions: dict[str, str | None] = {}
    floor_errors: dict[str, str] = {}
    for metric in METRIC_ORDER:
        try:
            floor, direction = read_floor(config, metric, floors_file=floors_file, root=root)
        except _Unavailable as exc:
            floors[metric], directions[metric], floor_errors[metric] = None, None, exc.detail
        else:
            floors[metric], directions[metric] = floor, direction

    try:
        traces_dir, expected, found, seed = resolve_traces(
            config, floors_file=floors_file, root=root
        )
    except _Unavailable as exc:
        metrics = tuple(
            _unavailable_metric(metric, floors[metric], floor_errors.get(metric, exc.detail))
            for metric in METRIC_ORDER
        )
        return _report(
            floors_file, None, None, None, None, metrics, Outcome.UNAVAILABLE, exc.detail,
            root=root,
        )

    # The tier-routing replay runs first; the KV-cache gauge is read after it so any
    # cache observation the replay produced is already recorded.
    measured: dict[str, MetricReport] = {}
    active = dict(default_measurers()) if measurers is None else dict(measurers)
    for metric in (TIER_ROUTING_METRIC, KV_CACHE_METRIC):
        floor, direction = floors[metric], directions[metric]
        if floor is None or direction is None:
            measured[metric] = _unavailable_metric(metric, floor, floor_errors[metric])
            continue
        measurer = active.get(metric)
        if measurer is None:
            measured[metric] = _unavailable_metric(
                metric, floor, f"no measurer available for `{metric}`"
            )
            continue
        try:
            value, detail = measurer()
        except _Unavailable as exc:
            measured[metric] = _unavailable_metric(metric, floor, exc.detail)
        else:
            measured[metric] = _judge(metric, floor, direction, value, detail)

    metrics = tuple(measured[metric] for metric in METRIC_ORDER)
    return _report(
        floors_file,
        _rel(traces_dir, root),
        seed,
        expected,
        found,
        metrics,
        aggregate(metrics),
        None,
        root=root,
    )


def _report(
    floors_file: Path,
    traces_dir: str | None,
    seed: str | None,
    expected: int | None,
    found: int | None,
    metrics: tuple[MetricReport, ...],
    outcome: Outcome,
    reason: str | None,
    *,
    root: Path = ROOT,
) -> ReplayReport:
    exit_code = exit_code_for(outcome)
    if not metrics and reason is not None:
        metrics = tuple(_unavailable_metric(metric, None, reason) for metric in METRIC_ORDER)
    return ReplayReport(
        floors_file=_rel(floors_file, root),
        traces_dir=traces_dir,
        seed=seed,
        traces_expected=expected,
        traces_found=found,
        metrics=metrics,
        outcome=outcome,
        exit_code=exit_code,
    )


_MARKER = {Outcome.PASS: "[OK]", Outcome.FAIL: "[XX]", Outcome.UNAVAILABLE: "[??]"}


def _format(report: ReplayReport) -> list[str]:
    """ASCII-only human summary. Every metric prints its measured value and floor."""
    lines: list[str] = []
    if report.traces_found is not None:
        lines.append(
            f"replay-metrics: {report.traces_found} golden traces from "
            f"{report.traces_dir} (seed {report.seed}); floors from {report.floors_file}"
        )
    else:
        lines.append(f"replay-metrics: no replay performed; floors from {report.floors_file}")
    for metric in report.metrics:
        marker = _MARKER[metric.outcome]
        floor = "unknown" if metric.floor is None else f"{metric.floor:.4f}"
        if metric.measured is None:
            lines.append(
                f"{marker} {metric.metric}: measured UNAVAILABLE, floor {floor} "
                f"-- {metric.detail}"
            )
        else:
            relation = ">=" if metric.outcome is Outcome.PASS else "<"
            lines.append(
                f"{marker} {metric.metric}: measured {metric.measured:.4f} {relation} "
                f"floor {floor} ({metric.detail})"
            )
    if report.outcome is Outcome.UNAVAILABLE:
        lines.append(
            "[??] replay-metrics: UNAVAILABLE - at least one floor has no measurement "
            "behind it. Absence of proof is not a pass (I-7)."
        )
    elif report.outcome is Outcome.FAIL:
        lines.append("[XX] replay-metrics: FAIL - a measured value is below its committed floor.")
    else:
        lines.append("[OK] replay-metrics: every measured value is at or above its floor.")
    return lines


def run(*, as_json: bool = False, check: bool = False, out: Path | None = None) -> int:
    report = evaluate()
    if as_json:
        print(report.canonical_json())
    else:
        for line in _format(report):
            print(line)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.canonical_json(), encoding="utf-8")
    return report.exit_code if check else EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-replay-metrics")
    parser.add_argument("--json", action="store_true", help="Emit the canonical JSON report.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 pass / 1 below floor / 2 unavailable.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Persist the canonical report.")
    args = parser.parse_args(argv)
    return run(as_json=args.json, check=args.check, out=args.out)


if __name__ == "__main__":
    sys.exit(main())
