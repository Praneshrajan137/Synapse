"""SYNAPSE Supplier Trust -- MCP Tool Definitions (I-9)."""
from __future__ import annotations

MCP_TOOLS: list[dict[str, object]] = [
    {
        "name": "score_supplier_trust",
        "description": "Score a supplier's trustworthiness using GNN embeddings and Bayesian lead-time model. Tier 2-3.",
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier_id": {"type": "string", "minLength": 1},
                "delivery_history": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "lead_time_days": {"type": "number", "minimum": 0},
                            "on_time": {"type": "boolean"},
                        },
                        "required": ["lead_time_days", "on_time"],
                    },
                },
                "is_new_vendor": {"type": "boolean", "default": False},
            },
            "required": ["supplier_id"],
        },
    },
    {
        "name": "estimate_lead_time",
        "description": "Bayesian posterior estimation for supplier lead times. Returns mean, std, p10, p90.",
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier_id": {"type": "string", "minLength": 1},
                "observed_lead_times": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0.01},
                    "minItems": 1,
                },
            },
            "required": ["supplier_id", "observed_lead_times"],
        },
    },
]
