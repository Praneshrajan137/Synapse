"""ADR-057: the operator store authenticated mode will verify against, proven while dormant.

* ``SYNAPSE_OPERATORS_JSON`` holds scrypt verifiers; stdlib ``hashlib.scrypt`` derives and
  ``hmac.compare_digest`` compares. The right password signs in and a wrong one does not.
* The cost floor admits exactly the OWASP Password Storage Cheat Sheet's scrypt rows; the
  memory ceiling keeps one derivation within 256 MiB; every entry shares one cost.
* Operator ids are e-mail addresses, the only thing the console's sign-in field submits.
* A malformed store refuses startup in either access mode, without echoing its secrets.
* The plaintext development table is reachable only behind ``SYNAPSE_DEV_OPERATORS_INSECURE=1``
  and warns whenever it is enabled.
* A sign-in waits for one of two derivation slots on the event loop, not in a worker thread,
  and is answered 503 once the wait runs out.
* ``python -m api.operator_hash`` writes one entry the store accepts, or refuses and writes
  nothing to stdout.

Each verifier here is derived at a real cost (``N * p * r`` equal to OWASP's minimum), so the
module hashes its shared entry once.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from anyio import to_thread
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from synapse_common.auth import Role

from api import operator_hash, operators
from api.access import ACCESS_MODE_ENV, AccessMode
from api.middleware.jwt import manager
from api.operators import (
    DERIVATION_SLOTS,
    DEV_OPT_IN_ENV,
    MIN_PASSWORD_CHARS,
    OPERATORS_ENV,
    RECOMMENDED_COST,
    InsecureDevOperatorTable,
    OperatorConfigError,
    ScryptCost,
    ScryptOperatorStore,
    ScryptParams,
    check_new_password,
    hash_operator,
    insecure_dev_opt_in,
    operator_id_problem,
    operator_source,
    parse_operators_json,
    validate_operator_config,
)
from api.routers import auth

if TYPE_CHECKING:
    from collections.abc import Callable

#: OWASP's last scrypt row: the same work as N=2**17, p=1, in 8 MiB rather than 128 MiB.
FLOOR_COST = ScryptCost(n=2**13, r=8, p=10, dklen=32)
OPS_ID = "ops@example.test"
PASSWORD = "correct horse battery staple"
DEV_OPS_ID = "ops@synapse.local"
DEV_OPS_PASSWORD = operators._INSECURE_DEV_OPERATORS[DEV_OPS_ID][0]
#: The OWASP Password Storage Cheat Sheet's scrypt configurations, all with r = 8.
OWASP_SCRYPT_ROWS = [(2**17, 1), (2**16, 2), (2**15, 3), (2**14, 5), (2**13, 10)]
#: The most one derivation may allocate: two at once stay within half of a 1 GiB container.
CEILING_BYTES = 256 * 2**20
#: Distinctive verifier bytes, so a leak of either into an error message is detectable.
SALT_B64 = base64.b64encode(b"S" * 16).decode("ascii")
HASH_B64 = base64.b64encode(b"H" * 32).decode("ascii")


@pytest.fixture(autouse=True)
def _clean_access_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (ACCESS_MODE_ENV, OPERATORS_ENV, DEV_OPT_IN_ENV):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="module")
def operators_json() -> str:
    entry = hash_operator(OPS_ID, Role.OPS, PASSWORD, FLOOR_COST)
    return json.dumps([entry], sort_keys=True, separators=(",", ":"))


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")
    return TestClient(app)


def _entry(**scrypt: Any) -> dict[str, Any]:
    """A well-formed entry with zero derivation cost to build; ``scrypt`` overrides fields."""
    params: dict[str, Any] = {
        "salt_b64": SALT_B64,
        "n": 2**17,
        "r": 8,
        "p": 1,
        "dklen": 32,
        "hash_b64": HASH_B64,
    }
    params.update(scrypt)
    return {"id": OPS_ID, "role": "ops", "scrypt": params}


def _params(n: int, p: int) -> ScryptParams:
    return ScryptParams(salt_b64=SALT_B64, n=n, r=8, p=p, dklen=32, hash_b64=HASH_B64)


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
def test_scrypt_accepts_the_right_password_and_rejects_a_wrong_one(operators_json: str) -> None:
    store = parse_operators_json(operators_json)
    assert store.authenticate(OPS_ID, PASSWORD) is Role.OPS
    assert store.authenticate(OPS_ID, PASSWORD + "!") is None
    # The id matches case-insensitively; the password never does.
    assert store.authenticate(OPS_ID.upper(), PASSWORD) is Role.OPS
    assert store.authenticate(OPS_ID, PASSWORD.upper()) is None


def test_canonically_equivalent_spellings_of_a_password_verify_alike() -> None:
    composed = "caf\u00e9 au lait, extra hot"
    decomposed = "cafe\u0301 au lait, extra hot"
    entry = hash_operator(OPS_ID, Role.VIEWER, composed, FLOOR_COST)
    store = parse_operators_json(json.dumps([entry]))
    assert store.authenticate(OPS_ID, decomposed) is Role.VIEWER


def test_an_unknown_operator_is_refused_after_one_decoy_derivation(
    operators_json: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = parse_operators_json(operators_json)
    costs: list[ScryptCost] = []
    derive = operators._scrypt

    def counting(password: str, salt: bytes, cost: ScryptCost) -> bytes:
        costs.append(cost)
        return derive(password, salt, cost)

    monkeypatch.setattr(operators, "_scrypt", counting)
    assert store.authenticate("nobody@example.test", PASSWORD) is None
    assert costs == [FLOOR_COST]


# --------------------------------------------------------------------------- #
# The cost floor, the memory ceiling, and one cost per store
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("n", "p"), OWASP_SCRYPT_ROWS)
def test_the_cost_floor_admits_every_owasp_scrypt_row(n: int, p: int) -> None:
    assert _params(n, p).cost == ScryptCost(n=n, r=8, p=p, dklen=32)


@pytest.mark.parametrize(("n", "p"), OWASP_SCRYPT_ROWS)
def test_the_cost_floor_refuses_each_owasp_row_with_one_less_parallelism(n: int, p: int) -> None:
    with pytest.raises(ValidationError, match=r"n \* p must be"):
        _params(n, p - 1)


def test_the_recommended_cost_is_owasps_first_row() -> None:
    assert ScryptCost(n=2**17, r=8, p=1, dklen=32) == RECOMMENDED_COST
    assert _params(RECOMMENDED_COST.n, RECOMMENDED_COST.p).cost == RECOMMENDED_COST


def test_no_admitted_entry_lets_one_derivation_allocate_more_than_256_mib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ceiling caps the ``maxmem`` the derivation itself hands ``hashlib.scrypt``, which is
    what bounds OpenSSL's allocation; two derivations at once then fit in half of the gateway's
    1 GiB container. ``N = 2**18`` at ``r = 8`` needs 256 MiB for V alone, so it is refused."""
    passed: list[int] = []

    def recording_scrypt(
        password: bytes, *, salt: bytes, n: int, r: int, p: int, maxmem: int, dklen: int
    ) -> bytes:
        passed.append(maxmem)
        return bytes(dklen)

    monkeypatch.setattr(hashlib, "scrypt", recording_scrypt)
    for n, p in OWASP_SCRYPT_ROWS:
        operators._scrypt(PASSWORD, b"S" * 16, _params(n, p).cost)
    assert len(passed) == len(OWASP_SCRYPT_ROWS)
    assert max(passed) <= CEILING_BYTES
    for n in (2**18, 2**19):
        with pytest.raises(ValidationError, match="more than 256 MiB"):
            _params(n, 1)


#: A second entry differing from ``_entry(p=2)`` in exactly the named part of the cost.
OTHER_COSTS: dict[str, dict[str, Any]] = {
    "n": {"n": 2**16, "p": 2},
    "r": {"p": 2, "r": 9},
    "p": {"p": 3},
    "dklen": {"p": 2, "dklen": 64, "hash_b64": base64.b64encode(b"H" * 64).decode("ascii")},
}


@pytest.mark.parametrize("other", list(OTHER_COSTS.values()), ids=list(OTHER_COSTS))
def test_every_entry_of_a_store_must_share_one_scrypt_cost(other: dict[str, Any]) -> None:
    """An unknown id pays its decoy derivation at entry 0's cost, so a store whose entries
    cost differently would let response time tell its ids apart."""
    differing = _entry(**other)
    differing["id"] = "eng@example.test"
    with pytest.raises(OperatorConfigError, match="one scrypt cost"):
        parse_operators_json(json.dumps([_entry(p=2), differing]))
    matching = _entry(p=2)
    matching["id"] = "eng@example.test"
    store = parse_operators_json(json.dumps([_entry(p=2), matching]))
    assert len(store.operators) == 2


# --------------------------------------------------------------------------- #
# Operator ids are e-mail addresses
# --------------------------------------------------------------------------- #
#: Ids the console's ``type="email"`` sign-in field submits, the 120-character ceiling included.
ACCEPTED_IDS = [
    OPS_ID,
    "first.last+tag@sub.example.co",
    "o'brien@example.org",
    "OPS@EXAMPLE.TEST",
    "a" * 108 + "@example.org",
]
#: Ids the store and the hashing CLI refuse, each for the reason its key names.
REFUSED_IDS = {
    "no @": "ops.example.org",
    "two @": "ops@ops@example.org",
    "an empty local part": "@example.org",
    "a space": "ops team@example.org",
    "a trailing tab": "ops@example.org\t",
    "no dot in the domain": "ops@localhost",
    "an empty domain label": "ops@example..org",
    "a trailing dot": "ops@example.org.",
    "an underscore in the domain": "ops@exa_mple.org",
    "a parenthesis in the local part": "op(s)@example.org",
    "a non-ASCII letter": "ops@ex\u00e1mple.org",
    "121 characters": "a" * 109 + "@example.org",
    "the reserved preview id": "preview",
}


@pytest.mark.parametrize("operator_id", ACCEPTED_IDS)
def test_an_e_mail_address_is_an_operator_id_the_store_admits(operator_id: str) -> None:
    assert operator_id_problem(operator_id) is None
    entry = _entry()
    entry["id"] = operator_id
    store = parse_operators_json(json.dumps([entry]))
    assert store.operators[0].operator_id == operator_id


@pytest.mark.parametrize("operator_id", list(REFUSED_IDS.values()), ids=list(REFUSED_IDS))
def test_an_id_that_is_not_an_e_mail_address_is_refused_by_the_store_and_the_cli(
    operator_id: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert operator_id_problem(operator_id) is not None
    entry = _entry()
    entry["id"] = operator_id
    with pytest.raises(OperatorConfigError, match="Refusing to start"):
        parse_operators_json(json.dumps([entry]))
    prompts: list[str] = []

    def read_secret(prompt: str) -> str:
        prompts.append(prompt)
        return PASSWORD

    args = ["--id", operator_id, "--role", "ops"]
    assert operator_hash.main(args, read_secret) == operator_hash.EXIT_REFUSED
    # Refused before any password is asked for, and nothing reaches stdout.
    assert prompts == []
    written = capsys.readouterr()
    assert written.out == ""
    assert written.err.startswith("refused: ")


# --------------------------------------------------------------------------- #
# A malformed store refuses startup, in either mode, without leaking
# --------------------------------------------------------------------------- #
def _duplicate_ids() -> str:
    first, second = _entry(), _entry()
    second["id"] = OPS_ID.upper()
    return json.dumps([first, second])


def _with(**changes: Any) -> str:
    entry = _entry()
    entry.update(changes)
    return json.dumps([entry])


def _without_scrypt() -> str:
    entry = _entry()
    del entry["scrypt"]
    return json.dumps([entry])


def _two_costs() -> str:
    second = _entry(n=2**16, p=2)
    second["id"] = "eng@example.test"
    return json.dumps([_entry(), second])


MALFORMED_STORES = {
    "not JSON": "{",
    "empty value": "",
    "an empty list": "[]",
    "an object, not a list": json.dumps(_entry()),
    "no verifier": _without_scrypt(),
    "an extra key": _with(note="x"),
    "an unknown role": _with(role="root"),
    "the reserved preview id": _with(id="preview"),
    "an id too short": _with(id="ab"),
    "an id that is not an e-mail address": _with(id="operator-7"),
    "ids equal case-insensitively": _duplicate_ids(),
    "n not a power of two": json.dumps([_entry(n=100_000)]),
    "r below eight": json.dumps([_entry(r=4)]),
    "n * p below the floor": json.dumps([_entry(n=2**16, p=1)]),
    "one derivation above 256 MiB (n = 2**19)": json.dumps([_entry(n=2**19)]),
    "n = 2**18 at r = 8 (256 MiB of V before B and slack)": json.dumps([_entry(n=2**18)]),
    "two costs in one store": _two_costs(),
    "a short salt": json.dumps([_entry(salt_b64=base64.b64encode(b"s" * 8).decode())]),
    "a hash of the wrong length": json.dumps([_entry(dklen=64)]),
    "salt not base64": json.dumps([_entry(salt_b64="@@@@")]),
    "n as a float": json.dumps([_entry(n=131072.0)]),
}


@pytest.mark.parametrize("mode", [AccessMode.OPEN, AccessMode.AUTHENTICATED])
@pytest.mark.parametrize("raw", list(MALFORMED_STORES.values()), ids=list(MALFORMED_STORES))
def test_a_malformed_operator_store_refuses_startup_in_either_mode(
    raw: str, mode: AccessMode
) -> None:
    with pytest.raises(OperatorConfigError, match="Refusing to start"):
        validate_operator_config({OPERATORS_ENV: raw}, mode)


def test_a_refused_store_never_echoes_a_salt_or_a_hash() -> None:
    with pytest.raises(OperatorConfigError) as caught:
        parse_operators_json(json.dumps([_entry(n=100_000)]))
    message = str(caught.value)
    assert "n must be a power of two" in message
    assert SALT_B64 not in message
    assert HASH_B64 not in message
    # `from None`: the chained ValidationError, which holds the input, is not attached.
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


# --------------------------------------------------------------------------- #
# Which source authenticated mode verifies against
# --------------------------------------------------------------------------- #
class _RecordingLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, event: str, **_fields: Any) -> None:
        self.warnings.append(event)


def test_the_development_table_is_reachable_only_behind_the_insecure_opt_in(
    operators_json: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _RecordingLogger()
    monkeypatch.setattr(operators, "logger", recorder)
    # Without the opt-in the development passwords open nothing.
    store = operator_source({OPERATORS_ENV: operators_json})
    assert isinstance(store, ScryptOperatorStore)
    assert store.authenticate(DEV_OPS_ID, DEV_OPS_PASSWORD) is None
    assert recorder.warnings == []
    # With it, they do, and every enablement and consultation is a structured warning.
    table = operator_source({DEV_OPT_IN_ENV: "1"})
    assert isinstance(table, InsecureDevOperatorTable)
    assert table.authenticate(DEV_OPS_ID, DEV_OPS_PASSWORD) is Role.OPS
    assert recorder.warnings == [
        "dev_operators_insecure_enabled",
        "dev_operators_insecure_consulted",
    ]


@pytest.mark.parametrize("value", ["yes", "true", "2", "on", "-1"])
def test_an_insecure_opt_in_other_than_one_refuses_startup(value: str) -> None:
    with pytest.raises(OperatorConfigError, match="set it to 1"):
        insecure_dev_opt_in({DEV_OPT_IN_ENV: value})


def test_the_insecure_opt_in_is_exactly_one() -> None:
    assert insecure_dev_opt_in({DEV_OPT_IN_ENV: "1"}) is True


@pytest.mark.parametrize("value", [None, "", "0"])
def test_an_unset_empty_or_zero_opt_in_stays_off(value: str | None) -> None:
    environ = {} if value is None else {DEV_OPT_IN_ENV: value}
    assert insecure_dev_opt_in(environ) is False


def test_authenticated_mode_without_an_operator_source_refuses_startup() -> None:
    with pytest.raises(OperatorConfigError, match="authenticated mode needs"):
        validate_operator_config({}, AccessMode.AUTHENTICATED)


def test_both_operator_sources_at_once_refuse_startup(operators_json: str) -> None:
    environ = {OPERATORS_ENV: operators_json, DEV_OPT_IN_ENV: "1"}
    with pytest.raises(OperatorConfigError, match="exactly one operator source"):
        validate_operator_config(environ, AccessMode.AUTHENTICATED)


def test_open_mode_starts_with_no_operator_source() -> None:
    assert validate_operator_config({}, AccessMode.OPEN) is None


# --------------------------------------------------------------------------- #
# Sign-in once authenticated mode is active
# --------------------------------------------------------------------------- #
def test_sign_in_verifies_against_the_scrypt_store(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, operators_json: str
) -> None:
    monkeypatch.setenv(ACCESS_MODE_ENV, "authenticated")
    monkeypatch.setenv(OPERATORS_ENV, operators_json)
    ok = client.post("/api/v1/auth/login", json={"operator_id": OPS_ID, "password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["role"] == "ops"
    claims = manager().verify(ok.json()["access_token"], expected_type="access").raw_claims
    assert "preview" not in claims
    wrong = client.post("/api/v1/auth/login", json={"operator_id": OPS_ID, "password": "x" * 20})
    assert wrong.status_code == 401
    dev = client.post(
        "/api/v1/auth/login", json={"operator_id": DEV_OPS_ID, "password": DEV_OPS_PASSWORD}
    )
    assert dev.status_code == 401


def test_with_the_insecure_opt_in_a_development_password_signs_in(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ACCESS_MODE_ENV, "authenticated")
    monkeypatch.setenv(DEV_OPT_IN_ENV, "1")
    resp = client.post(
        "/api/v1/auth/login", json={"operator_id": DEV_OPS_ID, "password": DEV_OPS_PASSWORD}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "ops"


def test_sign_in_derives_through_two_slots_with_a_five_second_wait(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, operators_json: str
) -> None:
    calls: list[tuple[float, float]] = []

    async def recording(
        verify: Callable[[str, str], Role | None],
        operator_id: str,
        password: str,
        limiter: anyio.CapacityLimiter,
        wait_seconds: float,
    ) -> Role | None:
        calls.append((limiter.total_tokens, wait_seconds))
        return verify(operator_id, password)

    monkeypatch.setattr(auth, "verify_with_bounded_wait", recording)
    monkeypatch.setenv(ACCESS_MODE_ENV, "authenticated")
    monkeypatch.setenv(OPERATORS_ENV, operators_json)
    ok = client.post("/api/v1/auth/login", json={"operator_id": OPS_ID, "password": PASSWORD})
    assert ok.status_code == 200
    assert calls == [(2, 5.0)]


@pytest.mark.asyncio
async def test_a_queued_sign_in_waits_on_the_event_loop_then_gets_503() -> None:
    """With every derivation slot taken, a sign-in waits on the event loop, holding no worker
    thread, and once the bound runs out it is answered 503 with ``Retry-After``, underived."""
    limiter = anyio.CapacityLimiter(DERIVATION_SLOTS)
    holders = [object() for _ in range(DERIVATION_SLOTS)]
    for holder in holders:
        limiter.acquire_on_behalf_of_nowait(holder)
    threads = to_thread.current_default_thread_limiter()
    threads_before = threads.borrowed_tokens
    derived: list[str] = []
    refusals: list[HTTPException] = []

    def verify(operator_id: str, _password: str) -> Role | None:
        derived.append(operator_id)
        return Role.OPS

    async def sign_in() -> None:
        try:
            await auth.verify_with_bounded_wait(verify, OPS_ID, PASSWORD, limiter, 0.5)
        except HTTPException as exc:
            refusals.append(exc)

    try:
        # A wait with no bound fails this test here instead of hanging the run.
        with anyio.fail_after(10):
            async with anyio.create_task_group() as group:
                group.start_soon(sign_in)
                await anyio.sleep(0.1)
                assert limiter.statistics().tasks_waiting == 1
                assert threads.borrowed_tokens == threads_before
    finally:
        for holder in holders:
            limiter.release_on_behalf_of(holder)
    assert derived == []
    assert [refusal.status_code for refusal in refusals] == [503]
    assert refusals[0].detail == auth.SIGN_IN_BUSY
    assert refusals[0].headers == {"Retry-After": "1"}


@pytest.mark.asyncio
async def test_a_sign_in_with_a_free_slot_derives_off_the_event_loop() -> None:
    limiter = anyio.CapacityLimiter(DERIVATION_SLOTS)
    loop_thread = threading.get_ident()
    seen_threads: list[int] = []

    def verify(operator_id: str, password: str) -> Role | None:
        seen_threads.append(threading.get_ident())
        return Role.OPS if (operator_id, password) == (OPS_ID, PASSWORD) else None

    with anyio.fail_after(10):
        role = await auth.verify_with_bounded_wait(verify, OPS_ID, PASSWORD, limiter, 5.0)
    assert role is Role.OPS
    assert len(seen_threads) == 1
    assert seen_threads[0] != loop_thread
    # The slot came back: nothing is left borrowed once the derivation returns.
    assert limiter.borrowed_tokens == 0


# --------------------------------------------------------------------------- #
# New passwords, and the hashing CLI
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("x" * (MIN_PASSWORD_CHARS - 1), "at least 15 characters"),
        ("e\u0301" * 8, "at least 15 characters"),  # 16 code points typed, 8 after NFC
        (OPS_ID, "blocklist"),
        ("SYNAPSE CONSOLE", "blocklist"),
        ("engineer_dev_2026!!", "blocklist"),
    ],
)
def test_a_new_password_needs_fifteen_characters_and_must_avoid_the_blocklist(
    password: str, reason: str
) -> None:
    refusal = check_new_password(OPS_ID, password)
    assert refusal is not None
    assert reason in refusal


def test_a_long_unlisted_password_is_accepted_as_new() -> None:
    assert check_new_password(OPS_ID, PASSWORD) is None


def _answers(*replies: str) -> Callable[[str], str]:
    queue = list(replies)
    return lambda _prompt: queue.pop(0)


def test_the_hashing_cli_writes_one_entry_the_store_accepts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = ["--id", "eng@example.test", "--role", "engineer"]
    assert operator_hash.main(args, _answers(PASSWORD, PASSWORD)) == 0
    written = capsys.readouterr()
    entry = json.loads(written.out)
    assert entry["scrypt"]["n"] == RECOMMENDED_COST.n
    assert PASSWORD not in written.out
    assert PASSWORD not in written.err
    store = parse_operators_json(json.dumps([entry]))
    assert store.authenticate("eng@example.test", PASSWORD) is Role.ENGINEER


@pytest.mark.parametrize(
    ("operator_id", "replies", "reason"),
    [
        (OPS_ID, ("too short",), "at least 15 characters"),
        (OPS_ID, (PASSWORD, PASSWORD + "x"), "differ"),
        ("preview", (PASSWORD, PASSWORD), "reserved"),
    ],
    ids=["short", "mismatch", "reserved-id"],
)
def test_the_hashing_cli_refuses_and_writes_nothing_to_stdout(
    capsys: pytest.CaptureFixture[str],
    operator_id: str,
    replies: tuple[str, ...],
    reason: str,
) -> None:
    args = ["--id", operator_id, "--role", "ops"]
    assert operator_hash.main(args, _answers(*replies)) == operator_hash.EXIT_REFUSED
    written = capsys.readouterr()
    assert written.out == ""
    assert reason in written.err
