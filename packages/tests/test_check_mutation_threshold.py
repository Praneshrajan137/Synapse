from __future__ import annotations

import sqlite3
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureFixture
    from pytest import MonkeyPatch

from scripts import check_mutation_threshold


def _write_cache(path: Path, statuses: list[str], table: str = "Mutant") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(f'CREATE TABLE "{table}" (status TEXT NOT NULL)')
        conn.executemany(
            f'INSERT INTO "{table}" (status) VALUES (?)',
            [(status,) for status in statuses],
        )
        conn.commit()
    finally:
        conn.close()


def test_reads_mutmut_2_file_cache(tmp_path: Path) -> None:
    cache = tmp_path / ".mutmut-cache"
    _write_cache(
        cache,
        [
            "bad_survived",
            "ok_suspicious",
            "ok_killed",
            "bad_timeout",
            "untested",
            "skipped",
        ],
    )

    assert check_mutation_threshold.survival_rate_from_cache(cache) == (2, 4)


def test_reads_legacy_directory_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / ".mutmut-cache"
    _write_cache(cache_dir / "mutants.db", ["bad_survived", "ok_killed"], table="mutant")

    assert check_mutation_threshold.survival_rate_from_cache(cache_dir) == (1, 2)


def test_legacy_db_argument_falls_back_to_file_cache(tmp_path: Path) -> None:
    cache = tmp_path / ".mutmut-cache"
    _write_cache(cache, ["bad_survived", "ok_killed"])

    assert check_mutation_threshold.survival_rate_from_cache(cache / "mutants.db") == (1, 2)


def test_missing_cache_fails_closed(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_mutation_threshold.py",
            "--threshold",
            "15",
            "--label",
            "example",
        ],
    )

    assert check_mutation_threshold.main() == 1
    captured = capsys.readouterr()
    assert "example" in captured.err
    assert "FAIL" in captured.err


def test_threshold_breach_fails(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    cache = tmp_path / ".mutmut-cache"
    _write_cache(cache, ["bad_survived", "ok_killed"])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_mutation_threshold.py",
            "--cache",
            str(cache),
            "--threshold",
            "15",
            "--label",
            "example",
        ],
    )

    assert check_mutation_threshold.main() == 1
