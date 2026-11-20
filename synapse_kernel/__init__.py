"""SYNAPSE's decision kernel: the twin, the incumbent, the challengers and the objective, light.

Pure Python plus numpy and simpy: no pydantic, no logging framework, no YAML, no network and no
environment reads, so the same code runs in CPython and in a browser (Pyodide). The "legacy mode"
-- :data:`synapse_kernel.world.LEGACY_PRIMARY` driven by :func:`synapse_kernel.drive.run_replicate`
and priced by :func:`synapse_kernel.objective.legacy_cost` -- reproduces the E5 harness to the bit
(``tests/kernel/test_legacy_parity.py``), and the Sentinel alone
(:mod:`synapse_kernel.policies.sentinel`) reproduces the eight-agent consensus arm there to the bit
(``tests/kernel/test_sentinel_*.py``, truth session 5). Legacy mode is kept as the parity anchor:
the release's truer world is built beside it, never by changing it, and the legacy code it was
ported from is left untouched (its sealed source sets bind the proof's records).
"""

__version__ = "0.1.0"
