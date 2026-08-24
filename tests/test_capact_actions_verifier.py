from __future__ import annotations

import json

import pytest

from experiments.vfps_agent.actions import (
    ACTION_CARDINALITY,
    IF1_ORIGIN_SPECIFIC_QUOTIENT,
    IF1_SYNTACTIC_CARDINALITY,
    INFLATION_BINS,
    PRIMARY_ACTION_CARDINALITY,
    SHIFT_BINS,
    Action,
    ActionSchemaError,
    ActionSpace,
    BaseAction,
    BaseOperator,
    TransformOperator,
    build_action_fixture,
    build_if1_predicate_fixture,
    build_if1_program_fixture,
    parse_action,
)
from experiments.vfps_agent.arms import CAPArmId, FROZEN_CAP_ARM_SPECS, execute_arm
from experiments.vfps_agent.canonical import canonical_bytes
from experiments.vfps_agent.contracts import CommitDisposition, ForecastKey
from experiments.vfps_agent.registry import (
    CAPActionRegistry,
    ChampionBaseSpec,
    FeatureSpec,
    ForecastBundle,
    ForecastValue,
    FrozenFeatureRegistry,
    FrozenNumericalRegistry,
    RegistryError,
    ScaleSpec,
    TargetContract,
    WeightTemplate,
)
from experiments.vfps_agent.verifier import (
    ACTION_RESPONSE_SCHEMA_VERSION,
    DIRECT_RESPONSE_SCHEMA_VERSION,
)


MODEL_IDS = tuple(
    sorted(
        (
            "last_value",
            "held_prefix_drift",
            "local_linear",
            "log_linear_exponential",
            "causal_local_trend_kf",
            "ridge_causal_increment",
        )
    )
)
TEMPLATE_IDS = tuple(f"template_{index}" for index in range(5))


def make_registry() -> CAPActionRegistry:
    capacity_key = ForecastKey("capacity", 1, "F")
    rul_key = ForecastKey("rul", 1, "cycle")
    keys = (capacity_key, rul_key)
    bundles: list[ForecastBundle] = []
    for index, model_id in enumerate(MODEL_IDS):
        point = 1.0 + 0.1 * index
        bundles.append(
            ForecastBundle(
                model_id,
                (
                    ForecastValue.numeric(
                        capacity_key,
                        point=point,
                        lower=point - 0.2,
                        median=point,
                        upper=point + 0.2,
                    ),
                    ForecastValue.rul_na(rul_key),
                ),
            )
        )
    template_weights = (
        {model: float(index == 0) for index, model in enumerate(MODEL_IDS)},
        {model: 1.0 / 6.0 for model in MODEL_IDS},
        {model: float(index == 1) for index, model in enumerate(MODEL_IDS)},
        {model: (0.5 if index < 2 else 0.0) for index, model in enumerate(MODEL_IDS)},
        {model: (0.5 if index in (0, 5) else 0.0) for index, model in enumerate(MODEL_IDS)},
    )
    templates = tuple(
        WeightTemplate.from_mapping(template_id, weights)
        for template_id, weights in zip(TEMPLATE_IDS, template_weights)
    )
    champion = BaseAction(BaseOperator.FALLBACK)
    numerical = FrozenNumericalRegistry(
        model_bundles=tuple(bundles),
        weight_templates=templates,
        fallback_bundle=ForecastBundle("fallback", bundles[0].forecasts),
        scales=(ScaleSpec(capacity_key.token, 1.0), ScaleSpec(rul_key.token, 1.0)),
        target_contracts=(
            TargetContract("capacity", "F", True, 0.0, 2.0),
            TargetContract("rul", "cycle", False),
        ),
        champion_bases=(
            ChampionBaseSpec(capacity_key.token, champion),
            ChampionBaseSpec(rul_key.token, champion),
        ),
    )
    features = FrozenFeatureRegistry(
        tuple(
            FeatureSpec(f"feature_{index}", ("high", "low", "mid"), str(index) * 64)
            for index in range(5)
        )
    )
    return CAPActionRegistry(numerical, features)


def action_for(
    registry: CAPActionRegistry,
    key_token: str,
    *,
    base_operator: BaseOperator,
    transform: TransformOperator | None = None,
    reference_id: str | None = None,
    parameter: float | None = None,
    space: ActionSpace = ActionSpace.PRIMARY19,
) -> Action:
    for action in registry.actions_for(key_token, space):
        if (
            action.base.operator is base_operator
            and action.base.reference_id == reference_id
            and action.transform is transform
            and action.parameter == parameter
        ):
            return action
    raise AssertionError("requested action is not in fixture")


def selections_payload(registry: CAPActionRegistry, actions: dict[str, Action]) -> dict[str, object]:
    return {
        "schema_version": ACTION_RESPONSE_SCHEMA_VERSION,
        "selections": [
            {"key": key.token, "action_id": actions[key.token].action_id}
            for key in registry.numerical.planned_keys
        ],
    }


def test_exact_compositional_96_and_primary_19_are_distinct_frozen_manifests() -> None:
    registry = make_registry()
    fixture = build_action_fixture(MODEL_IDS, TEMPLATE_IDS)
    assert len(fixture) == ACTION_CARDINALITY == 96
    assert len({item.action_hash for item in fixture}) == 96
    assert sum(item.transform is None for item in fixture) == 12
    assert sum(item.transform is TransformOperator.SHIFT for item in fixture) == 48
    assert sum(item.transform is TransformOperator.INFLATE for item in fixture) == 36
    capacity, rul = registry.numerical.planned_keys
    assert len(registry.primary_actions(capacity.token)) == PRIMARY_ACTION_CARDINALITY == 19
    forced_rul = registry.primary_actions(rul.token)
    assert len(forced_rul) == 1
    assert forced_rul[0].transform is None
    assert forced_rul[0].base.operator is BaseOperator.FALLBACK
    assert IF1_ORIGIN_SPECIFIC_QUOTIENT == 19
    assert IF1_SYNTACTIC_CARDINALITY == 76_969
    assert FROZEN_CAP_ARM_SPECS[CAPArmId.ACT_COMP96].action_cardinality == 96


def test_if1_declared_grammar_is_materialized_not_only_counted() -> None:
    registry = make_registry()
    key = registry.numerical.planned_keys[0].token
    action_ids = tuple(item.action_id for item in registry.primary_actions(key))
    predicates = build_if1_predicate_fixture(
        {f"feature_{index}": ("high", "low", "mid") for index in range(5)}
    )
    programs = build_if1_program_fixture(action_ids, predicates)
    assert len(programs) == IF1_SYNTACTIC_CARDINALITY == 76_969
    assert sum(set(item) == {"action_id"} for item in programs) == 19
    assert sum(set(item) == {"predicate", "true_action_id", "false_action_id"} for item in programs) == 76_950


def test_each_action_has_strict_tagged_schema_and_canonical_hash() -> None:
    for action in build_action_fixture(MODEL_IDS, TEMPLATE_IDS):
        parsed = parse_action(action.canonical_bytes)
        assert parsed == action
        assert parsed.action_id == action.action_hash
        mutated = dict(action.payload())
        mutated["unexpected"] = True
        with pytest.raises(ActionSchemaError, match="keys"):
            parse_action(mutated)

    action = build_action_fixture(MODEL_IDS, TEMPLATE_IDS)[0]
    noncanonical = json.dumps(action.payload(), indent=2)
    with pytest.raises(Exception, match="canonical"):
        parse_action(noncanonical)
    assert parse_action(noncanonical, canonical=False) == action


def test_numerical_and_feature_registry_hashes_are_immutable_and_bstar_is_n0() -> None:
    registry = make_registry()
    numerical_hash = registry.numerical.numerical_registry_hash
    feature_hash = registry.features.feature_registry_hash
    action_hash = registry.action_manifest_hash
    with pytest.raises(TypeError):
        registry.numerical.model_map["new"] = registry.numerical.model_bundles[0]  # type: ignore[index]
    with pytest.raises(TypeError):
        registry.features.by_id["new"] = registry.features.features[0]  # type: ignore[index]
    assert registry.numerical.numerical_registry_hash == numerical_hash
    assert registry.features.feature_registry_hash == feature_hash
    assert registry.action_manifest_hash == action_hash
    for key in registry.numerical.planned_keys:
        b_star = registry.numerical.execute_base(registry.numerical.champion_map[key.token], key)
        assert canonical_bytes(b_star.payload()) == canonical_bytes(
            registry.numerical.fallback_bundle.by_key[key.token].payload()
        )


@pytest.mark.parametrize(
    "wrong",
    (
        BaseAction(BaseOperator.EMIT, MODEL_IDS[0]),
        BaseAction(BaseOperator.FUSE, TEMPLATE_IDS[0]),
    ),
)
def test_registry_rejects_champion_that_is_not_common_fallback(wrong: BaseAction) -> None:
    registry = make_registry()
    numerical = registry.numerical
    # Both the first model and first (one-hot) fusion are numerically
    # byte-identical to fallback in this fixture, but authority is defined by
    # literal action ID, not coincident values.
    with pytest.raises(RegistryError, match="literal common FALLBACK"):
        FrozenNumericalRegistry(
            numerical.model_bundles,
            numerical.weight_templates,
            numerical.fallback_bundle,
            numerical.scales,
            numerical.target_contracts,
            tuple(ChampionBaseSpec(key.token, wrong) for key in numerical.planned_keys),
        )


def test_h1_rf1_rc1_are_disjoint_and_their_exact_union_is_act1() -> None:
    registry = make_registry()
    key = registry.numerical.planned_keys[0].token
    primary = registry.primary_actions(key)
    h1_ids = {
        action.action_id
        for action in primary
        if action.transform is None and action.base.operator is BaseOperator.EMIT
    }
    rf1_ids = {
        action.action_id
        for action in primary
        if action.transform is None and action.base.operator is BaseOperator.FUSE
    }
    rc1_ids = {
        action.action_id
        for action in primary
        if action.base.operator is BaseOperator.FALLBACK
    }
    act1_ids = {action.action_id for action in primary}
    assert (len(h1_ids), len(rf1_ids), len(rc1_ids), len(act1_ids)) == (6, 5, 8, 19)
    assert h1_ids.isdisjoint(rf1_ids)
    assert h1_ids.isdisjoint(rc1_ids)
    assert rf1_ids.isdisjoint(rc1_ids)
    assert h1_ids | rf1_ids | rc1_ids == act1_ids


def test_arm_permissions_are_isolated_and_every_failure_is_exact_fallback() -> None:
    registry = make_registry()
    keys = registry.numerical.planned_keys
    emit = {
        key.token: action_for(
            registry,
            key.token,
            base_operator=(BaseOperator.EMIT if key.target != "rul" else BaseOperator.FALLBACK),
            reference_id=(MODEL_IDS[1] if key.target != "rul" else None),
        )
        for key in keys
    }
    h1 = execute_arm(CAPArmId.H1, selections_payload(registry, emit), registry=registry)
    assert h1.disposition is CommitDisposition.PREDICTION
    assert h1.bundle.by_key[keys[1].token].status.value == "RUL_NA"

    fuse = {
        key.token: action_for(
            registry,
            key.token,
            base_operator=(BaseOperator.FUSE if key.target != "rul" else BaseOperator.FALLBACK),
            reference_id=(TEMPLATE_IDS[1] if key.target != "rul" else None),
        )
        for key in keys
    }
    unauthorized = execute_arm(CAPArmId.H1, selections_payload(registry, fuse), registry=registry)
    assert unauthorized.error_fallback
    assert unauthorized.bundle is registry.numerical.fallback_bundle
    assert unauthorized.prediction_hash == registry.numerical.fallback_bundle.bundle_hash

    rf = execute_arm(CAPArmId.RF1, selections_payload(registry, fuse), registry=registry)
    assert not rf.fallback_used
    fused_point = rf.bundle.by_key[keys[0].token].point
    candidate_points = [bundle.by_key[keys[0].token].point for bundle in registry.numerical.model_bundles]
    assert min(candidate_points) <= fused_point <= max(candidate_points)


def test_rc1_is_eight_actions_on_bstar_and_comp96_cannot_leak_into_act1() -> None:
    registry = make_registry()
    keys = registry.numerical.planned_keys
    rc_actions: dict[str, Action] = {}
    for key in keys:
        champion = registry.numerical.champion_map[key.token]
        rc_actions[key.token] = action_for(
            registry,
            key.token,
            base_operator=champion.operator,
            reference_id=champion.reference_id,
            transform=(TransformOperator.INFLATE if key.target == "capacity" else None),
            parameter=(1.25 if key.target == "capacity" else None),
        )
    rc = execute_arm(CAPArmId.RC1, selections_payload(registry, rc_actions), registry=registry)
    assert not rc.fallback_used
    original = registry.numerical.fallback_bundle.by_key[keys[0].token]
    widened = rc.bundle.by_key[keys[0].token]
    assert widened.point == original.point
    assert widened.lower <= original.lower
    assert widened.upper >= original.upper

    illegal: dict[str, Action] = {}
    for key in keys:
        if key.target == "rul":
            illegal[key.token] = action_for(
                registry,
                key.token,
                base_operator=BaseOperator.FALLBACK,
                space=ActionSpace.COMPOSITIONAL96,
            )
            continue
        illegal[key.token] = action_for(
            registry,
            key.token,
            base_operator=BaseOperator.EMIT,
            reference_id=MODEL_IDS[-1],
            transform=TransformOperator.SHIFT,
            parameter=-0.5,
            space=ActionSpace.COMPOSITIONAL96,
        )
    assert execute_arm(CAPArmId.RC1, selections_payload(registry, illegal), registry=registry).error_fallback
    assert execute_arm(CAPArmId.ACT1, selections_payload(registry, illegal), registry=registry).error_fallback
    assert not execute_arm(
        CAPArmId.ACT_COMP96,
        selections_payload(registry, illegal),
        registry=registry,
    ).error_fallback


def test_trust_region_violation_and_missing_key_fall_back_as_whole_bundle() -> None:
    registry = make_registry()
    keys = registry.numerical.planned_keys
    actions: dict[str, Action] = {}
    for key in keys:
        champion = registry.numerical.champion_map[key.token]
        actions[key.token] = action_for(
            registry,
            key.token,
            base_operator=champion.operator,
            reference_id=champion.reference_id,
            transform=(TransformOperator.SHIFT if key.target == "capacity" else None),
            parameter=(1.0 if key.target == "capacity" else None),
        )
    violated = execute_arm(CAPArmId.RC1, selections_payload(registry, actions), registry=registry)
    assert violated.error_fallback
    assert violated.bundle is registry.numerical.fallback_bundle

    payload = selections_payload(registry, actions)
    payload["selections"] = payload["selections"][:-1]  # type: ignore[index]
    missing = execute_arm(CAPArmId.RC1, payload, registry=registry)
    assert missing.error_fallback
    assert missing.bundle is registry.numerical.fallback_bundle


def test_selected_abstention_is_not_miscounted_as_error_fallback() -> None:
    registry = make_registry()
    fallback_actions = {
        key.token: action_for(
            registry,
            key.token,
            base_operator=BaseOperator.FALLBACK,
        )
        for key in registry.numerical.planned_keys
    }
    result = execute_arm(
        CAPArmId.ACT1,
        selections_payload(registry, fallback_actions),
        registry=registry,
    )
    assert result.selected_abstention
    assert not result.error_fallback
    assert result.disposition is CommitDisposition.PREDICTION
    assert result.bundle is registry.numerical.fallback_bundle


def test_direct_arm_requires_complete_finite_bundle_and_blocked_rul_is_na() -> None:
    registry = make_registry()
    capacity, rul = registry.numerical.planned_keys
    response = {
        "schema_version": DIRECT_RESPONSE_SCHEMA_VERSION,
        "forecasts": [
            {
                "key": capacity.token,
                "status": "NUMERIC",
                "point": 0.9,
                "lower": 0.7,
                "median": 0.9,
                "upper": 1.1,
            },
            {"key": rul.token, "status": "RUL_NA"},
        ],
    }
    accepted = execute_arm(CAPArmId.D1_RAW, response, registry=registry)
    assert not accepted.error_fallback
    response["forecasts"][1] = {  # type: ignore[index]
        "key": rul.token,
        "status": "NUMERIC",
        "point": 10,
        "lower": 5,
        "median": 10,
        "upper": 15,
    }
    blocked = execute_arm(CAPArmId.D1_PACKET, response, registry=registry)
    assert blocked.error_fallback
    assert blocked.bundle is registry.numerical.fallback_bundle
