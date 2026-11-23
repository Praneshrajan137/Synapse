"""A fixed-delay sleep says why it is not a retry (ADR-016; the ``jitter-enforcement`` hook).

``CLAUDE.md``: never fixed-delay retries, Full Jitter from ``synapse_common.retry`` only. A
``time.sleep`` whose delay comes from a jitter function (any called name containing ``jitter``),
directly or through a name the same module assigns from one, passes. Any other ``time.sleep``
must carry ``# not-a-retry: <reason>`` on its line or the line above: a periodic loop, a clock's
pace, a readiness poll. Test files (``test_*.py``, ``conftest.py``, anything under a ``tests``
directory) are not checked.

The first version (May to November 2026) failed every file holding ``time.sleep`` and not the
string ``retry_with_jitter``, so it flagged periodic loops and the jittered retry in
``synapse_common.features``; it never ran (TRUTH-MAP F-34, truth session 5).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import PurePosixPath
from typing import Final

MARK: Final[re.Pattern[str]] = re.compile(r"#\s*not-a-retry:\s*\S")


def is_test(path: str) -> bool:
    parts = PurePosixPath(path.replace("\\", "/")).parts
    name = parts[-1] if parts else ""
    return name.startswith("test_") or name == "conftest.py" or "tests" in parts[:-1]


def _sleep_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Names bound to the ``time`` module, and names bound to ``time.sleep``."""
    modules: set[str] = set()
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.asname or a.name for a in node.names if a.name == "time")
        elif isinstance(node, ast.ImportFrom) and node.module == "time":
            functions.update(a.asname or a.name for a in node.names if a.name == "sleep")
    return modules, functions


def _called_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _calls_jitter(node: ast.AST) -> bool:
    return any(
        isinstance(inner, ast.Call) and "jitter" in _called_name(inner).lower()
        for inner in ast.walk(node)
    )


def _jitter_names(tree: ast.AST) -> set[str]:
    """Names the module assigns from an expression that calls a jitter function."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _calls_jitter(node.value):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.target, ast.Name)
            and _calls_jitter(node.value)
        ):
            names.add(node.target.id)
    return names


def check(path: str, source: str) -> list[str]:
    """Every unmarked fixed-delay ``time.sleep`` in ``source``, as failure lines."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [f"FAIL {path}: cannot parse ({exc.msg}, line {exc.lineno})"]
    modules, functions = _sleep_names(tree)
    jittered_names = _jitter_names(tree)
    lines = source.splitlines()
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        sleeps = (
            isinstance(func, ast.Attribute)
            and func.attr == "sleep"
            and isinstance(func.value, ast.Name)
            and func.value.id in modules
        ) or (isinstance(func, ast.Name) and func.id in functions)
        if not sleeps:
            continue
        arguments = [*node.args, *(k.value for k in node.keywords)]
        if any(_calls_jitter(arg) for arg in arguments) or any(
            isinstance(arg, ast.Name) and arg.id in jittered_names for arg in arguments
        ):
            continue
        first = max(0, node.lineno - 2)  # the line above the call, and the call's own line
        if not any(MARK.search(line) for line in lines[first : node.lineno]):
            out.append(
                f"FAIL {path}:{node.lineno}: fixed-delay time.sleep without "
                "'# not-a-retry: <reason>' - retries use Full Jitter (ADR-016)"
            )
    return out


def main(paths: list[str]) -> int:
    failures: list[str] = []
    for path in paths:
        if is_test(path) or not path.endswith(".py"):
            continue
        with open(path, encoding="utf-8") as handle:
            failures.extend(check(path, handle.read()))
    for line in failures:
        print(line)
    if failures:
        return 1
    print("OK every fixed-delay sleep says why it is not a retry (ADR-016)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
