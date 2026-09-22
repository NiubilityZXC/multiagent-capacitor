from copy import deepcopy

import pytest

from experiments.audit_cap import ren_target_group as group
from experiments.audit_cap.ren_workbook_reader import schema_rows
from tests.test_ren_target_workbook import book, fixture
from tests.test_ren_workbook_reader import ALLOWED


@pytest.fixture(autouse=True)
def require_xlrd():
    pytest.importorskip('xlrd', reason='mandatory group integration in audit env')


def sources(extended=True):
    sheets = fixture(extended)
    rows = sheets[2][2]
    blobs = {'main': book(sheets[:2] + [('record_1', sheets[2][1], rows[:1])]),
             'fragment': book([('record_1', sheets[2][1], rows[1:])])}
    return blobs, {m: schema_rows(b, ALLOWED) for m, b in blobs.items()}


@pytest.mark.parametrize('extended', [False, True])
def test_cross_source_single_pass_positions_energy_and_terminal(extended):
    blobs, schemas = sources(extended)
    calls = []
    def load(m):
        calls.append(m)
        return blobs[m]
    out = group.collect_group(list(blobs), schemas, ALLOWED, load)
    assert calls == ['main', 'fragment']
    assert out['source_coverage'] == [dict(member='main', record=1, step=1, cycle=1),
                                      dict(member='fragment', record=1, step=0, cycle=0)]
    assert len(out['segments']) == 1 and out['segments'][0]['rows'] == 2
    extra = out['segment_source_energy'][0]
    assert extra['first_position'] == ['main', 2, 'record_1', 2]
    assert extra['last_position'] == ['fragment', 0, 'record_1', 2]
    assert extra['energy_missing_rows'] == (0 if extended else 2)
    assert out['energy_joins'][0]['summary_minus_last_energy_mWh'] == (0 if extended else None)
    assert out['summary_positions'] == [['main', 0, 'step', 2]]
    assert out['cycle_positions'] == [['main', 1, 'cycle', 2]]
    assert out['cycle_observations'][0]['current_sign_segment_indices']['negative'] == [0]
    assert out['cycle_observations'][0]['cycle_capacity_minus_current_sign_bucket_endpoint_sum_mAh'] == {'positive': None, 'negative': 0}
    assert out['last_observed_cycle'] == 1
    assert not any(out[k] for k in ('failure_event_verified','physical_identity_verified','p2_eligible','data_gate_pass'))


def test_multiple_charging_steps_and_duplicate_cycle_summary_not_overwritten():
    sheets = fixture(True)
    sheets[0][2][:] = [[1,1,1,'0:00:01',.1,.2,1.,2.], [1,2,1,'0:00:01',.3,.4,1.,2.]]
    sheets[1][2][:] = [[1,.4,0.,.6,0.], [1,.4,0.,.6,0.]]
    sheets[2][2][:] = [[1,1,1,1,'0:00:01',2.,10.,.1,.2], [1,2,1,2,'0:00:01',2.,20.,.3,.4]]
    data = book(sheets)
    out = group.collect_group(['one'], {'one':schema_rows(data,ALLOWED)}, ALLOWED, lambda _:data)
    cycle = out['cycle_observations'][0]
    assert cycle['segment_indices'] == [0,1] and cycle['summary_indices'] == [0,1]
    assert cycle['current_sign_segment_indices']['positive'] == [0,1]
    assert cycle['cycle_capacity_minus_current_sign_bucket_endpoint_sum_mAh'] is None


@pytest.mark.parametrize('mode', ['missing','extra','displaced'])
def test_event_coverage_corruption_rejected(monkeypatch, mode):
    blobs, schemas = sources()
    original = group.events
    def altered(*args):
        values = list(original(*args))
        if mode == 'missing': values.pop()
        if mode == 'extra': values.append(deepcopy(values[-1]))
        if mode == 'displaced': values[-1]['position'][-1] += 1
        yield from values
    monkeypatch.setattr(group, 'events', altered)
    with pytest.raises(ValueError, match='coverage mismatch'):
        group.collect_group(list(blobs), schemas, ALLOWED, blobs.__getitem__)


def test_missing_duplicate_reordered_and_late_failed_sources():
    blobs, schemas = sources()
    for members in ([], ['main','main'], ['unknown']):
        with pytest.raises(ValueError): group.collect_group(members,schemas,ALLOWED,blobs.__getitem__)
    with pytest.raises(ValueError, match='record number discontinuity'):
        group.collect_group(['fragment','main'],schemas,ALLOWED,blobs.__getitem__)
    def broken(m):
        if m == 'fragment': raise RuntimeError('late load failure')
        return blobs[m]
    with pytest.raises(RuntimeError, match='late load failure'):
        group.collect_group(list(blobs),schemas,ALLOWED,broken)


def test_independent_segment_count_divergence_rejected(monkeypatch):
    blobs, schemas = sources()
    original = group.join_step_summaries
    def corrupt(*args):
        result = original(*args)
        result['segments'][0]['rows'] += 1
        return result
    monkeypatch.setattr(group,'join_step_summaries',corrupt)
    with pytest.raises(ValueError, match='segment reconstruction'):
        group.collect_group(list(blobs),schemas,ALLOWED,blobs.__getitem__)

def test_multiple_positive_steps_have_explicit_sum_hypothesis():
    sheets = fixture(True)
    sheets[0][2][:] = [[1,1,1,'0:00:01',.125,.25,1.,2.],
                       [1,2,1,'0:00:01',.375,.5,1.,2.]]
    sheets[1][2][:] = [[1,.5,0.,.75,0.]]
    sheets[2][2][:] = [[1,1,1,1,'0:00:01',2.,10.,.125,.25],
                       [1,2,1,2,'0:00:01',2.,20.,.375,.5]]
    data = book(sheets)
    out = group.collect_group(['one'], {'one':schema_rows(data,ALLOWED)}, ALLOWED, lambda _:data)
    cycle = out['cycle_observations'][0]
    assert cycle['current_sign_segment_indices']['positive'] == [0,1]
    assert cycle['cycle_capacity_minus_current_sign_bucket_endpoint_sum_mAh'] == {'positive':0., 'negative':None}
    assert cycle['sum_semantics_verified'] is False


def test_missing_summary_and_mixed_current_do_not_create_cycle_or_failure():
    sheets = fixture(True)
    sheets[0][2].clear()
    sheets[1][2].clear()
    sheets[2][2][0][6] = 20.
    data = book(sheets)
    out = group.collect_group(['one'], {'one':schema_rows(data,ALLOWED)}, ALLOWED, lambda _:data)
    assert out['joins'][0]['status'] == 'RECORD_ONLY'
    assert out['energy_joins'][0]['comparison_available'] is False
    cycle = out['cycle_observations'][0]
    assert cycle['current_sign_segment_indices']['mixed'] == [0]
    assert cycle['summary_indices'] == []
    assert cycle['cycle_capacity_minus_current_sign_bucket_endpoint_sum_mAh'] is None
    assert out['failure_event_verified'] is False and out['termination_reason_available'] is False


def test_missing_energy_in_one_fragment_is_not_zero_filled():
    blobs, schemas = sources(True)
    plain, plain_schemas = sources(False)
    blobs['fragment'] = plain['fragment']
    schemas['fragment'] = plain_schemas['fragment']
    out = group.collect_group(list(blobs),schemas,ALLOWED,blobs.__getitem__)
    assert out['segment_source_energy'][0]['energy_missing_rows'] == 1
    assert out['segment_source_energy'][0]['last_energy_mWh'] is None
    assert out['energy_joins'][0]['summary_minus_last_energy_mWh'] is None


def test_energy_difference_is_observation_not_tolerance_decision():
    sheets = fixture(True)
    sheets[0][2][0][5] = .8
    data = book(sheets)
    out = group.collect_group(['one'], {'one':schema_rows(data,ALLOWED)}, ALLOWED, lambda _:data)
    assert out['energy_joins'][0]['summary_minus_last_energy_mWh'] == .8 - .3
    assert out['data_gate_pass'] is False

def test_reducer_error_closes_stream_while_traceback_is_retained(monkeypatch):
    sheets = fixture(True)
    sheets[2][2][1][3] = 12  # record number gap after first record_number=10
    data = book(sheets)
    original = group.events
    closed, held = [], []
    def tracked(*args):
        try:
            yield from original(*args)
        finally:
            closed.append(True)
    monkeypatch.setattr(group, 'events', tracked)
    try:
        group.collect_group(['one'], {'one':schema_rows(data,ALLOWED)}, ALLOWED, lambda _:data)
    except ValueError as exc:
        held.append(exc)
    assert len(held) == 1 and 'record number discontinuity' in str(held[0])
    assert closed == [True]
