"""Export E5's primary world cell from the legacy reader into the kernel's JSON document.

    python -m scripts.kernel.export_legacy_world          # rewrite the committed document
    python -m scripts.kernel.export_legacy_world --check  # exit 1 if it would change

The kernel reads no YAML, so the legacy cell (``digital_twin/simulation/policy.yaml`` ``world:``,
resolved by ``digital_twin.simulation.world``) is exported once, canonically, and
``tests/kernel/test_legacy_parity.py`` pins the export equal to what the legacy reader resolves.
"""

from __future__ import annotations

import argparse
import json
import sys

from synapse_kernel.world import LEGACY_PRIMARY, world_to_document


def render() -> str:
    """The canonical JSON text of E5's primary cell, as the legacy reader resolves it."""
    from digital_twin.simulation.world import load_world

    spec = load_world()
    world = spec.resolve(spec.primary_cell)
    document = world_to_document(world)  # type: ignore[arg-type]  # same fields, legacy class
    return json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the document, or with ``--check`` report whether it is current."""
    parser = argparse.ArgumentParser(prog="python -m scripts.kernel.export_legacy_world")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render()
    current = LEGACY_PRIMARY.read_text(encoding="utf-8") if LEGACY_PRIMARY.is_file() else ""
    if args.check:
        if text != current:
            print(f"{LEGACY_PRIMARY} is stale: run python -m scripts.kernel.export_legacy_world")
            return 1
        print(f"{LEGACY_PRIMARY.name} is current")
        return 0
    LEGACY_PRIMARY.write_text(text, encoding="utf-8")
    print(f"wrote {LEGACY_PRIMARY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
