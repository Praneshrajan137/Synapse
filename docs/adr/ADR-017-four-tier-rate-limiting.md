# ADR-017: Four-Tier Rate Limiting (Stripe Model)

## Status
Accepted

## Context
A flat per-IP rate limit conflates four distinct kinds of overload: legitimate burst, slow client tying up workers, fleet-wide saturation, and per-worker pathological queues. Stripe's published rate-limiting architecture handles all four with composable layers. Without this, a single bad client can either be blocked too aggressively (legitimate users denied) or starve the fleet entirely.

## Decision
Implement four sequential rate-limit layers in nginx + FastAPI middleware:
1. **Request Rate** — `nginx limit_req_zone` per IP (100 req/min).
2. **Concurrency** — FastAPI `Semaphore` per agent (max 50 concurrent inflight per agent).
3. **Fleet Usage** — Redis-backed token bucket across all agents (10K req/min globally).
4. **Worker Utilization** — uvicorn worker rejects new connections when CPU > 85% sustained 30s.

Each layer is independently configurable, observable via Prometheus, and emits structured rejection codes (429 with `X-RateLimit-Tier` header).

## Consequences
- Bursty-but-legitimate clients pass tiers 1 and 2; pathological clients fail tier 4.
- Fleet protection is independent of per-IP fairness.
- Adds 4 new Prometheus metrics (one per tier); dashboards in `infrastructure/grafana/dashboards/`.
- nginx config grows; mitigated by templating in `infrastructure/nginx/nginx.conf`.

## Alternatives Rejected
- **Flat per-IP rate limiting**: rejected — single layer covers only one failure mode.
- **API gateway service (Kong/Tyk)**: rejected — additional service for one feature; not zero-cost-friendly.
- **No rate limiting**: rejected — trivially DoS-able.
