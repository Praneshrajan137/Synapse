#!/usr/bin/env bash
# ============================================================================
# SYNAPSE — Daily backup to Google Cloud Storage
#
# Run from /etc/crontab (installed by setup_gcp_vm.sh):
#   0 3 * * * root . /etc/synapse-backup.env && /home/synapse/synapse/backup_to_gcs.sh
#
# Reads BACKUP_BUCKET and SYNAPSE_HOME from /etc/synapse-backup.env.
# Uses the VM service account (via `gsutil`, no key files) to upload.
# Bucket lifecycle rule (terraform) auto-deletes objects after 7 days.
# ============================================================================

set -euo pipefail

BACKUP_BUCKET="${BACKUP_BUCKET:?BACKUP_BUCKET env var required}"
SYNAPSE_HOME="${SYNAPSE_HOME:-/home/synapse/synapse}"

DATE=$(date -u +%Y-%m-%d)
TS=$(date -u +%Y%m%dT%H%M%SZ)
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

POSTGRES_USER="${POSTGRES_USER:-synapse}"
POSTGRES_DB="${POSTGRES_DB:-synapse_audit}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-synapse_graph_2026}"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# ── Postgres dump ───────────────────────────────────────────────────────────
PG_OUT="$WORKDIR/postgres-$DATE.sql.gz"
log "Dumping Postgres → $PG_OUT"
if docker ps --format '{{.Names}}' | grep -q '^synapse-postgres$'; then
    docker exec synapse-postgres pg_dumpall -U "$POSTGRES_USER" \
        | gzip -9 > "$PG_OUT"
    gsutil cp "$PG_OUT" "gs://$BACKUP_BUCKET/postgres/postgres-$DATE.sql.gz"
    log "Postgres backup uploaded ($(du -h "$PG_OUT" | cut -f1))"
else
    log "WARN: synapse-postgres container not running, skipping pg backup"
fi

# ── Neo4j dump ──────────────────────────────────────────────────────────────
# neo4j-admin dump requires the DB to be stopped. We use an online APOC export
# instead so we don't need to take the DB down nightly.
NEO_OUT="$WORKDIR/neo4j-$DATE.cypher.gz"
log "Dumping Neo4j (APOC export.cypher.all) → $NEO_OUT"
if docker ps --format '{{.Names}}' | grep -q '^synapse-neo4j$'; then
    docker exec synapse-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
        "CALL apoc.export.cypher.all(null, {format: 'plain', stream: true}) YIELD cypherStatements RETURN cypherStatements" \
        2>/dev/null \
        | gzip -9 > "$NEO_OUT" || log "WARN: Neo4j export failed (APOC plugin loaded?)"
    if [ -s "$NEO_OUT" ]; then
        gsutil cp "$NEO_OUT" "gs://$BACKUP_BUCKET/neo4j/neo4j-$DATE.cypher.gz"
        log "Neo4j backup uploaded ($(du -h "$NEO_OUT" | cut -f1))"
    fi
else
    log "WARN: synapse-neo4j container not running, skipping neo backup"
fi

# ── Compose + env snapshot (handy for disaster recovery) ───────────────────
if [ -f "$SYNAPSE_HOME/docker-compose.gcp.yml" ]; then
    SNAP="$WORKDIR/stack-$DATE.tar.gz"
    tar -C "$SYNAPSE_HOME" -czf "$SNAP" \
        docker-compose.gcp.yml \
        --exclude='.env.gcp' \
        2>/dev/null || true
    gsutil cp "$SNAP" "gs://$BACKUP_BUCKET/stack/stack-$DATE.tar.gz" || true
fi

log "Backup run complete @ $TS"
