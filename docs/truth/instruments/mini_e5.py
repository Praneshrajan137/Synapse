"""Session-2 instrument: a miniature of E5 on one machine, each replicate run twice (R-43).

Run from an exported tree of the branch under study, with PYTHONPATH set to that tree and its
`packages` folder:  python mini_e5.py <replicates>

For each of the first <replicates> seeds E5 itself would use, this prices one 24-hour replicate
of the consensus arm and of the tuned control E with E5's own function
(`uplift.e5_suite.production_arm_cost`), then does both again with freshly built arms. It
reports whether the repeat is identical and the paired difference. It is a miniature: the same
physics, price and seeds as E5, far fewer replicates, no bootstrap, no controls.
"""
from __future__ import annotations

import logging
import statistics
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )
    from uplift import e5_suite
    from uplift.bprime_record import read_bprime_record

    replicates = int(argv[1]) if len(argv) > 1 else 5
    record = read_bprime_record(Path.cwd())
    world = e5_suite.e5_world()
    seeds = e5_suite.e5_replicate_seeds(replicates, record)
    rows = []
    started = time.perf_counter()
    for seed in seeds:
        costs = {}
        for label in ("consensus", "consensus_again", "tuned", "tuned_again"):
            if label.startswith("consensus"):
                policy = e5_suite.e5_consensus_policy()
            else:
                policy = e5_suite.e5_baseline_arms(record)[0].policy
            costs[label] = e5_suite.production_arm_cost(seed, policy, world)
        rows.append((seed, costs))
        print(
            f"seed {seed}: consensus {costs['consensus']:.6f} tuned {costs['tuned']:.6f} "
            f"difference {costs['tuned'] - costs['consensus']:+.6f} "
            f"repeat identical: consensus={costs['consensus'] == costs['consensus_again']} "
            f"tuned={costs['tuned'] == costs['tuned_again']}"
        )
    elapsed = time.perf_counter() - started
    consensus = [c["consensus"] for _, c in rows]
    tuned = [c["tuned"] for _, c in rows]
    diffs = [t - c for t, c in zip(tuned, consensus, strict=True)]
    print(f"replicates {len(rows)} wall {elapsed:.1f}s ({elapsed / (4 * len(rows)):.1f}s per replicate run)")
    print(f"mean consensus {statistics.mean(consensus):.4f}  mean tuned {statistics.mean(tuned):.4f}  "
          f"mean difference (tuned - consensus) {statistics.mean(diffs):+.4f}")
    print(f"consensus worse than tuned in {sum(d < 0 for d in diffs)} of {len(diffs)} replicates; "
          f"all repeats identical: "
          f"{all(c['consensus'] == c['consensus_again'] and c['tuned'] == c['tuned_again'] for _, c in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
