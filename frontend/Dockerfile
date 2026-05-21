# ---------------------------------------------------------------------------
# SYNAPSE Atlas Console — multi-stage Dockerfile.
#
# Build context: REPO ROOT (../). This lets us COPY the committed OpenAPI
# snapshot at packages/openapi/openapi.json without escaping the context.
# Set in docker-compose.yml: { context: .., dockerfile: frontend/Dockerfile }.
#
# Stage 1 (build): node:20-alpine + pnpm via Corepack. Generates Orval API
#   client + Zod schemas, then runs `vite build` to produce dist/.
# Stage 2 (runtime): nginx-unprivileged:1.27-alpine serving static dist/ on
#   port 8080. Health probe at /healthz. SBOM embedded as image label.
#
# Plan §13 / B6: container listens on 8080. The reverse-proxy upstream in
# infrastructure/nginx/nginx.conf is updated to match (was :5173, the dev port).
# ---------------------------------------------------------------------------
ARG NODE_VERSION=20.18.0
ARG NGINX_VERSION=1.27-alpine
ARG PNPM_VERSION=9.12.3

# ─── Stage 1: build ────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS build

ARG PNPM_VERSION
ENV CI=true \
    HUSKY=0 \
    PNPM_HOME="/pnpm" \
    PATH="/pnpm:$PATH"

RUN corepack enable \
 && corepack prepare pnpm@${PNPM_VERSION} --activate \
 && apk add --no-cache python3 make g++ git

WORKDIR /app

# Lockfile + manifest first so the install layer caches independently of source.
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
COPY frontend/.npmrc* ./

RUN --mount=type=cache,id=pnpm-store,target=/pnpm/store \
    pnpm install --frozen-lockfile --prefer-offline

# Source.
COPY frontend/ ./

# OpenAPI snapshot — committed in packages/openapi/. The Orval config reads
# from ../packages/openapi/openapi.json relative to /app, so we mirror that
# layout inside the build stage.
RUN mkdir -p /packages/openapi
COPY packages/openapi/openapi.json /packages/openapi/openapi.json

# Generate API client + Zod schemas, then build. Type-check is part of build.
RUN pnpm orval --config orval.config.ts \
 && pnpm schemas:zod \
 && pnpm typecheck \
 && pnpm build

# ─── Stage 2: runtime ──────────────────────────────────────────────────────
FROM nginxinc/nginx-unprivileged:${NGINX_VERSION} AS runtime

LABEL org.opencontainers.image.title="synapse-atlas-console" \
      org.opencontainers.image.description="SYNAPSE Atlas Console — ops control surface" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/synapse/synapse" \
      org.opencontainers.image.vendor="SYNAPSE"

# nginx-unprivileged runs as user `nginx` (uid 101). Static assets live under
# /usr/share/nginx/html; conf at /etc/nginx/conf.d/default.conf.
COPY --from=build /app/dist /usr/share/nginx/html
COPY infrastructure/nginx/frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --quiet --spider --tries=1 http://localhost:8080/healthz || exit 1

# nginx-unprivileged image already specifies USER nginx and CMD; do not override.
