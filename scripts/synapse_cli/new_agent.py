"""``synapse new-agent --name foo`` — scaffold a fresh agent (Sprint 9 §M-dx-1).

Reads Jinja templates from ``scripts/templates/agent/`` and writes a
minimal viable agent layout under ``agents/<name>/``. After generation,
runs ``python scripts/spec_cli.py validate`` to confirm the new spec
passes. The scaffold is intentionally tiny — Sprint 10 wires the
inference + reward + a2a templates once the policy contract is real.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "scripts" / "templates" / "agent"
AGENTS_DIR = REPO_ROOT / "agents"


def _render(template_path: Path, **context: object) -> str:
    """Minimal Jinja-like substitution: replace `{{ var }}` with str(value).

    We deliberately avoid the Jinja2 dependency for this scaffold — the
    templates only use ``{{ name }}``, ``{{ class_name }}``, ``{{ short }}``,
    ``{{ description }}`` so a 5-line substitution is enough and keeps
    the install lean (I-1).
    """
    text = template_path.read_text(encoding="utf-8")
    for key, value in context.items():
        text = text.replace("{{ " + key + " }}", str(value))
    return text


def _short_code(name: str) -> str:
    parts = name.split("_")
    if len(parts) == 1:
        return name[:2].upper()
    return "".join(p[0] for p in parts).upper()


def _class_name(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def scaffold(name: str, description: str) -> int:
    target = AGENTS_DIR / name
    if target.exists():
        print(f"agents/{name}/ already exists — refusing to overwrite", file=sys.stderr)
        return 1
    short = _short_code(name)
    class_name = _class_name(name)
    context = {
        "name": name,
        "short": short,
        "class_name": class_name,
        "description": description,
    }

    # Layout to create (mirrors existing agent skeletons).
    layout = {
        target / "__init__.py": "",
        target / "spec.yaml": _render(TEMPLATES_DIR / "spec.yaml.j2", **context),
        target / "agent_card.json": _render(TEMPLATES_DIR / "agent_card.json.j2", **context),
        target / "state_machine.py": _render(TEMPLATES_DIR / "state_machine.py.j2", **context),
        target / "tests" / "__init__.py": "",
        target / "tests" / "test_spec.py": _render(TEMPLATES_DIR / "test_spec.py.j2", **context),
    }
    for path, content in layout.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO_ROOT)}")

    # Validate the new spec passes the existing gate.
    result = subprocess.run(
        [sys.executable, "scripts/spec_cli.py", "validate"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print("spec validate failed:", result.stderr, file=sys.stderr)
        return 1
    print(result.stdout.strip())
    print(f"\nscaffolded agents/{name}/ — next steps:")
    print(f"  - implement agents/{name}/inference/ + agents/{name}/a2a/")
    print(f"  - add real invariants to agents/{name}/spec.yaml")
    print("  - run `python scripts/check_spec_coverage.py`")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse new-agent")
    parser.add_argument("--name", required=True, help="snake_case agent name")
    parser.add_argument("--description", default="Auto-generated agent skeleton.")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return scaffold(args.name, args.description)


if __name__ == "__main__":
    raise SystemExit(main())
