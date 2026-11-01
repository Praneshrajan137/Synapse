"""Policy wrappers the suites share: a renamed arm, and the consensus arm that cannot stand up.

Feature: decision-quality-proof, session 12 (wave 2, the E5 suite). Two small things several
modules need, kept in one place so no two copies can drift:

* :class:`NamedPolicy` -- one policy registered under another arm name. The E5 suite runs arm E'
  (B-prime's in-sample levels) through ``GroupParLevelReorder``, whose name is arm E's; the
  harness keys every record by arm name, so two arms with one name would overwrite each other.
* :class:`UnavailableConsensusArm` -- the stand-in whose every decision fails honestly when the
  in-process consensus network cannot be assembled (R1.5, R2.7, R7.6). Moved here from
  ``uplift/cli.py`` so the E5 suite degrades exactly as the canonical suite does without
  importing the CLI; ``uplift.cli._UnavailableConsensusArm`` remains as an alias of it.

**Two classes, not one, for run scope.** ``NamedPolicy(policy, name)`` returns a
:class:`RunScopedNamedPolicy` -- a subclass that forwards ``begin_run``/``end_run`` -- when the
wrapped policy is :class:`~uplift.interfaces.RunScoped`, and a plain :class:`NamedPolicy`
otherwise. ``RunScoped`` is a structural protocol, so a single class always defining the two
methods would claim a per-run tally for a policy that keeps none, and the harness would then
record a tally nobody kept. The choice is made in ``__new__``; ``__getnewargs__`` replays it on
unpickling, so a wrapper sent to a ``ProcessPoolExecutor`` worker arrives as the same class.
"""

from __future__ import annotations

from uplift.consensus_arm import ConsensusArmUnavailable
from uplift.harness import DEFAULT_CONSENSUS_ARM
from uplift.interfaces import DecisionCounts, DecisionPolicy, Observation, PolicyAction, RunScoped

__all__ = [
    "NamedPolicy",
    "RunScopedNamedPolicy",
    "UnavailableConsensusArm",
]


class NamedPolicy:
    """``policy`` registered under the arm name ``name``; delegates ``decide`` unchanged.

    ``name`` must be a non-blank string, refused otherwise -- an arm the harness cannot name is
    an arm it cannot key, pair or label. ``policy`` must satisfy
    :class:`~uplift.interfaces.DecisionPolicy`. Construction returns a
    :class:`RunScopedNamedPolicy` when ``policy`` is :class:`~uplift.interfaces.RunScoped`, so the
    wrapper is run-scoped exactly when what it wraps is (see the module docstring).

    Raises:
        ValueError: On a blank or non-string ``name``, or a ``policy`` that is not a
            ``DecisionPolicy``.
    """

    def __new__(cls, policy: DecisionPolicy, name: str) -> NamedPolicy:
        if cls is NamedPolicy and isinstance(policy, RunScoped):
            return object.__new__(RunScopedNamedPolicy)
        return object.__new__(cls)

    def __init__(self, policy: DecisionPolicy, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"an arm name must be a non-blank string, got {name!r}: the harness keys, pairs "
                "and labels every run by it"
            )
        if not isinstance(policy, DecisionPolicy):
            raise ValueError(
                f"{type(policy).__name__} is not a DecisionPolicy (it needs `name` and `decide`), "
                "so there is nothing to register under the name"
            )
        self._policy = policy
        self._name = name

    def __getnewargs__(self) -> tuple[DecisionPolicy, str]:
        """Replay the construction arguments on unpickling, so ``__new__`` chooses the class."""
        return (self._policy, self._name)

    @property
    def name(self) -> str:
        """The arm name this wrapper registers its policy under."""
        return self._name

    @property
    def inner(self) -> DecisionPolicy:
        """The wrapped policy, unchanged."""
        return self._policy

    def decide(self, obs: Observation) -> PolicyAction:
        """The wrapped policy's decision for ``obs``, returned as it is."""
        return self._policy.decide(obs)


class RunScopedNamedPolicy(NamedPolicy):
    """A :class:`NamedPolicy` over a :class:`~uplift.interfaces.RunScoped` policy.

    Forwards ``begin_run`` and ``end_run`` to the wrapped policy, so the tally the harness
    attaches to a run is the wrapped policy's own. Built by ``NamedPolicy(policy, name)``; built
    directly over a policy that is not run-scoped, it is refused rather than left unable to
    answer the two calls it advertises.

    Raises:
        ValueError: As :class:`NamedPolicy`, or when ``policy`` is not ``RunScoped``.
    """

    def __init__(self, policy: DecisionPolicy, name: str) -> None:
        super().__init__(policy, name)
        if not isinstance(policy, RunScoped):
            raise ValueError(
                f"{type(policy).__name__} is not RunScoped, so a run-scoped wrapper over it "
                "would advertise a tally nobody keeps; use NamedPolicy(policy, name)"
            )
        self._scoped: RunScoped = policy

    def begin_run(self, seed: int) -> None:
        """Open the wrapped policy's run at twin ``seed``."""
        self._scoped.begin_run(seed)

    def end_run(self) -> DecisionCounts:
        """Close the wrapped policy's run and return its tally."""
        return self._scoped.end_run()


class UnavailableConsensusArm:
    """A stand-in consensus arm whose every decision fails honestly (R2.7, R7.6).

    The real :class:`~uplift.consensus_arm.ConsensusArm` needs an injected in-process
    consensus protocol + A2A transport (the full eight-agent + twin network), which a
    plain ``$0`` environment cannot stand up. Rather than crash the whole run or
    fabricate a decision, a suite substitutes this arm under the canonical consensus
    name: each :meth:`decide` raises :class:`ConsensusArmUnavailable`, so the harness
    records every consensus run as a *failed* run, excludes it from aggregation, and
    continues -- exactly the honest-failure contract. The assembled result is then marked
    incomplete and the consensus-vs-baseline headline is not credited to SYNAPSE.

    Moved verbatim from ``uplift/cli.py`` (session 12); keeps no tally, so it is not
    :class:`~uplift.interfaces.RunScoped`, and its failed runs carry none.
    """

    def __init__(self, reason: str, name: str = DEFAULT_CONSENSUS_ARM) -> None:
        self.name = name
        self._reason = reason

    @property
    def reason(self) -> str:
        """Why the network could not be assembled: the message every :meth:`decide` raises.

        Read-only, for a record that names this stand-in and must say why it stood in: the E5
        cost probe's ``unavailable`` record and the pathway probe's refusal (finding 116).
        """
        return self._reason

    def decide(self, obs: Observation) -> PolicyAction:  # noqa: ARG002 — always fails
        raise ConsensusArmUnavailable(self._reason)
