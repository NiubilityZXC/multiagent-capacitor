"""Typed, durable CAP-ACT M2 execution path.

This is the only path intended for future accuracy experiments.  It binds a
causal packet, frozen policy, numerical/action registry and one-call budget
*before* a provider can be invoked.  Every raw provider response is ephemeral;
only a verified forecast bundle, closed status codes, hashes, reported usage,
and a typed secret-free binding record are persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

from .actions import BaseOperator
from .arms import ArmExecution, FROZEN_CAP_ARM_SPECS, execute_arm
from .canonical import (
    canonical_bytes,
    canonical_sha256,
    scan_forbidden_proxies,
    strict_json_loads,
    to_primitive,
)
from .contracts import (
    AccuracyBudgetSpec,
    ArmId,
    AttemptResult,
    AttemptStart,
    AttemptStatus,
    CausalPacketSchema,
    ClosedErrorCode,
    CommitDisposition,
    CommitReason,
    ExecutionState,
    ForecastEstimate,
    OriginPacketV2,
    PacketKind,
    PlannedKeyExecution,
    PolicySpec,
    PredictionCommit,
    ProtocolId,
    RevealedObservation,
    SealedSplitProvenance,
    UsageStatus,
)
from .ledger import (
    CanonicalJSONLLedger,
    LedgerIntegrityError,
    LedgerKind,
    read_verified_ledger_records,
    verify_ledger,
)
from .provider import AccuracyProvider, ProviderResponse
from .registry import CAPActionRegistry, ForecastBundle, ForecastStatus, ForecastValue


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CAP_M2_VERIFIER_HASH = canonical_sha256(
    {
        "schema_version": "CAPTypedAccuracyRunner.v3",
        "bindings": [
            "policy",
            "packet",
            "causal_schema",
            "split_provenance",
            "registry",
            "action_manifest",
            "fallback",
            "budget",
        ],
        "attempts": "accuracy_v1_one_physical_attempt_no_retry",
        "commit": "started_finished_prediction_execution_checkpoint",
        "semantic_validation": "exact_prediction_bundle_certificate_and_key_rows",
        "provider_persistence": "closed_status_hashes_usage_and_typed_safe_evidence_only",
        "provider_audit": "typed_secret_free_request_response_evidence_in_finished_record",
    }
)


class CAPM2Error(RuntimeError):
    """A formal M2 binding, recovery, or cross-ledger invariant failed."""


def _require_hash(value: str | None, name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise CAPM2Error(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_exact_fields(value: Mapping[str, Any], fields: Sequence[str], name: str) -> None:
    if set(value) != set(fields):
        raise CAPM2Error(f"{name} differs from the frozen causal allowlist")


def _candidate_from_bundle(bundle: ForecastBundle, registry_hash: str):
    from .contracts import CandidateBundle

    estimates: list[ForecastEstimate] = []
    for forecast in bundle.forecasts:
        if forecast.status is ForecastStatus.RUL_NA:
            estimates.append(ForecastEstimate(forecast.key, None, None, None, None, "RUL_NA"))
        else:
            estimates.append(
                ForecastEstimate(
                    forecast.key,
                    forecast.point,
                    forecast.lower,
                    forecast.median,
                    forecast.upper,
                )
            )
    return CandidateBundle(bundle.bundle_id, registry_hash, tuple(estimates))


def build_causal_packet(
    *,
    packet_kind: PacketKind,
    origin_event_index: int,
    availability_cutoff: float,
    revealed_observations: Sequence[RevealedObservation],
    causal_schema: CausalPacketSchema,
    split: SealedSplitProvenance,
    registry: CAPActionRegistry,
    known_schedule: Sequence[Mapping[str, Any]] = (),
    normalization: Mapping[str, Any] | None = None,
    allowed_conditions: Mapping[str, Any] | None = None,
    train_error_summaries: Mapping[str, Any] | None = None,
    diagnostic_bins: Mapping[str, Any] | None = None,
) -> OriginPacketV2:
    """Build a packet from an already revealed prefix only.

    There is intentionally no argument for a full series, final length,
    termination record, private unit identifier, or held-out loss.  The opaque
    origin hash is derived from sealed split lineage and the causal cutoff.
    """

    observations = tuple(revealed_observations)
    if not observations or observations[-1].event_index != origin_event_index:
        raise CAPM2Error("origin must be the final event in the revealed prefix")
    for observation in observations:
        _require_exact_fields(observation.measurements, causal_schema.measurement_fields, "measurements")
        _require_exact_fields(observation.missingness, causal_schema.missingness_fields, "missingness")
    schedule = tuple(dict(item) for item in known_schedule)
    for item in schedule:
        _require_exact_fields(item, causal_schema.schedule_fields, "known schedule")
    normalization_value = dict(normalization or {})
    conditions_value = dict(allowed_conditions or {})
    train_value = dict(train_error_summaries or {})
    diagnostic_value = dict(diagnostic_bins or {})
    _require_exact_fields(normalization_value, causal_schema.normalization_fields, "normalization")
    _require_exact_fields(conditions_value, causal_schema.condition_fields, "conditions")
    _require_exact_fields(train_value, causal_schema.train_summary_fields, "train summaries")
    _require_exact_fields(diagnostic_value, causal_schema.diagnostic_fields, "diagnostics")
    for value in (schedule, normalization_value, conditions_value, train_value, diagnostic_value):
        scan_forbidden_proxies(value)

    key_tokens = tuple(item.token for item in registry.numerical.planned_keys)
    prefix_hash = canonical_sha256(
        {
            "schema_hash": causal_schema.schema_hash,
            "observations": observations,
            "schedule": schedule,
            "normalization": normalization_value,
            "conditions": conditions_value,
        }
    )
    origin_hash = canonical_sha256(
        {
            "outer_fold_hash": split.outer_fold_hash,
            "split_manifest_hash": split.split_manifest_hash,
            "held_out_member_hash": split.held_out_member_hash,
            "origin_event_index": origin_event_index,
            "availability_cutoff": availability_cutoff,
            "forecast_keys": key_tokens,
            "prefix_hash": prefix_hash,
        }
    )
    context_hash = canonical_sha256(
        {
            "prefix_hash": prefix_hash,
            "diagnostic_bins": diagnostic_value,
            "feature_registry_hash": registry.features.feature_registry_hash,
            "crossfit_manifest_hash": split.crossfit_manifest_hash,
        }
    )
    hybrid = packet_kind is PacketKind.HYBRID
    candidates = (
        tuple(_candidate_from_bundle(bundle, registry.registry_hash) for bundle in registry.numerical.model_bundles)
        if hybrid
        else ()
    )
    return OriginPacketV2(
        packet_kind=packet_kind,
        opaque_origin_hash=origin_hash,
        availability_cutoff=availability_cutoff,
        forecast_keys=registry.numerical.planned_keys,
        revealed_observations=observations,
        known_schedule=schedule,
        normalization=normalization_value,
        allowed_conditions=conditions_value,
        candidate_bundles=candidates,
        train_error_summaries=train_value,
        diagnostic_bins=diagnostic_value,
        action_manifest_hash=registry.action_manifest_hash if hybrid else None,
        predicate_manifest_hash=registry.features.feature_registry_hash if hybrid else None,
        registry_hash=registry.registry_hash if hybrid else None,
        fallback_bundle_hash=registry.numerical.fallback_bundle.bundle_hash if hybrid else None,
        causal_schema_hash=causal_schema.schema_hash,
        outer_fold_hash=split.outer_fold_hash,
        split_manifest_hash=split.split_manifest_hash,
        provenance_manifest_hash=split.provenance_manifest_hash,
        outer_train_set_hash=split.outer_train_set_hash,
        held_out_member_hash=split.held_out_member_hash,
        crossfit_manifest_hash=split.crossfit_manifest_hash,
        additive_loss_spec_hash=split.additive_loss_spec_hash,
        packet_context_hash=context_hash,
        origin_event_index=origin_event_index,
    )


@dataclass(frozen=True, slots=True)
class CAPRunPaths:
    root: Path

    @property
    def attempt(self) -> Path:
        return self.root / "ATTEMPT_LEDGER.jsonl"

    @property
    def prediction(self) -> Path:
        return self.root / "PREDICTION_LEDGER.jsonl"

    @property
    def execution(self) -> Path:
        return self.root / "EXECUTION_LEDGER.jsonl"

    @property
    def checkpoint(self) -> Path:
        return self.root / "CHECKPOINT_LEDGER.jsonl"

    @property
    def access(self) -> Path:
        return self.root / "ACCESS_LEDGER.jsonl"

    @property
    def maturity(self) -> Path:
        return self.root / "MATURITY_LEDGER.jsonl"

    def ledger_path(self, kind: LedgerKind) -> Path:
        return {
            LedgerKind.ATTEMPT: self.attempt,
            LedgerKind.PREDICTION: self.prediction,
            LedgerKind.EXECUTION: self.execution,
            LedgerKind.CHECKPOINT: self.checkpoint,
            LedgerKind.ACCESS: self.access,
            LedgerKind.MATURITY: self.maturity,
        }[kind]

    def seal_path(self, kind: LedgerKind) -> Path:
        return self.root / f"{kind.value.upper()}_LEDGER.seal.json"

    @property
    def prediction_phase_seal(self) -> Path:
        return self.root / "PREDICTION_PHASE_SEAL.json"

    @property
    def final_run_seal(self) -> Path:
        return self.root / "RUN_SEAL.json"


@dataclass(frozen=True, slots=True)
class TypedOriginResult:
    attempt: AttemptResult
    commit: PredictionCommit
    prediction_record_hash: str
    execution_record_hashes: tuple[tuple[str, str], ...]
    checkpoint_record_hash: str
    provider_called: bool
    recovered_without_resend: bool


def _ensure_directory(path: Path, *, resume: bool) -> None:
    if path.exists():
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise CAPM2Error("run output must be a regular directory, never a symlink")
        if not resume and any(path.iterdir()):
            raise CAPM2Error("new run output directory must be empty")
    else:
        path.mkdir(parents=False, mode=0o700)


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> str:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise CAPM2Error("refusing pre-existing or unsafe seal artifact") from exc
    raw = canonical_bytes(payload)
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise CAPM2Error("short canonical seal write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return hashlib.sha256(raw).hexdigest()


def _read_regular(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise CAPM2Error("required run artifact is missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise CAPM2Error("run artifact must be a regular non-symlink file")
    flags = os.O_RDONLY | (getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(path, flags)
    try:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _artifact_hash(path: Path) -> str:
    return hashlib.sha256(_read_regular(path)).hexdigest()


def _validate_bindings(
    *,
    policy: PolicySpec,
    packet: OriginPacketV2,
    registry: CAPActionRegistry,
    budget: AccuracyBudgetSpec,
) -> None:
    if policy.protocol is not ProtocolId.ACCURACY_V1:
        raise CAPM2Error("formal runner accepts accuracy_v1 only")
    if policy.arm not in FROZEN_CAP_ARM_SPECS:
        raise CAPM2Error("arm is not implemented by the typed CAP registry")
    arm = FROZEN_CAP_ARM_SPECS[policy.arm]
    if arm.packet_kind is not None and arm.packet_kind is not packet.packet_kind:
        raise CAPM2Error("arm and causal packet kind differ")
    if budget.physical_calls != arm.physical_calls or budget.retries != 0:
        raise CAPM2Error("budget differs from the frozen arm call envelope")
    if policy.one_call_budget_hash != budget.budget_hash:
        raise CAPM2Error("policy does not bind the supplied one-call budget")
    if policy.verifier_hash != CAP_M2_VERIFIER_HASH:
        raise CAPM2Error("policy does not bind the M2 verifier contract")
    if policy.registry_hash != registry.registry_hash:
        raise CAPM2Error("policy registry hash differs from the executable registry")
    if policy.grammar_hash != registry.action_manifest_hash:
        raise CAPM2Error("policy grammar hash differs from the executable action manifest")
    if policy.fallback_hash != registry.numerical.fallback_bundle.bundle_hash:
        raise CAPM2Error("policy fallback hash differs from the common N0 bundle")
    if packet.causal_schema_hash is None or policy.packet_schema_hash != packet.causal_schema_hash:
        raise CAPM2Error("policy does not bind the causal packet schema")
    required_m2 = (
        packet.outer_fold_hash,
        packet.split_manifest_hash,
        packet.provenance_manifest_hash,
        packet.outer_train_set_hash,
        packet.held_out_member_hash,
        packet.crossfit_manifest_hash,
        packet.additive_loss_spec_hash,
        packet.packet_context_hash,
    )
    if any(value is None for value in required_m2) or packet.origin_event_index is None:
        raise CAPM2Error("packet was not built through the sealed M2 causal boundary")
    if packet.outer_train_set_hash == packet.held_out_member_hash:
        raise CAPM2Error("outer train and held-out member bindings overlap")
    if tuple(key.token for key in packet.forecast_keys) != tuple(
        key.token for key in registry.numerical.planned_keys
    ):
        raise CAPM2Error("packet planned keys differ from the numerical registry")
    prefix_hash = canonical_sha256(
        {
            "schema_hash": packet.causal_schema_hash,
            "observations": packet.revealed_observations,
            "schedule": packet.known_schedule,
            "normalization": packet.normalization,
            "conditions": packet.allowed_conditions,
        }
    )
    expected_origin_hash = canonical_sha256(
        {
            "outer_fold_hash": packet.outer_fold_hash,
            "split_manifest_hash": packet.split_manifest_hash,
            "held_out_member_hash": packet.held_out_member_hash,
            "origin_event_index": packet.origin_event_index,
            "availability_cutoff": packet.availability_cutoff,
            "forecast_keys": tuple(key.token for key in packet.forecast_keys),
            "prefix_hash": prefix_hash,
        }
    )
    expected_context_hash = canonical_sha256(
        {
            "prefix_hash": prefix_hash,
            "diagnostic_bins": packet.diagnostic_bins,
            "feature_registry_hash": registry.features.feature_registry_hash,
            "crossfit_manifest_hash": packet.crossfit_manifest_hash,
        }
    )
    if packet.opaque_origin_hash != expected_origin_hash or packet.packet_context_hash != expected_context_hash:
        raise CAPM2Error("packet origin/context hashes are not derivable from its sealed causal prefix")
    if packet.packet_kind is PacketKind.HYBRID:
        if (
            packet.registry_hash != registry.registry_hash
            or packet.action_manifest_hash != registry.action_manifest_hash
            or packet.predicate_manifest_hash != registry.features.feature_registry_hash
            or packet.fallback_bundle_hash != registry.numerical.fallback_bundle.bundle_hash
        ):
            raise CAPM2Error("hybrid packet authority hashes differ from the executable registry")
        expected = tuple(
            _candidate_from_bundle(bundle, registry.registry_hash).bundle_hash
            for bundle in registry.numerical.model_bundles
        )
        actual = tuple(bundle.bundle_hash for bundle in packet.candidate_bundles)
        if actual != expected:
            raise CAPM2Error("hybrid packet candidates differ from the frozen numerical registry")
    scan_forbidden_proxies(packet.payload())


def _closed_result(
    attempt: AttemptStart,
    response: ProviderResponse,
    *,
    expected_policy: PolicySpec | None = None,
    expected_budget: AccuracyBudgetSpec | None = None,
    expected_registry: CAPActionRegistry | None = None,
) -> AttemptResult:
    """Close one consumed slot using runner-owned, fail-closed semantics."""

    status_valid = isinstance(response.status, AttemptStatus)
    status = response.status if status_valid else AttemptStatus.ERROR
    completed = response.completed_unix_ms
    completed_valid = (
        isinstance(completed, int)
        and not isinstance(completed, bool)
        and completed >= attempt.started_unix_ms
    )
    if not completed_valid:
        completed = attempt.started_unix_ms

    input_tokens = response.input_tokens
    output_tokens = response.output_tokens
    usage_absent = input_tokens is None and output_tokens is None
    usage_reported = (
        isinstance(input_tokens, int)
        and not isinstance(input_tokens, bool)
        and input_tokens >= 0
        and isinstance(output_tokens, int)
        and not isinstance(output_tokens, bool)
        and 0 <= output_tokens <= attempt.requested_tokens
    )
    usage_invalid = not usage_absent and not usage_reported

    late_valid = isinstance(response.late, bool)
    late = response.late if late_valid else False
    late = late or completed > attempt.deadline_unix_ms

    response_id_hash: str | None = None
    raw_response_id = response.provider_response_id
    direct_response_id_hash = getattr(response, "provider_response_id_sha256", None)
    invalid_response = not status_valid or not completed_valid or not late_valid or usage_invalid
    if raw_response_id is not None:
        try:
            if not isinstance(raw_response_id, str) or not raw_response_id:
                raise ValueError("invalid response ID")
            scan_forbidden_proxies({"provider_response_id": raw_response_id})
            raw_direct_hash = hashlib.sha256(raw_response_id.encode("utf-8")).hexdigest()
            if direct_response_id_hash is not None and direct_response_id_hash != raw_direct_hash:
                raise ValueError("response ID hash mismatch")
            response_id_hash = (
                direct_response_id_hash
                if direct_response_id_hash is not None
                else canonical_sha256({"provider_response_id": raw_response_id})
            )
        except Exception:
            invalid_response = True
            response_id_hash = None
    elif direct_response_id_hash is not None:
        if isinstance(direct_response_id_hash, str) and _SHA256_RE.fullmatch(direct_response_id_hash):
            response_id_hash = direct_response_id_hash
        else:
            invalid_response = True

    observed = response.observed_model_hash
    if observed is not None and (
        not isinstance(observed, str) or _SHA256_RE.fullmatch(observed) is None
    ):
        observed = None
        invalid_response = True

    error: ClosedErrorCode | None = None
    if status is AttemptStatus.TIMEOUT:
        error = ClosedErrorCode.TIMEOUT
    elif status is AttemptStatus.MODEL_MISMATCH:
        error = ClosedErrorCode.MODEL_MISMATCH
    elif status is AttemptStatus.ERROR:
        error = ClosedErrorCode.PROVIDER_ERROR
    if invalid_response:
        status = AttemptStatus.ERROR
        error = ClosedErrorCode.INVALID_RESPONSE
        input_tokens = output_tokens = None
        usage_reported = False

    provider_evidence: Mapping[str, Any] | None = None
    provider_evidence_hash: str | None = None
    rebuilt_evidence: Any | None = None
    audit = getattr(response, "audit", None)
    evidence = getattr(response, "evidence", None)
    if audit is not None or evidence is not None:
        try:
            # Imported only when production Ark evidence is present; mock
            # providers retain a dependency-free formal interface.
            from .ark_provider import (
                ArkClosedOutcome,
                ArkInvocationAudit,
                ArkProviderEvidenceEnvelope,
            )

            if not isinstance(audit, ArkInvocationAudit) or not isinstance(
                evidence, ArkProviderEvidenceEnvelope
            ):
                raise TypeError("provider evidence has the wrong closed type")
            primitive = to_primitive(evidence)
            if not isinstance(primitive, Mapping):
                raise TypeError("provider evidence is not an object")
            rebuilt_evidence = ArkProviderEvidenceEnvelope.from_mapping(primitive)
            rebuilt_evidence.validate_attempt(attempt)
            if expected_policy is not None and canonical_bytes(rebuilt_evidence.policy) != canonical_bytes(
                expected_policy
            ):
                raise ValueError("provider policy differs from runner policy")
            if expected_budget is not None and canonical_bytes(rebuilt_evidence.budget) != canonical_bytes(
                expected_budget
            ):
                raise ValueError("provider budget differs from runner budget")
            if expected_registry is not None:
                from .response_schema import build_response_schema_registry

                expected_spec = build_response_schema_registry(expected_registry).spec_for(
                    attempt.arm
                )
                actual_spec = rebuilt_evidence.request_contract.response_schema_spec
                if actual_spec is None or canonical_bytes(actual_spec) != canonical_bytes(
                    expected_spec
                ):
                    raise ValueError("provider response schema differs from canonical registry")
            rebuilt_audit = rebuilt_evidence.invocation_audit
            if canonical_bytes(audit) != canonical_bytes(rebuilt_audit):
                raise ValueError("ephemeral audit differs from evidence envelope")
            expected_status = {
                ArkClosedOutcome.SUCCESS: AttemptStatus.SUCCESS,
                ArkClosedOutcome.LATE_RESPONSE: AttemptStatus.SUCCESS,
                ArkClosedOutcome.MODEL_MISMATCH: AttemptStatus.MODEL_MISMATCH,
                ArkClosedOutcome.TRANSPORT_ERROR: AttemptStatus.ERROR,
                ArkClosedOutcome.HTTP_ERROR: AttemptStatus.ERROR,
                ArkClosedOutcome.INVALID_RESPONSE: AttemptStatus.ERROR,
            }[rebuilt_audit.outcome]
            expected_error = {
                ArkClosedOutcome.SUCCESS: None,
                ArkClosedOutcome.LATE_RESPONSE: None,
                ArkClosedOutcome.MODEL_MISMATCH: ClosedErrorCode.MODEL_MISMATCH,
                ArkClosedOutcome.TRANSPORT_ERROR: ClosedErrorCode.PROVIDER_ERROR,
                ArkClosedOutcome.HTTP_ERROR: ClosedErrorCode.PROVIDER_ERROR,
                ArkClosedOutcome.INVALID_RESPONSE: ClosedErrorCode.INVALID_RESPONSE,
            }[rebuilt_audit.outcome]
            content_hash = None
            if response.response_text is not None:
                if not isinstance(response.response_text, str):
                    raise TypeError("response content is not text")
                parsed_content = strict_json_loads(response.response_text)
                content_bytes = canonical_bytes(parsed_content)
                if content_bytes.decode("utf-8") != response.response_text:
                    raise ValueError("response content is not canonical JSON")
                content_hash = hashlib.sha256(content_bytes).hexdigest()
            ephemeral_pairs = (
                (getattr(response, "ephemeral_request_body_sha256", None), rebuilt_audit.request_body_sha256),
                (getattr(response, "ephemeral_raw_response_sha256", None), rebuilt_audit.raw_response_sha256),
                (
                    getattr(response, "ephemeral_response_content_sha256", None),
                    rebuilt_audit.response_content_sha256,
                ),
                (
                    getattr(response, "ephemeral_provider_response_id_sha256", None),
                    rebuilt_audit.provider_response_id_sha256,
                ),
            )
            if any(left != right for left, right in ephemeral_pairs) or content_hash != rebuilt_audit.response_content_sha256:
                raise ValueError("ephemeral request/response hashes differ from provider evidence")
            if (
                raw_response_id is not None
                or status is not expected_status
                or error is not expected_error
                or completed != rebuilt_audit.completed_unix_ms
                or late != (completed > attempt.deadline_unix_ms)
                or input_tokens != rebuilt_audit.input_tokens
                or output_tokens != rebuilt_audit.output_tokens
                or response_id_hash != rebuilt_audit.provider_response_id_sha256
                or observed != rebuilt_audit.resolved_model_hash
            ):
                raise ValueError("provider response differs from rebuilt evidence")
            scan_forbidden_proxies(primitive)
            provider_evidence = primitive
            provider_evidence_hash = canonical_sha256(provider_evidence)
        except Exception:
            # Never include provider/audit values in a failed binding row.
            status = AttemptStatus.ERROR
            error = ClosedErrorCode.BINDING_MISMATCH
            input_tokens = output_tokens = None
            usage_reported = False
            response_id_hash = None
            observed = None
            provider_evidence = None
            provider_evidence_hash = None
            rebuilt_evidence = None

    result = AttemptResult(
        attempt_id=attempt.attempt_id,
        status=status,
        completed_unix_ms=completed,
        usage_status=UsageStatus.REPORTED if usage_reported else UsageStatus.UNKNOWN,
        input_tokens=input_tokens if usage_reported else None,
        output_tokens=output_tokens if usage_reported else None,
        provider_response_id_hash=response_id_hash,
        error_code=error,
        observed_model_hash=observed,
        late=late,
        provider_evidence=provider_evidence,
        provider_evidence_hash=provider_evidence_hash,
    )
    if rebuilt_evidence is not None:
        try:
            rebuilt_evidence.validate_result(result)
        except Exception:
            return AttemptResult(
                attempt_id=attempt.attempt_id,
                status=AttemptStatus.ERROR,
                completed_unix_ms=completed,
                usage_status=UsageStatus.UNKNOWN,
                error_code=ClosedErrorCode.BINDING_MISMATCH,
                late=late,
            )
    return result


def _recovery_result(start: AttemptStart, completed_unix_ms: int) -> AttemptResult:
    return AttemptResult(
        attempt_id=start.attempt_id,
        status=AttemptStatus.ERROR,
        completed_unix_ms=max(completed_unix_ms, start.started_unix_ms),
        usage_status=UsageStatus.UNKNOWN,
        error_code=ClosedErrorCode.CRASH_RECOVERY,
    )


def _prediction_payload(execution: ArmExecution, registry: CAPActionRegistry) -> tuple[dict[str, Any], tuple[PlannedKeyExecution, ...]]:
    certificate = execution.certificate
    selected = dict(certificate.selected_action_hashes) if certificate is not None else {}
    key_rows: list[PlannedKeyExecution] = []
    for forecast in execution.bundle.forecasts:
        selected_hash = selected.get(forecast.key.token)
        forced_na = forecast.status is ForecastStatus.RUL_NA
        if execution.error_fallback:
            state = ExecutionState.ERROR_FALLBACK
        elif forced_na:
            state = ExecutionState.DELIBERATE_FALLBACK
        elif selected_hash is not None:
            action = registry.resolve(selected_hash, key_token=forecast.key.token)
            if action.transform is None and action.base.operator is BaseOperator.FALLBACK:
                state = ExecutionState.DELIBERATE_FALLBACK
            else:
                state = ExecutionState.ACTIVE
        else:
            state = ExecutionState.ACTIVE
        key_rows.append(
            PlannedKeyExecution(
                key_token=forecast.key.token,
                execution_state=state,
                forecast_status=forecast.status.value,
                forecast_hash=canonical_sha256(forecast.payload()),
                selected_action_hash=selected_hash,
                forced_rul_na=forced_na,
                active_coverage_eligible=state is ExecutionState.ACTIVE and not forced_na,
            )
        )
    payload = {
        "schema_version": "CAPCommittedPrediction.v1",
        "arm": execution.arm_id.value,
        "bundle": execution.bundle.payload(),
        "certificate": to_primitive(certificate) if certificate is not None else None,
        "selected_abstention": execution.selected_abstention,
        "error_fallback": execution.error_fallback,
        "key_executions": [to_primitive(item) for item in key_rows],
    }
    scan_forbidden_proxies(payload)
    return payload, tuple(key_rows)


def _commit_id_body(
    *,
    attempt: AttemptStart,
    started_record_hash: str,
    disposition: CommitDisposition,
    prediction_hash: str,
    committed_unix_ms: int,
    reason: CommitReason,
    late: bool,
) -> dict[str, Any]:
    return {
        "attempt_id": attempt.attempt_id,
        "started_record_hash": started_record_hash,
        "policy_hash": attempt.policy_hash,
        "origin_hash": attempt.origin_hash,
        "packet_hash": attempt.packet_hash,
        "disposition": disposition.value,
        "prediction_hash": prediction_hash,
        "committed_unix_ms": committed_unix_ms,
        "reason_code": reason.value,
        "late_response_ignored": late,
    }


def _parse_commit(payload: Mapping[str, Any]) -> PredictionCommit:
    return PredictionCommit(
        commit_id=payload["commit_id"],
        attempt_id=payload["attempt_id"],
        started_record_hash=payload["started_record_hash"],
        policy_hash=payload["policy_hash"],
        origin_hash=payload["origin_hash"],
        packet_hash=payload["packet_hash"],
        disposition=CommitDisposition(payload["disposition"]),
        prediction=payload["prediction"],
        prediction_hash=payload["prediction_hash"],
        committed_unix_ms=payload["committed_unix_ms"],
        reason_code=CommitReason(payload["reason_code"]),
        late_response_ignored=payload["late_response_ignored"],
    )


def _validate_forecast_record(record: Any) -> tuple[str, str]:
    if not isinstance(record, Mapping):
        raise CAPM2Error("committed forecast must be an object")
    key_token = record.get("key")
    if not isinstance(key_token, str) or not key_token:
        raise CAPM2Error("committed forecast key must be non-empty")
    token_parts = key_token.split("|", 2)
    if (
        len(token_parts) != 3
        or not token_parts[0]
        or not token_parts[1].isdigit()
        or int(token_parts[1]) <= 0
        or not token_parts[2]
    ):
        raise CAPM2Error("committed forecast key is not a canonical target/horizon/unit token")
    status = record.get("status")
    if status == ForecastStatus.RUL_NA.value:
        if set(record) != {"key", "status"}:
            raise CAPM2Error("RUL_NA forecast schema differs")
        normalized_target = re.sub(r"[^a-z0-9]+", "_", token_parts[0].casefold()).strip("_")
        if "rul" not in normalized_target.split("_"):
            raise CAPM2Error("RUL_NA may be committed only for a RUL key")
    elif status == ForecastStatus.NUMERIC.value:
        if set(record) != {"key", "status", "point", "lower", "median", "upper"}:
            raise CAPM2Error("numeric forecast schema differs")
        raw = tuple(record[name] for name in ("point", "lower", "median", "upper"))
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in raw
        ):
            raise CAPM2Error("committed forecast numbers must be finite")
        point, lower, median, upper = (float(value) for value in raw)
        if not lower <= median <= upper or not lower <= point <= upper:
            raise CAPM2Error("committed forecast interval is inconsistent")
    else:
        raise CAPM2Error("committed forecast status is outside the closed enum")
    return key_token, status


def _validate_committed_prediction(
    commit: PredictionCommit,
    *,
    start_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Recompute the semantic links inside one committed CAP prediction."""

    prediction = to_primitive(commit.prediction)
    if not isinstance(prediction, dict) or set(prediction) != {
        "schema_version",
        "arm",
        "bundle",
        "certificate",
        "selected_abstention",
        "error_fallback",
        "key_executions",
        "origin_event_index",
    }:
        raise CAPM2Error("committed prediction schema differs from the frozen protocol")
    if prediction["schema_version"] != "CAPCommittedPrediction.v1":
        raise CAPM2Error("unknown committed prediction schema")
    try:
        arm = ArmId(prediction["arm"])
    except Exception as exc:
        raise CAPM2Error("committed prediction has an unknown arm") from exc
    if arm.value != start_payload.get("arm"):
        raise CAPM2Error("committed prediction arm differs from STARTED")
    if not isinstance(prediction["selected_abstention"], bool) or not isinstance(
        prediction["error_fallback"], bool
    ):
        raise CAPM2Error("committed prediction outcome flags must be booleans")
    origin_event_index = prediction["origin_event_index"]
    if isinstance(origin_event_index, bool) or not isinstance(origin_event_index, int) or origin_event_index < 0:
        raise CAPM2Error("committed origin_event_index must be non-negative")

    bundle = prediction["bundle"]
    if not isinstance(bundle, Mapping) or set(bundle) != {
        "schema_version", "bundle_id", "forecasts"
    }:
        raise CAPM2Error("committed bundle schema differs")
    if bundle["schema_version"] != "CAPForecastBundle.v1":
        raise CAPM2Error("unknown committed bundle schema")
    if not isinstance(bundle["bundle_id"], str) or not bundle["bundle_id"]:
        raise CAPM2Error("committed bundle ID must be non-empty")
    forecasts = bundle["forecasts"]
    if not isinstance(forecasts, list) or not forecasts:
        raise CAPM2Error("committed bundle must contain forecasts")
    forecast_pairs = [_validate_forecast_record(record) for record in forecasts]
    forecast_keys = [key for key, _ in forecast_pairs]
    if forecast_keys != sorted(forecast_keys) or len(forecast_keys) != len(set(forecast_keys)):
        raise CAPM2Error("committed forecast keys must be unique and canonical")
    forecast_by_key = {key: record for key, record in zip(forecast_keys, forecasts)}

    embedded_rows = prediction["key_executions"]
    if not isinstance(embedded_rows, list) or len(embedded_rows) != len(forecasts):
        raise CAPM2Error("committed prediction lacks one execution row per forecast")
    typed_rows: list[PlannedKeyExecution] = []
    for row in embedded_rows:
        if not isinstance(row, Mapping) or set(row) != {
            "key_token", "execution_state", "forecast_status", "forecast_hash",
            "selected_action_hash", "forced_rul_na", "active_coverage_eligible",
        }:
            raise CAPM2Error("embedded key execution schema differs")
        try:
            typed_rows.append(
                PlannedKeyExecution(
                    key_token=row["key_token"],
                    execution_state=ExecutionState(row["execution_state"]),
                    forecast_status=row["forecast_status"],
                    forecast_hash=row["forecast_hash"],
                    selected_action_hash=row["selected_action_hash"],
                    forced_rul_na=row["forced_rul_na"],
                    active_coverage_eligible=row["active_coverage_eligible"],
                )
            )
        except Exception as exc:
            raise CAPM2Error("embedded key execution is invalid") from exc
    row_keys = [row.key_token for row in typed_rows]
    if row_keys != sorted(row_keys) or row_keys != forecast_keys:
        raise CAPM2Error("embedded key execution order differs from the bundle")
    for row in typed_rows:
        forecast = forecast_by_key[row.key_token]
        if (
            row.forecast_status != forecast["status"]
            or row.forecast_hash != canonical_sha256(forecast)
        ):
            raise CAPM2Error("embedded key execution does not bind its forecast")

    certificate = prediction["certificate"]
    selected_map: dict[str, str] = {}
    if certificate is not None:
        if not isinstance(certificate, Mapping) or set(certificate) != {
            "response_schema_version", "registry_hash", "action_space",
            "selected_action_hashes", "prediction_hash",
        }:
            raise CAPM2Error("verification certificate schema differs")
        _require_hash(certificate["registry_hash"], "certificate registry_hash")
        _require_hash(certificate["prediction_hash"], "certificate prediction_hash")
        expected_certificate = {
            ArmId.D1_RAW: ("CAPDirectForecastResponse.v1", "DIRECT_NUMERIC"),
            ArmId.D1_PACKET: ("CAPDirectForecastResponse.v1", "DIRECT_NUMERIC"),
            ArmId.H1: ("CAPActionSelectionResponse.v1", "PRIMARY19"),
            ArmId.RF1: ("CAPActionSelectionResponse.v1", "PRIMARY19"),
            ArmId.RC1: ("CAPActionSelectionResponse.v1", "PRIMARY19"),
            ArmId.ACT1: ("CAPActionSelectionResponse.v1", "PRIMARY19"),
            ArmId.IF1: ("CAPIFRepresentationResponse.v1", "PRIMARY19"),
            ArmId.ACT_COMP96: ("CAPActionSelectionResponse.v1", "COMPOSITIONAL96"),
        }.get(arm)
        if expected_certificate is None or (
            certificate["response_schema_version"], certificate["action_space"]
        ) != expected_certificate:
            raise CAPM2Error("verification certificate authority differs from the arm")
        if certificate["prediction_hash"] != canonical_sha256(bundle):
            raise CAPM2Error("verification certificate does not bind the committed bundle")
        selected = certificate["selected_action_hashes"]
        if not isinstance(selected, list):
            raise CAPM2Error("certificate selected actions must be a list")
        selected_pairs: list[tuple[str, str]] = []
        for pair in selected:
            if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
                raise CAPM2Error("certificate selected-action entry is invalid")
            _require_hash(pair[1], "selected_action_hash")
            selected_pairs.append((pair[0], pair[1]))
        selected_keys = [key for key, _ in selected_pairs]
        if selected_keys != sorted(selected_keys) or len(selected_keys) != len(set(selected_keys)):
            raise CAPM2Error("certificate selected-action keys must be unique and canonical")
        selected_map = dict(selected_pairs)
    expected_selected = {
        row.key_token: row.selected_action_hash
        for row in typed_rows
        if row.selected_action_hash is not None
    }
    if selected_map != expected_selected:
        raise CAPM2Error("certificate selected actions differ from key executions")

    should_fallback = prediction["error_fallback"] or prediction["selected_abstention"]
    expected_disposition = (
        CommitDisposition.FALLBACK if should_fallback else CommitDisposition.PREDICTION
    )
    if commit.disposition is not expected_disposition:
        raise CAPM2Error("commit disposition differs from the verified outcome")
    return [dict(row) for row in embedded_rows]


def verify_durable_checkpoint(
    run_dir: str | os.PathLike[str],
    *,
    checkpoint_record_hash: str,
    expected_origin_index: int,
    expected_origin_hash: str,
    expected_packet_hash: str,
    allowed_policy_hashes: Sequence[str] = (),
) -> dict[str, Any]:
    """Verify one unsealed checkpoint through the complete durable lineage.

    Online reveal cannot wait for the prediction-phase seal, but it must still
    validate the same STARTED -> FINISHED -> prediction -> execution ->
    checkpoint semantics.  Every input ledger is parsed through the canonical
    typed verifier first; this function then proves the cross-ledger links for
    exactly one origin and binds it to the evaluator-recomputed causal packet.
    """

    _require_hash(checkpoint_record_hash, "checkpoint_record_hash")
    _require_hash(expected_origin_hash, "expected_origin_hash")
    _require_hash(expected_packet_hash, "expected_packet_hash")
    policy_authority = frozenset(
        _require_hash(value, "allowed_policy_hash") for value in allowed_policy_hashes
    )
    if (
        isinstance(expected_origin_index, bool)
        or not isinstance(expected_origin_index, int)
        or expected_origin_index < 0
    ):
        raise CAPM2Error("expected_origin_index must be non-negative")
    paths = CAPRunPaths(Path(run_dir))
    records = {
        kind: read_verified_ledger_records(paths.ledger_path(kind), expected_kind=kind)
        for kind in (
            LedgerKind.ATTEMPT,
            LedgerKind.PREDICTION,
            LedgerKind.EXECUTION,
            LedgerKind.CHECKPOINT,
        )
    }
    checkpoint_matches = [
        item
        for item in records[LedgerKind.CHECKPOINT]
        if item["record_hash"] == checkpoint_record_hash
    ]
    if len(checkpoint_matches) != 1:
        raise CAPM2Error("reveal checkpoint is absent or duplicated in the durable ledger")
    checkpoint_record = checkpoint_matches[0]
    checkpoint = checkpoint_record["payload"]
    if (
        checkpoint["origin_event_index"] != expected_origin_index
        or checkpoint["origin_hash"] != expected_origin_hash
        or checkpoint["packet_hash"] != expected_packet_hash
        or (policy_authority and checkpoint["policy_hash"] not in policy_authority)
    ):
        raise CAPM2Error("reveal checkpoint differs from the evaluator causal origin")

    attempt_id = checkpoint["attempt_id"]
    starts = [
        item
        for item in records[LedgerKind.ATTEMPT]
        if item["event"] == "STARTED" and item["payload"]["attempt_id"] == attempt_id
    ]
    finishes = [
        item
        for item in records[LedgerKind.ATTEMPT]
        if item["event"] == "FINISHED" and item["payload"]["attempt_id"] == attempt_id
    ]
    predictions = [
        item
        for item in records[LedgerKind.PREDICTION]
        if item["payload"]["attempt_id"] == attempt_id
    ]
    if len(starts) != 1 or len(finishes) != 1 or len(predictions) != 1:
        raise CAPM2Error("checkpoint requires exactly one STARTED, FINISHED, and prediction")
    start = starts[0]
    finish = finishes[0]
    prediction_record = predictions[0]
    try:
        commit = _parse_commit(prediction_record["payload"])
    except Exception as exc:
        raise CAPM2Error("checkpoint prediction commit is invalid") from exc
    start_payload = start["payload"]
    if (
        start_payload["protocol"] != ProtocolId.ACCURACY_V1.value
        or commit.started_record_hash != start["record_hash"]
        or commit.policy_hash != start_payload["policy_hash"]
        or commit.origin_hash != start_payload["origin_hash"]
        or commit.packet_hash != start_payload["packet_hash"]
        or finish["payload"]["started_record_hash"] != start["record_hash"]
        or checkpoint["attempt_final_record_hash"] != finish["record_hash"]
        or checkpoint["prediction_record_hash"] != prediction_record["record_hash"]
        or checkpoint["commit_id"] != commit.commit_id
        or checkpoint["policy_hash"] != commit.policy_hash
        or checkpoint["origin_hash"] != commit.origin_hash
        or checkpoint["packet_hash"] != commit.packet_hash
    ):
        raise CAPM2Error("checkpoint lineage differs from STARTED/FINISHED/prediction")

    embedded_rows = _validate_committed_prediction(commit, start_payload=start_payload)
    all_commit_checkpoints = [
        item
        for item in records[LedgerKind.CHECKPOINT]
        if item["payload"]["commit_id"] == commit.commit_id
    ]
    if len(all_commit_checkpoints) != 1:
        raise CAPM2Error("prediction commit has duplicate durable checkpoints")
    execution_rows = [
        item
        for item in records[LedgerKind.EXECUTION]
        if item["payload"]["commit_id"] == commit.commit_id
    ]
    actual_by_key = {
        item["payload"]["key_execution"]["key_token"]: item for item in execution_rows
    }
    expected_by_key = {item["key_token"]: item for item in embedded_rows}
    if (
        len(actual_by_key) != len(execution_rows)
        or set(actual_by_key) != set(expected_by_key)
    ):
        raise CAPM2Error("checkpoint execution key set differs from committed prediction")
    for key_token, execution_record in actual_by_key.items():
        if (
            execution_record["payload"]["prediction_record_hash"]
            != prediction_record["record_hash"]
            or execution_record["payload"]["key_execution"] != expected_by_key[key_token]
        ):
            raise CAPM2Error("checkpoint execution row differs from committed prediction")
    expected_references = [
        {"key_token": key_token, "record_hash": actual_by_key[key_token]["record_hash"]}
        for key_token in sorted(actual_by_key)
    ]
    if (
        checkpoint["execution_record_hashes"] != expected_references
        or checkpoint["planned_key_count"] != len(expected_references)
        or checkpoint["origin_event_index"] != commit.prediction["origin_event_index"]
    ):
        raise CAPM2Error("checkpoint does not bind the complete execution set and origin")
    return checkpoint_record


class CAPAccuracyRun:
    """One append/resume-safe accuracy_v1 run directory."""

    def __init__(self, run_dir: str | os.PathLike[str], *, resume: bool = False) -> None:
        self.paths = CAPRunPaths(Path(run_dir))
        _ensure_directory(self.paths.root, resume=resume)
        if self.paths.prediction_phase_seal.exists():
            raise CAPM2Error("a sealed prediction phase is immutable and cannot be resumed")
        self._ledgers: dict[LedgerKind, CanonicalJSONLLedger] = {}
        try:
            for kind in (LedgerKind.ATTEMPT, LedgerKind.PREDICTION, LedgerKind.EXECUTION, LedgerKind.CHECKPOINT):
                self._ledgers[kind] = CanonicalJSONLLedger(
                    self.paths.ledger_path(kind), kind, resume=resume
                )
        except Exception:
            self.close()
            raise
        self._closed = False
        self._prediction_sealed = False

    def __enter__(self) -> "CAPAccuracyRun":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        for ledger in self._ledgers.values():
            ledger.close()
        self._closed = True

    def _records(self, kind: LedgerKind) -> tuple[dict[str, Any], ...]:
        return read_verified_ledger_records(self.paths.ledger_path(kind), expected_kind=kind)

    def _append_execution_and_checkpoint(
        self,
        *,
        attempt: AttemptStart,
        commit: PredictionCommit,
        prediction_record_hash: str,
        key_rows: Sequence[PlannedKeyExecution],
    ) -> tuple[tuple[tuple[str, str], ...], str]:
        existing_exec = {
            (record["payload"]["commit_id"], record["payload"]["key_execution"]["key_token"]): record
            for record in self._records(LedgerKind.EXECUTION)
        }
        execution_hashes: list[tuple[str, str]] = []
        for row in key_rows:
            payload = {
                "schema_version": "CAPKeyExecutionRecord.v1",
                "commit_id": commit.commit_id,
                "prediction_record_hash": prediction_record_hash,
                "key_execution": to_primitive(row),
            }
            key = (commit.commit_id, row.key_token)
            if key in existing_exec:
                if existing_exec[key]["payload"] != payload:
                    raise CAPM2Error("existing execution row differs from recovered prediction")
                record_hash = existing_exec[key]["record_hash"]
            else:
                record_hash = self._ledgers[LedgerKind.EXECUTION].append_execution(payload)
            execution_hashes.append((row.key_token, record_hash))
        execution_hashes.sort()
        attempt_records = self._records(LedgerKind.ATTEMPT)
        attempt_final_hash = next(
            record["record_hash"]
            for record in reversed(attempt_records)
            if record["payload"].get("attempt_id") == attempt.attempt_id
        )
        checkpoint_payload = {
            "schema_version": "CAPOriginCheckpoint.v1",
            "attempt_id": attempt.attempt_id,
            "commit_id": commit.commit_id,
            "policy_hash": attempt.policy_hash,
            "origin_hash": attempt.origin_hash,
            "origin_event_index": int(commit.prediction["origin_event_index"]),
            "packet_hash": attempt.packet_hash,
            "attempt_final_record_hash": attempt_final_hash,
            "prediction_record_hash": prediction_record_hash,
            "execution_record_hashes": [
                {"key_token": key, "record_hash": record_hash}
                for key, record_hash in execution_hashes
            ],
            "planned_key_count": len(key_rows),
        }
        existing_checkpoints = [
            record for record in self._records(LedgerKind.CHECKPOINT)
            if record["payload"].get("commit_id") == commit.commit_id
        ]
        if existing_checkpoints:
            if len(existing_checkpoints) != 1 or existing_checkpoints[0]["payload"] != checkpoint_payload:
                raise CAPM2Error("existing checkpoint differs from recovered ledger state")
            checkpoint_hash = existing_checkpoints[0]["record_hash"]
        else:
            checkpoint_hash = self._ledgers[LedgerKind.CHECKPOINT].append_checkpoint(checkpoint_payload)
        return tuple(execution_hashes), checkpoint_hash

    def run_origin(
        self,
        *,
        provider: AccuracyProvider | None,
        policy: PolicySpec,
        packet: OriginPacketV2,
        registry: CAPActionRegistry,
        budget: AccuracyBudgetSpec,
        started_unix_ms: int,
    ) -> TypedOriginResult:
        if self._closed or self._prediction_sealed:
            raise CAPM2Error("prediction phase is closed")
        _validate_bindings(policy=policy, packet=packet, registry=registry, budget=budget)
        attempt_id = canonical_sha256(
            {
                "protocol": ProtocolId.ACCURACY_V1.value,
                "policy_hash": policy.policy_hash,
                "origin_hash": packet.opaque_origin_hash,
                "physical_slot": 0 if budget.physical_calls else -1,
            }
        )
        starts = [
            record for record in self._records(LedgerKind.ATTEMPT)
            if record["event"] == "STARTED" and record["payload"].get("attempt_id") == attempt_id
        ]
        if len(starts) > 1:
            raise CAPM2Error("durable one-attempt slot is duplicated")
        provider_called = False
        recovered = bool(starts)
        if starts:
            start_record = starts[0]
            payload = start_record["payload"]
            attempt = AttemptStart(
                attempt_id=payload["attempt_id"],
                policy_hash=payload["policy_hash"],
                origin_hash=payload["origin_hash"],
                packet_hash=payload["packet_hash"],
                arm=ArmId(payload["arm"]),
                protocol=ProtocolId(payload["protocol"]),
                physical_slot=payload["physical_slot"],
                requested_tokens=payload["requested_tokens"],
                deadline_unix_ms=payload["deadline_unix_ms"],
                started_unix_ms=payload["started_unix_ms"],
            )
            if (
                attempt.policy_hash != policy.policy_hash
                or attempt.origin_hash != packet.opaque_origin_hash
                or attempt.packet_hash != packet.packet_hash
                or attempt.requested_tokens != budget.requested_tokens
            ):
                raise CAPM2Error("existing durable slot has different frozen bindings")
        else:
            attempt = AttemptStart(
                attempt_id=attempt_id,
                policy_hash=policy.policy_hash,
                origin_hash=packet.opaque_origin_hash,
                packet_hash=packet.packet_hash,
                arm=policy.arm,
                protocol=policy.protocol,
                physical_slot=0 if budget.physical_calls else -1,
                requested_tokens=budget.requested_tokens,
                deadline_unix_ms=started_unix_ms + budget.deadline_ms,
                started_unix_ms=started_unix_ms,
            )
            start_hash = self._ledgers[LedgerKind.ATTEMPT].append_started(attempt)
            start_record = {"record_hash": start_hash, "payload": to_primitive(attempt)}

        predictions = [
            record for record in self._records(LedgerKind.PREDICTION)
            if record["payload"].get("attempt_id") == attempt_id
        ]
        if len(predictions) > 1:
            raise CAPM2Error("durable slot has multiple prediction commits")
        finished_records = [
            record for record in self._records(LedgerKind.ATTEMPT)
            if record["event"] == "FINISHED" and record["payload"].get("attempt_id") == attempt_id
        ]

        if predictions:
            prediction_record = predictions[0]
            commit = _parse_commit(prediction_record["payload"])
            raw_rows = _validate_committed_prediction(
                commit,
                start_payload=start_record["payload"],
            )
            key_rows = tuple(
                PlannedKeyExecution(
                    key_token=item["key_token"],
                    execution_state=ExecutionState(item["execution_state"]),
                    forecast_status=item["forecast_status"],
                    forecast_hash=item["forecast_hash"],
                    selected_action_hash=item.get("selected_action_hash"),
                    forced_rul_na=item["forced_rul_na"],
                    active_coverage_eligible=item["active_coverage_eligible"],
                )
                for item in raw_rows
            )
            if not finished_records:
                raise CAPM2Error("prediction commit exists without a FINISHED attempt")
            result_payload = finished_records[0]["payload"]
            result = AttemptResult(
                attempt_id=result_payload["attempt_id"],
                status=AttemptStatus(result_payload["status"]),
                completed_unix_ms=result_payload["completed_unix_ms"],
                usage_status=UsageStatus(result_payload["usage_status"]),
                input_tokens=result_payload.get("input_tokens"),
                output_tokens=result_payload.get("output_tokens"),
                provider_response_id_hash=result_payload.get("provider_response_id_hash"),
                error_code=ClosedErrorCode(result_payload["error_code"])
                if result_payload.get("error_code") is not None else None,
                observed_model_hash=result_payload.get("observed_model_hash"),
                late=result_payload.get("late", False),
                provider_evidence=result_payload.get("provider_evidence"),
                provider_evidence_hash=result_payload.get("provider_evidence_hash"),
            )
            execution_hashes, checkpoint_hash = self._append_execution_and_checkpoint(
                attempt=attempt,
                commit=commit,
                prediction_record_hash=prediction_record["record_hash"],
                key_rows=key_rows,
            )
            return TypedOriginResult(
                result, commit, prediction_record["record_hash"], execution_hashes,
                checkpoint_hash, False, True,
            )

        if finished_records:
            result = _recovery_result(attempt, started_unix_ms)
            execution = execute_arm(policy.arm, None, registry=registry)
        elif recovered:
            result = _recovery_result(attempt, started_unix_ms)
            self._ledgers[LedgerKind.ATTEMPT].append_finished(start_record["record_hash"], result)
            execution = execute_arm(policy.arm, None, registry=registry)
        elif budget.physical_calls == 0:
            result = AttemptResult(
                attempt_id=attempt.attempt_id,
                status=AttemptStatus.LOCAL,
                completed_unix_ms=started_unix_ms,
                usage_status=UsageStatus.REPORTED,
                input_tokens=0,
                output_tokens=0,
            )
            self._ledgers[LedgerKind.ATTEMPT].append_finished(start_record["record_hash"], result)
            execution = execute_arm(policy.arm, None, registry=registry)
        else:
            if provider is None:
                raise CAPM2Error("a physical-call arm requires a provider")
            try:
                ephemeral = provider.invoke(packet.packet_bytes, attempt)
                provider_called = True
            except Exception:
                provider_called = True
                ephemeral = ProviderResponse(
                    status=AttemptStatus.ERROR,
                    completed_unix_ms=started_unix_ms,
                    response_text=None,
                )
            result = _closed_result(
                attempt,
                ephemeral,
                expected_policy=policy,
                expected_budget=budget,
                expected_registry=registry,
            )
            self._ledgers[LedgerKind.ATTEMPT].append_finished(start_record["record_hash"], result)
            if result.status is AttemptStatus.SUCCESS and not result.late and ephemeral.response_text is not None:
                execution = execute_arm(
                    policy.arm,
                    ephemeral.response_text,
                    registry=registry,
                    feature_bins=dict(packet.diagnostic_bins) if policy.arm is ArmId.IF1 else None,
                )
            else:
                execution = execute_arm(policy.arm, None, registry=registry)

        prediction, key_rows = _prediction_payload(execution, registry)
        prediction["origin_event_index"] = packet.origin_event_index
        prediction_hash = canonical_sha256(prediction)
        if recovered:
            reason = CommitReason.CRASH_RECOVERY
        elif result.late:
            reason = CommitReason.LATE_RESPONSE
        elif result.status not in {AttemptStatus.SUCCESS, AttemptStatus.LOCAL}:
            reason = CommitReason.PROVIDER_FAILURE
        elif execution.error_fallback:
            reason = CommitReason.INVALID_RESPONSE
        elif execution.selected_abstention:
            reason = CommitReason.DELIBERATE_FALLBACK
        elif policy.arm is ArmId.N0:
            reason = CommitReason.NUMERICAL_CHAMPION
        else:
            reason = CommitReason.VERIFIED_RESPONSE
        disposition = (
            CommitDisposition.FALLBACK
            if execution.error_fallback or execution.bundle is registry.numerical.fallback_bundle and execution.selected_abstention
            else CommitDisposition.PREDICTION
        )
        commit_body = _commit_id_body(
            attempt=attempt,
            started_record_hash=start_record["record_hash"],
            disposition=disposition,
            prediction_hash=prediction_hash,
            committed_unix_ms=result.completed_unix_ms,
            reason=reason,
            late=result.late,
        )
        commit = PredictionCommit(
            commit_id=canonical_sha256(commit_body),
            attempt_id=attempt.attempt_id,
            started_record_hash=start_record["record_hash"],
            policy_hash=attempt.policy_hash,
            origin_hash=attempt.origin_hash,
            packet_hash=attempt.packet_hash,
            disposition=disposition,
            prediction=prediction,
            prediction_hash=prediction_hash,
            committed_unix_ms=result.completed_unix_ms,
            reason_code=reason,
            late_response_ignored=result.late,
        )
        _validate_committed_prediction(commit, start_payload=start_record["payload"])
        prediction_hash_record = self._ledgers[LedgerKind.PREDICTION].append_prediction(commit)
        execution_hashes, checkpoint_hash = self._append_execution_and_checkpoint(
            attempt=attempt,
            commit=commit,
            prediction_record_hash=prediction_hash_record,
            key_rows=key_rows,
        )
        return TypedOriginResult(
            result, commit, prediction_hash_record, execution_hashes,
            checkpoint_hash, provider_called, recovered,
        )

    def seal_prediction_phase(self) -> str:
        if self._prediction_sealed:
            return _artifact_hash(self.paths.prediction_phase_seal)
        artifacts: list[dict[str, Any]] = []
        for kind in (LedgerKind.ATTEMPT, LedgerKind.PREDICTION, LedgerKind.EXECUTION, LedgerKind.CHECKPOINT):
            ledger = self._ledgers[kind]
            seal_path = self.paths.seal_path(kind)
            ledger.seal(seal_path)
            ledger.close()
            report = verify_ledger(self.paths.ledger_path(kind), expected_kind=kind, seal_path=seal_path)
            if report.incomplete_attempt_ids:
                raise CAPM2Error("prediction phase cannot seal with an incomplete attempt")
            artifacts.append(
                {
                    "ledger_kind": kind.value,
                    "ledger_file": self.paths.ledger_path(kind).name,
                    "ledger_sha256": _artifact_hash(self.paths.ledger_path(kind)),
                    "ledger_record_count": report.record_count,
                    "ledger_final_record_hash": report.final_record_hash,
                    "seal_file": seal_path.name,
                    "seal_sha256": _artifact_hash(seal_path),
                }
            )
        body = {
            "schema_version": "CAPPredictionPhaseSeal.v1",
            "verifier_hash": CAP_M2_VERIFIER_HASH,
            "artifacts": artifacts,
        }
        record = dict(body)
        record["phase_seal_hash"] = canonical_sha256(body)
        _write_exclusive(self.paths.prediction_phase_seal, record)
        self._prediction_sealed = True
        verify_prediction_phase(self.paths.root)
        return record["phase_seal_hash"]


def verify_prediction_phase(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Cross-verify sealed attempts, commits, key rows and checkpoints."""

    paths = CAPRunPaths(Path(run_dir))
    records: dict[LedgerKind, tuple[dict[str, Any], ...]] = {}
    for kind in (LedgerKind.ATTEMPT, LedgerKind.PREDICTION, LedgerKind.EXECUTION, LedgerKind.CHECKPOINT):
        records[kind] = read_verified_ledger_records(
            paths.ledger_path(kind), expected_kind=kind, seal_path=paths.seal_path(kind)
        )
    starts = {
        item["payload"]["attempt_id"]: item
        for item in records[LedgerKind.ATTEMPT]
        if item["event"] == "STARTED"
    }
    finishes = {
        item["payload"]["attempt_id"]: item
        for item in records[LedgerKind.ATTEMPT]
        if item["event"] == "FINISHED"
    }
    predictions = {item["payload"]["attempt_id"]: item for item in records[LedgerKind.PREDICTION]}
    if set(starts) != set(finishes) or set(starts) != set(predictions):
        raise CAPM2Error("attempt, finish, and prediction key sets differ")
    execution_by_commit: dict[str, list[dict[str, Any]]] = {}
    for item in records[LedgerKind.EXECUTION]:
        execution_by_commit.setdefault(item["payload"]["commit_id"], []).append(item)
    checkpoint_by_commit: dict[str, list[dict[str, Any]]] = {}
    for item in records[LedgerKind.CHECKPOINT]:
        checkpoint_by_commit.setdefault(item["payload"]["commit_id"], []).append(item)

    for attempt_id, prediction_record in predictions.items():
        start = starts[attempt_id]
        finish = finishes[attempt_id]
        commit = _parse_commit(prediction_record["payload"])
        start_payload = start["payload"]
        if (
            commit.started_record_hash != start["record_hash"]
            or commit.policy_hash != start_payload["policy_hash"]
            or commit.origin_hash != start_payload["origin_hash"]
            or commit.packet_hash != start_payload["packet_hash"]
            or finish["payload"].get("started_record_hash") != start["record_hash"]
        ):
            raise CAPM2Error("prediction/finish lineage differs from STARTED")
        embedded_rows = _validate_committed_prediction(
            commit,
            start_payload=start_payload,
        )
        rows = execution_by_commit.get(commit.commit_id, [])
        if len(rows) != len(embedded_rows):
            raise CAPM2Error("execution row count differs from committed planned keys")
        actual = {
            row["payload"]["key_execution"]["key_token"]: row
            for row in rows
        }
        expected = {row["key_token"]: row for row in embedded_rows}
        if set(actual) != set(expected):
            raise CAPM2Error("execution key set differs from committed planned keys")
        for key, row in actual.items():
            if (
                row["payload"]["prediction_record_hash"] != prediction_record["record_hash"]
                or row["payload"]["key_execution"] != expected[key]
            ):
                raise CAPM2Error("execution row differs from the sealed prediction")
        checkpoints = checkpoint_by_commit.get(commit.commit_id, [])
        if len(checkpoints) != 1:
            raise CAPM2Error("each prediction commit requires exactly one checkpoint")
        checkpoint = checkpoints[0]["payload"]
        expected_hashes = [
            {"key_token": key, "record_hash": actual[key]["record_hash"]}
            for key in sorted(actual)
        ]
        if (
            checkpoint["attempt_id"] != attempt_id
            or checkpoint["policy_hash"] != commit.policy_hash
            or checkpoint["origin_hash"] != commit.origin_hash
            or checkpoint["packet_hash"] != commit.packet_hash
            or checkpoint["prediction_record_hash"] != prediction_record["record_hash"]
            or checkpoint["attempt_final_record_hash"] != finish["record_hash"]
            or checkpoint["execution_record_hashes"] != expected_hashes
            or checkpoint["planned_key_count"] != len(expected_hashes)
            or checkpoint["origin_event_index"] != commit.prediction["origin_event_index"]
        ):
            raise CAPM2Error("checkpoint does not bind the actual ledger rows")

    raw_seal = _read_regular(paths.prediction_phase_seal)
    seal = strict_json_loads(raw_seal)
    if not isinstance(seal, dict) or canonical_bytes(seal) != raw_seal:
        raise CAPM2Error("prediction phase seal is not canonical")
    body = {key: value for key, value in seal.items() if key != "phase_seal_hash"}
    if set(seal) != {"schema_version", "verifier_hash", "artifacts", "phase_seal_hash"}:
        raise CAPM2Error("prediction phase seal schema differs")
    if (
        seal["schema_version"] != "CAPPredictionPhaseSeal.v1"
        or seal["verifier_hash"] != CAP_M2_VERIFIER_HASH
        or seal["phase_seal_hash"] != canonical_sha256(body)
    ):
        raise CAPM2Error("prediction phase seal hash or verifier differs")
    expected_artifacts = []
    for kind in (LedgerKind.ATTEMPT, LedgerKind.PREDICTION, LedgerKind.EXECUTION, LedgerKind.CHECKPOINT):
        report = verify_ledger(paths.ledger_path(kind), expected_kind=kind, seal_path=paths.seal_path(kind))
        expected_artifacts.append(
            {
                "ledger_kind": kind.value,
                "ledger_file": paths.ledger_path(kind).name,
                "ledger_sha256": _artifact_hash(paths.ledger_path(kind)),
                "ledger_record_count": report.record_count,
                "ledger_final_record_hash": report.final_record_hash,
                "seal_file": paths.seal_path(kind).name,
                "seal_sha256": _artifact_hash(paths.seal_path(kind)),
            }
        )
    if seal["artifacts"] != expected_artifacts:
        raise CAPM2Error("prediction phase seal does not bind the actual artifacts")
    return {
        "status": "PASS",
        "attempt_count": len(starts),
        "prediction_count": len(predictions),
        "execution_count": len(records[LedgerKind.EXECUTION]),
        "checkpoint_count": len(records[LedgerKind.CHECKPOINT]),
        "phase_seal_hash": seal["phase_seal_hash"],
    }
