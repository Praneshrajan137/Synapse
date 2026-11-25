"""Write the record of one confirmatory attempt, to be pushed before the attempt reads the beacon.

PREREG-1 section 5: "An attempt is any execution that reads R_C's signature; each is logged
publicly (a pushed commit) before its output is opened." This writes
``docs/truth/confirm/attempts/<nonce>.json``: a fresh random nonce, the time, the commit and the
digest of freeze C's sums file. :mod:`scripts.confirm.run` refuses an attempt whose record is not on
``origin/main`` byte for byte, or that a results file has already used, so every execution that
reads the signature was announced first, and a crashed or repeated one needs a new record.

``python -m scripts.confirm.attempt`` then commit and push the file it names.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATTEMPTS = ROOT / "docs" / "truth" / "confirm" / "attempts"
SUMS_C = ROOT / "docs" / "truth" / "sealed" / "SHA256SUMS-C"
ROUND = 34714612


def main() -> None:
    nonce = secrets.token_hex(16)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    record = {
        "nonce": nonce,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit,
        "freeze_c_sums_sha256": hashlib.sha256(
            SUMS_C.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "round": ROUND,
    }
    ATTEMPTS.mkdir(parents=True, exist_ok=True)
    path = ATTEMPTS / f"{nonce}.json"
    path.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    rel = path.relative_to(ROOT).as_posix()
    print(f"written {rel}\nnext: commit and push it to main, then run")
    print(f"  python -m scripts.confirm.run --attempt {nonce}")


if __name__ == "__main__":
    main()
