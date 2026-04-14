#!/bin/bash
set -euo pipefail

# ─── OSRM MUMBAI DATA PREPARATION ────────────────────────────────────────────
# This script ONLY prepares OSRM routing data (download, extract, process).
# Container lifecycle is managed by docker-compose.mumbai.yml.
#
# Usage:  bash scripts/setup_osrm_mumbai.sh
#
# After running this script, start the OSRM container via:
#   docker compose -f docker/docker-compose.yml -f docker/docker-compose.mumbai.yml up -d osrm-mumbai
#
# INVARIANT I-1: OSRM is BSD-licensed. $0 cost.

MUMBAI_DATA_DIR="$(pwd)/data/mumbai"

echo "[OSRM-Mumbai] Starting data preparation..."

mkdir -p "$MUMBAI_DATA_DIR"

# Step 1: Download Maharashtra OSM extract
if [ ! -f "$MUMBAI_DATA_DIR/mumbai.osm.pbf" ]; then
    echo "[OSRM-Mumbai] Downloading Maharashtra OSM extract..."
    wget -O "$MUMBAI_DATA_DIR/mumbai.osm.pbf" \
      "https://download.geofabrik.de/asia/india/maharashtra-latest.osm.pbf"
else
    echo "[OSRM-Mumbai] OSM extract already exists, skipping download."
fi

# Step 2: Extract Mumbai bounding box
if [ ! -f "$MUMBAI_DATA_DIR/mumbai_extract.osm.pbf" ]; then
    echo "[OSRM-Mumbai] Extracting Mumbai bounding box..."
    command -v osmium >/dev/null 2>&1 || {
        echo "[OSRM-Mumbai] Installing osmium-tool..."
        sudo apt-get install -y osmium-tool
    }
    osmium extract -b 72.77,18.87,73.15,19.30 \
      "$MUMBAI_DATA_DIR/mumbai.osm.pbf" -o "$MUMBAI_DATA_DIR/mumbai_extract.osm.pbf" \
      --overwrite
else
    echo "[OSRM-Mumbai] Mumbai extract already exists, skipping."
fi

# Step 3: Process for OSRM (extract -> partition -> customize)
if [ ! -f "$MUMBAI_DATA_DIR/mumbai_extract.osrm.cell_metrics" ]; then
    echo "[OSRM-Mumbai] Processing OSRM data (extract/partition/customize)..."
    docker run -t --rm -v "$MUMBAI_DATA_DIR:/data" osrm/osrm-backend:latest \
      osrm-extract -p /opt/car.lua /data/mumbai_extract.osm.pbf
    docker run -t --rm -v "$MUMBAI_DATA_DIR:/data" osrm/osrm-backend:latest \
      osrm-partition /data/mumbai_extract.osrm
    docker run -t --rm -v "$MUMBAI_DATA_DIR:/data" osrm/osrm-backend:latest \
      osrm-customize /data/mumbai_extract.osrm
else
    echo "[OSRM-Mumbai] OSRM data already processed, skipping."
fi

echo "[OSRM-Mumbai] Data preparation complete."
echo "[OSRM-Mumbai] Start the routing server via:"
echo "  docker compose -f docker/docker-compose.yml -f docker/docker-compose.mumbai.yml up -d osrm-mumbai"
