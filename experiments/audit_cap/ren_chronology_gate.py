"""Approved-scope read-only chronology observations, never final Data Gate."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import time

if __package__:
    from experiments.audit_cap import ren_fleet_schema as fleet
    from experiments.audit_cap import ren_chronology as chronology
else:
    import ren_fleet_schema as fleet
    import ren_chronology as chronology

RUN = "record_chronology_20260911_v1"
POLICY = (*fleet.POLICY, "experiments/audit_cap/ren_chronology.py",
    "experiments/audit_cap/ren_chronology_gate.py", "tests/test_ren_chronology.py",
    "refine-logs/REN_CHRONOLOGY_POLICY_20260911.md")
SCHEMA_SUMMARY_SHA = "361f9f854aa22fe02be8b5bc9cddcb3ebd36bc23b1979c5037ca3cc65b8e4b3f"
AUTHOR_SOURCE = "data/raw/ren_scs/author_source_20260911/preprocess.py.txt"
AUTHOR_SHA = "4c3a1b071464021393a31fece4531cdd01e139f524fdd02f9b71d58b44719d29"
FLAGS = {**fleet.FLAGS, "physical_identity_verified": False, "target_verified": False,
         "cross_group_partial_overlap_verified": False}


def candidate_groups(reports, schemas):
    groups = defaultdict(list)
    seen = set()
    for report in reports:
        member = report["member_path"]
        m = re.fullmatch(r"(batch[1-4])/([1-9][0-9]*)(?:__([1-9][0-9]*))?\.xls", member)
        if m is None or member in seen:
            raise ValueError("invalid or repeated source naming")
        seen.add(member)
        fragment = int(m[3] or 0)
        names = [s["name"] for s in schemas[member]["sheets"]]
        if fragment == 0:
            if names[:2] != ["step", "cycle"]:
                raise ValueError("main file lacks source schema")
        elif any(not n.startswith("record_") for n in names):
            raise ValueError("fragment contains nonrecord schema")
        groups[(m[1], int(m[2]))].append((fragment, report))
    ordered = []
    for group in sorted(groups):
        items = sorted(groups[group], key=lambda v: v[0])
        if [v[0] for v in items] != list(range(len(items))):
            raise ValueError("missing source-named fragment")
        ordered.append((f"{group[0]}/{group[1]}", [v[1] for v in items]))
    return ordered


def preflight(root):
    rec = fleet.pilot.context.recovery
    release = rec._strict_json(root / "refine-logs/REN_CHRONOLOGY_RELEASE.json")
    if (release.get("status") != "PASS_RECORD_CHRONOLOGY_AUDIT"
        or release.get("policy_sha256") != {p: rec._digests(root/p)["sha256"] for p in POLICY}
        or release.get("approval_record_sha256") != rec.APPROVAL_SHA256):
        raise ValueError("chronology pre-run release mismatch")
    reports, allowed = fleet.preflight(root)
    public = root / "data/audit/ren_scs" / fleet.RUN
    local = root / "data/raw/ren_scs" / fleet.RUN
    for p, digest in ((public/"SUMMARY.json", SCHEMA_SUMMARY_SHA), (root/AUTHOR_SOURCE, AUTHOR_SHA)):
        rec._no_symlink_components(root, p)
        if rec._digests(p)["sha256"] != digest:
            raise ValueError("chronology prerequisite mismatch")
    complete = rec._strict_json(public/"COMPLETE.json")
    if complete.get("summary_sha256") != SCHEMA_SUMMARY_SHA or complete.get("status") != "FLEET_SCHEMA_COMPLETE_NOT_DATA_GATE":
        raise ValueError("schema completion missing")
    schemas = {}
    for i, report in enumerate(reports, 1):
        p = local / f"{i:03d}.json"
        receipt = rec._strict_json(public/f"{i:03d}.json")
        rec._no_symlink_components(root, p)
        if (receipt["member_path"] != report["member_path"] or receipt["input_sha256"] != report["input_sha256"]
            or rec._digests(p)["sha256"] != receipt["schema_evidence_sha256"]):
            raise ValueError("prior schema receipt mismatch")
        schema = rec._strict_json(p)
        if schema["workbook_sha256"] != report["workbook_scans"][0]["stream_sha256"]:
            raise ValueError("prior schema stream mismatch")
        schemas[report["member_path"]] = schema
    groups = candidate_groups(reports, schemas)
    if (len(groups) != 113 or Counter(g.split("/")[0] for g,_ in groups) !=
        {"batch1":28,"batch2":25,"batch3":30,"batch4":30}
        or Counter(len(rs) for _,rs in groups) != {1:53,3:60}):
        raise ValueError("candidate source group coverage mismatch")
    return groups, schemas, allowed


def read_member(root, extraction, report, schema, allowed):
    rec = fleet.pilot.context.recovery
    path = extraction / report["member_path"]
    rec._no_symlink_components(root, path)
    info = rec._require_file(path, "chronology input")
    if info.st_nlink != 1 or info.st_size != report["input_bytes"]:
        raise ValueError("chronology input metadata changed")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != report["input_sha256"]:
        raise ValueError("chronology input changed")
    data = fleet.pilot.workbook_bytes(raw)
    del raw
    return chronology.workbook(data, allowed, schema)


def run(root):
    root = root.resolve(strict=True)
    groups, schemas, allowed = preflight(root)
    rec = fleet.pilot.context.recovery
    extraction = rec.Paths.build(str(root), fleet.pilot.context.RUN, new=False).extraction
    public, local = [root / p / RUN for p in ("data/audit/ren_scs", "data/raw/ren_scs")]
    for p in (public, local):
        rec._no_symlink_components(root, p)
        if p.exists():
            raise ValueError("chronology run append-only")
    public.mkdir(); local.mkdir(mode=0o700)
    receipts = []
    current = None
    started = time.monotonic()
    try:
        for i, (candidate, reports) in enumerate(groups, 1):
            current = candidate
            sheets = []
            for report in reports:
                member = report["member_path"]
                member_sheets = read_member(root, extraction, report, schemas[member], allowed)
                expected = [(s["index"], s["name"], s["nrows"]-1) for s in schemas[member]["sheets"]
                            if s["name"] not in ("step", "cycle")]
                if [(s["index"], s["name"], s["rows"]) for s in member_sheets] != expected:
                    raise ValueError("chronology record coverage mismatch")
                for sheet in member_sheets:
                    sheets.append(dict(member_path=member, **sheet))
            metrics = chronology.aggregate(sheets)
            evidence = dict(status="RECORD_CHRONOLOGY_OBSERVATIONS_NOT_DATA_GATE",
                source_naming_candidate=candidate, members=[r["member_path"] for r in reports],
                sheets=sheets, metrics=metrics, **FLAGS)
            p = local / f"{i:03d}.json"
            rec._write_json(p, evidence)
            saved = rec._strict_json(p)
            chronology.verify_fields(saved, evidence)
            chronology.verify_fields(saved["metrics"], chronology.aggregate(saved["sheets"]))
            receipt = dict(source_naming_candidate=candidate, member_count=len(reports),
                record_sheet_count=len(sheets), metrics=metrics,
                evidence_sha256=rec._digests(p)["sha256"], **FLAGS)
            rec._write_json(public/f"{i:03d}.json", receipt)
            receipts.append(receipt)
            print(json.dumps(dict(groups_audited=i, groups_expected=113,
                elapsed_seconds=round(time.monotonic()-started,1))), flush=True)
        # Rebuild persisted receipts before accepting completion, rather than
        # trusting the in-memory accumulator or an earlier successful write.
        verified = []
        for i, (candidate, reports) in enumerate(groups, 1):
            current = candidate
            p = local/f"{i:03d}.json"
            saved = rec._strict_json(p)
            if saved["source_naming_candidate"] != candidate or saved["members"] != [r["member_path"] for r in reports]:
                raise ValueError("persisted candidate identity mismatch")
            for name, value in FLAGS.items():
                if type(saved[name]) is not bool or saved[name] is not value:
                    raise ValueError("persisted authority flag mismatch")
            metrics = chronology.aggregate(saved["sheets"])
            chronology.verify_fields(saved["metrics"], metrics)
            expected = dict(source_naming_candidate=candidate, member_count=len(reports),
                record_sheet_count=len(saved["sheets"]), metrics=metrics,
                evidence_sha256=rec._digests(p)["sha256"], **FLAGS)
            receipt = rec._strict_json(public/f"{i:03d}.json")
            chronology.verify_fields(receipt, expected)
            verified.append(receipt)
        totals = {k: sum(r["metrics"][k] for r in verified) for k in verified[0]["metrics"]}
        summary = dict(status="FULL_CHRONOLOGY_OBSERVATIONS_DATA_GATE_PENDING",
            source_naming_candidates=len(verified), member_count=sum(r["member_count"] for r in verified),
            record_sheet_count=sum(r["record_sheet_count"] for r in verified), metrics=totals, **FLAGS)
        if summary["source_naming_candidates"] != 113 or summary["member_count"] != 233:
            raise ValueError("incomplete chronology audit")
        rec._write_json(public/"SUMMARY.json", summary)
        rec._write_json(public/"COMPLETE.json", dict(status="CHRONOLOGY_COMPLETE_NOT_DATA_GATE",
            summary_sha256=rec._digests(public/"SUMMARY.json")["sha256"], **FLAGS))
        return summary
    except Exception as exc:
        rec._write_json(public/"BLOCKED.json", dict(status="CHRONOLOGY_FAILED_CLOSED",
            failed_candidate=current, groups_audited=len(receipts), error_type=type(exc).__name__, **FLAGS))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    print(json.dumps(run(Path(parser.parse_args().project_root)), sort_keys=True))
