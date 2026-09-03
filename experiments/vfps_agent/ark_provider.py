"""Auditable Ark AgentPlan ``/responses`` adapter for ``accuracy_v1``.

The adapter deliberately owns neither credentials nor network I/O.  An
authenticated transport is injected by the composition root and receives one
secret-free :class:`ArkTransportRequest`.  This separation keeps environment
lookup, Authorization headers, HTTP libraries and retry policy outside the
scientific execution path and makes the complete adapter testable offline.

Provider-side structured-output support is an explicitly frozen capability,
not an assumption.  Irrespective of the requested response-format mode, the
returned output text is parsed with duplicate/non-finite rejection and checked
against a deliberately small, fail-closed JSON-Schema subset locally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import math
import re
import threading
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from .canonical import (
    StrictJSONError,
    canonical_bytes,
    canonical_sha256,
    strict_canonical_loads,
    strict_json_loads,
    to_primitive,
)
from .contracts import (
    AccuracyBudgetSpec,
    ArmId,
    AttemptResult,
    AttemptStart,
    AttemptStatus,
    ClosedErrorCode,
    FROZEN_ARM_SPECS,
    PolicySpec,
    ProtocolId,
    UsageStatus,
)
from .provider import ProviderResponse
from .response_schema import ArmResponseSchemaSpec
from .verifier import (
    ACTION_RESPONSE_SCHEMA_VERSION,
    DIRECT_RESPONSE_SCHEMA_VERSION,
    IF_RESPONSE_SCHEMA_VERSION,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,159}$")
_SAFE_SCHEMA_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SECRET_PATTERNS = (
    re.compile(rb"(?i)\bark-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"(?i)\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*\b"),
    re.compile(rb"(?i)CANARY[_-]DO[_-]NOT[_-]PERSIST"),
)
_SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "$schema",
        "title",
        "description",
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
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "pattern",
        "allOf",
        "anyOf",
        "oneOf",
    }
)
_RESPONSE_TOP_LEVEL_KEYS = frozenset(
    {
        "background",
        "completed_at",
        "created_at",
        "error",
        "id",
        "incomplete_details",
        "instructions",
        "max_output_tokens",
        "max_tool_calls",
        "metadata",
        "model",
        "object",
        "output",
        "parallel_tool_calls",
        "previous_response_id",
        "prompt",
        "prompt_cache_key",
        "reasoning",
        "safety_identifier",
        "service_tier",
        "status",
        "store",
        "temperature",
        "text",
        "tool_choice",
        "tools",
        "top_logprobs",
        "top_p",
        "truncation",
        "usage",
        "user",
    }
)
_USAGE_KEYS = frozenset(
    {
        "input_tokens",
        "prompt_tokens",
        "output_tokens",
        "completion_tokens",
        "total_tokens",
        "input_tokens_details",
        "prompt_tokens_details",
        "output_tokens_details",
        "completion_tokens_details",
    }
)


class ArkProviderError(RuntimeError):
    """Base class whose messages never contain provider or transport text."""


class ArkBindingError(ArkProviderError):
    """A frozen local binding failed before the physical request."""


class ArkInvocationError(ArkProviderError):
    """The one physical slot was already consumed."""


class ArkResponseFormat(str, Enum):
    """Provider-side output constraint; local validation is always mandatory."""

    PROMPT_ONLY = "prompt_only"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


class ArkClosedOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    LATE_RESPONSE = "LATE_RESPONSE"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    MODEL_MISMATCH = "MODEL_MISMATCH"


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ArkBindingError(f"invalid frozen {name}")


def _require_safe_model(value: str, name: str) -> None:
    if not isinstance(value, str) or _SAFE_MODEL_RE.fullmatch(value) is None:
        raise ArkBindingError(f"invalid {name}")
    _reject_secret_bytes(value.encode("utf-8"))


def _reject_secret_bytes(value: bytes) -> None:
    if any(pattern.search(value) is not None for pattern in _SECRET_PATTERNS):
        raise ArkBindingError("secret-like material is forbidden at the adapter boundary")


def _is_finite_json_number(value: Any) -> bool:
    """Classify JSON numbers without coercing unbounded integers to float."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return isinstance(value, int) or math.isfinite(value)


def _detached_json_mapping(value: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArkBindingError(f"{name} must be an object")
    try:
        detached = strict_json_loads(canonical_bytes(value))
    except (StrictJSONError, TypeError, ValueError) as exc:
        raise ArkBindingError(f"{name} is not strict JSON") from exc
    if not isinstance(detached, dict):
        raise ArkBindingError(f"{name} must be an object")

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(detached)


@dataclass(frozen=True, slots=True)
class ArkPromptSpec:
    """Origin-independent prompt with a declared canonical packet insertion."""

    instructions: str
    packet_preamble: str
    input_encoding: str = "canonical_origin_packet_json_utf8"
    schema_version: str = field(default="ArkPromptSpec.v1", init=False)

    def __post_init__(self) -> None:
        for name in ("instructions", "packet_preamble"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value.strip() != value:
                raise ArkBindingError(f"invalid prompt {name}")
            _reject_secret_bytes(value.encode("utf-8"))
        if self.input_encoding != "canonical_origin_packet_json_utf8":
            raise ArkBindingError("unsupported packet input encoding")

    @property
    def prompt_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class ArkDecodeSpec:
    """Sampling/reasoning parameters sent verbatim and bound to the policy."""

    temperature: float = 0.0
    top_p: float = 1.0
    reasoning_effort: str | None = None
    schema_version: str = field(default="ArkDecodeSpec.v1", init=False)

    def __post_init__(self) -> None:
        for name, lower, upper in (("temperature", 0.0, 2.0), ("top_p", 0.0, 1.0)):
            value = getattr(self, name)
            if (
                not _is_finite_json_number(value)
                or not lower <= value <= upper
            ):
                raise ArkBindingError(f"invalid decode parameter {name}")
            object.__setattr__(self, name, float(value))
        if self.reasoning_effort not in {None, "minimal", "low", "medium", "high"}:
            raise ArkBindingError("unsupported reasoning effort")

    @property
    def decode_parameters_hash(self) -> str:
        return canonical_sha256(self)

    def request_fields(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if self.reasoning_effort is not None:
            result["reasoning"] = {"effort": self.reasoning_effort}
        return result


@dataclass(frozen=True, slots=True)
class ArkCapabilitySnapshot:
    """Detached authenticated model-list × text-resource eligibility artifact."""

    model_list_artifact_sha256: str
    text_resources_artifact_sha256: str
    authenticated_model_ids: tuple[str, ...]
    text_resource_model_ids: tuple[str, ...]
    eligible_model_ids: tuple[str, ...]
    qualification: str = "AUTHENTICATED_MODEL_LIST_X_TEXT_RESOURCES"
    schema_version: str = field(default="ArkCapabilitySnapshot.v1", init=False)

    def __post_init__(self) -> None:
        _require_sha256(self.model_list_artifact_sha256, "model-list artifact hash")
        _require_sha256(self.text_resources_artifact_sha256, "text-resources artifact hash")
        for name in (
            "authenticated_model_ids",
            "text_resource_model_ids",
            "eligible_model_ids",
        ):
            values = tuple(getattr(self, name))
            if values != tuple(sorted(set(values))) or not values:
                raise ArkBindingError(f"{name} must be non-empty, unique, and sorted")
            for value in values:
                _require_safe_model(value, name)
            object.__setattr__(self, name, values)
        expected = tuple(
            sorted(set(self.authenticated_model_ids) & set(self.text_resource_model_ids))
        )
        if self.eligible_model_ids != expected:
            raise ArkBindingError("eligible models must equal the authenticated intersection")
        if self.qualification != "AUTHENTICATED_MODEL_LIST_X_TEXT_RESOURCES":
            raise ArkBindingError("capability snapshot is not an authenticated intersection")

    @property
    def snapshot_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class ArkModelRule:
    """Exact requested/returned identity rule tied to a capability snapshot."""

    requested_model_id: str
    capability_snapshot: ArkCapabilitySnapshot
    returned_model_rule: str = "exact_string_equality"
    schema_version: str = field(default="ArkModelRule.v1", init=False)

    def __post_init__(self) -> None:
        _require_safe_model(self.requested_model_id, "requested model ID")
        if not isinstance(self.capability_snapshot, ArkCapabilitySnapshot):
            raise ArkBindingError("model rule requires a typed capability snapshot")
        if self.requested_model_id not in self.capability_snapshot.eligible_model_ids:
            raise ArkBindingError("requested model is absent from the authenticated intersection")
        if self.returned_model_rule != "exact_string_equality":
            raise ArkBindingError("accuracy_v1 requires exact returned-model equality")

    @property
    def model_version_rule_hash(self) -> str:
        return canonical_sha256(self)

    @property
    def capability_snapshot_hash(self) -> str:
        return self.capability_snapshot.snapshot_hash


@dataclass(frozen=True, slots=True)
class ArkProviderRule:
    """Stateless, tool-free AgentPlan data-plane request rule."""

    response_format: ArkResponseFormat
    response_schema_name: str
    endpoint_path: str = "/responses"
    max_raw_response_bytes: int = 2_000_000
    transport_profile_hash: str | None = None
    require_transport_receipt: bool = False
    schema_version: str = field(default="ArkProviderRule.v1", init=False)
    http_method: str = field(default="POST", init=False)
    stream: bool = field(default=False, init=False)
    store: bool = field(default=False, init=False)
    tools: str = field(default="disabled", init=False)
    previous_response_id: str = field(default="omitted", init=False)
    cache: str = field(default="omitted_stateless_lane", init=False)
    retries: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.response_format, ArkResponseFormat):
            raise ArkBindingError("response_format must be ArkResponseFormat")
        if _SAFE_SCHEMA_NAME_RE.fullmatch(self.response_schema_name) is None:
            raise ArkBindingError("invalid response schema name")
        if self.endpoint_path != "/responses":
            raise ArkBindingError("Ark AgentPlan data-plane path must be /responses")
        if (
            isinstance(self.max_raw_response_bytes, bool)
            or not isinstance(self.max_raw_response_bytes, int)
            or not 1 <= self.max_raw_response_bytes <= 16_000_000
        ):
            raise ArkBindingError("invalid raw response byte ceiling")
        if not isinstance(self.require_transport_receipt, bool):
            raise ArkBindingError("transport receipt requirement must be boolean")
        if self.transport_profile_hash is not None:
            _require_sha256(self.transport_profile_hash, "transport profile hash")
        if self.require_transport_receipt != (self.transport_profile_hash is not None):
            raise ArkBindingError(
                "attested transport requires exactly one frozen transport profile hash"
            )

    @property
    def provider_rule_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class ArkRequestContract:
    """All request-construction inputs frozen before an origin is revealed."""

    prompt: ArkPromptSpec
    decode: ArkDecodeSpec
    model: ArkModelRule
    provider: ArkProviderRule
    response_schema: Mapping[str, Any]
    response_schema_spec: ArmResponseSchemaSpec | None = None
    schema_version: str = field(default="ArkRequestContract.v1", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, ArkPromptSpec):
            raise ArkBindingError("prompt must be ArkPromptSpec")
        if not isinstance(self.decode, ArkDecodeSpec):
            raise ArkBindingError("decode must be ArkDecodeSpec")
        if not isinstance(self.model, ArkModelRule):
            raise ArkBindingError("model must be ArkModelRule")
        if not isinstance(self.provider, ArkProviderRule):
            raise ArkBindingError("provider must be ArkProviderRule")
        frozen = _detached_json_mapping(self.response_schema, "response schema")
        _reject_secret_bytes(canonical_bytes(frozen))
        _check_schema_definition(frozen, root=True)
        object.__setattr__(self, "response_schema", frozen)
        if self.response_schema_spec is not None:
            if not isinstance(self.response_schema_spec, ArmResponseSchemaSpec):
                raise ArkBindingError("response schema spec has the wrong typed authority")
            if self.response_schema_spec.response_schema is None:
                raise ArkBindingError("local-only response schema spec cannot bind Ark")
            if canonical_bytes(frozen) != canonical_bytes(
                self.response_schema_spec.response_schema
            ):
                raise ArkBindingError("response schema differs from its canonical arm spec")
            if self.response_schema_spec.response_schema_hash != canonical_sha256(frozen):
                raise ArkBindingError("response schema hash differs from its canonical arm spec")

    @property
    def response_schema_hash(self) -> str:
        return canonical_sha256(self.response_schema)


def _expected_response_schema_version(arm: ArmId) -> str:
    if arm in {ArmId.D1_RAW, ArmId.D1_PACKET}:
        return DIRECT_RESPONSE_SCHEMA_VERSION
    if arm is ArmId.IF1:
        return IF_RESPONSE_SCHEMA_VERSION
    if arm in {
        ArmId.H1,
        ArmId.RF1,
        ArmId.RC1,
        ArmId.ACT1,
        ArmId.ACT_COMP96,
    }:
        return ACTION_RESPONSE_SCHEMA_VERSION
    raise ArkBindingError("Ark provider cannot be attached to a local-only arm")


@dataclass(frozen=True, slots=True)
class ArkBindingManifest:
    """Immutable bridge from the formal policy to exact HTTP construction."""

    policy_hash: str
    protocol: ProtocolId
    arm: ArmId
    packet_schema_hash: str
    prompt_hash: str
    response_schema_hash: str
    expected_response_schema_version: str
    grammar_hash: str
    registry_hash: str
    decode_parameters_hash: str
    provider_rule_hash: str
    transport_profile_hash: str | None
    transport_receipt_required: bool
    model_version_rule_hash: str
    verifier_hash: str
    fallback_hash: str
    one_call_budget_hash: str
    capability_snapshot_hash: str
    request_contract_hash: str
    requested_model_id: str
    requested_output_tokens: int
    deadline_ms: int
    physical_calls: int
    retries: int
    schema_version: str = field(default="ArkBindingManifest.v1", init=False)

    def __post_init__(self) -> None:
        if self.protocol is not ProtocolId.ACCURACY_V1 or not isinstance(self.arm, ArmId):
            raise ArkBindingError("invalid accuracy binding manifest protocol or arm")
        for name in (
            "policy_hash",
            "packet_schema_hash",
            "prompt_hash",
            "response_schema_hash",
            "grammar_hash",
            "registry_hash",
            "decode_parameters_hash",
            "provider_rule_hash",
            "model_version_rule_hash",
            "verifier_hash",
            "fallback_hash",
            "one_call_budget_hash",
            "capability_snapshot_hash",
            "request_contract_hash",
        ):
            _require_sha256(getattr(self, name), name)
        if self.transport_profile_hash is not None:
            _require_sha256(self.transport_profile_hash, "transport_profile_hash")
        if not isinstance(self.transport_receipt_required, bool) or (
            self.transport_receipt_required
            != (self.transport_profile_hash is not None)
        ):
            raise ArkBindingError("binding manifest transport profile is inconsistent")
        _require_safe_model(self.requested_model_id, "requested model ID")
        if self.expected_response_schema_version != _expected_response_schema_version(self.arm):
            raise ArkBindingError("response schema version differs from arm authority")
        if (
            self.requested_output_tokens <= 0
            or self.deadline_ms <= 0
            or self.physical_calls != 1
            or self.retries != 0
        ):
            raise ArkBindingError("invalid accuracy binding manifest budget")

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class ArkTransportRequest:
    """Secret-free transport input; the transport owns authentication."""

    method: str
    path: str
    body: bytes
    deadline_unix_ms: int
    timeout_ms: int
    headers: tuple[tuple[str, str], ...] = (
        ("Accept", "application/json"),
        ("Content-Type", "application/json"),
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", bytes(self.body))
        if self.method != "POST" or self.path != "/responses":
            raise ArkBindingError("invalid transport route")
        if self.timeout_ms <= 0 or self.deadline_unix_ms <= 0:
            raise ArkBindingError("invalid transport deadline")
        if self.headers != (
            ("Accept", "application/json"),
            ("Content-Type", "application/json"),
        ):
            raise ArkBindingError("transport request headers must be the frozen non-secret set")
        _reject_secret_bytes(self.body)

    @property
    def body_sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


@dataclass(frozen=True, slots=True)
class ArkTransportResponse:
    """Minimal HTTP result returned by an injected authenticated transport."""

    status_code: int
    body: bytes
    completed_unix_ms: int
    content_type: str = "application/json"

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", bytes(self.body))


class ArkTransport(Protocol):
    """One-shot transport protocol.  Implementations must not retry ``send``.

    The production transport returns a typed success/failure union from
    ``ark_https_transport``.  The deliberately unsafe offline mock lane may
    return ``ArkTransportResponse`` directly.
    """

    def send(self, request: ArkTransportRequest) -> object: ...


@dataclass(frozen=True, slots=True)
class ArkInvocationAudit:
    """Compact, secret-free binding of one request and its raw response."""

    attempt_id: str
    arm: ArmId
    policy_hash: str
    binding_manifest_hash: str
    origin_hash: str
    packet_hash: str
    packet_schema_hash: str
    prompt_hash: str
    response_schema_hash: str
    grammar_hash: str
    registry_hash: str
    decode_parameters_hash: str
    provider_rule_hash: str
    model_version_rule_hash: str
    verifier_hash: str
    fallback_hash: str
    one_call_budget_hash: str
    capability_snapshot_hash: str
    request_contract_hash: str
    requested_model_id: str
    requested_model_hash: str
    request_body_sha256: str
    request_body_bytes: int
    requested_output_tokens: int
    started_unix_ms: int
    deadline_unix_ms: int
    completed_unix_ms: int
    reserved_slots: int
    physical_attempts: int
    retries: int
    transport_profile_hash: str | None
    transport_receipt: Mapping[str, Any] | None
    transport_receipt_hash: str | None
    outcome: ArkClosedOutcome
    http_status: int | None
    resolved_model_id: str | None
    resolved_model_hash: str | None
    raw_response_sha256: str | None
    raw_response_bytes: int | None
    provider_response_id_sha256: str | None
    response_content_sha256: str | None
    usage: Mapping[str, Any] | None
    usage_sha256: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    schema_version: str = field(default="ArkInvocationAudit.v1", init=False)

    def __post_init__(self) -> None:
        if self.usage is not None:
            object.__setattr__(self, "usage", _detached_json_mapping(self.usage, "usage"))
        if self.transport_receipt is not None:
            frozen_receipt = _detached_json_mapping(
                self.transport_receipt, "transport receipt"
            )
            object.__setattr__(self, "transport_receipt", frozen_receipt)
        for name in (
            "policy_hash",
            "binding_manifest_hash",
            "origin_hash",
            "packet_hash",
            "packet_schema_hash",
            "prompt_hash",
            "response_schema_hash",
            "grammar_hash",
            "registry_hash",
            "decode_parameters_hash",
            "provider_rule_hash",
            "model_version_rule_hash",
            "verifier_hash",
            "fallback_hash",
            "one_call_budget_hash",
            "capability_snapshot_hash",
            "request_contract_hash",
            "requested_model_hash",
            "request_body_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        for name in (
            "resolved_model_hash",
            "raw_response_sha256",
            "provider_response_id_sha256",
            "response_content_sha256",
            "usage_sha256",
            "transport_profile_hash",
            "transport_receipt_hash",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_sha256(value, name)
        _require_safe_model(self.requested_model_id, "requested model ID")
        if self.requested_model_hash != canonical_sha256(
            {"requested_model_id": self.requested_model_id}
        ):
            raise ArkBindingError("requested model hash is inconsistent")
        if not isinstance(self.arm, ArmId):
            raise ArkBindingError("invalid audited arm")
        if self.resolved_model_id is not None:
            _require_safe_model(self.resolved_model_id, "resolved model ID")
            if self.resolved_model_hash != canonical_sha256(
                {"resolved_model_id": self.resolved_model_id}
            ):
                raise ArkBindingError("resolved model hash is inconsistent")
        elif self.resolved_model_hash is not None:
            raise ArkBindingError("resolved model hash lacks its model ID")
        if (
            self.reserved_slots != 1
            or self.physical_attempts not in {0, 1}
            or self.retries != 0
        ):
            raise ArkBindingError(
                "accuracy_v1 audit must bind one reserved slot, zero/one wire call, and zero retries"
            )
        if (self.transport_receipt is None) != (self.transport_receipt_hash is None) or (
            self.transport_receipt is None
        ) != (self.transport_profile_hash is None):
            raise ArkBindingError("transport receipt, hash, and profile must be paired")
        if self.transport_receipt is not None:
            try:
                from .ark_https_transport import ArkOneShotTransportReceipt

                receipt = ArkOneShotTransportReceipt.from_mapping(
                    to_primitive(self.transport_receipt)
                )
            except Exception as exc:
                raise ArkBindingError("typed transport receipt is invalid") from exc
            if (
                self.transport_receipt_hash != receipt.receipt_hash
                or self.transport_profile_hash != receipt.profile_hash
                or self.physical_attempts != receipt.request_calls
                or self.retries != receipt.retries
                or self.request_body_sha256 != receipt.request_body_sha256
                or self.request_body_bytes != receipt.request_body_bytes
                or self.completed_unix_ms != receipt.completed_unix_ms
            ):
                raise ArkBindingError("transport receipt differs from invocation audit")
            if receipt.response_complete:
                if (
                    self.http_status != receipt.http_status
                    or self.raw_response_sha256 != receipt.observed_response_sha256
                    or self.raw_response_bytes != receipt.observed_response_bytes
                ):
                    raise ArkBindingError(
                        "complete transport receipt differs from response audit"
                    )
            elif self.outcome is not ArkClosedOutcome.TRANSPORT_ERROR:
                raise ArkBindingError(
                    "incomplete transport receipt cannot support response evidence"
                )
        if not isinstance(self.outcome, ArkClosedOutcome):
            raise ArkBindingError("invalid closed adapter outcome")
        usage_values = (self.input_tokens, self.output_tokens, self.total_tokens)
        if self.usage_sha256 is None:
            if self.usage is not None or any(value is not None for value in usage_values):
                raise ArkBindingError("unknown usage must not contain token values")
        else:
            if self.usage is None:
                raise ArkBindingError("reported usage lacks its canonical payload")
            expected_usage = _extract_usage(
                self.usage,
                requested_tokens=self.requested_output_tokens,
            )
            if expected_usage != (
                self.input_tokens,
                self.output_tokens,
                self.total_tokens,
                self.usage_sha256,
            ):
                raise ArkBindingError("reported usage evidence is inconsistent")
        if (self.raw_response_sha256 is None) != (self.raw_response_bytes is None):
            raise ArkBindingError("raw response hash and size must be present together")
        if self.raw_response_bytes is not None and (
            isinstance(self.raw_response_bytes, bool)
            or not isinstance(self.raw_response_bytes, int)
            or self.raw_response_bytes < 0
        ):
            raise ArkBindingError("raw response size is invalid")
        if self.completed_unix_ms < self.started_unix_ms:
            raise ArkBindingError("audit completion precedes attempt start")
        if self.deadline_unix_ms <= self.started_unix_ms:
            raise ArkBindingError("audit deadline is invalid")
        if self.request_body_bytes <= 0 or self.requested_output_tokens <= 0:
            raise ArkBindingError("audit request sizes must be positive")
        success = self.outcome in {ArkClosedOutcome.SUCCESS, ArkClosedOutcome.LATE_RESPONSE}
        if success:
            if (
                self.physical_attempts != 1
                or self.http_status != 200
                or self.resolved_model_id != self.requested_model_id
                or self.resolved_model_hash is None
                or self.raw_response_sha256 is None
                or self.provider_response_id_sha256 is None
                or self.response_content_sha256 is None
            ):
                raise ArkBindingError("successful audit lacks complete response bindings")
        if self.outcome is ArkClosedOutcome.MODEL_MISMATCH:
            if (
                self.physical_attempts != 1
                or self.http_status != 200
                or self.resolved_model_id is None
                or self.resolved_model_id == self.requested_model_id
                or self.resolved_model_hash is None
                or self.raw_response_sha256 is None
                or self.provider_response_id_sha256 is None
                or self.response_content_sha256 is not None
            ):
                raise ArkBindingError("model-mismatch audit is inconsistent")
        if self.outcome is ArkClosedOutcome.HTTP_ERROR:
            if (
                self.physical_attempts != 1
                or self.http_status is None
                or self.http_status == 200
                or self.raw_response_sha256 is None
                or self.response_content_sha256 is not None
            ):
                raise ArkBindingError("HTTP-error audit is inconsistent")
        if self.outcome is ArkClosedOutcome.INVALID_RESPONSE:
            if (
                self.physical_attempts != 1
                or self.raw_response_sha256 is None
                or self.response_content_sha256 is not None
            ):
                raise ArkBindingError("invalid-response audit is inconsistent")
        if self.outcome is ArkClosedOutcome.TRANSPORT_ERROR and any(
            value is not None
            for value in (
                self.http_status,
                self.resolved_model_id,
                self.raw_response_sha256,
                self.provider_response_id_sha256,
                self.response_content_sha256,
            )
        ):
            raise ArkBindingError("transport failure must not claim response evidence")
        if self.outcome is ArkClosedOutcome.LATE_RESPONSE:
            if self.completed_unix_ms <= self.deadline_unix_ms:
                raise ArkBindingError("late outcome did not cross its deadline")
        elif success and self.completed_unix_ms > self.deadline_unix_ms:
            raise ArkBindingError("on-time success crossed its deadline")

    @property
    def audit_hash(self) -> str:
        return canonical_sha256(self)


def _roundtrip_typed(raw: Mapping[str, Any], value: Any, name: str) -> Any:
    if not isinstance(raw, Mapping) or canonical_bytes(raw) != canonical_bytes(value):
        raise ArkBindingError(f"invalid typed {name}")
    return value


def _parse_capability_snapshot(raw: Mapping[str, Any]) -> ArkCapabilitySnapshot:
    try:
        value = ArkCapabilitySnapshot(
            model_list_artifact_sha256=raw["model_list_artifact_sha256"],
            text_resources_artifact_sha256=raw["text_resources_artifact_sha256"],
            authenticated_model_ids=tuple(raw["authenticated_model_ids"]),
            text_resource_model_ids=tuple(raw["text_resource_model_ids"]),
            eligible_model_ids=tuple(raw["eligible_model_ids"]),
            qualification=raw["qualification"],
        )
        return _roundtrip_typed(raw, value, "capability snapshot")
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed capability snapshot") from exc


def _parse_prompt(raw: Mapping[str, Any]) -> ArkPromptSpec:
    try:
        return _roundtrip_typed(
            raw,
            ArkPromptSpec(
                instructions=raw["instructions"],
                packet_preamble=raw["packet_preamble"],
                input_encoding=raw["input_encoding"],
            ),
            "prompt",
        )
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed prompt") from exc


def _parse_decode(raw: Mapping[str, Any]) -> ArkDecodeSpec:
    try:
        return _roundtrip_typed(
            raw,
            ArkDecodeSpec(
                temperature=raw["temperature"],
                top_p=raw["top_p"],
                reasoning_effort=raw["reasoning_effort"],
            ),
            "decode contract",
        )
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed decode contract") from exc


def _parse_model_rule(raw: Mapping[str, Any]) -> ArkModelRule:
    try:
        value = ArkModelRule(
            requested_model_id=raw["requested_model_id"],
            capability_snapshot=_parse_capability_snapshot(raw["capability_snapshot"]),
            returned_model_rule=raw["returned_model_rule"],
        )
        return _roundtrip_typed(raw, value, "model rule")
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed model rule") from exc


def _parse_provider_rule(raw: Mapping[str, Any]) -> ArkProviderRule:
    try:
        value = ArkProviderRule(
            response_format=ArkResponseFormat(raw["response_format"]),
            response_schema_name=raw["response_schema_name"],
            endpoint_path=raw["endpoint_path"],
            max_raw_response_bytes=raw["max_raw_response_bytes"],
            transport_profile_hash=raw["transport_profile_hash"],
            require_transport_receipt=raw["require_transport_receipt"],
        )
        return _roundtrip_typed(raw, value, "provider rule")
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed provider rule") from exc


def _parse_request_contract(raw: Mapping[str, Any]) -> ArkRequestContract:
    try:
        value = ArkRequestContract(
            prompt=_parse_prompt(raw["prompt"]),
            decode=_parse_decode(raw["decode"]),
            model=_parse_model_rule(raw["model"]),
            provider=_parse_provider_rule(raw["provider"]),
            response_schema=raw["response_schema"],
            response_schema_spec=(
                ArmResponseSchemaSpec.from_mapping(raw["response_schema_spec"])
                if raw["response_schema_spec"] is not None
                else None
            ),
        )
        return _roundtrip_typed(raw, value, "request contract")
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed request contract") from exc


def _parse_policy(raw: Mapping[str, Any]) -> PolicySpec:
    try:
        value = PolicySpec(
            policy_id=raw["policy_id"],
            generation=raw["generation"],
            protocol=ProtocolId(raw["protocol"]),
            arm=ArmId(raw["arm"]),
            provider_rule_hash=raw["provider_rule_hash"],
            model_version_rule_hash=raw["model_version_rule_hash"],
            prompt_hash=raw["prompt_hash"],
            packet_schema_hash=raw["packet_schema_hash"],
            response_schema_hash=raw["response_schema_hash"],
            grammar_hash=raw["grammar_hash"],
            registry_hash=raw["registry_hash"],
            decode_parameters_hash=raw["decode_parameters_hash"],
            one_call_budget_hash=raw["one_call_budget_hash"],
            verifier_hash=raw["verifier_hash"],
            fallback_hash=raw["fallback_hash"],
            capability_snapshot_hash=raw["capability_snapshot_hash"],
        )
        return _roundtrip_typed(raw, value, "policy")
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed policy") from exc


def _parse_budget(raw: Mapping[str, Any]) -> AccuracyBudgetSpec:
    try:
        value = AccuracyBudgetSpec(
            requested_tokens=raw["requested_tokens"],
            deadline_ms=raw["deadline_ms"],
            physical_calls=raw["physical_calls"],
            retries=raw["retries"],
        )
        return _roundtrip_typed(raw, value, "accuracy budget")
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed accuracy budget") from exc


def _parse_manifest(raw: Mapping[str, Any]) -> ArkBindingManifest:
    try:
        kwargs = dict(raw)
        kwargs.pop("schema_version")
        kwargs["protocol"] = ProtocolId(kwargs["protocol"])
        kwargs["arm"] = ArmId(kwargs["arm"])
        value = ArkBindingManifest(**kwargs)
        return _roundtrip_typed(raw, value, "binding manifest")
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed binding manifest") from exc


def _parse_audit(raw: Mapping[str, Any]) -> ArkInvocationAudit:
    try:
        kwargs = dict(raw)
        kwargs.pop("schema_version")
        kwargs["arm"] = ArmId(kwargs["arm"])
        kwargs["outcome"] = ArkClosedOutcome(kwargs["outcome"])
        value = ArkInvocationAudit(**kwargs)
        return _roundtrip_typed(raw, value, "invocation audit")
    except ArkBindingError:
        raise
    except Exception as exc:
        raise ArkBindingError("invalid typed invocation audit") from exc


def build_binding_manifest(
    policy: PolicySpec,
    budget: AccuracyBudgetSpec,
    contract: ArkRequestContract,
) -> ArkBindingManifest:
    return ArkBindingManifest(
        policy_hash=policy.policy_hash,
        protocol=policy.protocol,
        arm=policy.arm,
        packet_schema_hash=policy.packet_schema_hash,
        prompt_hash=policy.prompt_hash,
        response_schema_hash=policy.response_schema_hash,
        expected_response_schema_version=_expected_response_schema_version(policy.arm),
        grammar_hash=policy.grammar_hash,
        registry_hash=policy.registry_hash,
        decode_parameters_hash=policy.decode_parameters_hash,
        provider_rule_hash=policy.provider_rule_hash,
        transport_profile_hash=contract.provider.transport_profile_hash,
        transport_receipt_required=contract.provider.require_transport_receipt,
        model_version_rule_hash=policy.model_version_rule_hash,
        verifier_hash=policy.verifier_hash,
        fallback_hash=policy.fallback_hash,
        one_call_budget_hash=policy.one_call_budget_hash,
        capability_snapshot_hash=policy.capability_snapshot_hash,
        request_contract_hash=canonical_sha256(contract),
        requested_model_id=contract.model.requested_model_id,
        requested_output_tokens=budget.requested_tokens,
        deadline_ms=budget.deadline_ms,
        physical_calls=budget.physical_calls,
        retries=budget.retries,
    )


@dataclass(frozen=True, slots=True)
class ArkProviderEvidenceEnvelope:
    """Complete closed evidence reconstructed independently after persistence."""

    policy: PolicySpec
    budget: AccuracyBudgetSpec
    request_contract: ArkRequestContract
    binding_manifest: ArkBindingManifest
    invocation_audit: ArkInvocationAudit
    schema_version: str = field(default="ArkProviderEvidenceEnvelope.v1", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.policy, PolicySpec):
            raise ArkBindingError("evidence policy has the wrong type")
        if not isinstance(self.budget, AccuracyBudgetSpec):
            raise ArkBindingError("evidence budget has the wrong type")
        if not isinstance(self.request_contract, ArkRequestContract):
            raise ArkBindingError("evidence request contract has the wrong type")
        if not isinstance(self.binding_manifest, ArkBindingManifest):
            raise ArkBindingError("evidence binding manifest has the wrong type")
        if not isinstance(self.invocation_audit, ArkInvocationAudit):
            raise ArkBindingError("evidence invocation audit has the wrong type")
        expected_policy_hashes = {
            "prompt_hash": self.request_contract.prompt.prompt_hash,
            "response_schema_hash": self.request_contract.response_schema_hash,
            "decode_parameters_hash": self.request_contract.decode.decode_parameters_hash,
            "provider_rule_hash": self.request_contract.provider.provider_rule_hash,
            "model_version_rule_hash": self.request_contract.model.model_version_rule_hash,
            "one_call_budget_hash": self.budget.budget_hash,
            "capability_snapshot_hash": self.request_contract.model.capability_snapshot_hash,
        }
        if any(getattr(self.policy, name) != value for name, value in expected_policy_hashes.items()):
            raise ArkBindingError("evidence policy differs from budget or request contract")
        spec = self.request_contract.response_schema_spec
        if spec is not None and (
            spec.arm_id is not self.policy.arm
            or spec.physical_calls != 1
            or spec.action_manifest_hash != self.policy.registry_hash
            or spec.response_schema_hash != self.policy.response_schema_hash
            or canonical_bytes(spec.response_schema)
            != canonical_bytes(self.request_contract.response_schema)
        ):
            raise ArkBindingError("evidence canonical schema spec differs from policy authority")
        rebuilt_manifest = build_binding_manifest(
            self.policy,
            self.budget,
            self.request_contract,
        )
        if canonical_bytes(self.binding_manifest) != canonical_bytes(rebuilt_manifest):
            raise ArkBindingError("evidence manifest cannot be rebuilt from frozen contracts")
        audit = self.invocation_audit
        manifest = self.binding_manifest
        expected_audit = {
            "policy_hash": self.policy.policy_hash,
            "binding_manifest_hash": manifest.manifest_hash,
            "packet_schema_hash": manifest.packet_schema_hash,
            "prompt_hash": manifest.prompt_hash,
            "response_schema_hash": manifest.response_schema_hash,
            "grammar_hash": manifest.grammar_hash,
            "registry_hash": manifest.registry_hash,
            "decode_parameters_hash": manifest.decode_parameters_hash,
            "provider_rule_hash": manifest.provider_rule_hash,
            "model_version_rule_hash": manifest.model_version_rule_hash,
            "verifier_hash": manifest.verifier_hash,
            "fallback_hash": manifest.fallback_hash,
            "one_call_budget_hash": manifest.one_call_budget_hash,
            "capability_snapshot_hash": manifest.capability_snapshot_hash,
            "request_contract_hash": manifest.request_contract_hash,
            "requested_model_id": manifest.requested_model_id,
            "requested_output_tokens": manifest.requested_output_tokens,
            "reserved_slots": manifest.physical_calls,
            "retries": manifest.retries,
        }
        if any(getattr(audit, name) != value for name, value in expected_audit.items()):
            raise ArkBindingError("invocation audit differs from the rebuilt manifest")
        if audit.physical_attempts > manifest.physical_calls:
            raise ArkBindingError("invocation used more wire calls than its reserved slot")
        if manifest.transport_receipt_required:
            if (
                audit.transport_profile_hash != manifest.transport_profile_hash
                or audit.transport_receipt is None
                or audit.transport_receipt_hash is None
            ):
                raise ArkBindingError(
                    "attested manifest lacks its typed transport receipt"
                )
        elif any(
            value is not None
            for value in (
                audit.transport_profile_hash,
                audit.transport_receipt,
                audit.transport_receipt_hash,
            )
        ):
            raise ArkBindingError("unattested manifest contains transport evidence")

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def validate_attempt(self, attempt: AttemptStart) -> None:
        audit = self.invocation_audit
        if (
            audit.attempt_id != attempt.attempt_id
            or audit.arm is not attempt.arm
            or audit.policy_hash != attempt.policy_hash
            or audit.origin_hash != attempt.origin_hash
            or audit.packet_hash != attempt.packet_hash
            or audit.requested_output_tokens != attempt.requested_tokens
            or audit.started_unix_ms != attempt.started_unix_ms
            or audit.deadline_unix_ms != attempt.deadline_unix_ms
            or audit.deadline_unix_ms - audit.started_unix_ms != self.budget.deadline_ms
        ):
            raise ArkBindingError("provider evidence differs from durable STARTED")

    def validate_result(self, result: AttemptResult) -> None:
        """Bind a durable FINISHED row to the independently rebuilt evidence."""

        audit = self.invocation_audit
        expected_status = {
            ArkClosedOutcome.SUCCESS: AttemptStatus.SUCCESS,
            ArkClosedOutcome.LATE_RESPONSE: AttemptStatus.SUCCESS,
            ArkClosedOutcome.MODEL_MISMATCH: AttemptStatus.MODEL_MISMATCH,
            ArkClosedOutcome.TRANSPORT_ERROR: AttemptStatus.ERROR,
            ArkClosedOutcome.HTTP_ERROR: AttemptStatus.ERROR,
            ArkClosedOutcome.INVALID_RESPONSE: AttemptStatus.ERROR,
        }[audit.outcome]
        expected_error = {
            ArkClosedOutcome.SUCCESS: None,
            ArkClosedOutcome.LATE_RESPONSE: None,
            ArkClosedOutcome.MODEL_MISMATCH: ClosedErrorCode.MODEL_MISMATCH,
            ArkClosedOutcome.TRANSPORT_ERROR: ClosedErrorCode.PROVIDER_ERROR,
            ArkClosedOutcome.HTTP_ERROR: ClosedErrorCode.PROVIDER_ERROR,
            ArkClosedOutcome.INVALID_RESPONSE: ClosedErrorCode.INVALID_RESPONSE,
        }[audit.outcome]
        usage_known = audit.input_tokens is not None and audit.output_tokens is not None
        if (
            result.attempt_id != audit.attempt_id
            or result.status is not expected_status
            or result.error_code is not expected_error
            or result.completed_unix_ms != audit.completed_unix_ms
            or result.usage_status
            is not (UsageStatus.REPORTED if usage_known else UsageStatus.UNKNOWN)
            or result.input_tokens != audit.input_tokens
            or result.output_tokens != audit.output_tokens
            or result.provider_response_id_hash != audit.provider_response_id_sha256
            or result.observed_model_hash != audit.resolved_model_hash
            or result.late != (audit.completed_unix_ms > audit.deadline_unix_ms)
        ):
            raise ArkBindingError("durable FINISHED differs from provider evidence")
        if result.provider_evidence_hash != self.evidence_hash:
            raise ArkBindingError("durable FINISHED evidence hash is inconsistent")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ArkProviderEvidenceEnvelope":
        try:
            value = cls(
                policy=_parse_policy(raw["policy"]),
                budget=_parse_budget(raw["budget"]),
                request_contract=_parse_request_contract(raw["request_contract"]),
                binding_manifest=_parse_manifest(raw["binding_manifest"]),
                invocation_audit=_parse_audit(raw["invocation_audit"]),
            )
            return _roundtrip_typed(raw, value, "provider evidence envelope")
        except ArkBindingError:
            raise
        except Exception as exc:
            raise ArkBindingError("invalid typed provider evidence envelope") from exc


@dataclass(frozen=True, slots=True)
class AuditedProviderResponse(ProviderResponse):
    """Runner-compatible response carrying a separate compact audit object."""

    audit: ArkInvocationAudit | None = None
    evidence: ArkProviderEvidenceEnvelope | None = None
    ephemeral_request_body_sha256: str | None = None
    ephemeral_raw_response_sha256: str | None = None
    ephemeral_response_content_sha256: str | None = None
    ephemeral_provider_response_id_sha256: str | None = None


def _schema_error() -> ArkBindingError:
    return ArkBindingError("unsupported or invalid strict response schema")


def _check_schema_definition(
    schema: Mapping[str, Any],
    *,
    depth: int = 0,
    root: bool = False,
) -> None:
    if depth > 32 or not isinstance(schema, Mapping):
        raise _schema_error()
    if not set(schema).issubset(_SUPPORTED_SCHEMA_KEYWORDS):
        raise _schema_error()
    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in {
        "object",
        "array",
        "string",
        "number",
        "integer",
        "boolean",
        "null",
    }:
        raise _schema_error()
    if root and schema_type is None and not set(schema) & {"allOf", "anyOf", "oneOf"}:
        raise _schema_error()
    object_keywords = {"properties", "required", "additionalProperties"}
    array_keywords = {"items", "minItems", "maxItems", "uniqueItems"}
    string_keywords = {"minLength", "maxLength", "pattern"}
    numeric_keywords = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}
    for expected_type, keywords in (
        ("object", object_keywords),
        ("array", array_keywords),
        ("string", string_keywords),
    ):
        if set(schema) & keywords and schema_type != expected_type:
            raise _schema_error()
    if set(schema) & numeric_keywords and schema_type not in {"number", "integer"}:
        raise _schema_error()
    for keyword in ("allOf", "anyOf", "oneOf"):
        if keyword in schema:
            branches = schema[keyword]
            if (
                not isinstance(branches, (list, tuple))
                or isinstance(branches, (str, bytes))
                or not branches
            ):
                raise _schema_error()
            for branch in branches:
                _check_schema_definition(branch, depth=depth + 1)
    if schema_type == "object" or "properties" in schema:
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, Mapping) or schema.get("additionalProperties") is not False:
            raise _schema_error()
        if (
            not isinstance(required, (list, tuple))
            or isinstance(required, (str, bytes))
            or any(not isinstance(item, str) for item in required)
            or len(required) != len(set(required))
            or set(required) != set(properties)
        ):
            raise _schema_error()
        for child in properties.values():
            _check_schema_definition(child, depth=depth + 1)
    if schema_type == "array" or "items" in schema:
        if not isinstance(schema.get("items"), Mapping):
            raise _schema_error()
        _check_schema_definition(schema["items"], depth=depth + 1)
    for name in ("minItems", "maxItems", "minLength", "maxLength"):
        if name in schema and (
            isinstance(schema[name], bool)
            or not isinstance(schema[name], int)
            or schema[name] < 0
        ):
            raise _schema_error()
    if (
        "minItems" in schema
        and "maxItems" in schema
        and schema["minItems"] > schema["maxItems"]
    ) or (
        "minLength" in schema
        and "maxLength" in schema
        and schema["minLength"] > schema["maxLength"]
    ):
        raise _schema_error()
    if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
        raise _schema_error()
    for name in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
        if name in schema:
            value = schema[name]
            if not _is_finite_json_number(value):
                raise _schema_error()
    lower = schema.get("minimum", schema.get("exclusiveMinimum"))
    upper = schema.get("maximum", schema.get("exclusiveMaximum"))
    if lower is not None and upper is not None and lower > upper:
        raise _schema_error()
    if "pattern" in schema:
        if not isinstance(schema["pattern"], str) or len(schema["pattern"]) > 1024:
            raise _schema_error()
        try:
            re.compile(schema["pattern"])
        except re.error as exc:
            raise _schema_error() from exc
    if "enum" in schema:
        values = schema["enum"]
        if (
            not isinstance(values, (list, tuple))
            or isinstance(values, (str, bytes))
            or not values
        ):
            raise _schema_error()
        fingerprints = [canonical_bytes(item) for item in values]
        if len(fingerprints) != len(set(fingerprints)):
            raise _schema_error()


def _json_equal(left: Any, right: Any) -> bool:
    """JSON equality without Python's ``True == 1`` coercion."""

    try:
        return canonical_bytes(left) == canonical_bytes(right)
    except (StrictJSONError, TypeError, ValueError):
        return False


def _validate_local_schema(value: Any, schema: Mapping[str, Any], *, depth: int = 0) -> None:
    if depth > 32:
        raise _schema_error()
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
        raise _schema_error()
    if "const" in schema and not _json_equal(value, schema["const"]):
        raise _schema_error()
    if "enum" in schema and not any(_json_equal(value, item) for item in schema["enum"]):
        raise _schema_error()
    if isinstance(value, Mapping) and (schema_type == "object" or "properties" in schema):
        properties = schema["properties"]
        required = set(schema["required"])
        if not required.issubset(value) or not set(value).issubset(properties):
            raise _schema_error()
        for key, child in value.items():
            _validate_local_schema(child, properties[key], depth=depth + 1)
    if isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)):
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise _schema_error()
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise _schema_error()
        if schema.get("uniqueItems") is True:
            fingerprints = [canonical_bytes(item) for item in value]
            if len(fingerprints) != len(set(fingerprints)):
                raise _schema_error()
        if "items" in schema:
            for item in value:
                _validate_local_schema(item, schema["items"], depth=depth + 1)
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise _schema_error()
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise _schema_error()
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise _schema_error()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        for name, predicate in (
            ("minimum", lambda bound: value >= bound),
            ("maximum", lambda bound: value <= bound),
            ("exclusiveMinimum", lambda bound: value > bound),
            ("exclusiveMaximum", lambda bound: value < bound),
        ):
            if name in schema and not predicate(schema[name]):
                raise _schema_error()
    if "allOf" in schema:
        for branch in schema["allOf"]:
            _validate_local_schema(value, branch, depth=depth + 1)
    if "anyOf" in schema:
        matches = 0
        for branch in schema["anyOf"]:
            try:
                _validate_local_schema(value, branch, depth=depth + 1)
                matches += 1
            except ArkBindingError:
                pass
        if matches < 1:
            raise _schema_error()
    if "oneOf" in schema:
        matches = 0
        for branch in schema["oneOf"]:
            try:
                _validate_local_schema(value, branch, depth=depth + 1)
                matches += 1
            except ArkBindingError:
                pass
        if matches != 1:
            raise _schema_error()


def _nonnegative_integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ArkBindingError("invalid response usage")
    return value


def _check_usage_details(value: Any, *, depth: int = 0) -> None:
    if depth > 4 or not isinstance(value, Mapping):
        raise ArkBindingError("invalid response usage")
    for child in value.values():
        if isinstance(child, Mapping):
            _check_usage_details(child, depth=depth + 1)
        else:
            _nonnegative_integer(child)


def _extract_usage(
    raw: Any,
    *,
    requested_tokens: int,
) -> tuple[int, int, int, str]:
    if not isinstance(raw, Mapping) or not set(raw).issubset(_USAGE_KEYS):
        raise ArkBindingError("invalid response usage")
    for name in (
        "input_tokens_details",
        "prompt_tokens_details",
        "output_tokens_details",
        "completion_tokens_details",
    ):
        if name in raw:
            _check_usage_details(raw[name])

    def alias(primary: str, alternate: str) -> int:
        present = [name for name in (primary, alternate) if name in raw]
        if not present:
            raise ArkBindingError("invalid response usage")
        values = [_nonnegative_integer(raw[name]) for name in present]
        if len(set(values)) != 1:
            raise ArkBindingError("invalid response usage")
        return values[0]

    input_tokens = alias("input_tokens", "prompt_tokens")
    output_tokens = alias("output_tokens", "completion_tokens")
    total_tokens = _nonnegative_integer(raw.get("total_tokens"))
    if output_tokens > requested_tokens or total_tokens < input_tokens + output_tokens:
        raise ArkBindingError("invalid response usage")
    return input_tokens, output_tokens, total_tokens, canonical_sha256(raw)


def _extract_output_text(envelope: Mapping[str, Any]) -> str:
    output = envelope.get("output")
    if not isinstance(output, list) or not output:
        raise ArkBindingError("invalid response envelope")
    messages: list[Mapping[str, Any]] = []
    for item in output:
        if not isinstance(item, Mapping):
            raise ArkBindingError("invalid response envelope")
        if item.get("type") == "reasoning":
            allowed_reasoning = {
                "id",
                "type",
                "summary",
                "content",
                "encrypted_content",
                "status",
            }
            if not {"id", "type", "summary"}.issubset(item) or not set(item).issubset(
                allowed_reasoning
            ):
                raise ArkBindingError("invalid response envelope")
            if (
                not isinstance(item["id"], str)
                or not isinstance(item["summary"], list)
                or ("content" in item and item["content"] is not None and not isinstance(item["content"], list))
                or ("encrypted_content" in item and item["encrypted_content"] is not None and not isinstance(item["encrypted_content"], str))
                or item.get("status") not in (None, "completed")
            ):
                raise ArkBindingError("invalid response envelope")
            _reject_secret_bytes(item["id"].encode("utf-8"))
            continue
        if item.get("type") != "message":
            raise ArkBindingError("tool, refusal, or unknown output is forbidden")
        messages.append(item)
    if len(messages) != 1:
        raise ArkBindingError("invalid response envelope")
    message = messages[0]
    if not isinstance(message, Mapping):
        raise ArkBindingError("invalid response envelope")
    allowed_message = {"id", "type", "status", "role", "content"}
    required_message = {"type", "status", "role", "content"}
    if not required_message.issubset(message) or not set(message).issubset(allowed_message):
        raise ArkBindingError("invalid response envelope")
    if (
        message["type"] != "message"
        or message["status"] != "completed"
        or message["role"] != "assistant"
    ):
        raise ArkBindingError("invalid response envelope")
    content = message["content"]
    if not isinstance(content, list) or len(content) != 1:
        raise ArkBindingError("invalid response envelope")
    part = content[0]
    if not isinstance(part, Mapping):
        raise ArkBindingError("invalid response envelope")
    if not {"type", "text"}.issubset(part) or not set(part).issubset(
        {"type", "text", "annotations", "logprobs"}
    ):
        raise ArkBindingError("invalid response envelope")
    if part["type"] != "output_text" or not isinstance(part["text"], str):
        raise ArkBindingError("invalid response envelope")
    if "annotations" in part and part["annotations"] != []:
        raise ArkBindingError("annotated/network-derived output is forbidden")
    if "logprobs" in part and part["logprobs"] not in (None, []):
        raise ArkBindingError("unexpected response metadata")
    return part["text"]


class ArkProviderAdapter:
    """One-origin, one-attempt Ark provider for the durable accuracy runner."""

    def __init__(
        self,
        *,
        policy: PolicySpec,
        budget: AccuracyBudgetSpec,
        contract: ArkRequestContract,
        transport: ArkTransport,
        unsafe_allow_unqualified_mock_schema: bool = False,
    ) -> None:
        self._policy = policy
        self._budget = budget
        self._contract = contract
        self._transport = transport
        if not isinstance(unsafe_allow_unqualified_mock_schema, bool):
            raise TypeError("mock schema override must be boolean")
        self._unsafe_allow_unqualified_mock_schema = unsafe_allow_unqualified_mock_schema
        self._lock = threading.Lock()
        self._used = False
        self._physical_attempts = 0
        self._validate_static_bindings()
        self._binding_manifest = self._build_binding_manifest()

    @property
    def physical_attempts(self) -> int:
        with self._lock:
            return self._physical_attempts

    @property
    def binding_manifest(self) -> ArkBindingManifest:
        return self._binding_manifest

    def _validate_static_bindings(self) -> None:
        policy = self._policy
        budget = self._budget
        contract = self._contract
        spec = contract.response_schema_spec
        if spec is None:
            if not self._unsafe_allow_unqualified_mock_schema:
                raise ArkBindingError("Ark adapter requires a canonical arm response schema spec")
        else:
            if (
                spec.arm_id is not policy.arm
                or spec.physical_calls != 1
                or spec.action_manifest_hash != policy.registry_hash
                or spec.response_schema_hash != policy.response_schema_hash
                or canonical_bytes(spec.response_schema) != canonical_bytes(contract.response_schema)
            ):
                raise ArkBindingError("canonical response schema spec differs from policy authority")
        if not self._unsafe_allow_unqualified_mock_schema and (
            not contract.provider.require_transport_receipt
            or contract.provider.transport_profile_hash is None
        ):
            raise ArkBindingError(
                "formal Ark adapter requires the frozen attested one-shot transport"
            )
        if contract.provider.require_transport_receipt:
            profile = getattr(self._transport, "profile", None)
            if (
                profile is None
                or getattr(profile, "profile_hash", None)
                != contract.provider.transport_profile_hash
                or getattr(profile, "max_response_bytes", None)
                != contract.provider.max_raw_response_bytes
                or getattr(profile, "endpoint_path", None)
                != contract.provider.endpoint_path
            ):
                raise ArkBindingError(
                    "transport instance differs from the frozen provider profile"
                )
        if policy.protocol is not ProtocolId.ACCURACY_V1:
            raise ArkBindingError("Ark accuracy adapter requires accuracy_v1")
        if FROZEN_ARM_SPECS[policy.arm].physical_calls != 1:
            raise ArkBindingError("Ark accuracy adapter requires a one-call arm")
        if budget.physical_calls != 1 or budget.retries != 0:
            raise ArkBindingError("accuracy_v1 requires one physical call and zero retries")
        expected = {
            "prompt_hash": contract.prompt.prompt_hash,
            "response_schema_hash": contract.response_schema_hash,
            "decode_parameters_hash": contract.decode.decode_parameters_hash,
            "provider_rule_hash": contract.provider.provider_rule_hash,
            "model_version_rule_hash": contract.model.model_version_rule_hash,
            "one_call_budget_hash": budget.budget_hash,
            "capability_snapshot_hash": contract.model.capability_snapshot_hash,
        }
        for name, value in expected.items():
            if getattr(policy, name) != value:
                raise ArkBindingError(f"policy {name} differs from the frozen Ark contract")
        expected_version = _expected_response_schema_version(policy.arm)
        schema = contract.response_schema
        properties = schema.get("properties")
        version_schema = properties.get("schema_version") if isinstance(properties, Mapping) else None
        if (
            schema.get("type") != "object"
            or not isinstance(version_schema, Mapping)
            or version_schema.get("const") != expected_version
        ):
            raise ArkBindingError("response schema version differs from arm authority")

    def _build_binding_manifest(self) -> ArkBindingManifest:
        return build_binding_manifest(self._policy, self._budget, self._contract)

    def _validate_attempt(self, request_bytes: bytes, attempt: AttemptStart) -> bytes:
        if not isinstance(request_bytes, bytes):
            raise ArkBindingError("provider packet must be canonical bytes")
        try:
            packet = strict_canonical_loads(request_bytes)
        except (StrictJSONError, TypeError, ValueError) as exc:
            raise ArkBindingError("provider packet must be strict canonical JSON") from exc
        canonical_packet = canonical_bytes(packet)
        _reject_secret_bytes(canonical_packet)
        if (
            attempt.protocol is not ProtocolId.ACCURACY_V1
            or attempt.policy_hash != self._policy.policy_hash
            or attempt.arm is not self._policy.arm
            or attempt.packet_hash != hashlib.sha256(canonical_packet).hexdigest()
            or attempt.requested_tokens != self._budget.requested_tokens
            or attempt.physical_slot != 0
            or attempt.deadline_unix_ms - attempt.started_unix_ms != self._budget.deadline_ms
        ):
            raise ArkBindingError("attempt differs from the frozen Ark accuracy slot")
        return canonical_packet

    def _request_payload(self, packet_bytes: bytes, attempt: AttemptStart) -> dict[str, Any]:
        contract = self._contract
        packet_text = packet_bytes.decode("utf-8", errors="strict")
        payload: dict[str, Any] = {
            "model": contract.model.requested_model_id,
            "instructions": contract.prompt.instructions,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"{contract.prompt.packet_preamble}\n{packet_text}",
                        }
                    ],
                }
            ],
            "max_output_tokens": attempt.requested_tokens,
            "stream": False,
            "store": False,
            "tools": [],
            "tool_choice": "none",
            **contract.decode.request_fields(),
        }
        response_format = contract.provider.response_format
        if response_format is ArkResponseFormat.JSON_OBJECT:
            payload["text"] = {"format": {"type": "json_object"}}
        elif response_format is ArkResponseFormat.JSON_SCHEMA:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": contract.provider.response_schema_name,
                    "schema": to_primitive(contract.response_schema),
                    "strict": True,
                }
            }
        forbidden = {"previous_response_id", "file", "url", "search", "cache", "caching"}
        if set(payload) & forbidden:
            raise ArkBindingError("stateful, network, file, or cache request field is forbidden")
        return payload

    def _audit(
        self,
        *,
        attempt: AttemptStart,
        request_body: bytes,
        completed_unix_ms: int,
        physical_attempts: int,
        transport_receipt: object | None,
        outcome: ArkClosedOutcome,
        http_status: int | None,
        resolved_model_id: str | None = None,
        resolved_model_hash: str | None = None,
        raw_response: bytes | None = None,
        provider_response_id_sha256: str | None = None,
        response_content_sha256: str | None = None,
        usage: Mapping[str, Any] | None = None,
        usage_sha256: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> ArkInvocationAudit:
        policy = self._policy
        contract = self._contract
        receipt_payload = (
            to_primitive(transport_receipt) if transport_receipt is not None else None
        )
        receipt_hash = (
            canonical_sha256(receipt_payload) if receipt_payload is not None else None
        )
        transport_profile_hash = (
            getattr(transport_receipt, "profile_hash", None)
            if transport_receipt is not None
            else None
        )
        return ArkInvocationAudit(
            attempt_id=attempt.attempt_id,
            arm=attempt.arm,
            policy_hash=policy.policy_hash,
            binding_manifest_hash=self._binding_manifest.manifest_hash,
            origin_hash=attempt.origin_hash,
            packet_hash=attempt.packet_hash,
            packet_schema_hash=policy.packet_schema_hash,
            prompt_hash=contract.prompt.prompt_hash,
            response_schema_hash=contract.response_schema_hash,
            grammar_hash=policy.grammar_hash,
            registry_hash=policy.registry_hash,
            decode_parameters_hash=contract.decode.decode_parameters_hash,
            provider_rule_hash=contract.provider.provider_rule_hash,
            model_version_rule_hash=contract.model.model_version_rule_hash,
            verifier_hash=policy.verifier_hash,
            fallback_hash=policy.fallback_hash,
            one_call_budget_hash=self._budget.budget_hash,
            capability_snapshot_hash=contract.model.capability_snapshot_hash,
            request_contract_hash=canonical_sha256(contract),
            requested_model_id=contract.model.requested_model_id,
            requested_model_hash=canonical_sha256(
                {"requested_model_id": contract.model.requested_model_id}
            ),
            request_body_sha256=hashlib.sha256(request_body).hexdigest(),
            request_body_bytes=len(request_body),
            requested_output_tokens=attempt.requested_tokens,
            started_unix_ms=attempt.started_unix_ms,
            deadline_unix_ms=attempt.deadline_unix_ms,
            completed_unix_ms=max(attempt.started_unix_ms, completed_unix_ms),
            reserved_slots=1,
            physical_attempts=physical_attempts,
            retries=0,
            transport_profile_hash=transport_profile_hash,
            transport_receipt=receipt_payload,
            transport_receipt_hash=receipt_hash,
            outcome=outcome,
            http_status=http_status,
            resolved_model_id=resolved_model_id,
            resolved_model_hash=resolved_model_hash,
            raw_response_sha256=hashlib.sha256(raw_response).hexdigest()
            if raw_response is not None
            else None,
            raw_response_bytes=len(raw_response) if raw_response is not None else None,
            provider_response_id_sha256=provider_response_id_sha256,
            response_content_sha256=response_content_sha256,
            usage=usage,
            usage_sha256=usage_sha256,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    def _closed_response(
        self,
        *,
        attempt: AttemptStart,
        request_body: bytes,
        completed_unix_ms: int,
        physical_attempts: int,
        transport_receipt: object | None,
        outcome: ArkClosedOutcome,
        http_status: int | None,
        status: AttemptStatus = AttemptStatus.ERROR,
        resolved_model_id: str | None = None,
        resolved_model_hash: str | None = None,
        raw_response: bytes | None = None,
        provider_response_id_sha256: str | None = None,
        response_content_sha256: str | None = None,
        usage: Mapping[str, Any] | None = None,
        usage_sha256: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> AuditedProviderResponse:
        audit = self._audit(
            attempt=attempt,
            request_body=request_body,
            completed_unix_ms=completed_unix_ms,
            physical_attempts=physical_attempts,
            transport_receipt=transport_receipt,
            outcome=outcome,
            http_status=http_status,
            resolved_model_id=resolved_model_id,
            resolved_model_hash=resolved_model_hash,
            raw_response=raw_response,
            provider_response_id_sha256=provider_response_id_sha256,
            response_content_sha256=response_content_sha256,
            usage=usage,
            usage_sha256=usage_sha256,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        evidence = ArkProviderEvidenceEnvelope(
            policy=self._policy,
            budget=self._budget,
            request_contract=self._contract,
            binding_manifest=self._binding_manifest,
            invocation_audit=audit,
        )
        return AuditedProviderResponse(
            status=status,
            completed_unix_ms=audit.completed_unix_ms,
            response_text=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            observed_model_hash=resolved_model_hash,
            error_code=outcome.value,
            late=audit.completed_unix_ms > attempt.deadline_unix_ms,
            audit=audit,
            evidence=evidence,
            ephemeral_request_body_sha256=hashlib.sha256(request_body).hexdigest(),
            ephemeral_raw_response_sha256=hashlib.sha256(raw_response).hexdigest()
            if raw_response is not None
            else None,
            ephemeral_response_content_sha256=response_content_sha256,
            ephemeral_provider_response_id_sha256=provider_response_id_sha256,
        )

    def _unaudited_transport_error(
        self,
        *,
        attempt: AttemptStart,
        request_body: bytes,
        completed_unix_ms: int,
    ) -> AuditedProviderResponse:
        """Fail closed when the required typed receipt cannot be trusted.

        Fabricating an evidence envelope here would turn an implementation
        exception or malformed transport result into a false statement about
        wire-call count.  The runner therefore receives no formal provider
        evidence and records a closed provider/binding failure.
        """

        return AuditedProviderResponse(
            status=AttemptStatus.ERROR,
            completed_unix_ms=max(attempt.started_unix_ms, completed_unix_ms),
            response_text=None,
            error_code=ArkClosedOutcome.TRANSPORT_ERROR.value,
            late=completed_unix_ms > attempt.deadline_unix_ms,
            audit=None,
            evidence=None,
            ephemeral_request_body_sha256=hashlib.sha256(request_body).hexdigest(),
        )

    def invoke(self, request_bytes: bytes, attempt: AttemptStart) -> AuditedProviderResponse:
        """Make exactly one physical attempt; every failure is terminal and closed."""

        packet_bytes = self._validate_attempt(request_bytes, attempt)
        request_body = canonical_bytes(self._request_payload(packet_bytes, attempt))
        # Re-parse the exact transmitted bytes to detect accidental serializer drift.
        strict_canonical_loads(request_body)
        _reject_secret_bytes(request_body)
        transport_request = ArkTransportRequest(
            method="POST",
            path=self._contract.provider.endpoint_path,
            body=request_body,
            deadline_unix_ms=attempt.deadline_unix_ms,
            timeout_ms=attempt.deadline_unix_ms - attempt.started_unix_ms,
        )
        with self._lock:
            if self._used:
                raise ArkInvocationError("accuracy_v1 physical slot is already consumed")
            self._used = True
        try:
            transport_result = self._transport.send(transport_request)
        except Exception:
            # Deliberately do not stringify or chain a transport exception: it
            # may contain Authorization headers or a request/response body.
            if self._contract.provider.require_transport_receipt:
                return self._unaudited_transport_error(
                    attempt=attempt,
                    request_body=request_body,
                    completed_unix_ms=attempt.started_unix_ms,
                )
            with self._lock:
                self._physical_attempts += 1
            return self._closed_response(
                attempt=attempt,
                request_body=request_body,
                completed_unix_ms=attempt.started_unix_ms,
                physical_attempts=1,
                transport_receipt=None,
                outcome=ArkClosedOutcome.TRANSPORT_ERROR,
                http_status=None,
            )

        transport_receipt: object | None = None
        physical_attempts = 1
        if self._contract.provider.require_transport_receipt:
            try:
                from .ark_https_transport import (
                    ArkOneShotTransportFailure,
                    ArkOneShotTransportReceipt,
                    ArkOneShotTransportSuccess,
                )

                if not isinstance(
                    transport_result,
                    (ArkOneShotTransportSuccess, ArkOneShotTransportFailure),
                ):
                    raise ArkBindingError("transport did not return a typed one-shot result")
                transport_receipt = ArkOneShotTransportReceipt.from_mapping(
                    to_primitive(transport_result.receipt)
                )
                physical_attempts = transport_receipt.request_calls
                if (
                    transport_receipt.profile_hash
                    != self._contract.provider.transport_profile_hash
                    or transport_receipt.request_body_sha256
                    != hashlib.sha256(request_body).hexdigest()
                    or transport_receipt.request_body_bytes != len(request_body)
                    or transport_receipt.started_unix_ms < attempt.started_unix_ms
                    or transport_receipt.request_target
                    != "/api/plan/v3" + self._contract.provider.endpoint_path
                ):
                    raise ArkBindingError(
                        "typed one-shot receipt differs from the frozen request"
                    )
            except Exception:
                return self._unaudited_transport_error(
                    attempt=attempt,
                    request_body=request_body,
                    completed_unix_ms=attempt.started_unix_ms,
                )
            with self._lock:
                self._physical_attempts += physical_attempts
            if isinstance(transport_result, ArkOneShotTransportFailure):
                return self._closed_response(
                    attempt=attempt,
                    request_body=request_body,
                    completed_unix_ms=transport_receipt.completed_unix_ms,
                    physical_attempts=physical_attempts,
                    transport_receipt=transport_receipt,
                    outcome=ArkClosedOutcome.TRANSPORT_ERROR,
                    http_status=None,
                )
            transport_response = transport_result.response
        else:
            with self._lock:
                self._physical_attempts += 1
            transport_response = transport_result

        if not isinstance(transport_response, ArkTransportResponse):
            return self._closed_response(
                attempt=attempt,
                request_body=request_body,
                completed_unix_ms=attempt.started_unix_ms,
                physical_attempts=physical_attempts,
                transport_receipt=transport_receipt,
                outcome=ArkClosedOutcome.TRANSPORT_ERROR,
                http_status=None,
            )
        completed = transport_response.completed_unix_ms
        if isinstance(completed, bool) or not isinstance(completed, int) or completed < attempt.started_unix_ms:
            completed = attempt.started_unix_ms
            invalid_transport_time = True
        else:
            invalid_transport_time = False
        raw = transport_response.body
        status_code = transport_response.status_code
        if (
            isinstance(status_code, bool)
            or not isinstance(status_code, int)
            or not 100 <= status_code <= 599
        ):
            return self._closed_response(
                attempt=attempt,
                request_body=request_body,
                completed_unix_ms=completed,
                physical_attempts=physical_attempts,
                transport_receipt=transport_receipt,
                outcome=ArkClosedOutcome.INVALID_RESPONSE,
                http_status=None,
                raw_response=raw,
            )
        if status_code != 200:
            return self._closed_response(
                attempt=attempt,
                request_body=request_body,
                completed_unix_ms=completed,
                physical_attempts=physical_attempts,
                transport_receipt=transport_receipt,
                outcome=ArkClosedOutcome.HTTP_ERROR,
                http_status=status_code,
                raw_response=raw,
            )
        if (
            invalid_transport_time
            or not isinstance(transport_response.content_type, str)
            or transport_response.content_type.split(";", 1)[0].strip().lower()
            != "application/json"
            or len(raw) > self._contract.provider.max_raw_response_bytes
        ):
            return self._closed_response(
                attempt=attempt,
                request_body=request_body,
                completed_unix_ms=completed,
                physical_attempts=physical_attempts,
                transport_receipt=transport_receipt,
                outcome=ArkClosedOutcome.INVALID_RESPONSE,
                http_status=200,
                raw_response=raw,
            )

        raw_hash = hashlib.sha256(raw).hexdigest()
        try:
            _reject_secret_bytes(raw)
            envelope = strict_json_loads(raw)
            if not isinstance(envelope, Mapping):
                raise ArkBindingError("invalid response envelope")
            if not set(envelope).issubset(_RESPONSE_TOP_LEVEL_KEYS):
                raise ArkBindingError("invalid response envelope")
            required = {"id", "model", "object", "output", "status", "store"}
            if not required.issubset(envelope):
                raise ArkBindingError("invalid response envelope")
            if (
                envelope["object"] != "response"
                or envelope["status"] != "completed"
                or envelope["store"] is not False
                or envelope.get("error") is not None
                or envelope.get("incomplete_details") is not None
                or envelope.get("previous_response_id") is not None
                or ("tools" in envelope and envelope["tools"] != [])
            ):
                raise ArkBindingError("invalid response envelope")
            response_id = envelope["id"]
            if (
                not isinstance(response_id, str)
                or not response_id
                or len(response_id) > 512
                or any(ord(char) < 32 for char in response_id)
            ):
                raise ArkBindingError("invalid response envelope")
            _reject_secret_bytes(response_id.encode("utf-8"))
            resolved_model = envelope["model"]
            _require_safe_model(resolved_model, "resolved model ID")
            resolved_model_hash = canonical_sha256({"resolved_model_id": resolved_model})
            response_id_hash = hashlib.sha256(response_id.encode("utf-8")).hexdigest()
            if envelope.get("usage") is None:
                input_tokens = output_tokens = total_tokens = None
                usage_hash = None
                usage_payload = None
            else:
                usage_payload = to_primitive(envelope["usage"])
                input_tokens, output_tokens, total_tokens, usage_hash = _extract_usage(
                    usage_payload, requested_tokens=attempt.requested_tokens
                )
            if resolved_model != self._contract.model.requested_model_id:
                return self._closed_response(
                    attempt=attempt,
                    request_body=request_body,
                    completed_unix_ms=completed,
                    physical_attempts=physical_attempts,
                    transport_receipt=transport_receipt,
                    outcome=ArkClosedOutcome.MODEL_MISMATCH,
                    http_status=200,
                    status=AttemptStatus.MODEL_MISMATCH,
                    resolved_model_id=resolved_model,
                    resolved_model_hash=resolved_model_hash,
                    raw_response=raw,
                    provider_response_id_sha256=response_id_hash,
                    usage=usage_payload,
                    usage_sha256=usage_hash,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
            output_text = _extract_output_text(envelope)
            decision = strict_json_loads(output_text)
            _validate_local_schema(decision, self._contract.response_schema)
            canonical_decision = canonical_bytes(decision)
            _reject_secret_bytes(canonical_decision)
        except (ArkBindingError, StrictJSONError, TypeError, ValueError, OverflowError):
            return self._closed_response(
                attempt=attempt,
                request_body=request_body,
                completed_unix_ms=completed,
                physical_attempts=physical_attempts,
                transport_receipt=transport_receipt,
                outcome=ArkClosedOutcome.INVALID_RESPONSE,
                http_status=200,
                raw_response=raw,
            )

        outcome = (
            ArkClosedOutcome.LATE_RESPONSE
            if completed > attempt.deadline_unix_ms
            else ArkClosedOutcome.SUCCESS
        )
        audit = self._audit(
            attempt=attempt,
            request_body=request_body,
            completed_unix_ms=completed,
            physical_attempts=physical_attempts,
            transport_receipt=transport_receipt,
            outcome=outcome,
            http_status=200,
            resolved_model_id=resolved_model,
            resolved_model_hash=resolved_model_hash,
            raw_response=raw,
            provider_response_id_sha256=response_id_hash,
            response_content_sha256=hashlib.sha256(canonical_decision).hexdigest(),
            usage=usage_payload,
            usage_sha256=usage_hash,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        # raw_hash is recomputed by _audit; retaining this assertion makes the
        # raw-response binding mechanically explicit at the accept boundary.
        if audit.raw_response_sha256 != raw_hash:
            raise AssertionError("raw response hash binding failed")
        evidence = ArkProviderEvidenceEnvelope(
            policy=self._policy,
            budget=self._budget,
            request_contract=self._contract,
            binding_manifest=self._binding_manifest,
            invocation_audit=audit,
        )
        return AuditedProviderResponse(
            status=AttemptStatus.SUCCESS,
            completed_unix_ms=completed,
            response_text=canonical_decision.decode("utf-8"),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider_response_id=None,
            provider_response_id_sha256=response_id_hash,
            observed_model_hash=resolved_model_hash,
            error_code=None,
            late=completed > attempt.deadline_unix_ms,
            audit=audit,
            evidence=evidence,
            ephemeral_request_body_sha256=hashlib.sha256(request_body).hexdigest(),
            ephemeral_raw_response_sha256=raw_hash,
            ephemeral_response_content_sha256=hashlib.sha256(canonical_decision).hexdigest(),
            ephemeral_provider_response_id_sha256=response_id_hash,
        )


__all__ = [
    "ArkCapabilitySnapshot",
    "ArkBindingManifest",
    "ArkBindingError",
    "ArkClosedOutcome",
    "ArkDecodeSpec",
    "ArkInvocationAudit",
    "ArkInvocationError",
    "ArkModelRule",
    "ArkPromptSpec",
    "ArkProviderAdapter",
    "ArkProviderEvidenceEnvelope",
    "ArkProviderError",
    "ArkProviderRule",
    "ArkRequestContract",
    "ArkResponseFormat",
    "ArkTransport",
    "ArkTransportRequest",
    "ArkTransportResponse",
    "AuditedProviderResponse",
    "build_binding_manifest",
]
