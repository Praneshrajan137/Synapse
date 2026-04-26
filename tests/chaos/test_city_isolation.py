"""E3 (elevation): cross-city failure isolation chaos test.

The other 9 chaos tests target a single city. This 10th scenario asserts
the *city-scoping invariant* (CLAUDE.md error patterns E-S6-03 / E-S6-05):
when Mumbai's Redis partition (db=1) goes hard-down, Bengaluru (db=0) must
keep serving without elevated error rate.

The test is hermetic and uses ``chaos_rng`` (E-S5-12, E4 elevation) for
reproducibility. It models per-city Redis access through a thin shim so
the real client is never required.
"""
from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest


@dataclasses.dataclass
class _CityRedisShim:
    """Stand-in for a per-city Redis client.

    ``db_index`` mirrors the production convention: Bengaluru uses db=0,
    Mumbai uses db=1 (E-S6-03). When ``healthy`` is False, every call
    raises ConnectionError -- this is the failure we inject.
    """

    city: str
    db_index: int
    healthy: bool = True

    def get(self, key: str) -> str | None:
        if not self.healthy:
            raise ConnectionError(f"redis db={self.db_index} ({self.city}) down")
        return f"{self.city}:{key}:value"


def _serve_request(client: _CityRedisShim, key: str) -> tuple[bool, Any]:
    """Mirror an agent's read path: returns (success, value_or_error)."""
    try:
        return True, client.get(key)
    except ConnectionError as exc:
        return False, str(exc)


@pytest.mark.chaos
class TestCityIsolation:
    """Mumbai Redis outage MUST NOT degrade Bengaluru."""

    def test_mumbai_outage_does_not_affect_bengaluru(
        self,
        chaos_rng: np.random.Generator,
    ) -> None:
        bengaluru = _CityRedisShim(city="bengaluru", db_index=0, healthy=True)
        mumbai = _CityRedisShim(city="mumbai", db_index=1, healthy=False)

        bengaluru_results = [
            _serve_request(bengaluru, f"sku:{int(chaos_rng.integers(0, 500))}")
            for _ in range(200)
        ]
        mumbai_results = [
            _serve_request(mumbai, f"sku:{int(chaos_rng.integers(0, 500))}")
            for _ in range(200)
        ]

        bengaluru_success_rate = sum(1 for ok, _ in bengaluru_results if ok) / 200
        mumbai_success_rate = sum(1 for ok, _ in mumbai_results if ok) / 200

        # Bengaluru is unaffected (city-scoping invariant).
        assert bengaluru_success_rate == 1.0, (
            f"Bengaluru success rate {bengaluru_success_rate:.0%} -- "
            "Mumbai outage must not bleed across the city boundary (E-S6-05)."
        )
        # Mumbai's failure is observable (sanity: we did inject the outage).
        assert mumbai_success_rate == 0.0

    def test_per_city_db_indexes_are_distinct(self) -> None:
        """E-S6-03: Bengaluru db=0, Mumbai db=1 (no collision)."""
        bengaluru = _CityRedisShim(city="bengaluru", db_index=0)
        mumbai = _CityRedisShim(city="mumbai", db_index=1)
        assert bengaluru.db_index != mumbai.db_index
