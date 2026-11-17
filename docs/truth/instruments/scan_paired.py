"""Session-2 instrument: same world states through the fast path (tier 2) and the full path (tier 4)."""
from __future__ import annotations
import cProfile, dataclasses, json, logging, pstats, sys, time
import structlog
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
                    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))
from uplift import e5_suite  # noqa: E402
from uplift.interfaces import ShockParams  # noqa: E402

shock = ShockParams(demand_multiplier=1.0, lead_time_multiplier=1.0, failure_rate_multiplier=1.0,
                    spoilage_rate_multiplier=1.0)
unit_costs = e5_suite._derive_unit_costs()
fast, full = e5_suite.e5_consensus_policy(), e5_suite.e5_consensus_policy()
sim = e5_suite.SupplyChainSimulation(seed=296, world=e5_suite.e5_world())
sim.start(); sim.set_policy(restock_threshold=e5_suite.comparator_restock_threshold())
same = differ = 0
prof = cProfile.Profile()
for hour in range(16):
    obs = e5_suite.observe(sim, unit_costs=unit_costs)
    if hour in (5, 7, 9, 11, 13, 15):  # late enough for stock to have fallen, so orders are non-zero
        a = fast.consult(obs)
        t0 = time.perf_counter()
        if hour == 9:
            prof.enable()
        b = full.consult(dataclasses.replace(obs, active_shock=shock))
        if hour == 9:
            prof.disable()
        sec = time.perf_counter() - t0
        qa = {str(k): round(float(v), 6) for k, v in a.translated.reorder_quantities.items() if v}
        qb = {str(k): round(float(v), 6) for k, v in b.translated.reorder_quantities.items() if v}
        eq = qa == qb
        same += eq; differ += (not eq)
        print(f"hour {hour:2}: tier {a.decision.tier}->{b.decision.tier} bind {a.binding_agent}->{b.binding_agent} "
              f"orders fast={sum(qa.values()):.1f} over {len(qa)} skus, full={sum(qb.values()):.1f} over {len(qb)} skus, "
              f"identical={eq}, full-path seconds={sec:.1f}")
    sim.advance(1.0)   # nothing is ever ordered: stock only falls
print(f"paired states: {same + differ}; identical orders: {same}; different: {differ}")
stats = pstats.Stats(prof); stats.sort_stats("cumulative")
import io
buf = io.StringIO(); pstats.Stats(prof, stream=buf).sort_stats("cumulative").print_stats(45)
keep = [l for l in buf.getvalue().splitlines() if any(k in l for k in ("protocol.py", "monte_carlo", "twin", "debate", "pareto", "nsga", "escalat", "sleep", "wait", "ollama", "engine.py", "function calls"))]
print("\n".join(l[:170] for l in keep[:28]))
