"""SBOM drift gate (WS-8 §3).

Compares the current SBOMs under ``infrastructure/sbom/*.cdx.json`` against
an allowlist of approved dependencies (``infrastructure/security/sbom-allowlist.yaml``).
If a new dependency arrives without an allowlist entry, CI fails — forcing
a human to review the addition.

The allowlist is the policy artefact, not the SBOM itself. SBOMs are
regenerated on every CI run by ``scripts/generate_sbom.py``; this script
asserts that nothing in the regenerated SBOM is missing from the allowlist.

Usage::

    python scripts/sbom_diff.py            # human report
    python scripts/sbom_diff.py --check    # exit 1 on drift (CI gate)
    python scripts/sbom_diff.py --update   # append new deps to allowlist
                                            # (operator step, NOT in CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # YAML is optional; fall back to JSON allowlist when missing.

ROOT = Path(__file__).resolve().parents[1]
SBOM_DIR = ROOT / "infrastructure" / "sbom"
ALLOWLIST = ROOT / "infrastructure" / "security" / "sbom-allowlist.yaml"


def _load_allowlist() -> dict[str, dict[str, Any]]:
    """Allowlist shape: {component_name: {versions: [...], notes: "..."}}."""
    if not ALLOWLIST.exists():
        return {}
    text = ALLOWLIST.read_text(encoding="utf-8")
    if yaml is not None:
        loaded = yaml.safe_load(text) or {}
    else:
        # Permissive JSON fallback if PyYAML isn't installed.
        loaded = json.loads(text) if text.strip().startswith("{") else {}
    components = loaded.get("components", {}) if isinstance(loaded, dict) else {}
    return components


def _sbom_components() -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for path in sorted(SBOM_DIR.glob("*.cdx.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for c in doc.get("components", []):
            name = c.get("name")
            version = c.get("version")
            if not name:
                continue
            key = f"{name}=={version}" if version else name
            if key not in seen:
                seen[key] = {
                    "name": name,
                    "version": version,
                    "source": path.name,
                    "purl": c.get("purl"),
                    "licenses": c.get("licenses", []),
                }
    return list(seen.values())


def _is_allowed(component: dict[str, Any], allowlist: dict[str, dict[str, Any]]) -> bool:
    entry = allowlist.get(component["name"])
    if entry is None:
        return False
    versions = entry.get("versions")
    if not versions:
        return True  # any version allowed
    return component["version"] in versions


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    p.add_argument(
        "--update", action="store_true", help="Operator-only: append new deps to the allowlist."
    )
    args = p.parse_args()

    allowlist = _load_allowlist()
    components = _sbom_components()
    missing = [c for c in components if not _is_allowed(c, allowlist)]

    if args.update:
        if yaml is None:
            print("PyYAML required for --update", file=sys.stderr)
            return 2
        ALLOWLIST.parent.mkdir(parents=True, exist_ok=True)
        for c in missing:
            allowlist.setdefault(c["name"], {"versions": [], "notes": "auto-added"})
            if c["version"] and c["version"] not in allowlist[c["name"]]["versions"]:
                allowlist[c["name"]]["versions"].append(c["version"])
        ALLOWLIST.write_text(
            yaml.safe_dump({"components": allowlist}, sort_keys=True),
            encoding="utf-8",
        )
        print(f"Appended {len(missing)} components to {ALLOWLIST}.")
        return 0

    print(f"SBOM components: {len(components)}")
    print(f"Allowlisted: {len(components) - len(missing)}")
    print(f"NOT allowlisted: {len(missing)}")
    for c in missing[:20]:
        v = c.get("version") or "<no-version>"
        print(f"  - {c['name']} {v}  (from {c['source']})")
    if len(missing) > 20:
        print(f"  ... and {len(missing) - 20} more")

    if args.check and missing:
        print(
            "FAIL: SBOM drift — review missing deps and run with --update "
            "from an operator workstation.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
