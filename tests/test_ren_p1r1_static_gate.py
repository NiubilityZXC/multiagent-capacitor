import json
from pathlib import Path

from experiments.audit_cap import ren_p1r1_static_gate as gate
from experiments.audit_cap.ren_p1r1_static_gate import summarize
from tests.test_ren_p1r1_recovery import MockRecoveryRun


def test_static_block_cannot_become_row_or_model_eligibility():
    result = summarize([{"container": "OLE_CFB", "blockers": ["unclassified_record_types"], "scan_complete": True}])
    assert result["status"] == "BLOCKED_ROW_PARSE"
    assert result["workbooks_blocked"] == 1
    assert result["row_parse_executed"] is False
    assert result["p2_eligible"] is False
    assert result["rul_eligible"] is False
    assert result["model_or_api_executed"] is False


def test_complete_static_scan_alone_cannot_grant_row_gate():
    result = summarize([{"container": "OLE_CFB", "blockers": [], "scan_complete": True}])
    assert result["status"] == "R1D_COMPLETE_R1E_NOT_RUN"
    assert result["row_parse_executed"] is False
    assert result["p2_eligible"] is False


def test_full_static_caller_produces_honest_blocked_gate_for_unknown_containers(monkeypatch, tmp_path):
    run = MockRecoveryRun(monkeypatch, tmp_path)
    run.complete()
    root = Path(__file__).resolve().parents[1]
    for name in gate.POLICY_NAMES:
        target = run.project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / name).read_bytes())
    policy = {name: gate.recovery._digests(run.project / name)["sha256"] for name in gate.POLICY_NAMES}
    run.write_json(run.project / "refine-logs/REN_P1R1_R1D_RELEASE.json", {
        "status": "PASS_TO_RUN_STATIC_R1D", "reviewed_policy_sha256": policy,
        "approval_record_sha256": gate.recovery.APPROVAL_SHA256,
    })
    # Only replace the installed-environment boundary, not container inspection,
    # recovery verification, release validation, reporting or artifact writes.
    monkeypatch.setattr(gate, "validate_environment", lambda project: None)
    result = gate.run(run.project, run.run_id)
    assert result["status"] == "BLOCKED_ROW_PARSE"
    assert result["workbooks_blocked"] == 233
    output = run.project / "data/audit/ren_scs" / (run.run_id + "_static")
    complete = json.loads((output / "COMPLETE.json").read_text())
    assert complete["row_gate_pass"] is False
    assert complete["model_or_api_executed"] is False
    manifest = json.loads((output / "ARTIFACT_MANIFEST.json").read_text())
    assert "artifact:XLS_STATIC_SAFETY_LEDGER.csv" in manifest["bound_files"]
    assert len([name for name in manifest["bound_files"] if name.startswith("local:")]) == 233
    assert "NOT_EVALUATED_R1D_BLOCKED" in (output / "UNIT_IDENTITY_LEDGER.csv").read_text()
