"""SYNAPSE WorldRuntime — the standing, ticking digital-twin world (ADR-052).

This is the substrate that turns SYNAPSE from a request-response pipeline into an
autonomous agent system. It promotes the offline-only ``SupplyChainSimulation``
(``digital_twin/simulation/engine.py``) to a **long-lived, clock-advanced world** that:

  * **perceives** — ``perceive()`` returns a typed ``WorldState`` snapshot;
  * **is actuated** — ``apply_action(WorldAction)`` mutates real state (reorder / policy /
    price / disruption) and returns the *actual effect* (never a fake ``{"status":"ok"}``);
  * **evolves on its own** — a background clock thread advances the SimPy env, draws demand
    from a pluggable ``WorldSource`` (SimWorldSource now, ExternalFeedSource later), and
    depletes inventory.

Design notes
------------
* **SimPy is synchronous** (``env.run`` blocks), so the clock runs in a daemon thread and
  every perceive/act acquires one ``RLock``. The FastAPI event loop is never blocked.
* **Agent reorders are load-bearing.** ``start()`` disables the engine's built-in
  auto-restock (``restock_threshold=0``) so the *only* thing that replenishes stock is an
  agent's reorder decision flowing through ``apply_action``. If the agents do nothing,
  stock genuinely runs out and ``fill_rate`` falls — which is exactly the realized signal
  the outcome loop (P5) scores against.
* **Injectable sim** for testing: the default is the real engine; a test may inject a
  lightweight fake exposing the same surface. A fake used with a **non-seeded** source must
  accept ``start(external_demand=..., initial_inventory=...)``, because that is the call
  R4.9 requires (the opening stock comes from the source, never from a literal).
* **Honest degradation (I-7):** a dead clock thread makes ``perceive().clock_advancing``
  False; callers degrade rather than trust a frozen world.

Provenance (purpose-achievement-audit R4.2/R4.9, design AD-11)
--------------------------------------------------------------
``perceive()`` no longer hands back a state whose ``is_synthetic`` is pinned ``True``. It
reports the active source's declared class in ``source_class``, from which
``WorldState.is_synthetic`` is computed, and it reports ``degraded`` +
``degraded_reason`` from three things the runtime actually knows: the source's own last
poll (an unreachable feed), an absent opening stock, and a ``STUB`` source. A stub-driven
world is always degraded — an empty world must never read as a healthy one.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog
from synapse_common.world.models import SourceProvenance, WorldAction, WorldActionKind, WorldState
from synapse_common.world.source import INVENTORY_ABSENT, STUB_SOURCE, SimWorldSource

from digital_twin.config import TwinConfig
from digital_twin.simulation.engine import SupplyChainSimulation

if TYPE_CHECKING:
    from synapse_common.world.source import WorldSource

logger = structlog.get_logger(__name__)

_POLICY_KEYS = frozenset(
    {"dispatch_speed", "restock_threshold", "order_qty_mult", "demand_mult", "lead_time_mult"}
)
_SHOCK_KEYS = frozenset(
    {"failure_rate_multiplier", "spoilage_rate_multiplier", "lead_time_multiplier"}
)


class WorldRuntime:
    """One city's standing world: perceive + actuate + a self-advancing clock."""

    def __init__(
        self,
        *,
        city: str,
        sim: Any = None,
        source: WorldSource | None = None,
        config: TwinConfig | None = None,
        seed: int = 42,
        step_hours: float = 1.0,
        real_seconds_per_step: float = 5.0,
        store_ids: list[str] | None = None,
    ) -> None:
        self.city = city
        self._config = config or TwinConfig()
        self._sim: Any = sim if sim is not None else SupplyChainSimulation(
            config=self._config, seed=seed
        )
        self._seed = seed
        self._step_hours = float(step_hours)
        self._real_seconds_per_step = float(real_seconds_per_step)
        self._store_ids = store_ids or ["store_001"]
        self._source = source
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._started = False
        self._last_tick_monotonic: float | None = None
        self._last_arrivals = 0
        self._ticks = 0
        # Set at start() when a non-seeded source supplies no opening stock (R4.9). It is
        # persistent, not per-poll: a world that began with no stock stays a degraded
        # reading until it is restarted from a source that has some.
        self._inventory_degradation: str | None = None

    # ── lifecycle ───────────────────────────────────────────────────────

    def start(self, run_clock: bool = True) -> WorldRuntime:
        """Boot the world. ``run_clock=False`` lets tests drive ``tick()`` manually."""
        with self._lock:
            if not self._started:
                if self._source is None:
                    # No source given: a seeded world whose catalog is the sim's own stock,
                    # so the sim must boot first. Its literal opening stock is a declared
                    # part of the seeded scenario, which is why R4.9 does not reach it.
                    self._sim.start(external_demand=True)
                    skus = list(self._sim.inventory.keys()) or [f"sku_{i}" for i in range(10)]
                    self._source = SimWorldSource(
                        city=self.city,
                        store_ids=self._store_ids,
                        sku_ids=skus,
                        arrival_rate_per_min=self._config.order_arrival_rate,
                        seed=self._seed,
                    )
                elif self._source.provenance() is SourceProvenance.SEEDED:
                    self._sim.start(external_demand=True)
                else:
                    self._start_from_non_seeded_source(self._source)
                # Agent reorders are the ONLY replenishment (see module docstring).
                self._sim.set_policy(restock_threshold=0.0)
                self._started = True
                logger.info(
                    "world_started",
                    city=self.city,
                    skus=len(self._sim.inventory),
                    source=self._source.name,
                    source_class=self._source.provenance().value,
                    degraded_reason=self._inventory_degradation,
                )
        if run_clock and self._thread is None:
            self._running = True
            self._thread = threading.Thread(
                target=self._clock_loop, name=f"world-clock-{self.city}", daemon=True
            )
            self._thread.start()
        return self

    def _start_from_non_seeded_source(self, source: WorldSource) -> None:
        """Boot the world on stock the source supplies — or honestly on none (R4.9).

        The literal ``{sku_i: 100.0}`` default is *not* available here. When a non-seeded
        source supplies no inventory the sim starts empty and ``perceive()`` reports
        ``degraded`` with ``external_inventory_absent``, because a fabricated 100 units per
        SKU would be indistinguishable, downstream, from a real store's reported stock —
        and every KPI derived from it (fill rate, stockout risk) would be fiction.
        """
        opening = source.initial_inventory()
        if opening is None:
            self._inventory_degradation = INVENTORY_ABSENT
            self._sim.start(external_demand=True, initial_inventory={})
            logger.error(
                "world_initial_inventory_absent",
                city=self.city,
                source=source.name,
                substituted_default=False,
            )
            return
        self._inventory_degradation = None
        self._sim.start(external_demand=True, initial_inventory=dict(opening))

    def stop(self) -> None:
        self._running = False
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=5.0)
        self._thread = None

    # ── the clock ───────────────────────────────────────────────────────

    def tick(self) -> None:
        """Advance the world one step: draw demand from the source, then advance the sim."""
        with self._lock:
            if not self._started:
                self.start(run_clock=False)
            arrivals = (
                self._source.poll_arrivals(self._sim.sim_time_min, self._step_hours * 60.0)
                if self._source is not None
                else []
            )
            if arrivals:
                self._sim.inject_orders(len(arrivals))
            self._last_arrivals = len(arrivals)
            self._sim.advance(self._step_hours)
            self._last_tick_monotonic = time.monotonic()
            self._ticks += 1

    def _clock_loop(self) -> None:
        while self._running:
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 — a tick failure must not kill the clock (I-7)
                logger.error("world_clock_tick_failed", city=self.city, error=str(exc))
            time.sleep(self._real_seconds_per_step)

    def _clock_advancing(self) -> bool:
        if self._thread is not None:
            return self._thread.is_alive()
        return self._started  # manual-tick mode: live once started

    # ── perceive ────────────────────────────────────────────────────────

    def perceive(self) -> WorldState:
        """Snapshot the world as a typed ``WorldState`` (I-3)."""
        with self._lock:
            inv = self._sim.inventory
            m = self._sim.metrics
            sim_min = float(self._sim.sim_time_min)
            demand_rate = self._config.order_arrival_rate * float(
                getattr(self._sim, "demand_mult", 1.0)
            )
            source_class = (
                self._source.provenance() if self._source is not None else SourceProvenance.SEEDED
            )
            degraded_reason = self._degraded_reason(source_class)
        in_stock = sum(1 for v in inv.values() if v > 0.0)
        fill = (in_stock / len(inv)) if inv else 1.0
        created = int(m.orders_created)
        delivered = int(m.orders_delivered)
        return WorldState(
            city=self.city,
            sim_time_min=sim_min,
            inventory=inv,
            pending_orders=max(0, created - delivered),
            fill_rate=round(fill, 4),
            spoilage_rate=round(min(1.0, max(0.0, float(m.spoilage_rate))), 4),
            avg_delivery_min=round(float(m.avg_delivery_time_min), 2),
            restocks_triggered=int(m.restocks_triggered),
            demand_rate=round(demand_rate, 4),
            clock_advancing=self._clock_advancing(),
            # Declared by the source, never asserted here: `is_synthetic` is computed from
            # this value (AD-11), so there is no keyword a caller could pass to claim the
            # world is real.
            source_class=source_class,
            degraded=degraded_reason is not None,
            degraded_reason=degraded_reason,
        )

    def _degraded_reason(self, source_class: SourceProvenance) -> str | None:
        """First applicable degradation, most-recent condition first, else ``None``.

        Order matters only for which reason is reported, not for whether the state is
        degraded: the source's own last poll (an unreachable feed) is the live condition and
        wins over the boot-time absent-inventory reason. A ``STUB`` source that reports no
        degradation of its own still degrades here — a source that can never produce an
        arrival must not present an empty world as a healthy one (R4.8, I-7).
        """
        live = self._source.degradation() if self._source is not None else None
        if live is not None:
            return live
        if self._inventory_degradation is not None:
            return self._inventory_degradation
        if source_class is SourceProvenance.STUB:
            return STUB_SOURCE
        return None

    # ── actuate ─────────────────────────────────────────────────────────

    def apply_action(self, action: WorldAction) -> dict[str, Any]:
        """Apply an agent's action to the world; return the *actual* effect (no theater)."""
        with self._lock:
            effect = self._apply_locked(action)
        logger.info(
            "world_action_applied",
            city=self.city,
            kind=action.kind.value,
            decision_id=action.decision_id,
            effect=effect,
        )
        return {
            "status": "applied",
            "kind": action.kind.value,
            "city": self.city,
            "decision_id": action.decision_id,
            "effect": effect,
        }

    def _apply_locked(self, action: WorldAction) -> dict[str, Any]:
        kind = action.kind
        if kind is WorldActionKind.REORDER:
            qty = float(action.params.get("quantity", 0.0))
            inv = self._sim.inventory
            sku = action.sku_id or (next(iter(inv)) if inv else None)
            if sku is None:
                return {"error": "no_sku_to_reorder"}
            new_level = float(self._sim.add_stock(sku, qty))
            return {"sku_id": sku, "reordered": qty, "new_level": new_level}
        if kind is WorldActionKind.SET_POLICY:
            policy = {k: float(v) for k, v in action.params.items() if k in _POLICY_KEYS}
            self._sim.set_policy(**policy)
            return {"policy": policy}
        if kind is WorldActionKind.SET_PRICE_MULT:
            price_mult = float(action.params.get("price_mult", 1.0))
            # Higher price suppresses demand; bounded proxy demand_mult = 1/price.
            demand_mult = max(0.1, min(3.0, 1.0 / price_mult)) if price_mult > 0 else 1.0
            self._sim.set_policy(demand_mult=demand_mult)
            return {"price_mult": price_mult, "demand_mult": round(demand_mult, 4)}
        if kind is WorldActionKind.INJECT_DISRUPTION:
            shock = {k: float(v) for k, v in action.params.items() if k in _SHOCK_KEYS}
            self._sim.inject_shock(**shock)
            return {"shock": shock}
        return {"error": f"unknown_kind:{kind}"}

    def inject_disruption(
        self,
        *,
        failure_rate_multiplier: float = 1.0,
        spoilage_rate_multiplier: float = 1.0,
        lead_time_multiplier: float = 1.0,
    ) -> dict[str, Any]:
        """Convenience wrapper to shock the live world (used by tests + the demo)."""
        return self.apply_action(
            WorldAction(
                action_id=f"disrupt-{uuid4().hex[:8]}",
                kind=WorldActionKind.INJECT_DISRUPTION,
                city=self.city,
                params={
                    "failure_rate_multiplier": failure_rate_multiplier,
                    "spoilage_rate_multiplier": spoilage_rate_multiplier,
                    "lead_time_multiplier": lead_time_multiplier,
                },
            )
        )


# ── per-city registry (mirrors the orchestrator brownout-controller pattern) ──

_RUNTIMES: dict[str, WorldRuntime] = {}


def register_runtime(runtime: WorldRuntime) -> WorldRuntime:
    _RUNTIMES[runtime.city] = runtime
    return runtime


def get_runtime(city: str) -> WorldRuntime | None:
    return _RUNTIMES.get(city)


def all_runtimes() -> dict[str, WorldRuntime]:
    return dict(_RUNTIMES)


def reset_runtimes() -> None:
    """Stop + clear all registered runtimes (test teardown)."""
    for rt in list(_RUNTIMES.values()):
        rt.stop()
    _RUNTIMES.clear()
