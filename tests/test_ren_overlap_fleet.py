import hashlib
from types import SimpleNamespace

import pytest
from experiments.audit_cap import ren_overlap_fleet as f
from experiments.audit_cap import ren_overlap as overlap


def metadata():
    selected, schemas = [], {}
    sheet_id = 0
    base, extra = divmod(104190778, 1633)
    for gid in range(113):
        reports = []
        for fragment in range(3 if gid < 60 else 1):
            member = f"g{gid}_{fragment}.xls"
            sheets = []
            # 233*7=1631; add two record sheets to the first member.
            for index in range(9 if gid == fragment == 0 else 7):
                rows = base + (sheet_id < extra)
                sheets.append(dict(index=index, name=f"record_{index+1}", nrows=rows+1))
                sheet_id += 1
            schemas[member] = dict(sheets=sheets)
            reports.append(dict(member_path=member))
        selected.append((f"g{gid}", reports))
    return selected, schemas


def test_complete_coverage_and_fragment_order():
    selected, schemas = metadata()
    groups = f.coverage(selected, schemas)
    assert len(groups) == 113
    assert [s[0] for s in groups[0][1]][:10] == ["g0_0.xls"]*9+["g0_1.xls"]
    assert groups[-1][0] == "g112"


@pytest.mark.parametrize("change", ["group", "file", "sheet", "row", "duplicate"])
def test_coverage_failures(change):
    selected, schemas = metadata()
    if change == "group": selected.pop()
    if change == "file": selected[0][1].pop()
    if change == "sheet": schemas["g0_0.xls"]["sheets"].pop()
    if change == "row": schemas["g0_0.xls"]["sheets"][0]["nrows"] += 1
    if change == "duplicate": selected[0][1][1] = selected[0][1][0]
    with pytest.raises(ValueError, match="coverage"):
        f.coverage(selected, schemas)


def preflight_fixture(monkeypatch, tmp_path):
    selected, schemas = metadata()
    release = dict(status="PASS_OVERLAP_FULL_FLEET", run=f.RUN,
                   policy_sha256={p:"bound" for p in f.POLICY},
                   approval_record_sha256=f.prior.fleet.pilot.context.recovery.APPROVAL_SHA256,
                   pair_budget=f.PAIR_BUDGET, min_free_bytes=f.MIN_FREE)
    hashes = {str(tmp_path/p):"bound" for p in f.POLICY}
    hashes.update({str(tmp_path/f"data/audit/ren_scs/{f.pilot.RUN}/SUMMARY.json"):f.PILOT_SUMMARY_SHA,
                   str(tmp_path/f"data/audit/ren_scs/{f.pilot.RUN}/COMPLETE.json"):f.PILOT_COMPLETE_SHA,
                   str(tmp_path/f.PILOT_REVIEW):f.PILOT_REVIEW_SHA,
                   str(tmp_path/f"data/audit/ren_scs/{f.prior.RUN}/SUMMARY.json"):f.pilot.CHRONOLOGY_SHA})
    monkeypatch.setattr(f.prior.fleet.pilot.context.recovery, "_strict_json", lambda p:release)
    monkeypatch.setattr(f.pipeline, "digest", lambda p:hashes[str(p)])
    monkeypatch.setattr(f.shutil, "disk_usage", lambda p:SimpleNamespace(free=f.MIN_FREE))
    monkeypatch.setattr(f.prior, "preflight", lambda p:(selected,schemas,[]))
    return release, hashes


def test_valid_preflight_selects_all(monkeypatch,tmp_path):
    preflight_fixture(monkeypatch,tmp_path)
    selected, schemas, allowed, groups = f.preflight(tmp_path)
    assert len(selected) == len(groups) == 113


@pytest.mark.parametrize("field", ["status", "run", "policy_sha256", "approval_record_sha256", "pair_budget", "min_free_bytes"])
def test_bad_release_before_prior(monkeypatch,tmp_path,field):
    release,_ = preflight_fixture(monkeypatch,tmp_path)
    release[field] = None
    monkeypatch.setattr(f.prior,"preflight",lambda p:pytest.fail("source preflight called"))
    with pytest.raises(ValueError,match="release"):
        f.preflight(tmp_path)


def test_missing_release_no_output(monkeypatch,tmp_path):
    monkeypatch.setattr(f.prior,"preflight",lambda p:pytest.fail("source preflight called"))
    with pytest.raises(f.prior.fleet.pilot.context.recovery.RecoveryError):
        f.run(tmp_path)
    assert not (tmp_path/"data").exists()


def test_wrong_pilot_and_low_space(monkeypatch,tmp_path):
    _, hashes = preflight_fixture(monkeypatch,tmp_path)
    hashes[str(tmp_path/f.PILOT_REVIEW)] = "changed"
    monkeypatch.setattr(f.prior,"preflight",lambda p:pytest.fail("source preflight called"))
    with pytest.raises(ValueError,match="prerequisite"):
        f.preflight(tmp_path)
    hashes[str(tmp_path/f.PILOT_REVIEW)] = f.PILOT_REVIEW_SHA
    monkeypatch.setattr(f.shutil,"disk_usage",lambda p:SimpleNamespace(free=f.MIN_FREE-1))
    with pytest.raises(ValueError,match="40 GiB"):
        f.preflight(tmp_path)


def test_caller_pipeline_all_groups_and_fragments(monkeypatch,tmp_path):
    rec = f.prior.fleet.pilot.context.recovery
    extraction = tmp_path/"extracted"
    extraction.mkdir()
    selected, schemas, groups = [], {}, []
    for gid in range(3):
        reports, spans = [], []
        for fragment in range(2):
            member = f"{gid}_{fragment}.xls"
            raw = bytes([gid,fragment])
            (extraction/member).write_bytes(raw)
            reports.append(dict(member_path=member,input_bytes=2,input_sha256=hashlib.sha256(raw).hexdigest()))
            schemas[member] = {}
            spans.append((member,0,"record_1",40))
        selected.append((str(gid),reports)); groups.append((str(gid),spans))
    monkeypatch.setattr(f,"preflight",lambda p:(selected,schemas,[],groups))
    monkeypatch.setattr(rec.Paths,"build",lambda *a,**kw:SimpleNamespace(extraction=extraction))
    monkeypatch.setattr(f.prior.fleet.pilot,"workbook_bytes",lambda raw:raw)
    closed=[]
    def records(raw,*args):
        try:
            for i in range(40):
                token=overlap.measurement_token((1,1,0,i,i),[1,1,0,i,"",raw[0]+i/100.,-20.,raw[1]+i/100.])
                yield 0,"record_1",i+2,token,None
        finally:closed.append(tuple(raw))
    monkeypatch.setattr(f.stream,"records",records)
    for path in (tmp_path/"data/raw/ren_scs",tmp_path/"data/audit/ren_scs"):
        path.mkdir(parents=True)
    summary=f.run(tmp_path)
    assert summary["groups"]==3 and summary["rows"]==240 and len(closed)==6
    for flag in f.pipeline.FLAGS: assert summary[flag] is False
