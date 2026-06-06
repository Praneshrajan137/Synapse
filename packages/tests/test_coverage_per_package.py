from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.coverage_per_package import evaluate

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_coverage_attribution_uses_the_real_source_root(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    _write(project / "packages" / "synapse_common" / "budget.py", "x = 1\n")
    _write(project / "orchestrator" / "state_machine.py", "x = 1\n")

    xml = tmp_path / "coverage.xml"
    xml.write_text(
        f"""<?xml version="1.0" ?>
<coverage>
  <sources>
    <source>{project / "packages" / "synapse_common"}</source>
    <source>{project / "orchestrator"}</source>
  </sources>
  <packages>
    <package name=".">
      <classes>
        <class name="budget.py" filename="budget.py">
          <lines><line number="1" hits="1"/></lines>
        </class>
        <class name="state_machine.py" filename="state_machine.py">
          <lines><line number="1" hits="0"/></lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
""",
        encoding="utf-8",
    )
    floors = tmp_path / "floors.yaml"
    floors.write_text(
        """
target: 84.0
packages:
  packages/synapse_common:
    line: 0.0
  orchestrator:
    line: 0.0
""",
        encoding="utf-8",
    )

    results = {result.package: result for result in evaluate(xml, floors)}

    assert results["packages/synapse_common"].statements_total == 1
    assert results["packages/synapse_common"].statements_covered == 1
    assert results["packages/synapse_common"].measured_combined_pct == 100.0
    assert results["orchestrator"].statements_total == 1
    assert results["orchestrator"].statements_covered == 0
    assert results["orchestrator"].measured_combined_pct == 0.0
