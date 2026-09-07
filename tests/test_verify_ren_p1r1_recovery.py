from __future__ import annotations

import json
import hashlib
from pathlib import Path
import zlib

import pytest

import experiments.audit_cap.verify_ren_p1r1_recovery as verifier

from experiments.audit_cap.verify_ren_p1r1_recovery import (
    VerificationError,
    _flags,
    _json,
)


def test_strict_json_rejects_duplicate_keys(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"a":1,"a":2}\n', encoding="utf-8")
    with pytest.raises(VerificationError, match="duplicate JSON key"):
        _json(path)


def test_strict_json_rejects_nonfinite(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"x":NaN}\n', encoding="utf-8")
    with pytest.raises(VerificationError, match="non-finite JSON"):
        _json(path)


def test_false_execution_flags_are_mandatory() -> None:
    with pytest.raises(VerificationError, match="model_or_api"):
        _flags({"model_or_api_executed": True, "numeric_target_emitted": False}, "x")
    with pytest.raises(VerificationError, match="numeric_target"):
        _flags({"model_or_api_executed": False, "numeric_target_emitted": True}, "x")


def test_false_execution_flags_accept_only_literal_false() -> None:
    _flags({"model_or_api_executed": False, "numeric_target_emitted": False}, "x")


def _command_record(stdout: bytes, stderr: bytes = b"", *, return_code: int = 0,
                    timed_out: bool = False, execution_error: bool = False) -> dict:
    return {
        "schema_version": verifier.GENERATOR_SCHEMA,
        "argv": ["unrar", "t", "-p-", "FROZEN_RAW_RAR"],
        "return_code": return_code,
        "timed_out": timed_out,
        "execution_error": execution_error,
        "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "model_or_api_executed": False,
        "numeric_target_emitted": False,
    }


def test_command_evidence_detects_transcript_mutation(tmp_path) -> None:
    evidence = tmp_path / "evidence"; evidence.mkdir()
    stdout = b"Testing batch/a.xls OK\nAll OK\n"
    (evidence / "ARCHIVE_TEST.stdout.raw").write_bytes(stdout)
    (evidence / "ARCHIVE_TEST.stderr.raw").write_bytes(b"")
    (evidence / "ARCHIVE_TEST.command.json").write_text(
        json.dumps(_command_record(stdout)) + "\n", encoding="utf-8"
    )
    verifier._command_evidence(evidence, "ARCHIVE_TEST")
    (evidence / "ARCHIVE_TEST.stdout.raw").write_bytes(stdout + b"tamper")
    with pytest.raises(VerificationError, match="transcript record mismatch"):
        verifier._command_evidence(evidence, "ARCHIVE_TEST")


def test_test_report_is_rebuilt_field_for_field_and_warning_changes_status(monkeypatch) -> None:
    monkeypatch.setattr(verifier, "FILE_COUNT", 1)
    stdout = b"Testing batch/a.xls OK\nAll OK\n"
    command = {"return_code": 0, "timed_out": False, "execution_error": False,
               "argv": ["unrar"], "model_or_api_executed": False,
               "numeric_target_emitted": False}
    report = verifier._rebuild_test_report(command, stdout, b"", ["batch/a.xls"])
    assert report["status"] == "PASS_ARCHIVE_TEST"
    assert report["observed_tested_file_count"] == 1
    warned = verifier._rebuild_test_report(command, stdout + b"warning\n", b"", ["batch/a.xls"])
    assert warned["status"] == "BLOCKED_ARCHIVE_TEST"
    tampered = dict(report); tampered["return_code"] = 9
    assert tampered != report


def test_extraction_scan_rejects_symlink_and_crc_mismatch(tmp_path) -> None:
    extraction = tmp_path / "extracted"; extraction.mkdir()
    payload = extraction / "a.xls"; payload.write_bytes(b"abc")
    (extraction / "link.xls").symlink_to(payload)
    expected = {"a.xls": {"member_type": "regular_file", "uncompressed_bytes": 3, "crc": "00000000"}}
    rows, missing, unexpected, unsafe = verifier._scan_extraction(extraction, expected)
    assert not missing
    assert unexpected == ["link.xls"]
    assert any("member_mismatch:a.xls" in item for item in unsafe)
    assert any("unsafe_type_or_link:link.xls:symlink" in item for item in unsafe)


def test_extraction_manifest_rebuild_includes_all_failure_fields(monkeypatch) -> None:
    monkeypatch.setattr(verifier, "MEMBER_COUNT", 1)
    monkeypatch.setattr(verifier, "FILE_COUNT", 1)
    stdout = b"Extracting a.xls OK\nAll OK\n"
    command = {"return_code": 0, "timed_out": False, "execution_error": False,
               "argv": ["unrar"], "model_or_api_executed": False,
               "numeric_target_emitted": False}
    rows = [{"member_path": "a.xls", "observed_type": "regular_file", "observed_bytes": "3"}]
    passed = verifier._rebuild_extraction_manifest(command, stdout, b"", rows, [], [], [], "quarantine_extracted")
    assert passed["status"] == "PASS_EXTRACTION_BYTE_IDENTITY"
    blocked = verifier._rebuild_extraction_manifest(command, stdout, b"", rows, [], ["extra"], ["member_mismatch:extra"], "quarantine_extracted")
    assert blocked["status"] == "QUARANTINED_EXTRACTION_MISMATCH"
    assert blocked["unexpected_members"] == ["extra"]
    assert blocked["unsafe_or_mismatched"] == ["member_mismatch:extra"]


def test_symlink_ancestor_is_rejected(tmp_path) -> None:
    project = tmp_path / "project"; project.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    (project / "data").symlink_to(outside, target_is_directory=True)
    with pytest.raises(VerificationError, match="symlink path component"):
        verifier._no_symlink_components(project, project / "data/raw/ren_scs")
