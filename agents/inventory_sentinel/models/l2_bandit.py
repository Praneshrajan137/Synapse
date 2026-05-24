"""LinUCB contextual bandit — L2 safety-stock multiplier policy.

Per (store_id, sku_id) pair, learn the multiplier ∈ [1.0, 3.0] that minimises
holding-vs-stockout cost given a context vector (rolling demand stats,
volatility, lead time, freshness pressure). Pure NumPy; deterministic under a
fixed seed; persists posteriors as a Parquet table for warm-restart.

Reference: Li et al. 2010, "A Contextual-Bandit Approach to Personalized News
Article Recommendation". Adapted for a discrete arm set
{1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0}.

The bandit is *advisory*: it surfaces an arm + UCB; the pipeline still clips
to the model.py field constraint (1.0 ≤ multiplier ≤ 3.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_ARMS: tuple[float, ...] = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)


@dataclass
class LinUCB:
    """Disjoint LinUCB — one Aᵃ, bᵃ per arm.

    Aᵃ ∈ R^{d×d}, bᵃ ∈ R^d. Posterior mean θ̂ᵃ = Aᵃ⁻¹ bᵃ. UCB at context x:
        x·θ̂ᵃ + α √(x·Aᵃ⁻¹·xᵀ)
    """

    d: int
    arms: tuple[float, ...] = DEFAULT_ARMS
    alpha: float = 1.0
    A: dict[float, np.ndarray] = field(default_factory=dict)
    b: dict[float, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for a in self.arms:
            self.A.setdefault(a, np.eye(self.d))
            self.b.setdefault(a, np.zeros(self.d))

    def select(self, context: np.ndarray) -> tuple[float, float]:
        """Return (chosen_arm, ucb)."""
        x = context.reshape(self.d)
        best_arm = self.arms[0]
        best_ucb = -np.inf
        for arm in self.arms:
            A_inv = np.linalg.inv(self.A[arm])
            theta = A_inv @ self.b[arm]
            mean = float(x @ theta)
            ucb = mean + self.alpha * float(np.sqrt(x @ A_inv @ x))
            if ucb > best_ucb:
                best_ucb = ucb
                best_arm = arm
        return best_arm, best_ucb

    def update(self, context: np.ndarray, arm: float, reward: float) -> None:
        x = context.reshape(self.d)
        if arm not in self.A:
            return
        self.A[arm] = self.A[arm] + np.outer(x, x)
        self.b[arm] = self.b[arm] + reward * x

    # --- persistence -------------------------------------------------------

    def to_parquet(self, path: Path) -> None:
        try:
            import pandas as pd

            rows: list[dict[str, Any]] = []
            for arm in self.arms:
                rows.append(
                    {
                        "arm": float(arm),
                        "A": self.A[arm].astype(np.float64).tobytes(),
                        "b": self.b[arm].astype(np.float64).tobytes(),
                        "d": self.d,
                    }
                )
            pd.DataFrame(rows).to_parquet(path, index=False)
        except ImportError:
            logger.warning("linucb_parquet_skipped_no_pandas")

    @classmethod
    def from_parquet(cls, path: Path, *, alpha: float = 1.0) -> "LinUCB":
        import pandas as pd

        df = pd.read_parquet(path)
        d = int(df.iloc[0]["d"])
        arms = tuple(float(a) for a in df["arm"].tolist())
        bandit = cls(d=d, arms=arms, alpha=alpha)
        for _, row in df.iterrows():
            arm = float(row["arm"])
            bandit.A[arm] = np.frombuffer(row["A"], dtype=np.float64).reshape(d, d).copy()
            bandit.b[arm] = np.frombuffer(row["b"], dtype=np.float64).copy()
        return bandit


__all__ = ["DEFAULT_ARMS", "LinUCB"]
