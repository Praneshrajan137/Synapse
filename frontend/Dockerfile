# syntax=docker/dockerfile:1.7
# SYNAPSE Frontend — Multi-stage build.
# Stage 1: Node build → static assets.
# Stage 2: nginx-unprivileged → serves the SPA with strict cache headers + CSP.
# Holds I-1: no SaaS, no telemetry to third parties, base images are Apache-2.0/BSD.

# ───────── Stage 1: builder ─────────
FROM node:20.18-alpine AS builder
WORKDIR /app

ENV CI=1 \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile=false --prefer-offline

COPY tsconfig.json tsconfig.node.json vite.config.ts ./
COPY tailwind.config.ts postcss.config.cjs ./
COPY index.html ./
COPY src ./src

ARG VITE_BUILD_SHA=dev
ARG VITE_BUILD_TIME
ENV VITE_BUILD_SHA=${VITE_BUILD_SHA} \
    VITE_BUILD_TIME=${VITE_BUILD_TIME}

RUN pnpm typecheck && pnpm build

# ───────── Stage 2: runtime ─────────
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
USER root
RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/synapse.conf
COPY --from=builder /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s \
  CMD wget --spider -q http://localhost:8080/healthz || exit 1
CMD ["nginx", "-g", "daemon off;"]
