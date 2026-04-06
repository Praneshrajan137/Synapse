"""SYNAPSE Routing Navigator -- MCP Tool Definitions (I-9)."""
from __future__ import annotations

MCP_TOOLS: list[dict[str, object]] = [
    {
        "name": "rl_route_optimize",
        "description": "Optimize delivery routes using trained RL policy. Tier 1-2.",
        "input_schema": {
            "type": "object",
            "properties": {
                "orders": {"type": "array", "items": {"type": "object"}, "maxItems": 200},
                "riders": {"type": "array", "items": {"type": "object"}},
                "store_id": {"type": "string"},
            },
            "required": ["orders", "riders", "store_id"],
        },
    },
]
