import json
import pytest
from experiments.audit_cap import ren_overlap_pipeline as p
from experiments.audit_cap import ren_overlap_pilot as pilot
from experiments.audit_cap import ren_overlap as o


def source(gid):
    for i in range(80):
        token=o.measurement_token((1,1,0,i,i*1000),[1,1,0,i,"",i/100.,-20.,i/1000.])
        yield (f"{gid}.xls",0,"record_1",i+2,token,None)


def groups():return [(str(g),[(f"{g}.xls",0,"record_1",80)]) for g in range(2)]


def test_pipeline_persisted_confirmation(tmp_path):
    local,public=tmp_path/"local",tmp_path/"public"
    result=p.run_pipeline(local,public,groups(),source)
    assert result["groups"]==2 and result["rows"]==160
    assert result["confirmed_projected_spans"]>0 and not result["p2_eligible"]
    assert json.loads((public/"COMPLETE.json").read_text())["summary_sha256"]==p.digest(public/"SUMMARY.json")
    with pytest.raises(ValueError,match="append-only"):p.run_pipeline(local,public,groups(),source)


@pytest.mark.parametrize("mode",["missing","extra","position","failure"])
def test_bad_source_never_completes(tmp_path,mode):
    def bad(gid):
        rows=list(source(gid))
        if mode=="missing":rows.pop()
        if mode=="extra":rows.append(rows[-1])
        if mode=="position":rows[2]=(*rows[2][:3],99,*rows[2][4:])
        yield from rows
        if mode=="failure":raise RuntimeError("late upstream failure")
    with pytest.raises((ValueError,RuntimeError)):
        p.run_pipeline(tmp_path/"l",tmp_path/"u",groups(),bad)
    assert (tmp_path/"u/BLOCKED.json").exists()
    assert not (tmp_path/"u/COMPLETE.json").exists()


def test_corrupt_confirmation_stops(tmp_path,monkeypatch):
    real=p.search.confirm_anchor
    def corrupt(*args):
        out=real(*args)
        if out:out["energy_missing_rows"]+=1
        return out
    monkeypatch.setattr(p.search,"confirm_anchor",corrupt)
    with pytest.raises(ValueError,match="independent match ledger"):
        p.run_pipeline(tmp_path/"l",tmp_path/"u",groups(),source)
    assert not (tmp_path/"u/COMPLETE.json").exists()


def test_index_omission_detected(tmp_path,monkeypatch):
    real=o.winnow
    def incomplete(tokens):
        values=list(real(tokens))
        yield from values[:-1]
    monkeypatch.setattr(o,"winnow",incomplete)
    with pytest.raises(ValueError,match="index mismatch"):
        p.run_pipeline(tmp_path/"l",tmp_path/"u",groups(),source)


def test_candidate_budget_is_failure_not_truncation(tmp_path):
    with pytest.raises(ValueError,match="budget exceeded"):
        p.run_pipeline(tmp_path/"l",tmp_path/"u",groups(),source,pair_budget=1)
    assert not (tmp_path/"u/COMPLETE.json").exists()


def test_missing_release_before_source_or_output(tmp_path,monkeypatch):
    monkeypatch.setattr(pilot.prior,"preflight",lambda root:pytest.fail("prerequisite called before release"))
    with pytest.raises(pilot.prior.fleet.pilot.context.recovery.RecoveryError):
        pilot.run(tmp_path)
    assert not (tmp_path/"data").exists()


def test_reference_matches_independent_anchor_geometry():
    for offset in range(25):
        read=lambda i:(bytes([i])*40,None)
        assert p.reference_match(read,read,32,32,offset,offset)==p.search.confirm_anchor(read,read,32,32,offset,offset)


def test_synthetic_pilot_caller_real_reader_and_pipeline(tmp_path,monkeypatch):
    pytest.importorskip("xlrd",reason="mandatory pilot end-to-end in audit env")
    import hashlib
    from types import SimpleNamespace
    from tests.test_ren_measurement_stream import multibook
    from tests.test_ren_chronology import ALLOWED
    from experiments.audit_cap.ren_workbook_reader import schema_rows
    extraction=tmp_path/"extraction";extraction.mkdir()
    selected=[];schemas={}
    rows=[[1,1,0,i+1,f"0:00:{i:02d}",1+i/100.,-20.,i/1000.] for i in range(40)]
    for gid,chunks in enumerate(([rows[:20],rows[20:]],[rows[:13],rows[13:]])):
        member=f"{gid}.xls";data=multibook(chunks)
        (extraction/member).write_bytes(data)
        schemas[member]=schema_rows(data,ALLOWED)
        selected.append((str(gid),[dict(member_path=member,input_bytes=len(data),input_sha256=hashlib.sha256(data).hexdigest())]))
    monkeypatch.setattr(pilot,"preflight",lambda root:(selected,schemas,ALLOWED))
    rec=pilot.prior.fleet.pilot.context.recovery
    monkeypatch.setattr(rec.Paths,"build",lambda *a,**k:SimpleNamespace(extraction=extraction))
    monkeypatch.setattr(pilot.prior.fleet.pilot,"workbook_bytes",lambda raw:raw)
    for path in (tmp_path/"data/raw/ren_scs",tmp_path/"data/audit/ren_scs"):path.mkdir(parents=True)
    result=pilot.run(tmp_path)
    assert result["rows"]==80 and result["confirmed_projected_spans"]>0
    assert not result["p2_eligible"]


def test_spool_corruption_fails_before_completion(tmp_path,monkeypatch):
    real=p.verify_index;calls=0
    def corrupt(index,gid,path,rows):
        nonlocal calls
        calls+=1
        if calls==1:
            data=path.read_bytes();path.write_bytes(data[:-1])
        return real(index,gid,path,rows)
    monkeypatch.setattr(p,"verify_index",corrupt)
    with pytest.raises(ValueError,match="row count mismatch"):
        p.run_pipeline(tmp_path/"l",tmp_path/"u",groups(),source)
    assert not (tmp_path/"u/COMPLETE.json").exists()
