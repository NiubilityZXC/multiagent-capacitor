from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

import pytest

from experiments.vfps_agent.budget import AccuracyV1Budget, execute_mock_accuracy_v1
from experiments.vfps_agent.contracts import (
    ArmId,
    CommitDisposition,
    ForecastKey,
    OriginPacketV2,
    PacketKind,
    PolicySpec,
    ProtocolId,
    RevealedObservation,
)
from experiments.vfps_agent.ledger import CanonicalJSONLLedger, LedgerKind
from experiments.vfps_agent.provider import MockProvider


def _deny(*args: object, **kwargs: object) -> object:
    raise AssertionError("network or subprocess access is forbidden in VFPS M0")


def _packet() -> OriginPacketV2:
    return OriginPacketV2(
        packet_kind=PacketKind.RAW,
        opaque_origin_hash="1" * 64,
        availability_cutoff=5.0,
        forecast_keys=(ForecastKey("capacity", 1, "F"),),
        revealed_observations=(
            RevealedObservation(0, 1.0, 2.0, {"capacity": 1.0}),
        ),
    )


def _policy() -> PolicySpec:
    values = [f"{value:x}" * 64 for value in range(2, 14)]
    return PolicySpec(
        policy_id="no-network-mock",
        generation=1,
        protocol=ProtocolId.ACCURACY_V1,
        arm=ArmId.D1_RAW,
        provider_rule_hash=values[0],
        model_version_rule_hash=values[1],
        prompt_hash=values[2],
        packet_schema_hash=values[3],
        response_schema_hash=values[4],
        grammar_hash=values[5],
        registry_hash=values[6],
        decode_parameters_hash=values[7],
        one_call_budget_hash=values[8],
        verifier_hash=values[9],
        fallback_hash=values[10],
        capability_snapshot_hash=values[11],
    )


def test_mock_provider_never_uses_network_subprocess_or_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    canary = "CANARY_DO_NOT_PERSIST_6c1f65ab"
    monkeypatch.setenv("ARK_API_KEY", canary)
    monkeypatch.setattr(socket, "socket", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)
    monkeypatch.setattr(subprocess, "Popen", _deny)
    monkeypatch.setattr(subprocess, "run", _deny)
    monkeypatch.setattr(urllib.request, "urlopen", _deny)

    class RequestsTrap:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"requests access is forbidden: {name}")

    monkeypatch.setitem(sys.modules, "requests", RequestsTrap())

    attempt_ledger = CanonicalJSONLLedger(tmp_path / "attempt.jsonl", LedgerKind.ATTEMPT)
    prediction_ledger = CanonicalJSONLLedger(tmp_path / "prediction.jsonl", LedgerKind.PREDICTION)
    # The free-form canary field violates the frozen prediction shape.  The raw
    # response stays ephemeral; only its SHA-256 may enter the attempt ledger.
    provider = MockProvider(response_text='{"capacity_h1":0.9,"note":"' + canary + '"}')
    _, commit = execute_mock_accuracy_v1(
        provider=provider,
        policy=_policy(),
        packet=_packet(),
        budget=AccuracyV1Budget(),
        attempt_ledger=attempt_ledger,
        prediction_ledger=prediction_ledger,
        fallback_prediction={"capacity_h1": 0.8},
        attempt_id="canary-attempt",
        requested_tokens=32,
        started_unix_ms=100,
        deadline_unix_ms=200,
    )
    assert commit.disposition is CommitDisposition.FALLBACK
    attempt_ledger.seal(tmp_path / "attempt.seal.json")
    prediction_ledger.seal(tmp_path / "prediction.seal.json")
    attempt_ledger.close()
    prediction_ledger.close()

    for path in tmp_path.iterdir():
        assert canary.encode("utf-8") not in path.read_bytes()
    assert os.environ["ARK_API_KEY"] == canary


def test_provider_source_has_no_real_io_imports() -> None:
    source = Path("experiments/vfps_agent/provider.py").read_text(encoding="utf-8")
    forbidden = ("import os", "import socket", "import subprocess", "import urllib", "import requests")
    assert not any(token in source for token in forbidden)
