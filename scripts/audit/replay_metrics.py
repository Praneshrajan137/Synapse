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

**Declared unmeasurable in CI.** A floor may carry an ``unmeasurable_in_ci`` block in the
committed configuration -- ``declared: true`` plus a ``prerequisite``, a ``blocked_on`` and
a ``procedure``, the same shape ``dataset-licences.yaml`` uses for terms behind an
acceptance gate (C74). Then an absent measurement reports ``declared-unmeasurable``: still
not a pass in the record, but not a failure of the step either, so a step can gate on the
floors it CAN measure. Three things keep that from being a mute button:

* **the declaration must be well formed.** A missing prerequisite, reason or procedure --
  or an unrecognised key -- declares nothing, and the floor stays ``unavailable`` at exit 2;
* **the declaration is falsifiable.** It names the prerequisite whose presence voids it. If
  the measurement is ever obtainable it is taken, the declaration is reported ``void``, and
  the gate FAILS until the block is deleted -- whichever side of the floor the measurement
  fell on, because a flag that can disagree with its own subject is a claim rather than
  evidence;
* **it silences nothing else.** A measured breach on any floor still fails, and an
  undeclared absence on any floor still exits 2.

It lives in the configuration rather than behind a CLI flag on purpose: a flag would let
any caller silence any floor from any workflow line, with no record of who did it or why.
**No floor value is ever changed by a declaration** (R2.10), and the step is never made
``continue-on-error`` (finding 35).

Outcome mapping::

    any metric measured and below its floor   -> exit 1  (fail; measured + floor printed)
    any declaration voided by a measurement   -> exit 1  (fail; the declaration is false)
    else any metric unavailable, undeclared   -> exit 2  (unavailable; never a pass)
    else any metric declared unmeasurable     -> exit 0  (skip; not a pass, not a failure)
    else every metric at-or-above its floor   -> exit 0  (pass)

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
from typing import Any, Final

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
    """Metric outcome. Only ``PASS`` is a pass (I-7).

    ``DECLARED_UNMEASURABLE`` is the fourth state and the only one that is neither a
    measurement nor a bare absence: the floor has no measurement AND the committed
    configuration declares why, names the prerequisite that would void the declaration, and
    records the procedure to obtain the number. It maps to exit ``0`` so a step can gate on
    the floors it CAN measure, and it is reported as its own state so no reader can mistake
    it for a pass -- a SKIP is not a PASS, in the record as well as in the exit code.
    """

    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    DECLARED_UNMEASURABLE = "declared-unmeasurable"


#: Metric outcomes that do not, on their own, stop the gate exiting ``0``. Written as the
#: set of ALLOWED states rather than as "not FAIL and not UNAVAILABLE", so a fifth outcome
#: added later is non-passing until somebody deliberately says otherwise (fail-closed).
_NON_BLOCKING_OUTCOMES: Final[frozenset[Outcome]] = frozenset(
    {Outcome.PASS, Outcome.DECLARED_UNMEASURABLE}
)


class Declaration(str, Enum):
    """Whether a floor carries a usable unmeasurable-in-CI declaration.

    Kept separate from :class:`Outcome` on purpose. The floor and its declaration are two
    different subjects, and folding them into one value would make "the floor is satisfied"
    and "the declaration is still true" indistinguishable in the report -- which is the
    exact conflation this gate exists to refuse elsewhere.
    """

    #: No declaration. An absent measurement is ``UNAVAILABLE`` exactly as before.
    ABSENT = "absent"
    #: A declaration missing its prerequisite, reason or procedure declares nothing.
    #: Fail-closed: the metric stays ``UNAVAILABLE`` and the gate still exits 2.
    MALFORMED = "malformed"
    #: Declared, and no measurement was obtainable -- the declaration bears out.
    HONOURED = "honoured"
    #: Declared, and a measurement WAS obtained. The declaration is false and the gate
    #: fails until it is deleted, whatever the measured value was. A declaration that
    #: cannot go stale would be a permanent mute button rather than a recorded absence.
    VOID = "void"


#: Keys a declaration must carry to declare anything at all. ``blocked_on`` and
#: ``procedure`` mirror C74's ``confirmation`` block; ``prerequisite`` is what makes the
#: declaration falsifiable rather than merely stated.
DECLARATION_KEYS: Final[tuple[str, ...]] = ("prerequisite", "blocked_on", "procedure")

#: Where a floor's declaration lives, under that floor's entry.
DECLARATION_FIELD: Final[str] = "unmeasurable_in_ci"


class DeclarationRecord(BaseModel):
    """The committed unmeasurable-in-CI declaration for one floor, as read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prerequisite: str
    blocked_on: str
    procedure: str


class MetricReport(BaseModel):
    """One measured (or unmeasurable) replay metric against its committed floor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric: str
    floor: float | None = None
    measured: float | None = None
    direction: str | None = None
    outcome: Outcome
    declaration: Declaration = Declaration.ABSENT
    detail: str

    @property
    def passing(self) -> bool:
        """Whether this metric lets the gate exit ``0``. Never true for ``UNAVAILABLE``."""
        return self.outcome in _NON_BLOCKING_OUTCOMES and self.declaration is not (
            Declaration.VOID
        )


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


def read_declaration(
    config: dict[str, Any], metric: str
) -> tuple[DeclarationRecord | None, bool]:
    """``(record, present)`` for *metric*'s unmeasurable-in-CI declaration.

    ``present`` says a declaration was attempted; ``record`` is ``None`` when it declares
    nothing usable. The two are distinguished so a MALFORMED declaration is reported as a
    malformation the operator can fix, rather than silently reading as an absence.

    Fail-closed on every path: a non-mapping block, ``declared`` other than ``True``, a
    missing key, a non-string, a blank string, or an unrecognised extra key all decline to
    declare. A declaration that cannot state its prerequisite, its reason and its procedure
    is a mute button, and a mute button is what R2.10 and finding 35 forbid.
    """
    floors = config.get("floors")
    if not isinstance(floors, dict):
        return None, False
    entry = floors.get(metric)
    if not isinstance(entry, dict):
        return None, False
    block = entry.get(DECLARATION_FIELD)
    if block is None:
        return None, False
    if not isinstance(block, dict) or block.get("declared") is not True:
        return None, True
    values: dict[str, str] = {}
    for key in DECLARATION_KEYS:
        text = block.get(key)
        if not isinstance(text, str) or not text.strip():
            return None, True
        values[key] = " ".join(text.split())
    if set(block) - {"declared", *DECLARATION_KEYS}:
        return None, True
    return DeclarationRecord(**values), True


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
    metric: str,
    floor: float,
    direction: str,
    measured: float,
    detail: str,
    *,
    declaration: DeclarationRecord | None = None,
    declared: bool = False,
) -> MetricReport:
    """Judge a metric that WAS measured, and void any declaration that a measurement voids.

    Reaching here at all falsifies a well-formed unmeasurable-in-CI declaration, so it is
    reported ``VOID`` regardless of which side of the floor the measurement fell on. That is
    C74's rule in the other direction: a flag that can disagree with its own subject is a
    claim rather than evidence, so the disagreement is itself the finding. The floor's own
    verdict is left intact - the two subjects stay separate in the report.

    A block that declares nothing is reported ``MALFORMED`` here too, even though a measured
    floor silenced nothing: present-and-unusable is a defect an operator should see, and
    dropping it to ``ABSENT`` would hide the junk until the day it mattered.
    """
    below = measured < floor
    outcome = Outcome.FAIL if below else Outcome.PASS
    if declaration is not None:
        return MetricReport(
            metric=metric,
            floor=floor,
            measured=measured,
            direction=direction,
            outcome=outcome,
            declaration=Declaration.VOID,
            detail=(
                f"{detail}; the `{DECLARATION_FIELD}` declaration is VOID -- its prerequisite "
                f"({declaration.prerequisite}) is satisfied, so the measurement was taken. "
                "Delete the declaration in the commit that records this run."
            ),
        )
    if declared:
        return MetricReport(
            metric=metric,
            floor=floor,
            measured=measured,
            direction=direction,
            outcome=outcome,
            declaration=Declaration.MALFORMED,
            detail=(
                f"{detail}; a `{DECLARATION_FIELD}` block is present but declares nothing. "
                "It silenced nothing here because the floor was measured -- delete it, or "
                f"complete it with `declared: true` plus {', '.join(DECLARATION_KEYS)}."
            ),
        )
    return MetricReport(
        metric=metric,
        floor=floor,
        measured=measured,
        direction=direction,
        outcome=outcome,
        detail=detail,
    )


def _unavailable_metric(
    metric: str,
    floor: float | None,
    detail: str,
    *,
    declaration: DeclarationRecord | None = None,
    declared: bool = False,
) -> MetricReport:
    """A metric with no measurement: declared and non-failing, or absent and exit 2."""
    if declaration is not None:
        return MetricReport(
            metric=metric,
            floor=floor,
            measured=None,
            direction=None,
            outcome=Outcome.DECLARED_UNMEASURABLE,
            declaration=Declaration.HONOURED,
            detail=(
                f"{detail}; declared unmeasurable in CI -- blocked on "
                f"{declaration.blocked_on} Voided by: {declaration.prerequisite}"
            ),
        )
    if declared:
        return MetricReport(
            metric=metric,
            floor=floor,
            measured=None,
            direction=None,
            outcome=Outcome.UNAVAILABLE,
            declaration=Declaration.MALFORMED,
            detail=(
                f"{detail}; a `{DECLARATION_FIELD}` block is present but declares nothing: "
                f"it needs `declared: true` plus non-empty {', '.join(DECLARATION_KEYS)} "
                "and no other key. Until it does, this floor is simply unmeasured."
            ),
        )
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

    A measured breach outranks everything, so an unrelated absent measurement can never mask
    a real floor regression. **A VOID declaration ranks with a breach**, because the only
    thing that makes a declared skip safe is that the declaration is true: one a measurement
    has falsified must stop the build rather than quietly persist. An undeclared
    unavailability outranks a pass, so absence of proof is never a pass (I-7). A DECLARED
    unavailability is the fourth state - non-passing in the record, non-blocking in the exit
    code - and it ranks below a bare absence so a mixed report reports the worse of the two.
    An empty metric set is unavailable.
    """
    if any(metric.outcome is Outcome.FAIL for metric in metrics) or any(
        metric.declaration is Declaration.VOID for metric in metrics
    ):
        return Outcome.FAIL
    if not metrics or any(metric.outcome is Outcome.UNAVAILABLE for metric in metrics):
        return Outcome.UNAVAILABLE
    if any(metric.outcome is Outcome.DECLARED_UNMEASURABLE for metric in metrics):
        return Outcome.DECLARED_UNMEASURABLE
    return Outcome.PASS


def exit_code_for(outcome: Outcome) -> int:
    """The process exit code each outcome maps to. ``2`` is non-passing (I-7).

    ``DECLARED_UNMEASURABLE`` maps to ``0``, so a step can gate on the floors it can measure
    while an undeclared absence still exits ``2``. That is the whole of disposition (b), and
    the honesty it rests on is carried by :class:`Declaration`: the exit code is ``0`` only
    while every unmeasured floor's declaration is well-formed AND unfalsified.
    """
    return {
        Outcome.PASS: EXIT_PASS,
        Outcome.FAIL: EXIT_FAIL,
        Outcome.UNAVAILABLE: EXIT_UNAVAILABLE,
        Outcome.DECLARED_UNMEASURABLE: EXIT_PASS,
    }[outcome]


def evaluate(
    floors_file: Path | None = None,
    *,
    root: Path = ROOT,
    measurers: Mapping[str, Measurer] | None = None,
) -> ReplayReport:
    """Measure both replay metrics and return the four-state verdict.

    A measured breach (``fail``) outranks an unavailability so an absent measurement
    can never mask a real floor regression. A floor with no measurement is ``unavailable``
    unless the committed configuration declares it unmeasurable in CI, in which case it is
    ``declared-unmeasurable`` - and that declaration is voided, failing the gate, the moment
    a measurement proves it wrong.
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
    declarations: dict[str, DeclarationRecord | None] = {}
    declared: dict[str, bool] = {}
    for metric in METRIC_ORDER:
        declarations[metric], declared[metric] = read_declaration(config, metric)
        try:
            floor, direction = read_floor(config, metric, floors_file=floors_file, root=root)
        except _Unavailable as exc:
            floors[metric], directions[metric], floor_errors[metric] = None, None, exc.detail
        else:
            floors[metric], directions[metric] = floor, direction

    def absent(metric: str, detail: str) -> MetricReport:
        """An unmeasured metric, with its declaration (if any) applied."""
        return _unavailable_metric(
            metric,
            floors[metric],
            detail,
            declaration=declarations[metric],
            declared=declared[metric],
        )

    try:
        traces_dir, expected, found, seed = resolve_traces(
            config, floors_file=floors_file, root=root
        )
    except _Unavailable as exc:
        metrics = tuple(
            absent(metric, floor_errors.get(metric, exc.detail)) for metric in METRIC_ORDER
        )
        return _report(
            floors_file, None, None, None, None, metrics, aggregate(metrics), exc.detail,
            root=root,
        )

    # The tier-routing replay runs first; the KV-cache gauge is read after it so any
    # cache observation the replay produced is already recorded.
    measured: dict[str, MetricReport] = {}
    active = dict(default_measurers()) if measurers is None else dict(measurers)
    for metric in (TIER_ROUTING_METRIC, KV_CACHE_METRIC):
        metric_floor, metric_direction = floors[metric], directions[metric]
        if metric_floor is None or metric_direction is None:
            # An unreadable floor is not an unmeasurable one: there is no floor to declare
            # anything about, so no declaration can apply and the gate stays at exit 2.
            measured[metric] = _unavailable_metric(metric, metric_floor, floor_errors[metric])
            continue
        measurer = active.get(metric)
        if measurer is None:
            measured[metric] = absent(metric, f"no measurer available for `{metric}`")
            continue
        try:
            value, detail = measurer()
        except _Unavailable as exc:
            measured[metric] = absent(metric, exc.detail)
        else:
            measured[metric] = _judge(
                metric,
                metric_floor,
                metric_direction,
                value,
                detail,
                declaration=declarations[metric],
                declared=declared[metric],
            )

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


_MARKER = {
    Outcome.PASS: "[OK]",
    Outcome.FAIL: "[XX]",
    Outcome.UNAVAILABLE: "[??]",
    Outcome.DECLARED_UNMEASURABLE: "[SKIP]",
}


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
            state = (
                "DECLARED UNMEASURABLE"
                if metric.outcome is Outcome.DECLARED_UNMEASURABLE
                else "UNAVAILABLE"
            )
            lines.append(
                f"{marker} {metric.metric}: measured {state}, floor {floor} "
                f"-- {metric.detail}"
            )
        else:
            relation = ">=" if metric.measured >= (metric.floor or 0.0) else "<"
            lines.append(
                f"{marker} {metric.metric}: measured {metric.measured:.4f} {relation} "
                f"floor {floor} ({metric.detail})"
            )
    for metric in report.metrics:
        if metric.declaration is Declaration.VOID:
            lines.append(
                f"[XX] {metric.metric}: its `{DECLARATION_FIELD}` declaration is VOID -- the "
                "floor was measured, so the declaration is false. Delete it."
            )
        elif metric.declaration is Declaration.MALFORMED:
            lines.append(
                f"[??] {metric.metric}: its `{DECLARATION_FIELD}` block declares nothing, so "
                "the floor is unmeasured rather than declared unmeasurable."
            )
    if report.outcome is Outcome.UNAVAILABLE:
        lines.append(
            "[??] replay-metrics: UNAVAILABLE - at least one floor has no measurement "
            "behind it and none is declared. Absence of proof is not a pass (I-7)."
        )
    elif report.outcome is Outcome.FAIL:
        lines.append(
            "[XX] replay-metrics: FAIL - a measured value is below its committed floor, "
            "or a declared-unmeasurable floor turned out to be measurable."
        )
    elif report.outcome is Outcome.DECLARED_UNMEASURABLE:
        lines.append(
            "[SKIP] replay-metrics: every MEASURED value is at or above its floor; at least "
            "one floor is declared unmeasurable in CI with its reason and procedure. A SKIP "
            "is not a PASS (I-7) - it does not fail the step, and it is not a measurement."
        )
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
