from __future__ import annotations

import pytest
import structlog
import structlog.testing

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos


class GPUMemoryManager:
    """Manages GPU memory with adaptive batch sizing and gradient checkpointing."""

    OOM_THRESHOLD_PERCENT = 85.0
    BATCH_REDUCTION_FACTOR = 0.5
    MEMORY_FREE_FACTOR = 0.6  # simulated fraction retained after recovery
    MIN_BATCH_SIZE = 4

    def __init__(self, total_memory_mb: int = 15360) -> None:
        self.total_memory_mb = total_memory_mb
        self.used_memory_mb: float = 0.0
        self.batch_size: int = 64
        self.gradient_checkpointing: bool = False
        self.oom_recovery_count: int = 0
        self._in_cooldown: bool = False

    @property
    def usage_percent(self) -> float:
        return (self.used_memory_mb / self.total_memory_mb) * 100.0

    def simulate_allocation(self, mb: float) -> None:
        self.used_memory_mb += mb
        self._in_cooldown = False

    def check_memory(self) -> dict:
        if self._in_cooldown:
            return {
                "status": "cooldown",
                "usage_percent": self.usage_percent,
                "batch_size": self.batch_size,
                "gradient_checkpointing": self.gradient_checkpointing,
            }

        if self.usage_percent >= self.OOM_THRESHOLD_PERCENT:
            return self._handle_oom()

        return {
            "status": "ok",
            "usage_percent": self.usage_percent,
            "batch_size": self.batch_size,
            "gradient_checkpointing": self.gradient_checkpointing,
        }

    def _handle_oom(self) -> dict:
        self.oom_recovery_count += 1
        self._in_cooldown = True
        logger.warning(
            "gpu_oom_approaching",
            usage_percent=self.usage_percent,
            action="reduce_batch_enable_checkpointing",
        )

        self.gradient_checkpointing = True
        self.batch_size = max(self.MIN_BATCH_SIZE, self.batch_size // 2)
        self.used_memory_mb *= self.MEMORY_FREE_FACTOR

        return {
            "status": "recovered",
            "action": "gradient_checkpointing_and_batch_reduction",
            "new_batch_size": self.batch_size,
            "gradient_checkpointing": True,
            "usage_percent": self.usage_percent,
        }


class TestGPUOOM:
    """Chaos logic validation: GPU OOM during RL training. Gradient
    checkpointing enabled, batch size reduced. Recovery SLA: <2 minutes."""

    def test_oom_triggers_recovery(self, chaos_clock) -> None:
        """OOM at 85% threshold triggers recovery mechanism."""
        mgr = GPUMemoryManager(total_memory_mb=15360)
        mgr.simulate_allocation(13500.0)

        chaos_clock.start()
        with structlog.testing.capture_logs() as captured:
            result = mgr.check_memory()

        assert result["status"] == "recovered"
        assert result["gradient_checkpointing"] is True
        assert result["new_batch_size"] < 64
        chaos_clock.assert_within_sla(120.0, "GPU OOM recovery")
        assert any(e.get("event") == "gpu_oom_approaching" for e in captured)

    def test_batch_size_halved(self) -> None:
        """Batch size is halved on OOM."""
        mgr = GPUMemoryManager()
        mgr.batch_size = 64
        mgr.simulate_allocation(14000.0)

        mgr.check_memory()

        assert mgr.batch_size == 32

    def test_minimum_batch_size_floor(self) -> None:
        """Batch size never goes below 4."""
        mgr = GPUMemoryManager()
        mgr.batch_size = 4
        mgr.simulate_allocation(14000.0)

        mgr.check_memory()

        assert mgr.batch_size == 4

    def test_memory_freed_after_recovery(self) -> None:
        """Memory usage drops after recovery actions."""
        mgr = GPUMemoryManager(total_memory_mb=15360)
        mgr.simulate_allocation(14000.0)
        pre_recovery = mgr.usage_percent

        mgr.check_memory()

        assert mgr.usage_percent < pre_recovery

    def test_normal_usage_no_recovery(self) -> None:
        """Below-threshold usage does not trigger recovery."""
        mgr = GPUMemoryManager(total_memory_mb=15360)
        mgr.simulate_allocation(10000.0)

        result = mgr.check_memory()

        assert result["status"] == "ok"
        assert mgr.gradient_checkpointing is False

    def test_cooldown_prevents_double_trigger(self) -> None:
        """Immediate re-check after recovery returns cooldown, not re-trigger."""
        mgr = GPUMemoryManager(total_memory_mb=15360)
        mgr.simulate_allocation(14000.0)

        first = mgr.check_memory()
        assert first["status"] == "recovered"

        second = mgr.check_memory()
        assert second["status"] == "cooldown"

    def test_cooldown_clears_on_new_allocation(self) -> None:
        """New allocation after recovery clears cooldown so monitoring resumes."""
        mgr = GPUMemoryManager(total_memory_mb=15360)
        mgr.simulate_allocation(14000.0)
        mgr.check_memory()

        mgr.simulate_allocation(100.0)
        result = mgr.check_memory()

        assert result["status"] != "cooldown"
