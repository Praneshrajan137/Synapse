"""Tests for Kafka client — SynapseProducer / SynapseConsumer (I-3, I-13)."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
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
        # Sprint-7 batching (WS-8 §3): produce() no longer flushes per call.
        # Callers (e.g. outbox dispatcher, api.routers.orders) flush explicitly.
        mock_producer.poll.assert_called_once_with(0)

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
