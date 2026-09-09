"""Read-only blocker diagnosis, never a replacement Data Gate or row reader."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import struct

if __package__:
    from experiments.audit_cap import ren_p1r1_recovery as recovery
    from experiments.audit_cap import verify_ren_p1r1_recovery as independent
    from experiments.audit_cap import ren_p1r1_static_gate as original
else:
    import ren_p1r1_recovery as recovery
    import verify_ren_p1r1_recovery as independent
    import ren_p1r1_static_gate as original

RUN = "p1r1_20260908_150800"
POLICY = ("experiments/audit_cap/ren_static_context.py", "tests/test_ren_static_context.py")
FLAGS = {**original.FLAGS, "p2_eligible": False, "row_parse_authorized": False}


def directory_kind(parts: list[str]) -> str:
    """Diagnostic names only, not a safety verdict; never open these streams."""
    folded = tuple(p.casefold() for p in parts)
    if len(parts) == 1 and folded[0] in ("workbook", "book"):
        return "workbook"
    if len(parts) == 1 and folded[0] == "\x01compobj":
        return "root_compobj_metadata_marker"
    if folded[0] == "_vba_project_cur":
        return "vba_project_tree_marker"
    if any(p in ("objectpool", "package", "\x01ole10native") or p.startswith("mbd") for p in folded):
        return "embedded_container_marker"
    if any(p in ("vba", "_vba_project", "macros", "project", "projectwm") for p in folded):
        return "other_macro_name_marker"
    if len(parts) == 1 and folded[0] in ("\x05summaryinformation", "\x05documentsummaryinformation"):
        return "summary_metadata_marker"
    return "unclassified_directory_marker"


def continuation_context(data: bytes) -> dict:
    """Frame headers only; skip every payload, including cell/print data."""
    cursor = count = 0
    predecessor = None
    previous = None
    chains = []
    while cursor < len(data):
        if len(data) - cursor < 4:
            raise ValueError("truncated record header")
        kind, size = struct.unpack_from("<HH", data, cursor)
        if size > 8224 or cursor + 4 + size > len(data):
            raise ValueError("invalid record framing")
        if kind == 0x002F:
            raise ValueError("encrypted FILEPASS")
        if kind == 0x003C:
            if previous == 0x003C:
                chains[-1]["continue_records"] += 1
                chains[-1]["payload_bytes"] += size
            else:
                chains.append({"offset": cursor, "predecessor_record_id":
                               None if predecessor is None else f"0x{predecessor:04X}",
                               "continue_records": 1, "payload_bytes": size,
                               "following_record_id": None})
        else:
            if previous == 0x003C:
                chains[-1]["following_record_id"] = f"0x{kind:04X}"
            predecessor = kind
        previous = kind
        cursor += 4 + size
        count += 1
    return {"records_framed": count, "bytes_framed": cursor, "chains": chains,
            "payloads_decoded": False, **FLAGS}


def inspect_container(data: bytes, inspect_continue: bool, olefile_module=None) -> dict:
    if len(data) > 256 * 1024 * 1024:
        raise ValueError("input limit")
    if olefile_module is None:
        import olefile as olefile_module
    entries = []
    context = None
    with olefile_module.OleFileIO(io.BytesIO(data), write_mode=False,
                                 raise_defects=olefile_module.DEFECT_INCORRECT) as ole:
        names = ole.listdir(streams=True, storages=True)
        if len(names) > 4096:
            raise ValueError("directory limit")
        seen = set()
        workbook_count = 0
        for parts in names:
            if not parts or any(not isinstance(p, str) or not p or "/" in p or "\\" in p for p in parts):
                raise ValueError("invalid directory entry")
            folded = tuple(p.casefold() for p in parts)
            if folded in seen:
                raise ValueError("duplicate directory entry")
            seen.add(folded)
            kind = directory_kind(parts)
            entry_type = ole.get_type(parts)
            if entry_type not in (1, 2):
                raise ValueError("unexpected OLE type")
            entries.append({"path_sha256": hashlib.sha256("/".join(parts).encode("utf-8", errors="surrogatepass")).hexdigest(),
                            "kind": kind, "ole_entry_type": entry_type})
            if kind == "workbook":
                workbook_count += 1
                if entry_type != 2:
                    raise ValueError("workbook is not a stream")
                if inspect_continue:
                    size = ole.get_size(parts)
                    if not 0 <= size <= 256 * 1024 * 1024:
                        raise ValueError("stream limit")
                    with ole.openstream(parts) as stream:
                        payload = stream.read(size + 1)
                    if len(payload) != size:
                        raise ValueError("stream length mismatch")
                    context = continuation_context(payload)
        if workbook_count != 1 or getattr(ole, "parsing_issues", None) != []:
            raise ValueError("container structure mismatch or defects")
    return {"input_sha256": hashlib.sha256(data).hexdigest(), "entries": entries,
            "continuation_context": context, "status": "DIAGNOSTIC_ONLY_NO_GATE_CHANGE", **FLAGS}


def verify_static_artifacts(project: Path) -> list[dict]:
    output = project / "data/audit/ren_scs" / (RUN + "_static")
    local = project / "data/raw/ren_scs" / RUN / "static_evidence"
    manifest = recovery._strict_json(output / "ARTIFACT_MANIFEST.json")
    for key, expected in manifest["bound_files"].items():
        if key.startswith("policy:") and key[7:] in original.POLICY_NAMES:
            path = project / key[7:]
        elif key.startswith("artifact:") and Path(key[9:]).name == key[9:]:
            path = output / key[9:]
        elif key.startswith("local:") and Path(key[6:]).name == key[6:]:
            path = local / key[6:]
        elif key == "release":
            path = project / "refine-logs/REN_P1R1_R1D_RELEASE.json"
        elif key == "recovery_seal":
            path = project / "data/audit/ren_scs" / RUN / "R1C_SEAL.json"
        else:
            raise ValueError("unknown static manifest binding")
        recovery._no_symlink_components(project, path)
        if recovery._digests(path) != expected:
            raise ValueError("prior static artifact changed")
    reports = [recovery._strict_json(local / f"{i:03d}.json") for i in range(1, 234)]
    if len({r["member_path"] for r in reports}) != 233:
        raise ValueError("duplicate static members")
    return reports


def run(project: Path) -> dict:
    project = project.resolve(strict=True)
    paths = recovery.Paths.build(str(project), RUN, new=False)
    independent.verify(project, RUN)
    original.validate_environment(project)
    release = recovery._strict_json(project / "refine-logs/REN_STATIC_CONTEXT_RELEASE.json")
    policy = {name: recovery._digests(project / name)["sha256"] for name in POLICY}
    prior_manifest = project / "data/audit/ren_scs" / (RUN + "_static") / "ARTIFACT_MANIFEST.json"
    if (release.get("status") != "PASS_DIAGNOSTIC_ONLY" or release.get("policy_sha256") != policy
            or release.get("prior_manifest_sha256") != recovery._digests(prior_manifest)["sha256"]
            or release.get("approval_record_sha256") != recovery.APPROVAL_SHA256):
        raise ValueError("diagnostic pre-run release mismatch")
    reports = verify_static_artifacts(project)
    output = project / "data/audit/ren_scs" / (RUN + "_static_context_v1")
    recovery._no_symlink_components(project, output)
    output.mkdir()  # append-only: never update a prior diagnosis
    try:
        kinds = Counter()
        chains = Counter()
        details = []
        for report in reports:
            blockers = report["blockers"]
            has_continue = "unclassified_active_or_context_record_CONTINUE" in blockers
            if not has_continue and not any(b.startswith("ole_") for b in blockers):
                continue
            path = paths.extraction / report["member_path"]
            recovery._no_symlink_components(project, path)
            meta = recovery._require_file(path, "diagnostic workbook")
            if meta.st_size != report["input_bytes"] or meta.st_nlink != 1:
                raise ValueError("diagnostic input changed")
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != report["input_sha256"]:
                raise ValueError("diagnostic input hash mismatch")
            diagnostic = inspect_container(data, has_continue)
            diagnostic["member_path"] = report["member_path"]
            kinds.update({e["kind"] for e in diagnostic["entries"]})
            if diagnostic["continuation_context"] is not None:
                for chain in diagnostic["continuation_context"]["chains"]:
                    chains[str(chain["predecessor_record_id"]) + "->CONTINUE->" + str(chain["following_record_id"])] += 1
            details.append(diagnostic)
        summary = {"status": "DIAGNOSTIC_COMPLETE_GATE_UNCHANGED", "workbooks_inspected": len(details),
                   "directory_kind_workbook_counts": dict(sorted(kinds.items())),
                   "continuation_chain_counts": dict(sorted(chains.items())), **FLAGS}
        recovery._write_json(output / "DIAGNOSTICS.json", {"workbooks": details, **FLAGS})
        recovery._write_json(output / "SUMMARY.json", summary)
        recovery._write_json(output / "COMPLETE.json", {"status": "DIAGNOSTIC_COMPLETE", **FLAGS})
        return summary
    except Exception as exc:
        recovery._write_json(output / "BLOCKED.json", {"status": "DIAGNOSTIC_FAILED_CLOSED",
                                                       "error_type": type(exc).__name__, **FLAGS})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    print(json.dumps(run(Path(parser.parse_args().project_root)), sort_keys=True))
