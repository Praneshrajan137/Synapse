"""R6.2 / R6.10 - the chain verifier against a real Postgres, not a model of one.

Feature: purpose-achievement-audit, task 7.10 (design E4, "Chain tamper detection
against Postgres -> ``integration.yml`` (has Postgres)").

Two clauses, both of which need a database and therefore live here rather than beside
Property 18:

* **R6.2** - "WHEN a row is deleted from the middle of a scratch Audit_Chain, THE chain
  verifier SHALL compare each row's stored ``prev_hash`` against the ``current_hash`` of
  the row that precedes that row in the ordered walk, SHALL exit non-zero, and SHALL
  name the successor of the deleted row as the break." Property 18
  (``packages/tests/test_chain_walk_perturbation_property.py``) already quantifies this
  over generated in-memory chains through the pure walker. What it cannot establish is
  that the *adapter* delivers a real deletion to that walker: that the ``ORDER BY
  created_at, id`` snapshot, the ``UUID``-to-ordinal mapping, ``canonical_row_for``'s
  field set, and the process exit code compose into a non-zero exit naming a row an
  operator can query. A ``DELETE`` is also the one perturbation that cannot be
  simulated in memory without deciding, in the test, what the database would have
  returned - which is the self-referential-oracle pattern the audit reports in
  Requirement 12. So this file deletes a row with SQL and reads the verdict from the
  CLI's own exit code.

* **R6.10** - "WHILE rows are being appended during a verification run, THE chain
  verifier SHALL walk the row set fixed by a snapshot taken at the start of the run and
  SHALL report that snapshot's upper boundary."

Why this is not the same test twice
-----------------------------------

Property 18 owns *detection over row sequences*. This file owns *the seam between
Postgres and that walker*, and it deliberately asserts nothing about tamper classes the
pure property already covers: there is one deletion case and one append case here, not
six operators.

The append case, and why it is deterministic
--------------------------------------------

A test that raced an ``INSERT`` against a running verification would be flaky and would
prove whichever side won. Instead the append case is ordered, and the appended row is
one that *would break the walk*:

1. read the ordered snapshot (this is "the start of the run"),
2. append a row whose ``prev_hash`` points nowhere - committed, from its own
   transaction,
3. walk the snapshot read in step 1: still ``verified``, and its reported upper bound is
   still the pre-append head. The appended row is provably outside the snapshot,
   because had it been inside, the walk would have broken.
4. run the whole CLI again: now ``broken``, exit ``1``.

Step 4 is what stops step 3 from being vacuous - it proves the row really was committed
and really is visible to a later run. Step 3 alone would also pass against a verifier
that silently dropped the newest row.

The transaction-level guarantee is asserted separately
(:func:`test_repeatable_read_snapshot_does_not_grow_under_a_concurrent_append`), because
today's read is a single ``SELECT`` - atomic whatever the isolation level - while the
CLI's docstring already anticipates task 7.6's anchor read joining the same
transaction. At that point ``REPEATABLE READ`` stops being belt-and-braces and starts
being the guarantee, so the level is pinned now, against the CLI's own exported
constant rather than a literal.

I-4, and why a ``DELETE`` appears in a test at all
--------------------------------------------------

``make_canonical_row`` and ``hash_payload_for_row`` are **imported** from
``orchestrator.audit.hash_chain`` and called, never reimplemented and never modified:
they are byte-pinned by a literal-digest test
(``packages/tests/test_audit_chain.py``). Every seeded row is hashed by the production
primitives, so a chain this test calls "correctly linked" is one the writer would
actually have produced.

The append-only guarantee is untouched. Every statement here runs against a
**throwaway database** created and dropped by :func:`scratch_chain`, holding one table
and no production data; the production ledger is never opened. ``synapse_app`` still
has UPDATE/DELETE revoked on ``audit_consensus``
(``infrastructure/postgres/02_sprint4_consensus.sql:47,56``) and nothing here changes
that - the ``DELETE`` runs as the maintenance role, which is exactly the threat model
R6.2 describes: an actor who *can* delete a row, and a verifier that must notice.

Where this runs, and what it does when it does not
--------------------------------------------------

Following the convention of the sibling integration proof
(``tests/integration/test_published_entry_serving_resolution.py``): ``@pytest.mark.
integration`` plus a ``skipif`` on the one environment variable the proving job sets,
and a reason that says the SKIP is an unproven claim rather than a passing one (I-7).

**No workflow sets ``SYNAPSE_AUDIT_CHAIN_IT_DSN`` today, so this file SKIPs
everywhere - including in ``integration.yml``.** That is reported, not hidden: until
the step below exists, R6.2 has no executed proof against a database and this module's
``s`` in a green run is the honest record of that. The step ``integration.yml::
integration-e2e`` needs, after "Start base compose" and with no ``continue-on-error``
and no ``|| true``::

    - name: Audit-chain tamper detection against Postgres (R6.2, R6.10)
      env:
        SYNAPSE_AUDIT_CHAIN_IT_DSN: postgresql+asyncpg://synapse:synapse_audit_2026@localhost:5432/synapse_audit
      run: |
        PYTHONPATH=. pytest tests/integration/test_audit_chain_tamper_postgres.py -q --tb=short

The DSN's role must be able to ``CREATE DATABASE``; the compose superuser
(``POSTGRES_USER=synapse``, ``docker/docker-compose.yml:161``) can. A deliberate
variable rather than a reachability probe: a probe that skips when Postgres is
unreachable would report a green run for a database that was never there, which is the
silent-SKIP-as-pass failure this whole spec exists to remove.

Prerequisites *inside* the proving job are asserted, never skipped: with the variable
set, a missing ``asyncpg`` or an unreachable server is a failure, because in that job
both must be present.

``encoding='utf-8'`` on every read (E-S13-07, inside ``load_chain_bounds``);
ASCII-only output.
"""

from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final, cast

import pytest

pytest.importorskip("sqlalchemy")

import pytest_asyncio  # noqa: E402  - imported after the sqlalchemy availability gate
from sqlalchemy import Table, delete, func, select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from orchestrator.audit.chain_walk import (  # noqa: E402
    BreakKind,
    load_chain_bounds,
    walk,
)
from orchestrator.audit.cli import (  # noqa: E402
    SNAPSHOT_ISOLATION_LEVEL,
    read_snapshot,
    verify_and_report,
)
from orchestrator.audit.hash_chain import (  # noqa: E402
    hash_payload_for_row,
    make_canonical_row,
)
from orchestrator.audit.models import AuditConsensusRow

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

__all__ = ["SCRATCH_DB_PREFIX", "ScratchChain"]

#: ``DeclarativeBase.__table__`` is typed ``FromClause``, which carries no ``create``.
#: The cast is the standard SQLAlchemy 2.0 narrowing; only ``audit_consensus`` is
#: created, because ``Base.metadata.create_all`` would also attempt ``audit_outbox``
#: whose ENUM is declared ``create_type=False`` and does not exist in a scratch database.
_AUDIT_TABLE: Final[Table] = cast("Table", AuditConsensusRow.__table__)

#: The one variable the proving job sets. Absent -> SKIP, and a SKIP is not a PASS.
_DSN_ENV: Final[str] = "SYNAPSE_AUDIT_CHAIN_IT_DSN"
_DSN: Final[str] = os.environ.get(_DSN_ENV, "")

#: Every scratch database this module creates carries this prefix, and
#: :func:`_drop_database` refuses to drop anything that does not. A ``DROP DATABASE``
#: built from an environment variable needs a name guard, not just a careful caller.
SCRATCH_DB_PREFIX: Final[str] = "synapse_chain_scratch_"

#: Rows seeded per chain. Four is the smallest length where the re-linked-tail case
#: this file's sibling property covers is distinguishable from a truncation, and it
#: leaves a genuine "middle" for R6.2's deletion (positions 2 and 3).
_CHAIN_LENGTH: Final[int] = 4

#: 0-based index of the row R6.2 deletes: strictly inside the chain, so the break is a
#: linkage fault at its successor rather than a truncation at the head.
_DELETED_INDEX: Final[int] = 1

_EXIT_VERIFIED: Final[int] = 0
_EXIT_BROKEN: Final[int] = 1

#: A 64-char digest that is not any row's hash, so a row carrying it as ``prev_hash``
#: links to nothing in the chain.
_ORPHAN_HASH: Final[str] = "f" * 64

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _DSN,
        reason=(
            f"R6.2/R6.10 need a real Postgres. Set {_DSN_ENV} to a SQLAlchemy asyncpg "
            "DSN whose role can CREATE DATABASE (integration.yml::integration-e2e "
            "already boots the compose postgres). SKIPPED here: an unproven claim, "
            "not a passing one (I-7)."
        ),
    ),
]


class ScratchChain:
    """A seeded chain in a throwaway database, plus the ids of the rows seeded.

    Deliberately a small mutable holder rather than a frozen model: the fixture hands
    it to a test that then changes the database underneath it, and pretending the
    handle is immutable evidence would be misleading. The *evidence* in this file is
    the verifier's exit code, not this object.
    """

    def __init__(
        self,
        *,
        dsn: str,
        engine: AsyncEngine,
        row_ids: tuple[uuid.UUID, ...],
        hashes: tuple[str, ...],
        created_at: tuple[datetime, ...],
        boundary: datetime,
    ) -> None:
        self.dsn = dsn
        self.engine = engine
        self.row_ids = row_ids
        self.hashes = hashes
        self.created_at = created_at
        self.boundary = boundary

    @property
    def head_hash(self) -> str:
        """The newest ``current_hash`` - what an anchor would commit to (R6.5)."""
        return self.hashes[-1]


def _async_url(raw: str) -> Any:  # noqa: ANN401 - sqlalchemy URL is not generic
    """Normalise a DSN to the asyncpg driver, leaving credentials untouched."""
    url = make_url(raw)
    if url.drivername in {"postgresql", "postgres"}:
        url = url.set(drivername="postgresql+asyncpg")
    return url


async def _create_database(admin_url: Any, name: str) -> None:  # noqa: ANN401
    """``CREATE DATABASE name`` over an AUTOCOMMIT connection.

    ``CREATE DATABASE`` cannot run inside a transaction block, which is the whole
    reason for the explicit AUTOCOMMIT engine here.
    """
    engine = create_async_engine(str(admin_url), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()


async def _drop_database(admin_url: Any, name: str) -> None:  # noqa: ANN401
    """``DROP DATABASE ... WITH (FORCE)``, guarded by the scratch-name prefix.

    ``WITH (FORCE)`` (PG13+, and the compose image is ``postgres:16-alpine``)
    terminates leftover backends so a connection the verifier failed to dispose
    cannot leave a database behind for the next run to trip over.
    """
    if not name.startswith(SCRATCH_DB_PREFIX):
        msg = f"refusing to drop {name!r}: not a {SCRATCH_DB_PREFIX}* scratch database"
        raise AssertionError(msg)
    engine = create_async_engine(str(admin_url), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()


def _seed_row(
    *,
    index: int,
    prev_hash: str | None,
    boundary: datetime,
) -> tuple[AuditConsensusRow, str]:
    """Build one correctly linked row and its ``current_hash``.

    The canonical dict comes from the untouched ``make_canonical_row`` with exactly the
    field set ``orchestrator/audit/cli.py::canonical_row_for`` reads back, so the
    verifier recomputes the same bytes the writer hashed. Anything else here would be
    a second, drifting definition of the chain (E-S9-02).

    ``created_at`` sits strictly after the committed migration boundary so these are
    post-boundary rows under the verifier's default ``--since`` (CF-6), and ascending
    so ``ORDER BY created_at, id`` reproduces the insert order.
    """
    decision_id = uuid.uuid4()
    tier = "tier_3"
    selected_action: dict[str, Any] = {
        "action": "restock",
        "sku_id": f"SKU{index:03d}",
        "quantity": 10 * (index + 1),
    }
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
    current_hash = hash_payload_for_row(prev_hash, canonical)
    created_at = boundary + timedelta(minutes=index + 1)
    row = AuditConsensusRow(
        id=uuid.uuid4(),
        decision_id=decision_id,
        timestamp=created_at,
        tier=tier,
        phase_reached=4,
        proposals=proposals,
        selected_action=selected_action,
        pareto_weights=pareto_weights,
        confidence=confidence,
        debate_rounds=0,
        escalated=False,
        human_override=None,
        execution_confirmations=[],
        context_messages=[],
        audit_trace=audit_trace,
        pareto_front=None,
        outcome=None,
        created_at=created_at,
        prev_hash=prev_hash,
        current_hash=current_hash,
    )
    return row, current_hash


@pytest_asyncio.fixture
async def scratch_chain() -> AsyncIterator[ScratchChain]:
    """Create a throwaway database, seed a correctly linked chain, drop it after.

    An absent ``asyncpg`` or an unreachable server raises here rather than skipping:
    the variable being set means the job promised a database (I-7).
    """
    if importlib.util.find_spec("asyncpg") is None:
        msg = (
            f"{_DSN_ENV} is set but asyncpg is not installed: the job promised a "
            "database and cannot reach one. Failing rather than skipping (I-7)."
        )
        raise AssertionError(msg)

    boundary = load_chain_bounds().migration_boundary
    url = _async_url(_DSN)
    admin_url = url.set(database="postgres")
    scratch_name = f"{SCRATCH_DB_PREFIX}{uuid.uuid4().hex[:12]}"

    await _create_database(admin_url, scratch_name)
    scratch_url = url.set(database=scratch_name)
    engine = create_async_engine(str(scratch_url))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(_AUDIT_TABLE.create)

        rows: list[AuditConsensusRow] = []
        hashes: list[str] = []
        prev: str | None = None
        for index in range(_CHAIN_LENGTH):
            row, current = _seed_row(index=index, prev_hash=prev, boundary=boundary)
            rows.append(row)
            hashes.append(current)
            prev = current

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session, session.begin():
            session.add_all(rows)

        yield ScratchChain(
            dsn=str(scratch_url),
            engine=engine,
            row_ids=tuple(row.id for row in rows),
            hashes=tuple(hashes),
            created_at=tuple(row.created_at for row in rows),
            boundary=boundary,
        )
    finally:
        await engine.dispose()
        await _drop_database(admin_url, scratch_name)


async def _append_orphan_row(chain: ScratchChain) -> uuid.UUID:
    """Append a committed row whose ``prev_hash`` links to nothing.

    Deliberately chain-breaking. A correctly linked append would verify either way and
    so could not distinguish "outside the snapshot" from "inside it"; this row makes
    the two verdicts differ, which is what turns R6.10 into an assertion.
    """
    row, _ = _seed_row(index=_CHAIN_LENGTH, prev_hash=_ORPHAN_HASH, boundary=chain.boundary)
    factory = async_sessionmaker(chain.engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        session.add(row)
    appended: uuid.UUID = row.id
    return appended


async def _row_count(chain: ScratchChain) -> int:
    factory = async_sessionmaker(chain.engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(select(func.count()).select_from(AuditConsensusRow))
        return int(result.scalar_one())


async def _verify(chain: ScratchChain) -> int:
    """Run the CLI's async core end to end and return the process exit code."""
    bounds = load_chain_bounds()
    return await verify_and_report(
        dsn=chain.dsn,
        since=chain.boundary,
        max_rows=bounds.max_rows,
        timeout=float(bounds.max_wall_clock_seconds),
        recorded_head=None,
        bounds=bounds,
    )


@pytest.mark.asyncio
async def test_seeded_row_deletion_exits_non_zero_and_names_the_successor(
    scratch_chain: ScratchChain,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """R6.2: delete a middle row with SQL; the verifier exits ``1`` naming its successor.

    The clean run first. Without it a verifier that rejects every chain would satisfy
    the interesting half, and the exit code below would carry no information.
    """
    assert await _verify(scratch_chain) == _EXIT_VERIFIED
    clean_output = capsys.readouterr()
    assert "status          : verified" in clean_output.out
    assert f"walked          : {_CHAIN_LENGTH}" in clean_output.out
    assert "breaks          : 0" in clean_output.out

    deleted_id = scratch_chain.row_ids[_DELETED_INDEX]
    successor_id = scratch_chain.row_ids[_DELETED_INDEX + 1]

    factory = async_sessionmaker(scratch_chain.engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await session.execute(delete(AuditConsensusRow).where(AuditConsensusRow.id == deleted_id))
    assert await _row_count(scratch_chain) == _CHAIN_LENGTH - 1

    exit_code = await _verify(scratch_chain)
    captured = capsys.readouterr()
    report = captured.out + captured.err

    # The exit code is the whole point: both call sites (Makefile::deploy-gcp-verify,
    # cd-gcp.yml::deploy-to-vm) propagate it now, and for two sprints this class of
    # tamper produced a zero.
    assert exit_code == _EXIT_BROKEN, report
    assert "status          : broken" in report
    assert f"walked          : {_CHAIN_LENGTH - 1}" in report

    # R6.2's naming clause: the break is a LINKAGE fault reported against the row that
    # FOLLOWED the deleted one, resolved back to a database id an operator can query.
    assert f"TAMPER [{BreakKind.LINKAGE}]" in report
    assert f"db_id={successor_id}" in report
    assert str(deleted_id) not in report

    # And the finding is genuinely the linkage comparison, not a payload artefact: the
    # surviving successor is still self-consistent against its OWN stored prev_hash,
    # which is exactly why scripts/synapse_cli/audit_verify.py's old
    # `row.prev_hash or prev_hash` fallback reported zero breaks here.
    assert f"TAMPER [{BreakKind.PAYLOAD}]" not in report


@pytest.mark.asyncio
async def test_rows_appended_after_the_snapshot_are_outside_the_walk(
    scratch_chain: ScratchChain,
) -> None:
    """R6.10: the walk uses the snapshot fixed at the start of the run.

    Ordered rather than raced, and the appended row is chain-breaking so the two
    verdicts must differ. Step 4 (the fresh run) is what makes step 3 non-vacuous.
    """
    bounds = load_chain_bounds()

    # 1. the start of the run.
    snapshot = await read_snapshot(scratch_chain.dsn, since=scratch_chain.boundary)
    assert len(snapshot.rows) == _CHAIN_LENGTH
    # The snapshot names its own upper boundary, in both senses the adapter reports:
    # the ordinal count the walker uses and the storage row it stopped at.
    assert snapshot.upper_bound_row_id == str(scratch_chain.row_ids[-1])
    assert snapshot.upper_bound_created_at == scratch_chain.created_at[-1]
    assert snapshot.isolation_level == SNAPSHOT_ISOLATION_LEVEL

    # 2. a committed append that would break the chain if it were in scope.
    appended_id = await _append_orphan_row(scratch_chain)
    assert await _row_count(scratch_chain) == _CHAIN_LENGTH + 1

    # 3. the walk of the fixed snapshot is unaffected, and reports that snapshot's
    #    upper bound - not the table's current head.
    report = walk(
        snapshot.rows,
        boundary=scratch_chain.boundary,
        recorded_head=scratch_chain.head_hash,
        max_rows=bounds.max_rows,
    )
    assert report.status == "verified"
    assert report.exit_code == _EXIT_VERIFIED
    assert report.breaks == ()
    assert report.walked == _CHAIN_LENGTH
    assert report.snapshot_upper_bound == _CHAIN_LENGTH
    assert report.head_hash == scratch_chain.head_hash
    assert str(appended_id) not in {str(row_id) for row_id in scratch_chain.row_ids}

    # 4. non-vacuity: a run that takes its own snapshot DOES see the appended row, and
    #    breaks on it. Without this the assertions above would also hold for a
    #    verifier that quietly dropped the newest row.
    fresh = await read_snapshot(scratch_chain.dsn, since=scratch_chain.boundary)
    assert len(fresh.rows) == _CHAIN_LENGTH + 1
    assert fresh.upper_bound_row_id == str(appended_id)
    fresh_report = walk(
        fresh.rows,
        boundary=scratch_chain.boundary,
        recorded_head=scratch_chain.head_hash,
        max_rows=bounds.max_rows,
    )
    assert fresh_report.status == "broken"
    assert fresh_report.exit_code == _EXIT_BROKEN
    first = fresh_report.first_break
    assert first is not None
    assert first.kind is BreakKind.LINKAGE
    assert first.row_id == _CHAIN_LENGTH + 1


@pytest.mark.asyncio
async def test_repeatable_read_snapshot_does_not_grow_under_a_concurrent_append(
    scratch_chain: ScratchChain,
) -> None:
    """R6.10, transaction level: the isolation the adapter declares actually holds.

    Today's read is one ``SELECT``, so it is atomic whatever the level - which means a
    regression from ``REPEATABLE READ`` to ``READ COMMITTED`` would be invisible until
    task 7.6's anchor read joins the same transaction, exactly as
    ``orchestrator/audit/cli.py``'s docstring anticipates. At that point the level is
    the guarantee. So it is pinned here, against the CLI's exported constant rather
    than a literal, by the only observation that distinguishes the two levels: a second
    statement in the same transaction, after another connection committed an insert.
    """
    engine = create_async_engine(scratch_chain.dsn, isolation_level=SNAPSHOT_ISOLATION_LEVEL)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session, session.begin():
            statement = select(AuditConsensusRow).order_by(
                AuditConsensusRow.created_at.asc(), AuditConsensusRow.id.asc()
            )
            before = list((await session.execute(statement)).scalars())
            assert len(before) == _CHAIN_LENGTH

            # A different connection, its own transaction, committed.
            await _append_orphan_row(scratch_chain)

            after = list((await session.execute(statement)).scalars())
            assert len(after) == _CHAIN_LENGTH, (
                "the snapshot grew mid-transaction: the ordered read is not fixed at "
                f"transaction start, so {SNAPSHOT_ISOLATION_LEVEL} is not in effect"
            )
            assert [row.id for row in after] == [row.id for row in before]
    finally:
        await engine.dispose()

    # The append was real and is visible outside the snapshot.
    assert await _row_count(scratch_chain) == _CHAIN_LENGTH + 1
