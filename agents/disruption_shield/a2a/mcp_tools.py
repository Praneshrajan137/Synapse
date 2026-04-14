"""
SYNAPSE Disruption Shield -- MCP Tool Definitions (I-9).
Agent-to-tool communication uses MCP exclusively.
"""

from __future__ import annotations

MCP_TOOLS: list[dict[str, object]] = [
    {
        "name": "rl_disruption_detect",
        "description": (
            "Run anomaly ensemble on supply chain signals and produce disruption alert. Tier 2-3."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Supply chain graph node identifiers",
                },
                "tabular_features": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "Tabular feature matrix (n_nodes x n_features)",
                },
                "anomaly_threshold": {
                    "type": "number",
                    "description": "Threshold for anomaly classification (default 0.65)",
                },
            },
            "required": ["node_ids", "tabular_features"],
        },
    },
    {
        "name": "pinecone_get_playbooks",
        "description": (
            "Retrieve historical disruption recovery playbooks from Pinecone vector store. Tier 2."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language description of the disruption scenario",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of playbooks to retrieve (default 3)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "ollama_generate_reasoning",
        "description": (
            "Generate reasoning chain via DeepSeek-R1 on Ollama for disruption analysis. Tier 3."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ensemble_score": {"type": "number"},
                "anomalous_nodes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "context": {"type": "object"},
            },
            "required": ["ensemble_score", "anomalous_nodes"],
        },
    },
    {
        "name": "feast_get_supply_chain_signals",
        "description": "Retrieve supply chain signal features from Feast feature store. Tier 1-4.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["node_ids"],
        },
    },
]
