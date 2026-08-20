"""Write where a decision's input came from (audit R4.4, design AD-10 / conflict CF-1).

Requirement 4.4: a decision convened from state whose ``is_synthetic`` is ``false`` must
carry a data-provenance value **distinct** from a simulation-sourced decision's. The hashed
canonical audit row cannot carry it - ``make_canonical_row`` is byte-pinned and adding a
field to it is a chain-rewrite migration, not a field bump (I-4, E-S9-02). So provenance is
its own append-only stream, ``decision_data_provenance``, keyed by ``decision_id``, exactly
as ``decision_outcomes`` was for realized outcomes. This module is that stream's writer.

Two halves, kept apart on purpose:

* :func:`build_provenance` is **pure** - a perceived-state mapping in, a
  :class:`~orchestrator.audit.models.DecisionDataProvenance` (or ``None``) out. No clock, no
  database, no environment. That is the seam the provenance property tests use, and it is
  where every honesty decision lives.
* :func:`record_provenance` is the thin Postgres adapter. It degrades the way
  ``data_fabric/jobs/outcome_score.py`` does: a missing DSN, an absent driver, or an
  unreachable database logs and returns ``False``. A decision is never blocked because its
  provenance could not be filed, and an unwritten row is never reported as written.

What this module refuses to do (I-7)
------------------------------------
It never invents a class. A state that declares no ``source_class`` yields ``None`` and a
warning, not a defaulted ``SEEDED`` row - because a fabricated ``SEEDED`` would look exactly
like an honest one and would make the ``EXTERNAL`` count meaningless, and a fabricated
``EXTERNAL`` would be the over-claim the whole audit is about. It also stores the
``is_synthetic`` flag the state reported rather than silently normalising it, so a source
whose flag disagrees with its declared class leaves a visible trace (it logs the
disagreement and keeps both).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import structlog

from orchestrator.audit.models import SOURCE_CLASSES, DecisionDataProvenance

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

    from orchestrator.audit.models import SourceClass

logger = structlog.get_logger(__name__)

TABLE: str = "decision_data_provenance"

#: Keys read out of the perceived-state payload (``WorldState.model_dump(mode="json")`` as
#: it arrives over the twin's A2A ``world_state`` method).
STATE_SOURCE_CLASS = "source_class"
STATE_IS_SYNTHETIC = "is_synthetic"
STATE_OBSERVED_AT = "as_of"
STATE_FEED_REVISION = "feed_revision"


def _dsn() -> str | None:
    return os.environ.get("POSTGRES_DSN")


def _coerce_decision_id(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _coerce_observed_at(value: object) -> datetime | None:
    """Parse an ISO-8601 instant from the state payload; ``None`` if it is not one."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def build_provenance(
    *,
    decision_id: object,
    state: Mapping[str, Any],
    observed_at: datetime | None = None,
) -> DecisionDataProvenance | None:
    """Build the provenance row for one decision, or ``None`` when it cannot be known.

    ``state`` is the perceived ``WorldState`` payload the decision was convened from.
    ``observed_at`` is the fallback instant used only when the payload carries no usable
    ``as_of``; passing it keeps this function pure (a caller supplies the clock).

    Returns ``None`` - and logs why - when the decision id is unusable or the state declares
    no recognised ``source_class``. ``None`` means *no row*, which is the honest outcome: the
    absence of a provenance row is readable evidence that provenance was unknown, whereas a
    defaulted row would be indistinguishable from a measured one.
    """
    identifier = _coerce_decision_id(decision_id)
    if identifier is None:
        logger.warning("provenance_decision_id_unusable", decision_id=str(decision_id))
        return None

    raw_class = state.get(STATE_SOURCE_CLASS)
    # A StrEnum member stringifies to its value, so both the in-process WorldState and the
    # JSON-dumped A2A payload land on the same three literals.
    source_class = str(raw_class) if raw_class is not None else None
    if source_class not in SOURCE_CLASSES:
        logger.warning(
            "provenance_source_class_undeclared",
            decision_id=str(identifier),
            declared=source_class,
            known=list(SOURCE_CLASSES),
        )
        return None

    derived_synthetic = source_class == "SEEDED"
    reported = state.get(STATE_IS_SYNTHETIC)
    if isinstance(reported, bool):
        is_synthetic = reported
        if reported != derived_synthetic:
            # Recorded as reported, not corrected: a disagreement between the flag and the
            # declared class is exactly the kind of drift an audit trail should preserve.
            logger.error(
                "provenance_flag_contradicts_source_class",
                decision_id=str(identifier),
                source_class=source_class,
                reported_is_synthetic=reported,
                derived_is_synthetic=derived_synthetic,
            )
    else:
        is_synthetic = derived_synthetic

    revision = state.get(STATE_FEED_REVISION)
    feed_revision = revision if isinstance(revision, str) and revision else None

    when = _coerce_observed_at(state.get(STATE_OBSERVED_AT)) or observed_at or datetime.now(UTC)
    return DecisionDataProvenance(
        decision_id=identifier,
        source_class=cast("SourceClass", source_class),
        is_synthetic=is_synthetic,
        feed_revision=feed_revision,
        observed_at=when,
    )


def record_provenance(row: DecisionDataProvenance, dsn: str | None = None) -> bool:
    """INSERT one append-only provenance row. ``True`` only if it actually landed.

    Never raises: the caller is a decision path, and a filing failure must not take a
    decision with it (I-7). It also never retries into a duplicate - the table is
    append-only and a correction appends, so a second identical row is harmless but a
    silent success would not be.
    """
    dsn = dsn or _dsn()
    if not dsn:
        logger.warning("provenance_no_dsn", decision_id=str(row.decision_id))
        return False
    try:
        import psycopg2
    except ImportError:
        logger.warning("provenance_psycopg2_missing", decision_id=str(row.decision_id))
        return False
    try:
        conn = psycopg2.connect(dsn)
    except Exception as exc:  # noqa: BLE001 - an unreachable DB degrades, never crashes
        logger.warning(
            "provenance_connect_failed", decision_id=str(row.decision_id), error=str(exc)
        )
        return False
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {TABLE}
                    (decision_id, source_class, is_synthetic, feed_revision, observed_at)
                VALUES (%s, %s, %s, %s, %s)
                """,  # noqa: S608 - TABLE is a module constant, never caller input
                (
                    str(row.decision_id),
                    row.source_class,
                    row.is_synthetic,
                    row.feed_revision,
                    row.observed_at,
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "provenance_insert_failed", decision_id=str(row.decision_id), error=str(exc)
        )
        return False
    finally:
        conn.close()
    logger.info(
        "provenance_recorded",
        decision_id=str(row.decision_id),
        source_class=row.source_class,
        is_synthetic=row.is_synthetic,
    )
    return True


def count_external_decisions(dsn: str | None = None) -> int | None:
    """Rows carrying ``source_class = 'EXTERNAL'``, or ``None`` if the count is unavailable.

    This is the evidence ``scripts/audit/feed_provenance.py --external-decisions`` consumes.
    ``None`` (not ``0``) when the database cannot be read, so "unmeasured" stays distinct
    from "measured zero" - the caller must not turn an unreadable database into a claim in
    either direction.
    """
    dsn = dsn or _dsn()
    if not dsn:
        return None
    try:
        import psycopg2
    except ImportError:
        return None
    try:
        conn = psycopg2.connect(dsn)
    except Exception as exc:  # noqa: BLE001
        logger.warning("provenance_count_connect_failed", error=str(exc))
        return None
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {TABLE} WHERE source_class = %s",  # noqa: S608
                ("EXTERNAL",),
            )
            fetched = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        logger.warning("provenance_count_failed", error=str(exc))
        return None
    finally:
        conn.close()
    if not fetched:
        return None
    return int(fetched[0])
