"""Make the SYNAPSE outbox ORM<->DDL contract mechanically enforceable (Sprint 20).

The transactional outbox is the reliability spine — "never commit a decision
without queuing its publication" (ADR-026). It only holds if the SQL that creates
``audit_outbox`` matches ``orchestrator/audit/models.py::AuditOutboxRow`` exactly.
For a long time it did NOT: the ORM (and ``synapse_common/outbox.py::enqueue``,
which flushes the row INSIDE the decision's own transaction) wrote
``audit_id/partition_key/headers/retries/next_attempt_at/published_at/updated_at``
+ an ``outbox_status`` ENUM, while the mounted DDL created
``message_key/attempts/trace_id/sent_at`` + a TEXT status. On a fresh database the
mismatch failed the enqueue INSERT → rolled back the whole decision-logging
transaction → the orchestrator logged NO decisions, silently. The drift was
invisible because nothing compared the two.

This gate compares, by static parse (no DB, no SQLAlchemy import — stdlib only):

  * the ORM column set + the ``outbox_status`` ENUM values, vs
  * the DDL column set + ``CREATE TYPE outbox_status`` values, in BOTH the
    canonical migration and its docker-init mirror (which must agree, E-S9-14).

Any divergence is a violation. Baseline: 0.

Run::

    python -m scripts.audit.outbox_schema_truth            # human table
    python -m scripts.audit.outbox_schema_truth --json      # machine JSON
    python -m scripts.audit.outbox_schema_truth --check      # exit 1 on any violation

Reported via ``verify_claims.py`` (C55).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ORM_MODEL = "orchestrator/audit/models.py"
ORM_CLASS = "AuditOutboxRow"
ORM_ENUM_CONST = "OUTBOX_STATUSES"
CANONICAL_DDL = "orchestrator/audit/migrations/0002_outbox.sql"
MIRROR_DDL = "infrastructure/postgres/03_sprint7_outbox.sql"
TABLE = "audit_outbox"
ENUM_TYPE = "outbox_status"

# SQL tokens that begin a table-level constraint line (not a column definition).
_CONSTRAINT_KEYWORDS = {"constraint", "primary", "foreign", "unique", "check", "like", "exclude"}


@dataclass
class Violation:
    file: str
    line: int
    kind: str
    detail: str


# --------------------------------------------------------------------------- ORM


def _orm_columns_and_enum(src: str) -> tuple[set[str], tuple[str, ...]]:
    """Extract AuditOutboxRow's column names and the OUTBOX_STATUSES tuple."""
    tree = ast.parse(src)
    columns: set[str] = set()
    enum_values: tuple[str, ...] = ()

    for node in ast.walk(tree):
        # OUTBOX_STATUSES: tuple[str, ...] = ("PENDING", ...)
        if isinstance(node, ast.AnnAssign | ast.Assign):
            target = (
                node.target
                if isinstance(node, ast.AnnAssign)
                else (node.targets[0] if node.targets else None)
            )
            if (
                isinstance(target, ast.Name)
                and target.id == ORM_ENUM_CONST
                and isinstance(node.value, ast.Tuple)
            ):
                enum_values = tuple(
                    el.value
                    for el in node.value.elts
                    if isinstance(el, ast.Constant) and isinstance(el.value, str)
                )

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == ORM_CLASS:
            for stmt in node.body:
                # name: Any = Column(...)
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    val = stmt.value
                    if (
                        isinstance(val, ast.Call)
                        and isinstance(val.func, ast.Name)
                        and val.func.id == "Column"
                    ):
                        columns.add(stmt.target.id)
    return columns, enum_values


# --------------------------------------------------------------------------- DDL


def _ddl_columns(src: str) -> set[str]:
    """Extract column names from the CREATE TABLE ... audit_outbox (...) block."""
    # Locate the CREATE TABLE block (case-insensitive).
    pattern = re.compile(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?" + re.escape(TABLE) + r"\s*\(",
        re.IGNORECASE,
    )
    m = pattern.search(src)
    if not m:
        return set()
    columns: set[str] = set()
    # Walk lines from just after the "(" until the closing ");".
    rest = src[m.end():]
    for raw in rest.splitlines():
        line = raw.strip()
        if line.startswith(")"):
            break
        if not line or line.startswith("--"):
            continue
        # First token is the column name (or a constraint keyword we skip).
        token = re.split(r"[\s(]", line, maxsplit=1)[0].lower()
        if not token or token in _CONSTRAINT_KEYWORDS:
            continue
        if re.fullmatch(r"[a-z_][a-z0-9_]*", token):
            columns.add(token)
    return columns


def _ddl_enum_values(src: str) -> tuple[str, ...]:
    m = re.search(
        r"create\s+type\s+" + re.escape(ENUM_TYPE) + r"\s+as\s+enum\s*\(([^)]*)\)",
        src,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return ()
    return tuple(re.findall(r"'([^']+)'", m.group(1)))


# ----------------------------------------------------------------------- collect


def collect() -> list[Violation]:
    violations: list[Violation] = []

    model_path = ROOT / ORM_MODEL
    if not model_path.is_file():
        return [Violation(ORM_MODEL, 0, "missing_target", "ORM model not found")]
    try:
        orm_cols, orm_enum = _orm_columns_and_enum(model_path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [Violation(ORM_MODEL, 0, "parse_error", f"could not parse ORM: {exc}")]

    if not orm_cols:
        violations.append(
            Violation(ORM_MODEL, 0, "orm_empty", f"no columns parsed from {ORM_CLASS}")
        )
    if set(orm_enum) != {"PENDING", "IN_FLIGHT", "PUBLISHED", "FAILED"}:
        violations.append(
            Violation(ORM_MODEL, 0, "orm_enum_unexpected", f"OUTBOX_STATUSES={orm_enum!r}")
        )

    ddl_col_sets: dict[str, set[str]] = {}
    for rel in (CANONICAL_DDL, MIRROR_DDL):
        path = ROOT / rel
        if not path.is_file():
            violations.append(Violation(rel, 0, "missing_target", "DDL file not found"))
            continue
        src = path.read_text(encoding="utf-8")
        ddl_cols = _ddl_columns(src)
        ddl_col_sets[rel] = ddl_cols
        ddl_enum = _ddl_enum_values(src)

        if not ddl_cols:
            violations.append(
                Violation(rel, 0, "ddl_no_table", f"no CREATE TABLE {TABLE} block found")
            )
            continue

        for missing in sorted(orm_cols - ddl_cols):
            violations.append(
                Violation(
                    rel,
                    0,
                    "missing_in_ddl",
                    f"ORM column '{missing}' has no DDL column - INSERT will fail at runtime",
                )
            )
        for extra in sorted(ddl_cols - orm_cols):
            violations.append(
                Violation(
                    rel,
                    0,
                    "extra_in_ddl",
                    f"DDL column '{extra}' is not on the ORM model (stale schema)",
                )
            )
        if set(ddl_enum) != set(orm_enum):
            violations.append(
                Violation(
                    rel,
                    0,
                    "enum_mismatch",
                    f"DDL outbox_status={ddl_enum!r} != ORM OUTBOX_STATUSES={orm_enum!r}",
                )
            )

    # Canonical and mirror must agree (E-S9-14 lockstep).
    if len(ddl_col_sets) == 2:
        a, b = ddl_col_sets[CANONICAL_DDL], ddl_col_sets[MIRROR_DDL]
        if a != b:
            violations.append(
                Violation(
                    MIRROR_DDL,
                    0,
                    "canonical_mirror_drift",
                    f"mirror columns differ from canonical: {sorted(a ^ b)}",
                )
            )
    return violations


def run(*, as_json: bool = False, check: bool = False) -> int:
    violations = collect()
    total = len(violations)

    if as_json:
        print(
            json.dumps(
                {
                    "summary": {"total_violations": total},
                    "violations": [v.__dict__ for v in violations],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        mark = "[XX]" if violations else "[OK]"
        print(f"{mark} outbox ORM<->DDL contract: {total} violation(s)")
        for v in violations:
            print(f"        {v.file}:{v.line}  {v.kind:<24} {v.detail}")
        print()
        if not violations:
            print("Outbox-schema-truth audit: ORM == canonical DDL == mirror DDL. Clean.")

    if check:
        return 1 if total else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
