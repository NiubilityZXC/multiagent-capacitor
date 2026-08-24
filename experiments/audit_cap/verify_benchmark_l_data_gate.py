#!/usr/bin/env python3
"""Independent, read-only verifier for Benchmark-L P1 Data Gate outputs.

The verifier intentionally does not import the generator.  It treats the output
directory as an untrusted append-only evidence bundle and checks the bundle's
file graph, hashes, lineage, tabular schemas, gate aggregation, and downstream
locks.  It never reads the source MAT payloads and cannot run a model or produce
RUL values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn, Sequence


SCHEMA_VERSION = "audit-cap.benchmark-l-data-gate-verifier.v1"
OUTPUT_SCHEMA_VERSION = "audit-cap.benchmark-l-data-gate.v1.1"

FROZEN_CONTRACT_SHA256 = "6e2a726177e68a51f9df39f33b5ac8135aeb1221642c48743d37605cb2eaad19"
FROZEN_AMENDMENT_SHA256 = "73228e662c5d742a1cd5e3f6fadedd22e8e24fa34d501a274d55d4dd6f12e5a7"

STATUS_PRECEDENCE = ("FAIL", "BLOCKED", "AMBER", "PASS")
STATUS_RANK = {status: index for index, status in enumerate(STATUS_PRECEDENCE)}
GATE_IDS = tuple(f"G{index:02d}" for index in range(11))
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

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
REQUIRED_REPORTS = ("DATA_GATE_REPORT.md", "ARTIFACT_HASHES.sha256")
REQUIRED_FILES = frozenset((*REQUIRED_JSON, *REQUIRED_CSV, *REQUIRED_REPORTS))

# ARTIFACT_MANIFEST cannot contain its own digest. ARTIFACT_HASHES additionally
# binds that manifest; COMPLETE then binds both without a self-referential hash.
SCIENTIFIC_ARTIFACTS = frozenset(
    REQUIRED_FILES - {"ARTIFACT_MANIFEST.json", "ARTIFACT_HASHES.sha256", "COMPLETE.json"}
)
HASH_LEDGER_FILES = frozenset((*SCIENTIFIC_ARTIFACTS, "ARTIFACT_MANIFEST.json"))

LINEAGE_KEYS = (
    "contract_sha256",
    "amendment_sha256",
    "integrity_manifest_sha256",
    "code_sha256",
)

DOWNSTREAM_LOCK_KEYS = (
    "model_training",
    "model_evaluation",
    "rul_generation_or_scoring",
    "benchmark_l_modeling",
    "formal_design_gate",
    "freeze_b",
    "agent_topology_evaluation",
)
LOCK_VALUE = "BLOCKED_BY_USER_SCOPE"

ELIGIBILITY_REQUIRED_COLUMNS = (
    "gate_id",
    "scope_id",
    "status",
    "evidence",
    "unlocks",
    "parser_release_eligible",
    "modeling_eligible",
    "rul_eligible",
    "benchmark_l_modeling_eligible",
)

# These headers duplicate the independently reviewed v1.1 output adapter.  The
# manifest must repeat them and the on-disk CSV must match both, in order.
CSV_REQUIRED_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "REFERENCE_LINKAGE_LEDGER.csv": (
        "item_id", "source_sha256", "condition", "provisional_unit", "event_index",
        "raw_replicate_index", "header_reference_status", "data_reference_status",
        "pair_status", "raw_slot_class", "column_schema_status", "header_sha256",
        "matrix_content_sha256", "acquisition_start", "finish_candidate_inferred",
        "finish_evidence", "sorted_replicate_rank", "eligibility", "quarantine_reason",
    ),
    "EIS_EVENT_LEDGER.csv": (
        "source_sha256", "condition", "provisional_unit", "event_index",
        "calendar_date_raw", "start_clock_raw", "finish_clock_raw", "elapsed_like_raw",
        "raw_slot_count", "eligible_nonempty_count", "quarantined_count",
        "structural_empty_count", "nonempty_pair_count", "raw_order_chronological",
        "sorted_order_raw_indices", "acquisition_tie_count", "finish_candidate_inferred",
        "causal_availability_status", "causal_availability_reason", "status",
    ),
    "COLUMN_FREQUENCY_LEDGER.csv": (
        "item_id", "source_sha256", "condition", "provisional_unit", "event_index",
        "raw_replicate_index", "raw_shape", "canonical_shape", "raw_token_count",
        "canonical_column_count", "column_token_nul_sha256", "column_mapping_status",
        "n_raw_rows", "n_preamble", "n_frequency", "invalid_frequency_count",
        "preamble_status", "positive_sweep_status", "positive_grid_sha256",
        "algebra_status", "algebra_max_scaled_error", "finite_count", "nan_count",
        "inf_count", "matrix_content_sha256", "status",
    ),
    "TRANSIENT_ALIGNMENT_LEDGER.csv": (
        "item_id", "condition", "provisional_unit", "signal_kind", "timestamp_rows",
        "signal_rows", "row_difference", "timestamp_reversal_count",
        "timestamp_duplicate_count", "timestamp_irregular_gap_count",
        "timestamp_content_sha256", "candidate_explanations", "applied_repair",
        "alignment_status",
    ),
    "MISSINGNESS_LEDGER.csv": (
        "item_id", "modality", "condition", "provisional_unit", "signal_kind", "shape",
        "element_count", "finite_count", "nan_count", "inf_count", "rows_any_nan",
        "rows_all_nan", "positions_any_nan", "positions_all_nan",
        "rowwise_nan_run_count", "finite_prefix_nan_suffix_violation_rows",
        "nan_mask_sha256", "content_sha256",
    ),
    "UNIT_IDENTITY_LEDGER.csv": (
        "condition", "provisional_unit", "provenance_only_group", "eis_available",
        "transient_available", "stable_physical_id_status", "serial_evidence",
        "board_evidence", "batch_evidence", "replacement_reuse_evidence",
        "split_group_status",
    ),
    "CONTENT_SIGNATURE_LEDGER.csv": (
        "item_id", "content_type", "condition", "provisional_unit", "event_index",
        "sorted_replicate_rank", "signal_kind", "dtype", "shape", "content_sha256",
        "sample_sha256",
    ),
    "DUPLICATE_CANDIDATE_LEDGER.csv": (
        "candidate_type", "item_id_a", "item_id_b", "content_type", "finite_overlap",
        "pearson_r", "pooled_rms_nrmse", "evidence", "resolution",
        "split_group_created",
    ),
    "REPAIR_QUARANTINE_LEDGER.csv": (
        "scope_id", "condition", "provisional_unit", "event_index",
        "raw_replicate_index", "reason", "candidate_explanation", "applied_repair",
        "resolution",
    ),
    "TARGET_TRAJECTORY_LEDGER.csv": (
        "condition", "provisional_unit", "raw_observables", "capacity_target_status",
        "esr_target_status", "soh_target_status", "rul_target_status",
        "numeric_target_emitted", "reason",
    ),
    "OUTCOME_LEDGER.csv": (
        "condition", "provisional_unit", "termination_reason", "failure_event",
        "censoring_status", "sequence_end_is_eol", "outcome_status",
    ),
    "ELIGIBILITY_MATRIX.csv": ELIGIBILITY_REQUIRED_COLUMNS,
}

GOLDEN_REAL_DATA_COUNTS: Mapping[str, int] = {
    "eis_event_slots": 1_752,
    "raw_inner_slots": 9_316,
    "nonempty_matrix_pairs": 8_835,
    "paired_canonical_empties": 481,
    "eis_nonfinite_count": 0,
    "exact_eis_matrix_duplicate_candidates": 0,
}


class DataGateVerificationError(RuntimeError):
    """Raised when an output bundle is incomplete, inconsistent, or unsafe."""


def _fail(message: str) -> NoReturn:
    raise DataGateVerificationError(message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_plain_directory(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise DataGateVerificationError(f"output directory does not exist: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        _fail(f"output must be a real, non-symlink directory: {path}")

    # Refuse a symlink in any existing path component as well as within output.
    current = Path(path.anchor) if path.is_absolute() else Path()
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current /= part
        try:
            component = current.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(component.st_mode):
            _fail(f"symlink path component is forbidden: {current}")


def _validate_file_graph(output_dir: Path) -> None:
    _require_plain_directory(output_dir)
    observed: set[str] = set()
    for child in output_dir.iterdir():
        metadata = child.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            _fail(f"symlink artifact is forbidden: {child.name}")
        if not stat.S_ISREG(metadata.st_mode):
            _fail(f"nested directory or special artifact is forbidden: {child.name}")
        observed.add(child.name)
    missing = sorted(REQUIRED_FILES - observed)
    unexpected = sorted(observed - REQUIRED_FILES)
    if missing or unexpected:
        _fail(f"artifact file set mismatch; missing={missing}, unexpected={unexpected}")


def _reject_json_constant(token: str) -> None:
    _fail(f"non-finite JSON token is forbidden: {token}")


def _no_duplicate_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key is forbidden: {key!r}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicate_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataGateVerificationError(f"invalid strict JSON in {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        _fail(f"{path.name} must contain a top-level object")
    return value


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(f"schema adapter error: {context} must be an object")
    return value


def _list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"schema adapter error: {context} must be an array")
    return value


def _required(mapping: Mapping[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        _fail(f"schema adapter error: {context}.{key} is required")
    return mapping[key]


def _strict_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"schema adapter error: {context} must be boolean")
    return value


def _strict_int(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"schema adapter error: {context} must be a non-negative integer")
    return value


def _strict_sha(value: Any, context: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(f"schema adapter error: {context} must be a lowercase SHA-256")
    return value


def _verify_lineage(
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    expected_source_manifest: Path | None,
    expected_code: Path | None,
) -> dict[str, str]:
    manifest = payloads["ARTIFACT_MANIFEST.json"]
    complete = payloads["COMPLETE.json"]
    canonical = {
        key: _strict_sha(
            _required(manifest, key, "ARTIFACT_MANIFEST.json"),
            f"ARTIFACT_MANIFEST.json.{key}",
        )
        for key in LINEAGE_KEYS
    }
    for key, expected in canonical.items():
        observed = _strict_sha(
            _required(complete, key, "COMPLETE.json"),
            f"COMPLETE.json.{key}",
        )
        if observed != expected:
            _fail(f"lineage mismatch for {key} between artifact manifest and COMPLETE.json")

    contract_artifact = payloads["DATA_GATE_CONTRACT.json"]
    base = _mapping(
        _required(contract_artifact, "base_contract", "DATA_GATE_CONTRACT.json"),
        "DATA_GATE_CONTRACT.json.base_contract",
    )
    amendment = _mapping(
        _required(contract_artifact, "amendment", "DATA_GATE_CONTRACT.json"),
        "DATA_GATE_CONTRACT.json.amendment",
    )
    if _strict_sha(_required(base, "sha256", "base_contract"), "base_contract.sha256") != canonical["contract_sha256"]:
        _fail("DATA_GATE_CONTRACT base-contract lineage mismatch")
    if _strict_sha(_required(amendment, "sha256", "amendment"), "amendment.sha256") != canonical["amendment_sha256"]:
        _fail("DATA_GATE_CONTRACT amendment lineage mismatch")
    data_manifest_sha = _strict_sha(
        _required(payloads["DATA_MANIFEST.json"], "integrity_manifest_sha256", "DATA_MANIFEST.json"),
        "DATA_MANIFEST.json.integrity_manifest_sha256",
    )
    if data_manifest_sha != canonical["integrity_manifest_sha256"]:
        _fail("DATA_MANIFEST integrity lineage mismatch")
    base_content = _mapping(_required(base, "content", "base_contract"), "base_contract.content")
    precedence = _list(
        _required(base_content, "status_precedence", "base_contract.content"),
        "base_contract.content.status_precedence",
    )
    if tuple(precedence) != STATUS_PRECEDENCE:
        _fail("embedded contract status precedence is not FAIL > BLOCKED > AMBER > PASS")
    if canonical["contract_sha256"] != FROZEN_CONTRACT_SHA256:
        _fail("contract lineage does not bind the frozen v1 protocol JSON")
    if canonical["amendment_sha256"] != FROZEN_AMENDMENT_SHA256:
        _fail("amendment lineage does not bind the frozen v1.1 amendment JSON")
    if expected_source_manifest is not None:
        if expected_source_manifest.is_symlink() or not expected_source_manifest.is_file():
            _fail("expected source manifest must be a regular, non-symlink file")
        if _sha256_file(expected_source_manifest) != canonical["integrity_manifest_sha256"]:
            _fail("source manifest lineage SHA-256 mismatch")
    if expected_code is not None:
        if expected_code.is_symlink() or not expected_code.is_file():
            _fail("expected parser code must be a regular, non-symlink file")
        if _sha256_file(expected_code) != canonical["code_sha256"]:
            _fail("parser code lineage SHA-256 mismatch")
    return canonical


def _parse_artifact_manifest(
    output_dir: Path,
    payload: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if _required(payload, "schema_version", "ARTIFACT_MANIFEST.json") != OUTPUT_SCHEMA_VERSION:
        _fail("unsupported ARTIFACT_MANIFEST.json schema_version")
    raw_entries = _list(
        _required(payload, "stable_artifacts", "ARTIFACT_MANIFEST.json"),
        "stable_artifacts",
    )
    entries: dict[str, dict[str, Any]] = {}
    for index, raw_entry in enumerate(raw_entries):
        context = f"ARTIFACT_MANIFEST.json.stable_artifacts[{index}]"
        entry = dict(_mapping(raw_entry, context))
        required_keys = {"name", "size_bytes", "sha256"}
        missing = sorted(required_keys - set(entry))
        if missing:
            _fail(f"schema adapter error: {context} missing keys {missing}")
        name = entry["name"]
        if not isinstance(name, str) or Path(name).name != name or name in {"", ".", ".."}:
            _fail(f"unsafe artifact manifest name at {context}: {name!r}")
        if name in entries:
            _fail(f"duplicate ARTIFACT_MANIFEST entry: {name}")
        expected_bytes = _strict_int(entry["size_bytes"], f"{context}.size_bytes")
        expected_sha = _strict_sha(entry["sha256"], f"{context}.sha256")
        artifact = output_dir / name
        if artifact.stat().st_size != expected_bytes:
            _fail(f"artifact byte-count mismatch: {name}")
        if _sha256_file(artifact) != expected_sha:
            _fail(f"artifact SHA-256 mismatch: {name}")
        entries[name] = entry
    if set(entries) != SCIENTIFIC_ARTIFACTS:
        _fail(
            "ARTIFACT_MANIFEST scientific file set mismatch; "
            f"missing={sorted(SCIENTIFIC_ARTIFACTS - set(entries))}, "
            f"unexpected={sorted(set(entries) - SCIENTIFIC_ARTIFACTS)}"
        )
    return entries


def _parse_hash_ledger(path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise DataGateVerificationError("ARTIFACT_HASHES.sha256 must be ASCII") from exc
    for line_number, line in enumerate(lines, start=1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None:
            _fail(f"invalid ARTIFACT_HASHES.sha256 line {line_number}")
        digest, name = match.groups()
        if name in hashes:
            _fail(f"duplicate hash-ledger entry: {name}")
        hashes[name] = digest
    if set(hashes) != HASH_LEDGER_FILES:
        _fail(
            "ARTIFACT_HASHES file set mismatch; "
            f"missing={sorted(HASH_LEDGER_FILES - set(hashes))}, "
            f"unexpected={sorted(set(hashes) - HASH_LEDGER_FILES)}"
        )
    return hashes


def _read_csv_schema_and_count(path: Path) -> tuple[tuple[str, ...], int, list[dict[str, str]]]:
    retained: list[dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames is None:
                _fail(f"CSV header is missing: {path.name}")
            columns = tuple(reader.fieldnames)
            if not columns or any(not value or "\x00" in value for value in columns):
                _fail(f"CSV has an empty or NUL header field: {path.name}")
            if len(set(columns)) != len(columns):
                _fail(f"CSV has duplicate header fields: {path.name}")
            count = 0
            for row in reader:
                if None in row:
                    _fail(f"CSV row has excess fields: {path.name} row {count + 2}")
                if any(value is None for value in row.values()):
                    _fail(f"CSV row has missing fields: {path.name} row {count + 2}")
                count += 1
                retained.append(row)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise DataGateVerificationError(f"invalid CSV {path.name}: {exc}") from exc
    return columns, count, retained


def _verify_csv_artifacts(
    output_dir: Path,
    entries: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, int], dict[str, list[dict[str, str]]]]:
    row_counts: dict[str, int] = {}
    rows_by_name: dict[str, list[dict[str, str]]] = {}
    for name in REQUIRED_CSV:
        entry = entries[name]
        expected_columns_raw = _required(entry, "columns", f"artifact entry {name}")
        expected_columns_list = _list(expected_columns_raw, f"artifact entry {name}.columns")
        if not all(isinstance(column, str) for column in expected_columns_list):
            _fail(f"artifact entry {name}.columns must contain only strings")
        expected_columns = tuple(expected_columns_list)
        expected_rows = _strict_int(_required(entry, "row_count", f"artifact entry {name}"), f"{name}.row_count")
        columns, row_count, retained = _read_csv_schema_and_count(output_dir / name)
        if columns != expected_columns:
            _fail(f"CSV stable-column mismatch for {name}: actual={columns}, manifest={expected_columns}")
        if columns != CSV_REQUIRED_COLUMNS[name]:
            _fail(
                f"schema adapter error: {name} does not match frozen v1.1 columns; "
                f"actual={columns}, expected={CSV_REQUIRED_COLUMNS[name]}"
            )
        if row_count != expected_rows:
            _fail(f"CSV row-count mismatch for {name}: actual={row_count}, manifest={expected_rows}")
        row_counts[name] = row_count
        rows_by_name[name] = retained
    return row_counts, rows_by_name


def _parse_bool_cell(value: str, context: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    _fail(f"{context} must be literal true or false, got {value!r}")


def _aggregate_status(statuses: Iterable[str]) -> str:
    values = list(statuses)
    if not values:
        _fail("cannot aggregate an empty gate result set")
    for status in values:
        if status not in STATUS_RANK:
            _fail(f"unknown gate status: {status!r}")
    return min(values, key=STATUS_RANK.__getitem__)


def _verify_gate_and_eligibility(
    summary: Mapping[str, Any],
    eligibility_rows: Sequence[Mapping[str, str]],
) -> tuple[str, int]:
    gate_results_raw = _list(
        _required(summary, "gates", "DATA_GATE_SUMMARY.json"),
        "DATA_GATE_SUMMARY.json.gates",
    )
    summary_gates: dict[tuple[str, str], str] = {}
    for index, raw_result in enumerate(gate_results_raw):
        context = f"DATA_GATE_SUMMARY.json.gates[{index}]"
        result = _mapping(raw_result, context)
        gate_id = _required(result, "gate_id", context)
        scope_id = _required(result, "scope_id", context)
        status = _required(result, "status", context)
        if gate_id not in GATE_IDS:
            _fail(f"invalid gate_id at {context}: {gate_id!r}")
        if not isinstance(scope_id, str) or not scope_id.strip():
            _fail(f"invalid scope_id at {context}")
        if status not in STATUS_RANK:
            _fail(f"invalid status at {context}: {status!r}")
        key = (gate_id, scope_id)
        if key in summary_gates:
            _fail(f"duplicate gate scope in summary: {key}")
        summary_gates[key] = status
    missing_gate_ids = sorted(set(GATE_IDS) - {key[0] for key in summary_gates})
    if missing_gate_ids:
        _fail(f"summary omits required gate IDs: {missing_gate_ids}")

    aggregate = _aggregate_status(summary_gates.values())
    if _required(summary, "overall_status", "DATA_GATE_SUMMARY.json") != aggregate:
        _fail(f"overall_status violates frozen precedence; expected {aggregate}")

    matrix_gates: dict[tuple[str, str], str] = {}
    for index, row in enumerate(eligibility_rows):
        context = f"ELIGIBILITY_MATRIX.csv row {index + 2}"
        gate_id, scope_id, status = row["gate_id"], row["scope_id"], row["status"]
        if gate_id not in GATE_IDS or not scope_id or status not in STATUS_RANK:
            _fail(f"invalid gate identity/status in {context}")
        key = (gate_id, scope_id)
        if key in matrix_gates:
            _fail(f"duplicate gate scope in eligibility matrix: {key}")
        matrix_gates[key] = status
        parser_eligible = _parse_bool_cell(row["parser_release_eligible"], f"{context}.parser_release_eligible")
        modeling_eligible = _parse_bool_cell(row["modeling_eligible"], f"{context}.modeling_eligible")
        rul_eligible = _parse_bool_cell(row["rul_eligible"], f"{context}.rul_eligible")
        benchmark_eligible = _parse_bool_cell(
            row["benchmark_l_modeling_eligible"],
            f"{context}.benchmark_l_modeling_eligible",
        )
        if status != "PASS" and parser_eligible:
            _fail(f"{context} unlocks parser with non-PASS status {status}; AMBER is not PASS")
        if modeling_eligible or rul_eligible or benchmark_eligible:
            _fail(f"{context} illegally unlocks modeling or RUL inside P1")
    if matrix_gates != summary_gates:
        missing = sorted(set(summary_gates) - set(matrix_gates))
        extra = sorted(set(matrix_gates) - set(summary_gates))
        differing = sorted(key for key in set(matrix_gates) & set(summary_gates) if matrix_gates[key] != summary_gates[key])
        _fail(f"summary/eligibility gate mismatch; missing={missing}, extra={extra}, differing={differing}")

    return aggregate, len(summary_gates)


def _verify_downstream_locks(
    summary: Mapping[str, Any],
    complete: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> None:
    locks = _mapping(
        _required(summary, "downstream", "DATA_GATE_SUMMARY.json"),
        "DATA_GATE_SUMMARY.json.downstream",
    )
    missing = sorted(set(DOWNSTREAM_LOCK_KEYS) - set(locks))
    if missing:
        _fail(f"schema adapter error: DATA_GATE_SUMMARY.json.downstream missing {missing}")
    for key in DOWNSTREAM_LOCK_KEYS:
        if locks[key] != LOCK_VALUE:
            _fail(f"DATA_GATE_SUMMARY.json.downstream.{key} must equal {LOCK_VALUE}")
    for release_key in (
        "eis_parser_release",
        "transient_parser_release",
        "capacity_eval",
        "esr_soh_eval",
        "rul_survival_eval",
    ):
        if _required(locks, release_key, "DATA_GATE_SUMMARY.json.downstream") != "BLOCKED":
            _fail(f"DATA_GATE_SUMMARY.json.downstream.{release_key} must remain BLOCKED")
    if _required(complete, "downstream_scope", "COMPLETE.json") != LOCK_VALUE:
        _fail("COMPLETE.json.downstream_scope must remain BLOCKED_BY_USER_SCOPE")
    scope_lock = _mapping(
        _required(contract, "scope_lock", "DATA_GATE_CONTRACT.json"),
        "DATA_GATE_CONTRACT.json.scope_lock",
    )
    for key in ("models", "model_evaluation", "rul_generation_or_scoring", "rul", "formal_design_gate", "freeze_b", "agent_topology"):
        if _required(scope_lock, key, "DATA_GATE_CONTRACT.json.scope_lock") != LOCK_VALUE:
            _fail(f"DATA_GATE_CONTRACT.json.scope_lock.{key} must equal {LOCK_VALUE}")


def _verify_target_locks(payload: Mapping[str, Any]) -> None:
    emitted = _list(
        _required(payload, "numeric_targets_emitted", "TARGET_DEFINITIONS.json"),
        "TARGET_DEFINITIONS.json.numeric_targets_emitted",
    )
    if emitted:
        _fail("TARGET_DEFINITIONS.json must emit no numeric targets in P1")
    for target in ("capacity", "ESR", "SOH", "RUL"):
        definition = _mapping(
            _required(payload, target, "TARGET_DEFINITIONS.json"),
            f"TARGET_DEFINITIONS.json.{target}",
        )
        status = _required(definition, "status", f"TARGET_DEFINITIONS.json.{target}")
        if status != "BLOCKED":
            _fail(f"target {target} must remain blocked in P1, got {status!r}")
        if not isinstance(_required(definition, "numeric_values_emitted", f"TARGET_DEFINITIONS.json.{target}"), bool):
            _fail(f"TARGET_DEFINITIONS.json.{target}.numeric_values_emitted must be boolean")
        if definition["numeric_values_emitted"]:
            _fail(f"target {target} illegally emits numeric values in P1")
    failure = _mapping(
        _required(payload, "failure_threshold", "TARGET_DEFINITIONS.json"),
        "TARGET_DEFINITIONS.json.failure_threshold",
    )
    if _required(failure, "status", "TARGET_DEFINITIONS.json.failure_threshold") != "BLOCKED":
        _fail("failure threshold and target proxy must remain BLOCKED")


def _verify_complete(
    output_dir: Path,
    payload: Mapping[str, Any],
    artifact_manifest: Mapping[str, Any],
    expected_overall: str,
) -> None:
    if _required(payload, "schema_version", "COMPLETE.json") != OUTPUT_SCHEMA_VERSION:
        _fail("unsupported COMPLETE.json schema_version")
    if _required(payload, "status", "COMPLETE.json") != "COMPLETE":
        _fail("COMPLETE.json status must equal COMPLETE")
    if _required(payload, "overall_data_gate_status", "COMPLETE.json") != expected_overall:
        _fail("COMPLETE.json overall status disagrees with DATA_GATE_SUMMARY")
    required_artifacts = _list(
        _required(payload, "required_artifacts", "COMPLETE.json"),
        "COMPLETE.json.required_artifacts",
    )
    if len(required_artifacts) != len(set(required_artifacts)) or set(required_artifacts) != REQUIRED_FILES:
        _fail("COMPLETE.json required_artifacts does not exactly match the frozen file set")
    manifest_sha = _strict_sha(
        _required(payload, "artifact_manifest_sha256", "COMPLETE.json"),
        "COMPLETE.json.artifact_manifest_sha256",
    )
    hashes_sha = _strict_sha(
        _required(payload, "artifact_hashes_sha256", "COMPLETE.json"),
        "COMPLETE.json.artifact_hashes_sha256",
    )
    if manifest_sha != _sha256_file(output_dir / "ARTIFACT_MANIFEST.json"):
        _fail("COMPLETE.json does not bind ARTIFACT_MANIFEST.json")
    if hashes_sha != _sha256_file(output_dir / "ARTIFACT_HASHES.sha256"):
        _fail("COMPLETE.json does not bind ARTIFACT_HASHES.sha256")
    declared_manifest_sha = artifact_manifest.get("self_sha256")
    if declared_manifest_sha is not None:
        _fail("ARTIFACT_MANIFEST.json must not claim a self-referential self_sha256")


def _verify_manifest_hashes(
    output_dir: Path,
    entries: Mapping[str, Mapping[str, Any]],
    hashes: Mapping[str, str],
) -> None:
    for name in HASH_LEDGER_FILES:
        observed = _sha256_file(output_dir / name)
        if hashes[name] != observed:
            _fail(f"ARTIFACT_HASHES digest mismatch for {name}")
        if name in entries and entries[name]["sha256"] != observed:
            _fail(f"manifest/hash-ledger disagreement for {name}")


def _csv_nonnegative_int(value: str, context: str) -> int:
    if re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        _fail(f"{context} must be a canonical non-negative integer")
    return int(value)


def _verify_summary_row_counts(
    summary: Mapping[str, Any],
    contract: Mapping[str, Any],
    actual: Mapping[str, int],
) -> None:
    counts = _mapping(
        _required(summary, "observed_counts", "DATA_GATE_SUMMARY.json"),
        "DATA_GATE_SUMMARY.json.observed_counts",
    )
    if _required(summary, "counts", "DATA_GATE_SUMMARY.json") != counts:
        _fail("DATA_GATE_SUMMARY counts and observed_counts aliases disagree")
    expected_counts = _mapping(
        _required(
            _mapping(_required(contract, "base_contract", "DATA_GATE_CONTRACT.json"), "base_contract"),
            "content",
            "base_contract",
        ),
        "base_contract.content",
    )
    expected_counts = _mapping(
        _required(expected_counts, "expected_counts", "base_contract.content"),
        "base_contract.content.expected_counts",
    )
    provisional_units = _strict_int(
        _required(expected_counts, "provisional_eis_units", "expected_counts"),
        "expected_counts.provisional_eis_units",
    )
    event_slots = _strict_int(_required(counts, "eis_event_slots", "observed_counts"), "counts.eis_event_slots")
    raw_slots = _strict_int(_required(counts, "raw_inner_slots", "observed_counts"), "counts.raw_inner_slots")
    nonempty = _strict_int(_required(counts, "nonempty_matrix_pairs", "observed_counts"), "counts.nonempty_matrix_pairs")
    transient_arrays = _strict_int(_required(counts, "transient_signal_arrays", "observed_counts"), "counts.transient_signal_arrays")
    duplicate_candidates = _strict_int(_required(counts, "duplicate_candidates", "observed_counts"), "counts.duplicate_candidates")
    expected_relations = {
        "REFERENCE_LINKAGE_LEDGER.csv": raw_slots,
        "EIS_EVENT_LEDGER.csv": event_slots,
        "COLUMN_FREQUENCY_LEDGER.csv": nonempty,
        "TRANSIENT_ALIGNMENT_LEDGER.csv": transient_arrays,
        "MISSINGNESS_LEDGER.csv": nonempty + transient_arrays + 3,
        "UNIT_IDENTITY_LEDGER.csv": provisional_units,
        "CONTENT_SIGNATURE_LEDGER.csv": nonempty + transient_arrays + 3,
        "DUPLICATE_CANDIDATE_LEDGER.csv": duplicate_candidates,
        "TARGET_TRAJECTORY_LEDGER.csv": provisional_units,
        "OUTCOME_LEDGER.csv": provisional_units,
        "ELIGIBILITY_MATRIX.csv": len(_list(_required(summary, "gates", "summary"), "summary.gates")),
    }
    for name, expected in expected_relations.items():
        if actual[name] != expected:
            _fail(f"semantic CSV row-count mismatch for {name}: actual={actual[name]}, expected={expected}")


def _verify_reconciliation(summary: Mapping[str, Any]) -> None:
    counts = _mapping(
        _required(summary, "observed_counts", "DATA_GATE_SUMMARY.json"),
        "DATA_GATE_SUMMARY.json.observed_counts",
    )
    for key in ("raw_inner_slots", "nonempty_matrix_pairs", "paired_canonical_empties"):
        _strict_int(_required(counts, key, "DATA_GATE_SUMMARY.json.observed_counts"), f"observed_counts.{key}")
    raw = counts["raw_inner_slots"]
    nonempty = counts["nonempty_matrix_pairs"]
    structural_empty = counts["paired_canonical_empties"]
    quarantined = _strict_int(
        _required(counts, "quarantined_raw_slots", "DATA_GATE_SUMMARY.json.observed_counts"),
        "observed_counts.quarantined_raw_slots",
    )
    eligible = _strict_int(
        _required(counts, "eligible_raw_slots", "DATA_GATE_SUMMARY.json.observed_counts"),
        "observed_counts.eligible_raw_slots",
    )
    if raw != eligible + quarantined + structural_empty:
        _fail("slot reconciliation fails raw = eligible + quarantined + structural_empty")
    if nonempty != eligible + quarantined:
        _fail("nonempty matrix pairs must equal eligible + quarantined reference slots")
    reconciliation = _mapping(
        _required(summary, "raw_reconciliation", "DATA_GATE_SUMMARY.json"),
        "DATA_GATE_SUMMARY.json.raw_reconciliation",
    )
    if reconciliation != {
        "formula": "raw=eligible+quarantined+structural_empty",
        "passed": True,
    }:
        _fail("DATA_GATE_SUMMARY raw_reconciliation is not the frozen passing identity")


def _verify_golden_counts(
    summary: Mapping[str, Any],
    rows_by_name: Mapping[str, Sequence[Mapping[str, str]]],
) -> None:
    counts = _mapping(
        _required(summary, "observed_counts", "DATA_GATE_SUMMARY.json"),
        "DATA_GATE_SUMMARY.json.observed_counts",
    )
    missing = sorted(set(GOLDEN_REAL_DATA_COUNTS) - set(counts))
    if missing:
        _fail(f"golden real-data adapter keys missing from observed_counts: {missing}")
    for key, expected in GOLDEN_REAL_DATA_COUNTS.items():
        observed = _strict_int(counts[key], f"observed_counts.{key}")
        if observed != expected:
            _fail(f"golden count mismatch for {key}: observed={observed}, expected={expected}")
    shape_counts = _mapping(_required(counts, "eis_shape_counts", "observed_counts"), "observed_counts.eis_shape_counts")
    if shape_counts != {"[58,18]": 1, "[59,18]": 8_834}:
        _fail(f"golden EIS shape counts mismatch: {shape_counts}")
    nonchron = _mapping(
        _required(counts, "raw_order_nonchronological_unit_events", "observed_counts"),
        "observed_counts.raw_order_nonchronological_unit_events",
    )
    if set(nonchron) != {"ES10", "ES12", "ES14"}:
        _fail("golden nonchronological count map must contain exactly ES10/ES12/ES14")
    if sum(_strict_int(value, f"nonchronological.{key}") for key, value in nonchron.items()) != 39:
        _fail("golden nonchronological unit-event total must equal 39")

    frequency_rows = rows_by_name["COLUMN_FREQUENCY_LEDGER.csv"]
    observed_shapes: dict[str, int] = {}
    for index, row in enumerate(frequency_rows, start=2):
        shape = row["canonical_shape"]
        observed_shapes[shape] = observed_shapes.get(shape, 0) + 1
        if _csv_nonnegative_int(row["nan_count"], f"frequency row {index}.nan_count") != 0:
            _fail("golden EIS ledger contains NaN")
        if _csv_nonnegative_int(row["inf_count"], f"frequency row {index}.inf_count") != 0:
            _fail("golden EIS ledger contains Inf")
    if observed_shapes != shape_counts:
        _fail("golden shape summary disagrees with COLUMN_FREQUENCY_LEDGER")
    exact_eis = sum(
        row["candidate_type"] == "exact_duplicate_candidate" and row["content_type"] == "eis_matrix"
        for row in rows_by_name["DUPLICATE_CANDIDATE_LEDGER.csv"]
    )
    if exact_eis != 0:
        _fail("golden duplicate ledger contains an exact EIS matrix duplicate")


def _verify_ledger_truth(
    summary: Mapping[str, Any],
    rows_by_name: Mapping[str, Sequence[Mapping[str, str]]],
) -> None:
    counts = _mapping(_required(summary, "observed_counts", "summary"), "summary.observed_counts")
    linkage = rows_by_name["REFERENCE_LINKAGE_LEDGER.csv"]
    slot_classes = {"eligible": 0, "quarantined": 0, "structural_empty": 0}
    for index, row in enumerate(linkage, start=2):
        slot_class = row["raw_slot_class"]
        if slot_class not in slot_classes:
            _fail(f"REFERENCE_LINKAGE_LEDGER row {index} has invalid raw_slot_class {slot_class!r}")
        slot_classes[slot_class] += 1
    for summary_key, class_key in (
        ("eligible_raw_slots", "eligible"),
        ("quarantined_raw_slots", "quarantined"),
        ("paired_canonical_empties", "structural_empty"),
    ):
        if _strict_int(_required(counts, summary_key, "observed_counts"), f"counts.{summary_key}") != slot_classes[class_key]:
            _fail(f"REFERENCE_LINKAGE_LEDGER disagrees with {summary_key}")

    frequency = rows_by_name["COLUMN_FREQUENCY_LEDGER.csv"]
    nonfinite = sum(
        _csv_nonnegative_int(row["nan_count"], "frequency.nan_count")
        + _csv_nonnegative_int(row["inf_count"], "frequency.inf_count")
        for row in frequency
    )
    if nonfinite != _strict_int(_required(counts, "eis_nonfinite_count", "observed_counts"), "counts.eis_nonfinite_count"):
        _fail("COLUMN_FREQUENCY_LEDGER nonfinite count disagrees with summary")

    duplicate_rows = rows_by_name["DUPLICATE_CANDIDATE_LEDGER.csv"]
    if len(duplicate_rows) != _strict_int(_required(counts, "duplicate_candidates", "observed_counts"), "counts.duplicate_candidates"):
        _fail("DUPLICATE_CANDIDATE_LEDGER count disagrees with summary")
    for index, row in enumerate(duplicate_rows, start=2):
        if row["resolution"] != "quarantined_unresolved":
            _fail(f"duplicate candidate row {index} is not unresolved quarantine")
        if _parse_bool_cell(row["split_group_created"], f"duplicate row {index}.split_group_created"):
            _fail(f"duplicate candidate row {index} illegally creates a split group")

    for name in ("TRANSIENT_ALIGNMENT_LEDGER.csv", "REPAIR_QUARANTINE_LEDGER.csv"):
        for index, row in enumerate(rows_by_name[name], start=2):
            if _parse_bool_cell(row["applied_repair"], f"{name} row {index}.applied_repair"):
                _fail(f"{name} row {index} applies a repair inside P1")

    for index, row in enumerate(rows_by_name["UNIT_IDENTITY_LEDGER.csv"], start=2):
        if row["stable_physical_id_status"] != "BLOCKED" or row["split_group_status"] != "BLOCKED":
            _fail(f"UNIT_IDENTITY_LEDGER row {index} illegally resolves identity/split group")
        if not _parse_bool_cell(row["provenance_only_group"], f"identity row {index}.provenance_only_group"):
            _fail(f"UNIT_IDENTITY_LEDGER row {index} is not marked provenance-only")

    for index, row in enumerate(rows_by_name["TARGET_TRAJECTORY_LEDGER.csv"], start=2):
        for key in ("capacity_target_status", "esr_target_status", "soh_target_status", "rul_target_status"):
            if row[key] != "BLOCKED":
                _fail(f"TARGET_TRAJECTORY_LEDGER row {index} illegally resolves {key}")
        if _parse_bool_cell(row["numeric_target_emitted"], f"target row {index}.numeric_target_emitted"):
            _fail(f"TARGET_TRAJECTORY_LEDGER row {index} emits a numeric target")

    for index, row in enumerate(rows_by_name["OUTCOME_LEDGER.csv"], start=2):
        if row["outcome_status"] != "BLOCKED":
            _fail(f"OUTCOME_LEDGER row {index} illegally resolves outcome/RUL")
        if _parse_bool_cell(row["sequence_end_is_eol"], f"outcome row {index}.sequence_end_is_eol"):
            _fail(f"OUTCOME_LEDGER row {index} treats sequence end as EOL")


def _verify_schema_tests(payload: Mapping[str, Any], aggregate_status: str) -> None:
    tests = _list(_required(payload, "tests", "SCHEMA_TEST_RESULTS.json"), "SCHEMA_TEST_RESULTS.json.tests")
    if not tests:
        _fail("SCHEMA_TEST_RESULTS.json.tests must not be empty")
    saw_fail = False
    seen: set[str] = set()
    for index, raw_test in enumerate(tests):
        context = f"SCHEMA_TEST_RESULTS.json.tests[{index}]"
        test = _mapping(raw_test, context)
        test_id = _required(test, "test_id", context)
        status = _required(test, "status", context)
        if not isinstance(test_id, str) or not test_id or test_id in seen:
            _fail(f"invalid or duplicate schema test_id at {context}")
        seen.add(test_id)
        if status not in {"PASS", "FAIL"}:
            _fail(f"invalid schema-test status at {context}: {status!r}")
        saw_fail |= status == "FAIL"
    if saw_fail and aggregate_status != "FAIL":
        _fail("a failed schema test is masked by a non-FAIL aggregate status")


def verify_data_gate_output(
    output_dir: str | Path,
    *,
    expected_source_manifest: str | Path | None = None,
    expected_code: str | Path | None = None,
    golden_real_data: bool = False,
) -> dict[str, Any]:
    """Verify an existing P1 output bundle without mutating it.

    ``expected_source_manifest`` and ``expected_code`` are optional external
    anchors.  Their hashes are compared with the mandatory four-way lineage
    embedded in the bundle.  ``golden_real_data`` additionally enforces the
    independently probed Benchmark-L counts; it should be disabled for small
    synthetic generator fixtures.
    """

    root = Path(output_dir)
    source_manifest_path = None if expected_source_manifest is None else Path(expected_source_manifest)
    code_path = None if expected_code is None else Path(expected_code)
    _validate_file_graph(root)

    payloads = {name: _load_json(root / name) for name in REQUIRED_JSON}
    lineage = _verify_lineage(
        payloads,
        expected_source_manifest=source_manifest_path,
        expected_code=code_path,
    )

    artifact_manifest = payloads["ARTIFACT_MANIFEST.json"]
    entries = _parse_artifact_manifest(root, artifact_manifest)
    hashes = _parse_hash_ledger(root / "ARTIFACT_HASHES.sha256")
    _verify_manifest_hashes(root, entries, hashes)

    row_counts, rows_by_name = _verify_csv_artifacts(root, entries)
    summary = payloads["DATA_GATE_SUMMARY.json"]
    _verify_summary_row_counts(summary, payloads["DATA_GATE_CONTRACT.json"], row_counts)
    _verify_reconciliation(summary)
    aggregate_status, gate_scope_count = _verify_gate_and_eligibility(
        summary,
        rows_by_name["ELIGIBILITY_MATRIX.csv"],
    )
    _verify_complete(root, payloads["COMPLETE.json"], artifact_manifest, aggregate_status)
    _verify_target_locks(payloads["TARGET_DEFINITIONS.json"])
    _verify_downstream_locks(
        summary,
        payloads["COMPLETE.json"],
        payloads["DATA_GATE_CONTRACT.json"],
    )
    _verify_ledger_truth(summary, rows_by_name)
    _verify_schema_tests(payloads["SCHEMA_TEST_RESULTS.json"], aggregate_status)
    if golden_real_data:
        _verify_golden_counts(summary, rows_by_name)

    return {
        "schema_version": SCHEMA_VERSION,
        "verification_status": "PASS",
        "bundle_status": aggregate_status,
        "artifact_file_count": len(REQUIRED_FILES),
        "scientific_artifact_count": len(SCIENTIFIC_ARTIFACTS),
        "gate_scope_count": gate_scope_count,
        "golden_real_data_counts_checked": golden_real_data,
        "lineage": lineage,
        "downstream_unlocks": {
            "modeling": False,
            "rul": False,
            "benchmark_l_modeling": False,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--expected-source-manifest", type=Path)
    parser.add_argument("--expected-code", type=Path)
    parser.add_argument("--golden-real-data", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = verify_data_gate_output(
            args.output_dir,
            expected_source_manifest=args.expected_source_manifest,
            expected_code=args.expected_code,
            golden_real_data=args.golden_real_data,
        )
    except DataGateVerificationError as exc:
        print(json.dumps({"verification_status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
