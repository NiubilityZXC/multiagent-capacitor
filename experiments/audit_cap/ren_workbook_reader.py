"""R1E candidate: isolated Workbook bytes, no OLE/VBA given to xlrd.

No CLI: a reviewed caller must establish source, static policy and release
authority before using these helpers. Schema evidence alone is not Data Gate.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import math
import struct


def workbook_bytes(container: bytes, olefile_module=None) -> bytes:
    if len(container) > 256 * 1024 * 1024:
        raise ValueError("container limit")
    if olefile_module is None:
        import olefile as olefile_module
    with olefile_module.OleFileIO(io.BytesIO(container), write_mode=False,
                                 raise_defects=olefile_module.DEFECT_INCORRECT) as ole:
        names = ole.listdir(streams=True, storages=True)
        roots = [p for p in names if len(p) == 1 and p[0].casefold() in ("workbook", "book")]
        if len(roots) != 1 or ole.get_type(roots[0]) != 2:
            raise ValueError("expected one Workbook stream")
        size = ole.get_size(roots[0])
        if not 0 < size <= 256 * 1024 * 1024:
            raise ValueError("stream limit")
        with ole.openstream(roots[0]) as stream:
            data = stream.read(size + 1)
        if len(data) != size or getattr(ole, "parsing_issues", None) != []:
            raise ValueError("OLE length or defect mismatch")
        return data


def guard_biff(data: bytes, allowed_ids: set[int]) -> None:
    """Fresh byte-level guard independent of cached summaries; never execute."""
    forbidden = {0x0006, 0x0017, 0x0018, 0x0023, 0x002F, 0x005D, 0x01AE,
                 0x01B8, 0x0221, 0x0236, 0x04BC}
    cursor = 0
    opened = False
    previous = None
    continue_base = None
    if not data or len(data) > 256 * 1024 * 1024:
        raise ValueError("empty or oversized Workbook")
    while cursor < len(data):
        if len(data) - cursor < 4:
            raise ValueError("truncated header")
        kind, size = struct.unpack_from("<HH", data, cursor)
        end = cursor + 4 + size
        if size > 8224 or end > len(data):
            raise ValueError("invalid framing")
        if kind not in allowed_ids or kind in forbidden:
            raise ValueError("unapproved or active BIFF record")
        if previous == 0x003C and kind != 0x003C and kind != 0x00A1:
            raise ValueError("CONTINUE is not followed by SETUP")
        if kind == 0x003C:
            if previous != 0x003C:
                continue_base = previous
            if continue_base != 0x004D:
                raise ValueError("only PLS CONTINUE is permitted")
        if kind == 0x0809:
            if opened or size != 16:
                raise ValueError("invalid BOF")
            version, substream = struct.unpack_from("<HH", data, cursor + 4)
            if version != 0x0600 or substream not in (5, 16) or (cursor == 0 and substream != 5):
                raise ValueError("only BIFF8 globals and worksheets")
            opened = True
        elif not opened:
            raise ValueError("record outside substream")
        elif kind == 0x000A:
            if size:
                raise ValueError("invalid EOF")
            opened = False
        previous = kind
        cursor = end
    if opened or previous != 0x000A:
        raise ValueError("incomplete Workbook")


def schema_rows(data: bytes, allowed_ids: set[int], xlrd_module=None) -> dict:
    guard_biff(data, allowed_ids)
    if xlrd_module is None:
        import xlrd as xlrd_module
    # No filename, OLE container, VBA streams, formatting, corruption bypass,
    # formula evaluation, external-link resolution or network operation.
    warnings = io.StringIO()
    book = xlrd_module.open_workbook(file_contents=data, logfile=warnings,
        verbosity=0, use_mmap=False, formatting_info=False, on_demand=True,
        ragged_rows=True, ignore_workbook_corruption=False)
    sheets = []
    try:
        if book.nsheets > 256:
            raise ValueError("sheet limit")
        for index in range(book.nsheets):
            sheet = book.sheet_by_index(index)
            if sheet.nrows > 65536 or sheet.ncols > 256:
                raise ValueError("BIFF8 dimensions exceeded")
            types = Counter()
            nonfinite = 0
            text_preview = []
            for row in range(sheet.nrows):
                for col, cell in enumerate(sheet.row(row)):
                    types[str(cell.ctype)] += 1
                    if cell.ctype in (2, 3) and not math.isfinite(cell.value):
                        nonfinite += 1
                    # Local-only schema hints, not an inferred header or unit.
                    if row < 8 and cell.ctype == 1:
                        text_preview.append({"row": row, "col": col, "text": cell.value[:256],
                                             "truncated": len(cell.value) > 256})
            sheets.append({"index": index, "name": sheet.name, "nrows": sheet.nrows,
                           "ncols": sheet.ncols, "cell_type_counts": dict(types),
                           "nonfinite_count": nonfinite, "first_eight_rows_text_only": text_preview})
            book.unload_sheet(index)
        if warnings.getvalue():
            raise ValueError("reader emitted warnings; inspect locally before continuing")
    finally:
        book.release_resources()
    return {"status": "SCHEMA_ROWS_AUDITED_NOT_DATA_GATE", "workbook_sha256": hashlib.sha256(data).hexdigest(),
            "sheets": sheets, "row_parse_executed": True, "numeric_target_emitted": False,
            "model_or_api_executed": False, "formulas_evaluated": False,
            "identity_verified": False, "target_verified": False, "p2_eligible": False}
