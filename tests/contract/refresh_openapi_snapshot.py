"""Refresh the committed OpenAPI snapshot from the live FastAPI app.

Companion to ``test_openapi_byte_equality.py``. Run this whenever the
gateway's surface legitimately changes; review the resulting diff in
``packages/openapi/openapi.json`` exactly the way you'd review a
database migration.

Usage:
    python tests/contract/refresh_openapi_snapshot.py

The output is canonicalised: ``json.dumps(..., sort_keys=True, indent=2)``
with a trailing newline. Same encoder the test uses.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO_ROOT / "packages" / "openapi" / "openapi.json"


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from api.main import app  # noqa: PLC0415

    spec = app.openapi()
    text = json.dumps(spec, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(text, encoding="utf-8")
    print(f"wrote {SNAPSHOT.relative_to(REPO_ROOT)} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
