# ============================================================================
# SYNAPSE Orchestrator — Multi-Stage Dockerfile
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

COPY orchestrator/requirements.txt /app/orchestrator/
RUN pip install --no-cache-dir -r /app/orchestrator/requirements.txt

# -- Stage 2: Inference --
FROM base AS serve

COPY orchestrator/ /app/orchestrator/
COPY proto/ /app/proto/
COPY packages/synapse_common/ /app/packages/synapse_common/
# The audit-chain verifier reads its migration boundary and walk bounds from this
# committed file (AD-13: never inlined as literals). `python -m orchestrator.audit.cli
# verify` runs INSIDE this container at deploy time (cd-gcp.yml::deploy-to-vm,
# Makefile::deploy-gcp-verify) and that step is blocking as of task 7.3, so an image
# without the file would fail every deploy with "cannot read the committed chain bounds"
# instead of reporting on the chain. Resolution is relative to /app, which is
# `load_chain_bounds`'s repo root inside the image.
COPY infrastructure/quality/audit-chain-bounds.yaml /app/infrastructure/quality/audit-chain-bounds.yaml
# Same contract for the Tier-4 twin veto (ADR-054 D3, task 8.7): the bound is
# committed configuration (AD-13) and `load_twin_verdict_bounds` is deliberately
# fail-closed - a deployment that declares a veto and cannot read its own bound
# refuses to ratify a Tier-4 decision rather than dispatching as though the veto had
# been evaluated. The consensus protocol runs in THIS container, so the file must be
# in the image or every Tier-4 decision raises. Resolution is relative to /app.
COPY infrastructure/quality/twin-verdict-bounds.yaml /app/infrastructure/quality/twin-verdict-bounds.yaml

RUN useradd -m -r synapse && chown -R synapse:synapse /app
USER synapse

EXPOSE 8085

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8085/health')"

CMD ["python", "-m", "orchestrator.inference.serve"]
