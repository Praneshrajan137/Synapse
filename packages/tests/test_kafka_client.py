"""Tests for Kafka client — SynapseProducer / SynapseConsumer (I-3, I-13)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from pydantic import BaseModel
from synapse_common.kafka_client import (
    KafkaConfig,
    SynapseConsumer,
    SynapseProducer,
)


class TestKafkaConfig:

    def test_defaults(self) -> None:
        cfg = KafkaConfig()
        assert cfg.bootstrap_servers == "localhost:9092"
        assert cfg.group_id == "synapse-default"
        assert cfg.auto_offset_reset == "earliest"
        assert cfg.enable_auto_commit is True

    def test_custom_values(self) -> None:
        cfg = KafkaConfig(bootstrap_servers="broker:9093", group_id="custom")
        assert cfg.bootstrap_servers == "broker:9093"
        assert cfg.group_id == "custom"


class TestSynapseProducer:

    @patch("synapse_common.kafka_client.Producer")
    def test_produce_dict(self, mock_producer_cls: MagicMock) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        cfg = KafkaConfig()
        producer = SynapseProducer(cfg)
        producer.produce("topic-a", {"key": "value"}, key="k1")

        mock_producer.produce.assert_called_once()
        call_kwargs = mock_producer.produce.call_args[1]
        assert call_kwargs["topic"] == "topic-a"
        assert call_kwargs["key"] == b"k1"
        payload = json.loads(call_kwargs["value"].decode("utf-8"))
        assert payload == {"key": "value"}
        mock_producer.flush.assert_called_once()

    @patch("synapse_common.kafka_client.Producer")
    def test_produce_pydantic_model(self, mock_producer_cls: MagicMock) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        class Sample(BaseModel):
            x: int = 1

        cfg = KafkaConfig()
        producer = SynapseProducer(cfg)
        producer.produce("topic-b", Sample())

        call_kwargs = mock_producer.produce.call_args[1]
        assert call_kwargs["key"] is None
        payload = json.loads(call_kwargs["value"].decode("utf-8"))
        assert payload == {"x": 1}

    @patch("synapse_common.kafka_client.Producer")
    def test_produce_deterministic_json(self, mock_producer_cls: MagicMock) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        cfg = KafkaConfig()
        producer = SynapseProducer(cfg)
        producer.produce("t", {"b": 2, "a": 1})

        raw = mock_producer.produce.call_args[1]["value"].decode("utf-8")
        assert raw == '{"a":1,"b":2}'

    @patch("synapse_common.kafka_client.Producer")
    def test_close(self, mock_producer_cls: MagicMock) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        producer = SynapseProducer(KafkaConfig())
        producer.close()
        mock_producer.flush.assert_called_with(timeout=10.0)


class TestTraceHeaders:
    """W3C trace-context propagation through Kafka (Sprint 7, WS-2)."""

    @patch("synapse_common.kafka_client.Producer")
    def test_caller_supplied_headers_are_forwarded(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        producer = SynapseProducer(KafkaConfig())
        producer.produce(
            "t",
            {"x": 1},
            headers={"traceparent": "00-abc-def-01", "Idempotency-Key": "k1"},
        )

        call_kwargs = mock_producer.produce.call_args[1]
        emitted = dict(call_kwargs["headers"])
        # bytes values per confluent_kafka contract
        assert emitted["traceparent"] == b"00-abc-def-01"
        assert emitted["Idempotency-Key"] == b"k1"

    @patch("synapse_common.kafka_client.Producer")
    def test_otel_traceparent_auto_injected_when_absent(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        with patch(
            "synapse_common.kafka_client._inject_trace_headers",
            return_value={"traceparent": "00-AUTO-AUTO-01"},
        ):
            producer = SynapseProducer(KafkaConfig())
            producer.produce("t", {"x": 1})

        emitted = dict(mock_producer.produce.call_args[1]["headers"])
        assert emitted["traceparent"] == b"00-AUTO-AUTO-01"

    @patch("synapse_common.kafka_client.Producer")
    def test_caller_traceparent_wins_over_otel(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        with patch(
            "synapse_common.kafka_client._inject_trace_headers",
            return_value={"traceparent": "00-AUTO-AUTO-01"},
        ):
            producer = SynapseProducer(KafkaConfig())
            producer.produce(
                "t", {"x": 1}, headers={"traceparent": "00-CALLER-CALLER-01"}
            )

        emitted = dict(mock_producer.produce.call_args[1]["headers"])
        assert emitted["traceparent"] == b"00-CALLER-CALLER-01"

    @patch("synapse_common.kafka_client.Consumer")
    def test_consumer_extracts_trace_headers(
        self, mock_consumer_cls: MagicMock
    ) -> None:
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer

        msg = MagicMock()
        msg.error.return_value = None
        msg.value.return_value = b'{"x":1}'
        msg.headers.return_value = [
            ("traceparent", b"00-abc-def-01"),
            ("Idempotency-Key", b"k1"),
        ]
        mock_consumer.poll.return_value = msg

        consumer = SynapseConsumer(KafkaConfig(), ["t"])
        result = consumer.poll_with_context(timeout=0.5)
        assert result is not None
        payload, headers = result
        assert payload == {"x": 1}
        assert headers["traceparent"] == "00-abc-def-01"
        assert headers["Idempotency-Key"] == "k1"

    def test_trace_headers_only_filters_recognised_keys(self) -> None:
        all_headers = {
            "traceparent": "00-abc-def-01",
            "tracestate": "vendor=value",
            "x-b3-traceid": "abc",
            "Idempotency-Key": "k1",
            "user-agent": "agent",
        }
        out = SynapseConsumer.trace_headers_only(all_headers)
        assert set(out) == {"traceparent", "tracestate", "x-b3-traceid"}

    @patch("synapse_common.kafka_client.Consumer")
    def test_consumer_handles_missing_headers(
        self, mock_consumer_cls: MagicMock
    ) -> None:
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer

        msg = MagicMock()
        msg.error.return_value = None
        msg.value.return_value = b'{"x":1}'
        msg.headers.return_value = None
        mock_consumer.poll.return_value = msg

        consumer = SynapseConsumer(KafkaConfig(), ["t"])
        result = consumer.poll_with_context()
        assert result is not None
        _, headers = result
        assert headers == {}


class TestSynapseConsumer:

    @patch("synapse_common.kafka_client.Consumer")
    def test_poll_valid_message(self, mock_consumer_cls: MagicMock) -> None:
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer

        msg = MagicMock()
        msg.error.return_value = None
        msg.value.return_value = b'{"hello":"world"}'
        mock_consumer.poll.return_value = msg

        consumer = SynapseConsumer(KafkaConfig(), ["topic-a"])
        result = consumer.poll(timeout=0.5)
        assert result == {"hello": "world"}

    @patch("synapse_common.kafka_client.Consumer")
    def test_poll_returns_none_on_no_message(self, mock_consumer_cls: MagicMock) -> None:
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer
        mock_consumer.poll.return_value = None

        consumer = SynapseConsumer(KafkaConfig(), ["topic-a"])
        assert consumer.poll() is None

    @patch("synapse_common.kafka_client.Consumer")
    def test_poll_returns_none_on_error(self, mock_consumer_cls: MagicMock) -> None:
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer

        msg = MagicMock()
        msg.error.return_value = MagicMock()
        mock_consumer.poll.return_value = msg

        consumer = SynapseConsumer(KafkaConfig(), ["topic-a"])
        assert consumer.poll() is None

    @patch("synapse_common.kafka_client.Consumer")
    def test_poll_returns_none_on_decode_error(self, mock_consumer_cls: MagicMock) -> None:
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer

        msg = MagicMock()
        msg.error.return_value = None
        msg.value.return_value = b"not-json"
        mock_consumer.poll.return_value = msg

        consumer = SynapseConsumer(KafkaConfig(), ["topic-a"])
        assert consumer.poll() is None

    @patch("synapse_common.kafka_client.Consumer")
    def test_close(self, mock_consumer_cls: MagicMock) -> None:
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer

        consumer = SynapseConsumer(KafkaConfig(), ["topic-a"])
        consumer.close()
        mock_consumer.close.assert_called_once()
