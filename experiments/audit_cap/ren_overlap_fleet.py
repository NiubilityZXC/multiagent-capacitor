"""Full-fleet P1 overlap observations. No targets, forecasts or final Data Gate."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

if __package__:
    from experiments.audit_cap import ren_overlap_pilot as pilot
else:
    import ren_overlap_pilot as pilot

prior, pipeline, stream = pilot.prior, pilot.pipeline, pilot.stream
RUN = "overlap_fleet_20260915_v1"
PAIR_BUDGET = 1000000
MIN_FREE = 40 * 1024**3
POLICY = (*pilot.POLICY, "experiments/audit_cap/ren_overlap_fleet.py",
          "tests/test_ren_overlap_fleet.py", "refine-logs/REN_OVERLAP_FLEET_POLICY_20260915.md")
PILOT_SUMMARY_SHA = "c1544ff993feedf4a7513562879c1a7a9032a596c68f8e63379a3cb3b7d263a9"
PILOT_COMPLETE_SHA = "b7be7a9152ad089838c9ec084bfcd981443c69a600eea952c5253937f98ca725"
PILOT_REVIEW = "data/raw/ren_scs/overlap_pilot_postrun_response_20260915.md"
PILOT_REVIEW_SHA = "793f85eda334afdd5270939674e2258fa8361b5a312ae23fc4791666367257cf"


def coverage(selected, schemas):
    groups = []
    members = []
    for name, reports in selected:
        spans = []
        for report in reports:
            member = report["member_path"]
            members.append(member)
            spans.extend((member, s["index"], s["name"], s["nrows"] - 1)
                         for s in schemas[member]["sheets"] if s["name"] not in ("step", "cycle"))
        groups.append((name, spans))
    if (len(groups) != 113 or len({g[0] for g in groups}) != 113
            or len(members) != 233 or len(set(members)) != 233
            or sum(len(g[1]) for g in groups) != 1633
            or sum(s[3] for _, spans in groups for s in spans) != 104190778):
        raise ValueError("full fleet coverage mismatch")
    return groups


def preflight(root):
    rec = prior.fleet.pilot.context.recovery
    release = rec._strict_json(root / "refine-logs/REN_OVERLAP_FLEET_RELEASE.json")
    if (release.get("status") != "PASS_OVERLAP_FULL_FLEET"
            or release.get("run") != RUN
            or release.get("policy_sha256") != {p: pipeline.digest(root / p) for p in POLICY}
            or release.get("approval_record_sha256") != rec.APPROVAL_SHA256
            or type(release.get("pair_budget")) is not int or release["pair_budget"] != PAIR_BUDGET
            or type(release.get("min_free_bytes")) is not int or release["min_free_bytes"] != MIN_FREE):
        raise ValueError("full fleet release mismatch")
    for relative, expected in (
            (f"data/audit/ren_scs/{pilot.RUN}/SUMMARY.json", PILOT_SUMMARY_SHA),
            (f"data/audit/ren_scs/{pilot.RUN}/COMPLETE.json", PILOT_COMPLETE_SHA),
            (PILOT_REVIEW, PILOT_REVIEW_SHA),
            (f"data/audit/ren_scs/{prior.RUN}/SUMMARY.json", pilot.CHRONOLOGY_SHA)):
        if pipeline.digest(root / relative) != expected:
            raise ValueError("full fleet prerequisite mismatch")
    if shutil.disk_usage(root).free < MIN_FREE:
        raise ValueError("full fleet requires 40 GiB free")
    selected, schemas, allowed = prior.preflight(root)
    return selected, schemas, allowed, coverage(selected, schemas)


def run(root):
    root = root.resolve(strict=True)
    selected, schemas, allowed, groups = preflight(root)
    rec = prior.fleet.pilot.context.recovery
    extraction = rec.Paths.build(str(root), prior.fleet.pilot.context.RUN, new=False).extraction
    # Keep the reviewed pilot byte-identical; reproduce its small source boundary
    # here, without changing globals or broadening its first-two release.
    def read_group(gid):
        for report in selected[gid][1]:
            member = report["member_path"]
            path = extraction / member
            rec._no_symlink_components(root, path)
            info = rec._require_file(path, "full overlap source")
            if info.st_nlink != 1 or info.st_size != report["input_bytes"]:
                raise ValueError("full overlap input metadata mismatch")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != report["input_sha256"]:
                raise ValueError("full overlap input changed")
            workbook = prior.fleet.pilot.workbook_bytes(raw)
            del raw
            iterator = stream.records(workbook, allowed, schemas[member])
            try:
                for record in iterator:
                    yield (member, *record)
            finally:
                iterator.close()
    local = root / "data/raw/ren_scs" / RUN
    public = root / "data/audit/ren_scs" / RUN
    for path in (local, public):
        rec._no_symlink_components(root, path)
    return pipeline.run_pipeline(local, public, groups, read_group, pair_budget=PAIR_BUDGET)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    print(json.dumps(run(Path(parser.parse_args().project_root)), sort_keys=True))
