"""Shared Hypothesis strategies for audit-chain verification and canonical rows.

Feature: purpose-achievement-audit, task 1.2. Imported by the E4 property tests
(design Property 18 chain perturbation detection, Property 19 anchoring, Property 21
canonical-row round-trip and append-only history).

What this module generates:

* **``ChainRow`` sequences** - ``chains`` builds a correctly linked chain over the
  real, untouched ``synapse_common.audit_chain`` primitives, optionally prefixed with
  the legacy pre-migration rows whose hashes are NULL by design.
* **canonical decisions** - ``canonical_decisions`` draws the seven-field argument set
  ``make_canonical_row`` accepts and ``canonical_rows`` returns its output verbatim.
  ``make_canonical_row`` is never reimplemented here: it is byte-pinned (I-4, E-S9-02),
  so a strategy that mirrored it would silently become a second source of truth.
* **perturbation operators** - ``Perturbation`` plus ``apply_perturbation`` implement
  exactly the six operators design Property 18 quantifies over, and
  ``perturbed_chains`` pairs a perturbed chain with the outcome a correct walk owes.

**Import independence.** ``orchestrator/audit/chain_walk.py`` (the ``ChainRow`` /
``BreakKind`` / ``WalkReport`` models) does not exist until task 7.1, so this module
imports nothing from it - not even under ``TYPE_CHECKING``. It defines a plain frozen
:class:`ChainRowDraft` carrying the design's declared field set and exposes
:meth:`ChainRowDraft.as_kwargs` so task 7.1's model can be constructed from a draft
without either side importing the other. Break kinds are plain strings equal to the
declared ``BreakKind`` values.

**I-0.** Every generator is pure in-memory construction: no Postgres, no subprocess,
no container. ``max_examples`` is never set here or in the importing tests - the budget
comes from the root ``conftest.py`` profiles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID

import yaml
from hypothesis import strategies as st

from synapse_common.audit_chain import hash_payload_for_row, make_canonical_row

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "BREAK_KIND_HEAD_UNREACHABLE",
    "BREAK_KIND_LINKAGE",
    "BREAK_KIND_NULL_AFTER_BOUNDARY",
    "BREAK_KIND_PAYLOAD",
    "CanonicalDecision",
    "ChainBounds",
    "ChainRowDraft",
    "Perturbation",
    "PerturbedChain",
    "apply_perturbation",
    "canonical_decisions",
    "canonical_rows",
    "chain_bounds",
    "chains",
    "expected_break_kinds",
    "head_hash",
    "nullify_hashes",
    "perturbations",
    "perturbed_chains",
]

# The four declared ``BreakKind`` values (design E4.1), as plain strings so this
# module stays independent of the module that will define the enum (task 7.1).
BREAK_KIND_PAYLOAD: Final = "payload"
BREAK_KIND_LINKAGE: Final = "linkage"
BREAK_KIND_NULL_AFTER_BOUNDARY: Final = "null_after_boundary"
BREAK_KIND_HEAD_UNREACHABLE: Final = "head_unreachable"


# ---------------------------------------------------------------------------
# Committed bounds (never hardcoded here - AD-13)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainBounds:
    """The committed walk bounds and migration boundary (AD-13).

    Read from ``infrastructure/quality/audit-chain-bounds.yaml`` rather than
    duplicated as literals, so a boundary correction is a reviewed data edit in one
    place and the strategies follow it automatically.
    """

    migration_boundary: datetime
    max_rows: int
    max_wall_clock_seconds: int
    anchor_max_age_hours: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def chain_bounds() -> ChainBounds:
    """Load the committed chain bounds (``encoding='utf-8'`` per E-S13-07)."""
    path = _repo_root() / "infrastructure" / "quality" / "audit-chain-bounds.yaml"
    payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    boundary_raw = str(payload["migration_boundary"]["value"])
    walk = payload["walk_bounds"]
    return ChainBounds(
        migration_boundary=datetime.fromisoformat(boundary_raw.replace("Z", "+00:00")),
        max_rows=int(walk["max_rows"]),
        max_wall_clock_seconds=int(walk["max_wall_clock_seconds"]),
        anchor_max_age_hours=int(payload["anchor_freshness"]["max_age_hours"]),
    )


# ---------------------------------------------------------------------------
# Canonical decisions (Property 21)
# ---------------------------------------------------------------------------

_TIERS: Final[tuple[str, ...]] = ("tier_1", "tier_2", "tier_3", "tier_4")
_ACTION_KINDS: Final[tuple[str, ...]] = ("restock", "reprice", "reroute", "noop")
_SKUS: Final[tuple[str, ...]] = ("SKU001", "SKU002", "SKU042", "SKU666")
_OBJECTIVES: Final[tuple[str, ...]] = ("cost", "time", "waste", "co2", "latency")
_AGENTS: Final[tuple[str, ...]] = (
    "demand_prophet",
    "inventory_sentinel",
    "pricing_oracle",
    "routing_navigator",
    "disruption_shield",
)


@dataclass(frozen=True)
class CanonicalDecision:
    """The seven-field argument set ``make_canonical_row`` accepts, unmodified.

    Held as a dataclass so a test can perturb one field and re-derive the canonical
    row through the real function, which is the only permitted way to produce one.
    """

    decision_id: UUID
    tier: str
    selected_action: Mapping[str, Any]
    pareto_weights: Mapping[str, float]
    confidence: float
    proposals: Sequence[Mapping[str, Any]]
    audit_trace: Sequence[str]

    def canonical(self) -> dict[str, Any]:
        """The canonical row, built by the byte-pinned ``make_canonical_row`` (I-4)."""
        return make_canonical_row(
            decision_id=self.decision_id,
            tier=self.tier,
            selected_action=dict(self.selected_action),
            pareto_weights=dict(self.pareto_weights),
            confidence=self.confidence,
            proposals=[dict(proposal) for proposal in self.proposals],
            audit_trace=list(self.audit_trace),
        )

    def canonical_json(self) -> str:
        """Canonical serialisation (I-13: ``sort_keys=True``, compact separators)."""
        return json.dumps(
            self.canonical(), sort_keys=True, separators=(",", ":"), default=str
        )


def _uuids() -> st.SearchStrategy[UUID]:
    return st.uuids(version=4)


def _selected_actions() -> st.SearchStrategy[dict[str, Any]]:
    return st.fixed_dictionaries(
        {
            "action": st.sampled_from(_ACTION_KINDS),
            "sku_id": st.sampled_from(_SKUS),
            "quantity": st.integers(min_value=0, max_value=500),
        }
    )


def _pareto_weights() -> st.SearchStrategy[dict[str, float]]:
    """Weights over a non-empty objective subset, each rounded to six decimals.

    Six decimals mirrors the rounding ``make_canonical_row`` applies to
    ``confidence``: it keeps generated rows byte-stable across a JSON round-trip,
    which is what Property 21 asserts.
    """
    return st.lists(st.sampled_from(_OBJECTIVES), min_size=1, max_size=4, unique=True).flatmap(
        lambda names: st.fixed_dictionaries(
            {
                name: st.floats(min_value=0.0, max_value=1.0, allow_nan=False).map(
                    lambda value: round(value, 6)
                )
                for name in names
            }
        )
    )


def _proposals() -> st.SearchStrategy[list[dict[str, Any]]]:
    return st.lists(
        st.fixed_dictionaries(
            {
                "agent_name": st.sampled_from(_AGENTS),
                "confidence": st.floats(min_value=0.0, max_value=1.0, allow_nan=False).map(
                    lambda value: round(value, 6)
                ),
            }
        ),
        max_size=4,
    )


def canonical_decisions() -> st.SearchStrategy[CanonicalDecision]:
    """One decision's worth of canonical-row inputs."""
    return st.builds(
        CanonicalDecision,
        decision_id=_uuids(),
        tier=st.sampled_from(_TIERS),
        selected_action=_selected_actions(),
        pareto_weights=_pareto_weights(),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        proposals=_proposals(),
        audit_trace=st.lists(
            st.sampled_from(("tier=tier_2", "phase=4", "guardrail=ok", "twin=agree")),
            max_size=5,
        ),
    )


def canonical_rows() -> st.SearchStrategy[dict[str, Any]]:
    """The output of ``make_canonical_row`` for a generated decision."""
    return canonical_decisions().map(lambda decision: decision.canonical())


# ---------------------------------------------------------------------------
# Chain rows (Property 18, 19)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainRowDraft:
    """One ``audit_consensus`` row, carrying E4.1's declared ``ChainRow`` field set.

    Deliberately a plain dataclass, not the Pydantic model: task 7.1 owns that model
    and this module must not depend on it. :meth:`as_kwargs` is the bridge - a test
    can write ``ChainRow(**draft.as_kwargs())`` once the model exists, and nothing
    here changes.
    """

    row_id: int
    created_at: datetime
    prev_hash: str | None
    current_hash: str | None
    canonical: Mapping[str, Any]

    @property
    def is_legacy(self) -> bool:
        """A pre-migration row: chain columns NULL because the ALTER left them so."""
        return self.prev_hash is None and self.current_hash is None

    def as_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for task 7.1's ``ChainRow`` model."""
        return {
            "row_id": self.row_id,
            "created_at": self.created_at,
            "prev_hash": self.prev_hash,
            "current_hash": self.current_hash,
            "canonical": dict(self.canonical),
        }


def head_hash(rows: Sequence[ChainRowDraft]) -> str | None:
    """The newest non-null ``current_hash``, i.e. the head an anchor commits to."""
    for row in reversed(rows):
        if row.current_hash is not None:
            return row.current_hash
    return None


def _link(
    canonicals: Sequence[Mapping[str, Any]],
    *,
    boundary: datetime,
    legacy_count: int,
) -> tuple[ChainRowDraft, ...]:
    """Build a correctly linked chain: ``legacy_count`` NULL rows, then hashed rows.

    Legacy rows sit strictly before ``boundary`` with NULL hashes (R6.7); hashed rows
    sit after it and chain from genesis (``prev_hash=None`` on the first), because the
    legacy rows carry no hash to chain from.
    """
    rows: list[ChainRowDraft] = []
    prev: str | None = None
    for index, canonical in enumerate(canonicals):
        legacy = index < legacy_count
        # Legacy rows sit before the boundary in ascending order, hashed rows after
        # it, so ``created_at`` and ``row_id`` agree on the ordering the walker reads.
        created_at = (
            boundary - timedelta(minutes=legacy_count - index)
            if legacy
            else boundary + timedelta(minutes=index + 1)
        )
        if legacy:
            rows.append(
                ChainRowDraft(
                    row_id=index + 1,
                    created_at=created_at,
                    prev_hash=None,
                    current_hash=None,
                    canonical=canonical,
                )
            )
            continue
        current = hash_payload_for_row(prev, dict(canonical))
        rows.append(
            ChainRowDraft(
                row_id=index + 1,
                created_at=created_at,
                prev_hash=prev,
                current_hash=current,
                canonical=canonical,
            )
        )
        prev = current
    # Legacy rows are the oldest, so re-order by created_at to match the ordered
    # snapshot the walker reads (`ORDER BY created_at, id`).
    return tuple(sorted(rows, key=lambda row: (row.created_at, row.row_id)))


@st.composite
def chains(
    draw: st.DrawFn,
    *,
    min_length: int = 2,
    max_length: int = 8,
    max_legacy: int = 2,
) -> tuple[ChainRowDraft, ...]:
    """A correctly linked chain of ``[min_length, max_length]`` rows.

    ``min_length`` defaults to 2 because Property 18 is stated over chains of length
    n >= 2: a single-row chain has no linkage to break. Up to ``max_legacy`` leading
    rows carry NULL hashes so the legacy accounting (R6.7) is exercised on a share of
    examples rather than needing its own generator.
    """
    length = draw(st.integers(min_value=min_length, max_value=max_length))
    legacy_count = draw(st.integers(min_value=0, max_value=min(max_legacy, length - min_length)))
    canonicals = [draw(canonical_rows()) for _ in range(length)]
    return _link(canonicals, boundary=chain_bounds().migration_boundary, legacy_count=legacy_count)


def nullify_hashes(
    rows: Sequence[ChainRowDraft], index: int
) -> tuple[ChainRowDraft, ...]:
    """NULL the chain columns of a post-boundary row (the R6.8 clause).

    Separate from :class:`Perturbation` because it is not one of Property 18's six
    operators: it is the boundary clause of the same property, and a walk owes
    ``null_after_boundary`` for it.
    """
    mutated = list(rows)
    mutated[index] = replace(mutated[index], prev_hash=None, current_hash=None)
    return tuple(mutated)


# ---------------------------------------------------------------------------
# Perturbation operators (Property 18)
# ---------------------------------------------------------------------------


class Perturbation(StrEnum):
    """Exactly the six operators design Property 18 quantifies over.

    ``NONE`` is the null operator: it must leave the walk verified with
    ``verified == n``, which is what stops the property from being satisfied by a
    verifier that rejects everything.
    """

    NONE = "none"
    ALTER_PAYLOAD = "alter_payload"
    DELETE_ROW = "delete_row"
    DELETE_AND_RELINK = "delete_and_relink"
    SWAP_ADJACENT = "swap_adjacent"
    TRUNCATE_TAIL = "truncate_tail"


def perturbations() -> st.SearchStrategy[Perturbation]:
    """One perturbation operator, uniformly."""
    return st.sampled_from(tuple(Perturbation))


#: The break kind a correct walk reports per operator - exactly one kind each.
#:
#: ``DELETE_AND_RELINK`` reports ``payload`` and nothing else. The convention was
#: left open here and is now **settled** by task 7.1
#: (``orchestrator/audit/chain_walk.py``, module docstring conventions 2 and 3): a
#: walk reports at most one break per row under the declared per-row precedence
#: ``NULL_AFTER_BOUNDARY`` > ``LINKAGE`` > ``PAYLOAD``. The reason ``payload`` is the
#: surviving kind is worth stating: the operator rewrites the successor's
#: ``prev_hash`` to the surviving predecessor's ``current_hash`` but does NOT
#: recompute the successor's ``current_hash`` (recomputing it forward would re-hash
#: the whole tail - a different attack). The attacker has therefore *made linkage
#: consistent*, so E4.1's linkage comparison passes honestly and the un-recomputed
#: ``current_hash`` is the surviving evidence: a payload break. The pair (payload
#: break, linkage intact) is thus the fingerprint of a re-link rather than of a byte
#: edit, which is why narrowing to one kind is a strengthening and not a concession.
#: Task 7.2's Property 18 asserts this single kind
#: (``packages/tests/test_chain_walk_perturbation_property.py``).
_EXPECTED_BREAK_KINDS: Final[Mapping[Perturbation, tuple[str, ...]]] = {
    Perturbation.NONE: (),
    Perturbation.ALTER_PAYLOAD: (BREAK_KIND_PAYLOAD,),
    Perturbation.DELETE_ROW: (BREAK_KIND_LINKAGE,),
    Perturbation.DELETE_AND_RELINK: (BREAK_KIND_PAYLOAD,),
    Perturbation.SWAP_ADJACENT: (BREAK_KIND_LINKAGE,),
    Perturbation.TRUNCATE_TAIL: (BREAK_KIND_HEAD_UNREACHABLE,),
}


def expected_break_kinds(perturbation: Perturbation) -> tuple[str, ...]:
    """The break kind a correct walk reports for ``perturbation``.

    Empty for :attr:`Perturbation.NONE`; a one-tuple for every other operator, per
    the settled precedence recorded on :data:`_EXPECTED_BREAK_KINDS`.
    """
    return _EXPECTED_BREAK_KINDS[perturbation]


def _hashed_indices(rows: Sequence[ChainRowDraft]) -> tuple[int, ...]:
    """Positions of the non-legacy rows: the only rows a perturbation can target."""
    return tuple(index for index, row in enumerate(rows) if not row.is_legacy)


def apply_perturbation(
    rows: Sequence[ChainRowDraft],
    perturbation: Perturbation,
    index: int,
) -> tuple[ChainRowDraft, ...]:
    """Apply one operator at ``index``, returning the perturbed row sequence.

    Pure: the input sequence is never mutated. ``index`` must address a hashed
    (non-legacy) row; ``perturbed_chains`` only ever draws such an index.
    """
    mutable = list(rows)
    if perturbation is Perturbation.NONE:
        return tuple(mutable)

    if perturbation is Perturbation.ALTER_PAYLOAD:
        target = mutable[index]
        altered = dict(target.canonical)
        # Alter the content without touching either hash: the row now hashes to
        # something other than what it stores, which is a PAYLOAD break.
        altered["audit_trace"] = [*list(altered.get("audit_trace", [])), "tampered"]
        mutable[index] = replace(target, canonical=altered)
        return tuple(mutable)

    if perturbation is Perturbation.DELETE_ROW:
        del mutable[index]
        return tuple(mutable)

    if perturbation is Perturbation.DELETE_AND_RELINK:
        predecessor_hash = mutable[index - 1].current_hash if index > 0 else None
        del mutable[index]
        if index < len(mutable):
            mutable[index] = replace(mutable[index], prev_hash=predecessor_hash)
        return tuple(mutable)

    if perturbation is Perturbation.SWAP_ADJACENT:
        successor = index + 1
        mutable[index], mutable[successor] = mutable[successor], mutable[index]
        return tuple(mutable)

    # TRUNCATE_TAIL: drop every row from ``index`` onward. The recorded head then
    # names a hash the walk never reaches (HEAD_UNREACHABLE).
    return tuple(mutable[:index])


@dataclass(frozen=True)
class PerturbedChain:
    """A perturbed chain plus the verdict a correct walk owes it.

    ``recorded_head`` is always the head of the *original* chain: that is what an
    anchor or a chain-head record holds, and it is what makes a truncation
    detectable at all.
    """

    original: tuple[ChainRowDraft, ...]
    rows: tuple[ChainRowDraft, ...]
    perturbation: Perturbation
    index: int
    recorded_head: str | None
    boundary: datetime

    @property
    def expected_status(self) -> str:
        """``"verified"`` for the null operator, ``"broken"`` for every other."""
        return "verified" if self.perturbation is Perturbation.NONE else "broken"

    @property
    def expected_break_kinds(self) -> tuple[str, ...]:
        """Admissible break kinds (see :data:`_EXPECTED_BREAK_KINDS`)."""
        return expected_break_kinds(self.perturbation)

    @property
    def expected_verified_count(self) -> int:
        """Rows a clean walk verifies: the hashed rows, legacy rows excluded (R6.7)."""
        return len(_hashed_indices(self.original))

    @property
    def expected_legacy_count(self) -> int:
        """Pre-boundary NULL-hash rows, counted separately from ``verified``."""
        return sum(1 for row in self.original if row.is_legacy)

    @property
    def snapshot_upper_bound(self) -> int:
        """Highest ``row_id`` in the walked snapshot (R6.10); ``0`` when empty."""
        return max((row.row_id for row in self.rows), default=0)


@st.composite
def perturbed_chains(
    draw: st.DrawFn,
    *,
    min_length: int = 2,
    max_length: int = 8,
) -> PerturbedChain:
    """A chain, one operator, one target index, and the verdict a walk owes.

    The index is always a *hashed* (non-legacy) row, and it is constrained per
    operator so the drawn example genuinely exhibits the break the operator is named
    for. Constraining it here keeps the property statement free of ``assume`` filters
    that would quietly shrink the example budget:

    * ``DELETE_ROW`` / ``DELETE_AND_RELINK`` / ``SWAP_ADJACENT`` need a surviving
      successor, so the last hashed row is excluded. Deleting the *last* row leaves a
      well-linked shorter chain that only the recorded head detects - that is the
      truncation case, and conflating the two would let a walker pass Property 18
      while reporting the wrong kind.
    * ``TRUNCATE_TAIL`` excludes the first hashed row, so at least one hashed row
      survives. Truncating every hashed row is the zero-rows case (R6.9,
      ``not_verified``), a different clause of the requirement.
    * ``ALTER_PAYLOAD`` accepts any hashed row: an alteration is a payload break
      wherever it lands, including at the head.
    """
    rows = draw(chains(min_length=min_length, max_length=max_length))
    perturbation = draw(perturbations())
    hashed = _hashed_indices(rows)

    if perturbation in (
        Perturbation.DELETE_ROW,
        Perturbation.DELETE_AND_RELINK,
        Perturbation.SWAP_ADJACENT,
    ):
        candidates = hashed[:-1]
    elif perturbation is Perturbation.TRUNCATE_TAIL:
        candidates = hashed[1:]
    else:
        candidates = hashed
    if candidates:
        index = draw(st.sampled_from(candidates))
    else:  # only reachable if a caller asks for a chain with <2 hashed rows
        index = hashed[0] if hashed else 0

    return PerturbedChain(
        original=rows,
        rows=apply_perturbation(rows, perturbation, index),
        perturbation=perturbation,
        index=index,
        recorded_head=head_hash(rows),
        boundary=chain_bounds().migration_boundary,
    )
