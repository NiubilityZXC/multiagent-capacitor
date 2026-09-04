from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.n0_plus.verify_sn0_manifest import (
    DEFAULT_MANIFEST_PATH,
    SN0ManifestError,
    verify_sn0_manifest,
)


def _manifest() -> dict:
    return json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))


def _write_manifest(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path


def test_checked_in_sn0_manifest_passes() -> None:
    result = verify_sn0_manifest()
    assert result["status"] == "PASS"
    assert result["artifact_count"] == 10


def test_manifest_rejects_artifact_hash_drift(tmp_path: Path) -> None:
    payload = _manifest()
    payload["artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(SN0ManifestError, match="artifact hash differs"):
        verify_sn0_manifest(_write_manifest(tmp_path, payload))


def test_manifest_rejects_extra_artifact(tmp_path: Path) -> None:
    payload = _manifest()
    payload["artifacts"].append(dict(payload["artifacts"][0]))
    payload["artifacts"][-1]["path"] = "MANIFEST.md"
    with pytest.raises(SN0ManifestError, match="artifact membership differs"):
        verify_sn0_manifest(_write_manifest(tmp_path, payload))


def test_manifest_rejects_path_escape(tmp_path: Path) -> None:
    payload = _manifest()
    payload["artifacts"][0]["path"] = "../outside"
    with pytest.raises(SN0ManifestError, match="escapes"):
        verify_sn0_manifest(_write_manifest(tmp_path, payload))


def test_manifest_rejects_execution_authority_drift(tmp_path: Path) -> None:
    payload = _manifest()
    payload["status"] = "MODEL_RUNS_ALLOWED"
    with pytest.raises(SN0ManifestError, match="unknown authority"):
        verify_sn0_manifest(_write_manifest(tmp_path, payload))
