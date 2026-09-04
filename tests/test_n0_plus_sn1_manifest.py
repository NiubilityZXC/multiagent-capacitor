from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.n0_plus.verify_sn1_manifest import SN1ManifestError, verify_sn1_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "refine-logs" / "N0_PLUS_SN1_MANIFEST.json"


def _payload() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_checked_in_sn1_manifest_passes() -> None:
    assert verify_sn1_manifest()["status"] == "PASS"


def test_manifest_rejects_artifact_hash_drift(tmp_path: Path) -> None:
    payload = _payload()
    payload["artifacts"][0]["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    _write(path, payload)
    with pytest.raises(SN1ManifestError, match="artifact hash"):
        verify_sn1_manifest(path)


def test_manifest_rejects_scientific_authority_drift(tmp_path: Path) -> None:
    payload = _payload()
    payload["status"] = "REAL_DATA_ACCURACY_PASS"
    path = tmp_path / "manifest.json"
    _write(path, payload)
    with pytest.raises(SN1ManifestError, match="version or authority"):
        verify_sn1_manifest(path)


def test_manifest_rejects_removed_p2_gate(tmp_path: Path) -> None:
    payload = _payload()
    payload["not_authorized"].remove("p2_execution")
    path = tmp_path / "manifest.json"
    _write(path, payload)
    with pytest.raises(SN1ManifestError, match="not-authorized"):
        verify_sn1_manifest(path)


def test_manifest_rejects_path_escape(tmp_path: Path) -> None:
    payload = _payload()
    payload["artifacts"][0]["path"] = "../outside"
    path = tmp_path / "manifest.json"
    _write(path, payload)
    with pytest.raises(SN1ManifestError, match="escapes"):
        verify_sn1_manifest(path)
