from __future__ import annotations

import hashlib
import json
import subprocess

from experiments.audit_cap.ren_scs_data_gate import (
    EXPECTED_BYTES,
    PROJECT_SHA256,
    PUBLISHED_MD5,
    _finalize_artifact_graph,
    _member_safety,
    _parse_slt,
    _sanitize_url,
    _target_rows,
    _test_evidence,
)


def test_frozen_ren_byte_contract_is_exact() -> None:
    assert EXPECTED_BYTES == 2_114_703_017
    assert PUBLISHED_MD5 == "26a7a663217c59377c83fb2a8274466b"
    assert PROJECT_SHA256 == "a8f1083b887f95483561a94b624b323ff42814654ee7f23e7f95bc042fa258d8"


def test_transport_url_redaction_removes_signed_query() -> None:
    assert (
        _sanitize_url("https://bucket.invalid/raw.rar?X-Amz-Signature=secret#fragment")
        == "https://bucket.invalid/raw.rar"
    )


def test_listing_parser_and_safety_accept_only_normal_regular_xls_members() -> None:
    raw = b"""7-Zip fixture\n--\nPath = raw.rar\nType = Rar5\nPhysical Size = 7\nEncrypted = -\nMultivolume = -\nVolumes = 1\n\n----------\nPath = batch1/1.xls\nFolder = -\nSize = 10\nPacked Size = 7\nEncrypted = -\nSplit Before = -\nSplit After = -\nCRC = AABBCCDD\nMethod = m3:25\nSymbolic Link = \nHard Link = \nCopy Link = \n"""
    archive, members = _parse_slt(raw)
    rows, summary = _member_safety(members)
    assert archive["Type"] == "Rar5"
    assert summary["status"] == "PASS_LISTING_METADATA_ONLY"
    assert summary["listed_uncompressed_bytes"] == 10
    assert rows[0]["row_content_status"] == "NOT_EXTRACTED_NOT_PARSED"


def test_listing_safety_rejects_traversal_and_unexpected_active_extension() -> None:
    members = [
        {
            "Path": "../escape.exe",
            "Folder": "-",
            "Size": "1",
            "Packed Size": "1",
            "Encrypted": "-",
            "Split Before": "-",
            "Split After": "-",
            "Symbolic Link": "",
            "Hard Link": "",
            "Copy Link": "",
        }
    ]
    _, summary = _member_safety(members)
    assert summary["status"] == "FAIL_LISTING_SAFETY"
    assert "unsafe_path:../escape.exe" in summary["unsafe_findings"]
    assert "unexpected_extension:../escape.exe" in summary["unsafe_findings"]


def test_unsupported_decoder_is_a_closed_archive_test_block() -> None:
    completed = subprocess.CompletedProcess(
        args=["7z", "t"],
        returncode=2,
        stdout=b"archive summary",
        stderr=b"ERROR: Unsupported Method : batch1/1.xls\n",
    )
    evidence = _test_evidence(completed)
    assert evidence["status"] == "BLOCKED_ARCHIVE_TEST_UNSUPPORTED_METHOD"
    assert evidence["unsupported_method_error_count"] == 1


def test_target_gate_emits_no_numerical_target_or_rul() -> None:
    rows = {row["target"]: row for row in _target_rows()}
    assert all(row["numeric_target_emitted"] == "NO" for row in rows.values())
    assert rows["RUL"]["status"] == "NA_NO_EVENT_CENSOR_TRUTH"
    assert rows["ESR"]["status"] == "NA_NO_NATIVE_ESR_OR_EIS_EVIDENCE"


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
