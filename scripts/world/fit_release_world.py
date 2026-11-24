"""Fit the release world to FreshRetailNet-50K: shape, skew and variability, with demand recovered.

``python -m scripts.world.fit_release_world --data DIR`` reads the dataset's two parquet files
(revision ``c374e85975c82816c495acfa904cc55ab14a47d3``, checked by sha256), and writes
``synapse_kernel/worlds/release_world.json`` and ``docs/truth/world/fit-report.json``.

**Reading the data (measured in session 5, record S5-M-11 and S5-M-12).** Hourly sales lie on a
lattice of step 0.1 (99.56% of positive values), and the Poisson noise floor of daily totals then
has slope 1.29 on ``1 / mean``: one unit is 0.1, so units = 10 x the value (truth finding F-35,
falsified). ``hours_stock_status`` is an out-of-stock flag: 1 = out of stock (it sums to
``stock_hour6_22_cnt`` over hours 6 to 21 on every row; sales occur in 28.7% of in-stock hours and
2.9% of out-of-stock ones). The paper's censoring indicator (its Eq. 1) is the complement (F-37).

**The named method: the exposure-weighted profile estimator.** For a series-day with in-stock hours
``A``, its demand level is ``sum_{h in A} sales_h / sum_{h in A} pi_h``: the Poisson maximum
likelihood estimate of the level under a known intraday profile ``pi`` from the hours the item could
sell in, the hourly-checkpoint form of the stock-out-timing estimator (Jain, Rudi and Wang,
Operations Research 63(1), 2015). An out-of-stock hour is recovered as ``max(sales, level x pi_h)``.
The profile, per category group and weekday, is re-estimated from the recovered demand, alternating
until it moves less than 1e-9.

**The masking check.** On held-out series (one in five, never used to fit the profile), every fully
in-stock day is masked two ways: MNAR, like a real stock-out (a stock level drawn as a share
``U(0.4, 0.95)`` of the day's total; every hour after cumulative sales reach it is hidden and the
crossing hour keeps only the units sold before the shelf emptied), and evening tails (from an onset
hour drawn from the data's own first-stock-out hours). The method's error on the hidden hours and on
the day totals is reported with 95% store-bootstrap intervals, beside two baselines under the same
masks: no recovery, and a shape-blind fill at the day's in-stock hourly mean. Pass condition, fixed
in the session-5 gate before this ran: signed bias of masked day totals (MNAR) within +-3%, its
interval inside +-5%, and a WAPE below both baselines'.

Everything that is not fitted is declared in :data:`CHOICES` with its reason or source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq
from scipy import stats

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
REVISION: Final[str] = "c374e85975c82816c495acfa904cc55ab14a47d3"
SHA256: Final[dict[str, str]] = {
    "train.parquet": "6706832db892bbae4969c19d87e07975d2543d2ba7d7d4756360654785de5a3d",
    "eval.parquet": "1b118840664280c6b88bffc84c80ee1f54c05d911e354b7599e5da10995e960e",
}
UNIT: Final[float] = 0.1  # one unit of sale, as the lattice and the noise floor show
ATTRIBUTION: Final[str] = (
    "Demand shape, item skew and day-level variability fitted to FreshRetailNet-50K "
    "(Wang, Gu, Long, Li, Shen, Fu, Zhou and Jiang, 'FreshRetailNet-50K: A Stockout-Annotated "
    "Censored Demand Dataset for Latent Demand Recovery and Forecasting in Fresh Retail', "
    "arXiv:2505.16319, 2025; https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K, "
    f"revision {REVISION}), licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). "
    "Changes: sales rescaled to units, stock-out hours recovered, aggregated into profiles, "
    "quantiles and variance components; no row of the dataset is redistributed."
)
#: Categories with at least this many series get a profile of their own; the rest share one.
OWN_PROFILE_SERIES: Final[int] = 1000
MIN_PROFILE_MASS: Final[float] = 0.25
DAY_FACTOR_POINTS: Final[int] = 16
FIT_SEED: Final[int] = 20261120
HOLDOUT_SHARE: Final[float] = 0.2

#: The declared, unfitted parameters, each with its kind and reason (PREREG-1 section 5).
CHOICES: Final[dict[str, dict[str, Any]]] = {
    "suppliers": {
        "fresh_morning": {"delivery_hours": [6], "lead_time_hours": 8},
        "chilled_morning": {"delivery_hours": [5], "lead_time_hours": 12},
        "hub_twice": {"delivery_hours": [6, 15], "lead_time_hours": 4},
    },
    "shelf_life_days": [1, 2, 3, 5, 7],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    """The columns the fit reads, as arrays: units per hour (float32) and out-of-stock flags."""
    table = pq.read_table(
        path,
        columns=[
            "store_id",
            "product_id",
            "first_category_id",
            "dt",
            "hours_sale",
            "hours_stock_status",
        ],
    )
    rows = table.num_rows
    sales = pc.list_flatten(table["hours_sale"]).to_numpy(zero_copy_only=False)
    status = pc.list_flatten(table["hours_stock_status"]).to_numpy(zero_copy_only=False)
    dates = pd.to_datetime(table["dt"].to_pandas())
    return {
        "store": table["store_id"].to_numpy(),
        "product": table["product_id"].to_numpy(),
        "category": table["first_category_id"].to_numpy(),
        "date": dates.dt.strftime("%Y-%m-%d").to_numpy(),
        "dow": dates.dt.dayofweek.to_numpy().astype(np.int64),
        "units": (sales.reshape(rows, 24) / UNIT).astype(np.float64),
        "oos": status.reshape(rows, 24).astype(bool),
    }


def category_groups(category: np.ndarray, series_key: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Each row's profile group: its category if it has enough series, else ``other``."""
    frame = pd.DataFrame({"category": category, "key": series_key})
    counts = frame.drop_duplicates().groupby("category").size()
    own = sorted(int(c) for c, n in counts.items() if n >= OWN_PROFILE_SERIES)
    names = [f"cat{c:02d}" for c in own] + ["other"]
    index = {c: k for k, c in enumerate(own)}
    group = np.array([index.get(int(c), len(own)) for c in category], dtype=np.int64)
    return group, names


def fit_profiles(
    units: np.ndarray, oos: np.ndarray, group: np.ndarray, dow: np.ndarray, groups: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """The exposure-weighted profile estimator, alternated to a fixed point.

    Rows must be sorted by (group, weekday): each iteration then works segment by segment, never
    copying the whole table. A series-day is used if its in-stock hours hold at least
    :data:`MIN_PROFILE_MASS` of the INITIAL profile (from fully in-stock days); the set is fixed
    before iterating, because a set re-decided each iteration let rows flip in and out and the full
    fit cycled instead of settling (session 5). Returns ``(pi, level, recovered, iterations)``:
    ``pi[g, dow, h]`` sums to one over ``h``; ``level`` per row (NaN for an unused row);
    ``recovered`` hourly demand per row.
    """
    segment = group * 7 + dow
    if bool(np.any(np.diff(segment) < 0)):
        raise ValueError("rows must be sorted by group and weekday")
    bounds = np.searchsorted(segment, np.arange(groups * 7 + 1))
    instock = ~oos
    pi = np.full((groups, 7, 24), 1.0 / 24.0)
    for s in range(groups * 7):
        a, b = bounds[s], bounds[s + 1]
        full = instock[a:b].all(axis=1)
        shares = units[a:b][full].sum(axis=0)
        if shares.sum() > 0:
            pi[s // 7, s % 7] = shares / shares.sum()
    level = np.full(units.shape[0], np.nan)
    recovered = units.copy()
    usable = np.zeros(units.shape[0], dtype=bool)
    for s in range(groups * 7):
        a, b = bounds[s], bounds[s + 1]
        usable[a:b] = (instock[a:b] * pi[s // 7, s % 7]).sum(axis=1) >= MIN_PROFILE_MASS
    for iteration in range(1, 500):
        new = pi.copy()
        for s in range(groups * 7):
            a, b = bounds[s], bounds[s + 1]
            if a == b:
                continue
            profile = pi[s // 7, s % 7]
            ins = instock[a:b]
            u = units[a:b]
            mass = (ins * profile).sum(axis=1)
            valid = usable[a:b] & (mass > 0.0)
            lev = np.where(valid, (u * ins).sum(axis=1) / np.where(valid, mass, 1.0), np.nan)
            rec = np.where(ins, u, np.maximum(u, profile[None, :] * np.nan_to_num(lev)[:, None]))
            level[a:b] = lev
            recovered[a:b] = rec
            shares = rec[valid].sum(axis=0)
            if shares.sum() > 0:
                new[s // 7, s % 7] = shares / shares.sum()
        moved = float(np.abs(new - pi).max())
        pi = new
        if moved < 1e-9:
            return pi, level, recovered, iteration
    raise RuntimeError("the profile did not settle in 500 iterations")


def recover_day(units: np.ndarray, hidden: np.ndarray, pi: np.ndarray) -> np.ndarray:
    """Recovered hourly demand for days whose ``hidden`` hours are out of stock, profile ``pi``."""
    shown = ~hidden
    mass = (pi * shown).sum(axis=1)
    level = (units * shown).sum(axis=1) / np.maximum(mass, 1e-12)
    return np.where(shown, units, np.maximum(units, level[:, None] * pi))


def masking_check(
    data: dict[str, Any],
    pi_fit: np.ndarray,
    pi_fallback: np.ndarray,
    held: np.ndarray,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """The named method against two baselines on held-out fully in-stock days, two masks each."""
    units = data["units"]
    oos = data["oos"]
    days = held & (~oos).all(axis=1) & (units.sum(axis=1) >= 2)
    true = units[days]
    pi = pi_fit[data["group"][days], data["dow"][days]]
    stores = data["store"][days]
    totals = true.sum(axis=1)
    # Evening-tail onsets from the data's own first out-of-stock hours (6 to 21).
    window = oos[:, 6:22]
    has = window.any(axis=1)
    first = np.argmax(window, axis=1)[has] + 6
    out: dict[str, Any] = {"days": int(days.sum()), "series_held_out_share": HOLDOUT_SHARE}
    key = data["key"][days]
    usual = pd.Series(totals).groupby(key).transform("mean").to_numpy()
    for family in ("mnar", "evening", "mnar_fixed_stock_post_hoc"):
        observed = true.copy()
        hidden = np.zeros_like(true, dtype=bool)
        if family.startswith("mnar"):
            if family == "mnar":
                stock = rng.uniform(0.4, 0.95, len(true)) * totals
            else:  # post hoc: a stock fixed before the day, from the series' usual day
                stock = rng.uniform(0.6, 1.4, len(true)) * usual
            cum = np.cumsum(true, axis=1)
            crossing = np.argmax(cum >= stock[:, None], axis=1)
            for r in np.nonzero(cum[:, -1] >= stock)[0]:
                h = crossing[r]
                before = cum[r, h - 1] if h > 0 else 0.0
                observed[r, h] = stock[r] - before
                observed[r, h + 1 :] = 0.0
                hidden[r, h:] = True
        else:
            onset = rng.choice(first, size=len(true))
            for r in range(len(true)):
                observed[r, onset[r] :] = 0.0
                hidden[r, onset[r] :] = True
        named = recover_day(observed, hidden, pi)
        fallback = recover_day(
            observed, hidden, pi_fallback[data["group"][days], data["dow"][days]]
        )
        shown = ~hidden
        in_stock_rate = (observed * shown).sum(axis=1) / np.maximum(shown.sum(axis=1), 1)
        uniform = np.where(hidden, np.maximum(observed, in_stock_rate[:, None]), observed)
        methods = {
            "exposure_profile": named,
            "exposure_profile_weekday_type_fallback": fallback,
            "no_recovery": observed,
            "uniform_fill": uniform,
        }
        out[family] = {
            "hidden_share_of_units": float((true * hidden).sum() / true.sum()),
            "methods": {
                name: _errors(estimate, true, hidden, stores, rng)
                for name, estimate in methods.items()
            },
        }

    def passes(method: str) -> bool:
        m = out["mnar"]["methods"][method]
        low, high = m["day_total_bias_ci95"]
        return bool(
            abs(m["day_total_bias"]) <= 0.03
            and low >= -0.05
            and high <= 0.05
            and m["hidden_wape"] < out["mnar"]["methods"]["no_recovery"]["hidden_wape"]
            and m["hidden_wape"] < out["mnar"]["methods"]["uniform_fill"]["hidden_wape"]
        )

    out["passes"] = passes("exposure_profile")
    out["fallback_passes"] = passes("exposure_profile_weekday_type_fallback")
    # The gate's rule when both fail: the smaller-bias method, labelled as failing. "Smaller bias"
    # is read as the smaller worst case over BOTH pre-declared mask families (the gate asked for
    # both); the post hoc family is reported, never used to choose.
    worst = {
        name: max(abs(out[f]["methods"][name]["day_total_bias"]) for f in ("mnar", "evening"))
        for name in ("exposure_profile", "exposure_profile_weekday_type_fallback", "uniform_fill")
    }
    if out["passes"]:
        out["used"] = "exposure_profile"
    elif out["fallback_passes"]:
        out["used"] = "exposure_profile_weekday_type_fallback"
    else:
        out["used"] = min(worst, key=lambda name: (worst[name], name))
    out["worst_day_total_bias_over_predeclared_families"] = worst
    out["label"] = "passes" if (out["passes"] or out["fallback_passes"]) else "failing"
    return out


def _errors(
    estimate: np.ndarray,
    true: np.ndarray,
    hidden: np.ndarray,
    stores: np.ndarray,
    rng: np.random.Generator,
) -> dict[str, Any]:
    err = (estimate - true) * hidden
    frame = (
        pd.DataFrame(
            {
                "store": stores,
                "abs": np.abs(err).sum(axis=1),
                "signed": err.sum(axis=1),
                "hidden_true": (true * hidden).sum(axis=1),
                "total": true.sum(axis=1),
            }
        )
        .groupby("store")
        .sum()
    )

    def ratios(table: pd.DataFrame) -> tuple[float, float, float]:
        hidden_true = float(table.hidden_true.sum())
        return (
            float(table["abs"].sum()) / hidden_true,
            float(table.signed.sum()) / hidden_true,
            float(table.signed.sum()) / float(table.total.sum()),
        )

    wape, wpe, day_bias = ratios(frame)
    boots = np.array(
        [ratios(frame.iloc[rng.integers(0, len(frame), len(frame))]) for _ in range(400)]
    )
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    return {
        "hidden_wape": wape,
        "hidden_wape_ci95": [float(lo[0]), float(hi[0])],
        "hidden_wpe": wpe,
        "hidden_wpe_ci95": [float(lo[1]), float(hi[1])],
        "day_total_bias": day_bias,
        "day_total_bias_ci95": [float(lo[2]), float(hi[2])],
    }


def rational_mean_one(values: np.ndarray, digits: int = 6) -> list[float]:
    """Rounded to ``digits`` decimals, the largest then adjusted so the mean is exactly one."""
    mean = float(np.mean(values))
    rounded = [round(float(v) / mean, digits) for v in values]
    total = sum(Fraction(str(v)) for v in rounded)
    target = Fraction(len(rounded))
    k = int(np.argmax(rounded))
    rounded[k] = float(Fraction(str(rounded[k])) + target - total)
    assert sum(Fraction(str(v)) for v in rounded) == target, "a profile must have mean exactly one"
    return rounded


def gamma_table(variance: float, points: int = DAY_FACTOR_POINTS) -> list[float]:
    """Equal-probability midpoints of a mean-one gamma with ``variance``, mean exactly one."""
    if variance <= 1e-9:
        return [1.0]
    shape = 1.0 / variance
    probs = (np.arange(points) + 0.5) / points
    return rational_mean_one(stats.gamma.ppf(probs, shape, scale=variance))


def dispersion(data: dict[str, Any], key: np.ndarray) -> dict[str, float]:
    """Pair share and day-level variance components from fully in-stock days (exact units)."""
    full = (~data["oos"]).all(axis=1)
    frame = pd.DataFrame(
        {
            "key": key[full],
            "store": data["store"][full],
            "date": data["date"][full],
            "dow": data["dow"][full],
            "x": data["units"][full].sum(axis=1),
        }
    )
    level = frame.groupby(["key", "dow"]).x.transform("mean")
    frame["y"] = frame.x / level.where(level > 0)
    stats_by = frame.groupby("key").agg(n=("x", "size"), mean=("x", "mean"), cv2=("y", "var"))
    used = stats_by[(stats_by.n >= 20) & (stats_by["mean"] >= 1.0)].dropna()
    design = np.vstack([1.0 / used["mean"].to_numpy(), np.ones(len(used))]).T
    slope, intercept = np.linalg.lstsq(design, used.cv2.to_numpy(), rcond=None)[0]
    pair_share = float(np.clip((slope - 1.0) / (3.0 - slope), 0.0, 0.5))
    total_var = float(max(intercept, 0.0))
    per_store_day = (
        frame.dropna()
        .groupby(["store", "date"])
        .agg(m=("y", "mean"), v=("y", "var"), n=("y", "size"))
    )
    per_store_day = per_store_day[per_store_day.n >= 5]
    store_var = float(
        max((per_store_day.m.var() - (per_store_day.v / per_store_day.n).mean()), 0.0)
    )
    item_var = float(max((1.0 + total_var) / (1.0 + store_var) - 1.0, 0.0))
    return {
        "series_used": int(len(used)),
        "slope": float(slope),
        "intercept": float(intercept),
        "pair_share": pair_share,
        "day_variance_total": total_var,
        "store_day_variance": store_var,
        "item_day_variance": item_var,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.world.fit_release_world")
    parser.add_argument(
        "--data", type=Path, required=True, help="folder with the two parquet files"
    )
    parser.add_argument("--items", type=int, default=300, help="items in the store (default 300)")
    parser.add_argument(
        "--world-out", type=Path, default=ROOT / "synapse_kernel/worlds/release_world.json"
    )
    parser.add_argument(
        "--report-out", type=Path, default=ROOT / "docs/truth/world/fit-report.json"
    )
    args = parser.parse_args(argv)
    for name, digest in SHA256.items():
        if sha256(args.data / name) != digest:
            print(f"REFUSED: {name} is not the revision this fit is pinned to")
            return 2
    rng = np.random.default_rng(FIT_SEED)
    data = load(args.data / "train.parquet")
    key = data["store"].astype(np.int64) * 10_000 + data["product"].astype(np.int64)
    data["group"], group_names = category_groups(data["category"], key)
    data["key"] = key
    order = np.lexsort((data["dow"], data["group"]))
    data = {name: values[order] for name, values in data.items()}
    key = key[order]
    series = np.unique(key)
    held_series = set(
        rng.choice(series, size=int(len(series) * HOLDOUT_SHARE), replace=False).tolist()
    )
    held = np.array([k in held_series for k in key])

    # The profile from the four fifths not held out, for the masking check.
    fit_rows = ~held
    pi_fit, _, _, _ = fit_profiles(
        data["units"][fit_rows],
        data["oos"][fit_rows],
        data["group"][fit_rows],
        data["dow"][fit_rows],
        len(group_names),
    )
    # The gate's named fallback: profiles by category group and weekday TYPE (Mon-Fri, Sat-Sun).
    weekend = (data["dow"] >= 5).astype(np.int64)
    by_type = np.lexsort((weekend, data["group"]))
    sub = by_type[fit_rows[by_type]]
    pi_type, _, _, _ = fit_profiles(
        data["units"][sub], data["oos"][sub], data["group"][sub], weekend[sub], len(group_names)
    )
    pi_fallback = np.stack([pi_type[:, 1 if d >= 5 else 0] for d in range(7)], axis=1)
    masking = masking_check(data, pi_fit, pi_fallback, held, rng)
    if masking["used"] != "exposure_profile":
        raise SystemExit(
            f"the masking rule chose {masking['used']!r}, which this fit does not build"
        )

    # The world's profile from all series.
    pi, level, recovered, iterations = fit_profiles(
        data["units"], data["oos"], data["group"], data["dow"], len(group_names)
    )
    valid = ~np.isnan(level)
    day_total = recovered.sum(axis=1)
    frame = pd.DataFrame(
        {
            "key": key,
            "store": data["store"],
            "group": data["group"],
            "dow": data["dow"],
            "total": day_total,
            "valid": valid,
        }
    )
    weekly = frame[frame.valid].groupby(["group", "dow"]).total.mean().unstack()
    profiles: dict[str, list[float]] = {}
    for g, name in enumerate(group_names):
        week = np.concatenate(
            [pi[g, d] * 24.0 * weekly.loc[g, d] / weekly.loc[g].mean() for d in range(7)]
        )
        profiles[name] = rational_mean_one(week)

    rates = frame[frame.valid].groupby(["key", "store", "group"]).total.mean().reset_index()
    store_median = rates.groupby("store").total.transform("median")
    rates["z"] = rates.total / store_median
    reference = float(rates.groupby("store").total.median().median())
    share = rates.groupby("group").size() / len(rates)
    counts = np.floor(share * args.items).astype(int)
    for g in (
        (share * args.items - counts)
        .sort_values(ascending=False)
        .index[: args.items - counts.sum()]
    ):
        counts[g] += 1
    raw_unit_mean = float(data["units"].sum(axis=1).mean())
    disp = dispersion(data, key)

    # Holdout: the eval split (the 7 days after the train split).
    test = load(args.data / "eval.parquet")
    tkey = test["store"].astype(np.int64) * 10_000 + test["product"].astype(np.int64)
    known = dict(zip(key, data["group"], strict=True))
    other = len(group_names) - 1
    test["group"] = np.array([known.get(k, other) for k in tkey])
    torder = np.lexsort((test["dow"], test["group"]))
    test = {name: values[torder] for name, values in test.items()}
    tkey = tkey[torder]
    pi_test, level_test, recovered_test, _ = fit_profiles(
        test["units"], test["oos"], test["group"], test["dow"], len(group_names)
    )
    volume = np.array([(data["group"] == g).sum() for g in range(len(group_names))], dtype=float)
    l1 = np.abs(pi - pi_test).sum(axis=2).mean(axis=1)
    shape_error = float((l1 * volume).sum() / volume.sum())
    train_rate = frame[frame.valid].groupby("key").total.mean()
    test_rate = (
        pd.Series(
            recovered_test.sum(axis=1)[~np.isnan(level_test)], index=tkey[~np.isnan(level_test)]
        )
        .groupby(level=0)
        .mean()
    )
    both = train_rate.index.intersection(test_rate.index)
    level_ratio = float(
        np.median(test_rate.loc[both] / train_rate.loc[both].where(train_rate.loc[both] > 0))
    )

    # The store: items at evenly spaced quantiles of each group's within-store rate distribution.
    suppliers = CHOICES["suppliers"]
    group_volume = frame[frame.valid].groupby("group").total.sum().sort_values(ascending=False)
    load_by = dict.fromkeys(suppliers, 0.0)
    group_supplier: dict[int, str] = {}
    for g, vol in group_volume.items():
        target = min(load_by, key=lambda s: (load_by[s], s))
        group_supplier[int(g)] = target
        load_by[target] += float(vol)
    lives = CHOICES["shelf_life_days"]
    items = []
    for g, name in enumerate(group_names):
        z = np.sort(rates.loc[rates.group == g, "z"].to_numpy())
        n = int(counts.get(g, 0))
        for k in range(n):
            q = (k + 0.5) / n
            rate = round(float(np.quantile(z, q)) * reference, 4)
            life = lives[(k * 7 + g) % len(lives)] * 24
            items.append(
                {
                    "name": f"{name}-{k:03d}",
                    "supplier": group_supplier[g],
                    "rate_per_day": max(rate, 0.01),
                    "profile": name,
                    "shelf_life_hours": life,
                    "price": 1.0,
                }
            )
    world = {
        "schema": 1,
        "name": "release-world-1",
        "attribution": ATTRIBUTION,
        "items": items,
        "suppliers": [
            {
                "name": s,
                "delivery_hours": spec["delivery_hours"],
                "lead_time_hours": spec["lead_time_hours"],
            }
            for s, spec in suppliers.items()
        ],
        "profiles": profiles,
        "day_item_factors": gamma_table(disp["item_day_variance"]),
        "day_store_factors": gamma_table(disp["store_day_variance"]),
        "pair_share": round(disp["pair_share"], 4),
        "provenance": PROVENANCE,
    }
    report = {
        "dataset": {"revision": REVISION, "sha256": SHA256, "unit": UNIT},
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "fit_seed": FIT_SEED,
        "groups": group_names,
        "profile_iterations": iterations,
        "masking_check": masking,
        "holdout_eval_split": {
            "shape_l1_per_day_mean": shape_error,
            "median_level_ratio_eval_over_train": level_ratio,
        },
        "dispersion": disp,
        "rates": {
            "reference_store_median_units_per_day": reference,
            "series": int(len(rates)),
            "z_quantiles": {
                str(q): float(np.quantile(rates.z, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)
            },
            "raw_mean_units_per_series_day": raw_unit_mean,
            "recovered_mean_units_per_series_day": float(day_total[valid].mean()),
            "unrecoverable_series_days": int((~valid).sum()),
        },
        "store": {
            "items": len(items),
            "units_per_day": float(sum(i["rate_per_day"] for i in items)),
            "supplier_volume_share": {s: v / sum(load_by.values()) for s, v in load_by.items()},
        },
    }
    args.world_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.world_out.write_text(
        json.dumps(world, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    args.report_out.write_text(
        json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"masking": masking["passes"], "store": report["store"], "dispersion": disp},
            sort_keys=True,
        )
    )
    return 0


PROVENANCE: Final[dict[str, dict[str, str]]] = {
    "items.rate_per_day": {
        "kind": "fitted",
        "source": (
            "FreshRetailNet-50K: per-series mean recovered daily demand over its own store's "
            "median (within-store skew), evenly spaced quantiles per category group, times the "
            "median store's median"
        ),
    },
    "items.profile": {
        "kind": "fitted",
        "source": ("the item's category group's profile"),
    },
    "items.shelf_life_hours": {
        "kind": "chosen",
        "source": (
            "the data carries no shelf life: remaining life at receipt of 1, 2, 3, 5 or 7 days, "
            "spread evenly and independently of rate within each group (context, snippets only: "
            "3 to 9 days in van Donselaar and Broekmeulen 2025); one global scale is the "
            "pre-declared calibration knob"
        ),
    },
    "items.price": {
        "kind": "chosen",
        "source": (
            "unit prices: every term of J is proportional to price, so per-item decisions do "
            "not depend on it; the data carries no price"
        ),
    },
    "items.supplier": {
        "kind": "chosen",
        "source": (
            "category groups assigned to the three suppliers greedily by recovered volume, so a "
            "uniformly drawn supplier shock (S2, S3) strikes about a third of demand whichever "
            "is drawn"
        ),
    },
    "profiles": {
        "kind": "fitted",
        "source": (
            "FreshRetailNet-50K: exposure-weighted profile estimator per category group and "
            "weekday, alternated to a fixed point; weekday levels from recovered day totals"
        ),
    },
    "day_item_factors": {
        "kind": "fitted",
        "source": (
            "item-day variance from fully in-stock days (CV^2 intercept less the store-day "
            "component); gamma form chosen; 16 equal-probability points"
        ),
    },
    "day_store_factors": {
        "kind": "fitted",
        "source": (
            "store-day variance from co-movement of a store's series on fully in-stock days; "
            "gamma form chosen; 16 equal-probability points"
        ),
    },
    "pair_share": {
        "kind": "fitted",
        "source": (
            "slope s of CV^2 of daily totals on 1/mean across series: q = (s - 1) / (3 - s)"
        ),
    },
    "suppliers.delivery_hours": {
        "kind": "cited",
        "source": (
            "06:00 restock (FreshRetailNet-50K paper, section 3.2: stockouts below 2% after the "
            "6 AM restock); a hub's second delivery at 15:00 (dark stores restock 2-3 times a "
            "day, TechCrunch 2024, snippet); 05:00 for chilled goods chosen"
        ),
    },
    "suppliers.lead_time_hours": {
        "kind": "chosen",
        "source": (
            "order by 22:00 for a 06:00 fresh delivery, by 17:00 for 05:00 chilled, four hours "
            "from the hub: no source found for Indian dark stores"
        ),
    },
    "item_count": {
        "kind": "chosen",
        "source": (
            "300 items: many skewed items as sealed, within the browser's budget (stage C); the "
            "data's stores carry 50 sampled series at the median, not their full assortment"
        ),
    },
}


if __name__ == "__main__":
    sys.exit(main())
