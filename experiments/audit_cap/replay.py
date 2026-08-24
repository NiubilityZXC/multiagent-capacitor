"""Causal nested-LOCO replay with a durable per-origin reveal barrier.

The full held-out trajectory is owned only by :class:`Stress2EventLabelService`.
Forecasting code receives outer-training trajectories and copies of the prefix
that the service has already revealed.  For every evaluated origin, all
model/target/horizon predictions are appended and fsynced, a hash checkpoint is
fsynced, and only then may the service reveal the next event.  Final scoring
re-verifies the prediction ledger and, for formal runs, the checkpoint/access
logs before reading maturity labels.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .ledger import (
    GENESIS_HASH,
    _csv_value,
    _json_value,
    read_verified_ledger,
    sha256_file,
    verify_sealed_ledger,
)
from .models import MODEL_ORDER, candidate_configs, fit_global_state, predict_prefix
from .stress2 import Stress2Data

TARGETS = ("capacity_ratio", "esr_ratio")

PREDICTION_COLUMNS = [
    "prediction_id", "protocol_hash", "data_zip_hash", "data_mat_hash",
    "verification_status", "code_hash", "split_hash", "train_set_hash",
    "training_snapshot_hash", "prefix_hash", "outer_test_unit", "model",
    "target", "horizon_event_steps", "context_event_steps",
    "origin_event_index_0based", "origin_time_h",
    "causal_cutoff_event_index_0based", "expected_target_event_index_0based",
    "prediction_commit_seq", "expected_label_available_seq", "config_json",
    "config_hash", "point_prediction", "interval_status", "status",
    "failure_stage", "error", "seed",
]
MATURITY_COLUMNS = [
    "prediction_id", "label_available_seq", "target_event_index_0based",
    "target_time_h", "actual", "label_lineage_hash", "score_status", "error",
]
TUNING_COLUMNS = [
    "outer_test_unit", "model", "target", "horizon", "candidate_order",
    "config_json", "config_hash", "status", "inner_macro_mae",
    "inner_unit_mae_json", "selected", "error", "split_hash",
    "train_set_hash", "training_snapshot_hash",
]
FAILURE_COLUMNS = [
    "prediction_id", "failure_stage", "outer_test_unit", "model", "target",
    "horizon_event_steps", "origin_event_index_0based", "protocol_hash",
    "code_hash", "data_zip_hash", "data_mat_hash", "seed", "split_hash",
    "train_set_hash", "training_snapshot_hash", "prefix_hash", "status",
    "error_type", "error",
]
UNIT_METRIC_COLUMNS = [
    "model", "target", "horizon_event_steps", "outer_test_unit",
    "planned_count", "predicted_count", "matured_count", "failed_count",
    "metric_status", "mae", "rmse", "mase_training_scale", "mase",
    "last_value_mae", "relative_mae_vs_last_value", "skill_vs_last_value",
    "comparison_status",
]
AGGREGATE_METRIC_COLUMNS = [
    "model", "target", "horizon_event_steps", "n_units", "planned_count",
    "failed_count", "aggregate_status", "macro_mae", "macro_rmse",
    "macro_mase", "macro_relative_mae_vs_last_value",
    "macro_skill_vs_last_value", "comparison_status",
]


def _canonical_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical_value(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )


def content_hash(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: str | Path) -> str:
    return sha256_file(path)


def package_code_hash(package_dir: str | Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(package_dir).glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def exact_series_snapshot_hash(
    unit_series: Mapping[str, np.ndarray], *, role: str, target: str
) -> str:
    digest = hashlib.sha256()
    digest.update(canonical_json({"role": role, "target": target}).encode("utf-8"))
    for unit in sorted(unit_series):
        values = np.ascontiguousarray(np.asarray(unit_series[unit], dtype="<f8"))
        digest.update(b"\x00unit\x00")
        digest.update(unit.encode("utf-8"))
        digest.update(b"\x00shape\x00")
        digest.update(canonical_json(list(values.shape)).encode("ascii"))
        digest.update(b"\x00values\x00")
        digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def exact_prefix_hash(unit: str, target: str, prefix: np.ndarray) -> str:
    return exact_series_snapshot_hash(
        {unit: np.asarray(prefix, dtype=np.float64)},
        role="outer_test_revealed_prefix", target=target,
    )


def eligible_origins(length: int, context: int, horizon: int) -> list[int]:
    if context < 2:
        raise ValueError("context must be at least two")
    if horizon < 1:
        raise ValueError("horizon must be positive")
    return list(range(context - 1, length - horizon))


def _all_series_after_seal(data: Stress2Data, target: str) -> dict[str, np.ndarray]:
    table = data.events.sort_values(["dataset_unit_key", "event_index_0based"])
    return {
        str(unit): group[target].to_numpy(dtype=np.float64)
        for unit, group in table.groupby("dataset_unit_key", sort=True)
    }


def _outer_training_series(
    data: Stress2Data, target: str, outer_test_unit: str
) -> dict[str, np.ndarray]:
    """Read target values only after excluding the held-out unit."""

    table = data.events.loc[
        data.events["dataset_unit_key"] != outer_test_unit,
        ["dataset_unit_key", "event_index_0based", target],
    ].sort_values(["dataset_unit_key", "event_index_0based"])
    return {
        str(unit): group[target].to_numpy(dtype=np.float64)
        for unit, group in table.groupby("dataset_unit_key", sort=True)
    }


def _validation_score(
    model: str,
    config: dict[str, Any],
    train_series: dict[str, np.ndarray],
    target: str,
    horizon: int,
    context: int,
) -> tuple[float, dict[str, float]]:
    unit_scores: dict[str, float] = {}
    for validation_unit in sorted(train_series):
        inner_train = {
            key: value for key, value in train_series.items()
            if key != validation_unit
        }
        state = fit_global_state(model, inner_train, horizon, context, config)
        values = train_series[validation_unit]
        errors: list[float] = []
        for origin in eligible_origins(values.size, context, horizon):
            prediction = predict_prefix(
                model, values[: origin + 1], horizon, target, config, state
            )
            errors.append(abs(prediction - float(values[origin + horizon])))
        if not errors or not np.all(np.isfinite(errors)):
            raise ValueError(f"invalid validation errors for {validation_unit}")
        unit_scores[validation_unit] = float(np.mean(errors))
    return float(np.mean(list(unit_scores.values()))), unit_scores


def _select_config(
    model: str,
    train_series: dict[str, np.ndarray],
    target: str,
    horizon: int,
    context: int,
    outer_test_unit: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    records: list[dict[str, Any]] = []
    best_config: dict[str, Any] | None = None
    best_score = np.inf
    try:
        configs = candidate_configs(model)
    except Exception as exc:
        return None, records, f"{type(exc).__name__}: {exc}"
    for order, raw_config in enumerate(configs):
        try:
            config = dict(raw_config)
            config_json = canonical_json(config)
            config_hash = content_hash(config)
            record: dict[str, Any] = {
                "outer_test_unit": outer_test_unit, "model": model,
                "target": target, "horizon": horizon, "candidate_order": order,
                "config_json": config_json, "config_hash": config_hash,
                "status": "OK", "inner_macro_mae": np.nan,
                "inner_unit_mae_json": None, "selected": False, "error": None,
            }
            score, unit_scores = _validation_score(
                model, config, train_series, target, horizon, context
            )
            record["inner_macro_mae"] = score
            record["inner_unit_mae_json"] = canonical_json(unit_scores)
            if score < best_score - 1e-15:
                best_score = score
                best_config = config
        except Exception as exc:
            fallback = {"candidate_order": order, "model": model}
            record = {
                "outer_test_unit": outer_test_unit, "model": model,
                "target": target, "horizon": horizon, "candidate_order": order,
                "config_json": canonical_json(fallback),
                "config_hash": hashlib.sha256(
                    canonical_json(fallback).encode("utf-8")
                ).hexdigest(),
                "status": "FAIL", "inner_macro_mae": np.nan,
                "inner_unit_mae_json": None, "selected": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        records.append(record)
    if best_config is None:
        return (
            None,
            records,
            f"RuntimeError: all configurations failed: {model}/{target}/h{horizon}/{outer_test_unit}",
        )
    selected_hash = content_hash(best_config)
    for record in records:
        record["selected"] = (
            record["status"] == "OK" and record["config_hash"] == selected_hash
        )
    return best_config, records, None


def _prediction_identity_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "protocol_hash": str(row["protocol_hash"]),
        "code_hash": str(row["code_hash"]),
        "data_zip_hash": str(row["data_zip_hash"]),
        "data_mat_hash": str(row["data_mat_hash"]),
        "seed": int(row["seed"]),
        "split_hash": str(row["split_hash"]),
        "train_set_hash": str(row["train_set_hash"]),
        "training_snapshot_hash": str(row["training_snapshot_hash"]),
        "prefix_hash": str(row["prefix_hash"]),
        "outer_test_unit": str(row["outer_test_unit"]),
        "model": str(row["model"]),
        "target": str(row["target"]),
        "horizon_event_steps": int(row["horizon_event_steps"]),
        "context_event_steps": int(row["context_event_steps"]),
        "origin_event_index_0based": int(row["origin_event_index_0based"]),
        "config_hash": str(row["config_hash"]),
    }


def prediction_identity_hash(row: Mapping[str, Any]) -> str:
    return content_hash(_prediction_identity_payload(row))


def _failure_from_prediction(
    row: Mapping[str, Any], stage: str, error: str, status: str = "FAIL"
) -> dict[str, Any]:
    error_type = error.split(":", 1)[0] if ":" in error else "RuntimeError"
    return {
        "prediction_id": row["prediction_id"], "failure_stage": stage,
        "outer_test_unit": row["outer_test_unit"], "model": row["model"],
        "target": row["target"],
        "horizon_event_steps": int(row["horizon_event_steps"]),
        "origin_event_index_0based": int(row["origin_event_index_0based"]),
        "protocol_hash": row["protocol_hash"], "code_hash": row["code_hash"],
        "data_zip_hash": row["data_zip_hash"],
        "data_mat_hash": row["data_mat_hash"], "seed": int(row["seed"]),
        "split_hash": row["split_hash"],
        "train_set_hash": row["train_set_hash"],
        "training_snapshot_hash": row["training_snapshot_hash"],
        "prefix_hash": row["prefix_hash"], "status": status,
        "error_type": error_type, "error": error,
    }


def _payload_json(row: Mapping[str, Any], columns: Sequence[str]) -> str:
    payload = {column: _json_value(row.get(column)) for column in columns}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


class _DurableJsonlChain:
    def __init__(self, path: Path) -> None:
        if path.exists():
            raise FileExistsError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._handle = path.open("x", encoding="utf-8", newline="\n")
        self.previous_hash = GENESIS_HASH
        self.row_count = 0

    def append(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload_json = canonical_json(payload)
        row_hash = hashlib.sha256(
            (self.previous_hash + "\n" + payload_json).encode("utf-8")
        ).hexdigest()
        record = {
            **dict(payload), "prev_row_hash": self.previous_hash,
            "row_hash": row_hash,
        }
        self._handle.write(canonical_json(record) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.previous_hash = row_hash
        self.row_count += 1
        return record

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.flush()
            os.fsync(self._handle.fileno())
            self._handle.close()


def verify_jsonl_chain(path: str | Path) -> dict[str, Any]:
    previous = GENESIS_HASH
    count = 0
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                raise ValueError("blank line in append-only JSONL chain")
            record = json.loads(line)
            observed_previous = record.pop("prev_row_hash")
            observed_hash = record.pop("row_hash")
            if observed_previous != previous:
                raise ValueError("JSONL previous-hash chain is broken")
            expected = hashlib.sha256(
                (previous + "\n" + canonical_json(record)).encode("utf-8")
            ).hexdigest()
            if observed_hash != expected:
                raise ValueError("JSONL row hash is invalid")
            previous = expected
            count += 1
    return {"row_count": count, "final_row_hash": previous, "sha256": file_hash(path)}


class DurablePredictionWriter:
    """Append predictions and durable origin checkpoints without labels."""

    def __init__(
        self, ledger_path: Path, checkpoint_path: Path, lineage: Mapping[str, Any]
    ) -> None:
        if ledger_path.exists():
            raise FileExistsError(ledger_path)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path = ledger_path
        self.lineage = dict(lineage)
        self.columns = [
            *PREDICTION_COLUMNS, "row_payload_json", "prev_row_hash", "row_hash"
        ]
        self._handle = ledger_path.open("x", encoding="utf-8", newline="")
        self._csv = csv.DictWriter(
            self._handle, fieldnames=self.columns, lineterminator="\n"
        )
        self._csv.writeheader()
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.previous_hash = GENESIS_HASH
        self.row_count = 0
        self.checkpoints = _DurableJsonlChain(checkpoint_path)
        self._checkpoint_index: dict[tuple[str, int], dict[str, Any]] = {}
        self.logical_rows: list[dict[str, Any]] = []

    def append_origin(
        self, unit: str, origin: int, rows: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        if not rows:
            raise ValueError("origin checkpoint requires at least one prediction")
        key = (unit, int(origin))
        if key in self._checkpoint_index:
            raise ValueError(f"duplicate origin checkpoint: {key}")
        first_row = self.row_count + 1
        for source in rows:
            logical = {column: source.get(column) for column in PREDICTION_COLUMNS}
            payload_json = _payload_json(logical, PREDICTION_COLUMNS)
            row_hash = hashlib.sha256(
                (self.previous_hash + "\n" + payload_json).encode("utf-8")
            ).hexdigest()
            chained = {
                **logical, "row_payload_json": payload_json,
                "prev_row_hash": self.previous_hash, "row_hash": row_hash,
            }
            self._csv.writerow(
                {column: _csv_value(chained[column]) for column in self.columns}
            )
            self._handle.flush()
            os.fsync(self._handle.fileno())
            self.previous_hash = row_hash
            self.row_count += 1
            self.logical_rows.append(logical)
        checkpoint = self.checkpoints.append({
            "checkpoint_type": "origin_prediction_batch_committed",
            "outer_test_unit": unit,
            "origin_event_index_0based": int(origin),
            "first_prediction_row_1based": first_row,
            "last_prediction_row_1based": self.row_count,
            "prediction_row_count_total": self.row_count,
            "prediction_final_row_hash": self.previous_hash,
        })
        self._checkpoint_index[key] = checkpoint
        return checkpoint

    def require_checkpoint(self, unit: str, origin: int) -> dict[str, Any]:
        key = (unit, int(origin))
        if key not in self._checkpoint_index:
            raise RuntimeError(
                f"future event reveal forbidden before durable origin checkpoint: {key}"
            )
        return dict(self._checkpoint_index[key])

    def finalize(
        self,
        seal_path: Path,
        *,
        access_log_name: str,
        access_log_evidence: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        self.checkpoints.close()
        checkpoint_evidence = verify_jsonl_chain(self.checkpoints.path)
        seal = {
            "ledger": self.ledger_path.name,
            "ledger_sha256": file_hash(self.ledger_path),
            "row_count": self.row_count,
            "final_row_hash": self.previous_hash,
            "columns": self.columns,
            "lineage": {
                **self.lineage,
                "causal_checkpoint_log": self.checkpoints.path.name,
                "causal_checkpoint_evidence": checkpoint_evidence,
                "event_access_log": access_log_name,
                "event_access_log_evidence": dict(access_log_evidence),
            },
            "seal_status": "SEALED_AFTER_VERIFIED_PER_ORIGIN_CAUSAL_COMMITS",
        }
        _atomic_json(seal_path, seal)
        verify_sealed_ledger(self.ledger_path, seal_path)
        return seal


class Stress2EventLabelService:
    """The only component permitted to own and reveal held-out labels."""

    def __init__(
        self,
        data: Stress2Data,
        unit: str,
        writer: DurablePredictionWriter,
        access_log: _DurableJsonlChain,
    ) -> None:
        self._data = data
        self.unit = unit
        self._writer = writer
        self._access_log = access_log
        unit_mask = data.events["dataset_unit_key"].eq(unit)
        self.length = int(unit_mask.sum())
        expected = list(range(self.length))
        observed = sorted(
            int(value)
            for value in data.events.loc[unit_mask, "event_index_0based"].tolist()
        )
        if observed != expected:
            raise ValueError(f"non-contiguous held-out event schedule for {unit}")
        self._next_index = 0
        self._times: list[float] = []
        self._prefixes: dict[str, list[float]] = {target: [] for target in TARGETS}

    @property
    def revealed_index(self) -> int:
        return self._next_index - 1

    def prefix(self, target: str) -> np.ndarray:
        if target not in self._prefixes:
            raise KeyError(target)
        return np.asarray(self._prefixes[target], dtype=np.float64).copy()

    def current_time_h(self) -> float:
        if not self._times:
            raise RuntimeError("no event has been revealed")
        return float(self._times[-1])

    def reveal_next(self, *, required_origin: int | None) -> None:
        if self._next_index >= self.length:
            raise StopIteration(self.unit)
        checkpoint: dict[str, Any] | None = None
        if required_origin is not None:
            checkpoint = self._writer.require_checkpoint(self.unit, required_origin)
        event_index = self._next_index
        access_record = {
            "access_type": (
                "bootstrap_context_reveal"
                if required_origin is None
                else "post_origin_checkpoint_reveal"
            ),
            "outer_test_unit": self.unit,
            "revealed_event_index_0based": event_index,
            "required_committed_origin_event_index_0based": required_origin,
            "required_checkpoint_row_hash": (
                None if checkpoint is None else checkpoint["row_hash"]
            ),
            "required_prediction_final_row_hash": (
                None if checkpoint is None
                else checkpoint["prediction_final_row_hash"]
            ),
        }
        # The access authorization is itself durable before label values are read.
        self._access_log.append(access_record)
        rows = self._data.events.loc[
            self._data.events["dataset_unit_key"].eq(self.unit)
            & self._data.events["event_index_0based"].eq(event_index),
            ["aging_time_h", *TARGETS],
        ]
        if len(rows) != 1:
            raise ValueError(f"expected one held-out event, found {len(rows)}")
        row = rows.iloc[0]
        time_h = float(row["aging_time_h"])
        values = {target: float(row[target]) for target in TARGETS}
        if not np.isfinite(time_h) or not all(np.isfinite(value) for value in values.values()):
            raise ValueError("revealed held-out event is non-finite")
        self._times.append(time_h)
        for target, value in values.items():
            self._prefixes[target].append(value)
        self._next_index += 1


def _assert_common_key_parity(predictions: pd.DataFrame, models: Sequence[str]) -> None:
    key_columns = [
        "outer_test_unit", "target", "horizon_event_steps",
        "origin_event_index_0based",
    ]
    reference: set[tuple[Any, ...]] | None = None
    for model in models:
        keys = set(
            predictions[predictions["model"] == model][key_columns]
            .itertuples(index=False, name=None)
        )
        if reference is None:
            reference = keys
        elif keys != reference:
            raise AssertionError("models do not share all planned common evaluation keys")
    if predictions.duplicated([*key_columns, "model"]).any():
        raise AssertionError("duplicate planned prediction key")


def _prepared_model_states(
    *,
    outer_test: str,
    train_by_target: Mapping[str, dict[str, np.ndarray]],
    horizons: Sequence[int],
    models: Sequence[str],
    context: int,
    split_hash: str,
    train_set_hash: str,
    training_hashes: Mapping[str, str],
) -> tuple[dict[tuple[str, int, str], dict[str, Any]], list[dict[str, Any]]]:
    prepared: dict[tuple[str, int, str], dict[str, Any]] = {}
    tuning: list[dict[str, Any]] = []
    for target in TARGETS:
        train_series = train_by_target[target]
        for horizon in horizons:
            for model in models:
                try:
                    config, records, selection_error = _select_config(
                        model, train_series, target, horizon, context, outer_test
                    )
                except Exception as exc:
                    config, records = None, []
                    selection_error = f"{type(exc).__name__}: {exc}"
                for record in records:
                    record.update({
                        "split_hash": split_hash,
                        "train_set_hash": train_set_hash,
                        "training_snapshot_hash": training_hashes[target],
                    })
                tuning.extend(records)
                if config is None:
                    fallback = {
                        "selection": "FAIL", "model": model,
                        "target": target, "horizon": horizon,
                    }
                    config = {}
                    config_json = canonical_json(config)
                    config_hash = hashlib.sha256(
                        canonical_json(fallback).encode("utf-8")
                    ).hexdigest()
                    state = None
                    state_error = None
                else:
                    try:
                        config_json = canonical_json(config)
                        config_hash = content_hash(config)
                    except Exception as exc:
                        config_json = canonical_json({})
                        config_hash = hashlib.sha256(
                            f"config_hash_failure:{model}:{target}:{horizon}".encode("utf-8")
                        ).hexdigest()
                        selection_error = f"{type(exc).__name__}: {exc}"
                    try:
                        state = fit_global_state(
                            model, train_series, horizon, context, config
                        )
                        state_error = None
                    except Exception as exc:
                        state = None
                        state_error = f"{type(exc).__name__}: {exc}"
                prepared[(target, horizon, model)] = {
                    "config": config, "config_json": config_json,
                    "config_hash": config_hash, "state": state,
                    "selection_error": selection_error,
                    "state_error": state_error,
                }
    return prepared, tuning


def _predict_revealed_origin(
    *,
    revealed_prefixes: Mapping[str, np.ndarray],
    origin_time_h: float,
    frozen_stream_length: int,
    outer_test: str,
    origin: int,
    context: int,
    horizons: Sequence[int],
    models: Sequence[str],
    prepared: Mapping[tuple[str, int, str], Mapping[str, Any]],
    protocol_hash: str,
    code_hash: str,
    data_zip_hash: str,
    data_mat_hash: str,
    verification_status: str,
    split_hash: str,
    train_set_hash: str,
    training_hashes: Mapping[str, str],
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pure predictor boundary: it receives only copied revealed prefixes."""

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    prefixes = {
        target: np.asarray(revealed_prefixes[target], dtype=np.float64).copy()
        for target in TARGETS
    }
    if any(prefix.size != origin + 1 for prefix in prefixes.values()):
        raise AssertionError("event service exposed an invalid prefix length")
    for target in TARGETS:
        prefix = prefixes[target]
        prefix_hash = exact_prefix_hash(outer_test, target, prefix)
        for horizon in horizons:
            if origin + horizon >= frozen_stream_length:
                continue
            for model in models:
                item = prepared[(target, horizon, model)]
                row: dict[str, Any] = {
                    "protocol_hash": protocol_hash,
                    "data_zip_hash": data_zip_hash,
                    "data_mat_hash": data_mat_hash,
                    "verification_status": verification_status,
                    "code_hash": code_hash, "split_hash": split_hash,
                    "train_set_hash": train_set_hash,
                    "training_snapshot_hash": training_hashes[target],
                    "prefix_hash": prefix_hash,
                    "outer_test_unit": outer_test, "model": model,
                    "target": target, "horizon_event_steps": horizon,
                    "context_event_steps": context,
                    "origin_event_index_0based": origin,
                    "origin_time_h": float(origin_time_h),
                    "causal_cutoff_event_index_0based": origin,
                    "expected_target_event_index_0based": origin + horizon,
                    "prediction_commit_seq": origin,
                    "expected_label_available_seq": origin + horizon,
                    "config_json": item["config_json"],
                    "config_hash": item["config_hash"],
                    "point_prediction": np.nan,
                    "interval_status": "NA_insufficient_independent_calibration_units",
                    "status": "OK", "failure_stage": None,
                    "error": None, "seed": seed,
                }
                row["prediction_id"] = prediction_identity_hash(row)
                if item["selection_error"] is not None:
                    row["status"] = "FAIL"
                    row["failure_stage"] = "config"
                    row["error"] = item["selection_error"]
                elif item["state_error"] is not None:
                    row["status"] = "FAIL"
                    row["failure_stage"] = "state"
                    row["error"] = item["state_error"]
                else:
                    try:
                        prediction = predict_prefix(
                            model, prefix, horizon, target,
                            dict(item["config"]), item["state"],
                        )
                        if not np.isfinite(prediction):
                            raise ValueError("non-finite prediction")
                        row["point_prediction"] = float(prediction)
                    except Exception as exc:
                        row["status"] = "FAIL"
                        row["failure_stage"] = "predict"
                        row["error"] = f"{type(exc).__name__}: {exc}"
                rows.append(row)
                if row["status"] != "OK":
                    failures.append(_failure_from_prediction(
                        row, str(row["failure_stage"]), str(row["error"])
                    ))
    return rows, failures


def verify_causal_barrier(
    prediction_ledger_path: str | Path,
    prediction_seal_path: str | Path,
    checkpoint_path: str | Path,
    access_log_path: str | Path,
) -> dict[str, Any]:
    seal = verify_sealed_ledger(prediction_ledger_path, prediction_seal_path)
    predictions = pd.read_csv(
        prediction_ledger_path, na_values=["NA", "+Inf", "-Inf"],
        keep_default_na=True,
    )
    checkpoint_evidence = verify_jsonl_chain(checkpoint_path)
    access_evidence = verify_jsonl_chain(access_log_path)
    lineage = seal.get("lineage", {})
    if lineage.get("causal_checkpoint_log") != Path(checkpoint_path).name:
        raise ValueError("seal does not bind the causal checkpoint filename")
    if lineage.get("event_access_log") != Path(access_log_path).name:
        raise ValueError("seal does not bind the event access filename")
    if lineage.get("causal_checkpoint_evidence") != checkpoint_evidence:
        raise ValueError("checkpoint evidence differs from sealed lineage")
    if lineage.get("event_access_log_evidence") != access_evidence:
        raise ValueError("event access evidence differs from sealed lineage")
    checkpoints: dict[tuple[str, int], dict[str, Any]] = {}
    checkpoint_sequence: list[dict[str, Any]] = []
    with Path(checkpoint_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = (
                str(row["outer_test_unit"]),
                int(row["origin_event_index_0based"]),
            )
            if key in checkpoints:
                raise ValueError("duplicate causal checkpoint")
            checkpoints[key] = row
            checkpoint_sequence.append(row)
    previous_last_row = 0
    for checkpoint in checkpoint_sequence:
        first_row = int(checkpoint["first_prediction_row_1based"])
        last_row = int(checkpoint["last_prediction_row_1based"])
        total_rows = int(checkpoint["prediction_row_count_total"])
        if first_row != previous_last_row + 1 or last_row < first_row:
            raise ValueError("checkpoint prediction row ranges are not contiguous")
        if total_rows != last_row or last_row > len(predictions):
            raise ValueError("checkpoint prediction row count is invalid")
        committed = predictions.iloc[first_row - 1:last_row]
        unit = str(checkpoint["outer_test_unit"])
        origin = int(checkpoint["origin_event_index_0based"])
        if committed.empty or not committed["outer_test_unit"].astype(str).eq(unit).all():
            raise ValueError("checkpoint row range contains another held-out unit")
        if not committed["origin_event_index_0based"].astype(int).eq(origin).all():
            raise ValueError("checkpoint row range contains another origin")
        ledger_final_hash = str(committed.iloc[-1]["row_hash"])
        if checkpoint["prediction_final_row_hash"] != ledger_final_hash:
            raise ValueError("checkpoint is not bound to the prediction ledger row hash")
        previous_last_row = last_row
    if previous_last_row != len(predictions):
        raise ValueError("checkpoint ranges do not cover the prediction ledger")
    for unit, origin in predictions[
        ["outer_test_unit", "origin_event_index_0based"]
    ].drop_duplicates().itertuples(index=False, name=None):
        if (str(unit), int(origin)) not in checkpoints:
            raise ValueError("prediction origin lacks a durable checkpoint")
    access_rows: list[dict[str, Any]] = []
    with Path(access_log_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            access_rows.append(row)
            required = row["required_committed_origin_event_index_0based"]
            if required is None:
                continue
            key = (str(row["outer_test_unit"]), int(required))
            checkpoint = checkpoints.get(key)
            if checkpoint is None:
                raise ValueError("event reveal references a missing checkpoint")
            if row["required_checkpoint_row_hash"] != checkpoint["row_hash"]:
                raise ValueError("event reveal checkpoint hash mismatch")
            if (
                row["required_prediction_final_row_hash"]
                != checkpoint["prediction_final_row_hash"]
            ):
                raise ValueError("event reveal prediction hash mismatch")
    context_values = predictions["context_event_steps"].astype(int).unique()
    if len(context_values) != 1:
        raise ValueError("causal barrier requires one frozen context length")
    context = int(context_values[0])
    predicted_origins = {
        str(unit): sorted(int(value) for value in group["origin_event_index_0based"].unique())
        for unit, group in predictions.groupby("outer_test_unit", sort=True)
    }
    for unit, origins in predicted_origins.items():
        unit_access = [
            row for row in access_rows if str(row["outer_test_unit"]) == unit
        ]
        revealed = [int(row["revealed_event_index_0based"]) for row in unit_access]
        if revealed != list(range(len(revealed))):
            raise ValueError("event reveals are not contiguous and causal within unit")
        bootstrap = unit_access[:context]
        if [int(row["revealed_event_index_0based"]) for row in bootstrap] != list(range(context)):
            raise ValueError("bootstrap reveal sequence does not match frozen context")
        if any(
            row["access_type"] != "bootstrap_context_reveal"
            or row["required_committed_origin_event_index_0based"] is not None
            or row["required_checkpoint_row_hash"] is not None
            or row["required_prediction_final_row_hash"] is not None
            for row in bootstrap
        ):
            raise ValueError("bootstrap reveal contains a forged checkpoint binding")
        post = unit_access[context:]
        post_origins = [
            int(row["required_committed_origin_event_index_0based"])
            for row in post
        ]
        if post_origins != origins:
            raise ValueError("each predicted origin must authorize exactly one next reveal")
        if any(
            row["access_type"] != "post_origin_checkpoint_reveal"
            or int(row["revealed_event_index_0based"])
            != int(row["required_committed_origin_event_index_0based"]) + 1
            for row in post
        ):
            raise ValueError("post-origin reveal is not the immediate next event")
        revealed_set = set(revealed)
        expected_targets = set(
            predictions.loc[
                predictions["outer_test_unit"].astype(str).eq(unit),
                "expected_target_event_index_0based",
            ].astype(int)
        )
        if not expected_targets.issubset(revealed_set):
            raise ValueError("a scored target was not causally revealed before sealing")
    if not (
        predictions["prediction_commit_seq"].astype(int)
        < predictions["expected_label_available_seq"].astype(int)
    ).all():
        raise ValueError("prediction commit is not before label availability")
    return {
        "status": "PASS",
        "checkpoint_log": checkpoint_evidence,
        "event_access_log": access_evidence,
        "prediction_origin_count": int(
            predictions[["outer_test_unit", "origin_event_index_0based"]]
            .drop_duplicates().shape[0]
        ),
    }


def _run_online_generation(
    *,
    data: Stress2Data,
    protocol_hash: str,
    package_dir: str | Path,
    ledger_path: Path,
    seal_path: Path,
    checkpoint_path: Path,
    access_log_path: Path,
    context: int,
    horizons: Sequence[int],
    models: Sequence[str],
    seed: int,
    verification_status: str,
) -> dict[str, pd.DataFrame | dict[str, Any]]:
    np.random.seed(seed)
    code_hash = package_code_hash(package_dir)
    units = sorted(str(value) for value in data.events["dataset_unit_key"].unique())
    if len(units) < 3:
        raise ValueError("nested LOCO requires at least three units")
    lineage = {
        "protocol_hash": protocol_hash, "code_hash": code_hash,
        "data_zip_hash": data.source_zip_sha256,
        "data_mat_hash": data.source_mat_sha256,
        "verification_status": verification_status,
        "context": context, "horizons": list(horizons),
        "models": list(models), "targets": list(TARGETS), "seed": seed,
        "online_barrier": "per_origin_append_fsync_hash_checkpoint_before_reveal",
    }
    writer = DurablePredictionWriter(ledger_path, checkpoint_path, lineage)
    access_log = _DurableJsonlChain(access_log_path)
    tuning: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for outer_test in units:
        outer_train = [unit for unit in units if unit != outer_test]
        split_manifest = {
            "test": [outer_test], "train": outer_train,
            "grouping": "column_surrogate",
        }
        split_hash = content_hash(split_manifest)
        train_set_hash = content_hash(outer_train)
        train_by_target = {
            target: _outer_training_series(data, target, outer_test)
            for target in TARGETS
        }
        if any(sorted(train_by_target[target]) != outer_train for target in TARGETS):
            raise ValueError("outer-training target unit mismatch")
        training_hashes = {
            target: exact_series_snapshot_hash(
                train_by_target[target], role="outer_training", target=target
            )
            for target in TARGETS
        }
        prepared, fold_tuning = _prepared_model_states(
            outer_test=outer_test, train_by_target=train_by_target,
            horizons=horizons, models=models, context=context,
            split_hash=split_hash, train_set_hash=train_set_hash,
            training_hashes=training_hashes,
        )
        tuning.extend(fold_tuning)
        service = Stress2EventLabelService(data, outer_test, writer, access_log)
        if service.length < context:
            raise ValueError(f"held-out stream shorter than context: {outer_test}")
        for _ in range(context):
            service.reveal_next(required_origin=None)
        for origin in range(context - 1, service.length - 1):
            rows, origin_failures = _predict_revealed_origin(
                revealed_prefixes={
                    target: service.prefix(target) for target in TARGETS
                },
                origin_time_h=service.current_time_h(),
                frozen_stream_length=service.length,
                outer_test=outer_test, origin=origin,
                context=context, horizons=horizons, models=models,
                prepared=prepared, protocol_hash=protocol_hash,
                code_hash=code_hash,
                data_zip_hash=data.source_zip_sha256,
                data_mat_hash=data.source_mat_sha256,
                verification_status=verification_status,
                split_hash=split_hash, train_set_hash=train_set_hash,
                training_hashes=training_hashes, seed=seed,
            )
            if not rows:
                break
            writer.append_origin(outer_test, origin, rows)
            failures.extend(origin_failures)
            service.reveal_next(required_origin=origin)
    access_log.close()
    access_evidence = verify_jsonl_chain(access_log_path)
    seal = writer.finalize(
        seal_path,
        access_log_name=access_log_path.name,
        access_log_evidence=access_evidence,
    )
    barrier = verify_causal_barrier(
        ledger_path, seal_path, checkpoint_path, access_log_path
    )
    prediction_df = pd.DataFrame(writer.logical_rows, columns=PREDICTION_COLUMNS)
    tuning_df = pd.DataFrame(tuning, columns=TUNING_COLUMNS)
    if not tuning_df.empty:
        tuning_df = tuning_df.sort_values([
            "outer_test_unit", "model", "target", "horizon", "candidate_order"
        ]).reset_index(drop=True)
    failure_df = pd.DataFrame(failures, columns=FAILURE_COLUMNS)
    if not failure_df.empty:
        failure_df = failure_df.sort_values([
            "outer_test_unit", "model", "target", "horizon_event_steps",
            "origin_event_index_0based",
        ]).reset_index(drop=True)
    _assert_common_key_parity(prediction_df, models)
    return {
        "predictions": prediction_df,
        "tuning": tuning_df,
        "failures": failure_df,
        "prediction_seal": seal,
        "barrier_evidence": barrier,
        "generation_summary": {
            **lineage,
            "prediction_rows": int(len(prediction_df)),
            "prediction_failure_rows": int(len(failure_df)),
            "causal_barrier_status": "PASS",
            "prediction_seal_status": seal["seal_status"],
            "checkpoint_rows": barrier["checkpoint_log"]["row_count"],
            "event_access_rows": barrier["event_access_log"]["row_count"],
        },
    }


def generate_nested_loco_predictions(
    data: Stress2Data,
    protocol_hash: str,
    package_dir: str | Path,
    context: int = 4,
    horizons: Iterable[int] = (1, 2, 3),
    models: Iterable[str] = MODEL_ORDER,
    seed: int = 20260813,
    verification_status: str = "VERIFIED",
    *,
    ledger_path: str | Path | None = None,
    seal_path: str | Path | None = None,
    checkpoint_path: str | Path | None = None,
    access_log_path: str | Path | None = None,
) -> dict[str, pd.DataFrame | dict[str, Any]]:
    """Generate predictions using the same causal stream used by the CLI."""

    horizon_tuple = tuple(int(value) for value in horizons)
    model_tuple = tuple(str(value) for value in models)
    if context < 2:
        raise ValueError("context must be at least two")
    if not horizon_tuple or any(value < 1 for value in horizon_tuple):
        raise ValueError("horizons must be positive")
    if 1 not in horizon_tuple:
        raise ValueError(
            "the frozen causal stream requires horizon 1 so every scored target "
            "is revealed through an immediately preceding origin checkpoint"
        )
    if len(set(horizon_tuple)) != len(horizon_tuple):
        raise ValueError("duplicate horizons")
    if not model_tuple or any(model not in MODEL_ORDER for model in model_tuple):
        raise ValueError("models must be a non-empty subset of MODEL_ORDER")
    if len(set(model_tuple)) != len(model_tuple):
        raise ValueError("duplicate models")
    if verification_status not in {"VERIFIED", "UNVERIFIED"}:
        raise ValueError("verification_status must be VERIFIED or UNVERIFIED")
    supplied = [ledger_path, seal_path, checkpoint_path, access_log_path]
    if any(value is None for value in supplied) and any(value is not None for value in supplied):
        raise ValueError("all causal artifact paths must be supplied together")
    if all(value is not None for value in supplied):
        return _run_online_generation(
            data=data, protocol_hash=protocol_hash, package_dir=package_dir,
            ledger_path=Path(ledger_path), seal_path=Path(seal_path),
            checkpoint_path=Path(checkpoint_path),
            access_log_path=Path(access_log_path), context=context,
            horizons=horizon_tuple, models=model_tuple, seed=seed,
            verification_status=verification_status,
        )
    with tempfile.TemporaryDirectory(prefix="audit-cap-causal-generation-") as directory:
        root = Path(directory)
        return _run_online_generation(
            data=data, protocol_hash=protocol_hash, package_dir=package_dir,
            ledger_path=root / "PREDICTION_LEDGER.csv",
            seal_path=root / "PREDICTION_LEDGER.seal.json",
            checkpoint_path=root / "PREDICTION_COMMIT_CHECKPOINTS.jsonl",
            access_log_path=root / "EVENT_REVEAL_LEDGER.jsonl",
            context=context, horizons=horizon_tuple, models=model_tuple,
            seed=seed, verification_status=verification_status,
        )


def _resolve_maturity_label(
    data: Stress2Data, unit: str, target: str, event_index: int
) -> tuple[float, float]:
    rows = data.events.loc[
        data.events["dataset_unit_key"].eq(unit)
        & data.events["event_index_0based"].eq(event_index)
    ]
    if len(rows) != 1:
        raise ValueError(f"expected one maturity event, found {len(rows)}")
    actual = float(rows.iloc[0][target])
    target_time = float(rows.iloc[0]["aging_time_h"])
    if not np.isfinite(actual) or not np.isfinite(target_time):
        raise ValueError("maturity label or time is non-finite")
    return actual, target_time


def _lineage_error_for_group(
    group: pd.DataFrame,
    data: Stress2Data,
    all_series: Mapping[str, dict[str, np.ndarray]],
) -> str | None:
    first = group.iloc[0]
    unit = str(first["outer_test_unit"])
    target = str(first["target"])
    origin = int(first["origin_event_index_0based"])
    if target not in all_series or unit not in all_series[target]:
        return "prediction references unknown target or unit"
    if not group["data_zip_hash"].astype(str).eq(data.source_zip_sha256).all():
        return "raw ZIP hash differs from prediction commitment"
    if not group["data_mat_hash"].astype(str).eq(data.source_mat_sha256).all():
        return "raw MAT hash differs from prediction commitment"
    prefix = all_series[target][unit][: origin + 1]
    if not group["prefix_hash"].astype(str).eq(
        exact_prefix_hash(unit, target, prefix)
    ).all():
        return "exact revealed-prefix hash mismatch"
    train = {key: values for key, values in all_series[target].items() if key != unit}
    train_units = sorted(train)
    if not group["train_set_hash"].astype(str).eq(content_hash(train_units)).all():
        return "train-set hash mismatch"
    expected_training_hash = exact_series_snapshot_hash(
        train, role="outer_training", target=target
    )
    if not group["training_snapshot_hash"].astype(str).eq(
        expected_training_hash
    ).all():
        return "exact outer-training snapshot hash mismatch"
    expected_split_hash = content_hash({
        "test": [unit], "train": train_units, "grouping": "column_surrogate"
    })
    if not group["split_hash"].astype(str).eq(expected_split_hash).all():
        return "split hash mismatch"
    for row in group.to_dict(orient="records"):
        if str(row["prediction_id"]) != prediction_identity_hash(row):
            return "prediction_id does not match committed lineage"
    return None


def _strict_mean(values: pd.Series) -> float:
    array = values.to_numpy(dtype=np.float64)
    return float(np.mean(array)) if array.size and np.all(np.isfinite(array)) else np.nan


def _score_predictions(
    predictions: pd.DataFrame, maturities: pd.DataFrame, data: Stress2Data
) -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = predictions.merge(maturities, on="prediction_id", validate="one_to_one")
    if len(joined) != len(predictions):
        raise AssertionError("every planned prediction must have one maturity row")
    prediction_ok = joined["status"].eq("OK")
    maturity_ok = joined["score_status"].eq("OK")
    finite = np.isfinite(joined["point_prediction"].to_numpy(dtype=float)) & np.isfinite(
        joined["actual"].to_numpy(dtype=float)
    )
    score_ok = prediction_ok.to_numpy() & maturity_ok.to_numpy() & finite
    joined["absolute_error"] = np.where(
        score_ok, np.abs(joined["point_prediction"] - joined["actual"]), np.nan
    )
    joined["squared_error"] = np.where(
        score_ok, (joined["point_prediction"] - joined["actual"]) ** 2, np.nan
    )
    all_series = {target: _all_series_after_seal(data, target) for target in TARGETS}
    records: list[dict[str, Any]] = []
    for (model, target, horizon, unit), group in joined.groupby(
        ["model", "target", "horizon_event_steps", "outer_test_unit"], sort=True
    ):
        failed_mask = (
            ~group["status"].eq("OK") | ~group["score_status"].eq("OK")
            | ~np.isfinite(group["point_prediction"].to_numpy(dtype=float))
            | ~np.isfinite(group["actual"].to_numpy(dtype=float))
        )
        failed = int(np.sum(failed_mask))
        outer_train = {
            key: values for key, values in all_series[str(target)].items()
            if key != str(unit)
        }
        scale_terms = np.asarray([
            float(np.mean(np.abs(np.diff(values))))
            for values in outer_train.values()
        ], dtype=np.float64)
        scale = (
            float(np.mean(scale_terms))
            if scale_terms.size and np.all(np.isfinite(scale_terms)) else np.nan
        )
        if failed:
            metric_status = "NA_planned_failure"
            mae = rmse = mase = np.nan
        elif not np.isfinite(scale) or scale <= 0.0:
            metric_status = "NA_invalid_training_scale"
            mae = rmse = mase = np.nan
        else:
            metric_status = "OK"
            mae = float(np.mean(group["absolute_error"].to_numpy(dtype=np.float64)))
            rmse = float(np.sqrt(np.mean(
                group["squared_error"].to_numpy(dtype=np.float64)
            )))
            mase = float(mae / scale)
        records.append({
            "model": model, "target": target,
            "horizon_event_steps": int(horizon), "outer_test_unit": unit,
            "planned_count": int(len(group)),
            "predicted_count": int(group["status"].eq("OK").sum()),
            "matured_count": int(group["score_status"].eq("OK").sum()),
            "failed_count": failed, "metric_status": metric_status,
            "mae": mae, "rmse": rmse, "mase_training_scale": scale,
            "mase": mase, "last_value_mae": np.nan,
            "relative_mae_vs_last_value": np.nan,
            "skill_vs_last_value": np.nan,
            "comparison_status": "NA_last_value_not_run",
        })
    unit_metrics = pd.DataFrame(records, columns=UNIT_METRIC_COLUMNS)
    baseline_lookup = {
        (row.target, int(row.horizon_event_steps), row.outer_test_unit): row
        for row in unit_metrics[unit_metrics["model"] == "last_value"]
        .itertuples(index=False)
    }
    for index, row in unit_metrics.iterrows():
        baseline = baseline_lookup.get((
            row["target"], int(row["horizon_event_steps"]),
            row["outer_test_unit"],
        ))
        if baseline is None:
            continue
        unit_metrics.at[index, "last_value_mae"] = baseline.mae
        if row["metric_status"] != "OK" or baseline.metric_status != "OK":
            unit_metrics.at[index, "comparison_status"] = "NA_planned_failure"
        elif not np.isfinite(baseline.mae) or baseline.mae <= 0.0:
            unit_metrics.at[index, "comparison_status"] = "NA_zero_last_value_mae"
        else:
            relative = float(row["mae"] / baseline.mae)
            unit_metrics.at[index, "relative_mae_vs_last_value"] = relative
            unit_metrics.at[index, "skill_vs_last_value"] = 1.0 - relative
            unit_metrics.at[index, "comparison_status"] = "OK"
    aggregates: list[dict[str, Any]] = []
    for (model, target, horizon), group in unit_metrics.groupby(
        ["model", "target", "horizon_event_steps"], sort=True
    ):
        any_failure = bool((group["metric_status"] != "OK").any()) or int(
            group["failed_count"].sum()
        ) > 0
        if any_failure:
            aggregate_status = "NA_planned_failure"
            macro_mae = macro_rmse = macro_mase = np.nan
            macro_relative = macro_skill = np.nan
            comparison_status = "NA_planned_failure"
        else:
            aggregate_status = "OK"
            macro_mae = _strict_mean(group["mae"])
            macro_rmse = _strict_mean(group["rmse"])
            macro_mase = _strict_mean(group["mase"])
            if group["comparison_status"].eq("OK").all():
                macro_relative = _strict_mean(group["relative_mae_vs_last_value"])
                macro_skill = _strict_mean(group["skill_vs_last_value"])
                comparison_status = "OK"
            else:
                macro_relative = macro_skill = np.nan
                comparison_status = "NA_incomplete_last_value_comparison"
        aggregates.append({
            "model": model, "target": target,
            "horizon_event_steps": int(horizon), "n_units": int(len(group)),
            "planned_count": int(group["planned_count"].sum()),
            "failed_count": int(group["failed_count"].sum()),
            "aggregate_status": aggregate_status, "macro_mae": macro_mae,
            "macro_rmse": macro_rmse, "macro_mase": macro_mase,
            "macro_relative_mae_vs_last_value": macro_relative,
            "macro_skill_vs_last_value": macro_skill,
            "comparison_status": comparison_status,
        })
    return unit_metrics, pd.DataFrame(aggregates, columns=AGGREGATE_METRIC_COLUMNS)


def mature_sealed_predictions(
    prediction_ledger_path: str | Path,
    prediction_seal_path: str | Path,
    data: Stress2Data,
    *,
    checkpoint_path: str | Path | None = None,
    access_log_path: str | Path | None = None,
) -> dict[str, pd.DataFrame | dict[str, Any]]:
    seal = verify_sealed_ledger(prediction_ledger_path, prediction_seal_path)
    if (checkpoint_path is None) != (access_log_path is None):
        raise ValueError("checkpoint and access logs must be supplied together")
    barrier = None
    if checkpoint_path is not None and access_log_path is not None:
        barrier = verify_causal_barrier(
            prediction_ledger_path, prediction_seal_path,
            checkpoint_path, access_log_path
        )
    predictions = read_verified_ledger(prediction_ledger_path, prediction_seal_path)
    missing = set(PREDICTION_COLUMNS) - set(predictions.columns)
    if missing:
        raise ValueError(f"prediction ledger missing columns: {sorted(missing)}")
    models = tuple(sorted(predictions["model"].astype(str).unique()))
    _assert_common_key_parity(predictions, models)
    all_series = {
        target: _all_series_after_seal(data, target) for target in TARGETS
    }
    maturities: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for row in predictions.to_dict(orient="records"):
        if str(row["status"]) != "OK":
            stage_value = row.get("failure_stage")
            stage = "predict" if pd.isna(stage_value) else str(stage_value)
            error_value = row.get("error")
            error = (
                "prediction failed without an error message"
                if pd.isna(error_value) else str(error_value)
            )
            failures.append(_failure_from_prediction(row, stage, error))
    common_columns = [
        "outer_test_unit", "target", "horizon_event_steps",
        "origin_event_index_0based", "expected_target_event_index_0based",
    ]
    for _, group in predictions.groupby(common_columns, sort=True, dropna=False):
        first = group.iloc[0]
        event_index = int(first["expected_target_event_index_0based"])
        try:
            lineage_error = _lineage_error_for_group(group, data, all_series)
            if lineage_error is not None:
                raise ValueError(lineage_error)
            actual, target_time = _resolve_maturity_label(
                data, str(first["outer_test_unit"]),
                str(first["target"]), event_index,
            )
            label_hash = content_hash({
                "data_zip_hash": data.source_zip_sha256,
                "data_mat_hash": data.source_mat_sha256,
                "unit": str(first["outer_test_unit"]),
                "target": str(first["target"]), "event_index": event_index,
                "actual_hex": float(actual).hex(),
                "target_time_hex": float(target_time).hex(),
            })
            maturity_error = None
        except Exception as exc:
            actual = target_time = np.nan
            label_hash = None
            maturity_error = f"{type(exc).__name__}: {exc}"
        for row in group.to_dict(orient="records"):
            if maturity_error is not None:
                score_status = "FAIL_maturity"
                error = maturity_error
                failures.append(_failure_from_prediction(
                    row, "maturity", maturity_error
                ))
            elif str(row["status"]) != "OK":
                score_status = "NA_prediction_failed"
                error = None
            else:
                score_status = "OK"
                error = None
            maturities.append({
                "prediction_id": row["prediction_id"],
                "label_available_seq": event_index,
                "target_event_index_0based": event_index,
                "target_time_h": target_time, "actual": actual,
                "label_lineage_hash": label_hash,
                "score_status": score_status, "error": error,
            })
    maturity_df = pd.DataFrame(maturities, columns=MATURITY_COLUMNS).sort_values(
        "prediction_id"
    ).reset_index(drop=True)
    failure_df = pd.DataFrame(failures, columns=FAILURE_COLUMNS)
    if not failure_df.empty:
        failure_df = failure_df.drop_duplicates(
            ["prediction_id", "failure_stage"], keep="first"
        ).sort_values([
            "outer_test_unit", "model", "target", "horizon_event_steps",
            "origin_event_index_0based", "failure_stage",
        ]).reset_index(drop=True)
    unit_metrics, aggregate_metrics = _score_predictions(
        predictions, maturity_df, data
    )
    return {
        "predictions": predictions, "maturities": maturity_df,
        "failures": failure_df, "unit_metrics": unit_metrics,
        "aggregate_metrics": aggregate_metrics,
        "maturity_summary": {
            "prediction_ledger_sha256": seal["ledger_sha256"],
            "prediction_ledger_final_row_hash": seal["final_row_hash"],
            "prediction_seal_verified_before_maturity": True,
            "seal_verified_before_maturity": True,
            "causal_barrier_verified_before_maturity": barrier is not None,
            "maturity_rows": int(len(maturity_df)),
            "failure_rows": int(len(failure_df)),
        },
    }


def run_nested_loco(
    data: Stress2Data,
    protocol_hash: str,
    package_dir: str | Path,
    context: int = 4,
    horizons: Iterable[int] = (1, 2, 3),
    models: Iterable[str] = MODEL_ORDER,
    seed: int = 20260813,
    verification_status: str = "VERIFIED",
) -> dict[str, pd.DataFrame | dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="audit-cap-online-replay-") as directory:
        root = Path(directory)
        ledger_path = root / "PREDICTION_LEDGER.csv"
        seal_path = root / "PREDICTION_LEDGER.seal.json"
        checkpoint_path = root / "PREDICTION_COMMIT_CHECKPOINTS.jsonl"
        access_path = root / "EVENT_REVEAL_LEDGER.jsonl"
        generation = generate_nested_loco_predictions(
            data=data, protocol_hash=protocol_hash, package_dir=package_dir,
            context=context, horizons=horizons, models=models, seed=seed,
            verification_status=verification_status,
            ledger_path=ledger_path, seal_path=seal_path,
            checkpoint_path=checkpoint_path, access_log_path=access_path,
        )
        scoring = mature_sealed_predictions(
            ledger_path, seal_path, data,
            checkpoint_path=checkpoint_path, access_log_path=access_path,
        )
    summary = {
        "benchmark": "NASA Stress-2 parser/replay harness",
        "identity_scope": "six column-surrogate units; physical identity unverified",
        "termination_scope": "unknown; RUL numeric scoring disabled",
        **dict(generation["generation_summary"]),
        **dict(scoring["maturity_summary"]),
        "rul_metrics_status": "NA_unknown_termination_and_insufficient_independent_units",
        "prediction_intervals_status": "NA_insufficient_independent_calibration_units",
    }
    return {
        "predictions": generation["predictions"],
        "maturities": scoring["maturities"],
        "tuning": generation["tuning"],
        "failures": scoring["failures"],
        "unit_metrics": scoring["unit_metrics"],
        "aggregate_metrics": scoring["aggregate_metrics"],
        "barrier_evidence": generation["barrier_evidence"],
        "summary": summary,
    }
