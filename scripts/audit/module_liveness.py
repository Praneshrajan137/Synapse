"""SYNAPSE — Module-liveness analyzer.

Builds a first-party import graph rooted at the LIVE service entrypoints (the
Python processes that actually run in docker-compose.gcp.yml) and classifies
every first-party Python module as:

  ALIVE      reachable from a live entrypoint (runs when a request hits the VM)
  TOOLING    not live, but reachable from scripts/ OR referenced by
             Makefile / .github/workflows / docker composes (offline/batch/CI)
  TEST       a test module (*/tests/* or test_*.py / *_test.py)
  DEAD       none of the above — 0 importers and 0 references

This is the deterministic source for docs/state/MODULE_INVENTORY.md and the
anti-rot gate (verify_claims C44). Removal decisions use the DEAD set ONLY.

Usage:
  python scripts/audit/module_liveness.py            # print inventory
  python scripts/audit/module_liveness.py --md FILE  # write the markdown doc
  python scripts/audit/module_liveness.py --check    # exit 1 if DEAD > baseline
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Source roots: repo root (agents/, orchestrator/, api/, digital_twin/,
# data_fabric/, ml_pipelines/, scripts/) + packages/ (synapse_common is
# imported as `synapse_common` via the editable install).
SRC_ROOTS = [ROOT, ROOT / "packages"]

# First-party top-level packages we resolve/track (everything else = stdlib/3p).
FIRST_PARTY = {
    "agents", "orchestrator", "api", "digital_twin",
    "synapse_common", "data_fabric", "ml_pipelines", "scripts",
}

# The Python processes that actually run in docker-compose.gcp.yml.
LIVE_ENTRYPOINTS = [
    ROOT / "api" / "main.py",
    ROOT / "orchestrator" / "inference" / "serve.py",
    ROOT / "digital_twin" / "inference" / "serve.py",
    *sorted(ROOT.glob("agents/*/inference/serve.py")),
]

# Baseline DEAD count — ratchets DOWN only (a NEW dead module fails CI).
# 0 as of the module-liveness sweep: 3 unmounted routers were WIRED
# (firehose/topology/telemetry), 6 orphans REMOVED (api/workers celery,
# cold_start_tracker, agent_models, the data_fabric/etl backfill cluster,
# api/routers/demo), and the offline batch jobs got `make` invocation paths.
DEAD_BASELINE = 0

# Files/dirs whose references prove a module is offline TOOLING, not dead.
REFERENCE_HAYSTACK = [
    ROOT / "Makefile",
    *ROOT.glob(".github/workflows/*.yml"),
    *ROOT.glob("docker/*.yml"),
    ROOT / "conftest.py",
    ROOT / "pyproject.toml",
]


def _iter_first_party_files() -> list[Path]:
    files: list[Path] = []
    for pkg in ("agents", "orchestrator", "api", "digital_twin", "data_fabric", "ml_pipelines", "scripts"):
        files += [p for p in (ROOT / pkg).rglob("*.py") if "__pycache__" not in p.parts]
    sc = ROOT / "packages" / "synapse_common"
    files += [p for p in sc.rglob("*.py") if "__pycache__" not in p.parts]
    return sorted(set(files))


def _module_name(path: Path) -> str | None:
    """File path -> dotted module name (None if not under a known root)."""
    for base in SRC_ROOTS:
        try:
            rel = path.resolve().relative_to(base.resolve())
        except ValueError:
            continue
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if parts and parts[0] in FIRST_PARTY:
            return ".".join(parts)
    return None


def _resolve(dotted: str) -> Path | None:
    """Dotted first-party module -> file path (module.py or package/__init__.py)."""
    if not dotted or dotted.split(".")[0] not in FIRST_PARTY:
        return None
    rel = Path(*dotted.split("."))
    for base in SRC_ROOTS:
        for cand in (base / rel.with_suffix(".py"), base / rel / "__init__.py"):
            if cand.is_file():
                return cand.resolve()
    return None


def _imports(path: Path) -> set[str]:
    """First-party dotted modules imported by this file (incl. relative)."""
    out: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return out
    pkg = _module_name(path)
    pkg_parts = pkg.split(".")[:-1] if pkg else []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and pkg_parts:  # relative import
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
                out.add(mod)
                for a in node.names:
                    out.add(f"{mod}.{a.name}")
            elif node.module:
                out.add(node.module)
                for a in node.names:
                    out.add(f"{node.module}.{a.name}")
    return {m for m in out if m.split(".")[0] in FIRST_PARTY}


def _ancestor_inits(path: Path) -> list[Path]:
    """The package __init__.py files Python implicitly executes to import this
    module (e.g. importing orchestrator.llm.x runs orchestrator/__init__.py and
    orchestrator/llm/__init__.py). Without this, package __init__ files look DEAD."""
    out: list[Path] = []
    for base in SRC_ROOTS:
        try:
            rel = path.resolve().relative_to(base.resolve())
        except ValueError:
            continue
        cur = base
        for part in rel.parts[:-1]:  # walk package dirs, not the file itself
            cur = cur / part
            init = (cur / "__init__.py").resolve()
            if init.is_file():
                out.append(init)
        break
    return out


def _reachable(roots: list[Path]) -> set[Path]:
    seen: set[Path] = set()
    q: deque[Path] = deque(r.resolve() for r in roots if r.is_file())
    while q:
        f = q.popleft()
        if f in seen:
            continue
        seen.add(f)
        for init in _ancestor_inits(f):  # implicit package imports
            if init not in seen:
                q.append(init)
        for dotted in _imports(f):
            tgt = _resolve(dotted)
            if tgt and tgt not in seen:
                q.append(tgt)
    return seen


def _loc(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def _haystack() -> str:
    return "\n".join(
        h.read_text(encoding="utf-8", errors="ignore") for h in REFERENCE_HAYSTACK if h.is_file()
    )


def _python_m_roots(haystack: str) -> list[Path]:
    """Tooling roots referenced by Makefile/CI: `python -m <dotted>` modules,
    AND every .py under a directory the Makefile `cd <dir>`s into (e.g.
    `cd data_fabric/feast` — those files are loaded by the feast CLI, not via a
    python import the AST graph can see)."""
    import re

    roots: list[Path] = []
    for m in re.findall(r"python\d?\s+-m\s+([\w.]+)", haystack):
        f = _resolve(m)
        if f:
            roots.append(f)
    for d in re.findall(r"\bcd\s+([\w./-]+)", haystack):
        dpath = (ROOT / d).resolve()
        if dpath.is_dir() and dpath != ROOT.resolve():
            roots += [p for p in dpath.rglob("*.py") if "__pycache__" not in p.parts]
    return roots


def _referenced(rel: str, dotted: str | None, haystack: str) -> bool:
    """Precise reference: the file path, its dotted name, or an ANCESTOR dir
    path of depth >= 2 (e.g. 'data_fabric/feast', 'ml_pipelines/ab_test')
    appears literally in Makefile/CI/compose. The bare top-level dir name is
    intentionally NOT enough (too coarse — would swallow real orphans)."""
    if rel in haystack:
        return True
    if dotted and (dotted in haystack):
        return True
    parts = rel.split("/")
    for depth in range(2, len(parts)):  # 'a/b', 'a/b/c', ... (skip bare 'a')
        anc = "/".join(parts[:depth])
        if anc in haystack or anc.replace("/", ".") in haystack:
            return True
    return False


def classify() -> dict[str, list[tuple[str, int]]]:
    files = _iter_first_party_files()
    alive = _reachable(LIVE_ENTRYPOINTS)
    haystack = _haystack()
    tooling_roots = (
        sorted((ROOT / "scripts").rglob("*.py"))
        + [f for f in files if "/tests/" in str(f).replace("\\", "/") or f.name.startswith("test_")]
        + _python_m_roots(haystack)
    )
    tooling = _reachable(tooling_roots)

    buckets: dict[str, list[tuple[str, int]]] = {"ALIVE": [], "TOOLING": [], "TEST": [], "DEAD": []}
    for f in files:
        rel = str(f.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        loc = _loc(f)
        if f.resolve() in alive:
            buckets["ALIVE"].append((rel, loc))
        elif "/tests/" in rel or f.name.startswith("test_") or f.name.endswith("_test.py"):
            buckets["TEST"].append((rel, loc))
        elif f.resolve() in tooling or _referenced(rel, _module_name(f), haystack):
            buckets["TOOLING"].append((rel, loc))
        else:
            buckets["DEAD"].append((rel, loc))
    return buckets


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--md", metavar="FILE")
    args = ap.parse_args()

    b = classify()
    totals = {k: (len(v), sum(loc for _, loc in v)) for k, v in b.items()}

    def _print(line: str = "") -> None:
        print(line)

    for cat in ("ALIVE", "TOOLING", "TEST", "DEAD"):
        n, loc = totals[cat]
        _print(f"{cat:9} {n:4} files  {loc:7} lines")
    _print()
    if b["DEAD"]:
        _print("DEAD modules (0 importers, 0 references):")
        for rel, loc in b["DEAD"]:
            _print(f"  {rel} ({loc})")

    if args.md:
        _write_md(Path(args.md), b, totals)
        _print(f"\nwrote {args.md}")

    if args.check:
        dead = totals["DEAD"][0]
        if dead > DEAD_BASELINE:
            print(f"\n[XX] DEAD modules {dead} > baseline {DEAD_BASELINE} — wire or remove the new orphan(s).")
            return 1
        print(f"\n[OK] DEAD modules {dead} <= baseline {DEAD_BASELINE}")
    return 0


def _write_md(path: Path, b: dict[str, list[tuple[str, int]]], totals: dict[str, tuple[int, int]]) -> None:
    lines = ["# SYNAPSE — Module-Liveness Inventory (Python, generated)", ""]
    lines.append("> Generated by `scripts/audit/module_liveness.py` — an AST import graph rooted at the")
    lines.append("> live docker-compose.gcp.yml entrypoints. Regenerate with `--md`. Frontend (~14k TS/TSX)")
    lines.append("> and infra YAML are measured separately (see docs/state/CURRENT.md live-system map).")
    lines.append("")
    lines.append("| Category | Files | Lines | Meaning |")
    lines.append("| --- | --- | --- | --- |")
    meaning = {
        "ALIVE": "runs when a request hits the live VM",
        "TOOLING": "offline/batch/CI/training — invoked via make/CI, not the live request path",
        "TEST": "test modules",
        "DEAD": "0 importers AND 0 references — removal candidates",
    }
    for cat in ("ALIVE", "TOOLING", "TEST", "DEAD"):
        n, loc = totals[cat]
        lines.append(f"| {cat} | {n} | {loc} | {meaning[cat]} |")
    for cat in ("DEAD", "TOOLING"):
        lines.append("")
        lines.append(f"## {cat}")
        for rel, loc in sorted(b[cat]):
            lines.append(f"- `{rel}` ({loc})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
