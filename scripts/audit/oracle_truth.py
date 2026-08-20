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
    python -m scripts.audit.oracle_truth --membership # exit 1/2 on oracle-layer findings (R12)

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

## Oracle-layer membership is earned, not declared (R12; design E2.3, RC-3)

The second half of this module answers a different question. The docstring audit
above asks "does this test assert what it says it asserts". Membership asks
"does this test have any standing to judge the thing it names".

The audit finding is that it had none. ``tests/oracle/`` was the Oracle layer
because of its **path**, and each module was an oracle for an agent because of
its **title**. `test_pricing_impact_oracle.py` was titled "Oracle Layer 6:
Pricing Oracle vs Twin revenue impact", imported no ``pricing_oracle`` module at
all, and compared the twin against an algebraic description of the twin - as its
own comment said out loud. A layer whose top rung is self-referential is not a
layer.

So membership is now derived from four observable properties of the test, all
read off its AST (:class:`OracleSubject`):

* ``imports_subject`` - the module imports the component its
  ``@pytest.mark.oracle(subject=...)`` names (R12.1);
* ``invokes_subject_on_asserted_path`` - a value derived from **calling** that
  component reaches an ``assert`` (R12.1). Importing a subject and never running
  it is not an oracle;
* ``reference_independent`` - the value the subject is compared *against* is not
  itself produced by the subject, and the module does not admit that its
  reference is a closed-form restatement of the comparison target (R12.2);
* ``tolerance_constraining`` - a declared tolerance bound is inside the ceiling
  committed in ``infrastructure/quality/oracle-layers.yaml``; a bound wide enough
  to admit a two-fold error is reported **unconstraining** (R12.7).

A test that declares the Oracle layer without earning it FAILs naming that test,
and so does one whose *title* claims the layer while the derivation refuses it -
that clause is the whole point of R12.6, and it is why a rename cannot restore
membership.

The known pre-existing exceptions are carried in a structured allowlist. Each
entry names the rules it excuses, and must carry **both** a dated rationale and
a stated removal condition; an entry missing either is itself a FAIL (R12.5).
The allowlist is the honest label on debt, never an exemption from measurement.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]
ORACLE_DIR = ROOT / "tests" / "oracle"
CONFIG_FILE: Final[Path] = ROOT / "infrastructure" / "quality" / "oracle-layers.yaml"

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
# Every entry carries a dated rationale AND a stated removal condition; the
# auditor FAILs on an entry that carries neither (R12.5). `rules` names exactly
# which findings the entry excuses for that node id — an entry cannot silently
# widen to cover a finding nobody reviewed.
_RAW_ALLOWLIST: Final[tuple[dict[str, object], ...]] = (
    {
        "node_id": (
            "tests/oracle/test_carbon_estimate_oracle.py"
            "::TestCarbonEstimateOracle::test_carbon_estimate_reasonable"
        ),
        "rules": ("docstring-body-mismatch", "oracle-subject-undeclared", "oracle-claim-unearned"),
        "rationale": (
            "Pre-existing oracle debt. The docstring promises a CO2 estimate 'within 10%' "
            "while the body asserts only orders>=0 and n_scenarios, and the module names no "
            "sustainability_agent subject it imports or invokes. Recorded by the "
            "purpose-achievement-audit, not introduced by it."
        ),
        "dated": "2026-06-17",
        "removal_condition": (
            "Delete when the test imports agents.sustainability_agent, invokes its CO2 "
            "estimator on the asserted path, and bounds the estimate against the twin's "
            "fuel/distance simulation — or is re-registered Metamorphic (layer 4)."
        ),
    },
    {
        "node_id": (
            "tests/oracle/test_demand_calibration_oracle.py"
            "::TestDemandCalibrationOracle::test_demand_within_conformal_interval"
        ),
        "rules": ("docstring-body-mismatch", "oracle-subject-undeclared", "oracle-claim-unearned"),
        "rationale": (
            "Pre-existing oracle debt. The docstring promises a '90% conformal interval ... "
            ">= 85%' coverage claim while the body asserts only that a demand spike raises "
            "orders_created, and no demand_prophet module is imported."
        ),
        "dated": "2026-06-17",
        "removal_condition": (
            "Delete when the test imports agents.demand_prophet, invokes its conformal "
            "predictor, and asserts measured interval coverage against twin arrivals."
        ),
    },
    {
        "node_id": (
            "tests/oracle/test_demand_calibration_oracle.py"
            "::TestDemandCalibrationOracle::test_forecast_stability"
        ),
        "rules": (
            "oracle-subject-undeclared",
            "oracle-reference-not-independent",
            "oracle-claim-unearned",
        ),
        "rationale": (
            "Pre-existing oracle debt. This test compares two twin runs to each other, so it "
            "is a twin determinism check with no agent subject at all and no reference "
            "independent of the twin — a Metamorphic (layer 4) property wearing an Oracle "
            "title."
        ),
        "dated": "2026-06-17",
        "removal_condition": (
            "Delete when the test is re-registered Metamorphic (layer 4), which is what "
            "comparing two runs of one simulator is."
        ),
    },
    {
        "node_id": (
            "tests/oracle/test_disruption_response_oracle.py"
            "::TestDisruptionResponseOracle::test_playbook_reduces_degradation"
        ),
        "rules": ("oracle-subject-undeclared", "oracle-claim-unearned"),
        "rationale": (
            "Pre-existing oracle debt. The test asserts a supplier shock inflates the twin's "
            "delivery SLA — a true statement about the twin that involves no "
            "disruption_shield playbook, despite the title."
        ),
        "dated": "2026-06-17",
        "removal_condition": (
            "Delete when the test imports agents.disruption_shield, invokes the playbook "
            "selector, and compares acted-on against no-action twin degradation."
        ),
    },
    {
        "node_id": (
            "tests/oracle/test_route_cost_oracle.py"
            "::TestRouteCostOracle::test_route_cost_within_threshold"
        ),
        "rules": ("docstring-body-mismatch", "oracle-subject-undeclared", "oracle-claim-unearned"),
        "rationale": (
            "Pre-existing oracle debt. The docstring promises route cost 'within 15%' while "
            "the body asserts mean_delivery>0, and no routing_navigator module is imported."
        ),
        "dated": "2026-06-17",
        "removal_condition": (
            "Delete when the test imports agents.routing_navigator, invokes its cost "
            "estimator, and bounds it against the twin's simulated delivery cost."
        ),
    },
    {
        "node_id": (
            "tests/oracle/test_route_cost_oracle.py"
            "::TestRouteCostOracle::test_delivery_time_distribution_reasonable"
        ),
        "rules": ("oracle-subject-undeclared", "oracle-claim-unearned"),
        "rationale": (
            "Pre-existing oracle debt. Asserts p5 <= p50 <= p95 of the twin's own output: a "
            "twin sanity property, not an oracle for any agent."
        ),
        "dated": "2026-06-17",
        "removal_condition": (
            "Delete when the test is moved to the twin's own unit suite, where a "
            "percentile-ordering assertion belongs."
        ),
    },
    {
        "node_id": (
            "tests/oracle/test_stockout_oracle.py"
            "::TestStockoutOracle::test_stockout_rate_below_threshold"
        ),
        "rules": ("docstring-body-mismatch", "oracle-subject-undeclared", "oracle-claim-unearned"),
        "rationale": (
            "Pre-existing oracle debt. The docstring promises 'no stockout in >= 95% of MC "
            "runs' while the body asserts spoilage<0.1, and no inventory_sentinel module is "
            "imported."
        ),
        "dated": "2026-06-17",
        "removal_condition": (
            "Delete when the test imports agents.inventory_sentinel, invokes its reorder "
            "policy, and asserts the twin's measured stockout rate under that policy."
        ),
    },
    {
        "node_id": (
            "tests/oracle/test_stockout_oracle.py::TestStockoutOracle::test_restocks_triggered"
        ),
        "rules": ("oracle-subject-undeclared", "oracle-claim-unearned"),
        "rationale": (
            "Pre-existing oracle debt. Asserts the twin fires restocks during a 4h run "
            "(E-DT-005 regression cover). A twin regression test, not an agent oracle."
        ),
        "dated": "2026-06-17",
        "removal_condition": (
            "Delete when the test is moved to the twin's own regression suite alongside the "
            "other E-DT-* covers."
        ),
    },
)

#: The finding rules an allowlist entry is permitted to excuse. An entry naming
#: anything else is malformed, because nobody reviewed a rule that does not exist.
#: ``allowlist-entry-incomplete`` is deliberately absent: the schema check on the
#: allowlist can never be excused by the allowlist (R12.5).
ALLOWLISTABLE_RULES: Final[frozenset[str]] = frozenset(
    {
        "docstring-body-mismatch",
        "oracle-subject-undeclared",
        "oracle-subject-not-invoked",
        "oracle-reference-not-independent",
        "oracle-claim-unearned",
        "tolerance-unconstraining",
    }
)


class Finding(BaseModel):
    """One violation, naming the test it is about (naming is half the contract)."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    node_id: str
    detail: str


class AllowlistEntry(BaseModel):
    """One reviewed, dated exception, and the condition that retires it (R12.5)."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    rules: tuple[str, ...]
    rationale: str
    dated: date
    removal_condition: str

    def excuses(self, rule: str) -> bool:
        return rule in self.rules


def _entry_defects(index: int, raw: dict[str, object]) -> tuple[str, ...]:
    """Every schema defect in one raw allowlist entry, named (R12.5).

    A dated rationale and a stated removal condition are both required. Either one
    alone leaves an entry that cannot be reviewed: a rationale with no date cannot
    be aged out, and a date with no removal condition never expires.
    """
    defects: list[str] = []
    node_id = raw.get("node_id")
    if not isinstance(node_id, str) or not node_id.strip():
        defects.append(f"entry {index} declares no node_id")

    rules = raw.get("rules")
    if not isinstance(rules, tuple) or not rules:
        defects.append("declares no rules")
    else:
        unknown = sorted(str(r) for r in rules if str(r) not in ALLOWLISTABLE_RULES)
        if unknown:
            defects.append(f"names unknown rule(s): {', '.join(unknown)}")

    rationale = raw.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        defects.append("carries no rationale")

    dated = raw.get("dated")
    if not isinstance(dated, str) or not dated.strip():
        defects.append("carries no date, so its rationale is undated")
    else:
        try:
            date.fromisoformat(dated)
        except ValueError:
            defects.append(f"date {dated!r} is not an ISO-8601 calendar date")

    removal = raw.get("removal_condition")
    if not isinstance(removal, str) or not removal.strip():
        defects.append("states no removal condition, so it can never be retired")

    return tuple(defects)


def allowlist_findings(
    raw_entries: tuple[dict[str, object], ...] = _RAW_ALLOWLIST,
) -> tuple[Finding, ...]:
    """Schema findings over the allowlist itself (R12.5).

    The auditor must fail when a listed entry carries neither a dated rationale nor
    a stated removal condition, so the allowlist is validated before it is allowed
    to excuse anything. A malformed entry is dropped from
    :func:`allowlist_entries`, which means the findings it would have excused
    surface as unresolved as well - the defect is never load-bearing in the
    direction of a pass (I-7).
    """
    findings: list[Finding] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_entries):
        node_id = raw.get("node_id")
        label = node_id if isinstance(node_id, str) and node_id.strip() else f"(entry {index})"
        for defect in _entry_defects(index, raw):
            findings.append(
                Finding(
                    rule="allowlist-entry-incomplete",
                    requirement="R12.5",
                    node_id=label,
                    detail=f"allowlist entry for {label} {defect}",
                )
            )
        if isinstance(node_id, str) and node_id in seen:
            findings.append(
                Finding(
                    rule="allowlist-entry-incomplete",
                    requirement="R12.5",
                    node_id=label,
                    detail=f"allowlist lists {label} twice; merge the entries",
                )
            )
        if isinstance(node_id, str):
            seen.add(node_id)
    return tuple(sorted(findings, key=lambda f: (f.node_id, f.detail)))


def allowlist_entries(
    raw_entries: tuple[dict[str, object], ...] = _RAW_ALLOWLIST,
) -> tuple[AllowlistEntry, ...]:
    """The well-formed entries only. A malformed entry excuses nothing."""
    entries: list[AllowlistEntry] = []
    for index, raw in enumerate(raw_entries):
        if _entry_defects(index, raw):
            continue
        raw_rules = raw["rules"]
        entries.append(
            AllowlistEntry(
                node_id=str(raw["node_id"]),
                rules=tuple(str(r) for r in raw_rules) if isinstance(raw_rules, tuple) else (),
                rationale=str(raw["rationale"]),
                dated=date.fromisoformat(str(raw["dated"])),
                removal_condition=str(raw["removal_condition"]),
            )
        )
    return tuple(entries)


#: Node ids whose *docstring-body mismatch* is pre-existing, allowlisted debt.
#: Derived from the structured allowlist so the two cannot drift apart, and kept
#: under its original name because ``verify_claims.check_oracle_truth`` (C61) and
#: the property test in ``tests/uplift/`` both read it.
KNOWN_BASELINE: frozenset[str] = frozenset(
    entry.node_id for entry in allowlist_entries() if entry.excuses("docstring-body-mismatch")
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


# ===========================================================================
# Oracle-layer membership (R12.1, R12.2, R12.5, R12.6, R12.7)
# ===========================================================================


class ConfigUnavailable(Exception):
    """The committed layer configuration is absent or unusable.

    Raised rather than defaulted. A ceiling this module invented for itself would
    be a threshold nobody reviewed, and a gate running on an invented threshold
    reports a verdict it did not earn. The caller maps this to ``unavailable``,
    which is not a pass (I-7).
    """


class OracleLayerConfig(BaseModel):
    """``infrastructure/quality/oracle-layers.yaml``, parsed."""

    model_config = ConfigDict(frozen=True)

    version: int
    oracle_layer: int
    layer_names: dict[str, str]
    tolerance_ceiling: float

    def layer_name(self, layer: int | None) -> str:
        if layer is None:
            return "(unregistered)"
        return self.layer_names.get(str(layer), f"layer {layer}")


def load_config(path: Path = CONFIG_FILE) -> OracleLayerConfig:
    """Read the committed layer configuration (``encoding='utf-8'``, E-S13-07)."""
    if not path.is_file():
        raise ConfigUnavailable(f"layer configuration not found: {path.name}")
    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigUnavailable(f"layer configuration unreadable: {path.name}: {error}") from error
    if not isinstance(raw, dict):
        raise ConfigUnavailable(f"layer configuration is not a mapping: {path.name}")
    try:
        ceiling = float(raw["tolerance_ceiling"])
        names = raw.get("layer_names") or {}
        config = OracleLayerConfig(
            version=int(raw["version"]),
            oracle_layer=int(raw["oracle_layer"]),
            layer_names={str(k): str(v) for k, v in dict(names).items()},
            tolerance_ceiling=ceiling,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigUnavailable(
            f"layer configuration is missing a required value: {path.name}: {error}"
        ) from error
    if not 0.0 < config.tolerance_ceiling <= 1.0:
        raise ConfigUnavailable(
            f"tolerance_ceiling {config.tolerance_ceiling} is outside (0, 1]: a ceiling "
            "outside that range cannot bound a relative tolerance"
        )
    return config


class OracleSubject(BaseModel):
    """Membership evidence for one test: four observable properties, no titles.

    ``tolerance_constraining`` is deliberately three-valued. ``None`` means the
    test declares no tolerance bound, so none was probed - which is different from
    a bound that was probed and found unconstraining, and different again from one
    inside the committed ceiling.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str
    test_module: str
    declared_subject: str
    declared_layer: int | None
    title_claims_oracle: bool
    imports_subject: bool
    invokes_subject_on_asserted_path: bool
    reference_independent: bool
    tolerance_constraining: bool | None
    tolerance_name: str | None
    tolerance_bound: float | None

    @property
    def earned(self) -> bool:
        """Membership, derived. Path and title contribute nothing (R12.6)."""
        return (
            bool(self.declared_subject)
            and self.imports_subject
            and self.invokes_subject_on_asserted_path
            and self.reference_independent
        )


#: Phrases by which a module admits its reference is a restatement of the thing it
#: compares against rather than an independent computation. The pricing test's own
#: comment ("the twin's own behaviour expressed in closed form") is the specimen
#: this set was written from, and a self-admission is the strongest possible
#: evidence for R12.2 - stronger than any inference this auditor could make.
_CLOSED_FORM_ADMISSIONS: Final[tuple[str, ...]] = (
    "closed form",
    "closed-form",
    "algebraic description",
    "algebraic restatement",
    "restatement of the",
    "own behaviour expressed",
    "own behavior expressed",
    "verified empirically against",
)

#: Names that carry the *reference* side of a comparison - the value the subject is
#: judged against. A test with no such name has nothing to be independent of.
_REFERENCE_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"observed|measured|reference|actual|twin|simulat|result|baseline|delivered|created"
)

#: Constant names that declare a tolerance bound (R12.7).
_TOLERANCE_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:[A-Z0-9]+_)*(TOLERANCE|TOL|BOUND|EPSILON|EPS|MARGIN)(?:_[A-Z0-9]+)*$"
)


def _import_paths(tree: ast.Module) -> tuple[set[str], dict[str, str]]:
    """``(dotted paths imported, local name -> dotted path)`` for one module."""
    paths: set[str] = set()
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                paths.add(alias.name)
                bound[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            paths.add(node.module)
            for alias in node.names:
                dotted = f"{node.module}.{alias.name}"
                paths.add(dotted)
                bound[alias.asname or alias.name] = dotted
    return paths, bound


def _matches_subject(dotted: str, subject: str) -> bool:
    """True when ``dotted`` names the subject, a part of it, or something inside it."""
    return dotted == subject or dotted.startswith(f"{subject}.") or subject.startswith(f"{dotted}.")


def _assignment_edges(*scopes: ast.AST) -> dict[str, set[str]]:
    """``target name -> names referenced by its right-hand side``, across scopes."""
    edges: dict[str, set[str]] = {}
    for scope in scopes:
        for node in ast.walk(scope):
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = list(node.targets), node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            elif isinstance(node, ast.AugAssign):
                targets, value = [node.target], node.value
            if value is None:
                continue
            referenced = _referenced_names(value)
            for target in targets:
                if isinstance(target, ast.Name):
                    edges.setdefault(target.id, set()).update(referenced)
                elif isinstance(target, ast.Tuple):
                    for element in target.elts:
                        if isinstance(element, ast.Name):
                            edges.setdefault(element.id, set()).update(referenced)
    return edges


def _assert_reachable_names(
    func: ast.FunctionDef | ast.AsyncFunctionDef, edges: dict[str, set[str]]
) -> set[str]:
    """Names an ``assert`` depends on, transitively through local assignments.

    ``spoilage = result.kpi_means[...]; assert spoilage < 0.1`` makes both
    ``spoilage`` and ``result`` assert-reachable, which is what lets the reference
    side be recognised through an intermediate variable.
    """
    frontier: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            frontier |= _referenced_names(node.test)
            if node.msg is not None:
                frontier |= _referenced_names(node.msg)
    reached: set[str] = set()
    while frontier:
        name = frontier.pop()
        if name in reached:
            continue
        reached.add(name)
        frontier |= edges.get(name, set()) - reached
    return reached


def _derived_names(seeds: set[str], edges: dict[str, set[str]]) -> set[str]:
    """Forward closure: every name whose value flows from one of ``seeds``."""
    derived = set(seeds)
    changed = True
    while changed:
        changed = False
        for target, referenced in edges.items():
            if target not in derived and referenced & derived:
                derived.add(target)
                changed = True
    return derived


def _call_roots(scope: ast.AST) -> set[str]:
    """Root names of everything called in ``scope`` (``a.b.c()`` -> ``a``)."""
    roots: set[str] = set()
    for node in ast.walk(scope):
        if not isinstance(node, ast.Call):
            continue
        target: ast.expr = node.func
        while isinstance(target, ast.Attribute):
            target = target.value
        if isinstance(target, ast.Name):
            roots.add(target.id)
    return roots


def _marker(decorators: list[ast.expr], name: str) -> ast.Call | ast.Attribute | None:
    """``@pytest.mark.<name>`` on this list of decorators, called or bare."""
    for decorator in decorators:
        node = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(node, ast.Attribute) and node.attr == name:
            inner = node.value
            if isinstance(inner, ast.Attribute) and inner.attr == "mark":
                return decorator if isinstance(decorator, ast.Call) else node
    return None


def _marker_kwarg(marker: ast.Call | ast.Attribute | None, keyword: str) -> object | None:
    if not isinstance(marker, ast.Call):
        return None
    for kw in marker.keywords:
        if kw.arg == keyword and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def _module_tolerances(tree: ast.Module) -> dict[str, float]:
    """Module-level constants that declare a numeric tolerance bound."""
    bounds: dict[str, float] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or not _TOLERANCE_NAME_RE.match(target.id):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int | float):
                bounds[target.id] = float(node.value.value)
    return bounds


def _iter_test_functions_with_decorators(
    tree: ast.Module,
) -> list[tuple[list[str], ast.FunctionDef | ast.AsyncFunctionDef, list[ast.expr]]]:
    """Like :func:`_iter_test_functions`, but carrying enclosing-class decorators.

    A class-level ``@pytest.mark.oracle(subject=...)`` registers every test method
    it contains, so the derivation has to see it.
    """
    found: list[tuple[list[str], ast.FunctionDef | ast.AsyncFunctionDef, list[ast.expr]]] = []

    def visit(node: ast.AST, prefix: list[str], inherited: list[ast.expr]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, [*prefix, child.name], [*inherited, *child.decorator_list])
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                if child.name.startswith("test"):
                    found.append(
                        ([*prefix, child.name], child, [*inherited, *child.decorator_list])
                    )

    visit(tree, [], [])
    return found


def derive_module_subjects(path: Path, config: OracleLayerConfig) -> tuple[OracleSubject, ...]:
    """Derive membership evidence for every test in one oracle-suite module."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ()

    rel = path.relative_to(ROOT).as_posix()
    module_doc = ast.get_docstring(tree, clean=True) or ""
    lowered = source.lower()
    admits_closed_form = any(phrase in lowered for phrase in _CLOSED_FORM_ADMISSIONS)
    claims_oracle = bool(
        re.search(rf"oracle\s+layer\s*{config.oracle_layer}\b", module_doc, re.IGNORECASE)
    )
    paths, bound = _import_paths(tree)
    tolerances = _module_tolerances(tree)
    module_scope = [
        node
        for node in tree.body
        if not isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    module_edges = _assignment_edges(*module_scope)

    subjects: list[OracleSubject] = []
    for parts, func, decorators in _iter_test_functions_with_decorators(tree):
        oracle_marker = _marker(decorators, "oracle")
        meta_marker = _marker(decorators, "metamorphic")

        subject_raw = _marker_kwarg(oracle_marker, "subject")
        declared_subject = str(subject_raw) if isinstance(subject_raw, str) else ""

        layer_raw = _marker_kwarg(oracle_marker, "layer") or _marker_kwarg(meta_marker, "layer")
        if isinstance(layer_raw, int):
            declared_layer: int | None = layer_raw
        elif oracle_marker is not None:
            declared_layer = config.oracle_layer
        elif meta_marker is not None:
            declared_layer = 4
        else:
            declared_layer = None

        edges = {**module_edges}
        for name, referenced in _assignment_edges(func).items():
            edges.setdefault(name, set()).update(referenced)

        imports_subject = bool(declared_subject) and any(
            _matches_subject(dotted, declared_subject) for dotted in paths
        )
        seeds = {
            name
            for name, dotted in bound.items()
            if declared_subject and _matches_subject(dotted, declared_subject)
        }
        derived = _derived_names(seeds, edges)
        asserted = _assert_reachable_names(func, edges)
        invokes = bool(seeds) and bool(_call_roots(func) & derived) and bool(derived & asserted)

        reference_side = {
            name for name in asserted if _REFERENCE_NAME_RE.search(name.lower())
        } - derived
        reference_independent = bool(reference_side) and not admits_closed_form

        declared_bounds = {
            name: value for name, value in tolerances.items() if name in asserted
        }
        if declared_bounds:
            tolerance_name, tolerance_bound = sorted(declared_bounds.items())[0]
            constraining: bool | None = 0.0 < tolerance_bound < config.tolerance_ceiling
        else:
            tolerance_name, tolerance_bound, constraining = None, None, None

        subjects.append(
            OracleSubject(
                node_id=rel + "::" + "::".join(parts),
                test_module=rel,
                declared_subject=declared_subject,
                declared_layer=declared_layer,
                title_claims_oracle=claims_oracle,
                imports_subject=imports_subject,
                invokes_subject_on_asserted_path=invokes,
                reference_independent=reference_independent,
                tolerance_constraining=constraining,
                tolerance_name=tolerance_name,
                tolerance_bound=tolerance_bound,
            )
        )
    return tuple(subjects)


def derive_subjects(config: OracleLayerConfig) -> tuple[OracleSubject, ...]:
    """Membership evidence for the whole oracle suite."""
    if not ORACLE_DIR.is_dir():
        return ()
    subjects: list[OracleSubject] = []
    for path in sorted(ORACLE_DIR.glob("test_*.py")):
        subjects.extend(derive_module_subjects(path, config))
    return tuple(subjects)


def membership_findings(
    subjects: tuple[OracleSubject, ...], config: OracleLayerConfig
) -> tuple[Finding, ...]:
    """Every membership and tolerance violation, each naming its test."""
    findings: list[Finding] = []
    for subject in subjects:
        registered_oracle = subject.declared_layer == config.oracle_layer

        if registered_oracle and not subject.declared_subject:
            findings.append(
                Finding(
                    rule="oracle-subject-undeclared",
                    requirement="R12.6",
                    node_id=subject.node_id,
                    detail=(
                        f"{subject.node_id} is registered in the Oracle layer but names no "
                        "subject, so membership cannot be derived from anything: add "
                        "@pytest.mark.oracle(subject='...') or register the test in the layer "
                        "it actually occupies"
                    ),
                )
            )

        if subject.declared_subject and not subject.imports_subject:
            findings.append(
                Finding(
                    rule="oracle-subject-not-invoked",
                    requirement="R12.1",
                    node_id=subject.node_id,
                    detail=(
                        f"{subject.node_id} names subject '{subject.declared_subject}' and "
                        "imports no module under it"
                    ),
                )
            )
        elif subject.declared_subject and not subject.invokes_subject_on_asserted_path:
            findings.append(
                Finding(
                    rule="oracle-subject-not-invoked",
                    requirement="R12.1",
                    node_id=subject.node_id,
                    detail=(
                        f"{subject.node_id} imports subject '{subject.declared_subject}' but no "
                        "value produced by calling it reaches an assertion, so the asserted "
                        "value is not the subject's"
                    ),
                )
            )

        if registered_oracle and not subject.reference_independent:
            findings.append(
                Finding(
                    rule="oracle-reference-not-independent",
                    requirement="R12.2",
                    node_id=subject.node_id,
                    detail=(
                        f"{subject.node_id} is registered in the Oracle layer but its reference "
                        "value is not computed independently of the implementation it judges; "
                        f"register it as {config.layer_name(4)} (layer 4) instead"
                    ),
                )
            )

        if subject.title_claims_oracle and not subject.earned:
            findings.append(
                Finding(
                    rule="oracle-claim-unearned",
                    requirement="R12.6",
                    node_id=subject.node_id,
                    detail=(
                        f"{subject.node_id} claims the Oracle layer in its title while the "
                        "derivation refuses it (imports_subject="
                        f"{subject.imports_subject}, invokes_subject_on_asserted_path="
                        f"{subject.invokes_subject_on_asserted_path}, reference_independent="
                        f"{subject.reference_independent}); membership is derived, not titled"
                    ),
                )
            )

        if subject.tolerance_constraining is False:
            findings.append(
                Finding(
                    rule="tolerance-unconstraining",
                    requirement="R12.7",
                    node_id=subject.node_id,
                    detail=(
                        f"{subject.node_id} asserts tolerance {subject.tolerance_name}="
                        f"{subject.tolerance_bound} which is at or above the committed ceiling "
                        f"{config.tolerance_ceiling}: that tolerance is unconstraining, because "
                        "a bound that wide admits an implementation error large enough for "
                        "agreement to prove nothing"
                    ),
                )
            )
    return tuple(sorted(findings, key=lambda f: (f.node_id, f.rule)))


def unresolved_findings(
    findings: tuple[Finding, ...],
    entries: tuple[AllowlistEntry, ...] | None = None,
) -> tuple[Finding, ...]:
    """Findings no well-formed allowlist entry excuses for that exact node id."""
    allowed = entries if entries is not None else allowlist_entries()
    index: dict[str, AllowlistEntry] = {entry.node_id: entry for entry in allowed}
    unresolved: list[Finding] = []
    for finding in findings:
        entry = index.get(finding.node_id)
        if entry is not None and entry.excuses(finding.rule):
            continue
        unresolved.append(finding)
    return tuple(unresolved)


class MembershipReport(BaseModel):
    """Everything one membership evaluation observed."""

    model_config = ConfigDict(frozen=True)

    subjects: tuple[OracleSubject, ...]
    oracle_members: tuple[str, ...]
    findings: tuple[Finding, ...]
    unresolved: tuple[Finding, ...]
    verdict: Literal["pass", "fail", "unavailable"]
    reason: str

    @property
    def exit_code(self) -> int:
        return {"pass": 0, "fail": 1, "unavailable": 2}[self.verdict]


def evaluate_membership(config: OracleLayerConfig | None = None) -> MembershipReport:
    """Derive membership for the oracle suite and roll it into a verdict.

    An unreadable configuration or an absent suite is ``unavailable`` (exit 2),
    never ``pass``: a derivation that could not run has not established membership
    for anything (I-7).
    """
    if config is None:
        try:
            config = load_config()
        except ConfigUnavailable as error:
            return MembershipReport(
                subjects=(),
                oracle_members=(),
                findings=(),
                unresolved=(),
                verdict="unavailable",
                reason=str(error),
            )

    subjects = derive_subjects(config)
    schema = allowlist_findings()
    derived = membership_findings(subjects, config)
    findings = schema + derived
    unresolved = schema + unresolved_findings(derived)
    members = tuple(
        subject.node_id
        for subject in subjects
        if subject.declared_layer == config.oracle_layer and subject.earned
    )

    if not subjects:
        return MembershipReport(
            subjects=(),
            oracle_members=(),
            findings=findings,
            unresolved=unresolved,
            verdict="unavailable",
            reason=f"no oracle-suite test modules found under {ORACLE_DIR.name}/",
        )
    if unresolved:
        return MembershipReport(
            subjects=subjects,
            oracle_members=members,
            findings=findings,
            unresolved=unresolved,
            verdict="fail",
            reason=f"{len(unresolved)} unresolved oracle-layer finding(s)",
        )
    return MembershipReport(
        subjects=subjects,
        oracle_members=members,
        findings=findings,
        unresolved=(),
        verdict="pass",
        reason=(
            f"{len(members)} test(s) earn Oracle-layer membership; "
            f"{len(findings)} finding(s), all allowlisted with a dated rationale and a "
            "removal condition"
        ),
    )


def _print_membership(report: MembershipReport, config: OracleLayerConfig | None) -> None:
    """ASCII-only membership table (Windows console safe)."""
    ceiling = config.tolerance_ceiling if config is not None else None
    for subject in report.subjects:
        if subject.declared_layer is None:
            mark = "[--]"
        elif config is not None and subject.declared_layer == config.oracle_layer:
            mark = "[OK]" if subject.earned else "[XX]"
        else:
            mark = "[  ]"
        layer = config.layer_name(subject.declared_layer) if config else str(subject.declared_layer)
        print(f"{mark} {subject.node_id}  ({layer})")
        print(
            f"        subject={subject.declared_subject or '-'} "
            f"imports={subject.imports_subject} "
            f"invokes={subject.invokes_subject_on_asserted_path} "
            f"reference_independent={subject.reference_independent} "
            f"tolerance={subject.tolerance_name or '-'}"
            f"({subject.tolerance_bound if subject.tolerance_bound is not None else '-'}) "
            f"constraining={subject.tolerance_constraining}"
        )
    print()
    if ceiling is not None:
        print(f"Tolerance ceiling (committed): {ceiling}")
    print(f"Oracle-layer members (earned): {len(report.oracle_members)}")
    for node_id in report.oracle_members:
        print(f"  [OK] {node_id}")
    if report.unresolved:
        print(f"Unresolved finding(s): {len(report.unresolved)}")
        for finding in report.unresolved:
            print(f"  [XX] {finding.rule} ({finding.requirement}): {finding.detail}")
    allowlisted = len(report.findings) - len(report.unresolved)
    print(f"Allowlisted finding(s): {allowlisted}")
    print(f"Oracle membership: {report.verdict.upper()} - {report.reason}")


def run(*, as_json: bool = False, check: bool = False, membership: bool = False) -> int:
    """Report the auditor's findings and return an exit code.

    ``check`` keeps its original, strict contract: exit 1 iff at least one
    docstring-body mismatch exists (R8.4). ``membership`` adds the R12 derivation
    as a second, independent gate - exit 1 on an unresolved membership/tolerance
    finding and 2 when the derivation could not run at all. The two are separate
    flags because they answer separate questions and one must never mask the other.
    """
    reports = collect()
    mismatches = all_mismatches(reports)
    total_tests = sum(len(r.tests) for r in reports)

    config: OracleLayerConfig | None = None
    member_report: MembershipReport | None = None
    if membership or as_json:
        try:
            config = load_config()
        except ConfigUnavailable as error:
            config = None
            member_report = MembershipReport(
                subjects=(),
                oracle_members=(),
                findings=(),
                unresolved=(),
                verdict="unavailable",
                reason=str(error),
            )
        if member_report is None:
            member_report = evaluate_membership(config)

    if as_json:
        assert member_report is not None  # set above whenever as_json is true
        payload = {
            "summary": {
                "modules_scanned": len(reports),
                "tests_scanned": total_tests,
                "mismatches": len(mismatches),
                "oracle_members": len(member_report.oracle_members),
                "membership_findings": len(member_report.findings),
                "membership_unresolved": len(member_report.unresolved),
                "membership_verdict": member_report.verdict,
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
            "oracle_members": list(member_report.oracle_members),
            "subjects": [subject.model_dump(mode="json") for subject in member_report.subjects],
            "membership_findings": [
                finding.model_dump(mode="json") for finding in member_report.findings
            ],
            "membership_unresolved": [
                finding.model_dump(mode="json") for finding in member_report.unresolved
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
        if member_report is not None:
            print()
            _print_membership(member_report, config)

    if membership:
        assert member_report is not None  # set above whenever membership is true
        if member_report.verdict != "pass":
            return member_report.exit_code
    if check:
        return 1 if mismatches else 0
    return 0


if __name__ == "__main__":
    sys.exit(
        run(
            as_json="--json" in sys.argv,
            check="--check" in sys.argv,
            membership="--membership" in sys.argv,
        )
    )
