from __future__ import annotations

import hashlib
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import zlib

import pytest

import experiments.audit_cap.ren_p1r1_recovery as recovery

from experiments.audit_cap.ren_p1r1_recovery import (
    ARCHIVE_SHA256,
    EXPECTED_FILE_COUNT,
    PLAN_SHA256,
    RecoveryError,
    _listing_diff,
    _ok_paths,
    _parse_unrar_listing,
    _safe_url,
    _verify_seal,
)


def _listing(path: str = "batch1/1.xls", *, size: int = 10, crc: str = "AABBCCDD") -> bytes:
    return f"""
UNRAR 7.23 freeware      Copyright (c) 1993-2026 Alexander Roshal

Archive: raw.rar
Details: RAR 5

        Name: {path}
        Type: File
        Size: {size}
 Packed size: 7
       Ratio: 70%
       mtime: 2019-12-20 11:27:42,854371100
  Attributes: ..A....
       CRC32: {crc}
     Host OS: Windows
 Compression: RAR 5.0(v50) -m3 -md=32m
""".encode()


def test_frozen_authority_and_source_hashes_are_pinned() -> None:
    assert PLAN_SHA256 == "a7a8f5521b6b249af59a9ded0971cb02f912d9f46e8babfe3d60777cbfcc3c6d"
    assert ARCHIVE_SHA256 == "a8f1083b887f95483561a94b624b323ff42814654ee7f23e7f95bc042fa258d8"
    assert EXPECTED_FILE_COUNT == 233


def test_url_sanitizer_drops_credentials_query_and_fragment() -> None:
    assert _safe_url("https://user:secret@www.rarlab.com/a?token=x#y") == "https://www.rarlab.com/a"


def test_unrar_listing_parser_maps_32m_dictionary_to_prior_semantic_method() -> None:
    _, rows = _parse_unrar_listing(_listing(), expected_member_count=1)
    assert rows[0]["compression_method"] == "m3:25"


def test_unrar_listing_parser_rejects_traversal_before_count_gate() -> None:
    with pytest.raises(RecoveryError, match="unsafe member path"):
        _parse_unrar_listing(_listing("../escape.xls"))


def test_unrar_listing_parser_rejects_redirection_marker() -> None:
    raw = _listing().replace(b"       CRC32:", b"        Redir: ../escape.xls\n       CRC32:")
    with pytest.raises(RecoveryError, match="link/encryption/redirection"):
        _parse_unrar_listing(raw, expected_member_count=1)


def test_listing_diff_detects_changed_crc() -> None:
    official = [{"member_path": "a.xls", "member_type": "regular_file", "uncompressed_bytes": 1, "packed_bytes": 1, "crc": "AABBCCDD", "compression_method": "m3:25", "encrypted": "false", "link_or_redirection": "false", "extension": ".xls", "safety_status": "PASS"}]
    prior = [{**official[0], "crc": "00000000"}]
    result = _listing_diff(official, prior)
    assert result["status"] == "BLOCKED_LISTING_DIFF"
    assert result["changed"][0]["fields"]["crc"]["official"] == "AABBCCDD"


def test_ok_path_parser_requires_terminal_ok_line() -> None:
    raw = b"Testing     batch1/1.xls                                  OK \nTesting batch1/2.xls CRC Failed\nAll OK\n"
    assert _ok_paths(raw, "Testing") == ["batch1/1.xls"]


def test_model_api_and_numeric_target_flags_are_false_in_diff() -> None:
    result = _listing_diff([], [])
    assert result["model_or_api_executed"] is False
    assert result["numeric_target_emitted"] is False


def test_seal_rejects_any_bound_byte_change(tmp_path) -> None:
    seal = tmp_path / "R1A_SEAL.json"
    seal.write_text(
        '{"automatic_next_stage":false,"bound_files":{"source":{"bytes":1,"sha256":"a"}},'
        '"model_or_api_executed":false,"numeric_target_emitted":false,"stage":"R1A",'
        '"status":"PASS_R1A_SEALED"}\n', encoding="utf-8"
    )
    with pytest.raises(RecoveryError, match="bound byte changed"):
        _verify_seal(seal, "R1A", "PASS_R1A_SEALED", {"source": {"bytes": 1, "sha256": "b"}})


def _paths(tmp_path: Path) -> recovery.Paths:
    project = tmp_path / "project"
    output = project / "data/audit/ren_scs/p1r1_20260905_000000"
    local = project / "data/raw/ren_scs/p1r1_20260905_000000"
    (local / "evidence").mkdir(parents=True)
    output.mkdir(parents=True)
    return recovery.Paths(
        project=project, run_id="p1r1_20260905_000000", output=output, local=local,
        archive=project / "data/raw/ren_scs/raw.rar", prior=project / "prior.csv",
        plan=project / "plan.md", packet=project / "packet.json",
        approval=project / "approval.json", release=project / "release.json",
        tool_tar=local / "tool/tool.tar.gz", tool_root=local / "tool/unpacked",
        extraction=local / "quarantine_extracted",
    )


def test_paths_build_enforces_ignored_local_and_tracked_output(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "data/raw/ren_scs").mkdir(parents=True)
    (project / "data/audit/ren_scs").mkdir(parents=True)
    (project / ".gitignore").write_text("/data/raw/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    paths = recovery.Paths.build(str(project), "p1r1_20260905_010203", new=True)
    assert paths.local.relative_to(project).as_posix().startswith("data/raw/ren_scs/")
    assert paths.output.relative_to(project).as_posix().startswith("data/audit/ren_scs/")


def test_curl_receipt_sanitizes_raw_redirect_query(monkeypatch, tmp_path) -> None:
    evidence = tmp_path / "evidence"; evidence.mkdir()
    payload = tmp_path / "download.htm"

    def fake_run(argv, timeout):
        header = Path(argv[argv.index("--dump-header") + 1])
        partial = Path(argv[argv.index("--output") + 1])
        header.write_bytes(b"HTTP/2 302\nLocation: https://www.rarlab.com/download.htm?secret=token\n\nHTTP/2 200\nContent-Type: text/html\n")
        partial.write_bytes(b"payload")
        meta = {"url_effective": "https://www.rarlab.com/download.htm", "http_code": 200,
                "num_redirects": 1, "size_download": 7, "content_type": "text/html"}
        return recovery.CommandResult(tuple(argv), 0, json.dumps(meta).encode(), b"", False, False)

    monkeypatch.setattr(recovery, "_run", fake_run)
    receipt = recovery._curl_download(recovery.DOWNLOAD_PAGE_URL, payload, evidence, "DOWNLOAD_PAGE")
    assert "secret" not in json.dumps(receipt)
    assert receipt["headers"]["redirect_scheme_host_paths"] == ["https://www.rarlab.com/download.htm"]
    assert (evidence / "DOWNLOAD_PAGE.headers.raw").read_bytes().find(b"secret=token") >= 0


def test_curl_receipt_rejects_insecure_redirect(monkeypatch, tmp_path) -> None:
    evidence = tmp_path / "evidence"; evidence.mkdir(); payload = tmp_path / "download.htm"

    def fake_run(argv, timeout):
        Path(argv[argv.index("--dump-header") + 1]).write_bytes(b"HTTP/2 302\nLocation: http://www.rarlab.com/download.htm\n")
        Path(argv[argv.index("--output") + 1]).write_bytes(b"payload")
        meta = {"url_effective": "https://www.rarlab.com/download.htm", "http_code": 200}
        return recovery.CommandResult(tuple(argv), 0, json.dumps(meta).encode(), b"", False, False)

    monkeypatch.setattr(recovery, "_run", fake_run)
    with pytest.raises(RecoveryError, match="unapproved tool transport"):
        recovery._curl_download(recovery.DOWNLOAD_PAGE_URL, payload, evidence, "DOWNLOAD_PAGE")


@pytest.mark.parametrize("member_type", ["symlink", "fifo", "duplicate"])
def test_tool_tar_rejects_links_specials_and_duplicates(monkeypatch, tmp_path, member_type) -> None:
    archive = tmp_path / "tool.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        root = tarfile.TarInfo("rar"); root.type = tarfile.DIRTYPE; stream.addfile(root)
        item = tarfile.TarInfo("rar/unrar"); item.size = 1
        if member_type == "symlink":
            item.type = tarfile.SYMTYPE; item.linkname = "../escape"; item.size = 0; stream.addfile(item)
        elif member_type == "fifo":
            item.type = tarfile.FIFOTYPE; item.size = 0; stream.addfile(item)
        else:
            stream.addfile(item, io.BytesIO(b"x")); stream.addfile(item, io.BytesIO(b"x"))
    monkeypatch.setattr(recovery, "EXPECTED_TAR_MEMBERS", {"rar": ("dir", 0), "rar/unrar": ("file", 1)})
    with pytest.raises(RecoveryError):
        recovery._extract_tool(archive, tmp_path / "unpacked")


def test_archive_test_report_blocks_warning_timeout_and_stderr() -> None:
    expected = ["batch/a.xls"]
    good = b"Testing     batch/a.xls      OK\nAll OK\n"
    for result in (
        recovery.CommandResult(("unrar",), 0, good + b"WARNING\n", b"", False, False),
        recovery.CommandResult(("unrar",), 124, good, b"", True, False),
        recovery.CommandResult(("unrar",), 0, good, b"unexpected", False, False),
    ):
        evidence = recovery._command_record(result, argv_label=("unrar", "t"))
        assert recovery._archive_test_report(result, evidence, expected)["status"] == "BLOCKED_ARCHIVE_TEST"


def test_mocked_r1b_r1c_pass_then_seals_reject_mutation(monkeypatch, tmp_path) -> None:
    paths = _paths(tmp_path)
    source = paths.project / "bound.bin"; source.write_bytes(b"bound")
    monkeypatch.setattr(recovery, "_r1a_files", lambda unused: {"source": source})
    recovery._seal(paths.output / "R1A_SEAL.json", "R1A", "PASS_R1A_SEALED", recovery._bound({"source": source}))
    file_bytes = b"abc"; crc = f"{zlib.crc32(file_bytes) & 0xFFFFFFFF:08X}"
    file_row = {"member_path": "batch/a.xls", "member_type": "regular_file", "uncompressed_bytes": "3", "crc": crc,
                "model_or_api_executed": "false", "numeric_target_emitted": "false"}
    directory_row = {"member_path": "batch", "member_type": "directory", "uncompressed_bytes": "0", "crc": "00000000",
                     "model_or_api_executed": "false", "numeric_target_emitted": "false"}
    monkeypatch.setattr(recovery, "_stored_members", lambda unused: [file_row])
    monkeypatch.setattr(recovery, "EXPECTED_FILE_COUNT", 1)
    monkeypatch.setattr(recovery, "EXPECTED_MEMBER_COUNT", 2)

    def fake_test(argv, timeout):
        return recovery.CommandResult(tuple(argv), 0, b"Testing batch/a.xls OK\nAll OK\n", b"", False, False)

    monkeypatch.setattr(recovery, "_run", fake_test)
    assert recovery.r1b(paths, 1) == 0
    monkeypatch.setattr(recovery, "_stored_members", lambda unused: [file_row, directory_row])

    def fake_extract(argv, timeout):
        (paths.extraction / "batch").mkdir()
        (paths.extraction / "batch/a.xls").write_bytes(file_bytes)
        return recovery.CommandResult(tuple(argv), 0, f"Extracting {paths.extraction}/batch/a.xls OK\nAll OK\n".encode(), b"", False, False)

    monkeypatch.setattr(recovery, "_run", fake_extract)
    assert recovery.r1c(paths, 1) == 0
    assert json.loads((paths.output / "EXTRACTION_MANIFEST.json").read_text())["status"] == "PASS_EXTRACTION_BYTE_IDENTITY"
    source.write_bytes(b"tampered")
    with pytest.raises(RecoveryError, match="bound byte changed"):
        recovery.r1c(paths, 1)


def test_broad_phase_exception_records_block(monkeypatch, tmp_path) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(recovery.Paths, "build", lambda *args, **kwargs: paths)
    monkeypatch.setattr(recovery, "r1a", lambda unused: (_ for _ in ()).throw(OSError("disk read failed")))
    with pytest.raises(RecoveryError, match="failed closed"):
        recovery.main(["r1a", "--project-root", str(paths.project), "--run-id", paths.run_id])
    blocked = json.loads((paths.output / "R1A_BLOCKED.json").read_text())
    assert blocked["status"] == "BLOCKED"
    assert blocked["error_type"] == "OSError"


class MockRecoveryRun:
    """Real generators/verifier with a strict, offline subprocess boundary.

    The source is deliberately not a RAR. Only our in-memory tool tarball is
    unpacked; simulated ``unrar x`` writes small opaque bytes, never workbooks.
    No evidence, parser, hashing, seal, or reconstruction function is mocked.
    """

    def __init__(self, monkeypatch, tmp_path):
        import experiments.audit_cap.verify_ren_p1r1_recovery as verifier

        self.verifier = verifier
        self.project = tmp_path / "project"
        self.project.mkdir()
        (self.project / ".gitignore").write_text("/data/raw/\n", encoding="utf-8")
        subprocess.run(["/usr/bin/git", "init", "-q", str(self.project)], check=True)
        self.run_id = "p1r1_20260905_030405"
        self.paths = recovery.Paths.build(str(self.project), self.run_id, new=True)
        self.commands = []
        self.failure = None
        self.files = {f"batch{index % 4}/{index:03}.xls": f"opaque-fixture-{index}".encode()
                      for index in range(233)}
        listing = ["UNRAR 7.23 freeware\n\nArchive: raw.rar\nDetails: RAR 5\n"]
        prior = []
        for name, payload in [(f"batch{index}", None) for index in range(4)] + list(self.files.items()):
            is_dir = payload is None
            size = 0 if is_dir else len(payload)
            crc = "00000000" if is_dir else f"{zlib.crc32(payload) & 0xFFFFFFFF:08X}"
            listing.append(f"\n        Name: {name}\n        Type: {'Directory' if is_dir else 'File'}\n"
                           f"        Size: {size}\n Packed size: {size}\n       CRC32: {crc}\n"
                           " Compression: RAR 5.0(v50) -m3 -md=32m\n")
            prior.append({"member_path": name, "member_type": "directory" if is_dir else "regular_file",
                          "batch_path_component": name.split("/")[0], "provisional_filename_stem": "NA",
                          "segment_suffix": "NA", "uncompressed_bytes": size, "packed_bytes": size,
                          "crc": crc, "compression_method": "m0" if is_dir else "m3:25",
                          "encrypted": "-", "link_fields_empty": "True", "extension": "NA" if is_dir else ".xls",
                          "listing_safety_status": "PASS_LISTING_METADATA", "row_content_status": "NOT_EXTRACTED_NOT_PARSED"})
        self.listing = "\n".join(listing).encode()
        self.paths.prior.parent.mkdir(parents=True)
        with self.paths.prior.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=recovery.PRIOR_HEADER)
            writer.writeheader(); writer.writerows(prior)
        self.paths.archive.parent.mkdir(parents=True, exist_ok=True)
        self.paths.archive.write_bytes(b"NOT A REAL RAR: offline adversarial fixture")
        self.paths.plan.parent.mkdir(parents=True)
        self.paths.plan.write_bytes(b"Offline test authority; not production authorization.\n")
        self.paths.packet.write_bytes(b'{"fixture":true}\n')
        plan_hash = hashlib.sha256(self.paths.plan.read_bytes()).hexdigest()
        self.write_json(self.paths.approval, {"approval_token": f"APPROVE_REN_P1R1:{plan_hash}",
                                               "automatic_next_stage": False})
        root = Path(__file__).resolve().parents[1]
        for name in ("experiments/audit_cap/ren_p1r1_recovery.py", "experiments/audit_cap/verify_ren_p1r1_recovery.py",
                     "tests/test_ren_p1r1_recovery.py", "tests/test_verify_ren_p1r1_recovery.py"):
            target = self.project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((root / name).read_bytes())
        tool_payloads = {name: (name + " opaque mock package bytes\n").encode()
                         for name, (kind, _) in recovery.EXPECTED_TAR_MEMBERS.items() if kind == "file"}
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as archive:
            directory = tarfile.TarInfo("rar"); directory.type = tarfile.DIRTYPE; archive.addfile(directory)
            for name, payload in tool_payloads.items():
                member = tarfile.TarInfo(name); member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
        self.tool_bytes = tar_buffer.getvalue()
        monkeypatch.setattr(recovery, "EXPECTED_TAR_MEMBERS", {"rar": ("dir", 0), **{
            name: ("file", len(payload)) for name, payload in tool_payloads.items()}})
        for generator_name, verifier_name, path in (
            ("PLAN_SHA256", "PLAN_SHA256", self.paths.plan),
            ("PACKET_SHA256", "PACKET_SHA256", self.paths.packet),
            ("APPROVAL_SHA256", "APPROVAL_SHA256", self.paths.approval),
            ("PRIOR_LEDGER_SHA256", "PRIOR_SHA256", self.paths.prior),
            ("ARCHIVE_SHA256", "ARCHIVE_SHA256", self.paths.archive),
            ("CURL_SHA256", "CURL_SHA256", Path("/usr/bin/curl")),
        ):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            monkeypatch.setattr(recovery, generator_name, digest)
            monkeypatch.setattr(verifier, verifier_name, digest)
        for module in (recovery, verifier):
            monkeypatch.setattr(module, "ARCHIVE_BYTES", self.paths.archive.stat().st_size)
            monkeypatch.setattr(module, "ARCHIVE_MD5", hashlib.md5(self.paths.archive.read_bytes(), usedforsecurity=False).hexdigest())
            for constant, name in (("RAR_SHA256", "rar/rar"), ("UNRAR_SHA256", "rar/unrar"), ("LICENSE_SHA256", "rar/license.txt")):
                monkeypatch.setattr(module, constant, hashlib.sha256(tool_payloads[name]).hexdigest())
        monkeypatch.setattr(recovery, "TOOL_TARBALL_BYTES", len(self.tool_bytes))
        monkeypatch.setattr(recovery, "TOOL_TARBALL_SHA256", hashlib.sha256(self.tool_bytes).hexdigest())
        monkeypatch.setattr(verifier, "TOOL_TAR_SHA256", hashlib.sha256(self.tool_bytes).hexdigest())
        monkeypatch.setattr(recovery, "EXPECTED_UNCOMPRESSED_BYTES", sum(map(len, self.files.values())))
        monkeypatch.setattr(verifier, "FILE_BYTES", sum(map(len, self.files.values())))
        policy = {name: path for name, path in recovery._authority(self.paths).items() if name.startswith("policy:")}
        self.write_json(self.paths.release, {
            "schema_version": "RenP1R1R4Release.v1", "status": "PASS_TO_RUN_R1ABC",
            "approval_record_sha256": recovery.APPROVAL_SHA256,
            "reviewed_policy_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in policy.items()},
            "automatic_next_stage": False, "model_or_api_executed": False,
        })
        self.real_subprocess_run = subprocess.run
        monkeypatch.setattr(subprocess, "run", self.run_command)

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")

    def run_command(self, argv, **kwargs):
        argv = [str(value) for value in argv]
        self.commands.append(argv)
        if argv[:3] == ["/usr/bin/git", "-C", str(self.project)] and argv[3:6] == ["check-ignore", "-q", "--"]:
            return self.real_subprocess_run(argv, **kwargs)
        stdout, stderr, code = b"", b"", 0
        if argv[0] == "/usr/bin/curl":
            assert argv[-1] in {recovery.TOOL_URL, recovery.DOWNLOAD_PAGE_URL}
            assert "--proto" in argv and argv[argv.index("--proto") + 1] == "=https"
            is_tool = argv[-1] == recovery.TOOL_URL
            payload = self.tool_bytes if is_tool else b'<a href="/rar/rarlinux-x64-723.tar.gz">RAR for Linux x64 7.23</a>'
            if self.failure == "tool_download" and is_tool:
                payload += b"tampered"
            if self.failure == "download_page" and not is_tool:
                payload = b"version not approved"
            Path(argv[argv.index("--output") + 1]).write_bytes(payload)
            redirect = b"Location: http://www.rarlab.com/download.htm\n" if self.failure == "redirect" else b""
            Path(argv[argv.index("--dump-header") + 1]).write_bytes(b"HTTP/2 200\n" + redirect + b"Content-Type: application/octet-stream\n")
            stdout = json.dumps({"url_effective": argv[-1], "http_code": 200, "num_redirects": 0,
                                 "size_download": len(payload), "content_type": "application/octet-stream"}).encode()
            if self.failure == "curl_stderr":
                stderr = b"download warning"
        elif argv[0] == "/usr/bin/df":
            assert argv == ["/usr/bin/df", "--output=avail", "-B1", str(self.paths.local.parent)]
            stdout = b"     Avail\n1\n" if self.failure == "disk" else b"     Avail\n999999999999\n"
        elif argv[0] in {str(self.paths.tool_root / "rar/rar"), str(self.paths.tool_root / "rar/unrar")}:
            action = argv[1]
            if action == "-iver":
                assert argv[1:] == ["-iver"]
                stdout = b"7.22\n" if self.failure == "version" else b"7.23\n"
            elif action == "lt":
                assert argv[1:] == ["lt", "-v", "-p-", str(self.paths.archive)]
                stdout = self.listing
                if self.failure == "listing_diff":
                    stdout = stdout.replace(b"-m3", b"-m2")
            elif action in {"t", "x"}:
                suffix = ["-o-", str(self.paths.archive), str(self.paths.extraction) + os.sep] if action == "x" else [str(self.paths.archive)]
                assert argv[1:] == [action, "-idp", "-p-", *suffix]
                label = "Testing" if action == "t" else "Extracting"
                directory_lines = "".join(f"Testing batch{index} OK\n" for index in range(4)) if action == "t" else ""
                names = self.files if action == "t" else [str(self.paths.extraction / name) for name in self.files]
                stdout = ("".join(f"{label} {name} OK\n" for name in names) + directory_lines + "All OK\n").encode()
                if action == "x":
                    for name, payload in self.files.items():
                        target = self.paths.extraction / name
                        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(payload)
                    if self.failure == "extraction_crc":
                        (self.paths.extraction / next(iter(self.files))).write_bytes(b"bad")
                    if self.failure == "extraction_symlink":
                        (self.paths.extraction / "extra.xls").symlink_to(self.paths.archive)
                    if self.failure == "extraction_wrong_path":
                        stdout = stdout.replace(next(iter(self.files)).encode(), b"batch0/WRONG.xls", 1)
                if self.failure == f"{action}_warning":
                    stdout += b"WARNING\n"
                elif self.failure == f"{action}_stderr":
                    stderr = b"unexpected diagnostic"
                elif self.failure == f"{action}_timeout":
                    raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=stdout)
                elif self.failure == f"{action}_error":
                    raise OSError("simulated process launch failure")
                elif self.failure == f"{action}_returncode":
                    code = 2
            else:
                raise AssertionError(f"unapproved mock tool command: {argv}")
        else:
            raise AssertionError(f"real network/archive command prohibited: {argv}")
        return subprocess.CompletedProcess(argv, code, stdout, stderr)

    def phase(self, phase):
        return recovery.main([phase, "--project-root", str(self.project), "--run-id", self.run_id, "--timeout", "1"])

    def complete(self):
        assert self.phase("r1a") == 0
        assert self.phase("r1b") == 0
        assert self.phase("r1c") == 0
        return self.verifier.verify(self.project, self.run_id)

    def reseal(self):
        """Act like an attacker who may rewrite every untrusted JSON seal."""
        files = recovery._r1a_files(self.paths)
        for stage, artifacts, local_names in (
            ("R1A", (), ()), ("R1B", recovery.R1B_ARTIFACTS, recovery.R1B_LOCAL_EVIDENCE),
            ("R1C", recovery.R1C_ARTIFACTS, recovery.R1C_LOCAL_EVIDENCE),
        ):
            files.update({f"artifact:{name}": self.paths.output / name for name in artifacts})
            files.update({f"local_evidence:{name}": self.paths.local / "evidence" / name for name in local_names})
            path = self.paths.output / f"{stage}_SEAL.json"
            seal = json.loads(path.read_text())
            seal["bound_files"] = recovery._bound(files)
            self.write_json(path, seal)
            # Prove negative cases pass byte seals and reach independent semantics.
            self.verifier._verify_seal(path, stage, self.verifier._bound(files))
            files[f"seal:{stage}"] = path


@pytest.fixture
def mocked_recovery_run(monkeypatch, tmp_path):
    return MockRecoveryRun(monkeypatch, tmp_path)


def test_full_mocked_r1abc_and_independent_verifier_pass(mocked_recovery_run):
    run = mocked_recovery_run
    report = run.complete()
    assert report["status"] == "PASS_R1ABC_INDEPENDENT_VERIFICATION"
    assert report["verified_member_count"] == 237
    assert report["verified_regular_file_count"] == 233
    assert report["verified_directory_count"] == 4
    assert report["verified_regular_file_bytes"] == sum(map(len, run.files.values()))
    assert report["workbook_opened_or_parsed"] is False
    assert report["model_or_api_executed"] is False
    assert report["numeric_target_emitted"] is False
    assert report["automatic_next_stage"] is False
    assert [argv[1] for argv in run.commands if Path(argv[0]).name == "unrar"] == ["-iver", "lt", "t", "x", "lt"]
    assert sum(argv[0] == "/usr/bin/curl" for argv in run.commands) == 2


@pytest.mark.parametrize("artifact", [
    "DOWNLOAD_PAGE_RECEIPT.json", "TOOL_DOWNLOAD_RECEIPT.json", "TOOL_IDENTITY.json",
    "ARCHIVE_LISTING_DIFF.json", "R1A_PREFLIGHT.json", "ARCHIVE_TEST_REPORT.json",
    "EXTRACTION_MANIFEST.json",
])
def test_full_verifier_rejects_every_report_field_after_resealing(mocked_recovery_run, artifact):
    run = mocked_recovery_run
    run.complete()
    path = run.paths.output / artifact
    original = json.loads(path.read_text())
    for key, value in original.items():
        changed = dict(original)
        changed[key] = not value if isinstance(value, bool) else "CORRUPTED_FIELD"
        run.write_json(path, changed)
        run.reseal()
        with pytest.raises(run.verifier.VerificationError):
            run.verifier.verify(run.project, run.run_id)
        run.write_json(path, original)
    run.reseal()
    assert run.verifier.verify(run.project, run.run_id)["status"] == "PASS_R1ABC_INDEPENDENT_VERIFICATION"


@pytest.mark.parametrize("failure", ["tool_download", "download_page", "redirect", "curl_stderr", "version", "disk", "listing_diff"])
def test_full_r1a_failure_cannot_unlock_archive_test(mocked_recovery_run, failure):
    run = mocked_recovery_run
    run.failure = failure
    with pytest.raises(recovery.RecoveryError):
        run.phase("r1a")
    assert (run.paths.output / "R1A_BLOCKED.json").exists()
    assert not (run.paths.output / "R1A_SEAL.json").exists()
    with pytest.raises(recovery.RecoveryError):
        run.phase("r1b")
    assert not any(len(argv) > 1 and argv[1] in {"t", "x"} for argv in run.commands)


@pytest.mark.parametrize("failure", ["t_warning", "t_stderr", "t_timeout", "t_error", "t_returncode"])
def test_full_r1b_failure_never_extracts(mocked_recovery_run, failure):
    run = mocked_recovery_run
    run.phase("r1a")
    run.failure = failure
    with pytest.raises(recovery.RecoveryError):
        run.phase("r1b")
    assert (run.paths.output / "R1B_BLOCKED.json").exists()
    assert not (run.paths.output / "R1B_SEAL.json").exists()
    with pytest.raises(recovery.RecoveryError):
        run.phase("r1c")
    assert not run.paths.extraction.exists()
    assert not any(len(argv) > 1 and argv[1] == "x" for argv in run.commands)


@pytest.mark.parametrize("failure", ["extraction_crc", "extraction_symlink", "extraction_wrong_path", "x_warning", "x_stderr", "x_timeout", "x_error", "x_returncode"])
def test_full_r1c_failure_stays_quarantined(mocked_recovery_run, failure):
    run = mocked_recovery_run
    run.phase("r1a"); run.phase("r1b")
    run.failure = failure
    with pytest.raises(recovery.RecoveryError):
        run.phase("r1c")
    assert (run.paths.output / "R1C_BLOCKED.json").exists()
    assert not (run.paths.output / "R1C_SEAL.json").exists()
    with pytest.raises(run.verifier.VerificationError):
        run.verifier.verify(run.project, run.run_id)


@pytest.mark.parametrize("mutation", ["raw_transcript", "code", "test", "ignore", "ancestor_symlink", "extracted_bytes"])
def test_full_verifier_rejects_bound_inputs_and_containment_changes(mocked_recovery_run, mutation):
    run = mocked_recovery_run
    run.complete()
    targets = {"raw_transcript": run.paths.local / "evidence/ARCHIVE_TEST.stdout.raw",
               "code": run.project / "experiments/audit_cap/ren_p1r1_recovery.py",
               "test": run.project / "tests/test_ren_p1r1_recovery.py",
               "ignore": run.project / ".gitignore",
               "extracted_bytes": run.paths.extraction / next(iter(run.files))}
    if mutation == "ancestor_symlink":
        directory = run.paths.local / "evidence"
        replacement = run.paths.local / "moved_evidence"
        directory.rename(replacement)
        directory.symlink_to(replacement, target_is_directory=True)
    else:
        targets[mutation].write_bytes(b"mutated")
    with pytest.raises(run.verifier.VerificationError):
        run.verifier.verify(run.project, run.run_id)


def test_full_verifier_report_can_be_rechecked_and_cannot_be_forged(mocked_recovery_run):
    run = mocked_recovery_run
    result = run.complete()
    target = run.paths.output / run.verifier.VERIFICATION_REPORT
    run.write_json(target, result)
    assert run.verifier.verify(run.project, run.run_id) == result
    result["verified_regular_file_count"] = 999
    run.write_json(target, result)
    with pytest.raises(run.verifier.VerificationError, match="stored verification report"):
        run.verifier.verify(run.project, run.run_id)


@pytest.mark.parametrize("directory_lines,passed", [
    (b"Testing batch OK\n", True),
    (b"", False),
    (b"Testing unknown OK\n", False),
    (b"Testing batch OK\nTesting batch OK\n", False),
    (b"Testing batch OK\nTesting extra.xls OK\n", False),
])
def test_real_unrar_directory_ok_format_is_classified_by_ledger(monkeypatch, directory_lines, passed):
    import experiments.audit_cap.verify_ren_p1r1_recovery as verifier
    monkeypatch.setattr(recovery, "EXPECTED_FILE_COUNT", 1)
    monkeypatch.setattr(verifier, "FILE_COUNT", 1)
    stdout = b"Testing batch/a.xls OK\n" + directory_lines + b"All OK\n"
    result = recovery.CommandResult(("unrar",), 0, stdout, b"", False, False)
    evidence = recovery._command_record(result, argv_label=("unrar", "t", "-idp", "-p-", "FROZEN_RAW_RAR"))
    generated = recovery._archive_test_report(result, evidence, ["batch/a.xls"], ["batch"])
    rebuilt = verifier._rebuild_test_report(evidence, stdout, b"", ["batch/a.xls"], ["batch"])
    assert generated == rebuilt
    assert (generated["status"] == "PASS_ARCHIVE_TEST") is passed
    assert generated["observed_tested_file_count"] == 1
    assert generated["expected_tested_directory_count"] == 1
    if passed:
        assert generated["observed_tested_directory_count"] == 1
        assert generated["observed_tested_member_count"] == 2
