"""ADR-057 (finding 89): open preview access now, authenticated sign-in dormant until activated.

The deployed console used to sign every visitor in as ``admin`` with a development credential
compiled into the public bundle. These tests pin what replaced it:

* ``SYNAPSE_ACCESS_MODE`` and ``SYNAPSE_OPEN_AUTHORITY`` take only the values ADR-057 names,
  anything else refuses startup, and ``api.main`` resolves both from its own environment at
  import, so a bad value stops the process before uvicorn binds a port;
* in open mode the only credential is a one-hour preview grant whose role follows the open
  authority and never reaches ENGINEER, and sign-in answers 404 whatever body it is sent;
* in authenticated mode the preview route does not exist, and every outstanding grant is
  retired the moment the mode changes;
* no compose file opts in to the published development passwords, and the frontend source
  carries none of them.

The app under test mounts only the auth router plus one VIEWER-gated probe, so no Kafka or
Postgres connection is attempted.
"""

from __future__ import annotations

import ast
import importlib
from datetime import timedelta
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from synapse_common.auth import OperatorContext, Role, TokenError

from api import main as gateway
from api import operators
from api.access import (
    ACCESS_MODE_ENV,
    OPEN_AUTHORITY_ENV,
    PREVIEW_CLAIM,
    PREVIEW_SUBJECT,
    PREVIEW_TTL,
    AccessConfigError,
    AccessMode,
    AccessSettings,
    OpenAuthority,
    is_preview_grant,
    load_access_settings,
    sign_preview_access,
)
from api.middleware.jwt import CurrentOperator, manager, verify_access_token
from api.routers import auth

REPO_ROOT = Path(__file__).resolve().parents[2]
#: The plaintext development passwords: public by construction, reachable only behind the opt-in.
DEV_PASSWORDS = {
    operator: entry[0] for operator, entry in operators._INSECURE_DEV_OPERATORS.items()
}
#: Every name a compose file may carry, in each directory compose files live in.
COMPOSE_PATTERNS = ("docker-compose*.yml", "docker-compose*.yaml", "compose*.yml", "compose*.yaml")
#: Sign-in bodies FastAPI decodes, and would refuse with a 422 naming the sign-in fields if the
#: dormancy check ran in the handler: (raw body, content type).
MALFORMED_SIGN_IN_BODIES = {
    "an empty object": (b"{}", "application/json"),
    "an id too short": (b'{"operator_id": "ab", "password": "long enough"}', "application/json"),
    "a number for a password": (
        b'{"operator_id": "ops@example.test", "password": 7}',
        "application/json",
    ),
    "a list, not an object": (b"[]", "application/json"),
    "no body at all": (b"", "application/json"),
    "a body that is not JSON": (b"operator_id=ops", "text/plain"),
}


@pytest.fixture(autouse=True)
def _clean_access_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        ACCESS_MODE_ENV,
        OPEN_AUTHORITY_ENV,
        operators.OPERATORS_ENV,
        operators.DEV_OPT_IN_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


def _posture(monkeypatch: pytest.MonkeyPatch, mode: str, authority: str | None = None) -> None:
    monkeypatch.setenv(ACCESS_MODE_ENV, mode)
    if authority is not None:
        monkeypatch.setenv(OPEN_AUTHORITY_ENV, authority)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")

    @app.get("/probe")
    def probe(op: Annotated[OperatorContext, Depends(CurrentOperator)]) -> dict[str, str]:
        return {"role": op.role.value}

    return TestClient(app)


# --------------------------------------------------------------------------- #
# The two settings, and startup refusal
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", ["public", "", "OPEN", "open-ish", "closed"])
def test_an_unknown_access_mode_refuses_startup(value: str) -> None:
    with pytest.raises(AccessConfigError, match="Refusing to start"):
        load_access_settings({ACCESS_MODE_ENV: value})


@pytest.mark.parametrize("value", ["admin", "", "ACT", "write", "ops"])
def test_an_unknown_open_authority_refuses_startup(value: str) -> None:
    with pytest.raises(AccessConfigError, match="Refusing to start"):
        load_access_settings({ACCESS_MODE_ENV: "open", OPEN_AUTHORITY_ENV: value})


def test_with_nothing_set_the_posture_is_open_and_view_only() -> None:
    settings = load_access_settings({})
    assert settings.mode is AccessMode.OPEN
    assert settings.authority is OpenAuthority.VIEW


def test_authenticated_mode_never_reads_the_open_authority() -> None:
    settings = load_access_settings({ACCESS_MODE_ENV: "authenticated", OPEN_AUTHORITY_ENV: "x"})
    assert settings.mode is AccessMode.AUTHENTICATED
    assert settings.authority is None


def _module_level_call(tree: ast.Module, name: str) -> ast.Assign | ast.Expr:
    """The one module-level statement of ``api/main.py`` whose value calls ``name``."""
    found: list[ast.Assign | ast.Expr] = []
    for node in tree.body:
        if (
            isinstance(node, (ast.Assign, ast.Expr))
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == name
        ):
            found.append(node)
    assert len(found) == 1, f"api/main.py calls {name} at module level {len(found)} times"
    return found[0]


def test_the_gateway_resolves_its_access_posture_at_import() -> None:
    """``api.main`` reads the posture from ``os.environ`` itself, not from a literal, and checks
    the operator store against that same environment and the mode it resolved, both at module
    level. The reload test below proves the same claim by its outcome."""
    tree = ast.parse((REPO_ROOT / "api" / "main.py").read_text(encoding="utf-8"))
    load = _module_level_call(tree, "load_access_settings")
    validate = _module_level_call(tree, "validate_operator_config")
    assert isinstance(load, ast.Assign)
    assert [ast.unparse(target) for target in load.targets] == ["ACCESS_SETTINGS"]
    assert ast.unparse(load.value) == "load_access_settings(os.environ)"
    assert ast.unparse(validate.value) == (
        "validate_operator_config(os.environ, ACCESS_SETTINGS.mode)"
    )


def _reimported_posture() -> AccessSettings:
    """Re-execute ``api.main`` under the current environment; the posture it resolved."""
    importlib.reload(gateway)
    return gateway.ACCESS_SETTINGS


def test_the_gateway_follows_a_changed_environment_on_import_and_refuses_a_bad_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each re-import of ``api.main`` resolves the posture its environment names, and a setting
    the gateway cannot honour fails the import itself, which is what stops uvicorn from ever
    binding its port. ``load_access_settings({})`` or a hard-coded mode would fail here."""
    try:
        _posture(monkeypatch, "open", "act")
        opened = _reimported_posture()
        assert opened.mode is AccessMode.OPEN
        assert opened.authority is OpenAuthority.ACT

        _posture(monkeypatch, "authenticated")
        monkeypatch.setenv(operators.DEV_OPT_IN_ENV, "1")
        signed_in_only = _reimported_posture()
        assert signed_in_only.mode is AccessMode.AUTHENTICATED
        assert signed_in_only.authority is None

        monkeypatch.delenv(operators.DEV_OPT_IN_ENV)
        with pytest.raises(operators.OperatorConfigError, match="authenticated mode needs"):
            importlib.reload(gateway)

        _posture(monkeypatch, "public")
        with pytest.raises(AccessConfigError, match="Refusing to start"):
            importlib.reload(gateway)
    finally:
        for name in (ACCESS_MODE_ENV, OPEN_AUTHORITY_ENV, operators.DEV_OPT_IN_ENV):
            monkeypatch.delenv(name, raising=False)
        importlib.reload(gateway)


# --------------------------------------------------------------------------- #
# GET /mode
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("mode", "authority", "expected"),
    [
        (None, None, {"mode": "open", "authority": "view"}),
        ("open", "act", {"mode": "open", "authority": "act"}),
        ("authenticated", "act", {"mode": "authenticated", "authority": None}),
    ],
)
def test_the_mode_endpoint_publishes_the_posture_and_nothing_else(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    mode: str | None,
    authority: str | None,
    expected: dict[str, str | None],
) -> None:
    if mode is not None:
        _posture(monkeypatch, mode, authority)
    resp = client.get("/api/v1/auth/mode")
    assert resp.status_code == 200
    assert resp.json() == expected


# --------------------------------------------------------------------------- #
# POST /preview
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("authority", "role"), [("view", Role.VIEWER), ("act", Role.OPS)])
def test_the_preview_role_follows_the_open_authority(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, authority: str, role: Role
) -> None:
    _posture(monkeypatch, "open", authority)
    resp = client.post("/api/v1/auth/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == role.value
    assert body["authority"] == authority
    assert body["token_type"] == "Bearer"
    assert 0 < body["expires_in"] <= int(PREVIEW_TTL.total_seconds())
    grant = manager().verify(body["access_token"], expected_type="access")
    assert grant.role is role
    assert grant.subject == PREVIEW_SUBJECT
    assert is_preview_grant(grant)
    assert body["operator_token_ref"] == grant.token_ref


def test_with_nothing_set_a_preview_grant_is_view_only(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/preview")
    assert resp.status_code == 200
    assert resp.json()["role"] == Role.VIEWER.value


@pytest.mark.parametrize("role", [Role.ENGINEER, Role.ADMIN])
def test_a_preview_grant_never_reaches_engineer(role: Role) -> None:
    with pytest.raises(ValueError, match="ceiling is 'ops'"):
        sign_preview_access(manager(), role)


def test_a_preview_grant_carries_every_sign_in_claim_plus_the_preview_marker() -> None:
    mgr = manager()
    sign_in, _ = mgr.sign_access("ops@example.test", Role.OPS)
    grant, _ = sign_preview_access(mgr, Role.OPS)
    sign_in_claims = mgr.verify(sign_in, expected_type="access").raw_claims
    preview_claims = mgr.verify(grant, expected_type="access").raw_claims
    assert PREVIEW_CLAIM not in sign_in_claims
    assert set(preview_claims) == set(sign_in_claims) | {PREVIEW_CLAIM}
    for name in ("role", "iss", "aud", "type"):
        assert preview_claims[name] == sign_in_claims[name]
    assert preview_claims["sub"] == PREVIEW_SUBJECT
    assert preview_claims[PREVIEW_CLAIM] is True


def test_a_preview_grant_lives_one_hour() -> None:
    assert timedelta(hours=1) == PREVIEW_TTL
    grant, _ = sign_preview_access(manager(), Role.VIEWER)
    claims = manager().verify(grant, expected_type="access").raw_claims
    assert claims["exp"] - claims["iat"] == int(PREVIEW_TTL.total_seconds())


def test_preview_access_is_absent_in_authenticated_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _posture(monkeypatch, "authenticated")
    resp = client.post("/api/v1/auth/preview")
    assert resp.status_code == 404
    assert resp.json()["detail"] == auth.PREVIEW_UNAVAILABLE


# --------------------------------------------------------------------------- #
# Sign-in is dormant in open mode
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("authority", ["view", "act"])
def test_sign_in_is_dormant_in_open_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, authority: str
) -> None:
    _posture(monkeypatch, "open", authority)
    # Not even the insecure development opt-in and a correct development password wake it.
    monkeypatch.setenv(operators.DEV_OPT_IN_ENV, "1")
    admin = "admin@synapse.local"
    resp = client.post(
        "/api/v1/auth/login",
        json={"operator_id": admin, "password": DEV_PASSWORDS[admin]},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == auth.SIGN_IN_DORMANT
    assert "not activated" in auth.SIGN_IN_DORMANT
    assert "set-cookie" not in resp.headers


@pytest.mark.parametrize(
    ("content", "content_type"),
    list(MALFORMED_SIGN_IN_BODIES.values()),
    ids=list(MALFORMED_SIGN_IN_BODIES),
)
def test_in_open_mode_a_malformed_sign_in_body_gets_the_dormant_404_not_a_422(
    client: TestClient, content: bytes, content_type: str
) -> None:
    """The dormancy check is a route dependency, resolved before FastAPI validates the body, so
    open mode never answers with a 422 that names the sign-in fields."""
    resp = client.post(
        "/api/v1/auth/login", content=content, headers={"Content-Type": content_type}
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": auth.SIGN_IN_DORMANT}


def test_refresh_is_dormant_in_open_mode(client: TestClient) -> None:
    sign_in_refresh, _ = manager().sign_refresh("ops@example.test", Role.OPS)
    client.cookies.set("syn_refresh", sign_in_refresh)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 404
    assert resp.json()["detail"] == auth.SIGN_IN_DORMANT


# --------------------------------------------------------------------------- #
# Verification follows the posture
# --------------------------------------------------------------------------- #
def test_activating_authenticated_mode_retires_every_preview_grant(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _posture(monkeypatch, "open", "act")
    token = client.post("/api/v1/auth/preview").json()["access_token"]
    assert client.get("/probe", headers=_bearer(token)).status_code == 200
    monkeypatch.setenv(ACCESS_MODE_ENV, "authenticated")
    assert client.get("/probe", headers=_bearer(token)).status_code == 401
    with pytest.raises(TokenError, match="retired"):
        verify_access_token(token)


def test_lowering_act_to_view_caps_the_ops_grants_already_issued(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _posture(monkeypatch, "open", "act")
    ops_grant = client.post("/api/v1/auth/preview").json()["access_token"]
    monkeypatch.setenv(OPEN_AUTHORITY_ENV, "view")
    view_grant = client.post("/api/v1/auth/preview").json()["access_token"]
    assert client.get("/probe", headers=_bearer(ops_grant)).status_code == 401
    assert client.get("/probe", headers=_bearer(view_grant)).status_code == 200


@pytest.mark.parametrize("mode", ["open", "authenticated"])
def test_a_sign_in_token_verifies_in_either_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    _posture(monkeypatch, mode)
    token, _ = manager().sign_access("ops@example.test", Role.OPS)
    resp = client.get("/probe", headers=_bearer(token))
    assert resp.status_code == 200
    assert resp.json() == {"role": "ops"}


# --------------------------------------------------------------------------- #
# What ships: compose files and the public bundle
# --------------------------------------------------------------------------- #
def _service_block(compose_text: str, service: str) -> str:
    """One top-level compose service, from its key to the next line indented less than 4."""
    lines = compose_text.splitlines()
    start = lines.index(f"  {service}:")
    body: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.lstrip(" ")
        if stripped and len(line) - len(stripped) < 4:
            break
        body.append(line)
    return "\n".join(body)


def _compose_files(directory: Path) -> list[Path]:
    return sorted({path for pattern in COMPOSE_PATTERNS for path in directory.glob(pattern)})


def test_no_compose_file_opts_in_to_the_development_passwords() -> None:
    """Both places compose files live are scanned: the repository root (where
    ``docker-compose.sprint2.yml`` sits) and ``docker/``. Neither scan may come back empty."""
    root_files = _compose_files(REPO_ROOT)
    docker_files = _compose_files(REPO_ROOT / "docker")
    assert root_files, "no compose file found at the repository root"
    assert docker_files, "no compose file found under docker/"
    for path in (*root_files, *docker_files):
        assert operators.DEV_OPT_IN_ENV not in path.read_text(encoding="utf-8"), path.name


def test_the_public_deployment_runs_open_and_view_only() -> None:
    text = (REPO_ROOT / "docker" / "docker-compose.gcp.yml").read_text(encoding="utf-8")
    for service in ("api", "orchestrator"):
        block = _service_block(text, service)
        assert 'SYNAPSE_ACCESS_MODE: "open"' in block, service
        assert 'SYNAPSE_OPEN_AUTHORITY: "view"' in block, service


def test_the_local_stack_runs_open_and_can_act() -> None:
    text = (REPO_ROOT / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    block = _service_block(text, "orchestrator")
    assert "- SYNAPSE_ACCESS_MODE=open" in block
    assert "- SYNAPSE_OPEN_AUTHORITY=act" in block


def test_the_frontend_source_compiles_no_credential_into_the_public_bundle() -> None:
    sources = [
        path
        for path in (REPO_ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".ts", ".tsx", ".json"}
    ]
    assert sources, "no frontend source found to scan"
    assert DEV_PASSWORDS, "no development password to look for"
    markers = (*DEV_PASSWORDS.values(), "env.VITE_AUTO_LOGIN", "readonly VITE_AUTO_LOGIN")
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in sources
        if any(marker in path.read_text(encoding="utf-8") for marker in markers)
    ]
    assert offenders == []
