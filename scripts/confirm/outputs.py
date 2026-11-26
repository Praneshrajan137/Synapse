"""Where the runner and power write, and the rule that no frozen file is ever overwritten.

Freeze C lists the dry run and the power record among its frozen files (``SHA256SUMS-C``). A dry run
or a power run made after the freeze is a rehearsal. If it overwrote those files, the freeze would
break and every later attempt would refuse (truth session 6, the attack on freeze C). Before the
freeze, the records are written where freeze C will find them. After it, they go to
``docs/truth/confirm/rehearsals/``. Whatever the caller asks, :func:`write_json` refuses any path
a sums file lists, and it writes atomically.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SEALED = ROOT / "docs" / "truth" / "sealed"
SUMS_FILES = ("SHA256SUMS", "SHA256SUMS-W", "SHA256SUMS-D1", "SHA256SUMS-C")
COMPOSITION = ROOT / "docs" / "truth" / "composition"
REHEARSALS = ROOT / "docs" / "truth" / "confirm" / "rehearsals"


def frozen_names() -> frozenset[str]:
    """Every path, relative and in posix form, that a sums file in ``docs/truth/sealed/`` lists."""
    names: set[str] = set()
    for sums in SUMS_FILES:
        path = SEALED / sums
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                names.add(line.split(maxsplit=1)[1].lstrip("*").strip())
    return frozenset(names)


def freeze_c_exists() -> bool:
    """Whether this checkout holds freeze C's sums."""
    return (SEALED / "SHA256SUMS-C").is_file()


def record_dir() -> Path:
    """Where a dry run or a power run writes its record: beside the composition before freeze C,
    and among the rehearsals after it."""
    return REHEARSALS if freeze_c_exists() else COMPOSITION


def write_json(path: Path, document: Any) -> None:
    """Write ``document`` as canonical JSON, atomically, refusing a path any freeze lists."""
    try:
        rel: str | None = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        rel = None
    if rel is not None and rel in frozen_names():
        raise SystemExit(f"refusing to overwrite {rel}: a freeze lists it")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    print("written", path, flush=True)
