"""JSON-determinism contract test (WS-2 §5, ADR-026).

Every ``json.dumps(...)`` call in production code (``packages/``,
``orchestrator/``, ``agents/``, ``api/``, ``scripts/``) must either:
  - pass explicit ``sort_keys=True, separators=(',',':')`` kwargs, or
  - splat ``**JSON_KWARGS`` / ``**SERIALIZATION_KWARGS`` / ``**_JSON_KWARGS``
    (the canonical kwargs containers used across the codebase).

This preserves KV-cache stability (I-13) and gives a single, mechanical
guard against accidental serialisation drift.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
# Runtime-code scope only — script tooling (scripts/, demo/) is allowed to
# use ``indent=`` for human-readable file output. The rule guards KV-cache
# stability and Kafka byte stability, which only applies on the hot path.
SCAN_DIRS = ["packages", "orchestrator", "agents", "api"]
SKIP_DIRS = {"__pycache__", "tests", "training", "migrations", "node_modules"}

ALLOWED_KWARGS_NAMES = {
    "JSON_KWARGS",
    "_JSON_KWARGS",
    "SERIALIZATION_KWARGS",
    "_SERIALIZATION_KWARGS",
}


def _is_json_dumps(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "json" and func.attr == "dumps"
    return False


def _is_deterministic(call: ast.Call) -> bool:
    has_sort_keys = False
    has_separators = False
    for kw in call.keywords:
        if (
            kw.arg is None
            and isinstance(kw.value, ast.Name)
            and kw.value.id in ALLOWED_KWARGS_NAMES
        ):
            return True
        if kw.arg == "sort_keys" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            has_sort_keys = True
        if kw.arg == "separators":
            has_separators = True
    return has_sort_keys and has_separators


def _python_files() -> list[Path]:
    files: list[Path] = []
    for scan in SCAN_DIRS:
        root = REPO_ROOT / scan
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            files.append(path)
    return files


def _violations(path: Path) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_json_dumps(node) and not _is_deterministic(node):
            offenders.append((node.lineno, ast.unparse(node)[:120]))
    return offenders


@pytest.mark.contract
def test_json_dumps_is_deterministic() -> None:
    bad: list[str] = []
    for path in _python_files():
        for lineno, snippet in _violations(path):
            bad.append(f"{path.relative_to(REPO_ROOT)}:{lineno} → {snippet}")
    assert not bad, (
        "json.dumps without sort_keys=True, separators=(',',':') breaks "
        "KV-cache stability (I-13). Use JSON_KWARGS:\n" + "\n".join(bad)
    )
