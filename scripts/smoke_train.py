"""Drive the CI smoke-train for every agent that has committed to a real loop.

This is the producer half of the ADR-042 two-tier training design. For each
agent in :data:`READY_AGENTS` it imports the agent's training entrypoint, runs it
in **smoke mode** (tiny seeded subset, <=2 epochs, CPU, <=5 min), and writes the
resulting :class:`~synapse_common.training_contract.TrainResult` to
``artifacts/training/<agent>.json``. The ``checkpoint_truth`` (C38) and
``calibration_truth`` (C40) gates then consume those artifacts.

Phase 0: :data:`READY_AGENTS` is empty — the driver writes nothing and the
runtime gates SKIP. Each agent is appended here in its ratchet PR (demand_prophet
first), at which point its smoke-train must produce a learned, checkpointed,
calibrated artifact or CI fails.

The driver never fabricates a result: an agent whose smoke-train raises is
reported and skipped (its gate then has no artifact and, if the agent is also in
the gate's committed set, fails there — not here). This keeps producing and
checking separate.

Run::

    python scripts/smoke_train.py            # train all READY_AGENTS
    python scripts/smoke_train.py demand_prophet   # train a subset
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import structlog

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ROOT / "artifacts" / "training"

# Run robustly whether invoked as `python scripts/smoke_train.py` (script dir on
# sys.path[0], repo root absent) or `python -m scripts.smoke_train`. Without this
# the `import agents.*` resolution fails with "No module named 'agents'".
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = structlog.get_logger(__name__)

# Agents whose training.train exposes a smoke path returning a TrainResult.
# Grows one per PR. demand_prophet = real gradient loop; inventory_sentinel =
# analytical (closed-form newsvendor; substance proven by conformal coverage);
# routing_navigator = analytical (CVRPTW solver; substance proven by optimality-
# gap coverage).
READY_AGENTS: list[str] = [
    "demand_prophet",
    "inventory_sentinel",
    "routing_navigator",
    "supplier_trust",
    "pricing_oracle",
    "disruption_shield",
    "freshness_guardian",
    "sustainability_agent",
]


def smoke_train_agent(agent: str) -> bool:
    """Run one agent's smoke-train; write its TrainResult artifact. Return success."""
    try:
        mod = importlib.import_module(f"agents.{agent}.training.train")
    except Exception as exc:  # noqa: BLE001 — a missing/broken train module is reported, not fatal
        logger.warning("smoke_train_import_failed", agent=agent, error=str(exc))
        return False

    train_fn = getattr(mod, "train", None)
    if train_fn is None:
        logger.warning("smoke_train_no_entrypoint", agent=agent)
        return False

    try:
        result = train_fn(smoke=True)  # type: ignore[call-arg]
    except TypeError:
        # Agent's train() does not yet accept smoke= — not ready.
        logger.warning("smoke_train_no_smoke_kwarg", agent=agent)
        return False
    except Exception as exc:  # noqa: BLE001 — surface a failing loop, do not mask it
        logger.error("smoke_train_failed", agent=agent, error=str(exc))
        return False

    to_dict = getattr(result, "to_dict", None)
    if not callable(to_dict):
        logger.warning("smoke_train_bad_result", agent=agent, type=type(result).__name__)
        return False

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / f"{agent}.json"
    out.write_text(
        json.dumps(to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    logger.info("smoke_train_artifact_written", agent=agent, path=str(out))
    return True


def main(argv: list[str]) -> int:
    agents = argv or READY_AGENTS
    if not agents:
        print("[--] smoke_train: no READY_AGENTS - nothing to train (Phase 0 posture).")
        return 0
    ok = 0
    for agent in agents:
        if smoke_train_agent(agent):
            ok += 1
            print(f"[OK] {agent}: smoke-train artifact written")
        else:
            print(f"[XX] {agent}: smoke-train did not produce a TrainResult")
    print(f"\nsmoke_train: {ok}/{len(agents)} agent(s) produced artifacts.")
    # Exit non-zero only if a *committed* agent failed to produce an artifact.
    return 0 if ok == len(agents) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
