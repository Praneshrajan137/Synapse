"""Unit tests for measured-floor enforcement (spec purpose-achievement-audit task 4.1).

Covers the three-way floor verdict in `scripts/coverage_per_package.py`
(R7.1, R7.2) and the provenance record `scripts/coverage_ratchet.py --apply`
writes beside each bumped floor (R7.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

from scripts.coverage_per_package import (
    FAILING_STATUSES,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_SKIP_UNMEASURED,
    STATUS_VACUOUS,
    evaluate,
)
from scripts.coverage_ratchet import (
    FloorProvenance,
    ProvenanceUnavailable,
    resolve_provenance,
    rewrite_floor_entry,
)

if TYPE_CHECKING:
    from pathlib import Path

_XML = """<?xml version="1.0" ?>
<coverage>
  <packages>
    <package name=".">
      <classes>
        <class name="mod.py" filename="pkg_a/mod.py">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""


def _report(tmp_path: Path) -> Path:
    xml = tmp_path / "coverage.xml"
    xml.write_text(_XML, encoding="utf-8")
    return xml


def _floors(tmp_path: Path, body: str) -> Path:
    floors = tmp_path / "floors.yaml"
    floors.write_text(f"target: 84.0\npackages:\n{body}", encoding="utf-8")
    return floors


def _status(tmp_path: Path, body: str, *, require: bool) -> dict[str, object]:
    results = evaluate(
        _report(tmp_path), _floors(tmp_path, body), require_measured_floors=require
    )
    result = next(r for r in results if r.package == "pkg_a")
    return {"status": result.status, "detail": result.detail}


def test_zero_floor_with_a_recorded_measurement_is_vacuous_and_fails(tmp_path: Path) -> None:
    verdict = _status(
        tmp_path,
        '  pkg_a:\n    line: 0.0\n    measured_at: "2026-05-30T09:14:00Z"\n'
        '    source_run: "gh-run-42"\n',
        require=True,
    )
    assert verdict["status"] == STATUS_VACUOUS
    assert STATUS_VACUOUS in FAILING_STATUSES
    assert "2026-05-30T09:14:00Z" in str(verdict["detail"])
    assert "gh-run-42" in str(verdict["detail"])


def test_zero_floor_without_a_measurement_skips_and_never_passes(tmp_path: Path) -> None:
    verdict = _status(tmp_path, "  pkg_a:\n    line: 0.0\n    measured_at: null\n", require=True)
    assert verdict["status"] == STATUS_SKIP_UNMEASURED
    assert verdict["status"] not in FAILING_STATUSES
    assert verdict["status"] != STATUS_PASS


def test_absent_provenance_key_reads_as_unmeasured(tmp_path: Path) -> None:
    verdict = _status(tmp_path, "  pkg_a:\n    line: 0.0\n", require=True)
    assert verdict["status"] == STATUS_SKIP_UNMEASURED


def test_bare_yaml_date_counts_as_a_recorded_measurement(tmp_path: Path) -> None:
    # PyYAML resolves an unquoted 2026-05-29 to a datetime.date; it must still
    # read as "something measured this", not as an absent measurement.
    verdict = _status(tmp_path, "  pkg_a:\n    line: 0.0\n    measured_at: 2026-05-29\n", require=True)
    assert verdict["status"] == STATUS_VACUOUS


def test_below_floor_names_the_measured_value_and_the_floor(tmp_path: Path) -> None:
    verdict = _status(tmp_path, "  pkg_a:\n    line: 80.0\n", require=True)
    assert verdict["status"] == STATUS_FAIL
    assert "50.00%" in str(verdict["detail"])
    assert "80.0%" in str(verdict["detail"])


def test_without_the_flag_a_zero_floor_behaves_as_before(tmp_path: Path) -> None:
    verdict = _status(
        tmp_path,
        '  pkg_a:\n    line: 0.0\n    measured_at: "2026-05-30T09:14:00Z"\n',
        require=False,
    )
    assert verdict["status"] == STATUS_PASS


# ---------------------------------------------------------------------------
# The ratchet side: what --apply writes
# ---------------------------------------------------------------------------

_FLOORS_TEXT = """target: 84.0

packages:
  packages/synapse_common:
    line: 0.0
    target: 84.0
    note: "CI-MUST-MEASURE -- torch absent locally."

  # a comment between entries
  orchestrator:
    line: 30.0
    target: 84.0
"""


def test_apply_writes_measured_at_and_source_run_beside_the_bumped_floor() -> None:
    provenance = FloorProvenance(measured_at="2026-05-30T09:14:00Z", source_run="gh-run-42")

    updated = rewrite_floor_entry(
        _FLOORS_TEXT, "packages/synapse_common", 61.5, provenance
    )

    doc = yaml.safe_load(updated)
    entry = doc["packages"]["packages/synapse_common"]
    assert entry["line"] == 61.5
    assert entry["measured_at"] == "2026-05-30T09:14:00Z"
    assert entry["source_run"] == "gh-run-42"
    # Comments, sibling entries and the note survive the text edit.
    assert "# a comment between entries" in updated
    assert "CI-MUST-MEASURE" in updated
    assert doc["packages"]["orchestrator"]["line"] == 30.0
    assert "measured_at" not in doc["packages"]["orchestrator"]


def test_reapplying_overwrites_provenance_in_place() -> None:
    first = rewrite_floor_entry(
        _FLOORS_TEXT,
        "packages/synapse_common",
        61.5,
        FloorProvenance(measured_at="2026-05-30T09:14:00Z", source_run="gh-run-42"),
    )
    second = rewrite_floor_entry(
        first,
        "packages/synapse_common",
        70.0,
        FloorProvenance(measured_at="2026-06-01T00:00:00Z", source_run="gh-run-99"),
    )

    entry = yaml.safe_load(second)["packages"]["packages/synapse_common"]
    assert entry["line"] == 70.0
    assert entry["measured_at"] == "2026-06-01T00:00:00Z"
    assert entry["source_run"] == "gh-run-99"
    assert second.count("measured_at:") == 1
    assert second.count("source_run:") == 1


def test_a_bump_without_a_run_is_refused_rather_than_invented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    with pytest.raises(ProvenanceUnavailable):
        resolve_provenance()


def test_the_github_run_id_supplies_the_source_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_RUN_ID", "1234567890")
    provenance = resolve_provenance(measured_at="2026-05-30T09:14:00Z")
    assert provenance.source_run == "gh-run-1234567890"
    assert provenance.measured_at == "2026-05-30T09:14:00Z"
