"""Preparation-only R1D static inspection; no file/CLI or row-parser entry point.

Inputs are caller-supplied bytes. This module does not establish R1A/R1B/R1C
authority, install dependencies, extract archives, evaluate workbook content,
or grant R1E eligibility. A future reviewed caller must enforce those gates.
Only BIFF8 framing and a deliberately small record vocabulary are supported.
Unknown records/streams are counted, never silently treated as passive. Reports
contain structural counts/types/offsets, not cell values, names, URLs, formula
tokens, cached numbers, exception messages, or raw workbook bytes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import importlib
import io
import math
import struct
from typing import Any


SCHEMA_VERSION = "audit-cap.ren-p1r1-xls-static.preparation.v1"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
FALSE_FLAGS = (
    "archive_test_executed", "extraction_attempted", "workbook_code_executed",
    "formulas_evaluated", "raw_rows_emitted", "model_or_api_executed",
    "numeric_target_emitted", "row_parse_authorized", "p2_eligible",
)

# Recognition is NOT schema validation. Variable-length passive data remains
# opaque here; R1E must separately validate its schema, types, units and rows.
PASSIVE_RECORDS = {
    0x000A: "EOF", 0x0031: "FONT", 0x003D: "WINDOW1", 0x0042: "CODEPAGE",
    0x005C: "WRITEACCESS", 0x008C: "COUNTRY", 0x0092: "PALETTE",
    0x00BD: "MULRK", 0x00BE: "MULBLANK", 0x00D7: "DBCELL", 0x00E0: "XF",
    0x00E1: "INTERFACEHDR", 0x00E2: "INTERFACEEND", 0x00FC: "SST",
    0x00FD: "LABELSST", 0x00FF: "EXTSST", 0x0200: "DIMENSIONS",
    0x0201: "BLANK", 0x0203: "NUMBER", 0x0204: "LABEL", 0x0205: "BOOLERR",
    0x0208: "ROW", 0x020B: "INDEX", 0x023E: "WINDOW2", 0x027E: "RK",
    0x0293: "STYLE", 0x041E: "FORMAT", 0x0022: "DATEMODE",
}
SPECIAL_RECORDS = {
    0x0809: "BOF", 0x0085: "BOUNDSHEET", 0x002F: "FILEPASS",
    0x0017: "EXTERNSHEET", 0x01AE: "SUPBOOK", 0x005D: "OBJ",
    0x0006: "FORMULA", 0x0207: "STRING", 0x003C: "CONTINUE",
    0x0018: "NAME", 0x0023: "EXTERNNAME", 0x01B8: "HLINK",
    0x0221: "ARRAY", 0x04BC: "SHRFMLA", 0x0236: "TABLE",
    0x00EB: "MSODRAWINGGROUP", 0x00EC: "MSODRAWING", 0x00ED: "MSODRAWINGSELECTION",
}
RECORD_NAMES = PASSIVE_RECORDS | SPECIAL_RECORDS
SHEET_TYPES = {0: "worksheet_or_dialog", 1: "xlm_macro", 2: "chart", 6: "vb_module"}
BOF_TYPES = {5: "workbook_globals", 6: "vb_module", 16: "worksheet_or_dialog", 32: "chart", 64: "xlm_macro"}


@dataclass(frozen=True)
class ScanLimits:
    max_input_bytes: int = 256 * 1024 * 1024
    max_stream_bytes: int = 256 * 1024 * 1024
    max_total_stream_bytes: int = 512 * 1024 * 1024
    max_ole_entries: int = 4096
    max_records: int = 2_000_000

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in vars(self).values()):
            raise ValueError("scan limits must be positive integers")


def _report(container: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "container": container,
        "preparation_only": True, "scan_complete": False,
        "status": "BLOCKED_ROW_PARSE", "blockers": [],
        **dict.fromkeys(FALSE_FLAGS, False),
    }


def _finish(report: dict[str, Any], blockers: set[str]) -> dict[str, Any]:
    report["blockers"] = sorted(blockers)
    report["status"] = (
        "BLOCKED_ROW_PARSE" if blockers or not report["scan_complete"]
        else "STATIC_SCAN_COMPLETE_REVIEW_REQUIRED"
    )
    return report


def identify_container(prefix: bytes) -> str:
    """Sniff signatures only; do not parse XML/HTML or decompress ZIP payloads."""
    if not isinstance(prefix, bytes):
        raise TypeError("input must be bytes")
    if not prefix:
        return "EMPTY"
    if prefix.startswith(OLE_MAGIC):
        return "OLE_CFB"
    if OLE_MAGIC.startswith(prefix):
        return "TRUNCATED_OLE_SIGNATURE"
    if prefix.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "ZIP_UNSUPPORTED"
    if prefix[:2] in (b"\x09\x00", b"\x09\x02", b"\x09\x04", b"\x09\x08"):
        return "RAW_BIFF_UNSUPPORTED"
    text = prefix[:4096]
    try:
        if text.startswith((b"\xff\xfe", b"\xfe\xff")):
            head = text.decode("utf-16", errors="replace").lstrip().lower()
        else:
            head = text.decode("utf-8-sig", errors="replace").lstrip().lower()
    except UnicodeError:
        return "UNKNOWN_UNSUPPORTED"
    if head.startswith(("<!doctype html", "<html", "<table", "<head", "<body")):
        return "HTML_UNSUPPORTED"
    if head.startswith(("<?xml", "<workbook", "<ss:workbook", "<!doctype")):
        return "XML_UNSUPPORTED"
    return "UNKNOWN_UNSUPPORTED"


def _boundsheet(body: bytes, blockers: set[str]) -> tuple[str, int | None]:
    if len(body) < 8:
        blockers.add("truncated_boundsheet")
        return "malformed", None
    target, visibility, kind, chars, options = struct.unpack_from("<IBBBB", body)
    name_size = chars * (2 if options & 1 else 1)
    if visibility not in (0, 1, 2) or options & ~1 or len(body) != 8 + name_size or not chars:
        blockers.add("malformed_boundsheet")
    label = SHEET_TYPES.get(kind, "unknown")
    if label == "unknown":
        blockers.add("unclassified_sheet_type")
    if kind in (1, 6):
        blockers.add("macro_sheet_present")
    return label, target


def _formula_cache(body: bytes, blockers: set[str]) -> str:
    blockers.add("formula_tokens_and_cache_semantics_unclassified")
    if len(body) < 22 or struct.unpack_from("<H", body, 20)[0] > len(body) - 22:
        blockers.add("truncated_formula")
        return "malformed"
    cached = body[6:14]
    if cached[6:8] == b"\xff\xff":
        kind = {0: "string_requires_STRING", 1: "boolean", 2: "error", 3: "empty"}.get(cached[0])
        if kind is None:
            blockers.add("unclassified_formula_cache")
            return "unknown_special"
        return kind
    if not math.isfinite(struct.unpack("<d", cached)[0]):
        blockers.add("nonfinite_formula_cache")
        return "nonfinite_numeric"
    return "finite_numeric_not_emitted"


def _object_type(body: bytes, blockers: set[str]) -> str:
    # Inspect FtCmo's numeric type only. No embedded object or control is opened.
    blockers.add("object_payload_and_actions_unclassified")
    cursor = 0
    kind = "missing_FtCmo"
    while cursor < len(body):
        if len(body) - cursor < 4:
            blockers.add("truncated_obj_subrecord")
            return kind
        sub_id, size = struct.unpack_from("<HH", body, cursor)
        cursor += 4
        if size > len(body) - cursor:
            blockers.add("truncated_obj_subrecord")
            return kind
        if sub_id == 0x0015:
            if size != 18 or kind != "missing_FtCmo":
                blockers.add("malformed_obj_FtCmo")
            else:
                kind = f"0x{struct.unpack_from('<H', body, cursor)[0]:04X}"
        cursor += size
    return kind


def scan_biff8_records(data: bytes, *, limits: ScanLimits = ScanLimits()) -> dict[str, Any]:
    """Statically scan a caller-supplied Workbook stream, never return raw rows.

    Every framed type is counted, including unknown types. The ledger records
    counts plus first/last offsets, not a potentially million-row value dump.
    Limits, FILEPASS and framing errors explicitly mark the remainder unscanned.
    """
    if not isinstance(data, bytes):
        raise TypeError("input must be bytes")
    result = _report("BIFF8_WORKBOOK_STREAM")
    blockers: set[str] = set()
    records: dict[int, dict[str, Any]] = {}
    categories: dict[str, Counter[str]] = {
        name: Counter() for name in ("sheet_types", "bof_types", "formula_cache_types", "supbook_types", "object_types")
    }
    offset = count = 0
    open_substream = False
    bofs: dict[int, str] = {}
    bounds: list[tuple[str, int]] = []
    if len(data) > limits.max_stream_bytes:
        blockers.add("stream_byte_limit_exceeded")
    else:
        while offset < len(data):
            if count >= limits.max_records:
                blockers.add("record_count_limit_exceeded")
                break
            if len(data) - offset < 4:
                blockers.add("truncated_record_header")
                break
            record_id, size = struct.unpack_from("<HH", data, offset)
            if size > len(data) - offset - 4:
                blockers.add("truncated_record_payload")
                result["truncated_record"] = {"offset": offset, "record_id": f"0x{record_id:04X}", "declared_bytes": size}
                break
            body = data[offset + 4:offset + 4 + size]
            item = records.setdefault(record_id, {
                "record_id": f"0x{record_id:04X}", "name": RECORD_NAMES.get(record_id, "UNKNOWN"),
                "classification": "recognized_passive_opaque" if record_id in PASSIVE_RECORDS else "special" if record_id in SPECIAL_RECORDS else "unclassified",
                "count": 0, "first_offset": offset, "last_offset": offset,
            })
            item["count"] += 1
            item["last_offset"] = offset
            if count == 0 and record_id != 0x0809:
                blockers.add("missing_initial_BIFF8_BOF")
            if record_id not in RECORD_NAMES:
                blockers.add("unclassified_record_types")
            if not open_substream and record_id != 0x0809:
                blockers.add("record_outside_substream")
            if size > 8224:
                blockers.add("oversize_BIFF8_record")
            if record_id == 0x0809:
                if open_substream:
                    blockers.add("nested_BOF")
                open_substream = True
                if len(body) != 16:
                    blockers.add("malformed_BIFF8_BOF")
                if len(body) >= 4:
                    version, kind = struct.unpack_from("<HH", body)
                    label = BOF_TYPES.get(kind, "unknown")
                    categories["bof_types"][label] += 1
                    bofs[offset] = label
                    if version != 0x0600:
                        blockers.add("unsupported_BIFF_version")
                    if kind not in BOF_TYPES:
                        blockers.add("unclassified_BOF_type")
                    if kind in (6, 64):
                        blockers.add("macro_substream_present")
                    if count == 0 and kind != 5:
                        blockers.add("missing_workbook_globals")
            elif record_id == 0x000A:
                if body:
                    blockers.add("malformed_EOF")
                open_substream = False
            elif record_id == 0x0085:
                label, target = _boundsheet(body, blockers)
                categories["sheet_types"][label] += 1
                if target is not None:
                    bounds.append((label, target))
            elif record_id == 0x0006:
                categories["formula_cache_types"][_formula_cache(body, blockers)] += 1
            elif record_id == 0x005D:
                categories["object_types"][_object_type(body, blockers)] += 1
            elif record_id == 0x01AE:
                label = "malformed"
                if len(body) >= 4:
                    marker = struct.unpack_from("<H", body, 2)[0]
                    label = "internal_reference" if marker == 0x0401 and len(body) == 4 else "addin_reference" if marker == 0x3A01 and len(body) == 4 else "external_or_unknown_reference"
                categories["supbook_types"][label] += 1
                blockers.add("supbook_reference_semantics_unclassified")
            elif record_id == 0x0017:
                blockers.add("external_sheet_reference_resolution_required")
                if len(body) < 2 or len(body) != 2 + 6 * struct.unpack_from("<H", body)[0]:
                    blockers.add("malformed_EXTERNSHEET")
            elif record_id in SPECIAL_RECORDS and record_id != 0x002F:
                blockers.add(f"unclassified_active_or_context_record_{RECORD_NAMES[record_id]}")
            count += 1
            offset += 4 + size
            if record_id == 0x002F:
                blockers.add("encrypted_FILEPASS_present")
                # Subsequent bytes may be encrypted: never interpret them as BIFF.
                result["encrypted_remainder_not_scanned"] = True
                break
    if not count:
        blockers.add("no_complete_BIFF_records")
    if open_substream:
        blockers.add("missing_EOF")
    for label, target in bounds:
        if label != bofs.get(target):
            blockers.add("boundsheet_BOF_target_mismatch")
    if any(label != "workbook_globals" and pos not in {target for _, target in bounds} for pos, label in bofs.items()):
        blockers.add("unlisted_sheet_substream")
    result.update({
        "stream_bytes": len(data), "stream_sha256": hashlib.sha256(data).hexdigest(),
        "records_scanned": count, "bytes_framed": offset, "unscanned_bytes": len(data) - offset,
        "record_types": [records[key] for key in sorted(records)],
        **{key: dict(sorted(value.items())) for key, value in categories.items()},
        "scan_complete": offset == len(data) and count > 0 and not result.get("encrypted_remainder_not_scanned", False),
    })
    return _finish(result, blockers)


def _ole_entry_kind(parts: list[str]) -> str:
    folded = [part.casefold() for part in parts]
    if len(parts) == 1 and folded[0] in ("workbook", "book"):
        return "workbook"
    if any(part in ("vba", "_vba_project_cur", "_vba_project", "macros", "project", "projectwm") for part in folded):
        return "macro"
    if any(part in ("objectpool", "package", "\x01ole10native", "\x01compobj") or part.startswith("mbd") for part in folded):
        return "embedded_object"
    if len(parts) == 1 and parts[0] in ("\x05SummaryInformation", "\x05DocumentSummaryInformation"):
        return "metadata_opaque"
    return "unclassified"


def scan_xls_bytes(data: bytes, *, limits: ScanLimits = ScanLimits(), olefile_module: Any = None) -> dict[str, Any]:
    """Optional olefile read-only adapter; deliberately no filesystem access.

    olefile_module injection exists for synthetic adapter tests. Production use
    requires a separately reviewed locked/hash-pinned environment; importing an
    arbitrary installed package here is NOT sufficient provenance for R1E.
    """
    if not isinstance(data, bytes):
        raise TypeError("input must be bytes")
    container = identify_container(data[:4096])
    result = _report(container)
    result.update({"input_bytes": len(data), "input_sha256": hashlib.sha256(data).hexdigest(), "ole_entries": [], "workbook_scans": []})
    blockers: set[str] = set()
    if len(data) > limits.max_input_bytes:
        return _finish(result, {"input_byte_limit_exceeded"})
    if container != "OLE_CFB":
        return _finish(result, {"unsupported_or_incomplete_container"})
    if len(data) < 512:
        return _finish(result, {"truncated_OLE_header"})
    if olefile_module is None:
        try:
            olefile_module = importlib.import_module("olefile")
        except ImportError:
            return _finish(result, {"optional_olefile_unavailable"})
    total = workbook_count = 0
    try:
        with olefile_module.OleFileIO(io.BytesIO(data), write_mode=False, raise_defects=olefile_module.DEFECT_INCORRECT) as ole:
            entries = ole.listdir(streams=True, storages=True)
            if len(entries) > limits.max_ole_entries:
                result["ole_entry_count"] = len(entries)
                return _finish(result, {"ole_entry_limit_exceeded"})
            seen: set[tuple[str, ...]] = set()
            for parts in entries:
                if not isinstance(parts, list) or not parts or any(not isinstance(part, str) or not part or "/" in part or "\\" in part for part in parts):
                    blockers.add("malformed_ole_directory_entry")
                    continue
                folded = tuple(part.casefold() for part in parts)
                if folded in seen:
                    blockers.add("duplicate_casefold_ole_entry")
                seen.add(folded)
                kind = _ole_entry_kind(parts)
                entry_type = ole.get_type(parts)
                row: dict[str, Any] = {
                    "entry_index": len(result["ole_entries"]),
                    "path_sha256": hashlib.sha256("/".join(parts).encode("utf-8", errors="surrogatepass")).hexdigest(),
                    "classification": kind, "ole_entry_type": entry_type,
                }
                result["ole_entries"].append(row)
                if kind in ("unclassified", "macro", "embedded_object"):
                    blockers.add(f"ole_{kind}_entry")
                if entry_type not in (1, 2):
                    blockers.add("unclassified_ole_entry_type")
                if kind == "workbook" and entry_type != 2:
                    blockers.add("workbook_entry_not_stream")
                if entry_type != 2:
                    continue
                size = ole.get_size(parts)
                row["bytes"] = size
                if not isinstance(size, int) or size < 0:
                    blockers.add("invalid_ole_stream_size")
                    continue
                total += size
                if size > limits.max_stream_bytes or total > limits.max_total_stream_bytes:
                    blockers.add("ole_stream_byte_limit_exceeded")
                    continue
                if kind == "workbook":
                    workbook_count += 1
                    with ole.openstream(parts) as stream:
                        payload = stream.read(size + 1)
                    if len(payload) != size:
                        blockers.add("ole_stream_length_mismatch")
                        continue
                    scanned = scan_biff8_records(payload, limits=limits)
                    scanned["entry_index"] = row["entry_index"]
                    result["workbook_scans"].append(scanned)
                    blockers.update(scanned["blockers"])
            issues = getattr(ole, "parsing_issues", None)
            if issues is None:
                blockers.add("ole_defect_ledger_unavailable")
            elif issues:
                result["ole_parsing_issue_count"] = len(issues)
                blockers.add("ole_parser_reported_defects")
    except Exception as exc:
        # Exception messages can contain stream names or raw data: redact them.
        result["exception_type"] = type(exc).__name__
        blockers.add("ole_static_parser_error")
        return _finish(result, blockers)
    if workbook_count != 1 or len(result["workbook_scans"]) != 1:
        blockers.add("expected_exactly_one_workbook_stream")
    result["scan_complete"] = not blockers and all(scan["scan_complete"] for scan in result["workbook_scans"])
    return _finish(result, blockers)
