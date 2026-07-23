"""
``No_Op_Disruption`` — the disruption-response baseline control policy (R1.5).

This baseline represents "what a competent operator does without SYNAPSE" when a
disruption occurs: nothing. For any disruption event (any :class:`Observation`,
shocked or not), it returns a :class:`PolicyAction` whose ``disruption_actions`` is
the empty ``frozenset`` — i.e. an empty action set (R1.5). It is a pure, deterministic,
seed-stable function object with no hidden global state (R1.9), and it implements the
shared :class:`~uplift.interfaces.DecisionPolicy` interface (R1.6) so the harness loop
can drive it identically to every other arm.
"""
from __future__ import annotations

from uplift.interfaces import DecisionPolicy, Observation, PolicyAction


class NoOpDisruption(DecisionPolicy):
    """Disruption-response baseline that takes no corrective action (R1.5).

    The control representing operation *without* SYNAPSE: on any disruption event it
    emits an empty action set, leaving the twin to absorb the shock unaided.
    """

    def __init__(self, name: str = "no_op_disruption") -> None:
        self.name = name

    def decide(self, obs: Observation) -> PolicyAction:
        """Return a ``PolicyAction`` with an empty disruption action set (R1.5).

        Regardless of whether ``obs.active_shock`` is present, no corrective action
        is taken: ``disruption_actions`` is the empty ``frozenset``.
        """
        return PolicyAction(disruption_actions=frozenset())
