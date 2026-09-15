"""Frozen first-two-source-candidate pilot, no final Data Gate or models."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

if __package__:
    from experiments.audit_cap import ren_chronology_gate as prior
    from experiments.audit_cap import ren_measurement_stream as stream
    from experiments.audit_cap import ren_overlap_pipeline as pipeline
else:
    import ren_chronology_gate as prior
    import ren_measurement_stream as stream
    import ren_overlap_pipeline as pipeline

RUN="overlap_pilot_20260915_v1"
POLICY=(*prior.POLICY,"experiments/audit_cap/ren_overlap.py",
    "experiments/audit_cap/ren_measurement_stream.py","experiments/audit_cap/ren_overlap_index.py",
    "experiments/audit_cap/ren_overlap_pipeline.py","experiments/audit_cap/ren_overlap_pilot.py",
    "tests/test_ren_overlap.py","tests/test_ren_measurement_stream.py",
    "tests/test_ren_overlap_index.py","tests/test_ren_overlap_pipeline.py",
    "refine-logs/REN_OVERLAP_PILOT_POLICY_20260915.md")
CHRONOLOGY_SHA="90600e3546069a0be49d3599ecf41a91ab6205d77f91b98c332305994147fe40"
PAIR_BUDGET=1000000


def preflight(root):
    rec=prior.fleet.pilot.context.recovery
    release=rec._strict_json(root/"refine-logs/REN_OVERLAP_PILOT_RELEASE.json")
    if (release.get("status")!="PASS_OVERLAP_FIRST_TWO_PILOT"
        or release.get("policy_sha256")!={p:pipeline.digest(root/p) for p in POLICY}
        or release.get("approval_record_sha256")!=rec.APPROVAL_SHA256
        or release.get("pair_budget")!=PAIR_BUDGET):
        raise ValueError("overlap pilot release mismatch")
    groups,schemas,allowed=prior.preflight(root)
    public=root/"data/audit/ren_scs"/prior.RUN
    if pipeline.digest(public/"SUMMARY.json")!=CHRONOLOGY_SHA:
        raise ValueError("chronology prerequisite mismatch")
    complete=rec._strict_json(public/"COMPLETE.json")
    if complete.get("summary_sha256")!=CHRONOLOGY_SHA or complete.get("status")!="CHRONOLOGY_COMPLETE_NOT_DATA_GATE":
        raise ValueError("chronology prerequisite incomplete")
    if [g[0] for g in groups[:2]]!=["batch1/1","batch1/2"]:
        raise ValueError("pilot selection mismatch")
    if shutil.disk_usage(root).free<2*1024**3:
        raise ValueError("pilot requires 2 GiB free")
    return groups[:2],schemas,allowed


def run(root):
    root=root.resolve(strict=True)
    selected,schemas,allowed=preflight(root)
    rec=prior.fleet.pilot.context.recovery
    extraction=rec.Paths.build(str(root),prior.fleet.pilot.context.RUN,new=False).extraction
    groups=[]
    for name,reports in selected:
        spans=[(r["member_path"],s["index"],s["name"],s["nrows"]-1)
               for r in reports for s in schemas[r["member_path"]]["sheets"] if s["name"] not in ("step","cycle")]
        groups.append((name,spans))
    def read_group(gid):
        for report in selected[gid][1]:
            member=report["member_path"];path=extraction/member
            rec._no_symlink_components(root,path)
            info=rec._require_file(path,"overlap pilot source")
            if info.st_nlink!=1 or info.st_size!=report["input_bytes"]:
                raise ValueError("overlap input metadata mismatch")
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=report["input_sha256"]:
                raise ValueError("overlap input changed")
            workbook=prior.fleet.pilot.workbook_bytes(raw);del raw
            iterator=stream.records(workbook,allowed,schemas[member])
            try:
                for record in iterator:yield (member,*record)
            finally:
                iterator.close()
    local=root/"data/raw/ren_scs"/RUN
    public=root/"data/audit/ren_scs"/RUN
    for p in (local,public):rec._no_symlink_components(root,p)
    return pipeline.run_pipeline(local,public,groups,read_group,pair_budget=PAIR_BUDGET)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root",required=True)
    print(json.dumps(run(Path(parser.parse_args().project_root)),sort_keys=True))
