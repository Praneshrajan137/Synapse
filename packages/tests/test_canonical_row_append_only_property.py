"""Property-based test for canonical rows and append-only history (design AD-10 / CF-1).

Feature: purpose-achievement-audit, Property 21: Canonical rows round-trip and audit
history is append-only

    *For any* decision, ``make_canonical_row`` followed by canonical JSON serialisation
    followed by parsing yields an equivalent row whose key set is exactly the frozen
    field set; and *for any* sequence of audit operations expressible by the application
    role, the row count is non-decreasing, no previously written row changes bytes, and
    recording data provenance adds a row to the provenance table without altering any
    canonical audit row.

Why the property is shaped this way. I-4 is not "there is an append-only table". It is
that a recorded audit fact is *unchangeable*, and that a new kind of fact is added by a
new stream rather than by editing the hashed row. Requirement 4.4 wanted a
data-provenance value on the audit record; conflict CF-1 resolved that against I-4 and
E-S9-02 by giving provenance its own append-only table keyed by ``decision_id``, exactly
as ``decision_outcomes`` did. So the property has to hold three things at once, and each
one is a way the resolution could have been got wrong:

* **The canonical row is untouched.** ``make_canonical_row`` is byte-pinned by
  ``packages/tests/test_audit_chain.py`` (literal digest + independent stdlib recompute).
  It is imported and called here as a **black box** - never modified, never
  re-implemented, never partially mirrored. What this file adds over that pin is
  *universality*: the existing pins cover two fixed rows, and this covers every row the
  generators can draw. The round trip is asserted through the plain
  ``json.dumps(obj, sort_keys=True, separators=(',',':'))`` form with **no** ``default=``
  hook, so a canonical row that ever leaked a ``UUID`` or ``datetime`` object would raise
  ``TypeError`` here rather than quietly stringify and change the digest.

* **Byte stability is asserted across two independent constructions**, not two calls on
  one object. The second construction is built from the same logical values with every
  mapping's insertion order reversed. A serialiser that leaked dict order would produce a
  different digest for a logically identical row - which is a chain break with no tamper
  behind it - and ``sort_keys=True`` is what buys the immunity. Asserting it on one object
  twice would prove nothing about that.

* **The append-only surface is read out of the DDL, not asserted about it.** The verb set
  the application role holds on each ledger table is *parsed* from every migration under
  ``infrastructure/postgres/`` and ``orchestrator/audit/migrations/``, and the history
  strategy then draws its operations **from that parsed set**. That is the load-bearing
  coupling: if a future migration granted ``UPDATE`` on a ledger table, the strategy would
  draw an ``UPDATE``, the append-only store would refuse it, and this test would go red at
  the commit that widened the grant. A test that hardcoded ``{SELECT, INSERT}`` would stay
  green through exactly that change.

Two non-vacuity guards, because a check that cannot fail is not a check (RC-3):

1. ``audit_outbox`` is the documented exception - a queue, deliberately granted ``UPDATE``
   (``03_sprint7_outbox.sql``), credited as correct in the audit's *unjustified
   perfectionism* section. The parser is required to **see** that ``UPDATE``. If it could
   not, its silence about the ledger tables would be worthless.
2. The append-only predicate is exercised over synthetic DDL covering every
   grant/revoke verb combination, so "no violation found in the real files" is a finding
   rather than an artefact of a predicate that never fires.

**No Postgres, no clock, no subprocess (I-0).** Every decision under test is either pure
value manipulation or a static read of committed text: the DDL is *parsed*, never applied,
and the writer is inspected by ``ast``, never executed. The database-backed halves - that
Postgres actually refuses the revoked verb, and that the migration's own ``I-4 VIOLATION``
self-test fires - belong to ``.github/workflows/integration.yml``, which has a Postgres
service. They are not asserted here and are not claimed to be (I-7).

Deliberately **not** duplicated. ``orchestrator/tests/test_decision_data_provenance.py``
(task 7.8) owns the example-class facts: the byte identity of the canonical migration and
its Docker-init mirror, the runner/compose wiring, UTC normalisation, and frozen-ness.
That file's docstring hands the universal round-trip and append-only claims to this one.
What this file asserts about the two SQL files is a different thing from byte identity: the
*derived* grant surface, so a reformat that preserved meaning would not fail here and a
meaning-preserving-looking edit that widened a grant would.

``max_examples`` is never set - the budget comes from the root ``conftest.py`` profiles
(``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000). Nothing here is
slow-marked: there is no twin, no protocol, no browser and no database in it.

**Validates: Requirements 4.4** (and invariant I-4)
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from orchestrator.audit import data_provenance
from orchestrator.audit.models import (
    PROVENANCE_FIELDS,
    SOURCE_CLASSES,
    DecisionDataProvenance,
)
from packages.tests.strategies_audit import CanonicalDecision, canonical_decisions
from synapse_common.audit_chain import hash_payload_for_row, make_canonical_row

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: Every directory holding DDL that can grant on an audit table. Globbed rather than
#: listed file by file, so a new migration is covered the day it lands instead of the day
#: someone remembers to add it here.
_SQL_DIRS: Final[tuple[Path, ...]] = (
    _REPO_ROOT / "infrastructure" / "postgres",
    _REPO_ROOT / "orchestrator" / "audit" / "migrations",
)

#: The canonical migration set and its Docker-init mirror set, in that order. Docker init
#: reads only from ``infrastructure/postgres/`` (E-S9-14), so the two must agree about
#: every table they both declare - otherwise a container and a migrated database end up
#: with different privileges and only one of them is the one anybody tested.
_CANONICAL_DIR: Final = _REPO_ROOT / "orchestrator" / "audit" / "migrations"
_MIRROR_DIR: Final = _REPO_ROOT / "infrastructure" / "postgres"

#: The role the orchestrator connects as. The privileged erasure role (DPDPA, E-S9-10) is
#: deliberately out of scope: a legal erasure obligation outranks append-only convenience
#: and the audit records that as correct.
_APP_ROLE: Final = "synapse_app"

#: The only verbs an append-only ledger may expose to the application role.
_APPEND_ONLY_VERBS: Final[frozenset[str]] = frozenset({"SELECT", "INSERT"})

#: Verbs that would let a recorded fact change or vanish.
_MUTATING_VERBS: Final[frozenset[str]] = frozenset(
    {"UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER"}
)

#: The append-only fact streams. ``decision_data_provenance`` is the new one (AD-10);
#: ``audit_consensus`` is the hashed chain itself; ``decision_outcomes`` is the precedent
#: CF-1 followed. All three are ledgers: a correction appends.
_LEDGER_TABLES: Final[tuple[str, ...]] = (
    "audit_consensus",
    "decision_data_provenance",
    "decision_outcomes",
)

#: The documented exception, and this file's proof that the parser can see an ``UPDATE``.
#: ``audit_outbox`` is a publish queue mutated PENDING -> IN_FLIGHT -> PUBLISHED|FAILED;
#: the requirements document files objecting to its ``UPDATE`` grant under unjustified
#: perfectionism, so it is asserted to be a queue rather than charged as a defect.
_QUEUE_TABLE: Final = "audit_outbox"

#: Tokens that appear where a table name would in a non-table grant
#: (``ON SCHEMA ...``, ``ON ALL TABLES IN SCHEMA ...``). Excluded so a schema-wide or
#: database-wide statement can never be mistaken for a per-table one.
_NON_TABLE_TOKENS: Final[frozenset[str]] = frozenset(
    {"ALL", "SCHEMA", "DATABASE", "TABLES", "SEQUENCES", "FUNCTIONS", "ROUTINES"}
)

#: The seven frozen keys of the hashed canonical row.
#:
#: Duplicating ``test_audit_chain.py::test_canonical_row_field_set_is_frozen`` is
#: deliberate, not drift. The field set changes only through a chain-rewrite migration
#: (E-S9-02), so two independent pins of it are redundancy on a contract that is supposed
#: to be immovable - and this one is asserted over generated rows rather than one fixture.
_CANONICAL_FIELDS: Final[tuple[str, ...]] = (
    "audit_trace",
    "confidence",
    "decision_id",
    "pareto_weights",
    "proposals",
    "selected_action",
    "tier",
)

#: The modules that make up the provenance write path. Both are scanned for SQL: the
#: writer because it issues statements, the model module because a future edit could put
#: one there and the check should already cover it.
_PROVENANCE_MODULES: Final[tuple[str, ...]] = (
    "orchestrator/audit/data_provenance.py",
    "orchestrator/audit/models.py",
)

#: Cursor methods that hand SQL to the database.
_EXECUTE_ATTRS: Final[frozenset[str]] = frozenset(
    {"execute", "executemany", "executescript", "execute_batch", "execute_values"}
)

_MUTATION_WORD_RE: Final = re.compile(
    r"\b(?:UPDATE|DELETE|TRUNCATE|DROP|ALTER)\b", re.IGNORECASE
)

_TABLE_GRANT_RE: Final = re.compile(
    r"\bGRANT\s+(?P<privs>[A-Za-z, ]+?)\s+ON\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s+TO\s+(?P<role>[A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.IGNORECASE,
)

_TABLE_REVOKE_RE: Final = re.compile(
    r"\bREVOKE\s+(?P<privs>[A-Za-z, ]+?)\s+ON\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s+FROM\s+(?P<role>[A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.IGNORECASE,
)

#: ``GRANT ... ON ALL TABLES IN SCHEMA x TO role`` and the
#: ``ALTER DEFAULT PRIVILEGES ... GRANT ... ON TABLES TO role`` form. Both apply to every
#: table in the schema, so whatever they grant is a floor under every ledger table's
#: surface and has to be folded in - otherwise a schema-wide ``UPDATE`` would be invisible
#: to a parser that only read per-table statements.
_WILDCARD_GRANT_RE: Final = re.compile(
    r"\bGRANT\s+(?P<privs>[A-Za-z, ]+?)\s+ON\s+"
    r"(?:ALL\s+TABLES\s+IN\s+SCHEMA\s+[A-Za-z_][A-Za-z0-9_]*|TABLES)"
    r"\s+TO\s+(?P<role>[A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.IGNORECASE,
)


class AppendOnlyViolation(RuntimeError):
    """Raised when an operation would change or remove an already-written row.

    Stands in for what Postgres does when the application role attempts a revoked verb.
    It is never expected to fire while the grant surface stays append-only - and if a
    migration widens that surface, this is the exception that reports it.
    """


# ---------------------------------------------------------------------------
# The committed grant surface, parsed (never assumed)
# ---------------------------------------------------------------------------


def _privileges(raw: str) -> frozenset[str]:
    """Split a ``GRANT``/``REVOKE`` privilege list into upper-case verbs."""
    return frozenset(part.strip().upper() for part in raw.split(",") if part.strip())


@lru_cache(maxsize=1)
def sql_sources() -> tuple[tuple[Path, str], ...]:
    """Every ``.sql`` file under the DDL directories, sorted (``utf-8``, E-S13-07)."""
    found: list[tuple[Path, str]] = []
    for directory in _SQL_DIRS:
        for path in sorted(directory.glob("*.sql")):
            found.append((path, path.read_text(encoding="utf-8")))
    return tuple(found)


def table_grants(text: str, *, role: str = _APP_ROLE) -> dict[str, frozenset[str]]:
    """Per-table verbs ``role`` holds after the table-scoped statements in ``text``.

    Grants accumulate, revokes subtract, in file order - the order Postgres applies them.
    """
    surface: dict[str, frozenset[str]] = {}
    events: list[tuple[int, bool, str, frozenset[str]]] = []
    for match in _TABLE_GRANT_RE.finditer(text):
        events.append(
            (match.start(), True, match.group("table").lower(), _privileges(match.group("privs")))
        )
        if match.group("role") != role:
            events.pop()
    for match in _TABLE_REVOKE_RE.finditer(text):
        events.append(
            (match.start(), False, match.group("table").lower(), _privileges(match.group("privs")))
        )
        if match.group("role") != role:
            events.pop()
    for _, is_grant, table, verbs in sorted(events, key=lambda event: event[0]):
        if table in _NON_TABLE_TOKENS or table.upper() in _NON_TABLE_TOKENS:
            continue
        current = surface.get(table, frozenset())
        surface[table] = current | verbs if is_grant else current - verbs
    return surface


def wildcard_grants(text: str, *, role: str = _APP_ROLE) -> frozenset[str]:
    """Verbs granted to ``role`` across every table in the schema by ``text``."""
    granted: frozenset[str] = frozenset()
    for match in _WILDCARD_GRANT_RE.finditer(text):
        if match.group("role") != role:
            continue
        granted |= _privileges(match.group("privs"))
    return granted


def directory_surface(directory: Path) -> dict[str, frozenset[str]]:
    """Table-scoped surface declared by one DDL directory, files applied in name order."""
    surface: dict[str, frozenset[str]] = {}
    for path, text in sql_sources():
        if path.parent != directory:
            continue
        for table, verbs in table_grants(text).items():
            surface[table] = surface.get(table, frozenset()) | verbs
        for match in _TABLE_REVOKE_RE.finditer(text):
            if match.group("role") != _APP_ROLE:
                continue
            table = match.group("table").lower()
            if table in surface:
                surface[table] -= _privileges(match.group("privs"))
    return surface


@lru_cache(maxsize=1)
def effective_surface() -> Mapping[str, frozenset[str]]:
    """The verbs ``synapse_app`` effectively holds per table, schema-wide floor included.

    This is the function the history strategy draws its operations from, which is what
    makes the append-only claim a consequence of the committed DDL rather than a belief
    about it.
    """
    floor = frozenset().union(*(wildcard_grants(text) for _, text in sql_sources()))
    surface: dict[str, frozenset[str]] = {}
    for path, text in sql_sources():
        del path
        for table, verbs in table_grants(text).items():
            surface[table] = surface.get(table, frozenset()) | verbs
    for path, text in sql_sources():
        del path
        for match in _TABLE_REVOKE_RE.finditer(text):
            if match.group("role") != _APP_ROLE:
                continue
            table = match.group("table").lower()
            if table in surface:
                surface[table] -= _privileges(match.group("privs"))
    return {table: verbs | floor for table, verbs in surface.items()}


def permitted_verbs(table: str) -> frozenset[str]:
    """Verbs the application role holds on ``table``, from the parsed DDL."""
    return effective_surface()[table]


def mutation_verbs(verbs: frozenset[str]) -> frozenset[str]:
    """The subset of ``verbs`` that could change or remove an already-written row."""
    return verbs & _MUTATING_VERBS


# ---------------------------------------------------------------------------
# An append-only store: what the application role can actually express
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerOp:
    """One operation the application role is permitted to attempt against a table."""

    table: str
    verb: str
    payload: str


@dataclass(frozen=True)
class AppendOnlyTable:
    """Rows as canonical byte strings, in insert order. Immutable by construction.

    ``permitted`` is the parsed grant surface, not a literal. ``apply`` refuses anything
    that is not ``SELECT`` or ``INSERT`` **even when the grant surface permits it**, so a
    widened grant surfaces as a loud failure instead of a silently-passing test.
    """

    name: str
    permitted: frozenset[str]
    rows: tuple[str, ...] = ()

    def apply(self, verb: str, payload: str) -> AppendOnlyTable:
        if verb not in self.permitted:
            msg = f"{verb} is not granted on {self.name}: {sorted(self.permitted)}"
            raise AppendOnlyViolation(msg)
        if verb == "SELECT":
            return self
        if verb == "INSERT":
            return replace(self, rows=(*self.rows, payload))
        msg = (
            f"{verb} on {self.name} would change or remove a written row; "
            f"{self.name} is granted {sorted(self.permitted)}"
        )
        raise AppendOnlyViolation(msg)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

#: Fixed UTC offsets rather than ``st.timezones()``: the named-zone strategy needs the
#: IANA database, which on Windows means a new dependency (I-1 forbids one) for no gain -
#: the model normalises by offset, so offsets are the whole domain that matters.
_OFFSETS: Final[tuple[timezone, ...]] = (
    timezone.utc,
    timezone(timedelta(hours=5, minutes=30)),
    timezone(timedelta(hours=-8)),
    timezone(timedelta(hours=9)),
    timezone(timedelta(hours=-3, minutes=-30)),
)

#: Hypothesis requires naive bounds when ``timezones`` is supplied.
_MIN_OBSERVED: Final = datetime(2026, 1, 1)
_MAX_OBSERVED: Final = datetime(2027, 1, 1)

#: Feed revisions look like ``ext:o-4213`` or ``synapse.orders.demand@0:4213``.
_REVISION_ALPHABET: Final = "abcdefghijklmnopqrstuvwxyz0123456789.:@_-"


def provenance_rows() -> st.SearchStrategy[DecisionDataProvenance]:
    """One append-only provenance record.

    ``source_class`` is drawn from the committed :data:`SOURCE_CLASSES` tuple rather than
    a local literal, so a fourth class added to the model is covered here automatically.
    ``is_synthetic`` is drawn independently of the class on purpose: the writer records a
    disagreement rather than normalising it away, and a round trip must preserve the
    disagreement exactly as it preserves an agreement.
    """
    return st.builds(
        DecisionDataProvenance,
        decision_id=st.uuids(version=4),
        source_class=st.sampled_from(SOURCE_CLASSES),
        is_synthetic=st.booleans(),
        feed_revision=st.one_of(
            st.none(),
            st.text(alphabet=_REVISION_ALPHABET, min_size=1, max_size=32),
        ),
        observed_at=st.datetimes(
            min_value=_MIN_OBSERVED,
            max_value=_MAX_OBSERVED,
            timezones=st.sampled_from(_OFFSETS),
        ),
    )


@st.composite
def ledger_histories(draw: st.DrawFn) -> tuple[LedgerOp, ...]:
    """A sequence of audit operations **expressible by the application role**.

    The verb of each operation is drawn from the surface parsed out of the committed DDL
    (:func:`permitted_verbs`), never from a literal list. That is the whole point: the
    property is quantified over what the role can actually do, so widening the grant
    widens the quantification and the append-only assertions below stop holding.
    """
    length = draw(st.integers(min_value=1, max_value=10))
    ops: list[LedgerOp] = []
    for _ in range(length):
        table = draw(st.sampled_from(("audit_consensus", "decision_data_provenance")))
        verb = draw(st.sampled_from(sorted(permitted_verbs(table))))
        if verb != "INSERT":
            ops.append(LedgerOp(table=table, verb=verb, payload=""))
            continue
        payload = (
            draw(canonical_decisions()).canonical_json()
            if table == "audit_consensus"
            else draw(provenance_rows()).to_canonical_json()
        )
        ops.append(LedgerOp(table=table, verb=verb, payload=payload))
    return tuple(ops)


def declared_surfaces() -> st.SearchStrategy[tuple[frozenset[str], frozenset[str]]]:
    """A (granted, revoked) verb pair over the full verb vocabulary.

    Used to prove the append-only predicate fires. Without this the real-file result
    ("no ledger table exposes a mutating verb") could just as well mean the predicate is
    incapable of finding one.
    """
    vocabulary = sorted(_APPEND_ONLY_VERBS | _MUTATING_VERBS)
    verb_sets = st.frozensets(st.sampled_from(vocabulary))
    return st.tuples(verb_sets, verb_sets)


# ---------------------------------------------------------------------------
# Static inspection of the writer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModuleSql:
    """What a module hands to a database, and every string it could hand.

    ``opaque_execute`` is the honest escape hatch: a statement assembled at runtime out
    of a name this scan cannot resolve is reported, not assumed benign. An empty
    ``opaque_execute`` is what makes ``statements`` a complete account of the module's
    SQL - and therefore what makes "this module issues no UPDATE" a claim rather than a
    hope (I-7).
    """

    module: str
    statements: tuple[str, ...]
    literals: tuple[str, ...]
    opaque_execute: tuple[str, ...]


def _joined_text(node: ast.JoinedStr) -> str:
    """Reconstruct an f-string, interpolations replaced by ``{}``."""
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append("{}")
    return "".join(parts)


def _static_text(node: ast.expr) -> str | None:
    """The text of ``node`` if it is statically visible, else ``None``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return _joined_text(node)
    return None


def scan_module(relative: str) -> ModuleSql:
    """Parse ``relative`` and collect its SQL and its executable string literals.

    A bare string expression statement is documentation - a module, class, function or
    attribute docstring - and is excluded. Nothing else is: an executable string literal
    is exactly what a query is made of, so all of them are in scope. This is a read plus
    an ``ast.parse``; the module is never imported for this and never run.
    """
    tree = ast.parse((_REPO_ROOT / relative).read_text(encoding="utf-8"))
    documentation = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }

    literals: list[str] = []
    statements: list[str] = []
    opaque: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in documentation:
                literals.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            literals.append(_joined_text(node))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _EXECUTE_ATTRS
        ):
            text = _static_text(node.args[0]) if node.args else None
            if text is None:
                opaque.append(f"{node.func.attr} at line {node.lineno}")
            else:
                statements.append(text)
    return ModuleSql(
        module=relative,
        statements=tuple(statements),
        literals=tuple(literals),
        opaque_execute=tuple(opaque),
    )


def leading_verb(sql: str) -> str:
    """The first token of ``sql``, upper-cased; ``""`` for an empty statement."""
    stripped = sql.strip()
    if not stripped:
        return ""
    return stripped.split(maxsplit=1)[0].upper()


def _reordered(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """The same mapping with its insertion order reversed."""
    return {key: mapping[key] for key in sorted(mapping, reverse=True)}


def _rebuild(decision: CanonicalDecision) -> CanonicalDecision:
    """The same logical decision, constructed again with every mapping order reversed."""
    return replace(
        decision,
        selected_action=_reordered(decision.selected_action),
        pareto_weights=_reordered(decision.pareto_weights),
        proposals=[_reordered(proposal) for proposal in decision.proposals],
        audit_trace=list(decision.audit_trace),
    )


# ---------------------------------------------------------------------------
# Clause 1 - the canonical row round-trips, losslessly and byte-stably
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 21: Canonical rows round-trip and audit
# history is append-only
@given(decision=canonical_decisions())
def test_canonical_rows_round_trip_losslessly_and_byte_stably(
    decision: CanonicalDecision,
) -> None:
    """I-4: the frozen field set, a lossless round trip, and order-independent bytes.

    ``make_canonical_row`` is called, never re-implemented: an expected row built here by
    hand would become a second source of truth for a byte-pinned contract, which is
    exactly the failure E-S9-02 records.
    """
    row = make_canonical_row(
        decision_id=decision.decision_id,
        tier=decision.tier,
        selected_action=dict(decision.selected_action),
        pareto_weights=dict(decision.pareto_weights),
        confidence=decision.confidence,
        proposals=[dict(proposal) for proposal in decision.proposals],
        audit_trace=list(decision.audit_trace),
    )

    # The field set is exactly the frozen seven - no more (a new key breaks every
    # production chain) and no fewer (a dropped key does the same).
    assert tuple(sorted(row)) == _CANONICAL_FIELDS
    assert row == decision.canonical()

    # No ``default=`` hook. A canonical row carrying a UUID or a datetime object would
    # raise here rather than be silently stringified into different bytes.
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
    assert ", " not in payload
    assert '": ' not in payload
    assert "\n" not in payload

    # Round trip: parse the bytes back and get an equivalent row.
    parsed: Any = json.loads(payload)
    assert isinstance(parsed, dict)
    assert parsed == row
    assert tuple(sorted(parsed)) == _CANONICAL_FIELDS
    # Idempotent: re-serialising the parsed value reproduces the same bytes, so a stored
    # payload read and rewritten is the same payload.
    assert json.dumps(parsed, sort_keys=True, separators=(",", ":")) == payload

    # The digest follows the bytes. ``hash_payload_for_row`` is the production primitive,
    # imported and called - the chain this test reasons about is the real one.
    assert hash_payload_for_row(None, parsed) == hash_payload_for_row(None, row)

    # Byte stability across two *constructions*, with every mapping's insertion order
    # reversed in the second. A serialiser leaking dict order would give a logically
    # identical row a different digest - a chain break with no tamper behind it.
    rebuilt = _rebuild(decision).canonical()
    assert rebuilt == row
    assert json.dumps(rebuilt, sort_keys=True, separators=(",", ":")) == payload
    assert hash_payload_for_row(None, rebuilt) == hash_payload_for_row(None, row)


# Feature: purpose-achievement-audit, Property 21: Canonical rows round-trip and audit
# history is append-only
@given(row=provenance_rows())
def test_provenance_rows_round_trip_and_add_facts_without_shadowing_hashed_ones(
    row: DecisionDataProvenance,
) -> None:
    """CF-1: the new stream round-trips, and it *adds* to the audit record.

    The key-set overlap clause is the one that makes CF-1's resolution checkable. If
    provenance carried a key the hashed row also carries, a reader joining the two would
    face two values for one field and the byte-pinned one would not obviously win. The
    only shared key is the join key.
    """
    payload = row.to_canonical_json()

    assert DecisionDataProvenance.from_canonical_json(payload) == row
    assert payload == row.to_canonical_json()
    assert payload == json.dumps(row.to_canonical_dict(), sort_keys=True, separators=(",", ":"))
    assert ", " not in payload
    assert '": ' not in payload

    parsed: Any = json.loads(payload)
    assert isinstance(parsed, dict)
    assert tuple(sorted(parsed)) == PROVENANCE_FIELDS
    assert DecisionDataProvenance.from_canonical_dict(parsed).to_canonical_json() == payload

    # Storage bookkeeping Postgres assigns is not part of the recorded fact, so it cannot
    # go missing in a round trip that never carried it.
    assert "id" not in parsed
    assert "created_at" not in parsed

    # The provenance stream adds facts; ``decision_id`` is the join and the only overlap.
    overlap = set(PROVENANCE_FIELDS) & set(_CANONICAL_FIELDS)
    assert overlap == {"decision_id"}
    assert parsed["decision_id"] == str(row.decision_id)


# ---------------------------------------------------------------------------
# Clause 2 - the append-only grant surface, read out of both migration files
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 21: Canonical rows round-trip and audit
# history is append-only
@given(table=st.sampled_from(_LEDGER_TABLES))
def test_every_ledger_table_exposes_only_select_and_insert(table: str) -> None:
    """I-4: for any append-only fact stream, the application role holds no mutating verb.

    Parsed from every migration in both DDL directories, including the schema-wide floor
    (``init_audit.sql``'s ``ON ALL TABLES`` and ``ALTER DEFAULT PRIVILEGES``) - a
    schema-wide ``UPDATE`` would otherwise be invisible to a per-table read.

    Postgres is not consulted. That the server really refuses the revoked verb, and that
    the migration's own ``I-4 VIOLATION`` self-test fires, is asserted in
    ``integration.yml``; this is the static half and it is not claimed to be the other one.
    """
    verbs = permitted_verbs(table)

    assert verbs, f"no grant found for {table}: the parser saw nothing to check"
    assert mutation_verbs(verbs) == frozenset(), (
        f"{table} is an append-only ledger but {_APP_ROLE} holds "
        f"{sorted(mutation_verbs(verbs))} on it (I-4)"
    )
    assert verbs <= _APPEND_ONLY_VERBS
    # A ledger that cannot be written to or cannot be read is not the contract either.
    assert verbs == _APPEND_ONLY_VERBS

    # Non-vacuity: the same parser, over the same files, DOES see the queue's UPDATE.
    # Without this, silence about the ledgers above would be worth nothing. The queue is
    # a workflow primitive, not a ledger, and the audit records its UPDATE as correct.
    queue = permitted_verbs(_QUEUE_TABLE)
    assert "UPDATE" in queue
    assert "DELETE" not in queue
    assert _QUEUE_TABLE not in _LEDGER_TABLES


# Feature: purpose-achievement-audit, Property 21: Canonical rows round-trip and audit
# history is append-only
@given(table=st.sampled_from(_LEDGER_TABLES))
def test_the_canonical_migration_and_its_docker_mirror_declare_the_same_surface(
    table: str,
) -> None:
    """E-S9-14: whatever both DDL sets declare about a table, they declare identically.

    Byte identity of the provenance pair is task 7.8's unit test. This is the weaker,
    more useful statement: the *derived* surface agrees, so a reformat that preserves
    meaning passes and a tidy-looking edit that widens a grant fails. Migrated databases
    and container-initialised ones must not end up with different privileges - only one of
    them would be the one anybody tested.
    """
    canonical = directory_surface(_CANONICAL_DIR)
    mirror = directory_surface(_MIRROR_DIR)

    shared = set(canonical) & set(mirror)
    assert shared, "the two DDL sets declare no table in common - one of them is unread"
    for name in sorted(shared):
        assert canonical[name] == mirror[name], (
            f"{name}: canonical migrations grant {sorted(canonical[name])} but the "
            f"Docker-init mirror grants {sorted(mirror[name])}"
        )

    # The provenance table specifically is declared in both, and identically.
    provenance = data_provenance.TABLE
    assert provenance in shared
    assert canonical[provenance] == mirror[provenance] == _APPEND_ONLY_VERBS

    # Every table this property quantifies over is declared somewhere, so no ledger is
    # silently absent from the surface being checked.
    assert table in set(canonical) | set(mirror)


# Feature: purpose-achievement-audit, Property 21: Canonical rows round-trip and audit
# history is append-only
@given(surfaces=declared_surfaces())
def test_the_append_only_predicate_fires_on_any_mutating_grant(
    surfaces: tuple[frozenset[str], frozenset[str]],
) -> None:
    """The detector can detect: over synthetic DDL, the predicate is exact, not lenient.

    Every gate in this repository is owed a demonstration that it fails when its property
    is violated (RC-3, design AD-4). This is that demonstration for the grant parser: DDL
    is synthesised for each drawn grant/revoke pair, parsed by the same functions the real
    files go through, and the verdict is required to be *exactly* "a mutating verb
    survives the revoke".
    """
    granted, revoked = surfaces
    table = "synthetic_ledger"
    ddl_lines = [f"CREATE TABLE IF NOT EXISTS {table} (id UUID PRIMARY KEY);"]
    if granted:
        ddl_lines.append(f"GRANT {', '.join(sorted(granted))} ON {table} TO {_APP_ROLE};")
    if revoked:
        ddl_lines.append(f"REVOKE {', '.join(sorted(revoked))} ON {table} FROM {_APP_ROLE};")
    # A statement addressed to a different role must not move this role's surface.
    ddl_lines.append(f"GRANT UPDATE, DELETE ON {table} TO some_other_role;")
    ddl = "\n".join(ddl_lines)

    parsed = table_grants(ddl)
    expected = granted - revoked
    if expected:
        assert parsed[table] == expected
    else:
        assert parsed.get(table, frozenset()) == frozenset()

    survived = mutation_verbs(expected)
    assert bool(mutation_verbs(parsed.get(table, frozenset()))) == bool(survived)
    assert (parsed.get(table, frozenset()) <= _APPEND_ONLY_VERBS) == (not survived)

    # And the store refuses a surviving mutating verb rather than applying it, so a
    # widened grant becomes a failure instead of a silently mutable history.
    store = AppendOnlyTable(name=table, permitted=parsed.get(table, frozenset()))
    for verb in sorted(survived):
        with pytest.raises(AppendOnlyViolation):
            store.apply(verb, "{}")


# ---------------------------------------------------------------------------
# Clause 3 - the history is append-only
# ---------------------------------------------------------------------------


def _apply_history(
    ops: Sequence[LedgerOp],
) -> tuple[dict[str, AppendOnlyTable], tuple[tuple[str, tuple[str, ...]], ...]]:
    """Apply ``ops`` in order, returning the final tables and a snapshot after each step."""
    tables = {
        name: AppendOnlyTable(name=name, permitted=permitted_verbs(name))
        for name in ("audit_consensus", "decision_data_provenance")
    }
    trace: list[tuple[str, tuple[str, ...]]] = []
    for op in ops:
        before = {name: table.rows for name, table in tables.items()}
        tables[op.table] = tables[op.table].apply(op.verb, op.payload)

        for name, table in tables.items():
            previous = before[name]
            # Non-decreasing row count.
            assert len(table.rows) >= len(previous)
            # No previously written row changes bytes: the earlier rows are a prefix of
            # the later ones, byte for byte.
            assert table.rows[: len(previous)] == previous
            # An operation against one stream never touches the other. This is the
            # clause CF-1 turns on: recording provenance adds a row to the provenance
            # table and leaves every canonical audit row exactly as written.
            if name != op.table:
                assert table.rows == previous
        trace.append((op.table, tables[op.table].rows))
    return tables, tuple(trace)


# Feature: purpose-achievement-audit, Property 21: Canonical rows round-trip and audit
# history is append-only
@given(ops=ledger_histories())
def test_any_expressible_history_is_append_only_and_leaves_written_rows_untouched(
    ops: tuple[LedgerOp, ...],
) -> None:
    """I-4 / R4.4: rows only accumulate, and provenance never disturbs the hashed row.

    The operations are drawn from the *parsed* grant surface, so this is a statement about
    what the application role can actually do rather than about what a literal list said
    it could.
    """
    tables, trace = _apply_history(ops)
    assert len(trace) == len(ops)

    for name, table in tables.items():
        inserted = [op.payload for op in ops if op.table == name and op.verb == "INSERT"]
        # Every insert landed, in order, and nothing else did.
        assert list(table.rows) == inserted
        assert len(table.rows) == sum(
            1 for op in ops if op.table == name and op.verb == "INSERT"
        )

    # Each audit row still hashes to what it hashed to when it was written, recomputed
    # from the stored bytes with the production primitive.
    for payload in tables["audit_consensus"].rows:
        stored: Any = json.loads(payload)
        assert isinstance(stored, dict)
        assert tuple(sorted(stored)) == _CANONICAL_FIELDS
        assert hash_payload_for_row(None, stored) == hash_payload_for_row(
            None, json.loads(json.dumps(stored, sort_keys=True, separators=(",", ":")))
        )

    # Each provenance row still parses back into the record that was filed.
    for payload in tables["decision_data_provenance"].rows:
        record = DecisionDataProvenance.from_canonical_json(payload)
        assert record.to_canonical_json() == payload
        assert record.source_class in SOURCE_CLASSES

    # The guard is not dead code: whatever the grant surface says, the store refuses to
    # change or remove a written row, and refusing is how a widened grant is reported.
    ledger = tables["decision_data_provenance"]
    for verb in ("UPDATE", "DELETE", "TRUNCATE"):
        with pytest.raises(AppendOnlyViolation):
            ledger.apply(verb, "{}")
    # A read changes nothing at all.
    assert ledger.apply("SELECT", "").rows == ledger.rows


# ---------------------------------------------------------------------------
# Clause 4 - no code path in the provenance module mutates an audit table
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 21: Canonical rows round-trip and audit
# history is append-only
@given(module=st.sampled_from(_PROVENANCE_MODULES))
def test_the_provenance_write_path_issues_no_update_or_delete(module: str) -> None:
    """I-4: the writer can only append, and its SQL is fully visible to this check.

    Three clauses, in the order they have to hold:

    1. No statement is assembled out of sight - an ``execute`` whose SQL this scan cannot
       resolve is reported, because an unreadable statement makes the other two clauses
       claims about nothing (I-7).
    2. Every statement's leading verb is one the parsed DDL actually grants on the table
       it targets, so the code and the grant surface are checked against each other rather
       than each against a comment.
    3. No executable string literal anywhere in the module contains a mutating verb.
       Docstrings are excluded and only docstrings are: a bare string expression is
       documentation, and every other string is something the module can hand to a
       database. This is what catches an ``ON CONFLICT ... DO UPDATE`` or a statement
       built for a call site this scan does not model.
    """
    scanned = scan_module(module)

    assert scanned.opaque_execute == (), (
        f"{module} builds SQL this check cannot read: {list(scanned.opaque_execute)}"
    )

    provenance = data_provenance.TABLE
    granted = permitted_verbs(provenance)
    for sql in scanned.statements:
        verb = leading_verb(sql)
        assert verb in granted, f"{module} issues {verb} but {provenance} grants {sorted(granted)}"
        assert not _MUTATION_WORD_RE.search(sql), f"{module} issues a mutating statement: {sql!r}"
        # The statement addresses the audited table, either directly or through the
        # module's single table constant.
        assert provenance in sql or "{}" in sql

    for literal in scanned.literals:
        match = _MUTATION_WORD_RE.search(literal)
        assert match is None, (
            f"{module} carries an executable string containing {match.group(0)!r}: {literal!r}"
        )

    # Non-vacuity across the write path: the scan really does find the append, so an
    # empty statement set could never be mistaken for a clean bill of health.
    writer = scan_module("orchestrator/audit/data_provenance.py")
    verbs = {leading_verb(sql) for sql in writer.statements}
    assert "INSERT" in verbs
    assert verbs <= granted
    assert data_provenance.TABLE in _LEDGER_TABLES
