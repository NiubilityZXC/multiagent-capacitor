import pytest
import struct
from experiments.audit_cap import ren_measurement_stream as m
from experiments.audit_cap import ren_overlap as o
from experiments.audit_cap import ren_chronology as c
from experiments.audit_cap.ren_workbook_reader import schema_rows
from tests.test_ren_chronology import record_workbook, ALLOWED
from tests.test_ren_workbook_reader import bof, rec


@pytest.fixture(autouse=True)
def require_xlrd():
    pytest.importorskip("xlrd", reason="mandatory measurement integration in audit env")


def test_real_workbook_position_projection_energy():
    for energy in (False, True):
        header=c.HEADER+(("energy(mWh)",) if energy else ())
        row=[1,2,0,99,"0:00:02.000",1.5,-20.,.2]+([.3] if energy else [])
        data=record_workbook(header, [row])
        output=list(m.records(data, ALLOWED, schema_rows(data, ALLOWED)))
        assert output==[(0,"record_1",2,o.measurement_token((1,2,0,99,2000000),row),.3 if energy else None)]


@pytest.mark.parametrize("column,value", [(5,"1"),(6,"-20"),(7,"0"),(4,"bad"),(0,1.5),(5,float("nan"))])
def test_invalid_rows_fail_closed(column,value):
    row=[1,1,0,1,"0:00:00",1.,-20.,.2]
    row[column]=value
    data=record_workbook(data_rows=[row])
    with pytest.raises(ValueError):
        list(m.records(data,ALLOWED,schema_rows(data,ALLOWED)))


def test_corrupt_independent_token_rejected(monkeypatch):
    data=record_workbook()
    monkeypatch.setattr(o,"measurement_token",lambda *a: b"x"*40)
    with pytest.raises(ValueError,match="token reconstruction"):
        list(m.records(data,ALLOWED,schema_rows(data,ALLOWED)))


@pytest.mark.parametrize("field,value", [("name","bad"),("nrows",99),("ncols",99),("index",1)])
def test_schema_change_rejected(field,value):
    data=record_workbook();schema=schema_rows(data,ALLOWED)
    schema["sheets"][0][field]=value
    with pytest.raises(ValueError):list(m.records(data,ALLOWED,schema))


def test_hash_before_parser():
    data=record_workbook();schema=schema_rows(data,ALLOWED);schema["workbook_sha256"]="0"*64
    with pytest.raises(ValueError,match="stream mismatch"):
        list(m.records(data,ALLOWED,schema,xlrd_module=object()))


def test_resource_release_on_early_close():
    import xlrd
    data=record_workbook();schema=schema_rows(data,ALLOWED);events=[]
    class Module:
        def open_workbook(self,**kwargs):
            book=xlrd.open_workbook(**kwargs)
            release=book.release_resources;unload=book.unload_sheet
            def close(): events.append("release");release()
            def drop(i): events.append(("unload",i));unload(i)
            book.release_resources=close;book.unload_sheet=drop
            return book
    stream=m.records(data,ALLOWED,schema,Module())
    next(stream);stream.close()
    assert events[-2:]==[("unload",0),"release"]


def test_invalid_energy_not_discarded():
    data=record_workbook(c.HEADER+("energy(mWh)",),[[1,1,0,1,"0:00:00",1.,-20.,.2,"bad"]])
    with pytest.raises(ValueError,match="numeric cell"):
        list(m.records(data,ALLOWED,schema_rows(data,ALLOWED)))


def multibook(chunks):
    bodies=[]
    for chunk in chunks:
        data=record_workbook(data_rows=chunk);offset=0
        while offset<len(data):
            kind,size=struct.unpack_from("<HH",data,offset)
            if kind==0x0809 and struct.unpack_from("<H",data,offset+6)[0]==16:
                bodies.append(data[offset:]);break
            offset+=4+size
    prefix=bof()+rec(0x0042,struct.pack("<H",1200))+rec(0x0022,b"\0\0")
    def bound(i,offset):
        name=f"record_{i+1}".encode()
        return rec(0x0085,struct.pack("<IBBBB",offset,0,0,len(name),0)+name)
    offset=len(prefix)+sum(len(bound(i,0)) for i in range(len(bodies)))+4
    bounds=[]
    for i,body in enumerate(bodies):bounds.append(bound(i,offset));offset+=len(body)
    return prefix+b"".join(bounds)+rec(0x000A)+b"".join(bodies)


def test_real_multisheet_preserves_cross_boundary_match():
    rows=[[1,1,0,i+1,f"0:00:{i:02d}",1+i/100.,-20.,i/1000.] for i in range(40)]
    data=multibook([rows[:20],rows[20:]])
    output=list(m.records(data,ALLOWED,schema_rows(data,ALLOWED)))
    assert len(output)==40
    assert output[19][:3]==(0,"record_1",21)
    assert output[20][:3]==(1,"record_2",2)
    # Neither isolated 20-row sheet produces a candidate; continuous stream does.
    assert list(o.winnow(x[3] for x in output[:20]))==[]
    assert list(o.winnow(x[3] for x in output[20:]))==[]
    assert list(o.winnow(x[3] for x in output))


def test_late_failure_cannot_be_mistaken_for_exhaustion():
    good=[1,1,0,1,"0:00:00",1.,-20.,.2]
    bad=[1,1,0,2,"0:00:01",1.,"-20",.2]
    data=multibook([[good],[bad]])
    stream=m.records(data,ALLOWED,schema_rows(data,ALLOWED))
    assert next(stream)[:3]==(0,"record_1",2)
    with pytest.raises(ValueError,match="numeric cell"):
        next(stream)


@pytest.mark.parametrize("reserved", ["step", "cycle"])
@pytest.mark.parametrize("sheet_index", [0, 1])
def test_reserved_schema_name_cannot_hide_record_sheet(reserved,sheet_index):
    row=[1,1,0,1,"0:00:00",1.,-20.,.2]
    data=multibook([[row],[row]])
    schema=schema_rows(data,ALLOWED)
    schema["sheets"][sheet_index]["name"]=reserved
    with pytest.raises(ValueError,match="dimensions mismatch"):
        list(m.records(data,ALLOWED,schema))
