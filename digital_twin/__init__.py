"""
SYNAPSE Digital Twin — Supply chain simulation, scenario analysis, and RL sandbox.

Invariants:
  INV-TW-001: Twin within 5% divergence at steady state.
  INV-TW-002: Monte Carlo >= 1000 scenarios per query.
  INV-TW-003: KL divergence alert fires when > 0.1.
  INV-TW-004: What-If API responds within 10s for 1000 scenarios.
"""
