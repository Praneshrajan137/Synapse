"""Session-2 instrument: what a SHOCKED request does in the repaired consensus arm (tier 4).

Run from an exported tree of the branch under study, with PYTHONPATH set to that tree and its
`packages` folder:  python scan_shocked.py <out.json> [<seed> ...]

The `__main__` guard is load-bearing on Windows. The twin's Monte Carlo check starts worker
processes with the spawn method, which re-imports the main module. Without the guard every
worker re-ran this whole script before doing its work, and the first version of this file
reported 24 s per decision because of it (see docs/truth/LOG.md, M-20).
"""
from __future__ import annotations

import collections
import dataclasses
import json
import logging
import statistics
import sys
import time


def main(argv: list[str]) -> int:
    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )
    from uplift import e5_suite
    from uplift.interfaces import ShockParams

    # Every multiplier at 1.0: only the flag differs from an unshocked observation.
    shock = ShockParams(
        demand_multiplier=1.0,
        lead_time_multiplier=1.0,
        failure_rate_multiplier=1.0,
        spoilage_rate_multiplier=1.0,
    )
    unit_costs = e5_suite._derive_unit_costs()
    rows: list[dict[str, object]] = []
    for seed in [int(s) for s in argv[2:]] or [296]:
        arm = e5_suite.e5_consensus_policy()
        sim = e5_suite.SupplyChainSimulation(seed=seed, world=e5_suite.e5_world())
        sim.start()
        sim.set_policy(restock_threshold=e5_suite.comparator_restock_threshold())
        for hour in range(12):
            obs = dataclasses.replace(e5_suite.observe(sim, unit_costs=unit_costs), active_shock=shock)
            started = time.perf_counter()
            outcome = arm.consult(obs)
            seconds = time.perf_counter() - started
            decision = outcome.decision
            quantities = {str(k): float(v) for k, v in outcome.translated.reorder_quantities.items()}
            rounds = decision.debate_rounds
            rows.append(
                {
                    "seed": seed,
                    "hour": hour,
                    "tier": str(decision.tier),
                    "binding": outcome.binding_agent,
                    "bucket": outcome.dispatch.bucket,
                    "phase_reached": decision.phase_reached,
                    "debate_rounds": rounds if isinstance(rounds, int) else len(rounds),
                    "pareto_front": len(decision.pareto_front or []),
                    "escalated": bool(decision.escalated_to_human),
                    "seconds": seconds,
                    "ordered": sum(quantities.values()),
                    "proposals": {
                        str(p.agent_name): [p.utility_score, p.confidence] for p in decision.proposals
                    },
                    "confirmations": list(decision.execution_confirmations or [])[:8],
                    "twin": [str(t) for t in (decision.audit_trace or []) if str(t).startswith("twin")],
                }
            )
            for sku, quantity in sorted(quantities.items()):
                if quantity > 0:
                    sim.place_order(sku, quantity)
            sim.advance(1.0)
    with open(argv[1], "w", encoding="utf-8") as handle:
        json.dump(rows, handle, sort_keys=True, separators=(",", ":"))

    count = collections.Counter
    print("decisions:", len(rows), "tiers:", dict(count(r["tier"] for r in rows)),
          "binding:", dict(count(str(r["binding"]) for r in rows)))
    print("buckets:", dict(count(r["bucket"] for r in rows)),
          "debate_rounds:", dict(count(r["debate_rounds"] for r in rows)),
          "front sizes:", dict(count(r["pareto_front"] for r in rows)),
          "escalated:", dict(count(r["escalated"] for r in rows)))
    seconds_all = [float(r["seconds"]) for r in rows]  # type: ignore[arg-type]
    print("seconds mean/median/max: %.3f / %.3f / %.3f"
          % (statistics.mean(seconds_all), statistics.median(seconds_all), max(seconds_all)))
    print("twin verdicts:", dict(count(t for r in rows for t in r["twin"])))  # type: ignore[union-attr]
    print("first proposals:", json.dumps(rows[0]["proposals"]))
    print("first confirmations:", rows[0]["confirmations"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
