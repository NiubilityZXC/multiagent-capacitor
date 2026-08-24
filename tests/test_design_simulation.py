from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from experiments.audit_cap.design_simulation import (
    TrajectoryScenario,
    clopper_pearson,
    decide_losses,
    generate_unit_losses,
    holm_rejections,
    main as design_main,
    run_quick,
    score_simulation_decision,
    seed_for,
)
from experiments.audit_cap.ledger import verify_sealed_ledger
from experiments.audit_cap.replay import package_code_hash


ROOT = Path(__file__).resolve().parents[1]


def test_seed_and_generator_are_deterministic():
    scenario = TrajectoryScenario("test", 12, 10, 0.4, 0.6, 0.8, 0.9, 0.5, 1, "test")
    cell = {"scenario": scenario.__dict__, "effect": 0.1, "repeats": 3}
    seed = seed_for(20260813, cell, 0)
    first = generate_unit_losses(np.random.default_rng(seed), scenario, 0.1)
    second = generate_unit_losses(np.random.default_rng(seed), scenario, 0.1)
    np.testing.assert_array_equal(first[0], second[0])
    np.testing.assert_array_equal(first[1], second[1])
    assert first[0].shape == (12,)
    assert first[1].shape == (12, 1)
    assert first[2] == second[2]


def test_decision_uses_one_loss_per_unit_and_holm():
    scenario = TrajectoryScenario("test", 12, 10, 0.4, 0.6, 0.8, 1.0, 0.0, 2, "test")
    incumbent = np.full(12, 2.0)
    candidates = np.column_stack([np.full(12, 1.0), np.full(12, 2.1)])
    result = decide_losses(incumbent, candidates, scenario)
    assert result["selected_candidate"] == 0
    assert result["promoted_any"] is True
    np.testing.assert_array_equal(holm_rejections([0.001, 0.2], alpha=0.04), [True, False])


def test_binomial_interval_boundaries():
    lower, upper = clopper_pearson(0, 200)
    assert lower == 0.0 and 0.0 < upper < 0.05
    lower, upper = clopper_pearson(200, 200)
    assert 0.95 < lower < 1.0 and upper == 1.0


def test_all_missing_is_explicit_failure_not_fabricated():
    scenario = TrajectoryScenario(
        "missing", 6, 2, 0.4, 0.0, 0.0, np.nextafter(0.0, 1.0), 0.0, 1, "failure_injection"
    )
    incumbent, candidates, failures = generate_unit_losses(np.random.default_rng(0), scenario, 0.1)
    assert failures == 6
    assert np.isnan(incumbent).all() and np.isnan(candidates).all()
    result = score_simulation_decision(decide_losses(incumbent, candidates, scenario), 0.1)
    assert result["analysis_status"] == "FAIL_NO_MATURE_ORIGIN"
    assert result["promoted_any"] is False


def test_candidate_decision_is_truth_blind():
    scenario = TrajectoryScenario("truth-blind", 12, 10, 0.4, 0.6, 0.8, 1.0, 0.0, 1, "test")
    incumbent = np.linspace(1.0, 2.1, 12)
    candidates = (incumbent * 0.8)[:, None]
    decision = decide_losses(incumbent, candidates, scenario)
    harmful_score = score_simulation_decision(decision, -0.05)
    beneficial_score = score_simulation_decision(decision, 0.10)
    assert harmful_score["selected_candidate"] == beneficial_score["selected_candidate"]
    assert harmful_score["primary_p_one_sided"] == beneficial_score["primary_p_one_sided"]
    assert harmful_score["correct_champion"] is False
    assert beneficial_score["correct_champion"] is True


def test_quick_slice_is_reproducible_and_never_claims_gate():
    repeat_a, cells_a, summary_a = run_quick(repeats=8, global_seed=123)
    repeat_b, cells_b, summary_b = run_quick(repeats=8, global_seed=123)
    pd.testing.assert_frame_equal(repeat_a, repeat_b)
    pd.testing.assert_frame_equal(cells_a, cells_b)
    assert summary_a == summary_b
    assert summary_a["design_gate"] == "NOT_EVALUATED_QUICK_SANITY"
    assert summary_a["rul_module"].startswith("NA_")
    assert cells_a.gate_status.eq("NOT_ELIGIBLE_QUICK_SANITY").all()

    repeat_long, _, _ = run_quick(repeats=10, global_seed=123)
    key = ["scenario_id", "effect", "repeat"]
    merged = repeat_a.merge(repeat_long, on=key, suffixes=("_short", "_long"), validate="one_to_one")
    assert (merged.seed_short == merged.seed_long).all()


def test_cli_binds_design_lineage_and_persists_raw_losses(tmp_path, monkeypatch):
    output = tmp_path / "design-run"
    protocol = ROOT / "refine-logs/DESIGN_SIM_PROTOCOL.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "design_simulation.py",
            "--output-dir", str(output),
            "--protocol", str(protocol),
            "--repeats", "2",
            "--seed", "20260813",
        ],
    )
    assert design_main() == 0
    repeat_seal = verify_sealed_ledger(
        output / "DESIGN_REPEAT_LEDGER.csv", output / "DESIGN_REPEAT_SEAL.json"
    )
    cell_seal = verify_sealed_ledger(
        output / "DESIGN_CELL_SUMMARY.csv", output / "DESIGN_CELL_SEAL.json"
    )
    expected_status = "SEALED_AFTER_SYNTHETIC_ANALYSIS_BEFORE_REPORTING"
    assert repeat_seal["seal_status"] == expected_status
    assert cell_seal["seal_status"] == expected_status
    repeat = pd.read_csv(output / "DESIGN_REPEAT_LEDGER.csv")
    assert isinstance(json.loads(repeat.iloc[0].incumbent_unit_losses_json), list)
    assert isinstance(json.loads(repeat.iloc[0].candidate_unit_losses_json), list)
    manifest = json.loads((output / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    complete = json.loads((output / "COMPLETE").read_text(encoding="utf-8"))
    assert manifest["lineage"]["code_hash"] == package_code_hash(ROOT / "experiments/audit_cap")
    assert complete["protocol_hash"] == hashlib.sha256(protocol.read_bytes()).hexdigest()
    assert complete["run_manifest_sha256"] == hashlib.sha256(
        (output / "RUN_MANIFEST.json").read_bytes()
    ).hexdigest()
