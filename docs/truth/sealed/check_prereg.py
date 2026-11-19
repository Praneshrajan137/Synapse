"""Check the sealed pre-registration against itself: python docs/truth/sealed/check_prereg.py

Standard library only, so anyone can run it anywhere. It recomputes what the sealed JSON states
and refuses on any disagreement:

1. every file listed in ``SHA256SUMS`` has the hash recorded there (the seal is intact);
2. the exploratory seed vectors follow from the stated derivation;
3. the confirmatory round is emitted at the stated instant under the stated round rule;
4. the freeze deadline is not after the round's emission.

It does not fetch the beacon: verifying the round itself is ``synapse_beacon``'s job, once the
round exists. Exit 0 when everything agrees, 1 otherwise.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _explore_seed(label: str, k: int) -> int:
    digest = hashlib.sha256(label.encode() + k.to_bytes(8, "big")).digest()
    return int.from_bytes(digest[:8], "big") >> 1


def _utc(text: str) -> int:
    return int(dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def main() -> int:
    """Run the four checks; print each; return the exit code."""
    failures: list[str] = []
    sums = (HERE / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    for line in sums:
        if not line.strip():
            continue
        recorded, name = line.split(maxsplit=1)
        actual = hashlib.sha256((HERE / name.strip()).read_bytes()).hexdigest()
        if actual != recorded:
            failures.append(f"{name.strip()}: sha256 {actual} is not the sealed {recorded}")
    doc = json.loads((HERE / "prereg-1.json").read_text(encoding="utf-8"))
    explore = doc["seeds"]["explore"]
    for k, value in explore["vectors"].items():
        if _explore_seed(explore["label"], int(k)) != value:
            failures.append(f"exploratory seed {k} does not follow from the stated derivation")
    confirm = doc["seeds"]["confirm"]
    beacon = confirm["beacon"]
    emitted = beacon["genesis_time"] + (confirm["round"] - 1) * beacon["period_s"]
    if emitted != _utc(confirm["round_emitted_at"]):
        failures.append(f"round {confirm['round']} is emitted at {emitted}, not as stated")
    if _utc(confirm["freeze_before"]) > emitted:
        failures.append("the freeze deadline falls after the confirmatory round's emission")
    for text in failures:
        print(f"FAIL {text}")
    print("OK the seal agrees with itself" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
