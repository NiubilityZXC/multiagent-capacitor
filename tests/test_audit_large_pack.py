from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from experiments.audit_cap.audit_large_pack import (  # noqa: E402
    AuditError,
    TARGET_MAT_FILES,
    run_audit,
)


def _write_hdf5(path: Path, offset: float) -> None:
    external_path = path.with_suffix(".raw")
    with h5py.File(path, "w") as h5_file:
        h5_file.attrs["MATLAB_class"] = np.bytes_("struct")
        group = h5_file.create_group("measurements")
        capacity = group.create_dataset(
            "capacity",
            data=np.array([1.0 + offset, np.nan, np.inf, -np.inf], dtype=np.float64),
            chunks=(2,),
            compression="gzip",
            compression_opts=1,
        )
        capacity.attrs["MATLAB_class"] = np.bytes_("double")
        references = h5_file.create_dataset("object_refs", shape=(1,), dtype=h5py.ref_dtype)
        references[0] = capacity.ref
        h5_file["capacity_alias"] = capacity
        h5_file["soft_capacity"] = h5py.SoftLink("/measurements/capacity")
        external = h5_file.create_dataset(
            "external_payload",
            shape=(4,),
            dtype=np.float64,
            external=[(str(external_path), 0, 4 * np.dtype(np.float64).itemsize)],
        )
        external[:] = np.arange(4, dtype=np.float64) + offset

        layout = h5py.VirtualLayout(shape=(4,), dtype=np.float64)
        virtual_source = h5py.VirtualSource(
            f"missing-{path.stem}-vds-source.h5",
            "/data",
            shape=(4,),
        )
        layout[:] = virtual_source
        h5_file.create_virtual_dataset("virtual_payload", layout, fillvalue=np.nan)

    # A metadata-only audit must remain safe and deterministic when neither an
    # external-storage payload nor a VDS source is present.
    external_path.unlink()


def _build_fixture(tmp_path: Path) -> tuple[Path, Path]:
    input_root = tmp_path / "extracted"
    input_root.mkdir()
    for index, target in enumerate(TARGET_MAT_FILES):
        _write_hdf5(input_root / target, float(index))

    zip_path = tmp_path / "Electrical_Stress.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for target in TARGET_MAT_FILES:
            archive.write(input_root / target, arcname=f"nested/{target}")
    return zip_path, input_root


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_metadata_audit_is_deterministic_and_conservative(tmp_path: Path) -> None:
    zip_path, input_root = _build_fixture(tmp_path)
    output_one = tmp_path / "audit-one"
    output_two = tmp_path / "audit-two"

    first = run_audit(zip_path, input_root, output_one, source_url="https://example.invalid/public.zip")
    second = run_audit(zip_path, input_root, output_two, source_url="https://example.invalid/public.zip")

    assert first == second
    assert first["mode"] == "metadata_only"
    assert first["integrity"]["all_target_streamed_sha256_match"] is True
    assert first["data_gate"]["overall"] == "partial_integrity_only"
    assert first["data_gate"]["benchmark_l_modeling"] == "blocked"
    assert not (output_one / "HDF5_NUMERIC_SCAN.csv").exists()

    manifest = json.loads((output_one / "DATA_MANIFEST.json").read_text(encoding="utf-8"))
    with ZipFile(zip_path, "r") as archive:
        for target_row in manifest["targets"]:
            with archive.open(target_row["archive_member"], "r") as member:
                independently_streamed = hashlib.sha256()
                while block := member.read(1024):
                    independently_streamed.update(block)
            assert target_row["archive_member_streamed_sha256"] == independently_streamed.hexdigest()
            assert target_row["input_sha256"] == independently_streamed.hexdigest()
            assert target_row["sha256_match"] is True
            assert "sha256" not in target_row

    for name in ("DATA_MANIFEST.json", "HDF5_OBJECTS.csv", "QUARANTINE.csv", "AUDIT_SUMMARY.json"):
        assert (output_one / name).read_bytes() == (output_two / name).read_bytes()

    object_rows = _read_csv(output_one / "HDF5_OBJECTS.csv")
    capacity_rows = [
        row for row in object_rows if row["object_path"] == "/measurements/capacity"
    ]
    assert len(capacity_rows) == 3
    assert all(row["object_type"] == "dataset" for row in capacity_rows)
    assert all(row["chunks_json"] == "[2]" for row in capacity_rows)
    assert all(row["compression"] == "gzip" for row in capacity_rows)
    assert all(row["matlab_class"] == "double" for row in capacity_rows)
    assert all(row["semantic_status"] == "quarantined_unknown" for row in capacity_rows)

    reference_rows = [row for row in object_rows if row["object_path"] == "/object_refs"]
    assert len(reference_rows) == 3
    assert all(json.loads(row["reference_dtype_json"])["kind"] == "direct" for row in reference_rows)
    assert any(row["object_type"] == "soft_link" for row in object_rows)

    external_rows = [row for row in object_rows if row["object_path"] == "/external_payload"]
    assert len(external_rows) == 3
    assert all(row["storage_layout_status"] == "external_payload_not_read" for row in external_rows)
    assert all(json.loads(row["external_storage_json"])[0]["filename"].endswith(".raw") for row in external_rows)
    virtual_rows = [row for row in object_rows if row["object_path"] == "/virtual_payload"]
    assert len(virtual_rows) == 3
    assert all(row["is_virtual"] == "True" for row in virtual_rows)
    assert all(row["storage_layout_status"] == "virtual_payload_not_read" for row in virtual_rows)
    assert all(json.loads(row["virtual_sources_json"])[0]["dataset_path"] == "/data" for row in virtual_rows)

    quarantine_rows = _read_csv(output_one / "QUARANTINE.csv")
    assert any(row["reason"] == "unknown_semantics" for row in quarantine_rows)
    assert any(row["reason"] == "soft_link_not_dereferenced" for row in quarantine_rows)
    assert sum(row["reason"] == "external_storage_payload_not_audited" for row in quarantine_rows) == 3
    assert sum(row["reason"] == "virtual_dataset_payload_not_audited" for row in quarantine_rows) == 3


def test_numeric_scan_is_explicit_and_chunked(tmp_path: Path) -> None:
    zip_path, input_root = _build_fixture(tmp_path)
    output = tmp_path / "numeric-audit"
    summary = run_audit(
        zip_path,
        input_root,
        output,
        scan_numeric=True,
        scan_chunk_bytes=16,
    )

    assert summary["mode"] == "numeric_scan"
    rows = _read_csv(output / "HDF5_NUMERIC_SCAN.csv")
    capacity_rows = [
        row
        for row in rows
        if row["object_path"] in {"/capacity_alias", "/measurements/capacity"}
        and row["status"] == "passed"
    ]
    # HDF5 hard links have no intrinsic preferred path.  The lexicographically
    # first link is scanned exactly once per physical object.
    assert len(capacity_rows) == 3
    for row in capacity_rows:
        assert row["status"] == "passed"
        assert int(row["scanned_element_count"]) == 4
        assert int(row["finite_count"]) == 1
        assert int(row["nan_count"]) == 1
        assert int(row["inf_count"]) == 2
        assert int(row["posinf_count"]) == 1
        assert int(row["neginf_count"]) == 1

    aliases = [row for row in rows if row["status"] == "skipped_hard_link_alias"]
    assert len(aliases) == 3


def test_external_and_vds_payloads_are_never_numeric_scanned(tmp_path: Path) -> None:
    zip_path, input_root = _build_fixture(tmp_path)
    output = tmp_path / "storage-layout-audit"

    run_audit(zip_path, input_root, output, scan_numeric=True, scan_chunk_bytes=8)

    rows = _read_csv(output / "HDF5_NUMERIC_SCAN.csv")
    external_rows = [row for row in rows if row["object_path"] == "/external_payload"]
    virtual_rows = [row for row in rows if row["object_path"] == "/virtual_payload"]
    assert len(external_rows) == 3
    assert len(virtual_rows) == 3
    assert all(row["status"] == "skipped_external_storage" for row in external_rows)
    assert all(row["status"] == "skipped_virtual_dataset" for row in virtual_rows)
    assert all(int(row["scanned_element_count"]) == 0 for row in external_rows + virtual_rows)


def test_zip_path_traversal_is_rejected_before_output(tmp_path: Path) -> None:
    zip_path, input_root = _build_fixture(tmp_path)
    unsafe_zip = tmp_path / "unsafe.zip"
    with ZipFile(zip_path, "r") as source, ZipFile(unsafe_zip, "w", compression=ZIP_DEFLATED) as target:
        for info in source.infolist():
            target.writestr(info.filename, source.read(info.filename))
        target.writestr("../escape.txt", b"forbidden")

    output = tmp_path / "must-not-exist"
    with pytest.raises(AuditError, match="traversing"):
        run_audit(unsafe_zip, input_root, output)
    assert not output.exists()


def test_extracted_mat_must_match_archive_member(tmp_path: Path) -> None:
    zip_path, input_root = _build_fixture(tmp_path)
    with h5py.File(input_root / "ES12.mat", "a") as h5_file:
        h5_file.create_dataset("post_extract_mutation", data=np.array([1], dtype=np.int8))

    output = tmp_path / "must-not-exist"
    with pytest.raises(AuditError, match="SHA-256 does not match"):
        run_audit(zip_path, input_root, output)
    assert not output.exists()


def test_output_directory_is_append_only(tmp_path: Path) -> None:
    zip_path, input_root = _build_fixture(tmp_path)
    output = tmp_path / "existing-output"
    output.mkdir()
    (output / "sentinel.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(AuditError, match="append-only"):
        run_audit(zip_path, input_root, output)
    assert (output / "sentinel.txt").read_text(encoding="utf-8") == "keep"
