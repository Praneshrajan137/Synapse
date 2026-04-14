from __future__ import annotations

import pytest
import structlog
import structlog.testing

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos


class OllamaHealthManager:
    """Manages Ollama process health and model fallback chain."""

    MODEL_FALLBACK_CHAIN = ["deepseek-r1:14b", "qwen2.5:7b", "phi3:mini"]
    HEALTHCHECK_INTERVAL_SECONDS = 2.0

    def __init__(self) -> None:
        self.current_model: str = self.MODEL_FALLBACK_CHAIN[0]
        self.process_alive: bool = True
        self.restart_count: int = 0
        self._chain_position: int = 0
        self.fallback_model: str | None = None

    def simulate_crash(self) -> None:
        """SIGKILL the Ollama process."""
        self.process_alive = False
        logger.error("ollama_process_killed", signal="SIGKILL")

    def healthcheck(self) -> dict:
        if not self.process_alive:
            return self._handle_crash()
        return {"healthy": True, "model": self.current_model}

    def _handle_crash(self) -> dict:
        logger.warning("ollama_crash_detected", action="auto_restart_with_fallback")
        self.restart_count += 1
        self.process_alive = True

        self._chain_position = min(
            self._chain_position + 1,
            len(self.MODEL_FALLBACK_CHAIN) - 1,
        )
        self.fallback_model = self.MODEL_FALLBACK_CHAIN[self._chain_position]
        self.current_model = self.fallback_model

        return {
            "healthy": True,
            "model": self.current_model,
            "restarted": True,
            "restart_count": self.restart_count,
            "fallback_model": self.fallback_model,
        }


class TestOllamaCrash:
    """Chaos logic validation: Ollama SIGKILL. Docker healthcheck detects and
    auto-restarts with progressively smaller model fallback. SLA: <5 seconds."""

    def test_crash_detected_and_restarted(self, chaos_clock) -> None:
        """Crash triggers auto-restart within SLA."""
        manager = OllamaHealthManager()

        manager.simulate_crash()
        assert manager.process_alive is False

        chaos_clock.start()
        with structlog.testing.capture_logs() as captured:
            result = manager.healthcheck()

        assert result["healthy"] is True
        assert result["restarted"] is True
        chaos_clock.assert_within_sla(5.0, "Ollama crash restart")
        assert any(e.get("event") == "ollama_crash_detected" for e in captured)

    def test_fallback_chain_progression(self) -> None:
        """Repeated crashes cascade through the fallback chain correctly."""
        manager = OllamaHealthManager()
        assert manager.current_model == "deepseek-r1:14b"

        manager.simulate_crash()
        r1 = manager.healthcheck()
        assert r1["model"] == "qwen2.5:7b"

        manager.simulate_crash()
        r2 = manager.healthcheck()
        assert r2["model"] == "phi3:mini"

        manager.simulate_crash()
        r3 = manager.healthcheck()
        assert r3["model"] == "phi3:mini", "Chain should stay at terminal model"

    def test_restart_counter_increments(self) -> None:
        """Restart counter tracks all crashes."""
        manager = OllamaHealthManager()

        for i in range(3):
            manager.simulate_crash()
            manager.healthcheck()

        assert manager.restart_count == 3

    def test_no_crash_healthy(self) -> None:
        """Healthy Ollama returns clean healthcheck."""
        manager = OllamaHealthManager()

        result = manager.healthcheck()

        assert result["healthy"] is True
        assert "restarted" not in result

    def test_initial_model_is_primary(self) -> None:
        """Fresh manager starts on the primary (largest) model."""
        manager = OllamaHealthManager()
        assert manager.current_model == "deepseek-r1:14b"
        assert manager._chain_position == 0
