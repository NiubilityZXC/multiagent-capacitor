#!/usr/bin/env python3
"""Run the frozen CPU-only Stress-2 parser/replay sanity benchmark."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy
import sklearn

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from experiments.audit_cap.models import MODEL_ORDER
from experiments.audit_cap.ledger import verify_sealed_ledger
from experiments.audit_cap.replay import (
    file_hash,
    generate_nested_loco_predictions,
    mature_sealed_predictions,
)
from experiments.audit_cap.stress2 import load_stress2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True, help="Official EOS_DataSet.zip")
    parser.add_argument("--protocol", type=Path, required=True, help="Frozen evaluation protocol")
    parser.add_argument("--output-dir", type=Path, required=True, help="New run-specific output directory")
    parser.add_argument("--context", type=int, default=4)
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--models", nargs="+", choices=MODEL_ORDER, default=list(MODEL_ORDER))
    parser.add_argument("--seed", type=int, default=20260813)
    parser.add_argument("--allow-unverified-data", action="store_true")
    return parser.parse_args()


def write_csv(path: Path, table: pd.DataFrame) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    table.to_csv(temporary, index=False, float_format="%.17g", na_rep="NA", lineterminator="\n")
    os.replace(temporary, path)


def write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    if args.output_dir.is_symlink():
        raise SystemExit(f"refusing symlink output directory: {args.output_dir}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty output directory: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    protocol_hash = file_hash(args.protocol)
    data = load_stress2(args.zip, verify_hash=not args.allow_unverified_data)
    verification_status = "UNVERIFIED" if args.allow_unverified_data else "VERIFIED"
    claim_status = (
        "PROHIBITED_UNVERIFIED_DATA"
        if args.allow_unverified_data
        else "NOT_ELIGIBLE_BENCHMARK_S_SANITY_ONLY"
    )

    # The event/label service owns the full held-out sequence.  Forecasting sees
    # only a revealed prefix.  Each origin is durably committed and checkpointed
    # before the service may reveal the next event.
    prediction_path = args.output_dir / "PREDICTION_LEDGER.csv"
    prediction_seal_path = args.output_dir / "PREDICTION_LEDGER.seal.json"
    checkpoint_path = args.output_dir / "PREDICTION_COMMIT_CHECKPOINTS.jsonl"
    access_log_path = args.output_dir / "EVENT_REVEAL_LEDGER.jsonl"
    generation = generate_nested_loco_predictions(
        data=data,
        protocol_hash=protocol_hash,
        package_dir=Path(__file__).resolve().parent,
        context=args.context,
        horizons=args.horizons,
        models=args.models,
        seed=args.seed,
        verification_status=verification_status,
        ledger_path=prediction_path,
        seal_path=prediction_seal_path,
        checkpoint_path=checkpoint_path,
        access_log_path=access_log_path,
    )
    prediction_seal = dict(generation["prediction_seal"])
    verified_seal = verify_sealed_ledger(prediction_path, prediction_seal_path)

    # Scoring re-verifies the final seal and both causal logs before resolving
    # any maturity target.
    scoring = mature_sealed_predictions(
        prediction_path,
        prediction_seal_path,
        data,
        checkpoint_path=checkpoint_path,
        access_log_path=access_log_path,
    )

    tables = {
        "CANONICAL_EVENTS.csv": data.events,
        "ENDPOINT_LABELS.csv": data.endpoints,
        "MATURITY_LEDGER.csv": scoring["maturities"],
        "INNER_TUNING_LEDGER.csv": generation["tuning"],
        "FAILURE_LEDGER.csv": scoring["failures"],
        "UNIT_METRICS.csv": scoring["unit_metrics"],
        "AGGREGATE_METRICS.csv": scoring["aggregate_metrics"],
    }
    for name, table in tables.items():
        write_csv(args.output_dir / name, table)

    summary = {
        "benchmark": "NASA Stress-2 parser/replay harness",
        "identity_scope": "six column-surrogate units; physical identity unverified",
        "termination_scope": "unknown; RUL numeric scoring disabled",
        **dict(generation["generation_summary"]),
        **dict(scoring["maturity_summary"]),
        "verification_status": verification_status,
        "claim_status": claim_status,
        "claim_prohibited": True,
        "rul_metrics_status": "NA_unknown_termination_and_insufficient_independent_units",
        "prediction_intervals_status": "NA_insufficient_independent_calibration_units",
        "prediction_seal_sha256": file_hash(prediction_seal_path),
        "prediction_seal_verified": verified_seal == prediction_seal,
    }
    summary.update(
        {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "command": " ".join(sys.argv),
            "python": sys.version,
            "platform": platform.platform(),
            "dependencies": {
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "pandas": pd.__version__,
                "h5py": h5py.__version__,
                "scikit_learn": sklearn.__version__,
            },
            "thread_environment": {
                key: os.environ.get(key)
                for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
            },
        }
    )
    write_json(args.output_dir / "RUN_SUMMARY.json", summary)
    artifacts = {
        path.name: {"bytes": path.stat().st_size, "sha256": file_hash(path)}
        for path in sorted(args.output_dir.iterdir())
        if path.is_file()
    }
    manifest_path = args.output_dir / "RUN_MANIFEST.json"
    write_json(
        manifest_path,
        {
            "artifacts": artifacts,
            "source_zip": str(args.zip.resolve()),
            "protocol": str(args.protocol.resolve()),
            "output_dir": str(args.output_dir.resolve()),
            "verification_status": verification_status,
            "claim_status": claim_status,
            "claim_prohibited": True,
            "prediction_ledger_seal": prediction_seal,
            "causal_barrier_evidence": generation["barrier_evidence"],
        },
    )
    # A run is consumable only after every ledger and the manifest have been
    # durably materialized.  The marker is intentionally written last and
    # binds the manifest rather than being included in it.
    write_json(
        args.output_dir / "COMPLETE",
        {
            "status": "COMPLETE",
            "run_manifest_sha256": file_hash(manifest_path),
            "prediction_ledger_seal_sha256": file_hash(prediction_seal_path),
            "completed_utc": datetime.now(timezone.utc).isoformat(),
            "claim_status": claim_status,
            "claim_prohibited": True,
        },
    )
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
