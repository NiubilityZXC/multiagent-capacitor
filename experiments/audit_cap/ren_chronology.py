"""Read-only record-key chronology with independent reductions; no target values."""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import math
import re

if __package__:
    from experiments.audit_cap.ren_workbook_reader import guard_biff
    from experiments.audit_cap.verify_ren_fleet_schema import verify_fields
else:
    from ren_workbook_reader import guard_biff
    from verify_ren_fleet_schema import verify_fields

HEADER = ("cycle", "step", "status", "record_number", "record_time(h:min:s.ms)",
          "voltage(V)", "current(mA)", "capacity(mAh)")
CLOCK = re.compile(r"([0-9]+):([0-5][0-9]):([0-5][0-9])(?:\.([0-9]{1,6}))?\Z")
TRANSITIONS = ("valid_adjacent_pairs", "record_nonunit", "record_repeats", "record_backwards",
    "record_forward_gaps", "missing_record_numbers", "cycle_backwards", "step_changes",
    "time_decreases", "same_step_time_decreases", "adjacent_duplicate_keys")


def clock_us(value):
    if not isinstance(value, str):
        return None
    m = CLOCK.fullmatch(value)
    if m is None:
        return None
    h, minute, second, fraction = m.groups()
    return (int(h)*3600 + int(minute)*60 + int(second))*1000000 + int((fraction or "").ljust(6, "0"))


def key_from_cells(sheet, row):
    cells = [sheet.cell(row, col) for col in range(5)]
    numbers = []
    for cell in cells[:4]:
        v = cell.value
        if cell.ctype != 2 or type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 2**53 or v != int(v):
            return None
        numbers.append(int(v))
    microseconds = clock_us(cells[4].value) if cells[4].ctype == 1 else None
    return None if microseconds is None else tuple(numbers + [microseconds])


def reference_key(sheet, row):
    kinds, values = sheet.row_types(row), sheet.row_values(row)
    if len(values) < 5 or tuple(kinds[:5]) != (2, 2, 2, 2, 1):
        return None
    for n in values[:4]:
        if type(n) not in (int, float) or not math.isfinite(n) or abs(n) > 9007199254740992 or int(n) != n:
            return None
    if not isinstance(values[4], str) or CLOCK.fullmatch(values[4]) is None:
        return None
    # Reconstruct time independently, not by calling clock_us.
    hour, minute, last = values[4].split(":")
    second, dot, fraction = last.partition(".")
    clock = int(hour)*3600000000 + int(minute)*60000000 + int(second)*1000000
    clock += int(fraction or 0) * (10 ** (6-len(fraction))) if dot else 0
    return tuple(int(v) for v in values[:4]) + (clock,)


def edge(left, right):
    result = dict.fromkeys(TRANSITIONS, 0)
    if left is None or right is None:
        return result
    delta = right[3] - left[3]
    changed = left[:3] != right[:3]
    result.update(valid_adjacent_pairs=1, record_nonunit=int(delta != 1),
        record_repeats=int(delta == 0), record_backwards=int(delta < 0),
        record_forward_gaps=int(delta > 1), missing_record_numbers=max(0, delta-1),
        cycle_backwards=int(right[0] < left[0]), step_changes=int(changed),
        time_decreases=int(right[4] < left[4]),
        same_step_time_decreases=int(not changed and right[4] < left[4]),
        adjacent_duplicate_keys=int(left == right))
    return result


def reduce_keys(keys):
    counts = dict.fromkeys(TRANSITIONS, 0)
    previous = first = last = None
    rows = invalid = negative = 0
    statuses = Counter()
    for key in keys:
        if rows == 0:
            first = key
        rows += 1
        last = key
        if key is None:
            invalid += 1
        else:
            negative += int(any(key[c] < 0 for c in (0, 1, 3)))
            statuses[str(key[2])] += 1
        if rows > 1:
            for name, n in edge(previous, key).items():
                counts[name] += n
        previous = key
    return dict(rows=rows, invalid_key_rows=invalid, negative_identifier_rows=negative,
        first_key=None if first is None else list(first), last_key=None if last is None else list(last),
        status_counts=dict(statuses), **counts)


def reference_reduce(keys):
    values = list(keys)
    pairs = [(a, b) for a, b in zip(values, values[1:]) if a is not None and b is not None]
    delta = [b[3]-a[3] for a, b in pairs]
    statuses = {}
    for value in values:
        if value is not None:
            s = str(value[2])
            statuses[s] = statuses.get(s, 0) + 1
    return dict(rows=len(values), invalid_key_rows=values.count(None),
        negative_identifier_rows=sum(v is not None and (v[0]<0 or v[1]<0 or v[3]<0) for v in values),
        first_key=list(values[0]) if values and values[0] is not None else None,
        last_key=list(values[-1]) if values and values[-1] is not None else None,
        status_counts=statuses, valid_adjacent_pairs=len(pairs),
        record_nonunit=sum(d!=1 for d in delta), record_repeats=delta.count(0),
        record_backwards=sum(d<0 for d in delta), record_forward_gaps=sum(d>1 for d in delta),
        missing_record_numbers=sum(d-1 for d in delta if d>1),
        cycle_backwards=sum(b[0]<a[0] for a,b in pairs),
        step_changes=sum(a[:3]!=b[:3] for a,b in pairs),
        time_decreases=sum(b[4]<a[4] for a,b in pairs),
        same_step_time_decreases=sum(a[:3]==b[:3] and b[4]<a[4] for a,b in pairs),
        adjacent_duplicate_keys=sum(a==b for a,b in pairs))


def workbook(data: bytes, allowed: set[int], schema: dict, xlrd_module=None):
    guard_biff(data, allowed)
    if hashlib.sha256(data).hexdigest() != schema["workbook_sha256"]:
        raise ValueError("chronology schema stream mismatch")
    if xlrd_module is None:
        import xlrd as xlrd_module
    log = io.StringIO()
    book = xlrd_module.open_workbook(file_contents=data, logfile=log, verbosity=0,
        use_mmap=False, formatting_info=False, on_demand=True, ragged_rows=True,
        ignore_workbook_corruption=False)
    results = []
    try:
        if book.nsheets != len(schema["sheets"]):
            raise ValueError("chronology sheet count mismatch")
        for index, expected in enumerate(schema["sheets"]):
            if expected["name"] in ("step", "cycle"):
                continue
            if re.fullmatch(r"record_[1-9][0-9]*", expected["name"]) is None:
                raise ValueError("unrecognized record sheet")
            sheet = book.sheet_by_index(index)
            if (sheet.name != expected["name"] or sheet.nrows != expected["nrows"]
                    or sheet.ncols != expected["ncols"] or not 2 <= sheet.nrows <= 65536):
                raise ValueError("chronology dimensions mismatch")
            header = tuple(sheet.row_values(0))
            if header not in (HEADER, HEADER + ("energy(mWh)",)):
                raise ValueError("unrecognized record units/header")
            if tuple(sheet.row_types(0)) != (1,)*len(header):
                raise ValueError("record header type mismatch")
            generated = reduce_keys(key_from_cells(sheet, row) for row in range(1, sheet.nrows))
            rebuilt = reference_reduce(reference_key(sheet, row) for row in range(1, sheet.nrows))
            verify_fields(generated, rebuilt)
            results.append(dict(index=index, name=sheet.name, **generated))
            book.unload_sheet(index)
        if log.getvalue() or not results:
            raise ValueError("chronology warnings or missing records")
    finally:
        book.release_resources()
    return results


def aggregate(sheets):
    if not sheets:
        raise ValueError("empty chronology group")
    counters = (*TRANSITIONS, "rows", "invalid_key_rows", "negative_identifier_rows")
    counts = {k: sum(s[k] for s in sheets) for k in counters}
    boundaries = []
    for previous, current in zip(sheets, sheets[1:]):
        boundary = edge(previous["last_key"], current["first_key"])
        independent = reference_reduce([previous["last_key"], current["first_key"]])
        verify_fields(boundary, {k: independent[k] for k in TRANSITIONS})
        boundaries.append(boundary)
        for k in TRANSITIONS:
            counts[k] += boundary[k]
    counts["sheet_boundaries"] = len(boundaries)
    counts["nonunit_record_boundaries"] = sum(b["record_nonunit"] for b in boundaries)
    counts["invalid_key_boundaries"] = sum(b["valid_adjacent_pairs"] == 0 for b in boundaries)
    return counts
