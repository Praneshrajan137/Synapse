"""SQLite compatibility shim for tests that exercise audit models.

Production models declare PostgreSQL ``JSONB`` columns. The
test-only ``sqlite+aiosqlite`` engine doesn't speak JSONB natively, so
we register a ``compiles`` rule that maps ``JSONB`` → ``JSON`` for the
SQLite dialect. This keeps production schema untouched while letting
the outbox / replay tests run hermetically.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_jsonb_to_json_sqlite(
    element,  # noqa: ANN001
    compiler,  # noqa: ANN001
    **kw,  # noqa: ANN003  # type: ignore[no-untyped-def]
) -> str:
    return "JSON"
