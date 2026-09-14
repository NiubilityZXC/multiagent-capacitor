"""Guarded Workbook-only measurement iterator; no standalone execution authority.

A reviewed caller must validate source/release and consume the iterator fully
before accepting completion. Values remain local audit material, not targets.
"""
import hashlib
import io
import math
import re
import struct

if __package__:
    from experiments.audit_cap import ren_chronology as chronology
    from experiments.audit_cap import ren_overlap as overlap
else:
    import ren_chronology as chronology
    import ren_overlap as overlap


def records(data, allowed, schema, xlrd_module=None):
    """Yield (sheet_index, sheet_name, one_based_XLS_row, token, energy).

    The first data row is XLS row 2; sheet indices are zero-based. Energy is
    None for the eight-column layout and a finite float otherwise. No rounding.
    Independent row/cell accessors must agree before a row can be emitted.
    """
    chronology.guard_biff(data, allowed)
    if hashlib.sha256(data).hexdigest() != schema["workbook_sha256"]:
        raise ValueError("measurement stream mismatch")
    if xlrd_module is None:
        import xlrd as xlrd_module
    warnings = io.StringIO()
    book = xlrd_module.open_workbook(file_contents=data, logfile=warnings,
        verbosity=0, use_mmap=False, formatting_info=False, on_demand=True,
        ragged_rows=True, ignore_workbook_corruption=False)
    rows = 0
    try:
        if book.nsheets != len(schema["sheets"]):
            raise ValueError("measurement sheet count mismatch")
        for index, expected in enumerate(schema["sheets"]):
            if expected["index"] != index:
                raise ValueError("measurement schema index mismatch")
            sheet = book.sheet_by_index(index)
            try:
                if (sheet.name != expected["name"] or sheet.nrows != expected["nrows"]
                        or sheet.ncols != expected["ncols"]):
                    raise ValueError("measurement dimensions mismatch")
                if sheet.name in ("step", "cycle"):
                    continue
                if re.fullmatch(r"record_[1-9][0-9]*", sheet.name) is None:
                    raise ValueError("unrecognized measurement sheet")
                if not 2 <= sheet.nrows <= 65536:
                    raise ValueError("measurement dimensions mismatch")
                header = tuple(sheet.row_values(0))
                if header not in (chronology.HEADER, chronology.HEADER+("energy(mWh)",)):
                    raise ValueError("measurement header mismatch")
                if tuple(sheet.row_types(0)) != (1,)*len(header):
                    raise ValueError("measurement header types")
                for row in range(1, sheet.nrows):
                    key = chronology.key_from_cells(sheet, row)
                    rebuilt_key = chronology.reference_key(sheet, row)
                    if key is None or key != rebuilt_key:
                        raise ValueError("measurement metadata mismatch")
                    kinds, values = sheet.row_types(row), sheet.row_values(row)
                    if len(values) != len(header) or tuple(kinds[5:]) != (2,)*(len(header)-5):
                        raise ValueError("measurement numeric cell types")
                    measured = values[5:]
                    if any(type(v) not in (int, float) or not math.isfinite(v) for v in measured):
                        raise ValueError("measurement nonfinite or invalid value")
                    # Distinct cell-access and struct-packing paths, no reuse of
                    # measurement_token in the independent reconstruction.
                    cells = [sheet.cell(row, col) for col in range(5, len(header))]
                    if any(cell.ctype != 2 or cell.value != value for cell, value in zip(cells, measured)):
                        raise ValueError("measurement cell reconstruction mismatch")
                    token = overlap.measurement_token(key, values)
                    rebuilt = struct.pack(">qqddd", rebuilt_key[2], rebuilt_key[4],
                        *(0.0 if cell.value == 0 else cell.value for cell in cells[:3]))
                    if token != rebuilt:
                        raise ValueError("measurement token reconstruction mismatch")
                    if warnings.getvalue():
                        raise ValueError("measurement parser warning")
                    rows += 1
                    yield index, sheet.name, row+1, token, (float(measured[3]) if len(header)==9 else None)
            finally:
                book.unload_sheet(index)
        if rows == 0 or warnings.getvalue():
            raise ValueError("measurement empty or warning")
    finally:
        book.release_resources()
