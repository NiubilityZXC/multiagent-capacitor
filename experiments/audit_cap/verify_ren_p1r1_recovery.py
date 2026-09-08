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
import tarfile
from typing import Any, Mapping, NoReturn, Sequence
from urllib.parse import urlsplit
import zlib


SCHEMA_VERSION = "audit-cap.ren-p1r1-recovery-verifier.v5"
GENERATOR_SCHEMA = "audit-cap.ren-p1r1-recovery.v5"
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
CURL_SHA256 = "74b4ce8f74b377f18ef1b3df7279c26cb3cd14c49e39ab1498575b209dc3f70f"
MEMBER_COUNT, FILE_COUNT, DIRECTORY_COUNT, FILE_BYTES = 237, 233, 4, 15_223_551_488
MIN_DISK_SAFETY_BYTES = 10 * 1024**3
RUN_RE = re.compile(r"p1r1_[0-9]{8}_[0-9]{6}")
R1A = (
    "DOWNLOAD_PAGE_RECEIPT.json", "TOOL_DOWNLOAD_RECEIPT.json", "TOOL_IDENTITY.json",
    "TOOL_HASH_LEDGER.csv", "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv",
    "ARCHIVE_LISTING_DIFF.json", "R1A_PREFLIGHT.json",
)
R1B = ("ARCHIVE_TEST_REPORT.json",)
R1C = ("EXTRACTION_MEMBER_LEDGER.csv", "EXTRACTION_MANIFEST.json")
EXACT_ARTIFACTS = frozenset((*R1A, "R1A_SEAL.json", *R1B, "R1B_SEAL.json", *R1C, "R1C_SEAL.json"))
VERIFICATION_REPORT = "R1ABC_INDEPENDENT_VERIFICATION.json"
R1A_LOCAL = (
    "DOWNLOAD_PAGE.headers.raw", "DOWNLOAD_PAGE.curl.stdout.raw", "DOWNLOAD_PAGE.curl.stderr.raw",
    "DOWNLOAD_PAGE.curl.command.json", "DOWNLOAD_PAGE.html.raw", "TOOL_DOWNLOAD.headers.raw",
    "TOOL_DOWNLOAD.curl.stdout.raw", "TOOL_DOWNLOAD.curl.stderr.raw", "TOOL_DOWNLOAD.curl.command.json",
    "RAR_VERSION.stdout.raw", "RAR_VERSION.stderr.raw", "RAR_VERSION.command.json",
    "UNRAR_VERSION.stdout.raw", "UNRAR_VERSION.stderr.raw", "UNRAR_VERSION.command.json",
    "OFFICIAL_LISTING.stdout.raw", "OFFICIAL_LISTING.stderr.raw", "OFFICIAL_LISTING.command.json",
    "DISK_PREFLIGHT.stdout.raw", "DISK_PREFLIGHT.stderr.raw", "DISK_PREFLIGHT.command.json",
)
R1B_LOCAL = ("ARCHIVE_TEST.stdout.raw", "ARCHIVE_TEST.stderr.raw", "ARCHIVE_TEST.command.json")
R1C_LOCAL = ("EXTRACTION.stdout.raw", "EXTRACTION.stderr.raw", "EXTRACTION.command.json")
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


def _no_symlink_components(project: Path, path: Path) -> None:
    try: relative = path.absolute().relative_to(project.absolute())
    except ValueError: _fail(f"path escapes project: {path}")
    current = project
    _dir(current)
    for part in relative.parts:
        current /= part
        if not current.exists() and not current.is_symlink(): break
        if stat.S_ISLNK(current.lstat().st_mode): _fail(f"symlink path component: {current}")


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


def _command_evidence(evidence: Path, prefix: str) -> tuple[dict[str, Any], bytes, bytes]:
    stdout_path = evidence / f"{prefix}.stdout.raw"
    stderr_path = evidence / f"{prefix}.stderr.raw"
    command_path = evidence / f"{prefix}.command.json"
    stdout = stdout_path.read_bytes()
    stderr = stderr_path.read_bytes()
    record = _json(command_path)
    _flags(record, command_path.name)
    expected_fields = {
        "stdout_bytes": len(stdout), "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_bytes": len(stderr), "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }
    if any(record.get(key) != value for key, value in expected_fields.items()):
        _fail(f"command transcript record mismatch: {prefix}")
    fields = {"schema_version", "argv", "return_code", "timed_out", "execution_error",
              "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256",
              "model_or_api_executed", "numeric_target_emitted"}
    if set(record) != fields or record.get("schema_version") != GENERATOR_SCHEMA or type(record.get("return_code")) is not int or not isinstance(record.get("timed_out"), bool) or not isinstance(record.get("execution_error"), bool) or not isinstance(record.get("argv"), list):
        _fail(f"command record schema mismatch: {prefix}")
    return {"stdout": _hash(stdout_path), "stderr": _hash(stderr_path),
            "command": _hash(command_path), **record}, stdout, stderr


def _safe_https(value: str, expected_path: str) -> str:
    parsed = urlsplit(value.strip())
    port = f":{parsed.port}" if parsed.port is not None else ""
    safe = f"{parsed.scheme.lower()}://{(parsed.hostname or '').lower()}{port}{parsed.path}"
    if parsed.scheme.lower() != "https" or parsed.hostname not in {"www.rarlab.com", "rarlab.com"} or parsed.path != expected_path:
        _fail(f"unapproved transport URL: {safe}")
    return safe


def _headers(path: Path, expected_path: str) -> dict[str, Any]:
    statuses: list[str] = []
    locations: list[str] = []
    selected: dict[str, list[str]] = {"content-length": [], "content-type": [], "etag": [], "last-modified": []}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip(); lower = line.lower()
        if line.startswith("HTTP/"): statuses.append(" ".join(line.split()[:3]))
        elif lower.startswith("location:"): locations.append(_safe_https(line.split(":", 1)[1].strip(), expected_path))
        else:
            for key in selected:
                if lower.startswith(key + ":"): selected[key].append(line.split(":", 1)[1].strip())
    if not statuses or not any(re.match(r"HTTP/\S+ 200(?:\s|$)", status) for status in statuses): _fail("transport lacks HTTP 200")
    return {"http_status_lines": statuses, "redirect_scheme_host_paths": locations,
            "selected_headers": selected, "raw": _hash(path),
            "query_fragment_credentials_persisted": False}


def _download_receipt(evidence: Path, prefix: str, payload: Path, url: str) -> dict[str, Any]:
    command, stdout, stderr = _command_evidence(evidence, f"{prefix}.curl")
    if command["argv"] != ["curl", "HTTPS_ONLY_FIXED_URL", prefix]:
        _fail(f"curl command label mismatch: {prefix}")
    try: meta = json.loads(stdout)
    except json.JSONDecodeError as exc: raise VerificationError(f"curl JSON mismatch: {prefix}") from exc
    path = urlsplit(url).path
    effective = _safe_https(str(meta.get("url_effective", "")), path)
    headers = _headers(evidence / f"{prefix}.headers.raw", path)
    curl = Path("/usr/bin/curl")
    if _hash(curl)["sha256"] != CURL_SHA256: _fail("curl identity mismatch")
    if command.get("return_code") != 0 or command.get("timed_out") is not False or command.get("execution_error") is not False or stderr or int(meta.get("http_code", 0)) != 200:
        _fail(f"curl transaction did not pass: {prefix}")
    return {"schema_version": GENERATOR_SCHEMA, "requested_url": url,
            "effective_scheme_host_path": effective, "http_code": meta["http_code"],
            "num_redirects": meta.get("num_redirects"), "size_download": meta.get("size_download"),
            "content_type": meta.get("content_type"), "remote_ip_redacted": True,
            "curl": {"path": str(curl), **_hash(curl)}, "headers": headers,
            "payload": _hash(payload), "raw_command_evidence": command,
            "model_or_api_executed": False, "numeric_target_emitted": False}


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


def _rebuild_r1a(output: Path, local: Path, tool_tar: Path, tool_root: Path,
                 page: Mapping[str, Any], download: Mapping[str, Any],
                 official: Sequence[Mapping[str, Any]], prior: Mapping[str, Mapping[str, Any]],
                 listing_command: Mapping[str, Any], source: Mapping[str, Any]) -> None:
    evidence = local / "evidence"
    tar_rows = []
    with tarfile.open(tool_tar, "r:gz") as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not (member.isdir() or member.isfile()):
                _fail("unsafe tool tar member")
            target = tool_root / name
            _no_symlink_components(local, target)
            kind = "dir" if member.isdir() else "file"
            if kind == "dir":
                _dir(target)
            else:
                stream = archive.extractfile(member)
                if stream is None: _fail("unreadable tool tar member")
                payload = stream.read()
                if _hash(target) != {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}:
                    _fail("unpacked tool member differs from tarball")
            tar_rows.append({"path": member.name, "kind": kind, "bytes": member.size})
    tar_rows.sort(key=lambda row: row["path"])
    identities = [{"item": label, "path_suffix": str(path.relative_to(local)), **_hash(path),
                   "model_or_api_executed": "false", "numeric_target_emitted": "false"}
                  for label, path in (("rar", tool_root / "rar/rar"), ("unrar", tool_root / "rar/unrar"),
                                      ("license", tool_root / "rar/license.txt"))]
    versions = {}
    for prefix, name in (("RAR_VERSION", "rar"), ("UNRAR_VERSION", "unrar")):
        command, stdout, stderr = _command_evidence(evidence, prefix)
        if command["argv"] != [name, "-iver"] or command["return_code"] != 0 or command["timed_out"] or command["execution_error"] or stderr or stdout != b"7.23\n":
            _fail(f"version command reconstruction mismatch: {prefix}")
        versions[name] = {"version": "7.23", "evidence": command}
    rebuilt_identity = {"schema_version": GENERATOR_SCHEMA, "status": "PASS_TOOL_IDENTITY",
                        "download_page": dict(page), "tool_download": dict(download),
                        "tarball": _hash(tool_tar), "tar_members": tar_rows, "package_items": identities,
                        "versions": versions, "license_reviewed_from_package": True,
                        "model_or_api_executed": False, "numeric_target_emitted": False}
    if _json(output / "TOOL_IDENTITY.json") != rebuilt_identity:
        _fail("tool identity field reconstruction mismatch")
    header = ("item", "path_suffix", "bytes", "sha256", "model_or_api_executed", "numeric_target_emitted")
    if _csv(output / "TOOL_HASH_LEDGER.csv", header) != [{key: str(value) for key, value in row.items()} for row in identities]:
        _fail("tool hash ledger reconstruction mismatch")
    files = [row for row in official if row["member_type"] == "regular_file"]
    totals = {"member_count": len(official), "regular_file_count": len(files),
              "directory_count": len(official) - len(files),
              "uncompressed_bytes": sum(int(row["uncompressed_bytes"]) for row in files)}
    # verify() already independently compared every prior/current member field.
    diff = {"schema_version": GENERATOR_SCHEMA, "status": "PASS_EXACT_LISTING_DIFF",
            "prior_ledger_sha256": PRIOR_SHA256, "totals": totals, "frozen_totals_pass": True,
            "missing_from_official": sorted(set(prior) - {row["member_path"] for row in official}),
            "unexpected_in_official": sorted({row["member_path"] for row in official} - set(prior)),
            "changed": [], "model_or_api_executed": False, "numeric_target_emitted": False}
    if _json(output / "ARCHIVE_LISTING_DIFF.json") != diff:
        _fail("listing diff field reconstruction mismatch")
    command, stdout, stderr = _command_evidence(evidence, "DISK_PREFLIGHT")
    if command["argv"] != ["df", "--output=avail", "-B1", "LOCAL_STAGING_PARENT"] or command["return_code"] != 0 or command["timed_out"] or command["execution_error"] or stderr:
        _fail("disk preflight command mismatch")
    lines = stdout.decode("ascii").splitlines()
    if len(lines) != 2 or lines[0].strip() != "Avail" or not lines[1].strip().isdigit():
        _fail("disk preflight output mismatch")
    free = int(lines[1].strip())
    required = FILE_BYTES + max(MIN_DISK_SAFETY_BYTES, FILE_BYTES // 5)
    if free < required: _fail("disk preflight below frozen requirement")
    preflight = {"schema_version": GENERATOR_SCHEMA, "stage": "R1A", "status": "PASS_R1A_PREFLIGHT",
                 "source": dict(source), "plan_sha256": PLAN_SHA256, "packet_sha256": PACKET_SHA256,
                 "approval_sha256": APPROVAL_SHA256, "prior_ledger_sha256": PRIOR_SHA256,
                 "listing": {"tool_banner": "UNRAR 7.23 freeware", "container": "RAR 5", **listing_command},
                 "disk": {"available_bytes": free, "required_bytes": required, "command_evidence": command, "status": "PASS"},
                 "model_or_api_executed": False, "numeric_target_emitted": False, "automatic_next_stage": False}
    if _json(output / "R1A_PREFLIGHT.json") != preflight:
        _fail("R1A preflight field reconstruction mismatch")


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


def _danger(text: str) -> dict[str, int]:
    tokens = ("unsupported", "crc failed", "data error", "checksum error", "wrong password",
              "enter password", "corrupt", "damaged", "warning", "cannot create")
    return {token: len(re.findall(re.escape(token), text, re.I)) for token in tokens}


def _rebuild_test_report(
    command: Mapping[str, Any], stdout: bytes, stderr: bytes, expected: Sequence[str],
    expected_directories: Sequence[str] = (),
) -> dict[str, Any]:
    combined = (stdout + b"\n" + stderr).decode("utf-8", errors="replace").replace("\r", "\n")
    tested = sorted(_ok_paths(stdout, "Testing")); danger = _danger(combined)
    observed = [path for path in tested if path in set(expected)]
    directories = [path for path in tested if path in set(expected_directories)]
    all_expected = sorted([*expected, *expected_directories])
    all_ok = len(re.findall(r"^All OK\s*$", combined, re.M))
    passed = (command["return_code"] == 0 and not stderr and command["timed_out"] is False
              and command["execution_error"] is False and observed == sorted(expected)
              and tested == all_expected and len(observed) == FILE_COUNT and all_ok == 1 and not any(danger.values()))
    return {"schema_version": GENERATOR_SCHEMA, "stage": "R1B",
            "status": "PASS_ARCHIVE_TEST" if passed else "BLOCKED_ARCHIVE_TEST",
            "command_evidence": dict(command), "return_code": command["return_code"],
            "timed_out": command["timed_out"], "execution_error": command["execution_error"],
            "expected_tested_file_count": len(expected), "observed_tested_file_count": len(observed),
            "expected_tested_directory_count": len(expected_directories),
            "observed_tested_directory_count": len(directories),
            "expected_tested_member_count": len(all_expected), "observed_tested_member_count": len(tested),
            "tested_member_path_set_exact": tested == all_expected,
            "tested_path_set_exact": observed == sorted(expected), "all_ok_marker_count": all_ok,
            "danger_marker_counts": danger, "extraction_authorized_by_this_report": passed,
            "extraction_attempted": False, "model_or_api_executed": False,
            "numeric_target_emitted": False, "automatic_next_stage": False}


def _scan_extraction(extraction: Path, listed: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, str]], list[str], list[str], list[str]]:
    rows: list[dict[str, str]] = []; observed: set[str] = set(); unsafe: list[str] = []
    for path in sorted(extraction.rglob("*")):
        rel = path.relative_to(extraction).as_posix(); observed.add(rel); meta = path.lstat()
        kind = "symlink" if stat.S_ISLNK(meta.st_mode) else "regular_file" if stat.S_ISREG(meta.st_mode) else "directory" if stat.S_ISDIR(meta.st_mode) else "special"
        if kind not in {"regular_file", "directory"} or kind == "regular_file" and meta.st_nlink != 1: unsafe.append(f"unsafe_type_or_link:{rel}:{kind}:{meta.st_nlink}")
        expected = listed.get(rel); size = meta.st_size if kind == "regular_file" else 0; crc = _crc(path) if kind == "regular_file" else "00000000"
        type_ok = bool(expected and kind == expected["member_type"]); size_ok = bool(expected and size == int(expected["uncompressed_bytes"])); crc_ok = bool(expected and crc == expected["crc"])
        if not (type_ok and size_ok and crc_ok): unsafe.append(f"member_mismatch:{rel}")
        rows.append({"member_path": rel, "observed_type": kind, "hardlink_count": str(meta.st_nlink) if kind == "regular_file" else "NA",
                     "observed_bytes": str(size), "expected_bytes": str(expected["uncompressed_bytes"]) if expected else "NA",
                     "observed_crc32": crc, "expected_crc32": str(expected["crc"]) if expected else "NA",
                     "type_match": str(type_ok).lower(), "size_match": str(size_ok).lower(), "crc_match": str(crc_ok).lower(),
                     "status": "PASS" if type_ok and size_ok and crc_ok else "FAIL",
                     "model_or_api_executed": "false", "numeric_target_emitted": "false"})
    return rows, sorted(listed.keys() - observed), sorted(observed - listed.keys()), unsafe


def _rebuild_extraction_manifest(command: Mapping[str, Any], stdout: bytes, stderr: bytes,
                                 rows: Sequence[Mapping[str, str]], missing: Sequence[str],
                                 unexpected: Sequence[str], unsafe: Sequence[str], destination: str,
                                 destination_path: Path | None = None) -> dict[str, Any]:
    text = (stdout + b"\n" + stderr).decode("utf-8", errors="replace").replace("\r", "\n")
    extracted = sorted(_ok_paths(stdout, "Extracting")); danger = _danger(text)
    expected_paths = sorted(row["member_path"] for row in rows if row["observed_type"] == "regular_file")
    if destination_path is not None:
        expected_paths = sorted(str(destination_path / member) for member in expected_paths)
    all_ok = len(re.findall(r"^All OK\s*$", text, re.M))
    passed = (command["return_code"] == 0 and not stderr and command["timed_out"] is False
              and command["execution_error"] is False and not missing and not unexpected and not unsafe
              and len(rows) == MEMBER_COUNT and len(extracted) == FILE_COUNT and extracted == expected_paths and all_ok == 1
              and not any(danger.values()))
    return {"schema_version": GENERATOR_SCHEMA, "stage": "R1C",
            "status": "PASS_EXTRACTION_BYTE_IDENTITY" if passed else "QUARANTINED_EXTRACTION_MISMATCH",
            "quarantine_state": "RELEASED_FOR_READ_ONLY_ROW_AUDIT" if passed else "QUARANTINED_BLOCKED",
            "destination_name": destination, "command_evidence": dict(command),
            "return_code": command["return_code"], "timed_out": command["timed_out"],
            "execution_error": command["execution_error"], "all_ok_marker_count": all_ok,
            "danger_marker_counts": danger, "extract_ok_file_count": len(extracted),
            "extracted_path_set_exact": extracted == expected_paths,
            "observed_member_count": len(rows),
            "observed_regular_file_count": sum(row["observed_type"] == "regular_file" for row in rows),
            "observed_directory_count": sum(row["observed_type"] == "directory" for row in rows),
            "observed_regular_file_bytes": sum(int(row["observed_bytes"]) for row in rows if row["observed_type"] == "regular_file"),
            "missing_members": list(missing), "unexpected_members": list(unexpected),
            "unsafe_or_mismatched": list(unsafe), "workbook_opened_or_parsed": False,
            "model_or_api_executed": False, "numeric_target_emitted": False,
            "automatic_next_stage": False}


def verify(project: Path, run_id: str) -> dict[str, Any]:
    if RUN_RE.fullmatch(run_id) is None:
        _fail("invalid run id")
    project = project.resolve(strict=True)
    output = project / "data/audit/ren_scs" / run_id
    local = project / "data/raw/ren_scs" / run_id
    evidence = local / "evidence"
    extraction = local / "quarantine_extracted"
    archive = project / "data/raw/ren_scs/raw.rar"
    prior = project / "data/audit/ren_scs/p1_20260828_180210/ARCHIVE_MEMBER_LEDGER.csv"
    plan = project / "refine-logs/REN_P1R1_ARCHIVE_RECOVERY_PLAN_20260904_145423.md"
    packet = project / "refine-logs/REN_P1R1_APPROVAL_PACKET_20260904_145423.json"
    approval = project / "refine-logs/REN_P1R1_APPROVAL_RECORD_20260904_213130.json"
    release = project / "refine-logs/REN_P1R1_R4_RELEASE.json"
    tool_tar, tool_root = local / "tool/rarlinux-x64-723.tar.gz", local / "tool/unpacked"
    for path in (output, local, evidence, extraction, archive, prior, plan, packet, approval, release):
        _no_symlink_components(project, path)
    _dir(output); _dir(local); _dir(evidence); _dir(extraction)
    ignored = _run(["/usr/bin/git", "-C", str(project), "check-ignore", "-q", "--", str(local.relative_to(project))])
    tracked = _run(["/usr/bin/git", "-C", str(project), "check-ignore", "-q", "--", str(output.relative_to(project))])
    if ignored.returncode != 0 or tracked.returncode == 0:
        _fail("ignored/tracked containment differs")
    observed_names = {path.name for path in output.iterdir()}
    if observed_names - {VERIFICATION_REPORT} != EXACT_ARTIFACTS:
        _fail(f"exact artifact set mismatch: missing={sorted(EXACT_ARTIFACTS-observed_names)}, unexpected={sorted(observed_names-EXACT_ARTIFACTS)}")
    for path in output.iterdir():
        _file(path)
        if path.suffix == ".json":
            _flags(_json(path), path.name)
    if {path.name for path in evidence.iterdir()} != set((*R1A_LOCAL, *R1B_LOCAL, *R1C_LOCAL)):
        _fail("local transcript set mismatch")
    for path in evidence.iterdir():
        _file(path)
    frozen = ((plan, PLAN_SHA256), (packet, PACKET_SHA256), (approval, APPROVAL_SHA256),
              (prior, PRIOR_SHA256), (tool_tar, TOOL_TAR_SHA256),
              (tool_root / "rar/rar", RAR_SHA256), (tool_root / "rar/unrar", UNRAR_SHA256),
              (tool_root / "rar/license.txt", LICENSE_SHA256))
    for path, digest in frozen:
        _no_symlink_components(project, path)
        if _hash(path)["sha256"] != digest:
            _fail(f"frozen hash mismatch: {path.name}")
    if _hash(archive, True) != {"bytes": ARCHIVE_BYTES, "sha256": ARCHIVE_SHA256, "md5": ARCHIVE_MD5}:
        _fail("archive identity mismatch")
    approved = _json(approval)
    if approved.get("approval_token") != f"APPROVE_REN_P1R1:{PLAN_SHA256}" or approved.get("automatic_next_stage") is not False:
        _fail("approval boundary mismatch")

    policy = {
        "policy:generator": project / "experiments/audit_cap/ren_p1r1_recovery.py",
        "policy:verifier": project / "experiments/audit_cap/verify_ren_p1r1_recovery.py",
        "policy:generator_tests": project / "tests/test_ren_p1r1_recovery.py",
        "policy:verifier_tests": project / "tests/test_verify_ren_p1r1_recovery.py",
        "policy:gitignore": project / ".gitignore",
    }
    release_payload = _json(release)
    for path in policy.values():
        _no_symlink_components(project, path)
    if (release_payload.get("schema_version") != "RenP1R1R4Release.v1"
            or release_payload.get("status") != "PASS_TO_RUN_R1ABC"
            or release_payload.get("approval_record_sha256") != APPROVAL_SHA256
            or release_payload.get("reviewed_policy_sha256") != {name: _hash(path)["sha256"] for name, path in sorted(policy.items())}
            or release_payload.get("automatic_next_stage") is not False
            or release_payload.get("model_or_api_executed") is not False):
        _fail("fresh release record mismatch")
    authority = {"source_archive": archive, "frozen_plan": plan, "approval_packet": packet,
                 "approval_record": approval, "pre_run_release": release,
                 "prior_listing_ledger": prior, **policy}
    r1a_files = dict(authority)
    r1a_files.update({f"artifact:{name}": output / name for name in R1A})
    r1a_files.update({f"local_evidence:{name}": evidence / name for name in R1A_LOCAL})
    r1a_files.update({"tool_tarball": tool_tar, "rar_binary": tool_root / "rar/rar",
                      "unrar_binary": tool_root / "rar/unrar", "tool_license": tool_root / "rar/license.txt"})
    _verify_seal(output / "R1A_SEAL.json", "R1A", _bound(r1a_files))
    r1b_files = dict(r1a_files); r1b_files["seal:R1A"] = output / "R1A_SEAL.json"
    r1b_files.update({f"artifact:{name}": output / name for name in R1B})
    r1b_files.update({f"local_evidence:{name}": evidence / name for name in R1B_LOCAL})
    _verify_seal(output / "R1B_SEAL.json", "R1B", _bound(r1b_files))
    r1c_files = dict(r1b_files); r1c_files["seal:R1B"] = output / "R1B_SEAL.json"
    r1c_files.update({f"artifact:{name}": output / name for name in R1C})
    r1c_files.update({f"local_evidence:{name}": evidence / name for name in R1C_LOCAL})
    _verify_seal(output / "R1C_SEAL.json", "R1C", _bound(r1c_files))

    page_expected = _download_receipt(evidence, "DOWNLOAD_PAGE", evidence / "DOWNLOAD_PAGE.html.raw", "https://www.rarlab.com/download.htm")
    tool_expected = _download_receipt(evidence, "TOOL_DOWNLOAD", tool_tar, "https://www.rarlab.com/rar/rarlinux-x64-723.tar.gz")
    if _json(output / "DOWNLOAD_PAGE_RECEIPT.json") != page_expected:
        _fail("download-page receipt field reconstruction mismatch")
    if _json(output / "TOOL_DOWNLOAD_RECEIPT.json") != tool_expected:
        _fail("tool receipt field reconstruction mismatch")
    page_bytes = (evidence / "DOWNLOAD_PAGE.html.raw").read_bytes()
    if b'href="/rar/rarlinux-x64-723.tar.gz"' not in page_bytes or b"RAR for Linux x64 7.23" not in page_bytes:
        _fail("download-page href/version evidence mismatch")
    for prefix, tool_name in (("RAR_VERSION", "rar"), ("UNRAR_VERSION", "unrar")):
        command, stdout, stderr = _command_evidence(evidence, prefix)
        if command["argv"] != [tool_name, "-iver"] or command["return_code"] != 0 or command["timed_out"] or command["execution_error"] or stderr or stdout != b"7.23\n":
            _fail(f"version command reconstruction mismatch: {prefix}")

    listing_command, listing_stdout, listing_stderr = _command_evidence(evidence, "OFFICIAL_LISTING")
    if listing_command["argv"] != ["unrar", "lt", "-v", "-p-", "FROZEN_RAW_RAR"] or listing_command["return_code"] != 0 or listing_command["timed_out"] or listing_command["execution_error"] or listing_stderr:
        _fail("stored listing command evidence mismatch")
    independent = _run([str(tool_root / "rar/unrar"), "lt", "-v", "-p-", str(archive)])
    if independent.returncode != 0 or independent.stderr or independent.stdout != listing_stdout:
        _fail("stored listing is not independently reproducible")
    official = _parse_listing(independent.stdout)
    stored = _csv(output / "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv", OFFICIAL_HEADER)
    if [{key: str(value) for key, value in row.items()} for row in official] != stored:
        _fail("stored member ledger differs from independent parse")
    prior_rows = _prior(prior)
    compare_keys = ("member_type", "uncompressed_bytes", "packed_bytes", "crc", "compression_method",
                    "encrypted", "link_or_redirection", "extension", "safety_status")
    for row in official:
        old = prior_rows.get(row["member_path"])
        if old is None or any(str(row[key]) != str(old[key]) for key in compare_keys):
            _fail(f"independent prior diff: {row['member_path']}")
    files = [row for row in official if row["member_type"] == "regular_file"]
    if len(files) != FILE_COUNT or len(official) - len(files) != DIRECTORY_COUNT or sum(int(row["uncompressed_bytes"]) for row in files) != FILE_BYTES:
        _fail("independent listing aggregate mismatch")
    _rebuild_r1a(output, local, tool_tar, tool_root, page_expected, tool_expected,
                 official, prior_rows, listing_command,
                 {"bytes": ARCHIVE_BYTES, "sha256": ARCHIVE_SHA256, "md5": ARCHIVE_MD5})

    test_command, test_stdout, test_stderr = _command_evidence(evidence, "ARCHIVE_TEST")
    if test_command["argv"] != ["unrar", "t", "-idp", "-p-", "FROZEN_RAW_RAR"]:
        _fail("archive-test command label mismatch")
    expected_paths = sorted(row["member_path"] for row in files)
    expected_directories = sorted(row["member_path"] for row in official if row["member_type"] == "directory")
    rebuilt_test = _rebuild_test_report(test_command, test_stdout, test_stderr, expected_paths, expected_directories)
    if _json(output / "ARCHIVE_TEST_REPORT.json") != rebuilt_test or rebuilt_test["status"] != "PASS_ARCHIVE_TEST":
        _fail("archive test report field reconstruction mismatch")

    listed = {row["member_path"]: row for row in official}
    rebuilt_rows, missing, unexpected, unsafe = _scan_extraction(extraction, listed)
    ledger = _csv(output / "EXTRACTION_MEMBER_LEDGER.csv", EXTRACTION_HEADER)
    if ledger != rebuilt_rows:
        _fail("extraction ledger independent row reconstruction mismatch")
    extraction_command, extraction_stdout, extraction_stderr = _command_evidence(evidence, "EXTRACTION")
    if extraction_command["argv"] != ["unrar", "x", "-idp", "-p-", "-o-", "FROZEN_RAW_RAR", "QUARANTINE_DESTINATION"]:
        _fail("extraction command label mismatch")
    rebuilt_manifest = _rebuild_extraction_manifest(extraction_command, extraction_stdout, extraction_stderr,
                                                    rebuilt_rows, missing, unexpected, unsafe, extraction.name, extraction)
    if _json(output / "EXTRACTION_MANIFEST.json") != rebuilt_manifest or rebuilt_manifest["status"] != "PASS_EXTRACTION_BYTE_IDENTITY":
        _fail("extraction manifest field reconstruction mismatch")
    result = {"schema_version": SCHEMA_VERSION, "status": "PASS_R1ABC_INDEPENDENT_VERIFICATION",
            "verified_member_count": MEMBER_COUNT, "verified_regular_file_count": FILE_COUNT,
            "verified_directory_count": DIRECTORY_COUNT, "verified_regular_file_bytes": FILE_BYTES,
            "archive_sha256": ARCHIVE_SHA256, "workbook_opened_or_parsed": False,
            "model_or_api_executed": False, "numeric_target_emitted": False, "automatic_next_stage": False}
    if (output / VERIFICATION_REPORT).exists() and _json(output / VERIFICATION_REPORT) != result:
        _fail("stored verification report differs from independently rebuilt result")
    return result


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
