#!/usr/bin/env python3
"""Validate all proto schemas are valid JSON Schema draft-07."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema


def validate_all_schemas() -> bool:
    proto_dir = Path("proto")
    errors: list[str] = []
    count = 0

    for schema_file in proto_dir.rglob("*.schema.json"):
        count += 1
        try:
            with open(schema_file) as f:
                schema = json.load(f)
            jsonschema.Draft7Validator.check_schema(schema)
            print(f"  OK {schema_file}")
        except Exception as e:
            errors.append(f"  FAIL {schema_file}: {e}")

    print(f"\nValidated {count} schemas.")
    if errors:
        print("ERRORS:")
        for err in errors:
            print(err)
        return False
    print("All schemas valid.")
    return True


if __name__ == "__main__":
    sys.exit(0 if validate_all_schemas() else 1)
