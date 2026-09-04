"""Typed, model-free registry for the approved N0+ SN0 preparation stage.

This module deliberately contains no data loader, estimator, scorer, provider,
network call, or dependency installer.  It freezes which candidate identities
may be implemented and which identities may participate in fold-local N0+
selection.  Executable estimators and their dependency/version hashes remain a
later pre-seal artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from experiments.vfps_agent.canonical import (
    canonical_bytes,
    canonical_sha256,
    strict_canonical_loads,
    strict_json_loads,
)


REGISTRY_SCHEMA_VERSION = "N0PlusCandidateRegistry.v1"
POLICY_SCHEMA_VERSION = "N0PlusSelectionPolicy.v1"
PARENT_PROTOCOL_SHA256 = "df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2"
PROPOSAL_SHA256 = "81da8aa72b79fb43d5c3bb94686b497c6fea5245ca02dcf7f6e63c4193c74b33"


class N0PlusRegistryError(ValueError):
    """The candidate registry differs from the approved SN0 draft."""


class CandidateTier(str, Enum):
    TIER_A_CPU_REQUIRED = "TIER_A_CPU_REQUIRED"
    TIER_B_COMPUTE_GATE = "TIER_B_COMPUTE_GATE"
    TIER_C_SEPARATE_STRESS = "TIER_C_SEPARATE_STRESS"
    CONDITIONAL_RUL_ADDENDUM = "CONDITIONAL_RUL_ADDENDUM"


class CandidateRole(str, Enum):
    SELECTABLE = "SELECTABLE"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    ENDPOINT_GATED = "ENDPOINT_GATED"


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    candidate_id: str
    family_id: str
    tier: CandidateTier
    role: CandidateRole
    implementation_status: str

    def __post_init__(self) -> None:
        for label, value in (
            ("candidate_id", self.candidate_id),
            ("family_id", self.family_id),
            ("implementation_status", self.implementation_status),
        ):
            if not isinstance(value, str) or not value or value.strip() != value:
                raise N0PlusRegistryError(f"{label} must be a non-empty canonical token")
        if not isinstance(self.tier, CandidateTier) or not isinstance(self.role, CandidateRole):
            raise N0PlusRegistryError("candidate tier and role must use frozen enums")
        expected_role = {
            CandidateTier.TIER_A_CPU_REQUIRED: CandidateRole.SELECTABLE,
            CandidateTier.TIER_B_COMPUTE_GATE: CandidateRole.SELECTABLE,
            CandidateTier.TIER_C_SEPARATE_STRESS: CandidateRole.DIAGNOSTIC_ONLY,
            CandidateTier.CONDITIONAL_RUL_ADDENDUM: CandidateRole.ENDPOINT_GATED,
        }[self.tier]
        if self.role is not expected_role:
            raise N0PlusRegistryError("candidate role is incompatible with its frozen tier")
        if self.implementation_status != "SPEC_ONLY_NOT_EXECUTABLE":
            raise N0PlusRegistryError("SN0 registry candidates must remain non-executable specs")

    def payload(self) -> dict[str, str]:
        return {
            "candidate_id": self.candidate_id,
            "family_id": self.family_id,
            "tier": self.tier.value,
            "role": self.role.value,
            "implementation_status": self.implementation_status,
        }


@dataclass(frozen=True, slots=True)
class SelectionPolicySpec:
    selectable_candidate_ids: tuple[str, ...]
    family_tie_order: tuple[str, ...]
    final_fallback_candidate_id: str
    inner_split: str = "NESTED_WHOLE_UNIT_LOCO"
    aggregation: str = "UNIT_MACRO_PRIMARY_RISK"
    outer_labels_visible_to_selection: bool = False
    retry_on_failure: bool = False

    def __post_init__(self) -> None:
        selectable = tuple(self.selectable_candidate_ids)
        tie_order = tuple(self.family_tie_order)
        object.__setattr__(self, "selectable_candidate_ids", selectable)
        object.__setattr__(self, "family_tie_order", tie_order)
        if not selectable or len(selectable) != len(set(selectable)):
            raise N0PlusRegistryError("selectable candidates must be non-empty and unique")
        if selectable != tuple(sorted(selectable)):
            raise N0PlusRegistryError("selectable candidate IDs must be canonically ordered")
        if not tie_order or len(tie_order) != len(set(tie_order)):
            raise N0PlusRegistryError("family tie order must be non-empty and unique")
        if self.final_fallback_candidate_id not in selectable:
            raise N0PlusRegistryError("final fallback must be a selectable candidate")
        if not isinstance(self.outer_labels_visible_to_selection, bool):
            raise N0PlusRegistryError("outer-label visibility must be boolean")
        if not isinstance(self.retry_on_failure, bool):
            raise N0PlusRegistryError("retry flag must be boolean")
        if self.inner_split != "NESTED_WHOLE_UNIT_LOCO":
            raise N0PlusRegistryError("N0+ selection must use nested whole-unit LOCO")
        if self.aggregation != "UNIT_MACRO_PRIMARY_RISK":
            raise N0PlusRegistryError("N0+ selection must use unit-macro primary risk")
        if self.outer_labels_visible_to_selection:
            raise N0PlusRegistryError("outer labels must remain invisible to selection")
        if self.retry_on_failure:
            raise N0PlusRegistryError("accuracy selection cannot retry failures")

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": POLICY_SCHEMA_VERSION,
            "selectable_candidate_ids": list(self.selectable_candidate_ids),
            "family_tie_order": list(self.family_tie_order),
            "final_fallback_candidate_id": self.final_fallback_candidate_id,
            "inner_split": self.inner_split,
            "aggregation": self.aggregation,
            "outer_labels_visible_to_selection": self.outer_labels_visible_to_selection,
            "retry_on_failure": self.retry_on_failure,
        }


@dataclass(frozen=True, slots=True)
class N0PlusRegistry:
    candidates: tuple[CandidateSpec, ...]
    selection_policy: SelectionPolicySpec
    parent_protocol_sha256: str = PARENT_PROTOCOL_SHA256
    proposal_sha256: str = PROPOSAL_SHA256
    execution_authority: str = "SN0_SPEC_ONLY_NO_MODEL_RUN"

    def __post_init__(self) -> None:
        candidates = tuple(self.candidates)
        object.__setattr__(self, "candidates", candidates)
        if not all(isinstance(item, CandidateSpec) for item in candidates):
            raise N0PlusRegistryError("candidates must use typed CandidateSpec values")
        identifiers = tuple(item.candidate_id for item in candidates)
        if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(set(identifiers)):
            raise N0PlusRegistryError("candidate IDs must be unique and canonically ordered")
        if tuple(item.payload() for item in candidates) != tuple(
            item.payload() for item in _expected_candidates()
        ):
            raise N0PlusRegistryError("candidate membership differs from the approved SN0 draft")
        by_id = {item.candidate_id: item for item in candidates}
        selectable = self.selection_policy.selectable_candidate_ids
        if tuple(sorted(item.candidate_id for item in candidates if item.role is CandidateRole.SELECTABLE)) != selectable:
            raise N0PlusRegistryError("selection policy must include every and only SELECTABLE candidate")
        selected_families = {by_id[candidate_id].family_id for candidate_id in selectable}
        if set(self.selection_policy.family_tie_order) != selected_families:
            raise N0PlusRegistryError("family tie order must cover every selectable family exactly once")
        if self.selection_policy.final_fallback_candidate_id != "legacy_n0_v1":
            raise N0PlusRegistryError("legacy_n0_v1 is the sole SN0 final fallback")
        if self.parent_protocol_sha256 != PARENT_PROTOCOL_SHA256:
            raise N0PlusRegistryError("parent protocol hash differs")
        if self.proposal_sha256 != PROPOSAL_SHA256:
            raise N0PlusRegistryError("approved proposal hash differs")
        if self.execution_authority != "SN0_SPEC_ONLY_NO_MODEL_RUN":
            raise N0PlusRegistryError("candidate registry cannot grant model execution authority")

    @property
    def by_id(self) -> Mapping[str, CandidateSpec]:
        return MappingProxyType({item.candidate_id: item for item in self.candidates})

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "parent_protocol_sha256": self.parent_protocol_sha256,
            "proposal_sha256": self.proposal_sha256,
            "execution_authority": self.execution_authority,
            "candidates": [item.payload() for item in self.candidates],
            "selection_policy": self.selection_policy.payload(),
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.payload())

    @property
    def registry_hash(self) -> str:
        return canonical_sha256(self.payload())


def _candidate(
    candidate_id: str,
    family_id: str,
    tier: CandidateTier,
    role: CandidateRole,
) -> CandidateSpec:
    return CandidateSpec(candidate_id, family_id, tier, role, "SPEC_ONLY_NOT_EXECUTABLE")


def _expected_candidates() -> tuple[CandidateSpec, ...]:
    specs = (
        _candidate(
            "classical_autoarima",
            "classical",
            CandidateTier.TIER_A_CPU_REQUIRED,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "classical_autoets",
            "classical",
            CandidateTier.TIER_A_CPU_REQUIRED,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "classical_dynamic_optimized_theta",
            "classical",
            CandidateTier.TIER_A_CPU_REQUIRED,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "dlinear_direct",
            "dlinear",
            CandidateTier.TIER_B_COMPUTE_GATE,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "legacy_n0_v1",
            "legacy",
            CandidateTier.TIER_A_CPU_REQUIRED,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "nhits_direct",
            "nhits",
            CandidateTier.TIER_B_COMPUTE_GATE,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "online_ssm_rls_rels_trend",
            "online_ssm",
            CandidateTier.TIER_A_CPU_REQUIRED,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "online_ssm_robust_local_trend_pf",
            "online_ssm",
            CandidateTier.TIER_A_CPU_REQUIRED,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "rul_physics_constrained",
            "conditional_rul",
            CandidateTier.CONDITIONAL_RUL_ADDENDUM,
            CandidateRole.ENDPOINT_GATED,
        ),
        _candidate(
            "rul_s4_revin",
            "conditional_rul",
            CandidateTier.CONDITIONAL_RUL_ADDENDUM,
            CandidateRole.ENDPOINT_GATED,
        ),
        _candidate(
            "small_ml_elastic_net_direct",
            "small_ml",
            CandidateTier.TIER_A_CPU_REQUIRED,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "small_ml_hist_gradient_boosting_direct",
            "small_ml",
            CandidateTier.TIER_A_CPU_REQUIRED,
            CandidateRole.SELECTABLE,
        ),
        _candidate(
            "tsfm_chronos_zero_shot",
            "tsfm_stress",
            CandidateTier.TIER_C_SEPARATE_STRESS,
            CandidateRole.DIAGNOSTIC_ONLY,
        ),
        _candidate(
            "tsfm_moirai_zero_shot",
            "tsfm_stress",
            CandidateTier.TIER_C_SEPARATE_STRESS,
            CandidateRole.DIAGNOSTIC_ONLY,
        ),
        _candidate(
            "tsfm_timesfm_zero_shot",
            "tsfm_stress",
            CandidateTier.TIER_C_SEPARATE_STRESS,
            CandidateRole.DIAGNOSTIC_ONLY,
        ),
    )
    return tuple(sorted(specs, key=lambda item: item.candidate_id))


def build_n0_plus_registry() -> N0PlusRegistry:
    candidates = _expected_candidates()
    selectable = tuple(
        sorted(item.candidate_id for item in candidates if item.role is CandidateRole.SELECTABLE)
    )
    policy = SelectionPolicySpec(
        selectable_candidate_ids=selectable,
        family_tie_order=("legacy", "classical", "online_ssm", "small_ml", "dlinear", "nhits"),
        final_fallback_candidate_id="legacy_n0_v1",
    )
    return N0PlusRegistry(candidates, policy)


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise N0PlusRegistryError(f"{label} keys differ from the frozen schema")


def parse_n0_plus_registry(
    payload: str | bytes | bytearray | Mapping[str, Any],
    *,
    canonical: bool = True,
) -> N0PlusRegistry:
    if isinstance(payload, Mapping):
        value: Any = dict(payload)
    elif canonical:
        value = strict_canonical_loads(payload)
    else:
        value = strict_json_loads(payload)
    if not isinstance(value, Mapping):
        raise N0PlusRegistryError("candidate registry must be an object")
    _require_exact_keys(
        value,
        {
            "schema_version",
            "parent_protocol_sha256",
            "proposal_sha256",
            "execution_authority",
            "candidates",
            "selection_policy",
        },
        "candidate registry",
    )
    if value["schema_version"] != REGISTRY_SCHEMA_VERSION:
        raise N0PlusRegistryError("unknown candidate registry schema version")
    raw_candidates = value["candidates"]
    if not isinstance(raw_candidates, list):
        raise N0PlusRegistryError("candidates must be an array")
    candidates: list[CandidateSpec] = []
    for index, raw in enumerate(raw_candidates):
        if not isinstance(raw, Mapping):
            raise N0PlusRegistryError(f"candidate {index} must be an object")
        _require_exact_keys(
            raw,
            {"candidate_id", "family_id", "tier", "role", "implementation_status"},
            f"candidate {index}",
        )
        try:
            tier = CandidateTier(raw["tier"])
            role = CandidateRole(raw["role"])
        except (TypeError, ValueError) as exc:
            raise N0PlusRegistryError(f"candidate {index} uses an unknown enum") from exc
        candidates.append(
            CandidateSpec(
                raw["candidate_id"],
                raw["family_id"],
                tier,
                role,
                raw["implementation_status"],
            )
        )
    raw_policy = value["selection_policy"]
    if not isinstance(raw_policy, Mapping):
        raise N0PlusRegistryError("selection_policy must be an object")
    _require_exact_keys(
        raw_policy,
        {
            "schema_version",
            "selectable_candidate_ids",
            "family_tie_order",
            "final_fallback_candidate_id",
            "inner_split",
            "aggregation",
            "outer_labels_visible_to_selection",
            "retry_on_failure",
        },
        "selection policy",
    )
    if raw_policy["schema_version"] != POLICY_SCHEMA_VERSION:
        raise N0PlusRegistryError("unknown selection policy schema version")
    for name in ("selectable_candidate_ids", "family_tie_order"):
        if not isinstance(raw_policy[name], list) or not all(
            isinstance(item, str) for item in raw_policy[name]
        ):
            raise N0PlusRegistryError(f"{name} must be an array of strings")
    policy = SelectionPolicySpec(
        selectable_candidate_ids=tuple(raw_policy["selectable_candidate_ids"]),
        family_tie_order=tuple(raw_policy["family_tie_order"]),
        final_fallback_candidate_id=raw_policy["final_fallback_candidate_id"],
        inner_split=raw_policy["inner_split"],
        aggregation=raw_policy["aggregation"],
        outer_labels_visible_to_selection=raw_policy["outer_labels_visible_to_selection"],
        retry_on_failure=raw_policy["retry_on_failure"],
    )
    return N0PlusRegistry(
        tuple(candidates),
        policy,
        parent_protocol_sha256=value["parent_protocol_sha256"],
        proposal_sha256=value["proposal_sha256"],
        execution_authority=value["execution_authority"],
    )
