"""The confirmatory runner's guarantees, each shown able to fail (truth session 6, stage D2).

* replicate ``j``'s seed is PREREG-1 section 5's, byte for byte (planted: ``j`` as 4 bytes);
* an attempt is refused unless its record exists, is on ``origin/main`` byte for byte, was not used
  by a results file, names R_C and the digest of the freeze C sums this checkout holds, and freeze
  C's checker passes (each refusal shown);
* the round is not asked for before it is emitted, a relay's signature that does not verify stops
  the run, and a relay serving another round is not used;
* a merge refuses a part of another attempt (attempt, round or signature), of another world, run
  with other challenger code or other arms, holding a cell outside the five, a missing or repeated
  replicate, or a replicate run with another seed than the round (or D3) gives it;
* the arms are SYNAPSE, its lane incumbent and one ablation per named component: the Freshness
  Guardian (the lane rule) and each trusted entry's decider;
* the per-item breakdown is each item's mean cost under the incumbent, SYNAPSE and the lane
  incumbent, and refuses rows that do not hold one cost per item.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
from typing import TYPE_CHECKING, Any

import pytest

import synapse_beacon
from scripts.challengers.measure import code_digest
from scripts.confirm import run as runner
from synapse_kernel.proof.analysis import CELLS
from synapse_kernel.release import seeds

if TYPE_CHECKING:
    from pathlib import Path


def test_the_seed_of_replicate_j_is_prereg_1s() -> None:
    signature = bytes(range(48))
    for j in (0, 1, 2, 199, 1999):
        digest = hashlib.sha256(
            b"synapse/prereg-1/confirm/" + signature + j.to_bytes(8, "big")
        ).digest()
        assert runner.confirm_seed(signature, j) == int.from_bytes(digest[:8], "big") >> 1
    planted = hashlib.sha256(b"synapse/prereg-1/confirm/" + signature + (5).to_bytes(4, "big"))
    assert runner.confirm_seed(signature, 5) != int.from_bytes(planted.digest()[:8], "big") >> 1


@pytest.fixture
def attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A private attempts and results folder, a stand-in ``git`` and freeze C checker."""
    root = tmp_path
    (root / "docs" / "truth" / "confirm" / "attempts").mkdir(parents=True)
    (root / "docs" / "truth" / "confirm" / "results").mkdir(parents=True)
    (root / "docs" / "truth" / "sealed").mkdir(parents=True)
    sums = root / "docs" / "truth" / "sealed" / "SHA256SUMS-C"
    sums.write_text("0" * 64 + " *docs/truth/sealed/FREEZE-C.md\n", encoding="utf-8", newline="\n")
    state: dict[str, Any] = {"published": {}, "checker": 0}
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
        return ""

    class Done:
        def __init__(self, code: int) -> None:
            self.returncode = code

    monkeypatch.setattr(runner, "_git", git)
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: Done(state["checker"]))
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


def test_an_attempt_without_a_record_is_refused(attempts: dict[str, Any]) -> None:
    with pytest.raises(SystemExit, match="no attempt record"):
        runner.check_attempt("bb")


def test_an_attempt_not_pushed_is_refused(attempts: dict[str, Any]) -> None:
    _write(attempts, "cc", publish=False)
    with pytest.raises(SystemExit, match="not on origin/main"):
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


class _Relay:
    """A stand-in relay response, served for every URL."""

    def __init__(self, body: dict[str, Any]) -> None:
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


def test_a_relay_serving_another_round_is_not_used(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"round": runner.ROUND - 1, "signature": "ab" * 48}
    monkeypatch.setattr(runner.time, "time", lambda: synapse_beacon.emitted_at(runner.ROUND) + 9.0)
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda url, timeout: _Relay(body))
    monkeypatch.setattr(synapse_beacon, "verify", lambda round_number, signature: True)
    with pytest.raises(SystemExit, match="no relay served the round"):
        runner.fetch_signature(runner.ROUND)


SIGNATURE = bytes(range(48))
HEAD = {"attempt": "nonce", "round": runner.ROUND, "signature": SIGNATURE.hex()}
N_C = dict.fromkeys(CELLS, 4)


def _seed(j: int) -> int:
    return runner.replicate_seed(False, SIGNATURE, j)


def _parts() -> list[dict[str, Any]]:
    """Two parts that together hold every replicate of every cell, as ``--chunk 0/2`` and 1/2."""
    arms = sorted(runner.specs("W"))
    return [
        {
            **HEAD,
            "world": "W",
            "arms": list(arms),
            "code": code_digest(),
            "rows": {
                cell: [{"j": j, "seed": _seed(j)} for j in range(N_C[cell]) if j % 2 == index]
                for cell in CELLS
            },
        }
        for index in (0, 1)
    ]


def test_whole_parts_merge_in_replicate_order() -> None:
    rows = runner.check_parts("W", _parts(), N_C, HEAD, _seed)
    assert all([row["j"] for row in rows[cell]] == [0, 1, 2, 3] for cell in CELLS)


def test_the_dry_run_stands_d3_in_for_the_round() -> None:
    assert [runner.replicate_seed(True, b"", j) for j in (0, 199)] == [
        seeds.explore_seed(448),
        seeds.explore_seed(647),
    ]
    assert runner.replicate_seed(False, SIGNATURE, 3) == runner.confirm_seed(SIGNATURE, 3)


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
        (lambda parts: parts[1]["rows"]["L"].append({"j": 0, "seed": _seed(0)}), "repeated"),
        (lambda parts: parts[0]["rows"]["S3"][1].update(seed=_seed(2) + 1), "another seed"),
        (lambda parts: parts.clear(), "no parts"),
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
