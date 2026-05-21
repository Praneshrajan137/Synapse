"""Real-User-Monitoring ingest — web-vitals + CSP violation reports.

Backend gap **B4** for the Atlas Console (plan §11). The frontend's
``web-vitals`` beacon (``src/shared/telemetry/web-vitals.ts``) batches LCP,
TBT, CLS, INP, FCP samples and POSTs them here via ``navigator.sendBeacon``.

This endpoint is also the CSP ``report-to`` target (B7 in nginx). CSP
violation reports follow ``application/reports+json`` (Reporting API);
we accept that content type alongside our own JSON and tag the row.

Why one endpoint?
-----------------
Two reasons. (1) The browser ships at most a handful of beacons per
session, and the violation rate is low — a single low-traffic endpoint
is cheaper to operate than two. (2) Both signals end up in the same
Prometheus histogram set + audit log; co-location keeps the operator
mental model coherent.

Storage
-------
S2: writes a structured-log line + increments three Prometheus
``Histogram`` instruments (``synapse_rum_lcp_seconds``,
``synapse_rum_tbt_seconds``, ``synapse_rum_cls`` etc.). The
existing ``Instrumentator`` mounted in ``api/main.py`` exposes them
on ``/metrics``; Grafana dashboard wiring lands in S6.

S3+: a Postgres ``rum_samples`` table appended (append-only per I-4).

Auth
----
**Public** (no session required). RUM and CSP reports must work even
before the user logs in — the very first paint of the login page must
report LCP. The CSP report path doubly cannot require auth: a script
that XSS'd the page is exactly when we want the report. Rate-limited
at nginx (``api_limit`` zone) to keep abuse bounded.

I-1: web-vitals (Apache-2.0) is on the allow-list; no SaaS RUM service.
I-3: payload validates against the Pydantic schema.
"""

from __future__ import annotations

from typing import Any, Final

import structlog
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Prometheus instruments — created lazily so the import order in api/main.py
# doesn't require a particular sequence with prometheus_fastapi_instrumentator.
# ---------------------------------------------------------------------------
_VITAL_BUCKETS: Final = (
    0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0,
    4.0, 5.0, 7.5, 10.0, 15.0, 30.0,
)


class _Metrics:
    """Lazy singleton — created on first ingest. Avoids double-registration in tests."""

    _instance: "_Metrics | None" = None

    def __init__(self) -> None:
        from prometheus_client import Counter, Histogram

        self.lcp = Histogram(
            "synapse_rum_lcp_seconds",
            "Largest Contentful Paint (s) reported from the browser",
            buckets=_VITAL_BUCKETS,
            labelnames=("route",),
        )
        self.tbt = Histogram(
            "synapse_rum_tbt_seconds",
            "Total Blocking Time (s)",
            buckets=_VITAL_BUCKETS,
            labelnames=("route",),
        )
        self.inp = Histogram(
            "synapse_rum_inp_seconds",
            "Interaction to Next Paint (s)",
            buckets=_VITAL_BUCKETS,
            labelnames=("route",),
        )
        self.fcp = Histogram(
            "synapse_rum_fcp_seconds",
            "First Contentful Paint (s)",
            buckets=_VITAL_BUCKETS,
            labelnames=("route",),
        )
        self.cls = Histogram(
            "synapse_rum_cls",
            "Cumulative Layout Shift (unitless)",
            buckets=(0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0),
            labelnames=("route",),
        )
        self.csp_violations = Counter(
            "synapse_csp_violations_total",
            "CSP violation reports received from the browser",
            labelnames=("blocked_uri", "violated_directive"),
        )
        self.unknown_metrics = Counter(
            "synapse_rum_unknown_metric_total",
            "RUM samples received with an unrecognised metric name",
        )

    @classmethod
    def get(cls) -> "_Metrics":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# ---------------------------------------------------------------------------
# Schemas. Web-vitals v4 emits {name, value, id, delta, rating, navigationType,
# entries[]}. We accept the minimal subset and ignore the rest.
# ---------------------------------------------------------------------------
ALLOWED_VITALS: Final = frozenset({"LCP", "TBT", "INP", "FCP", "CLS", "TTFB"})


class RumSample(BaseModel):
    name: str = Field(..., description="LCP|TBT|INP|FCP|CLS|TTFB")
    value: float = Field(..., ge=0)
    rating: str | None = Field(None, description="good|needs-improvement|poor")
    route: str = Field(..., max_length=256)
    nav_type: str | None = Field(None, max_length=32)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return v.upper()


class RumBatch(BaseModel):
    """A single beacon may contain many samples (web-vitals collects until unload)."""

    session_id: str = Field(..., min_length=8, max_length=128)
    user_agent: str | None = Field(None, max_length=512)
    samples: list[RumSample] = Field(..., max_length=64)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("", include_in_schema=True)
@router.post("/")
async def ingest_rum(
    request: Request,
    content_type: str | None = Header(default=None, alias="Content-Type"),
) -> dict[str, str]:
    """Accepts:

    - ``application/json`` — our own RumBatch beacon.
    - ``application/reports+json`` — browser CSP / Reporting API.
    """
    body = await request.body()
    if not body:
        return {"status": "ok", "kind": "empty"}

    metrics = _Metrics.get()

    # Dispatch on content type. The Reporting API may also send
    # `application/csp-report` (older spec); accept both.
    is_report = bool(
        content_type and ("reports+json" in content_type or "csp-report" in content_type)
    )

    import json

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.warning("rum_invalid_json", error=str(exc))
        return {"status": "rejected", "reason": "invalid_json"}

    if is_report:
        # Reporting API ships either a list of reports or a single object.
        reports = payload if isinstance(payload, list) else [payload]
        for r in reports:
            body_ = r.get("body") if isinstance(r, dict) else {}
            if not isinstance(body_, dict):
                continue
            metrics.csp_violations.labels(
                blocked_uri=str(body_.get("blockedURL") or body_.get("blocked-uri") or "unknown")[:128],
                violated_directive=str(body_.get("effectiveDirective") or body_.get("violated-directive") or "unknown")[:64],
            ).inc()
            logger.info("csp_violation", report=body_)
        return {"status": "ok", "kind": "csp"}

    # RUM beacon path.
    try:
        batch = RumBatch.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rum_invalid_batch", error=str(exc))
        return {"status": "rejected", "reason": "schema_validation"}

    for s in batch.samples:
        if s.name not in ALLOWED_VITALS:
            metrics.unknown_metrics.inc()
            continue
        # CLS is unit-less; everything else is in milliseconds from the
        # browser. Convert to seconds for the histograms.
        seconds = s.value if s.name == "CLS" else s.value / 1000.0
        # Truncate route to surface-level granularity (avoid cardinality blow-up
        # from time-window query strings). Keep the path; drop the search.
        route = s.route.split("?", 1)[0][:64]
        if s.name == "LCP":
            metrics.lcp.labels(route=route).observe(seconds)
        elif s.name == "TBT":
            metrics.tbt.labels(route=route).observe(seconds)
        elif s.name == "INP":
            metrics.inp.labels(route=route).observe(seconds)
        elif s.name == "FCP":
            metrics.fcp.labels(route=route).observe(seconds)
        elif s.name == "CLS":
            metrics.cls.labels(route=route).observe(seconds)
        # TTFB is recorded for completeness but not given its own histogram in S2.

    logger.info(
        "rum_batch_ingested",
        session_id=batch.session_id,
        sample_count=len(batch.samples),
    )
    return {"status": "ok", "kind": "rum", "samples_recorded": str(len(batch.samples))}
