"""Synthetic bytes only: never open the Ren archive or extracted workbooks."""

from __future__ import annotations

import io
import json
import struct
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from experiments.audit_cap.ren_p1r1_xls_static import (
    FALSE_FLAGS, OLE_MAGIC, ScanLimits, identify_container,
    scan_biff8_records, scan_xls_bytes,
)


def rec(kind: int, body: bytes = b"") -> bytes:
    return struct.pack("<HH", kind, len(body)) + body


def bof(kind: int = 5, version: int = 0x0600) -> bytes:
    return rec(0x0809, struct.pack("<HH", version, kind) + b"\x00" * 12)


def book(*records: bytes) -> bytes:
    return bof() + b"".join(records) + rec(0x000A)


def formula(cache: bytes, tokens: bytes = b"\x1e\x01\x00") -> bytes:
    return rec(0x0006, b"\x00" * 6 + cache + b"\x00" * 6 + struct.pack("<H", len(tokens)) + tokens)


def assert_no_authority(report: dict) -> None:
    assert all(report[key] is False for key in FALSE_FLAGS)
    assert report["preparation_only"] is True
    assert report["status"] != "PASS"


@pytest.mark.parametrize(("data", "expected"), [
    (b"", "EMPTY"), (OLE_MAGIC, "OLE_CFB"), (OLE_MAGIC[:5], "TRUNCATED_OLE_SIGNATURE"),
    (b"PK\x03\x04not-a-real-zip", "ZIP_UNSUPPORTED"),
    (b"PK\x05\x06", "ZIP_UNSUPPORTED"),
    (b"<?xml version='1.0'?><Workbook/>", "XML_UNSUPPORTED"),
    ("\ufeff<Workbook/>".encode("utf-16-le"), "XML_UNSUPPORTED"),
    (b" \xef\xbb\xbf<html/>", "UNKNOWN_UNSUPPORTED"),
    (b"\xef\xbb\xbf <HTML><script>ignored()</script></HTML>", "HTML_UNSUPPORTED"),
    (b"<!DOCTYPE HTML><html/>", "HTML_UNSUPPORTED"),
    (bof(), "RAW_BIFF_UNSUPPORTED"), (b"random binary\xff", "UNKNOWN_UNSUPPORTED"),
])
def test_container_identification_does_not_convert(data, expected) -> None:
    assert identify_container(data) == expected
    report = scan_xls_bytes(data)
    assert report["status"] == "BLOCKED_ROW_PARSE"
    assert_no_authority(report)


def test_complete_synthetic_static_scan_is_not_a_row_gate() -> None:
    report = scan_biff8_records(book(rec(0x0042, b"\xb0\x04")))
    assert report["scan_complete"]
    assert report["records_scanned"] == 3
    assert report["status"] == "STATIC_SCAN_COMPLETE_REVIEW_REQUIRED"
    assert_no_authority(report)


@pytest.mark.parametrize("data", [b"\x09", bof()[:-1], bof(), book() + b"\x00", rec(0x000A), rec(0x0809, b"\x00"), bof() + bof() + rec(0x000A)])
def test_truncation_and_framing_fail_closed(data) -> None:
    report = scan_biff8_records(data)
    assert report["status"] == "BLOCKED_ROW_PARSE"
    assert report["blockers"]


def test_unknown_types_are_counted_completely_without_raw_payloads() -> None:
    report = scan_biff8_records(book(rec(0xFFFF, b"PRIVATE_CELL"), rec(0xFEFE), rec(0xFFFF, b"SECRET")))
    unknown = {row["record_id"]: row for row in report["record_types"] if row["classification"] == "unclassified"}
    assert {key: row["count"] for key, row in unknown.items()} == {"0xFEFE": 1, "0xFFFF": 2}
    assert report["scan_complete"]
    assert "unclassified_record_types" in report["blockers"]
    assert "PRIVATE_CELL" not in json.dumps(report)
    assert "SECRET" not in json.dumps(report)
    assert sum(row["count"] for row in report["record_types"]) == report["records_scanned"]


def test_filepass_stops_before_encrypted_remainder() -> None:
    data = bof() + rec(0x002F, b"\x01\x00") + b"ENCRYPTED_SECRET_NOT_A_RECORD"
    report = scan_biff8_records(data)
    assert "encrypted_FILEPASS_present" in report["blockers"]
    assert not report["scan_complete"]
    assert report["records_scanned"] == 2
    assert report["unscanned_bytes"] == len(b"ENCRYPTED_SECRET_NOT_A_RECORD")
    assert "ENCRYPTED_SECRET" not in json.dumps(report)


@pytest.mark.parametrize(("kind", "bof_kind", "blocked"), [(0, 16, False), (1, 64, True), (2, 32, False), (6, 6, True), (3, 17, True)])
def test_boundsheet_type_and_bof_target(kind, bof_kind, blocked) -> None:
    # 20-byte globals BOF + 13-byte BOUNDSHEET + 4-byte EOF.
    sheet = rec(0x0085, struct.pack("<IBBBB", 37, 0, kind, 1, 0) + b"S")
    report = scan_biff8_records(book(sheet) + bof(bof_kind) + rec(0x000A))
    assert (report["status"] == "BLOCKED_ROW_PARSE") is blocked
    assert "S" not in report["sheet_types"]


@pytest.mark.parametrize("body", [b"\x00", struct.pack("<IBBBB", 999, 0, 0, 1, 0) + b"S", struct.pack("<IBBBB", 0, 7, 0, 20, 0) + b"S"])
def test_malformed_or_misdirected_boundsheet_blocked(body) -> None:
    assert scan_biff8_records(book(rec(0x0085, body)))["status"] == "BLOCKED_ROW_PARSE"


@pytest.mark.parametrize(("cache", "category"), [
    (struct.pack("<d", 987654.25), "finite_numeric_not_emitted"),
    (struct.pack("<d", float("nan")), "nonfinite_numeric"),
    (struct.pack("<d", float("inf")), "nonfinite_numeric"),
    (b"\x00\x00\x00\x00\x00\x00\xff\xff", "string_requires_STRING"),
    (b"\x01\x00\x01\x00\x00\x00\xff\xff", "boolean"),
    (b"\x02\x00\x07\x00\x00\x00\xff\xff", "error"),
    (b"\x03\x00\x00\x00\x00\x00\xff\xff", "empty"),
    (b"\x04\x00\x00\x00\x00\x00\xff\xff", "unknown_special"),
])
def test_formula_cache_types_never_evaluated_or_emitted(cache, category) -> None:
    report = scan_biff8_records(book(formula(cache)))
    assert report["formula_cache_types"] == {category: 1}
    assert report["status"] == "BLOCKED_ROW_PARSE"
    assert "987654.25" not in json.dumps(report)
    assert_no_authority(report)


def test_truncated_formula_and_obj_subrecord_block() -> None:
    report = scan_biff8_records(book(rec(0x0006, b"\x00" * 21), rec(0x005D, b"\x15\x00\x12\x00\x08")))
    assert "truncated_formula" in report["blockers"]
    assert "truncated_obj_subrecord" in report["blockers"]


def test_objects_and_external_references_are_static_only() -> None:
    report = scan_biff8_records(book(
        rec(0x005D, struct.pack("<HHH", 0x15, 18, 8) + b"\x00" * 16),
        rec(0x01AE, b"\x01\x00\x01\x04"),
        rec(0x0017, b"\x01\x00" + b"\x00" * 6),
        rec(0x0018, b"AUTO_OPEN_PRIVATE"), rec(0x003C, b"PRIVATE_CONTINUATION"),
    ))
    assert report["object_types"] == {"0x0008": 1}
    assert report["supbook_types"] == {"internal_reference": 1}
    assert "external_sheet_reference_resolution_required" in report["blockers"]
    assert report["status"] == "BLOCKED_ROW_PARSE"
    assert "PRIVATE" not in json.dumps(report)


def test_limits_and_unsupported_biff_version_fail_closed() -> None:
    assert "unsupported_BIFF_version" in scan_biff8_records(bof(version=0x0500) + rec(0x000A))["blockers"]
    capped = scan_biff8_records(book(), limits=ScanLimits(max_records=1))
    assert "record_count_limit_exceeded" in capped["blockers"]
    assert capped["unscanned_bytes"] == 4
    assert "stream_byte_limit_exceeded" in scan_biff8_records(book(), limits=ScanLimits(max_stream_bytes=1))["blockers"]
    assert "input_byte_limit_exceeded" in scan_xls_bytes(b"AB", limits=ScanLimits(max_input_bytes=1))["blockers"]
    with pytest.raises(ValueError):
        ScanLimits(max_records=0)


class FakeOle:
    def __init__(self, streams=None, storages=(), issues=(), failure=None):
        self.streams = {("Workbook",): book()} if streams is None else streams
        self.storages = list(storages)
        self.parsing_issues = list(issues)
        self.failure = failure
        self.opened = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def listdir(self, *, streams, storages):
        assert streams is True and storages is True
        if self.failure:
            raise ValueError(self.failure)
        return [list(key) for key in self.streams] + [list(key) for key in self.storages]

    def get_type(self, parts):
        return 2 if tuple(parts) in self.streams else 1

    def get_size(self, parts):
        return len(self.streams[tuple(parts)])

    def openstream(self, parts):
        self.opened.append(tuple(parts))
        return io.BytesIO(self.streams[tuple(parts)])


def adapter(fake):
    def open_ole(source, *, write_mode, raise_defects):
        assert isinstance(source, io.BytesIO)
        assert write_mode is False
        assert raise_defects == 30
        return fake
    return SimpleNamespace(OleFileIO=open_ole, DEFECT_INCORRECT=30)


OLE_FIXTURE = OLE_MAGIC + b"\x00" * (512 - len(OLE_MAGIC))


def test_optional_reader_unavailable_is_not_an_install_attempt() -> None:
    with patch("experiments.audit_cap.ren_p1r1_xls_static.importlib.import_module", side_effect=ImportError):
        report = scan_xls_bytes(OLE_FIXTURE)
    assert report["blockers"] == ["optional_olefile_unavailable"]
    assert_no_authority(report)


def test_synthetic_ole_adapter_read_only_and_no_authority() -> None:
    fake = FakeOle()
    report = scan_xls_bytes(OLE_FIXTURE, olefile_module=adapter(fake))
    assert fake.closed
    assert fake.opened == [("Workbook",)]
    assert report["scan_complete"]
    assert report["status"] == "STATIC_SCAN_COMPLETE_REVIEW_REQUIRED"
    assert_no_authority(report)
    assert_no_authority(report["workbook_scans"][0])


def test_ole_active_unknown_streams_and_storages_reported_without_opening() -> None:
    fake = FakeOle(streams={
        ("Workbook",): book(), ("VBA", "Module1"): b"NEVER_EXECUTE_SECRET",
        ("ObjectPool", "PRIVATE"): b"EMBEDDED_SECRET", ("PRIVATE_URL",): b"SECRET",
        ("\x05SummaryInformation",): b"PRIVATE_AUTHOR",
    }, storages=[("VBA",), ("ObjectPool",), ("UNKNOWN_PRIVATE",)])
    report = scan_xls_bytes(OLE_FIXTURE, olefile_module=adapter(fake))
    assert len(report["ole_entries"]) == 8
    assert fake.opened == [("Workbook",)]
    assert {"ole_macro_entry", "ole_embedded_object_entry", "ole_unclassified_entry"} <= set(report["blockers"])
    assert "PRIVATE" not in json.dumps(report)
    assert "SECRET" not in json.dumps(report)


@pytest.mark.parametrize("fake", [
    FakeOle(streams={}), FakeOle(streams={("Workbook",): book(), ("Book",): book()}),
    FakeOle(issues=[("defect", "PRIVATE")]), FakeOle(failure="SECRET_EXCEPTION_PAYLOAD"),
    FakeOle(streams={("workbook",): book(), ("Workbook",): book()}),
    FakeOle(streams={}, storages=[("Workbook",)]),
])
def test_ole_missing_duplicate_defective_or_malformed_is_blocked(fake) -> None:
    report = scan_xls_bytes(OLE_FIXTURE, olefile_module=adapter(fake))
    assert report["status"] == "BLOCKED_ROW_PARSE"
    assert "PRIVATE" not in json.dumps(report)
    assert "SECRET" not in json.dumps(report)
    assert fake.closed


def test_ole_limits_and_stream_truncation_are_explicit() -> None:
    fake = FakeOle()
    report = scan_xls_bytes(OLE_FIXTURE, olefile_module=adapter(fake), limits=ScanLimits(max_stream_bytes=1))
    assert "ole_stream_byte_limit_exceeded" in report["blockers"]
    assert fake.opened == []
    fake = FakeOle()
    fake.get_size = lambda parts: 100
    report = scan_xls_bytes(OLE_FIXTURE, olefile_module=adapter(fake))
    assert "ole_stream_length_mismatch" in report["blockers"]
    assert_no_authority(report)
