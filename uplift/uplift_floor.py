"""The ratcheted :data:`UPLIFT_FLOOR` constant (ADR-042, C60).

This is the single source of truth for the minimum measured decision-integrity
uplift SYNAPSE must sustain. It is imported by the ``uplift_truth`` honesty gate
(:mod:`scripts.audit.uplift_truth`), which fails CI when the measured headline
uplift regresses below this floor — the same BASELINE-ratchet pattern
``scripts/audit/training_truth.py`` uses to lock in a proven gain so it cannot
silently rot away.

Ratchet discipline (R6.2, R6.8):

  * :data:`UPLIFT_FLOOR` is a single declared numeric constant.
  * It is **never lowered**. Once a gain is verified, the floor is raised (in a
    version-controlled commit) to lock it in; a later regression below the
    committed value fails the gate. Lowering it would erase a proven gain and is
    forbidden by the monotonic-ratchet invariant.

The headline uplift is the relative percentage improvement of the Consensus_Arm
over the Baseline_Arm on the contract's primary KPI, so the floor is expressed in
the same unit (percentage points). It starts at ``0.0``: before the harness has
produced and committed a verified positive result, the honest floor is "no proven
uplift yet" — the gate must not assert a gain the repo has not yet demonstrated.
The floor ratchets *up* one PR at a time as verified gains land.

Data-gated raises (R4.2, R4.7 / AD-4). Monotonicity alone is not enough: a raise
above the committed value asserts a *measured* gain, so it is only legitimate
against a co-located, fully-powered, complete, within-fidelity-bound proof
artifact whose headline uplift is at least the proposed value.
:class:`PoweredProof` models that artifact and :func:`ratchet_to_measured` is the
guard that accepts a raise to ``0 < v <= measured`` only when such a proof backs
it. The value bump itself is committed by the operator, atomically with the proof,
after a powered run measures a positive within-bound headline — no powered proof
exists yet, so the shipped floor stays at ``0.0``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Minimum sustained headline uplift, in percentage points of relative improvement
# of the Consensus_Arm over the Baseline_Arm on the primary KPI. Ratchet UP only;
# never record a value below the previously committed floor (R6.8).
UPLIFT_FLOOR: float = 0.0

#: Replicates per arm a proof artifact must record to count as *fully powered*.
#: Mirrors the INV-TW-002 under-power floor
#: (``digital_twin.simulation.monte_carlo.MIN_SCENARIOS``); declared locally so this
#: module stays dependency-free for the C60 gate, and pinned to that constant by
#: ``tests/uplift/test_uplift_floor_data_gate.py``.
MIN_POWERED_REPLICATES: int = 1000

#: Artifact keys that may carry the replicates-per-arm count, in priority order.
_REPLICATE_KEYS = ("replicates_per_arm", "replicates", "n_per_arm")


class FloorRatchetError(ValueError):
    """Raised when a proposed :data:`UPLIFT_FLOOR` update would lower the floor.

    Lowering the floor erases a proven gain and violates the monotonic-ratchet
    invariant (R6.8), mirroring the way ``training_truth.BASELINE`` only ever
    ratchets in the direction that locks a gain in.
    """


def ratchet(previous: float, proposed: float) -> float:
    """Return the committed floor after proposing ``proposed`` over ``previous``.

    The uplift floor is a monotonic ratchet (R6.8): a verified gain is locked in
    by raising the floor, and it is **never lowered**. This pure helper enforces
    that discipline for a single update:

      * accept the update when ``proposed >= previous`` (raise or hold the floor),
        returning the new committed value ``proposed``;
      * reject the update when ``proposed < previous`` by raising
        :class:`FloorRatchetError`, since committing it would record a floor below
        the previously committed value.

    Args:
        previous: The previously committed floor value.
        proposed: The candidate new floor value.

    Returns:
        The new committed floor (``proposed``) when the update is monotonic.

    Raises:
        FloorRatchetError: If ``proposed`` is strictly below ``previous``.
    """
    if proposed < previous:
        raise FloorRatchetError(
            f"uplift floor may not be lowered: proposed {proposed!r} < "
            f"previously committed {previous!r} (R6.8 monotonic ratchet)"
        )
    return proposed


class UnprovenFloorRaiseError(FloorRatchetError):
    """Raised when a floor *raise* is not backed by a powered proof artifact.

    A subclass of :class:`FloorRatchetError` so callers that already guard the
    ratchet catch both failure modes: lowering a proven floor (R4.3) and asserting
    an unproven gain (R4.2, R4.7).
    """


@dataclass(frozen=True)
class PoweredProof:
    """The measured evidence a floor raise must be co-located with (R4.2, R4.7).

    Attributes:
        headline_uplift: The measured headline uplift, in percentage points.
        replicates: Replicates per arm the run used (power evidence, INV-TW-002).
        incomplete: True when any (scenario, arm) pair failed to complete.
        within_fidelity_bound: Whether the twin KL divergence was within the C34
            re-sync threshold; ``None`` when fidelity was unavailable.
    """

    headline_uplift: float
    replicates: int
    incomplete: bool
    within_fidelity_bound: bool | None

    @property
    def is_powered(self) -> bool:
        """True iff the run met the INV-TW-002 replicate floor."""
        return self.replicates >= MIN_POWERED_REPLICATES

    def supports(self, proposed: float) -> bool:
        """True iff this proof legitimises committing a floor of ``proposed``.

        A proof supports ``proposed`` only when the run was fully powered, complete,
        inside the twin fidelity bound, and measured a positive headline uplift at
        or above ``proposed`` — i.e. ``0 < proposed <= headline_uplift`` (R4.2, R4.7).
        """
        if not self.is_powered or self.incomplete:
            return False
        if self.within_fidelity_bound is not True:
            return False
        if not math.isfinite(self.headline_uplift) or self.headline_uplift <= 0.0:
            return False
        return 0.0 < proposed <= self.headline_uplift

    @classmethod
    def from_payload(cls, payload: Any) -> "PoweredProof | None":
        """Build a proof from a result-artifact mapping, or ``None`` if unusable.

        Returns ``None`` when the payload is not a mapping, carries no finite numeric
        ``headline_uplift``, or records no integral replicate count under any of
        :data:`_REPLICATE_KEYS` — an artifact that cannot evidence its own power is
        not a powered proof, and absence of proof is never a pass (R4.6, R4.7).
        """
        if not isinstance(payload, dict):
            return None
        uplift = payload.get("headline_uplift")
        if isinstance(uplift, bool) or not isinstance(uplift, (int, float)):
            return None
        measured = float(uplift)
        if not math.isfinite(measured):
            return None

        replicates: int | None = None
        for key in _REPLICATE_KEYS:
            value = payload.get(key)
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            replicates = value
            break
        if replicates is None:
            return None

        fidelity = payload.get("fidelity")
        within = fidelity.get("within_fidelity_bound") if isinstance(fidelity, dict) else None
        if not isinstance(within, bool):
            within = None

        return cls(
            headline_uplift=measured,
            replicates=replicates,
            incomplete=bool(payload.get("incomplete", True)),
            within_fidelity_bound=within,
        )

    @classmethod
    def from_artifact(cls, artifact: Path) -> "PoweredProof | None":
        """Read a proof from a persisted result artifact, or ``None`` if unavailable.

        Missing, unreadable, or malformed artifacts yield ``None`` so a raise
        attempted against them is rejected rather than silently accepted.
        """
        try:
            raw = Path(artifact).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return cls.from_payload(payload)


def is_proven_uplift(proof: PoweredProof | None, floor: float = UPLIFT_FLOOR) -> bool:
    """Return True iff the uplift may honestly be described as *proven* (R8.4, R10.6, R10.7).

    This is the single predicate the README/docs wording and the feature's own success
    definition are pinned to, so "proven"/"success" cannot drift from what a measurement
    actually shows. It resolves to ``True`` only when **every** condition holds:

      * ``proof`` exists — an unavailable measurement is never a proof (R4.6, R10.6);
      * the run is a ``Powered_Run``: ``replicates >= MIN_POWERED_REPLICATES``
        (INV-TW-002), so an under-powered run is never proof-grade;
      * the run is complete — no failed ``(scenario, arm)`` pair (R10.6);
      * the result is inside the committed Fidelity_Bound
        (``within_fidelity_bound is True``); an out-of-bound or unavailable-fidelity
        result never counts as success regardless of magnitude (R10.7);
      * the measured headline is finite, strictly positive, and at least the committed
        ``floor`` (R8.4, R10.5) — a zero or negative headline is an honest non-success,
        not a proof.

    Every other outcome is *unproven*, and because a "proven" measurement is exactly what
    :meth:`PoweredProof.supports` requires, an unproven outcome also leaves the floor
    ineligible to ratchet above ``0.0`` (R10.6): :func:`ratchet_to_measured` rejects any
    raise backed by it.

    Args:
        proof: The co-located proof artifact for the run, or ``None`` when no measurement
            is available (missing/unreadable/invalid artifact).
        floor: The committed :data:`UPLIFT_FLOOR` the headline must clear.

    Returns:
        ``True`` when the uplift is proven, ``False`` (unproven / non-success) otherwise.
    """
    if proof is None:
        return False
    if not proof.is_powered or proof.incomplete:
        return False
    if proof.within_fidelity_bound is not True:
        return False
    measured = proof.headline_uplift
    if not math.isfinite(measured):
        return False
    return measured > 0.0 and measured >= floor


def ratchet_to_measured(
    previous: float,
    proposed: float,
    proof: PoweredProof | None,
) -> float:
    """Return the committed floor for a data-gated update (R4.2, R4.3, R4.7).

    Layers the data gate on top of :func:`ratchet`:

      * ``proposed < previous`` -> :class:`FloorRatchetError` (never lower a proven
        floor);
      * ``proposed == previous`` -> accepted with no proof required (holding the
        already-committed floor asserts nothing new);
      * ``proposed > previous`` -> accepted only when ``proof`` is a fully-powered,
        complete, within-fidelity-bound measurement with
        ``0 < proposed <= proof.headline_uplift``; otherwise
        :class:`UnprovenFloorRaiseError`.

    Args:
        previous: The previously committed floor value.
        proposed: The candidate new floor value.
        proof: The co-located powered proof artifact backing a raise, or ``None``
            when no measurement is available.

    Returns:
        The new committed floor (``proposed``) when the update is legitimate.

    Raises:
        FloorRatchetError: If the update would lower the floor.
        UnprovenFloorRaiseError: If a raise is not backed by a supporting proof.
    """
    ratchet(previous, proposed)
    if proposed == previous:
        return proposed
    if proof is None:
        raise UnprovenFloorRaiseError(
            f"uplift floor may not be raised from {previous!r} to {proposed!r} without a "
            "co-located powered proof artifact (R4.7): no measurement available"
        )
    if not proof.supports(proposed):
        raise UnprovenFloorRaiseError(
            f"uplift floor may not be raised from {previous!r} to {proposed!r}: the "
            f"co-located proof does not support it (R4.2, R4.7) — measured "
            f"{proof.headline_uplift!r} pp over {proof.replicates} replicates/arm "
            f"(powered={proof.is_powered}, incomplete={proof.incomplete}, "
            f"within_fidelity_bound={proof.within_fidelity_bound}); a raise requires "
            f"0 < proposed <= measured from a powered, complete, within-bound run"
        )
    return proposed


__all__ = [
    "UPLIFT_FLOOR",
    "MIN_POWERED_REPLICATES",
    "FloorRatchetError",
    "UnprovenFloorRaiseError",
    "PoweredProof",
    "is_proven_uplift",
    "ratchet",
    "ratchet_to_measured",
]
