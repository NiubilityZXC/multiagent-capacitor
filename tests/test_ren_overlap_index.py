import sqlite3
import pytest
from experiments.audit_cap import ren_overlap as o
from experiments.audit_cap import ren_overlap_index as d


def token(i):
    return o.measurement_token((1,1,0,i,i*1000),[1,1,0,i,"",i/100.,-20.,i/1000.])


def test_disk_index_shifted_match_and_readback(tmp_path):
    a=[token(i) for i in range(70)]
    b=[token(999)]*5+a[15:55]+[token(888)]*5
    with d.DiskIndex(tmp_path/"index.sqlite") as index:
        index.add(1,len(a),o.winnow(a));index.add(2,len(b),o.winnow(b))
        pairs=list(index.pairs());assert pairs
        confirmed=[d.confirm_anchor(lambda i:(a[i],.2),lambda i:(b[i],.2),len(a),len(b),x,y)
                   for _,x,_,y in pairs]
        assert any(c and c["length"]>=32 for c in confirmed)
        assert all(c is None or c["energy_mismatch_rows"]==0 for c in confirmed)


def test_hash_collision_not_confirmation(tmp_path):
    with d.DiskIndex(tmp_path/"index.sqlite") as index:
        index.add(1,40,[(0,b"x"*32)]);index.add(2,40,[(0,b"x"*32)])
        assert len(list(index.pairs()))==1
        assert d.confirm_anchor(lambda i:(token(i),None),lambda i:(token(i+1),None),40,40,0,0) is None


@pytest.mark.parametrize("energy",[None, .2, .3])
def test_optional_energy_never_hidden(energy):
    result=d.confirm_anchor(lambda i:(token(i),.2),lambda i:(token(i),energy),32,32,10,10)
    assert result["length"]==32
    assert result["energy_missing_rows"]==(32 if energy is None else 0)
    assert result["energy_mismatch_rows"]==(32 if energy==.3 else 0)
    assert not result["physical_identity_verified"]
    assert not result["maximal_extent_verified"]


def test_all_seed_positions_in_exact32():
    for shift in range(25):
        result=d.confirm_anchor(lambda i:(token(i),None),lambda i:(token(i),None),32,32,shift,shift)
        assert result["length"]==32 and result["left_start"]==0


def test_short_near_match_and_invalid_bounds():
    assert d.confirm_anchor(lambda i:(token(i),None),lambda i:(token(i),None),31,31,5,5) is None
    with pytest.raises(ValueError):d.confirm_anchor(None,None,32,32,25,0)


def test_index_atomic_failure_and_append_only(tmp_path):
    path=tmp_path/"index.sqlite"
    with d.DiskIndex(path) as index:
        def broken():
            yield 0,b"x"*32
            raise RuntimeError("upstream read failed")
        with pytest.raises(RuntimeError):index.add(1,40,broken())
        assert index.db.execute("SELECT count(*) FROM groups").fetchone()[0]==0
        assert index.db.execute("SELECT count(*) FROM fingerprints").fetchone()[0]==0
        index.add(2,40,[(0,b"y"*32)])
        with pytest.raises(sqlite3.IntegrityError):index.add(2,40,[])
        assert index.db.execute("SELECT count(*) FROM groups").fetchone()[0]==1
    with pytest.raises(FileExistsError):d.DiskIndex(path)


@pytest.mark.parametrize("values",[[(33,b"x"*32)],[(0,b"x")],[(2,b"x"*32),(1,b"y"*32)],[(True,b"x"*32)]])
def test_bad_fingerprint_rollback(tmp_path,values):
    with d.DiskIndex(tmp_path/"index.sqlite") as index:
        with pytest.raises(ValueError):index.add(1,40,values)
        assert index.db.execute("SELECT count(*) FROM groups").fetchone()[0]==0


def test_all_cross_pairs_no_same_group_or_truncation(tmp_path):
    with d.DiskIndex(tmp_path/"index.sqlite") as index:
        for group in range(3):index.add(group,40,[(i,b"x"*32) for i in range(4)])
        pairs=list(index.pairs())
        assert len(pairs)==3*4*4
        assert all(a<b for a,_,b,_ in pairs)


def test_position_mapping_across_files():
    spans=[("a.xls",2,"record_1",20),("a.xls",3,"record_2",20),("a__1.xls",0,"record_1",20)]
    assert d.source_position(spans,19)==("a.xls",2,"record_1",21)
    assert d.source_position(spans,20)==("a.xls",3,"record_2",2)
    assert d.source_position(spans,40)==("a__1.xls",0,"record_1",2)
    with pytest.raises(ValueError):d.source_position(spans,60)


def test_invalid_readback_raises():
    with pytest.raises(ValueError):
        d.confirm_anchor(lambda i:(token(i),float("nan")),lambda i:(token(i),None),32,32,0,0)


def test_missing_fingerprints_not_success(tmp_path):
    with d.DiskIndex(tmp_path/"index.sqlite") as index:
        with pytest.raises(ValueError,match="missing fingerprints"):index.add(1,32,[])
        assert index.db.execute("SELECT count(*) FROM groups").fetchone()[0]==0
        index.add(2,31,[])  # Explicitly outside the minimum-match guarantee.


def test_synthetic_xls_to_index_to_confirm(tmp_path):
    pytest.importorskip("xlrd",reason="mandatory synthetic end-to-end in audit env")
    from tests.test_ren_measurement_stream import multibook
    from experiments.audit_cap.ren_workbook_reader import schema_rows
    from tests.test_ren_chronology import ALLOWED
    from experiments.audit_cap.ren_measurement_stream import records
    rows=[[1,1,0,i+1,f"0:00:{i:02d}",1+i/100.,-20.,i/1000.] for i in range(40)]
    # Same measurement sequence exported at different worksheet boundaries.
    groups=[]
    for chunks in ([rows[:20],rows[20:]],[rows[:13],rows[13:]]):
        data=multibook(chunks)
        groups.append(list(records(data,ALLOWED,schema_rows(data,ALLOWED))))
    with d.DiskIndex(tmp_path/"index.sqlite") as index:
        for gid,group in enumerate(groups):index.add(gid,len(group),o.winnow(r[3] for r in group))
        matches=[]
        for ga,a,gb,b in index.pairs():
            matches.append(d.confirm_anchor(lambda i:(groups[ga][i][3],groups[ga][i][4]),
                lambda i:(groups[gb][i][3],groups[gb][i][4]),40,40,a,b))
        assert matches and all(m and m["length"]>=32 for m in matches)
        assert all(m["energy_missing_rows"]==m["length"] for m in matches)
