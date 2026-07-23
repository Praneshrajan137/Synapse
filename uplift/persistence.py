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
      "version": 1,
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
            "co2_estimate": <float>
          }
        },
        ...
      ]
    }
"""
from __future__ import annotations

import dataclasses
import json
import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from uplift.interfaces import KpiVector, ScenarioRun

# The on-disk schema version. Bump only on an incompatible layout change so an older
# reader can refuse a newer file rather than silently misinterpret it.
SCHEMA_VERSION: int = 1

# The KpiVector field names, in declaration order, derived from the dataclass itself so
# this module stays in lock-step with the interface if a KPI is ever added/removed.
_KPI_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(KpiVector))


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


def _run_to_json(run: ScenarioRun) -> dict[str, object]:
    """Serialize one ``ScenarioRun`` (arm + seed + KpiVector + failed/error) to JSON."""
    return {
        "arm": str(run.arm),
        "seed": int(run.seed),
        "failed": bool(run.failed),
        "error": None if run.error is None else str(run.error),
        "kpis": _kpis_to_json(run.kpis),
    }


def _run_from_json(raw: object, index: int) -> ScenarioRun:
    """Rebuild one ``ScenarioRun`` from its JSON object, validating required keys."""
    if not isinstance(raw, dict):
        raise PersistenceError(f"run[{index}] must be an object, got {type(raw).__name__}")
    for key in ("arm", "seed"):
        if key not in raw:
            raise PersistenceError(f"run[{index}] missing required key '{key}'")
    error = raw.get("error")
    if error is not None:
        error = str(error)
    return ScenarioRun(
        arm=str(raw["arm"]),
        seed=int(raw["seed"]),
        kpis=_kpis_from_json(raw.get("kpis")),
        failed=bool(raw.get("failed", False)),
        error=error,
    )


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
    :class:`~uplift.interfaces.ScenarioRun` with its arm id, seed, and ``KpiVector``
    preserved (Property 8). Raises :class:`PersistenceError` on a malformed or
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
