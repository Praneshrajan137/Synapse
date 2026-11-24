"""The release world calls no function whose bits differ across platforms (truth finding F-36).

numpy's ``Generator`` distributions may change between numpy versions and CPUs, and libm's
transcendental functions are not correctly rounded everywhere; Pyodide ships its own builds of
both. So no module of the release world may call them: draws come from
:mod:`synapse_kernel.release.rng` (integer arithmetic) and samplers from
:mod:`synapse_kernel.release.sampling` (+ - * / and powers of two). ``sqrt``, ``floor``, ``ceil``,
``ldexp``, ``fsum`` and ``factorial`` are exact and allowed.
"""

from __future__ import annotations

import ast
from pathlib import Path

RELEASE = Path(__file__).resolve().parents[3] / "synapse_kernel" / "release"
FORBIDDEN = frozenset(
    {
        "exp",
        "expm1",
        "log",
        "log1p",
        "log2",
        "log10",
        "pow",
        "power",
        "float_power",
        "lgamma",
        "gamma",
        "erf",
        "erfc",
        "sin",
        "cos",
        "tan",
        "tanh",
        "random",
        "default_rng",
        "Generator",
        "SeedSequence",
        "RandomState",
    }
)


def _offences(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN:
            base = node.value
            name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
            if name in {"math", "np", "numpy", "random", "cmath"}:
                found.append(f"{path.name}:{node.lineno} {name}.{node.attr}")
        if isinstance(node, ast.Import):
            found += [
                f"{path.name}:{node.lineno} import {a.name}"
                for a in node.names
                if a.name == "random"
            ]
        if isinstance(node, ast.ImportFrom) and (node.module or "") in {"random", "numpy.random"}:
            found.append(f"{path.name}:{node.lineno} from {node.module}")
    return found


def test_no_release_module_calls_a_platform_dependent_function() -> None:
    offences = [o for path in sorted(RELEASE.rglob("*.py")) for o in _offences(path)]
    assert not offences, offences


def test_the_scan_sees_an_offence_when_one_is_planted(tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import math\nimport numpy as np\nx = math.exp(1.0)\ny = np.random.default_rng(1)\n",
        encoding="utf-8",
    )
    found = _offences(planted)
    assert any("math.exp" in o for o in found) and any("np.random" in o for o in found)
