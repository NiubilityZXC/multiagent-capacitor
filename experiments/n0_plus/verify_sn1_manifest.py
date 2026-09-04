"""Verify the N0+ SN1 synthetic-only qualification manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from experiments.n0_plus.registry import (
    PARENT_PROTOCOL_SHA256,
    PROPOSAL_SHA256,
    build_n0_plus_registry,
)
from experiments.n0_plus.sn1_synthetic_models import (
    IMPLEMENTED_CANDIDATES,
    QUANTILE_LEVELS,
    SN1_AUTHORITY,
)
from experiments.vfps_agent.canonical import strict_canonical_loads, strict_json_loads


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "refine-logs" / "N0_PLUS_SN1_MANIFEST.json"
MANIFEST_SCHEMA_VERSION = "N0PlusSN1Manifest.v1"
EXPECTED_STATUS = "SN1_SYNTHETIC_CONTRACT_COMPLETE_NO_SCIENTIFIC_RESULT"
EXPECTED_ARTIFACTS = frozenset(
    {
        "experiments/n0_plus/run_sn1_synthetic_qualification.py",
        "experiments/n0_plus/sn1_synthetic_models.py",
        "experiments/n0_plus/verify_sn1_manifest.py",
        "refine-logs/N0_PLUS_APPROVAL_RECORD_20260904_141528.json",
        "refine-logs/N0_PLUS_CANDIDATE_REGISTRY_20260904_142140.json",
        "refine-logs/N0_PLUS_SN0_MANIFEST_20260904_142406.json",
        "refine-logs/N0_PLUS_SN1_CODE_REVIEW_20260904_144233.md",
        "refine-logs/N0_PLUS_SN1_SYNTHETIC_QUALIFICATION_20260904_144233.json",
        "refine-logs/SPECIALIZED_MODEL_EXECUTION_TRACKER_20260904_144233.md",
        "requirements-n0-plus-tier-a.lock",
        "tests/test_n0_plus_sn1_manifest.py",
        "tests/test_n0_plus_sn1_runner.py",
        "tests/test_n0_plus_sn1_synthetic_models.py",
    }
)
EXPECTED_NOT_AUTHORIZED = frozenset(
    {
        "real_data_model_fit",
        "outer_test_score_or_reveal",
        "accuracy_or_calibration_claim",
        "rul_prediction",
        "ark_or_external_model_api",
        "gpu_execution",
        "p2_execution",
    }
)
EXPECTED_P2_REPLACEMENTS = (
    "unit_origin_target_cutoff_identity",
    "train_evaluation_disjointness",
    "irregular_grid_and_target_domain_gate",
    "frozen_degradation_direction",
    "failure_ledger_and_whole_origin_fallback",
    "nested_loco_selection",
    "held_out_unit_balanced_calibration",
    "legacy_n0_integration",
    "dependency_artifact_hashes",
)


class SN1ManifestError(ValueError):
    """The SN1 manifest or its synthetic-only evidence is invalid."""


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise SN1ManifestError(f"{label} keys differ")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_project_path(token: Any) -> Path:
    if not isinstance(token, str) or not token or token.strip() != token:
        raise SN1ManifestError("artifact path must be a canonical relative token")
    relative = Path(token)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != token:
        raise SN1ManifestError("artifact path escapes or is not normalized")
    return PROJECT_ROOT / relative


def _verify_qualification(path: Path, expected_sha256: str) -> None:
    if _sha256_file(path) != expected_sha256:
        raise SN1ManifestError("qualification payload hash differs")
    payload = strict_canonical_loads(path.read_bytes())
    required = {
        "api_calls",
        "authority",
        "candidate_count",
        "environment",
        "evaluation_unit_disjoint",
        "gpu_runs",
        "horizons",
        "interval_claim",
        "outer_labels_accessed",
        "quantile_levels",
        "real_data_accessed",
        "records",
        "schema_version",
        "scientific_metrics_computed",
        "seed",
        "small_ml_interval_semantics",
        "status",
        "training_unit_count",
    }
    _require_exact_keys(payload, required, "qualification")
    if payload["status"] != "PASS_CONTRACT_ONLY_NO_SCIENTIFIC_RESULT":
        raise SN1ManifestError("qualification status exceeds the synthetic contract")
    if payload["authority"] != SN1_AUTHORITY:
        raise SN1ManifestError("qualification authority differs")
    if payload["quantile_levels"] != list(QUANTILE_LEVELS):
        raise SN1ManifestError("qualification quantile levels differ")
    records = payload["records"]
    if not isinstance(records, list) or len(records) != len(IMPLEMENTED_CANDIDATES):
        raise SN1ManifestError("qualification candidate records differ")
    if {record.get("candidate_id") for record in records if isinstance(record, Mapping)} != set(
        IMPLEMENTED_CANDIDATES
    ):
        raise SN1ManifestError("qualification candidate membership differs")
    expected_checks = {
        "complete_horizons",
        "deterministic",
        "finite",
        "nested_quantiles",
        "suffix_invariant",
    }
    for record in records:
        if not isinstance(record, Mapping):
            raise SN1ManifestError("qualification record must be an object")
        _require_exact_keys(
            record,
            {"candidate_id", "checks", "forecast_payload_sha256"},
            "qualification record",
        )
        checks = record["checks"]
        if not isinstance(checks, Mapping) or set(checks) != expected_checks or not all(
            value is True for value in checks.values()
        ):
            raise SN1ManifestError("qualification contract check did not pass")
    if any(
        payload[key] is not False
        for key in ("scientific_metrics_computed", "real_data_accessed", "outer_labels_accessed")
    ):
        raise SN1ManifestError("qualification accessed forbidden scientific evidence")
    if payload["api_calls"] != 0 or payload["gpu_runs"] != 0:
        raise SN1ManifestError("qualification used API or GPU resources")
    if payload["evaluation_unit_disjoint"] is not True:
        raise SN1ManifestError("synthetic evaluation unit is not disjoint")
    if payload["interval_claim"] != "SHAPE_ONLY_NOT_CALIBRATED":
        raise SN1ManifestError("qualification overstates interval evidence")
    if payload["small_ml_interval_semantics"] != "IN_SAMPLE_TOY_RESIDUAL_QUANTILES_NOT_VALID_FOR_P2":
        raise SN1ManifestError("small-ML interval warning differs")


def verify_sn1_manifest(manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    payload = strict_json_loads(Path(manifest_path).read_bytes())
    if not isinstance(payload, Mapping):
        raise SN1ManifestError("SN1 manifest must be an object")
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "created_at",
            "status",
            "parent_protocol_sha256",
            "proposal_sha256",
            "registry_payload_sha256",
            "sn0_manifest_sha256",
            "qualification_payload_sha256",
            "environment",
            "checks",
            "review",
            "claim_ceiling",
            "artifacts",
            "not_authorized",
            "required_before_p2",
        },
        "manifest",
    )
    if payload["schema_version"] != MANIFEST_SCHEMA_VERSION or payload["status"] != EXPECTED_STATUS:
        raise SN1ManifestError("SN1 manifest version or authority differs")
    if payload["parent_protocol_sha256"] != PARENT_PROTOCOL_SHA256:
        raise SN1ManifestError("parent protocol hash differs")
    if payload["proposal_sha256"] != PROPOSAL_SHA256:
        raise SN1ManifestError("approved proposal hash differs")
    if payload["registry_payload_sha256"] != build_n0_plus_registry().registry_hash:
        raise SN1ManifestError("registry payload hash differs")
    sn0_path = PROJECT_ROOT / "refine-logs" / "N0_PLUS_SN0_MANIFEST_20260904_142406.json"
    if payload["sn0_manifest_sha256"] != _sha256_file(sn0_path):
        raise SN1ManifestError("SN0 parent manifest hash differs")

    if payload["environment"] != {
        "python": "3.12.3",
        "numpy": "1.26.4",
        "scikit_learn": "1.5.1",
        "statsforecast": "2.1.1",
        "tier_b_installed": False,
    }:
        raise SN1ManifestError("SN1 environment identity differs")
    if payload["checks"] != {
        "targeted_sn1": "44 passed",
        "full_project_tests": "366 passed",
        "reviewer_recheck": "PASS_SYNTHETIC_CONTRACT_ONLY",
        "manifest_verifier": "PASS",
    }:
        raise SN1ManifestError("SN1 check record differs")
    if payload["review"] != {
        "model": "gpt-5.6-sol",
        "reasoning_effort": "xhigh",
        "independence": "same-family",
        "acceptance": "provisional",
    }:
        raise SN1ManifestError("review route differs")
    ceiling = payload["claim_ceiling"]
    if not isinstance(ceiling, str) or "synthetic-only" not in ceiling or "one-attempt" not in ceiling:
        raise SN1ManifestError("claim ceiling differs")
    if frozenset(payload["not_authorized"]) != EXPECTED_NOT_AUTHORIZED:
        raise SN1ManifestError("not-authorized boundary differs")
    if tuple(payload["required_before_p2"]) != EXPECTED_P2_REPLACEMENTS:
        raise SN1ManifestError("P2 replacement requirements differ")

    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list):
        raise SN1ManifestError("artifacts must be an array")
    observed: set[str] = set()
    for index, entry in enumerate(artifacts):
        if not isinstance(entry, Mapping):
            raise SN1ManifestError(f"artifact {index} must be an object")
        _require_exact_keys(entry, {"path", "bytes", "sha256"}, f"artifact {index}")
        path = _safe_project_path(entry["path"])
        if entry["path"] in observed:
            raise SN1ManifestError("duplicate artifact path")
        observed.add(entry["path"])
        if not path.is_file() or entry["bytes"] != path.stat().st_size:
            raise SN1ManifestError(f"artifact missing or byte count differs: {entry['path']}")
        if entry["sha256"] != _sha256_file(path):
            raise SN1ManifestError(f"artifact hash differs: {entry['path']}")
    if observed != EXPECTED_ARTIFACTS:
        raise SN1ManifestError("artifact membership differs")

    qualification = PROJECT_ROOT / "refine-logs" / "N0_PLUS_SN1_SYNTHETIC_QUALIFICATION_20260904_144233.json"
    _verify_qualification(qualification, payload["qualification_payload_sha256"])
    approval = strict_json_loads(
        (PROJECT_ROOT / "refine-logs" / "N0_PLUS_APPROVAL_RECORD_20260904_141528.json").read_bytes()
    )
    if approval.get("status") != "APPROVED_SN0_SCOPE_ONLY" or approval.get("proposal", {}).get(
        "sha256"
    ) != PROPOSAL_SHA256:
        raise SN1ManifestError("SN0-scoped human approval is absent")
    review_text = (
        PROJECT_ROOT / "refine-logs" / "N0_PLUS_SN1_CODE_REVIEW_20260904_144233.md"
    ).read_text(encoding="utf-8")
    if "PASS_SYNTHETIC_CONTRACT_ONLY" not in review_text or "不支持 accuracy" not in review_text:
        raise SN1ManifestError("review claim boundary differs")
    return {
        "status": "PASS",
        "artifact_count": len(artifacts),
        "qualification_payload_sha256": payload["qualification_payload_sha256"],
    }


def main() -> int:
    result = verify_sn1_manifest()
    print(
        "SN1 manifest PASS: "
        f"{result['artifact_count']} artifacts, qualification={result['qualification_payload_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
