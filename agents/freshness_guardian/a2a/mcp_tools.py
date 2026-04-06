"""
SYNAPSE Freshness Guardian -- MCP Tool Definitions (I-9).
Agent-to-tool communication uses MCP exclusively.
"""
from __future__ import annotations

MCP_TOOLS: list[dict[str, object]] = [
    {
        "name": "rl_freshness_assess",
        "description": "Assess perishable freshness using trained survival model. Tier 1-2.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store_id": {"type": "string"},
                "sku_id": {"type": "string"},
                "days_since_receipt": {"type": "number"},
                "initial_shelf_life_days": {"type": "number"},
            },
            "required": ["store_id", "sku_id"],
        },
    },
    {
        "name": "feast_get_perishable_state",
        "description": "Retrieve perishable state features from Feast. Tier 1-4.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_id": {"type": "string"},
                "store_id": {"type": "string"},
            },
            "required": ["sku_id", "store_id"],
        },
    },
]
