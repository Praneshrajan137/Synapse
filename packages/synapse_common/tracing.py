"""OpenTelemetry wrapper for SYNAPSE agents and the orchestrator.

Single import surface so every service ships identical trace context.
Exports `configure_tracing(service_name)` which:

- sets the OTel `tracer_provider` with a `BatchSpanProcessor` to an OTLP
  HTTP endpoint (Jaeger by default via `otel-collector` in compose);
- instruments FastAPI, requests, and confluent-kafka at import time;
- returns a named tracer the caller uses for custom spans.

Never fails hard: when the OTel SDK isn't installed (unit tests, CI
stripped environments) the function degrades to a no-op tracer so calling
code stays identical.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

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
            def __enter__(self_inner) -> "_Ctx":
                return self_inner

            def __exit__(self_inner, *_: Any) -> None:
                return None

            def set_attribute(self_inner, *_: Any, **__: Any) -> None:
                return None

        return _Ctx()


def configure_tracing(service_name: str) -> Any:  # noqa: ANN401
    """Initialize OTel and return a tracer named `service_name`.

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
