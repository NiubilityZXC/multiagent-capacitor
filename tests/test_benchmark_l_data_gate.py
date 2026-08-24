from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from experiments.audit_cap.benchmark_l_data_gate import (  # noqa: E402
    CANONICAL_COLUMNS,
    DataGateError,
    EXPECTED_RAW_TOKENS,
    REQUIRED_CSV,
    REQUIRED_JSON,
    _array_signature,
    _sha_file,
    run_data_gate,
)


def _dump_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _char_matrix(strings: list[str]) -> np.ndarray:
    width = max(len(value) for value in strings)
    result = np.zeros((width, len(strings)), dtype=np.uint16)
    for column, value in enumerate(strings):
        result[: len(value), column] = [ord(char) for char in value]
    return result


def _canonical_matrix(unique: float) -> np.ndarray:
    frequencies = np.array([0.0, 100.0, 10.0, 1.0], dtype=np.float64)
    matrix = np.zeros((4, 18), dtype=np.float64)
    matrix[:, 0] = frequencies
    matrix[:, 5] = np.array([0.1, 0.2, 0.3, 0.4])
    matrix[:, 10] = unique
    matrix[:, 11] = 12.0
    positive = frequencies > 0
    f = frequencies[positive]
    re_z = 1.0 + unique * 0.01 + np.array([0.2, 0.4, 0.8])
    neg_im_z = np.array([0.3, 0.7, 1.4]) + unique * 0.001
    denom = re_z**2 + neg_im_z**2
    matrix[positive, 1] = re_z
    matrix[positive, 2] = neg_im_z
    matrix[positive, 3] = np.hypot(re_z, neg_im_z)
    matrix[positive, 4] = np.degrees(np.arctan2(-neg_im_z, re_z))
    matrix[positive, 8] = 1e6 / (2 * np.pi * f * neg_im_z)
    matrix[positive, 9] = 1e6 * (neg_im_z / denom) / (2 * np.pi * f)
    matrix[positive, 14] = re_z / denom
    matrix[positive, 15] = neg_im_z / denom
    matrix[positive, 16] = 1.0 / matrix[positive, 3]
    matrix[positive, 17] = -matrix[positive, 4]
    return matrix


def _signal(rows: int, unique: float, kind: str) -> np.ndarray:
    result = np.full((rows, 5), np.nan, dtype=np.float64)
    for row in range(rows):
        finite_length = 2 + ((row + (kind == "VO")) % 3)
        result[row, :finite_length] = unique + row + np.arange(finite_length) / 10
    return result


def _write_mat(
    path: Path,
    condition: str,
    *,
    asymmetric_empty: bool = False,
    bad_outer_reference: bool = False,
    unsafe_storage: str | None = None,
) -> None:
    counter = 0

    with h5py.File(path, "w") as h5_file:
        refs = h5_file.create_group("#refs#")
        root = h5_file.create_group(condition)
        eis = root.create_group("EIS_Data")

        def name() -> str:
            nonlocal counter
            counter += 1
            return f"r{counter:04d}"

        def char(strings: list[str]):
            target = refs.create_dataset(name(), data=_char_matrix(strings))
            target.attrs["MATLAB_class"] = np.bytes_("char")
            return target

        def cell(target_refs: list[object]):
            target = refs.create_dataset(name(), shape=(len(target_refs), 1), dtype=h5py.ref_dtype)
            target.attrs["MATLAB_class"] = np.bytes_("cell")
            for index, reference in enumerate(target_refs):
                target[index, 0] = reference
            return target

        empty = refs.create_dataset(name(), data=np.array([0, 0], dtype=np.uint64))
        empty.attrs["MATLAB_class"] = np.bytes_("canonical empty")

        table = eis.create_dataset("EIS_Reference_Table", shape=(4, 2), dtype=h5py.ref_dtype)
        for row, values in enumerate(
            (["01/01/2020", "01/02/2020"], ["12:00 PM", "12:00 PM"], ["12:05 PM", "12:05 PM"], ["0", "1"])
        ):
            for event, value in enumerate(values):
                table[row, event] = char([value]).ref

        unit_label = f"{condition}C1"
        measurement = eis.create_group(unit_label).create_group("EIS_Measurement")
        header_outer = measurement.create_dataset("Header", shape=(2, 1), dtype=h5py.ref_dtype)
        data_outer = measurement.create_dataset("Data", shape=(2, 1), dtype=h5py.ref_dtype)
        column_outer = measurement.create_dataset("ColumNames", shape=(2, 1), dtype=h5py.ref_dtype)
        condition_offset = {"ES10": 10.0, "ES12": 20.0, "ES14": 30.0}[condition]

        for event in range(2):
            if event == 0:
                times = ["01/01/2020 12:05:00", "01/01/2020 12:00:00"]
                header_refs: list[object] = []
                data_refs: list[object] = []
                for replicate, timestamp in enumerate(times):
                    header = char(
                        [
                            "EC-Lab ASCII FILE",
                            "Potentio Electrochemical Impedance Spectroscopy",
                            "Run on channel : 1 (SN 3864)",
                            f"Acquisition started on : {timestamp}",
                            "Saved on :",
                            "Device : SP-150 (SN 0020)",
                        ]
                    )
                    matrix = _canonical_matrix(condition_offset + event * 3 + replicate)
                    data = refs.create_dataset(name(), data=matrix.T)
                    data.attrs["MATLAB_class"] = np.bytes_("double")
                    header_refs.append(header.ref)
                    data_refs.append(data.ref)
            else:
                header = char(
                    [
                        "EC-Lab ASCII FILE",
                        "Potentio Electrochemical Impedance Spectroscopy",
                        "Run on channel : 1 (SN 3864)",
                        "Acquisition started on : 01/02/2020 12:00:00",
                        "Saved on :",
                        "Device : SP-150 (SN 0020)",
                    ]
                )
                matrix = _canonical_matrix(condition_offset + 9)
                data = refs.create_dataset(name(), data=matrix.T)
                data.attrs["MATLAB_class"] = np.bytes_("double")
                header_refs = [empty.ref, header.ref]
                data_refs = [empty.ref, data.ref]
                if asymmetric_empty and condition == "ES10":
                    header_refs[0] = header.ref
            header_outer[event, 0] = cell(header_refs).ref
            data_outer[event, 0] = cell(data_refs).ref
            column_outer[event, 0] = char(list(EXPECTED_RAW_TOKENS)).ref
        if bad_outer_reference and condition == "ES10":
            header_outer[0, 0] = h5py.Reference()

        initial_date = root.create_dataset("Initial_Date", data=_char_matrix(["01/01/2020 12:00:00 PM"]))
        initial_date.attrs["MATLAB_class"] = np.bytes_("char")
        transient = root.create_group("Transient_Data")
        timestamp_rows = {"ES10": 5, "ES12": 6, "ES14": 4}[condition]
        signal_rows = {"ES10": 5, "ES12": 4, "ES14": 4}[condition]
        serial = 737791.0 + np.arange(timestamp_rows, dtype=np.float64) / 720.0
        transient.create_dataset("Serial_Date", data=serial.reshape(-1, 1))
        unit = transient.create_group(unit_label)
        for signal_index, signal_kind in enumerate(("VL", "VO")):
            values = _signal(signal_rows, condition_offset + signal_index * 100, signal_kind)
            if unsafe_storage == "external" and condition == "ES10" and signal_kind == "VL":
                raw_path = path.with_suffix(".external.raw")
                dataset = unit.create_dataset(
                    signal_kind,
                    shape=values.shape,
                    dtype=np.float64,
                    external=[(str(raw_path), 0, values.nbytes)],
                )
                dataset[...] = values
            elif unsafe_storage == "vds" and condition == "ES10" and signal_kind == "VL":
                hidden = h5_file.require_group("hidden").create_dataset("source", data=values)
                layout = h5py.VirtualLayout(shape=values.shape, dtype=np.float64)
                layout[:] = h5py.VirtualSource(hidden)
                unit.create_virtual_dataset(signal_kind, layout, fillvalue=np.nan)
            else:
                unit.create_dataset(signal_kind, data=values)


def _fixture(
    tmp_path: Path,
    *,
    asymmetric_empty: bool = False,
    bad_outer_reference: bool = False,
    unsafe_storage: str | None = None,
) -> dict[str, Path]:
    input_root = tmp_path / "input"
    input_root.mkdir()
    for condition in ("ES10", "ES12", "ES14"):
        _write_mat(
            input_root / f"{condition}.mat",
            condition,
            asymmetric_empty=asymmetric_empty,
            bad_outer_reference=bad_outer_reference,
            unsafe_storage=unsafe_storage,
        )

    contract = {
        "schema_version": "test.contract.v1",
        "scope": "reference_aware_parser_and_data_gate_only",
        "forbidden_actions": [
            "model_training",
            "model_evaluation",
            "rul_generation_or_scoring",
            "formal_design_gate",
            "freeze_b",
            "agent_topology_evaluation",
        ],
        "expected_counts": {
            "provisional_eis_units": 3,
            "events_per_unit": 2,
            "eis_event_slots": 6,
            "eis_nonempty_matrices": 9,
            "eis_nonempty_by_condition": {"ES10": 3, "ES12": 3, "ES14": 3},
            "transient_units": 3,
            "transient_arrays": 6,
            "ES10_timestamp_rows": 5,
            "ES10_signal_rows": 5,
            "ES12_timestamp_rows": 6,
            "ES12_signal_rows": 4,
            "ES14_timestamp_rows": 4,
            "ES14_signal_rows": 4,
        },
        "forbidden_feature_classes": [
            "raw_header",
            "source_path",
            "source_filename",
            "hdf5_reference_name",
            "condition_label",
            "unit_label",
            "termination_proxy",
            "sequence_length",
        ],
    }
    contract_path = tmp_path / "contract.json"
    _dump_json(contract_path, contract)
    contract_sha = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    amendment = {
        "schema_version": "test.amendment.v1",
        "parent_contract_sha256": contract_sha,
        "expected_raw_reference_slots": 12,
        "expected_nonempty_matrix_pairs": 9,
        "expected_paired_canonical_empties": 3,
        "frequency_row_contract": {
            "preserve_all_raw_rows": True,
            "raw_row_counts_allowed": [4],
            "allowed_preamble_lengths": [1],
            "expected_positive_sweep_rows": 3,
        },
    }
    amendment_path = tmp_path / "amendment.json"
    _dump_json(amendment_path, amendment)

    archive_bytes = b"synthetic archive evidence"
    archive_path = tmp_path / "archive.zip"
    archive_path.write_bytes(archive_bytes)
    targets = []
    for filename in ("ES10.mat", "ES12.mat", "ES14.mat"):
        sha256, crc32, size = _sha_file(input_root / filename)
        targets.append(
            {
                "target": filename,
                "input_sha256": sha256,
                "input_crc32": crc32,
                "input_size_bytes": size,
                "archive_member_streamed_sha256": sha256,
                "archive_member_crc32": crc32,
                "archive_member_size_bytes": size,
            }
        )
    archive_sha, archive_crc, archive_size = _sha_file(archive_path)
    integrity = {
        "archive": {
            "archive_name": "archive.zip",
            "sha256": archive_sha,
            "file_crc32": archive_crc,
            "size_bytes": archive_size,
            "member_crc_status": "passed",
        },
        "targets": targets,
    }
    integrity_path = tmp_path / "integrity.json"
    _dump_json(integrity_path, integrity)
    return {
        "input": input_root,
        "contract": contract_path,
        "amendment": amendment_path,
        "integrity": integrity_path,
        "archive": archive_path,
    }


def _run(paths: dict[str, Path], output: Path):
    return run_data_gate(
        paths["input"],
        paths["integrity"],
        output,
        contract_path=paths["contract"],
        amendment_path=paths["amendment"],
        archive_path=paths["archive"],
        chunk_rows=2,
    )


def test_pair_before_sort_count_reconciliation_and_artifact_seal(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    output = tmp_path / "gate"
    summary = _run(paths, output)

    assert summary["counts"]["eis_event_slots"] == 6
    assert summary["counts"]["raw_inner_slots"] == 12
    assert summary["counts"]["nonempty_matrix_pairs"] == 9
    assert summary["counts"]["paired_canonical_empties"] == 3
    assert summary["raw_reconciliation"] == {
        "formula": "raw=eligible+quarantined+structural_empty",
        "passed": True,
    }
    rows = [
        row
        for row in _read_csv(output / "REFERENCE_LINKAGE_LEDGER.csv")
        if row["condition"] == "ES10" and row["event_index"] == "0"
    ]
    assert [(row["raw_replicate_index"], row["sorted_replicate_rank"]) for row in rows] == [
        ("0", "1"),
        ("1", "0"),
    ]
    assert rows[0]["acquisition_start"] > rows[1]["acquisition_start"]
    assert rows[0]["matrix_content_sha256"] != rows[1]["matrix_content_sha256"]
    assert all(row["finish_evidence"] == "inferred_start_plus_max_time_s" for row in rows)

    required = set(REQUIRED_JSON) | set(REQUIRED_CSV) | {"DATA_GATE_REPORT.md", "ARTIFACT_HASHES.sha256"}
    complete = json.loads((output / "COMPLETE.json").read_text(encoding="utf-8"))
    assert complete["status"] == "COMPLETE"
    assert set(complete["required_artifacts"]) == required
    manifest = json.loads((output / "ARTIFACT_MANIFEST.json").read_text(encoding="utf-8"))
    csv_entries = [row for row in manifest["stable_artifacts"] if row["name"].endswith(".csv")]
    assert len(csv_entries) == len(REQUIRED_CSV)
    assert all(row["columns"] and isinstance(row["row_count"], int) for row in csv_entries)
    assert complete["code_sha256"] == manifest["code_sha256"]


def test_asymmetric_empty_is_failed_and_never_silently_dropped(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, asymmetric_empty=True)
    output = tmp_path / "asymmetric"
    summary = _run(paths, output)
    gates = {(row["gate_id"], row["scope_id"]): row["status"] for row in summary["gates"]}
    assert gates[("G01", "eis_references")] == "FAIL"
    rows = _read_csv(output / "REFERENCE_LINKAGE_LEDGER.csv")
    asymmetric = [row for row in rows if row["pair_status"] == "asymmetric_empty"]
    assert len(asymmetric) == 1
    assert asymmetric[0]["raw_slot_class"] == "quarantined"
    assert summary["raw_reconciliation"]["passed"] is True


def test_es12_mismatch_is_candidate_only_and_no_trim_is_applied(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    output = tmp_path / "alignment"
    _run(paths, output)
    rows = [
        row
        for row in _read_csv(output / "TRANSIENT_ALIGNMENT_LEDGER.csv")
        if row["condition"] == "ES12"
    ]
    assert len(rows) == 2
    assert all(row["timestamp_rows"] == "6" and row["signal_rows"] == "4" for row in rows)
    assert all(row["row_difference"] == "2" for row in rows)
    assert all(row["applied_repair"] == "false" for row in rows)
    assert all(row["alignment_status"] == "BLOCKED" for row in rows)
    candidates = json.loads(rows[0]["candidate_explanations"])
    assert candidates[0]["unpaired_timestamp_indices"] == [4, 5]
    assert candidates[1]["unpaired_timestamp_indices"] == [0, 1]

    with h5py.File(paths["input"] / "ES12.mat", "r") as h5_file:
        signal = np.asarray(h5_file["/ES12/Transient_Data/ES12C1/VL"])
        expected_hash = _array_signature(signal, np)
    signatures = _read_csv(output / "CONTENT_SIGNATURE_LEDGER.csv")
    recorded = next(row for row in signatures if row["item_id"] == "transient:ES12:ES12C1:VL")
    assert recorded["content_sha256"] == expected_hash
    assert json.loads(recorded["shape"]) == [4, 5]


@pytest.mark.parametrize("unsafe_storage", ["external", "vds"])
def test_external_and_vds_are_rejected_before_publish(tmp_path: Path, unsafe_storage: str) -> None:
    paths = _fixture(tmp_path, unsafe_storage=unsafe_storage)
    output = tmp_path / "must-not-publish"
    with pytest.raises(DataGateError, match="external HDF5 storage|virtual HDF5"):
        _run(paths, output)
    assert not output.exists()


def test_null_outer_reference_is_rejected_before_publish(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, bad_outer_reference=True)
    output = tmp_path / "must-not-publish"
    with pytest.raises(DataGateError, match="outer Header/Data cell"):
        _run(paths, output)
    assert not output.exists()


def test_outputs_are_byte_deterministic_and_contain_no_absolute_output_path(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    _run(paths, first)
    _run(paths, second)
    first_names = sorted(path.name for path in first.iterdir())
    second_names = sorted(path.name for path in second.iterdir())
    assert first_names == second_names
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in first_names)
    absolute_first = str(first.resolve()).encode("utf-8")
    assert all(absolute_first not in (first / name).read_bytes() for name in first_names)


def test_forbidden_fields_targets_and_downstream_scope_remain_locked(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    output = tmp_path / "locked"
    summary = _run(paths, output)
    definitions = json.loads((output / "TARGET_DEFINITIONS.json").read_text(encoding="utf-8"))
    assert definitions["numeric_targets_emitted"] == []
    for target in ("capacity", "ESR", "SOH", "RUL"):
        assert definitions[target]["status"] == "BLOCKED"
        assert definitions[target]["numeric_values_emitted"] is False
    assert definitions["raw_observable_semantics"]["Re(Z)/Ohm"] == "raw_impedance_component_not_ESR"

    linkage_header = (output / "REFERENCE_LINKAGE_LEDGER.csv").read_text(encoding="utf-8").splitlines()[0]
    for forbidden in ("raw_header", "source_path", "source_filename", "hdf5_reference_name"):
        assert forbidden not in linkage_header
    expected_scope_locks = {
        "model_training",
        "model_evaluation",
        "rul_generation_or_scoring",
        "benchmark_l_modeling",
        "formal_design_gate",
        "freeze_b",
        "agent_topology_evaluation",
    }
    assert all(summary["downstream"][key] == "BLOCKED_BY_USER_SCOPE" for key in expected_scope_locks)
    eligibility = _read_csv(output / "ELIGIBILITY_MATRIX.csv")
    assert all(row["modeling_eligible"] == "false" for row in eligibility)
    assert all(row["rul_eligible"] == "false" for row in eligibility)
    assert all(row["benchmark_l_modeling_eligible"] == "false" for row in eligibility)


def test_transient_masks_are_independently_hashed_and_suffix_geometry_is_checked(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    output = tmp_path / "masks"
    _run(paths, output)
    rows = [
        row
        for row in _read_csv(output / "MISSINGNESS_LEDGER.csv")
        if row["condition"] == "ES10" and row["modality"] == "transient_signal"
    ]
    assert {row["signal_kind"] for row in rows} == {"VL", "VO"}
    assert len({row["nan_mask_sha256"] for row in rows}) == 2
    assert all(row["finite_prefix_nan_suffix_violation_rows"] == "0" for row in rows)


def test_integrity_mismatch_and_append_only_output_are_rejected(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "sentinel.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    with pytest.raises(DataGateError, match="append-only"):
        _run(paths, existing)
    assert sentinel.read_text(encoding="utf-8") == "preserve"

    with h5py.File(paths["input"] / "ES14.mat", "a") as h5_file:
        h5_file.create_dataset("mutation", data=np.array([1], dtype=np.int8))
    output = tmp_path / "integrity-failure"
    with pytest.raises(DataGateError, match="integrity manifest"):
        _run(paths, output)
    assert not output.exists()


def test_column_contract_names_are_exactly_frozen() -> None:
    assert len(EXPECTED_RAW_TOKENS) == 20
    assert len(CANONICAL_COLUMNS) == 18
    assert CANONICAL_COLUMNS[10:12] == ("cycle number", "I Range")
