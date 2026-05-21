"""Pre-commit / CI guard: no raw PII inside LLM prompts (Sprint 9 §M-life-5).

Scans LLM prompt-template files for the same PII regexes used by
``synapse_common.logging_config.PII_PATTERNS``. Prompts that ship raw
phone numbers, emails, Aadhaar IDs, or PIN codes are caught at
commit time so they never enter the KV-cached prefix.

Scope (Sprint 9):
  - ``orchestrator/llm/context_builder.py`` — the frozen system prompt.
  - any string assigned to ``SYSTEM_PROMPT`` / ``PROMPT`` / ``TEMPLATE``
    in ``agents/<name>/inference/*.py``.
  - ``tests/eval/judge_prompt.md``.

Sprint 10 widens to every ``.j2`` template once the scaffold generator
is fully adopted.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b"),
    "aadhaar": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "pin_code": re.compile(r"(?<!\d)\d{6}(?!\d)"),
}

TARGETS = [
    REPO_ROOT / "orchestrator" / "llm" / "context_builder.py",
    REPO_ROOT / "tests" / "eval" / "judge_prompt.md",
]
GLOB_TARGETS = [
    "agents/*/inference/*.py",
]
ALLOWLIST = {
    # File contains an example string explaining the rule — false positive.
    "scripts/check_llm_prompt_pii.py",
    "packages/synapse_common/logging_config.py",
}


def _collect_files() -> list[Path]:
    files = [p for p in TARGETS if p.exists()]
    for pattern in GLOB_TARGETS:
        files.extend(sorted(REPO_ROOT.glob(pattern)))
    return files


def scan_file(path: Path) -> list[tuple[str, str]]:
    """Return list of (pii_kind, snippet) findings for ``path``."""
    rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    if rel in ALLOWLIST:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    findings: list[tuple[str, str]] = []
    for kind, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append((kind, match.group(0)))
    return findings


def main() -> int:
    bad: list[str] = []
    for path in _collect_files():
        findings = scan_file(path)
        for kind, snippet in findings:
            rel = path.relative_to(REPO_ROOT)
            bad.append(f"{rel}: {kind} pattern matched ({snippet!r})")
    if bad:
        print("Raw PII detected in LLM prompts (Sprint 9 §M-life-5):", file=sys.stderr)
        for entry in bad:
            print(f"  - {entry}", file=sys.stderr)
        return 1
    print("LLM prompts: no raw PII detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
