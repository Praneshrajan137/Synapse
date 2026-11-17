"""Session-2 instrument: third-party imports reachable from the twin and the decision path.

Walks the repository's own modules by AST from a set of entry modules, follows imports that
resolve inside the repository (or its `packages/` folder), and lists every third-party top-level
package reached, with the first repository module that imports it. Read-only.

Usage: python import_closure.py <tree> <entry.module> [<entry.module> ...]
"""
from __future__ import annotations

import ast
import pathlib
import sys

tree = pathlib.Path(sys.argv[1]).resolve()
roots = [tree, tree / "packages"]
stdlib = set(sys.stdlib_module_names)


def resolve(mod: str) -> pathlib.Path | None:
    parts = mod.split(".")
    for root in roots:
        base = root.joinpath(*parts)
        if (base.with_suffix(".py")).is_file():
            return base.with_suffix(".py")
        if (base / "__init__.py").is_file():
            return base / "__init__.py"
    return None


def package_of(path: pathlib.Path) -> str:
    rel = None
    for root in roots:
        try:
            rel = path.relative_to(root)
            break
        except ValueError:
            continue
    assert rel is not None
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


seen: set[pathlib.Path] = set()
third: dict[str, str] = {}
type_only: dict[str, str] = {}
queue = [m for m in sys.argv[2:]]
while queue:
    mod = queue.pop()
    path = resolve(mod)
    if path is None or path in seen:
        continue
    seen.add(path)
    src = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current = package_of(path)
    guarded: set[int] = set()
    for node in ast.walk(src):
        if isinstance(node, ast.If):
            test = ast.unparse(node.test)
            if "TYPE_CHECKING" in test:
                for sub in ast.walk(node):
                    guarded.add(id(sub))
    for node in ast.walk(src):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = current.split(".")
                if not path.name == "__init__.py":
                    base = base[:-1]
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                prefix = ".".join(base)
                target = f"{prefix}.{node.module}" if node.module else prefix
                names = [target] + [f"{target}.{a.name}" for a in node.names]
            elif node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        for name in names:
            top = name.split(".")[0]
            if resolve(name) is not None:
                queue.append(name)
            elif resolve(top) is not None:
                continue
            elif top in stdlib or top == "__future__":
                continue
            else:
                bucket = type_only if id(node) in guarded else third
                bucket.setdefault(top, package_of(path))

print(f"repository modules reached: {len(seen)}")
print("third-party packages imported at run time (package <- first importer):")
for k in sorted(third):
    print(f"  {k:22} <- {third[k]}")
only_typed = sorted(set(type_only) - set(third))
if only_typed:
    print("imported only under TYPE_CHECKING:", ", ".join(only_typed))
