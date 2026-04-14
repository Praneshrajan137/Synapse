from __future__ import annotations

import numpy as np
import pytest
import structlog
import structlog.testing

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos


def kl_divergence(p: list[float], q: list[float], epsilon: float = 1e-10) -> float:
    """Compute KL divergence D_KL(P || Q) with numerical stability.

    NOTE: KL divergence is asymmetric.  D_KL(P||Q) != D_KL(Q||P).
    For twin drift monitoring, P is reality and Q is the twin's model
    of reality so we measure information lost by using Q instead of P.
    """
    p_arr = np.array(p, dtype=np.float64) + epsilon
    q_arr = np.array(q, dtype=np.float64) + epsilon
    p_arr /= p_arr.sum()
    q_arr /= q_arr.sum()
    return float(np.sum(p_arr * np.log(p_arr / q_arr)))


class DivergenceMonitor:
    """Monitors KL divergence between reality and Digital Twin state."""

    KL_THRESHOLD = 0.1

    def __init__(self) -> None:
        self.divergence_history: list[float] = []
        self.alert_fired: bool = False
        self.resync_triggered: bool = False
        self.human_flagged: bool = False

    def check_divergence(
        self, reality_distribution: list[float], twin_distribution: list[float]
    ) -> dict:
        kl = kl_divergence(reality_distribution, twin_distribution)
        self.divergence_history.append(kl)

        result: dict = {
            "kl_divergence": kl,
            "threshold": self.KL_THRESHOLD,
            "exceeded": kl > self.KL_THRESHOLD,
        }

        if kl > self.KL_THRESHOLD:
            self.alert_fired = True
            self.resync_triggered = True
            self.human_flagged = True
            logger.warning(
                "twin_divergence_exceeded",
                kl=kl,
                threshold=self.KL_THRESHOLD,
                action="force_resync_and_flag_human",
            )
            result["actions"] = ["force_resync", "disruption_shield_alert", "human_flag"]
        else:
            result["actions"] = []

        return result


class TestDigitalTwinDrift:
    """Chaos logic validation: 50% demand shift without Twin update causes
    KL divergence > 0.1 threshold.  System forces re-sync and flags for
    human review. SLA: <2min."""

    @staticmethod
    def _baseline_distribution() -> list[float]:
        """Uniform demand distribution across 10 zones."""
        return [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]

    @staticmethod
    def _shifted_distribution() -> list[float]:
        """50% demand shift — zones 1-3 spike, others drop."""
        return [0.25, 0.20, 0.15, 0.08, 0.07, 0.06, 0.05, 0.05, 0.05, 0.04]

    def test_drift_detected_after_demand_shift(self, chaos_clock) -> None:
        """50% demand shift triggers KL divergence > 0.1."""
        monitor = DivergenceMonitor()
        reality = self._shifted_distribution()
        twin = self._baseline_distribution()

        chaos_clock.start()
        with structlog.testing.capture_logs() as captured:
            result = monitor.check_divergence(reality, twin)

        assert result["exceeded"] is True
        assert result["kl_divergence"] > 0.1
        chaos_clock.assert_within_sla(120.0, "Twin drift detection")
        assert any(e.get("event") == "twin_divergence_exceeded" for e in captured)

    def test_resync_triggered_on_divergence(self) -> None:
        """Divergence exceeding threshold triggers forced re-sync."""
        monitor = DivergenceMonitor()
        monitor.check_divergence(self._shifted_distribution(), self._baseline_distribution())

        assert monitor.resync_triggered is True
        assert monitor.alert_fired is True

    def test_human_flagged_on_divergence(self) -> None:
        """Human is flagged when divergence exceeds threshold (I-5)."""
        monitor = DivergenceMonitor()
        monitor.check_divergence(self._shifted_distribution(), self._baseline_distribution())

        assert monitor.human_flagged is True

    def test_no_alert_within_threshold(self) -> None:
        """Slight drift below threshold does NOT trigger alert."""
        monitor = DivergenceMonitor()
        slight_shift = [0.11, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.09, 0.10]

        result = monitor.check_divergence(slight_shift, self._baseline_distribution())

        assert result["exceeded"] is False
        assert monitor.alert_fired is False

    def test_disruption_shield_notified(self) -> None:
        """Disruption Shield is included in alert actions."""
        monitor = DivergenceMonitor()
        result = monitor.check_divergence(
            self._shifted_distribution(), self._baseline_distribution()
        )

        assert "disruption_shield_alert" in result["actions"]

    def test_reverse_divergence_also_detected(self) -> None:
        """D_KL(twin || reality) also exceeds threshold for a major shift."""
        monitor = DivergenceMonitor()
        kl_reverse = kl_divergence(
            self._baseline_distribution(), self._shifted_distribution()
        )
        assert kl_reverse > 0.1, (
            "Reverse KL divergence should also exceed threshold for a 50% shift"
        )

    def test_divergence_history_accumulated(self) -> None:
        """Each check appends to divergence history for trend analysis."""
        monitor = DivergenceMonitor()
        baseline = self._baseline_distribution()

        monitor.check_divergence(baseline, baseline)
        monitor.check_divergence(self._shifted_distribution(), baseline)

        assert len(monitor.divergence_history) == 2
        assert monitor.divergence_history[0] < monitor.divergence_history[1]
