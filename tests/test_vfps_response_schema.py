from __future__ import annotations

from dataclasses import FrozenInstanceError
import re

import pytest

from experiments.vfps_agent.actions import (
    ActionSpace,
    BaseAction,
    BaseOperator,
)
from experiments.vfps_agent.canonical import to_primitive
from experiments.vfps_agent.contracts import (
    ArmId,
    FROZEN_ARM_SPECS,
    ForecastKey,
    ResponsePermission,
)
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
from experiments.vfps_agent.response_schema import (
    CanonicalResponseSchemaRegistry,
    ResponseParserKind,
    ResponseSchemaDefinitionError,
    ResponseSchemaValidationError,
    build_response_schema_registry,
    validate_response_payload,
    validate_schema_definition,
)
from experiments.vfps_agent.verifier import (
    ACTION_RESPONSE_SCHEMA_VERSION,
    DIRECT_RESPONSE_SCHEMA_VERSION,
    IF_RESPONSE_SCHEMA_VERSION,
    ActionAuthority,
    VerificationError,
    parse_direct_bundle,
    verify_and_execute_actions,
    verify_and_execute_if_representation,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TEMPLATES = tuple(f"w{index}" for index in range(5))


def make_registry(
    *,
    maximum: float = 3.0,
    feature_suffix: str = "",
    model_prefix: str = "m",
) -> CAPActionRegistry:
    capacity = ForecastKey("capacity", 1, "F")
    rul = ForecastKey("rul", 1, "cycle")
    model_ids = tuple(f"{model_prefix}{index}" for index in range(6))
    bundles = tuple(
        ForecastBundle(
            model_id,
            (
                ForecastValue.numeric(
                    capacity,
                    point=1.0 + index / 20.0,
                    lower=0.8 + index / 20.0,
                    median=1.0 + index / 20.0,
                    upper=1.2 + index / 20.0,
                ),
                ForecastValue.rul_na(rul),
            ),
        )
        for index, model_id in enumerate(model_ids)
    )
    weight_sets = (
        (1, 0, 0, 0, 0, 0),
        (0, 1, 0, 0, 0, 0),
        (0.5, 0.5, 0, 0, 0, 0),
        (1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6),
        (0.5, 0, 0, 0, 0, 0.5),
    )
    templates = tuple(
        WeightTemplate.from_mapping(template_id, dict(zip(model_ids, weights)))
        for template_id, weights in zip(_TEMPLATES, weight_sets)
    )
    fallback = BaseAction(BaseOperator.FALLBACK)
    numerical = FrozenNumericalRegistry(
        model_bundles=bundles,
        weight_templates=templates,
        fallback_bundle=ForecastBundle("fallback", bundles[0].forecasts),
        scales=(ScaleSpec(capacity.token, 0.1), ScaleSpec(rul.token, 1.0)),
        target_contracts=(
            TargetContract("capacity", "F", True, 0.0, maximum),
            TargetContract("rul", "cycle", False),
        ),
        champion_bases=(
            ChampionBaseSpec(capacity.token, fallback),
            ChampionBaseSpec(rul.token, fallback),
        ),
    )
    features = FrozenFeatureRegistry(
        tuple(
            FeatureSpec(
                f"f{index}",
                (f"a{feature_suffix}", f"b{feature_suffix}", f"c{feature_suffix}"),
                f"{index + 1:064x}",
            )
            for index in range(5)
        )
    )
    return CAPActionRegistry(numerical, features)


def _action_payload(spec: object) -> dict[str, object]:
    allowed = spec.allowed_action_ids  # type: ignore[attr-defined]
    return {
        "schema_version": ACTION_RESPONSE_SCHEMA_VERSION,
        "selections": [
            {"key": key, "action_id": action_ids[0]}
            for key, action_ids in allowed.items()
        ],
    }


def _direct_payload(registry: CAPActionRegistry) -> dict[str, object]:
    return {
        "schema_version": DIRECT_RESPONSE_SCHEMA_VERSION,
        "forecasts": [
            item.payload() for item in registry.numerical.fallback_bundle.forecasts
        ],
    }


def test_registry_covers_contract_authority_and_is_deeply_immutable() -> None:
    source = make_registry()
    schemas = build_response_schema_registry(source)

    assert isinstance(schemas, CanonicalResponseSchemaRegistry)
    assert tuple(schemas.by_arm) == tuple(ArmId)
    assert _SHA256_RE.fullmatch(schemas.registry_hash)
    assert schemas.registry_hash == schemas.response_registry_hash
    assert schemas.action_manifest_hash == source.action_manifest_hash

    local_arms = {ArmId.N0, ArmId.ENUM_ACTION, ArmId.ENUM_COMP96}
    for arm_id in ArmId:
        spec = schemas.spec_for(arm_id)
        authority = FROZEN_ARM_SPECS[arm_id]
        assert spec.permission is authority.permission
        assert spec.packet_kind is authority.packet_kind
        assert spec.physical_calls == authority.physical_calls
        assert _SHA256_RE.fullmatch(spec.spec_manifest_hash)
        assert _SHA256_RE.fullmatch(spec.planned_keys_hash)
        if arm_id in local_arms:
            assert spec.parser_kind is ResponseParserKind.NONE
            assert spec.response_schema is None
            assert spec.response_schema_hash is None
            with pytest.raises(ResponseSchemaValidationError):
                validate_response_payload({}, spec)
        else:
            assert spec.response_schema is not None
            assert _SHA256_RE.fullmatch(spec.response_schema_hash or "")
            validate_schema_definition(spec.response_schema)

    direct = schemas.spec_for(ArmId.D1_RAW)
    assert direct.response_schema is not None
    with pytest.raises(TypeError):
        direct.response_schema["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        direct.response_schema["properties"]["forecasts"]["maxItems"] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        direct.allowed_action_ids["new"] = ()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        direct.permission = ResponsePermission.NONE  # type: ignore[misc]


def test_every_permission_has_the_exact_registry_owned_action_ids() -> None:
    registry = make_registry()
    schemas = build_response_schema_registry(registry)
    capacity, rul = (key.token for key in registry.numerical.planned_keys)

    h1 = set(schemas.spec_for(ArmId.H1).allowed_action_ids[capacity])
    rf1 = set(schemas.spec_for(ArmId.RF1).allowed_action_ids[capacity])
    rc1 = set(schemas.spec_for(ArmId.RC1).allowed_action_ids[capacity])
    act1 = set(schemas.spec_for(ArmId.ACT1).allowed_action_ids[capacity])
    if1 = set(schemas.spec_for(ArmId.IF1).allowed_action_ids[capacity])
    comp96 = set(schemas.spec_for(ArmId.ACT_COMP96).allowed_action_ids[capacity])

    assert (len(h1), len(rf1), len(rc1), len(act1), len(if1), len(comp96)) == (
        6,
        5,
        8,
        19,
        19,
        96,
    )
    assert not h1 & rf1
    assert not h1 & rc1
    assert not rf1 & rc1
    assert h1 | rf1 | rc1 == act1 == if1
    assert act1 < comp96

    for action_id in h1:
        action = registry.resolve(
            action_id, key_token=capacity, action_space=ActionSpace.PRIMARY19
        )
        assert action.transform is None
        assert action.base.operator is BaseOperator.EMIT
    for action_id in rf1:
        action = registry.resolve(
            action_id, key_token=capacity, action_space=ActionSpace.PRIMARY19
        )
        assert action.transform is None
        assert action.base.operator is BaseOperator.FUSE
    champion = registry.numerical.champion_map[capacity]
    for action_id in rc1:
        action = registry.resolve(
            action_id, key_token=capacity, action_space=ActionSpace.PRIMARY19
        )
        assert action.base.action_id == champion.action_id

    forced_ids = {
        tuple(schemas.spec_for(arm).allowed_action_ids[rul])
        for arm in (ArmId.H1, ArmId.RF1, ArmId.RC1, ArmId.ACT1, ArmId.IF1, ArmId.ACT_COMP96)
    }
    assert len(forced_ids) == 1
    forced = next(iter(forced_ids))
    assert len(forced) == 1
    assert registry.resolve(
        forced[0], key_token=rul, action_space=ActionSpace.PRIMARY19
    ).base.operator is BaseOperator.FALLBACK

    assert schemas.spec_for(ArmId.H1).action_authority is ActionAuthority.H1
    assert schemas.spec_for(ArmId.RF1).action_authority is ActionAuthority.RF1
    assert schemas.spec_for(ArmId.RC1).action_authority is ActionAuthority.RC1
    assert schemas.spec_for(ArmId.ACT1).certificate_action_space == "PRIMARY19"
    assert schemas.spec_for(ArmId.IF1).certificate_action_space == "PRIMARY19"
    assert schemas.spec_for(ArmId.ACT_COMP96).certificate_action_space == "COMPOSITIONAL96"


def test_schema_and_manifest_hashes_are_deterministic_and_drift_sensitive() -> None:
    base = build_response_schema_registry(make_registry())
    same = build_response_schema_registry(make_registry())
    assert base.registry_hash == same.registry_hash
    assert tuple(spec.spec_manifest_hash for spec in base.specs) == tuple(
        spec.spec_manifest_hash for spec in same.specs
    )

    raw = base.spec_for(ArmId.D1_RAW)
    packet = base.spec_for(ArmId.D1_PACKET)
    assert raw.response_schema_hash == packet.response_schema_hash
    action_family = (
        ArmId.H1,
        ArmId.RF1,
        ArmId.RC1,
        ArmId.ACT1,
        ArmId.IF1,
        ArmId.ACT_COMP96,
    )
    assert len(
        {base.spec_for(arm).response_schema_hash for arm in action_family}
    ) == len(action_family)

    bounds_drift = build_response_schema_registry(make_registry(maximum=4.0))
    assert raw.response_schema_hash != bounds_drift.spec_for(ArmId.D1_RAW).response_schema_hash
    # Action IDs do not encode target bounds, but the typed spec manifest binds
    # the changed numerical/action registry authority.
    assert (
        base.spec_for(ArmId.H1).response_schema_hash
        == bounds_drift.spec_for(ArmId.H1).response_schema_hash
    )
    assert (
        base.spec_for(ArmId.H1).spec_manifest_hash
        != bounds_drift.spec_for(ArmId.H1).spec_manifest_hash
    )

    feature_drift = build_response_schema_registry(make_registry(feature_suffix="x"))
    assert (
        base.spec_for(ArmId.IF1).response_schema_hash
        != feature_drift.spec_for(ArmId.IF1).response_schema_hash
    )
    assert (
        base.spec_for(ArmId.ACT1).response_schema_hash
        == feature_drift.spec_for(ArmId.ACT1).response_schema_hash
    )

    action_drift = build_response_schema_registry(make_registry(model_prefix="x"))
    assert (
        base.spec_for(ArmId.H1).response_schema_hash
        != action_drift.spec_for(ArmId.H1).response_schema_hash
    )
    assert (
        base.spec_for(ArmId.D1_RAW).response_schema_hash
        == action_drift.spec_for(ArmId.D1_RAW).response_schema_hash
    )
    assert len({base.registry_hash, bounds_drift.registry_hash, feature_drift.registry_hash, action_drift.registry_hash}) == 4


def test_valid_direct_action_and_if_examples_match_the_strict_verifiers() -> None:
    registry = make_registry()
    schemas = build_response_schema_registry(registry)

    direct_payload = _direct_payload(registry)
    assert (
        validate_response_payload(direct_payload, schemas.spec_for(ArmId.D1_RAW))
        == direct_payload
    )
    direct = parse_direct_bundle(direct_payload, registry=registry)
    assert direct.certificate.response_schema_version == DIRECT_RESPONSE_SCHEMA_VERSION

    h1_spec = schemas.spec_for(ArmId.H1)
    h1_payload = _action_payload(h1_spec)
    assert validate_response_payload(h1_payload, h1_spec) == h1_payload
    h1_result = verify_and_execute_actions(
        h1_payload,
        authority=ActionAuthority.H1,
        registry=registry,
    )
    assert h1_result.certificate.response_schema_version == ACTION_RESPONSE_SCHEMA_VERSION

    capacity, rul = registry.numerical.planned_keys
    primary = registry.primary_actions(capacity.token)
    fallback = next(
        action
        for action in primary
        if action.transform is None and action.base.operator is BaseOperator.FALLBACK
    )
    emit = next(
        action
        for action in primary
        if action.transform is None and action.base.operator is BaseOperator.EMIT
    )
    rul_action = registry.primary_actions(rul.token)[0]
    if_payload = {
        "schema_version": IF_RESPONSE_SCHEMA_VERSION,
        "artifacts": [
            {
                "key": capacity.token,
                "predicate": {"operator": "ATOM", "feature_id": "f0", "bin_id": "a"},
                "true_action_id": fallback.action_id,
                "false_action_id": emit.action_id,
            },
            {"key": rul.token, "action_id": rul_action.action_id},
        ],
    }
    if_spec = schemas.spec_for(ArmId.IF1)
    assert validate_response_payload(if_payload, if_spec) == if_payload
    if_result = verify_and_execute_if_representation(
        if_payload,
        feature_bins={f"f{index}": "a" for index in range(5)},
        registry=registry,
    )
    assert if_result.certificate.response_schema_version == IF_RESPONSE_SCHEMA_VERSION


def test_permission_crossing_and_shape_mutation_fail_schema_and_verifier() -> None:
    registry = make_registry()
    schemas = build_response_schema_registry(registry)
    capacity = registry.numerical.planned_keys[0].token

    h1_spec = schemas.spec_for(ArmId.H1)
    crossed = _action_payload(h1_spec)
    crossed["selections"][0]["action_id"] = schemas.spec_for(ArmId.RF1).allowed_action_ids[capacity][0]  # type: ignore[index]
    with pytest.raises(ResponseSchemaValidationError):
        validate_response_payload(crossed, h1_spec)
    with pytest.raises(VerificationError):
        verify_and_execute_actions(
            crossed,
            authority=ActionAuthority.H1,
            registry=registry,
        )

    direct_spec = schemas.spec_for(ArmId.D1_RAW)
    extra = _direct_payload(registry)
    extra["unexpected"] = True
    with pytest.raises(ResponseSchemaValidationError):
        validate_response_payload(extra, direct_spec)
    with pytest.raises(VerificationError):
        parse_direct_bundle(extra, registry=registry)

    with pytest.raises(ResponseSchemaValidationError):
        validate_response_payload(
            '{"schema_version":"CAPDirectForecastResponse.v1",'
            '"schema_version":"CAPDirectForecastResponse.v1","forecasts":[]}',
            direct_spec,
        )

    weakened = to_primitive(direct_spec.response_schema)
    weakened["unexpectedKeyword"] = True
    with pytest.raises(ResponseSchemaDefinitionError):
        validate_schema_definition(weakened)


def test_arbitrarily_large_json_integer_closes_as_typed_schema_failure() -> None:
    registry = make_registry()
    spec = build_response_schema_registry(registry).spec_for(ArmId.D1_RAW)
    huge_json_integer = "1" + "0" * 400
    payload = _direct_payload(registry)
    numeric = payload["forecasts"][0]  # type: ignore[index]
    numeric["point"] = 10**400

    with pytest.raises(ResponseSchemaValidationError):
        validate_response_payload(payload, spec)
    with pytest.raises(ResponseSchemaValidationError):
        validate_response_payload(
            '{"schema_version":"CAPDirectForecastResponse.v1","forecasts":['
            '{"key":"capacity|1|F","status":"NUMERIC","point":'
            + huge_json_integer
            + ',"lower":1,"median":1,"upper":1},'
            '{"key":"rul|1|cycle","status":"RUL_NA"}]}',
            spec,
        )

    with pytest.raises(ResponseSchemaDefinitionError):
        validate_schema_definition(
            {"type": "number", "minimum": 10**400, "maximum": 1}
        )


def test_schema_is_a_provider_constraint_and_verifier_closes_residual_semantics() -> None:
    """Document two invariants intentionally left to the final verifier."""

    registry = make_registry()
    schemas = build_response_schema_registry(registry)
    capacity = registry.numerical.planned_keys[0].token

    # JSON Schema uniqueItems compares whole records, so two distinct records
    # for one key satisfy the schema and exact array length.  The verifier owns
    # exact per-key coverage and rejects the duplicate/missing-RUL response.
    h1_spec = schemas.spec_for(ArmId.H1)
    two_emit_ids = h1_spec.allowed_action_ids[capacity][:2]
    duplicate_key = {
        "schema_version": ACTION_RESPONSE_SCHEMA_VERSION,
        "selections": [
            {"key": capacity, "action_id": two_emit_ids[0]},
            {"key": capacity, "action_id": two_emit_ids[1]},
        ],
    }
    assert validate_response_payload(duplicate_key, h1_spec) == duplicate_key
    with pytest.raises(VerificationError, match="unknown or duplicate key"):
        verify_and_execute_actions(
            duplicate_key,
            authority=ActionAuthority.H1,
            registry=registry,
        )

    # Per-field target bounds are schema-expressible; ordering between four
    # numeric fields is not.  ForecastValue/verifier remains the authority for
    # lower <= point/median <= upper.
    direct_spec = schemas.spec_for(ArmId.D1_RAW)
    nonmonotone = _direct_payload(registry)
    nonmonotone["forecasts"][0].update(  # type: ignore[index]
        {"point": 1.0, "lower": 1.5, "median": 1.0, "upper": 0.5}
    )
    assert validate_response_payload(nonmonotone, direct_spec) == nonmonotone
    with pytest.raises(RegistryError, match="quantiles"):
        parse_direct_bundle(nonmonotone, registry=registry)
