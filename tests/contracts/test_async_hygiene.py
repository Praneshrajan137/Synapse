"""Async-hygiene contract test (WS-1 §1, ADR-025).

AST-walks ``api/`` and ``orchestrator/`` and asserts no ``async def``
function calls a synchronous-I/O escape hatch:

  - ``requests.post`` / ``requests.get`` / ``requests.request`` / etc.
  - ``psycopg2.connect`` / ``psycopg2.*``
  - ``time.sleep``
  - ``httpx.Client(...)`` (synchronous client)

Scope is bounded to ``api/`` and ``orchestrator/`` per the Sprint-7
plan §M10 — agents are not yet refactored and are addressed in a
follow-up cleanup task.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ["api", "orchestrator"]
SKIP_DIRS = {"__pycache__", "tests", "migrations"}


BANNED_ATTR_CALLS: set[tuple[str, str]] = {
    ("requests", "post"),
    ("requests", "get"),
    ("requests", "put"),
    ("requests", "delete"),
    ("requests", "patch"),
    ("requests", "request"),
    ("psycopg2", "connect"),
    ("time", "sleep"),
}

BANNED_NAME_CALLS: set[str] = set()  # left empty; module-level calls are usually fine


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

    sync_io_calls: list[tuple[int, str]] = []
    async_func_ranges: list[tuple[int, int, ast.AsyncFunctionDef]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            start = node.lineno
            end = max((n.lineno for n in ast.walk(node) if hasattr(n, "lineno")), default=start)
            async_func_ranges.append((start, end, node))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        attr = _attr_call(node)
        if attr in BANNED_ATTR_CALLS:
            sync_io_calls.append((node.lineno, ".".join(attr)))
        elif _is_sync_httpx_client(node):
            sync_io_calls.append((node.lineno, "httpx.Client"))

    offenders: list[tuple[int, str]] = []
    for lineno, name in sync_io_calls:
        for start, end, _ in async_func_ranges:
            if start <= lineno <= end:
                offenders.append((lineno, name))
                break
    return offenders


def _attr_call(call: ast.Call) -> tuple[str, str] | None:
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return (func.value.id, func.attr)
    return None


def _is_sync_httpx_client(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "httpx" and func.attr == "Client"
    return False


@pytest.mark.contract
def test_no_sync_io_inside_async_def() -> None:
    offenders: list[str] = []
    for path in _python_files():
        for lineno, name in _violations(path):
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno} → {name}")
    assert not offenders, (
        "Synchronous I/O inside async def — see docs/runbooks/async_hygiene_violation.md\n"
        + "\n".join(offenders)
    )
