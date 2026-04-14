from __future__ import annotations

import pytest
import structlog

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos

MINIMUM_TRUST_FLOOR = 0.3
TRUST_RAMP_DELIVERIES = 10


class SupplierTrustScorer:
    """Trust scoring with minimum floor for new vendors."""

    def __init__(
        self,
        min_trust_floor: float = MINIMUM_TRUST_FLOOR,
        ramp_deliveries: int = TRUST_RAMP_DELIVERIES,
    ) -> None:
        self.min_trust_floor = min_trust_floor
        self.ramp_deliveries = ramp_deliveries

    def compute_trust(
        self,
        delivery_count: int,
        on_time_rate: float,
        fill_rate: float,
        quality_score: float,
        *,
        vendor_size: str = "medium",
        vendor_region: str = "default",
    ) -> float:
        if delivery_count == 0:
            return self.min_trust_floor

        raw_trust = 0.4 * on_time_rate + 0.3 * fill_rate + 0.3 * quality_score

        if delivery_count < self.ramp_deliveries:
            ramp_factor = delivery_count / self.ramp_deliveries
            raw_trust = self.min_trust_floor + ramp_factor * (raw_trust - self.min_trust_floor)

        return max(raw_trust, self.min_trust_floor)


class TestSupplierBias:
    """Chaos logic validation: New vendor with zero history gets fair trust
    score. Minimum trust floor prevents cold-start bias. Preventive control."""

    def test_new_vendor_gets_minimum_floor(self) -> None:
        """Zero-history vendor receives minimum trust floor, not zero."""
        scorer = SupplierTrustScorer()
        trust = scorer.compute_trust(
            delivery_count=0, on_time_rate=0.0, fill_rate=0.0, quality_score=0.0,
        )

        assert trust == MINIMUM_TRUST_FLOOR
        assert trust > 0.0, "New vendor trust must never be zero"

    def test_trust_ramps_with_deliveries(self) -> None:
        """Trust ramps gradually from floor toward earned score."""
        scorer = SupplierTrustScorer()

        trust_1 = scorer.compute_trust(
            delivery_count=1, on_time_rate=0.9, fill_rate=0.95, quality_score=0.85,
        )
        trust_5 = scorer.compute_trust(
            delivery_count=5, on_time_rate=0.9, fill_rate=0.95, quality_score=0.85,
        )
        trust_10 = scorer.compute_trust(
            delivery_count=10, on_time_rate=0.9, fill_rate=0.95, quality_score=0.85,
        )

        assert trust_1 < trust_5 < trust_10
        assert trust_1 >= MINIMUM_TRUST_FLOOR

    def test_trust_never_below_floor(self) -> None:
        """Even terrible performance cannot drop trust below floor."""
        scorer = SupplierTrustScorer()
        trust = scorer.compute_trust(
            delivery_count=3, on_time_rate=0.1, fill_rate=0.2, quality_score=0.1,
        )

        assert trust >= MINIMUM_TRUST_FLOOR

    def test_consecutive_late_deliveries_decrease_trust(self) -> None:
        """MR-ST-001: Consecutive late deliveries strictly decrease trust."""
        scorer = SupplierTrustScorer()

        good = scorer.compute_trust(
            delivery_count=20, on_time_rate=0.95, fill_rate=0.95, quality_score=0.90,
        )
        degraded = scorer.compute_trust(
            delivery_count=20, on_time_rate=0.60, fill_rate=0.95, quality_score=0.90,
        )

        assert degraded < good, "Late deliveries must decrease trust score"

    def test_fairness_across_vendor_sizes(self) -> None:
        """New vendors of different sizes receive identical floor scores."""
        scorer = SupplierTrustScorer()

        large = scorer.compute_trust(
            delivery_count=0, on_time_rate=0.0, fill_rate=0.0, quality_score=0.0,
            vendor_size="enterprise",
        )
        small = scorer.compute_trust(
            delivery_count=0, on_time_rate=0.0, fill_rate=0.0, quality_score=0.0,
            vendor_size="micro",
        )
        medium = scorer.compute_trust(
            delivery_count=0, on_time_rate=0.0, fill_rate=0.0, quality_score=0.0,
            vendor_size="medium",
        )

        assert large == small == medium == MINIMUM_TRUST_FLOOR

    def test_fairness_across_vendor_regions(self) -> None:
        """New vendors from different regions receive identical floor scores."""
        scorer = SupplierTrustScorer()

        regions = ["tier1_metro", "tier2_city", "rural", "international"]
        scores = [
            scorer.compute_trust(
                delivery_count=0, on_time_rate=0.0, fill_rate=0.0, quality_score=0.0,
                vendor_region=region,
            )
            for region in regions
        ]

        assert all(s == MINIMUM_TRUST_FLOOR for s in scores)

    def test_fully_ramped_score_matches_raw_formula(self) -> None:
        """After ramp period, score equals the raw weighted formula."""
        scorer = SupplierTrustScorer()
        on_time, fill, quality = 0.9, 0.95, 0.85
        expected = 0.4 * on_time + 0.3 * fill + 0.3 * quality

        trust = scorer.compute_trust(
            delivery_count=10, on_time_rate=on_time, fill_rate=fill, quality_score=quality,
        )

        assert abs(trust - expected) < 1e-9
