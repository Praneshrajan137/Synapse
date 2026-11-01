"""The blocking call site for the Check_Registry (design AD-1 / E1.1, R1).

``make verify-claims`` is described as "the project's honesty meter"
(``docs/state/CURRENT.md``), but its exit code was consumed by nothing: the only CI
path into it was a 900s subprocess inside ``scripts/audit/doc_truth.py`` whose
``returncode`` was used to build an error string and then discarded. Twenty-six of
the registered checks therefore had no enforcement path at all. This module is the
one step a workflow can run whose exit status *is* the registry's verdict.

Three properties of this gate are load-bearing and deliberate:

* **In-process.** :func:`evaluate` imports ``verify_claims`` and calls
  :func:`~scripts.audit.verify_claims.collect_results` directly. No subprocess, so
  no 900s timeout to mask a FAIL, no summary text to re-parse, and no interaction
  with ``doc_truth``'s recursion guard.
* **Identity, not just counts.** The verdict names every divergence between the
  registered and the executed identifier set - registered ids that did not execute
  and reported ids that were never registered (R1.7) - and each identifier that
  failed (R1.1-R1.3). Two checks
  flipping in opposite directions leave the PASS/FAIL counts identical; they cannot
  leave this verdict identical.
* **A SKIP is not a PASS (I-7).** An empty registry, a registry that executed
  nothing, or a run in which every check SKIPped is reported ``unavailable`` and
  exits ``2``. ``2`` is a *non-passing* status for the CI step: absence of proof is
  never proof. Only checks reporting ``PASS`` are counted in the published PASS
  count (R2.9); everything else lands in ``failures`` or ``unproven``.

Unlike the report-first gates in this directory (``uplift_truth`` and friends,
which return ``EXIT_PASS`` unless ``--check`` is given), ``run()`` returns the
verdict-derived exit code in *both* modes. A gate whose default invocation cannot
fail is the exact hole this feature exists to close (R1.8), so ``--check`` here only
suppresses the trailing operator note. The gating step carries no
``continue-on-error`` and no ``|| true`` (enforced separately by
``scripts/audit/workflow_shape_truth.py``).

Run::

    python -m scripts.audit.registry_gate            # human summary, exits 0/1/2
    python -m scripts.audit.registry_gate --json     # canonical machine JSON
    python -m scripts.audit.registry_gate --check    # same codes, no operator note
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]

# Ensure the repo root is importable when run as a bare script (not -m).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit import verify_claims  # noqa: E402
from scripts.audit.verify_claims import STATUSES, CheckResult  # noqa: E402

# Exit codes. ``2`` is distinct from ``1`` so a CI log can tell "a claim stopped
# being true" from "the registry could not be evaluated" - both non-passing.
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNAVAILABLE = 2

_EXIT_CODES: Mapping[str, int] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}

#: Statuses that are neither a pass nor a failure, but an absence of proof (I-7).
UNPROVEN_STATUSES: tuple[str, ...] = ("PARTIAL", "SKIP")

_SYMBOLS: Mapping[str, str] = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[??]"}


class RegistryVerdict(BaseModel):
    """Outcome of one Check_Registry execution, as a gate sees it."""

    model_config = ConfigDict(frozen=True)

    registered_ids: tuple[str, ...]
    executed_ids: tuple[str, ...]
    counts: Mapping[str, int]  # PASS/FAIL/PARTIAL/SKIP/TOTAL
    failures: tuple[CheckResult, ...]
    unproven: tuple[CheckResult, ...]  # SKIP + PARTIAL
    missing_ids: tuple[str, ...]  # registered but not executed
    verdict: Literal["pass", "fail", "unavailable"]
    reason: str

    @property
    def exit_code(self) -> int:
        """The process exit status this verdict mandates (0 / 1 / 2)."""
        return _EXIT_CODES[self.verdict]

    @property
    def passing(self) -> bool:
        """True only for ``pass``. ``unavailable`` is not a pass (I-7)."""
        return self.verdict == "pass"


def status_counts(results: tuple[CheckResult, ...]) -> dict[str, int]:
    """Partition ``results`` into the four emitted statuses plus ``TOTAL``.

    A result carrying a status outside :data:`~scripts.audit.verify_claims.STATUSES`
    is counted in no bucket - ``verify_claims._run_check`` already coerces such a
    result to ``FAIL``, and if that coercion is ever bypassed the result must not be
    able to inflate a bucket. It is still surfaced, as a failure, by
    :func:`evaluate_results`.
    """
    counts = {status: 0 for status in STATUSES}
    for result in results:
        if result.status in counts:
            counts[result.status] += 1
    counts["TOTAL"] = len(results)
    return counts


def evaluate_results(
    registered_ids: tuple[str, ...],
    results: tuple[CheckResult, ...],
) -> RegistryVerdict:
    """Derive the verdict from one (registration, execution) pair.

    Pure: it reads no file, runs no check, and touches no process state, so the
    verdict is a total function of its two arguments (design Property 1) and the
    property test can drive it without executing the real 53-check registry (I-0).

    Rules, in order - first match wins:

    1. nothing registered              -> ``unavailable`` (R1.6)
    2. the executed id set differs from
       the registered id set           -> ``fail``, naming each (R1.7)
    3. every executed check SKIPped    -> ``unavailable`` (R1.6, I-7)
    4. any failing status              -> ``fail``, naming each id and status (R1.1-R1.3)
    5. otherwise                       -> ``pass``

    Rule 2 is symmetric because R1.7 and AD-1 are: "IF the set of executed
    identifiers differs from the set of registered identifiers, THEN the gating step
    SHALL record a non-passing result". A result reported under an id nobody
    registered is such a difference - ``verify_claims._run_check`` coerces that case
    upstream (AD-14), so seeing one here means the coercion itself was bypassed,
    which must not be able to reach the ``pass`` branch.
    """
    counts = status_counts(results)
    executed_ids = tuple(result.cid for result in results)
    executed = set(executed_ids)
    registered = set(registered_ids)
    missing_ids = tuple(cid for cid in registered_ids if cid not in executed)
    unregistered_ids = tuple(
        dict.fromkeys(cid for cid in executed_ids if cid not in registered)
    )
    # A status outside the emitted four is itself a defect, so it counts as a
    # failure rather than falling through to the pass branch.
    failures = tuple(
        result for result in results if result.status == "FAIL" or result.status not in STATUSES
    )
    unproven = tuple(result for result in results if result.status in UNPROVEN_STATUSES)

    verdict: Literal["pass", "fail", "unavailable"]
    if not registered_ids:
        verdict, reason = (
            "unavailable",
            "no checks are registered; the registry executed nothing to gate on",
        )
    elif missing_ids or unregistered_ids:
        divergences = []
        if missing_ids:
            divergences.append(
                f"{len(missing_ids)} registered check(s) did not execute: "
                f"{', '.join(missing_ids)}"
            )
        if unregistered_ids:
            divergences.append(
                f"{len(unregistered_ids)} result(s) reported an unregistered id: "
                f"{', '.join(unregistered_ids)}"
            )
        verdict, reason = "fail", "; ".join(divergences)
    elif counts["TOTAL"] > 0 and counts["SKIP"] == counts["TOTAL"]:
        verdict, reason = (
            "unavailable",
            f"all {counts['TOTAL']} executed check(s) reported SKIP; "
            "a SKIP is not a PASS, so nothing was proven",
        )
    elif failures:
        named = ", ".join(f"{result.cid}={result.status}" for result in failures)
        verdict, reason = (
            "fail",
            f"{len(failures)} check(s) did not pass: {named}",
        )
    else:
        verdict, reason = (
            "pass",
            f"{counts['PASS']} PASS of {counts['TOTAL']} registered check(s), no FAIL "
            f"({counts['PARTIAL']} PARTIAL, {counts['SKIP']} SKIP not counted as passes)",
        )

    return RegistryVerdict(
        registered_ids=registered_ids,
        executed_ids=executed_ids,
        counts=counts,
        failures=failures,
        unproven=unproven,
        missing_ids=missing_ids,
        verdict=verdict,
        reason=reason,
    )


def registered_ids() -> tuple[str, ...]:
    """Every identifier ``@register`` declared, in registration order.

    Read from ``verify_claims._CHECKS`` rather than re-derived, so the registration
    list stays the single source of truth and this module needs no edit to the
    registry module to know what should have run (R1.7).
    """
    return tuple(cid for cid, _title, _fn in verify_claims._CHECKS)


def evaluate() -> RegistryVerdict:
    """Execute the Check_Registry in this process and return the gate's verdict."""
    return evaluate_results(registered_ids(), tuple(verify_claims.collect_results()))


def _print_group(heading: str, symbol: str, results: tuple[CheckResult, ...]) -> None:
    if not results:
        return
    print()
    print(heading)
    for result in results:
        print(f"  {symbol} {result.cid:>4} {result.title:<48} {result.detail}")


def run(*, as_json: bool = False, check: bool = False) -> int:
    """Execute the registry and report. Returns ``0`` / ``1`` / ``2``."""
    verdict = evaluate()

    if as_json:
        print(
            json.dumps(
                verdict.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return verdict.exit_code

    counts = verdict.counts
    print(
        f"{_SYMBOLS[verdict.verdict]} registry-gate: {verdict.verdict.upper()} - {verdict.reason}"
    )
    print(
        f"Summary: PASS={counts['PASS']} FAIL={counts['FAIL']} PARTIAL={counts['PARTIAL']} "
        f"SKIP={counts['SKIP']} TOTAL={counts['TOTAL']} "
        f"REGISTERED={len(verdict.registered_ids)}"
    )
    if verdict.missing_ids:
        print()
        print(f"REGISTERED BUT NOT EXECUTED -- {len(verdict.missing_ids)}:")
        for cid in verdict.missing_ids:
            print(f"  [XX] {cid:>4} no result was emitted for this registered check")
    _print_group(f"FAILING -- {len(verdict.failures)}:", "[XX]", verdict.failures)
    _print_group(
        f"NOT VERIFIED -- {len(verdict.unproven)} PARTIAL/SKIP (a SKIP is not a PASS):",
        "[--]",
        verdict.unproven,
    )
    if not check:
        print()
        print(
            "(this gate's exit status is the registry's verdict - it must not be wrapped "
            "in `|| true` or `continue-on-error`.)"
        )

    return verdict.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="registry_gate",
        description="Execute the Check_Registry in-process and gate on its verdict.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the verdict as canonical JSON instead of a human summary",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="suppress the operator note; the exit code is verdict-derived either way",
    )
    args = parser.parse_args(argv)
    return run(as_json=bool(args.as_json), check=bool(args.check))


if __name__ == "__main__":
    sys.exit(main())
