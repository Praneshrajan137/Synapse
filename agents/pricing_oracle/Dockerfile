# ============================================================================
# SYNAPSE Pricing Oracle -- Multi-Stage Dockerfile
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

COPY agents/pricing_oracle/requirements.txt /app/agents/pricing_oracle/
RUN pip install --no-cache-dir -r /app/agents/pricing_oracle/requirements.txt

# -- Stage 2: Inference --
FROM base AS serve

COPY agents/pricing_oracle/ /app/agents/pricing_oracle/
COPY proto/ /app/proto/
COPY packages/synapse_common/ /app/packages/synapse_common/

RUN useradd -m -r synapse && chown -R synapse:synapse /app
USER synapse

EXPOSE 8005

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')"

CMD ["python", "-m", "agents.pricing_oracle.inference.serve"]
