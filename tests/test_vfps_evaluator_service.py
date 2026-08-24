from __future__ import annotations

import hashlib
import os
import copy
from dataclasses import replace

import pytest

import experiments.vfps_agent.evaluator_service as evaluator_module
from experiments.vfps_agent.canonical import canonical_bytes, strict_canonical_loads
from experiments.vfps_agent.contracts import ArmId, CausalPacketSchema, PacketKind
from experiments.vfps_agent.evaluator_service import (
    EvaluatorProtocolError,
    start_isolated_evaluator,
)
from experiments.vfps_agent.provider import MockProvider
from experiments.vfps_agent.ledger import LedgerKind, read_verified_ledger_records
from experiments.vfps_agent.runner import CAPAccuracyRun
from tests.test_capact_m2_runner import (
    budget_fixture,
    direct_response,
    hidden_events,
    policy_fixture,
    registry_fixture,
    split_fixture,
)


def evaluator_schema() -> CausalPacketSchema:
    return CausalPacketSchema(
        measurement_fields=("capacity",),
        missingness_fields=("capacity",),
        diagnostic_fields=("f0", "f1", "f2", "f3", "f4"),
    )


def launch(run_dir, *, events=None, fault_after_inflight=None, fault_after_completed=None):
    registry = registry_fixture()
    schema = evaluator_schema()
    budget = budget_fixture(ArmId.D1_PACKET)
    allowed_policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    supervisor, client = start_isolated_evaluator(
        run_dir,
        events=hidden_events() if events is None else events,
        context=3,
        causal_schema=schema,
        split=split_fixture(),
        registry=registry,
        packet_kind=PacketKind.HYBRID,
        allowed_policy_hashes=(allowed_policy.policy_hash,),
        diagnostic_bins={f"f{index}": "a" for index in range(5)},
        _fault_after_inflight=fault_after_inflight,
        _fault_after_completed=fault_after_completed,
    )
    return registry, schema, supervisor, client


def run_one_origin(run, client, registry, schema, *, started=1000):
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    provider = MockProvider(response_text=direct_response(registry))
    result = run.run_origin(
        provider=provider,
        policy=policy,
        packet=client.build_current_packet(),
        registry=registry,
        budget=budget,
        started_unix_ms=started,
    )
    assert provider.physical_attempts == 1
    return result


def close_pair(supervisor, client) -> None:
    client.close()
    supervisor.close()


def test_isolated_evaluator_holds_only_prefix_in_prediction_client_and_scores_after_seal(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(run_dir)
        try:
            assert client.evaluator_pid != os.getpid()
            assert not hasattr(client, "_events")
            assert not hasattr(client, "_state_key")
            assert [item.event_index for item in client.current_prefix()] == [0, 1, 2]
            assert [item.measurements["capacity"] for item in client.current_prefix()] == [1.0, 0.99, 0.98]

            first = run_one_origin(run, client, registry, schema, started=1000)
            assert client.reveal_next_after_checkpoint(first.checkpoint_record_hash).event_index == 3
            second = run_one_origin(run, client, registry, schema, started=1100)
            assert client.reveal_next_after_checkpoint(second.checkpoint_record_hash).event_index == 4
            run_one_origin(run, client, registry, schema, started=1200)

            run.seal_prediction_phase()
            result = client.finalize_and_score()
            assert result.prediction_count == 3
            assert result.execution_count == result.maturity_count == 6
            assert result.matured_count == 2
            assert result.never_matured_count == 4
        finally:
            close_pair(supervisor, client)


def test_evaluator_rejects_reveal_without_a_durable_checkpoint_and_stays_aborted(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir):
        _registry, _schema, supervisor, client = launch(run_dir)
        with pytest.raises(EvaluatorProtocolError, match="rejected"):
            client.reveal_next_after_checkpoint("f" * 64)
        supervisor.close()
        with pytest.raises(EvaluatorProtocolError, match="failed during startup"):
            supervisor.restart(client, events=hidden_events(), timeout=2.0)


def test_evaluator_rejects_checkpoint_from_unfrozen_policy_generation(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(run_dir)
        budget = budget_fixture(ArmId.D1_PACKET)
        unfrozen = replace(
            policy_fixture(ArmId.D1_PACKET, registry, schema, budget), generation=2
        )
        provider = MockProvider(response_text=direct_response(registry))
        checkpoint = run.run_origin(
            provider=provider,
            policy=unfrozen,
            packet=client.build_current_packet(),
            registry=registry,
            budget=budget,
            started_unix_ms=1000,
        )
        with pytest.raises(EvaluatorProtocolError, match="rejected"):
            client.reveal_next_after_checkpoint(checkpoint.checkpoint_record_hash)
        supervisor.close()


def test_early_finalize_fails_before_access_seal_or_any_maturity_label_write(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(run_dir)
        run_one_origin(run, client, registry, schema)
        run.seal_prediction_phase()
        access_before = (run_dir / "ACCESS_LEDGER.jsonl").read_bytes()
        with pytest.raises(EvaluatorProtocolError) as caught:
            client.finalize_and_score()
        assert "FINALIZE_REJECTED" in str(caught.value)
        assert "CAPM2Error" not in str(caught.value)
        assert "complete replay" not in str(caught.value)
        supervisor.close()

    assert (run_dir / "ACCESS_LEDGER.jsonl").read_bytes() == access_before
    assert not (run_dir / "ACCESS_LEDGER.seal.json").exists()
    assert not (run_dir / "MATURITY_LEDGER.jsonl").exists()
    assert not (run_dir / "MATURITY_LEDGER.seal.json").exists()
    assert not (run_dir / "RUN_SEAL.json").exists()
    assert [item.measurements["capacity"] for item in client.current_prefix()] == [1.0, 0.99, 0.98]
    assert client._closed


def test_evaluator_can_restart_between_completed_requests_without_hidden_data_in_client(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(run_dir)
        first_pid = client.evaluator_pid
        supervisor.crash()
        supervisor.restart(client, events=hidden_events())
        try:
            assert client.evaluator_pid != first_pid
            assert client.revealed_count == 3
            result = run_one_origin(run, client, registry, schema)
            revealed = client.reveal_next_after_checkpoint(result.checkpoint_record_hash)
            assert revealed.event_index == 3
        finally:
            close_pair(supervisor, client)


def test_restart_rejects_a_different_hidden_stream_binding(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir):
        _registry, _schema, supervisor, client = launch(run_dir)
        supervisor.crash()
        with pytest.raises(EvaluatorProtocolError, match="failed during startup"):
            supervisor.restart(client, events=hidden_events(altered_suffix=True), timeout=2.0)
        client.close()


def test_restart_rejects_non_event_launch_configuration_drift(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir):
        _registry, _schema, supervisor, client = launch(run_dir)
        supervisor.crash()
        supervisor._diagnostics = {f"f{index}": "b" for index in range(5)}
        with pytest.raises(EvaluatorProtocolError, match="failed during startup"):
            supervisor.restart(client, events=hidden_events(), timeout=2.0)
        client.close()


def test_launch_binding_covers_every_hidden_execution_configuration_field() -> None:
    registry = registry_fixture()
    schema = evaluator_schema()
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    events = tuple(
        evaluator_module._observation_payload(item.revealed()) for item in hidden_events()
    )
    payload = evaluator_module._launch_binding_payload(
        event_payloads=events,
        context=3,
        causal_schema=schema,
        split=split_fixture(),
        registry=registry,
        packet_kind=PacketKind.HYBRID,
        allowed_policy_hashes=(policy.policy_hash,),
        normalization={},
        allowed_conditions={},
        train_error_summaries={},
        diagnostic_bins={f"f{index}": "a" for index in range(5)},
    )
    expected = {
        "schema_version", "events", "context", "causal_schema", "split", "registry",
        "packet_kind", "allowed_policy_hashes", "normalization", "allowed_conditions",
        "train_error_summaries", "diagnostic_bins",
    }
    assert set(payload) == expected
    baseline = evaluator_module.canonical_sha256(payload)
    for field in expected - {"schema_version"}:
        altered = copy.deepcopy(payload)
        altered[field] = {"drift": field}
        assert evaluator_module.canonical_sha256(altered) != baseline


def test_crash_after_access_fsync_recovers_exact_pending_request_idempotently(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(
            run_dir, fault_after_inflight="REVEAL"
        )
        result = run_one_origin(run, client, registry, schema)
        with pytest.raises(EvaluatorProtocolError, match="closed or returned invalid JSON"):
            client.reveal_next_after_checkpoint(result.checkpoint_record_hash, timeout=3.0)
        supervisor.close()
        assert supervisor.exitcode == 93
        supervisor.restart(client, events=hidden_events(), timeout=2.0)
        try:
            recovered = client.reveal_next_after_checkpoint(result.checkpoint_record_hash)
            assert recovered.event_index == 3
            access = read_verified_ledger_records(
                run_dir / "ACCESS_LEDGER.jsonl", expected_kind=LedgerKind.ACCESS
            )
            assert [item["payload"]["revealed_event_index"] for item in access] == [0, 1, 2, 3]
        finally:
            close_pair(supervisor, client)


def test_crash_after_completed_fsync_before_reply_replays_byte_identical_response(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(
            run_dir, fault_after_completed="REVEAL"
        )
        result = run_one_origin(run, client, registry, schema)
        with pytest.raises(EvaluatorProtocolError, match="closed or returned invalid JSON"):
            client.reveal_next_after_checkpoint(result.checkpoint_record_hash, timeout=3.0)
        supervisor.close()
        assert supervisor.exitcode == 94
        state_before = (run_dir / "EVALUATOR_SESSION.jsonl").read_bytes()
        supervisor.restart(client, events=hidden_events(), timeout=2.0)
        try:
            recovered = client.reveal_next_after_checkpoint(result.checkpoint_record_hash)
            assert recovered.event_index == 3
            assert (run_dir / "EVALUATOR_SESSION.jsonl").read_bytes() == state_before
            access = read_verified_ledger_records(
                run_dir / "ACCESS_LEDGER.jsonl", expected_kind=LedgerKind.ACCESS
            )
            assert [item["payload"]["revealed_event_index"] for item in access] == [0, 1, 2, 3]
        finally:
            close_pair(supervisor, client)


def _send_adversarial_frame(client, frame: bytes) -> None:
    client._connection.send_bytes(frame)
    assert client._connection.poll(3.0)
    with pytest.raises(EOFError):
        client._connection.recv_bytes()
    client._closed = True


@pytest.mark.parametrize("attack", ["reorder", "nonce_reuse", "id_reuse"])
def test_duplicate_reorder_and_tamper_are_terminal_across_restart(tmp_path, attack) -> None:
    run_dir = tmp_path / attack
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(run_dir)
        result = run_one_origin(run, client, registry, schema)
        raw, request = client._encode_request(
            "REVEAL", {"checkpoint_record_hash": result.checkpoint_record_hash}
        )
        mutated = strict_canonical_loads(raw)
        if attack in {"nonce_reuse", "id_reuse"}:
            state_records = [
                strict_canonical_loads(line)
                for line in (run_dir / "EVALUATOR_SESSION.jsonl").read_bytes().splitlines()
            ]
            bootstrap = next(item for item in state_records if item["phase"] == "IN_FLIGHT")
            if attack == "nonce_reuse":
                mutated["nonce"] = bootstrap["request_nonce"]
            else:
                mutated["request_id"] = bootstrap["request_id"]
        else:
            mutated["sequence"] += 1
        body = {
            key: value
            for key, value in mutated.items()
            if key not in {"request_hash", "auth_tag"}
        }
        mutated["request_hash"] = evaluator_module.canonical_sha256(body)
        authenticated = {
            key: value for key, value in mutated.items() if key != "auth_tag"
        }
        mutated["auth_tag"] = evaluator_module._hmac_hex(
            client._capability, authenticated
        )
        frame = canonical_bytes(mutated)
        _send_adversarial_frame(client, frame)
        supervisor.close()
        with pytest.raises(EvaluatorProtocolError, match="failed during startup"):
            supervisor.restart(client, events=hidden_events(), timeout=2.0)


def test_unauthenticated_tamper_and_cross_session_bytes_leave_durable_state_unchanged(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(run_dir)
        result = run_one_origin(run, client, registry, schema)
        raw, _request = client._encode_request(
            "REVEAL", {"checkpoint_record_hash": result.checkpoint_record_hash}
        )
        mutated = strict_canonical_loads(raw)
        mutated["payload"]["checkpoint_record_hash"] = hashlib.sha256(b"tamper").hexdigest()
        state_path = run_dir / "EVALUATOR_SESSION.jsonl"
        before = state_path.read_bytes()
        _send_adversarial_frame(client, canonical_bytes(mutated))
        supervisor.close()
        assert state_path.read_bytes() == before
        supervisor.restart(client, events=hidden_events(), timeout=2.0)
        close_pair(supervisor, client)


def test_duplicate_checkpoint_and_exact_transport_replay_return_same_event_without_state_change(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        registry, schema, supervisor, client = launch(run_dir)
        try:
            result = run_one_origin(run, client, registry, schema)
            first = client.reveal_next_after_checkpoint(result.checkpoint_record_hash)
            access_path = run_dir / "ACCESS_LEDGER.jsonl"
            access_before = access_path.read_bytes()
            state_path = run_dir / "EVALUATOR_SESSION.jsonl"
            state_before_duplicate = state_path.read_bytes()
            duplicate = client.reveal_next_after_checkpoint(result.checkpoint_record_hash)
            assert duplicate == first
            assert access_path.read_bytes() == access_before
            assert state_path.read_bytes() != state_before_duplicate

            # A fresh duplicate request is auditable, but the transport replay
            # of that exact final request is byte-identical and state-neutral.
            pending_raw, pending_request = client._encode_request(
                "REVEAL", {"checkpoint_record_hash": result.checkpoint_record_hash}
            )
            client._connection.send_bytes(pending_raw)
            first_response = client._receive_response(pending_request, timeout=3.0)
            state_before_replay = state_path.read_bytes()
            client._connection.send_bytes(pending_raw)
            assert client._connection.poll(3.0)
            replay_response = strict_canonical_loads(client._connection.recv_bytes())
            assert replay_response["response_hash"] == first_response["response_hash"]
            assert state_path.read_bytes() == state_before_replay
            assert access_path.read_bytes() == access_before
        finally:
            close_pair(supervisor, client)


def test_evaluator_state_journal_tamper_is_rejected_on_restart(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir):
        _registry, _schema, supervisor, client = launch(run_dir)
        supervisor.crash()
        state_path = run_dir / "EVALUATOR_SESSION.jsonl"
        raw = bytearray(state_path.read_bytes())
        position = raw.index(b"CAPEvaluatorState.v1")
        raw[position] = ord("X")
        state_path.write_bytes(raw)
        with pytest.raises(EvaluatorProtocolError, match="failed during startup"):
            supervisor.restart(client, events=hidden_events(), timeout=2.0)
        client.close()


def test_malformed_journal_record_raises_the_closed_protocol_error() -> None:
    journal = object.__new__(evaluator_module._SessionJournal)
    journal.session_id = "session"
    journal.capability_hash = "a" * 64
    journal.hidden_binding_tag = "b" * 64
    journal.state_key = b"state-key"
    with pytest.raises(EvaluatorProtocolError, match="strict canonical JSON"):
        journal._verify_records(b"not-json\n")


def test_evaluator_state_complete_prefix_rollback_is_detected_by_authenticated_head(tmp_path) -> None:
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir):
        _registry, _schema, supervisor, client = launch(run_dir)
        supervisor.crash()
        state_path = run_dir / "EVALUATOR_SESSION.jsonl"
        first_complete_record = state_path.read_bytes().splitlines()[0] + b"\n"
        state_path.write_bytes(first_complete_record)
        with pytest.raises(EvaluatorProtocolError, match="failed during startup"):
            supervisor.restart(client, events=hidden_events(), timeout=2.0)
        client.close()
