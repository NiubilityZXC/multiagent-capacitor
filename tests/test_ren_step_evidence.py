from itertools import chain, groupby
import random

import pytest
from experiments.audit_cap.ren_step_evidence import iter_step_evidence


def reference(rows):
    result = []
    for key, grouped in groupby(rows, key=lambda r:r[:3]):
        g = list(grouped)
        pairs = list(zip(g, g[1:]))
        result.append(dict(key=list(key), first=list(g[0]), last=list(g[-1]), rows=len(g),
            current_min_mA=min(r[6] for r in g), current_max_mA=max(r[6] for r in g),
            positive_current_rows=sum(r[6]>0 for r in g),
            negative_current_rows=sum(r[6]<0 for r in g), zero_current_rows=sum(r[6]==0 for r in g),
            time_decreases=sum(b[4]<a[4] for a,b in pairs),
            equal_time_pairs=sum(b[4]==a[4] for a,b in pairs),
            voltage_increases=sum(b[5]>a[5] for a,b in pairs),
            voltage_decreases=sum(b[5]<a[5] for a,b in pairs),
            current_changes=sum(b[6]!=a[6] for a,b in pairs),
            charge_decreases=sum(b[7]<a[7] for a,b in pairs),
            numeric_target_emitted=False, target_verified=False))
    return result


def test_independent_reference_and_every_chunk_boundary():
    rng = random.Random(20260920)
    rows = [(n//30, (n//10)%3, (n//10)%2, n, rng.randrange(20),
             rng.randrange(10)/10, rng.choice([-20., 0., 5., 10., 15.]), rng.randrange(10)/10)
            for n in range(120)]
    expected = reference(rows)
    for split in range(len(rows)+1):
        assert list(iter_step_evidence(chain(rows[:split], rows[split:]))) == expected
    assert sum(x['rows'] for x in expected) == len(rows)


def test_noncontiguous_keys_retained_not_overwritten():
    rows = [(1,1,0,0,0,2.,-20.,0.), (1,2,1,1,0,1.,20.,0.),
            (1,1,0,2,0,2.,-20.,0.)]
    out = list(iter_step_evidence(rows))
    assert len(out) == 3 and out[0]['key'] == out[2]['key']
    assert out == reference(rows)


def test_singleton_and_unknown_status_are_observations():
    row = (0,0,17,100,0,1.,-0.,0.)
    out = list(iter_step_evidence([row]))
    assert out == reference([row])
    assert out[0]['zero_current_rows'] == 1


@pytest.mark.parametrize('field,value', [(0,True),(1,1.),(2,'0'),(3,-1),(4,-1),
    (5,float('nan')),(6,float('inf')),(7,'0'),(6,True)])
def test_invalid_rows_fail(field,value):
    row = [1,1,0,1,0,2.,-20.,0.]
    row[field] = value
    with pytest.raises(ValueError): list(iter_step_evidence([row]))


@pytest.mark.parametrize('rows', [[],[(1,)],['bad'],
    [(1,1,0,1,0,2.,-20.,0.),(1,1,0,3,1,1.,-20.,1.)],
    [(2,1,0,1,0,2.,-20.,0.),(1,1,0,2,1,1.,-20.,1.)]])
def test_empty_shape_gap_or_reversal_fail(rows):
    with pytest.raises(ValueError): list(iter_step_evidence(rows))


def test_step_resets_not_counted_as_within_step_time_reversal():
    rows = [(1,1,0,1,10,2.,-20.,1.),(1,2,1,2,0,1.,20.,0.),
            (1,2,1,3,0,1.,20.,0.),(1,2,1,4,1,2.,20.,1.)]
    out = list(iter_step_evidence(rows))
    assert out == reference(rows)
    assert sum(x['time_decreases'] for x in out) == 0
    assert out[1]['equal_time_pairs'] == 1


def test_late_source_error_must_not_be_silenced():
    def source():
        yield (1,1,0,0,0,2.,-20.,0.)
        yield (1,2,1,1,0,1.,20.,0.)
        raise RuntimeError('late failure')
    iterator = iter_step_evidence(source())
    assert next(iterator)['rows'] == 1
    with pytest.raises(RuntimeError, match='late failure'): list(iterator)
