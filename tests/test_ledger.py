from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from experiments.audit_cap.ledger import read_verified_ledger, verify_sealed_ledger, write_sealed_ledger


def test_sealed_ledger_hash_chain_and_tamper_detection(tmp_path: Path):
    frame = pd.DataFrame(
        [
            {"prediction_id": "p1", "point_prediction": 1.25, "actual": None},
            {"prediction_id": "p2", "point_prediction": 2.5, "actual": None},
        ]
    )
    ledger = tmp_path / "PREDICTION_LEDGER.csv"
    seal = tmp_path / "PREDICTION_SEAL.json"
    chained, seal_payload = write_sealed_ledger(ledger, frame, seal, {"protocol_hash": "abc"})
    assert len(chained) == 2
    assert seal_payload["seal_status"] == "SEALED_BEFORE_LABEL_ACCESS"
    assert verify_sealed_ledger(ledger, seal) == json.loads(seal.read_text())
    loaded = read_verified_ledger(ledger, seal)
    assert list(loaded.prediction_id) == ["p1", "p2"]

    payload = ledger.read_text(encoding="utf-8").replace("1.25", "1.26", 1)
    ledger.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_sealed_ledger(ledger, seal)


def test_append_only_writer_refuses_existing_target(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    seal = tmp_path / "seal.json"
    ledger.write_text("keep\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_sealed_ledger(ledger, pd.DataFrame([{"x": 1}]), seal, {})
    assert ledger.read_text(encoding="utf-8") == "keep\n"
