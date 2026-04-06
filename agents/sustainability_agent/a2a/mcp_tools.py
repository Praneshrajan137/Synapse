"""
SYNAPSE Sustainability Agent -- MCP Tool Definitions (I-9).
Agent-to-tool communication uses MCP exclusively.
"""
from __future__ import annotations

MCP_TOOLS: list[dict[str, object]] = [
    {
        "name": "rl_carbon_report",
        "description": "Generate carbon footprint report for a delivery route. Tier 2.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fuel_liters": {"type": "number", "minimum": 0.0},
                "distance_km": {"type": "number", "minimum": 0.0},
                "days_ahead": {"type": "integer", "minimum": 1, "default": 7},
            },
            "required": ["fuel_liters", "distance_km"],
        },
    },
    {
        "name": "rl_waste_prediction",
        "description": "Predict food waste probability via survival analysis. Tier 2-3.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "minimum": 1},
                "quality_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "shelf_life_days": {"type": "integer", "minimum": 1},
            },
            "required": ["days_ahead"],
        },
    },
    {
        "name": "feast_get_sustainability_features",
        "description": "Retrieve carbon and waste signal features from Feast. Tier 1-4.",
        "input_schema": {
            "type": "object",
            "properties": {
                "route_id": {"type": "string"},
                "store_id": {"type": "string"},
            },
            "required": ["route_id", "store_id"],
        },
    },
]
