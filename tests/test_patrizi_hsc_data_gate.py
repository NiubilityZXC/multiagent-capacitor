from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from experiments.audit_cap.patrizi_hsc_data_gate import (
    EXPECTED_PAYLOADS,
    PatriziDataGateError,
    _canonical_json_bytes,
    _cycle_audit,
    _finalize_artifact_graph,
    _sanitize_url,
    _target_rows,
    _write_or_validate_local_manifest,
)


def test_frozen_payload_contract_matches_approved_bytes_and_md5() -> None:
    observed = {
        item.filename: (item.expected_bytes, item.published_md5)
        for item in EXPECTED_PAYLOADS
    }
    assert observed == {
        "Dataset_HSC.mat": (225_986_697, "57e71c60cbae63142db44559edfa8ae0"),
        "HSC_dataset_info.pdf": (397_625, "0189a89a72c73080cece2104ba834bce"),
    }


def test_sanitized_transport_url_drops_all_query_and_fragment_material() -> None:
    assert (
        _sanitize_url(
            "https://EXAMPLE.invalid:443/path/file.mat?X-Amz-Credential=secret#token"
        )
        == "https://example.invalid:443/path/file.mat"
    )


def test_existing_local_manifest_is_immutable_but_reusable_across_audit_runs(
    tmp_path,
) -> None:
    path = tmp_path / "LOCAL_RAW_MANIFEST.json"
    first = {"schema": "v1", "created_at_utc": "2026-08-27T00:00:00+00:00", "x": 1}
    path.write_bytes(_canonical_json_bytes(first))

    second = dict(first, created_at_utc="2026-08-27T01:00:00+00:00")
    observed_hash = _write_or_validate_local_manifest(path, second)

    assert json.loads(path.read_text(encoding="utf-8")) == first
    assert observed_hash == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(PatriziDataGateError, match="differs"):
        _write_or_validate_local_manifest(path, dict(second, x=2))


def test_cycle_audit_reports_gaps_without_constructing_terminal_labels() -> None:
    row = _cycle_audit(
        np.array([2, 2, 3, 5], dtype=np.uint16),
        scope="summary",
        channel="ch4",
    )
    assert row["cycle_axis_status"] == "PARTIAL_PASS_CYCLE_AXIS_ONLY"
    assert row["missing_cycle_count_within_observed_range"] == 1
    assert row["missing_cycles_within_observed_range"] == "4"
    assert row["terminal_record_status"] == "BLOCKED_NO_EXPLICIT_TERMINATION_RECORD"


def test_target_gate_never_emits_soh_rul_or_relabels_capacity_as_capacitance() -> None:
    rows = {row["target"]: row for row in _target_rows()}
    assert all(row["numeric_target_emitted"] == "NO" for row in rows.values())
    assert rows["farad_capacitance"]["status"] == "NA"
    assert rows["ESR"]["status"] == "NA"
    assert rows["SOH"]["status"] == "BLOCKED"
    assert rows["RUL"]["status"] == "NA"


def test_completion_decision_is_bound_by_non_circular_artifact_graph(tmp_path) -> None:
    (tmp_path / "BASE.txt").write_bytes(b"base evidence\n")
    _finalize_artifact_graph(
        tmp_path,
        run_id="p1_graph_fixture",
        completion_decision={
            "schema_version": "fixture.v1",
            "run_id": "p1_graph_fixture",
            "status": "COMPLETE_FIXTURE",
        },
    )

    complete_bytes = (tmp_path / "COMPLETE.json").read_bytes()
    complete = json.loads(complete_bytes)
    manifest_bytes = (tmp_path / "ARTIFACT_MANIFEST.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    manifest_rows = {row["filename"]: row for row in manifest["artifacts"]}
    hash_rows = {}
    for line in (tmp_path / "ARTIFACT_HASHES.sha256").read_text(
        encoding="ascii"
    ).splitlines():
        digest, name = line.split("  ", 1)
        hash_rows[name] = digest

    assert "artifact_manifest_sha256" not in complete
    assert "artifact_hashes_sha256" not in complete
    assert complete["artifact_integrity"]["bound_by_later_artifacts"] == [
        "ARTIFACT_MANIFEST.json",
        "ARTIFACT_HASHES.sha256",
    ]
    assert set(manifest_rows) == {"BASE.txt", "COMPLETE.json"}
    assert manifest_rows["COMPLETE.json"]["sha256"] == hashlib.sha256(
        complete_bytes
    ).hexdigest()
    assert set(hash_rows) == {
        "BASE.txt",
        "COMPLETE.json",
        "ARTIFACT_MANIFEST.json",
    }
    assert hash_rows["COMPLETE.json"] == hashlib.sha256(complete_bytes).hexdigest()
    assert hash_rows["ARTIFACT_MANIFEST.json"] == hashlib.sha256(
        manifest_bytes
    ).hexdigest()
    assert "ARTIFACT_MANIFEST.json" not in manifest_rows
    assert "ARTIFACT_HASHES.sha256" not in hash_rows
