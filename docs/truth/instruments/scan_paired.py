"""Session-2 instrument: the same world states through the fast path (tier 2) and the full path.

Run from an exported tree of the branch under study, with PYTHONPATH set to that tree and its
`packages` folder:  python scan_paired.py

Two arms are built the way E5 builds its consensus arm. A twin is advanced with nothing ever
ordered, so stock only falls and the orders asked for are non-zero. At six hours the same
observation is put to one arm as it is (tier 2) and to the other with a shock flag whose
multipliers are all 1.0 (tier 4). The orders are compared, and one full-path decision is
profiled. The `__main__` guard is load-bearing on Windows; see scan_shocked.py.
"""
from __future__ import annotations

import cProfile
import dataclasses
import io
import logging
import pstats
import sys
import time


def main() -> int:
    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )
    from uplift import e5_suite
    from uplift.interfaces import ShockParams

    shock = ShockParams(
        demand_multiplier=1.0,
        lead_time_multiplier=1.0,
        failure_rate_multiplier=1.0,
        spoilage_rate_multiplier=1.0,
    )
    unit_costs = e5_suite._derive_unit_costs()
    fast, full = e5_suite.e5_consensus_policy(), e5_suite.e5_consensus_policy()
    sim = e5_suite.SupplyChainSimulation(seed=296, world=e5_suite.e5_world())
    sim.start()
    sim.set_policy(restock_threshold=e5_suite.comparator_restock_threshold())
    same = differ = 0
    profile = cProfile.Profile()
    for hour in range(16):
        obs = e5_suite.observe(sim, unit_costs=unit_costs)
        if hour in (5, 7, 9, 11, 13, 15):
            t_fast = time.perf_counter()
            a = fast.consult(obs)
            fast_seconds = time.perf_counter() - t_fast
            if hour == 9:
                profile.enable()
            t_full = time.perf_counter()
            b = full.consult(dataclasses.replace(obs, active_shock=shock))
            full_seconds = time.perf_counter() - t_full
            if hour == 9:
                profile.disable()
            qa = {str(k): round(float(v), 6) for k, v in a.translated.reorder_quantities.items() if v}
            qb = {str(k): round(float(v), 6) for k, v in b.translated.reorder_quantities.items() if v}
            equal = qa == qb
            same += equal
            differ += not equal
            twin = [str(t) for t in (b.decision.audit_trace or []) if str(t).startswith("twin=")]
            print(
                f"hour {hour:2}: {a.decision.tier}->{b.decision.tier} "
                f"bind {a.binding_agent}->{b.binding_agent} "
                f"units fast={sum(qa.values()):.1f} full={sum(qb.values()):.1f} identical={equal} "
                f"seconds fast={fast_seconds:.3f} full={full_seconds:.3f} {twin}"
            )
        sim.advance(1.0)
    print(f"paired states: {same + differ}; identical orders: {same}; different: {differ}")
    buffer = io.StringIO()
    pstats.Stats(profile, stream=buffer).sort_stats("cumulative").print_stats(60)
    wanted = ("protocol.py", "monte_carlo", "pareto", "nsga2.py", "escalat", "wait", "engine.py",
              "debate", "function calls")
    lines = [ln for ln in buffer.getvalue().splitlines() if any(w in ln for w in wanted)]
    for line in lines[:22]:
        head, _, tail = line.rpartition("\\")
        print((head[:58] + " ..\\" + tail) if head and len(line) > 150 else line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
