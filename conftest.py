"""
SYNAPSE -- Root conftest.py. Shared fixtures and path configuration.
Ensures all agent test modules can import from project root *and* prefer the
worktree-local `synapse_common` over any editable install in site-packages.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PACKAGES_ROOT = PROJECT_ROOT / "packages"

# Worktree-local packages take precedence over any editable install of the
# parent repo so the tests exercise the code in *this* worktree.
for path in (PACKAGES_ROOT, PROJECT_ROOT):
    p = str(path)
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

# Drop a stale `synapse_common` already loaded from elsewhere so the next
# import resolves against the worktree.
for mod in [m for m in list(sys.modules) if m == "synapse_common" or m.startswith("synapse_common.")]:
    sys.modules.pop(mod, None)
