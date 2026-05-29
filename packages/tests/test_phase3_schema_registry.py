"""Phase 3 — tests for synapse_common.schema_registry (was 0% → goal >85%).

The registry is the I-3 / I-13 boundary gate: every payload crossing a process
edge (Kafka topic, A2A HTTP, or response body) is validated. Mutation-survival
hardening: pin exact error messages, exact registered count, exact derived
names; not just `is not None`.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from synapse_common import schema_registry as sr


# -----------------------------------------------------------------------------
# Fixture: a minimal isolated registry rooted at a tmp proto dir
# -----------------------------------------------------------------------------


@pytest.fixture()
def proto_dir(tmp_path: Path) -> Path:
    """Build a small synthetic proto tree with two schemas in two namespaces."""
    ns_a = tmp_path / "alpha"
    ns_a.mkdir()
    (ns_a / "ping.schema.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "minimum": 0},
                    "msg": {"type": "string"},
                },
                "required": ["n", "msg"],
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )
    ns_b = tmp_path / "beta"
    ns_b.mkdir()
    (ns_b / "pong.schema.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {"value": {"type": "number"}},
                "required": ["value"],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def registry(proto_dir: Path) -> sr.SchemaRegistry:
    return sr.SchemaRegistry(proto_root=proto_dir)


# =============================================================================
# Discovery + load
# =============================================================================


class TestDiscovery:
    def test_logical_names_include_namespace(self, registry: sr.SchemaRegistry) -> None:
        names = registry.names
        assert "alpha.ping" in names
        assert "beta.pong" in names

    def test_short_aliases_registered(self, registry: sr.SchemaRegistry) -> None:
        """Bare names like 'ping' and 'pong' are also registered as aliases."""
        names = registry.names
        assert "ping" in names
        assert "pong" in names

    def test_count_matches_files(self, proto_dir: Path, registry: sr.SchemaRegistry) -> None:
        """Number of files * 2 (namespaced + bare) — minus any collisions."""
        files = list(proto_dir.rglob("*.schema.json"))
        # 2 files, 2 distinct bare names → 4 registered names
        assert len(registry.names) == 2 * len(files)

    def test_schema_round_trip(self, registry: sr.SchemaRegistry) -> None:
        s = registry.schema("alpha.ping")
        assert s["required"] == ["n", "msg"]
        assert "n" in s["properties"]


# =============================================================================
# validate() — happy and sad paths
# =============================================================================


class TestValidateDict:
    def test_valid_payload_passes(self, registry: sr.SchemaRegistry) -> None:
        # Must not raise
        registry.validate({"n": 1, "msg": "hi"}, "alpha.ping")

    def test_missing_required_field_raises_violation(self, registry: sr.SchemaRegistry) -> None:
        with pytest.raises(sr.SchemaViolation) as exc_info:
            registry.validate({"n": 1}, "alpha.ping")
        violation = exc_info.value
        assert violation.schema_name == "alpha.ping"
        # At least one error mentions the missing 'msg' field
        assert any("msg" in err for err in violation.errors), (
            f"Expected an error mentioning 'msg'; got {violation.errors}"
        )

    def test_wrong_type_raises_violation(self, registry: sr.SchemaRegistry) -> None:
        with pytest.raises(sr.SchemaViolation):
            registry.validate({"n": "not_an_int", "msg": "hi"}, "alpha.ping")

    def test_additional_properties_rejected(self, registry: sr.SchemaRegistry) -> None:
        with pytest.raises(sr.SchemaViolation):
            registry.validate({"n": 1, "msg": "hi", "extra": True}, "alpha.ping")

    def test_violation_message_carries_schema_and_errors(
        self, registry: sr.SchemaRegistry
    ) -> None:
        with pytest.raises(sr.SchemaViolation) as exc_info:
            registry.validate({"n": -1, "msg": "hi"}, "alpha.ping")
        msg = str(exc_info.value)
        assert "alpha.ping" in msg
        assert "violations=" in msg

    def test_unknown_schema_raises_keyerror(self, registry: sr.SchemaRegistry) -> None:
        with pytest.raises(KeyError, match="unknown schema"):
            registry.validate({"x": 1}, "not_a_real_schema")

    def test_schema_lookup_unknown_raises(self, registry: sr.SchemaRegistry) -> None:
        with pytest.raises(KeyError):
            registry.schema("nonexistent")


class TestValidatePydantic:
    def test_pydantic_model_dumped_in_json_mode(self, registry: sr.SchemaRegistry) -> None:
        class Ping(BaseModel):
            n: int
            msg: str

        # Must not raise — model_dump(mode='json') gives a dict matching schema
        registry.validate(Ping(n=2, msg="ok"), "alpha.ping")

    def test_pydantic_with_invalid_value_raises(self, registry: sr.SchemaRegistry) -> None:
        class Ping(BaseModel):
            n: int
            msg: str
            extra: bool = True  # extra field rejected by additionalProperties: false

        with pytest.raises(sr.SchemaViolation):
            registry.validate(Ping(n=1, msg="hi"), "alpha.ping")


# =============================================================================
# @validates_schema decorator
# =============================================================================


class TestValidatesSchemaDecoratorSync:
    def test_passes_when_return_valid(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the wrapped function returns a conforming dict, no exception."""
        # Override the module-level registry to use our test proto root
        monkeypatch.setattr(sr, "_REGISTRY", sr.SchemaRegistry(proto_root=proto_dir))

        @sr.validates_schema("alpha.ping")
        def make_ping() -> dict[str, Any]:
            return {"n": 1, "msg": "ok"}

        assert make_ping() == {"n": 1, "msg": "ok"}

    def test_raises_when_return_invalid(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sr, "_REGISTRY", sr.SchemaRegistry(proto_root=proto_dir))

        @sr.validates_schema("alpha.ping")
        def bad_ping() -> dict[str, Any]:
            return {"n": 1}  # missing 'msg'

        with pytest.raises(sr.SchemaViolation):
            bad_ping()

    def test_list_of_dicts_each_validated(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sr, "_REGISTRY", sr.SchemaRegistry(proto_root=proto_dir))

        @sr.validates_schema("alpha.ping")
        def make_pings() -> list[dict[str, Any]]:
            return [{"n": 1, "msg": "a"}, {"n": 2, "msg": "b"}]

        result = make_pings()
        assert len(result) == 2

    def test_list_with_one_invalid_item_raises_with_index(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sr, "_REGISTRY", sr.SchemaRegistry(proto_root=proto_dir))

        @sr.validates_schema("alpha.ping")
        def make_pings() -> list[dict[str, Any]]:
            return [{"n": 1, "msg": "ok"}, {"n": 2}]  # second one invalid

        with pytest.raises(sr.SchemaViolation) as exc_info:
            make_pings()
        # Error message should carry the offending index
        assert any("[1]" in e for e in exc_info.value.errors)

    def test_unsupported_return_type_raises(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sr, "_REGISTRY", sr.SchemaRegistry(proto_root=proto_dir))

        @sr.validates_schema("alpha.ping")
        def make_string() -> str:
            return "not a dict"

        with pytest.raises(TypeError, match="BaseModel|dict|list"):
            make_string()


class TestValidatesSchemaDecoratorAsync:
    def test_async_passes(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sr, "_REGISTRY", sr.SchemaRegistry(proto_root=proto_dir))

        @sr.validates_schema("alpha.ping")
        async def make_ping() -> dict[str, Any]:
            return {"n": 1, "msg": "ok"}

        result = asyncio.run(make_ping())
        assert result == {"n": 1, "msg": "ok"}

    def test_async_raises_on_invalid(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sr, "_REGISTRY", sr.SchemaRegistry(proto_root=proto_dir))

        @sr.validates_schema("alpha.ping")
        async def bad_ping() -> dict[str, Any]:
            return {"n": 1}

        with pytest.raises(sr.SchemaViolation):
            asyncio.run(bad_ping())


# =============================================================================
# Module-level convenience functions + lazy global registry
# =============================================================================


class TestModuleConvenience:
    def test_get_registry_caches(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_registry returns the same instance on repeat calls."""
        monkeypatch.setattr(sr, "_REGISTRY", None)
        monkeypatch.setenv("SYNAPSE_PROTO_ROOT", str(proto_dir))
        r1 = sr.get_registry()
        r2 = sr.get_registry()
        assert r1 is r2

    def test_module_validate_uses_global(
        self, proto_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sr, "_REGISTRY", None)
        monkeypatch.setenv("SYNAPSE_PROTO_ROOT", str(proto_dir))
        # Must not raise
        sr.validate({"n": 1, "msg": "ok"}, "alpha.ping")

    def test_env_var_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SYNAPSE_PROTO_ROOT env var overrides the default discovery path."""
        custom_root = tmp_path / "custom_proto"
        custom_root.mkdir()
        (custom_root / "x.schema.json").write_text(
            json.dumps({"type": "object", "properties": {"y": {"type": "integer"}}, "required": ["y"]}),
            encoding="utf-8",
        )
        monkeypatch.setenv("SYNAPSE_PROTO_ROOT", str(custom_root))
        registry = sr.SchemaRegistry()
        assert "x" in registry.names


# =============================================================================
# SchemaViolation dataclass-like surface
# =============================================================================


class TestSchemaViolation:
    def test_violation_carries_schema_and_errors_attrs(self) -> None:
        v = sr.SchemaViolation("my.schema", ["err1", "err2"])
        assert v.schema_name == "my.schema"
        assert v.errors == ["err1", "err2"]

    def test_violation_str_is_deterministic(self) -> None:
        v = sr.SchemaViolation("s", ["a", "b"])
        # Pin the format so a mutant changing the message format is caught
        assert str(v) == "schema=s violations=[a; b]"
