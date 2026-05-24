"""OpenTelemetry wrapper for SYNAPSE agents and the orchestrator.

Single import surface so every service ships identical trace context.
Exports:

- ``configure_tracing(service_name)`` — sets up the OTel tracer
  provider, BatchSpanProcessor to an OTLP HTTP endpoint, instruments
  FastAPI and requests, and **installs a W3C ``CompositePropagator``
  (TraceContext + Baggage + B3)** so ``traceparent`` flows over HTTP,
  A2A JSON-RPC, and Kafka headers (ADR-026, WS-2 §1).
- ``instrument_fastapi(app)`` — FastAPI middleware hook.
- ``inject_a2a_headers(headers)`` — write current span context into
  the headers dict used by the A2A SDK.
- ``KafkaHeaderCarrier`` — adapter for confluent-kafka header lists
  (list of ``(key, bytes)``); used by ``SynapseProducer`` and
  ``SynapseConsumer`` to propagate ``trace_id`` through Kafka.

Never fails hard: when the OTel SDK isn't installed (unit tests, CI
stripped environments) the function degrades to a no-op tracer so
calling code stays identical.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import MutableMapping

logger = structlog.get_logger(__name__)

OTEL_ENDPOINT = os.environ.get(
    "SYNAPSE_OTEL_ENDPOINT",
    "http://otel-collector:4318/v1/traces",
)
OTEL_ENABLED = os.environ.get("SYNAPSE_OTEL_ENABLED", "true").lower() == "true"


class _NoopTracer:
    """Fallback used when OTel is unavailable or disabled."""

    def start_as_current_span(self, *_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
        class _Ctx:
            def __enter__(self) -> _Ctx:
                return self

            def __exit__(self, *_: Any) -> None:
                return None

            def set_attribute(self, *_: Any, **__: Any) -> None:
                return None

        return _Ctx()


def _install_propagator() -> None:
    """Install a W3C CompositePropagator (TraceContext + Baggage + B3).

    Idempotent; safe to call multiple times. Falls back silently if
    optional ``opentelemetry-propagator-b3`` is missing — TraceContext
    alone is still active.
    """
    try:
        from opentelemetry import propagate
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        propagators: list[Any] = [TraceContextTextMapPropagator()]
        try:
            from opentelemetry.baggage.propagation import W3CBaggagePropagator

            propagators.append(W3CBaggagePropagator())
        except ImportError:
            logger.debug("otel_baggage_propagator_missing")
        try:
            from opentelemetry.propagators.b3 import B3MultiFormat

            propagators.append(B3MultiFormat())
        except ImportError:
            logger.debug("otel_b3_propagator_missing")
        propagate.set_global_textmap(CompositePropagator(propagators))
        logger.info("otel_propagator_installed", count=len(propagators))
    except ImportError as exc:
        logger.warning("otel_propagator_install_failed", error=str(exc))


def configure_tracing(service_name: str) -> Any:  # noqa: ANN401
    """Initialize OTel and return a tracer named ``service_name``.

    Safe to call multiple times; the second call becomes a no-op.
    """
    if not OTEL_ENABLED:
        logger.info("tracing_disabled", service=service_name)
        return _NoopTracer()

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: F401
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("otel_sdk_missing", error=str(exc))
        return _NoopTracer()

    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _install_propagator()

    try:
        RequestsInstrumentor().instrument()
    except Exception as exc:  # noqa: BLE001
        logger.warning("otel_requests_instrument_failed", error=str(exc))

    logger.info("tracing_configured", service=service_name, endpoint=OTEL_ENDPOINT)
    return trace.get_tracer(service_name)


def instrument_fastapi(app: Any) -> None:  # noqa: ANN401
    """Attach OTel middleware to a FastAPI app."""
    if not OTEL_ENABLED:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:  # noqa: BLE001
        logger.warning("otel_fastapi_instrument_failed", error=str(exc))


def inject_a2a_headers(headers: MutableMapping[str, str]) -> MutableMapping[str, str]:
    """Inject the current span context into ``headers`` (mutated in place).

    Use immediately before sending an A2A JSON-RPC request. When OTel
    is unavailable the dict is returned unchanged.
    """
    try:
        from opentelemetry import propagate

        propagate.inject(headers)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("otel_inject_failed", error=str(exc))
    return headers


class KafkaHeaderCarrier:
    """Adapter making confluent-kafka header lists look like a TextMap.

    Kafka headers are ``list[tuple[str, bytes]]``. OTel propagators
    expect a ``MutableMapping[str, str]``. This carrier translates.

    Usage::

        carrier = KafkaHeaderCarrier()
        propagate.inject(carrier)
        producer.produce(topic, value, headers=carrier.as_kafka_headers())
    """

    def __init__(self, headers: list[tuple[str, bytes]] | None = None) -> None:
        self._items: dict[str, str] = {}
        if headers:
            for key, value in headers:
                if isinstance(value, bytes):
                    self._items[key] = value.decode("utf-8", errors="ignore")
                else:
                    self._items[key] = str(value)

    def __getitem__(self, key: str) -> str:
        return self._items[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._items[key] = value

    def __delitem__(self, key: str) -> None:
        del self._items[key]

    def __iter__(self) -> Any:  # noqa: ANN401
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._items.get(key, default)

    def keys(self) -> Any:  # noqa: ANN401
        return self._items.keys()

    def as_kafka_headers(self) -> list[tuple[str, bytes]]:
        """Return the carrier as a list of ``(str, bytes)`` Kafka headers."""
        return [(k, v.encode("utf-8")) for k, v in self._items.items()]


def extract_kafka_context(headers: list[tuple[str, bytes]] | None) -> Any:  # noqa: ANN401
    """Extract an OTel context from Kafka headers. Returns ``None`` on miss."""
    if not headers:
        return None
    try:
        from opentelemetry import propagate

        carrier = KafkaHeaderCarrier(headers)
        return propagate.extract(carrier)
    except ImportError:
        return None
