# SYNAPSE Supplier Trust -- Multi-Stage Dockerfile
FROM python:3.11-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY packages/ /app/packages/
RUN pip install --no-cache-dir -e /app/packages/
COPY agents/supplier_trust/requirements.txt /app/agents/supplier_trust/
RUN pip install --no-cache-dir -r /app/agents/supplier_trust/requirements.txt

FROM base AS serve
COPY agents/supplier_trust/ /app/agents/supplier_trust/
COPY proto/ /app/proto/
COPY packages/synapse_common/ /app/packages/synapse_common/
RUN useradd -m -r synapse && chown -R synapse:synapse /app
USER synapse
EXPOSE 8007
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8007/health')"
CMD ["python", "-m", "agents.supplier_trust.inference.serve"]
