"""scripts/audit/doc_truth.py — narrative-truth gate (Phase 0, C56).

Pins the load-bearing NUMBERS and cadence claims that CLAUDE.md / the workflow
headers assert to their mechanical source of truth, and FAILS on drift.

Why this gate exists: the single biggest risk in this repo is the *narrative*
(CLAUDE.md, in-file comments) silently diverging from the *mechanical reality*
the gates enforce — which re-introduces the exact claim-vs-reality gap the whole
verification apparatus was built to kill. CLAUDE.md's own rule: "a fact worth
discovering twice is worth a gate." Two such drifts were found and fixed in
Phase 0 — the spec-coverage threshold said ``12`` while CI ran ``99``, and
``cd-gcp.yml`` claimed per-merge deploy while it actually deploys weekly. This
gate stops both from recurring.

Design: a small, explicit registry of claims. Each compares a value ASSERTED in
the docs against the TRUE value extracted from the mechanical source.
Deliberately narrow — it targets authoritative, present-tense governance
statements, never historical sprint-status prose. Add a claim only when a doc
number is load-bearing AND mechanically derivable. CLAIM A (numeric pin) is the
model for future numeric claims.

CLAIM C pins the README headline PASS/FAIL/PARTIAL/SKIP/TOTAL counts to the
summary emitted by *executing* `verify_claims` at evaluation time, so the
advertised headline can never drift from what the suite actually reports.

Never fabricates a pass: a claim whose source file is missing SKIPs, and so does
one whose mechanical source (the `verify_claims` suite) cannot be run or parsed.

Run::

    python -m scripts.audit.doc_truth            # human lines
    python -m scripts.audit.doc_truth --json     # machine JSON
    python -m scripts.audit.doc_truth --check     # exit 1 on any drift
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = ROOT / "CLAUDE.md"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
CD_GCP_YML = ROOT / ".github" / "workflows" / "cd-gcp.yml"
README_MD = ROOT / "README.md"
VERIFY_CLAIMS_PY = ROOT / "scripts" / "audit" / "verify_claims.py"


@dataclass
class ClaimResult:
    name: str
    status: str  # ok | fail | skip
    detail: str


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _claim_spec_threshold() -> ClaimResult:
    """CLAIM A (the model): the spec-coverage threshold CLAUDE.md advertises in
    its authoritative Testing-Rules line must equal CI's actual gate value."""
    md = _read(CLAUDE_MD)
    ci = _read(CI_YML)
    if md is None or ci is None:
        return ClaimResult("spec-threshold", "skip", "CLAUDE.md or ci.yml missing")
    # Anchored to the present-tense governance phrasing only ("CI gate
    # `--threshold N`"), NOT the historical "Wired into ci.yml at `--threshold
    # 12`" sprint-status line.
    asserted = re.search(r"CI gate `--threshold (\d+)`", md)
    actual = re.search(r"check_spec_coverage\.py --threshold (\d+)", ci)
    if asserted is None:
        return ClaimResult(
            "spec-threshold", "skip", "no 'CI gate `--threshold N`' claim in CLAUDE.md"
        )
    if actual is None:
        return ClaimResult(
            "spec-threshold", "skip", "no check_spec_coverage --threshold in ci.yml"
        )
    claimed, real = asserted.group(1), actual.group(1)
    if claimed != real:
        return ClaimResult(
            "spec-threshold",
            "fail",
            f"CLAUDE.md advertises --threshold {claimed} but ci.yml runs --threshold {real}",
        )
    return ClaimResult(
        "spec-threshold", "ok", f"CLAUDE.md and ci.yml agree: --threshold {claimed}"
    )


# Phrases that assert continuous per-merge freshness of the live VM. They are
# FALSE: the deploy-to-vm `if:` skips plain pushes; the VM deploys weekly. This
# is a regression guard for the exact drift fixed in Phase 0.
_STALE_DEPLOY_PHRASES = ("never more than one workflow run behind HEAD",)


def _claim_deploy_cadence() -> ClaimResult:
    """CLAIM B: cd-gcp.yml must not re-assert per-merge auto-deploy, because the
    deploy-to-vm `if:` only fires on schedule / `v*` tag / manual dispatch."""
    cd = _read(CD_GCP_YML)
    if cd is None:
        return ClaimResult("deploy-cadence", "skip", "cd-gcp.yml missing")
    hits = [p for p in _STALE_DEPLOY_PHRASES if p in cd]
    if hits:
        return ClaimResult(
            "deploy-cadence",
            "fail",
            f"cd-gcp.yml re-asserts a stale per-merge-deploy claim: {hits!r} — the "
            "deploy-to-vm `if:` skips plain pushes (weekly / tag / dispatch only)",
        )
    return ClaimResult(
        "deploy-cadence", "ok", "cd-gcp.yml carries no stale per-merge-deploy claim"
    )


# ---------------------------------------------------------------------------
# CLAIM C: the README headline counts are pinned to the LIVE verify_claims
# summary. The suite is executed at evaluation time and every "actual" count is
# derived from its emitted summary — nothing here is hardcoded, so the pin
# cannot rot the way the numbers it guards did.
# ---------------------------------------------------------------------------
_HEADLINE_CATEGORIES = ("PASS", "FAIL", "PARTIAL", "SKIP", "TOTAL")

# Recursion guard: verify_claims' own C56 check calls ``evaluate()`` here, and
# this claim executes verify_claims. The spawned suite carries this marker so
# its nested C56 skips *this* claim only (the other claims still run), bounding
# the recursion at depth 1 instead of forking forever.
_NESTED_ENV = "SYNAPSE_DOC_TRUTH_NESTED"

# The suite shells out to git/docker probes; generous but finite. A timeout is
# an honest SKIP ("suite could not run"), never a pass.
_SUITE_TIMEOUT_S = 900.0

_VERIFY_CLAIMS_MENTION = re.compile(r"verify[-_]claims", re.IGNORECASE)


def _extract_count(text: str, category: str) -> int | None:
    """Pull one headline count out of a doc line: ``16 PASS`` or ``PASS=16``."""
    prefixed = re.search(rf"(\d+)\s*{category}\b", text)
    if prefixed is not None:
        return int(prefixed.group(1))
    suffixed = re.search(rf"\b{category}\s*[=:]\s*(\d+)", text)
    if suffixed is not None:
        return int(suffixed.group(1))
    return None


def _readme_headline_line(md: str) -> str | None:
    """The README line that states the ``verify-claims`` headline counts.

    A candidate must both name the suite and carry at least one extractable
    count, so prose like "a SKIP is not a PASS" cannot be mistaken for the
    headline. When several lines qualify, the richest one wins.
    """
    best: tuple[int, str] | None = None
    for raw in md.splitlines():
        if _VERIFY_CLAIMS_MENTION.search(raw) is None:
            continue
        found = sum(1 for cat in _HEADLINE_CATEGORIES if _extract_count(raw, cat) is not None)
        if found and (best is None or found > best[0]):
            best = (found, raw.strip())
    return None if best is None else best[1]


def _parse_suite_summary(stdout: str) -> dict[str, int] | None:
    """Parse ``{PASS, FAIL, PARTIAL, SKIP, TOTAL}`` out of the suite output.

    Prefers the machine-readable ``--json`` payload; falls back to the human
    ``Summary: PASS=..`` line. Returns None when neither can be read, which the
    caller turns into a SKIP (R8.6).
    """
    text = stdout.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            summary = payload.get("summary")
            if isinstance(summary, dict):
                counts: dict[str, int] = {}
                for cat in _HEADLINE_CATEGORIES:
                    value = summary.get(cat.lower())
                    if isinstance(value, bool) or not isinstance(value, int):
                        counts = {}
                        break
                    counts[cat] = value
                if counts:
                    return counts
    line = re.search(r"^Summary:.*$", text, re.MULTILINE)
    if line is None:
        return None
    human: dict[str, int] = {}
    for cat in _HEADLINE_CATEGORIES:
        value_ = _extract_count(line.group(0), cat)
        if value_ is None:
            return None
        human[cat] = value_
    return human


def _suite_counts() -> tuple[dict[str, int] | None, str]:
    """Execute the verify_claims suite now and return its summary counts."""
    env = dict(os.environ)
    env[_NESTED_ENV] = "1"
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-m", "scripts.audit.verify_claims", "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=_SUITE_TIMEOUT_S,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"verify_claims suite could not be executed: {exc!r}"
    counts = _parse_suite_summary(proc.stdout)
    if counts is None:
        tail = (proc.stderr.strip() or proc.stdout.strip() or "<no output>").splitlines()[-1]
        return None, f"verify_claims summary could not be parsed (exit {proc.returncode}): {tail}"
    return counts, ""


def _claim_readme_headline_counts() -> ClaimResult:
    """CLAIM C (C56, R8.2/R8.3/R8.5/R8.6): every README headline count must equal
    the corresponding count in the summary emitted by running verify_claims."""
    name = "headline-counts"
    if os.environ.get(_NESTED_ENV):
        return ClaimResult(
            name,
            "skip",
            "nested inside a verify_claims run — recursion guard, pin is checked "
            "by the outer doc_truth evaluation",
        )
    md = _read(README_MD)
    if md is None:
        return ClaimResult(name, "skip", "README.md missing or unreadable")
    if not VERIFY_CLAIMS_PY.is_file():
        return ClaimResult(name, "skip", "scripts/audit/verify_claims.py missing")
    headline = _readme_headline_line(md)
    if headline is None:
        return ClaimResult(name, "skip", "no verify-claims headline count line found in README.md")
    actual, error = _suite_counts()
    if actual is None:
        return ClaimResult(name, "skip", error)
    claimed = {cat: _extract_count(headline, cat) for cat in _HEADLINE_CATEGORIES}
    drifts = [
        f"{cat} (README claims {'absent' if claimed[cat] is None else claimed[cat]}, "
        f"suite reports {actual[cat]})"
        for cat in _HEADLINE_CATEGORIES
        if claimed[cat] != actual[cat]
    ]
    if drifts:
        return ClaimResult(
            name,
            "fail",
            "README headline drifted from the live verify_claims summary: " + "; ".join(drifts),
        )
    return ClaimResult(
        name,
        "ok",
        "README headline matches the live verify_claims summary: "
        + " ".join(f"{cat}={actual[cat]}" for cat in _HEADLINE_CATEGORIES),
    )


_CLAIMS = (_claim_spec_threshold, _claim_deploy_cadence, _claim_readme_headline_counts)


@dataclass
class DocProbe:
    status: str  # ok | fail | skip
    detail: str


def evaluate() -> DocProbe:
    """Aggregate all claims: FAIL if any drifts, SKIP if none could be checked."""
    results = [claim() for claim in _CLAIMS]
    fails = [r for r in results if r.status == "fail"]
    oks = [r for r in results if r.status == "ok"]
    if fails:
        return DocProbe("fail", "; ".join(f"{r.name}: {r.detail}" for r in fails))
    if not oks:
        return DocProbe("skip", "; ".join(f"{r.name}: {r.detail}" for r in results))
    return DocProbe(
        "ok",
        f"{len(oks)}/{len(results)} doc claims match source ("
        + ", ".join(r.name for r in oks)
        + ")",
    )


def run(*, as_json: bool = False, check: bool = False) -> int:
    results = [claim() for claim in _CLAIMS]
    if as_json:
        print(json.dumps([r.__dict__ for r in results], indent=2, sort_keys=True))
    else:
        for r in results:
            sym = {"ok": "[OK]", "fail": "[XX]", "skip": "[--]"}[r.status]
            print(f"{sym} doc-truth/{r.name:<16} {r.detail}")
    if check:
        return 1 if any(r.status == "fail" for r in results) else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
