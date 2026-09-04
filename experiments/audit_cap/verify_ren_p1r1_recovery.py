#!/usr/bin/env python3
"""Independent verifier for the sealed Ren P1-R1 R1A--R1C recovery."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Any, Mapping, NoReturn, Sequence
from urllib.parse import urlsplit
import zlib


SCHEMA_VERSION = "audit-cap.ren-p1r1-recovery-verifier.v2"
GENERATOR_SCHEMA = "audit-cap.ren-p1r1-recovery.v2"
PLAN_SHA256 = "a7a8f5521b6b249af59a9ded0971cb02f912d9f46e8babfe3d60777cbfcc3c6d"
PACKET_SHA256 = "8ea05474bf90609a89e2c6e1725777e6c9030c2dae5067d94c3ad6b54511c365"
APPROVAL_SHA256 = "314dc2e62acf35eccf0053a8fd77591a1bc90d82fae9e70e1dbc4820f882f2d8"
PRIOR_SHA256 = "66353535e49f815bd32ed79615c13e78458bec5727acc90ab85fc3763acace4b"
ARCHIVE_BYTES = 2_114_703_017
ARCHIVE_MD5 = "26a7a663217c59377c83fb2a8274466b"
ARCHIVE_SHA256 = "a8f1083b887f95483561a94b624b323ff42814654ee7f23e7f95bc042fa258d8"
TOOL_TAR_SHA256 = "759b4b6aa0d9f77131882162951193f3a0e54bf60e1d8dc4255aa308accab588"
RAR_SHA256 = "56c3c4fd46faa7a9f52264d30cb96813e19ec7c4587d9f18424d7e909cf78555"
UNRAR_SHA256 = "926d3a00775ed96afccfdef69c3781334b71ccdb733931edf30f4866e4f08410"
LICENSE_SHA256 = "0420a0c2cd464466c13ddac80c2efd083163ca82c193fa59df068d8386c3f141"
MEMBER_COUNT, FILE_COUNT, DIRECTORY_COUNT, FILE_BYTES = 237, 233, 4, 15_223_551_488
RUN_RE = re.compile(r"p1r1_[0-9]{8}_[0-9]{6}")
R1A = (
    "DOWNLOAD_PAGE.curl.json", "DOWNLOAD_PAGE.headers.txt", "DOWNLOAD_PAGE.html",
    "TOOL_DOWNLOAD.curl.json", "TOOL_DOWNLOAD.headers.txt", "TOOL_IDENTITY.json",
    "TOOL_HASH_LEDGER.csv", "RAR_VERSION.stdout.txt", "RAR_VERSION.stderr.txt",
    "UNRAR_VERSION.stdout.txt", "UNRAR_VERSION.stderr.txt", "OFFICIAL_LISTING.stdout.txt",
    "OFFICIAL_LISTING.stderr.txt", "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv",
    "ARCHIVE_LISTING_DIFF.json", "R1A_PREFLIGHT.json",
)
R1B = ("ARCHIVE_TEST.stdout.txt", "ARCHIVE_TEST.stderr.txt", "ARCHIVE_TEST_REPORT.json")
R1C = ("EXTRACTION.stdout.txt", "EXTRACTION.stderr.txt", "EXTRACTION_MEMBER_LEDGER.csv", "EXTRACTION_MANIFEST.json")
EXACT_ARTIFACTS = frozenset((*R1A, "R1A_SEAL.json", *R1B, "R1B_SEAL.json", *R1C, "R1C_SEAL.json"))
PRIOR_HEADER = (
    "member_path", "member_type", "batch_path_component", "provisional_filename_stem",
    "segment_suffix", "uncompressed_bytes", "packed_bytes", "crc", "compression_method",
    "encrypted", "link_fields_empty", "extension", "listing_safety_status", "row_content_status",
)
OFFICIAL_HEADER = (
    "member_path", "member_type", "uncompressed_bytes", "packed_bytes", "crc",
    "compression_method", "encrypted", "link_or_redirection", "extension", "safety_status",
    "mtime", "attributes", "host_os", "model_or_api_executed", "numeric_target_emitted",
)
EXTRACTION_HEADER = (
    "member_path", "observed_type", "hardlink_count", "observed_bytes", "expected_bytes",
    "observed_crc32", "expected_crc32", "type_match", "size_match", "crc_match", "status",
    "model_or_api_executed", "numeric_target_emitted",
)


class VerificationError(RuntimeError):
    pass


def _fail(message: str) -> NoReturn:
    raise VerificationError(message)


def _file(path: Path) -> os.stat_result:
    try: meta = path.lstat()
    except FileNotFoundError as exc: raise VerificationError(f"missing file: {path}") from exc
    if stat.S_ISLNK(meta.st_mode) or not stat.S_ISREG(meta.st_mode): _fail(f"not a regular file: {path}")
    return meta


def _dir(path: Path) -> os.stat_result:
    try: meta = path.lstat()
    except FileNotFoundError as exc: raise VerificationError(f"missing directory: {path}") from exc
    if stat.S_ISLNK(meta.st_mode) or not stat.S_ISDIR(meta.st_mode): _fail(f"not a real directory: {path}")
    return meta


def _hash(path: Path, md5: bool = False) -> dict[str, Any]:
    meta = _file(path); sha = hashlib.sha256(); old = hashlib.md5(usedforsecurity=False) if md5 else None
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha.update(block)
            if old is not None: old.update(block)
    value: dict[str, Any] = {"bytes": meta.st_size, "sha256": sha.hexdigest()}
    if old is not None: value["md5"] = old.hexdigest()
    return value


def _json(path: Path) -> dict[str, Any]:
    _file(path)
    def pairs(items: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result: _fail(f"duplicate JSON key in {path.name}: {key}")
            result[key] = value
        return result
    def constant(token: str) -> NoReturn: _fail(f"non-finite JSON in {path.name}: {token}")
    try: value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise VerificationError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict): _fail(f"non-object JSON: {path}")
    return value


def _csv(path: Path, header: Sequence[str]) -> list[dict[str, str]]:
    _file(path)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != tuple(header): _fail(f"CSV header mismatch: {path.name}")
        rows = list(reader)
    return rows


def _flags(payload: Mapping[str, Any], name: str) -> None:
    if payload.get("model_or_api_executed") is not False:
        _fail(f"model_or_api_executed is missing/true: {name}")
    if payload.get("numeric_target_emitted") is not False:
        _fail(f"numeric_target_emitted is missing/true: {name}")


def _run(argv: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    try: return subprocess.run(list(argv), check=False, capture_output=True, timeout=300,
                               env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError) as exc: raise VerificationError("independent listing failed") from exc


def _parse_listing(raw: bytes) -> list[dict[str, Any]]:
    text = raw.decode("utf-8", errors="strict")
    if "UNRAR 7.23 freeware" not in text or "Details: RAR 5" not in text: _fail("listing banners differ")
    rows = []
    for block in re.split(r"\n\s*\n", text):
        fields = {match.group(1).strip(): match.group(2).strip() for line in block.splitlines()
                  if (match := re.match(r"^\s*([^:]+):\s*(.*)$", line))}
        if "Name" not in fields or "Type" not in fields: continue
        name = fields["Name"]; pure = PurePosixPath(name)
        if not name or pure.is_absolute() or ".." in pure.parts or "." in pure.parts or "\\" in name or str(pure) != name: _fail(f"unsafe independent path: {name}")
        kind = fields["Type"]
        if kind not in {"File", "Directory"}: _fail(f"special independent member: {name}")
        danger = {key: value for key, value in fields.items() if value and any(token in key.casefold() for token in ("redir", "link", "target", "encrypt", "password"))}
        if danger or re.search(r"(?i)\b(encrypted|password protected|symbolic link|hard link|redirection)\b", block): _fail(f"active/link marker: {name}")
        if kind == "File":
            if pure.suffix.lower() != ".xls": _fail(f"extension mismatch: {name}")
            try: size, packed = int(fields["Size"]), int(fields["Packed size"])
            except (KeyError, ValueError) as exc: raise VerificationError(f"size mismatch: {name}") from exc
            crc = fields.get("CRC32", "")
            if re.fullmatch(r"[0-9A-F]{8}", crc) is None: _fail(f"CRC mismatch: {name}")
            match = re.search(r"-m([0-5])\s+-md=(\d+)([kmg])", fields.get("Compression", ""), re.I)
            if match is None: _fail(f"compression mismatch: {name}")
            dictionary = int(match.group(2)); base = {"k": 10, "m": 20, "g": 30}[match.group(3).lower()]
            if dictionary <= 0 or dictionary & (dictionary - 1): _fail(f"dictionary mismatch: {name}")
            method = f"m{match.group(1)}:{base + dictionary.bit_length() - 1}"
        else: size, packed, crc, method = 0, 0, "00000000", "m0"
        rows.append({"member_path": name, "member_type": "regular_file" if kind == "File" else "directory",
                     "uncompressed_bytes": size, "packed_bytes": packed, "crc": crc, "compression_method": method,
                     "encrypted": "false", "link_or_redirection": "false", "extension": pure.suffix.lower() if kind == "File" else "NA",
                     "safety_status": "PASS", "mtime": fields.get("mtime", "NA"), "attributes": fields.get("Attributes", "NA"),
                     "host_os": fields.get("Host OS", "NA"), "model_or_api_executed": "false", "numeric_target_emitted": "false"})
    if len(rows) != MEMBER_COUNT or len({row["member_path"] for row in rows}) != MEMBER_COUNT: _fail("independent member count/uniqueness mismatch")
    return rows


def _prior(path: Path) -> dict[str, dict[str, Any]]:
    if _hash(path)["sha256"] != PRIOR_SHA256: _fail("prior ledger hash mismatch")
    rows = _csv(path, PRIOR_HEADER); result = {}
    for row in rows:
        is_dir = row["member_type"] == "directory"
        if row["encrypted"] != "-" or row["link_fields_empty"] != "True" or row["listing_safety_status"] != "PASS_LISTING_METADATA" or row["row_content_status"] != "NOT_EXTRACTED_NOT_PARSED": _fail("prior safety flag mismatch")
        result[row["member_path"]] = {"member_type": "directory" if is_dir else "regular_file",
            "uncompressed_bytes": 0 if is_dir else int(row["uncompressed_bytes"]), "packed_bytes": 0 if is_dir else int(row["packed_bytes"]),
            "crc": "00000000" if is_dir else row["crc"], "compression_method": "m0" if is_dir else row["compression_method"],
            "encrypted": "false", "link_or_redirection": "false", "extension": "NA" if is_dir else row["extension"], "safety_status": "PASS"}
    if len(result) != MEMBER_COUNT: _fail("prior member count mismatch")
    return result


def _bound(files: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    return {key: _hash(path) for key, path in sorted(files.items())}


def _verify_seal(path: Path, stage: str, expected: Mapping[str, Mapping[str, Any]]) -> None:
    value = _json(path); _flags(value, path.name)
    if value.get("schema_version") != GENERATOR_SCHEMA or value.get("stage") != stage or value.get("status") != f"PASS_{stage}_SEALED" or value.get("bound_files") != expected or value.get("automatic_next_stage") is not False: _fail(f"seal mismatch: {stage}")


def _ok_paths(raw: bytes, action: str) -> list[str]:
    pattern = re.compile(rf"^{action}\s+(.+?)\s+OK\s*$")
    return [m.group(1).strip() for line in raw.decode("utf-8", errors="replace").replace("\r", "\n").splitlines() if (m := pattern.match(line.strip()))]


def _crc(path: Path) -> str:
    value = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""): value = zlib.crc32(block, value)
    return f"{value & 0xFFFFFFFF:08X}"


def verify(project: Path, run_id: str) -> dict[str, Any]:
    if RUN_RE.fullmatch(run_id) is None: _fail("invalid run id")
    project = project.resolve(strict=True); output = project / "data/audit/ren_scs" / run_id; local = project / "data/raw/ren_scs" / run_id
    extraction = local / "quarantine_extracted"; archive = project / "data/raw/ren_scs/raw.rar"
    prior = project / "data/audit/ren_scs/p1_20260828_180210/ARCHIVE_MEMBER_LEDGER.csv"
    plan = project / "refine-logs/REN_P1R1_ARCHIVE_RECOVERY_PLAN_20260904_145423.md"
    packet = project / "refine-logs/REN_P1R1_APPROVAL_PACKET_20260904_145423.json"
    approval = project / "refine-logs/REN_P1R1_APPROVAL_RECORD_20260904_213130.json"
    tool_tar, tool_root = local / "tool/rarlinux-x64-723.tar.gz", local / "tool/unpacked"
    _dir(output); _dir(local); _dir(extraction)
    observed_names = {path.name for path in output.iterdir()}
    if observed_names != EXACT_ARTIFACTS: _fail(f"exact artifact set mismatch: missing={sorted(EXACT_ARTIFACTS-observed_names)}, unexpected={sorted(observed_names-EXACT_ARTIFACTS)}")
    for path in output.iterdir(): _file(path)
    frozen = ((plan, PLAN_SHA256), (packet, PACKET_SHA256), (approval, APPROVAL_SHA256),
              (prior, PRIOR_SHA256), (tool_tar, TOOL_TAR_SHA256), (tool_root / "rar/rar", RAR_SHA256),
              (tool_root / "rar/unrar", UNRAR_SHA256), (tool_root / "rar/license.txt", LICENSE_SHA256))
    for path, digest in frozen:
        if _hash(path)["sha256"] != digest: _fail(f"frozen hash mismatch: {path.name}")
    if _hash(archive, True) != {"bytes": ARCHIVE_BYTES, "sha256": ARCHIVE_SHA256, "md5": ARCHIVE_MD5}: _fail("archive identity mismatch")
    approved = _json(approval)
    if approved.get("approval_token") != f"APPROVE_REN_P1R1:{PLAN_SHA256}" or approved.get("automatic_next_stage") is not False: _fail("approval boundary mismatch")

    authority = {"source_archive": archive, "frozen_plan": plan, "approval_packet": packet,
                 "approval_record": approval, "prior_listing_ledger": prior}
    r1a_files = dict(authority); r1a_files.update({f"artifact:{n}": output / n for n in R1A})
    r1a_files.update({"tool_tarball": tool_tar, "rar_binary": tool_root / "rar/rar", "unrar_binary": tool_root / "rar/unrar", "tool_license": tool_root / "rar/license.txt"})
    _verify_seal(output / "R1A_SEAL.json", "R1A", _bound(r1a_files))
    r1b_files = dict(r1a_files); r1b_files["seal:R1A"] = output / "R1A_SEAL.json"; r1b_files.update({f"artifact:{n}": output / n for n in R1B})
    _verify_seal(output / "R1B_SEAL.json", "R1B", _bound(r1b_files))
    r1c_files = dict(r1b_files); r1c_files["seal:R1B"] = output / "R1B_SEAL.json"; r1c_files.update({f"artifact:{n}": output / n for n in R1C})
    _verify_seal(output / "R1C_SEAL.json", "R1C", _bound(r1c_files))

    for name in ("DOWNLOAD_PAGE.curl.json", "TOOL_DOWNLOAD.curl.json", "TOOL_IDENTITY.json", "ARCHIVE_LISTING_DIFF.json", "R1A_PREFLIGHT.json", "ARCHIVE_TEST_REPORT.json", "EXTRACTION_MANIFEST.json"):
        payload = _json(output / name); _flags(payload, name)
    page_receipt, tool_receipt = _json(output / "DOWNLOAD_PAGE.curl.json"), _json(output / "TOOL_DOWNLOAD.curl.json")
    if page_receipt.get("requested_url") != "https://www.rarlab.com/download.htm" or page_receipt.get("effective_scheme_host_path") != "https://www.rarlab.com/download.htm": _fail("download page receipt URL mismatch")
    if tool_receipt.get("requested_url") != "https://www.rarlab.com/rar/rarlinux-x64-723.tar.gz" or tool_receipt.get("effective_scheme_host_path") != "https://www.rarlab.com/rar/rarlinux-x64-723.tar.gz" or tool_receipt.get("payload") != _hash(tool_tar): _fail("tool receipt URL/payload mismatch")
    if b"RAR for Linux x64 7.23" not in (output / "DOWNLOAD_PAGE.html").read_bytes(): _fail("download-page version evidence mismatch")
    if (output / "RAR_VERSION.stdout.txt").read_bytes() != b"7.23\n" or (output / "UNRAR_VERSION.stdout.txt").read_bytes() != b"7.23\n" or (output / "RAR_VERSION.stderr.txt").read_bytes() or (output / "UNRAR_VERSION.stderr.txt").read_bytes(): _fail("version transcripts mismatch")

    independent = _run([str(tool_root / "rar/unrar"), "lt", "-v", "-p-", str(archive)])
    if independent.returncode != 0 or independent.stderr: _fail("independent listing command failed")
    if independent.stdout != (output / "OFFICIAL_LISTING.stdout.txt").read_bytes(): _fail("stored listing transcript is not independently reproducible")
    official = _parse_listing(independent.stdout); stored = _csv(output / "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv", OFFICIAL_HEADER)
    if [{key: str(value) for key, value in row.items()} for row in official] != stored: _fail("stored member ledger differs from independent parse")
    prior_rows = _prior(prior); compare_keys = ("member_type", "uncompressed_bytes", "packed_bytes", "crc", "compression_method", "encrypted", "link_or_redirection", "extension", "safety_status")
    for row in official:
        old = prior_rows.get(row["member_path"])
        if old is None or any(str(row[key]) != str(old[key]) for key in compare_keys): _fail(f"independent prior diff: {row['member_path']}")
    files = [row for row in official if row["member_type"] == "regular_file"]
    if len(files) != FILE_COUNT or len(official) - len(files) != DIRECTORY_COUNT or sum(int(row["uncompressed_bytes"]) for row in files) != FILE_BYTES: _fail("independent listing aggregate mismatch")

    test_stdout = (output / "ARCHIVE_TEST.stdout.txt").read_bytes(); test_stderr = (output / "ARCHIVE_TEST.stderr.txt").read_bytes()
    expected_paths = sorted(row["member_path"] for row in files); observed_test = sorted(_ok_paths(test_stdout, "Testing"))
    combined = (test_stdout + b"\n" + test_stderr).decode("utf-8", errors="replace").replace("\r", "\n")
    if test_stderr or observed_test != expected_paths or len(re.findall(r"^All OK\s*$", combined, re.M)) != 1 or re.search(r"unsupported|crc failed|data error|checksum error|wrong password|enter password|corrupt|damaged|warning", combined, re.I): _fail("archive test transcript is not a complete PASS")
    report = _json(output / "ARCHIVE_TEST_REPORT.json")
    if report.get("status") != "PASS_ARCHIVE_TEST" or report.get("return_code") != 0 or report.get("tested_path_set_exact") is not True or report.get("observed_tested_file_count") != FILE_COUNT: _fail("archive test report mismatch")

    listed = {row["member_path"]: row for row in official}; scanned = {}
    for path in sorted(extraction.rglob("*")):
        rel = path.relative_to(extraction).as_posix(); meta = path.lstat()
        if stat.S_ISLNK(meta.st_mode): _fail(f"extracted symlink: {rel}")
        if stat.S_ISREG(meta.st_mode):
            if meta.st_nlink != 1: _fail(f"extracted hardlink: {rel}")
            scanned[rel] = {"type": "regular_file", "bytes": meta.st_size, "crc": _crc(path), "nlink": str(meta.st_nlink)}
        elif stat.S_ISDIR(meta.st_mode): scanned[rel] = {"type": "directory", "bytes": 0, "crc": "00000000", "nlink": "NA"}
        else: _fail(f"extracted special member: {rel}")
    if set(scanned) != set(listed): _fail("extracted path set differs")
    for rel, actual in scanned.items():
        expected = listed[rel]
        if actual["type"] != expected["member_type"] or actual["bytes"] != int(expected["uncompressed_bytes"]) or actual["crc"] != expected["crc"]: _fail(f"extracted identity differs: {rel}")
    ledger = _csv(output / "EXTRACTION_MEMBER_LEDGER.csv", EXTRACTION_HEADER)
    if len(ledger) != MEMBER_COUNT or {row["member_path"] for row in ledger} != set(scanned): _fail("extraction ledger path/count mismatch")
    for row in ledger:
        actual, expected = scanned[row["member_path"]], listed[row["member_path"]]
        exact = {"observed_type": actual["type"], "hardlink_count": actual["nlink"], "observed_bytes": str(actual["bytes"]),
                 "expected_bytes": str(expected["uncompressed_bytes"]), "observed_crc32": actual["crc"], "expected_crc32": expected["crc"],
                 "type_match": "true", "size_match": "true", "crc_match": "true", "status": "PASS",
                 "model_or_api_executed": "false", "numeric_target_emitted": "false"}
        if any(row[key] != value for key, value in exact.items()): _fail(f"extraction ledger row mismatch: {row['member_path']}")
    manifest = _json(output / "EXTRACTION_MANIFEST.json")
    if manifest.get("status") != "PASS_EXTRACTION_BYTE_IDENTITY" or manifest.get("quarantine_state") != "RELEASED_FOR_READ_ONLY_ROW_AUDIT" or manifest.get("observed_member_count") != MEMBER_COUNT or manifest.get("observed_regular_file_bytes") != FILE_BYTES: _fail("extraction manifest mismatch")
    return {"schema_version": SCHEMA_VERSION, "status": "PASS_R1ABC_INDEPENDENT_VERIFICATION",
            "verified_member_count": MEMBER_COUNT, "verified_regular_file_count": FILE_COUNT,
            "verified_directory_count": DIRECTORY_COUNT, "verified_regular_file_bytes": FILE_BYTES,
            "archive_sha256": ARCHIVE_SHA256, "workbook_opened_or_parsed": False,
            "model_or_api_executed": False, "numeric_target_emitted": False, "automatic_next_stage": False}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--project-root", required=True); parser.add_argument("--run-id", required=True); parser.add_argument("--report")
    args = parser.parse_args(argv); result = verify(Path(args.project_root), args.run_id)
    if args.report:
        target = Path(args.report)
        if target.exists() or target.is_symlink(): _fail("verification report already exists")
        with target.open("xb") as stream:
            stream.write((json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
