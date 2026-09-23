from copy import deepcopy
import json

import pytest

from experiments.audit_cap import ren_target_group as producer
from experiments.audit_cap import ren_target_verify as reference
from experiments.audit_cap.ren_workbook_reader import schema_rows
from tests.test_ren_target_group import sources
from tests.test_ren_target_workbook import book, fixture
from tests.test_ren_workbook_reader import ALLOWED


@pytest.fixture(autouse=True)
def require_xlrd():
    pytest.importorskip('xlrd')


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, path + (key,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from leaves(child, path + (i,))
    else:
        yield path, value


@pytest.mark.parametrize('extended', [False, True])
def test_reconstruct_every_persisted_field_and_reject_each_leaf_mutation(tmp_path, extended):
    blobs, schemas = sources(extended)
    members = list(blobs)
    out = producer.collect_group(members, schemas, ALLOWED, blobs.__getitem__)
    path = tmp_path / 'evidence.json'
    path.write_text(json.dumps(out, allow_nan=False))
    saved = json.loads(path.read_text())
    rebuilt = reference.rebuild(members, schemas, ALLOWED, blobs.__getitem__)
    reference.verify(saved, members, schemas, ALLOWED, blobs.__getitem__)
    count = 0
    for location, value in leaves(saved):
        changed = deepcopy(saved)
        parent = changed
        for key in location[:-1]:
            parent = parent[key]
        parent[location[-1]] = (not value if type(value) is bool else
                                value + 1 if type(value) in (int,float) else
                                value + '_changed' if type(value) is str else 1)
        with pytest.raises(ValueError):
            reference.equal_fields(changed, rebuilt)
        count += 1
    assert count == (112 if extended else 108)
    for mutate in (lambda x:x.update(extra=1), lambda x:x.pop('joins'),
                   lambda x:x['segments'].clear(), lambda x:x.update(data_gate_pass=0)):
        changed = deepcopy(saved); mutate(changed)
        with pytest.raises(ValueError): reference.equal_fields(changed, rebuilt)


@pytest.mark.parametrize('mode', ['duplicates','missing','mixed','recur','time_changes','summary_only'])
def test_reference_handles_all_join_and_record_branches(mode):
    sheets = fixture(True)
    if mode == 'duplicates':
        sheets[0][2].append(deepcopy(sheets[0][2][0]))
        sheets[1][2].append(deepcopy(sheets[1][2][0]))
    elif mode == 'missing':
        sheets[0][2].clear(); sheets[1][2].clear()
    elif mode == 'mixed':
        sheets[2][2][0][6] = 0.
    elif mode == 'recur':
        row = deepcopy(sheets[2][2][-1]); row[3] += 1
        sheets[2][2].append(row); sheets[2][2][1][1] += 1
    elif mode == 'time_changes':
        sheets[2][2][1][4] = '0:00:00.1'
        sheets[2][2][1][5] = 3.; sheets[2][2][1][7] = 0.
    else:
        sheets[0][2][0][0] = 2; sheets[1][2][0][0] = 2
    data = book(sheets); schemas = {'one':schema_rows(data, ALLOWED)}
    actual = producer.collect_group(['one'],schemas,ALLOWED,lambda _:data)
    reference.verify(json.loads(json.dumps(actual)),['one'],schemas,ALLOWED,lambda _:data)


def test_independent_rebuild_detects_producer_fault(monkeypatch):
    blobs, schemas = sources()
    original = producer.join_step_summaries
    def corrupt(*args):
        out = original(*args)
        out['segments'][0]['negative_current_rows'] -= 1
        return out
    monkeypatch.setattr(producer, 'join_step_summaries', corrupt)
    saved = producer.collect_group(list(blobs),schemas,ALLOWED,blobs.__getitem__)
    with pytest.raises(ValueError, match='negative_current_rows'):
        reference.verify(saved,list(blobs),schemas,ALLOWED,blobs.__getitem__)


@pytest.mark.parametrize('mode',['missing','extra','displaced','gap'])
def test_reference_rejects_corrupt_input_and_closes_stream(monkeypatch, mode):
    blobs, schemas = sources()
    original = reference.events
    closed = []
    def corrupt(*args):
        values = list(original(*args))
        if mode == 'missing': values.pop()
        if mode == 'extra': values.append(deepcopy(values[-1]))
        if mode == 'displaced': values[-1]['position'][-1] += 1
        if mode == 'gap' and values[-1]['values'][3] == 11:
            values[-1]['values'][3] += 2
        try:
            yield from values
        finally:
            closed.append(True)
    monkeypatch.setattr(reference, 'events', corrupt)
    held = []
    try:
        reference.rebuild(list(blobs),schemas,ALLOWED,blobs.__getitem__)
    except ValueError as exc:
        held.append(exc)
    assert held and closed


@pytest.mark.parametrize('current', [20., 0.])
def test_reference_known_multistep_sign_buckets(current):
    sheets = fixture(True)
    sheets[0][2][:] = [[1,1,1,'0:00:01',.125,.25,1.,2.],
                       [1,2,1,'0:00:01',.375,.5,1.,2.]]
    sheets[1][2][:] = [[1,.5,0.,.75,0.]]
    sheets[2][2][:] = [[1,1,1,10,'0:00:01',2.,current,.125,.25],
                       [1,2,1,11,'0:00:01',2.,current,.375,.5]]
    data = book(sheets)
    schemas = {'one':schema_rows(data,ALLOWED)}
    out = reference.rebuild(['one'],schemas,ALLOWED,lambda _:data)
    cycle = out['cycle_observations'][0]
    sign = 'positive' if current else 'zero'
    assert cycle['current_sign_segment_indices'][sign] == [0,1]
    assert cycle['cycle_capacity_minus_current_sign_bucket_endpoint_sum_mAh'] == {
        'positive':0. if current else None, 'negative':None}
    assert cycle['sum_semantics_verified'] is False
    actual = producer.collect_group(['one'],schemas,ALLOWED,lambda _:data)
    reference.equal_fields(actual,out)

