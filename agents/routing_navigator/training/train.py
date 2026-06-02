"""SYNAPSE Routing Navigator -- analytical "training" (ADR-042/043 analytical branch).

The CVRPTW solver (Clarke-Wright savings + 2-opt, ``models/cvrptw.py``) is a
deterministic combinatorial optimiser — there is no gradient loop to run, and
forcing one onto it would be the very anti-pattern ADR-042 exists to prevent. So
this agent satisfies the training contract the way ``inventory_sentinel`` does:
via **calibration**, not loss.

What it actually does (the substance):

  1. Generates a seeded set of realistic Bengaluru CVRPTW instances.
  2. Solves each with the production solver and measures the **optimality gap** —
     the ratio of a nearest-neighbour lower bound to the achieved tour distance
     (``ratio = LB / achieved`` ∈ (0, 1]; closer to 1 = nearer optimal).
  3. Calibrates a split-conformal prediction interval for the achieved cost given
     the lower bound, and measures its **held-out coverage** (``og_coverage``) —
     the analytical analogue of demand_prophet's conformal coverage (C40).
  4. Persists the empirical ratio distribution to a serving checkpoint
     (``routing_cvrptw.pt`` + ``.serving.json`` sidecar) so serving can map a live
     optimality gap to a *calibrated* confidence (ADR-043 §"calibration travels").

Returns a :class:`~synapse_common.training_contract.TrainResult` with
``kind="analytical"``: C37 exempts it from the gradient-step requirement, C40
consumes ``metrics.og_coverage``.

Run::

    python -m agents.routing_navigator.training.train [--smoke]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import structlog
from synapse_common.training_contract import TrainResult, save_checkpoint

from agents.routing_navigator.models.cvrptw import Stop, haversine_km, solve_cvrptw

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"
SERVING_NAME = "routing_cvrptw"

# Bengaluru centre (matches pipeline DEFAULT_DEPOT_*). Instances are sampled in a
# ~0.12° box around it — a realistic dark-store delivery radius.
DEPOT_LAT, DEPOT_LON = 12.97, 77.59
# 90%-nominal prediction interval, gated at a 0.80 floor (INV-RN-010). The 10%
# slack absorbs finite-sample noise so the gate is robust, mirroring
# demand_prophet's 0.90-nominal / 0.85-floor conformal margin.
ALPHA = 0.1


def _generate_instance(rng: np.random.Generator, n_stops: int) -> list[Stop]:
    """One seeded CVRPTW instance: depot at index 0, then ``n_stops`` orders."""
    depot = Stop(lat=DEPOT_LAT, lon=DEPOT_LON, demand=0.0)
    stops = [depot]
    for _ in range(n_stops):
        stops.append(
            Stop(
                lat=DEPOT_LAT + float(rng.uniform(-0.06, 0.06)),
                lon=DEPOT_LON + float(rng.uniform(-0.06, 0.06)),
                demand=float(rng.uniform(1.0, 6.0)),
                ready_min=0.0,
                due_min=float(rng.uniform(120.0, 480.0)),
                service_min=2.0,
            )
        )
    return stops


def _nn_lower_bound(stops: list[Stop], order_idx: list[int]) -> float:
    """Sum over visited stops of the haversine distance to the closest other stop.

    A valid, cheap lower bound on any tour over these stops: the achieved tour
    cannot beat the sum of each node's nearest-neighbour edge.
    """
    lb = 0.0
    n = len(stops)
    for idx in order_idx:
        s = stops[idx]
        lb += min(haversine_km(s, stops[j]) for j in range(n) if j != idx)
    return lb


def _solve_and_measure(stops: list[Stop]) -> tuple[float, float]:
    """Return (lower_bound, achieved_distance) for one solved instance."""
    routes = solve_cvrptw(stops, capacity=30.0, speed_kmh=22.0, max_route_min=480.0)
    achieved = sum(r.distance_km for r in routes)
    order_idx = list(range(1, len(stops)))
    lb = _nn_lower_bound(stops, order_idx)
    return lb, max(achieved, 1e-6)


def train(config: object | None = None, *, smoke: bool = False) -> TrainResult:
    """Calibrate the solver's optimality-gap interval; report held-out coverage."""
    seed = 42
    rng = np.random.default_rng(seed)
    # The solver is microseconds on small instances, so even "smoke" runs enough
    # instances for a stable coverage estimate (a 20-point test split is too noisy).
    n_instances = 120 if smoke else 400
    n_stops = 8 if smoke else 15

    ratios: list[float] = []
    lbs: list[float] = []
    achieved: list[float] = []
    for _ in range(n_instances):
        stops = _generate_instance(rng, n_stops)
        lb, ach = _solve_and_measure(stops)
        ratios.append(min(lb / ach, 1.0))
        lbs.append(lb)
        achieved.append(ach)

    ratios_arr = np.asarray(ratios, dtype=np.float64)
    lbs_arr = np.asarray(lbs, dtype=np.float64)
    ach_arr = np.asarray(achieved, dtype=np.float64)

    # Split-conformal coverage: fit the ratio interval on the calibration half,
    # predict the achieved-cost interval [lb/q_hi, lb/q_lo] on the test half, and
    # measure the empirical fraction covered (the analytical analogue of C40).
    mid = len(ratios_arr) // 2
    cal_ratio = ratios_arr[:mid]
    q_lo = float(np.quantile(cal_ratio, ALPHA / 2))
    q_med = float(np.quantile(cal_ratio, 0.5))
    q_hi = float(np.quantile(cal_ratio, 1.0 - ALPHA / 2))

    test_lb, test_ach = lbs_arr[mid:], ach_arr[mid:]
    pred_lo = test_lb / max(q_hi, 1e-6)  # higher ratio → lower achieved
    pred_hi = test_lb / max(q_lo, 1e-6)
    covered = (test_ach >= pred_lo - 1e-9) & (test_ach <= pred_hi + 1e-9)
    og_coverage = float(np.mean(covered)) if len(test_ach) else 0.0
    mean_gap = float(np.mean(ratios_arr))

    # Persist the empirical ratio distribution (the calibration) + the serving
    # sidecar so the $0 ModelRegistry source resolves a *calibrated* solver.
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    calibration = {
        "ratios": [round(r, 6) for r in sorted(ratios)],
        "q_lo": round(q_lo, 6),
        "q_med": round(q_med, 6),
        "q_hi": round(q_hi, 6),
        "n_instances": n_instances,
    }
    ckpt_path = CHECKPOINT_DIR / f"{SERVING_NAME}.pt"
    sha = save_checkpoint(calibration, ckpt_path)
    sidecar = {
        "version": f"{'smoke' if smoke else 'full'}_{sha}",
        "smoke": smoke,
        "solver": {"capacity": 30.0, "speed_kmh": 22.0, "max_route_min": 480.0},
    }
    (CHECKPOINT_DIR / f"{SERVING_NAME}.serving.json").write_text(
        json.dumps(sidecar, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )

    result = TrainResult.analytical(
        "routing_navigator",
        metrics={
            "og_coverage": og_coverage,
            "mean_optimality_gap": mean_gap,
            "n_instances": float(n_instances),
        },
        seed=seed,
    )
    logger.info("routing_calibration_complete", sha=sha, **result.to_dict()["metrics"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Routing Navigator optimality gap")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    train(smoke=args.smoke)


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
