"""Session-2 instrument: is the consensus arm's loss explained by one level? A sensitivity probe.

Run from an exported tree of the branch under study, with PYTHONPATH set to that tree and its
`packages` folder:  python sensitivity_level.py <replicates> <all|landed> <k> [<k> ...]

`all` scales every reading. `landed` scales only readings whose lead time comes from orders
that have landed (under one day), and leaves alone the readings still planned against the
24-hour prior, which already order far above the tuned rule's levels at the start of a run.

Nothing in the tree is edited. In this process only, the Inventory Sentinel's reading of its
request (`forecast_from_request`, as its handler imports it) is wrapped so that the lead-time
demand it plans against is multiplied by k, and its spread by sqrt(k) (the Poisson relation the
original keeps). k = 1 is the arm as it is. Each k is priced over the same seeds E5 uses, with
E5's own cost function, beside the tuned control E.

This is a what-if on the evaluation seeds themselves. It can show whether one level accounts
for the loss. It cannot show an uplift: a k chosen here is fitted to the seeds it is judged on.
"""
from __future__ import annotations

import logging
import math
import statistics
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )
    from agents.inventory_sentinel.a2a import handler as sentinel_handler
    from uplift import e5_suite
    from uplift.bprime_record import read_bprime_record

    replicates = int(argv[1])
    mode = argv[2]
    if mode not in {"all", "landed"}:
        raise SystemExit("mode must be 'all' or 'landed'")
    factors = [float(a) for a in argv[3:]] or [1.0]
    record = read_bprime_record(Path.cwd())
    world = e5_suite.e5_world()
    seeds = e5_suite.e5_replicate_seeds(replicates, record)
    original = sentinel_handler.forecast_from_request

    tuned = [
        e5_suite.production_arm_cost(seed, e5_suite.e5_baseline_arms(record)[0].policy, world)
        for seed in seeds
    ]
    print(f"mode={mode}; tuned control E: mean {statistics.mean(tuned):.4f} over {len(seeds)} seeds")
    for k in factors:

        def scaled(ctx, _k=k):  # type: ignore[no-untyped-def]
            forecast = original(ctx)
            if forecast is None:
                return None
            out = {}
            for sku, reading in forecast.items():
                changed = dict(reading)
                if mode == "landed" and float(changed.get("lead_time_days", 1.0)) >= 1.0:
                    out[sku] = changed
                    continue
                if "mean" in changed:
                    changed["mean"] = changed["mean"] * _k
                if "std" in changed:
                    changed["std"] = changed["std"] * math.sqrt(_k)
                out[sku] = changed
            return out

        sentinel_handler.forecast_from_request = scaled  # type: ignore[assignment]
        try:
            costs = [
                e5_suite.production_arm_cost(seed, e5_suite.e5_consensus_policy(), world)
                for seed in seeds
            ]
        finally:
            sentinel_handler.forecast_from_request = original  # type: ignore[assignment]
        diffs = [t - c for t, c in zip(tuned, costs, strict=True)]
        print(
            f"k={k:4.1f}: consensus mean {statistics.mean(costs):.4f}  "
            f"tuned minus consensus {statistics.mean(diffs):+.4f}  "
            f"consensus better in {sum(d > 0 for d in diffs)} of {len(diffs)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
