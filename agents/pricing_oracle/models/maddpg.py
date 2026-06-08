"""
SYNAPSE Pricing Oracle -- MADDPG Multi-Agent RL for Per-Category Pricing.

Each category (essentials, snacks, beverages, dairy, produce) has its own
actor-critic pair. The essential cap 1.3x is a HARD CLAMP (I-6) applied
post-action — it is never part of the learned policy.

Environment: PettingZoo AEC (Agent Environment Cycle).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import structlog
import torch
import torch.nn as nn
from torch import Tensor

if TYPE_CHECKING:
    import numpy as np

logger = structlog.get_logger(__name__)

CATEGORIES: Final[list[str]] = ["essential", "snack", "beverage", "dairy", "produce"]
ESSENTIAL_CAP: Final[float] = 1.3
MIN_MULTIPLIER: Final[float] = 0.5
MAX_MULTIPLIER: Final[float] = 2.5


class ActorNetwork(nn.Module):
    """Deterministic policy: observation -> price multiplier action."""

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        num_layers: int = 3,
    ) -> None:
        super().__init__()

        layers: list[nn.Module] = []
        in_dim = obs_dim
        for _ in range(num_layers - 1):
            layers.extend([nn.Linear(in_dim, hidden_dim), nn.ReLU()])
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, action_dim))
        layers.append(nn.Sigmoid())

        self.net = nn.Sequential(*layers)
        self._action_dim = action_dim

    def forward(self, obs: Tensor) -> Tensor:
        raw = self.net(obs)
        return MIN_MULTIPLIER + raw * (MAX_MULTIPLIER - MIN_MULTIPLIER)


class CriticNetwork(nn.Module):
    """Centralised critic: all observations + all actions -> Q-value."""

    def __init__(
        self,
        total_obs_dim: int,
        total_action_dim: int,
        hidden_dim: int = 256,
        num_layers: int = 3,
    ) -> None:
        super().__init__()

        layers: list[nn.Module] = []
        in_dim = total_obs_dim + total_action_dim
        for _ in range(num_layers - 1):
            layers.extend([nn.Linear(in_dim, hidden_dim), nn.ReLU()])
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, 1))

        self.net = nn.Sequential(*layers)

    def forward(self, obs_all: Tensor, actions_all: Tensor) -> Tensor:
        x = torch.cat([obs_all, actions_all], dim=-1)
        return self.net(x)


class PricingMADDPG(nn.Module):
    """
    Multi-Agent DDPG for per-category pricing.

    Essential cap (1.3x) is enforced as a hard clamp in `select_actions` and
    `forward` — it is NEVER learned or softened. Violating I-6 is impossible
    because the clamp is applied after every action computation.
    """

    def __init__(
        self,
        num_agents: int = 5,
        obs_dim: int = 24,
        action_dim: int = 1,
        actor_hidden_dim: int = 128,
        actor_num_layers: int = 3,
        critic_hidden_dim: int = 256,
        critic_num_layers: int = 3,
    ) -> None:
        super().__init__()

        self.num_agents = num_agents
        self.obs_dim = obs_dim
        self.action_dim = action_dim

        self.actors = nn.ModuleList(
            [
                ActorNetwork(obs_dim, action_dim, actor_hidden_dim, actor_num_layers)
                for _ in range(num_agents)
            ]
        )

        total_obs = num_agents * obs_dim
        total_act = num_agents * action_dim
        self.critics = nn.ModuleList(
            [
                CriticNetwork(total_obs, total_act, critic_hidden_dim, critic_num_layers)
                for _ in range(num_agents)
            ]
        )

        self.target_actors = nn.ModuleList(
            [
                ActorNetwork(obs_dim, action_dim, actor_hidden_dim, actor_num_layers)
                for _ in range(num_agents)
            ]
        )
        self.target_critics = nn.ModuleList(
            [
                CriticNetwork(total_obs, total_act, critic_hidden_dim, critic_num_layers)
                for _ in range(num_agents)
            ]
        )

        for i in range(num_agents):
            self.target_actors[i].load_state_dict(self.actors[i].state_dict())
            self.target_critics[i].load_state_dict(self.critics[i].state_dict())

    def forward(self, observations: dict[str, Tensor]) -> dict[str, Tensor]:
        """
        Forward pass: compute price multipliers for all categories.

        Returns a dict mapping category name -> multiplier tensor.
        Essential category is HARD CLAMPED to [MIN_MULTIPLIER, ESSENTIAL_CAP].
        """
        actions: dict[str, Tensor] = {}

        for idx, category in enumerate(CATEGORIES):
            obs = observations[category]
            raw_action = self.actors[idx](obs)

            if category == "essential":
                raw_action = torch.clamp(raw_action, min=MIN_MULTIPLIER, max=ESSENTIAL_CAP)
            else:
                raw_action = torch.clamp(raw_action, min=MIN_MULTIPLIER, max=MAX_MULTIPLIER)

            actions[category] = raw_action

        return actions

    def select_actions(
        self,
        observations: dict[str, Tensor],
        noise_scale: float = 0.0,
    ) -> dict[str, Tensor]:
        """
        Select actions with optional exploration noise.
        Essential cap is enforced AFTER noise addition — no escape from I-6.
        """
        actions: dict[str, Tensor] = {}

        for idx, category in enumerate(CATEGORIES):
            # Serve only the categories actually requested (each keeps its fixed
            # agent index). The pipeline builds observations for the SKUs' subset
            # of categories, not always all five — skipping absent ones avoids a
            # KeyError and lets the actor serve any subset (training passes all 5).
            if category not in observations:
                continue
            obs = observations[category]

            with torch.no_grad():
                raw_action = self.actors[idx](obs)

            if noise_scale > 0.0:
                noise = torch.randn_like(raw_action) * noise_scale
                raw_action = raw_action + noise

            if category == "essential":
                raw_action = torch.clamp(raw_action, min=MIN_MULTIPLIER, max=ESSENTIAL_CAP)
            else:
                raw_action = torch.clamp(raw_action, min=MIN_MULTIPLIER, max=MAX_MULTIPLIER)

            actions[category] = raw_action

        return actions

    def soft_update(self, tau: float = 0.01) -> None:
        """Polyak averaging for target networks."""
        with torch.no_grad():
            for i in range(self.num_agents):
                for param, target_param in zip(
                    self.actors[i].parameters(),
                    self.target_actors[i].parameters(),
                    strict=True,
                ):
                    target_param.copy_(tau * param + (1.0 - tau) * target_param)

                for param, target_param in zip(
                    self.critics[i].parameters(),
                    self.target_critics[i].parameters(),
                    strict=True,
                ):
                    target_param.copy_(tau * param + (1.0 - tau) * target_param)

    def get_model_summary(self) -> dict[str, int]:
        """Return parameter counts for logging and MLflow."""
        actor_params = sum(p.numel() for actor in self.actors for p in actor.parameters())
        critic_params = sum(p.numel() for critic in self.critics for p in critic.parameters())
        target_params = sum(p.numel() for ta in self.target_actors for p in ta.parameters()) + sum(
            p.numel() for tc in self.target_critics for p in tc.parameters()
        )

        return {
            "actor_params": actor_params,
            "critic_params": critic_params,
            "target_params": target_params,
            "total_trainable": actor_params + critic_params,
            "total_params": actor_params + critic_params + target_params,
            "num_agents": self.num_agents,
        }

    @staticmethod
    def enforce_essential_cap(multiplier: float | np.floating[object]) -> float:
        """
        Standalone guardrail utility — usable without the full model.
        Ensures essential category multiplier never exceeds ESSENTIAL_CAP.
        """
        return float(min(max(float(multiplier), MIN_MULTIPLIER), ESSENTIAL_CAP))
