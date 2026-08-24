from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

import experiments.audit_cap.replay as replay
from experiments.audit_cap.ledger import verify_sealed_ledger, write_sealed_ledger
from experiments.audit_cap.models import candidate_configs, fit_global_state, predict_prefix
from experiments.audit_cap.replay import (
    FAILURE_COLUMNS,
    eligible_origins,
    generate_nested_loco_predictions,
    mature_sealed_predictions,
    prediction_identity_hash,
    run_nested_loco,
    verify_causal_barrier,
)
from experiments.audit_cap.run_stress2_baselines import main as baseline_main
from experiments.audit_cap.stress2 import load_stress2

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / "data/raw/NASA/capacitor_electrical_stress/EOS_DataSet.zip"


@pytest.fixture(scope="module")
def stress2():
    return load_stress2(ZIP)


def _seal(tmp_path: Path, generation: dict[str, object]):
    ledger_path = tmp_path / "PREDICTION_LEDGER.csv"
    seal_path = tmp_path / "PREDICTION_LEDGER.seal.json"
    _, seal = write_sealed_ledger(
        ledger_path,
        generation["predictions"],
        seal_path,
        lineage=dict(generation["generation_summary"]),
    )
    return ledger_path, seal_path, seal


def test_parser_and_endpoint_semantics(stress2):
    assert stress2.events.shape == (66, 23)
    assert stress2.endpoints.shape == (18, 14)
    cap = stress2.endpoints[stress2.endpoints.endpoint == "capacity_loss_20pct"]
    assert (cap.status == "interval_crossing").sum() == 5
    assert (cap.status == "not_observed_through_last_measurement").sum() == 1
    assert cap.loc[cap.dataset_unit_key == "stress2:column:04", "lower_time_h"].item() == 161.0
    assert cap.loc[cap.dataset_unit_key == "stress2:column:04", "upper_time_h"].item() == 171.0
    esr = stress2.endpoints[stress2.endpoints.endpoint == "esr_increase_100pct"]
    assert (esr.status == "interval_crossing").sum() == 0
    assert (esr.censor_type == "unknown_termination_not_administrative").all()
    assert np.isclose(stress2.events.capacity_ratio.min(), 1.0 - 22.675 / 100.0)
    assert np.isclose(stress2.events.esr_ratio.max(), 1.0 + 53.54 / 100.0)


def test_origin_count_and_off_by_one():
    assert [len(eligible_origins(11, 4, h)) for h in (1, 2, 3)] == [7, 6, 5]
    assert eligible_origins(11, 4, 1)[0] == 3
    assert eligible_origins(11, 4, 1)[-1] == 9


def test_prefix_predictors_ignore_unpassed_suffix(stress2):
    unit_values = {
        key: group.sort_values("event_index_0based").capacity_ratio.to_numpy()
        for key, group in stress2.events.groupby("dataset_unit_key")
    }
    held = "stress2:column:01"
    train = {key: value for key, value in unit_values.items() if key != held}
    prefix = unit_values[held][:4]
    for model in ("last_value", "global_drift", "local_linear", "exponential", "local_trend_kf", "ridge"):
        config = candidate_configs(model)[0]
        state = fit_global_state(model, train, horizon=1, context=4, config=config)
        expected = predict_prefix(model, prefix, 1, "capacity_ratio", config, state)
        mutated_full = unit_values[held].copy()
        mutated_full[4:] = np.linspace(-1e6, 1e6, mutated_full.size - 4)
        actual = predict_prefix(model, mutated_full[:4], 1, "capacity_ratio", config, state)
        assert actual == expected


def test_nested_loco_ledgers_and_future_suffix_invariance(stress2):
    kwargs = dict(
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        context=4,
        horizons=(1,),
        models=("last_value", "ridge"),
    )
    original = run_nested_loco(stress2, **kwargs)
    prediction = original["predictions"]
    assert len(prediction) == 2 * 2 * 6 * 7
    assert (prediction.prediction_commit_seq < prediction.expected_label_available_seq).all()
    assert prediction.status.eq("OK").all()
    assert original["failures"].empty

    events = stress2.events.copy()
    mask = (events.dataset_unit_key == "stress2:column:01") & (events.event_index_0based >= 4)
    events.loc[mask, "capacity_ratio"] = np.linspace(-1e6, 1e6, int(mask.sum()))
    mutated = replace(stress2, events=events)
    rerun = run_nested_loco(mutated, **kwargs)
    key = (
        (prediction.outer_test_unit == "stress2:column:01")
        & (prediction.target == "capacity_ratio")
        & (prediction.origin_event_index_0based == 3)
    )
    left = prediction.loc[key, ["model", "point_prediction"]].sort_values("model").reset_index(drop=True)
    right_prediction = rerun["predictions"]
    right_key = (
        (right_prediction.outer_test_unit == "stress2:column:01")
        & (right_prediction.target == "capacity_ratio")
        & (right_prediction.origin_event_index_0based == 3)
    )
    right = right_prediction.loc[right_key, ["model", "point_prediction"]].sort_values("model").reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_last_value_is_hand_checkable(stress2):
    result = run_nested_loco(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        context=4,
        horizons=(1, 2, 3),
        models=("last_value",),
    )
    prediction = result["predictions"]
    events = stress2.events.set_index(["dataset_unit_key", "event_index_0based"])
    for row in prediction.itertuples(index=False):
        expected = events.loc[(row.outer_test_unit, row.origin_event_index_0based), row.target]
        assert row.point_prediction == expected
    counts = prediction.groupby(["target", "horizon_event_steps"]).size().to_dict()
    assert counts == {
        ("capacity_ratio", 1): 42,
        ("capacity_ratio", 2): 36,
        ("capacity_ratio", 3): 30,
        ("esr_ratio", 1): 42,
        ("esr_ratio", 2): 36,
        ("esr_ratio", 3): 30,
    }
    assert result["summary"]["rul_metrics_status"].startswith("NA_")


def test_prediction_is_sealed_before_independent_maturity_and_tamper_is_rejected(
    stress2, tmp_path
):
    generation = generate_nested_loco_predictions(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        context=4,
        horizons=(1,),
        models=("last_value", "global_drift"),
    )
    prediction = generation["predictions"]
    assert "actual" not in prediction.columns
    assert "target_time_h" not in prediction.columns
    ledger_path, seal_path, seal = _seal(tmp_path, generation)
    assert seal["seal_status"] == "SEALED_BEFORE_LABEL_ACCESS"
    assert verify_sealed_ledger(ledger_path, seal_path) == seal

    scored = mature_sealed_predictions(ledger_path, seal_path, stress2)
    assert scored["maturity_summary"]["seal_verified_before_maturity"] is True
    assert scored["maturities"].score_status.eq("OK").all()
    assert len(scored["maturities"]) == len(prediction)

    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="SHA-256"):
        mature_sealed_predictions(ledger_path, seal_path, stress2)


def test_prediction_id_commits_protocol_code_raw_seed_split_training_and_prefix(stress2):
    kwargs = dict(
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        context=4,
        horizons=(1,),
        models=("last_value",),
        seed=20260813,
    )
    original = generate_nested_loco_predictions(stress2, **kwargs)["predictions"]
    row = original[
        (original.outer_test_unit == "stress2:column:01")
        & (original.target == "capacity_ratio")
        & (original.origin_event_index_0based == 3)
    ].iloc[0]
    assert row.prediction_id == prediction_identity_hash(row.to_dict())
    for column in (
        "protocol_hash",
        "code_hash",
        "data_zip_hash",
        "data_mat_hash",
        "split_hash",
        "train_set_hash",
        "training_snapshot_hash",
        "prefix_hash",
        "seed",
    ):
        assert pd.notna(row[column])

    suffix_events = stress2.events.copy()
    suffix_mask = (
        (suffix_events.dataset_unit_key == "stress2:column:01")
        & (suffix_events.event_index_0based >= 4)
    )
    suffix_events.loc[suffix_mask, "capacity_ratio"] = np.linspace(
        -1e6, 1e6, int(suffix_mask.sum())
    )
    suffix_run = generate_nested_loco_predictions(
        replace(stress2, events=suffix_events), **kwargs
    )["predictions"]
    suffix_row = suffix_run[
        (suffix_run.outer_test_unit == "stress2:column:01")
        & (suffix_run.target == "capacity_ratio")
        & (suffix_run.origin_event_index_0based == 3)
    ].iloc[0]
    assert suffix_row.prefix_hash == row.prefix_hash
    assert suffix_row.training_snapshot_hash == row.training_snapshot_hash
    assert suffix_row.prediction_id == row.prediction_id

    prefix_events = stress2.events.copy()
    prefix_mask = (
        (prefix_events.dataset_unit_key == "stress2:column:01")
        & (prefix_events.event_index_0based == 3)
    )
    prefix_events.loc[prefix_mask, "capacity_ratio"] += 0.125
    prefix_row = generate_nested_loco_predictions(
        replace(stress2, events=prefix_events), **kwargs
    )["predictions"]
    prefix_row = prefix_row[
        (prefix_row.outer_test_unit == "stress2:column:01")
        & (prefix_row.target == "capacity_ratio")
        & (prefix_row.origin_event_index_0based == 3)
    ].iloc[0]
    assert prefix_row.training_snapshot_hash == row.training_snapshot_hash
    assert prefix_row.prefix_hash != row.prefix_hash
    assert prefix_row.prediction_id != row.prediction_id

    training_events = stress2.events.copy()
    training_mask = (
        (training_events.dataset_unit_key == "stress2:column:02")
        & (training_events.event_index_0based == 10)
    )
    training_events.loc[training_mask, "capacity_ratio"] += 0.125
    training_row = generate_nested_loco_predictions(
        replace(stress2, events=training_events), **kwargs
    )["predictions"]
    training_row = training_row[
        (training_row.outer_test_unit == "stress2:column:01")
        & (training_row.target == "capacity_ratio")
        & (training_row.origin_event_index_0based == 3)
    ].iloc[0]
    assert training_row.prefix_hash == row.prefix_hash
    assert training_row.training_snapshot_hash != row.training_snapshot_hash
    assert training_row.prediction_id != row.prediction_id

    mutated_identity = row.to_dict()
    mutated_identity["train_set_hash"] = "0" * 64
    assert prediction_identity_hash(mutated_identity) != row.prediction_id


def test_persistent_online_barrier_commits_each_origin_before_next_reveal(
    stress2, tmp_path
):
    ledger_path = tmp_path / "PREDICTION_LEDGER.csv"
    seal_path = tmp_path / "PREDICTION_LEDGER.seal.json"
    checkpoint_path = tmp_path / "PREDICTION_COMMIT_CHECKPOINTS.jsonl"
    access_path = tmp_path / "EVENT_REVEAL_LEDGER.jsonl"
    generation = generate_nested_loco_predictions(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        context=4,
        horizons=(1, 2, 3),
        models=("last_value", "global_drift"),
        ledger_path=ledger_path,
        seal_path=seal_path,
        checkpoint_path=checkpoint_path,
        access_log_path=access_path,
    )
    assert generation["prediction_seal"]["seal_status"] == (
        "SEALED_AFTER_VERIFIED_PER_ORIGIN_CAUSAL_COMMITS"
    )
    evidence = verify_causal_barrier(
        ledger_path, seal_path, checkpoint_path, access_path
    )
    assert evidence["status"] == "PASS"
    assert evidence["checkpoint_log"]["row_count"] == 6 * 7
    assert evidence["event_access_log"]["row_count"] == 6 * 11

    access_rows = [
        json.loads(line)
        for line in access_path.read_text(encoding="utf-8").splitlines()
    ]
    post_commit = [
        row for row in access_rows
        if row["access_type"] == "post_origin_checkpoint_reveal"
    ]
    assert len(post_commit) == 6 * 7
    assert all(row["required_checkpoint_row_hash"] for row in post_commit)
    assert all(
        row["revealed_event_index_0based"]
        == row["required_committed_origin_event_index_0based"] + 1
        for row in post_commit
    )


def test_rechained_causal_logs_cannot_escape_original_seal(stress2, tmp_path):
    ledger_path = tmp_path / "PREDICTION_LEDGER.csv"
    seal_path = tmp_path / "PREDICTION_LEDGER.seal.json"
    checkpoint_path = tmp_path / "PREDICTION_COMMIT_CHECKPOINTS.jsonl"
    access_path = tmp_path / "EVENT_REVEAL_LEDGER.jsonl"
    generate_nested_loco_predictions(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        context=4,
        horizons=(1,),
        models=("last_value",),
        ledger_path=ledger_path,
        seal_path=seal_path,
        checkpoint_path=checkpoint_path,
        access_log_path=access_path,
    )

    def rechained(rows):
        previous = "0" * 64
        output = []
        for source in rows:
            payload = {
                key: value for key, value in source.items()
                if key not in {"prev_row_hash", "row_hash"}
            }
            row_hash = hashlib.sha256(
                (previous + "\n" + replay.canonical_json(payload)).encode("utf-8")
            ).hexdigest()
            output.append({
                **payload, "prev_row_hash": previous, "row_hash": row_hash,
            })
            previous = row_hash
        return output

    checkpoints = [
        json.loads(line) for line in checkpoint_path.read_text().splitlines()
    ]
    checkpoints[0]["prediction_final_row_hash"] = "f" * 64
    checkpoints = rechained(checkpoints)
    checkpoint_path.write_text(
        "".join(replay.canonical_json(row) + "\n" for row in checkpoints),
        encoding="utf-8",
    )
    checkpoint_map = {
        (row["outer_test_unit"], row["origin_event_index_0based"]): row
        for row in checkpoints
    }
    access = [json.loads(line) for line in access_path.read_text().splitlines()]
    first_post = next(
        row for row in access if row["access_type"] == "post_origin_checkpoint_reveal"
    )
    first_post["revealed_event_index_0based"] = 10
    for row in access:
        origin = row["required_committed_origin_event_index_0based"]
        if origin is None:
            continue
        checkpoint = checkpoint_map[(row["outer_test_unit"], origin)]
        row["required_checkpoint_row_hash"] = checkpoint["row_hash"]
        row["required_prediction_final_row_hash"] = checkpoint[
            "prediction_final_row_hash"
        ]
    access = rechained(access)
    access_path.write_text(
        "".join(replay.canonical_json(row) + "\n" for row in access),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sealed lineage"):
        mature_sealed_predictions(
            ledger_path,
            seal_path,
            stress2,
            checkpoint_path=checkpoint_path,
            access_log_path=access_path,
        )


def test_selector_exception_is_materialized_for_all_planned_keys(
    stress2, monkeypatch
):
    def injected_selector(*args, **kwargs):
        raise RuntimeError("injected selector boundary failure")

    monkeypatch.setattr(replay, "_select_config", injected_selector)
    generation = generate_nested_loco_predictions(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        context=4,
        horizons=(1,),
        models=("last_value", "global_drift"),
    )
    predictions = generation["predictions"]
    assert len(predictions) == 2 * 2 * 6 * 7
    assert predictions.status.eq("FAIL").all()
    assert predictions.failure_stage.eq("config").all()
    assert len(generation["failures"]) == len(predictions)


@pytest.mark.parametrize("failure_stage", ["config", "state", "predict"])
def test_generation_faults_keep_every_planned_common_key(
    stress2, monkeypatch, failure_stage
):
    if failure_stage == "config":
        monkeypatch.setattr(
            replay,
            "_select_config",
            lambda *args, **kwargs: (None, [], "InjectedConfigError: expected"),
        )
    else:
        monkeypatch.setattr(
            replay,
            "_select_config",
            lambda *args, **kwargs: ({}, [], None),
        )
        if failure_stage == "state":
            monkeypatch.setattr(
                replay,
                "fit_global_state",
                lambda *args, **kwargs: (_ for _ in ()).throw(
                    RuntimeError("injected state failure")
                ),
            )
        else:
            monkeypatch.setattr(replay, "fit_global_state", lambda *args, **kwargs: None)
            monkeypatch.setattr(
                replay,
                "predict_prefix",
                lambda *args, **kwargs: (_ for _ in ()).throw(
                    RuntimeError("injected predict failure")
                ),
            )

    generation = generate_nested_loco_predictions(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        context=4,
        horizons=(1,),
        models=("last_value", "global_drift"),
    )
    prediction = generation["predictions"]
    assert len(prediction) == 2 * 2 * 6 * 7
    assert prediction.status.eq("FAIL").all()
    assert prediction.failure_stage.eq(failure_stage).all()
    assert prediction.point_prediction.isna().all()
    assert len(generation["failures"]) == len(prediction)
    key_columns = [
        "outer_test_unit",
        "target",
        "horizon_event_steps",
        "origin_event_index_0based",
    ]
    left = set(
        prediction[prediction.model == "last_value"][key_columns]
        .itertuples(index=False, name=None)
    )
    right = set(
        prediction[prediction.model == "global_drift"][key_columns]
        .itertuples(index=False, name=None)
    )
    assert left == right


def test_empty_failure_schema_is_stable(stress2):
    generation = generate_nested_loco_predictions(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        horizons=(1,),
        models=("last_value",),
    )
    assert generation["failures"].empty
    assert list(generation["failures"].columns) == FAILURE_COLUMNS


def test_maturity_fault_propagates_to_all_models_and_strict_aggregate_na(
    stress2, tmp_path, monkeypatch
):
    generation = generate_nested_loco_predictions(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        horizons=(1,),
        models=("last_value", "global_drift"),
    )
    ledger_path, seal_path, _ = _seal(tmp_path, generation)
    real_resolver = replay._resolve_maturity_label

    def injected_resolver(data, unit, target, event_index):
        if unit == "stress2:column:01" and target == "capacity_ratio" and event_index == 4:
            raise RuntimeError("injected maturity failure")
        return real_resolver(data, unit, target, event_index)

    monkeypatch.setattr(replay, "_resolve_maturity_label", injected_resolver)
    scored = mature_sealed_predictions(ledger_path, seal_path, stress2)
    maturity = scored["maturities"].merge(
        generation["predictions"][
            ["prediction_id", "outer_test_unit", "model", "target", "origin_event_index_0based"]
        ],
        on="prediction_id",
        validate="one_to_one",
    )
    affected = maturity[
        (maturity.outer_test_unit == "stress2:column:01")
        & (maturity.target == "capacity_ratio")
        & (maturity.origin_event_index_0based == 3)
    ]
    assert set(affected.model) == {"last_value", "global_drift"}
    assert affected.score_status.eq("FAIL_maturity").all()
    assert affected.actual.isna().all()

    affected_units = scored["unit_metrics"][
        (scored["unit_metrics"].outer_test_unit == "stress2:column:01")
        & (scored["unit_metrics"].target == "capacity_ratio")
    ]
    assert affected_units.metric_status.eq("NA_planned_failure").all()
    assert affected_units[["mae", "rmse", "mase"]].isna().all().all()
    affected_aggregates = scored["aggregate_metrics"][
        scored["aggregate_metrics"].target == "capacity_ratio"
    ]
    assert affected_aggregates.aggregate_status.eq("NA_planned_failure").all()
    assert affected_aggregates[
        ["macro_mae", "macro_rmse", "macro_mase"]
    ].isna().all().all()
    assert len(scored["failures"].query("failure_stage == 'maturity'")) == 2


def test_success_metrics_use_real_matured_ground_truth_without_skipna(stress2):
    result = run_nested_loco(
        stress2,
        protocol_hash="protocol-test",
        package_dir=ROOT / "experiments/audit_cap",
        horizons=(1,),
        models=("last_value", "global_drift"),
    )
    joined = result["predictions"].merge(
        result["maturities"][["prediction_id", "actual"]],
        on="prediction_id",
        validate="one_to_one",
    )
    joined["absolute_error"] = abs(joined.point_prediction - joined.actual)
    manual = (
        joined.groupby(["model", "target", "outer_test_unit"], sort=True)
        .absolute_error.mean()
        .groupby(["model", "target"]).mean()
    )
    aggregates = result["aggregate_metrics"].set_index(["model", "target"])
    for key, expected in manual.items():
        assert aggregates.loc[key, "macro_mae"] == pytest.approx(expected)
        assert aggregates.loc[key, "aggregate_status"] == "OK"
    assert result["maturities"].actual.notna().all()


def test_allow_unverified_data_is_explicit_and_claim_prohibited(
    stress2, tmp_path, monkeypatch
):
    output_dir = tmp_path / "unverified-run"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_stress2_baselines.py",
            "--zip", str(ZIP),
            "--protocol", str(ROOT / "idea-stage/FROZEN_EVAL_PROTOCOL.md"),
            "--output-dir", str(output_dir),
            "--horizons", "1",
            "--models", "last_value",
            "--allow-unverified-data",
        ],
    )
    assert baseline_main() == 0
    summary = json.loads((output_dir / "RUN_SUMMARY.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    complete = json.loads((output_dir / "COMPLETE").read_text(encoding="utf-8"))
    assert summary["verification_status"] == "UNVERIFIED"
    assert summary["claim_status"] == "PROHIBITED_UNVERIFIED_DATA"
    assert summary["claim_prohibited"] is True
    assert manifest["verification_status"] == "UNVERIFIED"
    assert manifest["claim_prohibited"] is True
    assert complete["status"] == "COMPLETE"
    assert complete["claim_prohibited"] is True
    assert complete["run_manifest_sha256"] == hashlib.sha256(
        (output_dir / "RUN_MANIFEST.json").read_bytes()
    ).hexdigest()
    verify_sealed_ledger(
        output_dir / "PREDICTION_LEDGER.csv",
        output_dir / "PREDICTION_LEDGER.seal.json",
    )
