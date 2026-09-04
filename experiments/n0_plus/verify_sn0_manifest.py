"""Deterministically verify the N0+ SN0 preparation manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from experiments.n0_plus.registry import (
    PARENT_PROTOCOL_SHA256,
    PROPOSAL_SHA256,
    build_n0_plus_registry,
    parse_n0_plus_registry,
)
from experiments.vfps_agent.canonical import strict_json_loads


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "refine-logs" / "N0_PLUS_SN0_MANIFEST.json"
MANIFEST_SCHEMA_VERSION = "N0PlusSN0Manifest.v1"
EXPECTED_STATUS = "SN0_REGISTRY_AND_TIER_A_LOCK_COMPLETE_NO_MODEL_RUN"
EXPECTED_ARTIFACTS = frozenset(
    {
        "experiments/n0_plus/__init__.py",
        "experiments/n0_plus/registry.py",
        "experiments/n0_plus/verify_sn0_manifest.py",
        "refine-logs/N0_PLUS_APPROVAL_RECORD_20260904_141528.json",
        "refine-logs/N0_PLUS_CANDIDATE_REGISTRY_20260904_142140.json",
        "refine-logs/SPECIALIZED_MODEL_EXECUTION_TRACKER_20260904_142237.md",
        "refine-logs/SPECIALIZED_MODEL_NOVELTY_CHECK_20260904_141528.md",
        "requirements-n0-plus-tier-a.lock",
        "tests/test_n0_plus_registry.py",
        "tests/test_n0_plus_sn0_manifest.py",
    }
)


class SN0ManifestError(ValueError):
    """The SN0 manifest is malformed or an artifact has changed."""


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise SN0ManifestError(f"{label} keys differ")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_project_path(token: Any) -> Path:
    if not isinstance(token, str) or not token or token.strip() != token:
        raise SN0ManifestError("artifact path must be a canonical relative token")
    relative = Path(token)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != token:
        raise SN0ManifestError("artifact path escapes or is not normalized")
    return PROJECT_ROOT / relative


def verify_sn0_manifest(manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    payload = strict_json_loads(manifest_file.read_bytes())
    if not isinstance(payload, Mapping):
        raise SN0ManifestError("SN0 manifest must be an object")
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "created_at",
            "status",
            "parent_protocol_sha256",
            "proposal_sha256",
            "registry_payload_sha256",
            "environment",
            "checks",
            "artifacts",
            "not_authorized",
        },
        "manifest",
    )
    if payload["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise SN0ManifestError("unknown SN0 manifest version")
    if payload["status"] != EXPECTED_STATUS:
        raise SN0ManifestError("SN0 manifest grants or reports an unknown authority")
    if payload["parent_protocol_sha256"] != PARENT_PROTOCOL_SHA256:
        raise SN0ManifestError("parent protocol hash differs")
    if payload["proposal_sha256"] != PROPOSAL_SHA256:
        raise SN0ManifestError("approved proposal hash differs")
    if payload["registry_payload_sha256"] != build_n0_plus_registry().registry_hash:
        raise SN0ManifestError("registry payload hash differs")

    environment = payload["environment"]
    if not isinstance(environment, Mapping):
        raise SN0ManifestError("environment must be an object")
    _require_exact_keys(
        environment,
        {"python", "pip", "lock_path", "tier_b_installed"},
        "environment",
    )
    if environment["python"] != "3.12.3" or environment["pip"] != "24.0":
        raise SN0ManifestError("SN0 interpreter identity differs")
    if environment["lock_path"] != "requirements-n0-plus-tier-a.lock":
        raise SN0ManifestError("SN0 dependency lock path differs")
    if environment["tier_b_installed"] is not False:
        raise SN0ManifestError("Tier-B dependencies must remain outside SN0")

    checks = payload["checks"]
    if not isinstance(checks, Mapping):
        raise SN0ManifestError("checks must be an object")
    _require_exact_keys(
        checks,
        {"registry_tests", "full_regression", "pip_check", "tier_a_imports"},
        "checks",
    )
    expected_checks = {
        "registry_tests": "14 passed",
        "full_regression": "317 passed",
        "pip_check": "PASS",
        "tier_a_imports": "PASS",
    }
    if dict(checks) != expected_checks:
        raise SN0ManifestError("SN0 check record differs")

    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list):
        raise SN0ManifestError("artifacts must be an array")
    observed_paths: set[str] = set()
    for index, entry in enumerate(artifacts):
        if not isinstance(entry, Mapping):
            raise SN0ManifestError(f"artifact {index} must be an object")
        _require_exact_keys(entry, {"path", "bytes", "sha256"}, f"artifact {index}")
        path = _safe_project_path(entry["path"])
        if entry["path"] in observed_paths:
            raise SN0ManifestError("duplicate artifact path")
        observed_paths.add(entry["path"])
    if observed_paths != EXPECTED_ARTIFACTS:
        raise SN0ManifestError("artifact membership differs")

    for entry in artifacts:
        path = _safe_project_path(entry["path"])
        if not path.is_file():
            raise SN0ManifestError(f"artifact missing: {entry['path']}")
        if isinstance(entry["bytes"], bool) or not isinstance(entry["bytes"], int):
            raise SN0ManifestError("artifact byte count must be an integer")
        if entry["bytes"] != path.stat().st_size:
            raise SN0ManifestError(f"artifact size differs: {entry['path']}")
        if entry["sha256"] != _sha256_file(path):
            raise SN0ManifestError(f"artifact hash differs: {entry['path']}")

    registry_path = PROJECT_ROOT / "refine-logs" / "N0_PLUS_CANDIDATE_REGISTRY_20260904_142140.json"
    registry = parse_n0_plus_registry(registry_path.read_bytes(), canonical=False)
    if registry.registry_hash != payload["registry_payload_sha256"]:
        raise SN0ManifestError("registry artifact does not match its payload hash")

    approval = strict_json_loads(
        (PROJECT_ROOT / "refine-logs" / "N0_PLUS_APPROVAL_RECORD_20260904_141528.json").read_bytes()
    )
    if not isinstance(approval, Mapping) or approval.get("status") != "APPROVED_SN0_SCOPE_ONLY":
        raise SN0ManifestError("human approval record is missing or not SN0-scoped")
    if approval.get("proposal", {}).get("sha256") != PROPOSAL_SHA256:
        raise SN0ManifestError("approval does not bind the admitted proposal")

    lock_text = (PROJECT_ROOT / "requirements-n0-plus-tier-a.lock").read_text(encoding="utf-8")
    package_names = {
        line.split("==", 1)[0].casefold()
        for line in lock_text.splitlines()
        if line and not line.startswith("#") and "==" in line
    }
    if {"torch", "neuralforecast"} & package_names:
        raise SN0ManifestError("Tier-B packages leaked into the Tier-A lock")

    forbidden = payload["not_authorized"]
    if not isinstance(forbidden, list) or set(forbidden) != {
        "real_data_model_fit",
        "outer_test_score_or_reveal",
        "rul_prediction",
        "ark_or_external_model_api",
        "gpu_execution",
    }:
        raise SN0ManifestError("not-authorized boundary differs")
    return {
        "status": "PASS",
        "artifact_count": len(artifacts),
        "registry_payload_sha256": registry.registry_hash,
    }


def main() -> int:
    result = verify_sn0_manifest()
    print(
        "SN0 manifest PASS: "
        f"{result['artifact_count']} artifacts, registry={result['registry_payload_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
