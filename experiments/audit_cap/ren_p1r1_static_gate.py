"""Reviewed-caller boundary for R1D static inventory; no R1E row parsing."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

from experiments.audit_cap import ren_p1r1_recovery as recovery
from experiments.audit_cap import verify_ren_p1r1_recovery as independent
from experiments.audit_cap.ren_p1r1_xls_static import ScanLimits, scan_xls_bytes


FLAGS = {"model_or_api_executed": False, "numeric_target_emitted": False,
         "automatic_next_stage": False, "workbook_code_executed": False,
         "formulas_evaluated": False, "row_parse_executed": False}
POLICY_NAMES = (
    "experiments/audit_cap/ren_p1r1_xls_static.py",
    "experiments/audit_cap/ren_p1r1_static_gate.py",
    "tests/test_ren_p1r1_xls_static.py",
    "tests/test_ren_p1r1_static_gate.py",
    "requirements-ren-p1r1-audit.lock",
    "refine-logs/REN_P1R1_PARSER_ENVIRONMENT_20260906_101027.json",
)


def summarize(reports: list[dict]) -> dict:
    counts: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for report in reports:
        container = report["container"]
        counts[container] = counts.get(container, 0) + 1
        for blocker in report["blockers"]:
            reasons[blocker] = reasons.get(blocker, 0) + 1
    blocked = sum(bool(report["blockers"]) or not report["scan_complete"] for report in reports)
    return {"schema_version": "RenP1R1StaticGate.v1",
            "status": "BLOCKED_ROW_PARSE" if blocked else "R1D_COMPLETE_R1E_NOT_RUN",
            "workbooks_inspected": len(reports), "workbooks_blocked": blocked,
            "container_counts": dict(sorted(counts.items())),
            "blocker_workbook_counts": dict(sorted(reasons.items())),
            "identity_gate": "NOT_EVALUATED_NO_ROW_EVIDENCE",
            "target_gate": "NOT_EVALUATED_NO_ROW_EVIDENCE",
            "chronology_gate": "NOT_EVALUATED_NO_ROW_EVIDENCE",
            "duplicate_gate": "NOT_EVALUATED_NO_ROW_EVIDENCE",
            "censor_gate": "NOT_EVALUATED_NO_ROW_EVIDENCE",
            "split_gate": "BLOCKED_NO_VERIFIED_PHYSICAL_IDENTITY",
            "p2_eligible": False, "rul_eligible": False, **FLAGS}


def validate_environment(project: Path) -> None:
    if Path(sys.prefix).resolve() != project / ".venv-ren-p1r1":
        raise recovery.RecoveryError("static scanner requires the isolated Ren audit venv")
    import olefile
    import xlrd
    for module, version in ((olefile, "0.47"), (xlrd, "2.0.2")):
        if module.__version__ != version or not Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
            raise recovery.RecoveryError("static parser dependency identity mismatch")
    environment = recovery._strict_json(project / POLICY_NAMES[-1])
    if recovery._digests(project / "requirements-ren-p1r1-audit.lock")["sha256"] != environment["lock"]["sha256"]:
        raise recovery.RecoveryError("parser lock changed")
    if recovery._digests(project / environment["installation"]["report_local"])["sha256"] != environment["installation"]["report_sha256"]:
        raise recovery.RecoveryError("parser installation evidence changed")


def run(project: Path, run_id: str) -> dict:
    project = project.resolve(strict=True)
    paths = recovery.Paths.build(str(project), run_id, new=False)
    # Check current recovery source/approval/code/transcripts and re-scan member CRCs
    # before this caller reads even the first workbook's container bytes.
    recovery_result = independent.verify(project, run_id)
    validate_environment(project)
    release_path = project / "refine-logs/REN_P1R1_R1D_RELEASE.json"
    release = recovery._strict_json(release_path)
    policy = {name: recovery._digests(project / name)["sha256"] for name in POLICY_NAMES}
    if (release.get("status") != "PASS_TO_RUN_STATIC_R1D"
            or release.get("reviewed_policy_sha256") != policy
            or release.get("approval_record_sha256") != recovery.APPROVAL_SHA256):
        raise recovery.RecoveryError("static pre-run review release mismatch")
    output = project / "data/audit/ren_scs" / (run_id + "_static")
    local = paths.local / "static_evidence"
    for target in (output, local):
        recovery._no_symlink_components(project, target)
        if target.exists():
            raise recovery.RecoveryError("static output is append-only; run already attempted")
    output.mkdir(); local.mkdir(mode=0o700)
    recovery._write_json(output / "RECOVERY_VERIFICATION.json", recovery_result)
    rows = recovery._stored_members(paths.output / "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv")
    reports = []
    safety = []
    try:
        for row in rows:
            if row["member_type"] != "regular_file":
                continue
            source = paths.extraction / row["member_path"]
            recovery._no_symlink_components(project, source)
            meta = recovery._require_file(source, "static workbook input")
            if meta.st_size != int(row["uncompressed_bytes"]) or meta.st_nlink != 1:
                raise recovery.RecoveryError("static input differs from recovered ledger")
            # Small type vocabulary may block; preserve the full inventory instead
            # of treating unfamiliar BIFF records as harmless or silently parsing rows.
            report = scan_xls_bytes(source.read_bytes(), limits=ScanLimits(max_records=64 * 1024 * 1024))
            report["member_path"] = row["member_path"]
            reports.append(report)
            safety.append({"member_path": row["member_path"], "bytes": meta.st_size,
                           "sha256": report["input_sha256"], "container": report["container"],
                           "scan_complete": str(report["scan_complete"]).lower(),
                           "status": report["status"], "blockers": "|".join(report["blockers"]),
                           "macro_entries": sum(r["classification"] == "macro" for r in report["ole_entries"]),
                           "embedded_entries": sum(r["classification"] == "embedded_object" for r in report["ole_entries"]),
                           "model_or_api_executed": "false", "numeric_target_emitted": "false"})
            recovery._write_json(local / f"{len(reports):03d}.json", report)
            print(f"static {len(reports)}/{recovery.EXPECTED_FILE_COUNT}: {report['container']} {report['status']}", flush=True)
        if len(reports) != recovery.EXPECTED_FILE_COUNT:
            raise recovery.RecoveryError("static workbook count differs")
        summary = summarize(reports)
        recovery._write_csv(output / "XLS_STATIC_SAFETY_LEDGER.csv", safety, tuple(safety[0]))
        recovery._write_json(output / "DATA_GATE_SUMMARY.json", summary)
        # These artifacts explicitly carry NOT_EVALUATED, never invented row counts,
        # identifiers, units or target eligibility in lieu of an unrun R1E.
        if summary["status"] == "BLOCKED_ROW_PARSE":
            for name in ("WORKBOOK_SCHEMA_LEDGER", "ROW_COUNT_LEDGER", "MISSINGNESS_LEDGER",
                         "UNIT_IDENTITY_LEDGER", "CHRONOLOGY_LEDGER", "DUPLICATE_OVERLAP_LEDGER",
                         "TARGET_DEFINITION_LEDGER", "EVENT_CENSOR_LEDGER"):
                records = [{"member_path": row["member_path"], "status": "NOT_EVALUATED_R1D_BLOCKED",
                            "row_evidence": "NA", "model_or_api_executed": "false", "numeric_target_emitted": "false"}
                           for row in safety]
                recovery._write_csv(output / (name + ".csv"), records, tuple(records[0]))
            recovery._write_json(output / "SPLIT_LEAKAGE_LEDGER.json", {
                "status": "BLOCKED_NO_VERIFIED_PHYSICAL_IDENTITY", "split_constructed": False,
                "physical_unit_count": None, **FLAGS})
        text = ("# Ren P1-R1 静态审计与 Data Gate\n\n"
                f"状态：`{summary['status']}`。检查 {len(reports)} 个工作簿；"
                f"{summary['workbooks_blocked']} 个存在静态分类阻断。\n\n"
                "本阶段只读取容器和 BIFF 结构，不解析数据行，不执行公式/宏。"
                "identity、target、chronology、duplicate、censor 均无行级裁决；P2 与 RUL 均未放行。\n\n"
                "详细阻断计数见 DATA_GATE_SUMMARY.json；逐工作簿分类见 XLS_STATIC_SAFETY_LEDGER.csv。\n")
        recovery._write_bytes(output / "DATA_GATE_REPORT.md", text.encode())
        recovery._write_json(output / "COMPLETE.json", {
            "status": "STATIC_AUDIT_COMPLETE", "data_gate_status": summary["status"],
            "row_gate_pass": False, **FLAGS})
        files = {"policy:" + name: project / name for name in POLICY_NAMES}
        files.update({"release": release_path, "recovery_seal": paths.output / "R1C_SEAL.json"})
        files.update({"artifact:" + path.name: path for path in output.iterdir()})
        files.update({"local:" + path.name: path for path in local.iterdir()})
        recovery._write_json(output / "ARTIFACT_MANIFEST.json", {"bound_files": recovery._bound(files), **FLAGS})
        return summary
    except Exception as exc:
        recovery._write_json(output / "STATIC_BLOCKED.json", {"status": "BLOCKED_STATIC_EXECUTION",
            "error_type": type(exc).__name__, "workbooks_completed": len(reports), **FLAGS})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(run(Path(args.project_root), args.run_id), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
