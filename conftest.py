"""
SYNAPSE -- Root conftest.py. Shared fixtures and path configuration.
Ensures all agent test modules can import from project root.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
