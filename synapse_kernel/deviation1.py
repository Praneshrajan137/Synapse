"""Deviation 1's run-time check: W-d1's world and incumbent tables are the ones its freeze fixed.

Deviation 1 (truth session 6, decision S6-D-03; ``docs/truth/sealed/DEVIATION-1.md``) adds a second
release world, W-d1, calibrated by the other reading of the session-5 gate's rule, beside freeze W's
world, which stays primary. ``docs/truth/sealed/SHA256SUMS-D1`` lists its files with the sha256 of
their bytes as git stores them. This module guards a run on W-d1 as
:mod:`synapse_kernel.release.integrity` guards a run on freeze W's world: it refuses a listed file
whose digest differs, a world object that does not serialise to W-d1's file, and incumbent tables
that differ in memory from W-d1's file. Freeze W's own checks still apply to the kernel that runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np

from synapse_kernel.release.incumbent import load_incumbent_tables
from synapse_kernel.release.integrity import FrozenKernelError, canonical_sha256, read_sums
from synapse_kernel.release.world import load_release_world, world_to_document

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.world import ReleaseWorld

__all__ = [
    "SUMS",
    "TABLES_FILE",
    "WORLD_FILE",
    "assert_files",
    "assert_tables",
    "assert_world",
    "load",
]

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SUMS: Final[Path] = ROOT / "docs" / "truth" / "sealed" / "SHA256SUMS-D1"
WORLD_FILE: Final[str] = "synapse_kernel/worlds/release_world_d1.json"
TABLES_FILE: Final[str] = "synapse_kernel/worlds/incumbent_tables_d1.json"


def assert_files(sums: Path = SUMS, root: Path = ROOT) -> int:
    """Refuse unless every file deviation 1 lists has its recorded digest; return the count.

    Raises:
        FrozenKernelError: A listed file is missing or differs.
    """
    listed = read_sums(sums)
    for name, digest in sorted(listed.items()):
        path = root / name
        if not path.is_file():
            raise FrozenKernelError(f"deviation 1's file {name} is missing")
        if canonical_sha256(path) != digest:
            raise FrozenKernelError(f"deviation 1's file {name} is not the one its freeze fixed")
    return len(listed)


def assert_world(world: ReleaseWorld, sums: Path = SUMS) -> None:
    """Refuse unless a world object serialises to W-d1's file, byte for byte.

    Raises:
        FrozenKernelError: The world is not W-d1, or the sums file does not list it.
    """
    text = json.dumps(world_to_document(world), sort_keys=True, separators=(",", ":")) + "\n"
    frozen = read_sums(sums).get(WORLD_FILE)
    if frozen is None:
        raise FrozenKernelError(f"{WORLD_FILE} is not listed in {sums.name}")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != frozen:
        raise FrozenKernelError("the world in memory is not deviation 1's world")


def assert_tables(
    tables: Mapping[str, IncumbentTables], sums: Path = SUMS, root: Path = ROOT
) -> None:
    """Refuse unless loaded incumbent tables equal W-d1's file, version by version.

    Raises:
        FrozenKernelError: The tables file is not deviation 1's, or a version in memory differs.
    """
    frozen = read_sums(sums).get(TABLES_FILE)
    path = root / TABLES_FILE
    if frozen is None or canonical_sha256(path) != frozen:
        raise FrozenKernelError(f"{TABLES_FILE} is not deviation 1's")
    fresh = load_incumbent_tables(path)
    for name, version in tables.items():
        reference = fresh.get(name)
        if (
            reference is None
            or version.waste_aware is not reference.waste_aware
            or not np.array_equal(version.factors, reference.factors)
            or not np.array_equal(version.mean_table, reference.mean_table)
        ):
            raise FrozenKernelError(f"the incumbent's tables {name} in memory are not W-d1's")


def load(root: Path = ROOT) -> tuple[ReleaseWorld, dict[str, IncumbentTables]]:
    """W-d1's world and incumbent tables, each checked against deviation 1's sums."""
    sums = root / "docs" / "truth" / "sealed" / "SHA256SUMS-D1"
    assert_files(sums, root)
    world = load_release_world(root / WORLD_FILE)
    tables = load_incumbent_tables(root / TABLES_FILE)
    assert_world(world, sums)
    assert_tables(tables, sums, root)
    return world, tables
