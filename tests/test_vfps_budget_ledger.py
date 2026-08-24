from __future__ import annotations

import os
from pathlib import Path

import pytest

from experiments.vfps_agent.budget import AccuracyV1Budget, AttemptBudgetError, execute_mock_accuracy_v1
from experiments.vfps_agent.canonical import canonical_bytes, canonical_json, canonical_sha256
from experiments.vfps_agent.contracts import (
    ArmId,
    AttemptStatus,
    CommitDisposition,
    ForecastKey,
    OriginPacketV2,
    PacketKind,
    PolicySpec,
    ProtocolId,
    RevealedObservation,
    UsageStatus,
)
from experiments.vfps_agent.ledger import (
    CanonicalJSONLLedger,
    LedgerIntegrityError,
    LedgerKind,
    verify_ledger,
)
from experiments.vfps_agent.provider import MockProvider


def _packet() -> OriginPacketV2:
    return OriginPacketV2(
        packet_kind=PacketKind.RAW,
        opaque_origin_hash="1" * 64,
        availability_cutoff=10.0,
        forecast_keys=(ForecastKey("capacity", 1, "F"),),
        revealed_observations=(
            RevealedObservation(
                event_index=0,
                observed_at=1.0,
                available_at=2.0,
                measurements={"capacity": 1.0},
            ),
        ),
        normalization={"scale": 1.0},
    )


def _policy() -> PolicySpec:
    hashes = [f"{digit:x}" * 64 for digit in range(2, 14)]
    return PolicySpec(
        policy_id="direct-raw-mock",
        generation=1,
        protocol=ProtocolId.ACCURACY_V1,
        arm=ArmId.D1_RAW,
        provider_rule_hash=hashes[0],
        model_version_rule_hash=hashes[1],
        prompt_hash=hashes[2],
        packet_schema_hash=hashes[3],
        response_schema_hash=hashes[4],
        grammar_hash=hashes[5],
        registry_hash=hashes[6],
        decode_parameters_hash=hashes[7],
        one_call_budget_hash=hashes[8],
        verifier_hash=hashes[9],
        fallback_hash=hashes[10],
        capability_snapshot_hash=hashes[11],
    )


def _ledgers(tmp_path: Path) -> tuple[CanonicalJSONLLedger, CanonicalJSONLLedger]:
    return (
        CanonicalJSONLLedger(tmp_path / "attempt.jsonl", LedgerKind.ATTEMPT),
        CanonicalJSONLLedger(tmp_path / "prediction.jsonl", LedgerKind.PREDICTION),
    )


def _formal_access_payload() -> dict[str, object]:
    return {
        "schema_version": "CAPEventAccess.v1",
        "phase": "BOOTSTRAP",
        "revealed_event_index": 0,
        "observation_hash": "a" * 64,
        "checkpoint_record_hash": None,
        "commit_id": None,
    }


def _formal_checkpoint_payload() -> dict[str, object]:
    return {
        "schema_version": "CAPOriginCheckpoint.v1",
        "attempt_id": "1" * 64,
        "commit_id": "2" * 64,
        "policy_hash": "3" * 64,
        "origin_hash": "4" * 64,
        "origin_event_index": 0,
        "packet_hash": "5" * 64,
        "attempt_final_record_hash": "6" * 64,
        "prediction_record_hash": "7" * 64,
        "execution_record_hashes": [
            {"key_token": "capacity|1|F", "record_hash": "8" * 64}
        ],
        "planned_key_count": 1,
    }


def test_started_is_durable_before_provider_and_accuracy_has_no_retry(tmp_path: Path) -> None:
    attempt_ledger, prediction_ledger = _ledgers(tmp_path)

    def assert_started(_: object) -> None:
        report = verify_ledger(tmp_path / "attempt.jsonl", expected_kind=LedgerKind.ATTEMPT)
        assert report.record_count == 1
        assert report.status == "UNKNOWN_ATTEMPTS"

    provider = MockProvider(
        response_text='{"capacity_h1":0.91}',
        input_tokens=None,
        output_tokens=None,
        before_return=assert_started,
    )
    budget = AccuracyV1Budget()
    result, commit = execute_mock_accuracy_v1(
        provider=provider,
        policy=_policy(),
        packet=_packet(),
        budget=budget,
        attempt_ledger=attempt_ledger,
        prediction_ledger=prediction_ledger,
        fallback_prediction={"capacity_h1": 0.80},
        attempt_id="attempt-0001",
        requested_tokens=256,
        started_unix_ms=1_000,
        deadline_unix_ms=2_000,
    )
    assert provider.physical_attempts == 1
    assert result.status is AttemptStatus.SUCCESS
    assert result.usage_status is UsageStatus.UNKNOWN
    assert commit.disposition is CommitDisposition.PREDICTION
    assert commit.prediction == {"capacity_h1": 0.91}

    with pytest.raises(AttemptBudgetError, match="no retry"):
        execute_mock_accuracy_v1(
            provider=provider,
            policy=_policy(),
            packet=_packet(),
            budget=budget,
            attempt_ledger=attempt_ledger,
            prediction_ledger=prediction_ledger,
            fallback_prediction={"capacity_h1": 0.80},
            attempt_id="attempt-0002",
            requested_tokens=256,
            started_unix_ms=2_000,
            deadline_unix_ms=3_000,
        )
    assert provider.physical_attempts == 1

    attempt_ledger.seal(tmp_path / "attempt.seal.json")
    prediction_ledger.seal(tmp_path / "prediction.seal.json")
    attempt_ledger.close()
    prediction_ledger.close()
    attempt_report = verify_ledger(
        tmp_path / "attempt.jsonl",
        expected_kind=LedgerKind.ATTEMPT,
        seal_path=tmp_path / "attempt.seal.json",
    )
    prediction_report = verify_ledger(
        tmp_path / "prediction.jsonl",
        expected_kind=LedgerKind.PREDICTION,
        seal_path=tmp_path / "prediction.seal.json",
    )
    assert attempt_report.status == "PASS"
    assert prediction_report.status == "PASS"


def test_late_response_commits_exact_fallback_and_cannot_overwrite(tmp_path: Path) -> None:
    attempt_ledger, prediction_ledger = _ledgers(tmp_path)
    provider = MockProvider(
        response_text='{"capacity_h1":9.99}',
        input_tokens=10,
        output_tokens=4,
        force_late=True,
    )
    result, commit = execute_mock_accuracy_v1(
        provider=provider,
        policy=_policy(),
        packet=_packet(),
        budget=AccuracyV1Budget(),
        attempt_ledger=attempt_ledger,
        prediction_ledger=prediction_ledger,
        fallback_prediction={"capacity_h1": 0.80},
        attempt_id="late-attempt",
        requested_tokens=64,
        started_unix_ms=1_000,
        deadline_unix_ms=2_000,
    )
    assert result.late is True
    assert result.usage_status is UsageStatus.REPORTED
    assert commit.disposition is CommitDisposition.FALLBACK
    assert commit.prediction == {"capacity_h1": 0.80}
    assert commit.late_response_ignored is True
    with pytest.raises(LedgerIntegrityError, match="overwrite"):
        prediction_ledger.append_prediction(commit)
    attempt_ledger.close()
    prediction_ledger.close()


def test_crash_left_started_is_counted_unknown(tmp_path: Path) -> None:
    ledger = CanonicalJSONLLedger(tmp_path / "attempt.jsonl", LedgerKind.ATTEMPT)
    start = AccuracyV1Budget().reserve(
        attempt_id="crash-attempt",
        policy=_policy(),
        packet=_packet(),
        requested_tokens=32,
        started_unix_ms=100,
        deadline_unix_ms=200,
    )
    ledger.append_started(start)
    ledger.close()
    report = verify_ledger(tmp_path / "attempt.jsonl", expected_kind=LedgerKind.ATTEMPT)
    assert report.status == "UNKNOWN_ATTEMPTS"
    assert report.incomplete_attempt_ids == ("crash-attempt",)


def test_existing_and_symlink_outputs_are_refused(tmp_path: Path) -> None:
    existing = tmp_path / "existing.jsonl"
    existing.write_text("occupied", encoding="utf-8")
    with pytest.raises(LedgerIntegrityError):
        CanonicalJSONLLedger(existing, LedgerKind.ATTEMPT)

    target = tmp_path / "target.jsonl"
    target.write_text("target", encoding="utf-8")
    link = tmp_path / "link.jsonl"
    os.symlink(target, link)
    with pytest.raises(LedgerIntegrityError):
        CanonicalJSONLLedger(link, LedgerKind.ATTEMPT)


def test_tampering_fails_closed_even_if_json_remains_parseable(tmp_path: Path) -> None:
    ledger = CanonicalJSONLLedger(tmp_path / "checkpoint.jsonl", LedgerKind.CHECKPOINT)
    ledger.append_checkpoint(_formal_checkpoint_payload())
    ledger.seal(tmp_path / "checkpoint.seal.json")
    ledger.close()
    original = (tmp_path / "checkpoint.jsonl").read_text(encoding="utf-8")
    (tmp_path / "checkpoint.jsonl").write_text(
        original.replace('"origin_event_index":0', '"origin_event_index":1'),
        encoding="utf-8",
    )
    with pytest.raises(LedgerIntegrityError):
        verify_ledger(
            tmp_path / "checkpoint.jsonl",
            expected_kind=LedgerKind.CHECKPOINT,
            seal_path=tmp_path / "checkpoint.seal.json",
        )


def test_access_checkpoint_and_seals_are_separate_files(tmp_path: Path) -> None:
    access = CanonicalJSONLLedger(tmp_path / "access.jsonl", LedgerKind.ACCESS)
    checkpoint = CanonicalJSONLLedger(tmp_path / "checkpoint.jsonl", LedgerKind.CHECKPOINT)
    access.append_access(_formal_access_payload())
    checkpoint.append_checkpoint(_formal_checkpoint_payload())
    access.seal(tmp_path / "access.seal.json")
    checkpoint.seal(tmp_path / "checkpoint.seal.json")
    access.close()
    checkpoint.close()
    assert len({path.name for path in tmp_path.iterdir()}) == 4
    assert "seal_hash" not in (tmp_path / "access.jsonl").read_text(encoding="utf-8")
    assert canonical_json({"x": 1}) == '{"x":1}'


def test_rehashed_surplus_access_field_is_still_rejected(tmp_path: Path) -> None:
    path = tmp_path / "access.jsonl"
    ledger = CanonicalJSONLLedger(path, LedgerKind.ACCESS)
    ledger.append_access(_formal_access_payload())
    ledger.close()
    import json

    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["unexpected"] = True
    body = {key: value for key, value in record.items() if key != "record_hash"}
    record["record_hash"] = canonical_sha256(body)
    path.write_bytes(canonical_bytes(record) + b"\n")
    with pytest.raises(LedgerIntegrityError, match="schema mismatch"):
        verify_ledger(path, expected_kind=LedgerKind.ACCESS)
