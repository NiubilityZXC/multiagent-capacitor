from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.audit_cap import ren_fleet_schema as fleet
from experiments.audit_cap import verify_ren_fleet_schema as verify
from experiments.audit_cap.ren_workbook_reader import schema_rows
from tests.test_ren_workbook_reader import synthetic_workbook, ALLOWED


@pytest.fixture
def actual_schema():
    pytest.importorskip("xlrd", reason="mandatory real-xlrd integration in isolated audit environment")
    data = synthetic_workbook()
    return data, schema_rows(data, ALLOWED)


def test_independent_rebuild_matches_real_xlrd(actual_schema):
    data, result = actual_schema
    verify.verify_fields(result, verify.rebuild(data, ALLOWED))


@pytest.mark.parametrize("key", ["status", "workbook_sha256", "sheets", "row_parse_executed",
    "numeric_target_emitted", "model_or_api_executed", "formulas_evaluated",
    "identity_verified", "target_verified", "p2_eligible"])
def test_every_top_level_schema_field_rejected_if_changed(actual_schema, key):
    data, result = actual_schema
    result[key] = "tampered"
    with pytest.raises(ValueError, match="rebuilt schema mismatch"):
        verify.verify_fields(result, verify.rebuild(data, ALLOWED))


@pytest.mark.parametrize("key", ["index", "name", "nrows", "ncols", "cell_type_counts",
                                "nonfinite_count", "first_eight_rows_text_only"])
def test_every_sheet_field_rejected_if_changed(actual_schema, key):
    data, result = actual_schema
    result["sheets"][0][key] = "tampered"
    with pytest.raises(ValueError): verify.verify_fields(result, verify.rebuild(data, ALLOWED))


@pytest.mark.parametrize("key", ["row", "col", "text", "truncated"])
def test_every_text_hint_field_rejected_if_changed(actual_schema, key):
    data, result = actual_schema
    result["sheets"][0]["first_eight_rows_text_only"][0][key] = "tampered"
    with pytest.raises(ValueError): verify.verify_fields(result, verify.rebuild(data, ALLOWED))


def test_type_substitution_and_extra_key_rejected():
    with pytest.raises(ValueError): verify.verify_fields({"p2_eligible": 0}, {"p2_eligible": False})
    with pytest.raises(ValueError): verify.verify_fields({"a": 1, "x": 0}, {"a": 1})


def test_verifier_rejects_active_bytes_before_reader():
    from tests.test_ren_workbook_reader import bof, rec
    reader = SimpleNamespace(open_workbook=lambda **k: pytest.fail("active bytes reached xlrd"))
    with pytest.raises(ValueError): verify.rebuild(bof()+rec(0x0006)+rec(0x000A), ALLOWED|{6}, reader)


def test_release_missing_stops_before_recovery(monkeypatch, tmp_path):
    monkeypatch.setattr(fleet.pilot.context.independent, "verify", lambda *a: pytest.fail("before release"))
    with pytest.raises(fleet.pilot.context.recovery.RecoveryError): fleet.run(tmp_path)
    assert not (tmp_path / "data/audit/ren_scs" / fleet.RUN).exists()


@pytest.mark.parametrize("changed", ["status", "policy_sha256", "approval_record_sha256"])
def test_release_mismatch_stops_before_recovery(monkeypatch, tmp_path, changed):
    project = Path(__file__).resolve().parents[1]
    for name in fleet.POLICY:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((project / name).read_bytes())
    release = dict(status="PASS_FULL_FLEET_SCHEMA_AUDIT",
        policy_sha256={n: hashlib.sha256((tmp_path/n).read_bytes()).hexdigest() for n in fleet.POLICY},
        approval_record_sha256=fleet.pilot.context.recovery.APPROVAL_SHA256)
    release[changed] = "tampered"
    (tmp_path / "refine-logs/REN_FLEET_SCHEMA_RELEASE.json").write_text(json.dumps(release))
    monkeypatch.setattr(fleet.pilot.context.independent, "verify", lambda *a: pytest.fail("before release"))
    with pytest.raises(ValueError, match="release mismatch"): fleet.run(tmp_path)


@pytest.mark.parametrize("count", [0, 1, 232, 234])
def test_no_full_summary_for_partial_or_excess_fleet(count):
    with pytest.raises(ValueError): fleet.summarize([{"member_path": str(i)} for i in range(count)])


def test_no_full_summary_for_duplicate_members():
    with pytest.raises(ValueError): fleet.summarize([{"member_path": "duplicate"}] * 233)


def synthetic_fleet(monkeypatch, root, count=233):
    data = synthetic_workbook()
    digest = hashlib.sha256(data).hexdigest()
    extraction = root / "synthetic_extraction"
    extraction.mkdir()
    reports = []
    for i in range(count):
        name = f"{i:03d}.xls"
        (extraction / name).write_bytes(data)
        reports.append(dict(member_path=name, input_bytes=len(data), input_sha256=digest,
                            workbook_scans=[{"stream_sha256": digest}]))
    for path in ("data/audit/ren_scs", "data/raw/ren_scs"):
        (root / path).mkdir(parents=True)
    # The already sealed recovery/static/environment layer is mocked; actual
    # byte guard, both xlrd aggregators, local/public persistence and final
    # receipt reconstruction remain real. Release ordering tested separately.
    monkeypatch.setattr(fleet, "preflight", lambda r: (reports, ALLOWED))
    monkeypatch.setattr(fleet.pilot.context.recovery.Paths, "build",
                        lambda *a, **k: SimpleNamespace(extraction=extraction))
    monkeypatch.setattr(fleet.pilot, "workbook_bytes", lambda raw: raw)
    return reports


def test_full_233_caller_real_reader_and_verifier(monkeypatch, tmp_path, actual_schema):
    synthetic_fleet(monkeypatch, tmp_path)
    result = fleet.run(tmp_path)
    assert result["files_verified"] == 233 and result["stored_sheet_rows"] == 466
    assert result["p2_eligible"] is False
    public = tmp_path / "data/audit/ren_scs" / fleet.RUN
    assert len(list(public.glob("[0-9][0-9][0-9].json"))) == 233
    assert (public / "COMPLETE.json").exists()
    with pytest.raises(ValueError, match="append-only"): fleet.run(tmp_path)


def test_midfleet_mismatch_preserves_receipts_and_fails_closed(monkeypatch, tmp_path, actual_schema):
    synthetic_fleet(monkeypatch, tmp_path)
    original = verify.rebuild
    calls = 0
    def broken(*args):
        nonlocal calls
        calls += 1
        result = original(*args)
        if calls == 2:
            result["sheets"][0]["nrows"] += 1
        return result
    monkeypatch.setattr(fleet.verifier, "rebuild", broken)
    with pytest.raises(ValueError, match="rebuilt schema mismatch"): fleet.run(tmp_path)
    public = tmp_path / "data/audit/ren_scs" / fleet.RUN
    blocked = json.loads((public / "BLOCKED.json").read_text())
    assert blocked["files_verified"] == 1 and blocked["failed_member"] == "001.xls"
    assert (public / "001.json").exists() and not (public / "002.json").exists()
    assert not (public / "SUMMARY.json").exists() and not (public / "COMPLETE.json").exists()


def test_changed_container_stops_before_reader(monkeypatch, tmp_path):
    reports = synthetic_fleet(monkeypatch, tmp_path)
    reports[0]["input_sha256"] = "0" * 64
    monkeypatch.setattr(fleet.pilot, "workbook_bytes", lambda raw: pytest.fail("bad digest reached reader"))
    with pytest.raises(ValueError, match="member digest changed"): fleet.run(tmp_path)


def test_saved_receipt_tamper_prevents_complete(monkeypatch, tmp_path, actual_schema):
    synthetic_fleet(monkeypatch, tmp_path)
    rec = fleet.pilot.context.recovery
    writer = rec._write_json
    def corrupt(path, value):
        if path.name == "001.json" and "data/audit/" in str(path):
            value = deepcopy(value)
            value["stored_sheet_rows"] += 1
        return writer(path, value)
    monkeypatch.setattr(rec, "_write_json", corrupt)
    with pytest.raises(ValueError, match="rebuilt schema mismatch"): fleet.run(tmp_path)
    public = tmp_path / "data/audit/ren_scs" / fleet.RUN
    assert (public / "BLOCKED.json").exists() and not (public / "COMPLETE.json").exists()
