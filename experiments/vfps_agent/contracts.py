"""Typed, side-effect-free contracts for the mock-only VFPS M0 harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import canonical_bytes, canonical_sha256, scan_forbidden_proxies, to_primitive


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _require_finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


def _is_rul_target(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return "rul" in tuple(part for part in normalized.split("_") if part)


def _freeze_json(value: Any) -> Any:
    """Detach JSON-like data from caller-owned mutable containers."""

    primitive = to_primitive(value)

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(primitive)


def _freeze_mapping(value: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return frozen


class ProtocolId(str, Enum):
    ACCURACY_V1 = "accuracy_v1"
    RESILIENCE_V1 = "resilience_v1"


class PacketKind(str, Enum):
    RAW = "raw"
    HYBRID = "hybrid"


class ArmId(str, Enum):
    N0 = "N0"
    D1_RAW = "D1-RAW"
    D1_PACKET = "D1-PACKET"
    H1 = "H1"
    RF1 = "RF1"
    RC1 = "RC1"
    ACT1 = "ACT1"
    IF1 = "IF1"
    ACT_COMP96 = "ACT-COMP96"
    ENUM_ACTION = "ENUM-ACTION"
    ENUM_COMP96 = "ENUM-COMP96"


class ResponsePermission(str, Enum):
    NONE = "none"
    DIRECT_BUNDLE = "direct_bundle"
    EMIT_ONLY = "emit_only"
    FUSE_ONLY = "fuse_only"
    CHAMPION_CORRECTION = "champion_correction"
    PRIMARY_ACTION = "primary_action"
    IF_REPRESENTATION = "if_representation"
    COMPOSITIONAL_ACTION = "compositional_action"


class AttemptStatus(str, Enum):
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    LOCAL = "LOCAL"


class UsageStatus(str, Enum):
    REPORTED = "REPORTED"
    UNKNOWN = "UNKNOWN"


class CommitDisposition(str, Enum):
    PREDICTION = "PREDICTION"
    FALLBACK = "FALLBACK"


class ClosedErrorCode(str, Enum):
    """Persistence-safe failure categories; provider text is unrepresentable."""

    PROVIDER_EXCEPTION = "PROVIDER_EXCEPTION"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    LATE_RESPONSE = "LATE_RESPONSE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    CRASH_RECOVERY = "CRASH_RECOVERY"
    BINDING_MISMATCH = "BINDING_MISMATCH"


class CommitReason(str, Enum):
    VERIFIED_RESPONSE = "VERIFIED_RESPONSE"
    NUMERICAL_CHAMPION = "NUMERICAL_CHAMPION"
    ENUMERATED_ACTION = "ENUMERATED_ACTION"
    DELIBERATE_FALLBACK = "DELIBERATE_FALLBACK"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    LATE_RESPONSE = "LATE_RESPONSE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    CRASH_RECOVERY = "CRASH_RECOVERY"
    BINDING_MISMATCH = "BINDING_MISMATCH"


class ExecutionState(str, Enum):
    ACTIVE = "ACTIVE"
    DELIBERATE_FALLBACK = "DELIBERATE_FALLBACK"
    ERROR_FALLBACK = "ERROR_FALLBACK"


class MaturityState(str, Enum):
    MATURED = "MATURED"
    NEVER_MATURED = "NEVER_MATURED"


class LabelScope(str, Enum):
    OUTER_TRAIN_CROSSFIT = "OUTER_TRAIN_CROSSFIT"


@dataclass(frozen=True, slots=True)
class AccuracyBudgetSpec:
    """Hashable resource contract for one ``accuracy_v1`` logical slot."""

    requested_tokens: int
    deadline_ms: int
    physical_calls: int = 1
    retries: int = 0
    schema_version: str = field(default="AccuracyBudgetSpec.v1", init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.requested_tokens, bool)
            or not isinstance(self.requested_tokens, int)
            or self.requested_tokens < 0
        ):
            raise ValueError("requested_tokens must be a non-negative integer")
        if isinstance(self.deadline_ms, bool) or not isinstance(self.deadline_ms, int) or self.deadline_ms <= 0:
            raise ValueError("deadline_ms must be a positive integer")
        if self.physical_calls not in (0, 1) or self.retries != 0:
            raise ValueError("accuracy_v1 permits zero/one physical call and no retry")
        if self.physical_calls == 1 and self.requested_tokens == 0:
            raise ValueError("a physical call requires a positive requested-token ceiling")

    @property
    def budget_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class CausalPacketSchema:
    """Typed field allowlist; no arbitrary packet columns are accepted."""

    measurement_fields: tuple[str, ...]
    missingness_fields: tuple[str, ...]
    schedule_fields: tuple[str, ...] = ()
    normalization_fields: tuple[str, ...] = ()
    condition_fields: tuple[str, ...] = ()
    train_summary_fields: tuple[str, ...] = ()
    diagnostic_fields: tuple[str, ...] = ()
    schema_version: str = field(default="CausalPacketSchema.v1", init=False)

    def __post_init__(self) -> None:
        for name in (
            "measurement_fields",
            "missingness_fields",
            "schedule_fields",
            "normalization_fields",
            "condition_fields",
            "train_summary_fields",
            "diagnostic_fields",
        ):
            values = tuple(getattr(self, name))
            object.__setattr__(self, name, values)
            if values != tuple(sorted(values)) or len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique and canonically sorted")
            if any(not isinstance(item, str) or not item or item.strip() != item for item in values):
                raise ValueError(f"{name} contains an invalid field token")
            scan_forbidden_proxies({"allowlist": list(values)})
        if not self.measurement_fields:
            raise ValueError("at least one measurement field is required")
        if set(self.missingness_fields) != set(self.measurement_fields):
            raise ValueError("missingness allowlist must exactly match measurements")

    @property
    def schema_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class SealedSplitProvenance:
    """Opaque whole-unit split/provenance binding with no private identity."""

    outer_fold_hash: str
    split_manifest_hash: str
    provenance_manifest_hash: str
    outer_train_set_hash: str
    held_out_member_hash: str
    crossfit_manifest_hash: str
    additive_loss_spec_hash: str
    schema_version: str = field(default="SealedSplitProvenance.v1", init=False)

    def __post_init__(self) -> None:
        for name in (
            "outer_fold_hash",
            "split_manifest_hash",
            "provenance_manifest_hash",
            "outer_train_set_hash",
            "held_out_member_hash",
            "crossfit_manifest_hash",
            "additive_loss_spec_hash",
        ):
            _require_sha256(getattr(self, name), name)
        if self.outer_train_set_hash == self.held_out_member_hash:
            raise ValueError("outer training and held-out bindings must be disjoint")

    @property
    def seal_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class ArmSpec:
    arm_id: ArmId
    packet_kind: PacketKind | None
    permission: ResponsePermission
    physical_calls: int

    def __post_init__(self) -> None:
        if not isinstance(self.arm_id, ArmId):
            raise TypeError("arm_id must be ArmId")
        if self.packet_kind is not None and not isinstance(self.packet_kind, PacketKind):
            raise TypeError("packet_kind must be PacketKind or None")
        if not isinstance(self.permission, ResponsePermission):
            raise TypeError("permission must be ResponsePermission")
        if self.physical_calls not in (0, 1):
            raise ValueError("M0 arms permit zero or one physical call")


FROZEN_ARM_SPECS: Mapping[ArmId, ArmSpec] = {
    ArmId.N0: ArmSpec(ArmId.N0, None, ResponsePermission.NONE, 0),
    ArmId.D1_RAW: ArmSpec(ArmId.D1_RAW, PacketKind.RAW, ResponsePermission.DIRECT_BUNDLE, 1),
    ArmId.D1_PACKET: ArmSpec(ArmId.D1_PACKET, PacketKind.HYBRID, ResponsePermission.DIRECT_BUNDLE, 1),
    ArmId.H1: ArmSpec(ArmId.H1, PacketKind.HYBRID, ResponsePermission.EMIT_ONLY, 1),
    ArmId.RF1: ArmSpec(ArmId.RF1, PacketKind.HYBRID, ResponsePermission.FUSE_ONLY, 1),
    ArmId.RC1: ArmSpec(ArmId.RC1, PacketKind.HYBRID, ResponsePermission.CHAMPION_CORRECTION, 1),
    ArmId.ACT1: ArmSpec(ArmId.ACT1, PacketKind.HYBRID, ResponsePermission.PRIMARY_ACTION, 1),
    ArmId.IF1: ArmSpec(ArmId.IF1, PacketKind.HYBRID, ResponsePermission.IF_REPRESENTATION, 1),
    ArmId.ACT_COMP96: ArmSpec(
        ArmId.ACT_COMP96,
        PacketKind.HYBRID,
        ResponsePermission.COMPOSITIONAL_ACTION,
        1,
    ),
    ArmId.ENUM_ACTION: ArmSpec(ArmId.ENUM_ACTION, PacketKind.HYBRID, ResponsePermission.NONE, 0),
    ArmId.ENUM_COMP96: ArmSpec(ArmId.ENUM_COMP96, PacketKind.HYBRID, ResponsePermission.NONE, 0),
}


@dataclass(frozen=True, slots=True)
class ForecastKey:
    target: str
    horizon: int
    unit: str

    def __post_init__(self) -> None:
        if not self.target or not self.unit:
            raise ValueError("forecast target and unit must be non-empty")
        if isinstance(self.horizon, bool) or not isinstance(self.horizon, int) or self.horizon <= 0:
            raise ValueError("forecast horizon must be a positive integer")
        scan_forbidden_proxies({"target": self.target, "measurement_unit": self.unit})

    @property
    def token(self) -> str:
        return f"{self.target}|{self.horizon}|{self.unit}"


@dataclass(frozen=True, slots=True)
class ForecastEstimate:
    key: ForecastKey
    point: float | None
    lower: float | None
    median: float | None
    upper: float | None
    status: str = "NUMERIC"

    def __post_init__(self) -> None:
        if self.status == "RUL_NA":
            if not _is_rul_target(self.key.target) or any(
                value is not None for value in (self.point, self.lower, self.median, self.upper)
            ):
                raise ValueError("RUL_NA is valid only for a RUL key and carries no numbers")
            return
        if self.status != "NUMERIC":
            raise ValueError("forecast status must be NUMERIC or RUL_NA")
        for name in ("point", "lower", "median", "upper"):
            _require_finite(getattr(self, name), name)
        assert self.lower is not None and self.median is not None and self.upper is not None
        if not self.lower <= self.median <= self.upper:
            raise ValueError("forecast quantiles must be monotone")


@dataclass(frozen=True, slots=True)
class CandidateBundle:
    model_id: str
    registry_hash: str
    estimates: tuple[ForecastEstimate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.estimates, tuple) or not all(
            isinstance(item, ForecastEstimate) for item in self.estimates
        ):
            raise TypeError("estimates must be a tuple of ForecastEstimate")
        if not self.model_id or not self.estimates:
            raise ValueError("candidate bundle requires model_id and estimates")
        _require_sha256(self.registry_hash, "registry_hash")
        tokens = [item.key.token for item in self.estimates]
        if len(tokens) != len(set(tokens)):
            raise ValueError("candidate bundle contains duplicate forecast keys")
        scan_forbidden_proxies({"model_id": self.model_id})

    @property
    def bundle_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class RevealedObservation:
    event_index: int
    observed_at: float
    available_at: float
    measurements: Mapping[str, Any]
    missingness: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "measurements", _freeze_mapping(self.measurements, "measurements"))
        object.__setattr__(self, "missingness", _freeze_mapping(self.missingness, "missingness"))
        if isinstance(self.event_index, bool) or not isinstance(self.event_index, int) or self.event_index < 0:
            raise ValueError("event_index must be a non-negative integer")
        _require_finite(self.observed_at, "observed_at")
        _require_finite(self.available_at, "available_at")
        if self.observed_at > self.available_at:
            raise ValueError("observation cannot become available before it is observed")
        scan_forbidden_proxies(self.measurements)
        scan_forbidden_proxies(self.missingness)


@dataclass(frozen=True, slots=True)
class OriginPacketV2:
    """A causal packet whose constructor has no full-series or final-length input."""

    packet_kind: PacketKind
    opaque_origin_hash: str
    availability_cutoff: float
    forecast_keys: tuple[ForecastKey, ...]
    revealed_observations: tuple[RevealedObservation, ...]
    known_schedule: tuple[Mapping[str, Any], ...] = ()
    normalization: Mapping[str, Any] = field(default_factory=dict)
    allowed_conditions: Mapping[str, Any] = field(default_factory=dict)
    candidate_bundles: tuple[CandidateBundle, ...] = ()
    train_error_summaries: Mapping[str, Any] = field(default_factory=dict)
    diagnostic_bins: Mapping[str, Any] = field(default_factory=dict)
    action_manifest_hash: str | None = None
    predicate_manifest_hash: str | None = None
    registry_hash: str | None = None
    fallback_bundle_hash: str | None = None
    causal_schema_hash: str | None = None
    outer_fold_hash: str | None = None
    split_manifest_hash: str | None = None
    provenance_manifest_hash: str | None = None
    outer_train_set_hash: str | None = None
    held_out_member_hash: str | None = None
    crossfit_manifest_hash: str | None = None
    additive_loss_spec_hash: str | None = None
    packet_context_hash: str | None = None
    origin_event_index: int | None = None
    schema_version: str = field(default="OriginPacketV2", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.packet_kind, PacketKind):
            raise TypeError("packet_kind must be PacketKind")
        if not isinstance(self.forecast_keys, tuple) or not all(
            isinstance(item, ForecastKey) for item in self.forecast_keys
        ):
            raise TypeError("forecast_keys must be a tuple of ForecastKey")
        if not isinstance(self.revealed_observations, tuple) or not all(
            isinstance(item, RevealedObservation) for item in self.revealed_observations
        ):
            raise TypeError("revealed_observations must be a tuple of RevealedObservation")
        if not isinstance(self.candidate_bundles, tuple) or not all(
            isinstance(item, CandidateBundle) for item in self.candidate_bundles
        ):
            raise TypeError("candidate_bundles must be a tuple of CandidateBundle")
        if not isinstance(self.known_schedule, tuple) or not all(
            isinstance(item, Mapping) for item in self.known_schedule
        ):
            raise TypeError("known_schedule must be a tuple of mappings")
        object.__setattr__(self, "known_schedule", tuple(
            _freeze_mapping(item, "known_schedule item") for item in self.known_schedule
        ))
        for name in ("normalization", "allowed_conditions", "train_error_summaries", "diagnostic_bins"):
            object.__setattr__(self, name, _freeze_mapping(getattr(self, name), name))
        _require_sha256(self.opaque_origin_hash, "opaque_origin_hash")
        _require_finite(self.availability_cutoff, "availability_cutoff")
        if not self.forecast_keys or not self.revealed_observations:
            raise ValueError("packet requires forecast keys and a revealed prefix")
        if self.origin_event_index is not None:
            if (
                isinstance(self.origin_event_index, bool)
                or not isinstance(self.origin_event_index, int)
                or self.origin_event_index < 0
            ):
                raise ValueError("origin_event_index must be a non-negative integer")
            if self.revealed_observations[-1].event_index != self.origin_event_index:
                raise ValueError("origin_event_index must equal the final revealed event")
        key_tokens = [item.token for item in self.forecast_keys]
        if len(key_tokens) != len(set(key_tokens)):
            raise ValueError("packet contains duplicate forecast keys")
        event_indices = [item.event_index for item in self.revealed_observations]
        if event_indices != sorted(event_indices) or len(event_indices) != len(set(event_indices)):
            raise ValueError("revealed observations must have unique chronological event indices")
        observed_times = [float(item.observed_at) for item in self.revealed_observations]
        available_times = [float(item.available_at) for item in self.revealed_observations]
        if observed_times != sorted(observed_times) or available_times != sorted(available_times):
            raise ValueError("revealed observations must be chronological on both time axes")
        for observation in self.revealed_observations:
            if observation.available_at > self.availability_cutoff:
                raise ValueError("revealed observation is unavailable at the origin cutoff")
        for item in self.known_schedule:
            scan_forbidden_proxies(item)
        scan_forbidden_proxies(self.normalization)
        scan_forbidden_proxies(self.allowed_conditions)
        scan_forbidden_proxies(self.train_error_summaries)
        scan_forbidden_proxies(self.diagnostic_bins)

        hybrid_hashes = (
            self.action_manifest_hash,
            self.predicate_manifest_hash,
            self.registry_hash,
            self.fallback_bundle_hash,
        )
        if self.packet_kind is PacketKind.RAW:
            if self.candidate_bundles or any(value is not None for value in hybrid_hashes):
                raise ValueError("raw packet cannot contain hybrid authority fields")
        else:
            if not self.candidate_bundles or any(value is None for value in hybrid_hashes):
                raise ValueError("hybrid packet requires candidates and every frozen manifest hash")
            for name, value in zip(
                ("action_manifest_hash", "predicate_manifest_hash", "registry_hash", "fallback_bundle_hash"),
                hybrid_hashes,
            ):
                _require_sha256(value or "", name)
            if any(bundle.registry_hash != self.registry_hash for bundle in self.candidate_bundles):
                raise ValueError("candidate registry hash does not match packet registry")
            expected_tokens = set(key_tokens)
            if any(
                {estimate.key.token for estimate in bundle.estimates} != expected_tokens
                for bundle in self.candidate_bundles
            ):
                raise ValueError("each candidate bundle must cover every planned forecast key exactly once")

        m2_hashes = (
            self.causal_schema_hash,
            self.outer_fold_hash,
            self.split_manifest_hash,
            self.provenance_manifest_hash,
            self.outer_train_set_hash,
            self.held_out_member_hash,
            self.crossfit_manifest_hash,
            self.additive_loss_spec_hash,
            self.packet_context_hash,
        )
        if any(value is not None for value in m2_hashes):
            if any(value is None for value in m2_hashes):
                raise ValueError("M2 causal packet bindings must be present as one complete set")
            for name, value in zip(
                (
                    "causal_schema_hash",
                    "outer_fold_hash",
                    "split_manifest_hash",
                    "provenance_manifest_hash",
                    "outer_train_set_hash",
                    "held_out_member_hash",
                    "crossfit_manifest_hash",
                    "additive_loss_spec_hash",
                    "packet_context_hash",
                ),
                m2_hashes,
            ):
                _require_sha256(value or "", name)
            if self.outer_train_set_hash == self.held_out_member_hash:
                raise ValueError("outer training and held-out packet bindings must be disjoint")

        # Scan the fully materialized packet too, including structural keys and
        # string values introduced by nested typed objects.
        scan_forbidden_proxies(self.payload())

    def payload(self) -> Mapping[str, Any]:
        return to_primitive(self)

    @property
    def packet_bytes(self) -> bytes:
        return canonical_bytes(self.payload())

    @property
    def packet_hash(self) -> str:
        return canonical_sha256(self.payload())


@dataclass(frozen=True, slots=True)
class PolicySpec:
    policy_id: str
    generation: int
    protocol: ProtocolId
    arm: ArmId
    provider_rule_hash: str
    model_version_rule_hash: str
    prompt_hash: str
    packet_schema_hash: str
    response_schema_hash: str
    grammar_hash: str
    registry_hash: str
    decode_parameters_hash: str
    one_call_budget_hash: str
    verifier_hash: str
    fallback_hash: str
    capability_snapshot_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, ProtocolId):
            raise TypeError("protocol must be ProtocolId")
        if not isinstance(self.arm, ArmId):
            raise TypeError("arm must be ArmId")
        if not self.policy_id:
            raise ValueError("policy_id must be non-empty")
        if isinstance(self.generation, bool) or not isinstance(self.generation, int) or self.generation < 1:
            raise ValueError("policy generation must be positive")
        for name in (
            "provider_rule_hash", "model_version_rule_hash", "prompt_hash", "packet_schema_hash",
            "response_schema_hash", "grammar_hash", "registry_hash", "decode_parameters_hash",
            "one_call_budget_hash", "verifier_hash", "fallback_hash", "capability_snapshot_hash",
        ):
            _require_sha256(getattr(self, name), name)
        if self.protocol is ProtocolId.ACCURACY_V1 and FROZEN_ARM_SPECS[self.arm].physical_calls > 1:
            raise ValueError("accuracy_v1 forbids retry or multiple physical calls")
        scan_forbidden_proxies({"policy_id": self.policy_id})

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class AttemptStart:
    attempt_id: str
    policy_hash: str
    origin_hash: str
    packet_hash: str
    arm: ArmId
    protocol: ProtocolId
    physical_slot: int
    requested_tokens: int
    deadline_unix_ms: int
    started_unix_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.arm, ArmId):
            raise TypeError("arm must be ArmId")
        if not isinstance(self.protocol, ProtocolId):
            raise TypeError("protocol must be ProtocolId")
        if not self.attempt_id:
            raise ValueError("attempt_id must be non-empty")
        for name in ("policy_hash", "origin_hash", "packet_hash"):
            _require_sha256(getattr(self, name), name)
        expected_calls = FROZEN_ARM_SPECS[self.arm].physical_calls
        if self.protocol is ProtocolId.ACCURACY_V1:
            expected_slot = 0 if expected_calls == 1 else -1
            if self.physical_slot != expected_slot:
                raise ValueError("accuracy_v1 physical slot differs from the frozen arm budget")
        if expected_calls == 1 and self.requested_tokens <= 0:
            raise ValueError("physical attempts require positive requested_tokens")
        if expected_calls == 0 and self.requested_tokens != 0:
            raise ValueError("local arms require requested_tokens=0")
        if self.deadline_unix_ms <= self.started_unix_ms:
            raise ValueError("deadline must be after attempt start")


@dataclass(frozen=True, slots=True)
class AttemptResult:
    attempt_id: str
    status: AttemptStatus
    completed_unix_ms: int
    usage_status: UsageStatus
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_response_id_hash: str | None = None
    error_code: ClosedErrorCode | None = None
    observed_model_hash: str | None = None
    late: bool = False
    provider_evidence: Mapping[str, Any] | None = None
    provider_evidence_hash: str | None = None

    def __post_init__(self) -> None:
        if self.provider_evidence is not None:
            object.__setattr__(
                self,
                "provider_evidence",
                _freeze_mapping(self.provider_evidence, "provider_evidence"),
            )
        if not isinstance(self.status, AttemptStatus):
            raise TypeError("status must be AttemptStatus")
        if not isinstance(self.usage_status, UsageStatus):
            raise TypeError("usage_status must be UsageStatus")
        if self.error_code is not None and not isinstance(self.error_code, ClosedErrorCode):
            raise TypeError("error_code must use the closed persistence enum")
        if not self.attempt_id:
            raise ValueError("attempt_id must be non-empty")
        if self.completed_unix_ms < 0:
            raise ValueError("completed_unix_ms must be non-negative")
        if self.usage_status is UsageStatus.UNKNOWN:
            if self.input_tokens is not None or self.output_tokens is not None:
                raise ValueError("unknown usage must not be represented as measured tokens")
        else:
            if self.input_tokens is None or self.output_tokens is None:
                raise ValueError("reported usage requires both token counts")
            if self.input_tokens < 0 or self.output_tokens < 0:
                raise ValueError("token counts must be non-negative")
        for name in (
            "provider_response_id_hash",
            "observed_model_hash",
            "provider_evidence_hash",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_sha256(value, name)
        if (self.provider_evidence is None) != (self.provider_evidence_hash is None):
            raise ValueError("provider evidence and its hash must be present together")
        if self.provider_evidence is not None:
            if canonical_sha256(self.provider_evidence) != self.provider_evidence_hash:
                raise ValueError("provider_evidence_hash does not bind provider_evidence")
            scan_forbidden_proxies(self.provider_evidence)


@dataclass(frozen=True, slots=True)
class PredictionCommit:
    commit_id: str
    attempt_id: str
    started_record_hash: str
    policy_hash: str
    origin_hash: str
    packet_hash: str
    disposition: CommitDisposition
    prediction: Mapping[str, Any]
    prediction_hash: str
    committed_unix_ms: int
    reason_code: CommitReason
    late_response_ignored: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "prediction", _freeze_mapping(self.prediction, "prediction"))
        if not isinstance(self.disposition, CommitDisposition):
            raise TypeError("disposition must be CommitDisposition")
        if not self.commit_id or not self.attempt_id:
            raise ValueError("commit identifiers and reason_code must be non-empty")
        if not isinstance(self.reason_code, CommitReason):
            raise TypeError("reason_code must use the closed persistence enum")
        for name in ("started_record_hash", "policy_hash", "origin_hash", "packet_hash", "prediction_hash"):
            _require_sha256(getattr(self, name), name)
        if canonical_sha256(self.prediction) != self.prediction_hash:
            raise ValueError("prediction_hash does not bind the committed prediction")
        expected_commit_id = canonical_sha256(
            {
                "attempt_id": self.attempt_id,
                "started_record_hash": self.started_record_hash,
                "policy_hash": self.policy_hash,
                "origin_hash": self.origin_hash,
                "packet_hash": self.packet_hash,
                "disposition": self.disposition.value,
                "prediction_hash": self.prediction_hash,
                "committed_unix_ms": self.committed_unix_ms,
                "reason_code": self.reason_code.value,
                "late_response_ignored": self.late_response_ignored,
            }
        )
        if self.commit_id != expected_commit_id:
            raise ValueError("commit_id does not bind the complete prediction commit")
        scan_forbidden_proxies(self.prediction)
        if self.late_response_ignored and self.disposition is not CommitDisposition.FALLBACK:
            raise ValueError("a late provider response may only commit fallback")


@dataclass(frozen=True, slots=True)
class PlannedKeyExecution:
    key_token: str
    execution_state: ExecutionState
    forecast_status: str
    forecast_hash: str
    selected_action_hash: str | None
    forced_rul_na: bool
    active_coverage_eligible: bool

    def __post_init__(self) -> None:
        if not self.key_token or not isinstance(self.execution_state, ExecutionState):
            raise ValueError("planned key execution requires a key and closed execution state")
        if self.forecast_status not in {"NUMERIC", "RUL_NA"}:
            raise ValueError("forecast_status must use the closed forecast enum")
        if not isinstance(self.forced_rul_na, bool) or not isinstance(
            self.active_coverage_eligible, bool
        ):
            raise TypeError("execution coverage flags must be booleans")
        _require_sha256(self.forecast_hash, "forecast_hash")
        if self.selected_action_hash is not None:
            _require_sha256(self.selected_action_hash, "selected_action_hash")
        if self.forced_rul_na:
            if self.forecast_status != "RUL_NA" or self.active_coverage_eligible:
                raise ValueError("forced RUL_NA must be excluded from active coverage")
        elif self.forecast_status == "RUL_NA":
            raise ValueError("every RUL_NA execution must be marked forced")
        if self.execution_state is not ExecutionState.ACTIVE and self.active_coverage_eligible:
            raise ValueError("fallback states cannot count toward active coverage")


@dataclass(frozen=True, slots=True)
class KeyMaturity:
    key_token: str
    maturity_state: MaturityState
    execution_record_hash: str
    label_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.key_token or not isinstance(self.maturity_state, MaturityState):
            raise ValueError("key maturity requires a key and closed maturity state")
        _require_sha256(self.execution_record_hash, "execution_record_hash")
        if self.maturity_state is MaturityState.MATURED:
            _require_sha256(self.label_hash or "", "label_hash")
        elif self.label_hash is not None:
            raise ValueError("NEVER_MATURED carries no fabricated label")
