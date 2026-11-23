"""The colour system's spec conforms to its own JSON schema (the ``color-spec-validate`` hook).

``design-system/color/color-system.spec.yml`` against ``schema/color-spec.schema.json``, with the
validator its ``$schema`` names. Every error is printed with its path in the spec.

When it first ran (truth session 5) it failed: PR #77 had replaced the spec's ``preconditions:``
header with seven new invariants, which left ``PRE-CLR-001`` and ``PRE-CLR-002`` inside the
``invariants`` list (TRUTH-MAP F-34).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

import jsonschema  # type: ignore[import-untyped]
import yaml

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SPEC: Final[Path] = ROOT / "design-system" / "color" / "color-system.spec.yml"
SCHEMA: Final[Path] = ROOT / "design-system" / "color" / "schema" / "color-spec.schema.json"


def errors(spec_path: Path = SPEC, schema_path: Path = SCHEMA) -> list[str]:
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.validators.validator_for(schema)(schema)
    found = sorted(validator.iter_errors(spec), key=lambda e: [str(p) for p in e.absolute_path])
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in found]


def main(argv: list[str]) -> int:
    found = errors()
    for line in found:
        print(f"FAIL {SPEC.relative_to(ROOT).as_posix()} at {line}")
    if found:
        return 1
    print(f"OK {SPEC.relative_to(ROOT).as_posix()} conforms to its schema")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
