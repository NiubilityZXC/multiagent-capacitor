from __future__ import annotations

import pytest

from experiments.vfps_agent.actions import (
    ActionSpace,
    BaseAction,
    BaseOperator,
)
from experiments.vfps_agent.arms import CAPArmId, FROZEN_CAP_ARM_SPECS, execute_arm
from experiments.vfps_agent.contracts import ForecastKey
from experiments.vfps_agent.registry import (
    CAPActionRegistry,
    ChampionBaseSpec,
    FeatureSpec,
    ForecastBundle,
    ForecastValue,
    FrozenFeatureRegistry,
    FrozenNumericalRegistry,
    ScaleSpec,
    TargetContract,
    WeightTemplate,
)
from experiments.vfps_agent.search import (
    EnumSearchConfig,
    LossRecord,
    SealedDevelopmentLossTable,
    SearchError,
    enumerate_action,
)
from experiments.vfps_agent.verifier import (
    IF_RESPONSE_SCHEMA_VERSION,
    VerificationError,
    verify_and_execute_if_representation,
)


MODELS = tuple(sorted(("m0", "m1", "m2", "m3", "m4", "m5")))
TEMPLATES = tuple(f"w{index}" for index in range(5))


def registry_fixture() -> CAPActionRegistry:
    cap = ForecastKey("capacity", 1, "F")
    rul = ForecastKey("rul", 1, "cycle")
    bundles = tuple(
        ForecastBundle(
            model,
            (
                ForecastValue.numeric(
                    cap,
                    point=1.0 + index / 20.0,
                    lower=0.8 + index / 20.0,
                    median=1.0 + index / 20.0,
                    upper=1.2 + index / 20.0,
                ),
                ForecastValue.rul_na(rul),
            ),
        )
        for index, model in enumerate(MODELS)
    )
    weight_sets = (
        (1, 0, 0, 0, 0, 0),
        (0, 1, 0, 0, 0, 0),
        (0.5, 0.5, 0, 0, 0, 0),
        (1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6),
        (0.5, 0, 0, 0, 0, 0.5),
    )
    templates = tuple(
        WeightTemplate.from_mapping(template, dict(zip(MODELS, weights)))
        for template, weights in zip(TEMPLATES, weight_sets)
    )
    b_star = BaseAction(BaseOperator.FALLBACK)
    numerical = FrozenNumericalRegistry(
        bundles,
        templates,
        ForecastBundle("fallback", bundles[0].forecasts),
        (ScaleSpec(cap.token, 0.1), ScaleSpec(rul.token, 1.0)),
        (
            TargetContract("capacity", "F", True, 0.0, 3.0),
            TargetContract("rul", "cycle", False),
        ),
        (ChampionBaseSpec(cap.token, b_star), ChampionBaseSpec(rul.token, b_star)),
    )
    features = FrozenFeatureRegistry(
        tuple(
            FeatureSpec(f"f{index}", ("a", "b", "c"), str(index) * 64)
            for index in range(5)
        )
    )
    return CAPActionRegistry(numerical, features)


def test_if1_is_only_a_representation_ablation_with_quotient_19() -> None:
    registry = registry_fixture()
    artifacts = []
    for key in registry.numerical.planned_keys:
        primary = registry.primary_actions(key.token)
        fallback = next(
            action for action in primary
            if action.transform is None and action.base.operator is BaseOperator.FALLBACK
        )
        if key.target == "rul":
            artifacts.append({"key": key.token, "action_id": fallback.action_id})
            continue
        emit = next(
            action for action in primary
            if action.transform is None
            and action.base.operator is BaseOperator.EMIT
            and action.base.reference_id == MODELS[1]
        )
        artifacts.append(
            {
                "key": key.token,
                "predicate": {"operator": "ATOM", "feature_id": "f0", "bin_id": "a"},
                "true_action_id": fallback.action_id,
                "false_action_id": emit.action_id,
            }
        )
    result = execute_arm(
        CAPArmId.IF1,
        {"schema_version": IF_RESPONSE_SCHEMA_VERSION, "artifacts": artifacts},
        registry=registry,
        feature_bins={f"f{index}": "a" for index in range(5)},
    )
    assert FROZEN_CAP_ARM_SPECS[CAPArmId.IF1].representation_only
    assert FROZEN_CAP_ARM_SPECS[CAPArmId.IF1].origin_specific_quotient == 19
    assert result.selected_abstention
    assert not result.error_fallback
    assert result.bundle is registry.numerical.fallback_bundle


def test_if1_malformed_artifact_fails_with_closed_verification_error() -> None:
    registry = registry_fixture()
    payload = {
        "schema_version": IF_RESPONSE_SCHEMA_VERSION,
        "artifacts": [{"action_id": "f" * 64}],
    }
    with pytest.raises(VerificationError, match="unknown or duplicate key"):
        verify_and_execute_if_representation(
            payload,
            feature_bins={f"f{index}": "a" for index in range(5)},
            registry=registry,
        )


def sealed_table(
    registry: CAPActionRegistry,
    *,
    action_space: ActionSpace,
    loss_by_action: dict[str, float],
    strata: tuple[str, ...] = ("rare", "other"),
) -> SealedDevelopmentLossTable:
    key = registry.numerical.planned_keys[0].token
    records = []
    for action in registry.actions_for(key, action_space):
        base_loss = loss_by_action.get(action.action_id, 1.0)
        for index, stratum in enumerate(strata):
            records.append(
                LossRecord(
                    key,
                    action.action_id,
                    f"{index + 1:064x}",
                    stratum,
                    base_loss,
                )
            )
    return SealedDevelopmentLossTable.seal(
        records,
        loss_name="macro_mae",
        feature_registry_hash=registry.features.feature_registry_hash,
        action_manifest_hash=registry.action_manifest_hash,
        action_space=action_space,
    )


def test_enum_action_exhausts_19_and_returns_exact_toy_argmin() -> None:
    registry = registry_fixture()
    key = registry.numerical.planned_keys[0].token
    actions = registry.actions_for(key, ActionSpace.PRIMARY19)
    toy_winner = actions[-1]
    table = sealed_table(
        registry,
        action_space=ActionSpace.PRIMARY19,
        loss_by_action={toy_winner.action_id: 0.01},
    )
    selection = enumerate_action(
        table=table,
        registry=registry,
        key_token=key,
        context_stratum="rare",
        config=EnumSearchConfig(n_min=1, lambda_z=1.0, kappa=0.0, eta=0.0),
    )
    assert selection.policy_name == "ENUM-ACTION"
    assert selection.action.action_id == toy_winner.action_id
    assert selection.evaluated_action_count == 19
    assert not selection.stratum_unqualified
    assert selection.selected_score == pytest.approx(0.01)


def test_under_supported_stratum_uses_global_mean_and_cluster_se() -> None:
    registry = registry_fixture()
    key = registry.numerical.planned_keys[0].token
    actions = registry.actions_for(key, ActionSpace.PRIMARY19)
    winner = actions[3]
    table = sealed_table(
        registry,
        action_space=ActionSpace.PRIMARY19,
        loss_by_action={winner.action_id: 0.1},
    )
    selection = enumerate_action(
        table=table,
        registry=registry,
        key_token=key,
        context_stratum="rare",
        config=EnumSearchConfig(n_min=2, lambda_z=100.0, kappa=1.0, eta=0.0),
    )
    assert selection.action.action_id == winner.action_id
    assert selection.stratum_unqualified
    selected_row = next(row for row in selection.scores if row.action_id == winner.action_id)
    assert selected_row.independent_stratum_clusters == 1
    assert selected_row.chosen_cluster_se == pytest.approx(0.0)
    assert selected_row.score == pytest.approx(selected_row.global_mean)


def test_enum_fixed_tie_is_complexity_then_canonical_action_hash() -> None:
    registry = registry_fixture()
    key = registry.numerical.planned_keys[0].token
    table = sealed_table(
        registry,
        action_space=ActionSpace.PRIMARY19,
        loss_by_action={},
    )
    selection = enumerate_action(
        table=table,
        registry=registry,
        key_token=key,
        context_stratum="absent",
        config=EnumSearchConfig(n_min=2, lambda_z=1.0, kappa=0.0, eta=0.0),
    )
    base_ids = sorted(
        action.action_id
        for action in registry.primary_actions(key)
        if action.complexity == 1
    )
    assert selection.action.action_id == base_ids[0]
    assert selection.stratum_unqualified


def test_enum_comp96_is_explicit_and_mechanically_scores_all_96() -> None:
    registry = registry_fixture()
    key = registry.numerical.planned_keys[0].token
    actions = registry.actions_for(key, ActionSpace.COMPOSITIONAL96)
    winner = actions[-5]
    table = sealed_table(
        registry,
        action_space=ActionSpace.COMPOSITIONAL96,
        loss_by_action={winner.action_id: 0.05},
    )
    selection = enumerate_action(
        table=table,
        registry=registry,
        key_token=key,
        context_stratum="rare",
        config=EnumSearchConfig(n_min=1, lambda_z=1.0, kappa=0.0, eta=0.0),
        action_space=ActionSpace.COMPOSITIONAL96,
    )
    assert selection.policy_name == "ENUM-COMP96"
    assert selection.evaluated_action_count == 96
    assert selection.action.action_id == winner.action_id


def test_search_refuses_unsealed_or_mixed_action_tables() -> None:
    registry = registry_fixture()
    key = registry.numerical.planned_keys[0].token
    table = sealed_table(registry, action_space=ActionSpace.COMPOSITIONAL96, loss_by_action={})
    with pytest.raises(SearchError, match="different action space"):
        enumerate_action(
            table=table,
            registry=registry,
            key_token=key,
            context_stratum="rare",
            config=EnumSearchConfig(1, 1.0, 0.0, 0.0),
            action_space=ActionSpace.PRIMARY19,
        )
    with pytest.raises(SearchError, match="seal"):
        SealedDevelopmentLossTable(
            table.records,
            table.loss_name,
            table.feature_registry_hash,
            table.action_manifest_hash,
            table.action_space,
            "0" * 64,
        )
