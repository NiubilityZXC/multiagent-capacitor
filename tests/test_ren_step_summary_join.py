from itertools import chain

import pytest

from experiments.audit_cap.ren_step_summary_join import join_step_summaries


ROWS = [(1, 1, 2, 1, 100, 2., -20., .1),
        (1, 1, 2, 2, 900, 1., -20., .5),
        (1, 2, 1, 3, 0, 1., 10., 0.),
        (1, 2, 1, 4, 700, 2., 15., .25)]


def test_both_layouts_and_chunk_boundaries():
    summaries = [(1, 1, 2, 900, .5, .7), (1, 2, 1, 800, .3, .9, 1.1, 2.2)]
    for cut in range(len(ROWS) + 1):
        out = join_step_summaries(chain(ROWS[:cut], ROWS[cut:]), iter(summaries))
        assert sum(s['rows'] for s in out['segments']) == 4
        assert out['summaries'] == [list(s) for s in summaries]
        for i, (start, end) in enumerate(((ROWS[0], ROWS[1]), (ROWS[2], ROWS[3]))):
            item = out['joins'][i]
            assert item['segment_indices'] == item['summary_indices'] == [i]
            assert item['status'] == 'UNIQUE_KEY_OBSERVATION'
            got = item['comparison']
            assert got['summary_minus_last_time_us'] == summaries[i][3] - end[4]
            assert got['summary_minus_sampled_elapsed_us'] == summaries[i][3] - end[4] + start[4]
            assert got['summary_minus_last_charge_mAh'] == summaries[i][4] - end[7]
            assert got['energy_comparison'] == 'UNAVAILABLE_RECORD_ENERGY'
        assert out['joins'][0]['comparison']['summary_minus_first_voltage_V'] is None
        assert out['joins'][0]['comparison']['summary_minus_last_voltage_V'] is None
        assert out['joins'][0]['comparison']['voltage_endpoints_available'] is False
        assert out['joins'][1]['comparison']['summary_minus_first_voltage_V'] == 1.1 - 1.
        assert out['joins'][1]['comparison']['summary_minus_last_voltage_V'] == 2.2 - 2.
        assert not any(out[k] for k in ('numeric_target_emitted', 'target_verified', 'data_gate_pass'))


def test_duplicate_missing_extra_and_repeated_record_keys_retained():
    rows = ROWS + [(1, 1, 2, 5, 0, 2., -20., 0.)]
    summaries = [(1, 1, 2, 900, .5, .7)] * 2 + [(2, 1, 2, 100, .1, .2)]
    out = join_step_summaries(rows, summaries)
    assert [(j['key'], j['segment_indices'], j['summary_indices'], j['status'])
            for j in out['joins']] == [
        ([1, 1, 2], [0, 2], [0, 1], 'AMBIGUOUS_KEY'),
        ([1, 2, 1], [1], [], 'RECORD_ONLY'),
        ([2, 1, 2], [], [2], 'SUMMARY_ONLY')]
    assert all(j['comparison'] is None for j in out['joins'])


@pytest.mark.parametrize('field,value', [(0, True), (1, -1), (2, 2.),
    (3, -1), (3, '100'), (4, float('nan')), (5, float('inf')), (6, True), (7, '2')])
def test_invalid_summary_fields(field, value):
    row = [1, 1, 2, 900, .5, .7, 2., 1.]
    row[field] = value
    with pytest.raises(ValueError): join_step_summaries(ROWS, [row])


@pytest.mark.parametrize('summary', [[], [1], [1, 1, 2, 900, .5, .7, 2.], 'bad'])
def test_invalid_summary_shape(summary):
    with pytest.raises(ValueError): join_step_summaries(ROWS, [summary])


def test_empty_summary_is_explicit_not_zero_filled():
    out = join_step_summaries(ROWS, [])
    assert len(out['joins']) == 2
    assert all(j['status'] == 'RECORD_ONLY' for j in out['joins'])


@pytest.mark.parametrize('which', ['records', 'summaries'])
def test_late_source_error_never_returns_partial_result(which):
    def broken(source):
        yield from source
        raise RuntimeError('source failure')
    summaries = [(1, 1, 2, 900, .5, .7)]
    with pytest.raises(RuntimeError, match='source failure'):
        join_step_summaries(broken(ROWS) if which == 'records' else ROWS,
                            broken(summaries) if which == 'summaries' else summaries)


def test_finite_inputs_overflow_is_rejected():
    rows = [(1, 1, 2, 0, 0, 2., -20., -1e308)]
    with pytest.raises(ValueError, match='nonfinite comparison'):
        join_step_summaries(rows, [(1, 1, 2, 0, 1e308, 0.)])
