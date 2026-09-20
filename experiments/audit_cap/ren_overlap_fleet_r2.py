"""R2 append-only overlap caller, launched through a detached file-log supervisor."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

if __package__:
    from experiments.audit_cap import ren_overlap_fleet as fleet
    from experiments.audit_cap import durable_local_job as job
else:
    import ren_overlap_fleet as fleet
    import durable_local_job as job

RUN = "overlap_fleet_20260917_r2"
APPROVAL = "refine-logs/REN_OVERLAP_R2_APPROVAL_20260917.md"
POLICY = (*fleet.POLICY, "experiments/audit_cap/durable_local_job.py",
          "tests/test_durable_local_job.py", "experiments/audit_cap/ren_overlap_fleet_r2.py",
          "tests/test_ren_overlap_fleet_r2.py", "refine-logs/REN_OVERLAP_R2_POLICY_20260917.md", APPROVAL)
FAILED_SHA = "4088156530860dd17421312c901371006143f4c23e651eafe828612490811200"
HELPER_REVIEW = "data/raw/ren_scs/durable_launch_review_20260917.md"
HELPER_REVIEW_SHA = "efd405154288624bfda684ce1e41d1dcb9af19ee7c2181cd789ac7d32fb5f9d9"


def release_check(root):
    rec = fleet.prior.fleet.pilot.context.recovery
    release = rec._strict_json(root / "refine-logs/REN_OVERLAP_R2_RELEASE.json")
    if (release.get("status") != "PASS_OVERLAP_R2_INTEGRATION" or release.get("run") != RUN
            or release.get("policy_sha256") != {p:fleet.pipeline.digest(root/p) for p in POLICY}
            or release.get("approval_record_sha256") != rec.APPROVAL_SHA256
            or release.get("r2_approval_sha256") != fleet.pipeline.digest(root/APPROVAL)
            or type(release.get("pair_budget")) is not int or release["pair_budget"] != fleet.PAIR_BUDGET
            or type(release.get("min_free_bytes")) is not int or release["min_free_bytes"] != fleet.MIN_FREE):
        raise ValueError("R2 release mismatch")
    failed = root/"data/audit/ren_scs"/fleet.RUN/"BLOCKED.json"
    if fleet.pipeline.digest(failed) != FAILED_SHA or fleet.pipeline.digest(root/HELPER_REVIEW) != HELPER_REVIEW_SHA:
        raise ValueError("R2 prerequisite mismatch")


def execute(root):
    root = root.resolve(strict=True)
    release_check(root)
    selected, schemas, allowed, groups = fleet.preflight(root)
    rec = fleet.prior.fleet.pilot.context.recovery
    extraction = rec.Paths.build(str(root),fleet.prior.fleet.pilot.context.RUN,new=False).extraction
    # Same frozen source boundary. No mutations of the old caller's RUN/globals.
    def read_group(gid):
        for report in selected[gid][1]:
            member = report["member_path"]
            path = extraction/member
            rec._no_symlink_components(root,path)
            info = rec._require_file(path,"R2 overlap source")
            if info.st_nlink != 1 or info.st_size != report["input_bytes"]:
                raise ValueError("R2 source metadata mismatch")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != report["input_sha256"]:
                raise ValueError("R2 source changed")
            workbook = fleet.prior.fleet.pilot.workbook_bytes(raw)
            del raw
            iterator = fleet.stream.records(workbook,allowed,schemas[member])
            try:
                for record in iterator:
                    yield (member,*record)
            finally:
                iterator.close()
    local = root/"data/raw/ren_scs"/RUN
    public = root/"data/audit/ren_scs"/RUN
    for path in (local,public):
        rec._no_symlink_components(root,path)
    return fleet.pipeline.run_pipeline(local,public,groups,read_group,pair_budget=fleet.PAIR_BUDGET)


def launch(root):
    root = root.resolve(strict=True)
    release_check(root)  # Fail before spawning even the supervisor.
    rec = fleet.prior.fleet.pilot.context.recovery
    directory = root/"data/raw/ren_scs"/(RUN+"_job")
    for path in (directory,root/"data/raw/ren_scs"/RUN,root/"data/audit/ren_scs"/RUN):
        rec._no_symlink_components(root,path)
        if path.exists():
            raise ValueError("R2 attempt is append-only")
    return job.launch([sys.executable,str(Path(__file__).resolve()),"--execute",
                       "--project-root",str(root)],root,directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root",required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--launch",action="store_true")
    mode.add_argument("--execute",action="store_true")
    args = parser.parse_args()
    root = Path(args.project_root)
    result = dict(supervisor_pid=launch(root),status="LAUNCHED_NOT_COMPLETED") if args.launch else execute(root)
    print(json.dumps(result,sort_keys=True),flush=True)
