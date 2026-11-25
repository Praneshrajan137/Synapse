"""Check deviation 1 against itself: python docs/truth/sealed/check_deviation_1.py

Standard library only, so anyone can run it anywhere. Deviation 1 (truth session 6, decision
S6-D-03; ``DEVIATION-1.md``) adds a second release world, W-d1, calibrated by the other reading of
the session-5 gate's rule, beside freeze W's world, which stays primary. This script refuses on any
disagreement:

1. every file listed in ``SHA256SUMS-D1`` has the digest recorded there, read as git stores it, and
   the list includes ``SHA256SUMS-W`` itself, so this deviation is chained to freeze W;
2. the calibration is the reading it states: its first two steps are freeze W's own, number for
   number; every later scale follows from the shares by the log bisection toward 5.46% in [0.5, 2]
   (recomputed here); and the chosen scale is the step whose share is closest to 5.46%;
3. W-d1 is the uncalibrated world with every shelf life times that scale, rounded to whole hours, at
   least 12, nothing else changed; and the same uncalibrated world times ``sqrt(0.5)`` is freeze W's
   world, so both worlds come from one fit;
4. the incumbent's tables, counts and selection, ``D_c``, ``p_c`` and ``M_c`` (``M_c = 0.01 D_c 0.38
   p_c``) and the headroom are what ``deviation-1.json`` states.

Exit 0 when everything agrees, 1 otherwise.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CELLS = ("N", "L", "S1", "S2", "S3")
SHOCKS = ("S1", "S2", "S3")
TARGET = 0.0546
BRACKET = (0.5, 2.0)


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def tick(failures: list[str], ok: bool, item: str, detail: str) -> None:
    print(("OK   " if ok else "FAIL ") + f"{item}: {detail}")
    if not ok:
        failures.append(item)


def check_sums(failures: list[str]) -> list[str]:
    listed = []
    for line in (HERE / "SHA256SUMS-D1").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        recorded, name = line.split(maxsplit=1)
        name = name.lstrip("*").strip()
        listed.append(name)
        path = ROOT / name
        if not path.is_file():
            failures.append(f"{name}: listed file is missing")
        elif canonical_sha256(path) != recorded:
            failures.append(
                f"{name}: sha256 {canonical_sha256(path)} is not deviation 1's {recorded}"
            )
    return listed


def bisection(shares: list[float], steps: int) -> list[float]:
    """The scales the log bisection toward TARGET visits, given the share measured at each."""
    scale, lo, hi = 1.0, None, None
    out = [scale]
    for share in shares[:steps]:
        if share > TARGET:
            lo, hi = scale, (hi if hi is not None else BRACKET[1])
        else:
            hi, lo = scale, (lo if lo is not None else BRACKET[0])
        scale = math.sqrt(lo * hi)
        out.append(scale)
    return out


def scaled_lives(world: dict[str, Any], scale: float) -> list[int]:
    return [max(12, round(item["shelf_life_hours"] * scale)) for item in world["items"]]


def same_but_lives(a: dict[str, Any], b: dict[str, Any], lives: list[int]) -> bool:
    """Whether ``b`` is ``a`` with these shelf lives, its name and provenance aside."""
    if len(a["items"]) != len(b["items"]) or len(lives) != len(a["items"]):
        return False
    for item_a, item_b, life in zip(a["items"], b["items"], lives, strict=True):
        if item_b["shelf_life_hours"] != life:
            return False
        if {k: v for k, v in item_a.items() if k != "shelf_life_hours"} != {
            k: v for k, v in item_b.items() if k != "shelf_life_hours"
        }:
            return False
    keys = set(a) | set(b)
    return all(a.get(k) == b.get(k) for k in keys - {"items", "name", "provenance"})


def tick_items(failures: list[str], listed: list[str]) -> int:
    statement = json.loads((HERE / "deviation-1.json").read_text(encoding="utf-8"))
    files = statement["files"]
    missing = [rel for rel in files.values() if rel not in listed]
    tick(
        failures, not missing, "every file deviation-1.json names is in SHA256SUMS-D1", str(missing)
    )
    chain = canonical_sha256(HERE / "SHA256SUMS-W")
    tick(
        failures,
        "docs/truth/sealed/SHA256SUMS-W" in listed and chain == statement["freeze_w_sums_sha256"],
        "chained to freeze W",
        f"SHA256SUMS-W {chain[:16]}... is listed and stated",
    )

    calibration = statement["calibration"]
    steps = calibration["steps"]
    freeze_w = json.loads((HERE / "freeze-w.json").read_text(encoding="utf-8"))
    first_two = [{k: s[k] for k in ("scale", "better", "waste_share")} for s in steps[:2]]
    tick(
        failures,
        first_two == freeze_w["calibration"]["steps"],
        "steps 0 and 1 are freeze W's own",
        f"{[round(s['waste_share'], 5) for s in first_two]}",
    )
    visited = bisection([s["waste_share"] for s in steps], calibration["steps_after_scale_1"])
    tick(
        failures,
        [s["scale"] for s in steps] == visited
        and len(steps) == calibration["steps_after_scale_1"] + 1,
        "every scale follows from the shares by the log bisection toward 5.46%",
        f"{len(steps)} scales, from 1 to {visited[-1]!r}",
    )
    closest = min(steps, key=lambda s: (abs(s["waste_share"] - TARGET), -s["scale"]))
    tick(
        failures,
        closest["scale"] == calibration["scale"]
        and calibration["target_reachable"] == any(s["waste_share"] >= TARGET for s in steps),
        "the chosen scale is the step closest to 5.46%",
        f"{calibration['scale']!r}, share {closest['waste_share']:.4%}",
    )

    uncalibrated = _load(files["uncalibrated_world"])
    world = _load(files["world"])
    frozen_world = _load("synapse_kernel/worlds/release_world.json")
    lives = scaled_lives(uncalibrated, calibration["scale"])
    tick(
        failures,
        same_but_lives(uncalibrated, world, lives)
        and sorted(set(lives)) == statement["world"]["shelf_life_hours"],
        "W-d1 is the uncalibrated world with its shelf lives scaled, nothing else changed",
        f"shelf lives {sorted(set(lives))} hours",
    )
    tick(
        failures,
        same_but_lives(uncalibrated, frozen_world, scaled_lives(uncalibrated, math.sqrt(0.5))),
        "the same uncalibrated world scaled by sqrt(0.5) is freeze W's world",
        "both worlds come from one fit",
    )

    tables = _load(files["incumbent_tables"])
    report = _load(files["incumbent_report"])
    incumbent = statement["incumbent"]
    counts = {name: version["replicate_evaluations"] for name, version in tables.items()}
    shapes = all(
        len(v["factors"]) == len(world["items"]) and all(len(row) == 6 for row in v["factors"])
        for v in tables.values()
    )
    selected = {cell: report["selection"][cell]["selected"] for cell in CELLS}
    tick(
        failures,
        counts == incumbent["replicate_evaluations"]
        and shapes
        and selected == incumbent["selected"]
        and report["contest_incumbent"] == incumbent["contest"]
        and report["deviation_1"]["scale"] == calibration["scale"],
        "the incumbent's tuned tables, evaluation counts and selection on W-d1",
        f"selected {selected}, contest {report['contest_incumbent']}",
    )
    derived = {c: 0.01 * report["D_c"][c] * 0.38 * report["p_c"][c] for c in CELLS}
    tick(
        failures,
        report["D_c"] == statement["D_c"]
        and report["p_c"] == statement["p_c"]
        and report["M_c"] == statement["M_c"]
        and all(math.isclose(derived[c], statement["M_c"][c], rel_tol=1e-12) for c in CELLS),
        "D_c, p_c and M_c per cell on W-d1",
        "M_c = 0.01 * D_c * 0.38 * p_c holds in every cell",
    )
    same_head = all(
        report["headroom"][cell][variant][field] == value
        for cell in SHOCKS
        for variant, fields in statement["headroom"][cell].items()
        for field, value in fields.items()
    )
    tick(failures, same_head, "the shock headroom on W-d1", "as the report gives it")
    print("OK deviation 1 holds" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


def main() -> int:
    failures: list[str] = []
    listed = check_sums(failures)
    for text in failures:
        print(f"FAIL {text}")
    print(f"{'OK' if not failures else 'FAIL'} {len(listed)} files hashed against SHA256SUMS-D1")
    try:
        return tick_items(failures, listed)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL the items could not be read: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
