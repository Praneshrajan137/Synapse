"""The confirmatory runner's guarantees, each shown able to fail (truth session 6, stage D2).

* replicate ``j``'s seed is PREREG-1 section 5's, byte for byte (planted: ``j`` as 4 bytes);
* an attempt is refused unless its record exists, is on ``origin/main`` byte for byte, was not used
  by a results file, and freeze C's checker passes (each refusal shown);
* the arms are SYNAPSE, its lane incumbent and one ablation per named component: the Freshness
  Guardian (the lane rule) and each trusted entry's decider.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import pytest

from scripts.confirm import run as runner

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
    state: dict[str, Any] = {"published": {}, "checker": 0}
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "ATTEMPTS", root / "docs" / "truth" / "confirm" / "attempts")
    monkeypatch.setattr(runner, "RESULTS", root / "docs" / "truth" / "confirm" / "results")

    def git(*args: str) -> str:
        if args[0] == "show":
            path = args[1].split(":", 1)[1]
            if path not in state["published"]:
                raise SystemExit("not on origin/main")
            return str(state["published"][path])
        return ""

    class Done:
        def __init__(self, code: int) -> None:
            self.returncode = code

    monkeypatch.setattr(runner, "_git", git)
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: Done(state["checker"]))
    return {"root": root, "state": state}


def _write(attempts: dict[str, Any], nonce: str, publish: bool) -> None:
    text = json.dumps({"nonce": nonce, "round": runner.ROUND}) + "\n"
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
    with pytest.raises(SystemExit, match="origin/main"):
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
    with pytest.raises(SystemExit, match="freeze C"):
        runner.check_attempt("ff")


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
