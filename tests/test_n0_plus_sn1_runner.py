from __future__ import annotations

from pathlib import Path

from experiments.n0_plus.run_sn1_synthetic_qualification import main, qualification_payload
from experiments.vfps_agent.canonical import strict_canonical_loads


def test_qualification_payload_contains_contract_checks_not_scores() -> None:
    payload = qualification_payload(seed=11)
    assert payload["status"] == "PASS_CONTRACT_ONLY_NO_SCIENTIFIC_RESULT"
    assert payload["candidate_count"] == 7
    assert payload["training_unit_count"] == 4
    assert payload["evaluation_unit_disjoint"] is True
    assert payload["interval_claim"] == "SHAPE_ONLY_NOT_CALIBRATED"
    assert payload["small_ml_interval_semantics"].endswith("NOT_VALID_FOR_P2")
    assert payload["scientific_metrics_computed"] is False
    assert payload["real_data_accessed"] is False
    assert payload["outer_labels_accessed"] is False
    assert payload["api_calls"] == 0
    assert payload["gpu_runs"] == 0
    assert all(all(record["checks"].values()) for record in payload["records"])
    assert all("loss" not in record and "score" not in record for record in payload["records"])


def test_runner_writes_canonical_json(tmp_path: Path) -> None:
    output = tmp_path / "sn1.json"
    assert main(["--output", str(output), "--seed", "11"]) == 0
    payload = strict_canonical_loads(output.read_bytes())
    assert payload["candidate_count"] == 7
