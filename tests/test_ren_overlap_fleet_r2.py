import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest
from experiments.audit_cap import ren_overlap_fleet_r2 as r
from experiments.audit_cap import ren_overlap as overlap


@pytest.mark.parametrize("mode",["launch","execute"])
def test_no_release_stops_before_sources_or_launch(tmp_path,monkeypatch,mode):
    monkeypatch.setattr(r.fleet,"preflight",lambda p:pytest.fail("source access"))
    monkeypatch.setattr(r.job,"launch",lambda *a:pytest.fail("process launched"))
    with pytest.raises(r.fleet.prior.fleet.pilot.context.recovery.RecoveryError):
        getattr(r,mode)(tmp_path)
    assert not (tmp_path/"data").exists()


def test_launch_fixed_command_and_append_only(tmp_path,monkeypatch):
    monkeypatch.setattr(r,"release_check",lambda p:None)
    seen=[]
    monkeypatch.setattr(r.job,"launch",lambda *args:seen.append(args) or 123)
    assert r.launch(tmp_path)==123
    argv,cwd,directory=seen[0]
    assert argv==[sys.executable,str(Path(r.__file__).resolve()),"--execute","--project-root",str(tmp_path)]
    assert directory==tmp_path/"data/raw/ren_scs"/(r.RUN+"_job")
    directory.mkdir(parents=True)
    with pytest.raises(ValueError,match="append-only"):r.launch(tmp_path)
    assert len(seen)==1


def test_detached_real_r2_cli_missing_release_is_failure(tmp_path):
    directory=tmp_path/"job"
    r.job.launch([sys.executable,str(Path(r.__file__).resolve()),"--execute","--project-root",str(tmp_path)],tmp_path,directory)
    deadline=time.monotonic()+10
    receipt=directory/"RETURNED.json"
    while not receipt.exists() and time.monotonic()<deadline:time.sleep(.02)
    assert json.loads(receipt.read_text())["child_returncode"]!=0
    assert not (tmp_path/"data").exists()


def test_new_paths_all_fragments_and_false_flags(tmp_path,monkeypatch):
    monkeypatch.setattr(r,"release_check",lambda p:None)
    rec=r.fleet.prior.fleet.pilot.context.recovery
    extraction=tmp_path/"extracted";extraction.mkdir()
    selected=[];schemas={};groups=[]
    for gid in range(3):
        reports=[];spans=[]
        for part in range(2):
            member=f"{gid}_{part}.xls";raw=bytes([gid,part])
            (extraction/member).write_bytes(raw)
            reports.append(dict(member_path=member,input_bytes=2,input_sha256=hashlib.sha256(raw).hexdigest()))
            schemas[member]={};spans.append((member,0,"record_1",40))
        selected.append((str(gid),reports));groups.append((str(gid),spans))
    monkeypatch.setattr(r.fleet,"preflight",lambda p:(selected,schemas,[],groups))
    monkeypatch.setattr(rec.Paths,"build",lambda *a,**kw:SimpleNamespace(extraction=extraction))
    monkeypatch.setattr(r.fleet.prior.fleet.pilot,"workbook_bytes",lambda b:b)
    closed=[]
    def records(raw,*a):
        try:
            for i in range(40):
                token=overlap.measurement_token((1,1,0,i,i),[1,1,0,i,"",raw[0]+i/100.,-20.,raw[1]+i/100.])
                yield 0,"record_1",i+2,token,None
        finally:closed.append(tuple(raw))
    monkeypatch.setattr(r.fleet.stream,"records",records)
    for base in ("data/raw/ren_scs","data/audit/ren_scs"):(tmp_path/base).mkdir(parents=True)
    original=r.fleet.RUN
    result=r.execute(tmp_path)
    assert result["rows"]==240 and result["groups"]==3 and len(closed)==6
    assert all(result[k] is False for k in r.fleet.pipeline.FLAGS)
    assert r.fleet.RUN==original and original!=r.RUN
    assert (tmp_path/"data/audit/ren_scs"/r.RUN/"COMPLETE.json").exists()
    assert not (tmp_path/"data/audit/ren_scs"/original).exists()
