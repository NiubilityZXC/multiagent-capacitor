import struct
from types import SimpleNamespace
import io

import pytest

from experiments.audit_cap.ren_workbook_reader import workbook_bytes, guard_biff, schema_rows


def rec(kind, body=b""):
    return struct.pack("<HH", kind, len(body)) + body


def bof(kind=5):
    return rec(0x0809, struct.pack("<HH", 0x0600, kind) + b"\0" * 12)


def synthetic_workbook():
    globals_head = bof() + rec(0x0042, struct.pack("<H", 1200)) + rec(0x0022, b"\0\0")
    # BoundSheet with one compressed one-character sheet name.
    offset = len(globals_head) + 13 + 4
    bound = rec(0x0085, struct.pack("<IBBBB", offset, 0, 0, 1, 0) + b"S")
    label = rec(0x0204, struct.pack("<HHHHB", 0, 0, 0, 4, 0) + b"Time")
    value = rec(0x0203, struct.pack("<HHHd", 1, 0, 0, 42.0))
    dim = rec(0x0200, struct.pack("<IIHHH", 0, 2, 0, 1, 0))
    return globals_head + bound + rec(0x000A) + bof(16) + dim + label + value + rec(0x000A)


ALLOWED = {0x0809, 0x0042, 0x0022, 0x0085, 0x0204, 0x0203, 0x0200, 0x000A, 0x004D, 0x003C, 0x00A1}


def test_real_xlrd_reads_synthetic_raw_workbook_without_container():
    pytest.importorskip("xlrd", reason="real reader integration runs in the isolated audit environment")
    report = schema_rows(synthetic_workbook(), ALLOWED)
    assert report["sheets"][0]["nrows"] == 2
    assert report["sheets"][0]["first_eight_rows_text_only"] == [{"row": 0, "col": 0, "text": "Time", "truncated": False}]
    assert report["sheets"][0]["cell_type_counts"] == {"1": 1, "2": 1}
    assert report["p2_eligible"] is False and report["numeric_target_emitted"] is False


@pytest.mark.parametrize("record", [0x0006, 0x0017, 0x0018, 0x0023, 0x002F, 0x005D, 0x01AE, 0x01B8, 0x0221, 0x0236, 0x04BC, 0xFFFF])
def test_active_or_unknown_record_stops_before_xlrd(record):
    stub = SimpleNamespace(open_workbook=lambda **k: pytest.fail("must not parse"))
    with pytest.raises(ValueError):
        schema_rows(bof() + rec(record) + rec(0x000A), ALLOWED | ({record} if record != 0xFFFF else set()), stub)


@pytest.mark.parametrize("kind", [6, 32, 64])
def test_nonworksheet_bof_blocked(kind):
    with pytest.raises(ValueError): guard_biff(bof(kind) + rec(0x000A), ALLOWED)


@pytest.mark.parametrize("data", [b"", b"x", bof(), bof() + rec(0x000A) + b"x", rec(0x000A), bof() + bof()])
def test_incomplete_framing_blocked(data):
    with pytest.raises(ValueError): guard_biff(data, ALLOWED)


def test_pls_continue_only():
    guard_biff(bof() + rec(0x004D) + rec(0x003C) + rec(0x00A1) + rec(0x000A), ALLOWED)
    with pytest.raises(ValueError): guard_biff(bof() + rec(0x003C) + rec(0x000A), ALLOWED)


def test_ole_adapter_opens_only_root_workbook():
    payload = synthetic_workbook()
    class Ole:
        parsing_issues = []
        def __init__(self, *a, **k): assert k["write_mode"] is False
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def listdir(self, **k): return [["Workbook"], ["_VBA_PROJECT_CUR", "VBA", "AutoOpen"]]
        def get_type(self, p): return 2
        def get_size(self, p): return len(payload)
        def openstream(self, p):
            assert p == ["Workbook"]
            return io.BytesIO(payload)
    assert workbook_bytes(b"synthetic container", SimpleNamespace(OleFileIO=Ole, DEFECT_INCORRECT=30)) == payload
