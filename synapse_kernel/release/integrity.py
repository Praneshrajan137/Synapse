"""Freeze W's run-time check: the frozen kernel is the one that runs.

``docs/truth/sealed/SHA256SUMS-W`` lists every frozen file with its sha256 (freeze W, PREREG-1
section 5). CI fails on an edit to a listed file; this module guards the run itself, which a later
session's challenger shares with the frozen code. It refuses a run when

* a frozen file's bytes differ from their recorded digest, read as git stores them
  (:func:`assert_frozen`);
* anything the frozen release modules bind was replaced, changed in place or added since this
  module was imported (:func:`assert_frozen`): a function (its code, defaults and keyword defaults
  included), a class and every member of it (dunders included), a constant, the fields of a
  module-level dataclass instance (the objective's weights), the contents of a module-level
  container; a name added to a module or a class is refused too, since a new module-level name can
  shadow a builtin the frozen code calls;
* a world object, or the incumbent's loaded tables, differ from the frozen files
  (:func:`assert_world_frozen`, :func:`assert_tables_frozen`).

**What one process cannot see** (truth log S5-D-07): numpy, ``math`` or the standard library
patched under the kernel; code that ran before this module was first imported; nested state below
one level of a container; and a challenger that rebinds this module's own functions. Freeze W's
rules therefore run a challenger compared on the frozen world in a process of its own, apart from
the harness that measures it.

Import this module before any challenger code, so the bindings it captures are the frozen ones.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import types
from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np

from synapse_kernel.release import (
    cells,
    engine,
    guard,
    harness,
    incumbent,
    objective,
    observation,
    oracle,
    rng,
    sampling,
    scenario,
    seeds,
    tuning,
    world,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.world import ReleaseWorld

__all__ = [
    "FROZEN_MODULES",
    "FrozenKernelError",
    "assert_frozen",
    "assert_tables_frozen",
    "assert_world_frozen",
    "canonical_sha256",
    "frozen_bindings",
    "read_sums",
]

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SUMS: Final[Path] = ROOT / "docs" / "truth" / "sealed" / "SHA256SUMS-W"
#: The frozen world and the incumbent's tables, as listed in the sums file.
WORLD_FILE: Final[str] = "synapse_kernel/worlds/release_world.json"
TABLES_FILE: Final[str] = "synapse_kernel/worlds/incumbent_tables.json"
#: Every module of the release world but this one.
FROZEN_MODULES: Final[tuple[types.ModuleType, ...]] = (
    cells,
    engine,
    guard,
    harness,
    incumbent,
    objective,
    observation,
    oracle,
    rng,
    sampling,
    scenario,
    seeds,
    tuning,
    world,
)
#: Class members whose object is new on every access, so identity says nothing.
_UNSTABLE_MEMBERS: Final[frozenset[str]] = frozenset({"__dict__", "__weakref__"})
_SCALARS: Final[tuple[type, ...]] = (int, float, complex, str, bytes, bool, type(None))


class FrozenKernelError(RuntimeError):
    """A frozen file or binding is not the one freeze W fixed."""


def canonical_sha256(path: Path) -> str:
    """The sha256 of a file's bytes as git stores them: CRLF read as LF.

    A Windows checkout with ``core.autocrlf`` writes text files with CRLF; the repository holds LF.
    Reading CRLF as LF gives one digest on every checkout, equal to ``git show <rev>:<path> |
    sha256sum``. No frozen file holds a carriage return of its own.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def frozen_bindings() -> dict[str, object]:
    """``{"module.name": object}`` and ``{"module.Class.attr": object}`` as they are bound now.

    A module's dunder names are left out (Python adds some, such as ``__warningregistry__``); every
    member of a class the module defines is kept, dunders included.
    """
    out: dict[str, object] = {}
    for module in FROZEN_MODULES:
        for name, value in vars(module).items():
            if name.startswith("__") and name.endswith("__"):
                continue
            key = f"{module.__name__}.{name}"
            out[key] = value
            if isinstance(value, type) and value.__module__ == module.__name__:
                for attr, member in vars(value).items():
                    if attr not in _UNSTABLE_MEMBERS:
                        out[f"{key}.{attr}"] = member
    return out


def _state(value: object) -> tuple[object, ...] | None:
    """What could change inside ``value`` without rebinding it; ``None`` if nothing can."""
    if isinstance(value, types.FunctionType):
        keywords = value.__kwdefaults__
        return (
            value.__code__,
            value.__defaults__,
            None if keywords is None else tuple(sorted(keywords.items())),
        )
    if isinstance(value, staticmethod | classmethod):
        return (value.__func__, _state(value.__func__))
    if isinstance(value, property):
        accessors = (value.fget, value.fset, value.fdel)
        return (*accessors, *(None if f is None else _state(f) for f in accessors))
    if isinstance(value, np.ndarray):
        return (value.copy(),)
    if isinstance(value, dict):
        return tuple(value.items())
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, set):
        return (frozenset(value),)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(getattr(value, field.name) for field in dataclasses.fields(value))
    return None


def _same(kept: object, now: object) -> bool:
    """Identity, or equal contents for tuples, arrays and immutable scalars."""
    if kept is now:
        return True
    if isinstance(kept, tuple) and isinstance(now, tuple):
        return len(kept) == len(now) and all(_same(a, b) for a, b in zip(kept, now, strict=True))
    if isinstance(kept, np.ndarray) and isinstance(now, np.ndarray):
        return kept.shape == now.shape and bool(np.array_equal(kept, now))
    if isinstance(kept, _SCALARS) and type(kept) is type(now):
        return bool(kept == now)
    return False


_ORIGINAL: Final[types.MappingProxyType[str, object]] = types.MappingProxyType(frozen_bindings())
_STATES: Final[types.MappingProxyType[str, tuple[object, ...]]] = types.MappingProxyType(
    {key: kept for key, value in _ORIGINAL.items() if (kept := _state(value)) is not None}
)


def read_sums(path: Path = SUMS) -> dict[str, str]:
    """``{relative path: sha256}`` from a sums file.

    Each line is ``<sha256> *<path>`` (binary mode, as ``sha256sum -b`` writes) or
    ``<sha256>  <path>``; paths are relative to the repository root, with forward slashes.
    """
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        out[name.lstrip("*").strip()] = digest
    return out


def assert_frozen(sums: Path = SUMS, root: Path = ROOT) -> int:
    """Refuse unless every frozen file and binding is freeze W's; return the files checked.

    Raises:
        FrozenKernelError: A listed file is missing or differs, or a binding was replaced, removed,
            changed in place or added after this module was imported.
    """
    now = frozen_bindings()
    for key, original in _ORIGINAL.items():
        if key not in now:
            raise FrozenKernelError(f"{key} was removed in memory after import")
        if now[key] is not original:
            raise FrozenKernelError(f"{key} was replaced in memory after import")
        kept = _STATES.get(key)
        if kept is not None and not _same(kept, _state(now[key])):
            raise FrozenKernelError(f"{key} was changed in place in memory after import")
    added = sorted(set(now) - set(_ORIGINAL))
    if added:
        raise FrozenKernelError(f"{added[0]} was added in memory after import")
    listed = read_sums(sums)
    for name, digest in sorted(listed.items()):
        path = root / name
        if not path.is_file():
            raise FrozenKernelError(f"frozen file {name} is missing")
        actual = canonical_sha256(path)
        if actual != digest:
            message = f"frozen file {name}: sha256 {actual} is not freeze W's {digest}"
            raise FrozenKernelError(message)
    return len(listed)


def assert_world_frozen(world_in_memory: ReleaseWorld, sums: Path = SUMS) -> None:
    """Refuse unless a world object serialises to the frozen world file's exact bytes.

    The world file is written as ``json.dumps(world_to_document(world), sort_keys=True,
    separators=(",", ":"))`` plus a newline, so a loaded world re-serialises to it byte for byte;
    a world altered in memory after loading does not.

    Raises:
        FrozenKernelError: The world is not freeze W's, or the sums file does not list it.
    """
    document = world.world_to_document(world_in_memory)
    text = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    frozen = read_sums(sums).get(WORLD_FILE)
    if frozen is None:
        raise FrozenKernelError(f"{WORLD_FILE} is not listed in {sums.name}")
    if digest != frozen:
        raise FrozenKernelError("the world in memory is not freeze W's world")


def assert_tables_frozen(
    tables: Mapping[str, IncumbentTables], sums: Path = SUMS, root: Path = ROOT
) -> None:
    """Refuse unless loaded incumbent tables equal the frozen file's, version by version.

    The tables are frozen dataclasses holding numpy arrays, which can still be written in place:
    a run whose incumbent arm reads altered tables would sabotage the incumbent unseen.

    Raises:
        FrozenKernelError: The tables file is not freeze W's, or a version in memory differs.
    """
    frozen = read_sums(sums).get(TABLES_FILE)
    if frozen is None:
        raise FrozenKernelError(f"{TABLES_FILE} is not listed in {sums.name}")
    path = root / TABLES_FILE
    if canonical_sha256(path) != frozen:
        raise FrozenKernelError(f"{TABLES_FILE} is not freeze W's")
    fresh = incumbent.load_incumbent_tables(path)
    for name, version in tables.items():
        reference = fresh.get(name)
        if (
            reference is None
            or version.name != reference.name
            or version.waste_aware is not reference.waste_aware
            or not np.array_equal(version.factors, reference.factors)
            or not np.array_equal(version.mean_table, reference.mean_table)
        ):
            raise FrozenKernelError(f"the incumbent's tables {name} in memory are not freeze W's")
