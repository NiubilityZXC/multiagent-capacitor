from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from experiments.vfps_agent.ark_provider import (
    ArkBindingError,
    ArkCapabilitySnapshot,
    ArkClosedOutcome,
    ArkDecodeSpec,
    ArkInvocationError,
    ArkModelRule,
    ArkPromptSpec,
    ArkProviderAdapter,
    ArkProviderEvidenceEnvelope,
    ArkProviderRule,
    ArkRequestContract,
    ArkResponseFormat,
    ArkTransportRequest,
    ArkTransportResponse,
)
from experiments.vfps_agent.canonical import canonical_bytes, canonical_sha256
from experiments.vfps_agent.contracts import (
    AccuracyBudgetSpec,
    ArmId,
    AttemptStart,
    AttemptStatus,
    PolicySpec,
    ProtocolId,
)
from experiments.vfps_agent.ledger import (
    CanonicalJSONLLedger,
    LedgerIntegrityError,
    LedgerKind,
    read_verified_ledger_records,
)
from experiments.vfps_agent.runner import _closed_result
from experiments.vfps_agent.verifier import (
    ACTION_RESPONSE_SCHEMA_VERSION,
    DIRECT_RESPONSE_SCHEMA_VERSION,
)


CAPABILITY = ArkCapabilitySnapshot(
    model_list_artifact_sha256="a" * 64,
    text_resources_artifact_sha256="b" * 64,
    authenticated_model_ids=("glm-5.3", "kimi-k3"),
    text_resource_model_ids=("kimi-k3",),
    eligible_model_ids=("kimi-k3",),
)
CAPABILITY_HASH = CAPABILITY.snapshot_hash
DECISION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "value"],
    "properties": {
        "schema_version": {"const": DIRECT_RESPONSE_SCHEMA_VERSION},
        "value": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}
DECISION = {"schema_version": DIRECT_RESPONSE_SCHEMA_VERSION, "value": 0.75}


class CapturingTransport:
    def __init__(self, result: ArkTransportResponse | Exception) -> None:
        self.result = result
        self.requests: list[ArkTransportRequest] = []

    def send(self, request: ArkTransportRequest) -> ArkTransportResponse:
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def response_envelope(
    *,
    model: str = "kimi-k3",
    decision_text: str | None = None,
    completed: int = 1050,
    usage: Any = None,
    extra: dict[str, Any] | None = None,
) -> ArkTransportResponse:
    text = decision_text if decision_text is not None else canonical_bytes(DECISION).decode()
    envelope: dict[str, Any] = {
        "id": "resp_safe_001",
        "model": model,
        "object": "response",
        "output": [
            {
                "id": "msg_safe_001",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                        "annotations": [],
                    }
                ],
            }
        ],
        "status": "completed",
        "store": False,
        "usage": usage
        if usage is not None
        else {"input_tokens": 12, "output_tokens": 20, "total_tokens": 32},
    }
    if extra:
        envelope.update(extra)
    return ArkTransportResponse(200, canonical_bytes(envelope), completed)


def contract_fixture(
    response_format: ArkResponseFormat = ArkResponseFormat.JSON_SCHEMA,
    *,
    response_schema: dict[str, Any] | None = None,
) -> ArkRequestContract:
    return ArkRequestContract(
        prompt=ArkPromptSpec(
            instructions="Return only one decision object conforming to the frozen local contract.",
            packet_preamble="Causal origin packet follows.",
        ),
        decode=ArkDecodeSpec(temperature=0.0, top_p=1.0, reasoning_effort="medium"),
        model=ArkModelRule("kimi-k3", CAPABILITY),
        provider=ArkProviderRule(response_format, "capacitor_decision"),
        response_schema=response_schema or DECISION_SCHEMA,
    )


def policy_fixture(
    contract: ArkRequestContract,
    budget: AccuracyBudgetSpec,
) -> PolicySpec:
    return PolicySpec(
        policy_id="agentplan_direct_offline_fixture",
        generation=1,
        protocol=ProtocolId.ACCURACY_V1,
        arm=ArmId.D1_RAW,
        provider_rule_hash=contract.provider.provider_rule_hash,
        model_version_rule_hash=contract.model.model_version_rule_hash,
        prompt_hash=contract.prompt.prompt_hash,
        packet_schema_hash="1" * 64,
        response_schema_hash=contract.response_schema_hash,
        grammar_hash="2" * 64,
        registry_hash="3" * 64,
        decode_parameters_hash=contract.decode.decode_parameters_hash,
        one_call_budget_hash=budget.budget_hash,
        verifier_hash="4" * 64,
        fallback_hash="5" * 64,
        capability_snapshot_hash=CAPABILITY_HASH,
    )


def invocation_fixture(
    transport: CapturingTransport,
    *,
    response_format: ArkResponseFormat = ArkResponseFormat.JSON_SCHEMA,
    response_schema: dict[str, Any] | None = None,
) -> tuple[ArkProviderAdapter, AttemptStart, bytes, PolicySpec, AccuracyBudgetSpec]:
    contract = contract_fixture(response_format, response_schema=response_schema)
    budget = AccuracyBudgetSpec(
        requested_tokens=96,
        deadline_ms=100,
        physical_calls=1,
        retries=0,
    )
    policy = policy_fixture(contract, budget)
    packet = canonical_bytes(
        {
            "schema_version": "offline.causal.packet.v1",
            "measurements": [1.0, 0.99, 0.97],
        }
    )
    attempt = AttemptStart(
        attempt_id="ark-offline-attempt-001",
        policy_hash=policy.policy_hash,
        origin_hash="6" * 64,
        packet_hash=hashlib.sha256(packet).hexdigest(),
        arm=policy.arm,
        protocol=policy.protocol,
        physical_slot=0,
        requested_tokens=budget.requested_tokens,
        deadline_unix_ms=1100,
        started_unix_ms=1000,
    )
    adapter = ArkProviderAdapter(
        policy=policy,
        budget=budget,
        contract=contract,
        transport=transport,
    )
    return adapter, attempt, packet, policy, budget


def test_success_binds_exact_request_response_model_usage_and_raw_hash() -> None:
    transport = CapturingTransport(response_envelope())
    adapter, attempt, packet, policy, budget = invocation_fixture(transport)

    result = adapter.invoke(packet, attempt)

    assert result.status is AttemptStatus.SUCCESS
    assert result.response_text == canonical_bytes(DECISION).decode()
    assert result.input_tokens == 12
    assert result.output_tokens == 20
    assert result.provider_response_id is None
    assert result.provider_response_id_sha256 == hashlib.sha256(b"resp_safe_001").hexdigest()
    assert not result.late
    assert adapter.physical_attempts == 1
    assert len(transport.requests) == 1

    request = transport.requests[0]
    assert request.method == "POST"
    assert request.path == "/responses"
    assert request.timeout_ms == budget.deadline_ms
    assert request.deadline_unix_ms == attempt.deadline_unix_ms
    assert all(name.lower() != "authorization" for name, _ in request.headers)
    payload = json.loads(request.body)
    assert payload["model"] == "kimi-k3"
    assert payload["max_output_tokens"] == 96
    assert payload["stream"] is False
    assert payload["store"] is False
    assert payload["tools"] == []
    assert payload["tool_choice"] == "none"
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["text"]["format"]["strict"] is True
    assert not {
        "previous_response_id",
        "cache",
        "caching",
        "file",
        "url",
        "search",
    } & set(payload)

    audit = result.audit
    assert audit is not None
    assert audit.outcome is ArkClosedOutcome.SUCCESS
    assert audit.policy_hash == policy.policy_hash
    assert audit.arm is ArmId.D1_RAW
    assert audit.binding_manifest_hash == adapter.binding_manifest.manifest_hash
    assert adapter.binding_manifest.expected_response_schema_version == DIRECT_RESPONSE_SCHEMA_VERSION
    assert audit.packet_hash == attempt.packet_hash
    assert audit.prompt_hash == policy.prompt_hash
    assert audit.response_schema_hash == policy.response_schema_hash
    assert audit.decode_parameters_hash == policy.decode_parameters_hash
    assert audit.provider_rule_hash == policy.provider_rule_hash
    assert audit.model_version_rule_hash == policy.model_version_rule_hash
    assert audit.one_call_budget_hash == budget.budget_hash
    assert audit.requested_model_id == "kimi-k3"
    assert audit.resolved_model_id == "kimi-k3"
    assert audit.request_body_sha256 == request.body_sha256
    assert audit.raw_response_sha256 == hashlib.sha256(transport.result.body).hexdigest()
    assert audit.provider_response_id_sha256 == hashlib.sha256(b"resp_safe_001").hexdigest()
    assert audit.response_content_sha256 == hashlib.sha256(canonical_bytes(DECISION)).hexdigest()
    assert audit.usage_sha256 == canonical_sha256(
        {"input_tokens": 12, "output_tokens": 20, "total_tokens": 32}
    )
    assert audit.physical_attempts == 1
    assert audit.retries == 0
    assert len(audit.audit_hash) == 64


@pytest.mark.parametrize(
    "response_format",
    [
        ArkResponseFormat.PROMPT_ONLY,
        ArkResponseFormat.JSON_OBJECT,
        ArkResponseFormat.JSON_SCHEMA,
    ],
)
def test_provider_response_format_is_declared_but_local_schema_is_always_enforced(
    response_format: ArkResponseFormat,
) -> None:
    transport = CapturingTransport(response_envelope())
    adapter, attempt, packet, _, _ = invocation_fixture(
        transport, response_format=response_format
    )
    result = adapter.invoke(packet, attempt)
    assert result.status is AttemptStatus.SUCCESS
    payload = json.loads(transport.requests[0].body)
    if response_format is ArkResponseFormat.PROMPT_ONLY:
        assert "text" not in payload
    elif response_format is ArkResponseFormat.JSON_OBJECT:
        assert payload["text"] == {"format": {"type": "json_object"}}
    else:
        assert payload["text"]["format"]["type"] == "json_schema"


def test_policy_hash_mismatch_fails_before_transport() -> None:
    transport = CapturingTransport(response_envelope())
    contract = contract_fixture()
    budget = AccuracyBudgetSpec(96, 100, 1, 0)
    policy = replace(policy_fixture(contract, budget), prompt_hash="f" * 64)
    with pytest.raises(ArkBindingError, match="prompt_hash"):
        ArkProviderAdapter(
            policy=policy,
            budget=budget,
            contract=contract,
            transport=transport,
        )
    assert transport.requests == []


def test_arm_specific_schema_version_swap_fails_before_transport() -> None:
    swapped = json.loads(json.dumps(DECISION_SCHEMA))
    swapped["properties"]["schema_version"]["const"] = ACTION_RESPONSE_SCHEMA_VERSION
    contract = contract_fixture(response_schema=swapped)
    budget = AccuracyBudgetSpec(96, 100, 1, 0)
    policy = policy_fixture(contract, budget)
    transport = CapturingTransport(response_envelope())
    with pytest.raises(ArkBindingError, match="arm authority"):
        ArkProviderAdapter(
            policy=policy,
            budget=budget,
            contract=contract,
            transport=transport,
        )
    assert transport.requests == []


def test_noncanonical_or_attempt_mismatch_fails_without_consuming_slot() -> None:
    transport = CapturingTransport(response_envelope())
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    with pytest.raises(ArkBindingError, match="canonical"):
        adapter.invoke(b'{"b":2, "a":1}', attempt)
    assert adapter.physical_attempts == 0
    assert transport.requests == []

    wrong = replace(attempt, packet_hash="9" * 64)
    with pytest.raises(ArkBindingError, match="frozen"):
        adapter.invoke(packet, wrong)
    assert adapter.physical_attempts == 0
    assert transport.requests == []


def test_transport_exception_is_redacted_terminal_and_never_retried() -> None:
    secret = "CANARY_DO_NOT_PERSIST_transport"
    transport = CapturingTransport(RuntimeError(f"Authorization: Bearer {secret}"))
    adapter, attempt, packet, _, _ = invocation_fixture(transport)

    result = adapter.invoke(packet, attempt)

    assert result.status is AttemptStatus.ERROR
    assert result.error_code == "TRANSPORT_ERROR"
    assert result.audit is not None
    assert result.audit.outcome is ArkClosedOutcome.TRANSPORT_ERROR
    assert secret not in repr(result)
    assert secret not in canonical_bytes(result.audit).decode()
    assert len(transport.requests) == 1
    assert adapter.physical_attempts == 1
    with pytest.raises(ArkInvocationError, match="consumed"):
        adapter.invoke(packet, attempt)
    assert len(transport.requests) == 1


def test_model_mismatch_is_closed_and_binds_resolved_identity() -> None:
    transport = CapturingTransport(response_envelope(model="glm-5.3"))
    adapter, attempt, packet, _, _ = invocation_fixture(transport)

    result = adapter.invoke(packet, attempt)

    assert result.status is AttemptStatus.MODEL_MISMATCH
    assert result.response_text is None
    assert result.audit is not None
    assert result.audit.outcome is ArkClosedOutcome.MODEL_MISMATCH
    assert result.audit.requested_model_id == "kimi-k3"
    assert result.audit.resolved_model_id == "glm-5.3"
    assert result.audit.resolved_model_hash == result.observed_model_hash
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "decision_text",
    [
        '{"schema_version":"CAPDirectForecastResponse.v1","value":0.5,"extra":1}',
        '{"schema_version":"CAPDirectForecastResponse.v1","value":"0.5"}',
        '{"schema_version":"CAPDirectForecastResponse.v1","value":0.4,"value":0.5}',
        '{"schema_version":"CAPDirectForecastResponse.v1","value":NaN}',
        "not-json",
    ],
)
def test_local_strict_schema_fails_closed_for_every_provider_mode(
    decision_text: str,
) -> None:
    transport = CapturingTransport(response_envelope(decision_text=decision_text))
    adapter, attempt, packet, _, _ = invocation_fixture(
        transport, response_format=ArkResponseFormat.PROMPT_ONLY
    )
    result = adapter.invoke(packet, attempt)
    assert result.status is AttemptStatus.ERROR
    assert result.response_text is None
    assert result.audit is not None
    assert result.audit.outcome is ArkClosedOutcome.INVALID_RESPONSE
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "usage",
    [
        {},
        {"input_tokens": 12, "total_tokens": 12},
        {"output_tokens": 20, "total_tokens": 20},
        {"input_tokens": 12, "output_tokens": 97, "total_tokens": 109},
        {"input_tokens": -1, "output_tokens": 20, "total_tokens": 20},
        {"input_tokens": "12", "output_tokens": 20, "total_tokens": 32},
        {"input_tokens": 12, "output_tokens": 20, "total_tokens": 31},
        {"input_tokens": 12, "output_tokens": 20, "total_tokens": 32, "mystery": 1},
        {"input_tokens": True, "output_tokens": 20, "total_tokens": 21},
    ],
)
def test_unknown_or_inconsistent_usage_consumes_slot_and_fails_closed(usage: Any) -> None:
    transport = CapturingTransport(response_envelope(usage=usage))
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    result = adapter.invoke(packet, attempt)
    assert result.status is AttemptStatus.ERROR
    assert result.audit is not None
    assert result.audit.outcome is ArkClosedOutcome.INVALID_RESPONSE
    assert adapter.physical_attempts == 1
    assert len(transport.requests) == 1


@pytest.mark.parametrize("usage_override", [None, "missing"])
def test_missing_usage_accepts_valid_prediction_as_unknown(usage_override: Any) -> None:
    response = response_envelope(extra={"usage": None})
    if usage_override == "missing":
        envelope = json.loads(response.body)
        del envelope["usage"]
        response = ArkTransportResponse(200, canonical_bytes(envelope), 1050)
    transport = CapturingTransport(response)
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    ephemeral = adapter.invoke(packet, attempt)
    assert ephemeral.status is AttemptStatus.SUCCESS
    assert ephemeral.input_tokens is None
    assert ephemeral.output_tokens is None
    assert ephemeral.audit is not None
    assert ephemeral.audit.usage_sha256 is None
    assert ephemeral.audit.total_tokens is None
    durable = _closed_result(attempt, ephemeral)
    assert durable.status is AttemptStatus.SUCCESS
    assert durable.usage_status.value == "UNKNOWN"
    assert durable.provider_evidence is not None


@pytest.mark.parametrize("fault", ["missing_model", "oversize"])
def test_missing_resolved_model_or_oversize_response_fails_closed(fault: str) -> None:
    normal = response_envelope()
    if fault == "missing_model":
        envelope = json.loads(normal.body)
        del envelope["model"]
        response = ArkTransportResponse(200, canonical_bytes(envelope), 1050)
    else:
        response = ArkTransportResponse(200, b"x" * 2_000_001, 1050)
    transport = CapturingTransport(response)
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    result = adapter.invoke(packet, attempt)
    assert result.status is AttemptStatus.ERROR
    assert result.response_text is None
    assert result.audit is not None
    assert result.audit.outcome is ArkClosedOutcome.INVALID_RESPONSE
    assert result.audit.resolved_model_id is None
    assert len(transport.requests) == 1


def test_late_response_is_bound_and_marked_for_runner_fallback() -> None:
    transport = CapturingTransport(response_envelope(completed=1101))
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    result = adapter.invoke(packet, attempt)
    assert result.status is AttemptStatus.SUCCESS
    assert result.late
    assert result.audit is not None
    assert result.audit.outcome is ArkClosedOutcome.LATE_RESPONSE
    assert result.audit.completed_unix_ms == 1101


def test_compact_audit_is_validated_and_persisted_in_attempt_evidence(tmp_path: Path) -> None:
    transport = CapturingTransport(response_envelope())
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    ephemeral = adapter.invoke(packet, attempt)

    result = _closed_result(attempt, ephemeral)
    assert result.status is AttemptStatus.SUCCESS
    assert result.provider_evidence is not None
    assert result.provider_evidence_hash == canonical_sha256(result.provider_evidence)
    assert (
        result.provider_evidence["invocation_audit"]["raw_response_sha256"]
        == ephemeral.audit.raw_response_sha256
    )
    assert "response_text" not in result.provider_evidence
    assert "provider_response_id" not in result.provider_evidence

    ledger_path = tmp_path / "attempt.jsonl"
    with CanonicalJSONLLedger(ledger_path, LedgerKind.ATTEMPT) as ledger:
        started_hash = ledger.append_started(attempt)
        ledger.append_finished(started_hash, result)
    records = read_verified_ledger_records(ledger_path, expected_kind=LedgerKind.ATTEMPT)
    persisted = records[-1]["payload"]
    assert persisted["provider_evidence"] == json.loads(
        canonical_bytes(result.provider_evidence)
    )
    assert persisted["provider_evidence_hash"] == result.provider_evidence_hash
    assert transport.result.body not in ledger_path.read_bytes()


def test_runner_rejects_audit_that_does_not_bind_attempt() -> None:
    transport = CapturingTransport(response_envelope())
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    ephemeral = adapter.invoke(packet, attempt)
    assert ephemeral.audit is not None
    tampered = replace(ephemeral, audit=replace(ephemeral.audit, packet_hash="7" * 64))
    result = _closed_result(attempt, tampered)
    assert result.status is AttemptStatus.ERROR
    assert result.error_code.value == "BINDING_MISMATCH"
    assert result.provider_evidence is None
    assert result.provider_evidence_hash is None


@pytest.mark.parametrize(
    "field_name",
    [
        "ephemeral_request_body_sha256",
        "ephemeral_raw_response_sha256",
        "ephemeral_response_content_sha256",
        "ephemeral_provider_response_id_sha256",
    ],
)
def test_runner_rejects_every_ephemeral_hash_cross_binding(field_name: str) -> None:
    transport = CapturingTransport(response_envelope())
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    ephemeral = adapter.invoke(packet, attempt)
    tampered = replace(ephemeral, **{field_name: "f" * 64})
    result = _closed_result(attempt, tampered)
    assert result.status is AttemptStatus.ERROR
    assert result.error_code.value == "BINDING_MISMATCH"
    assert result.provider_evidence is None


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("policy", "prompt_hash"), "f" * 64),
        (("budget", "requested_tokens"), 95),
        (("binding_manifest", "registry_hash"), "f" * 64),
        (("invocation_audit", "deadline_unix_ms"), 1099),
        (("invocation_audit", "request_contract_hash"), "f" * 64),
        (("request_contract", "prompt", "instructions"), "Changed frozen prompt."),
        (("request_contract", "decode", "temperature"), 0.1),
        (("request_contract", "provider", "response_schema_name"), "swapped_schema"),
        (
            (
                "request_contract",
                "model",
                "capability_snapshot",
                "model_list_artifact_sha256",
            ),
            "f" * 64,
        ),
        (
            ("request_contract", "response_schema", "properties", "value", "maximum"),
            0.9,
        ),
    ],
)
def test_posthoc_ledger_rejects_rehashed_semantic_evidence_tamper(
    tmp_path: Path,
    path: tuple[str, ...],
    replacement: Any,
) -> None:
    transport = CapturingTransport(response_envelope())
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    result = _closed_result(attempt, adapter.invoke(packet, attempt))
    ledger_path = tmp_path / "attempt.jsonl"
    with CanonicalJSONLLedger(ledger_path, LedgerKind.ATTEMPT) as ledger:
        started_hash = ledger.append_started(attempt)
        ledger.append_finished(started_hash, result)

    records = [json.loads(line) for line in ledger_path.read_bytes().splitlines()]
    target = records[-1]["payload"]["provider_evidence"]
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = replacement
    records[-1]["payload"]["provider_evidence_hash"] = canonical_sha256(
        records[-1]["payload"]["provider_evidence"]
    )
    body = {key: value for key, value in records[-1].items() if key != "record_hash"}
    records[-1]["record_hash"] = canonical_sha256(body)
    ledger_path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in records))

    with pytest.raises(LedgerIntegrityError):
        read_verified_ledger_records(ledger_path, expected_kind=LedgerKind.ATTEMPT)


def test_capability_snapshot_requires_exact_intersection_and_membership() -> None:
    with pytest.raises(ArkBindingError, match="equal the authenticated intersection"):
        ArkCapabilitySnapshot(
            model_list_artifact_sha256="a" * 64,
            text_resources_artifact_sha256="b" * 64,
            authenticated_model_ids=("glm-5.3", "kimi-k3"),
            text_resource_model_ids=("kimi-k3",),
            eligible_model_ids=("glm-5.3",),
        )
    with pytest.raises(ArkBindingError, match="absent from the authenticated intersection"):
        ArkModelRule("glm-5.3", CAPABILITY)


def test_secret_in_packet_or_raw_response_never_appears_in_closed_result() -> None:
    canary = "CANARY_DO_NOT_PERSIST_response"
    raw = ArkTransportResponse(
        200,
        canonical_bytes(
            {
                "id": "resp_safe_001",
                "model": "kimi-k3",
                "object": "response",
                "output": [],
                "status": "completed",
                "store": False,
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                "metadata": {"debug": canary},
            }
        ),
        1050,
    )
    transport = CapturingTransport(raw)
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    result = adapter.invoke(packet, attempt)
    assert result.status is AttemptStatus.ERROR
    assert result.audit is not None
    assert result.audit.raw_response_sha256 == hashlib.sha256(raw.body).hexdigest()
    assert canary not in repr(result)
    assert canary not in canonical_bytes(result.audit).decode()

    second_transport = CapturingTransport(response_envelope())
    second, second_attempt, _, _, _ = invocation_fixture(second_transport)
    tainted_packet = canonical_bytes({"note": canary})
    tainted_attempt = replace(
        second_attempt,
        packet_hash=hashlib.sha256(tainted_packet).hexdigest(),
    )
    with pytest.raises(ArkBindingError, match="secret-like"):
        second.invoke(tainted_packet, tainted_attempt)
    assert second.physical_attempts == 0
    assert second_transport.requests == []


def test_http_error_hashes_body_without_leaking_or_retrying() -> None:
    canary = b"Authorization: Bearer CANARY_DO_NOT_PERSIST_http"
    transport = CapturingTransport(ArkTransportResponse(403, canary, 1025, "text/plain"))
    adapter, attempt, packet, _, _ = invocation_fixture(transport)
    result = adapter.invoke(packet, attempt)
    assert result.status is AttemptStatus.ERROR
    assert result.audit is not None
    assert result.audit.outcome is ArkClosedOutcome.HTTP_ERROR
    assert result.audit.http_status == 403
    assert result.audit.raw_response_sha256 == hashlib.sha256(canary).hexdigest()
    assert canary.decode() not in repr(result)
    assert len(transport.requests) == 1


def test_unsupported_schema_keyword_and_mutation_are_rejected_or_detached() -> None:
    with pytest.raises(ArkBindingError, match="strict response schema"):
        contract_fixture(response_schema={"$ref": "https://example.invalid/schema"})
    with pytest.raises(ArkBindingError, match="strict response schema"):
        contract_fixture(
            response_schema={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": True,
            }
        )

    mutable = json.loads(json.dumps(DECISION_SCHEMA))
    contract = contract_fixture(response_schema=mutable)
    frozen_hash = contract.response_schema_hash
    mutable["properties"]["value"]["maximum"] = 99.0
    assert contract.response_schema_hash == frozen_hash


def test_adapter_source_has_no_environment_network_or_retry_client() -> None:
    source = Path("experiments/vfps_agent/ark_provider.py").read_text(encoding="utf-8")
    forbidden = (
        "import os",
        "import socket",
        "import subprocess",
        "import urllib",
        "import requests",
        "os.environ",
    )
    assert not any(token in source for token in forbidden)
