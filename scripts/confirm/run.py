"""The confirmatory run of PREREG-1, and its dry run: every arm, every replicate, every replay.

PREREG-1 section 5 fixes how the confirmatory seeds arise and section 7 what is computed from them.
This script does both for one attempt, in this order, refusing at the first thing that is not so:

1. **The attempt is on record.** ``--attempt <nonce>`` names a record that
   :mod:`scripts.confirm.attempt` wrote and that is on ``origin/main`` (pushed before this run),
   byte for byte, and that no results file has used; freeze C's checker passes; the beacon round
   R_C has been emitted. An execution that reads the round's signature is an attempt: this order
   puts its record in public before its output exists.
2. **The round.** R_C's signature is fetched from public drand relays and verified against
   quicknet's public key (:mod:`synapse_beacon`); replicate ``j`` of every cell gets
   ``SHA-256("synapse/prereg-1/confirm/" || sig || j)``'s first 8 bytes, big-endian, shifted right
   by one bit.
3. **The arms**, per world (W primary, W-d1 secondary), per cell, ``n_c`` replicates (freeze C's
   power record): the cell's selected incumbent (frozen, in this process); SYNAPSE (freeze C's
   composition); SYNAPSE's lane incumbent (the comparator of its trust map, reported beside C1); and
   SYNAPSE without each component named at freeze C. Every SYNAPSE arm runs in a fresh child
   process per replicate, with the outcome replayed from its decision log and the decisions
   re-derived from its observation log by a second fresh child (:mod:`scripts.challengers.isolate`).
4. **The analysis**: :func:`synapse_kernel.proof.analysis.analyse`, its bootstrap seeded from
   ``SHA-256("synapse/prereg-1/bootstrap/" || sig)``, numpy's stream checked against its golden
   digest first.

``--cells``, ``--chunk i/m`` and ``--raw-out`` run a part (some cells, every m-th replicate from
the i-th) so the work can be spread over machines; ``--merge`` checks the parts whole and
analyses them. ``--dry-run`` stands the D3 development seeds (k 448-647) in for the confirmatory
ones and a fixed label in for the signature: no attempt, no round, every statistic computed (truth
session 6, stage D2). The results file names its attempt, so an attempt is used once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from scripts.challengers import child
from scripts.challengers.isolate import SPAWN, Spec, run_one, summarise
from synapse_kernel.proof.analysis import (
    CELLS,
    Arm,
    CellRun,
    analyse,
    assert_stream_pinned,
    bootstrap_seed,
)
from synapse_kernel.release import seeds

ROOT = Path(__file__).resolve().parents[2]
ATTEMPTS = ROOT / "docs" / "truth" / "confirm" / "attempts"
RESULTS = ROOT / "docs" / "truth" / "confirm" / "results"
COMPOSITION = ROOT / "docs" / "truth" / "composition"
REPORTS = {
    "W": ROOT / "docs" / "truth" / "world" / "incumbent-report.json",
    "W-d1": ROOT / "docs" / "truth" / "world" / "incumbent-report-d1.json",
}
WORLDS = ("W", "W-d1")
ROUND = 34714612
CONFIRM_LABEL = b"synapse/prereg-1/confirm/"
RELAYS = ("https://api.drand.sh", "https://api2.drand.sh", "https://drand.cloudflare.com")
D3 = range(448, 648)
DRY_SIGNATURE = b"truth-session-6/dry-run/D3"


def confirm_seed(signature: bytes, j: int) -> int:
    """PREREG-1 section 5: replicate ``j``'s seed from the round's signature."""
    digest = hashlib.sha256(CONFIRM_LABEL + signature + j.to_bytes(8, "big")).digest()
    return int.from_bytes(digest[:8], "big") >> 1


def _git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return done.stdout


def check_attempt(nonce: str) -> dict[str, Any]:
    """Refuse unless the attempt is pushed, unused, and freeze C holds; return its record."""
    path = ATTEMPTS / f"{nonce}.json"
    if not path.exists():
        raise SystemExit(f"no attempt record {path.name}; run scripts.confirm.attempt first")
    _git("fetch", "--quiet", "origin")
    published = _git("show", f"origin/main:{path.relative_to(ROOT).as_posix()}")
    if published.encode("utf-8") != path.read_bytes().replace(b"\r\n", b"\n"):
        raise SystemExit("the attempt record on origin/main differs from this one")
    for result in RESULTS.glob("*.json"):
        if json.loads(result.read_text(encoding="utf-8")).get("attempt") == nonce:
            raise SystemExit(f"attempt {nonce} was already used ({result.name})")
    checker = ROOT / "docs" / "truth" / "sealed" / "check_freeze_c.py"
    if subprocess.run([sys.executable, str(checker)], cwd=ROOT).returncode != 0:
        raise SystemExit("freeze C does not hold")
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return record


def fetch_signature(round_number: int) -> bytes:
    """R_C's signature from the first relay that serves it, verified against quicknet's key."""
    import synapse_beacon

    if time.time() < synapse_beacon.emitted_at(round_number):
        raise SystemExit(f"round {round_number} has not been emitted yet")
    errors: list[str] = []
    for relay in RELAYS:
        url = f"{relay}/{synapse_beacon.CHAIN_HASH}/public/{round_number}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https hosts
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as error:
            errors.append(f"{relay}: {error}")
            continue
        if int(body["round"]) != round_number:
            errors.append(f"{relay}: served round {body['round']}")
            continue
        if not synapse_beacon.verify(round_number, str(body["signature"])):
            raise SystemExit(f"{relay} served a signature that does not verify")
        return bytes.fromhex(str(body["signature"]))
    raise SystemExit("no relay served the round: " + "; ".join(errors))


def specs(world_label: str) -> dict[str, Spec]:
    """SYNAPSE, its lane incumbent and each ablation, as the challenger processes build them."""
    name = f"params-{world_label}.json"
    params = json.loads((COMPOSITION / name).read_text(encoding="utf-8"))
    rel = f"docs/truth/composition/{name}"
    out = {
        "synapse": Spec("synapse", world_label, params=rel),
        "lane": Spec("lane_incumbent", world_label),
        "without:freshness_guardian": Spec(
            "synapse",
            world_label,
            inline=json.dumps(
                {**params, "lane_rule": False}, sort_keys=True, separators=(",", ":")
            ),
        ),
    }
    for entry, decider in sorted(params["trust"].items()):
        trust = {e: d for e, d in params["trust"].items() if e != entry}
        out[f"without:{decider}@{entry}"] = Spec(
            "synapse",
            world_label,
            inline=json.dumps({**params, "trust": trust}, sort_keys=True, separators=(",", ":")),
        )
    return out


def _replicate(job: tuple[str, str, int, int, dict[str, Spec]]) -> dict[str, Any]:
    """One replicate of one cell: the incumbent here, every SYNAPSE arm in its own children."""
    from synapse_kernel.release import integrity
    from synapse_kernel.release.engine import run
    from synapse_kernel.release.incumbent import Incumbent
    from synapse_kernel.release.scenario import build_scenario

    world_label, cell, j, seed, arm_specs = job
    world, tables, _ = child.load(world_label)
    integrity.assert_frozen()
    version = json.loads(REPORTS[world_label].read_text(encoding="utf-8"))["selection"][cell][
        "selected"
    ]
    scenario = build_scenario(world, cell, seed)
    incumbent = summarise(world, run(world, [scenario], Incumbent(world, tables[version])))
    incumbent.pop("item_cost", None)
    out: dict[str, Any] = {"j": j, "seed": seed, "incumbent": incumbent}
    for arm, spec in arm_specs.items():
        result = run_one(spec, cell, seed)
        if not (result["outcome_replay"] and result["decision_replay"]):
            raise RuntimeError(f"a replay failed: {world_label} {cell} {j} {arm}")
        for heavy in ("item_cost", "handshake"):
            result.pop(heavy, None)
        out[arm] = result
    child.check(world_label, world, tables)
    integrity.assert_frozen()
    return out


def _arm(rows: list[dict[str, Any]]) -> Arm:
    def col(key: str) -> np.ndarray[Any, np.dtype[np.float64]]:
        return np.asarray([float(r[key]) for r in rows], dtype=np.float64)

    return Arm(
        col("cost"), col("fill"), col("lost"), col("wasted"), col("held"), col("end_on_hand")
    )


def collect(
    world_label: str, chosen: dict[str, list[tuple[int, int]]], workers: int
) -> dict[str, Any]:
    """Every arm at the chosen replicates ``(j, seed)`` of each cell, run in parallel: one part."""
    arm_specs = specs(world_label)
    jobs = [
        (world_label, cell, j, seed, arm_specs)
        for cell, pairs in chosen.items()
        for j, seed in pairs
    ]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers, mp_context=SPAWN) as pool:
        done = list(pool.map(_replicate, jobs))
    rows: dict[str, list[dict[str, Any]]] = {cell: [] for cell in chosen}
    for (_, cell, _, _, _), row in zip(jobs, done, strict=True):
        rows[cell].append(row)
    from scripts.challengers.measure import code_digest

    return {
        "world": world_label,
        "arms": sorted(arm_specs),
        "rows": rows,
        "wall_seconds": round(time.perf_counter() - t0, 1),
        "code": code_digest(),
    }


def analyse_world(
    world_label: str, parts: list[dict[str, Any]], n_c: dict[str, int], signature: bytes
) -> dict[str, Any]:
    """One world's parts, checked whole (every replicate ``j < n_c`` of every cell exactly once,
    the same arms and code in each), then the frozen analysis."""
    if len({json.dumps(p["code"], sort_keys=True) for p in parts}) != 1:
        raise RuntimeError(f"{world_label}: the parts ran different code")
    if len({tuple(p["arms"]) for p in parts}) != 1:
        raise RuntimeError(f"{world_label}: the parts ran different arms")
    margins = json.loads(REPORTS[world_label].read_text(encoding="utf-8"))["M_c"]
    by_cell: dict[str, list[dict[str, Any]]] = {cell: [] for cell in CELLS}
    for part in parts:
        for cell, rows in part["rows"].items():
            by_cell[cell].extend(rows)
    runs: dict[str, CellRun] = {}
    for cell in CELLS:
        rows = sorted(by_cell[cell], key=lambda r: int(r["j"]))
        if [int(r["j"]) for r in rows] != list(range(n_c[cell])):
            raise RuntimeError(f"{world_label} {cell}: replicates are missing or repeated")
        by_cell[cell] = rows
        reports = [r["synapse"]["report"] for r in rows]
        challenger = [k for k, name in enumerate(reports[0]["deciders"]) if name != "incumbent"]
        runs[cell] = CellRun(
            margin=float(margins[cell]),
            incumbent=_arm([r["incumbent"] for r in rows]),
            synapse=_arm([r["synapse"] for r in rows]),
            lane=_arm([r["lane"] for r in rows]),
            ablations={
                arm.removeprefix("without:"): _arm([r[arm] for r in rows])
                for arm in parts[0]["arms"]
                if arm.startswith("without:")
            },
            clipped=sum(rep["clipped"][0][k] for rep in reports for k in challenger),
            decisions=sum(rep["decided"][0][k] for rep in reports for k in challenger),
        )
    digests = {
        cell: hashlib.sha256(
            "".join(r["synapse"]["orders_digest"] for r in by_cell[cell]).encode()
        ).hexdigest()
        for cell in CELLS
    }
    return {
        "world": world_label,
        "replicates": {cell: n_c[cell] for cell in CELLS},
        "arms": parts[0]["arms"],
        "orders_digest_by_cell": digests,
        "analysis": analyse(runs, bootstrap_seed(signature)),
        "wall_seconds": max(p["wall_seconds"] for p in parts),
        "code": parts[0]["code"],
    }


def _write(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("written", path, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--attempt", help="the nonce of a pushed attempt record")
    mode.add_argument("--dry-run", action="store_true", help="D3 seeds stand in; no round read")
    parser.add_argument("--worlds", nargs="+", default=list(WORLDS), choices=WORLDS)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--per-cell", type=int, default=0, help="dry run: replicates per cell")
    parser.add_argument("--cells", nargs="+", default=list(CELLS), choices=CELLS)
    parser.add_argument("--chunk", default="0/1", help="i/m: the i-th of m slices of each cell")
    parser.add_argument("--raw-out", type=Path, help="run this part only; write its raw results")
    parser.add_argument("--merge", type=Path, help="assemble the parts in this folder")
    args = parser.parse_args()
    assert_stream_pinned()
    power = json.loads((COMPOSITION / "power.json").read_text(encoding="utf-8"))
    if args.dry_run:
        signature, label = DRY_SIGNATURE, "dry-run"
        out_dir = COMPOSITION
    else:
        record = check_attempt(args.attempt)
        signature, label = fetch_signature(int(record["round"])), args.attempt
        out_dir = RESULTS
    index, slices = (int(x) for x in args.chunk.split("/"))
    for world_label in args.worlds:
        n_c = {cell: int(power["worlds"][world_label][cell]["n_c"]) for cell in CELLS}
        if args.dry_run:
            n_c = {c: min(n, args.per_cell or len(D3), len(D3)) for c, n in n_c.items()}
        head = {
            "attempt": label,
            "round": None if args.dry_run else ROUND,
            "signature": None if args.dry_run else signature.hex(),
        }
        if args.merge is not None:
            parts = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(args.merge.glob("**/part-*.json"))
            ]
            parts = [p for p in parts if p["world"] == world_label and p["attempt"] == label]
            name = f"{'dry-run' if args.dry_run else args.attempt}-{world_label}.json"
            document = {
                **head,
                "commit": _git("rev-parse", "HEAD").strip(),
                **analyse_world(world_label, parts, n_c, signature),
            }
            _write(out_dir / name, document)
            continue
        chosen: dict[str, list[tuple[int, int]]] = {}
        for cell in args.cells:
            js = [j for j in range(n_c[cell]) if j % slices == index]
            chosen[cell] = [
                (j, seeds.explore_seed(D3[j]) if args.dry_run else confirm_seed(signature, j))
                for j in js
            ]
        part = {**head, **collect(world_label, chosen, args.workers)}
        if args.raw_out is not None:
            cells = "-".join(args.cells)
            _write(args.raw_out / f"part-{world_label}-{cells}-{index}of{slices}.json", part)
        else:
            whole = analyse_world(world_label, [part], n_c, signature)
            document = {**head, "commit": _git("rev-parse", "HEAD").strip(), **whole}
            name = f"{'dry-run' if args.dry_run else args.attempt}-{world_label}.json"
            _write(out_dir / name, document)


if __name__ == "__main__":
    main()
