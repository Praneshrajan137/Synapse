"""Write freeze W's ``freeze-w.json`` and ``SHA256SUMS-W`` from the committed tree.

    python -m scripts.truth.make_freeze_w --date YYYY-MM-DD --base <commit>

Run once, from the repository root, on the commit freeze W is taken from (``main`` after the
kernel's pull requests have merged), after ``FREEZE-W.md`` and ``check_freeze_w.py`` are in place;
then run ``python docs/truth/sealed/check_freeze_w.py``. The frozen set is the session-5 gate's
(section 7): every tracked file under ``synapse_kernel/``, the fit and incumbent scripts with their
outputs, and the freeze's own document, JSON and checker. It is not a check: once freeze W is on
``main``, files added beside it (allowed) would change what this writes, and only the checker
judges the freeze.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SEALED = ROOT / "docs" / "truth" / "sealed"
OUTSIDE_KERNEL = [
    "scripts/world/__init__.py",
    "scripts/world/fit_release_world.py",
    "docs/truth/world/fit-report.json",
    "scripts/kernel/tune_incumbent.py",
    "docs/truth/world/incumbent-report.json",
]
OWN = [
    "docs/truth/sealed/FREEZE-W.md",
    "docs/truth/sealed/freeze-w.json",
    "docs/truth/sealed/check_freeze_w.py",
]


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--base", required=True, help="the commit the frozen files come from")
    args = parser.parse_args()
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "synapse_kernel"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    kernel = sorted(name for name in tracked if not name.endswith(".pyc"))
    world = load("synapse_kernel/worlds/release_world.json")
    fit = load("docs/truth/world/fit-report.json")
    tables = load("synapse_kernel/worlds/incumbent_tables.json")
    report = load("docs/truth/world/incumbent-report.json")
    from synapse_kernel.release.world import REQUIRED_PROVENANCE  # noqa: PLC0415 - after the path

    freeze = {
        "freeze": "W",
        "prereg": "PREREG-1 section 5",
        "date": args.date,
        "base_commit": args.base,
        "hashing": "sha256 of each file's bytes as git stores them (CRLF read as LF)",
        "files": {
            "world": "synapse_kernel/worlds/release_world.json",
            "incumbent_tables": "synapse_kernel/worlds/incumbent_tables.json",
            "incumbent_report": "docs/truth/world/incumbent-report.json",
            "incumbent_script": "scripts/kernel/tune_incumbent.py",
            "fit_report": "docs/truth/world/fit-report.json",
            "fit_script": "scripts/world/fit_release_world.py",
        },
        "kernel": {"root": "synapse_kernel/", "files": len(kernel)},
        "world": {
            "items": len(world["items"]),
            "units_per_day": fit["store"]["units_per_day"],
            "suppliers": {
                s["name"]: {
                    "delivery_hours": s["delivery_hours"],
                    "lead_time_hours": s["lead_time_hours"],
                }
                for s in world["suppliers"]
            },
            "shelf_life_hours": sorted({i["shelf_life_hours"] for i in world["items"]}),
            "prices": "1 for every item",
            "initial_state": (
                "per item, one batch at age zero of ceil(mean demand over L_j + R_j) from hour "
                "0, R_j the longest interval between the supplier's deliveries "
                "(Supplier.review_hours); "
                "nothing on order "
                "(synapse_kernel/release/engine.py, initial_stock)"
            ),
            "required_provenance": sorted(REQUIRED_PROVENANCE),
        },
        "calibration": {
            "scale": report["calibration_scale"],
            "steps": [
                {"scale": s["scale"], "better": s["better"], "waste_share": s["waste_share"]}
                for s in report["calibration"]
            ],
            "band": [0.027, 0.109],
        },
        "demand_recovery": {
            "method": fit["masking_check"]["used"],
            "masking_label": fit["masking_check"]["label"],
            "masking_passes": fit["masking_check"]["passes"],
        },
        "incumbent": {
            "replicate_evaluations": {n: v["replicate_evaluations"] for n, v in tables.items()},
            "selected": {
                c: report["selection"][c]["selected"] for c in ("N", "L", "S1", "S2", "S3")
            },
            "contest": report["contest_incumbent"],
        },
        "D_c": report["D_c"],
        "p_c": report["p_c"],
        "M_c": report["M_c"],
        "headroom": {
            cell: {
                variant: {
                    field: report["headroom"][cell][variant][field]
                    for field in (
                        "mean_advantage",
                        "advantage_ci95",
                        "difference_in_differences",
                        "difference_in_differences_ci95",
                        "clipped_share",
                    )
                }
                for variant in (
                    "gate_unguarded",
                    "gate_guarded",
                    "informed_unguarded",
                    "informed_guarded",
                )
            }
            for cell in ("S1", "S2", "S3")
        },
        "run_time_check": (
            "synapse_kernel.release.integrity.assert_frozen(): import it before any challenger "
            "code; it refuses a run when a frozen file's digest differs or a frozen callable was "
            "replaced in memory"
        ),
        "rules": [
            "A later change to any frozen file or choice is a deviation: dated, with its reason "
            "and effect, in DEVIATIONS.md; the confirmatory run is then reported on both worlds, "
            "the frozen one primary (PREREG-1 sections 5 and 11).",
            "New files are allowed, under synapse_kernel/ and elsewhere: session 6 adds "
            "challengers and the composition beside the frozen world.",
            "No challenger, composition or component of SYNAPSE ran on the release world before "
            "this freeze was pushed.",
        ],
    }
    (SEALED / "freeze-w.json").write_text(
        json.dumps(freeze, sort_keys=True, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    names = kernel + OUTSIDE_KERNEL + OWN
    lines = [f"{canonical_sha256(ROOT / n)} *{n}" for n in names]
    (SEALED / "SHA256SUMS-W").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"freeze-w.json and SHA256SUMS-W written: {len(names)} files ({len(kernel)} kernel)")


if __name__ == "__main__":
    main()
