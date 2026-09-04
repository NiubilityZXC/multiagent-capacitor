from __future__ import annotations

import pytest

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
