#!/usr/bin/env bash
# ============================================================================
# SYNAPSE — Kafka Topic Provisioner
# Reads topics.json and creates every registered topic with correct configuration.
# Run AFTER Kafka is healthy: ./scripts/create_kafka_topics.sh
# ============================================================================
set -euo pipefail

KAFKA_CONTAINER="synapse-kafka"
BOOTSTRAP="localhost:9092"
TOPICS_FILE="infrastructure/kafka/topics.json"

if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required. Install with: sudo apt install jq"
    exit 1
fi

if [ ! -f "$TOPICS_FILE" ]; then
    echo "ERROR: $TOPICS_FILE not found. Run from synapse/ root."
    exit 1
fi

echo "╔══════════════════════════════════════════════════════╗"
echo "║  SYNAPSE Kafka Topic Provisioner                    ║"
echo "╚══════════════════════════════════════════════════════╝"

TOPIC_COUNT=$(jq '.topics | length' "$TOPICS_FILE")
echo "Creating $TOPIC_COUNT topics..."

jq -c '.topics[]' "$TOPICS_FILE" | while read -r topic; do
    NAME=$(echo "$topic" | jq -r '.name')
    PARTITIONS=$(echo "$topic" | jq -r '.partitions')
    RETENTION_HOURS=$(echo "$topic" | jq -r '.retention_hours')

    if [ "$RETENTION_HOURS" -eq -1 ]; then
        RETENTION_MS="-1"
    else
        RETENTION_MS=$((RETENTION_HOURS * 3600000))
    fi

    echo -n "  Creating $NAME (partitions=$PARTITIONS, retention=${RETENTION_HOURS}h)... "

    docker exec "$KAFKA_CONTAINER" /opt/kafka/bin/kafka-topics.sh \
        --create \
        --if-not-exists \
        --bootstrap-server "$BOOTSTRAP" \
        --topic "$NAME" \
        --partitions "$PARTITIONS" \
        --replication-factor 1 \
        --config retention.ms="$RETENTION_MS" \
        --config max.message.bytes=10485760 \
        2>/dev/null

    echo "done"
done

echo ""
echo "Verifying topics..."
CREATED=$(docker exec "$KAFKA_CONTAINER" /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server "$BOOTSTRAP" 2>/dev/null | grep "^synapse\." | wc -l)
echo "Total synapse topics created: $CREATED / $TOPIC_COUNT"

if [ "$CREATED" -eq "$TOPIC_COUNT" ]; then
    echo "All topics provisioned successfully."
else
    echo "MISMATCH: Expected $TOPIC_COUNT, got $CREATED"
    exit 1
fi
