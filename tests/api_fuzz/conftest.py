"""Schemathesis API fuzz test configuration.

Generates random valid/invalid inputs from OpenAPI specs to find:
- 500 errors on edge inputs
- Schema violations in responses
- Validation bypasses
- Stateful bugs from rapid sequential calls
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()

AGENT_ENDPOINTS: dict[str, str] = {
    "demand_prophet": "http://localhost:8081",
    "routing_navigator": "http://localhost:8082",
    "inventory_sentinel": "http://localhost:8083",
    "pricing_oracle": "http://localhost:8084",
    "orchestrator": "http://localhost:8085",
    "freshness_guardian": "http://localhost:8086",
    "disruption_shield": "http://localhost:8087",
    "supplier_trust": "http://localhost:8088",
    "sustainability_agent": "http://localhost:8089",
}


def get_openapi_url(agent_name: str) -> str:
    """Return the OpenAPI JSON URL for a given agent."""
    return f"{AGENT_ENDPOINTS[agent_name]}/openapi.json"
