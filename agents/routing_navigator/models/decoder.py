"""
SYNAPSE Routing Navigator -- Autoregressive Pointer-Network Decoder.
Produces a permutation of visit order using attention-based pointing.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F  # noqa: N812
from torch import Tensor


class PointerDecoder(nn.Module):
    """
    Autoregressive pointer decoder for route generation.
    At each step, attends over encoder outputs to select the next stop.
    """

    def __init__(self, embed_dim: int = 128, hidden_dim: int = 128) -> None:
        super().__init__()
        self.embed_dim = embed_dim
        self.hidden_dim = hidden_dim

        self.lstm_cell = nn.LSTMCell(embed_dim, hidden_dim)
        self.pointer_W1 = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.pointer_W2 = nn.Linear(embed_dim, hidden_dim, bias=False)
        self.pointer_v = nn.Linear(hidden_dim, 1, bias=False)
        self.start_token = nn.Parameter(torch.randn(embed_dim))

    def forward(
        self,
        encoder_outputs: Tensor,
        mask: Tensor | None = None,
        greedy: bool = False,
    ) -> tuple[Tensor, Tensor]:
        """
        Returns:
            tour: (batch, num_orders) indices of visit order
            log_probs: (batch, num_orders) log probabilities for REINFORCE
        """
        batch_size, num_orders, _ = encoder_outputs.shape
        device = encoder_outputs.device

        h = torch.zeros(batch_size, self.hidden_dim, device=device)
        c = torch.zeros(batch_size, self.hidden_dim, device=device)

        visited = torch.zeros(batch_size, num_orders, dtype=torch.bool, device=device)
        if mask is not None:
            visited = visited | mask

        current_input = self.start_token.unsqueeze(0).expand(batch_size, -1)

        tour_indices: list[Tensor] = []
        tour_log_probs: list[Tensor] = []

        for _step in range(num_orders):
            h, c = self.lstm_cell(current_input, (h, c))

            query = self.pointer_W1(h).unsqueeze(1)
            keys = self.pointer_W2(encoder_outputs)
            logits = self.pointer_v(torch.tanh(query + keys)).squeeze(-1)

            logits = logits.masked_fill(visited, float("-inf"))
            probs = F.softmax(logits, dim=-1)

            selected = probs.argmax(dim=-1) if greedy else torch.multinomial(probs, 1).squeeze(-1)

            log_prob = torch.log(probs.gather(1, selected.unsqueeze(1)) + 1e-8).squeeze(-1)

            visited = visited.scatter(1, selected.unsqueeze(1), True)
            current_input = encoder_outputs.gather(
                1, selected.unsqueeze(1).unsqueeze(2).expand(-1, -1, self.embed_dim)
            ).squeeze(1)

            tour_indices.append(selected)
            tour_log_probs.append(log_prob)

        tour = torch.stack(tour_indices, dim=1)
        log_probs = torch.stack(tour_log_probs, dim=1)

        return tour, log_probs
