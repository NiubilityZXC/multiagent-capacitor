import io
import json
import struct
from types import SimpleNamespace

import pytest

from experiments.audit_cap import ren_static_context as probe


def rec(kind, body=b""):
    return struct.pack("<HH", kind, len(body)) + body


@pytest.mark.parametrize(("parts", "kind"), [
    (["\x01CompObj"], "root_compobj_metadata_marker"),
    (["_VBA_PROJECT_CUR", "VBA", "PrivateModule"], "vba_project_tree_marker"),
    (["ObjectPool", "MBD012"], "embedded_container_marker"),
    (["PROJECT"], "other_macro_name_marker"),
    (["Workbook"], "workbook"),
    (["unrecognized"], "unclassified_directory_marker"),
])
def test_precise_directory_markers_not_safety_verdicts(parts, kind):
    assert probe.directory_kind(parts) == kind


def test_continue_context_skips_private_payloads():
    payload = rec(0x004D, b"PRIVATE_PRINT") + rec(0x003C, b"SECRET") + rec(0x003C, b"X") + rec(0x00A1)
    result = probe.continuation_context(payload)
    assert result["chains"] == [{"offset": 17, "predecessor_record_id": "0x004D", "continue_records": 2,
                                 "payload_bytes": 7, "following_record_id": "0x00A1"}]
    assert "SECRET" not in json.dumps(result)
    assert result["row_parse_authorized"] is False


@pytest.mark.parametrize("payload", [b"x", rec(0x002F), b"\x3c\x00\xff\xff", rec(0x003C, b"x")[:-1]])
def test_bad_or_encrypted_framing_fails_closed(payload):
    with pytest.raises(ValueError):
        probe.continuation_context(payload)


def test_orphan_continue_is_reported_not_accepted():
    result = probe.continuation_context(rec(0x003C, b"x"))
    assert result["chains"][0]["predecessor_record_id"] is None
    assert result["chains"][0]["following_record_id"] is None
    assert result["p2_eligible"] is False


class FakeOle:
    opened = []
    names = [["Workbook"], ["\x01CompObj"], ["_VBA_PROJECT_CUR", "VBA", "SECRET_MODULE"]]
    parsing_issues = []
    payload = rec(0x004D) + rec(0x003C, b"SECRET_CELL") + rec(0x00A1)

    def __init__(self, stream, *, write_mode, raise_defects):
        assert write_mode is False

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def listdir(self, **kwargs): return self.names
    def get_type(self, parts): return 2
    def get_size(self, parts): return len(self.payload)
    def openstream(self, parts):
        assert parts == ["Workbook"], "must never open VBA or embedded payload"
        self.opened.append(parts)
        return io.BytesIO(self.payload)


@pytest.mark.parametrize("inspect_continue", [False, True])
def test_only_workbook_stream_may_be_opened(inspect_continue):
    FakeOle.opened = []
    result = probe.inspect_container(b"fake", inspect_continue, SimpleNamespace(OleFileIO=FakeOle, DEFECT_INCORRECT=30))
    assert len(FakeOle.opened) == int(inspect_continue)
    assert result["status"] == "DIAGNOSTIC_ONLY_NO_GATE_CHANGE"
    assert "SECRET" not in json.dumps(result)
    assert all(result[k] is False for k in probe.FLAGS)


def test_release_failure_before_any_workbook_access(monkeypatch, tmp_path):
    monkeypatch.setattr(probe.recovery.Paths, "build", lambda *a, **k: None)
    monkeypatch.setattr(probe.independent, "verify", lambda *a: {})
    monkeypatch.setattr(probe.original, "validate_environment", lambda *a: None)
    monkeypatch.setattr(probe, "inspect_container", lambda *a: pytest.fail("no workbook access allowed"))
    with pytest.raises(probe.recovery.RecoveryError):
        probe.run(tmp_path)
    assert not (tmp_path / "data/audit/ren_scs" / (probe.RUN + "_static_context_v1")).exists()


def setup_caller(monkeypatch, tmp_path):
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    local = tmp_path / "data/raw/ren_scs" / probe.RUN / "static_evidence"
    local.mkdir(parents=True)
    old_output = tmp_path / "data/audit/ren_scs" / (probe.RUN + "_static")
    old_output.mkdir(parents=True)
    extraction = tmp_path / "extracted"
    extraction.mkdir()
    data = b"synthetic opaque OLE adapter input"
    (extraction / "001.xls").write_bytes(data)
    bindings = {}
    for i in range(1, 234):
        r = {"member_path": f"{i:03d}.xls", "input_bytes": len(data),
             "input_sha256": probe.hashlib.sha256(data).hexdigest(),
             "blockers": ["unclassified_active_or_context_record_CONTINUE"] if i == 1 else ["unclassified_record_types"]}
        path = local / f"{i:03d}.json"
        path.write_text(json.dumps(r))
        bindings["local:" + path.name] = probe.recovery._digests(path)
    manifest = old_output / "ARTIFACT_MANIFEST.json"
    manifest.write_text(json.dumps({"bound_files": bindings}))
    for name in probe.POLICY:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root / name).read_bytes())
    release = tmp_path / "refine-logs/REN_STATIC_CONTEXT_RELEASE.json"
    release.parent.mkdir()
    release.write_text(json.dumps({"status": "PASS_DIAGNOSTIC_ONLY",
        "policy_sha256": {name: probe.recovery._digests(tmp_path / name)["sha256"] for name in probe.POLICY},
        "prior_manifest_sha256": probe.recovery._digests(manifest)["sha256"],
        "approval_record_sha256": probe.recovery.APPROVAL_SHA256}))
    monkeypatch.setattr(probe.recovery.Paths, "build", lambda *a, **k: SimpleNamespace(extraction=extraction))
    monkeypatch.setattr(probe.independent, "verify", lambda *a: {})
    monkeypatch.setattr(probe.original, "validate_environment", lambda *a: None)
    monkeypatch.setitem(sys.modules, "olefile", SimpleNamespace(OleFileIO=FakeOle, DEFECT_INCORRECT=30))
    return local, extraction


def test_full_diagnostic_caller_preserves_gate_and_is_append_only(monkeypatch, tmp_path):
    setup_caller(monkeypatch, tmp_path)
    result = probe.run(tmp_path)
    assert result["workbooks_inspected"] == 1
    assert result["continuation_chain_counts"] == {"0x004D->CONTINUE->0x00A1": 1}
    assert result["p2_eligible"] is False
    with pytest.raises(FileExistsError):
        probe.run(tmp_path)


def test_prior_report_mutation_stops_before_scan(monkeypatch, tmp_path):
    local, _ = setup_caller(monkeypatch, tmp_path)
    (local / "001.json").write_text("{}")
    monkeypatch.setattr(probe, "inspect_container", lambda *a: pytest.fail("must not scan"))
    with pytest.raises(ValueError, match="prior static artifact changed"):
        probe.run(tmp_path)


def test_input_mutation_records_block_without_scanning(monkeypatch, tmp_path):
    _, extraction = setup_caller(monkeypatch, tmp_path)
    (extraction / "001.xls").write_bytes(b"altered")
    monkeypatch.setattr(probe, "inspect_container", lambda *a: pytest.fail("must not scan"))
    with pytest.raises(ValueError, match="diagnostic input changed"):
        probe.run(tmp_path)
    output = tmp_path / "data/audit/ren_scs" / (probe.RUN + "_static_context_v1")
    assert (output / "BLOCKED.json").exists()
    assert not (output / "COMPLETE.json").exists()
