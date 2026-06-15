#!/usr/bin/env python3
"""Generate the portable agent orientation from the Claude-authoritative source.

SYNAPSE is read by more than one agent tool. Claude Code reads ``CLAUDE.md`` +
``.claude/skills/``; the cross-tool "agentsmd" convention has other agents
(Codex, Cursor, ...) read ``AGENTS.md`` + ``.agents/``. Keeping a second,
hand-maintained copy of the governance is a DRIFT LIABILITY — exactly the
failure ``docs/state/CURRENT.md`` + ``verify_claims.py`` exist to fight (the
hand-written ``AGENTS.md`` had already drifted into stating ``.Codex/worktrees/``
where the real path is ``.claude/worktrees/``).

So there is ONE source of truth (the Claude side) and the portable copies are
GENERATED + GATED:

  * ``AGENTS.md``  <- ``CLAUDE.md``  (banner + H1 title swap; body unchanged)
  * ``.agents/skills/synapse-engineer/**`` <- ``.claude/skills/synapse-engineer/**``
    (verbatim byte copy)

``verify_claims.py`` C54 calls :func:`check` and fails CI on any drift, so the
mirror can never silently rot.

Usage::

    python scripts/sync_agents.py            # regenerate the targets
    python scripts/sync_agents.py --check    # exit 1 if any target is stale
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CLAUDE_MD = ROOT / "CLAUDE.md"
AGENTS_MD = ROOT / "AGENTS.md"
CLAUDE_SKILL = ROOT / ".claude" / "skills" / "synapse-engineer"
AGENTS_SKILL = ROOT / ".agents" / "skills" / "synapse-engineer"

_BANNER = (
    "<!-- GENERATED from CLAUDE.md by scripts/sync_agents.py - DO NOT EDIT.\n"
    "     CLAUDE.md + .claude/skills/ are the single source of truth; edit\n"
    "     there and re-run `python scripts/sync_agents.py`. Drift is blocked\n"
    "     by verify_claims.py C54. -->\n\n"
)

# Local junk that must never be mirrored or trip the byte-equality gate.
_SKIP_PARTS = {"__pycache__"}
_SKIP_SUFFIXES = {".pyc", ".pyo"}


def render_agents_md(claude_text: str) -> str:
    """Transform CLAUDE.md text into AGENTS.md text.

    Deterministic and minimal: prepend the generated banner and swap ONLY the
    H1 title. In-body references to ``CLAUDE.md`` are left intact — they
    correctly point at the canonical file (e.g. "Update CLAUDE.md sprint
    status" is still an instruction to edit the source, not this mirror).
    """
    lines = claude_text.splitlines(keepends=True)
    out: list[str] = []
    swapped = False
    for line in lines:
        if not swapped and line.startswith("# CLAUDE.md"):
            line = line.replace("# CLAUDE.md", "# AGENTS.md", 1)
            swapped = True
        out.append(line)
    return _BANNER + "".join(out)


def _skill_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(
        p
        for p in base.rglob("*")
        if p.is_file()
        and not (_SKIP_PARTS & set(p.parts))
        and p.suffix not in _SKIP_SUFFIXES
    )


def write() -> None:
    """Regenerate AGENTS.md + .agents/skills/ from the sources."""
    AGENTS_MD.write_text(
        render_agents_md(CLAUDE_MD.read_text(encoding="utf-8")), encoding="utf-8"
    )
    # Rebuild the skill mirror from scratch so source deletions propagate.
    if AGENTS_SKILL.exists():
        shutil.rmtree(AGENTS_SKILL)
    for src in _skill_files(CLAUDE_SKILL):
        rel = src.relative_to(CLAUDE_SKILL)
        dst = AGENTS_SKILL / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def check() -> list[str]:
    """Return drift descriptions; an empty list means the mirror is in sync."""
    drift: list[str] = []

    expected_md = render_agents_md(CLAUDE_MD.read_text(encoding="utf-8"))
    actual_md = AGENTS_MD.read_text(encoding="utf-8") if AGENTS_MD.exists() else ""
    if actual_md != expected_md:
        drift.append("AGENTS.md is stale vs CLAUDE.md")

    src_files = _skill_files(CLAUDE_SKILL)
    src_rel = {p.relative_to(CLAUDE_SKILL) for p in src_files}
    for src in src_files:
        rel = src.relative_to(CLAUDE_SKILL)
        dst = AGENTS_SKILL / rel
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            drift.append(f".agents/skills/synapse-engineer/{rel.as_posix()} is stale vs .claude")
    for dst in _skill_files(AGENTS_SKILL):
        rel = dst.relative_to(AGENTS_SKILL)
        if rel not in src_rel:
            drift.append(
                f".agents/skills/synapse-engineer/{rel.as_posix()} has no source (remove it)"
            )
    return drift


def main(argv: list[str]) -> int:
    if "--check" in argv:
        drift = check()
        if drift:
            print("agent-orientation DRIFT detected:")
            for d in drift:
                print(f"  - {d}")
            print("\nFix: python scripts/sync_agents.py")
            return 1
        print("AGENTS.md + .agents/ are in sync with CLAUDE.md + .claude/skills/")
        return 0
    write()
    print("Regenerated AGENTS.md + .agents/skills/ from CLAUDE.md + .claude/skills/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
