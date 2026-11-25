"""The confirmatory analysis of PREREG-1, sections 6 and 7, exactly as sealed.

Written in truth session 6 (stage D1) from the sealed text alone, before any SYNAPSE number existed
on the release world, so no choice below could be bent toward a result. Every choice the sealed text
leaves open was fixed in that session's gate (section 7, item 11) before this file was written:

* **The resamples.** One generator, ``numpy.random.Generator(PCG64(s))``, ``s`` the first 8 bytes,
  big-endian, of ``SHA-256("synapse/prereg-1/bootstrap/" || sig)`` shifted right by one bit; cells
  in the order N, L, S1, S2, S3, each drawing ``integers(0, n_c, size=(10_000, n_c))``. Every
  statistic of a cell uses that cell's one index matrix, so the comparisons stay paired. A second
  world is analysed with its own generator re-created from the same ``s``.
* **Means are sequential sums.** The estimate and every resample mean add their values one by one
  in replicate order (``cumsum``) and divide by ``n``, so a resample equal to the estimate is found
  exactly, and the same bits come out on every platform.
* **BCa** (Efron 1987): ``z0`` from the share of resample means below the estimate, a resample equal
  to it counting one half; a share of 0 gives the smallest resample mean at both ends and a share of
  1 the largest; the acceleration from the jackknife, ``sum(d^3) / (6 sum(d^2)^(3/2))`` with ``d``
  the jackknife means' distances from their mean, and 0 when the denominator is 0; the endpoint at
  nominal level ``alpha`` is the resample means' quantile at ``Phi(z0 + (z0 + z) / (1 - a (z0 +
  z)))``, ``z = Phi^-1(alpha)``, by numpy's ``linear`` rule; past the formula's pole (``1 - a (z0 +
  z) <= 0``) an upper end takes level 1 and a lower end level 0, since there the formula stops being
  monotone and would pull an upper end below the estimate. When every value is equal the interval is
  that value. Phi from :class:`statistics.NormalDist`.
* **Levels.** Two-sided 95% means the endpoints at 0.025 and 0.975; a one-sided bound at level
  ``1 - gamma`` is the endpoint at ``gamma`` (lower) or ``1 - gamma`` (upper).
* **C1** (intersection-union, Berger 1982): in every cell, the upper end of the two-sided 95%
  interval of mean delta is below ``M_c`` and the lower end of the two-sided 95% interval of the
  mean fill-rate difference is above -0.01, both strict.
* **C2 and C3, one Holm family** (Holm 1979) at familywise one-sided 0.025: with ``h`` hypotheses
  not yet rejected, every one whose one-sided bound at level ``1 - 0.025/h`` clears its margin is
  rejected; repeat until a step rejects none. C2 per shock cell: the lower bound of mean ``-delta``
  above ``M_c``. C3 in L: the upper bound of the mean difference in waste at cost below ``-M_L`` and
  the lower bound of the mean fill-rate difference above -0.01, both at the step's level.
* **The autonomy mark** of D-4(a), beside C1: the upper end of the two-sided 95% interval of mean
  delta at most 0 and the lower end for fill at least -0.01. Reported against two comparators: the
  cell's selected incumbent (PREREG-1, literally) and SYNAPSE's own lane incumbent (the comparator
  its trust map uses; truth session 6, gate item 1).
* **Ablations:** a component has no measured effect when, in every cell, the two-sided 90% interval
  of mean ``J_without - J_SYNAPSE`` lies strictly inside ``(-M_c, M_c)``.
* **Replicates per cell** (section 6): ``s_c`` the sample standard deviation (``n - 1``) of the
  paired differences on the 32 validation seeds; ``n_c = min(2000, max(200, ceil((2 * 1.96 * s_c /
  M_c)^2)))``; ``s_c = 0`` gives 200.
* **numpy** is pinned by what matters, its stream: :func:`assert_stream_pinned` refuses a numpy
  whose bounded-integer draws differ from the frozen digest (measured on numpy 2.4.4).
"""

from __future__ import annotations

import dataclasses
import hashlib
import math
from statistics import NormalDist
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.world import MEASURED_DAYS

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

__all__ = [
    "BAND",
    "BOOTSTRAP_LABEL",
    "CELLS",
    "RESAMPLES",
    "Arm",
    "Boot",
    "CellRun",
    "analyse",
    "assert_stream_pinned",
    "bootstrap",
    "bootstrap_seed",
    "endpoint",
    "holm",
    "index_stream",
    "replicates_for",
    "sample_sd",
    "seq_mean",
    "stream_digest",
]

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]

#: PREREG-1 section 7's label for the bootstrap's generator.
BOOTSTRAP_LABEL: Final[bytes] = b"synapse/prereg-1/bootstrap/"
RESAMPLES: Final[int] = 10_000
CELLS: Final[tuple[str, ...]] = ("N", "L", "S1", "S2", "S3")
SHOCK_CELLS: Final[tuple[str, ...]] = ("S1", "S2", "S3")
FAMILY_ALPHA: Final[float] = 0.025
FILL_FLOOR: Final[float] = -0.01
MIN_REPLICATES: Final[int] = 200
MAX_REPLICATES: Final[int] = 2000
#: PREREG-1 section 2's primary weights: margin m, beyond-margin loss g, carrying rate r.
PRIMARY: Final[tuple[float, float, float]] = (0.38, 0.0, 0.25)
#: The 27-point sensitivity band (PREREG-1 section 2): m, g and r, all combinations.
BAND: Final[tuple[tuple[float, float, float], ...]] = tuple(
    (m, g, r) for m in (0.25, 0.38, 0.50) for g in (0.0, 0.5, 1.0) for r in (0.10, 0.25, 0.40)
)
#: Resamples handled at once, to bound memory; the result does not depend on it.
CHUNK: Final[int] = 1000
_NORMAL: Final[NormalDist] = NormalDist()

#: The golden stream that pins numpy's bounded-integer draws: this seed, 200 replicates per cell.
GOLDEN_SEED: Final[int] = 20261124
GOLDEN_N: Final[int] = 200
#: Its sha256, measured on numpy 2.4.4 (Windows, CPython 3.11.15), truth session 6.
GOLDEN_DIGEST: Final[str] = "1b3cf648752b35a595f32aa10cd8d0c6a6a558065cc3648b4ba4ababc95185bc"


# -- the resamples -------------------------------------------------------------------------------


def bootstrap_seed(signature: bytes, label: bytes = BOOTSTRAP_LABEL) -> int:
    """The first 8 bytes, big-endian, of ``SHA-256(label || signature)``, shifted right by one."""
    return int.from_bytes(hashlib.sha256(label + signature).digest()[:8], "big") >> 1


def index_stream(
    seed: int,
    sizes: Mapping[str, int],
    cells: Sequence[str] = CELLS,
    resamples: int = RESAMPLES,
) -> dict[str, I64]:
    """Each cell's ``(resamples, n_c)`` resample indices from one generator, cells in order.

    Raises:
        ValueError: A cell with fewer than two replicates.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    out: dict[str, I64] = {}
    for cell in cells:
        n = int(sizes[cell])
        if n < 2:
            raise ValueError(f"cell {cell} has {n} replicates; a bootstrap needs at least 2")
        out[cell] = rng.integers(0, n, size=(resamples, n), dtype=np.int64)
    return out


def stream_digest(indices: Mapping[str, I64], cells: Sequence[str] = CELLS) -> str:
    """A sha256 of the index matrices, cell by cell, as little-endian 64-bit integers."""
    digest = hashlib.sha256()
    for cell in cells:
        digest.update(cell.encode("ascii"))
        digest.update(np.ascontiguousarray(indices[cell], dtype="<i8").tobytes())
    return digest.hexdigest()


def assert_stream_pinned() -> None:
    """Refuse a numpy whose bounded-integer stream is not the one this analysis was frozen with.

    numpy may change ``Generator`` streams in a feature release (its compatibility policy), and the
    claims depend on the exact resamples, so the stream itself is checked, not a version string.

    Raises:
        RuntimeError: The golden stream's digest differs.
    """
    sizes = dict.fromkeys(CELLS, GOLDEN_N)
    digest = stream_digest(index_stream(GOLDEN_SEED, sizes))
    if digest != GOLDEN_DIGEST:
        raise RuntimeError(
            f"numpy {np.__version__} draws a different bootstrap stream ({digest[:16]}...) "
            f"from the frozen one ({GOLDEN_DIGEST[:16]}...): use the numpy it was frozen with"
        )


# -- means, the jackknife and BCa ----------------------------------------------------------------


def seq_mean(values: npt.ArrayLike) -> float:
    """The mean as a sequential sum in order, divided by the count."""
    v = np.asarray(values, dtype=np.float64)
    if v.ndim != 1 or v.size == 0:
        raise ValueError("a mean needs a non-empty vector")
    return float(np.cumsum(v)[-1] / v.size)


def resample_means(values: F64, indices: I64) -> F64:
    """Each resample's mean: its values summed sequentially in the resample's order, over ``n``."""
    rows, n = indices.shape
    out = np.empty(rows, dtype=np.float64)
    for start in range(0, rows, CHUNK):
        block = values[indices[start : start + CHUNK]]
        out[start : start + CHUNK] = np.cumsum(block, axis=1)[:, -1] / n
    return out


def jackknife_means(values: F64) -> F64:
    """Leave-one-out means, each a sequential sum of the other values in order."""
    n = values.size
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        rest = np.concatenate([values[:i], values[i + 1 :]])
        out[i] = np.cumsum(rest)[-1] / (n - 1)
    return out


def acceleration(values: F64) -> float:
    """The jackknife acceleration ``sum(d^3) / (6 sum(d^2)^(3/2))``; 0 if ``sum(d^2)`` is 0."""
    jack = [float(x) for x in jackknife_means(values)]
    centre = math.fsum(jack) / len(jack)
    d = [centre - x for x in jack]
    cubes = math.fsum(x * x * x for x in d)
    squares = math.fsum(x * x for x in d)
    if squares == 0.0:
        return 0.0
    return cubes / (6.0 * squares * math.sqrt(squares))


@dataclasses.dataclass(frozen=True)
class Boot:
    """One statistic's bootstrap: the mean of ``values`` and what BCa needs to bound it."""

    estimate: float
    means: F64
    """The resample means, in resample order."""
    share: float
    """Resample means below the estimate, ties counting one half, over the resample count."""
    z0: float
    accel: float
    constant: float | None
    """The common value when every value is equal, else ``None``."""


def bootstrap(values: npt.ArrayLike, indices: I64) -> Boot:
    """The bootstrap of the mean of ``values`` under the resample ``indices``.

    Raises:
        ValueError: ``values`` is not a finite vector as long as a resample.
    """
    v = np.asarray(values, dtype=np.float64)
    if v.ndim != 1 or v.size != indices.shape[1] or not bool(np.all(np.isfinite(v))):
        raise ValueError("values must be a finite vector, one value per replicate")
    estimate = seq_mean(v)
    constant = float(v[0]) if bool(np.all(v == v[0])) else None
    means = resample_means(v, indices)
    below = int(np.count_nonzero(means < estimate))
    ties = int(np.count_nonzero(means == estimate))
    share = (below + 0.5 * ties) / means.size
    if share == 0.0:
        z0 = -math.inf
    elif share == 1.0:
        z0 = math.inf
    else:
        z0 = _NORMAL.inv_cdf(share)
    accel = 0.0 if constant is not None else acceleration(v)
    return Boot(estimate, means, share, z0, accel, constant)


def endpoint(boot: Boot, alpha: float) -> float:
    """The BCa endpoint at nominal level ``alpha`` (below 0.5 a lower end, above it an upper)."""
    if boot.constant is not None:
        return boot.constant
    if boot.share == 0.0:
        level = 0.0
    elif boot.share == 1.0:
        level = 1.0
    else:
        z = _NORMAL.inv_cdf(alpha)
        denominator = 1.0 - boot.accel * (boot.z0 + z)
        if denominator <= 0.0:
            level = 1.0 if alpha > 0.5 else 0.0
        else:
            level = _NORMAL.cdf(boot.z0 + (boot.z0 + z) / denominator)
    return float(np.quantile(boot.means, level, method="linear"))


def interval95(boot: Boot) -> tuple[float, float]:
    """The two-sided 95% interval."""
    return endpoint(boot, 0.025), endpoint(boot, 0.975)


# -- Holm's procedure ----------------------------------------------------------------------------


def holm(
    clears: Mapping[str, Callable[[float], bool]], alpha: float = FAMILY_ALPHA
) -> tuple[frozenset[str], list[dict[str, Any]]]:
    """Holm's step-down as PREREG-1 section 7 states it.

    ``clears[name](gamma)`` says whether hypothesis ``name``'s one-sided bound at level
    ``1 - gamma`` clears its margin. With ``h`` hypotheses not yet rejected, every one that clears
    at ``gamma = alpha / h`` is rejected; the step repeats until it rejects none.
    """
    remaining = sorted(clears)
    rejected: set[str] = set()
    steps: list[dict[str, Any]] = []
    while remaining:
        h = len(remaining)
        gamma = alpha / h
        newly = [name for name in remaining if clears[name](gamma)]
        steps.append({"h": h, "gamma": gamma, "rejected": newly})
        if not newly:
            break
        rejected.update(newly)
        remaining = [name for name in remaining if name not in rejected]
    return frozenset(rejected), steps


# -- replicates per cell -------------------------------------------------------------------------


def sample_sd(values: npt.ArrayLike) -> float:
    """The sample standard deviation, ``n - 1`` in the denominator, from exactly rounded sums."""
    v = [float(x) for x in np.asarray(values, dtype=np.float64)]
    if len(v) < 2:
        raise ValueError("a standard deviation needs two values")
    centre = math.fsum(v) / len(v)
    return math.sqrt(math.fsum((x - centre) * (x - centre) for x in v) / (len(v) - 1))


def replicates_for(s_c: float, margin: float) -> int:
    """PREREG-1 section 6: ``min(2000, max(200, ceil((2 * 1.96 * s_c / M_c)^2)))``."""
    if not (math.isfinite(s_c) and s_c >= 0.0 and margin > 0.0):
        raise ValueError("s_c must be finite and >= 0, M_c > 0")
    if s_c == 0.0:
        return MIN_REPLICATES
    ratio = 2.0 * 1.96 * s_c / margin
    return min(MAX_REPLICATES, max(MIN_REPLICATES, math.ceil(ratio * ratio)))


# -- the claims ----------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Arm:
    """One arm's replicates in one cell, in replicate order (one value per replicate)."""

    cost: F64
    """J at the primary weights, money per store-day (``objective.replicate_costs``)."""
    fill: F64
    """Units filled over units demanded, all items pooled, measured days."""
    lost: F64
    """Price-weighted units of demand not filled, measured days."""
    wasted: F64
    """Price-weighted units discarded at expiry, measured days."""
    held: F64
    """Price-weighted unit-days on hand, measured days."""
    end_on_hand: F64
    """Units on hand at the end of the replicate (reported, never priced)."""

    def __post_init__(self) -> None:
        n = self.cost.size
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if value.ndim != 1 or value.size != n or not bool(np.all(np.isfinite(value))):
                raise ValueError(f"{field.name}: one finite value per replicate, as cost has")

    def priced(self, margin: float, beyond: float, carrying: float) -> F64:
        """J re-priced at other weights from the recorded totals (the band; decisions unchanged)."""
        out: F64 = (
            (margin + beyond) * self.lost
            + (1.0 - margin) * self.wasted
            + carrying * (1.0 - margin) / 365.0 * self.held
        ) / MEASURED_DAYS
        return out

    def waste_at_cost(self) -> F64:
        """``sum_i (1 - m) p_i W_i`` per store-day at the primary margin (claim C3)."""
        out: F64 = (1.0 - PRIMARY[0]) * self.wasted / MEASURED_DAYS
        return out


@dataclasses.dataclass(frozen=True)
class CellRun:
    """Everything the analysis needs from one cell of one world's confirmatory run."""

    margin: float
    """``M_c``, frozen at freeze W."""
    incumbent: Arm
    """The cell's selected incumbent (PREREG-1 section 3)."""
    synapse: Arm
    lane: Arm
    """SYNAPSE's own lane incumbent on the same seeds: the comparator of its trust map."""
    ablations: Mapping[str, Arm] = dataclasses.field(default_factory=dict)
    """SYNAPSE without each component named at freeze C."""
    clipped: int = 0
    """Challenger decisions the guard changed."""
    decisions: int = 0
    """Challenger decisions (item and decision point)."""


def _bounds(boot: Boot) -> dict[str, Any]:
    low, high = interval95(boot)
    return {
        "mean": boot.estimate,
        "low95": low,
        "high95": high,
        "high95_hex": high.hex(),
        "low95_hex": low.hex(),
    }


def analyse(runs: Mapping[str, CellRun], seed: int) -> dict[str, Any]:
    """Every claim, mark, ablation and band of PREREG-1 section 7 for one world's run.

    Raises:
        ValueError: A cell is missing, or its arms differ in length.
    """
    missing = [cell for cell in CELLS if cell not in runs]
    if missing:
        raise ValueError(f"cells missing: {missing}")
    sizes = {cell: runs[cell].synapse.cost.size for cell in CELLS}
    for cell in CELLS:
        run = runs[cell]
        arms = [run.incumbent, run.lane, *run.ablations.values()]
        if any(arm.cost.size != sizes[cell] for arm in arms):
            raise ValueError(f"cell {cell}: every arm needs the same replicates")
    indices = index_stream(seed, sizes)
    report: dict[str, Any] = {
        "seed": seed,
        "resamples": RESAMPLES,
        "replicates": sizes,
        "numpy": np.__version__,
        "cells": {},
    }
    delta: dict[str, Boot] = {}
    fill: dict[str, Boot] = {}
    for cell in CELLS:
        run, idx = runs[cell], indices[cell]
        delta[cell] = bootstrap(run.synapse.cost - run.incumbent.cost, idx)
        fill[cell] = bootstrap(run.synapse.fill - run.incumbent.fill, idx)
        lane_delta = bootstrap(run.synapse.cost - run.lane.cost, idx)
        lane_fill = bootstrap(run.synapse.fill - run.lane.fill, idx)
        d_low, d_high = interval95(delta[cell])
        f_low, f_high = interval95(fill[cell])
        entry: dict[str, Any] = {
            "margin": run.margin,
            "delta": _bounds(delta[cell]),
            "fill_difference": _bounds(fill[cell]),
            "c1": {
                "cost_upper_below_margin": d_high < run.margin,
                "fill_lower_above_floor": f_low > FILL_FLOOR,
            },
            "autonomy": {
                "against_cell_incumbent": d_high <= 0.0 and f_low >= FILL_FLOOR,
                "against_lane_incumbent": interval95(lane_delta)[1] <= 0.0
                and interval95(lane_fill)[0] >= FILL_FLOOR,
                "lane_delta": _bounds(lane_delta),
                "lane_fill_difference": _bounds(lane_fill),
            },
            "means": {
                name: {
                    "cost": seq_mean(arm.cost),
                    "fill": seq_mean(arm.fill),
                    "waste_at_cost": seq_mean(arm.waste_at_cost()),
                    "end_on_hand": seq_mean(arm.end_on_hand),
                }
                for name, arm in (
                    ("incumbent", run.incumbent),
                    ("synapse", run.synapse),
                    ("lane", run.lane),
                )
            },
            "clipped_share": (run.clipped / run.decisions) if run.decisions else 0.0,
            "clipped": run.clipped,
            "decisions": run.decisions,
        }
        entry["c1"]["passes"] = all(entry["c1"].values())
        entry["band"] = [
            {
                "m": m,
                "g": g,
                "r": r,
                **_bounds(
                    bootstrap(run.synapse.priced(m, g, r) - run.incumbent.priced(m, g, r), idx)
                ),
            }
            for m, g, r in BAND
        ]
        entry["ablations"] = {
            name: _ablation(bootstrap(arm.cost - run.synapse.cost, idx), run.margin)
            for name, arm in sorted(run.ablations.items())
        }
        report["cells"][cell] = entry
    report["C1"] = all(report["cells"][cell]["c1"]["passes"] for cell in CELLS)
    report["holm"] = _superiority(runs, indices, delta, fill)
    components = sorted({name for cell in CELLS for name in runs[cell].ablations})
    report["ablations"] = {
        name: {
            "no_measured_effect": all(
                report["cells"][cell]["ablations"].get(name, {}).get("inside", False)
                for cell in CELLS
            )
        }
        for name in components
    }
    return report


def _ablation(boot: Boot, margin: float) -> dict[str, Any]:
    low, high = endpoint(boot, 0.05), endpoint(boot, 0.95)
    return {
        "mean": boot.estimate,
        "low90": low,
        "high90": high,
        "inside": -margin < low and high < margin,
    }


def _superiority(
    runs: Mapping[str, CellRun],
    indices: Mapping[str, I64],
    delta: Mapping[str, Boot],
    fill: Mapping[str, Boot],
) -> dict[str, Any]:
    """C2 per shock cell and C3, one Holm family at one-sided 0.025."""
    gain = {
        cell: bootstrap(-(runs[cell].synapse.cost - runs[cell].incumbent.cost), indices[cell])
        for cell in SHOCK_CELLS
    }
    waste_l = bootstrap(
        runs["L"].synapse.waste_at_cost() - runs["L"].incumbent.waste_at_cost(), indices["L"]
    )
    margin_l = runs["L"].margin

    def c2(cell: str) -> Callable[[float], bool]:
        return lambda gamma: endpoint(gain[cell], gamma) > runs[cell].margin

    def c3(gamma: float) -> bool:
        return (
            endpoint(waste_l, 1.0 - gamma) < -margin_l and endpoint(fill["L"], gamma) > FILL_FLOOR
        )

    clears: dict[str, Callable[[float], bool]] = {f"C2-{cell}": c2(cell) for cell in SHOCK_CELLS}
    clears["C3"] = c3
    rejected, steps = holm(clears)
    bounds = {
        f"C2-{cell}": {"gain_mean": gain[cell].estimate, "margin": runs[cell].margin}
        for cell in SHOCK_CELLS
    }
    bounds["C3"] = {
        "waste_difference_mean": waste_l.estimate,
        "fill_difference_mean": fill["L"].estimate,
        "margin": margin_l,
    }
    for step in steps:
        gamma = step["gamma"]
        step["bounds"] = {
            **{f"C2-{c}": endpoint(gain[c], gamma) for c in SHOCK_CELLS},
            "C3-waste-upper": endpoint(waste_l, 1.0 - gamma),
            "C3-fill-lower": endpoint(fill["L"], gamma),
        }
    del delta  # C2 bounds -delta directly, as sealed ("the lower one-sided bound of mean -delta")
    return {
        "rejected": sorted(rejected),
        "C2": any(f"C2-{cell}" in rejected for cell in SHOCK_CELLS),
        "C2_cells": {cell: f"C2-{cell}" in rejected for cell in SHOCK_CELLS},
        "C3": "C3" in rejected,
        "steps": steps,
        "hypotheses": bounds,
    }
