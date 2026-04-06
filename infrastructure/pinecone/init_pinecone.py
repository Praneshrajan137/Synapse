"""
SYNAPSE — Pinecone Starter Index Initialization.
Creates the synapse-playbooks index for Disruption Shield playbook retrieval
and semantic decision cache (ADR-018).

Pinecone Starter limits (verified April 2026):
  - 2GB storage (playbook corpus ~500 vectors at 768-dim = ~3MB)
  - 5 indexes (we use 1-2)
  - 2M write units/month, 1M read units/month
  - AWS us-east-1 only
  - Indexes paused after 3 weeks inactivity

Run: python infrastructure/pinecone/init_pinecone.py
Requires: PINECONE_API_KEY env var
"""
from __future__ import annotations

import os
import time

import numpy as np
import structlog
from pinecone import Pinecone, ServerlessSpec

logger = structlog.get_logger(__name__)


def init_playbook_index() -> None:
    """Create the disruption playbook index."""
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

    index_name = os.environ.get("PINECONE_INDEX_NAME", "synapse-playbooks")

    existing = [idx.name for idx in pc.list_indexes()]
    if index_name in existing:
        logger.info("index_exists", name=index_name)
        return

    pc.create_index(
        name=index_name,
        dimension=768,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

    while not pc.describe_index(index_name).status.get("ready"):
        logger.info("waiting_for_index", name=index_name)
        time.sleep(5)

    logger.info("index_created", name=index_name, dimension=768, metric="cosine")


def seed_playbooks() -> None:
    """Seed disruption playbooks as vectors.

    Playbook categories:
    1. Weather disruptions (flooding, cyclone, extreme heat)
    2. Supply chain disruptions (supplier delay, port closure)
    3. Demand shocks (IPL match, festival surge)
    4. Infrastructure failures (cold chain break, vehicle breakdown)
    5. Regulatory events (FSSAI recall, price control order)
    """
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index_name = os.environ.get("PINECONE_INDEX_NAME", "synapse-playbooks")
    index = pc.Index(index_name)

    rng = np.random.default_rng(42)

    playbooks = [
        {"id": "PB-FLOOD-001", "category": "weather", "severity": "high",
         "title": "Urban Flooding Response",
         "actions": "Reroute deliveries via elevated roads; pre-position inventory at unaffected stores; activate surge pricing on non-essentials only; notify riders of safe routes via OSRM re-route"},
        {"id": "PB-CYCLONE-001", "category": "weather", "severity": "critical",
         "title": "Cyclone Preparedness",
         "actions": "72h advance: pre-stock essentials; 24h: suspend deliveries in affected zones; activate warehouse-direct mode; resume via graduated zone reopening"},
        {"id": "PB-HEAT-001", "category": "weather", "severity": "medium",
         "title": "Extreme Heat Protocol",
         "actions": "Reduce rider shift duration; increase cold chain monitoring frequency to 5-min intervals; prioritize perishable deliveries in morning slots; activate dynamic markdown on heat-sensitive items"},
        {"id": "PB-SUPPLIER-001", "category": "supply_chain", "severity": "high",
         "title": "Primary Supplier Delay",
         "actions": "Activate secondary suppliers from trust-ranked list; increase safety stock multiplier to 2.5x; notify affected stores; trigger inter-store rebalancing for critical SKUs"},
        {"id": "PB-PORT-001", "category": "supply_chain", "severity": "critical",
         "title": "Port Closure Impact",
         "actions": "Switch to domestic alternatives; extend lead time estimates by 2x; activate rationing on imported SKUs; coordinate with warehouse for buffer stock release"},
        {"id": "PB-IPL-001", "category": "demand_shock", "severity": "medium",
         "title": "IPL Match Demand Surge",
         "actions": "Pre-position snacks and beverages 4h before match; hold essential prices at 1.0x; surge-price non-essentials up to 1.5x; pre-assign riders to high-demand zones"},
        {"id": "PB-FESTIVAL-001", "category": "demand_shock", "severity": "high",
         "title": "Festival Season Surge",
         "actions": "7-day advance: 3x inventory for festive categories; activate all riders; extend operating hours; hold essential prices; coordinate inter-store transfers"},
        {"id": "PB-COLDCHAIN-001", "category": "infrastructure", "severity": "critical",
         "title": "Cold Chain Break",
         "actions": "Immediate FSSAI compliance logging; quarantine affected inventory; activate markdown engine for near-expiry items; trigger emergency restock from nearest compliant store"},
        {"id": "PB-VEHICLE-001", "category": "infrastructure", "severity": "low",
         "title": "Delivery Vehicle Breakdown",
         "actions": "Reassign orders to nearest available rider; update ETA for affected customers; trigger backup rider pool; log incident for fleet maintenance"},
        {"id": "PB-RECALL-001", "category": "regulatory", "severity": "critical",
         "title": "FSSAI Product Recall",
         "actions": "Immediately delist affected SKU from all stores; notify customers with recent purchases; quarantine existing stock; activate substitute recommendations; log compliance audit trail"},
    ]

    vectors = []
    for pb in playbooks:
        embedding = rng.standard_normal(768).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)

        vectors.append({
            "id": pb["id"],
            "values": embedding.tolist(),
            "metadata": {
                "category": pb["category"],
                "severity": pb["severity"],
                "title": pb["title"],
                "actions": pb["actions"],
            },
        })

    index.upsert(vectors=vectors)
    logger.info("playbooks_seeded", count=len(vectors))

    stats = index.describe_index_stats()
    logger.info(
        "index_stats",
        total_vectors=stats.total_vector_count,
        dimension=stats.dimension,
    )


def main() -> None:
    """Initialize Pinecone and seed playbooks."""
    init_playbook_index()
    seed_playbooks()


if __name__ == "__main__":
    main()
