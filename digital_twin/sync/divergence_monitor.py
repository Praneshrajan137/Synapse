"""
SYNAPSE Digital Twin — Divergence monitor (I-12, INV-TW-003).

Computes KL divergence between twin state and live agent states.
Fires synapse.twin.divergence alert when threshold is exceeded.
"""
from __future__ import annotations

import time
import threading
from typing import Any

import numpy as np
import structlog

from digital_twin.config import TwinConfig
from synapse_common.kafka_client import KafkaConfig, SynapseProducer
from synapse_common.metrics import DIGITAL_TWIN_KL_DIVERGENCE

logger = structlog.get_logger(__name__)

DIVERGENCE_TOPIC = "synapse.twin.divergence"
THRESHOLD = 0.1


def compute_kl_divergence(
    p: np.ndarray,
    q: np.ndarray,
    epsilon: float = 1e-10,
) -> float:
    """Compute KL(P || Q) with smoothing to avoid log(0).

    Args:
        p: Twin state probability distribution.
        q: Live agent probability distribution.
        epsilon: Smoothing constant.

    Returns:
        KL divergence value.
    """
    p_safe = np.clip(p, epsilon, None)
    q_safe = np.clip(q, epsilon, None)
    p_norm = p_safe / p_safe.sum()
    q_norm = q_safe / q_safe.sum()
    return float(np.sum(p_norm * np.log(p_norm / q_norm)))


class DivergenceMonitor:
    """Monitors KL divergence between twin and live states.

    INV-TW-003: Fires alert on synapse.twin.divergence when KL > 0.1.
    I-12: Twin fidelity — KL divergence > 0.1 triggers re-sync.
    """

    def __init__(
        self,
        config: TwinConfig | None = None,
        producer: SynapseProducer | None = None,
    ) -> None:
        self._config = config or TwinConfig()
        self._threshold = self._config.kl_divergence_threshold

        if producer is not None:
            self._producer = producer
        else:
            kafka_cfg = KafkaConfig(
                bootstrap_servers=self._config.kafka_bootstrap,
            )
            self._producer = SynapseProducer(config=kafka_cfg)

        self._running = False
        self._thread: threading.Thread | None = None
        self._twin_state: dict[str, np.ndarray] = {}
        self._live_state: dict[str, np.ndarray] = {}
        self._last_divergence: dict[str, float] = {}

        logger.info(
            "divergence_monitor_init",
            threshold=self._threshold,
            check_interval_s=self._config.divergence_check_interval_s,
        )

    def update_twin_state(self, agent_name: str, distribution: np.ndarray) -> None:
        """Update the twin's internal state distribution for an agent."""
        self._twin_state[agent_name] = distribution

    def update_live_state(self, agent_name: str, distribution: np.ndarray) -> None:
        """Update the live agent state distribution."""
        self._live_state[agent_name] = distribution

    def check_divergence(self, agent_name: str) -> float | None:
        """Compute KL divergence for a specific agent and fire alert if needed.

        Returns:
            KL divergence value, or None if states are not available.
        """
        twin = self._twin_state.get(agent_name)
        live = self._live_state.get(agent_name)

        if twin is None or live is None:
            return None

        if twin.shape != live.shape:
            logger.warning(
                "divergence_shape_mismatch",
                agent=agent_name,
                twin_shape=twin.shape,
                live_shape=live.shape,
            )
            return None

        kl = compute_kl_divergence(twin, live)
        self._last_divergence[agent_name] = kl

        # I-12: emit the live fidelity metric on every comparison so the twin's
        # KL divergence is observable in Prometheus (previously this metric never
        # existed and the invariant was structurally unverifiable in production).
        DIGITAL_TWIN_KL_DIVERGENCE.labels(agent_name=agent_name).set(kl)

        if kl > self._threshold:
            self._fire_alert(agent_name, kl)

        return kl

    def check_all(self) -> dict[str, float]:
        """Check divergence for all agents with both twin and live states."""
        results: dict[str, float] = {}
        agents = set(self._twin_state.keys()) & set(self._live_state.keys())
        for agent_name in agents:
            kl = self.check_divergence(agent_name)
            if kl is not None:
                results[agent_name] = kl
        return results

    def _fire_alert(self, agent_name: str, kl_divergence: float) -> None:
        """Publish a divergence alert to Kafka (INV-TW-003)."""
        alert: dict[str, Any] = {
            "agent_name": agent_name,
            "kl_divergence": round(kl_divergence, 6),
            "threshold": self._threshold,
            "timestamp": time.time(),
            "action": "re_sync_required",
        }
        self._producer.produce(
            topic=DIVERGENCE_TOPIC,
            value=alert,
            key=agent_name,
        )
        logger.warning(
            "divergence_alert_fired",
            agent=agent_name,
            kl=round(kl_divergence, 6),
            threshold=self._threshold,
        )

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            self.check_all()
            time.sleep(self._config.divergence_check_interval_s)

    def start(self) -> None:
        """Start background divergence monitoring."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop, name="divergence-monitor", daemon=True
        )
        self._thread.start()
        logger.info("divergence_monitor_started")

    def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        logger.info("divergence_monitor_stopped")

    @property
    def last_divergence(self) -> dict[str, float]:
        return dict(self._last_divergence)
