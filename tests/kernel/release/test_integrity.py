"""Freeze W's run-time check refuses a changed file, or a binding replaced, changed or added."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import numpy as np
import pytest

from synapse_kernel.release import (
    cells,
    engine,
    incumbent,
    integrity,
    objective,
    sampling,
    world,
)


def _sums(tmp_path: Path, files: dict[str, bytes]) -> Path:
    lines = []
    for name, data in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        lines.append(f"{hashlib.sha256(data).hexdigest()} *{name}")
    sums = tmp_path / "SHA256SUMS-W"
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sums


def _listing(tmp_path: Path, name: str, source: Path) -> Path:
    """A sums file listing ``name`` with the canonical digest of the real ``source``."""
    data = source.read_bytes().replace(b"\r\n", b"\n")
    sums = tmp_path / "SHA256SUMS-W"
    sums.write_text(f"{hashlib.sha256(data).hexdigest()} *{name}\n", encoding="utf-8")
    return sums


def test_unchanged_files_and_bindings_pass(tmp_path: Path) -> None:
    sums = _sums(tmp_path, {"a/x.py": b"x = 1\n", "b.json": b"{}"})
    assert integrity.assert_frozen(sums, tmp_path) == 2


def test_every_release_module_is_watched() -> None:
    watched = {module.__name__ for module in integrity.FROZEN_MODULES}
    release = {name for name in watched if name.startswith("synapse_kernel.release.")}
    assert len(release) == 14 and "synapse_kernel.release.integrity" not in watched
    bindings = integrity.frozen_bindings()
    assert "synapse_kernel.release.incumbent.Incumbent.decide" in bindings
    assert "synapse_kernel.release.incumbent.Incumbent.__init__" in bindings


def test_an_edited_frozen_file_is_refused(tmp_path: Path) -> None:
    sums = _sums(tmp_path, {"a/x.py": b"x = 1\n"})
    (tmp_path / "a" / "x.py").write_bytes(b"x = 2\n")
    with pytest.raises(integrity.FrozenKernelError, match="is not freeze W's"):
        integrity.assert_frozen(sums, tmp_path)


def test_a_missing_frozen_file_is_refused(tmp_path: Path) -> None:
    sums = _sums(tmp_path, {"a/x.py": b"x = 1\n"})
    (tmp_path / "a" / "x.py").unlink()
    with pytest.raises(integrity.FrozenKernelError, match="missing"):
        integrity.assert_frozen(sums, tmp_path)


def test_a_crlf_checkout_has_the_same_digest(tmp_path: Path) -> None:
    sums = _sums(tmp_path, {"a/x.py": b"x = 1\ny = 2\n"})
    (tmp_path / "a" / "x.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    assert integrity.assert_frozen(sums, tmp_path) == 1


@pytest.mark.parametrize(
    ("owner", "name", "value"),
    [
        (engine, "run", lambda *args, **kwargs: None),
        (objective, "PRIMARY", objective.Weights(margin=0.5, beyond=0.0, carrying=0.25)),
        (cells, "CELLS", ("N",)),
        (sampling, "MAX_MEAN", 1.0),
        (incumbent.Incumbent, "decide", lambda self, obs: None),
        (incumbent.Incumbent, "__init__", lambda self, *args: None),
    ],
)
def test_a_binding_replaced_in_memory_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owner: object, name: str, value: object
) -> None:
    sums = _sums(tmp_path, {"a/x.py": b"x = 1\n"})
    monkeypatch.setattr(owner, name, value)
    with pytest.raises(integrity.FrozenKernelError, match="replaced in memory"):
        integrity.assert_frozen(sums, tmp_path)


def test_a_frozen_dataclass_changed_through_object_setattr_is_refused(tmp_path: Path) -> None:
    sums = _sums(tmp_path, {"a/x.py": b"x = 1\n"})
    weights = objective.PRIMARY
    saved = weights.margin
    object.__setattr__(weights, "margin", 0.5)
    try:
        with pytest.raises(integrity.FrozenKernelError, match="changed in place"):
            integrity.assert_frozen(sums, tmp_path)
    finally:
        object.__setattr__(weights, "margin", saved)
    assert integrity.assert_frozen(sums, tmp_path) == 1


def test_a_functions_defaults_or_code_changed_in_place_are_refused(tmp_path: Path) -> None:
    sums = _sums(tmp_path, {"a/x.py": b"x = 1\n"})
    loader = world.load_release_world
    defaults, code = loader.__defaults__, sampling.exp_neg.__code__
    loader.__defaults__ = (Path("elsewhere.json"),)
    try:
        with pytest.raises(integrity.FrozenKernelError, match="changed in place"):
            integrity.assert_frozen(sums, tmp_path)
    finally:
        loader.__defaults__ = defaults
    sampling.exp_neg.__code__ = (lambda x: x).__code__
    try:
        with pytest.raises(integrity.FrozenKernelError, match="changed in place"):
            integrity.assert_frozen(sums, tmp_path)
    finally:
        sampling.exp_neg.__code__ = code
    assert integrity.assert_frozen(sums, tmp_path) == 1


def test_a_name_added_to_a_module_or_a_class_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sums = _sums(tmp_path, {"a/x.py": b"x = 1\n"})
    monkeypatch.setattr(engine, "min", lambda *args: 0, raising=False)  # would shadow a builtin
    with pytest.raises(integrity.FrozenKernelError, match="added in memory"):
        integrity.assert_frozen(sums, tmp_path)
    monkeypatch.undo()
    monkeypatch.setattr(
        incumbent.Incumbent, "__getattribute__", object.__getattribute__, raising=False
    )
    with pytest.raises(integrity.FrozenKernelError, match="added in memory"):
        integrity.assert_frozen(sums, tmp_path)


def test_the_in_place_check_compares_contents() -> None:
    # The release modules bind no mutable container today, so the comparison is shown on its own.
    table = {"a": 1}
    kept = integrity._state(table)
    assert kept is not None and integrity._same(kept, integrity._state(table))
    table["a"] = 2
    assert not integrity._same(kept, integrity._state(table))


def test_a_world_altered_in_memory_is_refused(tmp_path: Path) -> None:
    sums = _listing(tmp_path, integrity.WORLD_FILE, world.RELEASE_WORLD)
    loaded = world.load_release_world()
    integrity.assert_world_frozen(loaded, sums)
    first = dataclasses.replace(loaded.items[0], rate_per_day=loaded.items[0].rate_per_day + 1.0)
    altered = dataclasses.replace(loaded, items=(first, *loaded.items[1:]))
    with pytest.raises(integrity.FrozenKernelError, match="not freeze W's world"):
        integrity.assert_world_frozen(altered, sums)


def test_tables_altered_in_memory_are_refused(tmp_path: Path) -> None:
    sums = _listing(tmp_path, integrity.TABLES_FILE, incumbent.INCUMBENT_TABLES)
    root = incumbent.INCUMBENT_TABLES.parents[2]
    tables = incumbent.load_incumbent_tables()
    integrity.assert_tables_frozen(tables, sums, root)
    tables["I2-N"].factors[:] = 0.0  # a frozen dataclass's array, written in place
    with pytest.raises(integrity.FrozenKernelError, match="I2-N in memory are not freeze W's"):
        integrity.assert_tables_frozen(tables, sums, root)
    assert np.any(incumbent.load_incumbent_tables()["I2-N"].factors != 0.0)


def test_a_run_of_the_world_changes_no_binding(tmp_path: Path) -> None:
    """The stricter snapshot raises no false alarm: running the world mutates nothing it watches."""
    from synapse_kernel.release.engine import run
    from synapse_kernel.release.harness import price, scenarios

    sums = _sums(tmp_path, {"a/x.py": b"x = 1\n"})
    loaded = world.load_release_world()
    tables = incumbent.load_incumbent_tables()
    batch = scenarios(loaded, "S1", (64,))
    run(loaded, batch, incumbent.Incumbent(loaded, tables["I2-P"]))
    price(loaded, batch, incumbent.Incumbent(loaded, tables["I1-N"]))
    assert integrity.assert_frozen(sums, tmp_path) == 1
