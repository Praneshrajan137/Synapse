"""
SYNAPSE Digital Twin — Mesa agent-based model for rider behavior.

RiderAgent models individual rider dynamics: shift schedules, fatigue accumulation,
and zone preferences. RiderModel manages the rider population across the network.
"""
from __future__ import annotations

import dataclasses
from enum import StrEnum
from typing import Any

import mesa
import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class ShiftType(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


SHIFT_HOURS: dict[ShiftType, tuple[int, int]] = {
    ShiftType.MORNING: (6, 14),
    ShiftType.AFTERNOON: (14, 22),
    ShiftType.EVENING: (18, 2),
    ShiftType.NIGHT: (22, 6),
}


@dataclasses.dataclass
class RiderStats:
    """Accumulated rider statistics for a simulation step."""

    active_riders: int = 0
    fatigued_riders: int = 0
    avg_fatigue: float = 0.0
    deliveries_completed: int = 0


class RiderAgent(mesa.Agent):
    """Individual rider with shift schedules, fatigue, and zone preference."""

    def __init__(
        self,
        model: RiderModel,
        shift: ShiftType,
        zone_preferences: list[str],
        fatigue_rate: float = 0.05,
        recovery_rate: float = 0.15,
    ) -> None:
        super().__init__(model)
        self.shift = shift
        self.zone_preferences = zone_preferences
        self.fatigue_rate = fatigue_rate
        self.recovery_rate = recovery_rate
        self.fatigue: float = 0.0
        self.is_on_shift: bool = False
        self.deliveries_completed: int = 0

    def _is_shift_active(self, hour: int) -> bool:
        start, end = SHIFT_HOURS[self.shift]
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def step(self) -> None:
        hour = int(self.model.current_hour) % 24  # type: ignore[attr-defined]
        self.is_on_shift = self._is_shift_active(hour)

        if self.is_on_shift:
            self.fatigue = min(1.0, self.fatigue + self.fatigue_rate)
            if self.fatigue < 0.8:
                self.deliveries_completed += 1
        else:
            self.fatigue = max(0.0, self.fatigue - self.recovery_rate)


class RiderModel(mesa.Model):
    """Population-level model managing all rider agents."""

    def __init__(
        self,
        num_riders: int = 50,
        zones: list[str] | None = None,
        seed: int | None = None,
    ) -> None:
        super().__init__(seed=seed)
        self.zones = zones or [f"zone_{i}" for i in range(5)]
        self.current_hour: float = 6.0
        self.step_duration_hours: float = 1.0

        rng = np.random.default_rng(seed)
        shifts = list(ShiftType)

        for _ in range(num_riders):
            shift = rng.choice(shifts)  # type: ignore[arg-type]
            n_zones = rng.integers(1, min(4, len(self.zones) + 1))
            zone_prefs = list(rng.choice(self.zones, size=n_zones, replace=False))
            fatigue_rate = float(rng.uniform(0.03, 0.08))
            RiderAgent(
                model=self,
                shift=ShiftType(shift),
                zone_preferences=zone_prefs,
                fatigue_rate=fatigue_rate,
            )

        logger.info("rider_model_init", num_riders=num_riders, zones=len(self.zones))

    def step(self) -> None:
        self.agents.shuffle_do("step")
        self.current_hour += self.step_duration_hours

    def get_stats(self) -> RiderStats:
        agents = list(self.agents)
        active = [a for a in agents if a.is_on_shift]  # type: ignore[union-attr]
        fatigue_values = [a.fatigue for a in agents]  # type: ignore[union-attr]
        return RiderStats(
            active_riders=len(active),
            fatigued_riders=sum(1 for a in agents if a.fatigue > 0.7),  # type: ignore[union-attr]
            avg_fatigue=float(np.mean(fatigue_values)) if fatigue_values else 0.0,
            deliveries_completed=sum(a.deliveries_completed for a in agents),  # type: ignore[union-attr]
        )

    def run(self, steps: int = 24) -> list[dict[str, Any]]:
        """Run simulation for given number of steps and return per-step stats."""
        history: list[dict[str, Any]] = []
        for _ in range(steps):
            self.step()
            stats = self.get_stats()
            history.append(dataclasses.asdict(stats))
        logger.info("rider_model_complete", steps=steps, final_hour=self.current_hour)
        return history
