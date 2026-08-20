"""Make SYNAPSE's *agency* mechanically verifiable (ADR-052) -- by observed world delta.

Sprints 11-19 proved the enforcement boundary; the Substance Mandate proved agent
outputs are real. This gate proves the system is *agentic* -- that the perceive ->
decide -> act -> learn loop actually exists and cannot silently regress to the
request-response pipeline the 2026-06-17 audit found.

Five structural invariants (a regression on any one fails ``--check``):

  * **A. autonomous_trigger** -- ``orchestrator/sensor/loop.py`` defines ``SensorLoop`` and
    it calls ``run_consensus`` (the system initiates decisions itself, not only on POST).
  * **B. sensor_wired** -- the orchestrator lifespan starts the SensorLoop.
  * **C. standing_world** -- ``digital_twin/world/runtime.py`` defines ``WorldRuntime`` with
    ``perceive`` + ``apply_action`` (a world to sense and change).
  * **D. real_actuation** -- at least one agent ``execute()`` reaches an actuator / event
    source on a *reachable* statement (not a status-dict-only stub).
  * **E. learn_from_world** -- the consensus learns from the realized world
    (``world_observer`` / ``_build_learning_outcome``), not the predicted utility.

A sixth, independently-verifiable signal -- **binding_arbitration** -- AST-asserts that the
full-path ratified action is chosen by the Pareto-knee ``select_binding_action`` and *not*
by a raw ``argmax`` over ``utility_score`` (ADR-052 / Requirements 9.1).

Plus a **ratchet**: the count of agents whose ``execute()`` is still the
``{"kafka_published": True}`` stub. ``--max-stubs`` defaults to 0 -- every agent is now
converted to real actuation or an Honest No-Op -- so any regression to the status-dict stub
fails the gate (parity with ``substance_truth``/coverage floors).

The delta is the oracle (design AD-5 / E2.2, R9)
------------------------------------------------
The 2026-06-17 audit's central charge against this gate was that "converted" was decided
by ``"WorldAction" in src`` -- a substring match, in a codebase whose own task list told
the implementation which substring to write. A gate satisfiable by vocabulary is not an
independent oracle. So the vocabulary pass is **demoted to a fast pre-filter** and the
classification comes from behaviour, at the standard
``orchestrator/tests/test_real_actuation_e2e.py`` already met once: snapshot
``WorldRuntime.perceive()``, invoke the handler's real ``execute()``, read the world back
through ``perceive()``, and classify from the difference. The agent's own report is
*evidence about the agent*, never evidence about the world.

Four classes, total over every discovered handler, so no agent can land in neither list
(R9.4): ``ACTUATING`` / ``EVENT_ONLY`` / ``INERT`` / ``UNCLASSIFIED``. The count reported
is the count compared against the baseline (R9.8), and that identity is itself a check.

**Two seams, deliberately separate.** ``probe_actuation`` drives a real ``WorldRuntime``
and is therefore a CI workload (``ci.yml::uplift-verify``, ``@pytest.mark.slow``), never a
local one (I-0). Everything that decides anything is pure: :func:`classify` maps one
:class:`AgentProbeObservation` to one :class:`AgentActuationReport`, and
:func:`evaluate_actuation` maps a sequence of observations to a verdict. Both read no
file, drive no world, and touch no process state -- mirroring the
``registry_gate.evaluate_results`` / ``doc_truth.evaluate_claims`` seams -- so totality
and behaviour can be property-tested without a simulation.

**Disclosed bound of the probe (I-7).** ``WorldState`` exposes ``inventory`` and
``demand_rate`` (the latter derived from the sim's public ``demand_mult`` property), so a
``REORDER`` and a ``SET_PRICE_MULT`` / ``demand_mult`` lever are visible in the very next
``perceive()``. ``dispatch_speed`` and ``lead_time_mult`` are **private** to
``SupplyChainSimulation`` and surface only after the clock advances, mixed with demand
consumption. An agent whose only lever is one of those cannot be decided by an immediate
delta: it is reported ``UNCLASSIFIED`` with the reason, not accused of being a stub and
not credited as actuating. Absence of proof is neither (I-7). Making those three agents
provable means exposing their levers on ``WorldState`` -- a change to the perception
surface, tracked outside this gate.

Run::

    python -m scripts.audit.agency_truth            # human table (static, laptop-safe)
    python -m scripts.audit.agency_truth --json
    python -m scripts.audit.agency_truth --check     # exit 1 on a regression
    python -m scripts.audit.agency_truth --probe     # CI ONLY: drives a real WorldRuntime
"""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / "agents"

# Ensure the repo root is importable when run as a bare script (not -m).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Default ratchet ceiling: agents still on the status-dict-only execute() stub. The
# broaden-to-8 work converted every agent to real actuation or an Honest No-Op, so the
# ceiling is now 0 and may only stay at 0 (R8.2/R8.5; ADR-052).
# Pinned by infrastructure/quality/ratchets.json ("actuation-stub-ceiling", extractor
# regex:^DEFAULT_MAX_STUBS = (?P<value>\\d+)$) -- do not reformat this line.
DEFAULT_MAX_STUBS = 0

#: Recorded baseline for the count of agents observed ACTUATING (R9.3). ``None`` means
#: **unmeasured**: no run has ever recorded an observed-delta count, so there is nothing to
#: regress against and the baseline clause reports ``unavailable`` rather than inventing a
#: number (I-7, and the CF-3 precedent for the coverage floors). ``ratchets.json`` records
#: why the *inferred* count was deliberately never ratcheted: "Ratcheting an inferred count
#: would pin the inference, not the behaviour." The first ``ci.yml::uplift-verify`` run that
#: executes :func:`probe_actuation` seeds this number; until then the comparison mechanism
#: below is live but has no bound to enforce.
ACTUATING_BASELINE: int | None = None

# The five structural loop invariants the gate enforces in --check (R8.7). The
# binding-arbitration signal (R9.1) is an additional, independently-verifiable check.
STRUCTURAL_INVARIANTS = (
    "autonomous_trigger",
    "sensor_wired",
    "standing_world",
    "learn_from_world",
    "real_actuation",
)

#: Behavioural checks this gate adds on top of the structural five (R9.2-R9.9).
BEHAVIOURAL_CHECKS = (
    "handlers_parseable",
    "agents_declared",
    "producer_wiring",
    "classification_total",
    "count_integrity",
    "inert_reports_executed",
    "actuating_baseline",
)

# ---------------------------------------------------------------------------
# Actuation markers. These are a PRE-FILTER, never a verdict (R9.7): a marker can
# only ever withhold the ACTUATING class, never grant it. They are matched against
# the AST nodes of statements *reachable from the invoked execute() path*, so a
# marker in a comment, a docstring, a nested def, or a branch that cannot execute
# contributes nothing.
# ---------------------------------------------------------------------------
WORLD_MARKERS = ("WorldAction", "self._actuator", "actuate_items")
EVENT_MARKERS = ("self._kafka.produce", "honest_produce")
ACTUATION_MARKERS = WORLD_MARKERS + EVENT_MARKERS


class ActuationClass(StrEnum):
    """The four total classes a discovered agent handler can be assigned (R9.4)."""

    ACTUATING = "actuating"  # perceive() differs across execute()
    EVENT_ONLY = "event_only"  # no world delta, a real publish with a real producer
    INERT = "inert"  # reports work, changes nothing, publishes nothing
    UNCLASSIFIED = "unclassified"  # discovered but not probeable


class LeverSpec(BaseModel):
    """The world lever an agent's ``execute()`` actuates, and whether it is perceivable.

    ``perceivable`` records whether the effect of this lever appears in the very next
    ``WorldState`` returned by ``WorldRuntime.perceive()``. It is a property of the
    *perception surface*, not of the agent: ``inventory`` and ``demand_rate`` are exposed,
    ``dispatch_speed`` and ``lead_time_mult`` are private to the simulation and surface
    only after the clock advances. A non-perceivable lever makes the agent undecidable by
    an immediate delta, which is reported honestly rather than guessed (I-7).
    """

    model_config = ConfigDict(frozen=True)

    kind: str | None  # WorldActionKind value; None => the agent has no world lever
    lever_key: str
    perceivable: bool
    observed_field: str  # the WorldState field the lever shows up in ("" when none)
    note: str


#: Every agent this gate expects to discover, with its declared lever. A handler found on
#: disk with no entry here is ``UNCLASSIFIED`` **and** a FAIL naming it, so a new agent
#: cannot be added without declaring what it actuates (R9.4).
AGENT_LEVERS: Mapping[str, LeverSpec] = {
    "inventory_sentinel": LeverSpec(
        kind="reorder",
        lever_key="quantity",
        perceivable=True,
        observed_field="inventory",
        note="add_stock raises the SKU level, which perceive() returns in inventory.",
    ),
    "pricing_oracle": LeverSpec(
        kind="set_price_mult",
        lever_key="price_mult",
        perceivable=True,
        observed_field="demand_rate",
        note="the world converts price to demand_mult, exposed via perceive().demand_rate.",
    ),
    "demand_prophet": LeverSpec(
        kind="set_policy",
        lever_key="demand_mult",
        perceivable=True,
        observed_field="demand_rate",
        note="demand_mult is a public sim property, so perceive().demand_rate moves with it.",
    ),
    "routing_navigator": LeverSpec(
        kind="set_policy",
        lever_key="dispatch_speed",
        perceivable=False,
        observed_field="",
        note=(
            "SupplyChainSimulation._dispatch_speed is private and WorldState exposes no "
            "dispatch field, so the lever cannot be seen in the next perceive()."
        ),
    ),
    "freshness_guardian": LeverSpec(
        kind="set_policy",
        lever_key="dispatch_speed",
        perceivable=False,
        observed_field="",
        note=(
            "same private dispatch_speed lever; the spoilage effect appears only after the "
            "clock advances, where it is inseparable from demand consumption."
        ),
    ),
    "disruption_shield": LeverSpec(
        kind="set_policy",
        lever_key="lead_time_mult",
        perceivable=False,
        observed_field="",
        note=(
            "SupplyChainSimulation._lead_time_mult is private and absent from WorldState."
        ),
    ),
    "supplier_trust": LeverSpec(
        kind=None,
        lever_key="",
        perceivable=False,
        observed_field="",
        note="no world lever by design: execute() event-sources the ratified trust score.",
    ),
    "sustainability_agent": LeverSpec(
        kind=None,
        lever_key="",
        perceivable=False,
        observed_field="",
        note="Honest No-Op: the standing world has no carbon lever (ADR-052 R6.2).",
    ),
}

# ---------------------------------------------------------------------------
# Probe fixtures: one schema-valid ratified consensus_action per agent.
#
# These are DATA, not logic. Each is the smallest payload that makes exactly one
# actionable item for the agent's lever, so a handler that actuates has something to
# actuate and a handler that does not cannot blame an empty proposal. The shapes mirror
# proto/domain/ (the same ones agents/tests/test_actuation_pbt.py validates against);
# five handlers call validate_agent_payload() on this payload inside execute(), so an
# invalid fixture would diverge before touching the world.
# ---------------------------------------------------------------------------
_PROBE_CITY = "bengaluru"
_PROBE_STORE = "STORE_BLR_001"
_PROBE_TS = "2025-01-01T00:00:00Z"


def _pricing_update(sku: str, multiplier: float) -> dict[str, Any]:
    """A schema-valid ``pricing_update`` with a strictly positive multiplier."""
    base_price = 100.0
    return {
        "pricing_id": f"pid-{sku}",
        "sku_id": sku,
        "store_id": _PROBE_STORE,
        "category": "staples",
        "base_price": base_price,
        "multiplier": multiplier,
        "final_price": base_price * multiplier,
        "is_essential": False,
        "elasticity_source": "correlation_fallback",
        "timestamp": _PROBE_TS,
        "confidence": 0.8,
    }


def _forecast(sku: str, point: float) -> dict[str, Any]:
    """A schema-valid ``demand_forecast`` with a positive 15min point demand."""
    return {
        "sku_id": sku,
        "store_id": _PROBE_STORE,
        "forecast_timestamp": _PROBE_TS,
        "horizons": {"15min": point},
        "lower_90": {"15min": point / 2.0},
        "upper_90": {"15min": point + 1.0},
        "confidence": 0.8,
        "drift_detected": False,
    }


def _route(idx: int, total_time_min: float) -> dict[str, Any]:
    """A schema-valid ``route_plan`` (every route is an actionable dispatch item)."""
    return {
        "route_id": f"rid-{idx}",
        "rider_id": f"R-{idx}",
        "store_id": _PROBE_STORE,
        "stops": [{"seq": 0}],
        "total_distance_km": 5.0,
        "total_time_min": total_time_min,
    }


def _freshness_alert(sku: str) -> dict[str, Any]:
    """A schema-valid ``freshness_alert`` flagged for spoilage mitigation."""
    return {
        "alert_id": f"aid-{sku}",
        "store_id": _PROBE_STORE,
        "sku_id": sku,
        "days_to_expiry": 2.0,
        "quality_score": 0.6,
        "markdown_applied": True,
        "markdown_pct": 20.0,
        "fssai_compliant": True,
        "timestamp": _PROBE_TS,
        "confidence": 0.7,
    }


def _disruption_payload() -> dict[str, Any]:
    """A schema-valid ``disruption_alert`` carrying one actionable alert level."""
    return {
        "alert_id": "aid-1",
        "alert_level": 8,
        "anomaly_scores": {
            "isolation_forest": 0.5,
            "lstm_autoencoder": 0.5,
            "gnn_structural": 0.5,
            "ensemble_weighted": 0.5,
        },
        "affected_nodes": ["node_0"],
        "disruption_type": "supplier_delay",
        "playbook_id": "PB-1",
        "playbook_actions": "reroute",
        "reasoning_chain": "ensemble anomaly above threshold",
        "timestamp": _PROBE_TS,
        "confidence": 0.7,
    }


def _reorder_action(sku: str) -> dict[str, Any]:
    """A schema-valid ``inventory_action`` of type ``reorder`` with positive quantity."""
    return {
        "store_id": _PROBE_STORE,
        "sku_id": sku,
        "action_type": "reorder",
        "quantity": 120.0,
        "safety_stock_multiplier": 1.5,
        "reorder_point": 40,
        "confidence": 0.8,
    }


def _consensus_action(agent: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap a ratified payload in the envelope every ``execute()`` expects."""
    return {
        "decision_id": f"agency-probe-{agent}",
        "city": _PROBE_CITY,
        "ratified_proposal": {"payload": payload},
    }


PROBE_ACTIONS: Mapping[str, dict[str, Any]] = {
    "inventory_sentinel": _consensus_action(
        "inventory_sentinel", {"actions": [_reorder_action("sku_0")]}
    ),
    "pricing_oracle": _consensus_action(
        "pricing_oracle", {"updates": [_pricing_update("sku_0", 1.5)]}
    ),
    "demand_prophet": _consensus_action(
        "demand_prophet",
        {"forecasts": [_forecast("sku_0", 12.0)], "store_id": _PROBE_STORE, "num_skus": 1},
    ),
    "routing_navigator": _consensus_action(
        "routing_navigator", {"routes": [_route(0, 18.0)]}
    ),
    "freshness_guardian": _consensus_action(
        "freshness_guardian",
        {"alerts": [_freshness_alert("sku_0")], "store_id": _PROBE_STORE},
    ),
    "disruption_shield": _consensus_action("disruption_shield", _disruption_payload()),
    "supplier_trust": _consensus_action(
        "supplier_trust", {"supplier_id": "SUP-1", "trust_score": 0.72}
    ),
    "sustainability_agent": _consensus_action("sustainability_agent", {}),
}

#: ``WorldState`` fields a world action can change. ``sim_time_min`` and ``as_of`` are
#: excluded: ``as_of`` is a wall-clock stamp that differs on every read, and a moved
#: ``sim_time_min`` means the clock ticked between the two reads, which makes any delta
#: unattributable to the call (handled explicitly as ``clock_intervened``).
DELTA_FIELDS = (
    "inventory",
    "pending_orders",
    "fill_rate",
    "spoilage_rate",
    "avg_delivery_min",
    "restocks_triggered",
    "demand_rate",
)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


class AgentProbeObservation(BaseModel):
    """The raw evidence gathered about one discovered agent handler.

    Everything in here is an *observation*: a fact read off the tree or off the world.
    Nothing in here is a judgement -- :func:`classify` turns one of these into exactly one
    :class:`AgentActuationReport`. Splitting the two is what lets the classification be
    property-tested for totality without a ``WorldRuntime`` (I-0).
    """

    model_config = ConfigDict(frozen=True)

    agent: str
    handler_file: str
    #: False when the handler file could not be parsed (R9.9: UNCLASSIFIED **and** a FAIL).
    parsed: bool = True
    #: Actuation markers found on statements *reachable* from ``execute()`` (R9.7).
    reachable_markers: tuple[str, ...] = ()
    #: The handler returns a constant ``kafka_published: True`` and never actuates.
    stub_shape: bool = False
    #: The handler returns a literal ``kafka_published: True`` (regardless of actuation).
    constant_kafka_published: bool = False
    #: A ``kafka_producer=`` is passed at the ``agents/<agent>/inference/serve.py``
    #: handler construction -- what the *deployed* server supplies (R9.6).
    producer_wired: bool = False
    #: The declared lever, or ``None`` when the agent is not declared in AGENT_LEVERS.
    lever: LeverSpec | None = None
    #: True only when a real ``execute()`` ran against a live world.
    probed: bool = False
    #: Non-empty when the probe could not reach a verdict (import, construction, or call).
    probe_error: str = ""
    #: The status the agent reported for itself. Evidence about the agent, never the world.
    reported_status: str = ""
    #: What the agent claims it published. ``None`` when it reported no such field.
    reported_kafka_published: bool | None = None
    #: The oracle: did the state read back through ``perceive()`` differ across the call?
    world_delta: bool = False
    #: True when the world clock advanced between the two reads, making a delta
    #: unattributable to ``execute()``.
    clock_intervened: bool = False


class AgentActuationReport(BaseModel):
    """One agent's classification and the evidence it rests on (design E2.2)."""

    model_config = ConfigDict(frozen=True)

    agent: str
    classification: ActuationClass
    world_delta: bool
    reported_status: str
    producer_wired: bool
    reachable_markers: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class ActuationVerdict:
    """The behavioural verdict over every discovered agent.

    ``actuating_count`` is the number this gate *reports*, and ``compared_count`` is the
    number it compares against :data:`ACTUATING_BASELINE`. R9.8 requires them to be the
    same value; ``count_integrity`` makes that requirement mechanical instead of assumed.
    """

    reports: tuple[AgentActuationReport, ...]
    actuating: tuple[str, ...]
    event_only: tuple[str, ...]
    inert: tuple[str, ...]
    unclassified: tuple[str, ...]
    actuating_count: int
    compared_count: int
    baseline: int | None
    checks: tuple[Check, ...]
    verdict: Literal["ok", "fail", "unavailable"]
    reason: str

    @property
    def ok(self) -> bool:
        """True only for ``ok``. ``unavailable`` is not a pass (I-7)."""
        return self.verdict == "ok"


# ---------------------------------------------------------------------------
# Reachability: the AST pass, demoted to a pre-filter over executable statements
# ---------------------------------------------------------------------------
def _static_truth(test: ast.expr) -> bool | None:
    """``True``/``False`` when a branch test is a compile-time constant, else ``None``."""
    if isinstance(test, ast.Constant):
        return bool(test.value)
    return None


def _dotted(node: ast.AST) -> str | None:
    """Render a ``Name``/``Attribute`` chain as a dotted string (``self._kafka.produce``)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def _collect_reachable(body: Sequence[ast.stmt], out: list[ast.AST]) -> None:
    """Collect the executable expression nodes of statements reachable from ``body``.

    Reachability is deliberately conservative in the one direction that matters: it may
    keep a statement that never runs at runtime, but it never *drops* one that does. What
    it excludes is what R9.7 names -- a docstring or bare string constant, the body of a
    constant-false branch (and the ``else`` of a constant-true one), a nested ``def``/
    ``class`` that calling ``execute()`` does not execute, and anything after an
    unconditional ``return``/``raise``/``break``/``continue`` in the same block. Comments
    are absent from the AST entirely, which is the point: a marker written in a comment
    cannot be found here at all.
    """
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, ast.If):
            out.append(stmt.test)
            truth = _static_truth(stmt.test)
            if truth is not False:
                _collect_reachable(stmt.body, out)
            if truth is not True:
                _collect_reachable(stmt.orelse, out)
        elif isinstance(stmt, ast.While):
            out.append(stmt.test)
            if _static_truth(stmt.test) is not False:
                _collect_reachable(stmt.body, out)
            _collect_reachable(stmt.orelse, out)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            out.append(stmt.iter)
            _collect_reachable(stmt.body, out)
            _collect_reachable(stmt.orelse, out)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            out.extend(item.context_expr for item in stmt.items)
            _collect_reachable(stmt.body, out)
        elif isinstance(stmt, ast.Try):
            _collect_reachable(stmt.body, out)
            for handler in stmt.handlers:
                _collect_reachable(handler.body, out)
            _collect_reachable(stmt.orelse, out)
            _collect_reachable(stmt.finalbody, out)
        elif isinstance(stmt, ast.Match):
            out.append(stmt.subject)
            for case in stmt.cases:
                _collect_reachable(case.body, out)
        else:
            # A docstring or bare string statement is not executable evidence.
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue
            out.append(stmt)
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                return


def reachable_markers(tree: ast.AST) -> tuple[str, ...]:
    """Actuation markers reachable from any ``execute()`` defined in ``tree`` (R9.7).

    A marker here is necessary-but-never-sufficient: it can only withhold the
    ``ACTUATING`` class (an agent whose ``execute()`` reaches no actuator cannot have
    changed the world, so the probe may be skipped), never grant it. The verdict is the
    observed delta.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "execute":
            continue
        nodes: list[ast.AST] = []
        _collect_reachable(node.body, nodes)
        for collected in nodes:
            for inner in ast.walk(collected):
                dotted = _dotted(inner)
                if dotted is None:
                    continue
                for marker in ACTUATION_MARKERS:
                    if dotted == marker or dotted.startswith(f"{marker}."):
                        found.add(marker)
    return tuple(marker for marker in ACTUATION_MARKERS if marker in found)


def _read(rel: str) -> str:
    path = ROOT / rel
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _structural_checks() -> list[Check]:
    sensor = _read("orchestrator/sensor/loop.py")
    serve = _read("orchestrator/inference/serve.py")
    world = _read("digital_twin/world/runtime.py")
    protocol = _read("orchestrator/consensus/protocol.py")
    return [
        Check(
            "autonomous_trigger",
            "class SensorLoop" in sensor and "run_consensus(" in sensor,
            "SensorLoop convenes run_consensus on its own initiative",
        ),
        Check(
            "sensor_wired",
            "SensorLoop(" in serve and "_sensor_loop" in serve,
            "orchestrator lifespan starts the SensorLoop",
        ),
        Check(
            "standing_world",
            all(s in world for s in ("class WorldRuntime", "def perceive", "def apply_action")),
            "WorldRuntime perceives + is actuated",
        ),
        Check(
            "learn_from_world",
            "world_observer" in protocol and "_build_learning_outcome" in protocol,
            "consensus learns from the realized world, not predicted utility",
        ),
    ]


def _execute_returns_stub(fn: ast.AST) -> bool:
    """True iff a function returns a dict literal with ``kafka_published`` = constant True
    and never actuates (no call to an actuator / producer). That is the old stub shape."""
    if not isinstance(fn, ast.FunctionDef):
        return False
    actuates = False
    stub_return = False
    for node in ast.walk(fn):
        # any apply()/produce() call means this execute does real work
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("apply", "produce")
        ):
            actuates = True
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key, val in zip(node.value.keys, node.value.values, strict=False):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "kafka_published"
                    and isinstance(val, ast.Constant)
                    and val.value is True
                ):
                    stub_return = True
    return stub_return and not actuates


def _returns_constant_kafka_true(fn: ast.AST) -> bool:
    """True iff ``fn`` returns a dict literal whose ``kafka_published`` is a literal True.

    Unlike :func:`_execute_returns_stub` this does not care whether the handler also
    actuates: a hardcoded publication claim is a false claim about Kafka regardless
    (R9.6), and it is a FAIL whenever the deployed server wires no producer.
    """
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key, val in zip(node.value.keys, node.value.values, strict=False):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "kafka_published"
                    and isinstance(val, ast.Constant)
                    and val.value is True
                ):
                    return True
    return False


def producer_wired(agent: str) -> bool:
    """True iff ``agents/<agent>/inference/serve.py`` passes a ``kafka_producer=``.

    This is what the **deployed** server supplies, read from the handler construction
    itself rather than from the presence of the word "kafka" in the file (R9.6). Five of
    the six mutating agents pass no producer -- the wiring gap the audit files under
    Quality -- so an agent that claims it published without one is making a claim its own
    deployment contradicts.
    """
    serve = AGENTS_DIR / agent / "inference" / "serve.py"
    try:
        src = serve.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        tree = ast.parse(src)
    except SyntaxError:
        logger.warning("serve_unparseable", agent=agent, file=str(serve))
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _dotted(node.func) or ""
        if not callee.split(".")[-1].endswith("A2AHandler"):
            continue
        if any(kw.arg == "kafka_producer" for kw in node.keywords):
            return True
    return False


def discover_handlers() -> tuple[Path, ...]:
    """Every ``agents/*/a2a/handler.py`` on disk, in a stable order."""
    return tuple(sorted(AGENTS_DIR.glob("*/a2a/handler.py")))


def _reported_path(path: Path) -> str:
    """A repo-relative posix path, falling back to the absolute one when outside the tree.

    R9.9 requires the check to *name the file*, so this never returns an empty string --
    including when ``AGENTS_DIR`` has been pointed at a synthetic tree for a test.
    """
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def static_observations() -> tuple[AgentProbeObservation, ...]:
    """Read every discovered handler statically. No world is driven and nothing is imported.

    This is the laptop-safe half of the gate (I-0) and the pre-filter half of AD-5. It
    records what can be known from the tree -- parseability, the reachable marker set, the
    old stub shape, a hardcoded publication claim, and the deployed producer wiring -- and
    leaves ``probed`` false, because nothing here observed the world.
    """
    observations: list[AgentProbeObservation] = []
    for handler in discover_handlers():
        agent = handler.relative_to(AGENTS_DIR).parts[0]
        lever = AGENT_LEVERS.get(agent)
        wired = producer_wired(agent)
        try:
            src = handler.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError) as exc:
            logger.warning("handler_unparseable", agent=agent, file=str(handler), error=str(exc))
            observations.append(
                AgentProbeObservation(
                    agent=agent,
                    handler_file=_reported_path(handler),
                    parsed=False,
                    producer_wired=wired,
                    lever=lever,
                    probe_error=f"handler could not be parsed: {exc}",
                )
            )
            continue
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute"
        ]
        observations.append(
            AgentProbeObservation(
                agent=agent,
                handler_file=_reported_path(handler),
                parsed=True,
                reachable_markers=reachable_markers(tree),
                stub_shape=any(_execute_returns_stub(fn) for fn in functions),
                constant_kafka_published=any(_returns_constant_kafka_true(fn) for fn in functions),
                producer_wired=wired,
                lever=lever,
            )
        )
    return tuple(observations)


def _agent_actuation() -> tuple[list[str], list[str]]:
    """Return ``(converted_agents, stub_agents)`` from the reachable-statement pre-filter.

    Kept as the gate's ratchet input and as the ``real_actuation`` structural signal. It is
    no longer a claim about behaviour: "converted" now means only "``execute()`` reaches an
    actuator or an event source on a statement that can execute", which is the sound
    over-approximation the probe narrows (R9.7).
    """
    converted: list[str] = []
    stubs: list[str] = []
    for observation in static_observations():
        if not observation.parsed:
            continue
        if observation.stub_shape:
            stubs.append(observation.agent)
        elif observation.reachable_markers:
            converted.append(observation.agent)
    return converted, stubs


# ---------------------------------------------------------------------------
# The pure seam: one observation -> one classification, and a total verdict.
# ---------------------------------------------------------------------------
def classify(observation: AgentProbeObservation) -> AgentActuationReport:
    """Assign exactly one :class:`ActuationClass` to one observation (R9.1, R9.2, R9.4).

    Pure and total: every observation gets a class, in this order.

    1. the handler did not parse                  -> ``UNCLASSIFIED`` (also a FAIL, R9.9)
    2. no lever is declared for the agent         -> ``UNCLASSIFIED`` (also a FAIL, R9.4)
    3. the probe did not run, or could not finish -> ``UNCLASSIFIED``
    4. the clock advanced across the two reads    -> ``UNCLASSIFIED`` (unattributable)
    5. ``perceive()`` differed across the call    -> ``ACTUATING`` (R9.1)
    6. the declared lever is not perceivable      -> ``UNCLASSIFIED`` (disclosed bound)
    7. a real publish with a wired producer       -> ``EVENT_ONLY``
    8. otherwise                                  -> ``INERT`` (R9.2)

    Rule 5 precedes rule 6 so an observed delta always wins over a declared expectation:
    the world, not the table, has the last word. Rule 6 exists because a lever the
    perception surface does not expose cannot be decided by an immediate delta -- reporting
    such an agent ``INERT`` would be an accusation the evidence does not support, and
    reporting it ``ACTUATING`` would be a credit the evidence does not support either. A
    marker never appears in this ordering as grounds for ``ACTUATING`` (R9.7).
    """
    markers = observation.reachable_markers
    lever = observation.lever
    detail: str
    classification: ActuationClass

    if not observation.parsed:
        classification = ActuationClass.UNCLASSIFIED
        detail = f"{observation.handler_file} could not be parsed; no classification possible"
    elif lever is None:
        classification = ActuationClass.UNCLASSIFIED
        detail = (
            f"{observation.agent} declares no lever in AGENT_LEVERS, so the probe has no "
            "ratified action to invoke execute() with"
        )
    elif not observation.probed or observation.probe_error:
        classification = ActuationClass.UNCLASSIFIED
        detail = observation.probe_error or (
            "not behaviourally probed; the observed-delta verdict requires probe_actuation() "
            "against a live WorldRuntime (ci.yml::uplift-verify)"
        )
    elif observation.clock_intervened:
        classification = ActuationClass.UNCLASSIFIED
        detail = (
            "the world clock advanced between the two perceive() reads, so any delta is not "
            "attributable to execute(); re-probe a manual-tick runtime"
        )
    elif observation.world_delta:
        classification = ActuationClass.ACTUATING
        detail = (
            f"perceive() differed across execute(); the {lever.lever_key} lever moved "
            f"{lever.observed_field or 'world state'}"
        )
    elif lever.kind is not None and not lever.perceivable:
        classification = ActuationClass.UNCLASSIFIED
        detail = (
            f"the {lever.lever_key} lever is not exposed by WorldState, so an immediate "
            f"perceive() delta cannot decide this agent: {lever.note}"
        )
    elif observation.reported_kafka_published is True and observation.producer_wired:
        classification = ActuationClass.EVENT_ONLY
        detail = (
            "no world delta, and a real publish through the producer the deployed server "
            "supplies"
        )
    else:
        classification = ActuationClass.INERT
        classification_reason = (
            "reports work but perceive() is unchanged"
            if observation.reported_status == "executed"
            else "changes nothing and publishes nothing"
        )
        detail = (
            f"{classification_reason} (reported status {observation.reported_status!r}, "
            f"kafka_published={observation.reported_kafka_published}, "
            f"producer_wired={observation.producer_wired}, markers={list(markers)})"
        )

    return AgentActuationReport(
        agent=observation.agent,
        classification=classification,
        world_delta=observation.world_delta,
        reported_status=observation.reported_status,
        producer_wired=observation.producer_wired,
        reachable_markers=markers,
        detail=detail,
    )


def evaluate_actuation(
    observations: Sequence[AgentProbeObservation],
    *,
    baseline: int | None = ACTUATING_BASELINE,
) -> ActuationVerdict:
    """Derive the behavioural verdict from a set of observations. Pure and total.

    Reads no file, imports no agent, drives no world, and touches no process state, so the
    verdict is a total function of its arguments -- which is what lets design Property 30
    assert totality and the count identity without a simulation (I-0). The same seam shape
    as ``registry_gate.evaluate_results`` and ``doc_truth.evaluate_claims``.
    """
    reports = tuple(classify(observation) for observation in observations)

    def named(cls: ActuationClass) -> tuple[str, ...]:
        return tuple(report.agent for report in reports if report.classification is cls)

    actuating = named(ActuationClass.ACTUATING)
    event_only = named(ActuationClass.EVENT_ONLY)
    inert = named(ActuationClass.INERT)
    unclassified = named(ActuationClass.UNCLASSIFIED)

    # R9.8: the reported count and the compared count are the same value, recomputed
    # independently from the reports so a divergence is detectable rather than assumed.
    actuating_count = len(actuating)
    compared_count = sum(
        1 for report in reports if report.classification is ActuationClass.ACTUATING
    )

    checks: list[Check] = []

    # R9.9: an unparseable handler is UNCLASSIFIED *and* a FAIL naming the file.
    unparseable = tuple(
        observation.handler_file for observation in observations if not observation.parsed
    )
    checks.append(
        Check(
            "handlers_parseable",
            not unparseable,
            f"{len(unparseable)} handler(s) failed to parse: {', '.join(unparseable) or 'none'}",
        )
    )

    # R9.4: a discovered agent with no declared lever cannot be probed, so it is named.
    undeclared = tuple(
        observation.agent
        for observation in observations
        if observation.parsed and observation.lever is None
    )
    checks.append(
        Check(
            "agents_declared",
            not undeclared,
            f"{len(undeclared)} discovered agent(s) undeclared in AGENT_LEVERS: "
            f"{', '.join(undeclared) or 'none'}",
        )
    )

    # R9.6: a publication claim with no producer behind it, observed or hardcoded.
    unbacked = tuple(
        observation.agent
        for observation in observations
        if not observation.producer_wired
        and (observation.reported_kafka_published is True or observation.constant_kafka_published)
    )
    checks.append(
        Check(
            "producer_wiring",
            not unbacked,
            f"{len(unbacked)} agent(s) claim kafka_published without a producer wired in "
            f"inference/serve.py: {', '.join(unbacked) or 'none'}",
        )
    )

    # R9.4: the classification is a partition -- every discovered agent lands in exactly
    # one list, so no agent can be omitted from every reported list.
    bucketed = len(actuating) + len(event_only) + len(inert) + len(unclassified)
    reported_agents = [report.agent for report in reports]
    total_ok = bucketed == len(reports) == len(observations) and len(set(reported_agents)) == len(
        reported_agents
    )
    checks.append(
        Check(
            "classification_total",
            total_ok,
            f"{bucketed} classification(s) over {len(observations)} discovered agent(s): "
            f"{len(actuating)} actuating, {len(event_only)} event-only, {len(inert)} inert, "
            f"{len(unclassified)} unclassified",
        )
    )

    # R9.8: if the reported count is not the enforced count, the check fails.
    checks.append(
        Check(
            "count_integrity",
            actuating_count == compared_count,
            f"reported actuating count {actuating_count} "
            f"{'==' if actuating_count == compared_count else '!='} compared count "
            f"{compared_count}",
        )
    )

    # R9.2: an agent that reports it executed while the world did not move is a stub.
    lying = tuple(
        report.agent
        for report in reports
        if report.classification is ActuationClass.INERT and report.reported_status == "executed"
    )
    checks.append(
        Check(
            "inert_reports_executed",
            not lying,
            f"{len(lying)} agent(s) report 'executed' with no observed world delta: "
            f"{', '.join(lying) or 'none'}",
        )
    )

    # R9.3: a drop below the recorded baseline fails, naming each agent that regressed.
    if baseline is None:
        checks.append(
            Check(
                "actuating_baseline",
                True,
                "no baseline recorded (unmeasured): the comparison is live but has no bound "
                "to enforce until a ci.yml::uplift-verify probe seeds ACTUATING_BASELINE",
            )
        )
    else:
        regressed = tuple(
            observation.agent
            for observation in observations
            if observation.agent not in actuating
            and observation.lever is not None
            and observation.lever.kind is not None
        )
        checks.append(
            Check(
                "actuating_baseline",
                compared_count >= baseline,
                f"{compared_count} agent(s) observed actuating against a baseline of "
                f"{baseline}"
                + (
                    f"; regressed: {', '.join(regressed) or 'none'}"
                    if compared_count < baseline
                    else ""
                ),
            )
        )

    failed = tuple(check for check in checks if not check.ok)
    verdict: Literal["ok", "fail", "unavailable"]
    if failed:
        verdict = "fail"
        reason = "; ".join(f"{check.name}: {check.detail}" for check in failed)
    elif not observations:
        verdict = "unavailable"
        reason = "no agent handlers were discovered, so nothing was classified"
    elif unclassified:
        verdict = "unavailable"
        reason = (
            f"{len(unclassified)} agent(s) unclassified ({', '.join(unclassified)}); "
            "absence of proof is not a pass (I-7)"
        )
    elif baseline is None:
        verdict = "unavailable"
        reason = (
            f"{compared_count} agent(s) observed actuating, but no baseline is recorded to "
            "compare against"
        )
    else:
        verdict = "ok"
        reason = (
            f"{compared_count} actuating (baseline {baseline}), {len(event_only)} event-only, "
            f"{len(inert)} inert, all classified from an observed perceive() delta"
        )

    return ActuationVerdict(
        reports=reports,
        actuating=actuating,
        event_only=event_only,
        inert=inert,
        unclassified=unclassified,
        actuating_count=actuating_count,
        compared_count=compared_count,
        baseline=baseline,
        checks=tuple(checks),
        verdict=verdict,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# The impure seam: drive a real world. CI ONLY (ci.yml::uplift-verify) -- never local.
# ---------------------------------------------------------------------------
class _InProcessActuator:
    """The production ``WorldActuator`` contract, minus the HTTP hop.

    ``WorldActuator`` POSTs ``apply_action`` over A2A. This forwards straight to the live
    ``WorldRuntime`` and returns the identical ``{"applied": bool, "result": ...}``
    envelope, so the handler runs its real lever-building, real actuation and real honest
    status logic against a real world -- exactly the shim
    ``orchestrator/tests/test_real_actuation_e2e.py`` uses. Only the network is removed;
    nothing about the actuation is faked.
    """

    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime

    def apply(self, action: Any) -> dict[str, Any]:
        return {"applied": True, "result": self._runtime.apply_action(action)}


class _RecordingProducer:
    """A Kafka producer that records what was produced, wired only where the server wires one.

    The probe mirrors the *deployed* construction: a producer is injected if and only if
    ``agents/<agent>/inference/serve.py`` passes one. An agent whose server supplies no
    producer is probed without one, so its ``kafka_published`` reports what it would report
    in production rather than what it could report in a friendlier harness.
    """

    def __init__(self) -> None:
        self.produced: list[tuple[str, Any, str | None]] = []

    def produce(
        self, topic: str, value: Any = None, key: str | None = None, headers: Any = None
    ) -> None:
        self.produced.append((topic, value, key))


#: A truthy stand-in for the agent's inference pipeline. No ``execute()`` in this repo
#: touches its pipeline (the actuation path reads only the ratified proposal), so this keeps
#: the probe free of every heavy serving model -- which is what makes it runnable in a CI
#: job at all.
_DUMMY_PIPELINE: Any = object()

_HANDLER_SUFFIX = "A2AHandler"


def _delta_projection(state: Any) -> dict[str, Any]:
    """The actuation-observable fields of a ``WorldState``, copied (see :data:`DELTA_FIELDS`).

    ``WorldRuntime.perceive()`` hands its ``inventory`` straight from the live simulation, so
    the container is copied here and the projection is taken *before* ``execute()`` runs. A
    projection that aliased the simulation's own dict would compare a mutated mapping against
    itself and report every reorder as no delta -- a silent false negative in the one place
    this gate must not have one.
    """
    projection: dict[str, Any] = {}
    for field_name in DELTA_FIELDS:
        value = getattr(state, field_name, None)
        projection[field_name] = dict(value) if isinstance(value, dict) else value
    return projection


def _load_handler_class(agent: str) -> type[Any]:
    """Import ``agents.<agent>.a2a.handler`` and return its own ``*A2AHandler`` class."""
    module_name = f"agents.{agent}.a2a.handler"
    module = importlib.import_module(module_name)
    for name, obj in vars(module).items():
        if (
            name.endswith(_HANDLER_SUFFIX)
            and inspect.isclass(obj)
            and getattr(obj, "__module__", "") == module_name
        ):
            return obj
    raise LookupError(f"no *{_HANDLER_SUFFIX} class defined in {module_name}")


def _construct_handler(agent: str, runtime: Any, *, wire_producer: bool) -> Any:
    """Build the agent's handler with the deployed wiring plus an in-process actuator."""
    handler_cls = _load_handler_class(agent)
    parameters = inspect.signature(handler_cls.__init__).parameters
    kwargs: dict[str, Any] = {}
    if "pipeline" in parameters:
        kwargs["pipeline"] = _DUMMY_PIPELINE
    if "actuator" in parameters:
        kwargs["actuator"] = _InProcessActuator(runtime)
    if "kafka_producer" in parameters and wire_producer:
        kwargs["kafka_producer"] = _RecordingProducer()
    return handler_cls(**kwargs)


def observe_agent(
    static: AgentProbeObservation,
    runtime: Any,
) -> AgentProbeObservation:
    """Probe one agent behaviourally and return the observation enriched with the delta.

    ``perceive()`` -> ``execute()`` -> ``perceive()``. The agent's returned dict is recorded
    as a *report about the agent*; the verdict comes from the two snapshots. A handler that
    cannot be imported, constructed, or called leaves ``probe_error`` set, which
    :func:`classify` turns into ``UNCLASSIFIED`` rather than an omission (R9.4).
    """
    if not static.parsed or static.lever is None:
        return static
    action = PROBE_ACTIONS.get(static.agent)
    if action is None:
        return static.model_copy(
            update={"probe_error": f"no ratified probe action declared for {static.agent}"}
        )

    # Every declared agent is probed, including one whose execute() reaches no actuator at
    # all. Short-circuiting on an empty marker set would put a static inference back on the
    # verdict path, which is the exact substitution this gate exists to remove: the markers
    # pre-filter the ratchet (see _agent_actuation), never the classification.
    try:
        handler = _construct_handler(
            static.agent, runtime, wire_producer=static.producer_wired
        )
    except Exception as exc:  # noqa: BLE001 -- an unprobeable agent is UNCLASSIFIED, not absent
        logger.warning("probe_construct_failed", agent=static.agent, error=str(exc))
        return static.model_copy(
            update={"probe_error": f"handler could not be constructed: {exc}"}
        )

    try:
        before_state = runtime.perceive()
        before = _delta_projection(before_state)
        before_time = float(before_state.sim_time_min)
        result = handler.execute(dict(action))
        after_state = runtime.perceive()
        after = _delta_projection(after_state)
        after_time = float(after_state.sim_time_min)
    except Exception as exc:  # noqa: BLE001 -- honest degradation (I-7)
        logger.warning("probe_execute_failed", agent=static.agent, error=str(exc))
        return static.model_copy(update={"probe_error": f"execute() raised: {exc}"})

    reported = result if isinstance(result, dict) else {}
    published = reported.get("kafka_published")
    return static.model_copy(
        update={
            "probed": True,
            "reported_status": str(reported.get("status", "")),
            "reported_kafka_published": published if isinstance(published, bool) else None,
            "world_delta": before != after,
            "clock_intervened": after_time != before_time,
        }
    )


def probe_actuation(runtime: Any) -> tuple[AgentActuationReport, ...]:
    """Classify every discovered agent from an observed ``perceive()`` delta (design E2.2).

    ``runtime`` is a live ``WorldRuntime``. It must be in manual-tick mode
    (``start(run_clock=False)``) and must not be ticked during the sweep: a clock advancing
    between the two reads makes the delta unattributable, which is detected and reported
    rather than silently credited.

    Heavy by construction -- it drives a real SimPy world -- so it belongs to
    ``ci.yml::uplift-verify`` behind ``@pytest.mark.slow`` and never runs on the dev box
    (I-0). The verdict logic it feeds is pure; see :func:`evaluate_actuation`.
    """
    return evaluate_actuation(
        [observe_agent(static, runtime) for static in static_observations()]
    ).reports


def probe_observations(runtime: Any) -> tuple[AgentProbeObservation, ...]:
    """The observations :func:`probe_actuation` classifies, for callers that want the seam."""
    return tuple(observe_agent(static, runtime) for static in static_observations())


# ---------------------------------------------------------------------------
# Binding arbitration (R9.1) -- unchanged structural signal
# ---------------------------------------------------------------------------
def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the first (async or sync) function definition named ``name``."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _call_name(call: ast.Call) -> str | None:
    """The simple callee name of a call (``foo`` for ``foo()`` / ``x.foo()``)."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _references_symbol(tree: ast.AST, name: str) -> bool:
    """True iff ``name`` is referenced anywhere as an identifier or import alias."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.alias) and node.name == name:
            return True
    return False


def _references_name(node: ast.AST, name: str) -> bool:
    """True iff ``name`` is referenced as an identifier within ``node``."""
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node))


def _calls_with_keyword(node: ast.AST, callee: str, keyword: str) -> bool:
    """True iff ``node`` contains a call to ``callee`` passing keyword ``keyword``."""
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Call)
            and _call_name(n) == callee
            and any(kw.arg == keyword for kw in n.keywords)
        ):
            return True
    return False


def _has_max_with_key(node: ast.AST) -> bool:
    """True iff ``node`` contains a ``max(..., key=...)`` argmax expression."""
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "max"
            and any(kw.arg == "key" for kw in n.keywords)
        ):
            return True
    return False


def _binding_arbitration_check() -> Check:
    """R9.1: distinguish binding Pareto-knee arbitration from raw ``argmax``.

    AST-parse ``orchestrator/consensus/protocol.py`` and assert all of:
      (a) ``select_binding_action`` is referenced (imported/called) in protocol.py;
      (b) the ``_full_path`` function reaches binding selection -- it calls
          ``select_binding_action`` and/or invokes ``_build_decision`` with a
          ``selection=`` keyword;
      (c) the ``_build_decision`` function contains NO ``max(..., key=...)`` call --
          the raw ``utility_score`` argmax no longer drives full-path selection (it may
          remain only on the Tier-1/2 fast path).
    The check is a deterministic, structural signal that is ``ok`` iff (a) and (b) and (c).
    """
    src = _read("orchestrator/consensus/protocol.py")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return Check("binding_arbitration", False, "protocol.py failed to parse")

    referenced = _references_symbol(tree, "select_binding_action")

    full_path = _find_function(tree, "_full_path")
    reaches = full_path is not None and (
        _references_name(full_path, "select_binding_action")
        or _calls_with_keyword(full_path, "_build_decision", "selection")
    )

    build_decision = _find_function(tree, "_build_decision")
    no_argmax = build_decision is not None and not _has_max_with_key(build_decision)

    ok = referenced and reaches and no_argmax
    if ok:
        detail = (
            "full path selects via select_binding_action (knee-weighted); "
            "_build_decision has no raw argmax"
        )
    else:
        detail = (
            f"binding wiring incomplete: referenced={referenced}, "
            f"full_path_reaches_binding={reaches}, build_decision_no_argmax={no_argmax}"
        )
    return Check("binding_arbitration", ok, detail)


# ---------------------------------------------------------------------------
# The gate verdict
# ---------------------------------------------------------------------------
@dataclass
class Probe:
    ok: bool
    checks: list[Check]
    converted: list[str]
    stubs: list[str]
    max_stubs: int
    converted_count: int
    binding: Check
    #: The behavioural verdict. ``None`` only when a caller constructs a ``Probe`` directly.
    actuation: ActuationVerdict | None = None

    @property
    def status(self) -> Literal["ok", "fail", "unavailable"]:
        """Tri-state verdict: a failure, a pass, or an absence of proof (I-7).

        ``ok``/``fail`` come from the static invariants and the ratchet -- the claims this
        gate can make from the tree alone. ``unavailable`` is reported when the behavioural
        classification was not observed (no probe ran, or an agent stayed
        ``UNCLASSIFIED``), so a caller that wants to gate on *behaviour* has a status
        distinct from a pass to gate on. The behavioural enforcement itself lives in design
        Property 30 (``@pytest.mark.slow``, ``ci.yml::uplift-verify``), which drives
        :func:`probe_actuation` against a real world; C57 keeps reporting the static
        verdict, so no claim here rests on a probe that did not run.
        """
        if not self.ok:
            return "fail"
        if self.actuation is not None and self.actuation.verdict == "unavailable":
            return "unavailable"
        return "ok"

    @property
    def detail(self) -> str:
        structural = [c for c in self.checks if c.name in STRUCTURAL_INVARIANTS]
        behaviour = (
            f"behaviour={self.actuation.verdict} ({self.actuation.reason})"
            if self.actuation is not None
            else "behaviour=not-probed"
        )
        # The stub agents are NAMED, not just counted: a gate that reports "1 stub" tells an
        # operator nothing, and R9.2/R9.3/R9.9 all require the offender to be named. This
        # string is what C57 surfaces, so it is also what a declared falsification is
        # checked against (gate-mutations.yaml C57 expects "inventory_sentinel" here).
        return (
            f"{sum(c.ok for c in structural)}/{len(structural)} loop invariants; "
            f"binding_arbitration={'ok' if self.binding.ok else 'FAIL'}; "
            f"{self.converted_count} agent(s) reach an actuator, {len(self.stubs)} stub(s) "
            f"[{', '.join(self.stubs) or 'none'}] (ratchet ceiling {self.max_stubs}); "
            f"{behaviour}"
        )


def evaluate(
    max_stubs: int = DEFAULT_MAX_STUBS,
    *,
    observations: Sequence[AgentProbeObservation] | None = None,
    baseline: int | None = ACTUATING_BASELINE,
) -> Probe:
    """Structured verdict for verify_claims (mirrors ``doc_truth.evaluate``).

    ``observations`` is the injection seam: pass the output of :func:`probe_observations`
    to get the behavioural verdict, or leave it ``None`` for the static-only sweep that is
    safe to run anywhere. Leaving it ``None`` never fabricates a behavioural result -- the
    unobserved agents are ``UNCLASSIFIED`` and the verdict is ``unavailable``.
    """
    checks = _structural_checks()
    converted, stubs = _agent_actuation()
    checks.append(
        Check(
            "real_actuation",
            len(converted) >= 1,
            f"{len(converted)} agent(s) reach an actuator or event source on a reachable "
            f"statement: {', '.join(converted) or 'none'}",
        )
    )
    # R9.1: binding-arbitration signal, exposed as a Check so it contributes to ok and
    # the --json checks[]. Independent of the actuation count below (R9.2).
    binding = _binding_arbitration_check()
    checks.append(binding)

    actuation = evaluate_actuation(
        static_observations() if observations is None else observations, baseline=baseline
    )
    checks.extend(actuation.checks)

    # R9.2: integer count of agents whose execute() reaches an actuator, computed from the
    # per-agent pre-filter classification, independently of the binding-arbitration check.
    converted_count = len(converted)
    ok = all(c.ok for c in checks) and len(stubs) <= max_stubs
    return Probe(
        ok=ok,
        checks=checks,
        converted=converted,
        stubs=stubs,
        max_stubs=max_stubs,
        converted_count=converted_count,
        binding=binding,
        actuation=actuation,
    )


def _build_probe_runtime(city: str = _PROBE_CITY, *, seed: int = 7, warmup: int = 5) -> Any:
    """Boot a manual-tick ``WorldRuntime`` and warm it so inventory and demand are non-zero.

    Manual tick (``run_clock=False``) is required: the probe must be the only thing that
    changes the world between its two ``perceive()`` reads.
    """
    from digital_twin.world import WorldRuntime  # noqa: PLC0415 -- CI-only heavy import

    runtime = WorldRuntime(city=city, seed=seed).start(run_clock=False)
    for _ in range(warmup):
        runtime.tick()
    return runtime


def run(
    *,
    as_json: bool = False,
    check: bool = False,
    max_stubs: int = DEFAULT_MAX_STUBS,
    probe: bool = False,
) -> int:
    observations: tuple[AgentProbeObservation, ...] | None = None
    runtime: Any = None
    if probe:
        runtime = _build_probe_runtime()
        try:
            observations = probe_observations(runtime)
        finally:
            runtime.stop()

    result = evaluate(max_stubs, observations=observations)
    checks, converted, stubs, ok = result.checks, result.converted, result.stubs, result.ok
    actuation = result.actuation

    if as_json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "status": result.status,
                    "checks": [c.__dict__ for c in checks],
                    "binding_arbitration": result.binding.__dict__,
                    "converted_agents": converted,
                    "converted_count": result.converted_count,
                    "stub_agents": stubs,
                    "max_stubs": max_stubs,
                    "behaviour": (
                        None
                        if actuation is None
                        else {
                            "verdict": actuation.verdict,
                            "reason": actuation.reason,
                            "probed": probe,
                            "baseline": actuation.baseline,
                            "actuating": list(actuation.actuating),
                            "actuating_count": actuation.actuating_count,
                            "compared_count": actuation.compared_count,
                            "event_only": list(actuation.event_only),
                            "inert": list(actuation.inert),
                            "unclassified": list(actuation.unclassified),
                            "reports": [
                                r.model_dump(mode="json") for r in actuation.reports
                            ],
                        }
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for c in checks:
            print(f"[{'OK' if c.ok else 'XX'}] {c.name:<24} {c.detail}")
        structural = [c for c in checks if c.name in STRUCTURAL_INVARIANTS]
        print(
            f"\nAgentic loop: {sum(c.ok for c in structural)}/{len(structural)} structural "
            f"invariants; binding_arbitration={'ok' if result.binding.ok else 'FAIL'}; "
            f"{result.converted_count} agent(s) reach an actuator, {len(stubs)} stub(s) "
            f"remaining (ratchet ceiling {max_stubs}: {', '.join(stubs) or 'none'})."
        )
        if actuation is not None:
            print(
                f"Behaviour ({'observed delta' if probe else 'NOT PROBED'}): "
                f"{actuation.verdict.upper()} - {actuation.reason}"
            )
            for report in actuation.reports:
                print(
                    f"  [{report.classification.value:<12}] {report.agent:<22} "
                    f"{report.detail}"
                )
            if not probe:
                print(
                    "  (run with --probe in ci.yml::uplift-verify for the observed-delta "
                    "verdict; it drives a real WorldRuntime and must not run locally.)"
                )
        if not ok:
            print("AGENCY REGRESSION: a loop invariant is missing or stubs exceeded the ceiling.")

    if check:
        return 0 if ok else 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agency_truth",
        description="Verify the agentic loop, classifying agents by observed world delta.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="emit the verdict as JSON"
    )
    parser.add_argument("--check", action="store_true", help="exit 1 on a regression")
    parser.add_argument(
        "--max-stubs",
        type=int,
        default=DEFAULT_MAX_STUBS,
        help="ratchet ceiling on status-dict-only execute() stubs",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help=(
            "drive a real WorldRuntime and classify by observed perceive() delta. "
            "CI ONLY (ci.yml::uplift-verify) -- heavy, never run on the dev box (I-0)."
        ),
    )
    args = parser.parse_args(argv)
    return run(
        as_json=bool(args.as_json),
        check=bool(args.check),
        max_stubs=int(args.max_stubs),
        probe=bool(args.probe),
    )


if __name__ == "__main__":
    sys.exit(main())
