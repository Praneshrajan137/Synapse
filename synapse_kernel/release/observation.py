"""What a policy sees at a decision, and what it may be built from: exactly PREREG-1 section 1.

The observation holds sales (censored by stock), on-hand stock by batch with each batch's expiry,
open orders with their placement times, receipts, realised lead times, the time of day and the day
of the week. It holds **no absolute time**: an expiry is hours from now, a placement is hours ago,
so neither the replicate's day index nor its horizon can be read from it; and no cell, shock or
shock parameter (``tests/kernel/release/test_observation.py`` enumerates the fields and shifts the
clock to show it). Arrays carry the batch of replicates as their first axis.

A policy is built from :class:`PolicyInputs` only: cell N's declared parameters and the records of
exploratory seeds; their canonical bytes are the same whichever cell the policy will run in.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.world import world_to_document

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["OBSERVATION_FIELDS", "PolicyInputs", "StoreObservation"]

I64 = npt.NDArray[np.int64]
I32 = npt.NDArray[np.int32]


@dataclasses.dataclass(frozen=True)
class StoreObservation:
    """The store at one decision, for every replicate of the batch."""

    hour_of_day: int
    day_of_week: int
    """0 is Monday."""
    deciding: npt.NDArray[np.bool_]
    """Per item: whether its supplier takes orders now (implied by the declared schedule)."""
    sales: I32 | I64
    """Units sold per hour per item since the previous decision, shape ``(R, hours, items)``."""
    receipts: I32 | I64
    """Units received per hour per item since the previous decision, ``(R, hours, items)``."""
    on_hand: I64
    """Units per batch, oldest first, shape ``(R, items, slots)``; empty slots hold 0."""
    hours_to_expiry: I64
    """Hours until each batch is discarded, ``-1`` for an empty slot."""
    open_qty: I64
    """Units of each open order, ``(R, items, slots)``; 0 for an empty slot."""
    open_age_hours: I64
    """Hours since each open order was placed, ``-1`` for an empty slot."""
    landed_lead_hours: I64
    """Realised lead times (placement to receipt, hours) of orders landed since the last decision,
    ``-1`` where none."""


#: The observation's fields, frozen: a new field is a change to what policies may see.
OBSERVATION_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(StoreObservation))


@dataclasses.dataclass(frozen=True)
class PolicyInputs:
    """Everything a release policy may be built from (PREREG-1 section 1)."""

    world: ReleaseWorld
    """Cell N's declared parameters, whichever cell the policy will run in."""
    records: Mapping[str, Mapping[int, I64]] = dataclasses.field(default_factory=dict)
    """Exploratory records: per cell, per exploratory seed, units demanded per hour and item."""

    def canonical_bytes(self) -> bytes:
        """The inputs as bytes: the world's canonical JSON, then every record in sorted order."""
        head = json.dumps(world_to_document(self.world), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(head.encode("utf-8"))
        for cell in sorted(self.records):
            for seed in sorted(self.records[cell]):
                digest.update(f"{cell}:{seed}:".encode())
                digest.update(
                    np.ascontiguousarray(self.records[cell][seed], dtype=np.int64).tobytes()
                )
        return digest.digest()
