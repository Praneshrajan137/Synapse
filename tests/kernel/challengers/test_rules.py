"""The rules every challenger module obeys, read from its source (truth session 6, gate items 8-10).

A challenger decides on the frozen world in a process of its own, but ``integrity`` itself imports
the world's scenario, engine and random streams into that process (the gate's attack, finding 13),
so a process boundary alone cannot keep the simulator out of a challenger's reach. These rules do:

* **imports** only from an allowlist: numpy, a few standard-library modules, the challengers' own
  package, and the frozen kernel modules a policy may use (the observation, the world's declared
  types, the incumbent, the guard, the exact sampler, the Sentinel's newsvendor);
* **no reflection or escape**: no ``open``, ``eval``, ``exec``, ``compile``, ``getattr``,
  ``setattr``, ``vars``, ``globals``, ``__import__``, ``global`` or ``nonlocal``, and no dunder
  attribute but ``__init__``;
* **exact arithmetic**: no libm transcendental, no float reduction, no BLAS, no ``**`` but by a
  whole-number literal (the exact helpers in ``exact.py`` are the one place allowed to reduce);
* **no memory across replicates**: module and class bodies bind only constants and functions; no
  mutable default argument; no cache decorator.

Each rule is shown failing on a planted violation in ``test_each_rule_catches_its_plant``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[3] / "synapse_kernel" / "challengers"

ALLOWED_IMPORTS = frozenset(
    {
        "__future__",
        "typing",
        "dataclasses",
        "math",
        "collections.abc",
        "numpy",
        "numpy.typing",
        "synapse_kernel.release.observation",
        "synapse_kernel.release.world",
        "synapse_kernel.release.incumbent",
        "synapse_kernel.release.guard",
        "synapse_kernel.policies.sentinel",
    }
)
#: The exact sampler is reached only through ``exact.py``.
EXACT_ONLY_IMPORTS = frozenset({"synapse_kernel.release.sampling"})
FORBIDDEN_NAMES = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "getattr",
        "setattr",
        "delattr",
        "vars",
        "globals",
        "locals",
        "__import__",
        "input",
        "breakpoint",
        "memoryview",
    }
)
#: numpy and math calls whose bits are not fixed across platforms, or that reduce floats.
FORBIDDEN_CALLS = frozenset(
    {
        "exp",
        "exp2",
        "expm1",
        "log",
        "log2",
        "log10",
        "log1p",
        "power",
        "float_power",
        "pow",
        "sum",
        "mean",
        "average",
        "prod",
        "dot",
        "vdot",
        "matmul",
        "inner",
        "einsum",
        "tensordot",
        "var",
        "std",
        "nansum",
        "nanmean",
        "sin",
        "cos",
        "tan",
        "tanh",
        "arctan",
        "erf",
        "gamma",
        "lgamma",
    }
)
FORBIDDEN_ATTRIBUTES = frozenset({"linalg", "random", "fft"})
CACHE_DECORATORS = frozenset({"lru_cache", "cache", "cached_property"})


def _module_name(node: ast.ImportFrom) -> str:
    return node.module or ""


def violations(source: str, filename: str) -> list[str]:
    """Every rule broken by one module's source, as messages."""
    tree = ast.parse(source, filename)
    exact_module = filename.endswith("exact.py")
    found: list[str] = []
    allowed = ALLOWED_IMPORTS | (EXACT_ONLY_IMPORTS if exact_module else frozenset())

    def ok_import(name: str) -> bool:
        return name in allowed or name.startswith("synapse_kernel.challengers")

    # Imports under ``if TYPE_CHECKING:`` never run; they may name any type.
    typing_only = {
        id(inner)
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
        for inner in ast.walk(node)
    }
    for node in ast.walk(tree):
        if id(node) in typing_only and isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if isinstance(node, ast.Import):
            found += [f"import {a.name}" for a in node.names if not ok_import(a.name)]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and not ok_import(_module_name(node)):
                found.append(f"from {_module_name(node)} import")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            found.append(f"name {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__") and node.attr != "__init__":
                found.append(f"attribute {node.attr}")
            if node.attr in FORBIDDEN_ATTRIBUTES:
                found.append(f"attribute {node.attr}")
        elif isinstance(node, ast.Global | ast.Nonlocal):
            found.append("global or nonlocal")
        elif isinstance(node, ast.Call) and not exact_module:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in FORBIDDEN_CALLS:
                found.append(f"call {name}")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and not exact_module:
            right = node.right
            if not (isinstance(right, ast.Constant) and isinstance(right.value, int)):
                found.append("** by a non-literal or non-whole power")
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for default in [*node.args.defaults, *node.args.kw_defaults]:
                if isinstance(default, ast.List | ast.Dict | ast.Set | ast.Call):
                    found.append(f"mutable default in {node.name}")
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                label = (
                    target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
                )
                if label in CACHE_DECORATORS:
                    found.append(f"cache decorator on {node.name}")
    found += _state_violations(tree)
    return found


def _mutable(value: ast.expr | None) -> bool:
    if value is None:
        return False
    if isinstance(value, ast.List | ast.Dict | ast.Set | ast.ListComp | ast.DictComp | ast.SetComp):
        return True
    if isinstance(value, ast.Call):
        func = value.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        return name not in {"frozenset", "tuple", "Final", "TypeVar", "NewType"}
    return False


def _state_violations(tree: ast.Module) -> list[str]:
    """Module and class bodies bind only constants, types and functions."""
    found: list[str] = []
    bodies: list[tuple[str, list[ast.stmt]]] = [("module", tree.body)]
    bodies += [(f"class {n.name}", n.body) for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    for where, body in bodies:
        for stmt in body:
            if isinstance(stmt, ast.Assign | ast.AnnAssign) and _mutable(stmt.value):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                if [getattr(t, "id", "") for t in targets] == ["__all__"]:
                    continue  # the export list is read by tools, never written by a policy
                found.append(f"mutable state in {where}")
    return found


def _modules() -> list[Path]:
    return sorted(PACKAGE.glob("*.py"))


@pytest.mark.parametrize("path", _modules(), ids=lambda p: p.name)
def test_every_challenger_module_obeys_the_rules(path: Path) -> None:
    assert violations(path.read_text(encoding="utf-8"), path.name) == []


def test_the_package_is_not_empty() -> None:
    assert len(_modules()) >= 4


PLANTS = {
    "the scenario imported": "from synapse_kernel.release.scenario import build_scenario\n",
    "integrity imported": "import synapse_kernel.release.integrity\n",
    "the engine imported beside a typing block": (
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\n"
        "from synapse_kernel.release.engine import run\n"
    ),
    "the engine imported": "from synapse_kernel.release import engine\n",
    "the system module": "import sys\n",
    "garbage collector": "import gc\n",
    "getattr by name": "x = getattr(object, 'a' + 'b')\n",
    "a file opened": "def f() -> None:\n    open('x')\n",
    "eval": "def f() -> None:\n    eval('1')\n",
    "a dunder walk": "def f(o: object) -> object:\n    return o.__class__\n",
    "globals": "def f() -> object:\n    return globals()\n",
    "a global statement": "def f() -> None:\n    global X\n",
    "libm exp": "import numpy as np\ndef f(x: float) -> float:\n    return float(np.exp(x))\n",
    "a float sum": "import numpy as np\ndef f(x: object) -> object:\n    return np.sum(x)\n",
    "a method reduction": "def f(x: object) -> object:\n    return x.mean()\n",
    "BLAS": "import numpy as np\ndef f(a: object, b: object) -> object:\n    return np.dot(a, b)\n",
    "numpy random": "import numpy as np\ndef f() -> object:\n    return np.random.default_rng()\n",
    "a fractional power": "def f(x: float) -> float:\n    return x ** 0.5\n",
    "module-level memory": "SEEN = []\n",
    "a class-level cache": "class A:\n    memo = {}\n",
    "a mutable default": "def f(x: list[int] = []) -> None:\n    pass\n",
    "a cache decorator": "import functools\n@functools.lru_cache\ndef f() -> int:\n    return 1\n",
}


@pytest.mark.parametrize("plant", sorted(PLANTS))
def test_each_rule_catches_its_plant(plant: str) -> None:
    assert violations(PLANTS[plant], "planted.py") != [], plant
