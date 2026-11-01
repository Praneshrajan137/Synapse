"""Operator credential store for authenticated mode (ADR-057).

Sign-in is dormant while the console runs open (``SYNAPSE_ACCESS_MODE=open``). Once
authenticated mode is activated, ``POST /api/v1/auth/login`` verifies against exactly ONE of:

``SYNAPSE_OPERATORS_JSON``
    A JSON list of ``{"id", "role", "scrypt": {"salt_b64", "n", "r", "p", "dklen",
    "hash_b64"}}`` entries, built by ``python -m api.operator_hash``. Verified with stdlib
    ``hashlib.scrypt`` and ``hmac.compare_digest``. A malformed list refuses startup in EITHER
    mode, so a broken store is found while it is still dormant, not at activation.
``SYNAPSE_DEV_OPERATORS_INSECURE=1``
    The plaintext development table below. Its passwords are public -- this repository is
    public -- so it is reachable only behind this explicit opt-in, it logs a structured
    warning whenever it is enabled or consulted, and no compose file sets it.

Cost floor. Every entry must cost at least one of the OWASP Password Storage Cheat Sheet's
minimum scrypt configurations: ``r >= 8``, ``N`` a power of two ``>= 2**13`` and
``N * p >= 81_920``. That one inequality admits exactly OWASP's rows -- (2**17, p=1),
(2**16, 2), (2**15, 3), (2**14, 5), (2**13, 10) -- and anything stronger at the same ``N``
up to the memory ceiling, and it refuses each row with one less unit of ``p``.

Memory ceiling. One derivation may allocate at most 256 MiB: the ``maxmem`` it passes to
``hashlib.scrypt`` (``128 * r * (N + p + 2)`` bytes, plus 1 MiB of slack) may not exceed it,
or the store refuses startup. Two derivations run at a time, so sign-in holds at most 512 MiB
of the gateway's 1 GiB container (``docker/docker-compose.gcp.yml``). OWASP's rows fit (the
first passes about 129 MiB); ``N = 2**18`` at ``r = 8`` does not.

One cost per store. Every entry shares one ``(n, r, p, dklen)``, so the decoy derivation an
unknown id pays costs exactly what a known id's derivation costs.

Operator ids are e-mail addresses (``operator_id_problem``): the console's sign-in field is
``type="email"`` and submits nothing else.

Passwords are NFC-normalised before derivation (NIST SP 800-63B-4 section 3.1.1.2), at hashing
and at verification alike, so canonically equivalent spellings verify the same way.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import threading
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import structlog
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator
from synapse_common.auth import Role

from api.access import PREVIEW_SUBJECT, AccessMode

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = structlog.get_logger(__name__)

OPERATORS_ENV: Final = "SYNAPSE_OPERATORS_JSON"
DEV_OPT_IN_ENV: Final = "SYNAPSE_DEV_OPERATORS_INSECURE"

MIN_SCRYPT_N: Final = 2**13
MIN_SCRYPT_R: Final = 8
MIN_SCRYPT_N_TIMES_P: Final = 5 * 2**14
MIN_SALT_BYTES: Final = 16
MIN_DKLEN: Final = 32
MAX_DKLEN: Final = 128
#: The most one derivation may allocate: the ``maxmem`` it passes to ``hashlib.scrypt``. Two
#: derivations at this ceiling hold half of the gateway's 1 GiB container.
MAX_SCRYPT_MEMORY_BYTES: Final = 2**28
_MAXMEM_SLACK_BYTES: Final = 2**20

MIN_OPERATOR_ID_CHARS: Final = 3
MAX_OPERATOR_ID_CHARS: Final = 120
#: The HTML Standard's "valid e-mail address", the rule a ``type="email"`` field applies before
#: it submits (https://html.spec.whatwg.org/multipage/forms.html#valid-e-mail-address).
_VALID_EMAIL_ADDRESS: Final = re.compile(
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*"
)

#: NIST SP 800-63B-4 section 3.1.1.2: a single-factor password is at least 15 characters.
MIN_PASSWORD_CHARS: Final = 15
#: The sign-in form's own ceiling (``LoginRequest.password``), above NIST's 64-character floor.
MAX_PASSWORD_CHARS: Final = 200

#: How many derivations run at once. The sign-in route waits for one of these slots on the
#: event loop (``api.routers.auth.derivation_limiter``); this semaphore holds the same bound for
#: any other caller in the process, so it never blocks a derivation the route has admitted.
DERIVATION_SLOTS: Final = 2
_DERIVATION_SEMAPHORE: Final = threading.BoundedSemaphore(DERIVATION_SLOTS)


@dataclass(frozen=True)
class ScryptCost:
    """The scrypt work factor of one entry: CPU/memory cost, block size, parallelism, length."""

    n: int
    r: int
    p: int
    dklen: int


#: The OWASP Password Storage Cheat Sheet's first scrypt row (128 MiB per derivation).
RECOMMENDED_COST: Final = ScryptCost(n=2**17, r=8, p=1, dklen=32)


class OperatorConfigError(RuntimeError):
    """An operator store the gateway refuses to start with."""


def _scrypt_memory_bytes(n: int, r: int, p: int) -> int:
    """OpenSSL's scrypt allocation: ``128 * r * p`` for B plus ``128 * r * (N + 2)`` for V."""
    return 128 * r * (n + p + 2)


def _maxmem(cost: ScryptCost) -> int:
    """The ``maxmem`` a derivation at ``cost`` passes: its allocation plus 1 MiB of slack."""
    return _scrypt_memory_bytes(cost.n, cost.r, cost.p) + _MAXMEM_SLACK_BYTES


def _decode_b64(value: str, field: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except binascii.Error:
        raise ValueError(f"{field} is not standard base64") from None


def _scrypt(password: str, salt: bytes, cost: ScryptCost) -> bytes:
    """Derive ``password`` (NFC-normalised, UTF-8) under ``cost``; two derivations at a time."""
    secret = unicodedata.normalize("NFC", password).encode("utf-8")
    with _DERIVATION_SEMAPHORE:
        return hashlib.scrypt(
            secret,
            salt=salt,
            n=cost.n,
            r=cost.r,
            p=cost.p,
            maxmem=_maxmem(cost),
            dklen=cost.dklen,
        )


def _require_scrypt() -> None:
    if not hasattr(hashlib, "scrypt"):
        raise OperatorConfigError(
            "this Python build has no hashlib.scrypt (it needs OpenSSL 1.1 or later); "
            "the operator store cannot verify anything. Refusing to start (ADR-057)."
        )


def operator_id_problem(operator_id: str) -> str | None:
    """Why ``operator_id`` cannot be an operator's sign-in id, or ``None`` when it can.

    The console's sign-in field is ``type="email"``, so an id the browser does not take for an
    e-mail address can never be submitted. An id is not the reserved ``preview``; it has 3 to
    120 characters, no whitespace, exactly one ``@`` after a non-empty local part and a dot in
    its domain; and it is a valid e-mail address by the HTML Standard's rule, which also
    refuses what those checks let through, such as ``ops@exa_mple.org`` or ``ops@example..org``.
    """
    if operator_id.casefold() == PREVIEW_SUBJECT:
        return f"id {PREVIEW_SUBJECT!r} is reserved for the synthetic preview grant"
    if not MIN_OPERATOR_ID_CHARS <= len(operator_id) <= MAX_OPERATOR_ID_CHARS:
        return f"an operator id has {MIN_OPERATOR_ID_CHARS} to {MAX_OPERATOR_ID_CHARS} characters"
    if any(character.isspace() for character in operator_id):
        return "an operator id has no whitespace"
    local_part, _at, domain = operator_id.partition("@")
    if operator_id.count("@") != 1 or not local_part:
        return "an operator id is an e-mail address: one @ after a non-empty local part"
    if "." not in domain:
        return "an operator id's domain has a dot"
    if _VALID_EMAIL_ADDRESS.fullmatch(operator_id) is None:
        return "an operator id is an e-mail address the sign-in form accepts"
    return None


class ScryptParams(BaseModel):
    """One entry's stored verifier: the salt, the cost and the derived hash, base64-encoded."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    salt_b64: str
    n: int
    r: int
    p: int
    dklen: int
    hash_b64: str

    @model_validator(mode="after")
    def _meets_the_cost_floor(self) -> ScryptParams:
        if self.n < MIN_SCRYPT_N or self.n & (self.n - 1):
            raise ValueError(f"n must be a power of two >= {MIN_SCRYPT_N}")
        if self.r < MIN_SCRYPT_R:
            raise ValueError(f"r must be >= {MIN_SCRYPT_R}")
        if self.p < 1 or self.n * self.p < MIN_SCRYPT_N_TIMES_P:
            raise ValueError(
                f"n * p must be >= {MIN_SCRYPT_N_TIMES_P}, OWASP's minimum scrypt cost"
            )
        if not MIN_DKLEN <= self.dklen <= MAX_DKLEN:
            raise ValueError(f"dklen must be between {MIN_DKLEN} and {MAX_DKLEN}")
        if _maxmem(self.cost) > MAX_SCRYPT_MEMORY_BYTES:
            raise ValueError(
                "n, r and p let one derivation allocate more than "
                f"{MAX_SCRYPT_MEMORY_BYTES // 2**20} MiB"
            )
        if len(_decode_b64(self.salt_b64, "salt_b64")) < MIN_SALT_BYTES:
            raise ValueError(f"salt_b64 must decode to at least {MIN_SALT_BYTES} bytes")
        if len(_decode_b64(self.hash_b64, "hash_b64")) != self.dklen:
            raise ValueError("hash_b64 must decode to exactly dklen bytes")
        return self

    @property
    def cost(self) -> ScryptCost:
        return ScryptCost(n=self.n, r=self.r, p=self.p, dklen=self.dklen)

    @property
    def salt(self) -> bytes:
        return _decode_b64(self.salt_b64, "salt_b64")

    @property
    def digest(self) -> bytes:
        return _decode_b64(self.hash_b64, "hash_b64")


class OperatorEntry(BaseModel):
    """One operator who may sign in once authenticated mode is active."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    operator_id: str = Field(
        alias="id", min_length=MIN_OPERATOR_ID_CHARS, max_length=MAX_OPERATOR_ID_CHARS
    )
    role: Role
    scrypt: ScryptParams

    @model_validator(mode="after")
    def _is_an_operator_id(self) -> OperatorEntry:
        problem = operator_id_problem(self.operator_id)
        if problem is not None:
            raise ValueError(problem)
        return self


class ScryptOperatorStore(BaseModel):
    """The ``SYNAPSE_OPERATORS_JSON`` operators: non-empty, ids unique case-insensitively, and
    one scrypt cost shared by every entry."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    operators: tuple[OperatorEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> ScryptOperatorStore:
        seen: dict[str, int] = {}
        for index, entry in enumerate(self.operators):
            key = entry.operator_id.casefold()
            if key in seen:
                raise ValueError(f"entries {seen[key]} and {index} share an id")
            seen[key] = index
        return self

    @model_validator(mode="after")
    def _every_entry_shares_one_cost(self) -> ScryptOperatorStore:
        first = self.operators[0].scrypt.cost
        for index, entry in enumerate(self.operators):
            if entry.scrypt.cost != first:
                raise ValueError(
                    f"entry {index} costs {entry.scrypt.cost} but entry 0 costs {first}: "
                    "every entry must use one scrypt cost (n, r, p, dklen), so an unknown "
                    "id costs what a known id costs"
                )
        return self

    def authenticate(self, operator_id: str, password: str) -> Role | None:
        """The entry's role when ``password`` derives to its hash; ``None`` otherwise.

        An unknown id still pays one derivation at the store's one cost (every entry shares
        it), so the response time does not say which ids exist (OWASP ASVS 5.0 requirement
        6.3.8).
        """
        wanted = operator_id.casefold()
        entry = next((e for e in self.operators if e.operator_id.casefold() == wanted), None)
        if entry is None:
            decoy = self.operators[0].scrypt
            _scrypt(password, decoy.salt, decoy.cost)
            return None
        derived = _scrypt(password, entry.scrypt.salt, entry.scrypt.cost)
        if hmac.compare_digest(derived, entry.scrypt.digest):
            return entry.role
        return None


#: PUBLIC development passwords: this repository is public, so anyone can read them.
#: Reachable only with SYNAPSE_DEV_OPERATORS_INSECURE=1, which no compose file sets.
_INSECURE_DEV_OPERATORS: Final[dict[str, tuple[str, Role]]] = {
    "ops@synapse.local": ("ops_dev_2026!!", Role.OPS),
    "engineer@synapse.local": ("engineer_dev_2026!!", Role.ENGINEER),
    "admin@synapse.local": ("admin_dev_2026!!", Role.ADMIN),
    "viewer@synapse.local": ("viewer_dev_2026!!", Role.VIEWER),
}

_INSECURE_WARNING: Final = (
    "plaintext development passwords published in a public repository; "
    "never set SYNAPSE_DEV_OPERATORS_INSECURE outside a local machine"
)


class InsecureDevOperatorTable:
    """The plaintext development operators, behind ``SYNAPSE_DEV_OPERATORS_INSECURE=1``."""

    def authenticate(self, operator_id: str, password: str) -> Role | None:
        logger.warning("dev_operators_insecure_consulted", warning=_INSECURE_WARNING)
        entry = _INSECURE_DEV_OPERATORS.get(operator_id)
        if entry is None:
            return None
        expected, role = entry
        if hmac.compare_digest(expected.encode("utf-8"), password.encode("utf-8")):
            return role
        return None


OperatorSource = ScryptOperatorStore | InsecureDevOperatorTable

_ENTRIES: Final = TypeAdapter(list[OperatorEntry])


def _describe(exc: ValidationError) -> str:
    """Where and why each entry failed -- never the input itself, which holds salts and hashes."""
    reasons: list[str] = []
    for error in exc.errors(include_url=False):
        where = ".".join(str(part) for part in error["loc"]) or "<list>"
        reasons.append(f"{where}: {error['msg']}")
    return "; ".join(reasons)


def parse_operators_json(raw: str) -> ScryptOperatorStore:
    """Parse ``SYNAPSE_OPERATORS_JSON``; raise ``OperatorConfigError`` naming every fault."""
    try:
        return ScryptOperatorStore(operators=tuple(_ENTRIES.validate_json(raw, strict=True)))
    except ValidationError as exc:
        # `from None`: the chained ValidationError would print the salts and hashes it saw.
        raise OperatorConfigError(
            f"{OPERATORS_ENV} is malformed: {_describe(exc)}. Rebuild each entry with "
            "`python -m api.operator_hash`. Refusing to start (ADR-057)."
        ) from None


def insecure_dev_opt_in(environ: Mapping[str, str]) -> bool:
    """``SYNAPSE_DEV_OPERATORS_INSECURE``: ``1`` opts in; unset, empty or ``0`` does not."""
    raw = environ.get(DEV_OPT_IN_ENV)
    if raw is None or raw.strip() in {"", "0"}:
        return False
    if raw.strip() == "1":
        return True
    raise OperatorConfigError(
        f"{DEV_OPT_IN_ENV}={raw!r}: set it to 1 to opt in to the PUBLIC development "
        "passwords, or unset it. Refusing to start (ADR-057)."
    )


def operator_source(environ: Mapping[str, str]) -> OperatorSource:
    """The one credential source authenticated mode verifies against.

    Exactly one of ``SYNAPSE_OPERATORS_JSON`` and ``SYNAPSE_DEV_OPERATORS_INSECURE=1`` must be
    set: neither leaves nobody able to sign in, and both is ambiguous. Either refuses startup.
    """
    raw = environ.get(OPERATORS_ENV)
    insecure = insecure_dev_opt_in(environ)
    if raw is not None and insecure:
        raise OperatorConfigError(
            f"both {OPERATORS_ENV} and {DEV_OPT_IN_ENV}=1 are set; set exactly one operator "
            "source. Refusing to start (ADR-057)."
        )
    if raw is not None:
        _require_scrypt()
        return parse_operators_json(raw)
    if insecure:
        logger.warning("dev_operators_insecure_enabled", warning=_INSECURE_WARNING)
        return InsecureDevOperatorTable()
    raise OperatorConfigError(
        f"authenticated mode needs {OPERATORS_ENV} (build entries with "
        f"`python -m api.operator_hash`) or, on a local machine only, {DEV_OPT_IN_ENV}=1. "
        "Refusing to start (ADR-057)."
    )


def validate_operator_config(environ: Mapping[str, str], mode: AccessMode) -> None:
    """Startup check: refuse a malformed operator config in either access mode.

    Authenticated mode needs exactly one source. Open mode still parses a provided
    ``SYNAPSE_OPERATORS_JSON``, so the store is proven well-formed before activation, and it
    warns that an insecure opt-in has nothing to open while sign-in is dormant.
    """
    if mode is AccessMode.AUTHENTICATED:
        operator_source(environ)
        return
    raw = environ.get(OPERATORS_ENV)
    if raw is not None:
        parse_operators_json(raw)
    if insecure_dev_opt_in(environ):
        logger.warning(
            "dev_operators_insecure_ignored",
            reason="open mode: sign-in is dormant, so the development table is unreachable",
        )


def check_new_password(operator_id: str, password: str) -> str | None:
    """Why ``password`` may not become ``operator_id``'s password, or ``None`` if it may.

    NIST SP 800-63B-4 section 3.1.1.2 sets the floor at 15 characters for a single-factor
    password, counted in Unicode code points after NFC normalisation, and asks for a
    blocklist of context-specific values. OWASP ASVS 5.0 requirements 6.1.2 and 6.2.11 make
    that list documented and enforced: here it is the operator id, its local part, the
    product's name and the four published development passwords, compared whole.
    """
    normalised = unicodedata.normalize("NFC", password)
    if len(normalised) < MIN_PASSWORD_CHARS:
        return f"a password needs at least {MIN_PASSWORD_CHARS} characters"
    if len(normalised) > MAX_PASSWORD_CHARS:
        return f"a password may have at most {MAX_PASSWORD_CHARS} characters"
    blocked = {
        operator_id.casefold(),
        operator_id.split("@", 1)[0].casefold(),
        "synapse",
        "synapse console",
        "synapseconsole",
        *(dev_password.casefold() for dev_password, _role in _INSECURE_DEV_OPERATORS.values()),
    }
    if normalised.casefold() in blocked:
        return "that password is on the context-specific blocklist"
    return None


def hash_operator(
    operator_id: str, role: Role, password: str, cost: ScryptCost
) -> dict[str, object]:
    """One ``SYNAPSE_OPERATORS_JSON`` entry for ``password``, proven parseable by the store.

    The entry is round-tripped through ``parse_operators_json`` before it is returned, so this
    function can only ever hand out an entry the gateway will accept. The password policy is
    ``check_new_password``'s job; this function derives whatever it is given.
    """
    _require_scrypt()
    salt = secrets.token_bytes(MIN_SALT_BYTES)
    digest = _scrypt(password, salt, cost)
    entry: dict[str, object] = {
        "id": operator_id,
        "role": role.value,
        "scrypt": {
            "salt_b64": base64.b64encode(salt).decode("ascii"),
            "n": cost.n,
            "r": cost.r,
            "p": cost.p,
            "dklen": cost.dklen,
            "hash_b64": base64.b64encode(digest).decode("ascii"),
        },
    }
    parse_operators_json(json.dumps([entry], sort_keys=True, separators=(",", ":")))
    return entry
