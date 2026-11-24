"""The LLM system prompt is a constant (I-13, ADR-021; the ``kv-cache-check`` hook).

In the files given: ``SYSTEM_PROMPT`` is bound once, at module level, to string literals only (no
f-string, ``.format``, call, name or clock), and every system message - ``{"role": "system",
"content": ...}`` or ``dict(role="system", content=...)`` - takes its content from
``SYSTEM_PROMPT`` or a string literal. Dynamic data belongs in the messages after the prefix,
which this hook does not police.

The first version (May to November 2026) failed any f-string, ``.format(``, ``time.time()`` or
``datetime.now(`` anywhere in its three files, exception text included, so it could not pass on
correct code (36 f-strings in ``orchestrator/consensus/protocol.py`` alone); it never ran
(TRUTH-MAP F-34, truth session 5).
"""

from __future__ import annotations

import ast
import sys
from typing import Final

NAME: Final[str] = "SYSTEM_PROMPT"


def _literal_text(node: ast.expr | None) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _literal_text(node.left) and _literal_text(node.right)
    return False


def _targets(node: ast.AST) -> list[ast.expr]:
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, ast.AnnAssign | ast.AugAssign):
        return [node.target]
    return []


def _names_prompt(target: ast.expr) -> bool:
    return (isinstance(target, ast.Name) and target.id == NAME) or (
        isinstance(target, ast.Attribute) and target.attr == NAME
    )


def _system_content(node: ast.AST) -> tuple[bool, ast.expr | None]:
    """Whether ``node`` builds a system message, and its content expression."""
    if isinstance(node, ast.Dict):
        fields = {
            key.value: value
            for key, value in zip(node.keys, node.values, strict=True)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        role = fields.get("role")
        if isinstance(role, ast.Constant) and role.value == "system":
            return True, fields.get("content")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        fields = {k.arg: k.value for k in node.keywords if k.arg is not None}
        role = fields.get("role")
        if isinstance(role, ast.Constant) and role.value == "system":
            return True, fields.get("content")
    return False, None


def check(path: str, source: str) -> list[str]:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [f"FAIL {path}: cannot parse ({exc.msg}, line {exc.lineno})"]
    out: list[str] = []
    top = {id(node) for node in tree.body}
    bindings = 0
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if any(_names_prompt(t) for t in _targets(node)):
            bindings += 1
            value = getattr(node, "value", None)
            if id(node) not in top or isinstance(node, ast.AugAssign):
                out.append(f"FAIL {path}:{line}: {NAME} rebound after its definition")
            elif not _literal_text(value):
                out.append(f"FAIL {path}:{line}: {NAME} is not made of string literals")
        system, content = _system_content(node)
        if system and content is not None:
            literal = _literal_text(content)
            named = isinstance(content, ast.Name) and content.id == NAME
            if not (literal or named):
                out.append(
                    f"FAIL {path}:{line}: a system message's content is computed - "
                    f"dynamic data in the system prompt breaks the KV-cache prefix (I-13)"
                )
    if bindings > 1:
        out.append(f"FAIL {path}: {NAME} bound {bindings} times")
    return out


def main(paths: list[str]) -> int:
    failures: list[str] = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            failures.extend(check(path, handle.read()))
    for line in failures:
        print(line)
    if failures:
        return 1
    print("OK the system prompt is a constant (I-13)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
