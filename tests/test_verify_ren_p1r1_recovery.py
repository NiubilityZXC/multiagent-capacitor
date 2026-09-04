from __future__ import annotations

import json

import pytest

from experiments.audit_cap.verify_ren_p1r1_recovery import (
    VerificationError,
    _flags,
    _json,
)


def test_strict_json_rejects_duplicate_keys(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"a":1,"a":2}\n', encoding="utf-8")
    with pytest.raises(VerificationError, match="duplicate JSON key"):
        _json(path)


def test_strict_json_rejects_nonfinite(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"x":NaN}\n', encoding="utf-8")
    with pytest.raises(VerificationError, match="non-finite JSON"):
        _json(path)


def test_false_execution_flags_are_mandatory() -> None:
    with pytest.raises(VerificationError, match="model_or_api"):
        _flags({"model_or_api_executed": True, "numeric_target_emitted": False}, "x")
    with pytest.raises(VerificationError, match="numeric_target"):
        _flags({"model_or_api_executed": False, "numeric_target_emitted": True}, "x")


def test_false_execution_flags_accept_only_literal_false() -> None:
    _flags({"model_or_api_executed": False, "numeric_target_emitted": False}, "x")
