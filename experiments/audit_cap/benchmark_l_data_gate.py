#!/usr/bin/env python3
"""Frozen P1 parser and Data Gate for the NASA capacitor ES10/12/14 files.

This module deliberately stops at byte, reference, schema, time, missingness,
identity, and outcome auditing.  It does not construct a capacity/ESR/SOH/RUL
target and it does not train or evaluate a model.

The stable artifacts contain neither a run timestamp nor an absolute output
path.  Unsafe inputs (links, external storage, VDS, dangling references, or
resource-limit violations) abort before the requested append-only output is
published.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import shutil
import tempfile
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "audit-cap.benchmark-l-data-gate.v1.1"
TARGET_FILES = ("ES10.mat", "ES12.mat", "ES14.mat")
CONDITIONS = ("ES10", "ES12", "ES14")
EXPECTED_RAW_TOKENS = (
    "freq/Hz",
    "Re(Z)/Ohm",
    "-Im(Z)/Ohm",
    "|Z|/Ohm",
    "Phase(Z)/deg",
    "time/s",
    "<Ewe>/V",
    "<I>/mA",
    "Cs/µF",
    "Cp/µF",
    "cycle",
    "number",
    "I",
    "Range",
    "|Ewe|/V",
    "|I|/A",
    "Re(Y)/Ohm-1",
    "Im(Y)/Ohm-1",
    "|Y|/Ohm-1",
    "Phase(Y)/deg",
)
CANONICAL_COLUMNS = (
    "freq/Hz",
    "Re(Z)/Ohm",
    "-Im(Z)/Ohm",
    "|Z|/Ohm",
    "Phase(Z)/deg",
    "time/s",
    "<Ewe>/V",
    "<I>/mA",
    "Cs/µF",
    "Cp/µF",
    "cycle number",
    "I Range",
    "|Ewe|/V",
    "|I|/A",
    "Re(Y)/Ohm-1",
    "Im(Y)/Ohm-1",
    "|Y|/Ohm-1",
    "Phase(Y)/deg",
)
REAL_CONTRACT_SHA256 = "6e2a726177e68a51f9df39f33b5ac8135aeb1221642c48743d37605cb2eaad19"
REAL_AMENDMENT_SHA256 = "73228e662c5d742a1cd5e3f6fadedd22e8e24fa34d501a274d55d4dd6f12e5a7"
REAL_TOKEN_NUL_SHA256 = "54f470b08afd092df6cadc7416935e539aa20ff07ef66595ecffb7efbf39ad09"
REAL_POSITIVE_GRID_SHA256 = "aa3342e1e33b3a41b1abdcbc916f81f48066ab65a84988a8ce8c9cfeb79c0629"
MAX_CELL_REFERENCES = 100_000
MAX_CHAR_ELEMENTS = 2_000_000
MAX_EIS_ELEMENTS = 2_000_000
ALGEBRA_TOLERANCE = 1e-5

REQUIRED_JSON = (
    "DATA_GATE_CONTRACT.json",
    "DATA_MANIFEST.json",
    "TARGET_DEFINITIONS.json",
    "SCHEMA_TEST_RESULTS.json",
    "DATA_GATE_SUMMARY.json",
    "ARTIFACT_MANIFEST.json",
    "COMPLETE.json",
)
REQUIRED_CSV = (
    "REFERENCE_LINKAGE_LEDGER.csv",
    "EIS_EVENT_LEDGER.csv",
    "COLUMN_FREQUENCY_LEDGER.csv",
    "TRANSIENT_ALIGNMENT_LEDGER.csv",
    "MISSINGNESS_LEDGER.csv",
    "UNIT_IDENTITY_LEDGER.csv",
    "CONTENT_SIGNATURE_LEDGER.csv",
    "DUPLICATE_CANDIDATE_LEDGER.csv",
    "REPAIR_QUARANTINE_LEDGER.csv",
    "TARGET_TRAJECTORY_LEDGER.csv",
    "OUTCOME_LEDGER.csv",
    "ELIGIBILITY_MATRIX.csv",
)


class DataGateError(RuntimeError):
    """Unsafe input or an unmet non-negotiable parser precondition."""


@dataclass(frozen=True)
class Source:
    condition: str
    path: Path
    sha256: str
    crc32: str
    size_bytes: int


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path, block_bytes: int = 8 * 1024 * 1024) -> tuple[str, str, int]:
    digest = hashlib.sha256()
    crc = 0
    size = 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(block_bytes)
            if not block:
                break
            digest.update(block)
            crc = zlib.crc32(block, crc)
            size += len(block)
    return digest.hexdigest(), f"{crc & 0xFFFFFFFF:08x}", size


def _read_json_file(path: Path, label: str) -> tuple[dict[str, Any], str]:
    if not path.is_file() or path.is_symlink():
        raise DataGateError(f"{label} must be a regular non-symlink file: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataGateError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DataGateError(f"{label} must contain a JSON object")
    return value, _sha_bytes(raw)


def _load_dependencies() -> tuple[Any, Any]:
    try:
        import h5py  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise DataGateError("h5py and numpy are required") from exc
    return h5py, np


def _matlab_class(obj: Any) -> str:
    value = obj.attrs.get("MATLAB_class", b"")
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="strict")
    if hasattr(value, "tobytes"):
        try:
            return value.tobytes().decode("utf-8", errors="strict").rstrip("\x00")
        except UnicodeDecodeError:
            return ""
    return str(value)


def _validate_storage(dataset: Any, context: str) -> None:
    try:
        external = tuple(dataset.external or ())
        virtual = bool(dataset.is_virtual)
    except Exception as exc:
        raise DataGateError(f"cannot inspect storage layout for {context}: {type(exc).__name__}") from exc
    if external:
        raise DataGateError(f"external HDF5 storage is forbidden at {context}")
    if virtual:
        raise DataGateError(f"virtual HDF5 datasets are forbidden at {context}")


def _hard_object(h5_file: Any, path: str, h5py: Any, *, group: bool = False) -> Any:
    parent_name, name = path.rsplit("/", 1)
    parent_name = parent_name or "/"
    try:
        parent = h5_file[parent_name]
        link = parent.get(name, getlink=True)
    except Exception as exc:
        raise DataGateError(f"missing allowlisted HDF5 path: {path}") from exc
    if not isinstance(link, h5py.HardLink):
        raise DataGateError(f"allowlisted HDF5 path must be a hard link: {path}")
    obj = parent[name]
    expected_type = h5py.Group if group else h5py.Dataset
    if not isinstance(obj, expected_type):
        raise DataGateError(f"unexpected object type at allowlisted path: {path}")
    if not group:
        _validate_storage(obj, path)
    return obj


def _is_canonical_empty(dataset: Any) -> bool:
    return _matlab_class(dataset).strip().lower() == "canonical empty"


def _resolve_ref(
    h5_file: Any,
    reference: Any,
    h5py: Any,
    context: str,
) -> tuple[Any | None, str]:
    try:
        truth = bool(reference)
    except Exception as exc:
        raise DataGateError(f"invalid reference value at {context}") from exc
    if not truth:
        return None, "null_empty_reference"
    try:
        obj = h5_file[reference]
    except Exception as exc:
        raise DataGateError(f"dangling or bad HDF5 reference at {context}") from exc
    if not isinstance(obj, h5py.Dataset):
        raise DataGateError(f"reference target must be a dataset at {context}")
    if not obj.name.startswith("/#refs#/"):
        raise DataGateError(f"reference target escapes the /#refs#/ allowlist at {context}")
    _validate_storage(obj, context)
    if _is_canonical_empty(obj):
        if int(obj.size) > 64:
            raise DataGateError(f"oversized canonical empty marker at {context}")
        return obj, "canonical_empty"
    return obj, "resolved"


def _reference_vector(dataset: Any, h5_file: Any, h5py: Any, context: str) -> list[Any]:
    if int(dataset.size) > MAX_CELL_REFERENCES:
        raise DataGateError(f"reference cell exceeds limit at {context}")
    if h5py.check_dtype(ref=dataset.dtype) is None:
        raise DataGateError(f"expected an object-reference cell at {context}")
    try:
        values = dataset[...]
    except Exception as exc:
        raise DataGateError(f"cannot read reference cell at {context}") from exc
    # MATLAB v7.3 arrays are traversed in MATLAB/Fortran index order.
    return list(values.reshape(-1, order="F"))


def _decode_char_columns(dataset: Any, np: Any, context: str) -> list[str]:
    if int(dataset.size) > MAX_CHAR_ELEMENTS:
        raise DataGateError(f"char matrix exceeds limit at {context}")
    if dataset.dtype.kind not in "ui" or dataset.ndim not in (1, 2):
        raise DataGateError(f"invalid MATLAB char matrix at {context}")
    values = np.asarray(dataset[...])
    if values.ndim == 1:
        values = values.reshape((-1, 1))
    result: list[str] = []
    for column in values.T:
        chars: list[str] = []
        for code in column:
            integer = int(code)
            if integer == 0:
                continue
            if integer < 0 or integer > 0x10FFFF:
                raise DataGateError(f"invalid Unicode codepoint in char matrix at {context}")
            chars.append(chr(integer))
        result.append("".join(chars).rstrip())
    return result


def _canonical_dtype(dtype: Any, np: Any) -> Any:
    value = np.dtype(dtype)
    if value.kind in "iufc":
        return value.newbyteorder("<")
    return value


def _normalised_numeric(values: Any, dtype: Any, np: Any) -> Any:
    target = _canonical_dtype(dtype, np)
    result = np.asarray(values, dtype=target, order="C").copy(order="C")
    if result.dtype.kind in "fc":
        result[result == 0] = 0
        if result.dtype.kind == "f":
            mask = np.isnan(result)
            if mask.any():
                result[mask] = np.array(np.nan, dtype=result.dtype)
        else:
            real_nan = np.isnan(result.real)
            imag_nan = np.isnan(result.imag)
            if real_nan.any():
                result.real[real_nan] = np.array(np.nan, dtype=result.real.dtype)
            if imag_nan.any():
                result.imag[imag_nan] = np.array(np.nan, dtype=result.imag.dtype)
    return result


def _signature_prefix(dtype: Any, shape: Sequence[int], np: Any) -> bytes:
    description = {
        "dtype": _canonical_dtype(dtype, np).str,
        "shape": [int(value) for value in shape],
    }
    return _json(description).encode("utf-8") + b"\x00"


def _array_signature(values: Any, np: Any) -> str:
    canonical = _normalised_numeric(values, values.dtype, np)
    digest = hashlib.sha256()
    digest.update(_signature_prefix(canonical.dtype, canonical.shape, np))
    digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.microsecond:
        return value.isoformat(timespec="microseconds")
    return value.isoformat(timespec="seconds")


_ACQUISITION_RE = re.compile(
    r"^Acquisition started on\s*:\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2})\s*$",
    re.IGNORECASE,
)
_CHANNEL_RE = re.compile(r"^Run on channel\s*:\s*(\d+)(?:\s*\(SN\s*([^\)]+)\))?", re.IGNORECASE)
_DEVICE_RE = re.compile(r"^Device\s*:\s*([^\(]+?)(?:\s*\(SN\s*([^\)]+)\))?\s*$", re.IGNORECASE)


def _parse_header(lines: Sequence[str]) -> dict[str, Any]:
    acquisition: datetime | None = None
    channel = ""
    channel_serial = ""
    instrument = ""
    instrument_serial = ""
    protocol = ""
    for raw_line in lines:
        line = raw_line.strip()
        match = _ACQUISITION_RE.match(line)
        if match:
            try:
                parsed = datetime.strptime(match.group(1), "%m/%d/%Y %H:%M:%S")
            except ValueError:
                parsed = None
            if acquisition is not None and parsed != acquisition:
                return {"status": "conflicting_acquisition_start"}
            acquisition = parsed
            continue
        match = _CHANNEL_RE.match(line)
        if match:
            channel = match.group(1)
            channel_serial = (match.group(2) or "").strip()
            continue
        match = _DEVICE_RE.match(line)
        if match:
            instrument = match.group(1).strip()
            instrument_serial = (match.group(2) or "").strip()
            continue
        lowered = line.lower()
        if "electrochemical impedance spectroscopy" in lowered:
            protocol = "electrochemical_impedance_spectroscopy"
    status = "passed" if acquisition is not None and protocol else "failed"
    return {
        "status": status,
        "acquisition_start": acquisition,
        "channel": channel,
        "channel_serial": channel_serial,
        "instrument": instrument,
        "instrument_serial": instrument_serial,
        "measurement_protocol": protocol,
    }


def _merge_column_tokens(tokens: Sequence[str]) -> tuple[str, ...] | None:
    if tuple(tokens) != EXPECTED_RAW_TOKENS:
        return None
    merged = list(tokens[:10])
    merged.append("cycle number")
    merged.append("I Range")
    merged.extend(tokens[14:])
    return tuple(merged) if tuple(merged) == CANONICAL_COLUMNS else None


def _scaled_error(actual: Any, expected: Any, np: Any) -> float:
    actual = np.asarray(actual, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    finite = np.isfinite(actual) & np.isfinite(expected)
    if not finite.all() or finite.size == 0:
        return math.inf
    denom = np.maximum(np.maximum(np.abs(actual), np.abs(expected)), 1e-12)
    return float(np.max(np.abs(actual - expected) / denom))


def _eis_numeric_audit(matrix: Any, amendment: Mapping[str, Any], np: Any) -> dict[str, Any]:
    if matrix.ndim != 2 or matrix.shape[1] != 18:
        return {"status": "failed", "reason": "canonical_shape_not_n_by_18"}
    n_rows = int(matrix.shape[0])
    freq = np.asarray(matrix[:, 0], dtype=np.float64)
    invalid = (~np.isfinite(freq)) | (freq < 0)
    preamble = freq == 0
    positive = freq > 0
    first_positive = int(np.argmax(positive)) if positive.any() else n_rows
    preamble_prefix = bool(
        np.all(preamble[:first_positive])
        and np.all(~preamble[first_positive:])
        and np.all(positive[first_positive:])
    )
    positive_values = freq[positive]
    decreasing = bool(positive_values.size > 1 and np.all(np.diff(positive_values) < 0))
    row_contract = amendment.get("frequency_row_contract", {})
    allowed_rows = {int(value) for value in row_contract.get("raw_row_counts_allowed", [58, 59])}
    allowed_preamble = {
        int(value) for value in row_contract.get("allowed_preamble_lengths", [7, 8])
    }
    expected_frequency = int(row_contract.get("expected_positive_sweep_rows", 51))
    positive_le = np.asarray(positive_values, dtype="<f8")
    grid_hash = _sha_bytes(positive_le.tobytes(order="C"))

    algebra_errors: dict[str, float] = {}
    algebra_status = "failed"
    if positive_values.size and matrix.shape[1] == 18:
        m = np.asarray(matrix[positive, :], dtype=np.float64)
        f, re_z, neg_im_z, zmag, phase = m[:, 0], m[:, 1], m[:, 2], m[:, 3], m[:, 4]
        cs, cp = m[:, 8], m[:, 9]
        re_y, im_y, ymag, phase_y = m[:, 14], m[:, 15], m[:, 16], m[:, 17]
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            denom = re_z * re_z + neg_im_z * neg_im_z
            expected = {
                "z_magnitude": np.hypot(re_z, neg_im_z),
                "z_phase": np.degrees(np.arctan2(-neg_im_z, re_z)),
                "re_y": re_z / denom,
                "im_y": neg_im_z / denom,
                "y_magnitude": 1.0 / zmag,
                "y_phase": -phase,
                "cs": 1e6 / (2.0 * np.pi * f * neg_im_z),
                "cp": 1e6 * im_y / (2.0 * np.pi * f),
            }
        actual = {
            "z_magnitude": zmag,
            "z_phase": phase,
            "re_y": re_y,
            "im_y": im_y,
            "y_magnitude": ymag,
            "y_phase": phase_y,
            "cs": cs,
            "cp": cp,
        }
        algebra_errors = {
            name: _scaled_error(actual[name], expected_value, np)
            for name, expected_value in expected.items()
        }
        algebra_status = (
            "passed" if all(value <= ALGEBRA_TOLERANCE for value in algebra_errors.values()) else "failed"
        )

    checks = {
        "raw_row_count_allowed": n_rows in allowed_rows,
        "invalid_frequency_count_zero": int(invalid.sum()) == 0,
        "preamble_contiguous_prefix": preamble_prefix,
        "preamble_length_allowed": int(preamble.sum()) in allowed_preamble,
        "positive_sweep_rows_expected": int(positive.sum()) == expected_frequency,
        "positive_sweep_strictly_decreasing": decreasing,
        "algebra_sanity": algebra_status == "passed",
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "n_raw_rows": n_rows,
        "n_preamble": int(preamble.sum()),
        "n_frequency": int(positive.sum()),
        "invalid_frequency_count": int(invalid.sum()),
        "positive_grid_sha256": grid_hash,
        "checks": checks,
        "algebra_status": algebra_status,
        "algebra_max_scaled_error": (
            max(algebra_errors.values()) if algebra_errors else math.inf
        ),
        "algebra_errors": algebra_errors,
    }


def _finite_counts(values: Any, np: Any) -> dict[str, int]:
    if values.dtype.kind not in "fc":
        return {
            "element_count": int(values.size),
            "finite_count": int(values.size),
            "nan_count": 0,
            "inf_count": 0,
        }
    return {
        "element_count": int(values.size),
        "finite_count": int(np.isfinite(values).sum()),
        "nan_count": int(np.isnan(values).sum()),
        "inf_count": int(np.isinf(values).sum()),
    }


def _equidistant_indices(length: int, count: int, np: Any) -> Any:
    if length <= 0:
        return np.asarray([], dtype=np.int64)
    return np.unique(np.linspace(0, length - 1, min(count, length), dtype=np.int64))


def _scan_transient(dataset: Any, chunk_rows: int, np: Any) -> dict[str, Any]:
    if dataset.ndim != 2 or dataset.dtype.kind not in "fc":
        raise DataGateError("transient signal must be a two-dimensional numeric dataset")
    rows, columns = (int(dataset.shape[0]), int(dataset.shape[1]))
    digest = hashlib.sha256()
    digest.update(_signature_prefix(dataset.dtype, dataset.shape, np))
    mask_digest = hashlib.sha256()
    finite = nan_count = inf_count = 0
    rows_any_nan = rows_all_nan = suffix_violations = nan_runs = 0
    position_nan = np.zeros(columns, dtype=np.int64)
    for start in range(0, rows, chunk_rows):
        stop = min(rows, start + chunk_rows)
        try:
            block = np.asarray(dataset[start:stop, :])
        except Exception as exc:
            raise DataGateError("failed while chunk-reading transient payload") from exc
        canonical = _normalised_numeric(block, dataset.dtype, np)
        digest.update(canonical.tobytes(order="C"))
        nan = np.isnan(block)
        inf = np.isinf(block)
        mask_digest.update(nan.astype(np.uint8, copy=False).tobytes(order="C"))
        finite += int(np.isfinite(block).sum())
        nan_count += int(nan.sum())
        inf_count += int(inf.sum())
        rows_any_nan += int(nan.any(axis=1).sum())
        rows_all_nan += int(nan.all(axis=1).sum())
        position_nan += nan.sum(axis=0, dtype=np.int64)
        if columns:
            nan_runs += int(nan[:, 0].sum())
            if columns > 1:
                nan_runs += int(((~nan[:, :-1]) & nan[:, 1:]).sum())
            after_nan = np.maximum.accumulate(nan, axis=1)
            suffix_violations += int((after_nan & ~nan).any(axis=1).sum())
    row_indices = _equidistant_indices(rows, 257, np)
    column_indices = _equidistant_indices(columns, 17, np)
    if row_indices.size and column_indices.size:
        sample = np.asarray(dataset[row_indices, :])[:, column_indices].reshape(-1, order="C")
    else:
        sample = np.asarray([], dtype=np.float64)
    return {
        "content_sha256": digest.hexdigest(),
        "nan_mask_sha256": mask_digest.hexdigest(),
        "element_count": rows * columns,
        "finite_count": finite,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "rows_any_nan": rows_any_nan,
        "rows_all_nan": rows_all_nan,
        "positions_any_nan": int((position_nan > 0).sum()),
        "positions_all_nan": int((position_nan == rows).sum()),
        "rowwise_nan_run_count": nan_runs,
        "finite_prefix_nan_suffix_violation_rows": suffix_violations,
        "sample": np.asarray(sample, dtype=np.float64),
        "sample_sha256": _sha_bytes(
            _normalised_numeric(np.asarray(sample, dtype=np.float64), np.dtype("<f8"), np).tobytes()
        ),
    }


def _time_audit(values: Any, np: Any) -> dict[str, Any]:
    flattened = np.asarray(values, dtype=np.float64).reshape(-1, order="C")
    finite = np.isfinite(flattened)
    diffs = np.diff(flattened) * 86400.0 if flattened.size > 1 else np.asarray([], dtype=np.float64)
    valid_diffs = diffs[np.isfinite(diffs)]
    tolerance = 1e-7
    reversal = int((valid_diffs < -tolerance).sum())
    duplicate = int((np.abs(valid_diffs) <= tolerance).sum())
    positive = valid_diffs[valid_diffs > tolerance]
    median_gap = float(np.median(positive)) if positive.size else 0.0
    gap_count = (
        int((~np.isclose(positive, median_gap, rtol=0, atol=1e-4)).sum())
        if positive.size
        else 0
    )
    return {
        "row_count": int(flattened.size),
        "finite_count": int(finite.sum()),
        "nan_count": int(np.isnan(flattened).sum()),
        "inf_count": int(np.isinf(flattened).sum()),
        "reversal_count": reversal,
        "duplicate_count": duplicate,
        "irregular_gap_count": gap_count,
        "median_positive_gap_seconds": median_gap,
        "minimum_gap_seconds": float(valid_diffs.min()) if valid_diffs.size else 0.0,
        "maximum_gap_seconds": float(valid_diffs.max()) if valid_diffs.size else 0.0,
    }


def _near_metrics(first: Any, second: Any, np: Any) -> tuple[int, float, float] | None:
    first = np.asarray(first, dtype=np.float64).reshape(-1)
    second = np.asarray(second, dtype=np.float64).reshape(-1)
    if first.size != second.size:
        return None
    mask = np.isfinite(first) & np.isfinite(second)
    overlap = int(mask.sum())
    if overlap < 64:
        return None
    x, y = first[mask], second[mask]
    x_centered, y_centered = x - x.mean(), y - y.mean()
    denominator = math.sqrt(float(np.dot(x_centered, x_centered) * np.dot(y_centered, y_centered)))
    if denominator == 0:
        return None
    correlation = float(np.dot(x_centered, y_centered) / denominator)
    pooled_rms = math.sqrt(float(np.mean((x * x + y * y) / 2.0)))
    nrmse = math.sqrt(float(np.mean((x - y) ** 2))) / max(pooled_rms, 1e-300)
    return overlap, correlation, nrmse


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "+Inf" if value > 0 else "-Inf" if value < 0 else "NaN"
        return format(value, ".17g")
    if isinstance(value, (dict, list, tuple)):
        return _json(value)
    return str(value)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(_json(value) + "\n", encoding="utf-8", newline="\n")


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _format_cell(row.get(column, "")) for column in columns})


def _source_manifest_rows(
    input_root: Path,
    integrity: Mapping[str, Any],
) -> tuple[list[Source], list[dict[str, Any]]]:
    if not input_root.is_dir() or input_root.is_symlink():
        raise DataGateError("input root must be a regular non-symlink directory")
    resolved_root = input_root.resolve(strict=True)
    target_rows = integrity.get("targets")
    if not isinstance(target_rows, list):
        raise DataGateError("integrity manifest lacks targets")
    by_target = {str(row.get("target")): row for row in target_rows if isinstance(row, dict)}
    if set(by_target) != set(TARGET_FILES):
        raise DataGateError("integrity manifest target set is not exactly ES10/ES12/ES14")
    sources: list[Source] = []
    verified: list[dict[str, Any]] = []
    for filename in TARGET_FILES:
        matches = sorted(input_root.rglob(filename), key=lambda item: item.as_posix())
        if len(matches) != 1:
            raise DataGateError(f"expected exactly one {filename}, found {len(matches)}")
        path = matches[0]
        if not path.is_file() or path.is_symlink():
            raise DataGateError(f"MAT input must be a regular non-symlink file: {filename}")
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise DataGateError(f"MAT input escapes input root: {filename}") from exc
        sha256, crc32, size = _sha_file(resolved)
        row = by_target[filename]
        expected_sha = row.get("input_sha256") or row.get("archive_member_streamed_sha256")
        expected_crc = row.get("input_crc32") or row.get("archive_member_crc32")
        expected_size = row.get("input_size_bytes") or row.get("archive_member_size_bytes")
        if sha256 != expected_sha or crc32.lower() != str(expected_crc).lower() or size != int(expected_size):
            raise DataGateError(f"{filename} does not match the required integrity manifest")
        sources.append(Source(filename[:-4], resolved, sha256, crc32, size))
        verified.append(
            {
                "source_name": filename,
                "sha256": sha256,
                "crc32": crc32,
                "size_bytes": size,
                "manifest_match": True,
            }
        )
    return sources, verified


def _verify_archive(archive_path: Path | None, integrity: Mapping[str, Any]) -> dict[str, Any]:
    archive = integrity.get("archive")
    if not isinstance(archive, dict):
        raise DataGateError("integrity manifest lacks archive evidence")
    required = ("sha256", "file_crc32", "size_bytes", "member_crc_status")
    if any(key not in archive for key in required):
        raise DataGateError("integrity manifest archive evidence is incomplete")
    if archive.get("member_crc_status") != "passed":
        raise DataGateError("integrity manifest does not attest passed ZIP member CRC")
    result = {
        "source_name": str(archive.get("archive_name", "archive.zip")),
        "sha256": str(archive["sha256"]),
        "crc32": str(archive["file_crc32"]),
        "size_bytes": int(archive["size_bytes"]),
        "verification_mode": "bound_prior_stream_and_crc_evidence",
        "manifest_match": True,
    }
    if archive_path is not None:
        if not archive_path.is_file() or archive_path.is_symlink():
            raise DataGateError("archive input must be a regular non-symlink file")
        sha256, crc32, size = _sha_file(archive_path)
        if (
            sha256 != result["sha256"]
            or crc32.lower() != result["crc32"].lower()
            or size != result["size_bytes"]
        ):
            raise DataGateError("archive bytes do not match the required integrity manifest")
        result.update(verification_mode="direct_bytes_reverified", sha256=sha256, crc32=crc32, size_bytes=size)
    return result


def _status_precedence(statuses: Iterable[str]) -> str:
    values = set(statuses)
    for status in ("FAIL", "BLOCKED", "AMBER", "PASS"):
        if status in values:
            return status
    return "BLOCKED"


def _required_count(contract: Mapping[str, Any], key: str, default: int = -1) -> int:
    value = contract.get("expected_counts", {}).get(key, default)
    return int(value)


def run_data_gate(
    input_root: Path | str,
    integrity_manifest_path: Path | str,
    output_dir: Path | str,
    *,
    contract_path: Path | str | None = None,
    amendment_path: Path | str | None = None,
    archive_path: Path | str | None = None,
    chunk_rows: int = 1024,
) -> dict[str, Any]:
    """Run the P1 Data Gate and atomically publish a new output directory."""

    if chunk_rows <= 0:
        raise DataGateError("chunk_rows must be positive")
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = Path(contract_path or repo_root / "refine-logs/BENCHMARK_L_DATA_GATE_PROTOCOL.json")
    amendment_path = Path(amendment_path or repo_root / "refine-logs/BENCHMARK_L_DATA_GATE_AMENDMENT.json")
    integrity_path = Path(integrity_manifest_path)
    input_path = Path(input_root)
    output_path = Path(output_dir)
    archive = None if archive_path is None else Path(archive_path)
    if output_path.exists() or output_path.is_symlink():
        raise DataGateError("output is append-only: the requested path must not already exist")

    contract, contract_sha = _read_json_file(contract_path, "base contract")
    amendment, amendment_sha = _read_json_file(amendment_path, "contract amendment")
    integrity, integrity_sha = _read_json_file(integrity_path, "integrity manifest")
    if amendment.get("parent_contract_sha256") != contract_sha:
        raise DataGateError("amendment is not bound to the supplied base contract")
    if contract.get("scope") != "reference_aware_parser_and_data_gate_only":
        raise DataGateError("base contract scope is not the frozen P1 scope")
    if amendment.get("frequency_row_contract", {}).get("preserve_all_raw_rows") is not True:
        raise DataGateError("amendment does not freeze preservation of all raw EIS rows")

    sources, source_rows = _source_manifest_rows(input_path, integrity)
    archive_row = _verify_archive(archive, integrity)
    h5py, np = _load_dependencies()

    linkage: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    frequency_rows: list[dict[str, Any]] = []
    alignment_rows: list[dict[str, Any]] = []
    missingness: list[dict[str, Any]] = []
    signatures: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    schema_tests: list[dict[str, Any]] = []
    content_internal: list[dict[str, Any]] = []
    timestamp_internal: dict[str, dict[str, Any]] = {}
    object_owners: dict[tuple[str, int], str] = {}
    ownership_conflicts = 0
    raw_order_nonchron = Counter()
    parsed_timestamp_count = 0
    acquisition_tie_count = 0
    event_slot_count = raw_slot_count = structural_empty_count = nonempty_count = quarantined_slot_count = 0
    nonempty_by_condition: Counter[str] = Counter()
    empty_by_condition: Counter[str] = Counter()

    for source in sources:
        with h5py.File(source.path, "r") as h5_file:
            root_path = f"/{source.condition}"
            _hard_object(h5_file, root_path, h5py, group=True)
            eis_root_path = f"{root_path}/EIS_Data"
            eis_root = _hard_object(h5_file, eis_root_path, h5py, group=True)
            reference_table = _hard_object(
                h5_file, f"{eis_root_path}/EIS_Reference_Table", h5py
            )
            if h5py.check_dtype(ref=reference_table.dtype) is None or reference_table.ndim != 2 or int(reference_table.shape[0]) != 4:
                raise DataGateError(f"invalid EIS Reference Table for {source.condition}")
            reference_tokens: list[list[str]] = []
            for row_index in range(4):
                row_tokens: list[str] = []
                for event_index in range(int(reference_table.shape[1])):
                    target, status = _resolve_ref(
                        h5_file,
                        reference_table[row_index, event_index],
                        h5py,
                        f"{source.condition}:reference_table:{row_index}:{event_index}",
                    )
                    if target is None or status != "resolved":
                        raise DataGateError("EIS Reference Table contains an empty reference")
                    decoded = _decode_char_columns(target, np, "EIS Reference Table target")
                    if len(decoded) != 1:
                        raise DataGateError("EIS Reference Table target is not a scalar string")
                    row_tokens.append(decoded[0])
                reference_tokens.append(row_tokens)

            unit_labels = sorted(
                (
                    name
                    for name in eis_root.keys()
                    if re.fullmatch(re.escape(source.condition) + r"C\d+", name)
                ),
                key=lambda name: int(name.split("C")[-1]),
            )
            for unit_label in unit_labels:
                measurement_path = f"{eis_root_path}/{unit_label}/EIS_Measurement"
                _hard_object(h5_file, f"{eis_root_path}/{unit_label}", h5py, group=True)
                _hard_object(h5_file, measurement_path, h5py, group=True)
                header_outer = _hard_object(h5_file, f"{measurement_path}/Header", h5py)
                data_outer = _hard_object(h5_file, f"{measurement_path}/Data", h5py)
                columns_outer = _hard_object(h5_file, f"{measurement_path}/ColumNames", h5py)
                for outer, field in ((header_outer, "Header"), (data_outer, "Data"), (columns_outer, "ColumNames")):
                    if h5py.check_dtype(ref=outer.dtype) is None or outer.ndim != 2 or int(outer.shape[1]) != 1:
                        raise DataGateError(f"invalid outer {field} reference array for {unit_label}")
                if header_outer.shape != data_outer.shape or header_outer.shape != columns_outer.shape:
                    raise DataGateError(f"outer Header/Data/ColumNames shape mismatch for {unit_label}")
                if int(header_outer.shape[0]) != int(reference_table.shape[1]):
                    raise DataGateError(f"event count differs from EIS Reference Table for {unit_label}")

                for event_index in range(int(header_outer.shape[0])):
                    event_slot_count += 1
                    column_target, column_ref_status = _resolve_ref(
                        h5_file,
                        columns_outer[event_index, 0],
                        h5py,
                        f"{source.condition}:{unit_label}:event:{event_index}:columns",
                    )
                    column_status = "failed"
                    column_hash = ""
                    if column_target is not None and column_ref_status == "resolved":
                        decoded_tokens = _decode_char_columns(column_target, np, "column names")
                        column_hash = _sha_bytes("\0".join(decoded_tokens).encode("utf-8"))
                        column_status = "passed" if _merge_column_tokens(decoded_tokens) is not None else "failed"
                    if column_status != "passed":
                        quarantine.append(
                            {
                                "scope_id": "eis_columns",
                                "condition": source.condition,
                                "provisional_unit": unit_label,
                                "event_index": event_index,
                                "raw_replicate_index": "",
                                "reason": "strict_20_to_18_column_mapping_failed",
                                "candidate_explanation": "",
                                "applied_repair": False,
                                "resolution": "quarantined_unresolved",
                            }
                        )

                    header_cell, header_outer_status = _resolve_ref(
                        h5_file,
                        header_outer[event_index, 0],
                        h5py,
                        f"{source.condition}:{unit_label}:event:{event_index}:Header",
                    )
                    data_cell, data_outer_status = _resolve_ref(
                        h5_file,
                        data_outer[event_index, 0],
                        h5py,
                        f"{source.condition}:{unit_label}:event:{event_index}:Data",
                    )
                    if header_cell is None or data_cell is None or header_outer_status != "resolved" or data_outer_status != "resolved":
                        raise DataGateError("outer Header/Data cell must resolve to a nonempty cell dataset")
                    header_refs = _reference_vector(header_cell, h5_file, h5py, "Header cell")
                    data_refs = _reference_vector(data_cell, h5_file, h5py, "Data cell")
                    inner_slots = max(len(header_refs), len(data_refs))
                    event_linkage_rows: list[dict[str, Any]] = []
                    valid_for_sort: list[tuple[datetime, int, dict[str, Any]]] = []
                    event_nonempty = event_empty = event_quarantine = 0
                    finish_candidates: list[datetime] = []
                    for raw_index in range(inner_slots):
                        raw_slot_count += 1
                        header_ref = header_refs[raw_index] if raw_index < len(header_refs) else None
                        data_ref = data_refs[raw_index] if raw_index < len(data_refs) else None
                        header_target, header_status = (
                            _resolve_ref(h5_file, header_ref, h5py, "inner Header")
                            if header_ref is not None
                            else (None, "missing_cell_position")
                        )
                        data_target, data_status = (
                            _resolve_ref(h5_file, data_ref, h5py, "inner Data")
                            if data_ref is not None
                            else (None, "missing_cell_position")
                        )
                        header_empty = header_status in {"canonical_empty", "null_empty_reference", "missing_cell_position"}
                        data_empty = data_status in {"canonical_empty", "null_empty_reference", "missing_cell_position"}
                        item_id = f"eis:{source.condition}:{unit_label}:e{event_index:03d}:r{raw_index:03d}"
                        row: dict[str, Any] = {
                            "item_id": item_id,
                            "source_sha256": source.sha256,
                            "condition": source.condition,
                            "provisional_unit": unit_label,
                            "event_index": event_index,
                            "raw_replicate_index": raw_index,
                            "header_reference_status": header_status,
                            "data_reference_status": data_status,
                            "pair_status": "",
                            "raw_slot_class": "",
                            "column_schema_status": column_status,
                            "header_sha256": "",
                            "matrix_content_sha256": "",
                            "acquisition_start": "",
                            "finish_candidate_inferred": "",
                            "finish_evidence": "",
                            "sorted_replicate_rank": "",
                            "eligibility": "",
                            "quarantine_reason": "",
                        }
                        if header_empty and data_empty:
                            structural_empty_count += 1
                            empty_by_condition[source.condition] += 1
                            event_empty += 1
                            row.update(
                                pair_status="paired_empty",
                                raw_slot_class="structural_empty",
                                eligibility="structural_empty",
                            )
                            event_linkage_rows.append(row)
                            continue
                        if header_empty != data_empty:
                            quarantined_slot_count += 1
                            event_quarantine += 1
                            row.update(
                                pair_status="asymmetric_empty",
                                raw_slot_class="quarantined",
                                eligibility="quarantined",
                                quarantine_reason="asymmetric_header_data_empty",
                            )
                            quarantine.append(
                                {
                                    "scope_id": "eis_references",
                                    "condition": source.condition,
                                    "provisional_unit": unit_label,
                                    "event_index": event_index,
                                    "raw_replicate_index": raw_index,
                                    "reason": "asymmetric_header_data_empty",
                                    "candidate_explanation": "",
                                    "applied_repair": False,
                                    "resolution": "quarantined_unresolved",
                                }
                            )
                            event_linkage_rows.append(row)
                            continue
                        assert header_target is not None and data_target is not None
                        if int(header_target.size) > MAX_CHAR_ELEMENTS:
                            raise DataGateError("header char matrix exceeds resource limit")
                        if data_target.ndim != 2 or int(data_target.size) > MAX_EIS_ELEMENTS or data_target.dtype.kind not in "fiu":
                            raise DataGateError("invalid or oversized EIS matrix")
                        address = int(h5py.h5o.get_info(data_target.id).addr)
                        owner_key = (source.sha256, address)
                        if owner_key in object_owners:
                            ownership_conflicts += 1
                        else:
                            object_owners[owner_key] = item_id
                        header_values = np.asarray(header_target[...])
                        header_sha = _array_signature(header_values, np)
                        header_lines = _decode_char_columns(header_target, np, "header")
                        parsed_header = _parse_header(header_lines)
                        raw_matrix = np.asarray(data_target[...])
                        canonical_matrix = np.asarray(raw_matrix.T, order="C")
                        matrix_sha = _array_signature(canonical_matrix, np)
                        numeric = _eis_numeric_audit(canonical_matrix, amendment, np)
                        counts = _finite_counts(canonical_matrix, np)
                        nonempty_count += 1
                        nonempty_by_condition[source.condition] += 1
                        event_nonempty += 1
                        acquisition = parsed_header.get("acquisition_start")
                        finish: datetime | None = None
                        if isinstance(acquisition, datetime) and canonical_matrix.shape[1] == 18:
                            time_values = np.asarray(canonical_matrix[:, 5], dtype=np.float64)
                            finite_time = time_values[np.isfinite(time_values)]
                            if finite_time.size:
                                finish = acquisition + timedelta(seconds=float(finite_time.max()))
                                finish_candidates.append(finish)
                        eligible = (
                            column_status == "passed"
                            and parsed_header.get("status") == "passed"
                            and numeric.get("status") == "passed"
                        )
                        if parsed_header.get("status") == "passed":
                            parsed_timestamp_count += 1
                        else:
                            quarantined_slot_count += 1
                            event_quarantine += 1
                        row.update(
                            pair_status="paired_nonempty",
                            raw_slot_class="eligible" if eligible else "quarantined",
                            header_sha256=header_sha,
                            matrix_content_sha256=matrix_sha,
                            acquisition_start=_iso(acquisition if isinstance(acquisition, datetime) else None),
                            finish_candidate_inferred=_iso(finish),
                            finish_evidence="inferred_start_plus_max_time_s" if finish else "unavailable",
                            eligibility="eligible" if eligible else "quarantined",
                            quarantine_reason="" if eligible else "header_schema_or_frequency_audit_failed",
                        )
                        if isinstance(acquisition, datetime):
                            valid_for_sort.append((acquisition, raw_index, row))
                        if not eligible:
                            quarantine.append(
                                {
                                    "scope_id": "eis_parser",
                                    "condition": source.condition,
                                    "provisional_unit": unit_label,
                                    "event_index": event_index,
                                    "raw_replicate_index": raw_index,
                                    "reason": row["quarantine_reason"],
                                    "candidate_explanation": "",
                                    "applied_repair": False,
                                    "resolution": "quarantined_unresolved",
                                }
                            )
                        frequency_rows.append(
                            {
                                "item_id": item_id,
                                "source_sha256": source.sha256,
                                "condition": source.condition,
                                "provisional_unit": unit_label,
                                "event_index": event_index,
                                "raw_replicate_index": raw_index,
                                "raw_shape": _json([int(v) for v in raw_matrix.shape]),
                                "canonical_shape": _json([int(v) for v in canonical_matrix.shape]),
                                "raw_token_count": len(EXPECTED_RAW_TOKENS) if column_status == "passed" else "",
                                "canonical_column_count": len(CANONICAL_COLUMNS) if column_status == "passed" else "",
                                "column_token_nul_sha256": column_hash,
                                "column_mapping_status": column_status,
                                "n_raw_rows": numeric.get("n_raw_rows", ""),
                                "n_preamble": numeric.get("n_preamble", ""),
                                "n_frequency": numeric.get("n_frequency", ""),
                                "invalid_frequency_count": numeric.get("invalid_frequency_count", ""),
                                "preamble_status": "passed" if numeric.get("checks", {}).get("preamble_contiguous_prefix") and numeric.get("checks", {}).get("preamble_length_allowed") else "failed",
                                "positive_sweep_status": "passed" if numeric.get("checks", {}).get("positive_sweep_rows_expected") and numeric.get("checks", {}).get("positive_sweep_strictly_decreasing") else "failed",
                                "positive_grid_sha256": numeric.get("positive_grid_sha256", ""),
                                "algebra_status": numeric.get("algebra_status", "failed"),
                                "algebra_max_scaled_error": numeric.get("algebra_max_scaled_error", ""),
                                "finite_count": counts["finite_count"],
                                "nan_count": counts["nan_count"],
                                "inf_count": counts["inf_count"],
                                "matrix_content_sha256": matrix_sha,
                                "status": numeric.get("status", "failed"),
                            }
                        )
                        missingness.append(
                            {
                                "item_id": item_id,
                                "modality": "eis_matrix",
                                "condition": source.condition,
                                "provisional_unit": unit_label,
                                "signal_kind": "",
                                "shape": _json([int(v) for v in canonical_matrix.shape]),
                                **counts,
                                "rows_any_nan": int(np.isnan(canonical_matrix).any(axis=1).sum()),
                                "rows_all_nan": int(np.isnan(canonical_matrix).all(axis=1).sum()),
                                "positions_any_nan": int(np.isnan(canonical_matrix).any(axis=0).sum()),
                                "positions_all_nan": int(np.isnan(canonical_matrix).all(axis=0).sum()),
                                "rowwise_nan_run_count": "",
                                "finite_prefix_nan_suffix_violation_rows": "",
                                "nan_mask_sha256": _sha_bytes(np.isnan(canonical_matrix).astype(np.uint8).tobytes(order="C")),
                                "content_sha256": matrix_sha,
                            }
                        )
                        sample_indices = _equidistant_indices(int(canonical_matrix.size), 64, np)
                        sample = np.asarray(canonical_matrix, dtype=np.float64).reshape(-1, order="C")[sample_indices]
                        entry = {
                            "item_id": item_id,
                            "content_type": "eis_matrix",
                            "condition": source.condition,
                            "provisional_unit": unit_label,
                            "event_index": event_index,
                            "sorted_replicate_rank": None,
                            "signal_kind": "",
                            "dtype": _canonical_dtype(canonical_matrix.dtype, np).str,
                            "shape": tuple(int(v) for v in canonical_matrix.shape),
                            "content_sha256": matrix_sha,
                            "sample": sample,
                            "sample_sha256": _sha_bytes(_normalised_numeric(sample, sample.dtype, np).tobytes()),
                        }
                        content_internal.append(entry)
                        signatures.append({key: value for key, value in entry.items() if key not in {"sample", "sorted_replicate_rank"}} | {"sorted_replicate_rank": ""})
                        row["_content_entry"] = entry
                        event_linkage_rows.append(row)

                    sorted_pairs = sorted(valid_for_sort, key=lambda item: (item[0], item[1]))
                    acquisition_tie_count += sum(
                        first[0] == second[0] for first, second in zip(sorted_pairs, sorted_pairs[1:])
                    )
                    raw_valid_order = [item[1] for item in valid_for_sort]
                    chronological_order = [item[1] for item in sorted_pairs]
                    raw_chronological = raw_valid_order == chronological_order
                    if not raw_chronological:
                        raw_order_nonchron[source.condition] += 1
                    for rank, (_, _, row) in enumerate(sorted_pairs):
                        row["sorted_replicate_rank"] = rank
                        entry = row.pop("_content_entry", None)
                        if entry is not None:
                            entry["sorted_replicate_rank"] = rank
                            for sig in reversed(signatures):
                                if sig["item_id"] == entry["item_id"]:
                                    sig["sorted_replicate_rank"] = rank
                                    break
                    for row in event_linkage_rows:
                        row.pop("_content_entry", None)
                    linkage.extend(event_linkage_rows)
                    events.append(
                        {
                            "source_sha256": source.sha256,
                            "condition": source.condition,
                            "provisional_unit": unit_label,
                            "event_index": event_index,
                            "calendar_date_raw": reference_tokens[0][event_index],
                            "start_clock_raw": reference_tokens[1][event_index],
                            "finish_clock_raw": reference_tokens[2][event_index],
                            "elapsed_like_raw": reference_tokens[3][event_index],
                            "raw_slot_count": inner_slots,
                            "eligible_nonempty_count": event_nonempty - event_quarantine,
                            "quarantined_count": event_quarantine,
                            "structural_empty_count": event_empty,
                            "nonempty_pair_count": event_nonempty,
                            "raw_order_chronological": raw_chronological,
                            "sorted_order_raw_indices": chronological_order,
                            "acquisition_tie_count": sum(first[0] == second[0] for first, second in zip(sorted_pairs, sorted_pairs[1:])),
                            "finish_candidate_inferred": _iso(max(finish_candidates) if finish_candidates else None),
                            "causal_availability_status": "BLOCKED",
                            "causal_availability_reason": "saved_finish_absent_start_plus_max_time_only_inferred",
                            "status": "passed" if event_quarantine == 0 else "failed",
                        }
                    )

            transient_root_path = f"{root_path}/Transient_Data"
            transient_root = _hard_object(h5_file, transient_root_path, h5py, group=True)
            serial_date = _hard_object(h5_file, f"{transient_root_path}/Serial_Date", h5py)
            if serial_date.ndim not in (1, 2) or serial_date.dtype.kind not in "fiu":
                raise DataGateError("invalid Serial_Date dataset")
            serial_values = np.asarray(serial_date[...])
            serial_signature = _array_signature(serial_values, np)
            time_stats = _time_audit(serial_values, np)
            timestamp_internal[source.condition] = {
                "values": np.asarray(serial_values, dtype=np.float64).reshape(-1),
                "hash": serial_signature,
                "stats": time_stats,
            }
            serial_item = f"transient-time:{source.condition}"
            signatures.append(
                {
                    "item_id": serial_item,
                    "content_type": "transient_timestamp",
                    "condition": source.condition,
                    "provisional_unit": "",
                    "event_index": "",
                    "sorted_replicate_rank": "",
                    "signal_kind": "Serial_Date",
                    "dtype": _canonical_dtype(serial_values.dtype, np).str,
                    "shape": tuple(int(v) for v in serial_values.shape),
                    "content_sha256": serial_signature,
                    "sample_sha256": "",
                }
            )
            content_internal.append(
                {
                    **signatures[-1],
                    "shape": tuple(int(v) for v in serial_values.shape),
                    "sample": np.asarray([], dtype=np.float64),
                }
            )
            missingness.append(
                {
                    "item_id": serial_item,
                    "modality": "transient_timestamp",
                    "condition": source.condition,
                    "provisional_unit": "",
                    "signal_kind": "Serial_Date",
                    "shape": _json([int(v) for v in serial_values.shape]),
                    **_finite_counts(serial_values, np),
                    "rows_any_nan": time_stats["nan_count"],
                    "rows_all_nan": time_stats["nan_count"],
                    "positions_any_nan": int(time_stats["nan_count"] > 0),
                    "positions_all_nan": int(time_stats["nan_count"] == int(serial_values.size) and serial_values.size > 0),
                    "rowwise_nan_run_count": "",
                    "finite_prefix_nan_suffix_violation_rows": "",
                    "nan_mask_sha256": _sha_bytes(np.isnan(serial_values).astype(np.uint8).tobytes(order="C")),
                    "content_sha256": serial_signature,
                }
            )

            transient_units = sorted(
                (
                    name
                    for name in transient_root.keys()
                    if re.fullmatch(re.escape(source.condition) + r"C\d+", name)
                ),
                key=lambda name: int(name.split("C")[-1]),
            )
            signal_rows_for_condition: list[int] = []
            for unit_label in transient_units:
                _hard_object(h5_file, f"{transient_root_path}/{unit_label}", h5py, group=True)
                for signal_kind in ("VL", "VO"):
                    signal = _hard_object(
                        h5_file, f"{transient_root_path}/{unit_label}/{signal_kind}", h5py
                    )
                    scan = _scan_transient(signal, chunk_rows, np)
                    signal_row_count = int(signal.shape[0])
                    signal_rows_for_condition.append(signal_row_count)
                    difference = int(serial_values.size) - signal_row_count
                    if difference == 0:
                        alignment_status = "PASS" if time_stats["reversal_count"] == 0 else "FAIL"
                        candidates: list[dict[str, Any]] = []
                    else:
                        alignment_status = "BLOCKED"
                        candidates = [
                            {
                                "hypothesis": "signals_map_timestamp_prefix",
                                "unpaired_timestamp_indices": list(range(signal_row_count, int(serial_values.size))),
                                "status": "candidate_only",
                            },
                            {
                                "hypothesis": "signals_map_timestamp_suffix",
                                "unpaired_timestamp_indices": list(range(max(0, difference))),
                                "status": "candidate_only",
                            },
                        ]
                    item_id = f"transient:{source.condition}:{unit_label}:{signal_kind}"
                    alignment_rows.append(
                        {
                            "item_id": item_id,
                            "condition": source.condition,
                            "provisional_unit": unit_label,
                            "signal_kind": signal_kind,
                            "timestamp_rows": int(serial_values.size),
                            "signal_rows": signal_row_count,
                            "row_difference": difference,
                            "timestamp_reversal_count": time_stats["reversal_count"],
                            "timestamp_duplicate_count": time_stats["duplicate_count"],
                            "timestamp_irregular_gap_count": time_stats["irregular_gap_count"],
                            "timestamp_content_sha256": serial_signature,
                            "candidate_explanations": candidates,
                            "applied_repair": False,
                            "alignment_status": alignment_status,
                        }
                    )
                    missingness.append(
                        {
                            "item_id": item_id,
                            "modality": "transient_signal",
                            "condition": source.condition,
                            "provisional_unit": unit_label,
                            "signal_kind": signal_kind,
                            "shape": _json([int(v) for v in signal.shape]),
                            "element_count": scan["element_count"],
                            "finite_count": scan["finite_count"],
                            "nan_count": scan["nan_count"],
                            "inf_count": scan["inf_count"],
                            "rows_any_nan": scan["rows_any_nan"],
                            "rows_all_nan": scan["rows_all_nan"],
                            "positions_any_nan": scan["positions_any_nan"],
                            "positions_all_nan": scan["positions_all_nan"],
                            "rowwise_nan_run_count": scan["rowwise_nan_run_count"],
                            "finite_prefix_nan_suffix_violation_rows": scan["finite_prefix_nan_suffix_violation_rows"],
                            "nan_mask_sha256": scan["nan_mask_sha256"],
                            "content_sha256": scan["content_sha256"],
                        }
                    )
                    entry = {
                        "item_id": item_id,
                        "content_type": "transient_signal",
                        "condition": source.condition,
                        "provisional_unit": unit_label,
                        "event_index": "",
                        "sorted_replicate_rank": "",
                        "signal_kind": signal_kind,
                        "dtype": _canonical_dtype(signal.dtype, np).str,
                        "shape": tuple(int(v) for v in signal.shape),
                        "content_sha256": scan["content_sha256"],
                        "sample": scan["sample"],
                        "sample_sha256": scan["sample_sha256"],
                    }
                    content_internal.append(entry)
                    signatures.append({key: value for key, value in entry.items() if key != "sample"})
                    if difference != 0:
                        quarantine.append(
                            {
                                "scope_id": "transient_time",
                                "condition": source.condition,
                                "provisional_unit": unit_label,
                                "event_index": "",
                                "raw_replicate_index": "",
                                "reason": "timestamp_signal_row_count_mismatch",
                                "candidate_explanation": candidates,
                                "applied_repair": False,
                                "resolution": "quarantined_unresolved",
                            }
                        )
            if time_stats["reversal_count"]:
                quarantine.append(
                    {
                        "scope_id": "transient_time",
                        "condition": source.condition,
                        "provisional_unit": "",
                        "event_index": "",
                        "raw_replicate_index": "",
                        "reason": "serial_date_time_reversal",
                        "candidate_explanation": {"reversal_count": time_stats["reversal_count"]},
                        "applied_repair": False,
                        "resolution": "quarantined_unresolved",
                    }
                )

            transient_unit_set = set(transient_units)
            for unit_label in unit_labels:
                has_transient = unit_label in transient_unit_set
                identities.append(
                    {
                        "condition": source.condition,
                        "provisional_unit": unit_label,
                        "provenance_only_group": True,
                        "eis_available": True,
                        "transient_available": has_transient,
                        "stable_physical_id_status": "BLOCKED",
                        "serial_evidence": "unknown",
                        "board_evidence": "unknown",
                        "batch_evidence": "unknown",
                        "replacement_reuse_evidence": "unknown",
                        "split_group_status": "BLOCKED",
                    }
                )
                targets.append(
                    {
                        "condition": source.condition,
                        "provisional_unit": unit_label,
                        "raw_observables": ["Cs/µF", "Cp/µF", "Re(Z)/Ohm"],
                        "capacity_target_status": "BLOCKED",
                        "esr_target_status": "BLOCKED",
                        "soh_target_status": "BLOCKED",
                        "rul_target_status": "BLOCKED",
                        "numeric_target_emitted": False,
                        "reason": "physical_derivation_baseline_aggregation_failure_rule_not_frozen",
                    }
                )
                outcomes.append(
                    {
                        "condition": source.condition,
                        "provisional_unit": unit_label,
                        "termination_reason": "unknown",
                        "failure_event": "unknown",
                        "censoring_status": "unknown",
                        "sequence_end_is_eol": False,
                        "outcome_status": "BLOCKED",
                    }
                )

    # Exact and frozen near-duplicate candidates.  Reference names and paths are
    # intentionally absent; IDs are provenance-only and forbidden as features.
    duplicate_rows: list[dict[str, Any]] = []
    exact_pairs: set[tuple[str, str]] = set()
    exact_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for entry in content_internal:
        exact_groups[(entry["content_type"], entry["dtype"], entry["shape"], entry["content_sha256"])].append(entry)
    for group in exact_groups.values():
        for first, second in itertools.combinations(sorted(group, key=lambda row: row["item_id"]), 2):
            pair = (first["item_id"], second["item_id"])
            exact_pairs.add(pair)
            duplicate_rows.append(
                {
                    "candidate_type": "exact_duplicate_candidate",
                    "item_id_a": pair[0],
                    "item_id_b": pair[1],
                    "content_type": first["content_type"],
                    "finite_overlap": "",
                    "pearson_r": "",
                    "pooled_rms_nrmse": 0.0,
                    "evidence": "canonical_content_signature_equal",
                    "resolution": "quarantined_unresolved",
                    "split_group_created": False,
                }
            )

    near_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for entry in content_internal:
        if entry["content_type"] == "eis_matrix":
            key = (
                "eis",
                entry["event_index"],
                entry["sorted_replicate_rank"],
                entry["shape"],
            )
        elif entry["content_type"] == "transient_signal":
            key = ("transient", entry["signal_kind"], entry["shape"])
        else:
            continue
        near_groups[key].append(entry)
    for group in near_groups.values():
        ordered = sorted(group, key=lambda row: row["item_id"])
        for first, second in itertools.combinations(ordered, 2):
            pair = (first["item_id"], second["item_id"])
            if pair in exact_pairs:
                continue
            metrics = _near_metrics(first["sample"], second["sample"], np)
            if metrics is None:
                continue
            overlap, correlation, nrmse = metrics
            if correlation >= 0.999999 and nrmse <= 1e-5:
                duplicate_rows.append(
                    {
                        "candidate_type": "near_duplicate_candidate",
                        "item_id_a": pair[0],
                        "item_id_b": pair[1],
                        "content_type": first["content_type"],
                        "finite_overlap": overlap,
                        "pearson_r": correlation,
                        "pooled_rms_nrmse": nrmse,
                        "evidence": "frozen_equidistant_sample_thresholds",
                        "resolution": "quarantined_unresolved",
                        "split_group_created": False,
                    }
                )

    expected = contract.get("expected_counts", {})
    expected_by_condition = {
        str(key): int(value) for key, value in expected.get("eis_nonempty_by_condition", {}).items()
    }
    expected_raw_slots = int(amendment.get("expected_raw_reference_slots", -1))
    expected_nonempty = int(amendment.get("expected_nonempty_matrix_pairs", expected.get("eis_nonempty_matrices", -1)))
    expected_empty = int(amendment.get("expected_paired_canonical_empties", -1))
    count_reconciled = raw_slot_count == (nonempty_count + structural_empty_count + sum(1 for row in linkage if row["pair_status"] == "asymmetric_empty"))
    # Ineligible nonempty matrices remain within nonempty_count and are also
    # quarantined; the mutually exclusive raw reconciliation uses raw_slot_class.
    raw_eligible = sum(row["raw_slot_class"] == "eligible" for row in linkage)
    raw_quarantined = sum(row["raw_slot_class"] == "quarantined" for row in linkage)
    exclusive_reconciliation = raw_slot_count == raw_eligible + raw_quarantined + structural_empty_count

    checks: list[tuple[str, bool, Any, Any]] = [
        ("source_count", len(sources) == 3, 3, len(sources)),
        ("event_slot_count", event_slot_count == int(expected.get("eis_event_slots", -1)), expected.get("eis_event_slots"), event_slot_count),
        ("raw_inner_slot_count", raw_slot_count == expected_raw_slots, expected_raw_slots, raw_slot_count),
        ("nonempty_matrix_pair_count", nonempty_count == expected_nonempty, expected_nonempty, nonempty_count),
        ("paired_canonical_empty_count", structural_empty_count == expected_empty, expected_empty, structural_empty_count),
        ("exclusive_raw_reconciliation", exclusive_reconciliation and count_reconciled, True, exclusive_reconciliation and count_reconciled),
        ("matrix_object_owned_once", ownership_conflicts == 0, 0, ownership_conflicts),
        ("all_nonempty_acquisition_starts_parsed", parsed_timestamp_count == nonempty_count, nonempty_count, parsed_timestamp_count),
        ("no_acquisition_time_ties", acquisition_tie_count == 0, 0, acquisition_tie_count),
        ("column_mapping_all", all(row["column_mapping_status"] == "passed" for row in frequency_rows), True, all(row["column_mapping_status"] == "passed" for row in frequency_rows)),
        ("frequency_contract_all", all(row["status"] == "passed" for row in frequency_rows), True, all(row["status"] == "passed" for row in frequency_rows)),
        ("eis_nonfinite_zero", all(int(row["nan_count"]) == 0 and int(row["inf_count"]) == 0 for row in frequency_rows), True, all(int(row["nan_count"]) == 0 and int(row["inf_count"]) == 0 for row in frequency_rows)),
    ]
    for condition, expected_count in sorted(expected_by_condition.items()):
        checks.append((f"nonempty_count_{condition}", nonempty_by_condition[condition] == expected_count, expected_count, nonempty_by_condition[condition]))
    if contract_sha == REAL_CONTRACT_SHA256 and amendment_sha == REAL_AMENDMENT_SHA256:
        checks.extend(
            [
                ("golden_column_token_hash", all(row["column_token_nul_sha256"] == REAL_TOKEN_NUL_SHA256 for row in frequency_rows), REAL_TOKEN_NUL_SHA256, sorted(set(row["column_token_nul_sha256"] for row in frequency_rows))),
                ("golden_positive_frequency_grid_hash", all(row["positive_grid_sha256"] == REAL_POSITIVE_GRID_SHA256 for row in frequency_rows), REAL_POSITIVE_GRID_SHA256, sorted(set(row["positive_grid_sha256"] for row in frequency_rows))),
            ]
        )
    for test_id, passed, expected_value, observed_value in checks:
        schema_tests.append(
            {
                "test_id": test_id,
                "status": "PASS" if passed else "FAIL",
                "expected": expected_value,
                "observed": observed_value,
            }
        )

    g00 = "PASS"
    g01 = "PASS" if all(row["status"] == "PASS" for row in schema_tests if row["test_id"] in {"event_slot_count", "raw_inner_slot_count", "nonempty_matrix_pair_count", "paired_canonical_empty_count", "exclusive_raw_reconciliation", "matrix_object_owned_once"} or row["test_id"].startswith("nonempty_count_")) else "FAIL"
    g02 = "PASS" if all(row["status"] == "PASS" for row in schema_tests if row["test_id"] in {"column_mapping_all", "frequency_contract_all", "eis_nonfinite_zero", "golden_column_token_hash", "golden_positive_frequency_grid_hash"}) else "FAIL"
    g03_eis = "PASS" if parsed_timestamp_count == nonempty_count and acquisition_tie_count == 0 else "FAIL"
    condition_alignment: dict[str, str] = {}
    for condition in CONDITIONS:
        rows = [row for row in alignment_rows if row["condition"] == condition]
        condition_alignment[condition] = _status_precedence(row["alignment_status"] for row in rows) if rows else "BLOCKED"
    g04 = "PASS" if all(
        int(row["inf_count"]) == 0
        and int(row["finite_prefix_nan_suffix_violation_rows"]) == 0
        for row in missingness
        if row["modality"] == "transient_signal"
    ) else "FAIL"
    g06 = "BLOCKED" if duplicate_rows else "PASS"

    eligibility = [
        {"gate_id": "G00", "scope_id": "source_bytes", "status": g00, "evidence": "MAT SHA/CRC/size/HDF5 open bound to required manifest", "unlocks": "integrity_only"},
        {"gate_id": "G01", "scope_id": "eis_references", "status": g01, "evidence": f"raw={raw_slot_count};eligible={raw_eligible};quarantined={raw_quarantined};structural_empty={structural_empty_count}", "unlocks": "parser_reference_layer_if_all_dependencies_pass"},
        {"gate_id": "G02", "scope_id": "eis_columns_frequency", "status": g02, "evidence": "strict 20-to-18 map; all 58/59 rows retained; 7/8 zero-frequency prefix plus 51-row sweep", "unlocks": "raw_eis_schema_if_all_dependencies_pass"},
        {"gate_id": "G03", "scope_id": "eis_acquisition_chronology", "status": g03_eis, "evidence": f"pair-before-sort; parsed={parsed_timestamp_count};ties={acquisition_tie_count};raw_nonchron={dict(sorted(raw_order_nonchron.items()))}", "unlocks": "chronological_eis_only"},
        {"gate_id": "G03", "scope_id": "eis_causal_availability", "status": "BLOCKED", "evidence": "Saved on is empty; finish is only inferred start+max(time/s)", "unlocks": "none"},
    ]
    for condition in CONDITIONS:
        eligibility.append(
            {"gate_id": "G03", "scope_id": f"transient_time_{condition}", "status": condition_alignment[condition], "evidence": "full Serial_Date chronology and exact row-count audit; no repair", "unlocks": "condition_transient_time_only_if_PASS"}
        )
    eligibility.extend(
        [
            {"gate_id": "G04", "scope_id": "transient_missingness", "status": g04, "evidence": "independent chunked content and NaN-mask geometry for every VL/VO", "unlocks": "missingness_audit_only"},
            {"gate_id": "G05", "scope_id": "physical_identity", "status": "BLOCKED", "evidence": "no stable serial/board/batch/replacement/reuse evidence", "unlocks": "none"},
            {"gate_id": "G06", "scope_id": "content_duplicates", "status": g06, "evidence": f"exact/near scan complete; unresolved_candidates={len(duplicate_rows)}", "unlocks": "no split group created"},
            {"gate_id": "G07", "scope_id": "capacity_target", "status": "BLOCKED", "evidence": "Cs/Cp are audited raw observables; no physical target rule frozen", "unlocks": "none"},
            {"gate_id": "G08", "scope_id": "esr_soh_target", "status": "BLOCKED", "evidence": "Re(Z) is not renamed ESR; no ESR fit/R0/SOH rule", "unlocks": "none"},
            {"gate_id": "G09", "scope_id": "outcome_rul", "status": "BLOCKED", "evidence": "termination/censor/EOL semantics absent; sequence end is not EOL", "unlocks": "none"},
            {"gate_id": "G10", "scope_id": "deterministic_reproduction", "status": "BLOCKED", "evidence": "single run sealed; independent second-run comparison required", "unlocks": "none"},
        ]
    )
    # These booleans are machine-readable decisions, not prose interpretations
    # of ``unlocks``.  P1 cannot release a parser because causal availability
    # and two-run invariance are unresolved; modeling and RUL are also outside
    # the user-approved scope regardless of an individual row's status.
    for row in eligibility:
        row.update(
            parser_release_eligible=False,
            modeling_eligible=False,
            rul_eligible=False,
            benchmark_l_modeling_eligible=False,
        )
    overall = _status_precedence(row["status"] for row in eligibility)

    # Explicit permanent quarantines/locks.
    for row in identities:
        quarantine.append(
            {
                "scope_id": "physical_identity",
                "condition": row["condition"],
                "provisional_unit": row["provisional_unit"],
                "event_index": "",
                "raw_replicate_index": "",
                "reason": "stable_physical_identity_unavailable",
                "candidate_explanation": "provisional label is provenance-only",
                "applied_repair": False,
                "resolution": "quarantined_unresolved",
            }
        )
    for row in duplicate_rows:
        quarantine.append(
            {
                "scope_id": "content_duplicates",
                "condition": "",
                "provisional_unit": "",
                "event_index": "",
                "raw_replicate_index": "",
                "reason": row["candidate_type"],
                "candidate_explanation": {"item_id_a": row["item_id_a"], "item_id_b": row["item_id_b"]},
                "applied_repair": False,
                "resolution": "quarantined_unresolved",
            }
        )

    contract_artifact = {
        "schema_version": SCHEMA_VERSION,
        "base_contract": {"sha256": contract_sha, "content": contract},
        "amendment": {"sha256": amendment_sha, "content": amendment},
        "effective_frequency_rule": amendment.get("frequency_row_contract"),
        "scope_lock": {
            "models": "BLOCKED_BY_USER_SCOPE",
            "model_evaluation": "BLOCKED_BY_USER_SCOPE",
            "rul_generation_or_scoring": "BLOCKED_BY_USER_SCOPE",
            "rul": "BLOCKED_BY_USER_SCOPE",
            "formal_design_gate": "BLOCKED_BY_USER_SCOPE",
            "freeze_b": "BLOCKED_BY_USER_SCOPE",
            "agent_topology": "BLOCKED_BY_USER_SCOPE",
        },
    }
    data_manifest = {
        "schema_version": SCHEMA_VERSION,
        "integrity_manifest_sha256": integrity_sha,
        "archive": archive_row,
        "sources": source_rows,
        "hdf5_open_status": "passed",
        "input_symlink_policy": "rejected",
        "external_storage_policy": "rejected",
        "virtual_dataset_policy": "rejected",
    }
    target_definitions = {
        "schema_version": SCHEMA_VERSION,
        "numeric_targets_emitted": [],
        "raw_observables_audited": ["Cs/µF", "Cp/µF", "Re(Z)/Ohm"],
        "raw_observable_semantics": {
            "Cs/µF": "raw_instrument_column_not_official_capacity_target",
            "Cp/µF": "raw_instrument_column_not_official_capacity_target",
            "Re(Z)/Ohm": "raw_impedance_component_not_ESR",
        },
        "capacity": {"status": "BLOCKED", "numeric_values_emitted": False},
        "ESR": {"status": "BLOCKED", "numeric_values_emitted": False},
        "SOH": {"status": "BLOCKED", "numeric_values_emitted": False},
        "RUL": {"status": "BLOCKED", "numeric_values_emitted": False},
        "failure_threshold": {"status": "BLOCKED"},
        "forbidden_feature_classes": contract.get("forbidden_feature_classes", []),
    }
    observed_counts = {
        "eis_event_slots": event_slot_count,
        "raw_inner_slots": raw_slot_count,
        "eligible_raw_slots": raw_eligible,
        "quarantined_raw_slots": raw_quarantined,
        "paired_canonical_empties": structural_empty_count,
        "nonempty_matrix_pairs": nonempty_count,
        "nonempty_by_condition": dict(sorted(nonempty_by_condition.items())),
        "empty_by_condition": dict(sorted(empty_by_condition.items())),
        "raw_order_nonchronological_unit_events": dict(sorted(raw_order_nonchron.items())),
        "eis_raw_shape_counts": dict(sorted(Counter(row["raw_shape"] for row in frequency_rows).items())),
        "eis_shape_counts": dict(sorted(Counter(row["canonical_shape"] for row in frequency_rows).items())),
        "eis_nonfinite_count": sum(int(row["nan_count"]) + int(row["inf_count"]) for row in frequency_rows),
        "exact_eis_matrix_duplicate_candidates": sum(
            row["candidate_type"] == "exact_duplicate_candidate"
            and row["content_type"] == "eis_matrix"
            for row in duplicate_rows
        ),
        "transient_signal_arrays": sum(row["content_type"] == "transient_signal" for row in signatures),
        "duplicate_candidates": len(duplicate_rows),
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "overall_status": overall,
        "counts": observed_counts,
        "observed_counts": observed_counts,
        "raw_reconciliation": {
            "formula": "raw=eligible+quarantined+structural_empty",
            "passed": exclusive_reconciliation,
        },
        "transient_time": {
            condition: {
                **timestamp_internal[condition]["stats"],
                "status": condition_alignment[condition],
                "content_sha256": timestamp_internal[condition]["hash"],
            }
            for condition in CONDITIONS
        },
        "cross_condition_timestamp_exact": {
            "ES12_equals_ES14": timestamp_internal["ES12"]["hash"] == timestamp_internal["ES14"]["hash"]
        },
        "gates": eligibility,
        "downstream": {
            "eis_parser_release": "BLOCKED",
            "transient_parser_release": "BLOCKED",
            "capacity_eval": "BLOCKED",
            "esr_soh_eval": "BLOCKED",
            "rul_survival_eval": "BLOCKED",
            "model_training": "BLOCKED_BY_USER_SCOPE",
            "model_evaluation": "BLOCKED_BY_USER_SCOPE",
            "rul_generation_or_scoring": "BLOCKED_BY_USER_SCOPE",
            "benchmark_l_modeling": "BLOCKED_BY_USER_SCOPE",
            "formal_design_gate": "BLOCKED_BY_USER_SCOPE",
            "freeze_b": "BLOCKED_BY_USER_SCOPE",
            "agent_topology_evaluation": "BLOCKED_BY_USER_SCOPE",
        },
    }

    columns = {
        "REFERENCE_LINKAGE_LEDGER.csv": (
            "item_id", "source_sha256", "condition", "provisional_unit", "event_index", "raw_replicate_index", "header_reference_status", "data_reference_status", "pair_status", "raw_slot_class", "column_schema_status", "header_sha256", "matrix_content_sha256", "acquisition_start", "finish_candidate_inferred", "finish_evidence", "sorted_replicate_rank", "eligibility", "quarantine_reason",
        ),
        "EIS_EVENT_LEDGER.csv": (
            "source_sha256", "condition", "provisional_unit", "event_index", "calendar_date_raw", "start_clock_raw", "finish_clock_raw", "elapsed_like_raw", "raw_slot_count", "eligible_nonempty_count", "quarantined_count", "structural_empty_count", "nonempty_pair_count", "raw_order_chronological", "sorted_order_raw_indices", "acquisition_tie_count", "finish_candidate_inferred", "causal_availability_status", "causal_availability_reason", "status",
        ),
        "COLUMN_FREQUENCY_LEDGER.csv": (
            "item_id", "source_sha256", "condition", "provisional_unit", "event_index", "raw_replicate_index", "raw_shape", "canonical_shape", "raw_token_count", "canonical_column_count", "column_token_nul_sha256", "column_mapping_status", "n_raw_rows", "n_preamble", "n_frequency", "invalid_frequency_count", "preamble_status", "positive_sweep_status", "positive_grid_sha256", "algebra_status", "algebra_max_scaled_error", "finite_count", "nan_count", "inf_count", "matrix_content_sha256", "status",
        ),
        "TRANSIENT_ALIGNMENT_LEDGER.csv": (
            "item_id", "condition", "provisional_unit", "signal_kind", "timestamp_rows", "signal_rows", "row_difference", "timestamp_reversal_count", "timestamp_duplicate_count", "timestamp_irregular_gap_count", "timestamp_content_sha256", "candidate_explanations", "applied_repair", "alignment_status",
        ),
        "MISSINGNESS_LEDGER.csv": (
            "item_id", "modality", "condition", "provisional_unit", "signal_kind", "shape", "element_count", "finite_count", "nan_count", "inf_count", "rows_any_nan", "rows_all_nan", "positions_any_nan", "positions_all_nan", "rowwise_nan_run_count", "finite_prefix_nan_suffix_violation_rows", "nan_mask_sha256", "content_sha256",
        ),
        "UNIT_IDENTITY_LEDGER.csv": tuple(identities[0].keys()) if identities else ("condition",),
        "CONTENT_SIGNATURE_LEDGER.csv": (
            "item_id", "content_type", "condition", "provisional_unit", "event_index", "sorted_replicate_rank", "signal_kind", "dtype", "shape", "content_sha256", "sample_sha256",
        ),
        "DUPLICATE_CANDIDATE_LEDGER.csv": (
            "candidate_type", "item_id_a", "item_id_b", "content_type", "finite_overlap", "pearson_r", "pooled_rms_nrmse", "evidence", "resolution", "split_group_created",
        ),
        "REPAIR_QUARANTINE_LEDGER.csv": (
            "scope_id", "condition", "provisional_unit", "event_index", "raw_replicate_index", "reason", "candidate_explanation", "applied_repair", "resolution",
        ),
        "TARGET_TRAJECTORY_LEDGER.csv": tuple(targets[0].keys()) if targets else ("condition",),
        "OUTCOME_LEDGER.csv": tuple(outcomes[0].keys()) if outcomes else ("condition",),
        "ELIGIBILITY_MATRIX.csv": (
            "gate_id", "scope_id", "status", "evidence", "unlocks",
            "parser_release_eligible", "modeling_eligible", "rul_eligible",
            "benchmark_l_modeling_eligible",
        ),
    }
    csv_rows: dict[str, list[dict[str, Any]]] = {
        "REFERENCE_LINKAGE_LEDGER.csv": linkage,
        "EIS_EVENT_LEDGER.csv": events,
        "COLUMN_FREQUENCY_LEDGER.csv": frequency_rows,
        "TRANSIENT_ALIGNMENT_LEDGER.csv": alignment_rows,
        "MISSINGNESS_LEDGER.csv": missingness,
        "UNIT_IDENTITY_LEDGER.csv": identities,
        "CONTENT_SIGNATURE_LEDGER.csv": signatures,
        "DUPLICATE_CANDIDATE_LEDGER.csv": duplicate_rows,
        "REPAIR_QUARANTINE_LEDGER.csv": quarantine,
        "TARGET_TRAJECTORY_LEDGER.csv": targets,
        "OUTCOME_LEDGER.csv": outcomes,
        "ELIGIBILITY_MATRIX.csv": eligibility,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_path.name}.tmp-", dir=output_path.parent))
    try:
        _write_json(staging / "DATA_GATE_CONTRACT.json", contract_artifact)
        _write_json(staging / "DATA_MANIFEST.json", data_manifest)
        _write_json(staging / "TARGET_DEFINITIONS.json", target_definitions)
        _write_json(staging / "SCHEMA_TEST_RESULTS.json", {"schema_version": SCHEMA_VERSION, "tests": schema_tests})
        _write_json(staging / "DATA_GATE_SUMMARY.json", summary)
        for filename in REQUIRED_CSV:
            _write_csv(staging / filename, columns[filename], csv_rows[filename])
        report_lines = [
            "# Benchmark-L P1 Data Gate Report",
            "",
            f"- Overall: `{overall}`",
            f"- EIS events: {event_slot_count}",
            f"- Raw inner slots: {raw_slot_count} = {raw_eligible} eligible + {raw_quarantined} quarantined + {structural_empty_count} structural empty",
            f"- Nonempty matrices: {nonempty_count}",
            f"- Raw-order nonchronological unit-events: {_json(dict(sorted(raw_order_nonchron.items()))) }",
            f"- Transient time: {_json(condition_alignment)}",
            f"- Duplicate candidates: {len(duplicate_rows)}; every candidate remains unresolved and creates no split group.",
            "",
            "All 58/59 EIS rows are retained. Zero-frequency acquisition preambles are classified, not removed. Header/Data were paired by raw replicate index before stable acquisition-time sorting.",
            "",
            "`finish_candidate_inferred` is start plus maximum raw `time/s`; it is not a measured save/finish time. Causal availability therefore remains BLOCKED.",
            "",
            "ES12 timestamp/signal candidates are reported without trimming, interpolation, sorting, or applied repair. Sequence end is not treated as EOL.",
            "",
            "No capacity, ESR, SOH, or RUL numeric target and no model result is emitted in P1.",
            "",
        ]
        (staging / "DATA_GATE_REPORT.md").write_text("\n".join(report_lines), encoding="utf-8", newline="\n")

        scientific_names = sorted(
            [name for name in REQUIRED_JSON if name not in {"ARTIFACT_MANIFEST.json", "COMPLETE.json"}]
            + list(REQUIRED_CSV)
            + ["DATA_GATE_REPORT.md"]
        )
        artifact_rows = []
        for name in scientific_names:
            raw = (staging / name).read_bytes()
            artifact_row = {"name": name, "sha256": _sha_bytes(raw), "size_bytes": len(raw)}
            if name in columns:
                artifact_row.update(columns=list(columns[name]), row_count=len(csv_rows[name]))
            artifact_rows.append(artifact_row)
        code_sha = _sha_file(Path(__file__))[0]
        artifact_manifest = {
            "schema_version": SCHEMA_VERSION,
            "code_sha256": code_sha,
            "contract_sha256": contract_sha,
            "amendment_sha256": amendment_sha,
            "integrity_manifest_sha256": integrity_sha,
            "stable_artifacts": artifact_rows,
        }
        _write_json(staging / "ARTIFACT_MANIFEST.json", artifact_manifest)
        hash_names = scientific_names + ["ARTIFACT_MANIFEST.json"]
        hash_lines = [f"{_sha_file(staging / name)[0]}  {name}" for name in sorted(hash_names)]
        (staging / "ARTIFACT_HASHES.sha256").write_text("\n".join(hash_lines) + "\n", encoding="utf-8", newline="\n")
        complete = {
            "schema_version": SCHEMA_VERSION,
            "status": "COMPLETE",
            "overall_data_gate_status": overall,
            "artifact_manifest_sha256": _sha_file(staging / "ARTIFACT_MANIFEST.json")[0],
            "artifact_hashes_sha256": _sha_file(staging / "ARTIFACT_HASHES.sha256")[0],
            "contract_sha256": contract_sha,
            "amendment_sha256": amendment_sha,
            "integrity_manifest_sha256": integrity_sha,
            "code_sha256": code_sha,
            "required_artifacts": sorted(list(REQUIRED_JSON) + list(REQUIRED_CSV) + ["DATA_GATE_REPORT.md", "ARTIFACT_HASHES.sha256"]),
            "downstream_scope": "BLOCKED_BY_USER_SCOPE",
        }
        _write_json(staging / "COMPLETE.json", complete)
        missing = [name for name in complete["required_artifacts"] if not (staging / name).is_file()]
        if missing:
            raise DataGateError(f"required artifacts missing before publish: {missing}")
        staging.rename(output_path)
    except Exception:
        if staging.exists() and staging.name.startswith(f".{output_path.name}.tmp-"):
            shutil.rmtree(staging)
        raise
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the frozen Benchmark-L P1 parser and Data Gate")
    parser.add_argument("--input", required=True, type=Path, help="root containing exactly ES10/12/14 MAT files")
    parser.add_argument("--integrity-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new append-only output directory")
    parser.add_argument("--contract", type=Path, default=None)
    parser.add_argument("--amendment", type=Path, default=None)
    parser.add_argument("--archive", type=Path, default=None, help="optional direct ZIP byte reverification")
    parser.add_argument("--chunk-rows", type=int, default=1024)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = run_data_gate(
        args.input,
        args.integrity_manifest,
        args.output,
        contract_path=args.contract,
        amendment_path=args.amendment,
        archive_path=args.archive,
        chunk_rows=args.chunk_rows,
    )
    print(_json({"output": args.output.name, "overall_status": summary["overall_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
