"""The pre-commit layer runs (TRUTH-MAP F-34, truth session 5 stage E).

The config parses and holds only local hooks; every hook that mirrors a CI step names a step
that exists and can run outside CI; every other hook is one ``hooks.yml`` runs over the tree,
except gitleaks, which reads the staged index; and each check this repository owns fails on a
planted violation and passes on the tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.hooks import (
    color_spec_validate,
    contract_validate,
    jitter_enforcement,
    kv_cache_check,
    run_ci_step,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".pre-commit-config.yaml"
MIRRORS = {
    "ruff-check",
    "ruff-format",
    "mypy-strict",
    "schema-validate",
    "spec-validate",
    "reward-isolation",
    "no-paid-apis",
    "spec-coverage",
    "no-raw-hex",
}
OWN = {"jitter-enforcement", "contract-validate", "kv-cache-check", "color-spec-validate"}
KV_FILES = (
    "orchestrator/llm/context_builder.py",
    "orchestrator/llm/ollama_client.py",
    "orchestrator/consensus/protocol.py",
)


def _hooks() -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return {hook["id"]: hook for repo in doc["repos"] for hook in repo["hooks"]}


def _planted_workflow(tmp_path: Path, step: dict[str, Any]) -> Path:
    path = tmp_path / "planted.yml"
    path.write_text(yaml.safe_dump({"jobs": {"job": {"steps": [step]}}}), encoding="utf-8")
    return path


# --- the layer -------------------------------------------------------------------------------


def test_the_config_parses_and_every_hook_is_local() -> None:
    doc = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert [repo["repo"] for repo in doc["repos"]] == ["local"]
    assert set(_hooks()) == MIRRORS | OWN | {"gitleaks"}


def test_every_mirror_names_a_ci_step_that_runs_outside_ci() -> None:
    assert {hook for hook, _ in run_ci_step.mirrors()} == MIRRORS
    assert run_ci_step.check() == len(MIRRORS) + 1  # mypy-strict mirrors two steps


def test_the_hooks_job_runs_every_hook_no_other_job_runs() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/hooks.yml").read_text(encoding="utf-8"))
    runs = "\n".join(step.get("run", "") for step in workflow["jobs"]["hooks"]["steps"])
    assert 'SKIP="$(python scripts/hooks/run_ci_step.py --mirrors),gitleaks"' in runs
    assert "pre-commit run --all-files" in runs
    for hook in OWN:
        assert _hooks()[hook].get("stages") is None, f"{hook} must run at the default stage"


# --- the mirror runner -------------------------------------------------------------------


def test_a_mirror_fails_when_its_step_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _planted_workflow(tmp_path, {"name": "planted", "run": "echo planted\nexit 3"})
    monkeypatch.setattr(run_ci_step, "ROOT", tmp_path)
    assert run_ci_step.run_steps("planted.yml", "job", ["planted"]) == 3


def test_a_missing_or_unrunnable_step_is_refused(tmp_path: Path) -> None:
    path = _planted_workflow(tmp_path, {"name": "planted", "run": "true"})
    with pytest.raises(run_ci_step.StepError, match="0 steps"):
        run_ci_step.find_step(path, "job", "renamed")
    with pytest.raises(run_ci_step.StepError, match="no job"):
        run_ci_step.find_step(path, "other", "planted")
    for step, why in (
        ({"name": "planted", "uses": "actions/checkout@v4"}, "no run"),
        ({"name": "planted", "run": "echo ${{ github.sha }}"}, "expression"),
        ({"name": "planted", "run": "true", "working-directory": "x"}, "working-directory"),
    ):
        with pytest.raises(run_ci_step.StepError, match=why):
            run_ci_step.find_step(_planted_workflow(tmp_path, step), "job", "planted")


# --- jitter-enforcement --------------------------------------------------------------------

FIXED = "import time\n\n\ndef poll():\n    while True:\n        time.sleep(5)\n"


def test_jitter_fails_an_unmarked_fixed_sleep() -> None:
    assert jitter_enforcement.check("x.py", FIXED)
    assert jitter_enforcement.check("x.py", "from time import sleep as nap\n\nnap(1)\n")
    assert jitter_enforcement.check("x.py", "import time as t\n\nt.sleep(1)\n")


def test_jitter_passes_marked_and_jittered_sleeps() -> None:
    marked = FIXED.replace(
        "        time.sleep(5)", "        # not-a-retry: a periodic loop\n        time.sleep(5)"
    )
    jittered = "import time\n\ntime.sleep(full_jitter_delay(0.05, 2, cap=0.5))\n"
    through_a_name = "import time\n\ndelay = full_jitter_delay(0.05, 2)\ntime.sleep(delay)\n"
    fixed_name = "import time\n\ndelay = 5\ntime.sleep(delay)\n"
    assert jitter_enforcement.check("x.py", marked) == []
    assert jitter_enforcement.check("x.py", jittered) == []
    assert jitter_enforcement.check("x.py", through_a_name) == []
    assert jitter_enforcement.check("x.py", fixed_name)


def test_jitter_skips_test_files_only() -> None:
    assert jitter_enforcement.is_test("agents/a/tests/helpers.py")
    assert jitter_enforcement.is_test("scripts/test_thing.py")
    assert not jitter_enforcement.is_test("scripts/deploy/verify_live.py")


# --- contract-validate ---------------------------------------------------------------------


def test_a_contract_without_a_pydantic_type_fails(tmp_path: Path) -> None:
    source = "import pytest\n\n\ndef test_x() -> None:\n    assert True\n"
    assert contract_validate.check("agents/a/contracts/b_contract.py", source, tmp_path)


def test_a_contract_typed_by_a_shared_or_repository_model_passes(tmp_path: Path) -> None:
    producer = tmp_path / "agents" / "p" / "inference"
    producer.mkdir(parents=True)
    (producer / "pipeline.py").write_text(
        "from pydantic import BaseModel\n\n\nclass Base(BaseModel):\n    pass\n\n\n"
        "class Request(Base):\n    pass\n\n\nclass Plain:\n    pass\n",
        encoding="utf-8",
    )
    typed = "def test_x() -> None:\n    from agents.p.inference.pipeline import Request\n"
    plain = typed.replace("Request", "Plain")
    shared = "from synapse_common.models import RoutePlan\n"
    path = "agents/a/contracts/p_contract.py"
    assert contract_validate.check(path, typed, tmp_path) == []
    assert contract_validate.check(path, shared, tmp_path) == []
    assert contract_validate.check(path, plain, tmp_path)


# --- kv-cache-check ------------------------------------------------------------------------

PROMPT = (
    'SYSTEM_PROMPT: str = ("a" "b")\n\n\n'
    "def build(x):\n"
    '    return [{"role": "system", "content": SYSTEM_PROMPT}, '
    '{"role": "user", "content": f"{x}"}]\n'
)


def test_kv_cache_passes_a_literal_prompt_and_dynamic_user_messages() -> None:
    assert kv_cache_check.check("c.py", PROMPT) == []


def test_kv_cache_fails_dynamic_data_in_the_system_prompt() -> None:
    planted = (
        PROMPT.replace('("a" "b")', 'f"now {x}"'),
        PROMPT.replace('"content": SYSTEM_PROMPT}', '"content": SYSTEM_PROMPT + str(1)}'),
        PROMPT.replace(
            '{"role": "system", "content": SYSTEM_PROMPT}',
            'dict(role="system", content=f"{x}")',
        ),
        PROMPT + "\n\ndef later():\n    global SYSTEM_PROMPT\n    SYSTEM_PROMPT = 'x'\n",
    )
    for source in planted:
        assert kv_cache_check.check("c.py", source), source


def test_kv_cache_passes_the_three_files_it_guards() -> None:
    for name in KV_FILES:
        assert kv_cache_check.check(name, (ROOT / name).read_text(encoding="utf-8")) == []


# --- color-spec-validate -------------------------------------------------------------------


def test_the_colour_spec_conforms_to_its_schema() -> None:
    assert color_spec_validate.errors() == []


def test_a_precondition_left_inside_the_invariants_fails(tmp_path: Path) -> None:
    text = color_spec_validate.SPEC.read_text(encoding="utf-8")
    assert "\npreconditions:\n" in text
    planted = tmp_path / "spec.yml"
    planted.write_text(text.replace("\npreconditions:\n", "\n"), encoding="utf-8")
    found = color_spec_validate.errors(planted)
    assert any("PRE-CLR-001" in line for line in found)
