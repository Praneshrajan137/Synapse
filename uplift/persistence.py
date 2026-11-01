"""
SYNAPSE Decision-Integrity Uplift Proof — recorded-run persistence.

Persists every recorded run — each carrying its arm identifier, scenario seed, and
derived :class:`~uplift.interfaces.KpiVector` — to a durable JSON file, and reloads it
back into the exact same :class:`~uplift.interfaces.ScenarioRun` objects (R2.6). The
harness (task 7.2) records one ``ScenarioRun`` per completed *(arm, seed)* run (and a
failed marker per failed run); this module is where those records are written and read.

The round-trip is *lossless* (Property 8): ``load_runs(save_runs(runs, path), path)``
yields the identical set of records with each vector's arm id and seed preserved. Floats
survive intact because Python's ``json`` encoder emits the shortest round-tripping
decimal representation (``repr``) for every ``float`` and decodes it back to the same
IEEE-754 value; non-finite KPI values (``nan``/``inf``) are preserved via the JSON
``NaN``/``Infinity`` tokens.

Schema (a single JSON object so the file is self-describing and forward-compatible)::

    {
      "version": 3,
      "runs": [
        {
          "arm": "<arm id>",
          "seed": <int>,
          "failed": <bool>,
          "error": <str | null>,
          "kpis": {                       # null for a failed run
            "fill_rate": <float>,
            "spoilage_rate": <float>,
            "stockout_rate": <float>,
            "avg_delivery_time_min": <float>,
            "margin": <float>,
            "co2_estimate": <float>,
            "avg_on_hand_units": <float>,
            "objective": <float>
          },
          "decision_counts": {            # null when the arm keeps no tally or the run failed
            "dispatched": <int>,
            "withheld_for_confidence": <int>,
            "guardrail_blocked": <int>,
            "untranslatable": <int>
          }
        },
        ...
      ]
    }

**Version 2 (decision-quality-proof task 29.4).** :class:`~uplift.interfaces.KpiVector` gained
two REQUIRED fields, ``avg_on_hand_units`` and ``objective``, so a version-1 file cannot carry a
complete vector. It is refused by the version check below rather than read with those two
values invented: an objective defaulted to ``0.0`` would be the best cost there is.

**Version 3 (decision-quality-proof session 12, R7.20).** Every run carries
``decision_counts``: the run's :class:`~uplift.interfaces.DecisionCounts`, or ``null``. The key
is REQUIRED, ``null`` included, because a version-2 file cannot say whether its consensus arm
kept a tally; reading one as "kept none" would turn an absent record into a stated zero, so a
version-2 file is refused by the version check, never migrated. A tally must name exactly the
four counts, each a non-negative ``int``; a failed run carrying one is refused, because
:class:`~uplift.interfaces.ScenarioRun` refuses it.
"""
from __future__ import annotations

import dataclasses
import json
import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from uplift.interfaces import DecisionCounts, KpiVector, ScenarioRun

# The on-disk schema version. Bump only on an incompatible layout change so an older
# reader can refuse a newer file rather than silently misinterpret it. Version 2: the
# KpiVector gained `avg_on_hand_units` and `objective` (task 29.4), both required. Version 3:
# every run carries `decision_counts` (session 12, R7.20), required and possibly null.
SCHEMA_VERSION: int = 3

# The KpiVector field names, in declaration order, derived from the dataclass itself so
# this module stays in lock-step with the interface if a KPI is ever added/removed.
_KPI_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(KpiVector))

# The DecisionCounts field names, derived the same way and for the same reason.
_DECISION_COUNT_FIELDS: tuple[str, ...] = tuple(
    f.name for f in dataclasses.fields(DecisionCounts)
)


class PersistenceError(ValueError):
    """Raised when a run-record file is missing required structure or is malformed."""


def _kpis_to_json(kpis: KpiVector | None) -> dict[str, float] | None:
    """Serialize a ``KpiVector`` to a plain ``{field: float}`` mapping (or ``None``)."""
    if kpis is None:
        return None
    return {name: float(getattr(kpis, name)) for name in _KPI_FIELDS}


def _kpis_from_json(raw: object) -> KpiVector | None:
    """Rebuild a ``KpiVector`` from its JSON mapping, tolerating ``None`` (failed run)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PersistenceError(f"'kpis' must be an object or null, got {type(raw).__name__}")
    missing = [name for name in _KPI_FIELDS if name not in raw]
    if missing:
        raise PersistenceError(f"'kpis' object missing required field(s): {', '.join(missing)}")
    return KpiVector(**{name: float(raw[name]) for name in _KPI_FIELDS})


def _counts_to_json(counts: DecisionCounts | None) -> dict[str, int] | None:
    """Serialize a ``DecisionCounts`` to a plain ``{count: int}`` mapping (or ``None``)."""
    if counts is None:
        return None
    return {name: int(getattr(counts, name)) for name in _DECISION_COUNT_FIELDS}


def _counts_from_json(raw: object, index: int) -> DecisionCounts | None:
    """Rebuild a run's ``DecisionCounts``, or ``None``; refuse anything but the four counts."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PersistenceError(
            f"run[{index}] 'decision_counts' must be an object or null, got {type(raw).__name__}"
        )
    missing = [name for name in _DECISION_COUNT_FIELDS if name not in raw]
    unknown = sorted(str(key) for key in raw if key not in _DECISION_COUNT_FIELDS)
    if missing or unknown:
        raise PersistenceError(
            f"run[{index}] 'decision_counts' must name exactly {list(_DECISION_COUNT_FIELDS)}: "
            f"missing {missing}, unknown {unknown}"
        )
    counts: dict[str, int] = {}
    for name in _DECISION_COUNT_FIELDS:
        value = raw[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise PersistenceError(
                f"run[{index}] 'decision_counts.{name}' is {value!r}, not an integer count"
            )
        counts[name] = value
    try:
        return DecisionCounts(**counts)
    except ValueError as exc:
        raise PersistenceError(f"run[{index}] 'decision_counts' is inadmissible: {exc}") from exc


def _run_to_json(run: ScenarioRun) -> dict[str, object]:
    """Serialize one ``ScenarioRun`` (arm, seed, KpiVector, failed/error, tally) to JSON."""
    return {
        "arm": str(run.arm),
        "seed": int(run.seed),
        "failed": bool(run.failed),
        "error": None if run.error is None else str(run.error),
        "kpis": _kpis_to_json(run.kpis),
        "decision_counts": _counts_to_json(run.decision_counts),
    }


def _run_from_json(raw: object, index: int) -> ScenarioRun:
    """Rebuild one ``ScenarioRun`` from its JSON object, validating required keys.

    The KPI object is read before the tally, so a run that lacks a version-2 KPI field is
    refused naming that field, whatever else it lacks.
    """
    if not isinstance(raw, dict):
        raise PersistenceError(f"run[{index}] must be an object, got {type(raw).__name__}")
    for key in ("arm", "seed"):
        if key not in raw:
            raise PersistenceError(f"run[{index}] missing required key '{key}'")
    error = raw.get("error")
    if error is not None:
        error = str(error)
    kpis = _kpis_from_json(raw.get("kpis"))
    if "decision_counts" not in raw:
        raise PersistenceError(
            f"run[{index}] missing required key 'decision_counts': schema version "
            f"{SCHEMA_VERSION} records it on every run, null when the arm kept no tally"
        )
    counts = _counts_from_json(raw["decision_counts"], index)
    try:
        return ScenarioRun(
            arm=str(raw["arm"]),
            seed=int(raw["seed"]),
            kpis=kpis,
            failed=bool(raw.get("failed", False)),
            error=error,
            decision_counts=counts,
        )
    except ValueError as exc:
        raise PersistenceError(f"run[{index}] is inadmissible: {exc}") from exc


def save_runs(runs: Iterable[ScenarioRun], path: str | os.PathLike[str]) -> Path:
    """Persist every recorded run to ``path`` as JSON, preserving arm id + seed (R2.6).

    Writes atomically (via a temporary sibling file + ``os.replace``) so a crash mid-write
    can never leave a half-written, unreadable results file. Parent directories are
    created as needed. Returns the resolved :class:`~pathlib.Path` that was written.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": SCHEMA_VERSION,
        "runs": [_run_to_json(run) for run in runs],
    }

    tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    # allow_nan=True keeps non-finite KPI values round-trippable via NaN/Infinity tokens.
    text = json.dumps(payload, indent=2, allow_nan=True, sort_keys=False)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)
    return target


def load_runs(path: str | os.PathLike[str]) -> list[ScenarioRun]:
    """Reload the recorded runs previously written by :func:`save_runs` (R2.6).

    Returns the runs in their original order, each rebuilt as an identical
    :class:`~uplift.interfaces.ScenarioRun` with its arm id, seed, ``KpiVector`` and decision
    tally preserved (Property 8). Raises :class:`PersistenceError` on a malformed or
    incompatible file.
    """
    source = Path(path)
    try:
        raw_text = source.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PersistenceError(f"no run-record file at {source}") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PersistenceError(f"{source} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise PersistenceError(f"{source} must contain a JSON object at the top level")

    version = payload.get("version")
    if version != SCHEMA_VERSION:
        raise PersistenceError(
            f"{source} has schema version {version!r}, expected {SCHEMA_VERSION}"
        )

    raw_runs = payload.get("runs")
    if not isinstance(raw_runs, Sequence) or isinstance(raw_runs, (str, bytes)):
        raise PersistenceError(f"{source} 'runs' must be a JSON array")

    return [_run_from_json(item, index) for index, item in enumerate(raw_runs)]
