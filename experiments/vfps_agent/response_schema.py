"""Canonical, permission-specific response schemas for CAP-ACT arms.

The schemas in this module constrain provider output before the strict CAP-ACT
verifier runs.  They deliberately do not replace the verifier: JSON Schema
cannot express every cross-record or numerical invariant enforced there.

This module is side-effect free and provider independent.  In particular, it
does not import :mod:`ark_provider`; the same frozen schema and hash can be
bound by any transport implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .actions import (
    Action,
    ActionSpace,
    BaseOperator,
    TransformOperator,
    build_if1_predicate_fixture,
)
from .canonical import (
    StrictJSONError,
    canonical_bytes,
    canonical_sha256,
    strict_json_loads,
    to_primitive,
)
from .contracts import (
    ArmId,
    FROZEN_ARM_SPECS,
    PacketKind,
    ResponsePermission,
)
from .registry import CAPActionRegistry, ForecastStatus
from .verifier import (
    ACTION_RESPONSE_SCHEMA_VERSION,
    DIRECT_RESPONSE_SCHEMA_VERSION,
    IF_RESPONSE_SCHEMA_VERSION,
    ActionAuthority,
)


RESPONSE_SCHEMA_REGISTRY_VERSION = "CAPResponseSchemaRegistry.v1"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$schema",
        "type",
        "const",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minimum",
        "maximum",
        "oneOf",
    }
)
_JSON_TYPES = frozenset(
    {"object", "array", "string", "number", "integer", "boolean", "null"}
)


class ResponseSchemaError(ValueError):
    """Base class for closed response-schema failures."""


class ResponseSchemaDefinitionError(ResponseSchemaError):
    """A schema is outside the deliberately small local dialect."""


class ResponseSchemaValidationError(ResponseSchemaError):
    """A response instance does not satisfy its canonical arm schema."""


class ResponseParserKind(str, Enum):
    NONE = "none"
    DIRECT = "direct"
    ACTION_SELECTION = "action_selection"
    IF_REPRESENTATION = "if_representation"


@dataclass(frozen=True, slots=True)
class _PermissionDescriptor:
    parser_kind: ResponseParserKind
    schema_version: str | None
    action_authority: ActionAuthority | None
    action_space: ActionSpace | None


# This is intentionally permission-level rather than another arm-level table.
# Arm ownership remains exclusively in contracts.FROZEN_ARM_SPECS.
_PERMISSION_DESCRIPTORS: Mapping[ResponsePermission, _PermissionDescriptor] = (
    MappingProxyType(
        {
            ResponsePermission.NONE: _PermissionDescriptor(
                ResponseParserKind.NONE, None, None, None
            ),
            ResponsePermission.DIRECT_BUNDLE: _PermissionDescriptor(
                ResponseParserKind.DIRECT,
                DIRECT_RESPONSE_SCHEMA_VERSION,
                None,
                None,
            ),
            ResponsePermission.EMIT_ONLY: _PermissionDescriptor(
                ResponseParserKind.ACTION_SELECTION,
                ACTION_RESPONSE_SCHEMA_VERSION,
                ActionAuthority.H1,
                ActionSpace.PRIMARY19,
            ),
            ResponsePermission.FUSE_ONLY: _PermissionDescriptor(
                ResponseParserKind.ACTION_SELECTION,
                ACTION_RESPONSE_SCHEMA_VERSION,
                ActionAuthority.RF1,
                ActionSpace.PRIMARY19,
            ),
            ResponsePermission.CHAMPION_CORRECTION: _PermissionDescriptor(
                ResponseParserKind.ACTION_SELECTION,
                ACTION_RESPONSE_SCHEMA_VERSION,
                ActionAuthority.RC1,
                ActionSpace.PRIMARY19,
            ),
            ResponsePermission.PRIMARY_ACTION: _PermissionDescriptor(
                ResponseParserKind.ACTION_SELECTION,
                ACTION_RESPONSE_SCHEMA_VERSION,
                ActionAuthority.ACT1,
                ActionSpace.PRIMARY19,
            ),
            ResponsePermission.IF_REPRESENTATION: _PermissionDescriptor(
                ResponseParserKind.IF_REPRESENTATION,
                IF_RESPONSE_SCHEMA_VERSION,
                ActionAuthority.ACT1,
                ActionSpace.PRIMARY19,
            ),
            ResponsePermission.COMPOSITIONAL_ACTION: _PermissionDescriptor(
                ResponseParserKind.ACTION_SELECTION,
                ACTION_RESPONSE_SCHEMA_VERSION,
                ActionAuthority.ACT_COMP96,
                ActionSpace.COMPOSITIONAL96,
            ),
        }
    )
)


def _require_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _freeze_json(value: Any) -> Any:
    primitive = to_primitive(value)

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(primitive)


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):  # pragma: no cover - defensive typing boundary
        raise TypeError("response schema must be a mapping")
    return frozen


def _schema_definition_error() -> ResponseSchemaDefinitionError:
    return ResponseSchemaDefinitionError("unsupported or invalid canonical response schema")


def _is_finite_json_number(value: Any) -> bool:
    """Classify JSON numbers without coercing unbounded integers to float."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return isinstance(value, int) or math.isfinite(value)


def validate_schema_definition(
    schema: Mapping[str, Any],
    *,
    _depth: int = 0,
    _root: bool = True,
) -> None:
    """Validate the closed JSON-Schema subset emitted by this module."""

    if _depth > 32 or not isinstance(schema, Mapping):
        raise _schema_definition_error()
    if not set(schema).issubset(_SUPPORTED_SCHEMA_KEYS):
        raise _schema_definition_error()
    if "$schema" in schema:
        if not _root or schema["$schema"] != JSON_SCHEMA_DIALECT:
            raise _schema_definition_error()

    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in _JSON_TYPES:
        raise _schema_definition_error()
    if schema_type is None and not set(schema) & {"const", "enum", "oneOf"}:
        raise _schema_definition_error()

    object_keys = {"properties", "required", "additionalProperties"}
    array_keys = {"items", "minItems", "maxItems", "uniqueItems"}
    numeric_keys = {"minimum", "maximum"}
    if set(schema) & object_keys and schema_type != "object":
        raise _schema_definition_error()
    if set(schema) & array_keys and schema_type != "array":
        raise _schema_definition_error()
    if set(schema) & numeric_keys and schema_type not in {"number", "integer"}:
        raise _schema_definition_error()

    if schema_type == "object":
        properties = schema.get("properties")
        required = schema.get("required")
        if (
            not isinstance(properties, Mapping)
            or schema.get("additionalProperties") is not False
            or not isinstance(required, (list, tuple))
            or isinstance(required, (str, bytes))
            or any(not isinstance(item, str) for item in required)
            or len(required) != len(set(required))
            or set(required) != set(properties)
        ):
            raise _schema_definition_error()
        for child in properties.values():
            validate_schema_definition(child, _depth=_depth + 1, _root=False)

    if schema_type == "array":
        items = schema.get("items")
        if not isinstance(items, Mapping):
            raise _schema_definition_error()
        validate_schema_definition(items, _depth=_depth + 1, _root=False)
        for name in ("minItems", "maxItems"):
            if name in schema and (
                isinstance(schema[name], bool)
                or not isinstance(schema[name], int)
                or schema[name] < 0
            ):
                raise _schema_definition_error()
        if (
            "minItems" in schema
            and "maxItems" in schema
            and schema["minItems"] > schema["maxItems"]
        ):
            raise _schema_definition_error()
        if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
            raise _schema_definition_error()

    for name in ("minimum", "maximum"):
        if name in schema:
            value = schema[name]
            if not _is_finite_json_number(value):
                raise _schema_definition_error()
    if (
        "minimum" in schema
        and "maximum" in schema
        and schema["minimum"] > schema["maximum"]
    ):
        raise _schema_definition_error()

    for name in ("const",):
        if name in schema:
            try:
                canonical_bytes(schema[name])
            except (StrictJSONError, TypeError, ValueError) as exc:
                raise _schema_definition_error() from exc
    if "enum" in schema:
        values = schema["enum"]
        if (
            not isinstance(values, (list, tuple))
            or isinstance(values, (str, bytes))
            or not values
        ):
            raise _schema_definition_error()
        try:
            fingerprints = tuple(canonical_bytes(item) for item in values)
        except (StrictJSONError, TypeError, ValueError) as exc:
            raise _schema_definition_error() from exc
        if len(fingerprints) != len(set(fingerprints)):
            raise _schema_definition_error()

    if "oneOf" in schema:
        branches = schema["oneOf"]
        if (
            not isinstance(branches, (list, tuple))
            or isinstance(branches, (str, bytes))
            or not branches
        ):
            raise _schema_definition_error()
        for branch in branches:
            validate_schema_definition(branch, _depth=_depth + 1, _root=False)


def _json_equal(left: Any, right: Any) -> bool:
    try:
        return canonical_bytes(left) == canonical_bytes(right)
    except (StrictJSONError, TypeError, ValueError):
        return False


def _instance_error() -> ResponseSchemaValidationError:
    return ResponseSchemaValidationError("response does not satisfy the canonical arm schema")


def _validate_instance(value: Any, schema: Mapping[str, Any], *, depth: int = 0) -> None:
    if depth > 32:
        raise _instance_error()
    schema_type = schema.get("type")
    type_ok = {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)),
        "string": isinstance(value, str),
        "number": _is_finite_json_number(value),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if schema_type is not None and not type_ok[schema_type]:
        raise _instance_error()
    if "const" in schema and not _json_equal(value, schema["const"]):
        raise _instance_error()
    if "enum" in schema and not any(_json_equal(value, item) for item in schema["enum"]):
        raise _instance_error()

    if schema_type == "object":
        assert isinstance(value, Mapping)
        properties = schema["properties"]
        if set(value) != set(schema["required"]):
            raise _instance_error()
        for key, child in value.items():
            if key not in properties:
                raise _instance_error()
            _validate_instance(child, properties[key], depth=depth + 1)

    if schema_type == "array":
        assert isinstance(value, (list, tuple))
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise _instance_error()
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise _instance_error()
        if schema.get("uniqueItems") is True:
            try:
                fingerprints = tuple(canonical_bytes(item) for item in value)
            except (StrictJSONError, TypeError, ValueError) as exc:
                raise _instance_error() from exc
            if len(fingerprints) != len(set(fingerprints)):
                raise _instance_error()
        for item in value:
            _validate_instance(item, schema["items"], depth=depth + 1)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not _is_finite_json_number(value):
            raise _instance_error()
        if "minimum" in schema and value < schema["minimum"]:
            raise _instance_error()
        if "maximum" in schema and value > schema["maximum"]:
            raise _instance_error()

    if "oneOf" in schema:
        matches = 0
        for branch in schema["oneOf"]:
            try:
                _validate_instance(value, branch, depth=depth + 1)
                matches += 1
            except ResponseSchemaValidationError:
                pass
        if matches != 1:
            raise _instance_error()


def validate_schema_instance(value: Any, schema: Mapping[str, Any]) -> Any:
    """Validate one JSON-compatible value against the closed local dialect.

    The returned value is detached into ordinary JSON-compatible containers.
    Provider text should normally use :func:`validate_response_payload`, which
    additionally applies duplicate-key and non-finite-number rejection.
    """

    validate_schema_definition(schema)
    try:
        primitive = to_primitive(value)
    except (StrictJSONError, TypeError, ValueError) as exc:
        raise _instance_error() from exc
    _validate_instance(primitive, schema)
    return primitive


@dataclass(frozen=True, slots=True)
class ArmResponseSchemaSpec:
    """Immutable response authority derived from one frozen arm permission."""

    arm_id: ArmId
    packet_kind: PacketKind | None
    permission: ResponsePermission
    physical_calls: int
    parser_kind: ResponseParserKind
    schema_version: str | None
    action_authority: ActionAuthority | None
    action_space: ActionSpace | None
    planned_key_tokens: tuple[str, ...]
    allowed_action_ids_by_key: tuple[tuple[str, tuple[str, ...]], ...]
    response_schema: Mapping[str, Any] | None
    action_manifest_hash: str
    numerical_registry_hash: str
    feature_registry_hash: str
    predicate_manifest_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.arm_id, ArmId):
            raise TypeError("arm_id must be ArmId")
        frozen_arm = FROZEN_ARM_SPECS[self.arm_id]
        if (
            self.packet_kind is not frozen_arm.packet_kind
            or self.permission is not frozen_arm.permission
            or self.physical_calls != frozen_arm.physical_calls
        ):
            raise ValueError("response spec differs from FROZEN_ARM_SPECS authority")
        descriptor = _PERMISSION_DESCRIPTORS[self.permission]
        if (
            self.parser_kind is not descriptor.parser_kind
            or self.schema_version != descriptor.schema_version
            or self.action_authority is not descriptor.action_authority
            or self.action_space is not descriptor.action_space
        ):
            raise ValueError("response spec differs from permission descriptor")
        for name in (
            "action_manifest_hash",
            "numerical_registry_hash",
            "feature_registry_hash",
        ):
            _require_sha256(getattr(self, name), name)
        if self.predicate_manifest_hash is not None:
            _require_sha256(self.predicate_manifest_hash, "predicate_manifest_hash")

        planned = tuple(self.planned_key_tokens)
        if not planned or len(planned) != len(set(planned)) or planned != tuple(sorted(planned)):
            raise ValueError("planned keys must be non-empty, unique, and canonical")
        object.__setattr__(self, "planned_key_tokens", planned)

        allowed = tuple(
            (key, tuple(action_ids))
            for key, action_ids in self.allowed_action_ids_by_key
        )
        allowed_keys = tuple(key for key, _ in allowed)
        if len(allowed_keys) != len(set(allowed_keys)) or allowed_keys != tuple(sorted(allowed_keys)):
            raise ValueError("allowed action keys must be unique and canonical")
        for _, action_ids in allowed:
            if (
                not action_ids
                or len(action_ids) != len(set(action_ids))
                or action_ids != tuple(sorted(action_ids))
            ):
                raise ValueError("allowed action IDs must be non-empty, unique, and canonical")
            for action_id in action_ids:
                _require_sha256(action_id, "action_id")
        object.__setattr__(self, "allowed_action_ids_by_key", allowed)

        is_action_response = self.action_space is not None
        if is_action_response and allowed_keys != planned:
            raise ValueError("action schemas must bind every planned key")
        if not is_action_response and allowed:
            raise ValueError("non-action schemas cannot carry action authority")

        if self.parser_kind is ResponseParserKind.NONE:
            if self.response_schema is not None or self.schema_version is not None:
                raise ValueError("local-only arms cannot carry a response schema")
            if self.physical_calls != 0:
                raise ValueError("no-response permission must be local-only")
        else:
            if self.response_schema is None or self.schema_version is None:
                raise ValueError("physical arms require a response schema and version")
            frozen_schema = _freeze_mapping(self.response_schema)
            validate_schema_definition(frozen_schema)
            try:
                version = frozen_schema["properties"]["schema_version"]["const"]
            except (KeyError, TypeError) as exc:
                raise ValueError("response schema lacks an exact schema version") from exc
            if version != self.schema_version:
                raise ValueError("response schema version differs from typed spec")
            object.__setattr__(self, "response_schema", frozen_schema)

        if self.parser_kind is ResponseParserKind.IF_REPRESENTATION:
            if self.predicate_manifest_hash is None:
                raise ValueError("IF1 requires a predicate manifest hash")
        elif self.predicate_manifest_hash is not None:
            raise ValueError("only IF1 may bind a predicate manifest")

    @property
    def allowed_action_ids(self) -> Mapping[str, tuple[str, ...]]:
        return MappingProxyType(dict(self.allowed_action_ids_by_key))

    @property
    def json_schema(self) -> Mapping[str, Any] | None:
        return self.response_schema

    @property
    def response_schema_hash(self) -> str | None:
        if self.response_schema is None:
            return None
        return canonical_sha256(self.response_schema)

    @property
    def schema_hash(self) -> str | None:
        return self.response_schema_hash

    @property
    def planned_keys_hash(self) -> str:
        return canonical_sha256(
            {
                "schema_version": "CAPPlannedResponseKeys.v1",
                "keys": list(self.planned_key_tokens),
            }
        )

    @property
    def allowed_action_ids_hash(self) -> str | None:
        if not self.allowed_action_ids_by_key:
            return None
        return canonical_sha256(
            {
                "schema_version": "CAPAllowedResponseActions.v1",
                "by_key": [
                    {"key": key, "action_ids": list(action_ids)}
                    for key, action_ids in self.allowed_action_ids_by_key
                ],
            }
        )

    @property
    def certificate_action_space(self) -> str | None:
        if self.parser_kind is ResponseParserKind.DIRECT:
            return "DIRECT_NUMERIC"
        if self.action_space is not None:
            return self.action_space.value
        return None

    def manifest_payload(self) -> Mapping[str, Any]:
        return {
            "schema_version": "CAPArmResponseSchemaSpec.v1",
            "response_schema_registry_version": RESPONSE_SCHEMA_REGISTRY_VERSION,
            "arm_id": self.arm_id.value,
            "packet_kind": self.packet_kind.value if self.packet_kind is not None else None,
            "permission": self.permission.value,
            "physical_calls": self.physical_calls,
            "parser_kind": self.parser_kind.value,
            "response_schema_version": self.schema_version,
            "action_authority": (
                self.action_authority.value if self.action_authority is not None else None
            ),
            "action_space": self.action_space.value if self.action_space is not None else None,
            "certificate_action_space": self.certificate_action_space,
            "response_schema_hash": self.response_schema_hash,
            "planned_keys_hash": self.planned_keys_hash,
            "allowed_action_ids_hash": self.allowed_action_ids_hash,
            "action_manifest_hash": self.action_manifest_hash,
            "numerical_registry_hash": self.numerical_registry_hash,
            "feature_registry_hash": self.feature_registry_hash,
            "predicate_manifest_hash": self.predicate_manifest_hash,
        }

    @property
    def spec_manifest_hash(self) -> str:
        return canonical_sha256(self.manifest_payload())

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ArmResponseSchemaSpec":
        """Rebuild and byte-check a persisted typed arm schema spec."""

        expected = {
            "arm_id",
            "packet_kind",
            "permission",
            "physical_calls",
            "parser_kind",
            "schema_version",
            "action_authority",
            "action_space",
            "planned_key_tokens",
            "allowed_action_ids_by_key",
            "response_schema",
            "action_manifest_hash",
            "numerical_registry_hash",
            "feature_registry_hash",
            "predicate_manifest_hash",
        }
        if not isinstance(payload, Mapping) or set(payload) != expected:
            raise ValueError("persisted response schema spec has the wrong fields")
        try:
            allowed = tuple(
                (row[0], tuple(row[1])) for row in payload["allowed_action_ids_by_key"]
            )
            value = cls(
                arm_id=ArmId(payload["arm_id"]),
                packet_kind=(
                    PacketKind(payload["packet_kind"])
                    if payload["packet_kind"] is not None
                    else None
                ),
                permission=ResponsePermission(payload["permission"]),
                physical_calls=payload["physical_calls"],
                parser_kind=ResponseParserKind(payload["parser_kind"]),
                schema_version=payload["schema_version"],
                action_authority=(
                    ActionAuthority(payload["action_authority"])
                    if payload["action_authority"] is not None
                    else None
                ),
                action_space=(
                    ActionSpace(payload["action_space"])
                    if payload["action_space"] is not None
                    else None
                ),
                planned_key_tokens=tuple(payload["planned_key_tokens"]),
                allowed_action_ids_by_key=allowed,
                response_schema=payload["response_schema"],
                action_manifest_hash=payload["action_manifest_hash"],
                numerical_registry_hash=payload["numerical_registry_hash"],
                feature_registry_hash=payload["feature_registry_hash"],
                predicate_manifest_hash=payload["predicate_manifest_hash"],
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ValueError("persisted response schema spec is invalid") from exc
        if canonical_bytes(payload) != canonical_bytes(value):
            raise ValueError("persisted response schema spec is not canonical")
        return value


@dataclass(frozen=True, slots=True)
class CanonicalResponseSchemaRegistry:
    """Complete immutable response-schema registry for one action registry."""

    specs: tuple[ArmResponseSchemaSpec, ...]
    action_manifest_hash: str
    numerical_registry_hash: str
    feature_registry_hash: str
    schema_version: str = RESPONSE_SCHEMA_REGISTRY_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RESPONSE_SCHEMA_REGISTRY_VERSION:
            raise ValueError("unknown response schema registry version")
        for name in (
            "action_manifest_hash",
            "numerical_registry_hash",
            "feature_registry_hash",
        ):
            _require_sha256(getattr(self, name), name)
        specs = tuple(self.specs)
        object.__setattr__(self, "specs", specs)
        arms = tuple(spec.arm_id for spec in specs)
        if arms != tuple(ArmId) or len(set(arms)) != len(ArmId):
            raise ValueError("response schema registry must cover every ArmId exactly once")
        for spec in specs:
            if (
                spec.action_manifest_hash != self.action_manifest_hash
                or spec.numerical_registry_hash != self.numerical_registry_hash
                or spec.feature_registry_hash != self.feature_registry_hash
            ):
                raise ValueError("arm spec registry bindings differ from registry head")

    @property
    def by_arm(self) -> Mapping[ArmId, ArmResponseSchemaSpec]:
        return MappingProxyType({spec.arm_id: spec for spec in self.specs})

    def spec_for(self, arm_id: ArmId) -> ArmResponseSchemaSpec:
        if not isinstance(arm_id, ArmId):
            raise TypeError("arm_id must be ArmId")
        return self.by_arm[arm_id]

    @property
    def registry_hash(self) -> str:
        return canonical_sha256(
            {
                "schema_version": self.schema_version,
                "action_manifest_hash": self.action_manifest_hash,
                "numerical_registry_hash": self.numerical_registry_hash,
                "feature_registry_hash": self.feature_registry_hash,
                "arm_specs": [
                    {"arm_id": spec.arm_id.value, "spec_manifest_hash": spec.spec_manifest_hash}
                    for spec in self.specs
                ],
            }
        )

    @property
    def response_registry_hash(self) -> str:
        return self.registry_hash


def _object_schema(properties: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(properties),
        "properties": dict(properties),
    }


def _array_schema(items: Mapping[str, Any], *, exact_length: int) -> dict[str, Any]:
    return {
        "type": "array",
        "items": dict(items),
        "minItems": exact_length,
        "maxItems": exact_length,
        "uniqueItems": True,
    }


def _string_const(value: str) -> dict[str, Any]:
    return {"type": "string", "const": value}


def _direct_response_schema(registry: CAPActionRegistry) -> dict[str, Any]:
    branches: list[dict[str, Any]] = []
    for key in registry.numerical.planned_keys:
        contract = registry.numerical.contract_map[f"{key.target}|{key.unit}"]
        if not contract.numeric_allowed:
            branch = _object_schema(
                {
                    "key": _string_const(key.token),
                    "status": _string_const(ForecastStatus.RUL_NA.value),
                }
            )
        else:
            number_schema: dict[str, Any] = {"type": "number"}
            if contract.minimum is not None:
                number_schema["minimum"] = contract.minimum
            if contract.maximum is not None:
                number_schema["maximum"] = contract.maximum
            branch = _object_schema(
                {
                    "key": _string_const(key.token),
                    "status": _string_const(ForecastStatus.NUMERIC.value),
                    "point": dict(number_schema),
                    "lower": dict(number_schema),
                    "median": dict(number_schema),
                    "upper": dict(number_schema),
                }
            )
        branches.append(branch)
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        **_object_schema(
            {
                "schema_version": _string_const(DIRECT_RESPONSE_SCHEMA_VERSION),
                "forecasts": _array_schema(
                    {"oneOf": branches},
                    exact_length=len(branches),
                ),
            }
        ),
    }


def _allowed_actions_for_permission(
    registry: CAPActionRegistry,
    *,
    key_token: str,
    permission: ResponsePermission,
    action_space: ActionSpace,
) -> tuple[Action, ...]:
    candidates = registry.actions_for(key_token, action_space)
    if registry.numerical.fallback_bundle.by_key[key_token].status is ForecastStatus.RUL_NA:
        # Every action-selection verifier grants the one explicit endpoint gate
        # before applying its ordinary permission filter.
        if len(candidates) != 1:
            raise AssertionError("endpoint-gated key must have exactly one forced action")
        return candidates
    if permission is ResponsePermission.EMIT_ONLY:
        result = tuple(
            item
            for item in candidates
            if item.transform is None and item.base.operator is BaseOperator.EMIT
        )
    elif permission is ResponsePermission.FUSE_ONLY:
        result = tuple(
            item
            for item in candidates
            if item.transform is None and item.base.operator is BaseOperator.FUSE
        )
    elif permission is ResponsePermission.CHAMPION_CORRECTION:
        champion = registry.numerical.champion_map[key_token]
        result = tuple(
            item
            for item in candidates
            if item.base.action_id == champion.action_id
            and item.transform in {None, TransformOperator.SHIFT, TransformOperator.INFLATE}
        )
    elif permission in {
        ResponsePermission.PRIMARY_ACTION,
        ResponsePermission.IF_REPRESENTATION,
        ResponsePermission.COMPOSITIONAL_ACTION,
    }:
        result = candidates
    else:  # pragma: no cover - closed descriptor table prevents this path
        raise ValueError("permission does not carry action authority")
    if not result:
        raise AssertionError("permission produced an empty action quotient")
    return result


def _allowed_action_ids(
    registry: CAPActionRegistry,
    *,
    permission: ResponsePermission,
    action_space: ActionSpace,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(
        (
            key.token,
            tuple(
                sorted(
                    item.action_id
                    for item in _allowed_actions_for_permission(
                        registry,
                        key_token=key.token,
                        permission=permission,
                        action_space=action_space,
                    )
                )
            ),
        )
        for key in registry.numerical.planned_keys
    )


def _action_response_schema(
    *,
    allowed_action_ids: Sequence[tuple[str, tuple[str, ...]]],
) -> dict[str, Any]:
    branches = [
        _object_schema(
            {
                "key": _string_const(key_token),
                "action_id": {"type": "string", "enum": list(action_ids)},
            }
        )
        for key_token, action_ids in allowed_action_ids
    ]
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        **_object_schema(
            {
                "schema_version": _string_const(ACTION_RESPONSE_SCHEMA_VERSION),
                "selections": _array_schema(
                    {"oneOf": branches},
                    exact_length=len(branches),
                ),
            }
        ),
    }


def _if_response_schema(
    *,
    allowed_action_ids: Sequence[tuple[str, tuple[str, ...]]],
    predicates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    branches: list[dict[str, Any]] = []
    predicate_schema = {"enum": list(predicates)}
    for key_token, action_ids in allowed_action_ids:
        branches.append(
            _object_schema(
                {
                    "key": _string_const(key_token),
                    "action_id": {"type": "string", "enum": list(action_ids)},
                }
            )
        )
        # A singleton endpoint gate cannot form two distinct branches.  The
        # verifier enforces branch inequality for all conditional programs.
        if len(action_ids) >= 2:
            branches.append(
                _object_schema(
                    {
                        "key": _string_const(key_token),
                        "predicate": predicate_schema,
                        "true_action_id": {
                            "type": "string",
                            "enum": list(action_ids),
                        },
                        "false_action_id": {
                            "type": "string",
                            "enum": list(action_ids),
                        },
                    }
                )
            )
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        **_object_schema(
            {
                "schema_version": _string_const(IF_RESPONSE_SCHEMA_VERSION),
                "artifacts": _array_schema(
                    {"oneOf": branches},
                    exact_length=len(allowed_action_ids),
                ),
            }
        ),
    }


def build_response_schema_registry(
    registry: CAPActionRegistry,
) -> CanonicalResponseSchemaRegistry:
    """Build all arm schemas solely from frozen contracts and registries."""

    if not isinstance(registry, CAPActionRegistry):
        raise TypeError("registry must be CAPActionRegistry")
    if set(FROZEN_ARM_SPECS) != set(ArmId):
        raise ValueError("FROZEN_ARM_SPECS does not cover the ArmId enum")

    planned_keys = tuple(key.token for key in registry.numerical.planned_keys)
    feature_bins = {
        feature.feature_id: feature.bin_ids for feature in registry.features.features
    }
    predicates = tuple(
        sorted(build_if1_predicate_fixture(feature_bins), key=canonical_bytes)
    )
    predicate_manifest_hash = canonical_sha256(
        {
            "schema_version": "CAPIFPredicateManifest.v1",
            "feature_registry_hash": registry.features.feature_registry_hash,
            "predicates": list(predicates),
        }
    )

    specs: list[ArmResponseSchemaSpec] = []
    for arm_id in ArmId:
        arm = FROZEN_ARM_SPECS[arm_id]
        descriptor = _PERMISSION_DESCRIPTORS[arm.permission]
        allowed: tuple[tuple[str, tuple[str, ...]], ...] = ()
        response_schema: Mapping[str, Any] | None = None
        bound_predicate_hash: str | None = None
        if descriptor.parser_kind is ResponseParserKind.DIRECT:
            response_schema = _direct_response_schema(registry)
        elif descriptor.parser_kind is ResponseParserKind.ACTION_SELECTION:
            assert descriptor.action_space is not None
            allowed = _allowed_action_ids(
                registry,
                permission=arm.permission,
                action_space=descriptor.action_space,
            )
            response_schema = _action_response_schema(allowed_action_ids=allowed)
        elif descriptor.parser_kind is ResponseParserKind.IF_REPRESENTATION:
            assert descriptor.action_space is not None
            allowed = _allowed_action_ids(
                registry,
                permission=arm.permission,
                action_space=descriptor.action_space,
            )
            response_schema = _if_response_schema(
                allowed_action_ids=allowed,
                predicates=predicates,
            )
            bound_predicate_hash = predicate_manifest_hash

        specs.append(
            ArmResponseSchemaSpec(
                arm_id=arm_id,
                packet_kind=arm.packet_kind,
                permission=arm.permission,
                physical_calls=arm.physical_calls,
                parser_kind=descriptor.parser_kind,
                schema_version=descriptor.schema_version,
                action_authority=descriptor.action_authority,
                action_space=descriptor.action_space,
                planned_key_tokens=planned_keys,
                allowed_action_ids_by_key=allowed,
                response_schema=response_schema,
                action_manifest_hash=registry.action_manifest_hash,
                numerical_registry_hash=registry.numerical.numerical_registry_hash,
                feature_registry_hash=registry.features.feature_registry_hash,
                predicate_manifest_hash=bound_predicate_hash,
            )
        )

    return CanonicalResponseSchemaRegistry(
        tuple(specs),
        action_manifest_hash=registry.action_manifest_hash,
        numerical_registry_hash=registry.numerical.numerical_registry_hash,
        feature_registry_hash=registry.features.feature_registry_hash,
    )


def validate_response_payload(
    payload: str | bytes | bytearray | Mapping[str, Any],
    spec: ArmResponseSchemaSpec,
) -> Mapping[str, Any]:
    """Strictly parse and locally validate one response for ``spec``.

    A successful result is only schema-valid.  The arm-specific verifier must
    still authorize cross-field invariants and deterministic execution.
    """

    if not isinstance(spec, ArmResponseSchemaSpec):
        raise TypeError("spec must be ArmResponseSchemaSpec")
    if spec.response_schema is None:
        raise ResponseSchemaValidationError("local-only arm does not accept a response")
    try:
        if isinstance(payload, (str, bytes, bytearray)):
            value = strict_json_loads(payload)
        else:
            value = to_primitive(payload)
    except (StrictJSONError, TypeError, ValueError) as exc:
        raise _instance_error() from exc
    _validate_instance(value, spec.response_schema)
    if not isinstance(value, Mapping):  # root schemas are all exact objects
        raise _instance_error()
    return value


__all__ = (
    "ArmResponseSchemaSpec",
    "CanonicalResponseSchemaRegistry",
    "JSON_SCHEMA_DIALECT",
    "RESPONSE_SCHEMA_REGISTRY_VERSION",
    "ResponseParserKind",
    "ResponseSchemaDefinitionError",
    "ResponseSchemaError",
    "ResponseSchemaValidationError",
    "build_response_schema_registry",
    "validate_response_payload",
    "validate_schema_definition",
    "validate_schema_instance",
)
