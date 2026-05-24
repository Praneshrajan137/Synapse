# SYNAPSE C4 — Data Flow (Sprint 9 §M-dx-2, auto-generated)

```mermaid
flowchart LR
    all_agents-->|synapse.audit.log|postgres_sink
    all_agents-->|synapse.audit.log|compliance
    demand_prophet-->|synapse.demand.drift_alert|ml_pipeline
    demand_prophet-->|synapse.demand.forecast|inventory_sentinel
    demand_prophet-->|synapse.demand.forecast|pricing_oracle
    demand_prophet-->|synapse.demand.forecast|orchestrator
    disruption_shield-->|synapse.disruption.alert|all_agents
    disruption_shield-->|synapse.disruption.alert|orchestrator
    disruption_shield-->|synapse.disruption.playbook|routing_navigator
    disruption_shield-->|synapse.disruption.playbook|inventory_sentinel
    freshness_guardian-->|synapse.freshness.alert|inventory_sentinel
    freshness_guardian-->|synapse.freshness.alert|pricing_oracle
    inventory_sentinel-->|synapse.inventory.reorder|supplier_trust
    inventory_sentinel-->|synapse.inventory.reorder|orchestrator
    inventory_sentinel-->|synapse.inventory.state|demand_prophet
    inventory_sentinel-->|synapse.inventory.state|freshness_guardian
    all_agents-->|synapse.metrics.agent|prometheus_exporter
    orchestrator-->|synapse.orchestrator.decision|all_agents
    orchestrator-->|synapse.orchestrator.decision|audit_logger
    orchestrator-->|synapse.orchestrator.escalation|hitl_console
    api_gateway-->|synapse.orders.demand|demand_prophet
    api_gateway-->|synapse.orders.demand|inventory_sentinel
    api_gateway-->|synapse.orders.demand|orchestrator
    pricing_oracle-->|synapse.pricing.update|demand_prophet
    pricing_oracle-->|synapse.pricing.update|orchestrator
    routing_navigator-->|synapse.routing.plan|orchestrator
    routing_navigator-->|synapse.routing.plan|sustainability_agent
    supplier_trust-->|synapse.supplier.score|inventory_sentinel
    supplier_trust-->|synapse.supplier.score|orchestrator
    sustainability_agent-->|synapse.sustainability.carbon|orchestrator
    sustainability_agent-->|synapse.sustainability.carbon|routing_navigator
    digital_twin-->|synapse.twin.divergence|disruption_shield
    digital_twin-->|synapse.twin.divergence|orchestrator
```
