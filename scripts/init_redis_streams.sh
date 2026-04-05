#!/usr/bin/env bash
# ============================================================================
# SYNAPSE — Redis Streams Initialization (I-7 Graceful Degradation)
# Creates Redis streams as Kafka fallback queues.
# ============================================================================
set -euo pipefail

REDIS_CONTAINER="synapse-redis"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  SYNAPSE Redis Streams Initialization               ║"
echo "╚══════════════════════════════════════════════════════╝"

STREAMS=(
    "synapse.fallback.demand"
    "synapse.fallback.routing"
    "synapse.fallback.inventory"
    "synapse.fallback.pricing"
    "synapse.fallback.disruption"
    "synapse.events"
)

for stream in "${STREAMS[@]}"; do
    echo -n "  Creating stream $stream... "
    docker exec "$REDIS_CONTAINER" redis-cli XADD "$stream" '*' init "true" > /dev/null 2>&1
    docker exec "$REDIS_CONTAINER" redis-cli XLEN "$stream" > /dev/null 2>&1
    echo "done"
done

echo ""
echo "Verifying streams..."
for stream in "${STREAMS[@]}"; do
    LEN=$(docker exec "$REDIS_CONTAINER" redis-cli XLEN "$stream" 2>/dev/null)
    echo "  $stream: $LEN entries"
done

echo ""
echo "Redis streams initialized."
