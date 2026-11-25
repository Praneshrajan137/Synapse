"""The pre-gate instruments of truth session 6 (S6-M-03 to S6-M-06), on frozen arms only.

Before any SYNAPSE component existed on the release world, these instruments asked what each claim
could be won by (findings F-42 to F-46). They are committed here, hardened as the gate's attack
asked (finding 7): every instrument that counts its own calls checks, at every call, that the hour
it counted is the observation's hour of the week, and the three freeze asserts run before and after.
Development seeds k 1000-1063, a range no fit uses.

* **M1, cell L** (S6-M-03): each incumbent version's cost, fill and waste share; I2-L behind the
  guard around I2-P and around I2-N, with the clipped share; in N, I2-P against I2-N.
* **M2, cell S1** (S6-M-04): the gate's oracle, guarded around I2-P, told the surge only ``delta``
  hours after its onset (its end, size and items known), for ``delta`` in 0, 6, 12, 24, 48; and
  unguarded at 0 and 12.
* **M3, day-level clairvoyance** (S6-M-06): the cell's incumbent planning against the scenario's
  true expected hourly demand, day factors included, for today's hours only and for every hour;
  N with I2-N and with I2-P, L with I2-L.
* **M4, cell S1** (S6-M-05): the gate's oracle with foresight, guarded, as freeze W ran it.

``python -m scripts.challengers.instruments`` writes ``docs/truth/challengers/instruments.json``.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from synapse_kernel.release import (
    integrity,  # first, as freeze W's rule asks
    seeds,
)
from synapse_kernel.release.engine import run
from synapse_kernel.release.harness import price, scenarios
from synapse_kernel.release.incumbent import Incumbent, load_incumbent_tables
from synapse_kernel.release.objective import fill_rate, replicate_costs
from synapse_kernel.release.oracle import Guarded, ShockOracle, _single
from synapse_kernel.release.scenario import hourly_means
from synapse_kernel.release.world import HOURS_PER_DAY, HOURS_PER_WEEK, load_release_world

F64 = npt.NDArray[np.float64]
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "truth" / "challengers" / "instruments.json"
KS = range(1000, 1064)


def _check_hour(hour: int, obs: Any) -> None:
    """Refuse unless a counted absolute hour is the observation's hour of the week."""
    if hour % HOURS_PER_WEEK != obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day:
        raise RuntimeError("an instrument lost count of the decisions")


class DelayedOracle(ShockOracle):
    """The gate's oracle, told the shock only from its onset plus ``delay`` hours."""

    def __init__(self, *args: Any, delay: float = 0.0, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.delay = delay

    def _decide_one(self, obs: Any, r: int, scenario: Any) -> Any:
        _check_hour(self.hour, obs)
        shock = scenario.shock
        if shock.kind != "none" and self.hour < shock.onset_hour + self.delay:
            return Incumbent.decide(self, _single(obs, r))[0]
        return super()._decide_one(obs, r, scenario)


class Clairvoyant(Incumbent):
    """The incumbent planning against the scenario's true expected hourly demand."""

    def __init__(self, world: Any, tables: Any, batch: list[Any], today_only: bool) -> None:
        super().__init__(world, tables)
        self.today_only = today_only
        horizon = world.horizon_hours
        hours = np.arange(horizon + 4 * HOURS_PER_WEEK)
        self.tables_abs = tables.mean_table[hours % HOURS_PER_WEEK]
        self.true_abs: list[F64] = []
        for scenario in batch:
            full = self.tables_abs.copy()
            full[:horizon] = hourly_means(world, scenario.seed)
            self.true_abs.append(full)
        cutoffs = {h for s in world.suppliers for h in s.cutoff_hours}
        self.decision_hours = [h for h in range(horizon) if h % HOURS_PER_DAY in cutoffs]
        self.calls = 0

    def start(self, replicates: int) -> None:
        self.calls = 0

    def decide(self, obs: Any) -> Any:
        hour = self.decision_hours[self.calls]
        self.calls += 1
        _check_hour(hour, obs)
        rows = []
        saved = self.cumulative
        try:
            for r in range(obs.on_hand.shape[0]):
                plan = self.true_abs[r].copy()
                if self.today_only:
                    later = np.arange(plan.shape[0]) // HOURS_PER_DAY > hour // HOURS_PER_DAY
                    plan[later] = self.tables_abs[later]
                week_hour = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
                window = plan[hour - week_hour : hour - week_hour + 4 * HOURS_PER_WEEK]
                if window.shape[0] < 4 * HOURS_PER_WEEK:
                    extra = 4 * HOURS_PER_WEEK - window.shape[0]
                    window = np.concatenate([window, self.tables_abs[:extra]], axis=0)
                self.cumulative = np.concatenate(
                    [np.zeros((1, window.shape[1])), np.cumsum(window, axis=0)], axis=0
                )
                rows.append(Incumbent.decide(self, _single(obs, r))[0])
        finally:
            self.cumulative = saved
        return np.stack(rows)


def _summary(diff: F64) -> dict[str, float]:
    sd = float(diff.std(ddof=1))
    return {
        "mean": round(float(diff.mean()), 3),
        "sd": round(sd, 3),
        "se": round(sd / math.sqrt(diff.size), 3),
        "n": int(diff.size),
    }


def _clairvoyance(world: Any, batch: list[Any], policy: Any, base: Any) -> dict[str, Any]:
    out = run(world, batch, policy)
    costs = np.array(replicate_costs(world, out))
    base_costs = np.array(replicate_costs(world, base))
    waste = out.wasted.sum(axis=-1) / 7.0
    base_waste = base.wasted.sum(axis=-1) / 7.0
    n = costs.size

    def se(x: F64) -> float:
        return float(x.std(ddof=1)) / math.sqrt(n)

    diff = costs - base_costs
    waste_cost = (waste - base_waste) * 0.62
    fill = np.array(fill_rate(out)) - np.array(fill_rate(base))
    return {
        "mean_cost": round(float(costs.mean()), 3),
        "cost_minus_base": {"mean": round(float(diff.mean()), 3), "se": round(se(diff), 3)},
        "waste_at_cost_minus_base": {
            "mean": round(float(waste_cost.mean()), 3),
            "se": round(se(waste_cost), 3),
        },
        "fill_minus_base": {"mean": round(float(fill.mean()), 5), "se": round(se(fill), 5)},
        "waste_units_per_day": round(float(waste.mean()), 2),
    }


def main() -> None:
    started = time.perf_counter()
    world = load_release_world()
    tables = load_incumbent_tables()
    integrity.assert_frozen()
    integrity.assert_world_frozen(world)
    integrity.assert_tables_frozen(tables)
    ks = seeds.explore_seeds(KS)
    out: dict[str, Any] = {"seeds_k": [KS.start, KS.stop - 1]}

    batch_l = scenarios(world, "L", ks)
    arms = {
        name: price(world, batch_l, Incumbent(world, tables[name]))
        for name in ("I2-L", "I1-L", "I2-P", "I2-N")
    }
    base_l = np.array(arms["I2-L"].costs)
    m1: dict[str, Any] = {
        name: {
            "mean_cost": round(p.mean_cost, 3),
            "fill": round(float(np.mean(p.fill)), 4),
            "waste_share": round(float(np.mean(p.waste)), 4),
            "minus_I2L": _summary(np.array(p.costs) - base_l),
        }
        for name, p in arms.items()
    }
    for anchor in ("I2-P", "I2-N"):
        guarded = Guarded(Incumbent(world, tables["I2-L"]), Incumbent(world, tables[anchor]))  # type: ignore[arg-type]
        p = price(world, batch_l, guarded)
        m1[f"guard(I2-L, {anchor})"] = {
            "mean_cost": round(p.mean_cost, 3),
            "fill": round(float(np.mean(p.fill)), 4),
            "waste_share": round(float(np.mean(p.waste)), 4),
            "minus_I2L": _summary(np.array(p.costs) - base_l),
            "clipped_share": round(guarded.clipped / max(guarded.decisions, 1), 4),
        }
    out["M1_cell_L"] = m1
    batch_n = scenarios(world, "N", ks)
    pn = {n: price(world, batch_n, Incumbent(world, tables[n])) for n in ("I2-N", "I2-P")}
    out["N"] = {
        "I2-N": round(pn["I2-N"].mean_cost, 3),
        "I2-P": round(pn["I2-P"].mean_cost, 3),
        "I2-P_minus_I2-N": _summary(np.array(pn["I2-P"].costs) - np.array(pn["I2-N"].costs)),
        "fill_I2-N": round(float(np.mean(pn["I2-N"].fill)), 4),
        "fill_I2-P": round(float(np.mean(pn["I2-P"].fill)), 4),
    }

    batch_s1 = scenarios(world, "S1", ks)
    base_s1 = np.array(price(world, batch_s1, Incumbent(world, tables["I2-P"])).costs)
    m2: dict[str, Any] = {"I2-P_mean": round(float(base_s1.mean()), 3)}
    for delay in (0.0, 6.0, 12.0, 24.0, 48.0):
        oracle = DelayedOracle(world, tables["I2-P"], batch_s1, None, rule="gate", delay=delay)
        guarded = Guarded(oracle, Incumbent(world, tables["I2-P"]))
        gain = base_s1 - np.array(price(world, batch_s1, guarded).costs)
        m2[f"delay_{int(delay)}h_guarded"] = {
            **_summary(gain),
            "clipped": round(guarded.clipped / max(guarded.decisions, 1), 4),
        }
    for delay in (0.0, 12.0):
        oracle = DelayedOracle(world, tables["I2-P"], batch_s1, None, rule="gate", delay=delay)
        m2[f"delay_{int(delay)}h_unguarded"] = _summary(
            base_s1 - np.array(price(world, batch_s1, oracle).costs)
        )
    out["M2_S1_delayed_oracle"] = m2

    for cell, name in (("N", "I2-N"), ("N", "I2-P"), ("L", "I2-L")):
        batch = scenarios(world, cell, ks)
        base = run(world, batch, Incumbent(world, tables[name]))
        entry: dict[str, Any] = {
            "base_mean_cost": round(float(np.mean(replicate_costs(world, base))), 3),
            "base_waste_units_per_day": round(float(base.wasted.sum(axis=-1).mean() / 7), 2),
            "base_fill": round(float(np.mean(fill_rate(base))), 4),
        }
        for label, today in (("today_only", True), ("all_days", False)):
            policy = Clairvoyant(world, tables[name], batch, today)
            entry[label] = _clairvoyance(world, batch, policy, base)
        out[f"M3_{cell}_{name}"] = entry

    guarded = Guarded(
        ShockOracle(world, tables["I2-P"], batch_s1, None, rule="gate"),
        Incumbent(world, tables["I2-P"]),
    )
    gain = base_s1 - np.array(price(world, batch_s1, guarded).costs)
    out["M4_S1_gate_oracle_with_foresight_guarded"] = {
        "mean": round(float(gain.mean()), 3),
        "se": round(float(gain.std(ddof=1)) / math.sqrt(gain.size), 3),
        "clipped": round(guarded.clipped / max(guarded.decisions, 1), 4),
    }
    integrity.assert_frozen()
    integrity.assert_world_frozen(world)
    integrity.assert_tables_frozen(tables)
    out["seconds"] = round(time.perf_counter() - started, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("written", OUT, flush=True)


if __name__ == "__main__":
    main()
