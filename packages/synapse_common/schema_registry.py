"""SYNAPSE schema registry — runtime JSON-Schema validation at the a2a/Kafka boundary.

Pydantic guards intra-process boundaries. JSON Schema (proto/*.schema.json) guards
the a2a + Kafka boundary. This module loads every domain + a2a schema once at
import time, caches a compiled `Draft7Validator` per schema, and exposes
`validate()` + a `@validates_schema(...)` decorator that wraps any function whose
return value is a payload destined to leave the process.

Architectural rationale: ADR-025. Invariants enforced: I-3 (deterministic JSON +
contract integrity), I-13 (KV-cache friendly payloads — non-conformant payloads
must never reach Kafka or another agent).
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Iterable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

import structlog
from jsonschema import Draft7Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import (  # type: ignore[import-untyped]
    ValidationError as _JsonSchemaValidationError,
)
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

_PROTO_ROOT_ENV = "SYNAPSE_PROTO_ROOT"
_DEFAULT_PROTO_RELATIVE = ("..", "..", "proto")


class SchemaViolation(ValueError):
    """Raised when a payload fails JSON-Schema validation at a process boundary."""

    def __init__(self, schema_name: str, errors: list[str]) -> None:
        self.schema_name = schema_name
        self.errors = errors
        joined = "; ".join(errors)
        super().__init__(f"schema={schema_name} violations=[{joined}]")


def _resolve_proto_root() -> Path:
    """Locate the proto directory. Override via SYNAPSE_PROTO_ROOT env var."""
    import os

    env = os.environ.get(_PROTO_ROOT_ENV)
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    return here.parent.joinpath(*_DEFAULT_PROTO_RELATIVE).resolve()


def _discover_schemas(proto_root: Path) -> Iterable[tuple[str, Path]]:
    """Yield (logical_name, path) for every *.schema.json under proto/.

    Logical names follow the pattern '<namespace>.<bare>' so callers refer to
    schemas by stable identifiers (e.g. 'domain.inventory_action', 'a2a.jsonrpc').
    """
    for path in proto_root.rglob("*.schema.json"):
        rel = path.relative_to(proto_root)
        # rel like 'domain/inventory_action.schema.json' -> 'domain.inventory_action'
        parts = list(rel.parts[:-1])
        bare = rel.parts[-1].removesuffix(".schema.json")
        logical = ".".join([*parts, bare])
        yield logical, path


class SchemaRegistry:
    """Registry of compiled JSON-Schema validators keyed by logical name."""

    def __init__(self, proto_root: Path | None = None) -> None:
        self._proto_root = proto_root or _resolve_proto_root()
        self._validators: dict[str, Draft7Validator] = {}
        self._raw: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        for name, path in _discover_schemas(self._proto_root):
            with path.open("r", encoding="utf-8") as fh:
                raw: dict[str, Any] = json.load(fh)
            Draft7Validator.check_schema(raw)
            self._validators[name] = Draft7Validator(raw)
            self._raw[name] = raw
            # Also register a short alias by bare name when unambiguous.
            bare = name.split(".")[-1]
            if bare not in self._validators or bare == name:
                self._validators[bare] = self._validators[name]
                self._raw[bare] = raw
        logger.info("schema_registry_loaded", count=len(self._raw), root=str(self._proto_root))

    @property
    def names(self) -> list[str]:
        return sorted(self._raw)

    def schema(self, name: str) -> dict[str, Any]:
        if name not in self._raw:
            raise KeyError(f"unknown schema: {name!r} (known={sorted(self._raw)[:8]}…)")
        return self._raw[name]

    def validate(self, payload: dict[str, Any] | BaseModel, schema_name: str) -> None:
        """Validate a payload against the named schema.

        Raises SchemaViolation aggregating every error path. Pydantic models are
        dumped via mode='json' so their serialized form (the form that crosses
        the process boundary) is what gets validated.
        """
        data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        validator = self._validators.get(schema_name)
        if validator is None:
            raise KeyError(f"unknown schema: {schema_name!r}")
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        if errors:
            messages = [_format_error(e) for e in errors]
            raise SchemaViolation(schema_name, messages)


def _format_error(err: _JsonSchemaValidationError) -> str:
    path = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{path}: {err.message}"


_REGISTRY: SchemaRegistry | None = None


def get_registry() -> SchemaRegistry:
    """Process-wide lazy registry. Cheap after first call."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = SchemaRegistry()
    return _REGISTRY


def validate(payload: dict[str, Any] | BaseModel, schema_name: str) -> None:
    """Module-level convenience: validate against the global registry."""
    get_registry().validate(payload, schema_name)


F = TypeVar("F", bound=Callable[..., Any])


def validates_schema(schema_name: str) -> Callable[[F], F]:
    """Decorator: validate a callable's return value against `schema_name`.

    Use on any function that produces a payload destined for the a2a/Kafka
    boundary. Pydantic models, dicts, and lists of either are supported. Other
    return types raise TypeError — be explicit at the boundary.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            _validate_return(result, schema_name)
            return result

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            _validate_return(result, schema_name)
            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return wrapper  # type: ignore[return-value]

    return decorator


def _validate_return(result: Any, schema_name: str) -> None:
    registry = get_registry()
    if isinstance(result, list):
        for i, item in enumerate(result):
            try:
                registry.validate(item, schema_name)
            except SchemaViolation as exc:
                raise SchemaViolation(schema_name, [f"[{i}] {msg}" for msg in exc.errors]) from None
        return
    if isinstance(result, BaseModel | dict):
        registry.validate(result, schema_name)
        return
    raise TypeError(
        f"@validates_schema can only wrap callables returning BaseModel|dict|list[...]; "
        f"got {type(result).__name__}"
    )


__all__ = [
    "SchemaRegistry",
    "SchemaViolation",
    "get_registry",
    "validate",
    "validates_schema",
]
