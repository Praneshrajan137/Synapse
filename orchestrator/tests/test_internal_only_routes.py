"""ADR-057 (finding 89): the orchestrator's writes are internal-only.

``infrastructure/nginx/nginx.gcp.conf`` used to proxy ``/orchestrator/`` on public 443, which
put the anonymous ``POST /api/v1/hitl/{id}/resolve``, ``POST /api/v1/decisions`` and
``POST /a2a`` on the internet. The edge now denies that location, and the orchestrator refuses
an edge-forwarded write itself, so the nginx rule is not the only lock.

The app under test runs without its lifespan, so nothing is initialised: a call the guard
admits reaches its handler and answers 503, which is the proof it was admitted; a refused call
answers 403 before any handler runs.

The nginx tests parse both edge configs into directives and judge what nginx would route, not
substrings. Some of them feed a check a deliberately broken config, so each check is shown
able to fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from api.access import AccessConfigError, AccessMode, OpenAuthority, load_access_settings
from orchestrator.inference import serve

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX = REPO_ROOT / "infrastructure" / "nginx"
#: The two edge configs: the public GCP edge (80 and 443) and the local stack's (80).
NGINX_CONFS = ("nginx.gcp.conf", "nginx.conf")
#: The names that resolve to the orchestrator on the compose network: its service name and its
#: container name, the same in both compose files. If they change, the route list in
#: ``test_every_edge_route_to_the_orchestrator_adds_the_simulated_edge_headers`` empties and
#: that test fails, which is the prompt to update this set.
ORCHESTRATOR_HOSTS = frozenset({"orchestrator", "synapse-orchestrator"})
#: What the edge adds to every call it forwards to the orchestrator. The edge tests below send
#: exactly these; ``test_every_edge_route_to_the_orchestrator_adds_the_simulated_edge_headers``
#: pins them against both nginx configs. Read-only: Starlette's ``websocket_connect`` adds its
#: handshake headers to the dict it is given, so a shared mutable dict would carry them into
#: every later test (measured: the nginx checks then demanded ``sec-websocket-key``).
EDGE: Mapping[str, str] = MappingProxyType(
    {"X-Real-IP": "203.0.113.7", "X-Forwarded-For": "203.0.113.7"}
)
RESOLVE_BODY = {
    "audit_escalation_id": 1,
    "operator_token_ref": "ref-probe",
    "action": "approved",
    "reason": "edge probe",
}
A2A_BODY = {"jsonrpc": "2.0", "id": "1", "method": "execute", "params": {}}
DECISION_BODY = {"order_id": "edge-probe", "store_id": "STORE_BLR_001"}
#: Postures as (SYNAPSE_ACCESS_MODE, SYNAPSE_OPEN_AUTHORITY); None leaves a variable unset.
EVERY_POSTURE = [(None, None), ("open", "view"), ("open", "act"), ("authenticated", None)]


@pytest.fixture()
def client() -> TestClient:
    return TestClient(serve.app)


def _posture(monkeypatch: pytest.MonkeyPatch, mode: str | None, authority: str | None) -> None:
    for name, value in ((serve.ACCESS_MODE_ENV, mode), (serve.OPEN_AUTHORITY_ENV, authority)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def _resolve_path() -> str:
    return f"/api/v1/hitl/{uuid4()}/resolve"


# --------------------------------------------------------------------------- #
# HITL resolve and A2A: internal-only in every posture
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("mode", "authority"), EVERY_POSTURE)
def test_an_edge_forwarded_hitl_resolve_is_refused_in_every_posture(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, mode: str | None, authority: str | None
) -> None:
    _posture(monkeypatch, mode, authority)
    resp = client.post(_resolve_path(), json=RESOLVE_BODY, headers=EDGE)
    assert resp.status_code == 403
    assert "internal-only" in resp.json()["detail"]


@pytest.mark.parametrize(("mode", "authority"), EVERY_POSTURE)
def test_an_edge_forwarded_a2a_call_is_refused_in_every_posture(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, mode: str | None, authority: str | None
) -> None:
    _posture(monkeypatch, mode, authority)
    resp = client.post("/a2a", json=A2A_BODY, headers=EDGE)
    assert resp.status_code == 403
    assert "internal-only" in resp.json()["detail"]


@pytest.mark.parametrize("header", serve.EDGE_FORWARDING_HEADERS)
def test_each_edge_forwarding_header_alone_marks_a_call_as_edge(
    client: TestClient, header: str
) -> None:
    resp = client.post(_resolve_path(), json=RESOLVE_BODY, headers={header: "203.0.113.7"})
    assert resp.status_code == 403


def test_the_gateways_hitl_notification_reaches_its_handler(client: TestClient) -> None:
    resp = client.post(_resolve_path(), json=RESOLVE_BODY)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "HITL not initialised"


def test_an_internal_a2a_call_reaches_its_handler(client: TestClient) -> None:
    resp = client.post("/a2a", json=A2A_BODY)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Handler not initialised"


# --------------------------------------------------------------------------- #
# The decision trigger: internal, or edge only in the local open + act posture
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("mode", "authority"), EVERY_POSTURE)
def test_an_internal_decision_trigger_reaches_its_handler_in_every_posture(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, mode: str | None, authority: str | None
) -> None:
    """The traffic generator, the deploy probe and the gateway's OPS route call it this way."""
    _posture(monkeypatch, mode, authority)
    resp = client.post("/api/v1/decisions", json=DECISION_BODY)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Protocol not initialised"


@pytest.mark.parametrize(
    ("mode", "authority", "expected"),
    [
        (None, None, 403),
        ("open", "view", 403),
        ("authenticated", None, 403),
        ("authenticated", "act", 403),
        ("open", "act", 503),
    ],
)
def test_an_edge_forwarded_decision_trigger_needs_open_and_act(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    mode: str | None,
    authority: str | None,
    expected: int,
) -> None:
    _posture(monkeypatch, mode, authority)
    resp = client.post("/api/v1/decisions", json=DECISION_BODY, headers=EDGE)
    assert resp.status_code == expected


# --------------------------------------------------------------------------- #
# The escalation WebSocket: an edge connection is listen-only
# --------------------------------------------------------------------------- #
class _RecordingHitl:
    def __init__(self) -> None:
        self.responses: list[tuple[UUID, dict[str, Any]]] = []

    async def receive_human_response(self, decision_id: UUID, response: dict[str, Any]) -> None:
        self.responses.append((decision_id, response))


def _send_response(client: TestClient, headers: Mapping[str, str]) -> None:
    message = {"decision_id": str(uuid4()), "response": {"action": "approved"}}
    # A copy: websocket_connect writes its handshake headers into the dict it receives.
    with client.websocket_connect("/ws/escalation", headers=dict(headers)) as ws:
        ws.send_json(message)


def test_an_edge_websocket_cannot_resolve_an_escalation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _RecordingHitl()
    monkeypatch.setattr(serve, "_hitl", recorder)
    _send_response(client, EDGE)
    assert recorder.responses == []


def test_an_internal_websocket_still_delivers_a_human_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _RecordingHitl()
    monkeypatch.setattr(serve, "_hitl", recorder)
    _send_response(client, {})
    assert len(recorder.responses) == 1
    assert recorder.responses[0][1] == {"action": "approved"}


# --------------------------------------------------------------------------- #
# The settings agree with the gateway's, and a bad one refuses startup
# --------------------------------------------------------------------------- #
ADMITTED_SETTINGS = [
    {},
    {"SYNAPSE_ACCESS_MODE": "open"},
    {"SYNAPSE_OPEN_AUTHORITY": "act"},
    {"SYNAPSE_ACCESS_MODE": "open", "SYNAPSE_OPEN_AUTHORITY": "view"},
    {"SYNAPSE_ACCESS_MODE": "open", "SYNAPSE_OPEN_AUTHORITY": "act"},
    {"SYNAPSE_ACCESS_MODE": "authenticated"},
    {"SYNAPSE_ACCESS_MODE": "authenticated", "SYNAPSE_OPEN_AUTHORITY": "act"},
    {"SYNAPSE_ACCESS_MODE": "authenticated", "SYNAPSE_OPEN_AUTHORITY": "stale"},
]
REFUSED_SETTINGS = [
    {"SYNAPSE_ACCESS_MODE": "public"},
    {"SYNAPSE_ACCESS_MODE": ""},
    {"SYNAPSE_ACCESS_MODE": "OPEN"},
    {"SYNAPSE_OPEN_AUTHORITY": "admin"},
    {"SYNAPSE_ACCESS_MODE": "open", "SYNAPSE_OPEN_AUTHORITY": ""},
]


@pytest.mark.parametrize("environ", ADMITTED_SETTINGS)
def test_the_orchestrator_reads_the_access_settings_as_the_gateway_does(
    environ: dict[str, str],
) -> None:
    settings = load_access_settings(environ)
    gateway_says_act = settings.mode is AccessMode.OPEN and settings.authority is OpenAuthority.ACT
    assert serve.edge_may_trigger_decisions(environ) is gateway_says_act


@pytest.mark.parametrize("environ", REFUSED_SETTINGS)
def test_a_setting_the_gateway_refuses_also_refuses_orchestrator_startup(
    environ: dict[str, str],
) -> None:
    with pytest.raises(AccessConfigError):
        load_access_settings(environ)
    with pytest.raises(RuntimeError, match="Refusing to start"):
        serve.edge_may_trigger_decisions(environ)


# --------------------------------------------------------------------------- #
# The nginx rule, which the guard above backs up. Each config is parsed into
# directives, so a check judges what nginx would route rather than a substring.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Directive:
    """One nginx directive: ``name args;``, or ``name args { ... }`` with its ``block``."""

    name: str
    args: tuple[str, ...]
    block: tuple[Directive, ...] | None

    def inside(self) -> tuple[Directive, ...]:
        """The directives this one's block holds; none for a simple statement."""
        return self.block or ()


@dataclass(frozen=True)
class ProxyHop:
    """One ``proxy_pass``: the location it serves, its target, and the headers nginx sets."""

    location: str
    target: str
    headers: frozenset[str]

    @property
    def host(self) -> str:
        """The target's host, without scheme, path or port, lower-cased."""
        return _without_port(self.target.split("://", 1)[-1].split("/", 1)[0])


def _without_port(address: str) -> str:
    host, colon, port = address.rpartition(":")
    return (host if colon and port.isdigit() else address).lower()


def _tokens(text: str) -> list[str]:
    """nginx's lexical units: words, quoted strings without their quotes, ``{``, ``}``, ``;``.

    As in nginx, ``#`` opens a comment and a quote opens a string only where a token starts,
    and a word ends at whitespace, ``;`` or ``{``, except the ``{`` of ``${name}``.
    """
    tokens: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char.isspace():
            i += 1
        elif char == "#":
            newline = text.find("\n", i)
            i = len(text) if newline == -1 else newline
        elif char in "{};":
            tokens.append(char)
            i += 1
        elif char in "\"'":
            end = i + 1
            while end < len(text) and text[end] != char:
                end += 2 if text[end] == "\\" else 1
            assert end < len(text), f"an unterminated {char} string"
            tokens.append(text[i + 1 : end])
            i = end + 1
        else:
            start = i
            while i < len(text) and not text[i].isspace() and text[i] not in ";{":
                i += 2 if text.startswith("${", i) else 1
            tokens.append(text[start:i])
    return tokens


def _parse(tokens: list[str], start: int, nested: bool) -> tuple[tuple[Directive, ...], int]:
    """The directives from ``start`` to the matching ``}`` (``nested``) or the end."""
    directives: list[Directive] = []
    words: list[str] = []
    i = start
    while i < len(tokens):
        token = tokens[i]
        if token == "}":
            assert nested and not words, f"an unexpected closing brace at token {i}"
            return tuple(directives), i + 1
        if token == ";":
            assert words, f"an empty statement at token {i}"
            directives.append(Directive(words[0], tuple(words[1:]), None))
            words = []
            i += 1
        elif token == "{":
            assert words, f"a block with no directive name at token {i}"
            block, i = _parse(tokens, i + 1, nested=True)
            directives.append(Directive(words[0], tuple(words[1:]), block))
            words = []
        else:
            words.append(token)
            i += 1
    assert not nested and not words, "the config ends inside a block or a statement"
    return tuple(directives), i


def _parse_conf(text: str) -> tuple[Directive, ...]:
    directives, _ = _parse(_tokens(text), 0, nested=False)
    return directives


def _conf(conf_name: str) -> tuple[Directive, ...]:
    return _parse_conf((NGINX / conf_name).read_text(encoding="utf-8"))


def _walk(directives: tuple[Directive, ...]) -> Iterator[Directive]:
    """Every directive, depth first, the ones inside nested blocks included."""
    for directive in directives:
        yield directive
        yield from _walk(directive.inside())


def _locations(conf: tuple[Directive, ...], prefix: str) -> list[Directive]:
    """Every ``location`` for ``prefix``, at any depth and with any modifier."""
    return [d for d in _walk(conf) if d.name == "location" and d.args[-1:] == (prefix,)]


def _http(conf: tuple[Directive, ...]) -> Directive:
    blocks = [d for d in conf if d.name == "http"]
    assert len(blocks) == 1, f"expected one http block, found {len(blocks)}"
    return blocks[0]


def _upstreams(conf: tuple[Directive, ...]) -> dict[str, frozenset[str]]:
    """Each ``upstream`` group's name and the hosts of its ``server`` lines."""
    groups = [d for d in _http(conf).inside() if d.name == "upstream"]
    return {
        group.args[0].lower(): frozenset(
            _without_port(line.args[0]) for line in group.inside() if line.name == "server"
        )
        for group in groups
    }


def _set_headers(level: tuple[Directive, ...]) -> frozenset[str] | None:
    """The header names one level sets to a non-empty value; ``None`` if it sets none.

    nginx inherits ``proxy_set_header`` from the enclosing level only when a level declares
    none of its own, and it does not send a header whose value is empty.
    """
    declared = [d for d in level if d.name == "proxy_set_header"]
    if not declared:
        return None
    return frozenset(d.args[0].lower() for d in declared if d.args[1:] != ("",))


def _collect_hops(
    level: tuple[Directive, ...], where: str, inherited: frozenset[str], hops: list[ProxyHop]
) -> None:
    own = _set_headers(level)
    headers = inherited if own is None else own
    for directive in level:
        if directive.name == "proxy_pass":
            hops.append(ProxyHop(where, directive.args[0], headers))
        elif directive.block is not None:
            label = " ".join(directive.args) if directive.name == "location" else where
            _collect_hops(directive.block, label, headers, hops)


def _proxy_hops(conf: tuple[Directive, ...]) -> list[ProxyHop]:
    """Every ``proxy_pass`` in every server, with the headers nginx sets on that hop."""
    http = _http(conf)
    inherited: frozenset[str] = _set_headers(http.inside()) or frozenset()
    hops: list[ProxyHop] = []
    for server in (d for d in http.inside() if d.name == "server"):
        _collect_hops(server.inside(), "server", inherited, hops)
    return hops


def _reaches_the_orchestrator(hop: ProxyHop, upstreams: dict[str, frozenset[str]]) -> bool:
    """Whether the hop's target, or the upstream group it names, is the orchestrator."""
    return bool(upstreams.get(hop.host, frozenset({hop.host})) & ORCHESTRATOR_HOSTS)


def _routes_to_the_orchestrator(conf: tuple[Directive, ...]) -> list[ProxyHop]:
    upstreams = _upstreams(conf)
    return [hop for hop in _proxy_hops(conf) if _reaches_the_orchestrator(hop, upstreams)]


def _edge_header_gaps(conf: tuple[Directive, ...]) -> list[str]:
    """Each route to the orchestrator that does not set every header ``EDGE`` simulates."""
    simulated = {name.lower() for name in EDGE}
    return [
        f"location {hop.location} does not set {sorted(simulated - hop.headers)}"
        for hop in _routes_to_the_orchestrator(conf)
        if not simulated <= hop.headers
    ]


def _public_edge_violations(conf: tuple[Directive, ...]) -> list[str]:
    """Why a location in ``conf`` could reach the orchestrator; empty when none can.

    Every target must name a declared upstream, so the check knows where each hop goes: a
    bare host, an address or a variable is refused rather than guessed at.
    """
    upstreams = _upstreams(conf)
    violations: list[str] = []
    for hop in _proxy_hops(conf):
        if _reaches_the_orchestrator(hop, upstreams):
            reason = "reaches the orchestrator"
        elif hop.host not in upstreams:
            reason = "names no declared upstream"
        else:
            continue
        violations.append(f"location {hop.location}: proxy_pass {hop.target} {reason}")
    return violations


def _marks_an_edge_hop(header: str) -> bool:
    """X-Real-IP, Forwarded and every X-Forwarded-*: what a proxy adds when it forwards."""
    name = header.lower()
    return name in {"x-real-ip", "forwarded"} or name.startswith("x-forwarded-")


def _refuses_everyone(location: Directive) -> bool:
    """Whether nginx answers every request to ``location`` with 403 and proxies none.

    nginx runs a ``return`` before it applies ``allow`` and ``deny``, and applies those in
    order, so the first ``return`` must be 403 or, with none, the first rule ``deny all``.
    """
    body = location.inside()
    if any(d.name == "proxy_pass" for d in _walk(body)):
        return False
    returns = [d for d in body if d.name == "return"]
    if returns:
        return returns[0].args[:1] == ("403",)
    rules = [d for d in body if d.name in {"allow", "deny"}]
    return bool(rules) and rules[0].name == "deny" and rules[0].args == ("all",)


def test_the_edge_header_list_names_what_nginx_sets() -> None:
    """Every edge-marking header either nginx config sets is one the guard refuses on."""
    marking = {
        directive.args[0].lower()
        for conf_name in NGINX_CONFS
        for directive in _walk(_conf(conf_name))
        if directive.name == "proxy_set_header" and _marks_an_edge_hop(directive.args[0])
    }
    assert marking, "neither nginx config sets an edge-marking header"
    assert marking - set(serve.EDGE_FORWARDING_HEADERS) == set()


def test_every_edge_route_to_the_orchestrator_adds_the_simulated_edge_headers() -> None:
    """nginx adds ``EDGE``'s headers on every route that reaches the orchestrator.

    Without them an edge call would look internal and pass the guard, and the edge tests
    above would simulate a call nginx never makes. Deleting the ``X-Real-IP`` line from
    either orchestrator location in ``nginx.conf`` fails this test.
    """
    confs = [_conf(conf_name) for conf_name in NGINX_CONFS]
    routes = [hop for conf in confs for hop in _routes_to_the_orchestrator(conf)]
    assert routes, "no edge route reaches the orchestrator: is ORCHESTRATOR_HOSTS stale?"
    assert [gap for conf in confs for gap in _edge_header_gaps(conf)] == []


def test_the_header_check_catches_a_route_that_stops_marking_edge_calls() -> None:
    text = (NGINX / "nginx.conf").read_text(encoding="utf-8")
    line = "proxy_set_header X-Real-IP $remote_addr;"
    assert line in text
    gaps = _edge_header_gaps(_parse_conf(text.replace(line, "", 1)))
    assert len(gaps) == 1
    assert "x-real-ip" in gaps[0]


@pytest.mark.parametrize("conf_name", NGINX_CONFS)
def test_the_edge_denies_the_orchestrator_location(conf_name: str) -> None:
    locations = _locations(_conf(conf_name), "/orchestrator/")
    assert locations, f"{conf_name} declares no location /orchestrator/"
    assert all(_refuses_everyone(location) for location in locations)


def test_the_local_edge_denies_hitl_resolution() -> None:
    locations = _locations(_conf("nginx.conf"), "/api/v1/hitl/")
    assert locations, "nginx.conf declares no location /api/v1/hitl/"
    assert all(_refuses_everyone(location) for location in locations)


@pytest.mark.parametrize(
    ("body", "refuses"),
    [
        ("deny all;", True),
        ("return 403;", True),
        ("allow 157.51.0.0/16; deny all;", False),
        ("deny all; proxy_pass http://orchestrator;", False),
        ("deny all; return 200;", False),
        ("", False),
    ],
)
def test_only_a_location_that_admits_nobody_counts_as_a_refusal(body: str, refuses: bool) -> None:
    (location,) = _parse_conf(f"location /orchestrator/ {{ {body} }}")
    assert location.name == "location"
    assert _refuses_everyone(location) is refuses


def test_the_public_edge_proxies_nothing_to_the_orchestrator() -> None:
    conf = _conf("nginx.gcp.conf")
    hops = _proxy_hops(conf)
    assert any(hop.location == "/api/" and hop.host == "api" for hop in hops), hops
    assert _public_edge_violations(conf) == []


@pytest.mark.parametrize("target", ["http://synapse-orchestrator:8085", "http://orchestrator"])
def test_the_public_edge_check_catches_a_location_that_proxies_to_the_orchestrator(
    target: str,
) -> None:
    """The old substring check let ``proxy_pass http://synapse-orchestrator:8085;`` pass."""
    text = (NGINX / "nginx.gcp.conf").read_text(encoding="utf-8")
    anchor = "proxy_pass http://frontend;"
    assert text.count(anchor) == 1
    mutated = text.replace(anchor, f"proxy_pass {target};")
    violations = _public_edge_violations(_parse_conf(mutated))
    assert len(violations) == 1
    assert "reaches the orchestrator" in violations[0]
