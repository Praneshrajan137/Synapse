FROM python:3.11-slim AS builder

WORKDIR /build

COPY packages/synapse_common/ /build/packages/synapse_common/
COPY digital_twin/ /build/digital_twin/

RUN pip install --no-cache-dir --prefix=/install \
    pydantic>=2.0 \
    pydantic-settings>=2.0 \
    fastapi>=0.110 \
    uvicorn[standard]>=0.29 \
    structlog>=24.1 \
    simpy>=4.1 \
    mesa>=3.0 \
    numpy>=1.26 \
    neo4j>=5.19 \
    confluent-kafka>=2.3 \
    httpx>=0.27 \
    prometheus-client>=0.20 \
    gymnasium>=1.0

# -------------------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL maintainer="synapse-team"
LABEL description="SYNAPSE Digital Twin — simulation, Monte Carlo, What-If API"

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /build/packages/synapse_common/ /app/packages/synapse_common/
COPY --from=builder /build/digital_twin/ /app/digital_twin/

ENV PYTHONPATH="/app:/app/packages" \
    TW_HOST="0.0.0.0" \
    TW_PORT="8009" \
    PYTHONUNBUFFERED="1"

EXPOSE 8009

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8009/health')"]

ENTRYPOINT ["python", "-m", "uvicorn", "digital_twin.inference.serve:app", \
            "--host", "0.0.0.0", "--port", "8009"]
