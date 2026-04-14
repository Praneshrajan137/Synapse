"""SYNAPSE Inventory Sentinel -- MCP Tool Definitions (I-9)."""

from __future__ import annotations

MCP_TOOLS: list[dict[str, object]] = [
    {
        "name": "rl_inventory_decision",
        "description": "Generate inventory decisions using trained H-MARL policy. Tier 1-2.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 1000},
                "store_id": {"type": "string"},
            },
            "required": ["sku_ids", "store_id"],
        },
    },
]
