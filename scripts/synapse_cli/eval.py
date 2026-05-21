"""``synapse eval run --suite golden`` CLI front-end (Sprint 8 WS-5 §M7)."""

from __future__ import annotations

import sys

from tests.eval.run import main as run_main


def main(argv: list[str] | None = None) -> int:
    return run_main(argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
