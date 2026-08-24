"""Durable append-only CSV ledgers with a per-row hash chain and seal."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

GENESIS_HASH = "0" * 64


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value):
            return {"nonfinite": "NaN"}
        if math.isinf(value):
            return {"nonfinite": "+Inf" if value > 0 else "-Inf"}
        return value
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def add_hash_chain(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach canonical row payload, previous hash, and current hash."""

    forbidden = {"row_payload_json", "prev_row_hash", "row_hash"} & set(frame.columns)
    if forbidden:
        raise ValueError(f"frame already contains hash-chain columns: {sorted(forbidden)}")
    rows: list[dict[str, Any]] = []
    previous = GENESIS_HASH
    for source in frame.to_dict(orient="records"):
        payload = {key: _json_value(source[key]) for key in frame.columns}
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        row_hash = hashlib.sha256((previous + "\n" + payload_json).encode("utf-8")).hexdigest()
        rows.append(
            {
                **source,
                "row_payload_json": payload_json,
                "prev_row_hash": previous,
                "row_hash": row_hash,
            }
        )
        previous = row_hash
    return pd.DataFrame(rows, columns=[*frame.columns, "row_payload_json", "prev_row_hash", "row_hash"])


def _csv_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return "NA"
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if not math.isfinite(value):
            return "NA" if math.isnan(value) else ("+Inf" if value > 0 else "-Inf")
        return format(value, ".17g")
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _atomic_json(path: Path, payload: object) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_sealed_ledger(
    path: str | Path,
    frame: pd.DataFrame,
    seal_path: str | Path,
    lineage: dict[str, Any],
    *,
    seal_status: str = "SEALED_BEFORE_LABEL_ACCESS",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Create a new ledger, fsync every row, then atomically publish a seal."""

    ledger_path = Path(path)
    seal = Path(seal_path)
    if ledger_path.exists() or seal.exists():
        raise FileExistsError("append-only ledger or seal already exists")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    chained = add_hash_chain(frame)
    with ledger_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(chained.columns), lineterminator="\n")
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())
        for row in chained.to_dict(orient="records"):
            writer.writerow({key: _csv_value(value) for key, value in row.items()})
            handle.flush()
            os.fsync(handle.fileno())
    seal_payload = {
        "ledger": ledger_path.name,
        "ledger_sha256": sha256_file(ledger_path),
        "row_count": int(len(chained)),
        "final_row_hash": GENESIS_HASH if chained.empty else str(chained.iloc[-1].row_hash),
        "columns": list(chained.columns),
        "lineage": lineage,
        "seal_status": seal_status,
    }
    _atomic_json(seal, seal_payload)
    return chained, seal_payload


def verify_sealed_ledger(path: str | Path, seal_path: str | Path) -> dict[str, Any]:
    ledger_path = Path(path)
    seal = json.loads(Path(seal_path).read_text(encoding="utf-8"))
    if sha256_file(ledger_path) != seal["ledger_sha256"]:
        raise ValueError("ledger SHA-256 does not match seal")
    previous = GENESIS_HASH
    count = 0
    with ledger_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != seal["columns"]:
            raise ValueError("ledger columns do not match seal")
        for row in reader:
            if row["prev_row_hash"] != previous:
                raise ValueError("ledger previous-hash chain is broken")
            expected = hashlib.sha256((previous + "\n" + row["row_payload_json"]).encode("utf-8")).hexdigest()
            if row["row_hash"] != expected:
                raise ValueError("ledger row hash is invalid")
            previous = expected
            count += 1
    if count != int(seal["row_count"]) or previous != seal["final_row_hash"]:
        raise ValueError("ledger row count or final hash does not match seal")
    return seal


def read_verified_ledger(path: str | Path, seal_path: str | Path) -> pd.DataFrame:
    verify_sealed_ledger(path, seal_path)
    return pd.read_csv(path, na_values=["NA", "+Inf", "-Inf"], keep_default_na=True)
