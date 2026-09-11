"""Independent field reconstruction for R1E schema, not an alternate XLS parser.

Shares locked xlrd and the reviewed byte boundary, but never calls schema_rows
or trusts generator statistics. No command-line or standalone read authority.
"""
from __future__ import annotations

import hashlib
import io
import math

if __package__:
    from experiments.audit_cap.ren_workbook_reader import guard_biff
else:
    from ren_workbook_reader import guard_biff


def rebuild(data: bytes, allowed: set[int], xlrd_module=None) -> dict:
    guard_biff(data, allowed)
    if xlrd_module is None:
        import xlrd as xlrd_module
    log = io.StringIO()
    book = xlrd_module.open_workbook(file_contents=data, logfile=log, verbosity=0,
        use_mmap=False, formatting_info=False, on_demand=True, ragged_rows=True,
        ignore_workbook_corruption=False)
    result = []
    try:
        if book.nsheets > 256:
            raise ValueError("verifier sheet bound")
        for number in range(book.nsheets):
            sheet = book.sheet_by_index(number)
            if sheet.nrows > 65536 or sheet.ncols > 256:
                raise ValueError("verifier dimensions")
            totals = {}
            invalid = 0
            hints = []
            # Different cell access/reduction from the generator's Cell loop.
            for row in range(sheet.nrows):
                kinds = sheet.row_types(row)
                values = sheet.row_values(row)
                if len(kinds) != len(values):
                    raise ValueError("verifier row length mismatch")
                for col in range(len(kinds)):
                    kind = int(kinds[col])
                    value = values[col]
                    key = str(kind)
                    totals[key] = totals.get(key, 0) + 1
                    invalid += int(kind in (2, 3) and not math.isfinite(value))
                    if row <= 7 and kind == 1:
                        hints.append(dict(row=row, col=col, text=value[0:256],
                                          truncated=len(value) > 256))
            result.append(dict(index=number, name=sheet.name, nrows=sheet.nrows,
                ncols=sheet.ncols, cell_type_counts=totals, nonfinite_count=invalid,
                first_eight_rows_text_only=hints))
            book.unload_sheet(number)
        if log.getvalue():
            raise ValueError("verifier reader warning")
    finally:
        book.release_resources()
    return dict(status="SCHEMA_ROWS_AUDITED_NOT_DATA_GATE",
        workbook_sha256=hashlib.sha256(data).hexdigest(), sheets=result,
        row_parse_executed=True, numeric_target_emitted=False,
        model_or_api_executed=False, formulas_evaluated=False,
        identity_verified=False, target_verified=False, p2_eligible=False)


def verify_fields(observed: dict, rebuilt: dict) -> None:
    # Canonical JSON additionally rejects type substitutions (False versus 0)
    # and unexpected keys that ordinary Python dict equality may miss.
    import json
    def canonical(value):
        return json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=True)
    if canonical(observed) != canonical(rebuilt):
        raise ValueError("independently rebuilt schema mismatch")
