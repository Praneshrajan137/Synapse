# ============================================================================
# SYNAPSE Freshness Guardian -- Multi-Stage Dockerfile
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

COPY agents/freshness_guardian/requirements.txt /app/agents/freshness_guardian/
RUN pip install --no-cache-dir -r /app/agents/freshness_guardian/requirements.txt

# -- Stage 2: Inference --
FROM base AS serve

COPY agents/freshness_guardian/ /app/agents/freshness_guardian/
COPY proto/ /app/proto/
COPY packages/synapse_common/ /app/packages/synapse_common/

RUN useradd -m -r synapse && chown -R synapse:synapse /app
USER synapse

EXPOSE 8004

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')"

CMD ["python", "-m", "agents.freshness_guardian.inference.serve"]
