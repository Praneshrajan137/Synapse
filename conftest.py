"""
SYNAPSE -- Root conftest.py. Shared fixtures and path configuration.
Ensures all agent test modules can import from project root.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Hypothesis profiles
# ---------------------------------------------------------------------------
# Property-based tests inherit ``max_examples`` from the active profile instead
# of hardcoding a count, so the example budget can be tuned per environment:
#
#   * ``dev``     (10 examples)   — fast local feedback / checkpoints.
#   * ``heavy``   (100 examples)  — CI budget for properties whose EACH example runs
#                                  real work (the SimPy twin, the real four-tier
#                                  ``ConsensusProtocol``, or the CLI end-to-end).
#                                  100 is the minimum any spec obligation requires;
#                                  500 of these would take the CI job past an hour.
#                                  Pair with ``-m slow``.
#   * ``default`` (500 examples)  — PR CI default (matches the prior hardcoded count).
#   * ``ci``      (500 examples)  — explicit alias for PR CI.
#   * ``nightly`` (5_000 examples)— exhaustive nightly fuzzing.
#
# Select one with ``HYPOTHESIS_PROFILE=dev pytest ...`` or
# ``pytest --hypothesis-profile=dev``.
#
# Per ``.kiro/steering/local-compute-budget.md`` (I-0), local runs use ``dev``; the
# ``heavy``/``ci``/``nightly`` budgets belong to CI, never the dev laptop.
try:
    from hypothesis import HealthCheck, settings
except ImportError:  # hypothesis is optional in some environments
    pass
else:
    _SUPPRESS = [HealthCheck.function_scoped_fixture]
    settings.register_profile(
        "dev", max_examples=10, deadline=None, suppress_health_check=_SUPPRESS
    )
    settings.register_profile(
        "heavy", max_examples=100, deadline=None, suppress_health_check=_SUPPRESS
    )
    settings.register_profile(
        "default", max_examples=500, deadline=None, suppress_health_check=_SUPPRESS
    )
    settings.register_profile(
        "ci", max_examples=500, deadline=None, suppress_health_check=_SUPPRESS
    )
    settings.register_profile(
        "nightly", max_examples=5_000, deadline=None, suppress_health_check=_SUPPRESS
    )
    settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))
