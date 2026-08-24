"""Legacy M0 unit harness for one-attempt ordering tests.

This module is intentionally not exported as the formal execution API.  All
future accuracy runs must use :class:`vfps_agent.runner.CAPAccuracyRun`, which
binds the concrete CAP registry and verifies the complete cross-ledger run.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .canonical import canonical_sha256, scan_forbidden_proxies, strict_json_loads, to_primitive
from .contracts import (
    ArmId,
    AttemptResult,
    AttemptStart,
    AttemptStatus,
    ClosedErrorCode,
    CommitReason,
    CommitDisposition,
    FROZEN_ARM_SPECS,
    OriginPacketV2,
    PolicySpec,
    PredictionCommit,
    ProtocolId,
    UsageStatus,
)
from .ledger import CanonicalJSONLLedger
from .provider import MockProvider, ProviderResponse


class AttemptBudgetError(RuntimeError):
    """Raised when code tries to retry or overwrite an accuracy attempt."""


class AccuracyV1Budget:
    """In-memory reservation guard; durable truth remains in the attempt ledger."""

    protocol = ProtocolId.ACCURACY_V1

    def __init__(self) -> None:
        self._reserved: set[tuple[str, str]] = set()
        self._committed: set[str] = set()

    def reserve(
        self,
        *,
        attempt_id: str,
        policy: PolicySpec,
        packet: OriginPacketV2,
        requested_tokens: int,
        started_unix_ms: int,
        deadline_unix_ms: int,
    ) -> AttemptStart:
        if policy.protocol is not ProtocolId.ACCURACY_V1:
            raise AttemptBudgetError("policy is not frozen for accuracy_v1")
        arm_spec = FROZEN_ARM_SPECS[policy.arm]
        if arm_spec.packet_kind is not None and arm_spec.packet_kind is not packet.packet_kind:
            raise AttemptBudgetError("arm and packet permission do not match")
        key = (policy.policy_hash, packet.opaque_origin_hash)
        if key in self._reserved:
            raise AttemptBudgetError("accuracy_v1 permits one physical attempt and no retry")
        self._reserved.add(key)
        return AttemptStart(
            attempt_id=attempt_id,
            policy_hash=policy.policy_hash,
            origin_hash=packet.opaque_origin_hash,
            packet_hash=packet.packet_hash,
            arm=policy.arm,
            protocol=policy.protocol,
            physical_slot=0 if arm_spec.physical_calls == 1 else -1,
            requested_tokens=requested_tokens,
            deadline_unix_ms=deadline_unix_ms,
            started_unix_ms=started_unix_ms,
        )

    def restore(self, start: AttemptStart, *, committed: bool) -> None:
        """Rebuild the in-memory guard from verified durable evidence."""

        key = (start.policy_hash, start.origin_hash)
        if key in self._reserved:
            raise AttemptBudgetError("durable reservation is duplicated")
        self._reserved.add(key)
        if committed:
            self._committed.add(start.attempt_id)

    def mark_committed(self, attempt_id: str) -> None:
        if attempt_id in self._committed:
            raise AttemptBudgetError("late or duplicate completion cannot overwrite a commit")
        self._committed.add(attempt_id)


def _attempt_result(attempt: AttemptStart, response: ProviderResponse) -> AttemptResult:
    status = response.status if isinstance(response.status, AttemptStatus) else AttemptStatus.ERROR
    completed = (
        response.completed_unix_ms
        if isinstance(response.completed_unix_ms, int)
        and not isinstance(response.completed_unix_ms, bool)
        and response.completed_unix_ms >= 0
        else attempt.started_unix_ms
    )
    usage_known = (
        isinstance(response.input_tokens, int)
        and not isinstance(response.input_tokens, bool)
        and response.input_tokens >= 0
        and isinstance(response.output_tokens, int)
        and not isinstance(response.output_tokens, bool)
        and response.output_tokens >= 0
    )
    usage_status = UsageStatus.REPORTED if usage_known else UsageStatus.UNKNOWN
    error_code: ClosedErrorCode | None = None
    if status is AttemptStatus.TIMEOUT:
        error_code = ClosedErrorCode.TIMEOUT
    elif status is AttemptStatus.MODEL_MISMATCH:
        error_code = ClosedErrorCode.MODEL_MISMATCH
    elif status is AttemptStatus.ERROR:
        error_code = ClosedErrorCode.PROVIDER_ERROR
    observed_model_hash = response.observed_model_hash
    if not isinstance(observed_model_hash, str) or len(observed_model_hash) != 64:
        observed_model_hash = None
    return AttemptResult(
        attempt_id=attempt.attempt_id,
        status=status,
        completed_unix_ms=completed,
        usage_status=usage_status,
        input_tokens=response.input_tokens if usage_known else None,
        output_tokens=response.output_tokens if usage_known else None,
        # MockProvider exposes no provider-issued response ID.  Raw response
        # bytes are deliberately not hashed because even their digest is not
        # part of the durable scientific contract.
        provider_response_id_hash=None,
        error_code=error_code,
        observed_model_hash=observed_model_hash,
        late=bool(response.late) or completed > attempt.deadline_unix_ms,
    )


def _same_prediction_shape(candidate: Any, template: Any) -> bool:
    """Reject extra free-form fields/strings before any response can be committed."""

    if isinstance(template, Mapping):
        return isinstance(candidate, Mapping) and set(candidate) == set(template) and all(
            _same_prediction_shape(candidate[key], template[key]) for key in template
        )
    if isinstance(template, list):
        return isinstance(candidate, list) and len(candidate) == len(template) and all(
            _same_prediction_shape(left, right) for left, right in zip(candidate, template)
        )
    if isinstance(template, bool):
        return isinstance(candidate, bool)
    if isinstance(template, (int, float)) and not isinstance(template, bool):
        return isinstance(candidate, (int, float)) and not isinstance(candidate, bool)
    if template is None:
        return candidate is None
    if isinstance(template, str):
        return candidate == template
    return False


def execute_mock_accuracy_v1(
    *,
    provider: MockProvider,
    policy: PolicySpec,
    packet: OriginPacketV2,
    budget: AccuracyV1Budget,
    attempt_ledger: CanonicalJSONLLedger,
    prediction_ledger: CanonicalJSONLLedger,
    fallback_prediction: Mapping[str, Any],
    attempt_id: str,
    requested_tokens: int,
    started_unix_ms: int,
    deadline_unix_ms: int,
    response_decoder: Callable[[Any], Mapping[str, Any]] | None = None,
) -> tuple[AttemptResult, PredictionCommit]:
    """Run one development-only mock request with Round-2 ordering.

    ``STARTED`` is appended and fsynced before ``provider.invoke``.  The raw
    request and response are never included in any artifact.  Missing usage is
    UNKNOWN, and every late/non-success/invalid response commits exact fallback.
    This compatibility harness cannot authorize an accuracy result.
    """

    # Detach fallback from caller-owned containers before provider code runs.
    fallback_snapshot = to_primitive(fallback_prediction)
    if not isinstance(fallback_snapshot, Mapping):
        raise TypeError("fallback_prediction must be a mapping")
    scan_forbidden_proxies(fallback_snapshot)
    attempt = budget.reserve(
        attempt_id=attempt_id,
        policy=policy,
        packet=packet,
        requested_tokens=requested_tokens,
        started_unix_ms=started_unix_ms,
        deadline_unix_ms=deadline_unix_ms,
    )
    started_record_hash = attempt_ledger.append_started(attempt)

    try:
        ephemeral = provider.invoke(packet.packet_bytes, attempt)
    except Exception:
        # Exception text may carry secrets.  Persist only a closed reason code.
        ephemeral = ProviderResponse(
            status=AttemptStatus.ERROR,
            completed_unix_ms=started_unix_ms,
            response_text=None,
            error_code="PROVIDER_EXCEPTION",
        )
    result = _attempt_result(attempt, ephemeral)

    prediction: Mapping[str, Any] = fallback_snapshot
    disposition = CommitDisposition.FALLBACK
    reason = CommitReason.PROVIDER_FAILURE
    if result.late:
        reason = CommitReason.LATE_RESPONSE
    elif result.status is AttemptStatus.SUCCESS and ephemeral.response_text is not None:
        try:
            decoded = strict_json_loads(ephemeral.response_text)
            scan_forbidden_proxies(decoded)
            resolved = response_decoder(decoded) if response_decoder is not None else decoded
            if not isinstance(resolved, Mapping) or not _same_prediction_shape(resolved, fallback_snapshot):
                raise ValueError("response does not match the frozen prediction schema")
            scan_forbidden_proxies(resolved)
            prediction = resolved
            disposition = CommitDisposition.PREDICTION
            reason = CommitReason.VERIFIED_RESPONSE
        except Exception:
            # Never persist parser exceptions or raw response values.
            prediction = fallback_snapshot
            disposition = CommitDisposition.FALLBACK
            reason = CommitReason.INVALID_RESPONSE

    attempt_ledger.append_finished(started_record_hash, result)
    budget.mark_committed(attempt.attempt_id)
    prediction_hash = canonical_sha256(prediction)
    commit_body = {
        "attempt_id": attempt.attempt_id,
        "started_record_hash": started_record_hash,
        "policy_hash": attempt.policy_hash,
        "origin_hash": attempt.origin_hash,
        "packet_hash": attempt.packet_hash,
        "disposition": disposition.value,
        "prediction_hash": prediction_hash,
        "committed_unix_ms": result.completed_unix_ms,
        "reason_code": reason.value,
        "late_response_ignored": result.late,
    }
    commit = PredictionCommit(
        commit_id=canonical_sha256(commit_body),
        attempt_id=attempt.attempt_id,
        started_record_hash=started_record_hash,
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
    prediction_ledger.append_prediction(commit)
    return result, commit
