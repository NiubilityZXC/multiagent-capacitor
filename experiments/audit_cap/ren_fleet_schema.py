"""One append-only full-fleet R1E schema audit with independently rebuilt fields.

No targets, training, API, RUL, physical identity or final Data Gate eligibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

if __package__:
    from experiments.audit_cap import ren_row_pilot as pilot
    from experiments.audit_cap import verify_ren_fleet_schema as verifier
else:
    import ren_row_pilot as pilot
    import verify_ren_fleet_schema as verifier

RUN = "fleet_schema_20260911_v1"
POLICY = (*pilot.POLICY, "experiments/audit_cap/ren_fleet_schema.py",
          "experiments/audit_cap/verify_ren_fleet_schema.py",
          "tests/test_ren_fleet_schema.py", ".gitignore",
          "refine-logs/REN_FLEET_SCHEMA_POLICY_20260911.md")
PILOT_SUMMARY = "data/audit/ren_scs/row_pilot_20260910_v1/SUMMARY.json"
PILOT_SHA = "e6d5da4a48ec0017567f91ede6142a9d8cf244790addc94ad35d8f36ec6c3982"
FLAGS = dict(pilot.FLAGS)


def preflight(root: Path):
    rec = pilot.context.recovery
    release = rec._strict_json(root / "refine-logs/REN_FLEET_SCHEMA_RELEASE.json")
    policy = {name: rec._digests(root / name)["sha256"] for name in POLICY}
    if (release.get("status") != "PASS_FULL_FLEET_SCHEMA_AUDIT"
            or release.get("policy_sha256") != policy
            or release.get("approval_record_sha256") != rec.APPROVAL_SHA256):
        raise ValueError("fleet schema release mismatch")
    pilot.context.independent.verify(root, pilot.context.RUN)
    pilot.context.original.validate_environment(root)
    for name, expected in ((pilot.CATALOG, pilot.CATALOG_SHA),
            (pilot.DIAGNOSTIC, pilot.DIAGNOSTIC_SHA),
            (pilot.PRIOR_MANIFEST, pilot.PRIOR_MANIFEST_SHA), (PILOT_SUMMARY, PILOT_SHA)):
        rec._no_symlink_components(root, root / name)
        if rec._digests(root / name)["sha256"] != expected:
            raise ValueError("fleet prerequisite changed")
    reports = sorted(pilot.context.verify_static_artifacts(root), key=lambda r: r["member_path"])
    if len(reports) != 233 or len({r["member_path"] for r in reports}) != 233:
        raise ValueError("fleet coverage must be exactly 233 unique files")
    allowed = pilot.allowed_record_ids(rec._strict_json(root / pilot.CATALOG))
    diagnostics = rec._strict_json(root / pilot.DIAGNOSTIC)["workbooks"]
    lookup = {d["member_path"]: d for d in diagnostics}
    if len(lookup) != len(diagnostics):
        raise ValueError("duplicate fleet diagnostics")
    for report in reports:
        pilot.validate_selected(report, lookup.get(report["member_path"]), allowed)
        if not 0 < report["input_bytes"] <= 256 * 1024 * 1024:
            raise ValueError("fleet input size bound")
    return reports, allowed


def audit_member(root: Path, extraction: Path, report: dict, allowed: set[int]) -> dict:
    rec = pilot.context.recovery
    path = extraction / report["member_path"]
    rec._no_symlink_components(root, path)
    meta = rec._require_file(path, "fleet XLS")
    if meta.st_nlink != 1 or meta.st_size != report["input_bytes"]:
        raise ValueError("fleet member metadata changed")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != report["input_sha256"]:
        raise ValueError("fleet member digest changed")
    workbook = pilot.workbook_bytes(raw)
    del raw
    if hashlib.sha256(workbook).hexdigest() != report["workbook_scans"][0]["stream_sha256"]:
        raise ValueError("fleet Workbook digest changed")
    generated = pilot.schema_rows(workbook, allowed)
    reconstructed = verifier.rebuild(workbook, allowed)
    verifier.verify_fields(generated, reconstructed)
    return generated


def summarize(entries: list[dict]) -> dict:
    if len(entries) != 233 or len({e["member_path"] for e in entries}) != 233:
        raise ValueError("incomplete fleet, no completion report")
    return dict(status="FULL_FLEET_SCHEMA_VERIFIED_DATA_GATE_PENDING", files_verified=len(entries),
        sheet_count=sum(e["sheet_count"] for e in entries),
        stored_sheet_rows=sum(e["stored_sheet_rows"] for e in entries),
        nonfinite_count=sum(e["nonfinite_count"] for e in entries),
        row_parse_executed=True, independent_schema_reconstruction=True,
        identity_verified=False, target_verified=False, **FLAGS)


def run(root: Path) -> dict:
    root = root.resolve(strict=True)
    reports, allowed = preflight(root)
    rec = pilot.context.recovery
    extraction = rec.Paths.build(str(root), pilot.context.RUN, new=False).extraction
    public = root / "data/audit/ren_scs" / RUN
    local = root / "data/raw/ren_scs" / RUN
    for path in (public, local):
        rec._no_symlink_components(root, path)
        if path.exists():
            raise ValueError("fleet audit append-only; inspect old attempt")
    public.mkdir()
    local.mkdir(mode=0o700)
    entries = []
    started = time.monotonic()
    current = None
    try:
        rec._write_json(public / "STARTED.json", dict(run=RUN, files_expected=233, **FLAGS))
        for index, report in enumerate(reports, 1):
            current = report["member_path"]
            result = audit_member(root, extraction, report, allowed)
            evidence = local / f"{index:03d}.json"
            rec._write_json(evidence, result)
            # Re-read persisted evidence; verify again, preventing a report from
            # describing different bytes than the saved local artifact.
            saved = rec._strict_json(evidence)
            verifier.verify_fields(saved, result)
            entry = dict(member_path=current, input_sha256=report["input_sha256"],
                schema_evidence_sha256=rec._digests(evidence)["sha256"],
                sheet_count=len(saved["sheets"]),
                stored_sheet_rows=sum(s["nrows"] for s in saved["sheets"]),
                nonfinite_count=sum(s["nonfinite_count"] for s in saved["sheets"]),
                independent_schema_reconstruction=True, **FLAGS)
            rec._write_json(public / f"{index:03d}.json", entry)
            entries.append(entry)
            print(json.dumps(dict(files_verified=index, files_expected=233,
                                  elapsed_seconds=round(time.monotonic()-started, 1))), flush=True)
        # Independently recompute each public receipt from local schema and the
        # frozen source list; no trust in the in-memory receipt accumulator.
        receipts = []
        for index, report in enumerate(reports, 1):
            evidence = local / f"{index:03d}.json"
            document = rec._strict_json(evidence)
            nrows = nsheets = invalid = 0
            for sheet in document["sheets"]:
                nsheets += 1
                nrows += sheet["nrows"]
                invalid += sheet["nonfinite_count"]
            expected = dict(member_path=report["member_path"], input_sha256=report["input_sha256"],
                schema_evidence_sha256=rec._digests(evidence)["sha256"], sheet_count=nsheets,
                stored_sheet_rows=nrows, nonfinite_count=invalid,
                independent_schema_reconstruction=True, **FLAGS)
            receipt = rec._strict_json(public / f"{index:03d}.json")
            verifier.verify_fields(receipt, expected)
            receipts.append(receipt)
        summary = summarize(receipts)
        rec._write_json(public / "SUMMARY.json", summary)
        rec._write_json(public / "COMPLETE.json", dict(status="FLEET_SCHEMA_COMPLETE_NOT_DATA_GATE",
            summary_sha256=rec._digests(public / "SUMMARY.json")["sha256"], **FLAGS))
        return summary
    except Exception as exc:
        rec._write_json(public / "BLOCKED.json", dict(status="FLEET_SCHEMA_FAILED_CLOSED",
            files_verified=len(entries), failed_member=current, error_type=type(exc).__name__, **FLAGS))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    print(json.dumps(run(Path(parser.parse_args().project_root)), sort_keys=True))
