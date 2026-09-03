#!/usr/bin/env python3
"""P1-only static Data Gate for the Patrizi HSC Figshare payload.

The scope of this module is deliberately narrow: it verifies the frozen MAT/PDF
bytes and audits aggregate properties of numeric arrays loaded from the single
``HSC`` variable.  MATLAB MCOS objects (Time, Method, duration, and EIS tables)
are never decoded or executed.  This module does not construct SOH or RUL,
does not train/evaluate a model, and does not call any network or model API.

The output is an append-only, timestamped evidence bundle containing aggregate
counts, extrema, and hashes only.  It never writes raw rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = "audit-cap.patrizi-hsc-p1-data-gate.v1"
LOCAL_MANIFEST_SCHEMA_VERSION = "audit-cap.patrizi-hsc-local-raw-manifest.v1"
SOURCE_ID = "patrizi_hsc_figshare_29153561_v2"
DOI = "10.6084/m9.figshare.29153561.v2"
LICENCE = "CC BY 4.0"


@dataclass(frozen=True)
class ExpectedPayload:
    item_id: str
    filename: str
    direct_url: str
    expected_bytes: int
    published_md5: str
    expected_sha256: str


EXPECTED_PAYLOADS: tuple[ExpectedPayload, ...] = (
    ExpectedPayload(
        item_id="figshare_file_54852761",
        filename="Dataset_HSC.mat",
        direct_url="https://ndownloader.figshare.com/files/54852761",
        expected_bytes=225_986_697,
        published_md5="57e71c60cbae63142db44559edfa8ae0",
        expected_sha256="bf9f5c4889ddaa739d04980b97eb37ed3e4990473d376ca9cd928324e5d8e9cb",
    ),
    ExpectedPayload(
        item_id="figshare_file_55269047",
        filename="HSC_dataset_info.pdf",
        direct_url="https://ndownloader.figshare.com/files/55269047",
        expected_bytes=397_625,
        published_md5="0189a89a72c73080cece2104ba834bce",
        expected_sha256="7d6c7895891b85721f051eaf92b84f8669efd92475d58ee80ad529e1751b62f1",
    ),
)

TOP_FIELDS = ("complete", "summary", "EIS", "info")
CHANNELS = tuple(f"ch{index}" for index in range(1, 9))
COMPLETE_FIELDS = (
    "Time",
    "Cycle",
    "Current",
    "Voltage",
    "Cap_ch",
    "Cap_dis",
    "IR",
    "Temp",
    "Method",
)
COMPLETE_NUMERIC_FIELDS = (
    "Cycle",
    "Current",
    "Voltage",
    "Cap_ch",
    "Cap_dis",
    "IR",
    "Temp",
)
SUMMARY_FIELDS = (
    "Cycle",
    "Cap_ch",
    "Cap_dis",
    "IR",
    "MaxTemp",
    "MinTemp",
    "AvgTemp",
    "ChargeTime",
    "DischargeTime",
    "Method",
)
SUMMARY_NUMERIC_FIELDS = (
    "Cycle",
    "Cap_ch",
    "Cap_dis",
    "IR",
    "MaxTemp",
    "MinTemp",
    "AvgTemp",
)
INFO_FIELDS = ("Environment", "Frequency", "Setpoints", "Test_date")

UNITS: Mapping[str, str] = {
    "Cycle": "cycle_index",
    "Current": "A",
    "Voltage": "V",
    "Cap_ch": "Ah",
    "Cap_dis": "Ah",
    "IR": "ohm_internal_resistance_not_ESR",
    "Temp": "degC",
    "MaxTemp": "degC",
    "MinTemp": "degC",
    "AvgTemp": "degC",
    "Time": "datetime_unavailable_opaque",
    "ChargeTime": "duration_unavailable_opaque",
    "DischargeTime": "duration_unavailable_opaque",
    "Method": "string_unavailable_opaque",
}

# These observations are tied to the pinned information-PDF SHA-256 above.
# They are documentation audit facts, not substitutes for raw-row evidence.
PINNED_PDF_CONFLICTS: tuple[Mapping[str, str], ...] = (
    {
        "conflict_id": "PDF_TOP_FIELD_COUNT",
        "scope": "HSC",
        "raw_observation": "four top-level fields: complete, summary, EIS, info",
        "documentation_observation": "dataset-structure prose calls HSC a struct with three fields",
        "status": "BLOCKED_DOCUMENTATION_CONFLICT",
    },
    {
        "conflict_id": "PDF_CYCLE_DTYPE",
        "scope": "complete.*.Cycle;summary.*.Cycle",
        "raw_observation": "uint16",
        "documentation_observation": "Cycle is described as a double array",
        "status": "BLOCKED_DOCUMENTATION_CONFLICT",
    },
    {
        "conflict_id": "PDF_CHARGE_TIME_DESCRIPTION",
        "scope": "summary.*.ChargeTime",
        "raw_observation": "MATLAB MCOS duration object; deliberately not decoded",
        "documentation_observation": "called duration but described as discharge capacity [Ah]",
        "status": "BLOCKED_DOCUMENTATION_CONFLICT",
    },
    {
        "conflict_id": "PDF_DISCHARGE_TIME_DESCRIPTION",
        "scope": "summary.*.DischargeTime",
        "raw_observation": "MATLAB MCOS duration object; deliberately not decoded",
        "documentation_observation": "called duration but described as internal resistance [ohm]",
        "status": "BLOCKED_DOCUMENTATION_CONFLICT",
    },
)

REQUIRED_OUTPUTS = (
    "ACQUISITION_MANIFEST.json",
    "RAW_HASH_LEDGER.csv",
    "CONTAINER_INSPECTION.json",
    "UNIT_IDENTITY_LEDGER.csv",
    "SCHEMA_UNIT_LEDGER.csv",
    "CHRONOLOGY_LEDGER.csv",
    "DUPLICATE_OVERLAP_LEDGER.csv",
    "TARGET_ELIGIBILITY.csv",
    "EVENT_CENSOR_LEDGER.csv",
    "SPLIT_LEAKAGE_LEDGER.json",
    "DATA_GATE_SUMMARY.json",
    "DATA_GATE_REPORT.md",
    "ARTIFACT_MANIFEST.json",
    "ARTIFACT_HASHES.sha256",
    "COMPLETE.json",
)
ARTIFACT_INTEGRITY_SCHEMA_VERSION = "audit-cap.non-circular-artifact-integrity.v1"
ARTIFACT_GRAPH_WRITE_ORDER = (
    "COMPLETE.json",
    "ARTIFACT_MANIFEST.json",
    "ARTIFACT_HASHES.sha256",
)


class PatriziDataGateError(RuntimeError):
    """Raised for an unsafe input or a violated frozen byte/parser contract."""


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_digests(path: Path, block_bytes: int = 8 * 1024 * 1024) -> dict[str, Any]:
    _require_regular_file(path, "payload")
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(block_bytes), b""):
            size += len(block)
            md5.update(block)
            sha256.update(block)
    return {"bytes": size, "md5": md5.hexdigest(), "sha256": sha256.hexdigest()}


def _require_regular_file(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise PatriziDataGateError(f"missing {label}: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PatriziDataGateError(f"{label} must be a regular non-symlink file: {path}")


def _require_plain_directory(path: Path, label: str, *, create: bool = False) -> None:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise PatriziDataGateError(f"missing {label}: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise PatriziDataGateError(f"{label} must be a real non-symlink directory: {path}")


def _sanitize_url(value: str) -> str:
    """Return scheme/host/path only; credentials, query, and fragment are dropped."""

    parsed = urlsplit(value.strip())
    host = parsed.hostname or ""
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme.lower(), host.lower(), parsed.path, "", ""))


def _parse_sanitized_header_evidence(header_dir: Path | None) -> list[dict[str, Any]]:
    if header_dir is None or not header_dir.is_dir() or header_dir.is_symlink():
        return []
    allowed = {
        "Dataset_HSC.mat.headers.partial": "Dataset_HSC.mat",
        "Dataset_HSC.mat.headers.retry1.partial": "Dataset_HSC.mat",
        "information.pdf.headers.partial": "HSC_dataset_info.pdf",
    }
    records: list[dict[str, Any]] = []
    for name, payload in allowed.items():
        path = header_dir / name
        if not path.is_file() or path.is_symlink():
            continue
        status_lines: list[str] = []
        final_path = "NA"
        content_lengths: list[str] = []
        content_ranges: list[str] = []
        last_modified: list[str] = []
        etags: list[str] = []
        content_types: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            lowered = stripped.lower()
            if stripped.startswith("HTTP/"):
                # Proxy CONNECT status is recorded as transport metadata, not as
                # the origin server's payload response.
                status_lines.append(" ".join(stripped.split()[:3]))
            elif lowered.startswith("location:"):
                final_path = _sanitize_url(stripped.split(":", 1)[1].strip())
            elif lowered.startswith("content-length:"):
                content_lengths.append(stripped.split(":", 1)[1].strip())
            elif lowered.startswith("content-range:"):
                content_ranges.append(stripped.split(":", 1)[1].strip())
            elif lowered.startswith("last-modified:"):
                last_modified.append(stripped.split(":", 1)[1].strip())
            elif lowered.startswith("etag:"):
                etags.append(stripped.split(":", 1)[1].strip().strip('"'))
            elif lowered.startswith("content-type:"):
                content_types.append(stripped.split(":", 1)[1].strip())
        records.append(
            {
                "payload": payload,
                "log_role": "initial" if "retry" not in name else "range_resume",
                "http_status_lines": status_lines,
                "redirect_effective_scheme_host_path": final_path,
                "content_lengths": content_lengths,
                "content_ranges": content_ranges,
                "last_modified": last_modified,
                "etags": etags,
                "content_types": content_types,
                "raw_header_log_sha256": _file_digests(path)["sha256"],
                "query_and_fragment_persisted": False,
            }
        )
    return records


def _curl_version() -> str:
    try:
        completed = subprocess.run(
            ["curl", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"
    first_line = completed.stdout.splitlines()[0] if completed.stdout else "UNAVAILABLE"
    return first_line[:500]


def _available_memory_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _dependency_versions() -> dict[str, str]:
    try:
        import numpy as np  # type: ignore
        import scipy  # type: ignore
    except ImportError as exc:
        raise PatriziDataGateError("numpy and scipy are required for the static MAT audit") from exc
    return {"python": os.sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__}


def _verify_payload(path: Path, expected: ExpectedPayload) -> dict[str, Any]:
    observed = _file_digests(path)
    mismatches: list[str] = []
    if observed["bytes"] != expected.expected_bytes:
        mismatches.append("bytes")
    if observed["md5"] != expected.published_md5:
        mismatches.append("published_md5")
    if observed["sha256"] != expected.expected_sha256:
        mismatches.append("project_sha256")
    if mismatches:
        raise PatriziDataGateError(
            f"frozen payload mismatch for {expected.filename}: {','.join(mismatches)}"
        )
    return {
        "item_id": expected.item_id,
        "filename": expected.filename,
        "direct_url": expected.direct_url,
        "expected_bytes": expected.expected_bytes,
        "observed_bytes": observed["bytes"],
        "published_md5": expected.published_md5,
        "observed_md5": observed["md5"],
        "project_sha256": observed["sha256"],
        "status": "PASS_EXACT_BYTES_MD5_SHA256",
    }


def _fieldnames(value: Any, context: str) -> tuple[str, ...]:
    fields = getattr(value, "_fieldnames", None)
    if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
        raise PatriziDataGateError(f"expected MATLAB struct at {context}")
    return tuple(fields)


def _require_exact_fields(value: Any, expected: Sequence[str], context: str) -> None:
    observed = _fieldnames(value, context)
    if observed != tuple(expected):
        raise PatriziDataGateError(
            f"unexpected field order/schema at {context}: observed={observed}, expected={tuple(expected)}"
        )


def _array_content_sha256(array: Any) -> str:
    import numpy as np  # type: ignore

    values = np.asarray(array)
    if not values.flags.c_contiguous:
        values = np.ascontiguousarray(values)
    digest = hashlib.sha256()
    digest.update(str(values.dtype).encode("ascii"))
    digest.update(b"\0")
    digest.update(json.dumps(list(values.shape), separators=(",", ":")).encode("ascii"))
    digest.update(b"\0")
    digest.update(memoryview(values).cast("B"))
    return digest.hexdigest()


def _safe_number(value: Any) -> int | float | str:
    number = value.item() if hasattr(value, "item") else value
    if isinstance(number, bool):
        return int(number)
    if isinstance(number, int):
        return number
    numeric = float(number)
    if not math.isfinite(numeric):
        return "NA_NONFINITE"
    return numeric


def _audit_numeric_array(
    array: Any,
    *,
    scope: str,
    channel: str,
    field: str,
    granularity: str,
) -> dict[str, Any]:
    import numpy as np  # type: ignore

    values = np.asarray(array)
    if values.ndim != 1 or values.dtype.kind not in "iuf":
        raise PatriziDataGateError(
            f"numeric field must be a one-dimensional real array at HSC.{scope}.{channel}.{field}"
        )
    finite = np.isfinite(values)
    finite_count = int(finite.sum())
    nan_count = int(np.isnan(values).sum()) if values.dtype.kind == "f" else 0
    inf_count = int(np.isinf(values).sum()) if values.dtype.kind == "f" else 0
    if finite_count:
        finite_values = values[finite]
        minimum: int | float | str = _safe_number(np.min(finite_values))
        maximum: int | float | str = _safe_number(np.max(finite_values))
    else:
        minimum = "NA_NO_FINITE_VALUES"
        maximum = "NA_NO_FINITE_VALUES"
    row_status = "OBSERVED_NUMERIC"
    reason = "raw numeric array statically audited"
    if field == "Cycle" and values.dtype != np.dtype("uint16"):
        row_status = "BLOCKED_UNEXPECTED_RAW_DTYPE"
        reason = "frozen raw audit observed Cycle as uint16"
    elif field == "Cycle":
        row_status = "OBSERVED_NUMERIC_DOCUMENTATION_CONFLICT"
        reason = "raw uint16 conflicts with pinned PDF description of double"
    return {
        "scope": scope,
        "provisional_trajectory": channel,
        "field": field,
        "parser_class": type(array).__name__,
        "dtype": str(values.dtype),
        "shape": json.dumps(list(values.shape), separators=(",", ":")),
        "element_count": int(values.size),
        "finite_count": finite_count,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "minimum": minimum,
        "maximum": maximum,
        "unit": UNITS[field],
        "unit_evidence": "pinned_information_pdf_subject_to_documentation_conflicts",
        "sampling_granularity": granularity,
        "provenance_class": "native_raw_numeric" if scope == "complete" else "author_summary_numeric",
        "content_sha256": _array_content_sha256(values),
        "status": row_status,
        "reason": reason,
    }


def _audit_unavailable_object(
    value: Any,
    *,
    scope: str,
    channel: str,
    field: str,
    granularity: str,
) -> dict[str, Any]:
    shape = getattr(value, "shape", None)
    dtype = getattr(value, "dtype", None)
    return {
        "scope": scope,
        "provisional_trajectory": channel,
        "field": field,
        "parser_class": type(value).__name__,
        "dtype": str(dtype) if dtype is not None else "NA_OPAQUE",
        "shape": json.dumps(list(shape), separators=(",", ":")) if shape is not None else "NA_OPAQUE",
        "element_count": "NA_NOT_DECODED",
        "finite_count": "NA_NOT_DECODED",
        "nan_count": "NA_NOT_DECODED",
        "inf_count": "NA_NOT_DECODED",
        "minimum": "NA_NOT_DECODED",
        "maximum": "NA_NOT_DECODED",
        "unit": UNITS[field],
        "unit_evidence": "pinned_information_pdf_only",
        "sampling_granularity": granularity,
        "provenance_class": "MATLAB_MCOS_or_object_not_decoded",
        "content_sha256": "NA_NOT_READ",
        "status": "BLOCKED_STATIC_OPAQUE",
        "reason": "author workspace/class code forbidden; no MCOS object decoding",
    }


def _cycle_audit(array: Any, *, scope: str, channel: str) -> dict[str, Any]:
    import numpy as np  # type: ignore

    values = np.asarray(array)
    if values.ndim != 1 or values.dtype.kind not in "iu":
        raise PatriziDataGateError(f"Cycle must be a 1-D integer array at HSC.{scope}.{channel}")
    signed = values.astype(np.int64, copy=False)
    differences = np.diff(signed)
    distinct = np.unique(signed)
    minimum = int(distinct[0]) if distinct.size else None
    maximum = int(distinct[-1]) if distinct.size else None
    missing: list[int] = []
    if distinct.size:
        expected = np.arange(minimum, maximum + 1, dtype=np.int64)
        missing = [int(item) for item in np.setdiff1d(expected, distinct, assume_unique=True)]
    reversals = int((differences < 0).sum())
    jumps = int((differences > 1).sum())
    chronology_status = (
        "PARTIAL_PASS_CYCLE_AXIS_ONLY"
        if reversals == 0
        else "BLOCKED_CYCLE_REVERSAL"
    )
    return {
        "scope": scope,
        "provisional_trajectory": channel,
        "row_count": int(values.size),
        "cycle_min": minimum if minimum is not None else "NA_EMPTY",
        "cycle_max": maximum if maximum is not None else "NA_EMPTY",
        "distinct_cycle_count": int(distinct.size),
        "adjacent_repeat_count": int((differences == 0).sum()),
        "reversal_count": reversals,
        "forward_jump_gt_one_count": jumps,
        "missing_cycle_count_within_observed_range": len(missing),
        "missing_cycles_within_observed_range": ";".join(map(str, missing)) if missing else "NONE",
        "cycle_axis_status": chronology_status,
        "absolute_time_status": "BLOCKED_STATIC_OPAQUE",
        "segment_identity_status": "BLOCKED_NO_AUDITABLE_ABSOLUTE_TIME_OR_RESET_ID",
        "terminal_record_status": "BLOCKED_NO_EXPLICIT_TERMINATION_RECORD",
        "feature_use_of_terminal_metadata": "FORBIDDEN",
    }


def _trajectory_signature(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = [
        {
            "field": row["field"],
            "dtype": row["dtype"],
            "shape": row["shape"],
            "content_sha256": row["content_sha256"],
        }
        for row in rows
        if row["content_sha256"] != "NA_NOT_READ"
    ]
    return _sha256_bytes(_canonical_json_bytes(payload))


def _load_and_audit_hsc(mat_path: Path) -> dict[str, Any]:
    try:
        import numpy as np  # type: ignore
        import scipy.io  # type: ignore
    except ImportError as exc:
        raise PatriziDataGateError("numpy and scipy are required") from exc

    available = _available_memory_bytes()
    required = max(2 * 1024**3, mat_path.stat().st_size * 6)
    if available is not None and available < required:
        raise PatriziDataGateError(
            f"memory preflight failed: available={available}, required={required}"
        )

    inventory = scipy.io.whosmat(mat_path)
    inventory_rows = [
        {"name": name, "shape": list(shape), "matlab_class": matlab_class}
        for name, shape, matlab_class in inventory
    ]
    hsc_inventory = [row for row in inventory_rows if row["name"] == "HSC"]
    if hsc_inventory != [{"name": "HSC", "shape": [1, 1], "matlab_class": "struct"}]:
        raise PatriziDataGateError(f"unexpected HSC inventory: {hsc_inventory}")

    # The allowlist is the safety boundary: __function_workspace__ is inventoried
    # above but is not requested from loadmat and is never executed or decoded.
    loaded = scipy.io.loadmat(
        mat_path,
        variable_names=["HSC"],
        struct_as_record=False,
        squeeze_me=True,
        verify_compressed_data_integrity=True,
    )
    if "HSC" not in loaded:
        raise PatriziDataGateError("HSC was not returned by the static reader")
    unexpected_loaded = set(loaded) - {"__header__", "__version__", "__globals__", "HSC"}
    if unexpected_loaded:
        raise PatriziDataGateError(f"unexpected loaded variables: {sorted(unexpected_loaded)}")
    hsc = loaded["HSC"]
    _require_exact_fields(hsc, TOP_FIELDS, "HSC")
    _require_exact_fields(hsc.complete, CHANNELS, "HSC.complete")
    _require_exact_fields(hsc.summary, CHANNELS, "HSC.summary")
    _require_exact_fields(hsc.info, INFO_FIELDS, "HSC.info")

    schema_rows: list[dict[str, Any]] = []
    chronology_rows: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    numeric_by_scope_channel: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for channel in CHANNELS:
        complete = getattr(hsc.complete, channel)
        summary = getattr(hsc.summary, channel)
        _require_exact_fields(complete, COMPLETE_FIELDS, f"HSC.complete.{channel}")
        _require_exact_fields(summary, SUMMARY_FIELDS, f"HSC.summary.{channel}")

        for scope, struct_value, fields, numeric_fields, granularity in (
            ("complete", complete, COMPLETE_FIELDS, COMPLETE_NUMERIC_FIELDS, "measurement_log_row"),
            ("summary", summary, SUMMARY_FIELDS, SUMMARY_NUMERIC_FIELDS, "author_per_cycle_summary"),
        ):
            expected_size: int | None = None
            for field in fields:
                value = getattr(struct_value, field)
                if field in numeric_fields:
                    row = _audit_numeric_array(
                        value,
                        scope=scope,
                        channel=channel,
                        field=field,
                        granularity=granularity,
                    )
                    size = int(row["element_count"])
                    if expected_size is None:
                        expected_size = size
                    elif size != expected_size:
                        raise PatriziDataGateError(
                            f"numeric field-length mismatch at HSC.{scope}.{channel}.{field}"
                        )
                    numeric_by_scope_channel[(scope, channel)].append(row)
                else:
                    row = _audit_unavailable_object(
                        value,
                        scope=scope,
                        channel=channel,
                        field=field,
                        granularity=granularity,
                    )
                schema_rows.append(row)
            chronology_rows.append(
                _cycle_audit(getattr(struct_value, "Cycle"), scope=scope, channel=channel)
            )

        identity_rows.append(
            {
                "provisional_trajectory": channel,
                "raw_hierarchy": f"HSC.complete.{channel};HSC.summary.{channel};HSC.EIS[*].{channel}",
                "stable_physical_device_id": "NA_NOT_PRESENT_IN_AUDITED_NUMERIC_ROWS",
                "physical_device_count_evidence": "DESCRIPTION_ONLY_NOT_ROW_PROVEN",
                "strategy_mapping": "NA_UNPROVEN_FROM_NUMERIC_ROWS",
                "additional_calibration_or_reference_runs": "UNRESOLVED_OPAQUE_EIS",
                "device_strategy_confounding": "UNRESOLVED_BECAUSE_IDENTITY_NOT_PROVEN",
                "loco_eligibility": "BLOCKED_IDENTITY",
                "status": "BLOCKED_IDENTITY",
                "reason": "channel labels are hierarchy names, not auditable physical serial/device IDs",
            }
        )
        event_rows.append(
            {
                "provisional_trajectory": channel,
                "explicit_physical_failure_record": "NA_NOT_PRESENT",
                "explicit_protocol_termination_reason": "NA_NOT_PRESENT",
                "pdf_70_percent_stop_description": "DESCRIPTIVE_CANDIDATE_NOT_ROW_PROVEN",
                "threshold_reference": "NA_NOT_FROZEN",
                "smoothing_rule": "NA_NOT_FROZEN",
                "persistence_rule": "NA_NOT_FROZEN",
                "event_indicator": "NA",
                "censoring_status": "UNRESOLVED",
                "rul_truth_status": "NA",
                "status": "BLOCKED_TERMINAL_EVENT_SEMANTICS",
            }
        )

    # EIS is intentionally not traversed.  Only its outer container shape and
    # element classes are recorded; MCOS table payloads remain unavailable.
    eis = hsc.EIS
    eis_shape = list(getattr(eis, "shape", ()))
    eis_element_classes = sorted({type(item).__name__ for item in np.asarray(eis).reshape(-1)})
    schema_rows.append(
        {
            "scope": "EIS",
            "provisional_trajectory": "all_channels",
            "field": "opaque_MCOS_table_payloads",
            "parser_class": type(eis).__name__,
            "dtype": str(getattr(eis, "dtype", "NA")),
            "shape": json.dumps(eis_shape, separators=(",", ":")),
            "element_count": int(np.asarray(eis).size),
            "finite_count": "NA_NOT_DECODED",
            "nan_count": "NA_NOT_DECODED",
            "inf_count": "NA_NOT_DECODED",
            "minimum": "NA_NOT_DECODED",
            "maximum": "NA_NOT_DECODED",
            "unit": "NA_NOT_AUDITED",
            "unit_evidence": "PDF_DESCRIPTION_ONLY",
            "sampling_granularity": "claimed_EIS_sweep_not_row_audited",
            "provenance_class": "outer_container_only",
            "content_sha256": "NA_NOT_READ",
            "status": "BLOCKED_STATIC_OPAQUE",
            "reason": "EIS MATLAB table/MCOS contents were not decoded; 61-point/frequency/cycle claims unverified",
        }
    )

    signatures: dict[tuple[str, str], str] = {
        key: _trajectory_signature(rows) for key, rows in numeric_by_scope_channel.items()
    }
    counts = Counter(signatures.values())
    duplicate_rows: list[dict[str, Any]] = []
    for scope in ("complete", "summary"):
        for channel in CHANNELS:
            signature = signatures[(scope, channel)]
            duplicate_rows.append(
                {
                    "scope": scope,
                    "provisional_trajectory": channel,
                    "numeric_trajectory_signature_sha256": signature,
                    "exact_cross_channel_duplicate_count": counts[signature] - 1,
                    "summary_raw_lineage": (
                        "NA_WITHIN_COMPLETE"
                        if scope == "complete"
                        else "AUTHOR_SUMMARY_DO_NOT_COUNT_AS_INDEPENDENT_PHYSICAL_UNIT"
                    ),
                    "physical_overlap_status": "BLOCKED_IDENTITY",
                    "split_resolution": "DO_NOT_SPLIT_UNTIL_PHYSICAL_IDENTITY_IS_PROVEN",
                    "status": (
                        "PASS_NO_EXACT_NUMERIC_TRAJECTORY_DUPLICATE"
                        if counts[signature] == 1
                        else "BLOCKED_EXACT_NUMERIC_TRAJECTORY_DUPLICATE"
                    ),
                }
            )

    return {
        "inventory": inventory_rows,
        "loaded_variable_allowlist": ["HSC"],
        "excluded_author_workspace": any(row["name"] == "__function_workspace__" for row in inventory_rows),
        "memory_preflight": {
            "available_bytes": available if available is not None else "UNKNOWN",
            "required_bytes": required,
            "status": "PASS" if available is None or available >= required else "FAIL",
        },
        "top_fields": list(_fieldnames(hsc, "HSC")),
        "eis_outer_shape": eis_shape,
        "eis_outer_element_classes": eis_element_classes,
        "schema_rows": schema_rows,
        "chronology_rows": chronology_rows,
        "identity_rows": identity_rows,
        "duplicate_rows": duplicate_rows,
        "event_rows": event_rows,
    }


def _write_bytes(path: Path, value: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise PatriziDataGateError(f"refusing to overwrite artifact: {path}")
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _write_json(path: Path, value: Any) -> None:
    _write_bytes(path, _canonical_json_bytes(value))


def _csv_cell(value: Any) -> str | int | float:
    if value is None:
        return "NA"
    if isinstance(value, (str, int, float)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    if path.exists() or path.is_symlink():
        raise PatriziDataGateError(f"refusing to overwrite artifact: {path}")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in fieldnames})
        stream.flush()
        os.fsync(stream.fileno())


def _write_or_validate_local_manifest(path: Path, manifest: Mapping[str, Any]) -> str:
    expected = _canonical_json_bytes(manifest)
    if path.exists():
        _require_regular_file(path, "local raw manifest")
        observed = path.read_bytes()
        try:
            prior = json.loads(observed)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PatriziDataGateError(
                "existing LOCAL_RAW_MANIFEST.json is not valid JSON"
            ) from exc
        if (
            not isinstance(prior, dict)
            or observed != _canonical_json_bytes(prior)
            or set(prior) != set(manifest)
            or not isinstance(prior.get("created_at_utc"), str)
            or {
                key: value for key, value in prior.items() if key != "created_at_utc"
            }
            != {
                key: value for key, value in manifest.items() if key != "created_at_utc"
            }
        ):
            raise PatriziDataGateError(
                "existing LOCAL_RAW_MANIFEST.json differs; refusing to overwrite or silently merge"
            )
        return _sha256_bytes(observed)
    else:
        _write_bytes(path, expected)
    return _sha256_bytes(expected)


def _artifact_record(path: Path) -> dict[str, Any]:
    digests = _file_digests(path)
    return {"filename": path.name, "bytes": digests["bytes"], "sha256": digests["sha256"]}


def _finalize_artifact_graph(
    staging: Path,
    *,
    run_id: str,
    completion_decision: Mapping[str, Any],
) -> None:
    """Write the decision first, then bind it without a circular self-hash."""

    if any(
        (staging / name).exists() or (staging / name).is_symlink()
        for name in ARTIFACT_GRAPH_WRITE_ORDER
    ):
        raise PatriziDataGateError("artifact integrity graph outputs already exist")
    if (
        not isinstance(completion_decision, Mapping)
        or completion_decision.get("run_id") != run_id
        or {"artifact_manifest_sha256", "artifact_hashes_sha256"}
        & set(completion_decision)
    ):
        raise PatriziDataGateError("completion decision violates non-circular graph schema")

    complete = dict(completion_decision)
    complete["artifact_integrity"] = {
        "schema_version": ARTIFACT_INTEGRITY_SCHEMA_VERSION,
        "write_order": list(ARTIFACT_GRAPH_WRITE_ORDER),
        "bound_by_later_artifacts": [
            "ARTIFACT_MANIFEST.json",
            "ARTIFACT_HASHES.sha256",
        ],
        "circular_hash_fields_omitted": [
            "artifact_manifest_sha256",
            "artifact_hashes_sha256",
        ],
    }
    _write_json(staging / "COMPLETE.json", complete)

    pre_manifest_names = sorted(path.name for path in staging.iterdir())
    artifact_manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "integrity_graph": {
            "schema_version": ARTIFACT_INTEGRITY_SCHEMA_VERSION,
            "write_order": list(ARTIFACT_GRAPH_WRITE_ORDER),
            "manifest_excludes": [
                "ARTIFACT_MANIFEST.json",
                "ARTIFACT_HASHES.sha256",
            ],
            "hash_list_excludes": ["ARTIFACT_HASHES.sha256"],
        },
        "artifacts": [_artifact_record(staging / name) for name in pre_manifest_names],
        "raw_rows_in_bundle": False,
    }
    _write_json(staging / "ARTIFACT_MANIFEST.json", artifact_manifest)

    hash_names = sorted(path.name for path in staging.iterdir())
    hash_lines = [
        f"{_file_digests(staging / name)['sha256']}  {name}\n" for name in hash_names
    ]
    _write_bytes(staging / "ARTIFACT_HASHES.sha256", "".join(hash_lines).encode("ascii"))


def _target_rows() -> list[dict[str, Any]]:
    return [
        {
            "target": "charge_capacity",
            "native_field": "Cap_ch",
            "unit": "Ah",
            "row_structure": "OBSERVED_NUMERIC",
            "online_availability": "BLOCKED_ABSOLUTE_TIME_AND_IDENTITY",
            "numeric_target_emitted": "NO",
            "status": "BLOCKED_MODELING_GATE",
            "reason": "Ah capacity exists but physical identity, chronology, and split are not eligible",
        },
        {
            "target": "discharge_capacity",
            "native_field": "Cap_dis",
            "unit": "Ah",
            "row_structure": "OBSERVED_NUMERIC",
            "online_availability": "BLOCKED_ABSOLUTE_TIME_AND_IDENTITY",
            "numeric_target_emitted": "NO",
            "status": "BLOCKED_MODELING_GATE",
            "reason": "Ah capacity exists but physical identity, chronology, and split are not eligible",
        },
        {
            "target": "farad_capacitance",
            "native_field": "NA",
            "unit": "F",
            "row_structure": "NA",
            "online_availability": "NA",
            "numeric_target_emitted": "NO",
            "status": "NA",
            "reason": "Cap_ch/Cap_dis are Ah and must not be renamed as farad capacitance",
        },
        {
            "target": "internal_resistance",
            "native_field": "IR",
            "unit": "ohm",
            "row_structure": "OBSERVED_NUMERIC_WITH_MISSING_VALUES",
            "online_availability": "BLOCKED_MEASUREMENT_SEMANTICS_AND_IDENTITY",
            "numeric_target_emitted": "NO",
            "status": "BLOCKED_NOT_ESR",
            "reason": "native IR is not automatically ESR",
        },
        {
            "target": "ESR",
            "native_field": "NA",
            "unit": "ohm",
            "row_structure": "BLOCKED_STATIC_OPAQUE_EIS",
            "online_availability": "NA",
            "numeric_target_emitted": "NO",
            "status": "NA",
            "reason": "EIS table payload is opaque and no ESR convention is frozen",
        },
        {
            "target": "SOH",
            "native_field": "NA_DERIVED_ONLY",
            "unit": "ratio",
            "row_structure": "NA_NOT_GENERATED",
            "online_availability": "BLOCKED_C_REF_STABILIZATION_AND_TRAIN_ONLY_RULE",
            "numeric_target_emitted": "NO",
            "status": "BLOCKED",
            "reason": "no frozen per-device C_ref or normalization rule",
        },
        {
            "target": "RUL",
            "native_field": "NA",
            "unit": "NA",
            "row_structure": "NA_NOT_GENERATED_OR_SCORED",
            "online_availability": "NA",
            "numeric_target_emitted": "NO",
            "status": "NA",
            "reason": "no auditable event/censor semantics; P1 forbids RUL generation and scoring",
        },
    ]


def _report(summary: Mapping[str, Any], audit: Mapping[str, Any]) -> str:
    chronology = audit["chronology_rows"]
    missing_summary = [
        f"{row['provisional_trajectory']}:{row['missing_cycles_within_observed_range']}"
        for row in chronology
        if row["scope"] == "summary" and row["missing_cycle_count_within_observed_range"]
    ]
    return "\n".join(
        [
            "# Patrizi HSC P1 Static Data Gate",
            "",
            f"- Overall decision: `{summary['overall_decision']}`",
            "- Scope: byte integrity and aggregate row-level static audit only.",
            "- No model, forecast, SOH/RUL label, RUL score, LLM, Agent, or external API was run.",
            "- MAT allowlist: only `HSC`; `__function_workspace__` was inventoried but not loaded.",
            "- `Time`, `Method`, duration objects, and EIS tables remain `BLOCKED_STATIC_OPAQUE`.",
            "",
            "## Gate decisions",
            "",
            *[f"- {gate}: `{status}`" for gate, status in summary["gate_status"].items()],
            "",
            "## Material findings",
            "",
            "- The raw hierarchy exposes `ch1`-`ch8`, but no row-auditable physical serial/device IDs; Identity and LOCO are `BLOCKED_IDENTITY`.",
            "- `Cap_ch` and `Cap_dis` are Ah capacity fields, not farad capacitance.",
            "- Native `IR` is not automatically ESR; EIS-derived ESR is unavailable because MCOS tables were not decoded.",
            "- SOH is blocked because `C_ref`, stabilization, normalization, and train-only rules are not frozen.",
            "- RUL is `NA`; no event/censor truth was generated or scored.",
            "- PDF/raw schema conflicts (top-field count, Cycle dtype, and duration-field descriptions) trigger a scientific schema/unit block.",
            f"- Summary cycle gaps within observed ranges: {', '.join(missing_summary) if missing_summary else 'none'}.",
            "- Exact numeric-trajectory hashing found no cross-channel duplicate, but physical overlap remains unresolved while identity is blocked.",
            "",
            "## Downstream lock",
            "",
            "All modeling, prediction, RUL, split generation, API, and P4/P5 actions remain blocked. The only positive conclusion is exact acquisition integrity.",
            "",
        ]
    )


def run_data_gate(
    *,
    mat_path: Path,
    pdf_path: Path,
    output_parent: Path,
    run_id: str | None = None,
    header_dir: Path | None = None,
    local_manifest_path: Path | None = None,
) -> Path:
    """Run the frozen P1 audit and atomically publish an evidence directory."""

    versions = _dependency_versions()
    if run_id is None:
        run_id = datetime.now().astimezone().strftime("p1_%Y%m%d_%H%M%S")
    if re.fullmatch(r"p1_[A-Za-z0-9_-]+", run_id) is None:
        raise PatriziDataGateError("run_id must match p1_[A-Za-z0-9_-]+")

    _require_plain_directory(output_parent, "output parent", create=True)
    final_dir = output_parent / run_id
    if final_dir.exists() or final_dir.is_symlink():
        raise PatriziDataGateError(f"append-only output already exists: {final_dir}")

    expected_by_name = {item.filename: item for item in EXPECTED_PAYLOADS}
    mat_integrity = _verify_payload(mat_path, expected_by_name["Dataset_HSC.mat"])
    pdf_integrity = _verify_payload(pdf_path, expected_by_name["HSC_dataset_info.pdf"])
    integrity_rows = [mat_integrity, pdf_integrity]
    transport = _parse_sanitized_header_evidence(header_dir)
    audit = _load_and_audit_hsc(mat_path)

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if local_manifest_path is None:
        local_manifest_path = mat_path.parent / "LOCAL_RAW_MANIFEST.json"
    if local_manifest_path.parent != mat_path.parent:
        _require_plain_directory(local_manifest_path.parent, "local manifest parent", create=True)
    local_manifest = {
        "schema_version": LOCAL_MANIFEST_SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "doi": DOI,
        "licence": LICENCE,
        "created_at_utc": created_at,
        "scope": "local_only_ignored_raw_byte_manifest",
        "payloads": integrity_rows,
        "sanitized_transport_evidence": transport,
        "download_tool_version_at_audit": _curl_version(),
        "retrieval_time_status": "UNAVAILABLE_NOT_ATTESTED_BY_STATIC_DATA_GATE",
        "raw_payload_policy": "ignored_local_only_never_commit",
    }
    local_manifest_sha256 = _write_or_validate_local_manifest(local_manifest_path, local_manifest)

    acquisition_manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "doi": DOI,
        "licence": LICENCE,
        "run_id": run_id,
        "generated_at_utc": created_at,
        "scope": "P1_STATIC_ROW_AUDIT_ONLY",
        "approval_boundary": {
            "approved": ["download", "byte_integrity", "static_numeric_row_audit"],
            "forbidden": [
                "model_training",
                "model_evaluation",
                "prediction",
                "soh_generation",
                "rul_generation_or_scoring",
                "llm_or_agent_call",
                "external_api_call",
                "author_workspace_or_class_execution",
            ],
        },
        "payloads": integrity_rows,
        "local_raw_manifest": {
            "relative_name": local_manifest_path.name,
            "sha256": local_manifest_sha256,
            "tracked": False,
        },
        "sanitized_transport_evidence": transport,
        "environment_versions": versions,
    }

    container_inspection = {
        "schema_version": SCHEMA_VERSION,
        "container": "MATLAB 5 MAT-file",
        "static_reader": "scipy.io.whosmat + scipy.io.loadmat",
        "variable_inventory": audit["inventory"],
        "loadmat_variable_names": audit["loaded_variable_allowlist"],
        "author_function_workspace_present_and_excluded": audit["excluded_author_workspace"],
        "author_script_executed": False,
        "matlab_class_code_executed": False,
        "memory_preflight": audit["memory_preflight"],
        "top_fields_observed": audit["top_fields"],
        "eis_outer_shape": audit["eis_outer_shape"],
        "eis_outer_element_classes": audit["eis_outer_element_classes"],
        "eis_payload_status": "BLOCKED_STATIC_OPAQUE",
        "pdf_role": "description_only_never_overrides_raw",
        "pinned_pdf_conflicts": list(PINNED_PDF_CONFLICTS),
        "status": "PASS_STATIC_HSC_ALLOWLIST_WITH_OPAQUE_FIELDS_BLOCKED",
    }

    split_ledger = {
        "schema_version": SCHEMA_VERSION,
        "physical_unit_registry_status": "BLOCKED_IDENTITY",
        "proposed_whole_unit_split_manifest": "NA_NOT_GENERATED",
        "split_hash": "NA",
        "whole_unit_loco_eligible": False,
        "device_strategy_confounding": "UNRESOLVED_UNTIL_PHYSICAL_IDENTITY_IS_PROVEN",
        "ren_patrizi_pooling": "FORBIDDEN",
        "suffix_only_split_inputs": [
            "final_length",
            "terminal_cycle",
            "event_or_eol_status",
            "future_gap",
            "source_member_size",
        ],
        "feature_calibration_status": "BLOCKED_NO_SPLIT",
        "status": "BLOCKED_IDENTITY",
    }

    gate_status = {
        "acquisition_integrity": "PASS_EXACT_BYTES_MD5_SHA256",
        "container_safety": "PASS_HSC_ONLY_AUTHOR_WORKSPACE_EXCLUDED",
        "identity": "BLOCKED_IDENTITY",
        "schema_unit": "BLOCKED_DOCUMENTATION_CONFLICT_AND_STATIC_OPAQUE_FIELDS",
        "chronology": "BLOCKED_ABSOLUTE_TIME_STATIC_OPAQUE_CYCLE_AXIS_PARTIAL_PASS",
        "duplicate_overlap": "BLOCKED_IDENTITY_EXACT_NUMERIC_SCREEN_PASS",
        "target": "BLOCKED_MODELING_ELIGIBILITY_RUL_NA_ESR_NA_SOH_BLOCKED",
        "terminal_event_censor": "BLOCKED_NO_AUDITABLE_EVENT_RUL_NA",
        "split_leakage": "BLOCKED_IDENTITY",
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "run_id": run_id,
        "gate_status": gate_status,
        "overall_decision": "ACQUISITION_INTEGRITY_PASS_ROW_LEVEL_BLOCKED",
        "scientific_eligibility": "BLOCKED",
        "row_level_target_eligibility_pass": False,
        "external_b5_status": "NA_BLOCKED_P1_PATRIZI",
        "rul_status": "NA",
        "esr_status": "NA",
        "soh_status": "BLOCKED",
        "numeric_target_emitted": False,
        "model_or_api_executed": False,
        "downstream_locks": {
            "model_training": "BLOCKED_BY_P1_SCOPE_AND_DATA_GATE",
            "model_evaluation": "BLOCKED_BY_P1_SCOPE_AND_DATA_GATE",
            "capacitor_prediction": "BLOCKED_BY_P1_SCOPE_AND_DATA_GATE",
            "soh_generation": "BLOCKED_BY_P1_SCOPE_AND_DATA_GATE",
            "rul_generation_or_scoring": "BLOCKED_BY_P1_SCOPE_AND_DATA_GATE",
            "llm_agent_api": "BLOCKED_BY_P1_SCOPE_AND_HUMAN_GATE",
            "P3": "BLOCKED_SEPARATE_HUMAN_GATE",
            "development_api": "BLOCKED_SEPARATE_HUMAN_GATE",
            "P4_P5": "BLOCKED_SEPARATE_HUMAN_GATE",
        },
    }

    target_rows = _target_rows()
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}.staging-", dir=output_parent))
    try:
        _write_json(staging / "ACQUISITION_MANIFEST.json", acquisition_manifest)
        _write_csv(
            staging / "RAW_HASH_LEDGER.csv",
            integrity_rows,
            (
                "item_id",
                "filename",
                "direct_url",
                "expected_bytes",
                "observed_bytes",
                "published_md5",
                "observed_md5",
                "project_sha256",
                "status",
            ),
        )
        _write_json(staging / "CONTAINER_INSPECTION.json", container_inspection)
        _write_csv(
            staging / "UNIT_IDENTITY_LEDGER.csv",
            audit["identity_rows"],
            tuple(audit["identity_rows"][0].keys()),
        )
        _write_csv(
            staging / "SCHEMA_UNIT_LEDGER.csv",
            audit["schema_rows"],
            tuple(audit["schema_rows"][0].keys()),
        )
        _write_csv(
            staging / "CHRONOLOGY_LEDGER.csv",
            audit["chronology_rows"],
            tuple(audit["chronology_rows"][0].keys()),
        )
        _write_csv(
            staging / "DUPLICATE_OVERLAP_LEDGER.csv",
            audit["duplicate_rows"],
            tuple(audit["duplicate_rows"][0].keys()),
        )
        _write_csv(
            staging / "TARGET_ELIGIBILITY.csv",
            target_rows,
            tuple(target_rows[0].keys()),
        )
        _write_csv(
            staging / "EVENT_CENSOR_LEDGER.csv",
            audit["event_rows"],
            tuple(audit["event_rows"][0].keys()),
        )
        _write_json(staging / "SPLIT_LEAKAGE_LEDGER.json", split_ledger)
        _write_json(staging / "DATA_GATE_SUMMARY.json", summary)
        _write_bytes(staging / "DATA_GATE_REPORT.md", _report(summary, audit).encode("utf-8"))

        complete = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": "COMPLETE_P1_AUDIT_ROW_LEVEL_BLOCKED",
            "overall_decision": summary["overall_decision"],
            "required_output_count": len(REQUIRED_OUTPUTS),
            "rul_generated_or_scored": False,
            "model_or_api_executed": False,
        }
        _finalize_artifact_graph(
            staging,
            run_id=run_id,
            completion_decision=complete,
        )

        observed_names = tuple(sorted(path.name for path in staging.iterdir()))
        if observed_names != tuple(sorted(REQUIRED_OUTPUTS)):
            raise PatriziDataGateError(
                f"incomplete artifact graph: observed={observed_names}, required={tuple(sorted(REQUIRED_OUTPUTS))}"
            )
        staging.rename(final_dir)
        return final_dir
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw/patrizi_hsc"),
        help="ignored directory containing the two frozen payload files",
    )
    parser.add_argument(
        "--output-parent",
        type=Path,
        default=Path("data/audit/patrizi_hsc"),
        help="parent for a new append-only p1_* evidence bundle",
    )
    parser.add_argument("--run-id", help="optional unique p1_* run identifier")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_data_gate(
        mat_path=args.raw_root / "Dataset_HSC.mat",
        pdf_path=args.raw_root / "HSC_dataset_info.pdf",
        output_parent=args.output_parent,
        run_id=args.run_id,
        header_dir=args.raw_root / "incoming",
        local_manifest_path=args.raw_root / "LOCAL_RAW_MANIFEST.json",
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
