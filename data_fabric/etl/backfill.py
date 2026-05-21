"""ETL backfill — reproducible date-range replay.

Re-runs `kafka_to_parquet` on a closed window of Kafka offsets to regenerate
the corresponding Parquet partitions. The output must be byte-identical to
the original ETL run for the same window — that's the determinism guarantee
WS-7.9 leans on.

CLI:

    python -m data_fabric.etl.backfill --topic synapse.demand.forecast \
        --start 2026-04-01 --end 2026-04-02 --output data_fabric/parquet/

Implementation note: this module is the *front* for Kafka offset windowing
and partition-by-date determinism. The actual write path lives in
`kafka_to_parquet.py`; we orchestrate it here with quality gates and lineage.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import structlog

from data_fabric.etl.lineage import LineageEvent, emit, new_run_id

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BackfillWindow:
    topic: str
    start: date
    end: date
    output_root: Path

    def days(self) -> list[date]:
        out: list[date] = []
        d = self.start
        while d < self.end:
            out.append(d)
            d = d + timedelta(days=1)
        return out


def run(window: BackfillWindow) -> None:
    """Execute the backfill for one closed [start, end) window."""
    run_id = new_run_id()
    emit(
        LineageEvent(
            run_id=run_id,
            job_name="etl.backfill",
            event_type="START",
            inputs=[{"namespace": "kafka", "name": window.topic}],
            outputs=[{"namespace": "parquet", "name": str(window.output_root)}],
            facets={"start": window.start.isoformat(), "end": window.end.isoformat()},
        )
    )

    try:
        from data_fabric.etl.kafka_to_parquet import write_partition

        for d in window.days():
            partition = window.output_root / window.topic / d.strftime("date=%Y-%m-%d")
            partition.mkdir(parents=True, exist_ok=True)
            logger.info(
                "backfill_partition_start",
                topic=window.topic,
                date=d.isoformat(),
                path=str(partition),
            )
            write_partition(topic=window.topic, day=d, output=partition)
    except Exception as exc:  # noqa: BLE001
        emit(
            LineageEvent(
                run_id=run_id,
                job_name="etl.backfill",
                event_type="FAIL",
                facets={"error": str(exc)},
            )
        )
        raise

    emit(
        LineageEvent(
            run_id=run_id,
            job_name="etl.backfill",
            event_type="COMPLETE",
            facets={"days": len(window.days())},
        )
    )


def _parse_date(s: str) -> date:
    return datetime.fromisoformat(s).replace(tzinfo=UTC).date()


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SYNAPSE ETL backfill")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--start", required=True, type=_parse_date)
    parser.add_argument("--end", required=True, type=_parse_date)
    parser.add_argument(
        "--output", required=True, type=Path, help="Parquet output root"
    )
    args = parser.parse_args(argv)
    window = BackfillWindow(
        topic=args.topic, start=args.start, end=args.end, output_root=args.output
    )
    run(window)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())


__all__ = ["BackfillWindow", "run"]
