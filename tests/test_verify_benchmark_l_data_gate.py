from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import pytest

from experiments.audit_cap.verify_benchmark_l_data_gate import (
    CSV_REQUIRED_COLUMNS,
    DOWNSTREAM_LOCK_KEYS,
    FROZEN_AMENDMENT_SHA256,
    FROZEN_CONTRACT_SHA256,
    GATE_IDS,
    LOCK_VALUE,
    OUTPUT_SCHEMA_VERSION,
    REQUIRED_CSV,
    REQUIRED_FILES,
    SCIENTIFIC_ARTIFACTS,
    DataGateVerificationError,
    main,
    verify_data_gate_output,
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4096), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _csv_metadata(path: Path) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames is not None
        rows = sum(1 for _ in reader)
    return list(reader.fieldnames), rows


def _locks() -> dict[str, str]:
    return {key: LOCK_VALUE for key in DOWNSTREAM_LOCK_KEYS}


def _reseal(root: Path, lineage: dict[str, str]) -> None:
    overall_status = json.loads((root / "DATA_GATE_SUMMARY.json").read_text(encoding="utf-8"))["overall_status"]
    entries: list[dict[str, object]] = []
    for name in sorted(SCIENTIFIC_ARTIFACTS):
        path = root / name
        if name.endswith(".csv"):
            columns, row_count = _csv_metadata(path)
            entry: dict[str, object] = {
                "name": name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha(path),
                "columns": columns,
                "row_count": row_count,
            }
        else:
            entry = {
                "name": name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha(path),
            }
        entries.append(entry)
    _write_json(
        root / "ARTIFACT_MANIFEST.json",
        {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            **lineage,
            "stable_artifacts": entries,
        },
    )

    hash_names = sorted((*SCIENTIFIC_ARTIFACTS, "ARTIFACT_MANIFEST.json"))
    (root / "ARTIFACT_HASHES.sha256").write_text(
        "".join(f"{_sha(root / name)}  {name}\n" for name in hash_names),
        encoding="ascii",
    )
    _write_json(
        root / "COMPLETE.json",
        {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "status": "COMPLETE",
            "overall_data_gate_status": overall_status,
            "artifact_manifest_sha256": _sha(root / "ARTIFACT_MANIFEST.json"),
            "artifact_hashes_sha256": _sha(root / "ARTIFACT_HASHES.sha256"),
            **lineage,
            "required_artifacts": sorted(REQUIRED_FILES),
            "downstream_scope": LOCK_VALUE,
        },
    )


def _gate_results() -> list[dict[str, str]]:
    results = []
    for gate_id in GATE_IDS:
        status = "BLOCKED" if gate_id in {"G05", "G06", "G07", "G08", "G09"} else "PASS"
        results.append(
            {
                "gate_id": gate_id,
                "scope_id": "raw_eis" if gate_id not in {"G04", "G05", "G07", "G08", "G09"} else "global",
                "status": status,
                "evidence": "synthetic fixture",
            }
        )
    return results


def _build_bundle(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    root = tmp_path / "gate-output"
    root.mkdir(parents=True)
    source_anchor = tmp_path / "source-manifest.json"
    source_anchor.write_text('{"frozen":true}\n', encoding="utf-8")
    code_anchor = tmp_path / "parser.py"
    code_anchor.write_text("# frozen parser\n", encoding="utf-8")
    lineage = {
        "contract_sha256": FROZEN_CONTRACT_SHA256,
        "amendment_sha256": FROZEN_AMENDMENT_SHA256,
        "integrity_manifest_sha256": _sha(source_anchor),
        "code_sha256": _sha(code_anchor),
    }

    _write_json(
        root / "DATA_GATE_CONTRACT.json",
        {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "base_contract": {
                "sha256": FROZEN_CONTRACT_SHA256,
                "content": {
                    "status_precedence": ["FAIL", "BLOCKED", "AMBER", "PASS"],
                    "expected_counts": {"provisional_eis_units": 1},
                },
            },
            "amendment": {"sha256": FROZEN_AMENDMENT_SHA256, "content": {}},
            "scope_lock": {
                "models": LOCK_VALUE,
                "model_evaluation": LOCK_VALUE,
                "rul_generation_or_scoring": LOCK_VALUE,
                "rul": LOCK_VALUE,
                "formal_design_gate": LOCK_VALUE,
                "freeze_b": LOCK_VALUE,
                "agent_topology": LOCK_VALUE,
            },
        },
    )
    _write_json(
        root / "DATA_MANIFEST.json",
        {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "integrity_manifest_sha256": lineage["integrity_manifest_sha256"],
            "sources": [],
        },
    )
    _write_json(
        root / "TARGET_DEFINITIONS.json",
        {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "numeric_targets_emitted": [],
            **{
                target: {"status": "BLOCKED", "numeric_values_emitted": False}
                for target in ("capacity", "ESR", "SOH", "RUL")
            },
            "failure_threshold": {"status": "BLOCKED"},
        },
    )
    _write_json(
        root / "SCHEMA_TEST_RESULTS.json",
        {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "tests": [{"test_id": "synthetic", "status": "PASS"}],
        },
    )

    gate_results = _gate_results()
    eligibility_rows: list[dict[str, object]] = []
    for row in gate_results:
        eligibility_rows.append(
            {
                "gate_id": row["gate_id"],
                "scope_id": row["scope_id"],
                "status": row["status"],
                "evidence": row["evidence"],
                "unlocks": "none",
                "parser_release_eligible": "false",
                "modeling_eligible": "false",
                "rul_eligible": "false",
                "benchmark_l_modeling_eligible": "false",
            }
        )

    rows_by_name: dict[str, list[dict[str, object]]] = {
        "REFERENCE_LINKAGE_LEDGER.csv": [
            {
                "item_id": "eis:SYN:U1:0:0",
                "condition": "SYN",
                "provisional_unit": "U1",
                "event_index": 0,
                "raw_replicate_index": 0,
                "pair_status": "paired_nonempty",
                "raw_slot_class": "eligible",
            },
            {
                "item_id": "eis:SYN:U1:0:1",
                "condition": "SYN",
                "provisional_unit": "U1",
                "event_index": 0,
                "raw_replicate_index": 1,
                "pair_status": "paired_canonical_empty",
                "raw_slot_class": "structural_empty",
            },
        ],
        "EIS_EVENT_LEDGER.csv": [
            {
                "condition": "SYN",
                "provisional_unit": "U1",
                "event_index": 0,
                "raw_slot_count": 2,
                "eligible_nonempty_count": 1,
                "quarantined_count": 0,
                "structural_empty_count": 1,
                "nonempty_pair_count": 1,
                "raw_order_chronological": "true",
                "status": "PASS",
            }
        ],
        "COLUMN_FREQUENCY_LEDGER.csv": [
            {
                "item_id": "sha:SYN:U1:0:0",
                "canonical_shape": "[59,18]",
                "n_raw_rows": 59,
                "n_frequency": 51,
                "n_preamble": 8,
                "invalid_frequency_count": 0,
                "nan_count": 0,
                "inf_count": 0,
                "status": "PASS",
            }
        ],
        "TRANSIENT_ALIGNMENT_LEDGER.csv": [
            {
                "condition": "SYN",
                "provisional_unit": "U1",
                "item_id": "transient:SYN:U1:VL",
                "timestamp_rows": 2,
                "signal_rows": 2,
                "alignment_status": "PASS",
                "applied_repair": "false",
            }
        ],
        "MISSINGNESS_LEDGER.csv": [
            {
                "item_id": f"missing:{index}",
                "modality": "eis",
                "condition": "SYN",
                "provisional_unit": "U1",
                "element_count": 1062,
                "nan_count": 0,
                "inf_count": 0,
                "nan_mask_sha256": "0" * 64,
            }
            for index in range(5)
        ],
        "UNIT_IDENTITY_LEDGER.csv": [
            {
                "condition": "SYN",
                "provisional_unit": "U1",
                "provenance_only_group": "true",
                "stable_physical_id_status": "BLOCKED",
                "split_group_status": "BLOCKED",
            }
        ],
        "CONTENT_SIGNATURE_LEDGER.csv": [
            {
                "item_id": f"sha:SYN:U1:0:{index}",
                "content_type": "eis_matrix" if index == 0 else "transient_timestamp",
                "dtype": "float64",
                "shape": "[59,18]",
                "content_sha256": "1" * 64,
            }
            for index in range(5)
        ],
        "DUPLICATE_CANDIDATE_LEDGER.csv": [],
        "REPAIR_QUARANTINE_LEDGER.csv": [
            {
                "scope_id": "identity",
                "reason": "physical ID unavailable",
                "applied_repair": "false",
                "resolution": "quarantined_unresolved",
            }
        ],
        "TARGET_TRAJECTORY_LEDGER.csv": [
            {
                "condition": "SYN",
                "provisional_unit": "U1",
                "capacity_target_status": "BLOCKED",
                "esr_target_status": "BLOCKED",
                "soh_target_status": "BLOCKED",
                "rul_target_status": "BLOCKED",
                "numeric_target_emitted": "false",
            }
        ],
        "OUTCOME_LEDGER.csv": [
            {
                "condition": "SYN",
                "provisional_unit": "U1",
                "sequence_end_is_eol": "false",
                "outcome_status": "BLOCKED",
            }
        ],
        "ELIGIBILITY_MATRIX.csv": eligibility_rows,
    }
    for name in REQUIRED_CSV:
        _write_csv(root / name, CSV_REQUIRED_COLUMNS[name], rows_by_name[name])
    observed_counts = {
        "eis_event_slots": 1,
        "raw_inner_slots": 2,
        "nonempty_matrix_pairs": 1,
        "paired_canonical_empties": 1,
        "eligible_raw_slots": 1,
        "quarantined_raw_slots": 0,
        "raw_order_nonchronological_unit_events": {"SYN": 0},
        "eis_shape_counts": {"[59,18]": 1},
        "eis_nonfinite_count": 0,
        "exact_eis_matrix_duplicate_candidates": 0,
        "transient_signal_arrays": 1,
        "duplicate_candidates": 0,
    }
    _write_json(
        root / "DATA_GATE_SUMMARY.json",
        {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "gates": gate_results,
            "overall_status": "BLOCKED",
            "counts": observed_counts,
            "observed_counts": observed_counts,
            "raw_reconciliation": {
                "formula": "raw=eligible+quarantined+structural_empty",
                "passed": True,
            },
            "downstream": {
                **_locks(),
                "eis_parser_release": "BLOCKED",
                "transient_parser_release": "BLOCKED",
                "capacity_eval": "BLOCKED",
                "esr_soh_eval": "BLOCKED",
                "rul_survival_eval": "BLOCKED",
            },
        },
    )
    (root / "DATA_GATE_REPORT.md").write_text(
        "# Synthetic P1 report\n\nNo model or RUL was run.\n",
        encoding="utf-8",
    )
    _reseal(root, lineage)
    return root, source_anchor, code_anchor, lineage


def test_valid_bundle_passes_read_only_verification(tmp_path: Path) -> None:
    root, source_anchor, code_anchor, lineage = _build_bundle(tmp_path)
    before = {path.name: (path.stat().st_size, _sha(path)) for path in root.iterdir()}

    result = verify_data_gate_output(
        root,
        expected_source_manifest=source_anchor,
        expected_code=code_anchor,
    )

    after = {path.name: (path.stat().st_size, _sha(path)) for path in root.iterdir()}
    assert before == after
    assert result["verification_status"] == "PASS"
    assert result["bundle_status"] == "BLOCKED"
    assert result["lineage"] == lineage
    assert result["downstream_unlocks"] == {
        "modeling": False,
        "rul": False,
        "benchmark_l_modeling": False,
    }


def test_rejects_symlink_artifact_before_hash_checks(tmp_path: Path) -> None:
    root, _, _, _ = _build_bundle(tmp_path)
    report = root / "DATA_GATE_REPORT.md"
    external = tmp_path / "external.md"
    external.write_bytes(report.read_bytes())
    report.unlink()
    report.symlink_to(external)

    with pytest.raises(DataGateVerificationError, match="symlink artifact"):
        verify_data_gate_output(root)


def test_rejects_tampering_and_missing_files(tmp_path: Path) -> None:
    root, _, _, _ = _build_bundle(tmp_path)
    with (root / "DATA_GATE_REPORT.md").open("a", encoding="utf-8") as stream:
        stream.write("tampered\n")
    with pytest.raises(DataGateVerificationError, match="byte-count mismatch"):
        verify_data_gate_output(root)

    root, _, _, _ = _build_bundle(tmp_path / "second")
    (root / "OUTCOME_LEDGER.csv").unlink()
    with pytest.raises(DataGateVerificationError, match="file set mismatch"):
        verify_data_gate_output(root)


def test_lineage_schema_is_mandatory_and_external_anchors_are_checked(tmp_path: Path) -> None:
    root, source_anchor, code_anchor, _ = _build_bundle(tmp_path)
    manifest = json.loads((root / "ARTIFACT_MANIFEST.json").read_text(encoding="utf-8"))
    del manifest["code_sha256"]
    _write_json(root / "ARTIFACT_MANIFEST.json", manifest)
    with pytest.raises(DataGateVerificationError, match="code_sha256"):
        verify_data_gate_output(root)

    root, source_anchor, code_anchor, _ = _build_bundle(tmp_path / "second")
    code_anchor.write_text("# mutated parser\n", encoding="utf-8")
    with pytest.raises(DataGateVerificationError, match="parser code lineage"):
        verify_data_gate_output(root, expected_source_manifest=source_anchor, expected_code=code_anchor)


def test_amber_cannot_unlock_parser_and_modeling_never_unlocks(tmp_path: Path) -> None:
    root, _, _, lineage = _build_bundle(tmp_path)
    matrix = root / "ELIGIBILITY_MATRIX.csv"
    with matrix.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[5]["status"] = "AMBER"
    rows[5]["parser_release_eligible"] = "true"
    _write_csv(matrix, CSV_REQUIRED_COLUMNS[matrix.name], rows)
    summary = json.loads((root / "DATA_GATE_SUMMARY.json").read_text(encoding="utf-8"))
    summary["gates"][5]["status"] = "AMBER"
    _write_json(root / "DATA_GATE_SUMMARY.json", summary)
    _reseal(root, lineage)
    with pytest.raises(DataGateVerificationError, match="AMBER is not PASS"):
        verify_data_gate_output(root)

    root, _, _, lineage = _build_bundle(tmp_path / "second")
    summary = json.loads((root / "DATA_GATE_SUMMARY.json").read_text(encoding="utf-8"))
    summary["downstream"]["benchmark_l_modeling"] = "UNLOCKED"
    _write_json(root / "DATA_GATE_SUMMARY.json", summary)
    _reseal(root, lineage)
    with pytest.raises(DataGateVerificationError, match="benchmark_l_modeling must equal"):
        verify_data_gate_output(root)


def test_frozen_precedence_and_stable_columns_are_enforced(tmp_path: Path) -> None:
    root, _, _, lineage = _build_bundle(tmp_path)
    summary = json.loads((root / "DATA_GATE_SUMMARY.json").read_text(encoding="utf-8"))
    summary["overall_status"] = "PASS"
    _write_json(root / "DATA_GATE_SUMMARY.json", summary)
    _reseal(root, lineage)
    with pytest.raises(DataGateVerificationError, match="frozen precedence"):
        verify_data_gate_output(root)

    root, _, _, lineage = _build_bundle(tmp_path / "second")
    matrix = root / "UNIT_IDENTITY_LEDGER.csv"
    with matrix.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    _write_csv(
        matrix,
        ("condition", "provisional_unit", "stable_physical_id_status"),
        [{key: row[key] for key in ("condition", "provisional_unit", "stable_physical_id_status")} for row in rows],
    )
    _reseal(root, lineage)
    with pytest.raises(DataGateVerificationError, match="frozen v1.1 columns"):
        verify_data_gate_output(root)


def test_golden_real_data_mode_is_optional_but_strict(tmp_path: Path) -> None:
    root, _, _, _ = _build_bundle(tmp_path)
    verify_data_gate_output(root, golden_real_data=False)
    with pytest.raises(DataGateVerificationError, match="golden count mismatch"):
        verify_data_gate_output(root, golden_real_data=True)


def test_cli_returns_nonzero_without_writing_on_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _, _, _ = _build_bundle(tmp_path)
    (root / "COMPLETE.json").unlink()

    assert main([os.fspath(root)]) == 1
    response = json.loads(capsys.readouterr().out)
    assert response["verification_status"] == "FAIL"
