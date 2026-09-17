"""SYNAPSE -- Module-liveness analyzer and enforcement gate (E3.5; R13.1-R13.3, R13.7, R13.9).

The audit's Requirement 13 finding is not that dormant code is *wrong* -- several
dormant modules are deliberate seams and two of them are the honest predicates that
would close Requirements 2 and 5. The finding is that property counts and test counts
are cited as capability evidence **without distinguishing "verified and reachable"
from "verified and dormant"**. This module is the mechanism that draws that line.

Three obligations, each mechanical:

**1. A total classification (R13.1, R13.2).** Every first-party Python module lands in
exactly one of five classes -- nothing is left unclassified:

  ``ALIVE``        reachable from a live docker-compose.gcp.yml entrypoint
  ``TOOLING``      reachable from ``scripts/`` or referenced by Makefile/CI/compose
  ``TEST``         a test module (``*/tests/*``, ``test_*.py``, ``*_test.py``)
  ``SEAM_EXEMPT``  would be dead, but carries a valid in-source seam marker
  ``DEAD``         none of the above -- 0 importers and 0 references

Totality is not a convention here, it is checked: :func:`classify` asserts the five
buckets partition the scanned file set (equal cardinality **and** pairwise disjoint)
and raises :class:`ClassificationError` otherwise, which :func:`evaluate` reports as
``UNAVAILABLE``. A partition that does not partition can never read as a pass.

**2. One exemption, and it lives in the source (R13.2).** The *only* way out of the
dead set is an in-source marker::

    # synapse: seam(reason="...", adr="ADR-0NN")

The justification therefore travels with the code and cannot be lost in a config diff.
A marker that is malformed -- empty reason, missing or ill-formed ADR id -- exempts
nothing and is reported as malformed (I-7: an unparseable justification is not a
justification). A marker on a module that is already ALIVE/TOOLING/TEST is *inert* and
reported as such, so a stale marker is visible rather than silently decorative.

**3. A named baseline, not a number (R13.9).** ``DEAD_BASELINE`` is no longer a hand
edited integer. It is derived as ``len(dormant)`` from the named baseline
``infrastructure/quality/dead-modules.yaml``, so the count is a *projection of the
names*. Consequences: the committed ``baseline:`` key must equal ``len(dormant)``, a
dormant name whose module has become reachable is reported resolved, and **removing a
name while its module is still unreachable FAILs naming that module**.

That file is **not a suppression list.** A name in it never turns a FAIL into a PASS;
it only fixes the count a FAIL is measured against.

Two projections
---------------

A projection is not a class -- these are *live* files whose **reachability** is
test-only. They are reported separately because their severity differs:

* **R13.3 -- model-validating property tests (report only).** A property test whose
  target no non-test module imports validates a *model*, not the shipped
  implementation. The criterion's verb is "SHALL be reported", so this projection
  never moves the exit code; it labels. Resolution is per-symbol first: for a target
  module that *is* production-reachable, only the symbols no non-test module imports
  are reported. ``frontend/src/lib/virtual-window.ts`` is exactly this case -- the
  surfaces import ``ROW_OVERSCAN`` from it, so reporting the *file* would be a false
  positive; only ``computeWindow`` is test-only. A target no non-test module imports
  at all is reported at module level (``frontend/src/lib/reconcile.ts``).

* **R13.7 -- invariant symbols only tests invoke (FAIL).** A symbol encoding an
  invariant precondition or postcondition must be invoked from a non-test module. If
  only tests invoke it, this FAILs naming **the symbol and the invariant it encodes**.
  Subjects come from two independent sources: mechanically, every first-party function
  carrying a ``deal.pre``/``deal.post``/``deal.ensure``/``deal.inv`` contract (the
  invariant text is the decorator's ``message=``); and declaratively, the
  ``test_only_reachable`` rows of the named baseline whose ``invariant`` is non-null.
  Neither source is an allowlist -- a subject listed there is *expected to be
  reported*, and production reachability is recomputed from the tree, never trusted
  from the record.

  A declared row whose recomputed caller count has become non-zero is reported
  ``resolved`` (a maintenance line, never a FAIL) -- landing the fix must not be
  punished. A row that records callers the tree no longer has is record drift, and
  that FAILs, following the ``ratchet_truth`` precedent.

Current expected state, honestly
--------------------------------
``orchestrator.guardrails.rules.execute_consensus`` is detected mechanically from its
``@deal.pre`` (I-5) / ``@deal.post`` (I-4) contract and now **passes**: task 8.5 landed
``ConsensusProtocol._ratify_and_dispatch``, which imports and calls it, so that contract
is on the production path. Its baseline row is kept with the corrected count so that
removing the choke point later reads as record drift and fails.

``uplift.uplift_floor.is_proven_uplift`` and ``ratchet_to_measured`` also **pass** now:
task 10.3 rewrote ``scripts/audit/uplift_truth.py`` so ``verdict()`` derives the C60 exit
code from the predicate and ``admit_floor_raise()`` is the ratchet's production caller.
Both baseline rows keep the corrected count for the same record-drift reason.

Still failing, correctly:
``synapse_common.contracts.validate_audit_insertion``, whose ``@deal.post`` asserts
I-4's audit-insertion postcondition and which no production module calls. That FAIL is
the requirement working, not a defect in this gate.

Outcome mapping (I-7: absence of proof is never a pass)::

    classification not total, or baseline unreadable  -> exit 2  (unavailable)
    dead > baseline, baseline inconsistent, a dormant
      name dropped while still dormant, a malformed
      seam marker, or an invariant symbol only tests
      invoke                                          -> exit 1  (fail)
    otherwise                                         -> exit 0  (pass)

I-0: this gate only reads and AST-parses files. It runs no suite, no build, and no
container. Every read passes ``encoding='utf-8'`` (E-S13-07) and all output is ASCII.

Run::

  python scripts/audit/module_liveness.py            # print the inventory
  python scripts/audit/module_liveness.py --md FILE  # write the markdown doc
  python scripts/audit/module_liveness.py --json     # canonical JSON report
  python scripts/audit/module_liveness.py --check    # exit 0 pass / 1 fail / 2 unavailable
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from collections import deque
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import structlog
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:  # importable when run as a bare script, not -m
    sys.path.insert(0, str(ROOT))

_LOG = structlog.get_logger(__name__)

# Source roots: repo root (agents/, orchestrator/, api/, digital_twin/,
# data_fabric/, ml_pipelines/, scripts/) + packages/ (synapse_common is
# imported as `synapse_common` via the editable install).
SRC_ROOTS = [ROOT, ROOT / "packages"]

# First-party top-level packages we resolve/track (everything else = stdlib/3p).
FIRST_PARTY = {
    "agents", "orchestrator", "api", "digital_twin",
    "synapse_common", "data_fabric", "ml_pipelines", "scripts",
}

# Packages scanned for the classification, in addition to packages/synapse_common.
SCANNED_PACKAGES = (
    "agents", "orchestrator", "api", "digital_twin", "data_fabric", "ml_pipelines", "scripts",
)

# The Python processes that actually run in docker-compose.gcp.yml.
LIVE_ENTRYPOINTS = [
    ROOT / "api" / "main.py",
    ROOT / "orchestrator" / "inference" / "serve.py",
    ROOT / "digital_twin" / "inference" / "serve.py",
    *sorted(ROOT.glob("agents/*/inference/serve.py")),
]

# Files/dirs whose references prove a module is offline TOOLING, not dead.
REFERENCE_HAYSTACK = [
    ROOT / "Makefile",
    *ROOT.glob(".github/workflows/*.yml"),
    *ROOT.glob("docker/*.yml"),
    ROOT / "conftest.py",
    ROOT / "pyproject.toml",
]

#: The named baseline (R13.9). `DEAD_BASELINE` is derived from its `dormant` list.
DEAD_MODULES_FILE = ROOT / "infrastructure" / "quality" / "dead-modules.yaml"

# Distinct exit codes, mirroring scripts/audit/ratchet_truth.py and uplift_truth.py.
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNAVAILABLE = 2

#: The one admissible exemption from the dead set (R13.2). `reason` must be non-empty
#: and `adr` must be a well-formed ADR id; anything else exempts nothing. Both values
#: are accepted quoted or bare and are unquoted by :func:`_unquote`.
SEAM_MARKER_RE = re.compile(
    r"#\s*synapse:\s*seam\s*\(\s*"
    r"reason\s*=\s*(?P<reason>\"[^\"]*\"|'[^']*'|[^,)]*?)\s*,\s*"
    r"adr\s*=\s*(?P<adr>\"[^\"]*\"|'[^']*'|[^,)\s]*)\s*"
    r"\)"
)
#: A bare `synapse: seam(` occurrence, used to spot markers the strict form rejects.
SEAM_MARKER_LOOSE_RE = re.compile(r"#\s*synapse:\s*seam\s*\(")
ADR_ID_RE = re.compile(r"^ADR-\d{3}$")

#: `deal` decorators that encode an invariant pre/postcondition (R13.7).
CONTRACT_DECORATORS = ("pre", "post", "ensure", "inv", "invariant")

# --- frontend projection (R13.3) --------------------------------------------
FRONTEND_SRC = ROOT / "frontend" / "src"
#: tsconfig.json `compilerOptions.paths`, flattened to prefix -> directory.
FRONTEND_ALIASES: Mapping[str, str] = {
    "@app/": "app/",
    "@surfaces/": "surfaces/",
    "@domain/": "domain/",
    "@transport/": "transport/",
    "@ds/": "design-system/",
    "@viz/": "visualization/",
    "@state/": "state/",
    "@hooks/": "hooks/",
    "@lib/": "lib/",
    "@i18n/": "i18n/",
    "@test/": "test/",
    "@/": "",
}
FRONTEND_EXTENSIONS = (".ts", ".tsx")
#: A property test in the frontend convention: `<name>.property.test.ts`.
FRONTEND_PROPERTY_TEST_RE = re.compile(r"\.property\.test\.tsx?$")
#: `import ... from "<specifier>"` / `export ... from "<specifier>"`.
TS_IMPORT_RE = re.compile(
    r"""(?:import|export)\s+(?P<clause>[^;'"]*?)\s*from\s*['"](?P<spec>[^'"]+)['"]""",
    re.DOTALL,
)
#: Bare side-effect import: `import "<specifier>"`.
TS_BARE_IMPORT_RE = re.compile(r"""import\s*['"](?P<spec>[^'"]+)['"]""")


class LivenessClass(str, Enum):
    """The five classes. The classification is total over these and only these."""

    ALIVE = "ALIVE"
    TOOLING = "TOOLING"
    TEST = "TEST"
    SEAM_EXEMPT = "SEAM_EXEMPT"
    DEAD = "DEAD"


#: Presentation/iteration order. Every class appears exactly once (checked below).
CLASS_ORDER: tuple[LivenessClass, ...] = (
    LivenessClass.ALIVE,
    LivenessClass.TOOLING,
    LivenessClass.TEST,
    LivenessClass.SEAM_EXEMPT,
    LivenessClass.DEAD,
)
assert set(CLASS_ORDER) == set(LivenessClass) and len(CLASS_ORDER) == len(LivenessClass)


class Outcome(str, Enum):
    """Four-state outcome. Only ``PASS`` is a pass (I-7)."""

    PASS = "pass"
    FAIL = "fail"
    REPORT = "report"
    UNAVAILABLE = "unavailable"


class Clause(str, Enum):
    """The clause a finding belongs to, so a failure names its own rule."""

    TOTALITY = "totality"            # R13.1 -- five classes, nothing unclassified
    SEAM_MARKER = "seam-marker"      # R13.2 -- the only exemption, and it must parse
    NEW_ORPHAN = "new-orphan"        # R13.1 -- dead set over the named baseline
    BASELINE_DROP = "baseline-drop"  # R13.9 -- a name removed while still dormant
    BASELINE_DRIFT = "baseline-drift"  # R13.9 -- `baseline:` != len(dormant)
    INVARIANT_SYMBOL = "invariant-symbol"  # R13.7 -- only tests invoke it
    RECORD_DRIFT = "record-drift"    # a recorded fact the tree contradicts


# ---------------------------------------------------------------------------
# The named baseline (R13.9)
# ---------------------------------------------------------------------------


def _rel(path: Path) -> str:
    """Repo-relative POSIX path, so every reported subject reads the same way."""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _unquote(value: str) -> str:
    """Strip one matching pair of surrounding quotes from a marker value."""
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1].strip()
    return text


class Unavailable(Exception):
    """A committed input could not be read. Never a pass (I-7)."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ClassificationError(RuntimeError):
    """The five buckets do not partition the scanned module set (R13.1)."""


class DormantRecord(BaseModel):
    """One declared-dormant module in the named baseline."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    path: str
    since: str | None = None
    rationale: str | None = None
    revive_by: str | None = None


class SeamExemptionRecord(BaseModel):
    """Attribution for a seam marker found in source. Grants nothing (R13.2)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    path: str
    reason: str | None = None
    adr: str | None = None


class TestOnlyRecord(BaseModel):
    """A declared test-only-reachable subject the projections must report."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    symbol: str
    invariant: str | None = None
    importers: str | None = None
    production_callers: int | None = None
    wired_by: str | None = None
    requirement: str | None = None
    note: str | None = None


class DeadModulesBaseline(BaseModel):
    """``infrastructure/quality/dead-modules.yaml`` -- the named baseline."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int | None = None
    dormant: tuple[DormantRecord, ...] = ()
    baseline: int | None = None
    seam_exemptions: tuple[SeamExemptionRecord, ...] = ()
    test_only_reachable: tuple[TestOnlyRecord, ...] = ()

    @property
    def derived_baseline(self) -> int:
        """The baseline is a *projection of the names*, never an independent number."""
        return len(self.dormant)

    @property
    def dormant_paths(self) -> tuple[str, ...]:
        return tuple(record.path.replace("\\", "/") for record in self.dormant)


def load_baseline(path: Path = DEAD_MODULES_FILE) -> DeadModulesBaseline:
    """Read the named baseline. An unreadable baseline is never a pass (I-7)."""
    if not path.is_file():
        raise Unavailable(f"named baseline missing: {_rel(path)}")
    try:
        document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise Unavailable(f"named baseline unreadable: {_rel(path)}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise Unavailable(f"named baseline is not valid YAML: {_rel(path)}: {exc}") from exc
    if not isinstance(document, dict):
        raise Unavailable(f"{_rel(path)} does not parse to a mapping")
    try:
        return DeadModulesBaseline.model_validate(document)
    except ValidationError as exc:
        raise Unavailable(
            f"{_rel(path)} is malformed: {exc.error_count()} validation error(s)"
        ) from exc


def _load_baseline_or_none() -> tuple[DeadModulesBaseline | None, str | None]:
    try:
        return load_baseline(), None
    except Unavailable as exc:
        _LOG.warning("module_liveness.baseline_unavailable", detail=exc.detail)
        return None, exc.detail


_BASELINE, _BASELINE_ERROR = _load_baseline_or_none()

#: Derived from the named baseline as ``len(dormant)`` -- the count is a projection of
#: the names, not a number anyone can nudge (R13.9). When the baseline cannot be read
#: this falls back to ``0``, the *strictest* admissible ceiling (the ratchet direction
#: is ``down``), so the fallback can only over-report, never excuse; :func:`evaluate`
#: independently reports ``UNAVAILABLE`` in that case rather than treating 0 as fact.
#:
#: Note for ``scripts/audit/ratchet_truth.py``: this is no longer a literal numeric
#: assignment, so ``extract_guard_constant`` reads it as ``None`` -- "not independently
#: verifiable here", which that gate never treats as agreement. The authority moved to
#: ``infrastructure/quality/dead-modules.yaml``, which is the point of R13.9.
DEAD_BASELINE: int = 0 if _BASELINE is None else _BASELINE.derived_baseline


# ---------------------------------------------------------------------------
# First-party import graph (unchanged mechanics -- this part already worked)
# ---------------------------------------------------------------------------


def _iter_first_party_files() -> list[Path]:
    """Every first-party Python file the classification must cover."""
    files: list[Path] = []
    for pkg in SCANNED_PACKAGES:
        base = ROOT / pkg
        if base.is_dir():
            files += [p for p in base.rglob("*.py") if "__pycache__" not in p.parts]
    sc = ROOT / "packages" / "synapse_common"
    if sc.is_dir():
        files += [p for p in sc.rglob("*.py") if "__pycache__" not in p.parts]
    return sorted(set(files))


def _module_name(path: Path) -> str | None:
    """File path -> dotted module name (None if not under a known root)."""
    for base in SRC_ROOTS:
        try:
            rel = path.resolve().relative_to(base.resolve())
        except ValueError:
            continue
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if parts and parts[0] in FIRST_PARTY:
            return ".".join(parts)
    return None


def _resolve(dotted: str) -> Path | None:
    """Dotted first-party module -> file path (module.py or package/__init__.py)."""
    if not dotted or dotted.split(".")[0] not in FIRST_PARTY:
        return None
    rel = Path(*dotted.split("."))
    for base in SRC_ROOTS:
        for cand in (base / rel.with_suffix(".py"), base / rel / "__init__.py"):
            if cand.is_file():
                return cand.resolve()
    return None


def _parse(path: Path) -> ast.Module | None:
    """Parse a source file with ``encoding='utf-8'`` (E-S13-07)."""
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return None


def _imports(path: Path) -> set[str]:
    """First-party dotted modules imported by this file (incl. relative)."""
    out: set[str] = set()
    tree = _parse(path)
    if tree is None:
        return out
    pkg = _module_name(path)
    pkg_parts = pkg.split(".")[:-1] if pkg else []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and pkg_parts:  # relative import
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
                out.add(mod)
                for a in node.names:
                    out.add(f"{mod}.{a.name}")
            elif node.module:
                out.add(node.module)
                for a in node.names:
                    out.add(f"{node.module}.{a.name}")
    return {m for m in out if m.split(".")[0] in FIRST_PARTY}


def _ancestor_inits(path: Path) -> list[Path]:
    """The package __init__.py files Python implicitly executes to import this
    module (e.g. importing orchestrator.llm.x runs orchestrator/__init__.py and
    orchestrator/llm/__init__.py). Without this, package __init__ files look DEAD."""
    out: list[Path] = []
    for base in SRC_ROOTS:
        try:
            rel = path.resolve().relative_to(base.resolve())
        except ValueError:
            continue
        cur = base
        for part in rel.parts[:-1]:  # walk package dirs, not the file itself
            cur = cur / part
            init = (cur / "__init__.py").resolve()
            if init.is_file():
                out.append(init)
        break
    return out


def _reachable(roots: Sequence[Path]) -> set[Path]:
    seen: set[Path] = set()
    q: deque[Path] = deque(r.resolve() for r in roots if r.is_file())
    while q:
        f = q.popleft()
        if f in seen:
            continue
        seen.add(f)
        for init in _ancestor_inits(f):  # implicit package imports
            if init not in seen:
                q.append(init)
        for dotted in _imports(f):
            tgt = _resolve(dotted)
            if tgt and tgt not in seen:
                q.append(tgt)
    return seen


def _loc(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def _haystack() -> str:
    return "\n".join(
        h.read_text(encoding="utf-8", errors="ignore") for h in REFERENCE_HAYSTACK if h.is_file()
    )


def _python_m_roots(haystack: str) -> list[Path]:
    """Tooling roots referenced by Makefile/CI: `python -m <dotted>` modules,
    AND every .py under a directory the Makefile `cd <dir>`s into (e.g.
    `cd data_fabric/feast` -- those files are loaded by the feast CLI, not via a
    python import the AST graph can see)."""
    roots: list[Path] = []
    for m in re.findall(r"python\d?\s+-m\s+([\w.]+)", haystack):
        f = _resolve(m)
        if f:
            roots.append(f)
    for d in re.findall(r"\bcd\s+([\w./-]+)", haystack):
        dpath = (ROOT / d).resolve()
        if dpath.is_dir() and dpath != ROOT.resolve():
            roots += [p for p in dpath.rglob("*.py") if "__pycache__" not in p.parts]
    return roots


def _referenced(rel: str, dotted: str | None, haystack: str) -> bool:
    """Precise reference: the file path, its dotted name, or an ANCESTOR dir
    path of depth >= 2 (e.g. 'data_fabric/feast', 'ml_pipelines/ab_test')
    appears literally in Makefile/CI/compose. The bare top-level dir name is
    intentionally NOT enough (too coarse -- would swallow real orphans)."""
    if rel in haystack:
        return True
    if dotted and (dotted in haystack):
        return True
    parts = rel.split("/")
    for depth in range(2, len(parts)):  # 'a/b', 'a/b/c', ... (skip bare 'a')
        anc = "/".join(parts[:depth])
        if anc in haystack or anc.replace("/", ".") in haystack:
            return True
    return False


def is_test_path(rel: str, name: str) -> bool:
    """The TEST class predicate, shared by the classification and the projections."""
    return "/tests/" in rel or name.startswith("test_") or name.endswith("_test.py")


# ---------------------------------------------------------------------------
# Seam markers -- the only exemption from the dead set (R13.2)
# ---------------------------------------------------------------------------


class SeamMarker(BaseModel):
    """One ``# synapse: seam(...)`` occurrence and whether it exempts anything."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line: int
    reason: str
    adr: str
    valid: bool
    #: True only when the module would otherwise be DEAD. A marker on a reachable
    #: module is inert -- recorded so a stale marker is visible, not silent.
    effective: bool = False
    detail: str = ""


def _comments(path: Path) -> list[tuple[int, str]]:
    """Every real ``#`` comment in a Python file, as ``(lineno, text)``.

    Tokenised rather than line-matched on purpose: a marker is a *comment*, and prose
    or a docstring that merely quotes the marker form must not be mistaken for one.
    (This module's own docstring quotes it, so a line-based scan would report itself.)
    A file that does not tokenise yields no markers, which can only over-report
    dormancy -- never excuse it.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    found: list[tuple[int, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                found.append((token.start[0], token.string))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return []
    return found


def scan_seam_markers(path: Path) -> tuple[SeamMarker, ...]:
    """Extract every seam marker in a file, valid or not.

    A malformed marker is returned with ``valid=False`` and exempts nothing: an
    unparseable justification is not a justification (I-7). Both a strict and a loose
    pattern are applied so a marker the strict form rejects is *reported* rather than
    silently ignored -- otherwise a typo would read as "no marker" and the module would
    look plainly dead, hiding the author's intent.
    """
    rel = _rel(path)
    markers: list[SeamMarker] = []
    for lineno, line in _comments(path):
        strict = SEAM_MARKER_RE.search(line)
        if strict is not None:
            reason = _unquote(strict.group("reason"))
            adr = _unquote(strict.group("adr"))
            problems: list[str] = []
            if not reason:
                problems.append("empty reason")
            if not ADR_ID_RE.match(adr):
                problems.append(f"adr {adr!r} is not of the form ADR-0NN")
            markers.append(
                SeamMarker(
                    path=rel,
                    line=lineno,
                    reason=reason,
                    adr=adr,
                    valid=not problems,
                    detail="; ".join(problems),
                )
            )
            continue
        if SEAM_MARKER_LOOSE_RE.search(line):
            markers.append(
                SeamMarker(
                    path=rel,
                    line=lineno,
                    reason="",
                    adr="",
                    valid=False,
                    detail=(
                        "marker does not parse; the only admissible form is "
                        '# synapse: seam(reason="...", adr="ADR-0NN")'
                    ),
                )
            )
    return tuple(markers)


# ---------------------------------------------------------------------------
# The total classification (R13.1, R13.2)
# ---------------------------------------------------------------------------


class ModuleRecord(BaseModel):
    """One classified first-party module. Exactly one class, always."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    dotted: str | None
    loc: int
    liveness: LivenessClass
    seam: SeamMarker | None = None


class Classification(BaseModel):
    """A total classification of the scanned first-party module set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    modules: tuple[ModuleRecord, ...]
    #: Every marker found anywhere, including the inert and the malformed ones.
    markers: tuple[SeamMarker, ...]

    def of(self, liveness: LivenessClass) -> tuple[ModuleRecord, ...]:
        return tuple(m for m in self.modules if m.liveness is liveness)

    @property
    def counts(self) -> Mapping[str, int]:
        return {c.value: len(self.of(c)) for c in CLASS_ORDER}

    @property
    def lines(self) -> Mapping[str, int]:
        return {c.value: sum(m.loc for m in self.of(c)) for c in CLASS_ORDER}

    @property
    def total(self) -> int:
        return len(self.modules)

    @property
    def dead_paths(self) -> tuple[str, ...]:
        return tuple(m.path for m in self.of(LivenessClass.DEAD))

    @property
    def unreachable_paths(self) -> frozenset[str]:
        """Paths no non-test module reaches: the DEAD set plus the exempted seams.

        R13.9 measures a dropped baseline name against *dormancy*, not against class
        membership, so a seam-marked module still counts as dormant here -- the marker
        exempts it from the FAIL, it does not make it reachable.
        """
        return frozenset(
            m.path
            for m in self.modules
            if m.liveness in (LivenessClass.DEAD, LivenessClass.SEAM_EXEMPT)
        )


def _assert_total(scanned: Sequence[str], records: Sequence[ModuleRecord]) -> None:
    """Totality is checked, not assumed (R13.1).

    Three conditions together make the classification a partition:
    every scanned file yields exactly one record (cardinality), no path appears twice
    (disjointness), and every record's class is one of the five. A violation raises,
    and :func:`evaluate` reports the raise as ``UNAVAILABLE`` -- a partition that does
    not partition can never read as a pass.

    A *fourth* condition, and the reason this function rejects the empty set: a scan that
    found no module has nothing to partition, so "every module is classified" is
    vacuously true and would read as a pass over zero evidence. That is precisely the
    shape I-7 refuses, and it is the same call ``agency_truth.evaluate_actuation([])``
    makes when a sweep discovers no handler. An empty classification is therefore
    ``UNAVAILABLE``, never a pass.
    """
    if not scanned:
        raise ClassificationError(
            "no first-party module was scanned, so there is nothing to partition and "
            "nothing is proven: an empty classification is unavailable, never a pass (I-7)"
        )
    expected = set(scanned)
    seen = [r.path for r in records]
    duplicates = sorted({p for p in seen if seen.count(p) > 1})
    if duplicates:
        raise ClassificationError(
            f"classification is not disjoint: {len(duplicates)} path(s) classified twice: "
            + ", ".join(duplicates[:5])
        )
    got = set(seen)
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    if missing or extra:
        raise ClassificationError(
            f"classification is not total: {len(missing)} scanned module(s) unclassified"
            + (f" ({', '.join(missing[:5])})" if missing else "")
            + f", {len(extra)} classified module(s) not scanned"
            + (f" ({', '.join(extra[:5])})" if extra else "")
        )
    stray = sorted({r.path for r in records if r.liveness not in set(LivenessClass)})
    if stray:
        raise ClassificationError(
            "classification produced a class outside the five: " + ", ".join(stray[:5])
        )


class ModuleFacts(BaseModel):
    """Everything the classification needs about one module, already gathered.

    The seam for Property 27 (task 8.12): a generated sequence of these is "any
    first-party module graph", so totality and the exemption rule can be exercised
    without a tree on disk.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    dotted: str | None = None
    loc: int = 0
    #: Reachable from a live docker-compose entrypoint.
    alive: bool = False
    #: A test module by path/filename convention.
    test: bool = False
    #: Reachable from scripts/ or referenced by Makefile / CI / compose.
    tooling: bool = False
    #: Every seam marker found in the module's real comments, valid or not.
    markers: tuple[SeamMarker, ...] = ()


def classify_facts(facts: Sequence[ModuleFacts]) -> Classification:
    """Pure five-class classification over already-gathered facts (R13.1, R13.2).

    The cascade is ordered so that the seam marker is *only* consulted for a module that
    would otherwise be DEAD -- which is precisely R13.2's "THE liveness check SHALL
    exempt only modules carrying that marker". The final branch is unconditional, so no
    module can fall through unclassified, and :func:`_assert_total` then proves the five
    buckets partition the input rather than trusting that they do.

    No I/O: this is the function Property 27 drives.
    """
    records: list[ModuleRecord] = []
    markers: list[SeamMarker] = []
    for fact in facts:
        if fact.alive:
            liveness = LivenessClass.ALIVE
        elif fact.test:
            liveness = LivenessClass.TEST
        elif fact.tooling:
            liveness = LivenessClass.TOOLING
        elif any(m.valid for m in fact.markers):
            liveness = LivenessClass.SEAM_EXEMPT
        else:
            liveness = LivenessClass.DEAD

        effective = liveness is LivenessClass.SEAM_EXEMPT
        seam: SeamMarker | None = None
        for marker in fact.markers:
            resolved = marker.model_copy(
                update={
                    "effective": effective and marker.valid,
                    "detail": marker.detail
                    or (
                        ""
                        if effective
                        else f"inert: module is {liveness.value}, so the marker exempts nothing"
                    ),
                }
            )
            markers.append(resolved)
            if seam is None and resolved.valid:
                seam = resolved
        records.append(
            ModuleRecord(
                path=fact.path,
                dotted=fact.dotted,
                loc=fact.loc,
                liveness=liveness,
                seam=seam,
            )
        )

    _assert_total(tuple(f.path for f in facts), records)
    return Classification(modules=tuple(records), markers=tuple(markers))


def gather_facts() -> tuple[ModuleFacts, ...]:
    """Read the tree once and produce the facts :func:`classify_facts` consumes."""
    files = _iter_first_party_files()
    alive = _reachable(LIVE_ENTRYPOINTS)
    haystack = _haystack()
    tooling_roots = (
        sorted((ROOT / "scripts").rglob("*.py"))
        + [f for f in files if is_test_path(_rel(f), f.name)]
        + _python_m_roots(haystack)
    )
    tooling = _reachable(tooling_roots)

    facts: list[ModuleFacts] = []
    for f in files:
        rel = _rel(f)
        dotted = _module_name(f)
        resolved = f.resolve()
        facts.append(
            ModuleFacts(
                path=rel,
                dotted=dotted,
                loc=_loc(f),
                alive=resolved in alive,
                test=is_test_path(rel, f.name),
                tooling=resolved in tooling or _referenced(rel, dotted, haystack),
                markers=scan_seam_markers(f),
            )
        )
    return tuple(facts)


def classify_modules() -> Classification:
    """Classify every first-party Python module into exactly one of five classes."""
    return classify_facts(gather_facts())


# The pre-8.11 `classify() -> {CLASS: [(path, loc)]}` bucket view is gone. Its only
# caller was C44, which now consumes `evaluate()`, and keeping an unreferenced wrapper
# in the module that enforces R13 would be the exact pattern R13 charges. The pure seam
# is `classify_facts`; the reporting surface is `evaluate`.


# ---------------------------------------------------------------------------
# Projection B (R13.7) -- invariant symbols only tests invoke
# ---------------------------------------------------------------------------

#: The referrer corpus for symbol-level reachability. Wider than the classification's
#: FIRST_PARTY set on purpose: `uplift/` is not a first-party *package* for the import
#: graph, but `uplift.uplift_floor.is_proven_uplift` is a declared R13.7 subject, so a
#: production caller anywhere in the tree must be visible.
REFERRER_ROOTS = (
    *SCANNED_PACKAGES,
    "packages",
    "uplift",
    "tests",
)


class InvariantSymbol(BaseModel):
    """A symbol that encodes an invariant precondition or postcondition (R13.7)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    invariant: str
    #: ``contract-decorator`` (found by AST) or ``declared`` (named in the baseline).
    source: str
    defined_in: str | None = None
    #: Callers recorded in the named baseline, when the subject came from there.
    recorded_callers: int | None = None
    wired_by: str | None = None


class ReferrerIndex:
    """Per-file dotted imports and attribute names, parsed once.

    Reachability of a symbol is decided from imports plus attribute usage, which covers
    both ``from mod import sym`` and ``import mod`` + ``mod.sym``. Reading the tree is
    the authority; a count recorded in a file is only ever the *compared* value.

    :meth:`from_edges` builds one without touching disk -- the third seam for Property
    27 (task 8.12), so symbol-level reachability can be driven from generated edges.
    """

    def __init__(self, files: Sequence[Path]) -> None:
        self._imports: dict[str, frozenset[str]] = {}
        self._attrs: dict[str, frozenset[str]] = {}
        self._is_test: dict[str, bool] = {}
        for path in files:
            tree = _parse(path)
            if tree is None:
                continue
            rel = _rel(path)
            dotted: set[str] = set()
            attrs: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dotted.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        dotted.add(node.module)
                        for alias in node.names:
                            dotted.add(f"{node.module}.{alias.name}")
                elif isinstance(node, ast.Attribute):
                    # Attribute access only. Bare `ast.Name` ids would make any local
                    # variable that happens to share a symbol's name read as a call
                    # site, and a false production caller silently excuses a FAIL.
                    attrs.add(node.attr)
            self._imports[rel] = frozenset(dotted)
            self._attrs[rel] = frozenset(attrs)
            self._is_test[rel] = is_test_path(rel, path.name)

    @classmethod
    def from_edges(
        cls,
        edges: Mapping[str, tuple[frozenset[str], frozenset[str]]],
        *,
        tests: Iterable[str] = (),
    ) -> "ReferrerIndex":
        """Build an index from ``{path: (dotted_imports, attribute_names)}``. No I/O."""
        index = cls(())
        test_paths = set(tests)
        for path, (imports, attrs) in edges.items():
            index._imports[path] = frozenset(imports)
            index._attrs[path] = frozenset(attrs)
            index._is_test[path] = path in test_paths
        return index

    def referrers(self, symbol: str, *, exclude: str | None = None) -> tuple[str, ...]:
        """Files that reference ``symbol``, as repo-relative paths."""
        module, _, name = symbol.rpartition(".")
        if not module or not name:
            return ()
        hits: list[str] = []
        for rel, imports in self._imports.items():
            if rel == exclude:
                continue
            if symbol in imports:
                hits.append(rel)
                continue
            if module in imports and name in self._attrs.get(rel, frozenset()):
                hits.append(rel)
        return tuple(sorted(hits))

    def uses_name(self, path: str, name: str) -> bool:
        """Whether ``path`` accesses ``name`` as an attribute somewhere in its body.

        This is what makes an intra-module call site count. ``ConsensusProtocol
        ._append_context`` carries a ``deal.pre`` and is invoked twelve times inside
        ``protocol.py`` and nowhere else; excluding the defining file would report it as
        test-only, which is false. A self-call is a production call.
        """
        return name in self._attrs.get(path, frozenset())

    def is_test(self, path: str) -> bool:
        return self._is_test.get(path, False)

    def split(self, referrers: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Partition referrers into (non-test, test)."""
        non_test = tuple(sorted(r for r in referrers if not self._is_test.get(r, False)))
        test = tuple(sorted(r for r in referrers if self._is_test.get(r, False)))
        return non_test, test


def _iter_referrer_files() -> list[Path]:
    files: list[Path] = []
    for name in REFERRER_ROOTS:
        base = ROOT / name
        if base.is_dir():
            files += [p for p in base.rglob("*.py") if "__pycache__" not in p.parts]
    root_conftest = ROOT / "conftest.py"
    if root_conftest.is_file():
        files.append(root_conftest)
    return sorted(set(files))


def _decorator_root(node: ast.expr) -> tuple[str, ...]:
    """Flatten a decorator expression to its dotted attribute path."""
    target = node.func if isinstance(node, ast.Call) else node
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return tuple(reversed(parts))


def _contract_message(node: ast.expr) -> str | None:
    """The ``message=`` text of a ``deal`` contract decorator, if present."""
    if not isinstance(node, ast.Call):
        return None
    for keyword in node.keywords:
        if keyword.arg == "message" and isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            if isinstance(value, str):
                return value
    return None


def find_contract_symbols(files: Sequence[Path]) -> tuple[InvariantSymbol, ...]:
    """Every first-party function carrying a ``deal`` pre/post/inv contract (R13.7).

    Mechanical, not curated: the subject set is derived from the tree, so a new contract
    lands under this criterion the moment it is written. The invariant text is the
    decorator's ``message=`` -- which is why the FAIL can name the invariant and not
    merely the symbol.
    """
    found: list[InvariantSymbol] = []
    for path in files:
        rel = _rel(path)
        if is_test_path(rel, path.name):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        module = _module_name(path) or rel.removesuffix(".py").replace("/", ".")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            messages: list[str] = []
            kinds: list[str] = []
            for decorator in node.decorator_list:
                parts = _decorator_root(decorator)
                if len(parts) < 2 or parts[0] != "deal" or parts[1] not in CONTRACT_DECORATORS:
                    continue
                kinds.append(f"deal.{parts[1]}")
                message = _contract_message(decorator)
                if message:
                    messages.append(f"deal.{parts[1]}: {message}")
            if not kinds:
                continue
            invariant = "; ".join(messages) if messages else "; ".join(sorted(set(kinds)))
            found.append(
                InvariantSymbol(
                    symbol=f"{module}.{node.name}",
                    invariant=invariant,
                    source="contract-decorator",
                    defined_in=rel,
                )
            )
    return tuple(sorted(found, key=lambda s: s.symbol))


def declared_invariant_symbols(baseline: DeadModulesBaseline) -> tuple[InvariantSymbol, ...]:
    """The baseline's ``test_only_reachable`` rows that carry an invariant (R13.7).

    These are *declarations of obligation*, not exemptions: the file says so in its own
    header. Production reachability is recomputed from the tree for each one.
    """
    out: list[InvariantSymbol] = []
    for record in baseline.test_only_reachable:
        if not record.invariant:
            continue
        out.append(
            InvariantSymbol(
                symbol=record.symbol,
                invariant=record.invariant,
                source="declared",
                defined_in=None,
                recorded_callers=record.production_callers,
                wired_by=record.wired_by,
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Projection A (R13.3) -- property tests that validate a model, not the shipped code
# ---------------------------------------------------------------------------

#: Sentinel binding for a default/namespace import: the whole module is used, so no
#: single exported symbol can be attributed.
WHOLE_MODULE = "*"


class _TsModule(BaseModel):
    """One frontend source file's import edges."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    is_test: bool
    #: target repo-relative path -> the exported bindings this file imports from it.
    edges: Mapping[str, tuple[str, ...]]


def _is_frontend_test(rel: str, name: str) -> bool:
    """Frontend test-ness: a co-located ``__tests__`` dir, the shared ``src/test``
    harness, or a ``*.test.tsx?`` / ``*.spec.tsx?`` filename."""
    return (
        "/__tests__/" in rel
        or "/test/" in rel
        or bool(re.search(r"\.(?:test|spec)\.tsx?$", name))
    )


def _resolve_ts(specifier: str, source: Path) -> Path | None:
    """Resolve a TS import specifier to a file under ``frontend/src``."""
    target: Path | None = None
    if specifier.startswith("."):
        target = (source.parent / specifier).resolve()
    else:
        for prefix, replacement in FRONTEND_ALIASES.items():
            if specifier.startswith(prefix):
                target = (FRONTEND_SRC / (replacement + specifier[len(prefix):])).resolve()
                break
    if target is None:
        return None
    candidates = [target, *(Path(f"{target}{ext}") for ext in FRONTEND_EXTENSIONS)]
    candidates += [target / f"index{ext}" for ext in FRONTEND_EXTENSIONS]
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix in FRONTEND_EXTENSIONS:
            return candidate
    return None


def _ts_bindings(clause: str) -> tuple[str, ...]:
    """The *value* bindings an import clause pulls in, or ``WHOLE_MODULE``.

    ``a as b`` resolves to ``a`` -- the *exported* name is what a reachability comparison
    has to match. Type-only bindings are deliberately excluded: a type is erased at
    runtime and carries no behaviour, so a property test importing one is not exercising
    a function and reporting it would be noise. ``virtual-window.property.test.ts``
    imports ``type WindowInput`` alongside ``computeWindow``; only the latter is a
    subject. The module edge is still recorded (as ``WHOLE_MODULE``) so a type-only
    import never turns into a spurious module-level projection either.
    """
    text = clause.strip()
    if not text:
        return (WHOLE_MODULE,)
    names: list[str] = []
    braced = re.search(r"\{(?P<body>.*)\}", text, re.DOTALL)
    outside = text[: braced.start()] if braced else text
    # `import type { ... }` / `export type { ... }`: the whole clause is types.
    clause_is_type_only = re.match(r"^type\b", outside.strip()) is not None
    residue = re.sub(r"\btype\b", "", outside).replace(",", "")
    if re.search(r"[A-Za-z_$]", residue):
        names.append(WHOLE_MODULE)  # default or `* as ns` import
    if braced and not clause_is_type_only:
        for piece in braced.group("body").split(","):
            token = piece.strip()
            if not token or re.match(r"^type\b", token):
                continue  # per-binding `type X` modifier
            exported = token.split(" as ")[0].strip()
            if exported:
                names.append(exported)
    return tuple(dict.fromkeys(names)) or (WHOLE_MODULE,)


def _load_frontend_modules() -> tuple[_TsModule, ...]:
    if not FRONTEND_SRC.is_dir():
        return ()
    modules: list[_TsModule] = []
    for path in sorted(FRONTEND_SRC.rglob("*.ts")) + sorted(FRONTEND_SRC.rglob("*.tsx")):
        if "node_modules" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = _rel(path)
        edges: dict[str, list[str]] = {}
        for match in TS_IMPORT_RE.finditer(text):
            target = _resolve_ts(match.group("spec"), path)
            if target is None:
                continue
            edges.setdefault(_rel(target), []).extend(_ts_bindings(match.group("clause")))
        for match in TS_BARE_IMPORT_RE.finditer(text):
            target = _resolve_ts(match.group("spec"), path)
            if target is not None:
                edges.setdefault(_rel(target), []).append(WHOLE_MODULE)
        modules.append(
            _TsModule(
                path=rel,
                is_test=_is_frontend_test(rel, path.name),
                edges={k: tuple(dict.fromkeys(v)) for k, v in edges.items()},
            )
        )
    return tuple(modules)


class ModelProjection(BaseModel):
    """A property test whose target no non-test module imports (R13.3).

    ``subject`` is the thing actually reported: the module path when *nothing* outside
    tests imports it, and ``path::symbol`` when the module is production-reachable but
    the exercised symbol is not. Reporting the file in the second case would be a false
    positive, which is why the resolution is symbol-first.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str
    scope: str  # "module" | "symbol"
    language: str  # "typescript" | "python"
    test: str
    target: str
    production_importers: tuple[str, ...] = ()
    detail: str


def _frontend_model_projections(modules: Sequence[_TsModule]) -> tuple[ModelProjection, ...]:
    non_test = [m for m in modules if not m.is_test]
    module_importers: dict[str, list[str]] = {}
    symbol_importers: dict[tuple[str, str], list[str]] = {}
    for module in non_test:
        for target, bindings in module.edges.items():
            module_importers.setdefault(target, []).append(module.path)
            for binding in bindings:
                symbol_importers.setdefault((target, binding), []).append(module.path)

    rows: list[ModelProjection] = []
    seen: set[tuple[str, str]] = set()
    for module in modules:
        if not module.is_test or not FRONTEND_PROPERTY_TEST_RE.search(module.path):
            continue
        for target, bindings in sorted(module.edges.items()):
            importers = tuple(sorted(set(module_importers.get(target, ()))))
            if not importers:
                key = (target, "module")
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    ModelProjection(
                        subject=target,
                        scope="module",
                        language="typescript",
                        test=module.path,
                        target=target,
                        production_importers=(),
                        detail=(
                            f"{target} is imported by no non-test module; the property test "
                            f"{module.path} validates a MODEL, not the shipped implementation"
                        ),
                    )
                )
                continue
            for binding in sorted(b for b in bindings if b != WHOLE_MODULE):
                if symbol_importers.get((target, binding)):
                    continue
                key = (f"{target}::{binding}", "symbol")
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    ModelProjection(
                        subject=f"{target}::{binding}",
                        scope="symbol",
                        language="typescript",
                        test=module.path,
                        target=target,
                        production_importers=importers,
                        detail=(
                            f"{target}::{binding} is imported by no non-test module (the module "
                            f"itself IS production-reachable via {', '.join(importers[:3])}), so "
                            f"the property test {module.path} validates a MODEL of that symbol; "
                            f"the SYMBOL is reported, not the file"
                        ),
                    )
                )
    return tuple(sorted(rows, key=lambda r: r.subject))


def _python_model_projections(
    files: Sequence[Path], index: ReferrerIndex
) -> tuple[ModelProjection, ...]:
    """Python property tests whose exercised symbol no non-test module imports."""
    rows: list[ModelProjection] = []
    seen: set[str] = set()
    for path in files:
        rel = _rel(path)
        if not is_test_path(rel, path.name) or "propert" not in path.name:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module or node.level:
                continue
            # Only SYNAPSE-owned targets: a third-party helper a property test imports
            # is not a SYNAPSE model, and reporting one would be a false positive.
            if node.module.split(".")[0] not in set(FIRST_PARTY) | set(REFERRER_ROOTS):
                continue
            for alias in node.names:
                symbol = f"{node.module}.{alias.name}"
                if symbol in seen or _resolve(symbol) is not None:
                    continue  # a module, not a symbol
                non_test, _tests = index.split(index.referrers(symbol))
                if non_test:
                    continue
                seen.add(symbol)
                rows.append(
                    ModelProjection(
                        subject=symbol,
                        scope="symbol",
                        language="python",
                        test=rel,
                        target=node.module,
                        production_importers=(),
                        detail=(
                            f"{symbol} is imported by no non-test module; the property test "
                            f"{rel} validates a MODEL, not the shipped implementation"
                        ),
                    )
                )
    return tuple(sorted(rows, key=lambda r: r.subject))


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


class InvariantProjection(BaseModel):
    """One R13.7 subject, judged against the tree.

    ``outcome`` is ``FAIL`` when only tests invoke the symbol, ``PASS`` when a non-test
    module does. A ``PASS`` whose recorded caller count was ``0`` carries ``resolved``
    detail: landing the production caller discharges the obligation and must never be
    punished, so the stale record is a maintenance line, not a failure. The mirror case
    -- a record claiming callers the tree does not have -- is record drift, and that
    fails.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    invariant: str
    source: str
    defined_in: str | None = None
    production_callers: tuple[str, ...] = ()
    test_callers: tuple[str, ...] = ()
    recorded_callers: int | None = None
    wired_by: str | None = None
    resolved: bool = False
    record_drift: bool = False
    outcome: Outcome
    detail: str


class Finding(BaseModel):
    """One clause violation, carrying the message that names its subjects."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    clause: Clause
    detail: str


class LivenessReport(BaseModel):
    """The full module-liveness verdict, persisted canonically."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_file: str
    baseline_version: int | None = None
    #: ``len(dormant)`` from the named baseline -- a projection of the names (R13.9).
    dead_baseline: int
    #: The ``baseline:`` key as committed, for the agreement clause.
    recorded_baseline: int | None = None
    counts: Mapping[str, int] = {}
    lines: Mapping[str, int] = {}
    total_modules: int = 0
    classification_total: bool = False
    dead: tuple[str, ...] = ()
    seam_exempt: tuple[str, ...] = ()
    tooling: tuple[str, ...] = ()
    markers: tuple[SeamMarker, ...] = ()
    new_orphans: tuple[str, ...] = ()
    dropped_dormant: tuple[str, ...] = ()
    resolved_dormant: tuple[str, ...] = ()
    model_projections: tuple[ModelProjection, ...] = ()
    invariant_projections: tuple[InvariantProjection, ...] = ()
    findings: tuple[Finding, ...] = ()
    outcome: Outcome
    exit_code: int
    detail: str

    def canonical_json(self) -> str:
        """Canonical serialisation for a persisted payload."""
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )


def judge_invariant_symbols(
    symbols: Sequence[InvariantSymbol], index: ReferrerIndex
) -> tuple[InvariantProjection, ...]:
    """Recompute reachability for every R13.7 subject. The tree is the authority."""
    merged: dict[str, InvariantSymbol] = {}
    for symbol in symbols:
        existing = merged.get(symbol.symbol)
        if existing is None:
            merged[symbol.symbol] = symbol
            continue
        # A subject found both mechanically and declaratively keeps both invariant
        # texts and the declared bookkeeping, so nothing recorded is lost.
        invariants = [existing.invariant, symbol.invariant]
        merged[symbol.symbol] = existing.model_copy(
            update={
                "invariant": " | ".join(dict.fromkeys(i for i in invariants if i)),
                "source": "contract-decorator+declared",
                "defined_in": existing.defined_in or symbol.defined_in,
                "recorded_callers": (
                    existing.recorded_callers
                    if existing.recorded_callers is not None
                    else symbol.recorded_callers
                ),
                "wired_by": existing.wired_by or symbol.wired_by,
            }
        )

    rows: list[InvariantProjection] = []
    for symbol in merged.values():
        referrers = index.referrers(symbol.symbol, exclude=symbol.defined_in)
        production, tests = index.split(referrers)
        # An intra-module call site is a production call site. A contract on a private
        # method invoked only from its own module is on the production path; excluding
        # the defining file would report it as test-only, which is simply false.
        bare = symbol.symbol.rpartition(".")[2]
        if (
            symbol.defined_in is not None
            and not index.is_test(symbol.defined_in)
            and index.uses_name(symbol.defined_in, bare)
            and symbol.defined_in not in production
        ):
            production = tuple(sorted((*production, symbol.defined_in)))
        recorded = symbol.recorded_callers
        resolved = bool(production) and recorded == 0
        drift = not production and recorded is not None and recorded > 0
        if production and not drift:
            detail = (
                f"{symbol.symbol}: invoked from {len(production)} non-test module(s) "
                f"({', '.join(production[:3])}) -- the invariant is on a production path"
            )
            if resolved:
                detail += (
                    f"; the named baseline still records production_callers: 0"
                    f"{f' (wired_by {symbol.wired_by})' if symbol.wired_by else ''} -- "
                    "the row is discharged and should be updated"
                )
            rows.append(
                InvariantProjection(
                    symbol=symbol.symbol,
                    invariant=symbol.invariant,
                    source=symbol.source,
                    defined_in=symbol.defined_in,
                    production_callers=production,
                    test_callers=tests,
                    recorded_callers=recorded,
                    wired_by=symbol.wired_by,
                    resolved=resolved,
                    outcome=Outcome.PASS,
                    detail=detail,
                )
            )
            continue
        if drift:
            rows.append(
                InvariantProjection(
                    symbol=symbol.symbol,
                    invariant=symbol.invariant,
                    source=symbol.source,
                    defined_in=symbol.defined_in,
                    production_callers=(),
                    test_callers=tests,
                    recorded_callers=recorded,
                    wired_by=symbol.wired_by,
                    record_drift=True,
                    outcome=Outcome.FAIL,
                    detail=(
                        f"{symbol.symbol}: the named baseline records "
                        f"production_callers: {recorded}, but the tree now has none -- "
                        f"a recorded fact has rotted; invariant: {symbol.invariant}"
                    ),
                )
            )
            continue
        rows.append(
            InvariantProjection(
                symbol=symbol.symbol,
                invariant=symbol.invariant,
                source=symbol.source,
                defined_in=symbol.defined_in,
                production_callers=(),
                test_callers=tests,
                recorded_callers=recorded,
                wired_by=symbol.wired_by,
                outcome=Outcome.FAIL,
                detail=(
                    f"{symbol.symbol} encodes an invariant [{symbol.invariant}] and is "
                    f"invoked ONLY from tests ({', '.join(tests[:3]) or 'no caller at all'})"
                    + (f"; wired by {symbol.wired_by}" if symbol.wired_by else "")
                ),
            )
        )
    return tuple(sorted(rows, key=lambda r: r.symbol))


class BaselineVerdict(BaseModel):
    """The named-baseline clauses, decided from a classification alone."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dead_baseline: int
    recorded_baseline: int | None = None
    new_orphans: tuple[str, ...] = ()
    dropped_dormant: tuple[str, ...] = ()
    resolved_dormant: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()


def judge_against_baseline(
    classification: Classification, baseline: DeadModulesBaseline
) -> BaselineVerdict:
    """Pure: judge a classification against the named baseline (R13.1, R13.2, R13.9).

    The second seam for Property 27 (task 8.12) -- no I/O, so a generated classification
    and a generated baseline can be paired arbitrarily.

    Four clauses, and none of them is a suppression:

    * **R13.9 agreement** -- the committed ``baseline:`` must equal ``len(dormant)``. The
      count is a projection of the names, so a hand edit that disagrees with the list is
      itself the failure.
    * **R13.1 new orphan** -- a dead module the baseline does not name.
    * **R13.9 dropped name** -- the named list under-counts the graph's dormancy, which
      is what removing a name while its module is still dormant produces.
    * **R13.2 seam marker** -- a marker that does not parse exempts nothing and fails.

    A name whose module has become reachable is returned in ``resolved_dormant`` and is
    **not** a finding -- discharging the obligation must never be punished.

    ``resolved_dormant`` is measured against *dormancy* (dead plus seam-exempt), not
    against class membership: a seam-marked module is still unreachable, so a name for it
    is not stale. The marker exempts it from the FAIL, it does not make it reachable.
    """
    dead_baseline = baseline.derived_baseline
    dormant_named = baseline.dormant_paths
    unreachable = classification.unreachable_paths
    findings: list[Finding] = []

    if baseline.baseline is not None and baseline.baseline != dead_baseline:
        findings.append(
            Finding(
                clause=Clause.BASELINE_DRIFT,
                detail=(
                    f"{_rel(DEAD_MODULES_FILE)} commits baseline: {baseline.baseline} but names "
                    f"{dead_baseline} dormant module(s); the baseline is a projection of the "
                    "names, so a hand edit that disagrees with the list is itself the failure"
                ),
            )
        )

    dead = classification.dead_paths
    new_orphans = tuple(path for path in dead if path not in dormant_named)
    if new_orphans:
        findings.append(
            Finding(
                clause=Clause.NEW_ORPHAN,
                detail=(
                    f"{len(dead)} dead module(s) against a named baseline of {dead_baseline}; "
                    f"{len(new_orphans)} not named in {_rel(DEAD_MODULES_FILE)}: "
                    + ", ".join(new_orphans[:8])
                    + ("..." if len(new_orphans) > 8 else "")
                    + " -- wire it, remove it, mark it a seam, or declare it dormant"
                ),
            )
        )

    # R13.9's "removed from the baseline" is not directly observable from one snapshot --
    # history is not in the tree. What IS observable is the arithmetic that a removal
    # produces: the named list under-counts the dormancy the graph actually has. When
    # `len(dormant) < len(dead)` at least one dormant module lost its name, and the
    # unnamed dead modules are exactly the candidates, so the FAIL still names them.
    # (A stale name plus a fresh orphan leaves the counts equal, which is why this clause
    # is separate from NEW_ORPHAN rather than derived from it.)
    dropped = new_orphans if dead_baseline < len(dead) else ()
    if dropped:
        findings.append(
            Finding(
                clause=Clause.BASELINE_DROP,
                detail=(
                    f"the named baseline holds {dead_baseline} dormant name(s) but the graph has "
                    f"{len(dead)} dormant module(s), so a name was removed while its module is "
                    "still imported by no non-test module: " + ", ".join(dropped[:8])
                ),
            )
        )

    malformed = tuple(m for m in classification.markers if not m.valid)
    if malformed:
        findings.append(
            Finding(
                clause=Clause.SEAM_MARKER,
                detail=(
                    f"{len(malformed)} seam marker(s) do not parse and therefore exempt "
                    "nothing: "
                    + "; ".join(f"{m.path}:{m.line} ({m.detail})" for m in malformed[:5])
                ),
            )
        )

    return BaselineVerdict(
        dead_baseline=dead_baseline,
        recorded_baseline=baseline.baseline,
        new_orphans=new_orphans,
        dropped_dormant=dropped,
        resolved_dormant=tuple(p for p in dormant_named if p not in unreachable),
        findings=tuple(findings),
    )


def _unavailable(detail: str, *, clause: Clause) -> LivenessReport:
    """No verdict could be formed. Not a pass, and never reported as one (I-7)."""
    return LivenessReport(
        baseline_file=_rel(DEAD_MODULES_FILE),
        dead_baseline=DEAD_BASELINE,
        findings=(Finding(clause=clause, detail=detail),),
        outcome=Outcome.UNAVAILABLE,
        exit_code=EXIT_UNAVAILABLE,
        detail=detail,
    )


def evaluate() -> LivenessReport:
    """Classify the tree, judge it against the named baseline, and run both projections.

    Clause order (all clauses are evaluated; a FAIL is never masked by a later PASS):

    1. **R13.1 totality** -- the five classes partition the scanned module set. A
       violation is ``UNAVAILABLE``: a classification that is not total has no verdict
       to give, and an absent verdict is not a pass (I-7).
    2. **R13.9 baseline agreement** -- the committed ``baseline:`` equals
       ``len(dormant)``.
    3. **R13.1 new orphans** -- each dead module not named in the baseline.
    4. **R13.9 dropped names** -- the named list under-counts the graph's dormancy,
       which is what removing a name while its module is still dormant produces.
    5. **R13.2 seam markers** -- a marker that does not parse exempts nothing and fails.
    6. **R13.7 invariant symbols** -- a symbol encoding an invariant pre/postcondition
       that only tests invoke fails, naming the symbol and the invariant.
    7. **R13.3 model-validating tests** -- reported, never gating. The criterion's verb
       is "SHALL be reported".
    """
    baseline, error = _load_baseline_or_none()
    if baseline is None:
        return _unavailable(
            f"named baseline could not be read, so no dead-module count can be judged: {error}",
            clause=Clause.BASELINE_DRIFT,
        )

    try:
        classification = classify_modules()
    except ClassificationError as exc:
        return _unavailable(str(exc), clause=Clause.TOTALITY)

    dead_baseline = baseline.derived_baseline
    verdict = judge_against_baseline(classification, baseline)
    dead = classification.dead_paths
    new_orphans = verdict.new_orphans
    dropped = verdict.dropped_dormant
    resolved_dormant = verdict.resolved_dormant
    findings: list[Finding] = list(verdict.findings)

    # -- clauses 6 and 7: the two projections -----------------------------------------
    referrer_files = _iter_referrer_files()
    index = ReferrerIndex(referrer_files)
    invariant_rows = judge_invariant_symbols(
        find_contract_symbols(referrer_files) + declared_invariant_symbols(baseline),
        index,
    )
    for row in invariant_rows:
        if row.outcome is not Outcome.FAIL:
            continue
        findings.append(
            Finding(
                clause=(
                    Clause.RECORD_DRIFT if row.record_drift else Clause.INVARIANT_SYMBOL
                ),
                detail=row.detail,
            )
        )

    model_rows = _frontend_model_projections(_load_frontend_modules()) + (
        _python_model_projections(referrer_files, index)
    )

    outcome = Outcome.FAIL if findings else Outcome.PASS
    if outcome is Outcome.PASS and model_rows:
        # R13.3 is a labelling obligation, not a gate: the projection is reported and
        # the verdict stays a pass. `REPORT` keeps that distinction legible.
        outcome = Outcome.REPORT
    exit_code = EXIT_FAIL if outcome is Outcome.FAIL else EXIT_PASS

    if outcome is Outcome.FAIL:
        detail = (
            f"{len(findings)} liveness violation(s): "
            + "; ".join(f.detail for f in findings[:3])
            + ("..." if len(findings) > 3 else "")
        )
    else:
        detail = (
            f"{classification.total} module(s) classified over "
            f"{len(CLASS_ORDER)} classes; {len(dead)} dead <= baseline {dead_baseline}; "
            f"{len(model_rows)} model-validating projection(s) reported"
        )

    return LivenessReport(
        baseline_file=_rel(DEAD_MODULES_FILE),
        baseline_version=baseline.version,
        dead_baseline=dead_baseline,
        recorded_baseline=baseline.baseline,
        counts=classification.counts,
        lines=classification.lines,
        total_modules=classification.total,
        classification_total=True,
        dead=dead,
        seam_exempt=tuple(m.path for m in classification.of(LivenessClass.SEAM_EXEMPT)),
        tooling=tuple(m.path for m in classification.of(LivenessClass.TOOLING)),
        markers=classification.markers,
        new_orphans=new_orphans,
        dropped_dormant=dropped,
        resolved_dormant=resolved_dormant,
        model_projections=model_rows,
        invariant_projections=invariant_rows,
        findings=tuple(findings),
        outcome=outcome,
        exit_code=exit_code,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Reporting (ASCII only)
# ---------------------------------------------------------------------------

_MARKER = {
    Outcome.PASS: "[OK]",
    Outcome.FAIL: "[XX]",
    Outcome.REPORT: "[..]",
    Outcome.UNAVAILABLE: "[??]",
}

CLASS_MEANING: Mapping[str, str] = {
    LivenessClass.ALIVE.value: "runs when a request hits the live VM",
    LivenessClass.TOOLING.value: (
        "offline/batch/CI/training -- invoked via make/CI, not the live request path"
    ),
    LivenessClass.TEST.value: "test modules",
    LivenessClass.SEAM_EXEMPT.value: (
        "would be dead; exempted by an in-source `# synapse: seam(...)` marker (R13.2)"
    ),
    LivenessClass.DEAD.value: "0 importers AND 0 references -- removal candidates",
}


def format_report(report: LivenessReport) -> list[str]:
    """ASCII-only human summary; every failure names its own subjects."""
    lines: list[str] = []
    if report.outcome is Outcome.UNAVAILABLE:
        lines.append(f"{_MARKER[report.outcome]} module-liveness: {report.detail}")
        return lines

    for name in (c.value for c in CLASS_ORDER):
        lines.append(
            f"{name:12} {report.counts.get(name, 0):4} files  "
            f"{report.lines.get(name, 0):7} lines"
        )
    lines.append(
        f"{'TOTAL':12} {report.total_modules:4} files"
        f"   (classification is total over {len(CLASS_ORDER)} classes)"
    )
    lines.append("")

    if report.dead:
        lines.append("DEAD modules (0 importers, 0 references):")
        lines += [f"  {path}" for path in report.dead]
    if report.seam_exempt:
        lines.append("SEAM_EXEMPT modules (in-source marker; R13.2):")
        lines += [f"  {path}" for path in report.seam_exempt]
    inert = [m for m in report.markers if not m.effective]
    if inert:
        lines.append("Seam markers that exempt nothing:")
        lines += [f"  {m.path}:{m.line} {m.detail}" for m in inert]

    lines.append("")
    lines.append(
        f"R13.3 model-validating projections ({len(report.model_projections)}) "
        "-- reported, not gating:"
    )
    for row in report.model_projections:
        lines.append(f"  [..] {row.detail}")
    if not report.model_projections:
        lines.append("  (none)")

    lines.append("")
    lines.append(
        f"R13.7 invariant-symbol projections ({len(report.invariant_projections)}):"
    )
    for row in report.invariant_projections:
        lines.append(f"  {_MARKER[row.outcome]} {row.detail}")
    if not report.invariant_projections:
        lines.append("  (none)")

    lines.append("")
    lines.append(
        f"named baseline {report.baseline_file}: dormant {report.dead_baseline} "
        f"(recorded {report.recorded_baseline}); dead {len(report.dead)}"
    )
    for path in report.resolved_dormant:
        lines.append(
            f"  [..] {path} is named dormant but is now reachable -- drop the name"
        )
    for finding in report.findings:
        lines.append(f"  [XX] {finding.clause.value}: {finding.detail}")

    if report.outcome is Outcome.FAIL:
        lines.append(
            "[XX] module-liveness: FAIL - a new orphan, a baseline disagreement, an "
            "unparseable seam marker, or an invariant symbol only tests invoke."
        )
    elif report.outcome is Outcome.REPORT:
        lines.append(
            "[OK] module-liveness: every module is classified and the dead set is within "
            "the named baseline; the projections above are labels, not failures."
        )
    else:
        lines.append(
            "[OK] module-liveness: classification total, dead set within the named "
            "baseline, every invariant symbol on a production path."
        )
    return lines


def _write_md(path: Path, report: LivenessReport) -> None:
    """Regenerate ``docs/state/MODULE_INVENTORY.md`` from one evaluation."""
    lines = ["# SYNAPSE - Module-Liveness Inventory (Python, generated)", ""]
    lines.append(
        "> Generated by `scripts/audit/module_liveness.py` - an AST import graph rooted at the"
    )
    lines.append(
        "> live docker-compose.gcp.yml entrypoints. Regenerate with `--md`. Frontend (~14k TS/TSX)"
    )
    lines.append(
        "> and infra YAML are measured separately (see docs/state/CURRENT.md live-system map)."
    )
    lines.append(">")
    lines.append(
        "> The classification is **total** over five classes (R13.1): every scanned module lands"
    )
    lines.append(
        "> in exactly one. The only exemption from DEAD is an in-source"
    )
    lines.append(
        '> `# synapse: seam(reason="...", adr="ADR-0NN")` marker (R13.2), and the baseline is the'
    )
    lines.append(
        f"> named list in `{report.baseline_file}`, not a number (R13.9)."
    )
    lines.append("")
    lines.append("| Category | Files | Lines | Meaning |")
    lines.append("| --- | --- | --- | --- |")
    for name in (c.value for c in CLASS_ORDER):
        lines.append(
            f"| {name} | {report.counts.get(name, 0)} | {report.lines.get(name, 0)} | "
            f"{CLASS_MEANING[name]} |"
        )
    lines.append(f"| **TOTAL** | **{report.total_modules}** | | classification is total |")

    lines.append("")
    lines.append("## R13.3 - property tests that validate a model")
    lines.append("")
    if report.model_projections:
        for row in report.model_projections:
            lines.append(f"- `{row.subject}` ({row.scope}, {row.language}) - via `{row.test}`")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## R13.7 - symbols encoding an invariant")
    lines.append("")
    if report.invariant_projections:
        for row in report.invariant_projections:
            state = "on a production path" if row.outcome is Outcome.PASS else "TEST-ONLY"
            lines.append(f"- `{row.symbol}` - {state} - invariant: {row.invariant}")
    else:
        lines.append("- none")

    members_by_class: Mapping[str, tuple[str, ...]] = {
        LivenessClass.DEAD.value: report.dead,
        LivenessClass.SEAM_EXEMPT.value: report.seam_exempt,
        LivenessClass.TOOLING.value: report.tooling,
    }
    for name, members in members_by_class.items():
        lines.append("")
        lines.append(f"## {name}")
        lines += [f"- `{item}`" for item in sorted(members)] or ["- none"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    as_json: bool = False,
    check: bool = False,
    md: Path | None = None,
    out: Path | None = None,
) -> int:
    report = evaluate()
    if as_json:
        print(report.canonical_json())
    else:
        for line in format_report(report):
            print(line)
    if md is not None:
        if report.outcome is Outcome.UNAVAILABLE:
            # Never publish an inventory from a run that produced no classification:
            # zeros would read as facts (I-7).
            print(f"\n[??] refusing to write {_rel(md)}: {report.detail}")
        else:
            _write_md(md, report)
            print(f"\nwrote {_rel(md)}")
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.canonical_json(), encoding="utf-8")
    return report.exit_code if check else EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-module-liveness")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 pass / 1 liveness violation / 2 unavailable (classification not total).",
    )
    parser.add_argument("--json", action="store_true", help="Emit the canonical JSON report.")
    parser.add_argument("--md", metavar="FILE", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="Persist the canonical report.")
    args = parser.parse_args(argv)
    return run(as_json=args.json, check=args.check, md=args.md, out=args.out)


if __name__ == "__main__":
    sys.exit(main())
