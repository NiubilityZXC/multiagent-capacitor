"""Real OLE -> isolated BIFF -> saved JSON -> independent rebuild integration.

Uses the current audit interpreter (olefile/xlrd), never a real dataset.
The container is generated from a completely synthetic >=4096-byte Workbook.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from tests.test_ren_target_workbook import book, fixture
from tests.test_ren_workbook_reader import ALLOWED


def ole_container(payload):
    assert 4096 <= len(payload) <= 126*512
    end, free, fat = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD
    sectors = (len(payload) + 511)//512
    header = bytearray(512)
    header[:8] = bytes.fromhex('d0cf11e0a1b11ae1')
    struct.pack_into('<HHHHH',header,24,0x003e,3,0xfffe,9,6)
    struct.pack_into('<IIIIIIIII',header,40,0,1,1,0,4096,end,0,end,0)
    struct.pack_into('<109I',header,76,0,*([free]*108))
    allocation = [fat,end] + [i+3 for i in range(sectors)]
    allocation[-1] = end
    fat_sector = struct.pack('<128I',*(allocation+[free]*(128-len(allocation))))
    def entry(name, kind, child, start, size):
        raw = bytearray(128)
        encoded = (name+'\0').encode('utf-16le')
        raw[:len(encoded)] = encoded
        struct.pack_into('<HBBIII',raw,64,len(encoded),kind,1,free,free,child)
        struct.pack_into('<IQ',raw,116,start,size)
        return bytes(raw)
    directory = entry('Root Entry',5,1,end,0)+entry('Workbook',2,free,2,len(payload))+bytes(256)
    return bytes(header)+fat_sector+directory+payload.ljust(sectors*512,b'\0')


@pytest.mark.parametrize('extended',[False,True])
def test_real_ole_source_persisted_roundtrip(tmp_path, extended):
    root = Path(__file__).resolve().parents[1]
    pytest.importorskip('olefile', reason='mandatory real OLE integration in audit env')
    python = sys.executable
    sheets = fixture(extended)
    template = sheets[2][2][0]
    sheets[2][2][:] = [template[:3]+[i+10]+template[4:] for i in range(200)]
    payload = book(sheets)
    container = ole_container(payload)
    extraction = tmp_path/'extracted'
    (extraction/'batch1').mkdir(parents=True)
    (extraction/'batch1/1.xls').write_bytes(container)
    config = dict(root=str(tmp_path),extraction=str(extraction),allowed=sorted(ALLOWED),
        container_sha=hashlib.sha256(container).hexdigest(),stream_sha=hashlib.sha256(payload).hexdigest())
    script = '''
import hashlib,json,sys
from pathlib import Path
from experiments.audit_cap.ren_workbook_reader import workbook_bytes,schema_rows
from experiments.audit_cap.ren_target_source import collect_source_group,verify_source_group
c=json.load(sys.stdin); root=Path(c['root']); extraction=Path(c['extraction'])
raw=(extraction/'batch1/1.xls').read_bytes(); data=workbook_bytes(raw)
assert hashlib.sha256(data).hexdigest()==c['stream_sha']
schema=schema_rows(data,set(c['allowed']))
report=dict(member_path='batch1/1.xls',input_bytes=len(raw),input_sha256=c['container_sha'],workbook_scans=[dict(stream_sha256=c['stream_sha'])])
args=(root,extraction,'batch1/1',[report],{'batch1/1.xls':schema},set(c['allowed']))
out=collect_source_group(*args)
p=root/'evidence.json'; p.write_text(json.dumps(out,allow_nan=False))
saved=json.loads(p.read_text()); verify_source_group(saved,*args)
assert saved['segments'][0]['rows']==200 and saved['data_gate_pass'] is False
saved['segments'][0]['current_min_mA']+=1
try: verify_source_group(saved,*args)
except ValueError: pass
else: raise AssertionError('persisted corruption accepted')
print(json.dumps(dict(records=200,real_ole=True,verified=True,data_gate_pass=False)))
'''
    result = subprocess.run([str(python),'-c',script],cwd=root,input=json.dumps(config),
                            text=True,capture_output=True,timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == dict(records=200,real_ole=True,verified=True,data_gate_pass=False)

