"""The kernel is light by measurement: what importing it loads, and what its source may touch.

A fresh interpreter imports every kernel module and reports every module that import loaded; the
third-party ones must be numpy and simpy (and what they import), and no repository module outside
``synapse_kernel`` may appear. Only modules the import ADDS are counted: the interpreter's own
start-up (``.pth`` hooks such as an editable install's finder) is not the kernel's doing. Measured
at run time, not read from import statements: a static reading misses a package ``__init__`` that
imports more than the module named (truth LOG M-37). The source is also scanned for environment
reads, which would make a run depend on where it runs (truth finding F-33).
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[2] / "synapse_kernel"
ALLOWED_THIRD_PARTY = frozenset({"numpy", "simpy"})
REPOSITORY_PACKAGES = frozenset(
    {
        "agents",
        "api",
        "data_fabric",
        "digital_twin",
        "ml_pipelines",
        "orchestrator",
        "scripts",
        "synapse_common",
        "tests",
        "uplift",
    }
)

_PROBE = """
import importlib, json, os, pkgutil, sys, sysconfig
before = set(sys.modules)
import synapse_kernel
for info in pkgutil.walk_packages(synapse_kernel.__path__, "synapse_kernel."):
    importlib.import_module(info.name)
stdlib = set(sys.stdlib_module_names)
purelib = os.path.normcase(sysconfig.get_paths()["purelib"])
platlib = os.path.normcase(sysconfig.get_paths()["platlib"])
third, loaded = set(), set()
for name, module in [(n, m) for n, m in sys.modules.items() if n not in before]:
    top = name.split(".")[0]
    loaded.add(top)
    path = os.path.normcase(getattr(module, "__file__", None) or "")
    if top not in stdlib and (path.startswith(purelib) or path.startswith(platlib)):
        third.add(top)
print(json.dumps({"third": sorted(third), "loaded": sorted(loaded)}))
"""


def _probe() -> dict[str, list[str]]:
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            f"import sys; sys.path.insert(0, {str(KERNEL.parent)!r})\n" + _PROBE,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, list[str]] = json.loads(done.stdout.strip().splitlines()[-1])
    return result


def test_importing_every_kernel_module_loads_only_numpy_and_simpy_from_outside() -> None:
    report = _probe()
    extra = sorted(set(report["third"]) - ALLOWED_THIRD_PARTY)
    assert not extra, f"the kernel pulls in third-party packages beyond numpy and simpy: {extra}"
    assert "numpy" in report["third"], "the probe saw no third-party package at all"


def test_importing_the_kernel_loads_no_other_repository_package() -> None:
    leaked = sorted(set(_probe()["loaded"]) & REPOSITORY_PACKAGES)
    assert not leaked, f"the kernel imports repository packages outside itself: {leaked}"


def test_no_kernel_source_reads_the_environment() -> None:
    offenders = []
    for path in sorted(KERNEL.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv", "environb"}:
                offenders.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Name) and node.id in {"environ", "getenv"}:
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, f"kernel code reads the environment at {offenders}"
