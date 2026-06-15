"""The outcome-truth gate must actually catch a fabricated outcome (Sprint 19).

A gate that passes on everything is theatre. These tests prove it flags a
hardcoded positive status and stays silent on honest derivation, and that the
real outcome-writing modules are clean.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_gate():
    spec = importlib.util.spec_from_file_location(
        "outcome_truth", ROOT / "scripts" / "audit" / "outcome_truth.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve the module (Py3.12+).
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_flags_fabricated_status_dict() -> None:
    gate = _load_gate()
    bad = 'def f():\n    return {"status": "confirmed", "source": "none"}\n'
    violations = gate._scan_source("x.py", bad)
    assert any(v.kind == "fabricated_outcome_dict" for v in violations)


def test_flags_fabricated_status_kwarg() -> None:
    gate = _load_gate()
    bad = "def f():\n    return dict(status='diverged')\n"
    violations = gate._scan_source("x.py", bad)
    assert any(v.kind == "fabricated_outcome_kwarg" for v in violations)


def test_allows_unknown_default_and_derived_status() -> None:
    gate = _load_gate()
    ok = (
        "def f(status):\n"
        "    verdict = 'diverged' if cond else 'confirmed'\n"
        '    return {"status": status, "fallback": "unknown"}\n'
    )
    violations = gate._scan_source("x.py", ok)
    assert violations == []


def test_real_modules_are_clean() -> None:
    gate = _load_gate()
    assert gate.run(check=True) == 0
