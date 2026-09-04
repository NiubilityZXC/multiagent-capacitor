#!/usr/bin/env python3
"""Fail-closed Ren P1-R1 archive recovery (R1A--R1C only).

All mutable/raw paths are derived from a validated run id beneath the ignored
``data/raw/ren_scs`` tree. Each phase re-hashes fixed inputs and verifies the
preceding non-circular seal before invoking RARLAB UnRAR. No workbook is opened
and no model, API, target, SOH, or RUL computation is present.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
from typing import Any, Mapping, NoReturn, Sequence
from urllib.parse import urlsplit, urlunsplit
import zlib


SCHEMA_VERSION = "audit-cap.ren-p1r1-recovery.v2"
ARCHIVE_BYTES = 2_114_703_017
ARCHIVE_MD5 = "26a7a663217c59377c83fb2a8274466b"
ARCHIVE_SHA256 = "a8f1083b887f95483561a94b624b323ff42814654ee7f23e7f95bc042fa258d8"
PLAN_SHA256 = "a7a8f5521b6b249af59a9ded0971cb02f912d9f46e8babfe3d60777cbfcc3c6d"
PACKET_SHA256 = "8ea05474bf90609a89e2c6e1725777e6c9030c2dae5067d94c3ad6b54511c365"
APPROVAL_SHA256 = "314dc2e62acf35eccf0053a8fd77591a1bc90d82fae9e70e1dbc4820f882f2d8"
PRIOR_LEDGER_SHA256 = "66353535e49f815bd32ed79615c13e78458bec5727acc90ab85fc3763acace4b"
TOOL_URL = "https://www.rarlab.com/rar/rarlinux-x64-723.tar.gz"
DOWNLOAD_PAGE_URL = "https://www.rarlab.com/download.htm"
TOOL_TARBALL_BYTES = 746_868
TOOL_TARBALL_SHA256 = "759b4b6aa0d9f77131882162951193f3a0e54bf60e1d8dc4255aa308accab588"
RAR_SHA256 = "56c3c4fd46faa7a9f52264d30cb96813e19ec7c4587d9f18424d7e909cf78555"
UNRAR_SHA256 = "926d3a00775ed96afccfdef69c3781334b71ccdb733931edf30f4866e4f08410"
LICENSE_SHA256 = "0420a0c2cd464466c13ddac80c2efd083163ca82c193fa59df068d8386c3f141"
CURL_SHA256 = "74b4ce8f74b377f18ef1b3df7279c26cb3cd14c49e39ab1498575b209dc3f70f"
EXPECTED_FILE_COUNT = 233
EXPECTED_DIRECTORY_COUNT = 4
EXPECTED_MEMBER_COUNT = 237
EXPECTED_UNCOMPRESSED_BYTES = 15_223_551_488
MIN_DISK_SAFETY_BYTES = 10 * 1024**3
RUN_RE = re.compile(r"p1r1_[0-9]{8}_[0-9]{6}")

EXPECTED_TAR_MEMBERS = {
    "rar": ("dir", 0), "rar/unrar": ("file", 441_632),
    "rar/acknow.txt": ("file", 2_721), "rar/whatsnew.txt": ("file", 43_348),
    "rar/order.htm": ("file", 3_471), "rar/readme.txt": ("file", 692),
    "rar/rar.txt": ("file", 109_989), "rar/makefile": ("file", 428),
    "rar/default.sfx": ("file", 248_960), "rar/rar": ("file", 798_760),
    "rar/rarfiles.lst": ("file", 1_223), "rar/license.txt": ("file", 6_753),
}
R1A_ARTIFACTS = (
    "DOWNLOAD_PAGE.curl.json", "DOWNLOAD_PAGE.headers.txt", "DOWNLOAD_PAGE.html",
    "TOOL_DOWNLOAD.curl.json", "TOOL_DOWNLOAD.headers.txt", "TOOL_IDENTITY.json",
    "TOOL_HASH_LEDGER.csv", "RAR_VERSION.stdout.txt", "RAR_VERSION.stderr.txt",
    "UNRAR_VERSION.stdout.txt", "UNRAR_VERSION.stderr.txt",
    "OFFICIAL_LISTING.stdout.txt", "OFFICIAL_LISTING.stderr.txt",
    "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv", "ARCHIVE_LISTING_DIFF.json", "R1A_PREFLIGHT.json",
)
R1B_ARTIFACTS = ("ARCHIVE_TEST.stdout.txt", "ARCHIVE_TEST.stderr.txt", "ARCHIVE_TEST_REPORT.json")
R1C_ARTIFACTS = ("EXTRACTION.stdout.txt", "EXTRACTION.stderr.txt", "EXTRACTION_MEMBER_LEDGER.csv", "EXTRACTION_MANIFEST.json")
PRIOR_HEADER = (
    "member_path", "member_type", "batch_path_component", "provisional_filename_stem",
    "segment_suffix", "uncompressed_bytes", "packed_bytes", "crc", "compression_method",
    "encrypted", "link_fields_empty", "extension", "listing_safety_status", "row_content_status",
)


class RecoveryError(RuntimeError):
    """A frozen recovery contract failed closed."""


def _fail(message: str) -> NoReturn:
    raise RecoveryError(message)


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _require_file(path: Path, label: str) -> os.stat_result:
    try:
        meta = path.lstat()
    except FileNotFoundError as exc:
        raise RecoveryError(f"missing {label}: {path}") from exc
    if stat.S_ISLNK(meta.st_mode) or not stat.S_ISREG(meta.st_mode):
        _fail(f"{label} must be a regular non-symlink file: {path}")
    return meta


def _require_dir(path: Path, label: str) -> os.stat_result:
    try:
        meta = path.lstat()
    except FileNotFoundError as exc:
        raise RecoveryError(f"missing {label}: {path}") from exc
    if stat.S_ISLNK(meta.st_mode) or not stat.S_ISDIR(meta.st_mode):
        _fail(f"{label} must be a real non-symlink directory: {path}")
    return meta


def _no_symlink_components(project: Path, path: Path) -> None:
    try:
        relative = path.absolute().relative_to(project.absolute())
    except ValueError:
        _fail(f"path escapes project root: {path}")
    current = project
    _require_dir(current, "project root")
    for part in relative.parts:
        current /= part
        if not current.exists() and not current.is_symlink():
            break
        if stat.S_ISLNK(current.lstat().st_mode):
            _fail(f"symlink path component is forbidden: {current}")


def _digests(path: Path, *, md5: bool = False) -> dict[str, Any]:
    meta = _require_file(path, "digest input")
    sha = hashlib.sha256()
    old = hashlib.md5(usedforsecurity=False) if md5 else None
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha.update(block)
            if old is not None:
                old.update(block)
    result: dict[str, Any] = {"bytes": meta.st_size, "sha256": sha.hexdigest()}
    if old is not None:
        result["md5"] = old.hexdigest()
    return result


def _write_bytes(path: Path, payload: bytes) -> None:
    if path.exists() or path.is_symlink():
        _fail(f"append-only artifact already exists: {path}")
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _write_json(path: Path, value: Any) -> None:
    _write_bytes(path, _canonical_json(value))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    if path.exists() or path.is_symlink():
        _fail(f"append-only artifact already exists: {path}")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "NA") for key in fields} for row in rows)
        stream.flush()
        os.fsync(stream.fileno())


def _strict_json(path: Path) -> dict[str, Any]:
    def reject(value: str) -> NoReturn:
        _fail(f"non-finite JSON token in {path}: {value}")
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)
    if not isinstance(value, dict):
        _fail(f"JSON artifact must be an object: {path}")
    return value


def _run(argv: Sequence[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(list(argv), check=False, capture_output=True, timeout=timeout,
                              env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
    except subprocess.TimeoutExpired as exc:
        raise RecoveryError(f"command timeout after {timeout}s: {Path(argv[0]).name}") from exc
    except OSError as exc:
        raise RecoveryError(f"command execution failed: {Path(argv[0]).name}") from exc


@dataclass(frozen=True)
class Paths:
    project: Path
    run_id: str
    output: Path
    local: Path
    archive: Path
    prior: Path
    plan: Path
    packet: Path
    approval: Path
    tool_tar: Path
    tool_root: Path
    extraction: Path

    @classmethod
    def build(cls, project_arg: str, run_id: str, *, new: bool) -> "Paths":
        if RUN_RE.fullmatch(run_id) is None:
            _fail("run id must match p1r1_YYYYMMDD_HHMMSS")
        project = Path(project_arg).resolve(strict=True)
        values = cls(
            project, run_id, project / "data/audit/ren_scs" / run_id,
            project / "data/raw/ren_scs" / run_id, project / "data/raw/ren_scs/raw.rar",
            project / "data/audit/ren_scs/p1_20260828_180210/ARCHIVE_MEMBER_LEDGER.csv",
            project / "refine-logs/REN_P1R1_ARCHIVE_RECOVERY_PLAN_20260904_145423.md",
            project / "refine-logs/REN_P1R1_APPROVAL_PACKET_20260904_145423.json",
            project / "refine-logs/REN_P1R1_APPROVAL_RECORD_20260904_213130.json",
            project / "data/raw/ren_scs" / run_id / "tool/rarlinux-x64-723.tar.gz",
            project / "data/raw/ren_scs" / run_id / "tool/unpacked",
            project / "data/raw/ren_scs" / run_id / "quarantine_extracted",
        )
        for path in (values.output, values.local, values.archive, values.prior, values.plan, values.packet, values.approval):
            _no_symlink_components(project, path)
        ignored = _run(["/usr/bin/git", "-C", str(project), "check-ignore", "-q", "--", str(values.local.relative_to(project))], 30)
        if ignored.returncode != 0:
            _fail("local staging is not protected by repository ignore rules")
        tracked = _run(["/usr/bin/git", "-C", str(project), "check-ignore", "-q", "--", str(values.output.relative_to(project))], 30)
        if tracked.returncode == 0:
            _fail("audit evidence output is unexpectedly ignored")
        if new:
            if values.output.exists() or values.output.is_symlink() or values.local.exists() or values.local.is_symlink():
                _fail("new run output or local staging already exists")
        else:
            _require_dir(values.output, "run evidence directory")
            _require_dir(values.local, "local run staging")
        return values


def _bound(logical: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    return {name: _digests(path) for name, path in sorted(logical.items())}


def _authority(paths: Paths) -> dict[str, Path]:
    return {"source_archive": paths.archive, "frozen_plan": paths.plan, "approval_packet": paths.packet,
            "approval_record": paths.approval, "prior_listing_ledger": paths.prior}


def _r1a_files(paths: Paths) -> dict[str, Path]:
    result = _authority(paths)
    result.update({f"artifact:{name}": paths.output / name for name in R1A_ARTIFACTS})
    result.update({"tool_tarball": paths.tool_tar, "rar_binary": paths.tool_root / "rar/rar",
                   "unrar_binary": paths.tool_root / "rar/unrar", "tool_license": paths.tool_root / "rar/license.txt"})
    return result


def _r1b_files(paths: Paths) -> dict[str, Path]:
    result = _r1a_files(paths)
    result["seal:R1A"] = paths.output / "R1A_SEAL.json"
    result.update({f"artifact:{name}": paths.output / name for name in R1B_ARTIFACTS})
    return result


def _seal(path: Path, stage: str, status_value: str, bound: Mapping[str, Mapping[str, Any]]) -> None:
    _write_json(path, {"schema_version": SCHEMA_VERSION, "stage": stage, "status": status_value,
                       "bound_files": bound, "model_or_api_executed": False,
                       "numeric_target_emitted": False, "automatic_next_stage": False})


def _verify_seal(path: Path, stage: str, status_value: str, current: Mapping[str, Mapping[str, Any]]) -> None:
    payload = _strict_json(path)
    if payload.get("stage") != stage or payload.get("status") != status_value or payload.get("bound_files") != current:
        _fail(f"{stage} seal or a bound byte changed")
    if payload.get("model_or_api_executed") is not False or payload.get("numeric_target_emitted") is not False or payload.get("automatic_next_stage") is not False:
        _fail(f"{stage} seal permission boundary differs")


def _safe_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower()
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme.lower(), host, parsed.path, "", ""))


def _validate_https_url(value: str, expected_path: str) -> str:
    safe = _safe_url(value)
    parsed = urlsplit(safe)
    if parsed.scheme != "https" or parsed.hostname not in {"www.rarlab.com", "rarlab.com"} or parsed.path != expected_path:
        _fail(f"unapproved tool transport URL: {safe}")
    return safe


def _curl_download(url: str, payload: Path, headers: Path, receipt_path: Path) -> dict[str, Any]:
    curl = Path("/usr/bin/curl")
    if _digests(curl)["sha256"] != CURL_SHA256:
        _fail("curl binary identity differs")
    partial = payload.with_name(payload.name + ".partial")
    for path in (payload, partial, headers, receipt_path):
        if path.exists() or path.is_symlink():
            _fail(f"download target already exists: {path}")
    completed = _run([str(curl), "--proto", "=https", "--tlsv1.2", "--location", "--max-redirs", "3",
                      "--fail-with-body", "--show-error", "--silent", "--dump-header", str(headers),
                      "--output", str(partial), "--write-out", "%{json}", url], 300)
    if completed.returncode != 0 or completed.stderr:
        _fail("curl download failed or emitted stderr")
    try:
        meta = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RecoveryError("curl write-out is not valid JSON") from exc
    expected_path = urlsplit(url).path
    effective = _validate_https_url(str(meta.get("url_effective", "")), expected_path)
    if int(meta.get("http_code", 0)) != 200:
        _fail("tool transport did not end in HTTP 200")
    header_text = headers.read_text(encoding="utf-8", errors="replace")
    for location in re.findall(r"(?im)^location:\s*(\S+)\s*$", header_text):
        _validate_https_url(location, expected_path)
    os.replace(partial, payload)
    receipt = {"schema_version": SCHEMA_VERSION, "requested_url": url, "effective_scheme_host_path": effective,
               "http_code": meta["http_code"], "num_redirects": meta.get("num_redirects"),
               "size_download": meta.get("size_download"), "content_type": meta.get("content_type"),
               "remote_ip_redacted": True, "curl": {"path": str(curl), **_digests(curl)},
               "headers": _digests(headers), "payload": _digests(payload),
               "stderr_bytes": 0, "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
               "model_or_api_executed": False, "numeric_target_emitted": False}
    _write_json(receipt_path, receipt)
    return receipt


def _extract_tool(tarball: Path, root: Path) -> list[dict[str, Any]]:
    root.mkdir(mode=0o700)
    rows: dict[str, tuple[str, int]] = {}
    with tarfile.open(tarball, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            pure = PurePosixPath(member.name)
            if not member.name or pure.is_absolute() or ".." in pure.parts or "." in pure.parts or member.issym() or member.islnk():
                _fail(f"unsafe RARLAB tar member: {member.name}")
            kind = "dir" if member.isdir() else "file" if member.isfile() else "special"
            if member.name in rows:
                _fail(f"duplicate RARLAB tar member: {member.name}")
            rows[member.name] = (kind, member.size)
        if rows != EXPECTED_TAR_MEMBERS:
            _fail("RARLAB tar member structure differs")
        for member in members:
            target = root.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(mode=0o700, parents=True)
            else:
                target.parent.mkdir(mode=0o700, parents=True)
                source = archive.extractfile(member)
                if source is None:
                    _fail(f"cannot read tool member: {member.name}")
                _write_bytes(target, source.read())
                target.chmod(0o755 if member.name in {"rar/rar", "rar/unrar", "rar/default.sfx"} else 0o600)
    return [{"path": name, "kind": kind, "bytes": size} for name, (kind, size) in sorted(rows.items())]


def _version(tool: Path, output: Path, error: Path) -> str:
    completed = _run([str(tool), "-iver"], 30)
    _write_bytes(output, completed.stdout)
    _write_bytes(error, completed.stderr)
    value = completed.stdout.decode("ascii", errors="replace").strip()
    if completed.returncode != 0 or completed.stderr or value != "7.23":
        _fail(f"tool version mismatch: {tool.name}")
    return value


def _parse_unrar_listing(raw: bytes, *, expected_member_count: int = EXPECTED_MEMBER_COUNT) -> tuple[dict[str, str], list[dict[str, Any]]]:
    text = raw.decode("utf-8", errors="strict")
    if "UNRAR 7.23 freeware" not in text or "Details: RAR 5" not in text:
        _fail("listing lacks frozen banners")
    records: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text):
        fields = {match.group(1).strip(): match.group(2).strip() for line in block.splitlines()
                  if (match := re.match(r"^\s*([^:]+):\s*(.*)$", line))}
        if "Name" not in fields or "Type" not in fields:
            continue
        path = fields["Name"]
        pure = PurePosixPath(path)
        if not path or pure.is_absolute() or ".." in pure.parts or "." in pure.parts or "\\" in path or str(pure) != path or re.match(r"^[A-Za-z]:", path):
            _fail(f"unsafe member path: {path}")
        kind = fields["Type"]
        if kind not in {"File", "Directory"}:
            _fail(f"special archive member: {path}:{kind}")
        danger_fields = {key: value for key, value in fields.items() if value and any(token in key.casefold() for token in ("redir", "link", "target", "encrypt", "password"))}
        danger_text = re.findall(r"(?i)\b(encrypted|password protected|symbolic link|hard link|redirection)\b", block)
        if danger_fields or danger_text:
            _fail(f"link/encryption/redirection marker for {path}")
        if kind == "File":
            if pure.suffix.lower() != ".xls":
                _fail(f"unexpected extension: {path}")
            try:
                size, packed = int(fields["Size"]), int(fields["Packed size"])
            except (KeyError, ValueError) as exc:
                raise RecoveryError(f"invalid member size: {path}") from exc
            crc = fields.get("CRC32", "")
            if re.fullmatch(r"[0-9A-F]{8}", crc) is None:
                _fail(f"invalid CRC: {path}")
            match = re.search(r"-m([0-5])\s+-md=(\d+)([kmg])", fields.get("Compression", ""), re.I)
            if match is None:
                _fail(f"unrecognized compression: {path}")
            dictionary = int(match.group(2))
            base = {"k": 10, "m": 20, "g": 30}[match.group(3).lower()]
            if dictionary <= 0 or dictionary & (dictionary - 1):
                _fail(f"invalid dictionary: {path}")
            method = f"m{match.group(1)}:{base + dictionary.bit_length() - 1}"
        else:
            size, packed, crc, method = 0, 0, "00000000", "m0"
        records.append({"member_path": path, "member_type": "regular_file" if kind == "File" else "directory",
                        "uncompressed_bytes": size, "packed_bytes": packed, "crc": crc,
                        "compression_method": method, "encrypted": "false", "link_or_redirection": "false",
                        "extension": pure.suffix.lower() if kind == "File" else "NA", "safety_status": "PASS",
                        "mtime": fields.get("mtime", "NA"), "attributes": fields.get("Attributes", "NA"),
                        "host_os": fields.get("Host OS", "NA"), "model_or_api_executed": "false",
                        "numeric_target_emitted": "false"})
    if len(records) != expected_member_count:
        _fail(f"official listing member count differs: {len(records)}")
    return {"tool_banner": "UNRAR 7.23 freeware", "container": "RAR 5"}, records


def _prior_rows(path: Path) -> list[dict[str, Any]]:
    if _digests(path)["sha256"] != PRIOR_LEDGER_SHA256:
        _fail("prior listing ledger hash differs")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != PRIOR_HEADER:
            _fail("prior listing ledger header differs")
        raw = list(reader)
    result = []
    for row in raw:
        is_dir = row["member_type"] == "directory"
        if row["encrypted"] != "-" or row["link_fields_empty"] != "True" or row["listing_safety_status"] != "PASS_LISTING_METADATA" or row["row_content_status"] != "NOT_EXTRACTED_NOT_PARSED":
            _fail("prior safety flags differ")
        if not is_dir and row["extension"] != ".xls":
            _fail("prior extension allowlist differs")
        result.append({"member_path": row["member_path"], "member_type": "directory" if is_dir else "regular_file",
                       "uncompressed_bytes": 0 if is_dir else int(row["uncompressed_bytes"]),
                       "packed_bytes": 0 if is_dir else int(row["packed_bytes"]),
                       "crc": "00000000" if is_dir else row["crc"],
                       "compression_method": "m0" if is_dir else row["compression_method"],
                       "encrypted": "false", "link_or_redirection": "false",
                       "extension": "NA" if is_dir else row["extension"], "safety_status": "PASS"})
    return result


def _listing_diff(official: Sequence[Mapping[str, Any]], prior: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    keys = ("member_type", "uncompressed_bytes", "packed_bytes", "crc", "compression_method", "encrypted", "link_or_redirection", "extension", "safety_status")
    left = {row["member_path"]: row for row in official}
    right = {row["member_path"]: row for row in prior}
    if len(left) != len(official) or len(right) != len(prior):
        _fail("duplicate listing path")
    changed = [{"member_path": path, "fields": {key: {"prior": right[path][key], "official": left[path][key]} for key in keys if right[path][key] != left[path][key]}}
               for path in sorted(left.keys() & right.keys()) if any(right[path][key] != left[path][key] for key in keys)]
    files = [row for row in official if row["member_type"] == "regular_file"]
    totals = {"member_count": len(official), "regular_file_count": len(files),
              "directory_count": len(official) - len(files),
              "uncompressed_bytes": sum(int(row["uncompressed_bytes"]) for row in files)}
    frozen = totals == {"member_count": EXPECTED_MEMBER_COUNT, "regular_file_count": EXPECTED_FILE_COUNT,
                        "directory_count": EXPECTED_DIRECTORY_COUNT, "uncompressed_bytes": EXPECTED_UNCOMPRESSED_BYTES}
    missing, unexpected = sorted(right.keys() - left.keys()), sorted(left.keys() - right.keys())
    passed = frozen and not missing and not unexpected and not changed
    return {"schema_version": SCHEMA_VERSION, "status": "PASS_EXACT_LISTING_DIFF" if passed else "BLOCKED_LISTING_DIFF",
            "prior_ledger_sha256": PRIOR_LEDGER_SHA256, "totals": totals, "frozen_totals_pass": frozen,
            "missing_from_official": missing, "unexpected_in_official": unexpected, "changed": changed,
            "model_or_api_executed": False, "numeric_target_emitted": False}


def r1a(paths: Paths) -> int:
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    paths.local.parent.mkdir(parents=True, exist_ok=True)
    paths.output.mkdir(mode=0o755)
    paths.local.mkdir(mode=0o700)
    paths.tool_tar.parent.mkdir(mode=0o700)
    for path, digest in ((paths.plan, PLAN_SHA256), (paths.packet, PACKET_SHA256),
                         (paths.approval, APPROVAL_SHA256), (paths.prior, PRIOR_LEDGER_SHA256)):
        if _digests(path)["sha256"] != digest:
            _fail(f"frozen authority hash differs: {path.name}")
    approval = _strict_json(paths.approval)
    if approval.get("approval_token") != f"APPROVE_REN_P1R1:{PLAN_SHA256}" or approval.get("automatic_next_stage") is not False:
        _fail("approval boundary differs")
    source = _digests(paths.archive, md5=True)
    if source != {"bytes": ARCHIVE_BYTES, "sha256": ARCHIVE_SHA256, "md5": ARCHIVE_MD5}:
        _fail("raw.rar identity differs")
    page = paths.local / "tool/download.htm"
    page_receipt = _curl_download(DOWNLOAD_PAGE_URL, page, paths.output / "DOWNLOAD_PAGE.headers.txt", paths.output / "DOWNLOAD_PAGE.curl.json")
    page_bytes = page.read_bytes()
    if b'href="/rar/rarlinux-x64-723.tar.gz"' not in page_bytes or b"RAR for Linux x64 7.23" not in page_bytes:
        _fail("official download page no longer lists Linux x64 7.23")
    _write_bytes(paths.output / "DOWNLOAD_PAGE.html", page_bytes)
    tool_receipt = _curl_download(TOOL_URL, paths.tool_tar, paths.output / "TOOL_DOWNLOAD.headers.txt", paths.output / "TOOL_DOWNLOAD.curl.json")
    if _digests(paths.tool_tar) != {"bytes": TOOL_TARBALL_BYTES, "sha256": TOOL_TARBALL_SHA256}:
        _fail("tool tarball identity differs")
    tar_members = _extract_tool(paths.tool_tar, paths.tool_root)
    rar, unrar, licence = paths.tool_root / "rar/rar", paths.tool_root / "rar/unrar", paths.tool_root / "rar/license.txt"
    identities = []
    for label, path, digest in (("rar", rar, RAR_SHA256), ("unrar", unrar, UNRAR_SHA256), ("license", licence, LICENSE_SHA256)):
        observed = _digests(path)
        if observed["sha256"] != digest:
            _fail(f"{label} identity differs")
        identities.append({"item": label, "path_suffix": str(path.relative_to(paths.local)), **observed,
                           "model_or_api_executed": "false", "numeric_target_emitted": "false"})
    versions = {"rar": _version(rar, paths.output / "RAR_VERSION.stdout.txt", paths.output / "RAR_VERSION.stderr.txt"),
                "unrar": _version(unrar, paths.output / "UNRAR_VERSION.stdout.txt", paths.output / "UNRAR_VERSION.stderr.txt")}
    listing = _run([str(unrar), "lt", "-v", "-p-", str(paths.archive)], 180)
    _write_bytes(paths.output / "OFFICIAL_LISTING.stdout.txt", listing.stdout)
    _write_bytes(paths.output / "OFFICIAL_LISTING.stderr.txt", listing.stderr)
    if listing.returncode != 0 or listing.stderr:
        _fail("official listing failed or emitted stderr")
    banner, official = _parse_unrar_listing(listing.stdout)
    difference = _listing_diff(official, _prior_rows(paths.prior))
    free = shutil.disk_usage(paths.local.parent).free
    required = EXPECTED_UNCOMPRESSED_BYTES + max(MIN_DISK_SAFETY_BYTES, EXPECTED_UNCOMPRESSED_BYTES // 5)
    passed = difference["status"] == "PASS_EXACT_LISTING_DIFF" and free >= required
    tool_identity = {"schema_version": SCHEMA_VERSION, "status": "PASS_TOOL_IDENTITY",
                     "download_page": page_receipt, "tool_download": tool_receipt,
                     "tarball": _digests(paths.tool_tar), "tar_members": tar_members,
                     "package_items": identities, "versions": versions,
                     "license_reviewed_from_package": True, "model_or_api_executed": False,
                     "numeric_target_emitted": False}
    preflight = {"schema_version": SCHEMA_VERSION, "stage": "R1A",
                 "status": "PASS_R1A_PREFLIGHT" if passed else "BLOCKED_R1A", "source": source,
                 "plan_sha256": PLAN_SHA256, "packet_sha256": PACKET_SHA256,
                 "approval_sha256": APPROVAL_SHA256, "prior_ledger_sha256": PRIOR_LEDGER_SHA256,
                 "listing": {"return_code": listing.returncode, **banner,
                             "stdout": _digests(paths.output / "OFFICIAL_LISTING.stdout.txt"),
                             "stderr": _digests(paths.output / "OFFICIAL_LISTING.stderr.txt")},
                 "disk": {"available_bytes": free, "required_bytes": required,
                          "status": "PASS" if free >= required else "BLOCKED"},
                 "model_or_api_executed": False, "numeric_target_emitted": False,
                 "automatic_next_stage": False}
    _write_json(paths.output / "TOOL_IDENTITY.json", tool_identity)
    _write_csv(paths.output / "TOOL_HASH_LEDGER.csv", identities,
               ("item", "path_suffix", "bytes", "sha256", "model_or_api_executed", "numeric_target_emitted"))
    _write_csv(paths.output / "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv", official, tuple(official[0]))
    _write_json(paths.output / "ARCHIVE_LISTING_DIFF.json", difference)
    _write_json(paths.output / "R1A_PREFLIGHT.json", preflight)
    if not passed:
        _fail("R1A did not pass")
    _seal(paths.output / "R1A_SEAL.json", "R1A", "PASS_R1A_SEALED", _bound(_r1a_files(paths)))
    print(paths.output)
    return 0


def _stored_members(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != EXPECTED_MEMBER_COUNT or len({row["member_path"] for row in rows}) != EXPECTED_MEMBER_COUNT:
        _fail("stored member ledger differs")
    if any(row.get("model_or_api_executed") != "false" or row.get("numeric_target_emitted") != "false" for row in rows):
        _fail("stored member ledger permission flags differ")
    return rows


def _ok_paths(raw: bytes, action: str) -> list[str]:
    text = raw.decode("utf-8", errors="replace").replace("\r", "\n")
    pattern = re.compile(rf"^{action}\s+(.+?)\s+OK\s*$")
    return [match.group(1).strip() for line in text.splitlines() if (match := pattern.match(line.strip()))]


def _danger(text: str) -> dict[str, int]:
    tokens = ("unsupported", "crc failed", "data error", "checksum error", "wrong password",
              "enter password", "corrupt", "damaged", "warning", "cannot create")
    return {token: len(re.findall(re.escape(token), text, re.I)) for token in tokens}


def r1b(paths: Paths, timeout: int) -> int:
    _verify_seal(paths.output / "R1A_SEAL.json", "R1A", "PASS_R1A_SEALED", _bound(_r1a_files(paths)))
    if any((paths.output / name).exists() for name in (*R1B_ARTIFACTS, "R1B_SEAL.json")):
        _fail("R1B already attempted")
    members = _stored_members(paths.output / "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv")
    expected = sorted(row["member_path"] for row in members if row["member_type"] == "regular_file")
    completed = _run([str(paths.tool_root / "rar/unrar"), "t", "-p-", str(paths.archive)], timeout)
    _write_bytes(paths.output / "ARCHIVE_TEST.stdout.txt", completed.stdout)
    _write_bytes(paths.output / "ARCHIVE_TEST.stderr.txt", completed.stderr)
    combined = (completed.stdout + b"\n" + completed.stderr).decode("utf-8", errors="replace").replace("\r", "\n")
    observed = sorted(_ok_paths(completed.stdout, "Testing"))
    danger = _danger(combined)
    all_ok = len(re.findall(r"^All OK\s*$", combined, re.M))
    passed = completed.returncode == 0 and not completed.stderr and observed == expected and len(observed) == EXPECTED_FILE_COUNT and all_ok == 1 and not any(danger.values())
    report = {"schema_version": SCHEMA_VERSION, "stage": "R1B",
              "status": "PASS_ARCHIVE_TEST" if passed else "BLOCKED_ARCHIVE_TEST",
              "return_code": completed.returncode, "expected_tested_file_count": len(expected),
              "observed_tested_file_count": len(observed), "tested_path_set_exact": observed == expected,
              "all_ok_marker_count": all_ok, "danger_marker_counts": danger,
              "stdout": _digests(paths.output / "ARCHIVE_TEST.stdout.txt"),
              "stderr": _digests(paths.output / "ARCHIVE_TEST.stderr.txt"),
              "extraction_authorized_by_this_report": passed, "extraction_attempted": False,
              "model_or_api_executed": False, "numeric_target_emitted": False,
              "automatic_next_stage": False}
    _write_json(paths.output / "ARCHIVE_TEST_REPORT.json", report)
    if not passed:
        _fail("full archive test did not pass; extraction forbidden")
    _seal(paths.output / "R1B_SEAL.json", "R1B", "PASS_R1B_SEALED", _bound(_r1b_files(paths)))
    print(paths.output / "ARCHIVE_TEST_REPORT.json")
    return 0


def _crc32(path: Path) -> str:
    crc = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            crc = zlib.crc32(block, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def r1c(paths: Paths, timeout: int) -> int:
    _verify_seal(paths.output / "R1A_SEAL.json", "R1A", "PASS_R1A_SEALED", _bound(_r1a_files(paths)))
    _verify_seal(paths.output / "R1B_SEAL.json", "R1B", "PASS_R1B_SEALED", _bound(_r1b_files(paths)))
    if paths.extraction.exists() or paths.extraction.is_symlink() or any((paths.output / name).exists() for name in (*R1C_ARTIFACTS, "R1C_SEAL.json")):
        _fail("R1C already attempted")
    paths.extraction.mkdir(mode=0o700)
    completed = _run([str(paths.tool_root / "rar/unrar"), "x", "-p-", "-o-", str(paths.archive), str(paths.extraction) + os.sep], timeout)
    _write_bytes(paths.output / "EXTRACTION.stdout.txt", completed.stdout)
    _write_bytes(paths.output / "EXTRACTION.stderr.txt", completed.stderr)
    expected_rows = _stored_members(paths.output / "OFFICIAL_ARCHIVE_MEMBER_LEDGER.csv")
    expected = {row["member_path"]: row for row in expected_rows}
    rows: list[dict[str, Any]] = []
    observed: set[str] = set()
    unsafe: list[str] = []
    for path in sorted(paths.extraction.rglob("*")):
        rel = path.relative_to(paths.extraction).as_posix()
        observed.add(rel)
        meta = path.lstat()
        kind = "symlink" if stat.S_ISLNK(meta.st_mode) else "regular_file" if stat.S_ISREG(meta.st_mode) else "directory" if stat.S_ISDIR(meta.st_mode) else "special"
        if kind not in {"regular_file", "directory"} or kind == "regular_file" and meta.st_nlink != 1:
            unsafe.append(f"unsafe_type_or_link:{rel}:{kind}:{meta.st_nlink}")
        reference = expected.get(rel)
        size = meta.st_size if kind == "regular_file" else 0
        crc = _crc32(path) if kind == "regular_file" else "00000000"
        type_ok = bool(reference and kind == reference["member_type"])
        size_ok = bool(reference and size == int(reference["uncompressed_bytes"]))
        crc_ok = bool(reference and crc == reference["crc"])
        if not (type_ok and size_ok and crc_ok):
            unsafe.append(f"member_mismatch:{rel}")
        rows.append({"member_path": rel, "observed_type": kind,
                     "hardlink_count": meta.st_nlink if kind == "regular_file" else "NA",
                     "observed_bytes": size, "expected_bytes": reference["uncompressed_bytes"] if reference else "NA",
                     "observed_crc32": crc, "expected_crc32": reference["crc"] if reference else "NA",
                     "type_match": str(type_ok).lower(), "size_match": str(size_ok).lower(),
                     "crc_match": str(crc_ok).lower(), "status": "PASS" if type_ok and size_ok and crc_ok else "FAIL",
                     "model_or_api_executed": "false", "numeric_target_emitted": "false"})
    missing, unexpected = sorted(expected.keys() - observed), sorted(observed - expected.keys())
    text = (completed.stdout + b"\n" + completed.stderr).decode("utf-8", errors="replace").replace("\r", "\n")
    extracted_ok = sorted(_ok_paths(completed.stdout, "Extracting"))
    danger = _danger(text)
    all_ok = len(re.findall(r"^All OK\s*$", text, re.M))
    passed = completed.returncode == 0 and not completed.stderr and not missing and not unexpected and not unsafe and len(rows) == EXPECTED_MEMBER_COUNT and len(extracted_ok) == EXPECTED_FILE_COUNT and all_ok == 1 and not any(danger.values())
    manifest = {"schema_version": SCHEMA_VERSION, "stage": "R1C",
                "status": "PASS_EXTRACTION_BYTE_IDENTITY" if passed else "QUARANTINED_EXTRACTION_MISMATCH",
                "quarantine_state": "RELEASED_FOR_READ_ONLY_ROW_AUDIT" if passed else "QUARANTINED_BLOCKED",
                "destination_name": paths.extraction.name, "return_code": completed.returncode,
                "stdout": _digests(paths.output / "EXTRACTION.stdout.txt"),
                "stderr": _digests(paths.output / "EXTRACTION.stderr.txt"),
                "all_ok_marker_count": all_ok, "danger_marker_counts": danger,
                "extract_ok_file_count": len(extracted_ok), "observed_member_count": len(rows),
                "observed_regular_file_count": sum(row["observed_type"] == "regular_file" for row in rows),
                "observed_directory_count": sum(row["observed_type"] == "directory" for row in rows),
                "observed_regular_file_bytes": sum(int(row["observed_bytes"]) for row in rows if row["observed_type"] == "regular_file"),
                "missing_members": missing, "unexpected_members": unexpected,
                "unsafe_or_mismatched": unsafe, "workbook_opened_or_parsed": False,
                "model_or_api_executed": False, "numeric_target_emitted": False,
                "automatic_next_stage": False}
    fields = tuple(rows[0]) if rows else ("member_path",)
    _write_csv(paths.output / "EXTRACTION_MEMBER_LEDGER.csv", rows, fields)
    _write_json(paths.output / "EXTRACTION_MANIFEST.json", manifest)
    if not passed:
        _fail("extraction remains quarantined after validation failure")
    r1c_files = _r1b_files(paths)
    r1c_files["seal:R1B"] = paths.output / "R1B_SEAL.json"
    r1c_files.update({f"artifact:{name}": paths.output / name for name in R1C_ARTIFACTS})
    _seal(paths.output / "R1C_SEAL.json", "R1C", "PASS_R1C_SEALED", _bound(r1c_files))
    print(paths.extraction)
    return 0


def _record_block(paths: Paths | None, phase: str, message: str) -> None:
    if paths is None or not paths.output.is_dir():
        return
    target = paths.output / f"{phase.upper()}_BLOCKED.json"
    if target.exists() or target.is_symlink():
        return
    _write_json(target, {"schema_version": SCHEMA_VERSION, "stage": phase.upper(),
                         "status": "BLOCKED", "reason": message,
                         "local_staging_is_quarantine": True, "model_or_api_executed": False,
                         "numeric_target_emitted": False, "automatic_next_stage": False})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("r1a", "r1b", "r1c"))
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args(argv)
    paths: Paths | None = None
    try:
        paths = Paths.build(args.project_root, args.run_id, new=args.phase == "r1a")
        if args.phase == "r1a":
            return r1a(paths)
        if args.phase == "r1b":
            return r1b(paths, args.timeout)
        return r1c(paths, args.timeout)
    except RecoveryError as exc:
        _record_block(paths, args.phase, str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
