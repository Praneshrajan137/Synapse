"""Hash one operator's password into a ``SYNAPSE_OPERATORS_JSON`` entry (ADR-057).

    python -m api.operator_hash --id ops@example.org --role ops

The id comes first: one that is not an e-mail address the console's sign-in field accepts
(``api.operators.operator_id_problem``) is refused before any password is asked for. The
password is then read twice with ``getpass`` (no echo; the prompts go to the terminal, not to
stdout). One that fails ``api.operators.check_new_password`` -- NIST SP 800-63B-4's 15-character
floor for a single-factor password, and the context-specific blocklist -- is refused. The rest
is derived with scrypt at the OWASP Password Storage Cheat Sheet's first configuration
(``N=2**17, r=8, p=1``), proven parseable by the gateway's own store, and written to stdout as
one canonical-JSON entry. Append it to the JSON list kept in the secret store
(``SYNAPSE_OPERATORS_JSON``); never commit it. Every entry of one store must share one cost
(the store refuses startup otherwise), and this CLI always derives at the same one, so
changing ``RECOMMENDED_COST`` means rebuilding every entry.

Exit status: 0 wrote an entry; 2 refused the input and wrote nothing to stdout. Standard
library only (I-1). It runs inside the api-gateway image, which ships ``api/``:
``docker compose exec api python -m api.operator_hash --id ... --role ...``.
"""

# synapse: seam(reason="operator-run hashing CLI for the dormant sign-in store", adr="ADR-057")

from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import TYPE_CHECKING, Final

from synapse_common.auth import Role

from api.operators import (
    RECOMMENDED_COST,
    OperatorConfigError,
    check_new_password,
    hash_operator,
    operator_id_problem,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

#: The exit status of a refused input: nothing was written to stdout.
EXIT_REFUSED: Final = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m api.operator_hash",
        description="Hash an operator password into one SYNAPSE_OPERATORS_JSON entry.",
    )
    parser.add_argument(
        "--id",
        required=True,
        dest="operator_id",
        help="the operator's sign-in id: an e-mail address",
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=[role.value for role in Role],
        help="the role this operator signs in with",
    )
    return parser


def _refuse(reason: str) -> int:
    sys.stderr.write(f"refused: {reason}\n")
    return EXIT_REFUSED


def main(argv: Sequence[str], read_secret: Callable[[str], str]) -> int:
    """Run the CLI over ``argv``, reading the password through ``read_secret``."""
    args = build_parser().parse_args(list(argv))
    operator_id: str = args.operator_id
    role = Role(args.role)
    id_problem = operator_id_problem(operator_id)
    if id_problem is not None:
        return _refuse(id_problem)
    password = read_secret(f"Password for {operator_id}: ")
    weakness = check_new_password(operator_id, password)
    if weakness is not None:
        return _refuse(weakness)
    if read_secret("Repeat the password: ") != password:
        return _refuse("the two entries differ")
    try:
        entry = hash_operator(operator_id, role, password, RECOMMENDED_COST)
    except OperatorConfigError as exc:
        return _refuse(str(exc))
    sys.stdout.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], getpass.getpass))
