"""Session-2 instrument: what a SHOCKED request does in the repaired consensus arm (tier 4 path)."""
from __future__ import annotations
import collections, dataclasses, json, logging, statistics, sys, time
import structlog
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
                    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))
from uplift import e5_suite  # noqa: E402
from uplift.interfaces import ShockParams  # noqa: E402

fields = {f.name: f for f in dataclasses.fields(ShockParams)}
print("ShockParams fields:", {n: str(f.type) for n, f in fields.items()})
kwargs = {}
for n, f in fields.items():
    if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
        continue
    kwargs[n] = 2.0 if "mult" in n or "factor" in n or "scale" in n else 1.0
shock = ShockParams(**kwargs)
print("shock used:", shock)
unit_costs = e5_suite._derive_unit_costs()
rows = []
for seed in [int(s) for s in sys.argv[2:]] or [296]:
    arm = e5_suite.e5_consensus_policy()
    sim = e5_suite.SupplyChainSimulation(seed=seed, world=e5_suite.e5_world())
    sim.start(); sim.set_policy(restock_threshold=e5_suite.comparator_restock_threshold())
    for hour in range(12):
        obs = dataclasses.replace(e5_suite.observe(sim, unit_costs=unit_costs), active_shock=shock)
        c0 = time.perf_counter(); outcome = arm.consult(obs); sec = time.perf_counter() - c0
        d = outcome.decision
        q = {str(k): float(v) for k, v in outcome.translated.reorder_quantities.items()}
        rows.append({"seed": seed, "hour": hour, "tier": str(d.tier), "binding": outcome.binding_agent,
                     "bucket": outcome.dispatch.bucket, "phase_reached": d.phase_reached,
                     "debate_rounds": d.debate_rounds if isinstance(d.debate_rounds, int) else len(d.debate_rounds),
                     "pareto_front": len(d.pareto_front or []), "escalated": bool(d.escalated_to_human),
                     "confidence": d.confidence, "seconds": sec, "ordered": sum(q.values()),
                     "proposals": {str(p.agent_name): [p.utility_score, p.confidence] for p in d.proposals},
                     "confirmations": list(d.execution_confirmations or [])[:8],
                     "trace_tail": [str(t)[:110] for t in (d.audit_trace or [])][-6:]})
        for sku, qty in sorted(q.items()):
            if qty > 0: sim.place_order(sku, qty)
        sim.advance(1.0)
json.dump(rows, open(sys.argv[1], "w", encoding="utf-8"), sort_keys=True, separators=(",", ":"))
C = collections.Counter
print("decisions:", len(rows), "tiers:", dict(C(r["tier"] for r in rows)), "binding:", dict(C(str(r["binding"]) for r in rows)))
print("buckets:", dict(C(r["bucket"] for r in rows)), "phase_reached:", dict(C(r["phase_reached"] for r in rows)))
print("debate_rounds:", dict(C(r["debate_rounds"] for r in rows)), "pareto_front sizes:", dict(C(r["pareto_front"] for r in rows)),
      "escalated:", dict(C(r["escalated"] for r in rows)))
print("seconds mean/max: %.3f / %.3f" % (statistics.mean(r["seconds"] for r in rows), max(r["seconds"] for r in rows)))
print("proposers per decision:", dict(C(len(r["proposals"]) for r in rows)))
print("first decision proposals:", json.dumps(rows[0]["proposals"]))
print("last decision proposals:", json.dumps(rows[-1]["proposals"]))
print("first confirmations:", rows[0]["confirmations"])
for t in rows[0]["trace_tail"]: print("  trace:", t)
