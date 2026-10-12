# ============================================================================
# SYNAPSE Demand Prophet -- Multi-Stage Dockerfile
# Total cost: $0 (all open-source)
# ============================================================================

# -- Stage 1: Base --
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/ /app/packages/
RUN pip install --no-cache-dir -e /app/packages/

COPY agents/demand_prophet/requirements.txt /app/agents/demand_prophet/
RUN pip install --no-cache-dir -r /app/agents/demand_prophet/requirements.txt

# -- Stage 2: Inference --
FROM base AS serve

COPY agents/demand_prophet/ /app/agents/demand_prophet/
COPY proto/ /app/proto/
COPY packages/synapse_common/ /app/packages/synapse_common/
# purpose-achievement-audit R4.7 (task 10.14): the `stream-materialization`
# compose service REUSES this image with a command override and runs
# `python -m data_fabric.feast.stream_materialization` -- the DEPLOYED consumer of
# synapse.orders.demand. It needs that module plus data_fabric.etl.quality_gates,
# whose package __init__ imports pandas/numpy: both are already installed here
# (agents/demand_prophet/requirements.txt), which is why this image hosts the
# sidecar rather than the leaner api-gateway one. No new CD-matrix image, no new
# dependency, no new AR pull -- C27/C49 lockstep untouched. Copied BEFORE the
# chown so the loop's quarantine writes under /app stay writable as `synapse`.
COPY data_fabric/etl/ /app/data_fabric/etl/
COPY data_fabric/feast/*.py data_fabric/feast/feature_store.yaml /app/data_fabric/feast/

RUN useradd -m -r synapse && chown -R synapse:synapse /app
USER synapse

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"

CMD ["python", "-m", "agents.demand_prophet.inference.serve"]
