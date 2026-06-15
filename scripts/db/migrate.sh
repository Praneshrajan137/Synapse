#!/usr/bin/env bash
# ============================================================================
# SYNAPSE database migration runner (Sprint 20, P0.2).
#
# WHY: docker-entrypoint-initdb.d only runs on an EMPTY data dir, so an
# already-provisioned postgres_data volume never picks up new/changed SQL. The
# previous CD step hand-listed THREE psql -f calls — which is exactly how the
# WS-2 outbox migration got forgotten and the whole outbox subsystem rotted. This
# runner is the SINGLE source of apply-order: adding a migration is one line in
# MIGRATIONS below, and it can never again be silently skipped.
#
# Every migration is written idempotently (CREATE ... IF NOT EXISTS, guarded
# CREATE TYPE, ADD COLUMN IF NOT EXISTS, guarded ALTERs), so applying the FULL
# ordered chain on every deploy is safe AND self-healing — it reconciles a
# partially-initialised volume up to the current schema. ON_ERROR_STOP=1 makes a
# non-idempotent regression fail the deploy loudly instead of rotting silently.
#
# USAGE:
#   # Inside the GCP VM (psql runs in the postgres container, files are mounted
#   # at /docker-entrypoint-initdb.d):
#   SYN_PSQL='docker compose -f docker/docker-compose.gcp.yml \
#       --env-file .env.gcp --env-file .env.gcp.local exec -T postgres \
#       psql -U synapse -d synapse_audit' \
#   bash scripts/db/migrate.sh
#
#   # Against any reachable Postgres (dev / local / CI), files on local disk:
#   SYN_PSQL='psql postgresql://synapse:pw@localhost:5432/synapse_audit' \
#   SYN_INITDB_DIR="$(pwd)/infrastructure/postgres" \
#   SYN_LOCAL_NAMES=1 \
#   bash scripts/db/migrate.sh
#
# The ORM<->DDL contract for the outbox table is enforced separately by
# scripts/audit/outbox_schema_truth.py (C55).
# ============================================================================
set -euo pipefail

PSQL="${SYN_PSQL:-psql}"
DIR="${SYN_INITDB_DIR:-/docker-entrypoint-initdb.d}"

# Single source of apply-order. The numeric prefixes match the container mount
# targets in docker/docker-compose.gcp.yml. Adding a migration = one line here.
MIGRATIONS=(
  "01_init_audit.sql"
  "02_sprint4_consensus.sql"
  "03_p1_override.sql"
  "04_p3_city.sql"
  "05_sprint7_outbox.sql"
  "06_ws2_orders_outbox.sql"
  "07_sprint9_audit_chain.sql"
  "08_ws5_steering.sql"
  "09_wsA_consensus_city.sql"
  "10_sprint19_outcomes.sql"
)

# When applying against local repo files (not the container mounts), the source
# filenames differ from the ordered mount-target names. Map them here.
declare -A LOCAL_NAME=(
  ["01_init_audit.sql"]="init_audit.sql"
  ["02_sprint4_consensus.sql"]="02_sprint4_consensus.sql"
  ["03_p1_override.sql"]="03_p1_override.sql"
  ["04_p3_city.sql"]="04_p3_city.sql"
  ["05_sprint7_outbox.sql"]="03_sprint7_outbox.sql"
  ["06_ws2_orders_outbox.sql"]="05_ws2_orders_outbox.sql"
  ["07_sprint9_audit_chain.sql"]="04_sprint9_audit_chain.sql"
  ["08_ws5_steering.sql"]="06_ws5_steering.sql"
  ["09_wsA_consensus_city.sql"]="07_wsA_consensus_city.sql"
  ["10_sprint19_outcomes.sql"]="08_sprint19_outcomes.sql"
)

# Ledger so re-runs are observable. Idempotent SQL means re-applying is safe; the
# ledger records when each was last applied (audit + a fast "what's the schema?").
# shellcheck disable=SC2086
$PSQL -v ON_ERROR_STOP=1 -c \
  "CREATE TABLE IF NOT EXISTS schema_migrations (
       filename   TEXT PRIMARY KEY,
       applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );"

for name in "${MIGRATIONS[@]}"; do
  file="$name"
  if [[ "${SYN_LOCAL_NAMES:-0}" == "1" ]]; then
    file="${LOCAL_NAME[$name]}"
  fi
  echo ">> applying ${file}"
  # shellcheck disable=SC2086
  $PSQL -v ON_ERROR_STOP=1 -f "${DIR}/${file}"
  # shellcheck disable=SC2086
  $PSQL -v ON_ERROR_STOP=1 -c \
    "INSERT INTO schema_migrations(filename) VALUES ('${name}')
     ON CONFLICT (filename) DO UPDATE SET applied_at = NOW();"
done

echo "OK: applied ${#MIGRATIONS[@]} migration(s) in order."
