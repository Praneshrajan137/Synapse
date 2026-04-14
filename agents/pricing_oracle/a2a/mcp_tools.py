"""
SYNAPSE Pricing Oracle -- MCP Tool Definitions (I-9).
Agent-to-tool communication uses MCP exclusively.
"""

from __future__ import annotations

MCP_TOOLS: list[dict[str, object]] = [
    {
        "name": "rl_price_optimize",
        "description": "Generate optimal price multipliers using trained MADDPG policy. Tier 2.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 200},
                "store_id": {"type": "string"},
                "categories": {"type": "array", "items": {"type": "string"}},
                "base_prices": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["sku_ids", "store_id", "categories", "base_prices"],
        },
    },
    {
        "name": "feast_get_price_features",
        "description": "Retrieve price history and competitor data from Feast. Tier 1-4.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_id": {"type": "string"},
                "store_id": {"type": "string"},
            },
            "required": ["sku_id", "store_id"],
        },
    },
    {
        "name": "causal_estimate_elasticity",
        "description": "Estimate causal price elasticity via Double ML. Tier 3.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_ids": {"type": "array", "items": {"type": "string"}},
                "store_id": {"type": "string"},
                "categories": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sku_ids", "store_id"],
        },
    },
]
