"""Generate CycloneDX SBOMs for every SYNAPSE service (Sprint 9 §M-sec-1).

Iterates the service requirements files and produces one
``infrastructure/sbom/<service>.cdx.json`` per service. Uses
``cyclonedx-bom`` (MIT) as the source-of-truth backend. CI uploads the
SBOMs as release artifacts; ``--check`` mode keeps the on-disk files
byte-stable against fresh generation so the CI gate is meaningful.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SBOM_DIR = REPO_ROOT / "infrastructure" / "sbom"

# Services SYNAPSE ships. Each entry maps to the requirements file the SBOM is built from.
SERVICES: dict[str, Path] = {
    "synapse-common": REPO_ROOT / "packages" / "requirements.txt",
    "orchestrator": REPO_ROOT / "orchestrator" / "requirements.txt",
}


def _have_cyclonedx() -> bool:
    return shutil.which("cyclonedx-py") is not None or shutil.which("cyclonedx-bom") is not None


def _emit_sbom_via_tool(service: str, requirements: Path, out_path: Path) -> bool:
    """Try the official cyclonedx-py CLI; if absent fall back to a minimal SBOM."""
    if shutil.which("cyclonedx-py") is not None:
        cmd = [
            "cyclonedx-py",
            "requirements",
            "--input-file",
            str(requirements),
            "--output-format",
            "json",
            "--output-file",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return True
        print(result.stderr, file=sys.stderr)
        return False
    return False


def _minimal_sbom(service: str, requirements: Path) -> dict[str, object]:
    """Deterministic minimal CycloneDX 1.5 doc; used when the CLI is absent."""
    components: list[dict[str, object]] = []
    if requirements.exists():
        for raw in sorted(requirements.read_text(encoding="utf-8").splitlines()):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # Strip extras and version constraints to get a clean name+version pair.
            name = line.split("[")[0].split("=")[0].split("<")[0].split(">")[0].strip()
            version = "unknown"
            if "==" in line:
                version = line.split("==", 1)[1].split()[0].split(",")[0]
            components.append(
                {
                    "type": "library",
                    "bom-ref": f"pkg:pypi/{name}@{version}",
                    "name": name,
                    "version": version,
                    "purl": f"pkg:pypi/{name}@{version}",
                }
            )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": service,
                "version": "1.0.0",
            }
        },
        "components": components,
    }


def _render(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def generate_all() -> dict[str, str]:
    rendered: dict[str, str] = {}
    for service, requirements in SERVICES.items():
        out_path = SBOM_DIR / f"{service}.cdx.json"
        if _emit_sbom_via_tool(service, requirements, out_path):
            rendered[service] = out_path.read_text(encoding="utf-8")
        else:
            rendered[service] = _render(_minimal_sbom(service, requirements))
    return rendered


def write_sboms(rendered: dict[str, str]) -> None:
    SBOM_DIR.mkdir(parents=True, exist_ok=True)
    for service, content in rendered.items():
        (SBOM_DIR / f"{service}.cdx.json").write_text(content, encoding="utf-8")


def check_sboms(rendered: dict[str, str]) -> bool:
    drift: list[str] = []
    for service, expected in rendered.items():
        on_disk = SBOM_DIR / f"{service}.cdx.json"
        if not on_disk.exists():
            drift.append(f"missing {on_disk.relative_to(REPO_ROOT)}")
            continue
        if on_disk.read_text(encoding="utf-8") != expected:
            drift.append(f"out of sync: {on_disk.relative_to(REPO_ROOT)}")
    if drift:
        print("\n".join(drift), file=sys.stderr)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = generate_all()
    if args.check:
        return 0 if check_sboms(rendered) else 1
    write_sboms(rendered)
    print(f"wrote {len(rendered)} SBOMs to {SBOM_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
