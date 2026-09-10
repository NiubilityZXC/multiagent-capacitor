from copy import deepcopy

import pytest

from experiments.audit_cap.ren_static_context_resolution import resolve_context_markers


def fixture():
    static = {"member_path": "synthetic.xls", "input_sha256": "a" * 64,
        "blockers": ["unclassified_record_types", "ole_macro_entry", "ole_embedded_object_entry",
                     "unclassified_active_or_context_record_CONTINUE"],
        "ole_entries": [{"path_sha256": "b" * 64, "classification": "embedded_object", "ole_entry_type": 2}],
        "workbook_scans": [{"scan_complete": True, "unscanned_bytes": 0, "stream_bytes": 32,
            "records_scanned": 4, "record_types": [{"record_id": "0x003C", "count": 2}]}]}
    diagnostic = {"member_path": static["member_path"], "input_sha256": static["input_sha256"],
        "status": "DIAGNOSTIC_ONLY_NO_GATE_CHANGE",
        "entries": [{"path_sha256": "b" * 64, "kind": "root_compobj_metadata_marker", "ole_entry_type": 2}],
        "continuation_context": {"payloads_decoded": False, "bytes_framed": 32, "records_framed": 4,
            "chains": [{"predecessor_record_id": "0x004D", "following_record_id": "0x00A1", "continue_records": 2}]},
        **dict.fromkeys(("row_parse_authorized", "p2_eligible", "model_or_api_executed", "numeric_target_emitted",
                         "workbook_code_executed", "formulas_evaluated"), False)}
    return static, diagnostic


def test_resolve_only_two_proven_markers_without_changing_original():
    static, diagnostic = fixture()
    before = deepcopy((static, diagnostic))
    result = resolve_context_markers(static, diagnostic)
    assert (static, diagnostic) == before
    assert result["remaining_blockers"] == ["unclassified_record_types", "ole_macro_entry"]
    assert len(result["resolved_markers"]) == 2
    assert result["row_parse_authorized"] is False and result["p2_eligible"] is False


@pytest.mark.parametrize("key,value", [("input_sha256", "c" * 64), ("member_path", "other.xls"),
                                     ("status", "PASS"), ("row_parse_authorized", True)])
def test_diagnostic_identity_and_authority_mismatch_rejected(key, value):
    static, diagnostic = fixture()
    diagnostic[key] = value
    with pytest.raises(ValueError): resolve_context_markers(static, diagnostic)


@pytest.mark.parametrize("key,value", [("predecessor_record_id", "0x0006"), ("following_record_id", None),
                                      ("continue_records", 1), ("continue_records", -1)])
def test_unsupported_continue_context_stays_blocked(key, value):
    static, diagnostic = fixture()
    diagnostic["continuation_context"]["chains"][0][key] = value
    result = resolve_context_markers(static, diagnostic)
    assert "unclassified_active_or_context_record_CONTINUE" in result["remaining_blockers"]


def test_actual_embedded_container_stays_blocked():
    static, diagnostic = fixture()
    diagnostic["entries"][0]["kind"] = "embedded_container_marker"
    assert "ole_embedded_object_entry" in resolve_context_markers(static, diagnostic)["remaining_blockers"]


def test_missing_diagnostic_resolves_nothing():
    static, _ = fixture()
    result = resolve_context_markers(static, None)
    assert result["remaining_blockers"] == static["blockers"] and result["resolved_markers"] == []


def test_directory_mismatch_rejected():
    static, diagnostic = fixture()
    diagnostic["entries"][0]["path_sha256"] = "c" * 64
    with pytest.raises(ValueError): resolve_context_markers(static, diagnostic)


def test_incomplete_stream_cannot_resolve_continue():
    static, diagnostic = fixture()
    static["workbook_scans"][0]["unscanned_bytes"] = 1
    assert "unclassified_active_or_context_record_CONTINUE" in resolve_context_markers(static, diagnostic)["remaining_blockers"]
