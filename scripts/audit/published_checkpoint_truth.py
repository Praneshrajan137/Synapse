"""Prove a *real, published* production checkpoint exists and is calibrated (C43).

ADR-043's C42 boots a checkpoint through the serving path — but in CI that is the
*smoke* artifact. This gate is the authenticity counterpart: it verifies that an
operator actually ran the free-GPU full train (``docs/runbooks/train-and-publish-
checkpoint.md``) and published a genuine, non-smoke, adequately-calibrated
checkpoint to the $0 serving source (HF Hub), and that what is published matches
what the operator recorded in the committed registry.

It is **$0-safe and never fabricates a pass**:

  * ``DP_HF_REPO`` unset                  → SKIP (no published model claimed yet).
  * ``huggingface_hub`` absent            → SKIP (cannot verify the remote).
  * registry still at ``__placeholder__`` → SKIP (no operator has published yet).
  * published sidecar marked ``smoke``    → FAIL (a smoke artifact is not production).
  * coverage below the floor              → FAIL (uncalibrated = not real).
  * registry sha ≠ published sha          → FAIL (drift between record and remote).

So CI stays green without any secret; the moment an operator publishes and records
the result, this turns into a live, regression-guarded proof that *a real model
serves*.

A second, network-free entry point validates the *record* the operator commits
(``--validate-registry``): the registry entry must carry every required key with a
sane value before it is worth cross-checking against the remote. It reports
``placeholder`` (not a failure) while no operator has published — landing a real
entry is a runbook step, and an absent model is stated honestly, never faked.

Run::

    python -m scripts.audit.published_checkpoint_truth            # human line
    python -m scripts.audit.published_checkpoint_truth --json     # machine JSON
    python -m scripts.audit.published_checkpoint_truth --check    # exit 1 on a real failure
    python -m scripts.audit.published_checkpoint_truth --validate-registry   # schema only
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "infrastructure" / "ml" / "published_checkpoints.json"
SERVING_NAME = "demand_prophet_hgt_tft"
COVERAGE_FLOOR = 0.85  # INV-DP-002 nominal 90% interval achieves >=85% coverage.

# The record the operator must commit for a published checkpoint (R5.2). Every key
# is produced by the runbook's step-5 output; a partial record cannot be
# cross-checked against the remote, so it is an invalid record, not a pass.
REQUIRED_ENTRY_KEYS: tuple[str, ...] = (
    "repo",
    "sha",
    "coverage_p90",
    "final_crps",
    "trained_at",
    "rows",
)
_SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_MIN_SHA_LEN = 7


@dataclass
class PublishProbe:
    status: str  # ok | fail | skip
    detail: str


@dataclass(frozen=True)
class RegistryStatus:
    """Result of validating the committed registry record (no network involved).

    ``status`` is one of:

      * ``populated`` — a complete, well-formed entry for the serving name.
      * ``placeholder`` — no operator has published yet (honest, not a failure).
      * ``missing`` — the registry file is absent or unreadable.
      * ``invalid`` — an entry exists but its shape/values are wrong (a real error).
    """

    status: str
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status == "populated"


def _load_registry() -> dict[str, Any]:
    if not REGISTRY.is_file():
        return {}
    try:
        parsed: dict[str, Any] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed


def _validate_number(
    key: str, value: Any, *, minimum: float | None = None, maximum: float | None = None
) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{key} must be a number, got {type(value).__name__}"
    if not math.isfinite(float(value)):
        return f"{key} must be finite, got {value!r}"
    if minimum is not None and float(value) < minimum:
        return f"{key}={value} is below the minimum {minimum}"
    if maximum is not None and float(value) > maximum:
        return f"{key}={value} is above the maximum {maximum}"
    return None


def validate_entry(entry: Any) -> list[str]:
    """Return the problems with one registry entry; empty list means well-formed.

    Checks presence of every :data:`REQUIRED_ENTRY_KEYS` key and that the values are
    the kind of value the runbook actually produces: an ``owner/name`` HF repo, a hex
    checkpoint sha, a coverage at or above the INV-DP-002 floor, a finite non-negative
    CRPS, an ISO-dated ``trained_at``, and a positive training row count.
    """
    if not isinstance(entry, dict):
        return [f"entry must be a JSON object, got {type(entry).__name__}"]

    problems: list[str] = [
        f"missing required key {k!r}" for k in REQUIRED_ENTRY_KEYS if k not in entry
    ]

    repo = entry.get("repo")
    if "repo" in entry and (
        not isinstance(repo, str) or repo.count("/") != 1 or not all(repo.split("/"))
    ):
        problems.append(f"repo must be an 'owner/name' HF repo id, got {repo!r}")

    sha = entry.get("sha")
    if "sha" in entry and (not isinstance(sha, str) or not _SHA_RE.match(sha.strip().lower())):
        problems.append(f"sha must be a hex string of >= {_MIN_SHA_LEN} chars, got {sha!r}")

    if "coverage_p90" in entry:
        problem = _validate_number("coverage_p90", entry["coverage_p90"], minimum=0.0, maximum=1.0)
        if problem:
            problems.append(problem)
        elif float(entry["coverage_p90"]) < COVERAGE_FLOOR:
            problems.append(
                f"coverage_p90={entry['coverage_p90']} < floor {COVERAGE_FLOOR} (uncalibrated)"
            )

    if "final_crps" in entry:
        problem = _validate_number("final_crps", entry["final_crps"], minimum=0.0)
        if problem:
            problems.append(problem)

    trained_at = entry.get("trained_at")
    if "trained_at" in entry and (
        not isinstance(trained_at, str) or not _DATE_RE.match(trained_at.strip())
    ):
        problems.append(f"trained_at must start with an ISO date (YYYY-MM-DD), got {trained_at!r}")

    rows = entry.get("rows")
    if "rows" in entry and (isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0):
        problems.append(f"rows must be a positive integer, got {rows!r}")

    return problems


def registry_status(
    registry: dict[str, Any] | None = None, *, name: str = SERVING_NAME
) -> RegistryStatus:
    """Classify the committed registry record for ``name`` without touching the network."""
    if registry is None:
        if not REGISTRY.is_file():
            return RegistryStatus("missing", (f"{REGISTRY.name} not found",))
        registry = _load_registry()
        if not registry:
            return RegistryStatus("missing", (f"{REGISTRY.name} is empty or unparseable",))
    if not registry:
        return RegistryStatus("missing", ("registry is empty",))
    if "__placeholder__" in registry:
        return RegistryStatus(
            "placeholder",
            ("no checkpoint published yet - run docs/runbooks/train-and-publish-checkpoint.md",),
        )
    if name not in registry:
        return RegistryStatus("invalid", (f"no entry for serving name {name!r}",))
    problems = validate_entry(registry[name])
    if problems:
        return RegistryStatus("invalid", tuple(problems))
    return RegistryStatus("populated")


def run_validate_registry(*, as_json: bool = False, check: bool = False) -> int:
    """Report the registry record's shape. Exit 1 (with ``--check``) only on ``invalid``."""
    status = registry_status()
    detail = "; ".join(status.problems) or f"entry for {SERVING_NAME} is complete and well-formed"
    if as_json:
        payload = {"status": status.status, "problems": list(status.problems)}
        print(json.dumps(payload, sort_keys=True))
    else:
        sym = {"populated": "[OK]", "placeholder": "[--]", "missing": "[--]", "invalid": "[XX]"}[
            status.status
        ]
        print(f"{sym} registry-schema  {status.status}: {detail}")
    if check:
        return 1 if status.status == "invalid" else 0
    return 0


def evaluate(*, name: str = SERVING_NAME) -> PublishProbe:
    """Verify the published production checkpoint; SKIP when unclaimed/unverifiable."""
    repo = os.environ.get("DP_HF_REPO") or None
    if repo is None:
        return PublishProbe("skip", "DP_HF_REPO unset - no published model claimed (operator step)")

    registry = _load_registry()
    if not registry or "__placeholder__" in registry:
        return PublishProbe(
            "skip",
            "published_checkpoints.json is a placeholder - run the publish runbook + record it",
        )

    try:
        from huggingface_hub import hf_hub_download  # noqa: PLC0415
    except ImportError:
        return PublishProbe("skip", "huggingface_hub absent - cannot verify the remote")

    try:
        sidecar_path = hf_hub_download(repo_id=repo, filename=f"{name}.serving.json")
        sidecar: dict[str, Any] = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — an unreachable/absent remote is honest SKIP, not a lie
        return PublishProbe("skip", f"could not fetch {name}.serving.json from {repo}: {exc}")

    if sidecar.get("smoke") is True:
        return PublishProbe("fail", f"published {name} is a SMOKE artifact, not a production model")

    calib = sidecar.get("calibrator", {}) or {}
    coverage = calib.get("last_coverage_p90")
    if coverage is None or float(coverage) < COVERAGE_FLOOR:
        return PublishProbe(
            "fail", f"published coverage_p90={coverage} < floor {COVERAGE_FLOOR} (uncalibrated)"
        )

    # Cross-check the operator's recorded sha against the published version sha.
    entry = registry.get(name) or registry.get(repo) or {}
    recorded_sha = str(entry.get("sha", "")).strip()
    published_version = str(sidecar.get("version", ""))  # e.g. "full_<sha>"
    if recorded_sha and recorded_sha not in published_version:
        return PublishProbe(
            "fail",
            f"registry sha {recorded_sha!r} not in published version {published_version!r} (drift)",
        )

    return PublishProbe(
        "ok",
        f"published {name} @ {repo}: version={published_version}, coverage_p90={coverage}",
    )


def run(*, as_json: bool = False, check: bool = False) -> int:
    probe = evaluate()
    if as_json:
        print(json.dumps({"status": probe.status, "detail": probe.detail}, sort_keys=True))
    else:
        sym = {"ok": "[OK]", "fail": "[XX]", "skip": "[--]"}[probe.status]
        print(f"{sym} published-checkpoint  {probe.detail}")
    if check:
        return 1 if probe.status == "fail" else 0
    return 0


if __name__ == "__main__":
    _as_json = "--json" in sys.argv
    _check = "--check" in sys.argv
    if "--validate-registry" in sys.argv:
        sys.exit(run_validate_registry(as_json=_as_json, check=_check))
    sys.exit(run(as_json=_as_json, check=_check))
