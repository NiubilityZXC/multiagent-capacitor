from copy import deepcopy

import pytest

from experiments.audit_cap import ren_row_pilot as pilot
from tests.test_ren_static_context_resolution import fixture


def test_missing_release_prevents_any_recovery_or_row_read(monkeypatch, tmp_path):
    monkeypatch.setattr(pilot.context.independent, "verify", lambda *a: pytest.fail("no recovery read"))
    with pytest.raises(pilot.context.recovery.RecoveryError): pilot.run(tmp_path)


def test_catalog_count_checked():
    with pytest.raises(ValueError): pilot.allowed_record_ids({"entries": []})


def test_unresolved_structures_block():
    report, diagnostic = fixture()
    report["blockers"].append("unknown_structural_defect")
    with pytest.raises(ValueError): pilot.validate_selected(report, diagnostic, {0x003C})


def test_complete_catalog_recognition_is_not_enough_for_truncated_stream():
    report, _ = fixture()
    report["blockers"] = ["unclassified_record_types"]
    report["workbook_scans"][0]["unscanned_bytes"] = 1
    with pytest.raises(ValueError): pilot.validate_selected(report, None, {0x003C})


def test_frozen_nonmacro_complete_report_can_reach_byte_guard():
    report, _ = fixture()
    report["blockers"] = ["unclassified_record_types"]
    before = deepcopy(report)
    pilot.validate_selected(report, None, {0x003C})
    assert report == before


def test_record_outside_catalog_blocked():
    report, _ = fixture()
    report["blockers"] = ["unclassified_record_types"]
    with pytest.raises(ValueError): pilot.validate_selected(report, None, set())


def test_full_caller_real_xlrd_synthetic_boundary(monkeypatch, tmp_path):
    pytest.importorskip("xlrd", reason="real reader integration runs in the isolated audit environment")
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from tests.test_ren_workbook_reader import synthetic_workbook
    project = Path(__file__).resolve().parents[1]
    rec = pilot.context.recovery
    for name in (*pilot.POLICY, pilot.CATALOG, pilot.DIAGNOSTIC, pilot.PRIOR_MANIFEST):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((project / name).read_bytes())
    release = tmp_path / "refine-logs/REN_ROW_PILOT_RELEASE.json"
    release.write_text(json.dumps({"status": "PASS_FIRST_MEMBER_ROW_PILOT",
        "policy_sha256": {n: rec._digests(tmp_path / n)["sha256"] for n in pilot.POLICY},
        "approval_record_sha256": rec.APPROVAL_SHA256}))
    data = synthetic_workbook()
    extraction = tmp_path / "synthetic_extraction"
    extraction.mkdir()
    (tmp_path / "data/raw/ren_scs").mkdir(parents=True)
    (extraction / "synthetic.xls").write_bytes(data)
    report = {"member_path": "synthetic.xls", "input_sha256": pilot.hashlib.sha256(data).hexdigest(),
        "input_bytes": len(data), "blockers": ["unclassified_record_types"], "ole_entries": [],
        "workbook_scans": [{"scan_complete": True, "unscanned_bytes": 0, "record_types": [],
                            "stream_sha256": pilot.hashlib.sha256(data).hexdigest()}]}
    monkeypatch.setattr(pilot.context.independent, "verify", lambda *a: {})
    monkeypatch.setattr(pilot.context.original, "validate_environment", lambda *a: None)
    monkeypatch.setattr(pilot.context, "verify_static_artifacts", lambda *a: [report])
    monkeypatch.setattr(rec.Paths, "build", lambda *a, **k: SimpleNamespace(extraction=extraction))
    # Adapter only: raw synthetic Workbook bytes stand in for OLE extraction;
    # byte guard, actual xlrd, row audit, reporting and release checks stay real.
    monkeypatch.setattr(pilot, "workbook_bytes", lambda container: container)
    result = pilot.run(tmp_path)
    assert result["stored_sheet_rows"] == 2 and result["p2_eligible"] is False
    assert (tmp_path / "data/raw/ren_scs/row_pilot_20260910_v1/SCHEMA_ROWS.json").exists()
    with pytest.raises(ValueError, match="append-only"): pilot.run(tmp_path)
