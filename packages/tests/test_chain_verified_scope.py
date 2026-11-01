"""R6.15 - ``chain_verified`` is row-level integrity, and cannot be read as more.

Feature: purpose-achievement-audit, task 7.10 (design: "the row-level scope statement
on ``chain_verified`` (R6.15)" is an EXAMPLE-class unit test, not a property).

R6.15: "THE per-row hash recompute that powers the console's ``chain_verified``
tri-state SHALL be reported as row-level integrity only, and THE Atlas_Console SHALL
NOT present it as evidence that no row was deleted and no chain segment was re-linked."

This is a **scope** requirement, so the test has to fail when the scope widens - in
either direction. Widening happens two ways, and each gets its own mechanism, because
a docstring saying "row-level only" is not a mechanism: it is the claim under test.

1. **Capability** (:func:`test_a_deleted_row_still_verifies_row_level`,
   :func:`test_a_re_linked_row_still_verifies_row_level`). The load-bearing half. Two
   real chains built with the untouched production primitives show that
   ``verify_row_hash`` answers ``True`` for a row whose *predecessor was deleted* and
   for a row that was *deleted-and-re-linked* - the two tamper classes R6.2 and R6.3
   name - while ``chain_walk.walk`` reports a ``LINKAGE`` break on the same rows. The
   field therefore carries no deletion and no re-link information: not because a
   comment says so, but because the function returns the same answer either way. If
   anyone widens ``verify_row_hash`` so that it *does* see linkage, these tests fail
   and the scope statement has to be revisited in the same change.
   :func:`test_a_payload_edit_does_not_verify` is the non-vacuity guard: a function
   that returned ``True`` unconditionally would satisfy both cases above.

2. **Implementation** (:func:`test_chain_verified_is_produced_only_by_the_row_recompute`,
   :func:`test_a_missing_chain_hash_is_unknown_never_verified`). The API field is
   produced by exactly one call to ``verify_row_hash`` and the router imports no
   chain-walk symbol, so the field's meaning cannot grow by quietly wiring the walker
   in behind the same key. Absence of a hash stays ``None``; the router never assigns
   ``True``.

3. **Statement and presentation**
   (:func:`test_every_scope_bearing_statement_carries_the_row_level_qualifier`,
   :func:`test_the_console_chain_copy_makes_no_deletion_or_re_link_claim`,
   :func:`test_the_console_input_surface_cannot_express_a_chain_wide_verdict`). The four
   places that state the field's scope must keep the row-level qualifier; the operator-
   visible console copy must make no chain-wide, no-deletion, or no-re-link claim; and
   the chip's entire input surface must remain one row's own three values, so a
   chain-wide verdict cannot be routed through it without widening a type.

Reported, not asserted - one residual gap
-----------------------------------------

The operator-visible success label is ``chain.verified`` = "Chain verified"
(``frontend/src/i18n/en/common.json``). It makes none of the claims R6.15 forbids, so
the scan below passes it honestly. It also carries no row-level qualifier of its own:
the qualification lives one layer away, in ``FE-INV-039``, the chip's doc comment, and
the API docstring, none of which an operator reads. Closing that would be a copy change
(for example "Row hash verified", with the existing ``chain.hash_title`` wording
attached to the success branch as a ``title`` as well as the danger branch) in
``frontend/`` - out of this task's ownership, so it is reported rather than edited, and
it is deliberately not asserted here: a test written to fail on today's committed copy
would be a red suite standing in for a report.

**No Postgres, no network, no browser.** Reads are ``encoding='utf-8'`` (E-S13-07);
the Postgres-backed deletion and snapshot cases are
``tests/integration/test_audit_chain_tamper_postgres.py``.

**I-4.** ``make_canonical_row``, ``hash_payload_for_row`` and ``verify_row_hash`` are
imported and called, never reimplemented and never modified - they are byte-pinned by
``packages/tests/test_audit_chain.py``.

**Validates: Requirement 6.15.**
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID, uuid4

from synapse_common.audit_chain import (
    hash_payload_for_row,
    make_canonical_row,
    verify_row_hash,
)

from orchestrator.audit.chain_walk import (
    BreakKind,
    ChainRow,
    WalkReport,
    load_chain_bounds,
    walk,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: The API field's implementation.
API_ROUTER: Final[Path] = REPO_ROOT / "api" / "routers" / "decisions.py"

#: The four places that state what ``chain_verified`` means. Every one of them must
#: keep a row-level qualifier; stripping it from any single one is the widening R6.15
#: forbids, and is what this list makes mechanical.
SCOPE_STATEMENT_SOURCES: Final[tuple[Path, ...]] = (
    API_ROUTER,
    REPO_ROOT / "frontend" / "src" / "design-system" / "compounds" / "ChainIntegrityChip.tsx",
    REPO_ROOT / "frontend" / "src" / "surfaces" / "operations" / "logic.ts",
    REPO_ROOT / "frontend" / "spec" / "fe_invariants.yaml",
)

#: The two that carry the field's documented *contract* (as opposed to a component's
#: local doc comment) must also delegate the chain-wide question explicitly.
WALK_DELEGATING_SOURCES: Final[tuple[Path, ...]] = (
    API_ROUTER,
    REPO_ROOT / "frontend" / "spec" / "fe_invariants.yaml",
)

CHIP_SOURCE: Final[Path] = (
    REPO_ROOT / "frontend" / "src" / "design-system" / "compounds" / "ChainIntegrityChip.tsx"
)
LOGIC_SOURCE: Final[Path] = REPO_ROOT / "frontend" / "src" / "surfaces" / "operations" / "logic.ts"
I18N_EN_COMMON: Final[Path] = REPO_ROOT / "frontend" / "src" / "i18n" / "en" / "common.json"

#: Any one of these, case-insensitively, keeps a scope statement row-scoped.
ROW_LEVEL_MARKERS: Final[tuple[str, ...]] = ("single-row", "row-level", "per-row")

#: Claim shapes R6.15 forbids: a chain-wide verdict, a no-deletion claim, or a
#: no-re-link claim. Deliberately assertive forms only. A *disclaimer* ("this does not
#: prove the chain is intact") is the honest wording R6.15 wants, and must not be
#: charged as a violation - which is why "full chain walk remains `synapse audit
#: verify`'s job" (the committed delegation in FE-INV-039) is not matched by any
#: pattern here.
FORBIDDEN_CLAIMS: Final[tuple[str, ...]] = (
    r"\bno\s+rows?\s+(?:were\s+|was\s+|has\s+been\s+|have\s+been\s+)?deleted\b",
    r"\bnothing\s+(?:was\s+)?deleted\b",
    r"\bno\s+deletions?\b",
    r"\bno\s+(?:chain\s+)?segments?\s+(?:was\s+|were\s+)?re-?linked\b",
    r"\bchain\s+(?:is\s+)?intact\b",
    r"\bunbroken\s+chain\b",
    r"\b(?:whole|entire|full)\s+chain\s+(?:is\s+)?verified\b",
    r"\bverifies\s+the\s+(?:whole|entire|full)\s+chain\b",
    r"\btamper-?proof\b",
)

#: Walker/CLI symbols. Their presence in the API router would mean the field's meaning
#: had grown past a single row's bytes.
CHAIN_WALK_SYMBOLS: Final[tuple[str, ...]] = (
    "chain_walk",
    "WalkReport",
    "ChainBreak",
    "BreakKind",
    "orchestrator.audit",
    "from orchestrator",
    "import orchestrator",
)

#: The chip's whole input surface: one row's own three values. Nothing here can carry
#: information about another row, so no chain-wide verdict can be routed through it.
CHIP_PROPS: Final[frozenset[str]] = frozenset({"verified", "prevHash", "currentHash"})

_CHAIN_LENGTH: Final[int] = 4
_DELETED_INDEX: Final[int] = 1


def _read(path: Path) -> str:
    """Read a committed source file (E-S13-07: always ``encoding='utf-8'``)."""
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace so a phrase check is not defeated by a line wrap.

    ``fe_invariants.yaml`` folds its descriptions, so "synapse audit verify" arrives as
    "synapse audit\\n      verify". A scope statement that a reader sees as one sentence
    must be matched as one sentence - in both directions: a forbidden claim split across
    two lines would otherwise pass the scan below.
    """
    return re.sub(r"\s+", " ", text)


# ---------------------------------------------------------------------------
# A real chain, built by the production primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    """One stored row: the canonical inputs plus the two stored chain values.

    Frozen, and every mutation below goes through :func:`dataclasses.replace`, so a
    "tampered" row is a new value and the original stays available for comparison.
    """

    position: int
    created_at: datetime
    decision_id: UUID
    tier: str
    selected_action: dict[str, Any]
    pareto_weights: dict[str, float]
    confidence: float
    proposals: list[dict[str, Any]]
    audit_trace: list[str]
    prev_hash: str | None
    current_hash: str

    def canonical(self) -> dict[str, Any]:
        """The hashed dict, from the byte-pinned ``make_canonical_row`` (I-4)."""
        return make_canonical_row(
            decision_id=self.decision_id,
            tier=self.tier,
            selected_action=self.selected_action,
            pareto_weights=self.pareto_weights,
            confidence=self.confidence,
            proposals=self.proposals,
            audit_trace=self.audit_trace,
        )

    def row_level_verdict(self) -> bool:
        """Exactly what ``api/routers/decisions.py`` computes for this row.

        Same function, same argument set, same stored values: this is the API's
        ``chain_verified`` for the row, not a model of it.
        """
        return verify_row_hash(
            prev_hash=self.prev_hash,
            current_hash=self.current_hash,
            decision_id=self.decision_id,
            tier=self.tier,
            selected_action=self.selected_action,
            pareto_weights=self.pareto_weights,
            confidence=self.confidence,
            proposals=self.proposals,
            audit_trace=self.audit_trace,
        )


def _boundary() -> datetime:
    """The committed chain-migration boundary (AD-13), never a literal."""
    return load_chain_bounds().migration_boundary


def _build_chain(length: int = _CHAIN_LENGTH) -> tuple[_Row, ...]:
    """A correctly linked chain of ``length`` post-boundary rows.

    Deterministic apart from the UUIDs, which nothing here asserts on.
    """
    boundary = _boundary()
    rows: list[_Row] = []
    prev: str | None = None
    for index in range(length):
        decision_id = uuid4()
        tier = "tier_3"
        selected_action: dict[str, Any] = {"action": "restock", "quantity": 10 * index}
        pareto_weights: dict[str, float] = {"cost": 0.5, "time": 0.5}
        confidence = 0.75
        proposals: list[dict[str, Any]] = [{"agent_name": "inventory_sentinel", "confidence": 0.8}]
        audit_trace: list[str] = [f"tier={tier}", f"seq={index}"]
        canonical = make_canonical_row(
            decision_id=decision_id,
            tier=tier,
            selected_action=selected_action,
            pareto_weights=pareto_weights,
            confidence=confidence,
            proposals=proposals,
            audit_trace=audit_trace,
        )
        current = hash_payload_for_row(prev, canonical)
        rows.append(
            _Row(
                position=index,
                created_at=boundary + timedelta(minutes=index + 1),
                decision_id=decision_id,
                tier=tier,
                selected_action=selected_action,
                pareto_weights=pareto_weights,
                confidence=confidence,
                proposals=proposals,
                audit_trace=audit_trace,
                prev_hash=prev,
                current_hash=current,
            )
        )
        prev = current
    return tuple(rows)


def _walk(rows: Sequence[_Row]) -> WalkReport:
    """Walk the same rows through the production walker, in the given order."""
    return walk(
        [
            ChainRow(
                row_id=ordinal,
                created_at=row.created_at,
                prev_hash=row.prev_hash,
                current_hash=row.current_hash,
                canonical=row.canonical(),
            )
            for ordinal, row in enumerate(rows, start=1)
        ],
        boundary=_boundary(),
        recorded_head=None,
        max_rows=load_chain_bounds().max_rows,
    )


# ---------------------------------------------------------------------------
# 1. Capability - the field cannot see deletion or a re-link
# ---------------------------------------------------------------------------


def test_a_deleted_row_still_verifies_row_level() -> None:
    """R6.15 / R6.2: the successor of a deleted row reports ``chain_verified=True``.

    The successor's stored ``prev_hash`` now points at a hash that is no longer in the
    chain, and its own bytes are untouched - so the per-row recompute is satisfied and
    the walk is not. That gap *is* the scope of the field.
    """
    chain = _build_chain()
    assert _walk(chain).status == "verified", "the unperturbed chain must verify first"

    survivors = tuple(row for row in chain if row.position != _DELETED_INDEX)
    successor = chain[_DELETED_INDEX + 1]

    # The API's field: True. It has no way to know a row is missing.
    assert successor.row_level_verdict() is True

    # The walker: one linkage break, named at the successor.
    report = _walk(survivors)
    assert report.status == "broken"
    first = report.first_break
    assert first is not None
    assert first.kind is BreakKind.LINKAGE
    assert first.row_id == _DELETED_INDEX + 1  # 1-based ordinal in the walked snapshot
    assert BreakKind.PAYLOAD not in {chain_break.kind for chain_break in report.breaks}


def test_a_re_linked_row_still_verifies_row_level() -> None:
    """R6.15 / R6.3: a deleted-and-re-linked row reports ``chain_verified=True``.

    R6.3's tamper class exactly: the row is deleted and its successor's ``prev_hash``
    *and* ``current_hash`` are rewritten so the successor "recomputes consistently
    against its own stored ``prev_hash``". The per-row recompute is what "consistently
    against its own stored prev_hash" means, so it answers True by construction. The
    walk still finds the fault - one row later, where the re-linked row's new
    ``current_hash`` no longer matches what the tail stores.
    """
    chain = _build_chain()
    predecessor = chain[_DELETED_INDEX - 1]
    successor = chain[_DELETED_INDEX + 1]

    re_linked = replace(successor, prev_hash=predecessor.current_hash)
    re_linked = replace(
        re_linked,
        current_hash=hash_payload_for_row(predecessor.current_hash, re_linked.canonical()),
    )
    assert re_linked.current_hash != successor.current_hash

    # The API's field: True. The row is internally consistent, which is all it checks.
    assert re_linked.row_level_verdict() is True

    tampered = (
        *chain[:_DELETED_INDEX],
        re_linked,
        *chain[_DELETED_INDEX + 2 :],
    )
    report = _walk(tampered)
    assert report.status == "broken"
    first = report.first_break
    assert first is not None
    assert first.kind is BreakKind.LINKAGE
    # The re-linked row itself passes the walk too - the tail is what gives it away.
    assert first.row_id == _DELETED_INDEX + 2


def test_a_payload_edit_does_not_verify() -> None:
    """Non-vacuity: the field does detect the one class it claims.

    Without this, a ``verify_row_hash`` that returned ``True`` unconditionally would
    satisfy both cases above, and "row-level integrity only" would be indistinguishable
    from "nothing at all".
    """
    chain = _build_chain()
    target = chain[_DELETED_INDEX]
    assert target.row_level_verdict() is True

    altered = replace(target, audit_trace=[*target.audit_trace, "tampered"])
    assert altered.row_level_verdict() is False

    report = _walk((*chain[:_DELETED_INDEX], altered, *chain[_DELETED_INDEX + 1 :]))
    assert report.status == "broken"
    first = report.first_break
    assert first is not None
    assert first.kind is BreakKind.PAYLOAD


# ---------------------------------------------------------------------------
# 2. Implementation - the field's meaning cannot grow behind the same key
# ---------------------------------------------------------------------------


def test_chain_verified_is_produced_only_by_the_row_recompute() -> None:
    """The API field has exactly one producer, and it is the single-row recompute.

    Read as text rather than imported: the assertion is about the committed source, and
    this way the test runs in any job without FastAPI installed.
    """
    source = _read(API_ROUTER)

    assert "from synapse_common.audit_chain import verify_row_hash" in source
    assert "chain_verified = verify_row_hash(" in source

    assignments = re.findall(r"^\s*chain_verified(?:\s*:[^=]+)?\s*=", source, re.MULTILINE)
    assert len(assignments) == 2, (
        "chain_verified must have exactly two assignments - the None declaration and "
        f"the single-row recompute - found {len(assignments)}: widening its meaning is "
        "a scope change (R6.15), not an edit"
    )

    for symbol in CHAIN_WALK_SYMBOLS:
        assert symbol not in source, (
            f"api/routers/decisions.py references {symbol!r}: chain_verified would no "
            "longer be row-level integrity only, and R6.15's scope statement plus the "
            "console copy have to change in the same commit"
        )


def test_a_missing_chain_hash_is_unknown_never_verified() -> None:
    """A row with no ``current_hash`` reports ``None`` - absence is not proof (I-7)."""
    source = _read(API_ROUTER)
    assert "chain_verified: bool | None = None" in source
    assert "if current_hash is not None:" in source
    assert "chain_verified = True" not in source
    assert "chain_verified = False" not in source


# ---------------------------------------------------------------------------
# 3. Statement and presentation
# ---------------------------------------------------------------------------


def test_every_scope_bearing_statement_carries_the_row_level_qualifier() -> None:
    """Each of the four scope statements keeps its row-level qualifier.

    Stripping "single-row" from any one of them widens the claim in the place a reader
    actually looks, which is what R6.15's "SHALL be reported as row-level integrity
    only" is about.
    """
    for path in SCOPE_STATEMENT_SOURCES:
        text = _flat(_read(path)).lower()
        assert any(marker in text for marker in ROW_LEVEL_MARKERS), (
            f"{path.relative_to(REPO_ROOT).as_posix()} states the scope of "
            f"chain_verified and carries none of {ROW_LEVEL_MARKERS} (R6.15)"
        )

    for path in WALK_DELEGATING_SOURCES:
        text = _flat(_read(path))
        assert "chain walk" in text.lower(), (
            f"{path.relative_to(REPO_ROOT).as_posix()} must keep the statement that "
            "the chain-wide question belongs to the chain walk, not to this field"
        )
        assert "audit verify" in text or "audit.cli" in text, (
            f"{path.relative_to(REPO_ROOT).as_posix()} must name the verifier that "
            "does answer the chain-wide question"
        )


def test_the_console_chain_copy_makes_no_deletion_or_re_link_claim() -> None:
    """R6.15's console clause: no chain-wide, no-deletion, no-re-link claim anywhere.

    Scanned over the operator-visible ``chain.*`` copy and over the four scope
    statements. Assertive claim shapes only - a disclaimer is the wording R6.15 wants
    and is deliberately not matched.
    """
    copy: dict[str, Any] = json.loads(_read(I18N_EN_COMMON))
    chain_copy = {key: value for key, value in copy.items() if key.startswith("chain.")}
    assert chain_copy, "the chain.* console copy keys vanished; R6.15 has no subject"

    scanned: dict[str, str] = {
        f"{I18N_EN_COMMON.name}:{key}": _flat(str(value)) for key, value in chain_copy.items()
    }
    for path in SCOPE_STATEMENT_SOURCES:
        scanned[path.relative_to(REPO_ROOT).as_posix()] = _flat(_read(path))

    for where, text in scanned.items():
        for pattern in FORBIDDEN_CLAIMS:
            match = re.search(pattern, text, re.IGNORECASE)
            assert match is None, (
                f"{where} claims {match.group(0)!r}. chain_verified is a single-row "
                "hash recompute: it cannot detect a deleted row or a re-linked "
                "segment, so presenting it as evidence of either violates R6.15. The "
                "chain-wide question belongs to `python -m orchestrator.audit.cli "
                "verify`."
            )


def test_the_console_input_surface_cannot_express_a_chain_wide_verdict() -> None:
    """The chip's inputs are one row's own values, and the helper takes one tri-state.

    A chain-wide verdict is information about *other* rows. Nothing in this input
    surface can carry it, so widening the console's claim requires widening a type
    here - and that is what this test catches.
    """
    chip = _read(CHIP_SOURCE)
    block = re.search(r"interface\s+ChainIntegrityChipProps\s*\{(?P<body>.*?)\}", chip, re.DOTALL)
    assert block is not None, "ChainIntegrityChipProps is gone; R6.15 has no subject"
    props = set(re.findall(r"readonly\s+(\w+)", block.group("body")))
    assert props == set(CHIP_PROPS), (
        f"ChainIntegrityChip's props changed to {sorted(props)}. Its inputs are one "
        "row's own values by design: an input carrying chain-wide state would let the "
        "console present a claim the field cannot support (R6.15)"
    )

    logic = _read(LOGIC_SOURCE)
    assert "export function chainIntegrity(chainVerified: boolean | null | undefined)" in logic, (
        "chainIntegrity's input widened past the single tri-state the API returns; the "
        "tri-state IS the scope boundary (R6.15)"
    )
