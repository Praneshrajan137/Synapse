"""Session-2 instrument: who binds each consensus decision over whole simulated days?

Runs the repaired tree's E5 consensus arm (reorders only) against the primary-cell twin for 24
hourly decisions per seed, in three ways of driving the world:
  probe   - the pathway probe's own schedule: 25 units of every SKU ordered every 3 hours
  deplete - nothing is ever ordered, so stock only falls
  closed  - the arm's own translated reorder quantities are placed, as an E5 replicate does
Read-only with respect to the repository. Run from the exported tree with PYTHONPATH set to it.

Usage: python scan_binding.py <out.json> <seed> [<seed> ...]
"""
from __future__ import annotations

import collections
import json
import logging
import statistics
import sys
import time

import structlog

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

from uplift import e5_suite  # noqa: E402

out_path = sys.argv[1]
seeds = [int(s) for s in sys.argv[2:]] or [e5_suite.E5_PROBE_TWIN_SEED]
unit_costs = e5_suite._derive_unit_costs()
HOURS = 24
rows: list[dict[str, object]] = []
first = True
t0 = time.perf_counter()
for seed in seeds:
    for mode in ("probe", "deplete", "closed"):
        arm = e5_suite.e5_consensus_policy()
        sim = e5_suite.SupplyChainSimulation(seed=seed, world=e5_suite.e5_world())
        sim.start()
        sim.set_policy(restock_threshold=e5_suite.comparator_restock_threshold())
        for hour in range(HOURS):
            obs = e5_suite.observe(sim, unit_costs=unit_costs)
            c0 = time.perf_counter()
            outcome = arm.consult(obs)
            seconds = time.perf_counter() - c0
            decision = outcome.decision
            if first:
                first = False
                fields = getattr(type(decision), "model_fields", None)
                print("decision fields:", sorted(fields) if fields else sorted(vars(decision)))
                print("outcome attrs:", [a for a in dir(outcome) if not a.startswith("_")])
            quantities = {str(k): float(v) for k, v in outcome.translated.reorder_quantities.items()}
            inv = {str(k): float(v) for k, v in obs.inventory.items()}
            rows.append(
                {
                    "seed": seed,
                    "mode": mode,
                    "hour": hour,
                    "tier": str(decision.tier),
                    "binding_agent": outcome.binding_agent,
                    "bucket": outcome.dispatch.bucket,
                    "proposals": {
                        str(p.agent_name): [p.utility_score, p.confidence] for p in decision.proposals
                    },
                    "ordered_total": sum(quantities.values()),
                    "skus_ordered": sum(1 for q in quantities.values() if q > 0),
                    "inv_min": min(inv.values()) if inv else None,
                    "inv_sum": sum(inv.values()),
                    "seconds": seconds,
                    "extra": {
                        k: (len(v) if hasattr(v, "__len__") and not isinstance(v, str) else v)
                        for k, v in (
                            (name, getattr(decision, name, None))
                            for name in ("debate_rounds", "pareto_front", "escalated", "violations",
                                         "guardrail_violations", "confidence", "utility_score",
                                         "consensus_reached", "phases", "degraded_agents")
                        )
                        if v is not None
                    },
                }
            )
            if mode == "probe" and hour % e5_suite.E5_PROBE_ORDER_EVERY_HOURS == 0:
                for sku in sorted(sim.inventory):
                    sim.place_order(sku, e5_suite.E5_PROBE_ORDER_UNITS)
            elif mode == "closed":
                for sku, quantity in sorted(quantities.items()):
                    if quantity > 0:
                        sim.place_order(sku, quantity)
            sim.advance(1.0)
elapsed = time.perf_counter() - t0

with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(rows, handle, sort_keys=True, separators=(",", ":"))

print(f"decisions={len(rows)} seeds={seeds} wall={elapsed:.1f}s")
print("binding agents:", dict(collections.Counter(str(r["binding_agent"]) for r in rows)))
print("tiers:", dict(collections.Counter(str(r["tier"]) for r in rows)))
print("buckets:", dict(collections.Counter(str(r["bucket"]) for r in rows)))
print("proposing agents per decision:", dict(collections.Counter(len(r["proposals"]) for r in rows)))  # type: ignore[arg-type]
per_agent: dict[str, list[tuple[float, float]]] = collections.defaultdict(list)
for r in rows:
    for agent, (utility, confidence) in r["proposals"].items():  # type: ignore[union-attr]
        per_agent[agent].append((utility, confidence))
for agent in sorted(per_agent):
    us = [u for u, _ in per_agent[agent]]
    cs = [c for _, c in per_agent[agent]]
    print(f"  {agent:22} n={len(us):4} utility min/med/max={min(us):.3f}/{statistics.median(us):.3f}/{max(us):.3f} "
          f"distinct={len(set(round(u, 6) for u in us)):3}  confidence min/max={min(cs):.3f}/{max(cs):.3f} "
          f"distinct={len(set(round(c, 6) for c in cs))}")
for mode in ("probe", "deplete", "closed"):
    sub = [r for r in rows if r["mode"] == mode]
    ordered = sum(1 for r in sub if r["skus_ordered"])  # type: ignore[misc]
    print(f"mode={mode:8} decisions={len(sub)} with-an-order={ordered} "
          f"inv_min over run: min={min(r['inv_min'] for r in sub):.1f} "  # type: ignore[type-var]
          f"mean consult seconds={statistics.mean(r['seconds'] for r in sub):.4f}")  # type: ignore[type-var]
print("extra fields seen:", dict(collections.Counter(k for r in rows for k in r["extra"])))  # type: ignore[union-attr]
