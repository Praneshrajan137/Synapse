# Feature: decision-quality-proof, Property 88: A data-suffixed read is flagged unless it resolves
# under an installed-distribution root, and every read under the project's data directories is
# flagged
"""The zero-cost guard flags this project's data reads, and not a dependency's bundled files.

Feature: decision-quality-proof, task 29.2 (finding 57). Subject: ``_ZeroCostGuard`` in
``tests/uplift/test_preserved_baseline_regression.py``: ``_recording_open`` through
``_is_project_data_read`` and ``_installed_distribution_roots``.

**Why.** The guard flagged ``suffix in _DATA_SUFFIXES or under_data``, so any ``.csv`` anywhere
was a "real-data read": codecarbon's bundled ``cpu_power.csv`` reddened the slow selection, and
``_REAL_DATA_DIRS`` could never be the reason for a record. The repair exempts only a read that
resolves, component by component, inside an installed distribution, and checks the data
directories before that. It is stricter than the rejected ``... and under_data``: clause (b) is
a purchased CSV outside ``data/``, which that predicate would pass.

**The REAL guard, reached by file path.** ``tests/uplift`` has no ``__init__.py`` (unlike
``tests/verify``, whose modules import siblings as ``tests.verify.*``) and nothing imports
``tests.uplift.*``; pytest imports these modules by basename. So the guard's module is executed
from its path under a private name, the tree's other by-path pattern
(``tests/verify/test_ratchet_monotonicity_property.py``), whatever the import mode. Pytest never
collects that copy. Every probe enters the real guard and calls ``open``, the one entry point
the guard wraps.

**The oracle is the construction.** Each verdict is read off how the probe was built, and the
installed roots are derived here from the contract's words, not imported, so a source the guard
forgets is a drawn counterexample. Probes are absent paths: the guard decides, then the real
``open`` raises ``FileNotFoundError``. Every unflagged read shares its guard with a flagged
control, so a recorder that records nothing cannot pass.

**The domain of clause (e).** ``purelib + "2"`` is not outside every root: purelib's parent is
the ``platstdlib`` root in the ``nt`` scheme, and in ``posix_prefix`` whenever ``platlibdir`` is
``lib``, so the guard is right not to flag it. The lookalike is built from the outermost root.

Budget inherited from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal. Not slow-marked: no
twin, no subprocess, and the guard itself blocks every dial. Locus:
``ci.yml::uplift-verify-fast-2``, which runs ``tests/uplift/test_[pqrstuvwxyz]*.py``.
"""

from __future__ import annotations

import enum
import importlib.util
import os
import site
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_HOST_FILE: Final = Path(__file__).resolve().with_name("test_preserved_baseline_regression.py")
_HOST_NAME: Final = "synapse_zero_cost_guard_under_test"

#: The first component under every probe base. Nothing creates it, so each probe is absent,
#: and a probe that does open fails loudly instead of being read.
_ABSENT: Final = "property-88-never-created"
_DATA_DIRS: Final = (_REPO_ROOT / "data", _REPO_ROOT / "data_fabric")


def _load_guard_host() -> ModuleType:
    """Execute the regression module from its path, registered first (the importlib recipe)."""
    cached = sys.modules.get(_HOST_NAME)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(_HOST_NAME, _HOST_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the zero-cost guard's module from {_HOST_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_HOST_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[_HOST_NAME]
        raise
    return module


class _RecordingGuard(Protocol):
    """The part of the regression module's ``_ZeroCostGuard`` that this property reads."""

    data_file_reads: list[str]

    def __enter__(self) -> _RecordingGuard:
        """Install the socket, paid-SDK and ``open`` patches."""
        ...

    def __exit__(self, *exc_info: object) -> None:
        """Restore everything the guard patched."""
        ...


_HOST: Final[ModuleType] = _load_guard_host()
#: The real guard and its declared dataset suffixes. No verdict is imported.
_ZERO_COST_GUARD: Final[Callable[[], _RecordingGuard]] = _HOST._ZeroCostGuard
_DATA_SUFFIXES: Final[frozenset[str]] = _HOST._DATA_SUFFIXES


# ---------------------------------------------------------------------------
# The oracle side: roots derived from the contract's words, and the probe runner
# ---------------------------------------------------------------------------


def _normalised(path: Path) -> Path:
    """``path`` resolved and case-folded the way the platform compares names."""
    return Path(os.path.normcase(path.resolve(strict=False)))


def _named_roots() -> tuple[Path, ...]:
    """The installed-distribution roots the finding-57 contract names, derived independently.

    ``sysconfig``'s purelib, platlib, stdlib and platstdlib (those present) plus ``site``'s global
    and user site-packages (each guarded). Restated on the oracle side, so a source the guard
    forgets is a drawn counterexample rather than a blind spot the two share.
    """
    paths = sysconfig.get_paths()
    named = [paths[key] for key in ("purelib", "platlib", "stdlib", "platstdlib") if key in paths]
    if hasattr(site, "getsitepackages"):
        named.extend(site.getsitepackages())
    if hasattr(site, "getusersitepackages"):
        named.append(site.getusersitepackages())
    return tuple(sorted({_normalised(Path(entry)) for entry in named if entry}, key=str))


_INSTALLED_ROOTS: Final = _named_roots()
#: Roots no other named root encloses, so a sibling spelled as a longer name is outside them all.
_OUTERMOST_ROOTS: Final = tuple(
    root
    for root in _INSTALLED_ROOTS
    if root.name
    and not any(root != other and root.is_relative_to(other) for other in _INSTALLED_ROOTS)
)


def _inside_an_installed_root(path: Path) -> bool:
    """Whether ``path`` lies, component by component, inside a named root (premises only)."""
    candidate = _normalised(path)
    return any(candidate.is_relative_to(root) for root in _INSTALLED_ROOTS)


def _recorded(*targets: str | Path) -> list[str]:
    """What ONE real guard records while each absent target is opened for reading, in order."""
    with _ZERO_COST_GUARD() as guard:
        for target in targets:
            # The guard decides, then hands the call to the real `open`, which refuses an absent
            # path. The body runs only if a probe exists, which voids its premise.
            with pytest.raises(FileNotFoundError), open(target, encoding="utf-8"):
                pytest.fail(f"probe {target} exists, so it is not the absent path it must be")
        return list(guard.data_file_reads)


# ---------------------------------------------------------------------------
# Vocabulary for the generated table
# ---------------------------------------------------------------------------


class _Where(enum.Enum):
    """Where a probed read lands, in finding 57's vocabulary."""

    PYTEST_TEMP = "a pytest temporary directory"
    REPOSITORY = "the repository, outside its data directories"
    DATA_DIRECTORY = "a project data directory"
    INSTALLED_ROOT = "an installed-distribution root"
    LOOKALIKE = "a lookalike sibling of an installed-distribution root"


_UNDER_REPOSITORY: Final = frozenset({_Where.REPOSITORY, _Where.DATA_DIRECTORY})


@dataclass(frozen=True)
class _Probe:
    """One generated read: where it lands, what it is called, and how it is spelled."""

    where: _Where
    #: ``None`` stands for the pytest temporary directory, which only a fixture can supply.
    base: Path | None
    parts: tuple[str, ...]
    name: str
    data_suffixed: bool
    #: Spelled relative to the repository root; drawn only for reads that land inside it.
    relative: bool
    #: Handed to ``open`` as ``str`` rather than as a ``Path``.
    as_text: bool

    def absolute(self, scratch: Path) -> Path:
        """Where the read lands."""
        base = scratch if self.base is None else self.base
        return base.joinpath(_ABSENT, *self.parts, self.name)

    def target(self, scratch: Path) -> str | Path:
        """What is handed to ``open``."""
        path = self.absolute(scratch)
        if self.relative:
            path = path.relative_to(_REPO_ROOT)
        return str(path) if self.as_text else path

    @property
    def is_this_projects_data(self) -> bool:
        """The contract's verdict, read off how the probe was BUILT and never off the guard."""
        if self.where is _Where.DATA_DIRECTORY:
            return True  # rule 1: a data-directory read, whatever its suffix
        if self.where is _Where.INSTALLED_ROOT:
            return False  # a dependency's bundled file, never this project's data
        return self.data_suffixed  # rule 2 everywhere else, lookalike siblings included


_SAFE: Final = "abcdefghijklmnopqrstuvwxyz0123456789_-"
#: The fixed prefix keeps every generated name clear of Windows device names (``con``, ``nul``).
_NAMES: Final = st.text(alphabet=_SAFE, min_size=1, max_size=10).map(lambda text: f"p88-{text}")
_TAILS: Final = st.text(alphabet=_SAFE, min_size=1, max_size=6)
_OTHER_SUFFIXES: Final = tuple(
    suffix
    for suffix in ("", ".json", ".yaml", ".txt", ".py", ".md", ".log", ".toml")
    if suffix not in _DATA_SUFFIXES
)


def _any_case(suffix: str) -> st.SearchStrategy[str]:
    """``suffix`` with each letter upper- or lower-cased independently: ``.CsV`` is a CSV."""
    letters = (st.sampled_from((char.lower(), char.upper())) for char in suffix)
    return st.tuples(*letters).map("".join)


_DATA_SPELLINGS: Final = st.sampled_from(sorted(_DATA_SUFFIXES)).flatmap(_any_case)


@st.composite
def _probes(draw: st.DrawFn) -> _Probe:
    """Any landing place, with any declared data suffix in any case or a non-data suffix."""
    where = draw(st.sampled_from(tuple(_Where)))
    base: Path | None = None
    if where is _Where.INSTALLED_ROOT:
        base = draw(st.sampled_from(_INSTALLED_ROOTS))
    elif where is _Where.LOOKALIKE:
        root = draw(st.sampled_from(_OUTERMOST_ROOTS))
        base = root.parent / f"{root.name}{draw(_TAILS)}"
    elif where is _Where.DATA_DIRECTORY:
        base = draw(st.sampled_from(_DATA_DIRS))
    elif where is _Where.REPOSITORY:
        base = _REPO_ROOT
    data_suffixed = draw(st.booleans())
    suffix = draw(_DATA_SPELLINGS if data_suffixed else st.sampled_from(_OTHER_SUFFIXES))
    return _Probe(
        where=where,
        base=base,
        parts=tuple(draw(st.lists(_NAMES, max_size=2))),
        name=draw(_NAMES) + suffix,
        data_suffixed=data_suffixed,
        relative=where in _UNDER_REPOSITORY and draw(st.booleans()),
        as_text=draw(st.booleans()),
    )


@pytest.fixture(scope="module")
def scratch(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A pytest temporary directory nothing writes to, so every path beneath it is absent."""
    return tmp_path_factory.mktemp("property-88")


# ---------------------------------------------------------------------------
# Each clause on one explicit example
# ---------------------------------------------------------------------------


def test_a_csv_read_under_a_pytest_temporary_directory_is_flagged_under_its_own_name(
    tmp_path: Path,
) -> None:
    """Clauses (a) and (f): a purchased CSV is flagged, and the record names that very path."""
    purchased = tmp_path / "purchased-sales.csv"
    recorded = _recorded(purchased)
    assert recorded, f"no record for a CSV read outside every named root: {purchased}"
    assert recorded == [str(purchased)]


def test_a_csv_read_inside_the_repository_but_outside_its_data_directories_is_flagged() -> None:
    """Clause (b): the rejected ``suffix and under_data`` predicate would let this read pass."""
    scraped = _REPO_ROOT / _ABSENT / "scraped-prices.csv"
    assert _recorded(scraped) == [str(scraped)]


def test_a_csv_bundled_under_the_real_purelib_root_is_not_this_projects_data(
    tmp_path: Path,
) -> None:
    """Clause (c), finding 57's own case: codecarbon's ``cpu_power.csv`` is one instance.

    The flagged control shares the guard, so the bundled file's absence from the record is a
    decision and not a recorder that records nothing.
    """
    bundled = Path(sysconfig.get_paths()["purelib"]) / _ABSENT / "cpu_power.csv"
    control = tmp_path / "control.csv"
    assert _recorded(bundled, control) == [str(control)]


def test_every_read_under_a_project_data_directory_is_flagged_whatever_its_suffix() -> None:
    """Clause (d): a data-directory read is this project's data with no data suffix at all."""
    notes = _REPO_ROOT / "data" / _ABSENT / "notes.txt"
    extract = _REPO_ROOT / "data_fabric" / _ABSENT / "extract"
    assert _recorded(notes, extract) == [str(notes), str(extract)]


def test_a_lookalike_sibling_of_an_installed_root_is_outside_it_and_is_flagged() -> None:
    """Clause (e): containment is by path component, never by string prefix.

    Built from the outermost named root enclosing purelib; the module docstring says why not
    from purelib itself. The same file inside that root is the converse, and is not flagged.
    """
    purelib = _normalised(Path(sysconfig.get_paths()["purelib"]))
    enclosing = [root for root in _OUTERMOST_ROOTS if purelib.is_relative_to(root)]
    assert enclosing, f"no outermost named root encloses {purelib}: {_INSTALLED_ROOTS}"
    lookalike = Path(f"{enclosing[0]}2")
    assert not _inside_an_installed_root(lookalike), f"{lookalike} lies inside a named root"
    inside = enclosing[0] / _ABSENT / "bundled.csv"
    outside = lookalike / _ABSENT / "bundled.csv"
    assert _recorded(inside, outside) == [str(outside)]


def test_a_data_directory_read_is_flagged_even_when_that_directory_is_an_installed_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Rule 1 outranks the exemption, proven by making the data directory a root.

    The guard's root set becomes ``data/`` and ``tmp_path``. The unflagged ``tmp_path`` read
    proves the substitution is live, so the flagged ``data/`` read is the precedence at work and
    not a root the guard failed to match.
    """
    data = _REPO_ROOT / "data"
    roots = (_normalised(data), _normalised(tmp_path))
    monkeypatch.setattr(_HOST, "_installed_distribution_roots", lambda: roots)
    exempted = tmp_path / "bundled.csv"
    licensed = data / _ABSENT / "licensed-panel.csv"
    assert _recorded(exempted, licensed) == [str(licensed)]


# ---------------------------------------------------------------------------
# Property 88 -- the whole table
# ---------------------------------------------------------------------------


@given(probe=_probes())
def test_every_generated_read_is_flagged_exactly_when_it_is_this_projects_data(
    scratch: Path, probe: _Probe
) -> None:
    """Five landing places, every declared data suffix in any case, and non-data suffixes.

    A flagged control shares each guard, so the record is never empty and an unflagged probe's
    absence from it is a decision.
    """
    if probe.where is _Where.LOOKALIKE:
        # A generated tail could, in principle, spell another named root exactly.
        assume(not _inside_an_installed_root(probe.absolute(scratch)))
    target = probe.target(scratch)
    control = scratch / _ABSENT / "p88-control.csv"
    flagged = [str(Path(target))] if probe.is_this_projects_data else []
    assert _recorded(target, control) == [*flagged, str(control)], (
        f"{probe.where.value}: {target}; named roots {_INSTALLED_ROOTS}"
    )
