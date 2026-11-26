"""The confirmatory run of PREREG-1, and its dry run: every arm, every replicate, every replay.

PREREG-1 section 5 fixes how the confirmatory seeds arise and section 7 what is computed from them.
This script does both for one attempt, in this order, refusing at the first thing that is not so:

0. **Before anything reads the round.**
   - The arguments make sense: an attempt runs as parts and one merge of both worlds.
   - numpy is the frozen 2.4.4, and its bootstrap stream is the pinned one.
   - No loaded module comes from an unfrozen file under the repository.
   - The beacon verifier accepts a known past round.
1. **The attempt is on record.** ``--attempt <nonce>`` names a record that
   :mod:`scripts.confirm.attempt` wrote, and all of these hold:
   - the record is on ``origin/main`` (pushed before this run), byte for byte;
   - no results file names the attempt, here or on ``origin/main``;
   - the record names R_C, and the digest of the freeze C sums that this checkout holds;
   - those sums are ``origin/main``'s;
   - this checkout's commit is on ``origin/main``;
   - freeze C's checker passes;
   - the beacon round R_C has been emitted.

   An execution that reads the round's signature is an attempt, and this order puts its record in
   public before its output exists.
2. **The round.** R_C's signature is fetched from public drand relays and verified against
   quicknet's public key (:mod:`synapse_beacon`). Replicate ``j`` of every cell gets the first 8
   bytes of ``SHA-256("synapse/prereg-1/confirm/" || sig || j)``, big-endian, shifted right by one
   bit.
3. **The arms**, per world (W primary, W-d1 secondary), per cell, ``n_c`` replicates (freeze C's
   power record):
   - the cell's selected incumbent (frozen, in this process);
   - SYNAPSE (freeze C's composition);
   - SYNAPSE's lane incumbent (the comparator of its trust map, reported beside C1);
   - SYNAPSE without each component named at freeze C.

   Every SYNAPSE arm runs in a fresh child process per replicate. Its outcome is replayed from its
   decision log, and its decisions are re-derived from its observation log by a second fresh child
   (:mod:`scripts.challengers.isolate`). Every child's launch inputs are digested and checked at
   the merge.
4. **The analysis.** :func:`synapse_kernel.proof.analysis.analyse` runs, its bootstrap seeded from
   ``SHA-256("synapse/prereg-1/bootstrap/" || sig)``. Beside it, as description:
   - section 7's per-item breakdown (:func:`per_item`);
   - each shock cell's difference in differences against N (:func:`shock_did`);
   - every replicate's totals.

**Parts and the merge.** ``--cells``, ``--chunk i/m`` and ``--raw-out`` run a part: some cells,
every m-th replicate from the i-th. A part records where it ran (``environment``: the interpreter,
numpy, the platform and GitHub's run and job), so the work can be spread over runners and every
execution checked against the public run history. ``--merge`` checks the parts whole, then analyses
both worlds, and writes nothing until both are done. Whole means:
- every part is this attempt's;
- every part ran this checkout's challenger code, its arms and numpy 2.4.4;
- every child of an arm was launched with the same inputs;
- every replicate ``j < n_c`` of every cell appears exactly once, with the seed the round gives it.

**The dry run.** ``--dry-run`` stands the D3 development seeds (k 448-647) in for the confirmatory
ones, and a fixed label in for the signature. There is no attempt and no round, and every
statistic is computed (truth session 6, stage D2).

**Rehearsal.** ``--rehearse`` exercises the confirmatory path's outside steps on a known past round:
the verifier, each relay, and the git reads of ``origin/main``. It never reads R_C.

**Records.** A results file names its attempt, so an attempt is used once. No run overwrites a file
that a freeze lists (:mod:`scripts.confirm.outputs`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import sysconfig
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from scripts.challengers import child
from scripts.challengers.isolate import SPAWN, Spec, run_one, summarise
from scripts.confirm.outputs import freeze_c_exists, frozen_names, record_dir, write_json
from synapse_kernel.proof.analysis import (
    CELLS,
    Arm,
    CellRun,
    analyse,
    assert_stream_pinned,
    bootstrap,
    bootstrap_seed,
    index_stream,
    interval95,
)
from synapse_kernel.release import seeds

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parents[2]
ATTEMPTS = ROOT / "docs" / "truth" / "confirm" / "attempts"
RESULTS = ROOT / "docs" / "truth" / "confirm" / "results"
RESULTS_REL = "docs/truth/confirm/results"
COMPOSITION = ROOT / "docs" / "truth" / "composition"
SUMS_C = ROOT / "docs" / "truth" / "sealed" / "SHA256SUMS-C"
SUMS_C_REL = "docs/truth/sealed/SHA256SUMS-C"
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
#: Freeze C fixes the numpy version (PREREG-1 section 5); any other is refused.
NUMPY = "2.4.4"
#: A past quicknet round and its signature (``tests/beacon/fixtures``), for the self-test.
KNOWN_ROUND = 34052212
KNOWN_SIGNATURE = (
    "b2a401b562d88856e2d0b85f426301913ff20eaa8bdf442fa96749f4b5be3777"
    "7793bcf1f447054977656f5f20f20add"
)
#: The arms whose per-item costs a replicate keeps, for the per-item breakdown.
ITEM_ARMS = ("incumbent", "synapse", "lane")
#: The totals of each arm that the analysis reads, kept per replicate in the results.
ARM_FIELDS = ("cost", "fill", "lost", "wasted", "held", "end_on_hand")
SHOCKS = ("S1", "S2", "S3")
#: GitHub's variables naming the workflow run and job an execution belongs to.
GITHUB = (
    "GITHUB_REPOSITORY",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_JOB",
    "GITHUB_SHA",
    "RUNNER_NAME",
    "RUNNER_OS",
    "RUNNER_ARCH",
)


def confirm_seed(signature: bytes, j: int) -> int:
    """PREREG-1 section 5: replicate ``j``'s seed from the round's signature."""
    digest = hashlib.sha256(CONFIRM_LABEL + signature + j.to_bytes(8, "big")).digest()
    return int.from_bytes(digest[:8], "big") >> 1


def _git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return done.stdout


def _git_ok(*args: str) -> bool:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True).returncode == 0


def _utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def environment() -> dict[str, Any]:
    """Where this process runs: the interpreter, numpy, the platform and, on GitHub's runners, the
    workflow run and job, so an execution can be checked against the public run history."""
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform": platform.platform(),
        "github": {name: os.environ.get(name) for name in GITHUB},
        "utc": _utc(),
    }


def sums_digest() -> str | None:
    """The sha256 of this checkout's freeze C sums, as git stores them (CRLF read as LF)."""
    if not SUMS_C.is_file():
        return None
    return hashlib.sha256(SUMS_C.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def audit_modules() -> None:
    """Refuse a loaded module whose file lies under the repository and that no freeze lists.

    Examples: an added ``scripts/__init__.py``, which would run before every frozen module, or a
    root-level file shadowing the standard library or numpy for a process started at the root.
    Files of the Python environment itself are not the repository's, even when a virtual
    environment sits inside it.
    """
    frozen = frozen_names()
    root = ROOT.resolve()
    environment_dirs = {Path(p).resolve() for p in sysconfig.get_paths().values()}
    environment_dirs |= {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}
    for name, module in sorted(sys.modules.items()):
        file = getattr(module, "__file__", None)
        if not isinstance(file, str):
            continue
        path = Path(file).resolve()
        if any(path.is_relative_to(d) for d in environment_dirs):
            continue
        if not path.is_relative_to(root):
            continue
        rel = path.relative_to(root).as_posix()
        if rel not in frozen:
            raise SystemExit(f"module {name} came from {rel}, which no freeze lists")


def validate(args: argparse.Namespace) -> tuple[int, int]:
    """Refuse, before anything reads the round, arguments that would fail after it; return the
    chunk ``(i, m)``."""
    if np.__version__ != NUMPY:
        raise SystemExit(f"numpy {np.__version__}: freeze C fixes numpy {NUMPY}")
    try:
        first, second = args.chunk.split("/")
        index, slices = int(first), int(second)
    except ValueError:
        raise SystemExit(f"--chunk {args.chunk!r}: expected i/m") from None
    if not (slices >= 1 and 0 <= index < slices):
        raise SystemExit(f"--chunk {args.chunk!r}: expected 0 <= i < m")
    if args.merge is not None and args.raw_out is not None:
        raise SystemExit("--merge and --raw-out are exclusive")
    partial = sorted(args.cells) != sorted(CELLS) or slices != 1
    if args.rehearse:
        if args.merge or args.raw_out or args.per_cell or partial or args.worlds != list(WORLDS):
            raise SystemExit("--rehearse takes no other option")
    elif args.attempt is not None:
        if args.per_cell:
            raise SystemExit("--per-cell belongs to the dry run")
        if args.merge is None and args.raw_out is None:
            raise SystemExit("an attempt runs as parts (--raw-out) and one merge (--merge)")
        if args.merge is not None and sorted(args.worlds) != sorted(WORLDS):
            raise SystemExit("an attempt's merge takes both worlds")
    elif args.merge is None and args.raw_out is None and partial:
        raise SystemExit("a subset of cells or a chunk is a part: give --raw-out")
    return index, slices


def beacon_self_test() -> None:
    """The verifier runs (py_ecc imports) and accepts a known past round. Called before anything
    asks for R_C, so a missing or broken verifier stops the run before the signature is read."""
    import synapse_beacon

    try:
        ok = synapse_beacon.verify(KNOWN_ROUND, KNOWN_SIGNATURE)
    except ImportError as error:
        raise SystemExit(f"the beacon verifier cannot run: {error}") from None
    if not ok:
        raise SystemExit(f"the beacon verifier rejects round {KNOWN_ROUND}, a known good one")


def check_attempt(nonce: str) -> dict[str, Any]:
    """Refuse unless all of these hold, then return the attempt's record:
    - the attempt is pushed and unused;
    - it is for R_C and for the freeze C sums this checkout holds;
    - those sums are ``origin/main``'s, and the checkout's commit is on ``origin/main``;
    - freeze C's checker passes, run isolated (``-I``) so no file beside it can stand in for a
      module it imports."""
    path = ATTEMPTS / f"{nonce}.json"
    if not path.exists():
        raise SystemExit(f"no attempt record {path.name}; run scripts.confirm.attempt first")
    _git("fetch", "--quiet", "origin")
    try:
        published = _git("show", f"origin/main:{path.relative_to(ROOT).as_posix()}")
    except subprocess.CalledProcessError:
        raise SystemExit(f"the attempt record {path.name} is not on origin/main") from None
    if published.encode("utf-8") != path.read_bytes().replace(b"\r\n", b"\n"):
        raise SystemExit("the attempt record on origin/main differs from this one")
    used = [
        result.name
        for result in RESULTS.glob("*.json")
        if json.loads(result.read_text(encoding="utf-8")).get("attempt") == nonce
    ]
    listed = _git("ls-tree", "-r", "--name-only", "origin/main", "--", RESULTS_REL).split()
    used += [Path(name).name for name in listed if Path(name).name.startswith(f"{nonce}-")]
    if used:
        raise SystemExit(f"attempt {nonce} was already used ({', '.join(sorted(set(used)))})")
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if record.get("round") != ROUND:
        raise SystemExit(f"the attempt names round {record.get('round')}, not R_C = {ROUND}")
    local = sums_digest()
    if local is None or record.get("freeze_c_sums_sha256") != local:
        raise SystemExit("the attempt was recorded against other freeze C sums than these")
    try:
        on_main = _git("show", f"origin/main:{SUMS_C_REL}").encode("utf-8")
    except subprocess.CalledProcessError:
        raise SystemExit("origin/main holds no freeze C") from None
    if hashlib.sha256(on_main).hexdigest() != local:
        raise SystemExit("this checkout's freeze C is not origin/main's")
    if not _git_ok("merge-base", "--is-ancestor", "HEAD", "origin/main"):
        raise SystemExit("this checkout's commit is not on origin/main")
    if not checker_passes():
        raise SystemExit("freeze C does not hold")
    return record


def checker_passes() -> bool:
    """Freeze C's checker, run isolated (``-I``): no file beside it, nor the working directory, can
    stand in for a module it imports (attack on freeze C, finding B1)."""
    checker = ROOT / "docs" / "truth" / "sealed" / "check_freeze_c.py"
    return subprocess.run([sys.executable, "-I", str(checker)], cwd=ROOT).returncode == 0


def fetch_from(relay: str, round_number: int) -> bytes:
    """One relay's signature of ``round_number``, verified against quicknet's key.

    Raises:
        OSError, ValueError, KeyError: the relay could not serve the round.
        SystemExit: the relay served a signature that does not verify (the run stops).
    """
    import synapse_beacon

    url = f"{relay}/{synapse_beacon.CHAIN_HASH}/public/{round_number}"
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https hosts
        body = json.loads(response.read().decode("utf-8"))
    if int(body["round"]) != round_number:
        raise ValueError(f"served round {body['round']}")
    if not synapse_beacon.verify(round_number, str(body["signature"])):
        raise SystemExit(f"{relay} served a signature that does not verify")
    return bytes.fromhex(str(body["signature"]))


def fetch_signature(round_number: int) -> bytes:
    """The round's signature from the first relay that serves it, verified; never before the round
    is emitted."""
    import synapse_beacon

    if time.time() < synapse_beacon.emitted_at(round_number):
        raise SystemExit(f"round {round_number} has not been emitted yet")
    errors: list[str] = []
    for relay in RELAYS:
        try:
            return fetch_from(relay, round_number)
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(f"{relay}: {error}")
    raise SystemExit("no relay served the round: " + "; ".join(errors))


def rehearse() -> int:
    """The confirmatory path's outside steps, without R_C. Prints a JSON report, and exits 0 when
    the verifier passes and at least one relay serves the known signature. The steps:
    - the verifier, on a known past round;
    - each relay, on that round;
    - the git reads that :func:`check_attempt` makes of ``origin/main``."""
    beacon_self_test()
    relays: dict[str, str] = {}
    for relay in RELAYS:
        try:
            signature = fetch_from(relay, KNOWN_ROUND)
        except SystemExit as stop:
            relays[relay] = f"refused: {stop}"
        except (OSError, ValueError, KeyError, TypeError) as error:
            relays[relay] = f"failed: {error}"
        else:
            relays[relay] = "verified" if signature.hex() == KNOWN_SIGNATURE else "verified, other"
    reads: dict[str, Any] = {}
    steps = {
        "fetch": ("fetch", "--quiet", "origin"),
        "freeze_c_on_main": ("show", f"origin/main:{SUMS_C_REL}"),
        "results_on_main": ("ls-tree", "-r", "--name-only", "origin/main", "--", RESULTS_REL),
    }
    for name, step in steps.items():
        try:
            out = _git(*step)
        except subprocess.CalledProcessError as error:
            reads[name] = f"failed ({error.returncode}): {str(error.stderr or '').strip()[:200]}"
            continue
        if name == "fetch":
            reads[name] = "ok"
        elif name == "freeze_c_on_main":
            reads[name] = hashlib.sha256(out.encode("utf-8")).hexdigest()
        else:
            reads[name] = out.split()
    reads["head_on_main"] = _git_ok("merge-base", "--is-ancestor", "HEAD", "origin/main")
    report = {"round": KNOWN_ROUND, "relays": relays, "git": reads, "environment": environment()}
    print(json.dumps(report, sort_keys=True, indent=1), flush=True)
    return 0 if "verified" in relays.values() else 1


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
    out: dict[str, Any] = {"j": j, "seed": seed, "incumbent": incumbent}
    for arm, spec in arm_specs.items():
        result = run_one(spec, cell, seed)
        if not (result["outcome_replay"] and result["decision_replay"]):
            raise RuntimeError(f"a replay failed: {world_label} {cell} {j} {arm}")
        if arm not in ITEM_ARMS:
            result.pop("item_cost", None)
        out[arm] = result
    child.check(world_label, world, tables)
    integrity.assert_frozen()
    if freeze_c_exists():
        audit_modules()
    return out


def _arm(rows: list[dict[str, Any]]) -> Arm:
    def col(key: str) -> np.ndarray[Any, np.dtype[np.float64]]:
        return np.asarray([float(r[key]) for r in rows], dtype=np.float64)

    return Arm(*(col(field) for field in ARM_FIELDS))


def collect(
    world_label: str, chosen: dict[str, list[tuple[int, int]]], workers: int
) -> dict[str, Any]:
    """Every arm at the chosen replicates ``(j, seed)`` of each cell, run in parallel: one part,
    with where and when it ran."""
    arm_specs = specs(world_label)
    started = environment()
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
        "environment": started,
        "finished_utc": _utc(),
    }


def replicate_seed(dry_run: bool, signature: bytes, j: int) -> int:
    """Replicate ``j``'s seed: from R_C's signature, or in the dry run D3's ``k = 448 + j``."""
    return seeds.explore_seed(D3[j]) if dry_run else confirm_seed(signature, j)


def replicates(
    power: dict[str, Any], world_label: str, dry_run: bool, per_cell: int
) -> dict[str, int]:
    """``n_c`` per cell from the power record; in the dry run at most D3's 200 (or ``per_cell``)."""
    n_c = {cell: int(power["worlds"][world_label][cell]["n_c"]) for cell in CELLS}
    if dry_run:
        n_c = {c: min(n, per_cell or len(D3), len(D3)) for c, n in n_c.items()}
    return n_c


def check_launches(
    world_label: str, parts: list[dict[str, Any]], arms: list[str]
) -> dict[str, dict[str, str]]:
    """Refuse unless all of these hold, then return each arm's spec and argument digests (the run's
    own evidence of the gate's launch parity, item 9):
    - every child of an arm got the same spec and arguments, whatever its cell, part or machine;
    - each child started in an empty folder;
    - every child within one part saw the same environment."""
    launched: dict[str, set[tuple[str, str]]] = {arm: set() for arm in arms}
    for part in parts:
        environments: set[str] = set()
        for rows in part["rows"].values():
            for row in rows:
                for arm in arms:
                    shake = row[arm].get("handshake")
                    if not isinstance(shake, dict) or shake.get("workdir_empty") != "True":
                        raise RuntimeError(f"{world_label} {arm}: a child not launched as frozen")
                    launched[arm].add((str(shake["spec"]), str(shake["argv"])))
                    environments.add(str(shake["environment"]))
        if len(environments) > 1:
            raise RuntimeError(f"{world_label}: one part's children saw several environments")
    out: dict[str, dict[str, str]] = {}
    for arm, seen in launched.items():
        if len(seen) != 1:
            raise RuntimeError(f"{world_label} {arm}: its children were launched with other inputs")
        spec, argv = next(iter(seen))
        out[arm] = {"spec": spec, "argv": argv}
    return out


def check_parts(
    world_label: str,
    parts: list[dict[str, Any]],
    n_c: dict[str, int],
    head: dict[str, Any],
    seed_of: Callable[[int], int],
) -> dict[str, list[dict[str, Any]]]:
    """Refuse a merge unless the parts are this attempt's whole, then return the rows by cell in
    replicate order. Whole means all of these:
    - every part is this attempt's (``head``: attempt, round, signature);
    - every part ran this checkout's challenger code, this world's arms and numpy 2.4.4, and holds
      no cell but the five;
    - every child was launched as :func:`check_launches` requires;
    - every replicate ``j < n_c`` of every cell appears exactly once, with ``seed_of(j)``."""
    from scripts.challengers.measure import code_digest

    if not parts:
        raise RuntimeError(f"{world_label}: no parts to merge")
    for part in parts:
        for key, value in head.items():
            if part.get(key) != value:
                raise RuntimeError(f"{world_label}: a part of another attempt ({key} differs)")
        if part.get("world") != world_label:
            raise RuntimeError(f"{world_label}: a part of world {part.get('world')}")
        if set(part["rows"]) - set(CELLS):
            raise RuntimeError(f"{world_label}: a part holds cells {sorted(part['rows'])}")
        ran = (part.get("environment") or {}).get("numpy")
        if ran != NUMPY:
            raise RuntimeError(f"{world_label}: a part ran numpy {ran}, not {NUMPY}")
    here = json.dumps(code_digest(), sort_keys=True)
    if {json.dumps(p["code"], sort_keys=True) for p in parts} != {here}:
        raise RuntimeError(f"{world_label}: a part ran other challenger code than this checkout's")
    arms = sorted(specs(world_label))
    if {tuple(p["arms"]) for p in parts} != {tuple(arms)}:
        raise RuntimeError(f"{world_label}: a part ran other arms than this world's")
    by_cell: dict[str, list[dict[str, Any]]] = {}
    for cell in CELLS:
        rows = sorted(
            (row for part in parts for row in part["rows"].get(cell, [])),
            key=lambda r: int(r["j"]),
        )
        if [int(r["j"]) for r in rows] != list(range(n_c[cell])):
            raise RuntimeError(f"{world_label} {cell}: replicates are missing or repeated")
        wrong = [int(r["j"]) for r in rows if int(r["seed"]) != seed_of(int(r["j"]))]
        if wrong:
            raise RuntimeError(f"{world_label} {cell}: replicates {wrong[:5]} ran another seed")
        by_cell[cell] = rows
    check_launches(world_label, parts, arms)
    return by_cell


def per_item(item_names: list[str], by_cell: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """PREREG-1 section 7's per-item breakdown, as description: in every cell, each item's mean
    cost per store-day (its part of J, ``objective.item_costs``) under the incumbent, SYNAPSE and
    the lane incumbent, each a ``math.fsum`` over replicates divided by their number, in the
    world's item order. An item's mean delta is SYNAPSE's minus the incumbent's."""
    cells: dict[str, dict[str, list[float]]] = {}
    for cell in CELLS:
        rows = by_cell[cell]
        means: dict[str, list[float]] = {}
        for arm in ITEM_ARMS:
            columns = list(zip(*(row[arm]["item_cost"] for row in rows), strict=True))
            if len(columns) != len(item_names):
                raise RuntimeError(f"{cell} {arm}: {len(columns)} item costs, not one per item")
            means[arm] = [math.fsum(column) / len(rows) for column in columns]
        cells[cell] = means
    return {"items": list(item_names), "arms": list(ITEM_ARMS), "cells": cells}


def shock_did(runs: dict[str, CellRun], signature: bytes) -> dict[str, Any]:
    """Description beside section 7: each shock cell's difference in differences, with its 95% BCa
    interval. Replicate ``j``'s value is its delta (SYNAPSE minus the cell's incumbent) minus the
    delta in N at the same ``j``: the same seeds, so N's construction gap cancels. It is resampled
    with the shock cell's own index matrix, from the stream the analysis uses."""
    sizes = {cell: runs[cell].synapse.cost.size for cell in CELLS}
    indices = index_stream(bootstrap_seed(signature), sizes)
    base = runs["N"].synapse.cost - runs["N"].incumbent.cost
    out: dict[str, Any] = {}
    for cell in SHOCKS:
        if sizes[cell] != sizes["N"]:
            out[cell] = None
            continue
        boot = bootstrap(
            (runs[cell].synapse.cost - runs[cell].incumbent.cost) - base, indices[cell]
        )
        low, high = interval95(boot)
        out[cell] = {"mean": boot.estimate, "low95": low, "high95": high}
    return out


def replicate_rows(
    by_cell: dict[str, list[dict[str, Any]]], arms: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Every replicate's totals per arm (``ARM_FIELDS``), so a later description can be computed
    from the results alone, without the parts."""
    return {
        cell: [
            {
                "j": int(row["j"]),
                "seed": int(row["seed"]),
                **{arm: {f: row[arm][f] for f in ARM_FIELDS} for arm in ("incumbent", *arms)},
            }
            for row in rows
        ]
        for cell, rows in by_cell.items()
    }


def analyse_world(
    world_label: str,
    parts: list[dict[str, Any]],
    n_c: dict[str, int],
    signature: bytes,
    head: dict[str, Any],
    seed_of: Callable[[int], int],
) -> dict[str, Any]:
    """One world's parts, checked whole by :func:`check_parts`, then the frozen analysis and the
    description beside it."""
    by_cell = check_parts(world_label, parts, n_c, head, seed_of)
    arms = sorted(specs(world_label))
    margins = json.loads(REPORTS[world_label].read_text(encoding="utf-8"))["M_c"]
    runs: dict[str, CellRun] = {}
    for cell in CELLS:
        rows = by_cell[cell]
        reports = [r["synapse"]["report"] for r in rows]
        challenger = [k for k, name in enumerate(reports[0]["deciders"]) if name != "incumbent"]
        runs[cell] = CellRun(
            margin=float(margins[cell]),
            incumbent=_arm([r["incumbent"] for r in rows]),
            synapse=_arm([r["synapse"] for r in rows]),
            lane=_arm([r["lane"] for r in rows]),
            ablations={
                arm.removeprefix("without:"): _arm([r[arm] for r in rows])
                for arm in arms
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
    world, _, _ = child.load(world_label)
    return {
        "world": world_label,
        "replicates": {cell: n_c[cell] for cell in CELLS},
        "arms": arms,
        "orders_digest_by_cell": digests,
        "analysis": analyse(runs, bootstrap_seed(signature)),
        "per_item": per_item([item.name for item in world.items], by_cell),
        "shock_did": shock_did(runs, signature),
        "rows": replicate_rows(by_cell, arms),
        "launches": check_launches(world_label, parts, arms),
        "parts": sorted(
            (
                {
                    "sha256": part["_sha256"],
                    "cells": sorted(part["rows"]),
                    "replicates": sum(len(rows) for rows in part["rows"].values()),
                    "environment": part.get("environment"),
                    "finished_utc": part.get("finished_utc"),
                    "wall_seconds": part["wall_seconds"],
                }
                for part in parts
            ),
            key=lambda entry: str(entry["sha256"]),
        ),
        "merge_environment": environment(),
        "wall_seconds": max(p["wall_seconds"] for p in parts),
        "code": parts[0]["code"],
    }


def load_parts(folder: Path) -> list[dict[str, Any]]:
    """Every ``part-*.json`` under ``folder``, each with the sha256 of its bytes (LF)."""
    parts: list[dict[str, Any]] = []
    for path in sorted(folder.glob("**/part-*.json")):
        data = path.read_bytes().replace(b"\r\n", b"\n")
        part: dict[str, Any] = json.loads(data.decode("utf-8"))
        part["_sha256"] = hashlib.sha256(data).hexdigest()
        parts.append(part)
    return parts


def document_for(
    world_label: str,
    parts: list[dict[str, Any]],
    n_c: dict[str, int],
    signature: bytes,
    head: dict[str, Any],
    seed_of: Callable[[int], int],
) -> dict[str, Any]:
    """A results document: the attempt's head, the commit and sums it ran on, then the world."""
    return {
        **head,
        "commit": _git("rev-parse", "HEAD").strip(),
        "freeze_c_sums_sha256": sums_digest(),
        **analyse_world(world_label, parts, n_c, signature, head, seed_of),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--attempt", help="the nonce of a pushed attempt record")
    mode.add_argument("--dry-run", action="store_true", help="D3 seeds stand in; no round read")
    mode.add_argument(
        "--rehearse", action="store_true", help="outside steps on a known past round; no R_C"
    )
    parser.add_argument("--worlds", nargs="+", default=list(WORLDS), choices=WORLDS)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--per-cell", type=int, default=0, help="dry run: replicates per cell")
    parser.add_argument("--cells", nargs="+", default=list(CELLS), choices=CELLS)
    parser.add_argument("--chunk", default="0/1", help="i/m: the i-th of m slices of each cell")
    parser.add_argument("--raw-out", type=Path, help="run this part only; write its raw results")
    parser.add_argument("--merge", type=Path, help="assemble the parts in this folder")
    args = parser.parse_args()
    index, slices = validate(args)
    # Spawned processes inherit sys.argv: clear it, so no child's launch inputs carry the part's
    # cells or chunk (gate item 9; the merge checks that every child of an arm got the same).
    del sys.argv[1:]
    assert_stream_pinned()
    if freeze_c_exists():
        audit_modules()
    if args.rehearse:
        sys.exit(rehearse())
    power = json.loads((COMPOSITION / "power.json").read_text(encoding="utf-8"))
    if args.dry_run:
        signature, label, out_dir = DRY_SIGNATURE, "dry-run", record_dir()
    else:
        beacon_self_test()
        record = check_attempt(args.attempt)
        signature, label, out_dir = fetch_signature(int(record["round"])), args.attempt, RESULTS
        audit_modules()
    head = {
        "attempt": label,
        "round": None if args.dry_run else ROUND,
        "signature": None if args.dry_run else signature.hex(),
    }

    def seed_of(j: int) -> int:
        return replicate_seed(args.dry_run, signature, j)

    if args.merge is not None:
        loaded = load_parts(args.merge)
        documents = {
            world_label: document_for(
                world_label,
                [p for p in loaded if p.get("world") == world_label],
                replicates(power, world_label, args.dry_run, args.per_cell),
                signature,
                head,
                seed_of,
            )
            for world_label in args.worlds
        }
        if freeze_c_exists():
            audit_modules()
        # Nothing is written until every world is analysed, so a failed merge leaves no results
        # file and is repeated on the same parts.
        for world_label, document in documents.items():
            write_json(out_dir / f"{label}-{world_label}.json", document)
        return
    for world_label in args.worlds:
        n_c = replicates(power, world_label, args.dry_run, args.per_cell)
        chosen = {
            cell: [(j, seed_of(j)) for j in range(n_c[cell]) if j % slices == index]
            for cell in args.cells
        }
        part = {**head, **collect(world_label, chosen, args.workers)}
        if args.raw_out is not None:
            cells = "-".join(args.cells)
            write_json(args.raw_out / f"part-{world_label}-{cells}-{index}of{slices}.json", part)
            continue
        canonical = json.dumps(part, sort_keys=True, separators=(",", ":")).encode()
        part["_sha256"] = hashlib.sha256(canonical + b"\n").hexdigest()
        document = document_for(world_label, [part], n_c, signature, head, seed_of)
        write_json(out_dir / f"{label}-{world_label}.json", document)


if __name__ == "__main__":
    main()
