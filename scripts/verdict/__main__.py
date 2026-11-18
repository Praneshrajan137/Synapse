"""Entry point for ``python -m scripts.verdict``.

The guard matters on Windows: the miniature's worker processes start by importing the main
module, and an unguarded call would re-run the whole verdict in every worker (truth LOG M-20).
"""

from __future__ import annotations

from scripts.verdict.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
