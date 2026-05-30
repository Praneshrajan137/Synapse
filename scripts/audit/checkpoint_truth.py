"""Make the SYNAPSE *checkpoint gap* mechanically visible (ADR-042, C38).

A training loop that takes real gradient steps (C37) is still not enough: the
weights must be *persisted* as a loadable, content-addressed artifact, or serving
has nothing to load (C39). This gate consumes the ``TrainResult`` JSON each
smoke-train writes to :data:`ARTIFACTS_DIR` and asserts, per agent:

  * a ``checkpoint_path`` was recorded and the file exists on disk;
  * its on-disk sha256 matches the recorded ``checkpoint_sha`` (determinism -
    two seeded smoke-trains of the same code produce the same bytes, E-S9-03
    discipline extended to weights).

With no artifacts present (the dev box, or a CI run before the smoke job), the
gate **SKIPs** - it never fabricates a pass. The runtime proof lives in the
``training-smoke`` CI job that produces the artifacts and then runs this gate.

Run::

    python -m scripts.audit.checkpoint_truth [--json|--check]
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts" / "training"

# Agents asserted to produce a checkpoint. Grows one per PR. Phase 0: empty.
CHECKPOINT_AGENTS: frozenset[str] = frozenset()


@dataclass
class Result:
    agent: str
    status: str  # ok | missing_file | sha_mismatch | no_artifact | no_checkpoint
    detail: str


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _check_artifact(agent: str, data: dict) -> Result:
    ckpt = data.get("checkpoint_path")
    sha = data.get("checkpoint_sha")
    if not ckpt or not sha:
        if data.get("kind") == "analytical":
            return Result(agent, "ok", "analytical agent - no checkpoint expected")
        return Result(agent, "no_checkpoint", "TrainResult recorded no checkpoint_path/sha")
    path = Path(ckpt)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return Result(agent, "missing_file", f"checkpoint {ckpt} not on disk")
    actual = _sha16(path)
    if actual != sha:
        return Result(agent, "sha_mismatch", f"recorded {sha}, on-disk {actual}")
    return Result(agent, "ok", f"{ckpt} sha={sha}")


def collect() -> tuple[Report, bool]:
    report = Report()
    any_artifact = False
    if ARTIFACTS_DIR.is_dir():
        for art in sorted(ARTIFACTS_DIR.glob("*.json")):
            any_artifact = True
            try:
                data = json.loads(art.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                report.results.append(Result(art.stem, "no_artifact", f"unreadable: {exc}"))
                continue
            report.results.append(_check_artifact(data.get("agent", art.stem), data))
    # Committed agents with no artifact at all are a regression in CI (the smoke
    # job should have produced one). Locally they simply SKIP.
    seen = {r.agent for r in report.results}
    for agent in sorted(CHECKPOINT_AGENTS - seen):
        report.results.append(Result(agent, "no_artifact", "committed agent produced no TrainResult"))
    return report, any_artifact


def run(*, as_json: bool = False, check: bool = False) -> int:
    report, any_artifact = collect()
    failures = [r for r in report.results if r.status in {"missing_file", "sha_mismatch", "no_checkpoint"}]
    # A committed agent missing its artifact is a failure only when some artifacts exist.
    if any_artifact:
        failures += [
            r for r in report.results
            if r.status == "no_artifact" and r.agent in CHECKPOINT_AGENTS
        ]

    if as_json:
        print(json.dumps({
            "summary": {
                "artifacts_found": any_artifact,
                "checked": len(report.results),
                "failures": len(failures),
            },
            "results": [r.__dict__ for r in report.results],
        }, indent=2, sort_keys=True))
    else:
        if not any_artifact and not CHECKPOINT_AGENTS:
            print("[--] checkpoint-truth: no training artifacts present (SKIP - run the smoke job)")
        for r in report.results:
            sym = {"ok": "[OK]"}.get(r.status, "[XX]" if r in failures else "[--]")
            print(f"{sym} {r.agent:<22} {r.status:<14} {r.detail}")
        print()
        print(f"Checkpoint-truth: {len(failures)} failure(s) across {len(report.results)} artifact(s).")

    if check:
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
