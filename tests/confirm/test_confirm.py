"""The confirmatory runner's guarantees, each shown able to fail (truth session 6, stages D2 and E).

* Replicate ``j``'s seed is PREREG-1 section 5's, byte for byte (planted: ``j`` as 4 bytes).
* An attempt is refused unless all of these hold:
  - its record exists, and is on ``origin/main`` byte for byte;
  - no results file names it, here or on ``origin/main``;
  - it names R_C, and the digest of the freeze C sums this checkout holds;
  - those sums are ``origin/main``'s, and the checkout's commit is on ``origin/main``;
  - freeze C's checker, run isolated, passes.
* Before the round is read:
  - the arguments are checked: an attempt runs as parts and one merge of both worlds;
  - numpy must be 2.4.4;
  - the beacon verifier must accept a known round;
  - no loaded module may come from an unfrozen file under the repository.
* The round is not asked for before it is emitted. A relay's signature that does not verify stops
  the run. A relay serving another round, or something that is not a round, is not used.
* A merge refuses any of these:
  - a part of another attempt (attempt, round or signature), or of another world;
  - a part run with other challenger code, other arms or another numpy;
  - a part holding a cell outside the five;
  - a missing or repeated replicate, or one run with another seed than the round (or D3) gives it;
  - children of one arm launched with different inputs, outside an empty folder, or within one
    part under different environments.
* The description beside the analysis:
  - the per-item breakdown;
  - the shock cells' difference in differences against N;
  - each replicate's totals.
* No run overwrites a frozen file. After freeze C, the dry run and power write to the rehearsals.
* The rehearsal exercises the verifier, every relay and the git reads on a known past round.
* The arms are SYNAPSE, its lane incumbent, and one ablation per named component: the Freshness
  Guardian (the lane rule), and each trusted entry's decider.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import synapse_beacon
from scripts.challengers.measure import code_digest
from scripts.confirm import outputs
from scripts.confirm import run as runner
from synapse_kernel.proof.analysis import CELLS, Arm, CellRun
from synapse_kernel.release import seeds


def test_the_seed_of_replicate_j_is_prereg_1s() -> None:
    signature = bytes(range(48))
    for j in (0, 1, 2, 199, 1999):
        digest = hashlib.sha256(
            b"synapse/prereg-1/confirm/" + signature + j.to_bytes(8, "big")
        ).digest()
        assert runner.confirm_seed(signature, j) == int.from_bytes(digest[:8], "big") >> 1
    planted = hashlib.sha256(b"synapse/prereg-1/confirm/" + signature + (5).to_bytes(4, "big"))
    assert runner.confirm_seed(signature, 5) != int.from_bytes(planted.digest()[:8], "big") >> 1


SUMS_TEXT = "0" * 64 + " *docs/truth/sealed/FREEZE-C.md\n"


@pytest.fixture
def attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A private attempts and results folder, a stand-in ``git`` whose ``origin/main`` holds the
    same freeze C sums, and a stand-in freeze C checker."""
    root = tmp_path
    (root / "docs" / "truth" / "confirm" / "attempts").mkdir(parents=True)
    (root / "docs" / "truth" / "confirm" / "results").mkdir(parents=True)
    (root / "docs" / "truth" / "sealed").mkdir(parents=True)
    sums = root / "docs" / "truth" / "sealed" / "SHA256SUMS-C"
    sums.write_text(SUMS_TEXT, encoding="utf-8", newline="\n")
    state: dict[str, Any] = {
        "published": {runner.SUMS_C_REL: SUMS_TEXT},
        "checker": 0,
        "on_main": True,
        "results_on_main": [],
    }
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "ATTEMPTS", root / "docs" / "truth" / "confirm" / "attempts")
    monkeypatch.setattr(runner, "RESULTS", root / "docs" / "truth" / "confirm" / "results")
    monkeypatch.setattr(runner, "SUMS_C", sums)

    def git(*args: str) -> str:
        if args[0] == "show":
            path = args[1].split(":", 1)[1]
            if path not in state["published"]:
                # what ``git show`` run with ``check=True`` raises for a path not on that commit
                raise subprocess.CalledProcessError(128, ["git", *args])
            return str(state["published"][path])
        if args[0] == "ls-tree":
            return "\n".join(state["results_on_main"])
        return ""

    monkeypatch.setattr(runner, "_git", git)
    monkeypatch.setattr(runner, "_git_ok", lambda *args: state["on_main"])
    monkeypatch.setattr(runner, "checker_passes", lambda: state["checker"] == 0)
    return {"root": root, "state": state, "sums": hashlib.sha256(sums.read_bytes()).hexdigest()}


def _write(attempts: dict[str, Any], nonce: str, publish: bool, **changes: Any) -> None:
    record = {"nonce": nonce, "round": runner.ROUND, "freeze_c_sums_sha256": attempts["sums"]}
    text = json.dumps({**record, **changes}) + "\n"
    rel = f"docs/truth/confirm/attempts/{nonce}.json"
    (attempts["root"] / rel).write_text(text, encoding="utf-8", newline="\n")
    if publish:
        attempts["state"]["published"][rel] = text


def test_a_pushed_unused_attempt_passes(attempts: dict[str, Any]) -> None:
    _write(attempts, "aa", publish=True)
    assert runner.check_attempt("aa")["nonce"] == "aa"


def test_the_checker_runs_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class Done:
        returncode = 0

    def run(command: list[str], **kwargs: Any) -> Done:
        calls.append(command)
        return Done()

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.checker_passes()
    assert calls[0][0] == sys.executable and calls[0][1] == "-I"
    assert calls[0][2].endswith("check_freeze_c.py")


def test_an_attempt_without_a_record_is_refused(attempts: dict[str, Any]) -> None:
    with pytest.raises(SystemExit, match="no attempt record"):
        runner.check_attempt("bb")


def test_an_attempt_not_pushed_is_refused(attempts: dict[str, Any]) -> None:
    _write(attempts, "cc", publish=False)
    with pytest.raises(SystemExit, match=r"record cc\.json is not on origin/main"):
        runner.check_attempt("cc")


def test_an_attempt_changed_after_its_push_is_refused(attempts: dict[str, Any]) -> None:
    _write(attempts, "dd", publish=True)
    path = attempts["root"] / "docs" / "truth" / "confirm" / "attempts" / "dd.json"
    path.write_text(json.dumps({"nonce": "dd", "round": 1}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="differs"):
        runner.check_attempt("dd")


def test_a_used_attempt_is_refused(attempts: dict[str, Any]) -> None:
    _write(attempts, "ee", publish=True)
    results = attempts["root"] / "docs" / "truth" / "confirm" / "results" / "ee-W.json"
    results.write_text(json.dumps({"attempt": "ee"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="already used"):
        runner.check_attempt("ee")


def test_an_attempt_used_on_main_is_refused_in_an_older_checkout(attempts: dict[str, Any]) -> None:
    _write(attempts, "ef", publish=True)
    attempts["state"]["results_on_main"] = ["docs/truth/confirm/results/ef-W-d1.json"]
    with pytest.raises(SystemExit, match="already used"):
        runner.check_attempt("ef")


def test_an_attempt_without_freeze_c_is_refused(attempts: dict[str, Any]) -> None:
    _write(attempts, "ff", publish=True)
    attempts["state"]["checker"] = 1
    with pytest.raises(SystemExit, match="freeze C does not hold"):
        runner.check_attempt("ff")


def test_an_attempt_for_another_round_is_refused(attempts: dict[str, Any]) -> None:
    _write(attempts, "gg", publish=True, round=runner.ROUND + 1)
    with pytest.raises(SystemExit, match="not R_C"):
        runner.check_attempt("gg")


def test_an_attempt_recorded_against_other_freeze_c_sums_is_refused(
    attempts: dict[str, Any],
) -> None:
    _write(attempts, "hh", publish=True, freeze_c_sums_sha256="1" * 64)
    with pytest.raises(SystemExit, match="other freeze C sums"):
        runner.check_attempt("hh")
    _write(attempts, "ii", publish=True)
    runner.SUMS_C.unlink()
    with pytest.raises(SystemExit, match="other freeze C sums"):
        runner.check_attempt("ii")


def test_a_checkout_whose_freeze_c_is_not_mains_is_refused(attempts: dict[str, Any]) -> None:
    _write(attempts, "jj", publish=True)
    attempts["state"]["published"][runner.SUMS_C_REL] = SUMS_TEXT + "1" * 64 + " *extra\n"
    with pytest.raises(SystemExit, match="not origin/main's"):
        runner.check_attempt("jj")
    del attempts["state"]["published"][runner.SUMS_C_REL]
    with pytest.raises(SystemExit, match="origin/main holds no freeze C"):
        runner.check_attempt("jj")


def test_a_checkout_whose_commit_is_not_on_main_is_refused(attempts: dict[str, Any]) -> None:
    _write(attempts, "kk", publish=True)
    attempts["state"]["on_main"] = False
    with pytest.raises(SystemExit, match="commit is not on origin/main"):
        runner.check_attempt("kk")


class _Relay:
    """A stand-in relay response, served for every URL."""

    def __init__(self, body: Any) -> None:
        self.data = io.BytesIO(json.dumps(body).encode("utf-8"))

    def __enter__(self) -> _Relay:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self.data.read()


def test_the_round_is_not_asked_for_before_it_is_emitted(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted = synapse_beacon.emitted_at(runner.ROUND)
    asked: list[str] = []
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda url, timeout: asked.append(url))
    monkeypatch.setattr(runner.time, "time", lambda: emitted - 1.0)
    with pytest.raises(SystemExit, match="has not been emitted"):
        runner.fetch_signature(runner.ROUND)
    assert asked == []


def test_a_relay_signature_that_does_not_verify_stops_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"round": runner.ROUND, "signature": "ab" * 48}
    monkeypatch.setattr(runner.time, "time", lambda: synapse_beacon.emitted_at(runner.ROUND) + 9.0)
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda url, timeout: _Relay(body))
    monkeypatch.setattr(synapse_beacon, "verify", lambda round_number, signature: False)
    with pytest.raises(SystemExit, match="does not verify"):
        runner.fetch_signature(runner.ROUND)
    monkeypatch.setattr(synapse_beacon, "verify", lambda round_number, signature: True)
    assert runner.fetch_signature(runner.ROUND) == bytes.fromhex("ab" * 48)


@pytest.mark.parametrize(
    "body", [{"round": runner.ROUND - 1, "signature": "ab" * 48}, ["not", "a", "round"], {}]
)
def test_a_relay_serving_another_round_or_no_round_is_not_used(
    monkeypatch: pytest.MonkeyPatch, body: Any
) -> None:
    monkeypatch.setattr(runner.time, "time", lambda: synapse_beacon.emitted_at(runner.ROUND) + 9.0)
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda url, timeout: _Relay(body))
    monkeypatch.setattr(synapse_beacon, "verify", lambda round_number, signature: True)
    with pytest.raises(SystemExit, match="no relay served the round"):
        runner.fetch_signature(runner.ROUND)


def test_the_beacon_self_test_stops_a_broken_or_missing_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(synapse_beacon, "verify", lambda round_number, signature: False)
    with pytest.raises(SystemExit, match="rejects round"):
        runner.beacon_self_test()

    def missing(round_number: int, signature: str) -> bool:
        raise ModuleNotFoundError("No module named 'py_ecc'")

    monkeypatch.setattr(synapse_beacon, "verify", missing)
    with pytest.raises(SystemExit, match="cannot run"):
        runner.beacon_self_test()
    seen: list[tuple[int, str]] = []
    monkeypatch.setattr(synapse_beacon, "verify", lambda r, s: seen.append((r, s)) is None)
    runner.beacon_self_test()
    assert seen == [(runner.KNOWN_ROUND, runner.KNOWN_SIGNATURE)]


def test_the_known_round_is_the_beacon_fixtures() -> None:
    root = Path(__file__).resolve().parents[2]
    fixture = root / "tests" / "beacon" / "fixtures" / f"quicknet-round-{runner.KNOWN_ROUND}.json"
    assert json.loads(fixture.read_text(encoding="utf-8"))["signature"] == runner.KNOWN_SIGNATURE


def _args(**changes: Any) -> argparse.Namespace:
    values: dict[str, Any] = {
        "attempt": None,
        "dry_run": False,
        "rehearse": False,
        "worlds": list(runner.WORLDS),
        "workers": 10,
        "per_cell": 0,
        "cells": list(CELLS),
        "chunk": "0/1",
        "raw_out": None,
        "merge": None,
    }
    return argparse.Namespace(**{**values, **changes})


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        ({"dry_run": True, "chunk": "1-2"}, "expected i/m"),
        ({"dry_run": True, "chunk": "0/0", "raw_out": Path("p")}, "0 <= i < m"),
        ({"dry_run": True, "chunk": "2/2", "raw_out": Path("p")}, "0 <= i < m"),
        ({"attempt": "x"}, "as parts"),
        ({"attempt": "x", "merge": Path("p"), "worlds": ["W"]}, "both worlds"),
        ({"attempt": "x", "raw_out": Path("p"), "per_cell": 3}, "dry run"),
        ({"dry_run": True, "merge": Path("p"), "raw_out": Path("p")}, "exclusive"),
        ({"dry_run": True, "cells": ["S1"]}, "give --raw-out"),
        ({"dry_run": True, "chunk": "1/3"}, "give --raw-out"),
        ({"rehearse": True, "cells": ["N"]}, "no other option"),
    ],
)
def test_arguments_that_would_fail_after_the_round_are_refused_before_it(
    changes: dict[str, Any], refusal: str
) -> None:
    with pytest.raises(SystemExit, match=refusal):
        runner.validate(_args(**changes))


def test_sound_arguments_pass_and_give_the_chunk() -> None:
    assert runner.validate(_args(dry_run=True)) == (0, 1)
    assert runner.validate(_args(attempt="x", raw_out=Path("p"), chunk="3/10")) == (3, 10)
    assert runner.validate(_args(attempt="x", merge=Path("p"))) == (0, 1)
    assert runner.validate(_args(rehearse=True)) == (0, 1)


def test_another_numpy_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "NUMPY", "2.4.5")
    with pytest.raises(SystemExit, match="freeze C fixes numpy 2.4.5"):
        runner.validate(_args(dry_run=True))


def test_a_module_from_an_unfrozen_file_under_the_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "frozen_names", lambda: frozenset({"scripts/confirm/run.py"}))
    frozen = types.ModuleType("frozen_here")
    frozen.__file__ = str(tmp_path / "scripts" / "confirm" / "run.py")
    monkeypatch.setitem(sys.modules, "frozen_here", frozen)
    runner.audit_modules()
    planted = types.ModuleType("scripts_init_planted")
    planted.__file__ = str(tmp_path / "scripts" / "__init__.py")
    monkeypatch.setitem(sys.modules, "scripts_init_planted", planted)
    with pytest.raises(SystemExit, match=r"came from scripts/__init__\.py"):
        runner.audit_modules()


SIGNATURE = bytes(range(48))
HEAD = {"attempt": "nonce", "round": runner.ROUND, "signature": SIGNATURE.hex()}
N_C = dict.fromkeys(CELLS, 4)
ARMS = sorted(runner.specs("W"))


def _seed(j: int) -> int:
    return runner.replicate_seed(False, SIGNATURE, j)


def _row(j: int, index: int) -> dict[str, Any]:
    shake = {"argv": "argv", "environment": f"env-{index}", "workdir_empty": "True", "pid": "1"}
    return {
        "j": j,
        "seed": _seed(j),
        **{arm: {"handshake": {**shake, "spec": f"spec-{arm}"}} for arm in ARMS},
    }


def _parts() -> list[dict[str, Any]]:
    """Two parts that together hold every replicate of every cell, as ``--chunk 0/2`` and 1/2."""
    return [
        {
            **HEAD,
            "world": "W",
            "arms": list(ARMS),
            "code": code_digest(),
            "environment": {"numpy": runner.NUMPY},
            "rows": {
                cell: [_row(j, index) for j in range(N_C[cell]) if j % 2 == index] for cell in CELLS
            },
        }
        for index in (0, 1)
    ]


def test_whole_parts_merge_in_replicate_order() -> None:
    rows = runner.check_parts("W", _parts(), N_C, HEAD, _seed)
    assert all([row["j"] for row in rows[cell]] == [0, 1, 2, 3] for cell in CELLS)
    launches = runner.check_launches("W", _parts(), ARMS)
    assert launches["synapse"] == {"spec": "spec-synapse", "argv": "argv"}


def test_the_dry_run_stands_d3_in_for_the_round() -> None:
    assert [runner.replicate_seed(True, b"", j) for j in (0, 199)] == [
        seeds.explore_seed(448),
        seeds.explore_seed(647),
    ]
    assert runner.replicate_seed(False, SIGNATURE, 3) == runner.confirm_seed(SIGNATURE, 3)


def _shake(parts: list[dict[str, Any]], part: int, cell: str, k: int, arm: str) -> dict[str, Any]:
    handshake: dict[str, Any] = parts[part]["rows"][cell][k][arm]["handshake"]
    return handshake


@pytest.mark.parametrize(
    ("plant", "refusal"),
    [
        (lambda parts: parts[1].update(attempt="other"), "another attempt"),
        (lambda parts: parts[1].update(round=runner.ROUND - 1), "another attempt"),
        (lambda parts: parts[1].update(signature="00" * 48), "another attempt"),
        (lambda parts: parts[1].update(world="W-d1"), "world W-d1"),
        (lambda parts: parts[1]["code"].update(all="0" * 64), "other challenger code"),
        (lambda parts: parts[1]["arms"].pop(), "other arms"),
        (lambda parts: parts[1]["rows"].update(S4=[]), "holds cells"),
        (lambda parts: parts[1]["rows"]["S1"].pop(), "missing or repeated"),
        (lambda parts: parts[1]["rows"]["L"].append(_row(0, 1)), "repeated"),
        (lambda parts: parts[0]["rows"]["S3"][1].update(seed=_seed(2) + 1), "another seed"),
        (lambda parts: parts.clear(), "no parts"),
        (lambda parts: parts[1]["environment"].update(numpy="2.4.6"), "ran numpy 2.4.6"),
        (lambda parts: parts[1].pop("environment"), "ran numpy None"),
        (lambda parts: _shake(parts, 1, "N", 0, "synapse").update(spec="x"), "other inputs"),
        (lambda parts: _shake(parts, 0, "S2", 1, "lane").update(argv="--cells S2"), "other inputs"),
        (
            lambda parts: _shake(parts, 0, "L", 0, "lane").update(environment="env-x"),
            "several environments",
        ),
        (
            lambda parts: _shake(parts, 1, "S1", 0, "synapse").update(workdir_empty="False"),
            "not launched as frozen",
        ),
        (
            lambda parts: parts[0]["rows"]["N"][0]["lane"].pop("handshake"),
            "not launched as frozen",
        ),
    ],
)
def test_a_merge_refuses_a_part_that_is_not_this_attempts_whole(plant: Any, refusal: str) -> None:
    parts = _parts()
    plant(parts)
    with pytest.raises(RuntimeError, match=refusal):
        runner.check_parts("W", parts, N_C, HEAD, _seed)


def test_the_arms_name_every_component(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    params = {
        "trust": {"P/surge": "surge_today", "L/calm": "sensing"},
        "surge_threshold": 4096.0,
    }
    (tmp_path / "params-W.json").write_text(json.dumps(params), encoding="utf-8")
    monkeypatch.setattr(runner, "COMPOSITION", tmp_path)
    arms = runner.specs("W")
    assert sorted(arms) == [
        "lane",
        "synapse",
        "without:freshness_guardian",
        "without:sensing@L/calm",
        "without:surge_today@P/surge",
    ]
    lane_off = json.loads(str(arms["without:freshness_guardian"].inline))
    assert lane_off["lane_rule"] is False and lane_off["trust"] == params["trust"]
    no_surge = json.loads(str(arms["without:surge_today@P/surge"].inline))
    assert no_surge["trust"] == {"L/calm": "sensing"}


def _item_rows(costs: list[list[float]]) -> list[dict[str, Any]]:
    """Replicates whose three item arms carry ``costs[j]`` (SYNAPSE twice it, the lane thrice)."""
    return [
        {
            "j": j,
            "incumbent": {"item_cost": list(row)},
            "synapse": {"item_cost": [2.0 * c for c in row]},
            "lane": {"item_cost": [3.0 * c for c in row]},
        }
        for j, row in enumerate(costs)
    ]


def test_the_per_item_breakdown_is_each_items_mean_cost_per_arm() -> None:
    by_cell = {cell: _item_rows([[1.0, 0.1, 5.0], [3.0, 0.2, 0.0]]) for cell in CELLS}
    out = runner.per_item(["a", "b", "c"], by_cell)
    assert out["items"] == ["a", "b", "c"] and out["arms"] == ["incumbent", "synapse", "lane"]
    for cell in CELLS:
        means = out["cells"][cell]
        assert means["incumbent"] == [2.0, 0.15000000000000002, 2.5]
        assert means["synapse"] == [4.0, 0.30000000000000004, 5.0]
        assert means["lane"] == [6.0, 0.45000000000000007, 7.5]


def test_the_per_item_breakdown_refuses_rows_without_one_cost_per_item() -> None:
    short = {cell: _item_rows([[1.0, 2.0], [3.0, 4.0]]) for cell in CELLS}
    with pytest.raises(RuntimeError, match="not one per item"):
        runner.per_item(["a", "b", "c"], short)
    ragged = {cell: _item_rows([[1.0, 2.0, 3.0], [3.0, 4.0]]) for cell in CELLS}
    with pytest.raises(ValueError, match="zip"):
        runner.per_item(["a", "b", "c"], ragged)


def _arm_of(costs: list[float]) -> Arm:
    cost = np.asarray(costs, dtype=np.float64)
    zeros = np.zeros_like(cost)
    return Arm(cost, zeros + 0.9, zeros, zeros, zeros, zeros)


def test_the_shock_cells_difference_in_differences_cancels_ns_gap() -> None:
    n = 6
    incumbent = _arm_of([10.0] * n)
    synapse = {
        "N": [12.0] * n,
        "L": [10.0] * n,
        "S1": [9.0] * n,
        "S2": [12.0] * n,
        "S3": [13.5] * n,
    }
    runs = {cell: CellRun(14.5, incumbent, _arm_of(synapse[cell]), incumbent) for cell in CELLS}
    did = runner.shock_did(runs, b"sig")
    assert did["S1"] == {"mean": -3.0, "low95": -3.0, "high95": -3.0}
    assert did["S2"]["mean"] == 0.0 and did["S3"]["mean"] == 1.5
    varied = [9.0, 8.0, 10.0, 9.5, 7.0, 11.0]
    runs["S1"] = CellRun(16.0, incumbent, _arm_of(varied), incumbent)
    s1 = runner.shock_did(runs, b"sig")["S1"]
    assert s1["low95"] < s1["mean"] < s1["high95"]
    assert s1["mean"] == pytest.approx(sum(v - 10.0 - 2.0 for v in varied) / n)


def test_each_replicates_totals_are_kept() -> None:
    row = {
        "j": 3,
        "seed": 99,
        **{
            arm: {**dict.fromkeys(runner.ARM_FIELDS, 1.0), "report": {}}
            for arm in ("incumbent", *ARMS)
        },
    }
    rows = runner.replicate_rows({"N": [row]}, ARMS)["N"][0]
    assert rows["j"] == 3 and rows["seed"] == 99
    assert sorted(rows) == sorted(["j", "seed", "incumbent", *ARMS])
    assert all(sorted(rows[arm]) == sorted(runner.ARM_FIELDS) for arm in ("incumbent", *ARMS))


@pytest.fixture
def sealed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A private repository root for :mod:`scripts.confirm.outputs`."""
    monkeypatch.setattr(outputs, "ROOT", tmp_path)
    monkeypatch.setattr(outputs, "SEALED", tmp_path / "docs" / "truth" / "sealed")
    monkeypatch.setattr(outputs, "COMPOSITION", tmp_path / "docs" / "truth" / "composition")
    monkeypatch.setattr(
        outputs, "REHEARSALS", tmp_path / "docs" / "truth" / "confirm" / "rehearsals"
    )
    (tmp_path / "docs" / "truth" / "sealed").mkdir(parents=True)
    return tmp_path


def test_no_run_overwrites_a_frozen_file(sealed: Path) -> None:
    frozen = sealed / "docs" / "truth" / "composition" / "dry-run-W.json"
    assert outputs.record_dir() == sealed / "docs" / "truth" / "composition"
    outputs.write_json(frozen, {"before": "freeze C"})
    sums = sealed / "docs" / "truth" / "sealed" / "SHA256SUMS-C"
    sums.write_text("0" * 64 + " *docs/truth/composition/dry-run-W.json\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="refusing to overwrite docs/truth/composition"):
        outputs.write_json(frozen, {"after": "freeze C"})
    assert json.loads(frozen.read_text(encoding="utf-8")) == {"before": "freeze C"}
    assert outputs.record_dir() == sealed / "docs" / "truth" / "confirm" / "rehearsals"
    outputs.write_json(outputs.record_dir() / "dry-run-W.json", {"a": 1})
    written = sorted(p.name for p in outputs.record_dir().iterdir())
    assert written == ["dry-run-W.json"]


def test_the_rehearsal_exercises_every_outside_step_on_a_known_round(
    attempts: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    body = {"round": runner.KNOWN_ROUND, "signature": runner.KNOWN_SIGNATURE}
    asked: list[str] = []

    def urlopen(url: str, timeout: int) -> _Relay:
        asked.append(url)
        return _Relay(body)

    monkeypatch.setattr(runner.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(synapse_beacon, "verify", lambda round_number, signature: True)
    assert runner.rehearse() == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report["relays"].values()) == {"verified"}
    assert report["git"]["fetch"] == "ok" and report["git"]["head_on_main"] is True
    assert report["git"]["freeze_c_on_main"] == hashlib.sha256(SUMS_TEXT.encode()).hexdigest()
    assert all(url.endswith(f"/public/{runner.KNOWN_ROUND}") for url in asked)
    assert all(str(runner.ROUND) not in url for url in asked)
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda url, timeout: _Relay({}))
    assert runner.rehearse() == 1
