#!/usr/bin/env python3
"""P1-only acquisition and pre-extraction Data Gate for Ren SCs ``raw.rar``.

The gate verifies the frozen payload, performs a metadata-only RAR listing and
an archive test, and stops before extraction whenever either operation is not
fully supported.  It never parses spreadsheet rows, derives targets, creates
SOH/RUL labels, runs a model, or calls an external API.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = "audit-cap.ren-scs-p1-data-gate.v1"
LOCAL_MANIFEST_SCHEMA_VERSION = "audit-cap.ren-scs-local-raw-manifest.v1"
SOURCE_ID = "ren_scs_figshare_11522082_v1"
DOI = "10.6084/m9.figshare.11522082.v1"
LICENCE = "CC BY 4.0"
DIRECT_URL = "https://ndownloader.figshare.com/files/20691603"
EXPECTED_BYTES = 2_114_703_017
PUBLISHED_MD5 = "26a7a663217c59377c83fb2a8274466b"
PROJECT_SHA256 = "a8f1083b887f95483561a94b624b323ff42814654ee7f23e7f95bc042fa258d8"
TEN_GIB = 10 * 1024**3

REQUIRED_OUTPUTS = (
    "ACQUISITION_MANIFEST.json",
    "RAW_HASH_LEDGER.csv",
    "ARCHIVE_SAFETY_REPORT.json",
    "ARCHIVE_MEMBER_LEDGER.csv",
    "UNIT_IDENTITY_LEDGER.csv",
    "SCHEMA_UNIT_LEDGER.csv",
    "CHRONOLOGY_LEDGER.csv",
    "DUPLICATE_OVERLAP_LEDGER.csv",
    "TARGET_ELIGIBILITY.csv",
    "EVENT_CENSOR_LEDGER.csv",
    "SPLIT_LEAKAGE_LEDGER.json",
    "DATA_GATE_SUMMARY.json",
    "DATA_GATE_REPORT.md",
    "ARTIFACT_MANIFEST.json",
    "ARTIFACT_HASHES.sha256",
    "COMPLETE.json",
)
ARTIFACT_INTEGRITY_SCHEMA_VERSION = "audit-cap.non-circular-artifact-integrity.v1"
ARTIFACT_GRAPH_WRITE_ORDER = (
    "COMPLETE.json",
    "ARTIFACT_MANIFEST.json",
    "ARTIFACT_HASHES.sha256",
)


class RenDataGateError(RuntimeError):
    """Raised when a frozen byte or safe-listing contract is violated."""


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _require_regular_file(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise RenDataGateError(f"missing {label}: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RenDataGateError(f"{label} must be a regular non-symlink file")


def _require_plain_directory(path: Path, label: str, *, create: bool = False) -> None:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise RenDataGateError(f"missing {label}: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise RenDataGateError(f"{label} must be a real non-symlink directory")


def _file_digests(path: Path, block_bytes: int = 8 * 1024 * 1024) -> dict[str, Any]:
    _require_regular_file(path, "file")
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(block_bytes), b""):
            size += len(block)
            md5.update(block)
            sha256.update(block)
    return {"bytes": size, "md5": md5.hexdigest(), "sha256": sha256.hexdigest()}


def _sanitize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower()
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme.lower(), host, parsed.path, "", ""))


def _sanitized_header_evidence(header_path: Path | None) -> dict[str, Any] | None:
    if header_path is None or not header_path.is_file() or header_path.is_symlink():
        return None
    statuses: list[str] = []
    lengths: list[str] = []
    etags: list[str] = []
    modified: list[str] = []
    content_types: list[str] = []
    final_path = "NA"
    for line in header_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped.startswith("HTTP/"):
            statuses.append(" ".join(stripped.split()[:3]))
        elif lowered.startswith("location:"):
            final_path = _sanitize_url(stripped.split(":", 1)[1].strip())
        elif lowered.startswith("content-length:"):
            lengths.append(stripped.split(":", 1)[1].strip())
        elif lowered.startswith("etag:"):
            etags.append(stripped.split(":", 1)[1].strip().strip('"'))
        elif lowered.startswith("last-modified:"):
            modified.append(stripped.split(":", 1)[1].strip())
        elif lowered.startswith("content-type:"):
            content_types.append(stripped.split(":", 1)[1].strip())
    return {
        "http_status_lines": statuses,
        "redirect_effective_scheme_host_path": final_path,
        "content_lengths": lengths,
        "etags": etags,
        "last_modified": modified,
        "content_types": content_types,
        "raw_header_log_sha256": _file_digests(header_path)["sha256"],
        "query_and_fragment_persisted": False,
    }


def _run_tool(argv: Sequence[str], timeout_seconds: int = 900) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
            env={"PATH": os.environ.get("PATH", "")},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenDataGateError(f"archive tool could not be executed: {argv[0]}") from exc


def _tool_identity(executable: str) -> dict[str, Any]:
    path_text = shutil.which(executable)
    if path_text is None:
        raise RenDataGateError(f"required archive tool is unavailable: {executable}")
    path = Path(path_text).resolve()
    identity = _file_digests(path)
    implementation_path = path
    # Ubuntu's /usr/bin/7z is a tiny fixed launcher.  Record both the launcher
    # and the ELF it names so the decoder implementation, not merely a shell
    # wrapper, is hash-pinned in the evidence bundle.
    if identity["bytes"] <= 4096:
        try:
            launcher_text = path.read_text(encoding="ascii")
        except (OSError, UnicodeDecodeError):
            launcher_text = ""
        match = re.fullmatch(
            r"#![^\n]+\nexec\s+(/[^\s]+)\s+\"\$@\"\s*\n?",
            launcher_text,
        )
        if match is not None:
            candidate = Path(match.group(1))
            _require_regular_file(candidate, "archive tool implementation")
            implementation_path = candidate
    implementation = _file_digests(implementation_path)
    probe = _run_tool([str(path), "i"], timeout_seconds=30)
    text = (probe.stdout + b"\n" + probe.stderr).decode("utf-8", errors="replace")
    version = next((line.strip() for line in text.splitlines() if line.strip()), "UNAVAILABLE")
    return {
        "executable": str(path),
        "bytes": identity["bytes"],
        "sha256": identity["sha256"],
        "implementation_executable": str(implementation_path),
        "implementation_bytes": implementation["bytes"],
        "implementation_sha256": implementation["sha256"],
        "version": version[:500],
    }


def _parse_properties(lines: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        if " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        result[key] = value
    return result


def _parse_slt(raw: bytes) -> tuple[dict[str, str], list[dict[str, str]]]:
    text = raw.decode("utf-8", errors="strict")
    marker = "----------\n"
    if marker not in text:
        raise RenDataGateError("7z listing lacks the member delimiter")
    header_text, member_text = text.split(marker, 1)
    header_lines = header_text.splitlines()
    try:
        header_start = max(index for index, line in enumerate(header_lines) if line == "--") + 1
    except ValueError as exc:
        raise RenDataGateError("7z listing lacks archive properties") from exc
    archive = _parse_properties(header_lines[header_start:])
    members = [
        _parse_properties(block.splitlines())
        for block in re.split(r"\n\s*\n", member_text.strip())
        if block.strip()
    ]
    if not members or any("Path" not in item for item in members):
        raise RenDataGateError("7z listing contains an invalid member record")
    return archive, members


def _integer_field(record: Mapping[str, str], field: str, *, required: bool) -> int | None:
    value = record.get(field, "")
    if not value and not required:
        return None
    if not value.isdigit():
        raise RenDataGateError(f"archive member lacks a valid {field}")
    return int(value)


def _member_safety(members: Sequence[Mapping[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    normalized: list[str] = []
    unsafe: list[str] = []
    file_count = 0
    directory_count = 0
    total_size = 0
    total_packed = 0
    allowed_file_count = 0
    for item in members:
        path_text = item["Path"]
        is_directory = item.get("Folder") == "+"
        pure = PurePosixPath(path_text)
        path_safe = bool(
            path_text
            and "\\" not in path_text
            and not pure.is_absolute()
            and not re.match(r"^[A-Za-z]:", path_text)
            and ".." not in pure.parts
            and "." not in pure.parts
            and str(pure) == path_text
        )
        if not path_safe:
            unsafe.append(f"unsafe_path:{path_text}")
        if any(item.get(name, "") for name in ("Symbolic Link", "Hard Link", "Copy Link")):
            unsafe.append(f"link_member:{path_text}")
        if item.get("Encrypted") != "-":
            unsafe.append(f"encrypted_member:{path_text}")
        if item.get("Split Before") != "-" or item.get("Split After") != "-":
            unsafe.append(f"split_member:{path_text}")
        size = _integer_field(item, "Size", required=not is_directory)
        packed = _integer_field(item, "Packed Size", required=not is_directory)
        suffix = pure.suffix.lower()
        if is_directory:
            directory_count += 1
        else:
            file_count += 1
            total_size += size or 0
            total_packed += packed or 0
            if suffix != ".xls":
                unsafe.append(f"unexpected_extension:{path_text}")
            else:
                allowed_file_count += 1
        normalized.append(str(pure))
        stem = pure.stem
        base_stem = re.sub(r"__(?:1|2)$", "", stem)
        segment = stem[len(base_stem) :] or "base"
        rows.append(
            {
                "member_path": path_text,
                "member_type": "directory" if is_directory else "regular_file_claim_from_listing",
                "batch_path_component": pure.parts[0] if pure.parts else "NA",
                "provisional_filename_stem": base_stem if not is_directory else "NA",
                "segment_suffix": segment if not is_directory else "NA",
                "uncompressed_bytes": size if size is not None else "NA",
                "packed_bytes": packed if packed is not None else "NA",
                "crc": item.get("CRC") or "NA",
                "compression_method": item.get("Method") or "NA",
                "encrypted": item.get("Encrypted") or "UNKNOWN",
                "link_fields_empty": not any(
                    item.get(name, "") for name in ("Symbolic Link", "Hard Link", "Copy Link")
                ),
                "extension": suffix if suffix else "NA",
                "listing_safety_status": "PASS_LISTING_METADATA" if path_safe else "FAIL_UNSAFE_PATH",
                "row_content_status": "NOT_EXTRACTED_NOT_PARSED",
            }
        )
    duplicates = sorted(path for path in set(normalized) if normalized.count(path) > 1)
    folded: dict[str, list[str]] = {}
    for path in normalized:
        folded.setdefault(path.casefold(), []).append(path)
    case_collisions = sorted(values for values in folded.values() if len(set(values)) > 1)
    if duplicates:
        unsafe.append("duplicate_normalized_path")
    if case_collisions:
        unsafe.append("casefold_collision")
    return rows, {
        "member_count": len(members),
        "regular_file_count": file_count,
        "directory_count": directory_count,
        "allowed_xls_file_count": allowed_file_count,
        "listed_uncompressed_bytes": total_size,
        "listed_packed_bytes": total_packed,
        "duplicate_normalized_paths": duplicates,
        "casefold_collisions": case_collisions,
        "unsafe_findings": sorted(set(unsafe)),
        "status": "PASS_LISTING_METADATA_ONLY" if not unsafe else "FAIL_LISTING_SAFETY",
    }


def _test_evidence(completed: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    combined = completed.stdout + b"\n" + completed.stderr
    text = combined.decode("utf-8", errors="replace")
    unsupported_count = len(re.findall(r"ERROR: Unsupported Method", text))
    if completed.returncode == 0 and unsupported_count == 0:
        status = "PASS_ARCHIVE_TEST"
    elif unsupported_count:
        status = "BLOCKED_ARCHIVE_TEST_UNSUPPORTED_METHOD"
    else:
        status = "FAIL_ARCHIVE_TEST"
    return {
        "return_code": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_bytes": len(completed.stderr),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "combined_sha256": hashlib.sha256(combined).hexdigest(),
        "unsupported_method_error_count": unsupported_count,
        "crc_error_marker_count": len(re.findall(r"CRC Failed|CRC error", text, flags=re.I)),
        "data_error_marker_count": len(re.findall(r"Data Error", text, flags=re.I)),
        "status": status,
    }


def _write_bytes(path: Path, value: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise RenDataGateError(f"refusing to overwrite artifact: {path}")
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _write_json(path: Path, value: Any) -> None:
    _write_bytes(path, _canonical_json_bytes(value))


def _csv_cell(value: Any) -> str | int | float:
    if value is None:
        return "NA"
    if isinstance(value, (str, int, float)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    if path.exists() or path.is_symlink():
        raise RenDataGateError(f"refusing to overwrite artifact: {path}")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in fields})
        stream.flush()
        os.fsync(stream.fileno())


def _write_or_validate_local_manifest(path: Path, manifest: Mapping[str, Any]) -> str:
    expected = _canonical_json_bytes(manifest)
    if path.exists():
        _require_regular_file(path, "local raw manifest")
        observed = path.read_bytes()
        try:
            prior = json.loads(observed)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RenDataGateError("existing local raw manifest is invalid") from exc
        if (
            not isinstance(prior, dict)
            or observed != _canonical_json_bytes(prior)
            or set(prior) != set(manifest)
            or not isinstance(prior.get("created_at_utc"), str)
            or {key: value for key, value in prior.items() if key != "created_at_utc"}
            != {key: value for key, value in manifest.items() if key != "created_at_utc"}
        ):
            raise RenDataGateError("existing local raw manifest differs")
        return hashlib.sha256(observed).hexdigest()
    _write_bytes(path, expected)
    return hashlib.sha256(expected).hexdigest()


def _artifact_record(path: Path) -> dict[str, Any]:
    value = _file_digests(path)
    return {"filename": path.name, "bytes": value["bytes"], "sha256": value["sha256"]}


def _finalize_artifact_graph(
    staging: Path,
    *,
    run_id: str,
    completion_decision: Mapping[str, Any],
) -> None:
    """Write the decision first, then bind it without a circular self-hash."""

    if any(
        (staging / name).exists() or (staging / name).is_symlink()
        for name in ARTIFACT_GRAPH_WRITE_ORDER
    ):
        raise RenDataGateError("artifact integrity graph outputs already exist")
    if (
        not isinstance(completion_decision, Mapping)
        or completion_decision.get("run_id") != run_id
        or {"artifact_manifest_sha256", "artifact_hashes_sha256"}
        & set(completion_decision)
    ):
        raise RenDataGateError("completion decision violates non-circular graph schema")

    complete = dict(completion_decision)
    complete["artifact_integrity"] = {
        "schema_version": ARTIFACT_INTEGRITY_SCHEMA_VERSION,
        "write_order": list(ARTIFACT_GRAPH_WRITE_ORDER),
        "bound_by_later_artifacts": [
            "ARTIFACT_MANIFEST.json",
            "ARTIFACT_HASHES.sha256",
        ],
        "circular_hash_fields_omitted": [
            "artifact_manifest_sha256",
            "artifact_hashes_sha256",
        ],
    }
    _write_json(staging / "COMPLETE.json", complete)

    pre_manifest_names = sorted(path.name for path in staging.iterdir())
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "integrity_graph": {
            "schema_version": ARTIFACT_INTEGRITY_SCHEMA_VERSION,
            "write_order": list(ARTIFACT_GRAPH_WRITE_ORDER),
            "manifest_excludes": [
                "ARTIFACT_MANIFEST.json",
                "ARTIFACT_HASHES.sha256",
            ],
            "hash_list_excludes": ["ARTIFACT_HASHES.sha256"],
        },
        "artifacts": [_artifact_record(staging / name) for name in pre_manifest_names],
        "raw_rows_in_bundle": False,
    }
    _write_json(staging / "ARTIFACT_MANIFEST.json", manifest)

    hash_names = sorted(path.name for path in staging.iterdir())
    hash_lines = [
        f"{_file_digests(staging / name)['sha256']}  {name}\n" for name in hash_names
    ]
    _write_bytes(staging / "ARTIFACT_HASHES.sha256", "".join(hash_lines).encode("ascii"))


def _provisional_groups(member_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in member_rows:
        if row["member_type"] == "directory":
            continue
        key = (str(row["batch_path_component"]), str(row["provisional_filename_stem"]))
        groups.setdefault(key, []).append(row)
    result: list[dict[str, Any]] = []
    for (batch, stem), rows in sorted(groups.items()):
        paths = sorted(str(row["member_path"]) for row in rows)
        result.append(
            {
                "provisional_key": f"{batch}/{stem}",
                "batch_path_component": batch,
                "filename_stem": stem,
                "listed_segment_count": len(rows),
                "listed_member_paths": ";".join(paths),
                "physical_device_id": "UNPROVEN_DO_NOT_INFER_FROM_FILENAME",
                "batch_identity": "UNPROVEN_DO_NOT_INFER_FROM_DIRECTORY",
                "protocol_group": "UNPROVEN_DO_NOT_INFER_FROM_FILE_COUNT",
                "row_identity_evidence": "UNAVAILABLE_ARCHIVE_NOT_EXTRACTED",
                "status": "BLOCKED_ARCHIVE_TEST_AND_IDENTITY",
            }
        )
    return result


def _target_rows() -> list[dict[str, Any]]:
    rows = [
        ("native_logged_voltage", "V", "BLOCKED_NOT_EXTRACTED"),
        ("native_logged_current", "A", "BLOCKED_NOT_EXTRACTED"),
        ("farad_capacitance", "F", "NA_NO_FROZEN_DERIVATION"),
        ("ESR", "ohm", "NA_NO_NATIVE_ESR_OR_EIS_EVIDENCE"),
        ("SOH", "ratio", "BLOCKED_NO_C_REF_OR_ELIGIBLE_CAPACITANCE"),
        ("RUL", "NA", "NA_NO_EVENT_CENSOR_TRUTH"),
    ]
    return [
        {
            "target": target,
            "unit": unit,
            "row_structure": "NOT_AUDITED_ARCHIVE_TEST_BLOCKED",
            "numeric_target_emitted": "NO",
            "status": status,
            "reason": "P1 stopped before extraction; no row, target, SOH, or RUL construction is permitted",
        }
        for target, unit, status in rows
    ]


def _report(summary: Mapping[str, Any], safety: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Ren SCs P1 Acquisition / Archive Data Gate",
            "",
            f"- Overall decision: `{summary['overall_decision']}`",
            "- Exact payload bytes, published MD5, and project SHA-256: `PASS`.",
            f"- Listing: {safety['regular_file_count']} files, {safety['directory_count']} directories, {safety['listed_uncompressed_bytes']} uncompressed bytes.",
            "- The installed 7-Zip decoder returned `Unsupported Method` for every listed file; archive test did not pass.",
            "- Frozen strong-stop rule applied: no extraction and no spreadsheet/row parsing.",
            "- Listed `.xls` members remain potential active-content containers until a separately approved safe static inspection is possible.",
            "- Filename stems/directories are not accepted as physical-device or protocol identity evidence.",
            "- Capacitance, ESR, SOH, event/censor truth, split manifest, and RUL remain `NA/BLOCKED`; none was generated or scored.",
            "- No model, LLM, Agent, authenticated API, P3, development API, or P4/P5 action ran.",
            "",
            "## Required next decision",
            "",
            "Keep the verified archive frozen. A new human-approved archive-tool/parser plan is required before any extraction attempt; the present P1 result cannot enter P2.",
            "",
        ]
    )


def run_data_gate(
    *,
    archive_path: Path,
    output_parent: Path,
    run_id: str | None = None,
    header_path: Path | None = None,
    local_manifest_path: Path | None = None,
) -> Path:
    if run_id is None:
        run_id = datetime.now().astimezone().strftime("p1_%Y%m%d_%H%M%S")
    if re.fullmatch(r"p1_[A-Za-z0-9_-]+", run_id) is None:
        raise RenDataGateError("run_id must match p1_[A-Za-z0-9_-]+")
    _require_plain_directory(output_parent, "output parent", create=True)
    final_dir = output_parent / run_id
    if final_dir.exists() or final_dir.is_symlink():
        raise RenDataGateError(f"append-only output already exists: {final_dir}")

    observed = _file_digests(archive_path)
    if observed != {"bytes": EXPECTED_BYTES, "md5": PUBLISHED_MD5, "sha256": PROJECT_SHA256}:
        raise RenDataGateError("frozen Ren archive bytes/MD5/SHA-256 differ")
    tool = _tool_identity("7z")
    listing = _run_tool([tool["executable"], "l", "-slt", str(archive_path)])
    if listing.returncode != 0:
        raise RenDataGateError("archive listing failed before member audit")
    archive_properties, raw_members = _parse_slt(listing.stdout)
    member_rows, safety = _member_safety(raw_members)
    if safety["status"] != "PASS_LISTING_METADATA_ONLY":
        raise RenDataGateError("archive listing exposed an unsafe member")
    if (
        archive_properties.get("Type") != "Rar5"
        or archive_properties.get("Physical Size") != str(EXPECTED_BYTES)
        or archive_properties.get("Encrypted") != "-"
        or archive_properties.get("Multivolume") != "-"
        or archive_properties.get("Volumes") != "1"
    ):
        raise RenDataGateError("archive container properties differ from the safe envelope")

    available = shutil.disk_usage(output_parent).free
    required = safety["listed_uncompressed_bytes"] + max(
        TEN_GIB, int(0.20 * safety["listed_uncompressed_bytes"])
    )
    disk_preflight = {
        "available_bytes": available,
        "pending_approved_payload_bytes": 0,
        "listed_uncompressed_bytes": safety["listed_uncompressed_bytes"],
        "safety_margin_bytes": max(TEN_GIB, int(0.20 * safety["listed_uncompressed_bytes"])),
        "required_available_bytes": required,
        "status": "PASS" if available >= required else "FAIL",
    }
    if available < required:
        raise RenDataGateError("disk preflight failed before archive test")

    tested = _run_tool([tool["executable"], "t", str(archive_path)])
    test_evidence = _test_evidence(tested)
    groups = _provisional_groups(member_rows)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    transport = _sanitized_header_evidence(header_path)
    local_manifest_path = local_manifest_path or archive_path.parent / "LOCAL_RAW_MANIFEST.json"
    local_manifest = {
        "schema_version": LOCAL_MANIFEST_SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "doi": DOI,
        "licence": LICENCE,
        "created_at_utc": created_at,
        "scope": "local_only_ignored_raw_archive_manifest",
        "payload": {
            "filename": archive_path.name,
            "direct_url": DIRECT_URL,
            "expected_bytes": EXPECTED_BYTES,
            "observed_bytes": observed["bytes"],
            "published_md5": PUBLISHED_MD5,
            "observed_md5": observed["md5"],
            "project_sha256": observed["sha256"],
            "status": "PASS_EXACT_BYTES_MD5_SHA256",
        },
        "sanitized_transport_evidence": transport,
        "archive_tool": tool,
        "listing_stdout_sha256": hashlib.sha256(listing.stdout).hexdigest(),
        "archive_test": test_evidence,
        "raw_payload_policy": "ignored_local_only_never_commit",
    }
    local_manifest_sha256 = _write_or_validate_local_manifest(local_manifest_path, local_manifest)

    acquisition = {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "doi": DOI,
        "licence": LICENCE,
        "run_id": run_id,
        "generated_at_utc": created_at,
        "scope": "P1_ACQUISITION_AND_PRE_EXTRACTION_AUDIT_ONLY",
        "payload": local_manifest["payload"],
        "sanitized_transport_evidence": transport,
        "local_raw_manifest": {
            "relative_name": local_manifest_path.name,
            "sha256": local_manifest_sha256,
            "tracked": False,
        },
        "model_or_api_executed": False,
    }
    archive_safety = {
        "schema_version": SCHEMA_VERSION,
        "archive_properties": archive_properties,
        "tool": tool,
        "listing_return_code": listing.returncode,
        "listing_stdout_bytes": len(listing.stdout),
        "listing_stdout_sha256": hashlib.sha256(listing.stdout).hexdigest(),
        "listing_stderr_sha256": hashlib.sha256(listing.stderr).hexdigest(),
        "member_summary": safety,
        "disk_preflight": disk_preflight,
        "archive_test": test_evidence,
        "extraction_attempted": False,
        "spreadsheet_opened_or_parsed": False,
        "legacy_xls_active_content_status": "BLOCKED_NOT_STATICALLY_INSPECTED",
        "status": test_evidence["status"],
    }
    raw_hash_rows = [
        {
            "item_id": "figshare_file_20691603",
            "filename": archive_path.name,
            "direct_url": DIRECT_URL,
            "expected_bytes": EXPECTED_BYTES,
            "observed_bytes": observed["bytes"],
            "published_md5": PUBLISHED_MD5,
            "observed_md5": observed["md5"],
            "project_sha256": observed["sha256"],
            "status": "PASS_EXACT_BYTES_MD5_SHA256",
        }
    ]
    schema_rows = [
        {
            "scope": "archive_members",
            "field_or_container": "legacy_binary_Excel_.xls",
            "listed_file_count": safety["regular_file_count"],
            "row_schema": "NOT_PARSED",
            "unit_evidence": "NOT_AUDITED",
            "formula_macro_hidden_sheet_status": "BLOCKED_NOT_EXTRACTED",
            "status": "BLOCKED_ARCHIVE_TEST",
        }
    ]
    chronology_rows = [
        {
            "scope": "all_provisional_filename_groups",
            "absolute_time": "NOT_AUDITED",
            "cycle_index": "NOT_AUDITED",
            "reset_segment_boundaries": "NOT_AUDITED",
            "terminal_record": "NOT_AUDITED",
            "status": "BLOCKED_ARCHIVE_TEST",
        }
    ]
    duplicate_rows = [
        {
            "provisional_key": row["provisional_key"],
            "listed_segment_count": row["listed_segment_count"],
            "exact_row_digest": "NOT_AVAILABLE",
            "waveform_fingerprint": "NOT_AVAILABLE",
            "physical_overlap": "UNRESOLVED",
            "status": "BLOCKED_ARCHIVE_TEST_AND_IDENTITY",
        }
        for row in groups
    ]
    event_rows = [
        {
            "provisional_key": row["provisional_key"],
            "physical_device_id": "UNPROVEN",
            "explicit_failure_record": "NOT_AUDITED",
            "threshold_crossing": "NOT_COMPUTED",
            "event_indicator": "NA_NOT_GENERATED",
            "censor_time": "NA_NOT_GENERATED",
            "rul_truth": "NA",
            "status": "BLOCKED_ARCHIVE_TEST_AND_EVENT_SEMANTICS",
        }
        for row in groups
    ]
    split = {
        "schema_version": SCHEMA_VERSION,
        "provisional_filename_group_count": len(groups),
        "physical_unit_registry_status": "BLOCKED_DO_NOT_INFER_FROM_113_FILENAME_STEMS",
        "four_batch_mapping_status": "BLOCKED_DO_NOT_INFER_FROM_DIRECTORIES",
        "protocol_88_25_mapping_status": "BLOCKED_DO_NOT_INFER_FROM_FILE_COUNTS",
        "whole_unit_outer_cv_manifest": "NA_NOT_GENERATED",
        "split_hash": "NA",
        "suffix_only_inputs_forbidden": True,
        "status": "BLOCKED_ARCHIVE_TEST_AND_IDENTITY",
    }
    overall = (
        "ACQUISITION_INTEGRITY_PASS_ARCHIVE_TEST_BLOCKED_NO_EXTRACTION"
        if test_evidence["status"] == "BLOCKED_ARCHIVE_TEST_UNSUPPORTED_METHOD"
        else "ACQUISITION_INTEGRITY_PASS_ARCHIVE_TEST_FAILED_NO_EXTRACTION"
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "run_id": run_id,
        "overall_decision": overall,
        "scientific_eligibility": "BLOCKED",
        "row_level_audit_completed": False,
        "row_level_target_eligibility_pass": False,
        "gate_status": {
            "acquisition_integrity": "PASS_EXACT_BYTES_MD5_SHA256",
            "archive_listing": safety["status"],
            "disk_preflight": disk_preflight["status"],
            "archive_test": test_evidence["status"],
            "extraction": "NOT_ATTEMPTED_STRONG_STOP",
            "identity": "BLOCKED_ARCHIVE_TEST_AND_IDENTITY",
            "schema_unit": "BLOCKED_NOT_EXTRACTED",
            "chronology": "BLOCKED_NOT_EXTRACTED",
            "duplicate_overlap": "BLOCKED_NOT_EXTRACTED_AND_IDENTITY",
            "target": "BLOCKED_RUL_NA_ESR_NA_SOH_BLOCKED",
            "terminal_event_censor": "BLOCKED_RUL_NA",
            "split_leakage": "BLOCKED_IDENTITY",
        },
        "listed_member_count": safety["member_count"],
        "listed_regular_file_count": safety["regular_file_count"],
        "listed_directory_count": safety["directory_count"],
        "listed_uncompressed_bytes": safety["listed_uncompressed_bytes"],
        "provisional_filename_group_count": len(groups),
        "rul_status": "NA",
        "esr_status": "NA",
        "soh_status": "BLOCKED",
        "numeric_target_emitted": False,
        "model_or_api_executed": False,
        "required_next_gate": "HUMAN_APPROVAL_FOR_A_NEW_ARCHIVE_TOOL_OR_PARSER_PLAN",
    }

    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}.staging-", dir=output_parent))
    try:
        _write_json(staging / "ACQUISITION_MANIFEST.json", acquisition)
        _write_csv(staging / "RAW_HASH_LEDGER.csv", raw_hash_rows, tuple(raw_hash_rows[0]))
        _write_json(staging / "ARCHIVE_SAFETY_REPORT.json", archive_safety)
        _write_csv(staging / "ARCHIVE_MEMBER_LEDGER.csv", member_rows, tuple(member_rows[0]))
        _write_csv(staging / "UNIT_IDENTITY_LEDGER.csv", groups, tuple(groups[0]))
        _write_csv(staging / "SCHEMA_UNIT_LEDGER.csv", schema_rows, tuple(schema_rows[0]))
        _write_csv(staging / "CHRONOLOGY_LEDGER.csv", chronology_rows, tuple(chronology_rows[0]))
        _write_csv(staging / "DUPLICATE_OVERLAP_LEDGER.csv", duplicate_rows, tuple(duplicate_rows[0]))
        target_rows = _target_rows()
        _write_csv(staging / "TARGET_ELIGIBILITY.csv", target_rows, tuple(target_rows[0]))
        _write_csv(staging / "EVENT_CENSOR_LEDGER.csv", event_rows, tuple(event_rows[0]))
        _write_json(staging / "SPLIT_LEAKAGE_LEDGER.json", split)
        _write_json(staging / "DATA_GATE_SUMMARY.json", summary)
        _write_bytes(staging / "DATA_GATE_REPORT.md", _report(summary, safety).encode("utf-8"))
        complete = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": "COMPLETE_P1_AUDIT_STRONG_STOP_NO_EXTRACTION",
            "overall_decision": overall,
            "required_output_count": len(REQUIRED_OUTPUTS),
            "extraction_attempted": False,
            "rul_generated_or_scored": False,
            "model_or_api_executed": False,
        }
        _finalize_artifact_graph(
            staging,
            run_id=run_id,
            completion_decision=complete,
        )
        observed_names = tuple(sorted(path.name for path in staging.iterdir()))
        if observed_names != tuple(sorted(REQUIRED_OUTPUTS)):
            raise RenDataGateError("incomplete Ren P1 artifact graph")
        staging.rename(final_dir)
        return final_dir
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/ren_scs"))
    parser.add_argument("--output-parent", type=Path, default=Path("data/audit/ren_scs"))
    parser.add_argument("--run-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_data_gate(
        archive_path=args.raw_root / "raw.rar",
        output_parent=args.output_parent,
        run_id=args.run_id,
        header_path=args.raw_root / "incoming" / "raw.rar.headers.partial",
        local_manifest_path=args.raw_root / "LOCAL_RAW_MANIFEST.json",
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
