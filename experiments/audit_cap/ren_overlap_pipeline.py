"""Append-only local overlap pipeline; caller supplies approved source streams.

No real-source CLI here. Binary measurements stay in the caller's ignored dir.
Completion is observation-only, never target or physical-identity eligibility.
"""
from collections import deque
from contextlib import ExitStack
import hashlib
from itertools import zip_longest
import json
import math
import struct

if __package__:
    from experiments.audit_cap import ren_overlap as overlap
    from experiments.audit_cap import ren_overlap_index as search
else:
    import ren_overlap as overlap
    import ren_overlap_index as search

RECORD = struct.Struct(">40sBd")
FLAGS = dict(model_or_api_executed=False,numeric_target_emitted=False,
             physical_identity_verified=False,target_verified=False,p2_eligible=False,
             automatic_next_stage=False,cross_group_partial_overlap_verified=False)


def write_json(path, value):
    with path.open("x",encoding="utf-8") as handle:
        json.dump(value,handle,sort_keys=True,allow_nan=False)
        handle.write("\n")


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,allow_nan=False)


def unpack(data):
    if len(data)!=RECORD.size:
        raise ValueError("truncated measurement spool")
    token,present,energy=RECORD.unpack(data)
    status,time,v,i,q=struct.unpack(">qqddd",token)
    if present not in (0,1) or time<0 or not all(math.isfinite(n) for n in (v,i,q,energy)):
        raise ValueError("invalid measurement spool")
    if not present and energy!=0:
        raise ValueError("invalid absent-energy representation")
    return token,energy if present else None


def spool_tokens(path):
    with path.open("rb") as handle:
        while data:=handle.read(RECORD.size):
            yield unpack(data)[0]


def reference_fingerprints(tokens):
    """Independent bounded window-min selection, not production deque logic."""
    recent=deque(maxlen=overlap.K);windows=deque(maxlen=overlap.WINDOW)
    previous=-1
    for row,token in enumerate(tokens):
        recent.append(token)
        if len(recent)!=overlap.K:continue
        position=row-overlap.K+1
        windows.append((position,hashlib.sha256(b"".join(recent)).digest()))
        if len(windows)==overlap.WINDOW:
            chosen=min(windows,key=lambda item:(item[1],-item[0]))
            if chosen[0]!=previous:
                yield chosen
                previous=chosen[0]


def verify_index(index,gid,path,rows):
    if path.stat().st_size!=rows*RECORD.size:
        raise ValueError("spool row count mismatch")
    stored=index.db.execute("SELECT offset,digest FROM fingerprints WHERE gid=? ORDER BY offset",(gid,))
    try:
        for expected,actual in zip_longest(reference_fingerprints(spool_tokens(path)),stored):
            if expected!=actual:raise ValueError("independent index mismatch")
    finally:
        stored.close()


def reference_match(read_left,read_right,nleft,nright,a,b):
    lo=max(-24,-a,-b);hi=min(32,nleft-a,nright-b)
    pairs={shift:(read_left(a+shift),read_right(b+shift)) for shift in range(lo,hi)}
    if any(pairs[s][0][0]!=pairs[s][1][0] for s in range(8)):return None
    start=0;end=8
    while start>lo and pairs[start-1][0][0]==pairs[start-1][1][0]:start-=1
    while end<hi and pairs[end][0][0]==pairs[end][1][0]:end+=1
    if end-start<32:return None
    energies=[(pairs[s][0][1],pairs[s][1][1]) for s in range(start,end)]
    missing=sum(x is None or y is None for x,y in energies)
    return dict(left_start=a+start,right_start=b+start,length=end-start,
        energy_compared_rows=len(energies)-missing,energy_missing_rows=missing,
        energy_mismatch_rows=sum(x is not None and y is not None and x!=y for x,y in energies),
        maximal_extent_verified=False,physical_identity_verified=False)


def match_document(groups,ga,gb,match):
    return dict(left_group=groups[ga][0],right_group=groups[gb][0],
        left_position=search.source_position(groups[ga][1],match["left_start"]),
        right_position=search.source_position(groups[gb][1],match["right_start"]),**match)


def run_pipeline(local,public,groups,read_group,*,pair_budget=1000000):
    """groups = ordered (name, spans); read_group(gid) yields source position + values.

    spans: (member,index,sheet_name,data_rows). Source rows must exactly exhaust
    these spans in order. read_group yields (member,index,name,XLS_row,token,energy).
    Caller must freeze group selection, budgets, paths and source identity first.
    """
    if type(pair_budget) is not int or pair_budget<1 or not groups:
        raise ValueError("invalid pipeline plan")
    if len({name for name,_ in groups})!=len(groups):raise ValueError("duplicate group")
    for _,spans in groups:
        if not spans or any(type(s[3]) is not int or s[3]<1 for s in spans):
            raise ValueError("invalid coverage spans")
    if local.exists() or public.exists():raise ValueError("append-only overlap run")
    local.mkdir(mode=0o700);public.mkdir()
    current=None;completed=0
    try:
        with search.DiskIndex(local/"index.sqlite") as index:
            evidence=[]
            for gid,(name,spans) in enumerate(groups):
                current=name;rows=sum(s[3] for s in spans);path=local/f"{gid:03d}.bin"
                generated_hash=hashlib.sha256()
                def tokens():
                    source=iter(read_group(gid));sentinel=object()
                    try:
                        with path.open("xb") as handle:
                            for member,sheet_index,sheet_name,n in spans:
                                for row in range(2,n+2):
                                    value=next(source,sentinel)
                                    if value is sentinel or tuple(value[:4])!=(member,sheet_index,sheet_name,row):
                                        raise ValueError("source row coverage mismatch")
                                    if len(value)!=6:raise ValueError("source row shape")
                                    token,energy=value[4:]
                                    if type(token) is not bytes or len(token)!=40:
                                        raise ValueError("invalid source token")
                                    if energy is not None and (type(energy) not in (int,float) or not math.isfinite(energy)):
                                        raise ValueError("invalid source energy")
                                    data=RECORD.pack(token,int(energy is not None),0.0 if energy is None else energy)
                                    unpack(data)
                                    handle.write(data);generated_hash.update(data)
                                    yield token
                            if next(source,sentinel) is not sentinel:
                                raise ValueError("extra source rows")
                    finally:
                        close=getattr(source,"close",None)
                        if close:close()
                index.add(gid,rows,overlap.winnow(tokens()))
                if digest(path)!=generated_hash.hexdigest():raise ValueError("spool write mismatch")
                verify_index(index,gid,path,rows)
                document=dict(group=name,spans=spans,rows=rows,spool_sha256=digest(path),**FLAGS)
                write_json(local/f"{gid:03d}.json",document)
                evidence.append(document);completed+=1
                print(json.dumps(dict(groups_indexed=completed,groups_expected=len(groups))),flush=True)
            counts=dict(candidate_pairs=0,confirmed_projected_spans=0,
                        spans_with_energy_missing=0,spans_with_energy_mismatch=0)
            with ExitStack() as stack:
                handles=[stack.enter_context((local/f"{gid:03d}.bin").open("rb")) for gid in range(len(groups))]
                def read(gid,position):
                    if not 0<=position<evidence[gid]["rows"]:raise ValueError("readback bounds")
                    handles[gid].seek(position*RECORD.size)
                    return unpack(handles[gid].read(RECORD.size))
                with (local/"matches.jsonl").open("x",encoding="utf-8") as matches:
                    for ga,a,gb,b in index.pairs():
                        current=f"pair:{ga}:{a}/{gb}:{b}"
                        counts["candidate_pairs"]+=1
                        if counts["candidate_pairs"]>pair_budget:
                            raise ValueError("candidate budget exceeded, no completion")
                        match=search.confirm_anchor(lambda pos:read(ga,pos),lambda pos:read(gb,pos),
                            evidence[ga]["rows"],evidence[gb]["rows"],a,b)
                        if match is None:continue
                        result=match_document(groups,ga,gb,match)
                        matches.write(json.dumps(result,sort_keys=True,allow_nan=False)+"\n")
                        counts["confirmed_projected_spans"]+=1
                        counts["spans_with_energy_missing"]+=int(match["energy_missing_rows"]>0)
                        counts["spans_with_energy_mismatch"]+=int(match["energy_mismatch_rows"]>0)
                rebuilt=dict.fromkeys(counts,0)
                with (local/"matches.jsonl").open(encoding="utf-8") as matches:
                    for ga,a,gb,b in index.pairs():
                        current=f"verify-pair:{ga}:{a}/{gb}:{b}"
                        rebuilt["candidate_pairs"]+=1
                        if rebuilt["candidate_pairs"]>pair_budget:raise ValueError("verification budget exceeded")
                        match=reference_match(lambda pos:read(ga,pos),lambda pos:read(gb,pos),
                            evidence[ga]["rows"],evidence[gb]["rows"],a,b)
                        if match is None:continue
                        line=matches.readline()
                        expected=match_document(groups,ga,gb,match)
                        if not line or canonical(json.loads(line))!=canonical(expected):
                            raise ValueError("independent match ledger mismatch")
                        rebuilt["confirmed_projected_spans"]+=1
                        rebuilt["spans_with_energy_missing"]+=int(match["energy_missing_rows"]>0)
                        rebuilt["spans_with_energy_mismatch"]+=int(match["energy_mismatch_rows"]>0)
                    if matches.read(1):raise ValueError("extra match ledger rows")
                if counts!=rebuilt:raise ValueError("independent match count mismatch")
            # Reconcile persisted inputs/index again before writing completion.
            for gid,expected in enumerate(evidence):
                current=expected["group"]
                saved=json.loads((local/f"{gid:03d}.json").read_text())
                normalized=json.loads(json.dumps(expected))
                if canonical(saved)!=canonical(normalized) or digest(local/f"{gid:03d}.bin")!=expected["spool_sha256"]:
                    raise ValueError("persisted evidence mismatch")
                verify_index(index,gid,local/f"{gid:03d}.bin",expected["rows"])
            sql_groups=list(index.db.execute("SELECT gid,rows FROM groups ORDER BY gid"))
            if sql_groups!=[(gid,e["rows"]) for gid,e in enumerate(evidence)]:
                raise ValueError("persisted group coverage mismatch")
        # Published numbers describe generated candidate spans, not unique overlap
        # events or devices. Match ledger remains ignored, pending post-run review.
        summary=dict(status="OVERLAP_OBSERVATIONS_NOT_DATA_GATE",groups=len(groups),
            rows=sum(e["rows"] for e in evidence),**counts,**FLAGS,
            index_sha256=digest(local/"index.sqlite"),matches_sha256=digest(local/"matches.jsonl"))
        write_json(public/"SUMMARY.json",summary)
        write_json(public/"COMPLETE.json",dict(status="OVERLAP_COMPLETE_NOT_DATA_GATE",
            summary_sha256=digest(public/"SUMMARY.json"),**FLAGS))
        return summary
    except Exception as exc:
        write_json(public/"BLOCKED.json",dict(status="OVERLAP_FAILED_CLOSED",group=current,
            groups_indexed=completed,error_type=type(exc).__name__,**FLAGS))
        raise
