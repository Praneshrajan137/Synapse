"""Check freeze W against itself: python docs/truth/sealed/check_freeze_w.py

Standard library only, so anyone can run it anywhere. Freeze W (PREREG-1 section 5, truth session
5) fixes the kernel, the release world, the incumbent and the numbers derived from them before any
challenger runs on that world. This script refuses on any disagreement:

1. every file listed in ``SHA256SUMS-W`` exists and has the digest recorded there, read as git
   stores it (CRLF read as LF, so a Windows checkout gives the same digest as ``git show
   <rev>:<path> | sha256sum``): an edit to a frozen file fails here, a new file does not;
2. each item PREREG-1 section 5 lists is ticked against the frozen files themselves: what
   ``freeze-w.json`` states must be what the world, the fit report, the incumbent's tables and
   its report hold, and ``M_c`` must follow from ``D_c`` and ``p_c`` by the sealed rule.

Exit 0 when everything agrees, 1 otherwise. A later change to a frozen choice is a deviation
(``DEVIATIONS.md``, PREREG-1 section 11), and the confirmatory run is then reported on both worlds.
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
#: PREREG-1 section 2: M_c is 1% of expected demand at the primary lost-sale weight.
MARGIN_SHARE = 0.01
LOST_SALE_WEIGHT = 0.38
CELLS = ("N", "L", "S1", "S2", "S3")
SHOCKS = ("S1", "S2", "S3")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def check_sums(failures: list[str]) -> list[str]:
    listed = []
    for line in (HERE / "SHA256SUMS-W").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        recorded, name = line.split(maxsplit=1)
        name = name.lstrip("*").strip()
        listed.append(name)
        path = ROOT / name
        if not path.is_file():
            failures.append(f"{name}: frozen file is missing")
        elif canonical_sha256(path) != recorded:
            failures.append(f"{name}: sha256 {canonical_sha256(path)} is not freeze W's {recorded}")
    return listed


def tick(failures: list[str], ok: bool, item: str, detail: str) -> None:
    print(("OK   " if ok else "FAIL ") + f"{item}: {detail}")
    if not ok:
        failures.append(item)


def main() -> int:
    failures: list[str] = []
    listed = check_sums(failures)
    for text in failures:
        print(f"FAIL {text}")
    verdict = "OK" if not failures else "FAIL"
    print(f"{verdict} {len(listed)} frozen files hashed against SHA256SUMS-W")
    try:
        return tick_items(failures, listed)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # A missing or malformed frozen file stops the ticks; it is a failure, never a pass.
        print(f"FAIL the items could not be read: {type(exc).__name__}: {exc}")
        return 1


def tick_items(failures: list[str], listed: list[str]) -> int:
    """Tick each PREREG-1 section 5 item against the frozen files; return the exit code."""
    freeze = json.loads((HERE / "freeze-w.json").read_text(encoding="utf-8"))
    files = freeze["files"]
    missing = [rel for rel in files.values() if isinstance(rel, str) and rel not in listed]
    tick(failures, not missing, "every file freeze-w.json names is in SHA256SUMS-W", str(missing))

    kernel = [name for name in listed if name.startswith("synapse_kernel/")]
    tick(
        failures,
        len(kernel) == freeze["kernel"]["files"] and "synapse_kernel/release/engine.py" in kernel,
        "the kernel",
        f"{len(kernel)} files under synapse_kernel/ (stated {freeze['kernel']['files']})",
    )

    world = _load(files["world"])
    items = world["items"]
    provenance = world["provenance"]
    bad = [
        key
        for key in freeze["world"]["required_provenance"]
        if key not in provenance
        or provenance[key]["kind"] not in {"fitted", "cited", "chosen"}
        or not provenance[key]["source"].strip()
    ]
    item = "every declared parameter, with its provenance"
    tick(failures, not bad, item, f"missing or empty: {bad}")
    names = [item["name"] for item in items]
    tick(
        failures,
        len(items) == freeze["world"]["items"] and len(set(names)) == len(names),
        "the item set",
        f"{len(items)} items, names unique",
    )
    suppliers = {s["name"]: s for s in world["suppliers"]}
    stated = freeze["world"]["suppliers"]
    same = {
        name: {"delivery_hours": s["delivery_hours"], "lead_time_hours": s["lead_time_hours"]}
        for name, s in suppliers.items()
    } == stated
    tick(
        failures,
        same and all(item["supplier"] in suppliers for item in items),
        "suppliers and their items, lead times, the delivery schedule",
        json.dumps(stated, sort_keys=True),
    )
    lives = sorted({item["shelf_life_hours"] for item in items})
    tick(
        failures,
        lives == freeze["world"]["shelf_life_hours"] and min(lives) >= 12,
        "shelf lives",
        f"{lives} hours (calibrated by {freeze['calibration']['scale']!r})",
    )
    tick(
        failures,
        all(item["price"] == 1 for item in items),
        "prices",
        "every item's price is 1 (ADR-062)",
    )
    tick(
        failures,
        "synapse_kernel/release/engine.py" in listed and bool(freeze["world"]["initial_state"]),
        "the initial state",
        freeze["world"]["initial_state"],
    )

    fit = _load(files["fit_report"])
    masking = fit["masking_check"]
    recovery = freeze["demand_recovery"]
    tick(
        failures,
        masking["used"] == recovery["method"]
        and masking["label"] == recovery["masking_label"]
        and masking["passes"] is recovery["masking_passes"]
        and files["fit_script"] in listed,
        "the method that recovers stock-out-hidden demand, with its masking check",
        f"{masking['used']}, masking check {masking['label']}",
    )

    tables = _load(files["incumbent_tables"])
    report = _load(files["incumbent_report"])
    incumbent = freeze["incumbent"]
    counts = {name: version["replicate_evaluations"] for name, version in tables.items()}
    shapes_ok = all(
        len(v["factors"]) == len(items) and all(len(row) == 6 for row in v["factors"])
        for v in tables.values()
    )
    selected = {cell: report["selection"][cell]["selected"] for cell in CELLS}
    tick(
        failures,
        counts == incumbent["replicate_evaluations"]
        and shapes_ok
        and selected == incumbent["selected"]
        and report["contest_incumbent"] == incumbent["contest"],
        "the incumbent's tuned tables, evaluation counts and selection",
        f"selected {selected}, contest {report['contest_incumbent']}",
    )

    derived = {
        cell: MARGIN_SHARE * report["D_c"][cell] * LOST_SALE_WEIGHT * report["p_c"][cell]
        for cell in CELLS
    }
    tick(
        failures,
        report["D_c"] == freeze["D_c"]
        and report["p_c"] == freeze["p_c"]
        and report["M_c"] == freeze["M_c"]
        and all(math.isclose(derived[c], freeze["M_c"][c], rel_tol=1e-12) for c in CELLS),
        "D_c, p_c and M_c per cell",
        "M_c = 0.01 * D_c * 0.38 * p_c holds in every cell",
    )

    head = report["headroom"]
    stated_head = freeze["headroom"]
    same_head = all(
        head[cell][variant][field] == value
        for cell in SHOCKS
        for variant, fields in stated_head[cell].items()
        for field, value in fields.items()
    ) and all("difference_in_differences" in stated_head[cell]["gate_unguarded"] for cell in SHOCKS)
    tick(
        failures,
        same_head,
        "the shock headroom of section 6",
        "per shock cell: the gate's oracle and the informed variant, each with its DiD against N",
    )

    print("OK freeze W holds" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
