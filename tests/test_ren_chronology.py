from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import struct
from types import SimpleNamespace

import pytest

from experiments.audit_cap import ren_chronology as c
from experiments.audit_cap import ren_chronology_gate as gate
from experiments.audit_cap.ren_workbook_reader import schema_rows
from tests.test_ren_workbook_reader import ALLOWED, bof, rec


@pytest.mark.parametrize("text,expected", [("0:00:00.000",0), ("1:02:03.4",3723400000),
    ("25:00:00",90000000000), ("0:00:00.000001",1), ("0:59:59.999999",3599999999)])
def test_clock_exact_microseconds(text, expected):
    assert c.clock_us(text) == expected


@pytest.mark.parametrize("text", [None, 0, "", "0:60:00", "0:00:60", "-1:00:00",
    "0:00:00.1234567", "0:0:00", "0:00:00x", "0:00:00\n", "0:00:00."])
def test_clock_rejects_ambiguous_values(text):
    assert c.clock_us(text) is None


def test_known_anomalies_and_invalid_break():
    keys = [(1,1,1,1,0),(1,1,1,2,10),(1,1,1,4,5),(1,1,1,4,5),
            (0,2,-1,3,0),None,(2,1,0,5,0)]
    result = c.reduce_keys(keys)
    assert result == c.reference_reduce(keys)
    expected = dict(rows=7, invalid_key_rows=1, valid_adjacent_pairs=4, record_nonunit=3,
        record_repeats=1, record_backwards=1, record_forward_gaps=1, missing_record_numbers=1,
        cycle_backwards=1, step_changes=1, time_decreases=2, same_step_time_decreases=1,
        adjacent_duplicate_keys=1, negative_identifier_rows=0)
    for k,v in expected.items(): assert result[k] == v
    assert result["status_counts"] == {"1":4,"-1":1,"0":1}


def test_deterministic_randomized_independent_reductions():
    rng = random.Random(20260914)
    for _ in range(300):
        keys = [None if rng.random()<.12 else tuple(rng.randrange(-1,10) for _ in range(5))
                for _ in range(rng.randrange(0,90))]
        c.verify_fields(c.reduce_keys(iter(keys)), c.reference_reduce(iter(keys)))


@pytest.mark.parametrize("field", [*c.TRANSITIONS,"rows","invalid_key_rows","negative_identifier_rows",
                                  "first_key","last_key","status_counts"])
def test_each_reconstructed_field_mismatch_is_rejected(field):
    keys=[(1,1,0,1,0),(1,1,0,2,100)]
    observed=c.reduce_keys(keys); observed[field]="tampered"
    with pytest.raises(ValueError): c.verify_fields(observed,c.reference_reduce(keys))


def test_boundaries_are_counted_without_connecting_across_invalid_rows():
    first = c.reduce_keys([(1,1,1,1,1),(1,1,1,2,2)])
    second = c.reduce_keys([(1,2,0,4,0),(1,2,0,5,1)])
    total = c.aggregate([first,second])
    assert total["rows"]==4 and total["valid_adjacent_pairs"]==3
    assert total["nonunit_record_boundaries"]==1 and total["missing_record_numbers"]==1
    assert total["time_decreases"]==1 and total["same_step_time_decreases"]==0
    first["last_key"] = None
    total = c.aggregate([first,second])
    assert total["invalid_key_boundaries"]==1 and total["nonunit_record_boundaries"]==0


class Sheet:
    def __init__(self, values, kinds=None):
        self.values = values
        self.kinds = kinds or [2,2,2,2,1]
    def cell(self,row,col): return SimpleNamespace(value=self.values[col], ctype=self.kinds[col])
    def row_values(self,row): return self.values
    def row_types(self,row): return self.kinds


@pytest.mark.parametrize("value", [None, "1", 1.5, float("nan"), float("inf"), 2**54, True])
def test_both_accessors_reject_invalid_identifier(value):
    sheet = Sheet([value,1,0,1,"0:00:00"])
    assert c.key_from_cells(sheet,1) is None and c.reference_key(sheet,1) is None


def test_both_accessors_keep_negative_status_and_exact_time():
    sheet = Sheet([1.0,2.0,-1.0,123.0,"28:32:12.1234"])
    expected=(1,2,-1,123,102732123400)
    assert c.key_from_cells(sheet,1)==expected==c.reference_key(sheet,1)


def record_workbook(header=c.HEADER, data_rows=None):
    if data_rows is None:
        data_rows=[[1,1,1,1,"0:00:00.000",1,1,1], [1,1,1,2,"0:00:01.000",1,1,1]]
    prefix=bof()+rec(0x0042,struct.pack("<H",1200))+rec(0x0022,b"\0\0")
    name=b"record_1"
    def bound(offset): return rec(0x0085,struct.pack("<IBBBB",offset,0,0,len(name),0)+name)
    offset=len(prefix)+len(bound(0))+4
    body=bof(16)+rec(0x0200,struct.pack("<IIHHH",0,len(data_rows)+1,0,len(header),0))
    for row, values in enumerate([header,*data_rows]):
        for col,value in enumerate(values):
            if isinstance(value,str):
                encoded=value.encode("ascii")
                body+=rec(0x0204,struct.pack("<HHHHB",row,col,0,len(encoded),0)+encoded)
            else:
                body+=rec(0x0203,struct.pack("<HHHd",row,col,0,value))
    return prefix+bound(offset)+rec(0x000A)+body+rec(0x000A)


@pytest.fixture
def real_book():
    pytest.importorskip("xlrd", reason="mandatory chronology integration in audit venv")
    data=record_workbook()
    return data,schema_rows(data,ALLOWED)


def test_real_raw_workbook_chronology(real_book):
    data,schema=real_book
    result=c.workbook(data,ALLOWED,schema)
    assert len(result)==1 and result[0]["rows"]==2 and result[0]["valid_adjacent_pairs"]==1
    assert result[0]["record_nonunit"]==0
    assert result[0]["first_key"]==[1,1,1,1,0]


def test_real_nine_column_schema_and_invalid_clock_count(real_book):
    data=record_workbook(header=c.HEADER+("energy(mWh)",),data_rows=[
        [1,1,1,1,"invalid",1,1,1,1], [1,1,1,2,"0:00:01",1,1,1,1]])
    result=c.workbook(data,ALLOWED,schema_rows(data,ALLOWED))[0]
    assert result["rows"]==2 and result["invalid_key_rows"]==1
    assert result["valid_adjacent_pairs"]==0 and result["first_key"] is None


def test_actual_reference_divergence_stops_before_reporting(monkeypatch,real_book):
    data,schema=real_book
    real=c.reference_reduce
    def corrupt(keys):
        out=real(keys); out["rows"]+=1; return out
    monkeypatch.setattr(c,"reference_reduce",corrupt)
    with pytest.raises(ValueError,match="rebuilt schema mismatch"): c.workbook(data,ALLOWED,schema)


def test_unrecognized_header_fails_without_column_relabeling(real_book):
    data=record_workbook(header=("unknown",)+c.HEADER[1:])
    with pytest.raises(ValueError,match="units/header"): c.workbook(data,ALLOWED,schema_rows(data,ALLOWED))


def test_changed_stream_before_parser(real_book):
    data,schema=real_book; schema["workbook_sha256"]="0"*64
    with pytest.raises(ValueError,match="stream mismatch"): c.workbook(data,ALLOWED,schema)


def test_name_grouping_orders_fragments_numerically_and_not_as_devices():
    names=["batch3/1__2.xls","batch3/1.xls","batch3/1__1.xls"]
    reports=[{"member_path":n} for n in names]
    schemas={n:{"sheets":[{"name":s} for s in (["record_1"] if "__" in n else ["step","cycle","record_1"])]} for n in names}
    groups=gate.candidate_groups(reports,schemas)
    assert [r["member_path"] for r in groups[0][1]]==[names[1],names[2],names[0]]
    with pytest.raises(ValueError,match="missing"): gate.candidate_groups(reports[:2],schemas)
    with pytest.raises(ValueError,match="repeated"): gate.candidate_groups(reports+reports[:1],schemas)


def test_missing_release_stops_before_inherited_preflight(monkeypatch,tmp_path):
    monkeypatch.setattr(gate.fleet,"preflight",lambda *a: pytest.fail("no authorization"))
    with pytest.raises(gate.fleet.pilot.context.recovery.RecoveryError): gate.run(tmp_path)


def synthetic_fleet(monkeypatch,root,data,schema):
    extraction=root/"synthetic_extraction"; extraction.mkdir()
    groups=[]; schemas={}; digest=hashlib.sha256(data).hexdigest()
    for group in range(113):
        reports=[]
        for frag in range(1 if group<53 else 3):
            name=f"g{group}_{frag}.xls"; (extraction/name).write_bytes(data)
            schemas[name]=schema
            reports.append(dict(member_path=name,input_bytes=len(data),input_sha256=digest))
        groups.append((f"synthetic/{group}",reports))
    for p in ("data/raw/ren_scs","data/audit/ren_scs"): (root/p).mkdir(parents=True)
    monkeypatch.setattr(gate,"preflight",lambda r:(groups,schemas,ALLOWED))
    monkeypatch.setattr(gate.fleet.pilot.context.recovery.Paths,"build",lambda *a,**k:SimpleNamespace(extraction=extraction))
    monkeypatch.setattr(gate.fleet.pilot,"workbook_bytes",lambda raw:raw)


def test_full_caller_all_113_groups_and_233_files(monkeypatch,tmp_path,real_book):
    data,schema=real_book; synthetic_fleet(monkeypatch,tmp_path,data,schema)
    result=gate.run(tmp_path)
    assert result["member_count"]==233 and result["source_naming_candidates"]==113
    assert result["metrics"]["rows"]==466 and result["p2_eligible"] is False
    assert result["metrics"]["record_backwards"]==120  # synthetic repeated fragments, not repaired
    with pytest.raises(ValueError,match="append-only"): gate.run(tmp_path)


def test_missing_sheet_coverage_fails_closed(monkeypatch,tmp_path,real_book):
    data,schema=real_book; synthetic_fleet(monkeypatch,tmp_path,data,schema)
    monkeypatch.setattr(gate,"read_member",lambda *a:[])
    with pytest.raises(ValueError,match="coverage mismatch"): gate.run(tmp_path)
    public=tmp_path/"data/audit/ren_scs"/gate.RUN
    assert (public/"BLOCKED.json").exists() and not (public/"COMPLETE.json").exists()


def test_persisted_receipt_corruption_cannot_yield_complete(monkeypatch,tmp_path,real_book):
    data,schema=real_book; synthetic_fleet(monkeypatch,tmp_path,data,schema)
    recmod=gate.fleet.pilot.context.recovery; writer=recmod._write_json
    def corrupt(path,value):
        if path.name=="001.json" and "data/audit/" in str(path):
            value=deepcopy(value); value["metrics"]["rows"]+=1
        return writer(path,value)
    monkeypatch.setattr(recmod,"_write_json",corrupt)
    with pytest.raises(ValueError,match="rebuilt schema mismatch"): gate.run(tmp_path)
    public=tmp_path/"data/audit/ren_scs"/gate.RUN
    assert json.loads((public/"BLOCKED.json").read_text())["failed_candidate"]=="synthetic/0"
    assert not (public/"COMPLETE.json").exists()
