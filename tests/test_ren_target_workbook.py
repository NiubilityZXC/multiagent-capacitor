from copy import deepcopy
import struct

import pytest

from experiments.audit_cap import ren_chronology as c
from experiments.audit_cap import ren_target_workbook as target
from experiments.audit_cap.ren_step_summary_join import join_step_summaries
from experiments.audit_cap.ren_workbook_reader import schema_rows
from tests.test_ren_chronology import record_workbook
from tests.test_ren_workbook_reader import ALLOWED, bof, rec


@pytest.fixture(autouse=True)
def require_xlrd():
    pytest.importorskip('xlrd', reason='mandatory target Workbook integration in audit env')


def book(sheets):
    """Reuse existing raw BIFF fixture builder for arbitrary named sheets."""
    bodies = []
    for name, header, rows in sheets:
        data = record_workbook(header, rows)
        offset = 0
        while offset < len(data):
            kind, size = struct.unpack_from('<HH', data, offset)
            if kind == 0x0809 and struct.unpack_from('<H', data, offset + 6)[0] == 16:
                bodies.append(data[offset:])
                break
            offset += size + 4
    prefix = bof() + rec(0x0042, struct.pack('<H', 1200)) + rec(0x0022, b'\0\0')
    def bound(name, offset):
        encoded = name.encode('ascii')
        return rec(0x0085, struct.pack('<IBBBB', offset, 0, 0, len(encoded), 0) + encoded)
    offset = len(prefix) + sum(len(bound(s[0], 0)) for s in sheets) + 4
    bounds = []
    for sheet, body in zip(sheets, bodies):
        bounds.append(bound(sheet[0], offset))
        offset += len(body)
    return prefix + b''.join(bounds) + rec(0x000A) + b''.join(bodies)


def fixture(extended=False):
    step = [1, 2, -1, '0:00:01.25', .2, .3] + ([2., 1.] if extended else [])
    cycle = [1, .4, .2] + ([.5, .3] if extended else [])
    rows = [[1, 2, -1, i + 10, t, v, -20., q] + ([e] if extended else [])
            for i, (t, v, q, e) in enumerate([('0:00:00.25', 2., .1, .15),
                                             ('0:00:01.25', 1., .2, .3)])]
    return [('step', target.STEP_VOLTAGE if extended else target.STEP, [step]),
            ('cycle', target.CYCLE_ENERGY if extended else target.CYCLE, [cycle]),
            ('record_1', c.HEADER + (('energy(mWh)',) if extended else ()), rows)]


def collect(sheets):
    data = book(sheets)
    return list(target.events(data, ALLOWED, schema_rows(data, ALLOWED)))


@pytest.mark.parametrize('extended', [False, True])
def test_real_parser_all_layouts_positions_and_units(extended):
    out = collect(fixture(extended))
    assert out[0] == dict(kind='step', position=[0, 'step', 2],
        values=[1, 2, -1, 1250000, .2, .3] + ([2., 1.] if extended else []), energy_mWh=None)
    assert out[1] == dict(kind='cycle', position=[1, 'cycle', 2],
        values=[1, .4, .2] + ([.5, .3] if extended else []), energy_mWh=None)
    assert out[2] == dict(kind='record', position=[2, 'record_1', 2],
        values=[1, 2, -1, 10, 250000, 2., -20., .1], energy_mWh=.15 if extended else None)
    assert out[3]['position'] == [2, 'record_1', 3]
    joined = join_step_summaries((e['values'] for e in out if e['kind'] == 'record'),
                                (e['values'] for e in out if e['kind'] == 'step'))
    assert joined['segments'][0]['rows'] == 2
    assert joined['joins'][0]['comparison']['summary_minus_last_time_us'] == 0
    assert joined['joins'][0]['comparison']['summary_minus_sampled_elapsed_us'] == 250000
    assert not joined['data_gate_pass']


def test_cross_workbook_step_not_reset_and_duplicate_summaries_preserved():
    sheets = fixture(True)
    rows = sheets[-1][2]
    left = collect(sheets[:2] + [('record_1', sheets[-1][1], rows[:1])])
    right = collect([('record_1', sheets[-1][1], rows[1:])])
    all_events = left + right
    summary = [e['values'] for e in all_events if e['kind'] == 'step']
    result = join_step_summaries((e['values'] for e in all_events if e['kind'] == 'record'),
                                 summary + summary)
    assert len(result['segments']) == 1 and result['segments'][0]['rows'] == 2
    assert result['joins'][0]['status'] == 'AMBIGUOUS_KEY'


@pytest.mark.parametrize('sheet,col,value', [(0, 0, 1.5), (0, 1, -1), (0, 2, '0'),
    (0, 3, 'bad'), (0, 4, '0.2'), (0, 5, float('inf')), (0, 6, float('nan')),
    (1, 0, -1), (1, 1, '0.4'), (2, 0, -1), (2, 4, 0), (2, 8, '0.15')])
def test_invalid_source_values_fail(sheet, col, value):
    sheets = fixture(True)
    sheets[sheet][2][0][col] = value
    data = book(sheets)
    with pytest.raises(ValueError):
        list(target.events(data, ALLOWED, schema_rows(data, ALLOWED)))


@pytest.mark.parametrize('index', [0, 1, 2])
def test_units_not_relabelled(index):
    sheets = fixture()
    name, header, rows = sheets[index]
    sheets[index] = (name, ('wrong_unit',) + header[1:], rows)
    with pytest.raises(ValueError, match='header mismatch'): collect(sheets)


@pytest.mark.parametrize('field,value', [('index', 10), ('name', 'cycle'), ('nrows', 99), ('ncols', 99)])
def test_schema_mismatch(field, value):
    data = book(fixture())
    schema = schema_rows(data, ALLOWED)
    schema['sheets'][0][field] = value
    with pytest.raises(ValueError, match='dimensions mismatch'):
        list(target.events(data, ALLOWED, schema))


def test_wrong_hash_and_active_biff_fail_before_parser():
    data = book(fixture())
    schema = schema_rows(data, ALLOWED)
    schema['workbook_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='stream mismatch'):
        list(target.events(data, ALLOWED, schema, object()))
    with pytest.raises(ValueError, match='active BIFF'):
        list(target.events(bof() + rec(0x0006) + rec(0x000A), ALLOWED | {0x0006}, {}, object()))


@pytest.mark.parametrize('kind', ['step', 'cycle'])
def test_independent_summary_field_corruption_detected(monkeypatch, kind):
    original = target.reference_summary
    def wrong(sheet, row, which):
        value = original(sheet, row, which)
        if which == kind:
            value[-1] += 1
        return value
    monkeypatch.setattr(target, 'reference_summary', wrong)
    with pytest.raises(ValueError, match='summary reconstruction'): collect(fixture(True))


def test_late_failure_and_early_close_release_resources():
    import xlrd
    sheets = fixture()
    sheets[2][2][1][6] = 'bad'
    data = book(sheets)
    schema = schema_rows(data, ALLOWED)
    observed = []
    class Module:
        def open_workbook(self, **kwargs):
            result = xlrd.open_workbook(**kwargs)
            release = result.release_resources
            def close():
                observed.append('released')
                release()
            result.release_resources = close
            return result
    stream = target.events(data, ALLOWED, schema, Module())
    next(stream)
    stream.close()
    assert observed == ['released']
    stream = target.events(data, ALLOWED, schema, Module())
    for _ in range(3): next(stream)
    with pytest.raises(ValueError, match='measurement'): next(stream)
    assert observed == ['released', 'released']


def test_missing_records_cannot_be_completed():
    with pytest.raises(ValueError, match='missing records'): collect(fixture()[:2])
