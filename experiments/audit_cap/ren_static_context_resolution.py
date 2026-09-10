"""Resolve two proven context-marker ambiguities; never grant row authority.

Inputs must come from the frozen static and independently reviewed diagnostic
generations. This pure function does not open workbooks or modify those inputs.
Unclassified record types and VBA markers deliberately remain blocking.
"""
from copy import deepcopy


def resolve_context_markers(static: dict, diagnostic: dict | None) -> dict:
    result = {"member_path": static["member_path"], "input_sha256": static["input_sha256"],
              "original_blockers": list(static["blockers"]), "resolved_markers": [],
              "remaining_blockers": list(static["blockers"]),
              "status": "CONTEXT_RESOLUTION_ONLY_NOT_DATA_GATE",
              "row_parse_authorized": False, "p2_eligible": False,
              "model_or_api_executed": False, "numeric_target_emitted": False}
    if diagnostic is None:
        return result
    if (diagnostic["member_path"] != static["member_path"]
            or diagnostic["input_sha256"] != static["input_sha256"]
            or diagnostic.get("status") != "DIAGNOSTIC_ONLY_NO_GATE_CHANGE"):
        raise ValueError("diagnostic identity mismatch")
    for flag in ("row_parse_authorized", "p2_eligible", "model_or_api_executed",
                 "numeric_target_emitted", "workbook_code_executed", "formulas_evaluated"):
        if diagnostic.get(flag) is not False:
            raise ValueError("diagnostic authority mismatch")
    old_entries = {e["path_sha256"]: e for e in static["ole_entries"]}
    new_entries = {e["path_sha256"]: e for e in diagnostic["entries"]}
    if (len(old_entries) != len(static["ole_entries"]) or len(new_entries) != len(diagnostic["entries"])
            or set(old_entries) != set(new_entries)
            or any(old_entries[k]["ole_entry_type"] != new_entries[k]["ole_entry_type"] for k in old_entries)):
        raise ValueError("OLE directory evidence mismatch")
    embedded = [e for e in static["ole_entries"] if e["classification"] == "embedded_object"]
    marker = "ole_embedded_object_entry"
    if marker in result["remaining_blockers"] and embedded and all(
            new_entries[e["path_sha256"]]["kind"] == "root_compobj_metadata_marker"
            and e["ole_entry_type"] == 2 for e in embedded):
        result["remaining_blockers"].remove(marker)
        result["resolved_markers"].append({"marker": marker, "reason": "ROOT_COMPOBJ_METADATA_NOT_EMBEDDED_CONTAINER"})
    marker = "unclassified_active_or_context_record_CONTINUE"
    if marker in result["remaining_blockers"]:
        context = diagnostic.get("continuation_context")
        scans = static["workbook_scans"]
        if context is not None and len(scans) == 1:
            scan = scans[0]
            expected = sum(t["count"] for t in scan["record_types"] if t["record_id"] == "0x003C")
            chains = context["chains"]
            if (context.get("payloads_decoded") is False and scan["scan_complete"] is True
                    and scan["unscanned_bytes"] == 0 and expected > 0 and chains
                    and context["bytes_framed"] == scan["stream_bytes"]
                    and context["records_framed"] == scan["records_scanned"]
                    and sum(c["continue_records"] for c in chains) == expected
                    and all(type(c["continue_records"]) is int and c["continue_records"] > 0
                            and c["predecessor_record_id"] == "0x004D"
                            and c["following_record_id"] == "0x00A1" for c in chains)):
                result["remaining_blockers"].remove(marker)
                result["resolved_markers"].append({"marker": marker, "reason": "PLS_CONTINUE_SETUP_PRINT_CONTEXT_PAYLOAD_NOT_EXECUTED"})
    # Name recognition is not full payload/schema validation. Do not remove the
    # unknown-type blocker or VBA blocker here, even when the catalog names them.
    return deepcopy(result)
