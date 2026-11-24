"""Sealed files are only ever added: edits fail, except to DEVIATIONS.md and the .ots proofs."""

from __future__ import annotations

from scripts.audit.sealed_add_only import violations


def test_additions_and_the_two_editable_kinds_pass() -> None:
    diff = (
        "A\tdocs/truth/sealed/FREEZE-W.md\n"
        "A\tdocs/truth/sealed/SHA256SUMS-W\n"
        "M\tdocs/truth/sealed/DEVIATIONS.md\n"
        "M\tdocs/truth/sealed/SHA256SUMS.ots\n"
    )
    assert violations(diff) == []


def test_an_edit_or_a_removal_of_a_sealed_file_fails() -> None:
    for line in (
        "M\tdocs/truth/sealed/SHA256SUMS-W",
        "M\tdocs/truth/sealed/prereg-1.json",
        "D\tdocs/truth/sealed/PREREG-1.md",
        "D\tdocs/truth/sealed/SHA256SUMS.ots",
    ):
        assert violations(line + "\n") == [line]
