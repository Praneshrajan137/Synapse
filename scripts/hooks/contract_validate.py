"""A consumer-driven contract types its expectation with Pydantic (the ``contract-validate`` hook).

A contract module (``agents/<consumer>/contracts/<producer>_contract.py``, the files the
``contracts`` job of ``integration.yml`` runs) passes when it imports from ``synapse_common`` (the
shared models), defines a ``BaseModel`` or ``RootModel`` class, or imports, anywhere in the module,
a name that the repository's own source defines as such a class (followed through the bases
defined in the same module). Package ``__init__`` files are not contracts.

The first version (May to November 2026) matched every path containing ``contracts/``, package
inits and ``tests/contracts`` included, and did not follow imports, so 17 of its 23 files failed;
it never ran (TRUTH-MAP F-34, truth session 5).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
PYDANTIC: Final[frozenset[str]] = frozenset({"BaseModel", "RootModel"})


def _base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Subscript):  # RootModel[list[X]]
        base = base.value
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return ""


def _pydantic_classes(tree: ast.Module) -> set[str]:
    """Classes of ``tree`` that derive, through classes of the same module, from Pydantic."""
    bases = {
        node.name: {_base_name(b) for b in node.bases}
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }
    found = {name for name, names in bases.items() if names & PYDANTIC}
    changed = True
    while changed:
        grown = {name for name, names in bases.items() if names & found} - found
        changed = bool(grown)
        found |= grown
    return found


def _module_source(module: str, root: Path) -> Path | None:
    stem = root.joinpath(*module.split("."))
    for candidate in (stem.with_suffix(".py"), stem / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def check(path: str, source: str, root: Path = ROOT) -> list[str]:
    """Why ``source`` fails the rule, or nothing."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [f"FAIL {path}: cannot parse ({exc.msg}, line {exc.lineno})"]
    if _pydantic_classes(tree):
        return []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module or node.level:
            continue
        if node.module == "synapse_common" or node.module.startswith("synapse_common."):
            return []
        imported = {alias.name for alias in node.names}
        origin = _module_source(node.module, root)
        if origin is not None:
            other = ast.parse(origin.read_text(encoding="utf-8"), filename=str(origin))
            if imported & _pydantic_classes(other):
                return []
    return [
        f"FAIL {path}: a contract module must import from synapse_common, define a Pydantic "
        "model, or import one the repository defines (consumer-driven contracts)"
    ]


def main(paths: list[str]) -> int:
    failures: list[str] = []
    for path in paths:
        if Path(path).name == "__init__.py":
            continue
        with open(path, encoding="utf-8") as handle:
            failures.extend(check(path, handle.read()))
    for line in failures:
        print(line)
    if failures:
        return 1
    print("OK every contract module types its expectation with Pydantic")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
