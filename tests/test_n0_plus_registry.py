from __future__ import annotations

import json

import pytest

from experiments.n0_plus.registry import (
    CandidateRole,
    N0PlusRegistryError,
    build_n0_plus_registry,
    parse_n0_plus_registry,
)


def _payload() -> dict:
    return json.loads(build_n0_plus_registry().canonical_bytes)


def test_registry_has_finite_approved_membership_and_stable_roles() -> None:
    registry = build_n0_plus_registry()
    assert len(registry.candidates) == 15
    assert len(registry.selection_policy.selectable_candidate_ids) == 10
    assert sum(item.role is CandidateRole.DIAGNOSTIC_ONLY for item in registry.candidates) == 3
    assert sum(item.role is CandidateRole.ENDPOINT_GATED for item in registry.candidates) == 2
    assert registry.selection_policy.final_fallback_candidate_id == "legacy_n0_v1"
    assert registry.execution_authority == "SN0_SPEC_ONLY_NO_MODEL_RUN"
    assert registry.registry_hash == "37db56f94533df47ff1eb44524af9db62887bfc4c8bbe5792f2a86a18a9a702b"


def test_registry_round_trip_requires_canonical_bytes_by_default() -> None:
    registry = build_n0_plus_registry()
    parsed = parse_n0_plus_registry(registry.canonical_bytes)
    assert parsed == registry
    pretty = json.dumps(registry.payload(), ensure_ascii=False, indent=2)
    with pytest.raises(Exception):
        parse_n0_plus_registry(pretty)
    assert parse_n0_plus_registry(pretty, canonical=False) == registry


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: value.update(execution_authority="RUN_MODELS"),
        lambda value: value.update(proposal_sha256="0" * 64),
        lambda value: value["candidates"].pop(),
        lambda value: value["candidates"][0].update(extra="drift"),
        lambda value: value["selection_policy"].update(retry_on_failure=True),
        lambda value: value["selection_policy"].update(retry_on_failure=0),
        lambda value: value["selection_policy"].update(outer_labels_visible_to_selection=True),
        lambda value: value["selection_policy"].update(outer_labels_visible_to_selection="false"),
        lambda value: value["selection_policy"]["selectable_candidate_ids"].append(
            "tsfm_chronos_zero_shot"
        ),
        lambda value: value["selection_policy"].update(
            final_fallback_candidate_id="dlinear_direct"
        ),
    ),
)
def test_registry_rejects_authority_candidate_and_leakage_drift(mutate) -> None:
    payload = _payload()
    mutate(payload)
    with pytest.raises(N0PlusRegistryError):
        parse_n0_plus_registry(payload)


def test_rul_and_tsfm_candidates_cannot_enter_selection() -> None:
    registry = build_n0_plus_registry()
    selected = set(registry.selection_policy.selectable_candidate_ids)
    assert not any(item.candidate_id in selected for item in registry.candidates if item.role is not CandidateRole.SELECTABLE)


def test_registry_rejects_duplicate_json_keys() -> None:
    registry = build_n0_plus_registry()
    text = registry.canonical_bytes.decode("utf-8")
    tampered = text.replace(
        '"schema_version":"N0PlusCandidateRegistry.v1"',
        '"schema_version":"N0PlusCandidateRegistry.v1","schema_version":"N0PlusCandidateRegistry.v1"',
        1,
    )
    with pytest.raises(Exception):
        parse_n0_plus_registry(tampered, canonical=False)
