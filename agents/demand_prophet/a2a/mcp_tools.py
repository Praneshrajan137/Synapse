"""
SYNAPSE Demand Prophet -- MCP Tool Definitions (I-9).
Agent-to-tool communication uses MCP exclusively.
"""
from __future__ import annotations

MCP_TOOLS: list[dict[str, object]] = [
    {
        "name": "rl_demand_forecast",
        "description": "Generate demand forecast using trained RL policy. Tier 1-2.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 500},
                "store_id": {"type": "string"},
                "horizons": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sku_ids", "store_id"],
        },
    },
    {
        "name": "feast_get_demand_features",
        "description": "Retrieve demand signal features from Feast. Tier 1-4.",
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
