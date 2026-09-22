"""Workbook-only canonical audit events. No file access, targets, or release.

A reviewed caller must supply source-bound schema and approved BIFF IDs, retain
source identity with positions, and exhaust every iterator before accepting
coverage. Step/cycle values keep native units; mAh is never relabeled as F.
"""
import hashlib
import io
import math
import re

from experiments.audit_cap import ren_chronology as chronology


STEP = ('cycle', 'step', 'status', 'record_time(h:min:s.ms)',
        'capacity(mAh)', 'energy(mWh)')
STEP_VOLTAGE = STEP + ('ini_voltage(V)', 'end_voltage(V)')
CYCLE = ('cycle', 'charge_capacity(mAh)', 'discharge_capacity(mAh)')
CYCLE_ENERGY = CYCLE + ('charge_energy(mWh)', 'discharge_energy(mWh)')


def _integer(value, kind, nonnegative=True):
    if (kind != 2 or type(value) not in (int, float) or not math.isfinite(value)
            or abs(value) > 2**53 or value != int(value)
            or (nonnegative and value < 0)):
        raise ValueError('invalid target-audit integer')
    return int(value)


def _numbers(values, kinds):
    if len(values) != len(kinds) or any(
            kind != 2 or type(v) not in (int, float) or not math.isfinite(v)
            for v, kind in zip(values, kinds)):
        raise ValueError('invalid target-audit measurement')
    return list(values)


def _summary_values(sheet, row, kind):
    values, kinds = sheet.row_values(row), sheet.row_types(row)
    if kind == 'step':
        result = [_integer(values[i], kinds[i], i != 2) for i in range(3)]
        time_us = chronology.clock_us(values[3]) if kinds[3] == 1 else None
        if time_us is None:
            raise ValueError('invalid summary clock')
        return result + [time_us] + _numbers(values[4:], kinds[4:])
    return [_integer(values[0], kinds[0])] + _numbers(values[1:], kinds[1:])


def reference_summary(sheet, row, kind):
    """Separate cell-access/key/clock reconstruction for summary rows."""
    cells = [sheet.cell(row, col) for col in range(sheet.ncols)]
    count = 3 if kind == 'step' else 1
    result = []
    for col in range(count):
        cell = cells[col]
        v = cell.value
        if (cell.ctype != 2 or type(v) not in (int, float) or not math.isfinite(v)
                or abs(v) > 9007199254740992 or v != int(v)
                or (col != 2 and v < 0)):
            raise ValueError('invalid independently reconstructed summary key')
        result.append(int(v))
    start = count
    if kind == 'step':
        cell = cells[3]
        if (cell.ctype != 1 or not isinstance(cell.value, str)
                or chronology.CLOCK.fullmatch(cell.value) is None):
            raise ValueError('invalid independently reconstructed summary clock')
        h, m, tail = cell.value.split(':')
        second, dot, fraction = tail.partition('.')
        time_us = (int(h) * 3600 + int(m) * 60 + int(second)) * 1000000
        if dot:
            time_us += int(fraction) * 10**(6 - len(fraction))
        result.append(time_us)
        start = 4
    for cell in cells[start:]:
        if (cell.ctype != 2 or type(cell.value) not in (int, float)
                or not math.isfinite(cell.value)):
            raise ValueError('invalid independently reconstructed summary measurement')
        result.append(cell.value)
    return result


def events(data, allowed, schema, xlrd_module=None):
    """Yield native record/step/cycle events with (index, name, XLS row).

    Positions use zero-based sheet index and one-based XLS row. Canonical record
    values are (cycle, step, status, record_number, time_us, V, mA, mAh), plus
    explicit energy_mWh outside that array. Summary arrays retain the exact
    documented column order, with the step clock converted to integer us.
    No sorting, grouping, repairs, sign interpretation or target calculation.
    """
    chronology.guard_biff(data, allowed)
    if hashlib.sha256(data).hexdigest() != schema['workbook_sha256']:
        raise ValueError('target-audit stream mismatch')
    if xlrd_module is None:
        import xlrd as xlrd_module
    warnings = io.StringIO()
    book = xlrd_module.open_workbook(file_contents=data, logfile=warnings,
        verbosity=0, use_mmap=False, formatting_info=False, on_demand=True,
        ragged_rows=True, ignore_workbook_corruption=False)
    record_count = 0
    try:
        if not 0 < book.nsheets <= 256 or book.nsheets != len(schema['sheets']):
            raise ValueError('target-audit sheet count mismatch')
        for index, expected in enumerate(schema['sheets']):
            sheet = book.sheet_by_index(index)
            try:
                if (expected['index'] != index or sheet.name != expected['name']
                        or sheet.nrows != expected['nrows'] or sheet.ncols != expected['ncols']
                        or not 1 <= sheet.nrows <= 65536):
                    raise ValueError('target-audit dimensions mismatch')
                if sheet.name == 'step':
                    kind, headers = 'step', (STEP, STEP_VOLTAGE)
                elif sheet.name == 'cycle':
                    kind, headers = 'cycle', (CYCLE, CYCLE_ENERGY)
                elif re.fullmatch(r'record_[1-9][0-9]*', sheet.name):
                    kind = 'record'
                    headers = (chronology.HEADER, chronology.HEADER + ('energy(mWh)',))
                else:
                    raise ValueError('unknown target-audit sheet')
                header = tuple(sheet.row_values(0))
                if (header not in headers or sheet.ncols != len(header)
                        or tuple(sheet.row_types(0)) != (1,) * len(header)):
                    raise ValueError('target-audit header mismatch')
                if kind == 'record' and sheet.nrows < 2:
                    raise ValueError('empty record sheet')
                for row in range(1, sheet.nrows):
                    if len(sheet.row_values(row)) != len(header):
                        raise ValueError('ragged target-audit row')
                    if kind == 'record':
                        key = chronology.key_from_cells(sheet, row)
                        independent = chronology.reference_key(sheet, row)
                        if (key is None or key != independent
                                or any(key[c] < 0 for c in (0, 1, 3, 4))):
                            raise ValueError('target-audit record key mismatch')
                        measured = _numbers(sheet.row_values(row)[5:], sheet.row_types(row)[5:])
                        cells = [sheet.cell(row, col) for col in range(5, len(header))]
                        rebuilt = _numbers([c.value for c in cells], [c.ctype for c in cells])
                        if measured != rebuilt:
                            raise ValueError('target-audit measurement reconstruction mismatch')
                        value = list(key) + measured[:3]
                        energy = measured[3] if len(measured) == 4 else None
                        record_count += 1
                    else:
                        value = _summary_values(sheet, row, kind)
                        if value != reference_summary(sheet, row, kind):
                            raise ValueError('target-audit summary reconstruction mismatch')
                        energy = None
                    if warnings.getvalue():
                        raise ValueError('target-audit parser warning')
                    yield dict(kind=kind, position=[index, sheet.name, row + 1],
                               values=value, energy_mWh=energy)
            finally:
                book.unload_sheet(index)
        if not record_count or warnings.getvalue():
            raise ValueError('target-audit missing records or parser warning')
    finally:
        book.release_resources()
