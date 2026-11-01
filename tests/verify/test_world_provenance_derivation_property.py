"""Property-based test for derived world provenance (design AD-11 / E5.3).

Feature: purpose-achievement-audit, Property 28: World provenance is derived, never
asserted

    *For any* world source, the perceived state reports ``is_synthetic`` true iff arrivals
    originate from a seeded generator; the source classifier assigns exactly one of
    seeded, external, or stub to every implementation and classifies an unconditionally
    empty arrival list as a stub; a configured-but-unreachable external feed yields a
    degraded state with zero substituted arrivals and does not advance demand from a
    seeded generator; and a non-seeded source with no inventory yields a degraded state
    rather than a literal default.

Why the property is shaped this way. The audit finding behind Requirement 4 is that
``WorldState.is_synthetic`` was **pinned** ``True`` in the model, so the one flag that
existed to separate "a real supply chain" from "a simulation of one" could not take the
other value even if the world were genuinely externally driven. Task 10.11 made the flag
derive from the active source's declared class. A declaration, though, is only a claim, so
this file states four things that no naming, docstring, or declaration can satisfy on its
own:

1. **The flag is a function of the source alone.** Over every provenance value crossed
   with every other field of ``WorldState``, ``is_synthetic`` equals
   ``source_class is SEEDED`` and nothing else moves it. It is also *unassertable*: there
   is no field to set, and the constructor rejects the keyword in both directions, so the
   only way to make the world report "not synthetic" is to hand it a source that declares
   a non-seeded provenance.
2. **A stub is a stub however it presents.** Over the cross product of class names
   (including ``ExternalFeedSource`` and ``SimWorldSource``), docstrings claiming a
   production feed, the three declarable classes plus an undeclarable fourth plus no
   declaration at all, and eight ways of writing an
   unconditionally empty ``poll_arrivals`` - including one that drains a broker and throws
   the records away - the derived class is ``STUB`` and the loop is never reported as
   externally driven (R4.8).
3. **An unreachable feed degrades and manufactures nothing.** Over six ways a configured
   broker can fail to serve its topic, arbitrary retry budgets, and repeated polls over
   arbitrary windows, every poll yields zero arrivals with ``external_feed_unreachable``,
   and the composed state is non-synthetic *and* degraded - the world does not become
   "synthetic" to explain the empty arrival list, nor read as healthy-and-quiet (R4.5).
   The no-fallback claim is asserted structurally as well: the live source holds no
   generator and no nested source, so there is nothing to fall back *to*.
4. **Classification is total.** Over any set of synthesised implementations, every one gets
   exactly one class from ``(SEEDED, EXTERNAL, STUB, UNCLASSIFIED)``, the violation set
   equals an independent recompute of the gate's own rules, and ``externally_driven``
   stays false for every decision count when no violation-free external body exists.

What the siblings already pin, and what this file therefore does not restate
---------------------------------------------------------------------------

* ``digital_twin/tests/test_world_provenance.py`` (task 10.11) drives a real manual-tick
  ``WorldRuntime`` through the four concrete states a shipped world can be in - seeded,
  feed-driven with opening stock, feed-driven with absent stock (degraded with
  ``external_inventory_absent``), and stub-driven (always degraded). That is the
  behavioural oracle for the runtime half of R4.2/R4.9 and it runs in
  ``ci.yml::quality-gates`` with the rest of ``digital_twin``. Nothing here re-drives the
  twin; the runtime's *structural* obligation - it must not be able to substitute the
  literal opening stock - is pinned below by reading the two modules rather than booting
  them.
* ``packages/tests/test_external_feed_source.py`` (task 10.11) pins the four wiring states
  of a feed by example: unconfigured, one unreachable broker, reachable-and-quiet,
  reachable-with-records, plus the inventory cases and the zero-horizon poll. This file
  generalises the *unreachable* state over the failure modes and the poll windows, which
  is the half an example cannot state.
* ``tests/verify/test_feed_provenance_gate.py`` (task 10.11) pins one example per
  classifier rule and checks the shipped tree classifies cleanly. This file quantifies the
  same classifier over generated implementations and over *sets* of them, adds the
  ``seeded_fallback_reachable`` rule (a feed class holding a generator one scope out,
  which no example covers), and recomputes the violation set independently instead of
  asserting one expected kind is present.

Disclosed bounds
----------------

* ``decision_data_provenance`` deliberately stores ``is_synthetic`` **as handed over**
  rather than re-deriving it, so a writer that disagrees with its own ``source_class``
  leaves that disagreement visible in the audit trail (see the migration's comment). That
  is a different obligation from Property 28 and is covered by
  ``packages/tests/test_canonical_row_append_only_property.py``; asserting agreement here
  would contradict the design.
* ``externally_driven`` needs a count of ``source_class = 'EXTERNAL'`` rows, which only a
  job with the database in front of it can supply. This file asserts the *static* half -
  no count promotes a tree with no violation-free external body - and the database half
  belongs to ``integration.yml``.

**I-0 routing.** Nothing here boots the SimPy twin, opens a socket, or touches Kafka or
Postgres: the feed is driven through the ``FeedConsumer`` protocol seam with fakes, and
the two production twin modules are *parsed*, never imported. So the file carries no
``slow`` marker and runs in ``ci.yml::uplift-verify`` at ``HYPOTHESIS_PROFILE=ci``
alongside the rest of ``tests/verify``. The retry budget is set to fractions of a
millisecond because the ADR-016 backoff policy itself is proven in
``packages/tests/test_retry.py`` and this property must not pay real seconds for it.
``max_examples`` is never set - the budget comes from the root ``conftest.py`` profiles
(``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

This property carries **no numeric threshold**, so there is nothing for it to read from
``infrastructure/quality/``: every assertion is an equality against an independently
recomputed value or a structural fact about a parsed module.

**Validates: Requirements 4.2, 4.5, 4.8, 4.9**
"""

from __future__ import annotations

import ast
import json
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from synapse_common.world.models import SourceProvenance, WorldState
from synapse_common.world.source import (
    DEMAND_TOPIC,
    INVENTORY_TOPIC,
    UNREACHABLE,
    ExternalFeedSource,
    FeedUnreachableError,
    SimWorldSource,
)

from scripts.audit.feed_provenance import (
    DECLARABLE,
    EXTERNAL,
    POLL_METHOD,
    PROVENANCE_METHOD,
    ROOT,
    SEEDED,
    STUB,
    UNCLASSIFIED,
    classify,
    external_implementation_present,
    externally_driven,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable, Sequence
    from pathlib import Path

#: The city every generated source is written for; a record for another city is not ours.
CITY: Final[str] = "bengaluru"

#: Names an implementation can carry, including the two the audit trail names: the
#: pre-10.11 stub *called* ``ExternalFeedSource``, and the seeded generator's own name on a
#: class that reads a feed. R4.8's claim is that the name decides nothing.
CLASS_NAMES: Final[tuple[str, ...]] = (
    "ExternalFeedSource",
    "SimWorldSource",
    "LiveOrderFeed",
    "RealTimeKafkaDemandSource",
    "_Source",
)

#: Docstrings, including ones that claim a production feed the body does not implement.
#: A docstring is an ``ast.Constant``, so the classifier cannot see it - which is the point.
DOCSTRINGS: Final[tuple[str, ...]] = (
    "",
    "Reads real operator orders off synapse.orders.demand.",
    "Non-synthetic demand. Externally driven. The production feed.",
    "Deterministic Poisson demand for the seeded scenario.",
)

#: What ``provenance()`` may declare: the three declarable classes, a fourth that is not in
#: the committed vocabulary, and no method at all.
DECLARATIONS: Final[tuple[str | None, ...]] = (SEEDED, EXTERNAL, STUB, "REALTIME", None)

# ---------------------------------------------------------------------------
# Generated ``poll_arrivals`` bodies
# ---------------------------------------------------------------------------
#: Eight ways to write a ``poll_arrivals`` that can never produce an arrival. R4.8 calls
#: every one of them a stub. ``drains_then_discards`` is the adversarial member: it reaches
#: a broker, so a body that were classified on "does it mention a feed" would credit it -
#: but no record can leave the method, so no arrival can ever reach a decision.
_STUB_BODIES: Final[dict[str, tuple[str, ...]]] = {
    "return_empty_list": ("return []",),
    "return_list_call": ("return list()",),
    "return_none": ("return None",),
    "no_return_at_all": ('logger.info("external_feed_not_wired")',),
    "ellipsis_only": ("...",),
    "log_then_return_empty": (
        'logger.info("external_feed_not_wired", topic=self._topic)',
        "return []",
    ),
    "every_branch_empty": (
        "if horizon_min <= 0.0:",
        "    return []",
        "return list()",
    ),
    "drains_then_discards": (
        "records = self._consumer.drain(max_records=10)",
        "return []",
    ),
}

#: Bodies that can produce an arrival, one per remaining derived class plus the two the
#: gate must reject outright.
_LIVE_BODIES: Final[dict[str, tuple[str, ...]]] = {
    "reads_a_feed": (
        "records = self._consumer.drain(max_records=10)",
        "return self._to_events(records, now_sim_min)",
    ),
    "draws_from_a_generator": (
        "count = self._poisson(self._lambda * horizon_min)",
        "return [self._event(index) for index in range(count)]",
    ),
    "feed_with_seeded_fallback": (
        "try:",
        "    return self._to_events(self._consumer.drain(max_records=10), now_sim_min)",
        "except Exception:",
        "    return [self._event(int(random.random() * 3))]",
    ),
    "neither_feed_nor_generator": ("return self._pending_events",),
}

BODIES: Final[dict[str, tuple[str, ...]]] = {**_STUB_BODIES, **_LIVE_BODIES}

#: The class each body derives, recomputed here rather than imported, so a test comparing
#: the two is comparing two implementations instead of one.
EXPECTED_DERIVED: Final[dict[str, str]] = {
    **dict.fromkeys(_STUB_BODIES, STUB),
    "reads_a_feed": EXTERNAL,
    "draws_from_a_generator": SEEDED,
    "feed_with_seeded_fallback": UNCLASSIFIED,
    "neither_feed_nor_generator": UNCLASSIFIED,
}

#: The violation a body earns on its own, independent of what the class declares.
EXPECTED_BODY_VIOLATION: Final[dict[str, str]] = {
    "feed_with_seeded_fallback": "seeded_fallback_in_feed",
    "neither_feed_nor_generator": "unclassifiable_source",
}

ALL_VARIANTS: Final[tuple[str, ...]] = tuple(BODIES)
STUB_VARIANTS: Final[tuple[str, ...]] = tuple(_STUB_BODIES)

#: Ways a *configured* broker can fail to serve the topic a world was pointed at. Every one
#: is R4.5's "configured and unreachable": the address is set, the client exists, and no
#: arrival can be read.
UNREACHABLE_MODES: Final[tuple[str, ...]] = (
    "factory_raises",
    "metadata_raises_feed_unreachable",
    "metadata_raises_client_error",
    "metadata_advertises_other_topics",
    "metadata_advertises_nothing",
    "drain_raises",
)

#: Modes where the topic check must reject the cluster before any record is read.
_METADATA_MODES: Final[frozenset[str]] = frozenset(
    {
        "metadata_raises_feed_unreachable",
        "metadata_raises_client_error",
        "metadata_advertises_other_topics",
        "metadata_advertises_nothing",
    }
)


# ---------------------------------------------------------------------------
# One generated WorldSource implementation
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ImplementationSpec:
    """A synthesised ``WorldSource`` implementation plus its independently known class.

    ``holds_generator`` adds an ``__init__`` that keeps a seeded RNG on the instance. For a
    body that reads a feed that is R4.5 one scope wider - the fallback need not be *taken*
    to exist - and the gate must report ``seeded_fallback_reachable``.
    """

    class_name: str
    docstring: str
    declared: str | None
    variant: str
    holds_generator: bool

    def source(self) -> str:
        """Render the implementation as the module text the gate would parse."""
        lines = [f"class {self.class_name}:"]
        if self.docstring:
            lines.append(f'    """{self.docstring}"""')
        if self.holds_generator:
            lines.extend(
                [
                    "    def __init__(self, seed):",
                    "        self._rng = random.Random(seed)",
                ]
            )
        if self.declared is not None:
            lines.extend(
                [
                    f"    def {PROVENANCE_METHOD}(self):",
                    f"        return SourceProvenance.{self.declared}",
                ]
            )
        lines.append(f"    def {POLL_METHOD}(self, now_sim_min, horizon_min):")
        lines.extend(f"        {line}" for line in BODIES[self.variant])
        return "\n".join([*lines, ""])

    def classdef(self) -> ast.ClassDef:
        """Parse the rendered source into the ``ClassDef`` the classifier consumes."""
        node = ast.parse(self.source()).body[0]
        assert isinstance(node, ast.ClassDef)
        return node

    def expected_derived(self) -> str:
        """The class the body mandates - a function of the body alone."""
        return EXPECTED_DERIVED[self.variant]

    def expected_violation_kinds(self) -> frozenset[str]:
        """The gate's rules restated: body defect, reachable fallback, declaration clash.

        The declaration clauses are mutually exclusive and ordered, exactly as the gate
        orders them: an undeclared source is reported as undeclared rather than also as
        contradicting a body it never made a claim about.
        """
        derived = self.expected_derived()
        kinds: set[str] = set()
        body_violation = EXPECTED_BODY_VIOLATION.get(self.variant)
        if body_violation is not None:
            kinds.add(body_violation)
        if derived == EXTERNAL and self.holds_generator:
            kinds.add("seeded_fallback_reachable")
        if self.declared is None:
            kinds.add("undeclared_provenance")
        elif self.declared not in DECLARABLE:
            kinds.add("unknown_declared_class")
        elif self.declared != derived:
            kinds.add("declaration_contradicts_body")
        return frozenset(kinds)

    def anonymised(self) -> ImplementationSpec:
        """The same implementation stripped of its name and its docstring."""
        return ImplementationSpec(
            class_name="_Anonymous",
            docstring="",
            declared=self.declared,
            variant=self.variant,
            holds_generator=self.holds_generator,
        )


# ---------------------------------------------------------------------------
# Broker fakes over the ``FeedConsumer`` protocol seam (no Kafka, I-0)
# ---------------------------------------------------------------------------
class _BrokenConsumer:
    """A configured broker that cannot serve the topic it was pointed at.

    Counts its own calls so a test can assert the *shape* of the failure - a cluster whose
    metadata was rejected must never have been drained - rather than only its outcome.
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.drained = 0
        self.closed = 0

    def reachable_topics(self, timeout: float = 5.0) -> tuple[str, ...]:
        if self.mode == "metadata_raises_feed_unreachable":
            raise FeedUnreachableError("no broker answered within the metadata timeout")
        if self.mode == "metadata_raises_client_error":
            raise RuntimeError("connection refused by every bootstrap server")
        if self.mode == "metadata_advertises_other_topics":
            return ("synapse.something.else", "synapse.telemetry")
        if self.mode == "metadata_advertises_nothing":
            return ()
        return (DEMAND_TOPIC, INVENTORY_TOPIC)

    def drain(self, *, max_records: int = 1000, timeout: float = 1.0) -> list[dict[str, Any]]:
        self.drained += 1
        if self.mode == "drain_raises":
            raise TimeoutError("no records available within the poll timeout")
        # Deliberately not an exception: ``_drain_once`` converts any client failure into
        # an unreachable feed, which would hide a defect in this fake. An empty batch makes
        # the source report "reachable and quiet", which the assertions catch loudly.
        return []

    def close(self) -> None:
        self.closed += 1


class _ReachableConsumer:
    """A reachable broker that hands over one batch for one topic, then nothing."""

    def __init__(self, batches: dict[str, list[dict[str, Any]]], topic: str) -> None:
        self._batches = batches
        self._topic = topic

    def reachable_topics(self, timeout: float = 5.0) -> tuple[str, ...]:
        return (DEMAND_TOPIC, INVENTORY_TOPIC)

    def drain(self, *, max_records: int = 1000, timeout: float = 1.0) -> list[dict[str, Any]]:
        return self._batches.pop(self._topic, [])[:max_records]

    def close(self) -> None:
        return None


def _broken_factory(
    mode: str,
    consumers: list[_BrokenConsumer],
) -> Callable[[str], _BrokenConsumer]:
    """A consumer factory for one failure mode, recording every client it builds."""

    def factory(topic: str) -> _BrokenConsumer:
        if mode == "factory_raises":
            raise RuntimeError(f"consumer for {topic} could not be constructed")
        consumer = _BrokenConsumer(mode)
        consumers.append(consumer)
        return consumer

    return factory


def _feed(
    factory: Callable[[str], Any],
    *,
    max_retries: int = 1,
) -> ExternalFeedSource:
    """A *configured* external feed over an injected factory.

    An injected factory is itself a configuration, so this is the R4.5 subject: configured,
    and reachable or not depending on what the factory builds. The retry budget is
    fractions of a millisecond - ADR-016's policy is proven in
    ``packages/tests/test_retry.py`` and this property must not pay real backoff (I-0).
    """
    return ExternalFeedSource(
        city=CITY,
        consumer_factory=factory,
        poll_timeout_s=0.01,
        max_retries=max_retries,
        retry_base_delay_s=1e-4,
    )


def _fallback_surfaces(source: object) -> tuple[str, ...]:
    """Attributes on ``source`` that could advance demand from a generator (R4.5).

    Structural rather than behavioural, because R4.5's claim is stronger than "the fallback
    branch was not taken": an unreachable feed must have nothing to fall back *to*. A
    seeded RNG or a nested ``WorldSource`` on the instance would be that something.
    """
    offenders = [
        name
        for name, value in vars(source).items()
        if isinstance(value, random.Random) or callable(getattr(value, POLL_METHOD, None))
    ]
    return tuple(sorted(offenders))


def _state_from(source: Any, *, sim_time_min: float) -> WorldState:
    """Compose the reading a runtime would perceive from this source, and nothing more.

    Only what the source itself declares is passed: its class, and its last poll's
    degradation. Stated as a bound rather than a claim - ``WorldRuntime._degraded_reason``
    adds two conditions this composition does not model (a boot-time absent snapshot, and
    the rule that a ``STUB`` source is degraded whatever it reports), and both are pinned
    behaviourally in ``digital_twin/tests/test_world_provenance.py`` against a real
    manual-tick runtime. Every source composed here is ``SEEDED`` or ``EXTERNAL`` with a
    boot that supplied stock or never happened, which is exactly the case where the live
    poll's degradation is the reason ``perceive()`` would report.
    """
    reason = source.degradation()
    return WorldState(
        city=CITY,
        sim_time_min=sim_time_min,
        source_class=source.provenance(),
        degraded=reason is not None,
        degraded_reason=reason,
    )


# ---------------------------------------------------------------------------
# Static readers for the two twin modules (parsed, never imported)
# ---------------------------------------------------------------------------
def _parse(path: Path) -> ast.Module:
    """Parse a production module without importing it (E-S13-07: explicit encoding)."""
    return ast.parse(path.read_text(encoding="utf-8"))


def _function_named(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found")


def _method_of(tree: ast.AST, class_name: str, method: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return _function_named(node, method)
    raise AssertionError(f"class {class_name} not found")


def _names_of(node: ast.AST) -> set[str]:
    return {inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name)}


def _is_none_identity_check(test: ast.expr, name: str) -> bool:
    """Whether ``test`` is exactly ``name is None`` - identity, not falsiness."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    left = test.left
    comparator = test.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == name
        and isinstance(test.ops[0], ast.Is)
        and isinstance(comparator, ast.Constant)
        and comparator.value is None
    )


def _is_truthiness_check(test: ast.expr, name: str) -> bool:
    """Whether ``test`` reads ``name`` for truth - ``if name:`` or ``if not name:``."""
    if isinstance(test, ast.Name) and test.id == name:
        return True
    return (
        isinstance(test, ast.UnaryOp)
        and isinstance(test.op, ast.Not)
        and isinstance(test.operand, ast.Name)
        and test.operand.id == name
    )


def _assignments_to(fn: ast.FunctionDef, attribute: str) -> list[ast.Assign]:
    return [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute) and target.attr == attribute
            for target in node.targets
        )
    ]


def _keyword_value(call: ast.Call, name: str) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
def _ascii_text(*, min_size: int = 1, max_size: int = 12) -> st.SearchStrategy[str]:
    """Printable-ASCII text, so a counterexample prints on a Windows console."""
    return st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=min_size,
        max_size=max_size,
    )


@st.composite
def world_state_fields(draw: st.DrawFn) -> dict[str, Any]:
    """Every ``WorldState`` field except ``source_class``, drawn independently.

    Independently on purpose, including combinations a runtime would not emit (a
    ``degraded_reason`` beside ``degraded=False``): the claim is that *no* other field can
    move the derived flag, which is a statement about the whole field space rather than
    about the states that arise today.
    """
    fraction = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    return {
        "city": draw(_ascii_text()),
        "sim_time_min": draw(
            st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
        ),
        "inventory": draw(
            st.dictionaries(
                keys=st.sampled_from(("sku_1", "sku_2", "sku_3")),
                values=st.floats(
                    min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False
                ),
                max_size=3,
            )
        ),
        "pending_orders": draw(st.integers(min_value=0, max_value=500)),
        "fill_rate": draw(fraction),
        "spoilage_rate": draw(fraction),
        "avg_delivery_min": draw(
            st.floats(min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False)
        ),
        "restocks_triggered": draw(st.integers(min_value=0, max_value=500)),
        "demand_rate": draw(
            st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False)
        ),
        "clock_advancing": draw(st.booleans()),
        "degraded": draw(st.booleans()),
        "degraded_reason": draw(st.none() | st.sampled_from((UNREACHABLE, "clock_stalled"))),
    }


@st.composite
def implementation_specs(
    draw: st.DrawFn,
    *,
    variants: Sequence[str] = ALL_VARIANTS,
) -> ImplementationSpec:
    """One synthesised implementation over names, docstrings, declarations, and bodies."""
    return ImplementationSpec(
        class_name=draw(st.sampled_from(CLASS_NAMES)),
        docstring=draw(st.sampled_from(DOCSTRINGS)),
        declared=draw(st.sampled_from(DECLARATIONS)),
        variant=draw(st.sampled_from(tuple(variants))),
        holds_generator=draw(st.booleans()),
    )


@st.composite
def inventory_records(draw: st.DrawFn) -> dict[str, Any]:
    """One inventory-snapshot record, usable or not.

    ``level`` is drawn over floats (including negative ones), booleans, and ``None`` so the
    reject paths are reachable: a feed that published ``level: true`` must not be read as
    one unit, and a negative stock level is not a stock level.
    """
    return {
        "city": draw(st.sampled_from((CITY, "mumbai"))),
        "sku_id": draw(st.sampled_from(("sku_1", "sku_2", ""))),
        "level": draw(
            st.one_of(
                st.floats(
                    min_value=-50.0, max_value=500.0, allow_nan=False, allow_infinity=False
                ),
                st.booleans(),
                st.none(),
            )
        ),
    }


def expected_opening_stock(records: Sequence[dict[str, Any]]) -> dict[str, float]:
    """The opening stock the published snapshots support - a later record supersedes.

    An independent restatement of the source's own acceptance rules: this city only, a
    non-empty SKU, a finite non-negative numeric level, and ``bool`` excluded because
    ``True`` is an ``int`` in Python.
    """
    levels: dict[str, float] = {}
    for record in records:
        if record.get("city") != CITY:
            continue
        sku = record.get("sku_id")
        level = record.get("level")
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            continue
        if isinstance(sku, str) and sku and level >= 0.0:
            levels[sku] = float(level)
    return levels


# ---------------------------------------------------------------------------
# Clause 1: the flag is a function of the active source, and of nothing else
# ---------------------------------------------------------------------------
# Feature: purpose-achievement-audit, Property 28: World provenance is derived, never asserted
@given(provenance=st.sampled_from(tuple(SourceProvenance)), fields=world_state_fields())
def test_is_synthetic_is_derived_from_the_active_source_and_from_nothing_else(
    provenance: SourceProvenance,
    fields: dict[str, Any],
) -> None:
    """R4.2: ``is_synthetic`` is true iff the source is seeded, whatever else is true."""
    state = WorldState(source_class=provenance, **fields)

    assert state.is_synthetic is (provenance is SourceProvenance.SEEDED)
    # Exactly one of the three classes reports synthetic, so "not synthetic" is not a
    # bucket two different declarations can mean two different things by. STUB reports
    # false because a stub is not a seeded generator, never because it is real - and a
    # stub-driven runtime is always degraded beside it (pinned behaviourally in
    # digital_twin/tests/test_world_provenance.py).
    synthetic = {
        candidate
        for candidate in SourceProvenance
        if WorldState(source_class=candidate, **fields).is_synthetic
    }
    assert synthetic == {SourceProvenance.SEEDED}

    # There is no field to assert, and no keyword to pass, in either direction. The
    # dishonest claim is unrepresentable rather than merely discouraged.
    assert "is_synthetic" not in WorldState.model_fields
    assert "source_class" in WorldState.model_fields
    for claimed in (True, False):
        with pytest.raises(ValidationError):
            WorldState(source_class=provenance, is_synthetic=claimed, **fields)

    # The serialised reading carries the derived value, so a consumer of the payload sees
    # the same flag the model computes - it is not a view that only Python callers get.
    payload = json.loads(state.to_deterministic_json())
    assert payload["is_synthetic"] is state.is_synthetic
    assert payload["source_class"] == provenance.value

    # Re-declaring the source is the only thing that moves the flag. Copying the state and
    # changing any other field cannot.
    for other in SourceProvenance:
        redeclared = state.model_copy(update={"source_class": other})
        assert redeclared.is_synthetic is (other is SourceProvenance.SEEDED)
    for field, value in (("degraded", not state.degraded), ("clock_advancing", False)):
        assert state.model_copy(update={field: value}).is_synthetic is state.is_synthetic


@given(
    seed=st.integers(min_value=1, max_value=2**16),
    arrival_rate=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False),
    horizon_min=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_a_seeded_generator_derives_a_synthetic_undegraded_reading(
    seed: int,
    arrival_rate: float,
    horizon_min: float,
) -> None:
    """R4.2 / R4.9: a seeded world is synthetic, and its literal stock is not a defect.

    The seeded generator supplies no inventory either, and that is deliberately *not* the
    R4.9 degradation: R4.9 scopes the obligation to a source that is not a seeded
    generator, where opening stock is a fact about a real store rather than a declared
    component of a scenario. So a seeded world must stay undegraded on this account.
    """
    source = SimWorldSource(
        city=CITY,
        store_ids=["store_001"],
        sku_ids=["sku_1", "sku_2"],
        arrival_rate_per_min=arrival_rate,
        seed=seed,
    )
    arrivals = source.poll_arrivals(0.0, horizon_min)

    assert source.provenance() is SourceProvenance.SEEDED
    assert source.initial_inventory() is None
    assert source.degradation() is None
    # Producing arrivals does not change what the source is: the declaration is a property
    # of the origin, not of the last poll's yield.
    assert source.provenance() is SourceProvenance.SEEDED
    state = _state_from(source, sim_time_min=0.0)
    assert state.is_synthetic is True
    assert state.degraded is False
    assert state.degraded_reason is None
    # Every arrival is this world's own, drawn from this source's own RNG, so the reading
    # is synthetic however many there are - including none, on a zero-length horizon.
    assert all(event.city == CITY for event in arrivals)


# ---------------------------------------------------------------------------
# Clause 2: a stub is a stub however it is named, documented, or declared
# ---------------------------------------------------------------------------
@given(
    spec=implementation_specs(variants=STUB_VARIANTS),
    decisions=st.integers(min_value=0, max_value=99),
)
def test_a_stub_is_classified_stub_however_it_is_named_or_documented(
    spec: ImplementationSpec,
    decisions: int,
) -> None:
    """R4.8: an unconditionally empty arrival list is a stub, and never externally driven."""
    report = classify("generated.py", spec.classdef())

    assert report.derived == STUB
    assert {violation.kind for violation in report.violations} == spec.expected_violation_kinds()
    assert report.evidence  # a reader is told why, not just told the verdict

    # A stub can never make the loop externally driven - not with any declaration, and not
    # with any number of recorded decisions behind it (I-7: a claim is not evidence).
    assert external_implementation_present([report]) is False
    assert externally_driven([report], decisions) is False

    # The same body with no name to trade on and no docstring to claim with classifies
    # identically: the single variable that could have moved the verdict did not exist.
    anonymous = classify("generated.py", spec.anonymised().classdef())
    assert anonymous.derived == report.derived
    assert {v.kind for v in anonymous.violations} == {v.kind for v in report.violations}


# ---------------------------------------------------------------------------
# Clause 3: a configured-but-unreachable feed degrades and manufactures nothing
# ---------------------------------------------------------------------------
@given(
    mode=st.sampled_from(UNREACHABLE_MODES),
    max_retries=st.integers(min_value=1, max_value=3),
    windows=st.lists(
        st.tuples(
            st.floats(min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False),
            st.floats(min_value=1e-3, max_value=180.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=1,
        max_size=3,
    ),
)
def test_an_unreachable_feed_yields_a_degraded_state_with_zero_arrivals(
    mode: str,
    max_retries: int,
    windows: list[tuple[float, float]],
) -> None:
    """R4.5: degraded, zero arrivals, and demand never advances from a generator."""
    consumers: list[_BrokenConsumer] = []
    source = _feed(_broken_factory(mode, consumers), max_retries=max_retries)

    assert source.provenance() is SourceProvenance.EXTERNAL

    for now_sim_min, horizon_min in windows:
        assert source.poll_arrivals(now_sim_min, horizon_min) == []
        assert source.degradation() == UNREACHABLE

        # The reading is non-synthetic AND degraded. Neither escape is available: the world
        # does not turn synthetic to account for the empty arrival list, and it does not
        # read as healthy-and-quiet, which is what a reachable feed with no orders reports.
        state = _state_from(source, sim_time_min=now_sim_min)
        assert state.is_synthetic is False
        assert state.degraded is True
        assert state.degraded_reason == UNREACHABLE

    # R4.9 on the same source: no opening stock is invented for a world that cannot be
    # reached, and the degradation is still reported rather than cleared by the attempt.
    assert source.initial_inventory() is None
    assert source.degradation() == UNREACHABLE

    # R4.5 structurally: after every one of those failures there is still no generator and
    # no nested source on the instance, so there is nothing here to fall back to.
    assert _fallback_surfaces(source) == ()

    # The failure had the shape it claimed: a cluster whose metadata was rejected was never
    # drained, and every client that was built was closed.
    if mode in _METADATA_MODES:
        assert all(consumer.drained == 0 for consumer in consumers)
    assert all(consumer.closed >= 1 for consumer in consumers)
    assert (mode == "factory_raises") is (consumers == [])


# ---------------------------------------------------------------------------
# Clause 4a: absent inventory degrades rather than substituting a literal
# ---------------------------------------------------------------------------
@given(records=st.lists(inventory_records(), max_size=6))
def test_absent_inventory_returns_nothing_and_a_present_one_is_never_padded(
    records: list[dict[str, Any]],
) -> None:
    """R4.9: the opening stock is exactly what was published, or it is absent."""
    batches = {INVENTORY_TOPIC: list(records)}
    source = _feed(lambda topic: _ReachableConsumer(batches, topic))
    expected = expected_opening_stock(records)

    opening = source.initial_inventory()

    if not expected:
        # Absent, not empty-but-present and not a stand-in. ``None`` is what lets the
        # runtime degrade; a ``{}`` would be a reading, and a literal would be fiction.
        assert opening is None
    else:
        assert opening is not None
        assert opening == expected
        # Nothing was padded in: every SKU reported was published for this city, so no
        # invented level can reach a fill-rate or stockout-risk KPI.
        assert set(opening) == set(expected)
    # Reachable and quiet is not a fault, so an absent snapshot is not reported as an
    # unreachable feed - the runtime attaches the absent-inventory reason at boot instead
    # (pinned behaviourally in digital_twin/tests/test_world_provenance.py).
    assert source.degradation() is None
    assert _fallback_surfaces(source) == ()


def test_the_twin_engine_reaches_its_literal_opening_stock_only_when_none_is_supplied() -> None:
    """R4.9, structurally: the empty mapping the runtime passes must not resurrect the literal.

    Parsed rather than imported and never started, so this states the obligation without
    booting SimPy (I-0). The trap being pinned is a one-character one: ``if not
    initial_inventory:`` would send the empty mapping ``WorldRuntime`` passes for an absent
    snapshot straight back into ``{sku_i: 100.0 for i in range(10)}``, which is exactly the
    fabricated stock R4.9 forbids. Only ``is None`` distinguishes "supplied nothing" from
    "supplied an empty snapshot".
    """
    start = _method_of(
        _parse(ROOT / "digital_twin" / "simulation" / "engine.py"),
        "SupplyChainSimulation",
        "start",
    )
    arguments = {arg.arg for arg in (*start.args.args, *start.args.kwonlyargs)}
    assert "initial_inventory" in arguments

    guards = [
        node
        for node in ast.walk(start)
        if isinstance(node, ast.If) and _is_none_identity_check(node.test, "initial_inventory")
    ]
    assert len(guards) == 1, "the opening-stock guard is not a single `is None` check"
    assert not [
        node
        for node in ast.walk(start)
        if isinstance(node, ast.If) and _is_truthiness_check(node.test, "initial_inventory")
    ], "an absent snapshot is distinguished by identity, never by truthiness"

    guarded = {id(inner) for stmt in guards[0].body for inner in ast.walk(stmt)}
    assignments = _assignments_to(start, "_inventory")
    literal = [node for node in assignments if id(node) in guarded]
    supplied = [node for node in assignments if id(node) not in guarded]

    assert len(literal) == 1, "the literal opening stock is not the guarded branch"
    assert len(supplied) == 1, "the supplied opening stock is not the unguarded branch"
    assert "initial_inventory" not in _names_of(literal[0])
    assert "initial_inventory" in _names_of(supplied[0])


def test_the_runtime_never_starts_a_non_seeded_world_on_a_substituted_stock() -> None:
    """R4.9, structurally: every non-seeded boot passes an explicit opening stock.

    Also parsed, not imported. The behavioural half - ``perceive()`` reporting
    ``external_inventory_absent`` with an empty inventory - is
    ``digital_twin/tests/test_world_provenance.py``, which drives a real manual-tick
    runtime; what cannot be seen from one boot is that *no* path through this function can
    hand the engine a populated literal, and that is what is asserted here.
    """
    boot = _function_named(
        _parse(ROOT / "digital_twin" / "world" / "runtime.py"),
        "_start_from_non_seeded_source",
    )
    starts = [
        node
        for node in ast.walk(boot)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "start"
    ]
    assert starts, "the non-seeded boot path does not start the simulation"

    empty_mappings = 0
    for call in starts:
        value = _keyword_value(call, "initial_inventory")
        assert value is not None, "a non-seeded boot omitted initial_inventory"
        # A comprehension or a populated literal here would be a substituted stock, which
        # is the failure R4.9 names. An empty mapping substitutes nothing.
        assert not isinstance(value, ast.DictComp)
        if isinstance(value, ast.Dict):
            assert not value.keys
            empty_mappings += 1

    assert empty_mappings >= 1, "no boot path starts the world genuinely empty"
    assert "INVENTORY_ABSENT" in _names_of(boot), "the absent snapshot is not reported"


# ---------------------------------------------------------------------------
# Clause 4b: classification is total over any set of implementations
# ---------------------------------------------------------------------------
@given(
    specs=st.lists(implementation_specs(), max_size=5),
    decisions=st.integers(min_value=0, max_value=99),
)
def test_classification_is_total_over_any_set_of_implementations(
    specs: list[ImplementationSpec],
    decisions: int,
) -> None:
    """R4.8: every implementation gets exactly one class, and none is omitted."""
    reports = [
        classify(f"generated_{index}.py", spec.classdef()) for index, spec in enumerate(specs)
    ]
    classes = (*DECLARABLE, UNCLASSIFIED)

    assert len(reports) == len(specs)
    for spec, report in zip(specs, reports, strict=True):
        assert report.derived in classes
        assert report.derived == spec.expected_derived()
        assert {v.kind for v in report.violations} == spec.expected_violation_kinds()
        assert report.evidence
        # Pure: the classifier reads no file and holds no state, so a second pass over the
        # same class must produce the same report.
        assert classify(report.file, spec.classdef()) == report

    # The four classes partition the set: nothing lands in neither list and nothing in two.
    counts = {cls: sum(1 for report in reports if report.derived == cls) for cls in classes}
    assert sum(counts.values()) == len(reports)

    # Capability is derived from bodies, evidence from recorded decisions, and the loop is
    # externally driven only with both. No count promotes a tree that cannot read a feed.
    capable = any(report.derived == EXTERNAL and not report.violations for report in reports)
    assert external_implementation_present(reports) is capable
    assert externally_driven(reports, 0) is False
    assert externally_driven(reports, decisions) is (capable and decisions > 0)


def test_the_declarable_vocabulary_is_one_vocabulary_across_model_gate_and_schema() -> None:
    """R4.8 rests on a closed class set; three copies of it must not drift apart.

    ``UNCLASSIFIED`` is deliberately absent from the declarable tuple: it is the residual
    the gate reports for a body it cannot place, not a class an implementation may claim.
    A fourth declared class would be rejected by Postgres at INSERT time, so a fourth added
    to the enum or the gate alone is a latent write failure, not a new category.
    """
    assert DECLARABLE == tuple(provenance.value for provenance in SourceProvenance)
    assert UNCLASSIFIED not in DECLARABLE

    ddl = (
        ROOT / "orchestrator" / "audit" / "migrations" / "0007_decision_data_provenance.sql"
    ).read_text(encoding="utf-8")
    for value in DECLARABLE:
        assert f"'{value}'" in ddl, f"{value} is declarable but absent from the CHECK constraint"


def test_the_generated_body_table_covers_every_class_the_gate_can_derive() -> None:
    """A class the gate can derive with no generated body would go unquantified silently."""
    assert set(EXPECTED_DERIVED) == set(BODIES)
    assert set(EXPECTED_DERIVED.values()) == {*DECLARABLE, UNCLASSIFIED}
    assert set(EXPECTED_BODY_VIOLATION) <= set(BODIES)
    assert STUB_VARIANTS and set(STUB_VARIANTS) < set(ALL_VARIANTS)
