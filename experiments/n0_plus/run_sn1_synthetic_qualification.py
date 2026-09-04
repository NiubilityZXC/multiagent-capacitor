"""Run the N0+ SN1 synthetic-only behavioral qualification.

No ground-truth accuracy ranking is computed.  The output records only causal,
deterministic, completeness, and schema checks for generated toy trajectories.
"""

from __future__ import annotations

import argparse
from importlib.metadata import version
import os
from pathlib import Path
import tempfile
from typing import Any, Sequence

import numpy as np

from experiments.n0_plus.sn1_synthetic_models import (
    IMPLEMENTED_CANDIDATES,
    QUANTILE_LEVELS,
    SN1_AUTHORITY,
    fit_synthetic_candidate,
    predict_synthetic_candidate,
)
from experiments.vfps_agent.canonical import canonical_bytes, canonical_sha256


def synthetic_fleet() -> dict[str, np.ndarray]:
    time = np.arange(48, dtype=np.float64)
    return {
        "synthetic-train-a": 1.00 - 0.0028 * time - 0.000035 * time * time,
        "synthetic-train-b": 1.02 - 0.0024 * time - 0.000045 * time * time,
        "synthetic-train-c": 0.98 - 0.0032 * time - 0.000030 * time * time,
        "synthetic-train-d": 1.01 - 0.0027 * time - 0.000040 * time * time,
    }


def held_out_synthetic_series() -> np.ndarray:
    time = np.arange(48, dtype=np.float64)
    return 1.015 - 0.0026 * time - 0.000038 * time * time


def qualification_payload(seed: int = 20260904) -> dict[str, Any]:
    units = synthetic_fleet()
    evaluation = held_out_synthetic_series()
    evaluation_unit_disjoint = all(
        not np.array_equal(evaluation, training_series)
        for training_series in units.values()
    )
    if not evaluation_unit_disjoint:
        raise RuntimeError("synthetic evaluation unit duplicates a training unit")
    visible = evaluation[:24]
    suffix_a = np.linspace(visible[-1], 0.20, 12)
    suffix_b = np.linspace(visible[-1], 1.80, 12)
    horizons = (1, 3, 5)
    records: list[dict[str, Any]] = []
    for candidate_id in sorted(IMPLEMENTED_CANDIDATES):
        state = fit_synthetic_candidate(
            candidate_id,
            units,
            horizons,
            seed=seed,
            authority=SN1_AUTHORITY,
        )
        first = predict_synthetic_candidate(
            state,
            np.concatenate([visible, suffix_a])[: len(visible)],
            authority=SN1_AUTHORITY,
        )
        second = predict_synthetic_candidate(
            state,
            np.concatenate([visible, suffix_b])[: len(visible)],
            authority=SN1_AUTHORITY,
        )
        repeated = predict_synthetic_candidate(
            state,
            visible,
            authority=SN1_AUTHORITY,
        )
        matrix = np.asarray(tuple(first.quantile_map.values()), dtype=np.float64)
        checks = {
            "complete_horizons": first.horizons == horizons,
            "deterministic": first == repeated,
            "finite": bool(np.all(np.isfinite(first.points)) and np.all(np.isfinite(matrix))),
            "nested_quantiles": bool(np.all(np.diff(matrix, axis=0) >= -1e-12)),
            "suffix_invariant": first == second,
        }
        if not all(checks.values()):
            raise RuntimeError(f"SN1 qualification failed for {candidate_id}: {checks}")
        forecast_payload = {
            "horizons": list(first.horizons),
            "points": list(first.points),
            "quantiles": {str(level): list(values) for level, values in first.quantiles},
            "diagnostics": dict(first.diagnostics),
        }
        records.append(
            {
                "candidate_id": candidate_id,
                "checks": checks,
                "forecast_payload_sha256": canonical_sha256(forecast_payload),
            }
        )
    return {
        "schema_version": "N0PlusSN1SyntheticQualification.v1",
        "status": "PASS_CONTRACT_ONLY_NO_SCIENTIFIC_RESULT",
        "authority": SN1_AUTHORITY,
        "seed": seed,
        "horizons": list(horizons),
        "quantile_levels": list(QUANTILE_LEVELS),
        "environment": {
            "numpy": version("numpy"),
            "scikit_learn": version("scikit-learn"),
            "statsforecast": version("statsforecast"),
        },
        "candidate_count": len(records),
        "training_unit_count": len(units),
        "evaluation_unit_disjoint": evaluation_unit_disjoint,
        "interval_claim": "SHAPE_ONLY_NOT_CALIBRATED",
        "small_ml_interval_semantics": "IN_SAMPLE_TOY_RESIDUAL_QUANTILES_NOT_VALID_FOR_P2",
        "records": records,
        "scientific_metrics_computed": False,
        "real_data_accessed": False,
        "outer_labels_accessed": False,
        "api_calls": 0,
        "gpu_runs": 0,
    }


def write_payload(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(canonical_bytes(payload))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Path for canonical JSON qualification output")
    parser.add_argument("--seed", type=int, default=20260904)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = qualification_payload(seed=args.seed)
    write_payload(args.output, payload)
    print(f"SN1 synthetic qualification PASS: {payload['candidate_count']} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
