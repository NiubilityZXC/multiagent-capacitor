from copy import deepcopy
import hashlib
import json
import os

import pytest

from experiments.audit_cap import ren_target_source as source
from tests.test_ren_target_group import sources
from tests.test_ren_workbook_reader import ALLOWED


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    pytest.importorskip('xlrd')
    blobs, old_schemas = sources()
    extraction = tmp_path / 'extracted'
    (extraction / 'batch1').mkdir(parents=True)
    reports, schemas = [], {}
    containers = {}
    for old, name in [('main','batch1/1.xls'), ('fragment','batch1/1__1.xls')]:
        raw = b'SYNTHETIC_CONTAINER:' + blobs[old]
        containers[raw] = blobs[old]
        (extraction/name).write_bytes(raw)
        schemas[name] = old_schemas[old]
        reports.append(dict(member_path=name,input_bytes=len(raw),
            input_sha256=hashlib.sha256(raw).hexdigest(),
            workbook_scans=[dict(stream_sha256=schemas[name]['workbook_sha256'])]))
    # Deliberately mocked OLE isolation; real BIFF parsing/reducer/verifier remain active.
    monkeypatch.setattr(source,'workbook_bytes',containers.__getitem__)
    return tmp_path, extraction, 'batch1/1', reports, schemas, ALLOWED


def test_source_to_saved_json_to_independent_reconstruction(prepared, tmp_path):
    actual = source.collect_source_group(*prepared)
    path = tmp_path/'saved.json'
    path.write_text(json.dumps(actual, allow_nan=False))
    saved = json.loads(path.read_text())
    source.verify_source_group(saved,*prepared)
    saved['segment_source_energy'][0]['last_position'][-1] += 1
    with pytest.raises(ValueError,match='last_position'):
        source.verify_source_group(saved,*prepared)


@pytest.mark.parametrize('mode',['size','hash','missing','symlink','hardlink','stream'])
def test_source_changes_fail_closed(prepared, mode, monkeypatch):
    root, extraction, candidate, reports, schemas, allowed = prepared
    path = extraction/reports[-1]['member_path']
    if mode == 'size': path.write_bytes(path.read_bytes()+b'x')
    elif mode == 'hash':
        raw = path.read_bytes(); path.write_bytes(b'X'+raw[1:])
    elif mode == 'missing': path.unlink()
    elif mode == 'symlink':
        real = extraction/'copy.xls'; path.rename(real); path.symlink_to(real)
    elif mode == 'hardlink': os.link(path,extraction/'alias.xls')
    else: monkeypatch.setattr(source,'workbook_bytes',lambda raw:b'wrong Workbook')
    with pytest.raises((ValueError,source.prior.fleet.pilot.context.recovery.RecoveryError)):
        source.collect_source_group(*prepared)


@pytest.mark.parametrize('mode',['candidate','order','duplicate','fragment_gap','schema','escape'])
def test_wrong_source_contract_rejected(prepared, mode):
    root, extraction, candidate, reports, schemas, allowed = prepared
    reports, schemas = deepcopy(reports), deepcopy(schemas)
    if mode == 'candidate': candidate = 'batch1/2'
    elif mode == 'order': reports.reverse()
    elif mode == 'duplicate': reports.append(deepcopy(reports[0]))
    elif mode in ('fragment_gap','escape'):
        name = 'batch1/1__2.xls' if mode == 'fragment_gap' else '../outside.xls'
        schemas[name] = schemas.pop(reports[1]['member_path'])
        reports[1]['member_path'] = name
    else: schemas[reports[0]['member_path']]['workbook_sha256'] = '0'*64
    with pytest.raises(ValueError):
        source.collect_source_group(root,extraction,candidate,reports,schemas,allowed)


def test_verifier_rechecks_container_not_cached_result(prepared):
    actual = source.collect_source_group(*prepared)
    root, extraction, candidate, reports, schemas, allowed = prepared
    path = extraction/reports[0]['member_path']
    raw = path.read_bytes(); path.write_bytes(b'X'+raw[1:])
    with pytest.raises(ValueError,match='container mismatch'):
        source.verify_source_group(actual,*prepared)
