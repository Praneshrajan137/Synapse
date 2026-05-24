"""CVRPTW solver — Capacitated Vehicle Routing with Time Windows.

Sprint-8 elevation (WS-8.2): replaces the previous nearest-neighbor stub
with a deterministic Clarke-Wright savings algorithm followed by a 2-opt
local-search polish. Pure NumPy + stdlib — zero-cost and dependency-light
(PyVRP is preferred when available; this is the always-on fallback).

The solver:
  1. Computes a haversine distance matrix (or accepts an OSRM matrix).
  2. Seeds with one route per stop.
  3. Iteratively merges two routes when the merge reduces total distance
     subject to capacity + time-window feasibility.
  4. Polishes each route with 2-opt segment reversal until no improvement.

Output: a list of routes, each a sequence of stop indices starting and
ending implicitly at the depot (index 0 by convention).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class Stop:
    lat: float
    lon: float
    demand: float = 1.0
    ready_min: float = 0.0
    due_min: float = 480.0
    service_min: float = 2.0


@dataclass
class Route:
    stops: list[int] = field(default_factory=list)  # indices into the stops list
    distance_km: float = 0.0
    duration_min: float = 0.0


def haversine_km(a: Stop, b: Stop) -> float:
    """Great-circle distance, kilometres."""
    R = 6371.0
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return float(2 * R * math.asin(min(1.0, math.sqrt(h))))


def build_distance_matrix(stops: Sequence[Stop]) -> np.ndarray:
    n = len(stops)
    M = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(stops[i], stops[j])
            M[i, j] = M[j, i] = d
    return M


def _route_distance(route: list[int], M: np.ndarray) -> float:
    """Distance from depot (0) → stops → depot."""
    if not route:
        return 0.0
    total = float(M[0, route[0]])
    for a, b in zip(route, route[1:], strict=False):
        total += float(M[a, b])
    total += float(M[route[-1], 0])
    return total


def _route_duration(
    route: list[int],
    M: np.ndarray,
    stops: Sequence[Stop],
    speed_kmh: float,
) -> float:
    """Total minutes including service. Sets `ready_min` waits implicitly."""
    if not route:
        return 0.0
    minutes_per_km = 60.0 / max(1e-3, speed_kmh)
    t = float(M[0, route[0]] * minutes_per_km)
    for i, idx in enumerate(route):
        t = max(t, stops[idx].ready_min)
        t += stops[idx].service_min
        if i + 1 < len(route):
            t += float(M[idx, route[i + 1]] * minutes_per_km)
    t += float(M[route[-1], 0] * minutes_per_km)
    return t


def _feasible(
    route: list[int],
    M: np.ndarray,
    stops: Sequence[Stop],
    *,
    capacity: float,
    speed_kmh: float,
    max_route_min: float,
) -> bool:
    if sum(stops[i].demand for i in route) > capacity:
        return False
    minutes_per_km = 60.0 / max(1e-3, speed_kmh)
    t = float(M[0, route[0]] * minutes_per_km) if route else 0.0
    for i, idx in enumerate(route):
        if t < stops[idx].ready_min:
            t = stops[idx].ready_min
        if t > stops[idx].due_min:
            return False
        t += stops[idx].service_min
        if i + 1 < len(route):
            t += float(M[idx, route[i + 1]] * minutes_per_km)
    t += float(M[route[-1], 0] * minutes_per_km) if route else 0.0
    return t <= max_route_min


def _two_opt(route: list[int], M: np.ndarray) -> list[int]:
    """Reverse every contiguous segment that strictly reduces distance."""
    if len(route) < 4:
        return route
    best = route[:]
    improved = True
    while improved:
        improved = False
        n = len(best)
        for i in range(0, n - 2):
            for j in range(i + 2, n):
                if j - i == 1:
                    continue
                a = 0 if i == 0 else best[i - 1]
                b = best[i]
                c = best[j - 1]
                d = best[j] if j < n else 0
                before = M[a, b] + M[c, d]
                after = M[a, c] + M[b, d]
                if after + 1e-9 < before:
                    best[i:j] = best[i:j][::-1]
                    improved = True
                    break
            if improved:
                break
    return best


def clarke_wright(
    stops: Sequence[Stop],
    M: np.ndarray,
    *,
    capacity: float = 30.0,
    speed_kmh: float = 22.0,
    max_route_min: float = 480.0,
    n_vehicles: int | None = None,
) -> list[list[int]]:
    """Clarke-Wright savings construction. Stops are indexed 1..N (0 = depot)."""
    n = len(stops) - 1
    if n <= 0:
        return []

    routes: dict[int, list[int]] = {i: [i] for i in range(1, n + 1)}
    in_route_of: dict[int, int] = {i: i for i in range(1, n + 1)}

    # Compute savings for every (i, j) pair.
    savings: list[tuple[float, int, int]] = []
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            s = float(M[0, i] + M[0, j] - M[i, j])
            savings.append((s, i, j))
    savings.sort(reverse=True)

    for s, i, j in savings:
        if s <= 0:
            break
        ri, rj = in_route_of[i], in_route_of[j]
        if ri == rj:
            continue
        # Only merge if i is a tail and j is a head (or vice versa).
        a = routes[ri]
        b = routes[rj]
        if a[-1] == i and b[0] == j:
            merged = a + b
        elif b[-1] == j and a[0] == i:
            merged = b + a
        else:
            continue
        if not _feasible(
            merged, M, stops, capacity=capacity, speed_kmh=speed_kmh, max_route_min=max_route_min
        ):
            continue
        routes[ri] = merged
        del routes[rj]
        for k in merged:
            in_route_of[k] = ri

    out = [_two_opt(r, M) for r in routes.values()]
    if n_vehicles is not None and len(out) > n_vehicles:
        # Truncate; in practice the client should escalate when this happens.
        out = sorted(out, key=lambda r: -sum(stops[i].demand for i in r))[:n_vehicles]
    return out


def solve_cvrptw(
    stops: Sequence[Stop],
    *,
    capacity: float = 30.0,
    speed_kmh: float = 22.0,
    max_route_min: float = 480.0,
    n_vehicles: int | None = None,
) -> list[Route]:
    """End-to-end: build matrix, savings, polish, return Route objects.

    `stops[0]` MUST be the depot. Returns one `Route` per vehicle.
    """
    M = build_distance_matrix(stops)
    raw = clarke_wright(
        stops,
        M,
        capacity=capacity,
        speed_kmh=speed_kmh,
        max_route_min=max_route_min,
        n_vehicles=n_vehicles,
    )
    return [
        Route(
            stops=r,
            distance_km=_route_distance(r, M),
            duration_min=_route_duration(r, M, stops, speed_kmh),
        )
        for r in raw
    ]


__all__ = [
    "Route",
    "Stop",
    "build_distance_matrix",
    "clarke_wright",
    "haversine_km",
    "solve_cvrptw",
]
