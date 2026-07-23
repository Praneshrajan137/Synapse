"""Make the *oracle honesty gap* mechanically visible (R8, ADR-042 lineage).

The ``tests/oracle/`` suite is SYNAPSE's "Layer 6": each test compares an
agent's claim to a Digital-Twin Monte-Carlo simulation. Their **docstrings**
promise a measurable outcome ("revenue within 20% of predicted delta", "CO2
within 10%", "stockout in >= 95% of runs"), but several **bodies** only assert
scaffolding facts (scenario count, non-negative order counts) and never check
the promised bound. That is the latent lie this auditor exposes: a docstring
that claims verification the code never performs.

Mirroring ``training_truth.py``'s ``ast.walk`` technique, this script AST-walks
every test function in ``tests/oracle/`` and flags a **docstring-body
mismatch** when *all* of the following hold (R8.2):

  * the test has a **non-empty docstring** (R8.7 - no docstring => never flag);
  * that docstring **describes a measurable outcome** - it contains a
    percentage, a numeric comparison, a tolerance phrase, or a directional
    bound keyword (R8.7 - no measurable outcome => never flag);
  * the test body contains **no assertion referencing that outcome** - none of
    the ``assert`` statements (nor the local names feeding them) mention any of
    the docstring's domain terms.

For every mismatch it reports the **fully qualified test name** (pytest node id
``path::Class::test``) and the **specific unasserted claim** (the measurable
docstring sentence + the domain terms that no assertion touches) (R8.3).

Run::

    python -m scripts.audit.oracle_truth            # human table
    python -m scripts.audit.oracle_truth --json      # machine JSON
    python -m scripts.audit.oracle_truth --check      # exit 1 iff any mismatch (R8.4)

``--check`` exits non-zero **iff** at least one unresolved docstring-body
mismatch remains, and zero when none remain (R8.4). It is surfaced through
``verify_claims.py`` (R8.6) so a reintroduced mismatch fails CI.

### Heuristic (documented on purpose - honesty about our own honesty gate)

*"Describes a measurable outcome"* :data:`_MEASURABLE_KEYWORDS` + a percentage
regex + a "number next to a comparator" regex. A docstring like "should produce
similar distributions" (no number, no comparator, no bound keyword) is treated
as **not** measurable and is never flagged.

*"Assertion referencing that outcome"* : we tokenize the docstring into domain
terms (alphabetic words >= 4 chars, minus english/scaffolding stopwords) and
tokenize every ``assert`` expression - splitting ``snake_case``/``camelCase``
identifiers, attribute names, and string subscript keys (e.g.
``kpi_means["revenue"]`` -> ``{kpi, means, revenue}``). Names used inside an
assert are expanded one level through local assignments so ``x = r.kpi_means[
"revenue"]; assert x > 0`` still counts as referencing ``revenue``. If any
domain term overlaps (equality, substring >= 4 chars, or a simple trailing-``s``
stem) an asserted token, the outcome is considered asserted and the test is
**not** flagged. Scaffolding tokens (``scenario``/``scenarios`` count,
``simulation``, ``twin`` ...) are deliberately excluded so a vacuous
``assert n_scenarios == 1000`` never grants false credit (R8.1's failure mode).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORACLE_DIR = ROOT / "tests" / "oracle"

# --- baseline-allowlist ratchet (R8.6) ------------------------------------
# ``--check`` is strict (exit 1 on ANY mismatch, R8.4) — that is the raw signal
# the property test (task 13.2) locks in and MUST NOT change. But CI cannot be
# green-at-zero today: four ``tests/oracle/`` tests carry a *pre-existing*
# docstring-body mismatch that predates this spec. Task 13.3 repaired only the
# pricing oracle. To honor R8.6 ("a *reintroduced* docstring-body mismatch
# fails CI") without failing on debt outside this spec's scope, we lock in an
# explicit, version-controlled baseline of the known pre-existing mismatch
# node_ids — the same honesty-ratchet pattern the coverage / stryker / uplift
# gates use. The baseline-aware check PASSES while current mismatches are a
# SUBSET of this allowlist and FAILS the moment a NON-allowlisted (new or
# reintroduced) mismatch appears. Repairing a listed test and deleting it from
# this set (tightening the ratchet) is encouraged but not required here.
KNOWN_BASELINE: frozenset[str] = frozenset(
    {
        # CO2 "within 10%" claim; body asserts only orders>=0 / n_scenarios.
        # Known pre-existing oracle debt — NOT introduced by this spec.
        "tests/oracle/test_carbon_estimate_oracle.py::TestCarbonEstimateOracle::test_carbon_estimate_reasonable",
        # "90% conformal interval ... >= 85%" claim; body asserts orders ordering.
        # Known pre-existing oracle debt — NOT introduced by this spec.
        "tests/oracle/test_demand_calibration_oracle.py::TestDemandCalibrationOracle::test_demand_within_conformal_interval",
        # "route cost within 15%" claim; body asserts mean_delivery>0.
        # Known pre-existing oracle debt — NOT introduced by this spec.
        "tests/oracle/test_route_cost_oracle.py::TestRouteCostOracle::test_route_cost_within_threshold",
        # "stockout in >= 95%" claim; body asserts spoilage<0.1.
        # Known pre-existing oracle debt — NOT introduced by this spec.
        "tests/oracle/test_stockout_oracle.py::TestStockoutOracle::test_stockout_rate_below_threshold",
    }
)

# --- "measurable outcome" detection ---------------------------------------
# A docstring describes a measurable outcome if it carries a percentage, a
# number sitting next to a comparator, or one of these bound / tolerance /
# directional keywords.
_MEASURABLE_KEYWORDS: frozenset[str] = frozenset(
    {
        "within", "tolerance", "threshold", "at least", "at most",
        "no more than", "no less than", "less than", "greater than",
        "more than", "fewer than", "exceed", "exceeds", "exceeding",
        "below", "above", "higher", "lower", "reduce", "reduces",
        "reducing", "reduction", "inflate", "inflates", "increase",
        "increases", "decrease", "decreases", "degrade", "degradation",
        "percent", "percentage", "ratio", "bound", "bounded",
    }
)
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_NUM_COMPARATOR_RE = re.compile(r"(?:>=|<=|>|<|~)\s*\d|\d+(?:\.\d+)?\s*%?")
_COMPARATOR_SYMBOL_RE = re.compile(r">=|<=|>|<")

# --- tokenization ----------------------------------------------------------
# Words too generic (english glue) or too scaffolding-flavored to count as a
# domain outcome term. Excluding scenario/count/simulation is deliberate: a
# vacuous ``assert n_scenarios == 1000`` must never grant credit for a docstring
# that promised a revenue/CO2/stockout bound (R8.1's exact failure mode).
_STOPWORDS: frozenset[str] = frozenset(
    {
        # english glue / filler >= 4 chars
        "must", "should", "shall", "produce", "produces", "produced",
        "with", "that", "this", "then", "than", "from", "into", "have",
        "same", "each", "when", "will", "must", "does", "only", "also",
        "over", "very", "some", "more", "most", "less", "such", "both",
        "make", "makes", "made", "using", "used", "still", "were", "been",
        "they", "their", "them", "there", "here", "what", "which", "while",
        "vs", "was", "now", "fix", "fixed",
        # measurement / scaffolding terms that are NOT the domain outcome
        "test", "tests", "oracle", "layer", "scenario", "scenarios",
        "count", "counts", "simulation", "simulate", "simulated", "twin",
        "monte", "carlo", "runs", "run", "result", "results", "value",
        "values", "actual", "estimate", "estimated", "distribution",
        "distributions", "similar", "reasonable", "batch", "batches",
        "sample", "samples", "seed", "seeds", "means", "mean",
    }
)


def _tokenize(text: str) -> set[str]:
    """Split identifiers/words into lowercase alpha tokens.

    Handles ``snake_case`` and ``camelCase`` and keeps tokens with >= 3 chars.
    """
    tokens: set[str] = set()
    # split camelCase boundaries first
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    for raw in re.split(r"[^A-Za-z]+", spaced):
        if len(raw) >= 3:
            tokens.add(raw.lower())
    return tokens


@dataclass
class Mismatch:
    node_id: str  # fully qualified pytest node id (R8.3)
    file: str
    line: int
    docstring_summary: str
    unasserted_terms: list[str]

    @property
    def claim(self) -> str:
        terms = ", ".join(self.unasserted_terms) if self.unasserted_terms else "-"
        return f'"{self.docstring_summary}" (unasserted term(s): {terms})'


@dataclass
class TestReport:
    node_id: str
    file: str
    line: int
    has_docstring: bool
    measurable: bool
    mismatch: Mismatch | None = None


@dataclass
class ModuleReport:
    file: str
    tests: list[TestReport] = field(default_factory=list)


def _is_measurable(docstring: str) -> bool:
    """True if the docstring describes a measurable outcome (R8.2/R8.7)."""
    low = docstring.lower()
    if _PERCENT_RE.search(low):
        return True
    if _COMPARATOR_SYMBOL_RE.search(low) and any(ch.isdigit() for ch in low):
        return True
    for kw in _MEASURABLE_KEYWORDS:
        # word-boundary match for single words; substring is fine for phrases
        if " " in kw:
            if kw in low:
                return True
        elif re.search(rf"\b{re.escape(kw)}\b", low):
            return True
    return False


def _measurable_sentence(docstring: str) -> str:
    """Pick the most representative measurable sentence for the report."""
    # collapse whitespace, split into sentences on '.' boundaries
    flat = " ".join(docstring.split())
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", flat) if p.strip()]
    for part in parts:
        if _is_measurable(part):
            return part
    return flat


def _docstring_terms(docstring: str) -> set[str]:
    """Domain terms (>= 4 chars, not stopwords) that carry the outcome meaning."""
    return {t for t in _tokenize(docstring) if len(t) >= 4 and t not in _STOPWORDS}


def _assert_reference_tokens(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Tokens referenced by the function's ``assert`` statements.

    Local names used inside an assert are expanded one level through simple
    ``name = <rhs>`` assignments so intermediate variables still grant credit.
    """
    # Map local variable name -> tokens from its assignment RHS.
    local_defs: dict[str, set[str]] = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            rhs_tokens = _expr_tokens(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    local_defs.setdefault(target.id, set()).update(rhs_tokens)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                local_defs.setdefault(node.target.id, set()).update(
                    _expr_tokens(node.value)
                )

    tokens: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            asserted = _expr_tokens(node.test)
            if node.msg is not None:
                asserted |= _expr_tokens(node.msg)
            # expand referenced local names one level
            expanded: set[str] = set()
            for name_id in _referenced_names(node.test):
                expanded |= local_defs.get(name_id, set())
            tokens |= asserted | expanded
    return tokens


def _referenced_names(expr: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)}


def _expr_tokens(expr: ast.AST) -> set[str]:
    """Tokens from names, attribute names, and string constants in an expr."""
    tokens: set[str] = set()
    for node in ast.walk(expr):
        if isinstance(node, ast.Name):
            tokens |= _tokenize(node.id)
        elif isinstance(node, ast.Attribute):
            tokens |= _tokenize(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            tokens |= _tokenize(node.value)
    return tokens


def _term_referenced(term: str, asserted: set[str]) -> bool:
    """True if a docstring domain term overlaps any asserted token."""
    if term in asserted:
        return True
    stem = term[:-1] if term.endswith("s") and len(term) > 4 else term
    for tok in asserted:
        if tok == term:
            return True
        # substring overlap, only for reasonably long tokens to avoid noise
        if len(term) >= 4 and len(tok) >= 4 and (term in tok or tok in term):
            return True
        tok_stem = tok[:-1] if tok.endswith("s") and len(tok) > 4 else tok
        if stem == tok_stem:
            return True
    return False


def _iter_test_functions(tree: ast.Module):
    """Yield (qualname_parts, func_node) for every ``test*`` function.

    Handles both module-level test functions and methods inside test classes.
    """

    def visit(node: ast.AST, prefix: list[str]):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                yield from visit(child, prefix + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name.startswith("test"):
                    yield (prefix + [child.name], child)

    yield from visit(tree, [])


def scan_module(path: Path) -> ModuleReport:
    rel = path.relative_to(ROOT).as_posix()
    report = ModuleReport(file=rel)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return report

    for parts, func in _iter_test_functions(tree):
        node_id = rel + "::" + "::".join(parts)
        docstring = ast.get_docstring(func, clean=True) or ""
        docstring = docstring.strip()
        has_doc = bool(docstring)
        measurable = has_doc and _is_measurable(docstring)

        test_report = TestReport(
            node_id=node_id,
            file=rel,
            line=func.lineno,
            has_docstring=has_doc,
            measurable=measurable,
        )

        # R8.7: never flag a test with no docstring or no measurable outcome.
        if has_doc and measurable:
            terms = _docstring_terms(docstring)
            asserted = _assert_reference_tokens(func)
            unasserted = sorted(t for t in terms if not _term_referenced(t, asserted))
            # A mismatch exists when NONE of the docstring's domain terms are
            # referenced by any assertion (R8.2). If the docstring had no domain
            # terms at all (pure comparator words), there is nothing to verify -
            # treat as not-measurable and do not flag.
            if terms and len(unasserted) == len(terms):
                test_report.mismatch = Mismatch(
                    node_id=node_id,
                    file=rel,
                    line=func.lineno,
                    docstring_summary=_measurable_sentence(docstring),
                    unasserted_terms=unasserted,
                )

        report.tests.append(test_report)
    return report


def collect() -> list[ModuleReport]:
    reports: list[ModuleReport] = []
    if not ORACLE_DIR.is_dir():
        return reports
    for path in sorted(ORACLE_DIR.glob("test_*.py")):
        reports.append(scan_module(path))
    return reports


def all_mismatches(reports: list[ModuleReport]) -> list[Mismatch]:
    out: list[Mismatch] = []
    for r in reports:
        for t in r.tests:
            if t.mismatch is not None:
                out.append(t.mismatch)
    return out


def unresolved_mismatches(
    mismatches: list[Mismatch], baseline: frozenset[str] = KNOWN_BASELINE
) -> list[Mismatch]:
    """Mismatches NOT covered by the baseline allowlist (new/reintroduced, R8.6).

    Returns the mismatches whose ``node_id`` is not in ``baseline``. An empty
    result means every current mismatch is a known pre-existing entry (current
    set is a SUBSET of the baseline); a non-empty result means a NEW or
    reintroduced docstring-body mismatch appeared and CI must fail.
    """
    return [m for m in mismatches if m.node_id not in baseline]


def check_against_baseline(baseline: frozenset[str] = KNOWN_BASELINE) -> int:
    """Baseline-aware gate: exit 0 iff current mismatches subset baseline (R8.6).

    Unlike strict ``run(check=True)`` (which fails on ANY mismatch, R8.4), this
    tolerates the known pre-existing debt and fails ONLY when a non-allowlisted
    (reintroduced or new) mismatch is present.
    """
    unresolved = unresolved_mismatches(all_mismatches(collect()), baseline)
    return 1 if unresolved else 0


def run(*, as_json: bool = False, check: bool = False) -> int:
    reports = collect()
    mismatches = all_mismatches(reports)
    total_tests = sum(len(r.tests) for r in reports)

    if as_json:
        payload = {
            "summary": {
                "modules_scanned": len(reports),
                "tests_scanned": total_tests,
                "mismatches": len(mismatches),
            },
            "mismatches": [
                {
                    "node_id": m.node_id,
                    "file": m.file,
                    "line": m.line,
                    "unasserted_claim": m.docstring_summary,
                    "unasserted_terms": m.unasserted_terms,
                }
                for m in mismatches
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for r in reports:
            for t in r.tests:
                if t.mismatch is not None:
                    mark = "[XX]"
                elif not t.has_docstring:
                    mark = "[--]"  # no docstring - never flagged (R8.7)
                elif not t.measurable:
                    mark = "[  ]"  # docstring, no measurable outcome (R8.7)
                else:
                    mark = "[OK]"  # measurable outcome IS asserted
                print(f"{mark} {t.node_id}")
                if t.mismatch is not None:
                    print(f"        {t.file}:{t.line}  docstring-body mismatch")
                    print(f"        claim: {t.mismatch.claim}")
        print()
        print(
            f"Oracle-truth: {len(mismatches)} docstring-body mismatch(es) across "
            f"{total_tests} oracle test(s) in {len(reports)} module(s)."
        )
        if mismatches and not check:
            print(
                "(each flagged test promises a measurable outcome its body never "
                "asserts - repair the assertion or rewrite the docstring, R8.5.)"
            )

    if check:
        return 1 if mismatches else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
