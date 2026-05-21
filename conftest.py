"""
SYNAPSE -- Root conftest.py. Shared fixtures and path configuration.
Ensures all agent test modules can import from project root and that the
worktree's local ``packages/synapse_common`` is preferred over any system-
installed copy (critical when running tests in a git worktree).
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PACKAGES_DIR = PROJECT_ROOT / "packages"

# Prepend in reverse priority order so PROJECT_ROOT wins, then PACKAGES_DIR
# beats site-packages. Without this the test runner sees a stale globally-
# installed ``synapse_common`` and skips Sprint-7 modules.
for path in (str(PACKAGES_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
