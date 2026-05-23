"""data_fabric/etl/kafka_to_parquet.py

Stream Kafka topic messages to local Parquet files via PyArrow ParquetWriter.

Use cases:
- Backfill Feast offline store from live event streams
- Build training datasets from production traffic with deterministic schema (I-3)
- Audit-trail Parquet snapshots for incident forensics

Usage:
    python -m data_fabric.etl.kafka_to_parquet \
        --topic synapse.orders.placed \
        --output data/streams/orders.parquet \
        --batch-size 1000 \
        --max-records 100000

Honors I-1 (no paid SaaS), I-3 (deterministic schema), and I-13 (deterministic
JSON serialization for KV cache compatibility).
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException

log = structlog.get_logger()


def _build_consumer(broker: str, group: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": broker,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,  # commit per batch flush only
            "session.timeout.ms": 30000,
        }
    )


def _parse_message(raw: bytes) -> dict[str, Any]:
    """Parse a Kafka message body. Assumes JSON-encoded payload."""
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot parse Kafka message as JSON: {exc!r}") from exc


def _records_to_table(records: list[dict[str, Any]]) -> pa.Table:
    """Convert list of dicts to PyArrow table with schema inference."""
    if not records:
        raise ValueError("Cannot build table from empty record list")
    return pa.Table.from_pylist(records)


def stream_topic_to_parquet(
    *,
    broker: str,
    topic: str,
    group: str,
    output: Path,
    batch_size: int = 1000,
    max_records: int | None = None,
    poll_timeout_seconds: float = 1.0,
    max_idle_polls: int = 30,
) -> int:
    """Drain `topic` to `output` Parquet file. Returns total records written.

    Stops when:
    - max_records reached, OR
    - max_idle_polls consecutive empty polls, OR
    - SIGINT/SIGTERM received

    Each batch is flushed to Parquet AND committed to Kafka atomically.
    """
    consumer = _build_consumer(broker, group)
    consumer.subscribe([topic])

    writer: pq.ParquetWriter | None = None
    schema: pa.Schema | None = None
    batch: list[dict[str, Any]] = []
    total = 0
    idle = 0

    output.parent.mkdir(parents=True, exist_ok=True)

    stop_requested = False

    def _request_stop(signum: int, _frame: Any) -> None:  # noqa: ARG001
        nonlocal stop_requested
        stop_requested = True
        log.info("stop_requested", signal=signum)

    signal.signal(signal.SIGINT, _request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_stop)

    try:
        while not stop_requested:
            msg = consumer.poll(timeout=poll_timeout_seconds)
            if msg is None:
                idle += 1
                if idle >= max_idle_polls:
                    log.info("idle_threshold_reached", polls=idle)
                    break
                continue
            idle = 0

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            try:
                record = _parse_message(msg.value())
            except ValueError as exc:
                log.warning("skip_unparseable", error=str(exc), offset=msg.offset())
                continue

            record["_kafka_offset"] = msg.offset()
            record["_kafka_partition"] = msg.partition()
            batch.append(record)

            if len(batch) >= batch_size:
                table = _records_to_table(batch)
                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(output, schema, compression="snappy")
                writer.write_table(table.cast(schema))
                consumer.commit(asynchronous=False)
                total += len(batch)
                log.info("batch_flushed", count=len(batch), total=total, offset=msg.offset())
                batch.clear()

                if max_records is not None and total >= max_records:
                    log.info("max_records_reached", total=total)
                    break

        if batch and writer is not None:
            table = _records_to_table(batch)
            writer.write_table(table.cast(schema))
            consumer.commit(asynchronous=False)
            total += len(batch)
            log.info("final_batch_flushed", count=len(batch), total=total)
        elif batch:
            table = _records_to_table(batch)
            writer = pq.ParquetWriter(output, table.schema, compression="snappy")
            writer.write_table(table)
            consumer.commit(asynchronous=False)
            total += len(batch)
            log.info("single_batch_written", count=len(batch))

    finally:
        if writer is not None:
            writer.close()
        consumer.close()

    log.info("stream_complete", topic=topic, output=str(output), total_records=total)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stream a Kafka topic to Parquet")
    parser.add_argument("--broker", default="localhost:9092")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--group", default="synapse-etl-kafka-to-parquet")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--max-idle-polls", type=int, default=30)
    args = parser.parse_args(argv)

    total = stream_topic_to_parquet(
        broker=args.broker,
        topic=args.topic,
        group=args.group,
        output=args.output,
        batch_size=args.batch_size,
        max_records=args.max_records,
        max_idle_polls=args.max_idle_polls,
    )
    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
