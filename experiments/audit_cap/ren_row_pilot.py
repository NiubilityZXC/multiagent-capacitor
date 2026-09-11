"""Frozen first-member R1D reader-boundary/R1E schema pilot, not Data Gate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from experiments.audit_cap import ren_static_context as context
    from experiments.audit_cap import ren_p1r1_xls_static as static
    from experiments.audit_cap.ren_static_context_resolution import resolve_context_markers
    from experiments.audit_cap.ren_workbook_reader import workbook_bytes, schema_rows
else:
    import ren_static_context as context
    import ren_p1r1_xls_static as static
    from ren_static_context_resolution import resolve_context_markers
    from ren_workbook_reader import workbook_bytes, schema_rows

POLICY = ("experiments/audit_cap/ren_workbook_reader.py", "experiments/audit_cap/ren_row_pilot.py",
          "experiments/audit_cap/ren_static_context.py", "experiments/audit_cap/ren_static_context_resolution.py",
          "tests/test_ren_workbook_reader.py", "tests/test_ren_row_pilot.py",
          "refine-logs/REN_READER_BOUNDARY_POLICY_20260910.md")
CATALOG = "refine-logs/REN_BIFF_OBSERVED_CATALOG_20260909.json"
CATALOG_SHA = "989e2c18ea7faf17f64e127947f1e7e414d186ee70fe164005366be14d37ca4a"
DIAGNOSTIC = "data/audit/ren_scs/p1r1_20260908_150800_static_context_v1/DIAGNOSTICS.json"
DIAGNOSTIC_SHA = "03b24b14081e45a295ad5036780d208b03b735f93297c55749f4f58c99ffb519"
PRIOR_MANIFEST = "data/audit/ren_scs/p1r1_20260908_150800_static/ARTIFACT_MANIFEST.json"
PRIOR_MANIFEST_SHA = "10adcf8fa53162dbddc00b051e2fe6c6d4a05bf9bcb6cffe23b309b1f3cb64d7"
FLAGS = {"model_or_api_executed": False, "numeric_target_emitted": False,
         "p2_eligible": False, "automatic_next_stage": False, "formulas_evaluated": False}


def allowed_record_ids(catalog: dict) -> set[int]:
    ids = {int(e["record_id"], 16) for e in catalog["entries"]}
    if len(ids) != 60 or len(catalog["entries"]) != 60:
        raise ValueError("observed catalog mismatch")
    return ids | set(static.PASSIVE_RECORDS) | {0x0809, 0x0085, 0x003C}


def validate_selected(report: dict, diagnostic: dict | None, allowed: set[int]) -> None:
    resolved = resolve_context_markers(report, diagnostic)
    if set(resolved["remaining_blockers"]) - {"unclassified_record_types", "ole_macro_entry"}:
        raise ValueError("unresolved structural blocker")
    if "ole_macro_entry" in resolved["remaining_blockers"]:
        if diagnostic is None:
            raise ValueError("macro tree not classified")
        by_hash = {e["path_sha256"]: e for e in diagnostic["entries"]}
        if not all(by_hash[e["path_sha256"]]["kind"] == "vba_project_tree_marker"
                   for e in report["ole_entries"] if e["classification"] == "macro"):
            raise ValueError("macro outside isolated VBA project tree")
    scans = report["workbook_scans"]
    if len(scans) != 1 or not scans[0]["scan_complete"] or scans[0]["unscanned_bytes"]:
        raise ValueError("incomplete old Workbook framing")
    if any(int(t["record_id"], 16) not in allowed for t in scans[0]["record_types"]):
        raise ValueError("unclassified record outside frozen catalog")


def run(root: Path) -> dict:
    root = root.resolve(strict=True)
    rec = context.recovery
    release = rec._strict_json(root / "refine-logs/REN_ROW_PILOT_RELEASE.json")
    actual = {p: rec._digests(root / p)["sha256"] for p in POLICY}
    if (release.get("status") != "PASS_FIRST_MEMBER_ROW_PILOT"
            or release.get("policy_sha256") != actual
            or release.get("approval_record_sha256") != rec.APPROVAL_SHA256):
        raise ValueError("row pilot pre-run release mismatch")
    # Existing generation verifies source/approval/recovery policy/CRC, not a
    # repeated download, archive test or extraction.
    context.independent.verify(root, context.RUN)
    context.original.validate_environment(root)
    for name, sha in ((CATALOG, CATALOG_SHA), (DIAGNOSTIC, DIAGNOSTIC_SHA), (PRIOR_MANIFEST, PRIOR_MANIFEST_SHA)):
        rec._no_symlink_components(root, root / name)
        if rec._digests(root / name)["sha256"] != sha:
            raise ValueError("frozen classification evidence changed")
    reports = context.verify_static_artifacts(root)
    allowed = allowed_record_ids(rec._strict_json(root / CATALOG))
    diagnostics = rec._strict_json(root / DIAGNOSTIC)["workbooks"]
    lookup = {d["member_path"]: d for d in diagnostics}
    if len(lookup) != len(diagnostics):
        raise ValueError("duplicate diagnostic members")
    selected = sorted(reports, key=lambda r: r["member_path"])[0]
    validate_selected(selected, lookup.get(selected["member_path"]), allowed)
    paths = rec.Paths.build(str(root), context.RUN, new=False)
    output = root / "data/audit/ren_scs/row_pilot_20260910_v1"
    local = root / "data/raw/ren_scs/row_pilot_20260910_v1"
    for p in (output, local):
        rec._no_symlink_components(root, p)
        if p.exists():
            raise ValueError("row pilot is append-only")
    output.mkdir(); local.mkdir(mode=0o700)
    try:
        path = paths.extraction / selected["member_path"]
        rec._no_symlink_components(root, path)
        meta = rec._require_file(path, "row pilot input")
        if meta.st_size != selected["input_bytes"] or meta.st_nlink != 1:
            raise ValueError("row pilot input changed")
        container = path.read_bytes()
        if hashlib.sha256(container).hexdigest() != selected["input_sha256"]:
            raise ValueError("row pilot SHA mismatch")
        data = workbook_bytes(container)
        if hashlib.sha256(data).hexdigest() != selected["workbook_scans"][0]["stream_sha256"]:
            raise ValueError("isolated Workbook differs from static scan")
        result = schema_rows(data, allowed)
        # Text hints remain ignored/local-only. Never publish raw rows/targets.
        rec._write_json(local / "SCHEMA_ROWS.json", result)
        summary = {"status": "FIRST_MEMBER_SCHEMA_AUDITED_DATA_GATE_PENDING",
                   "member_path": selected["member_path"], "row_parse_executed": True,
                   "sheet_count": len(result["sheets"]),
                   "stored_sheet_rows": sum(s["nrows"] for s in result["sheets"]),
                   "nonfinite_count": sum(s["nonfinite_count"] for s in result["sheets"]),
                   "schema_evidence_sha256": rec._digests(local / "SCHEMA_ROWS.json")["sha256"], **FLAGS}
        rec._write_json(output / "SUMMARY.json", summary)
        rec._write_json(output / "COMPLETE.json", {"status": "PILOT_COMPLETE_NOT_DATA_GATE", **FLAGS})
        return summary
    except Exception as exc:
        rec._write_json(output / "BLOCKED.json", {"status": "PILOT_FAILED_CLOSED", "error_type": type(exc).__name__, **FLAGS})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    print(json.dumps(run(Path(parser.parse_args().project_root)), sort_keys=True))
