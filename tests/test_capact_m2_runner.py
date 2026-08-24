from __future__ import annotations

import json
from dataclasses import replace

import pytest

import experiments.vfps_agent.runner as runner_module

from experiments.vfps_agent.actions import ActionSpace, BaseAction, BaseOperator
from experiments.vfps_agent.canonical import canonical_bytes, canonical_sha256
from experiments.vfps_agent.contracts import (
    AccuracyBudgetSpec,
    ArmId,
    CausalPacketSchema,
    ForecastKey,
    PacketKind,
    PolicySpec,
    ProtocolId,
    RevealedObservation,
    SealedSplitProvenance,
)
from experiments.vfps_agent.provider import MockProvider
from experiments.vfps_agent.ledger import CanonicalJSONLLedger, LedgerKind
from experiments.vfps_agent.replay import (
    BlindReplayService,
    HiddenEvent,
    verify_complete_run,
)
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
from experiments.vfps_agent.runner import (
    CAP_M2_VERIFIER_HASH,
    CAPAccuracyRun,
    CAPM2Error,
    build_causal_packet,
    verify_prediction_phase,
)
from experiments.vfps_agent.search import (
    EnumSearchConfig,
    LossRecord,
    SearchError,
    SealedDevelopmentLossTable,
    enumerate_action_outer_bound,
    packet_context_stratum,
)
from experiments.vfps_agent.verifier import (
    ACTION_RESPONSE_SCHEMA_VERSION,
    DIRECT_RESPONSE_SCHEMA_VERSION,
    IF_RESPONSE_SCHEMA_VERSION,
)


MODELS = tuple(f"m{index}" for index in range(6))
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
                    point=1.0 + index / 100,
                    lower=0.9 + index / 100,
                    median=1.0 + index / 100,
                    upper=1.1 + index / 100,
                ),
                ForecastValue.rul_na(rul),
            ),
        )
        for index, model in enumerate(MODELS)
    )
    weights = tuple(
        WeightTemplate.from_mapping(
            template,
            {model: float(model_index == (template_index % 6)) for model_index, model in enumerate(MODELS)},
        )
        for template_index, template in enumerate(TEMPLATES)
    )
    fallback = BaseAction(BaseOperator.FALLBACK)
    numerical = FrozenNumericalRegistry(
        bundles,
        weights,
        ForecastBundle("fallback", bundles[0].forecasts),
        (ScaleSpec(cap.token, 0.1), ScaleSpec(rul.token, 1.0)),
        (
            TargetContract("capacity", "F", True, 0.0, 2.0),
            TargetContract("rul", "cycle", False),
        ),
        (ChampionBaseSpec(cap.token, fallback), ChampionBaseSpec(rul.token, fallback)),
    )
    features = FrozenFeatureRegistry(
        tuple(FeatureSpec(f"f{index}", ("a", "b", "c"), f"{index + 1:064x}") for index in range(5))
    )
    return CAPActionRegistry(numerical, features)


def split_fixture() -> SealedSplitProvenance:
    return SealedSplitProvenance(
        outer_fold_hash="1" * 64,
        split_manifest_hash="2" * 64,
        provenance_manifest_hash="3" * 64,
        outer_train_set_hash="4" * 64,
        held_out_member_hash="5" * 64,
        crossfit_manifest_hash="6" * 64,
        additive_loss_spec_hash="7" * 64,
    )


def packet_fixture(registry: CAPActionRegistry, *, kind: PacketKind = PacketKind.HYBRID):
    schema = CausalPacketSchema(
        measurement_fields=("capacity",),
        missingness_fields=("capacity",),
        diagnostic_fields=("f0", "f1", "f2", "f3", "f4"),
    )
    observations = tuple(
        RevealedObservation(
            event_index=index,
            observed_at=float(index),
            available_at=float(index),
            measurements={"capacity": 1.0 - index / 100},
            missingness={"capacity": False},
        )
        for index in range(3)
    )
    return build_causal_packet(
        packet_kind=kind,
        origin_event_index=2,
        availability_cutoff=2.0,
        revealed_observations=observations,
        causal_schema=schema,
        split=split_fixture(),
        registry=registry,
        diagnostic_bins={f"f{index}": "a" for index in range(5)},
    ), schema


def budget_fixture(arm: ArmId) -> AccuracyBudgetSpec:
    physical = 0 if arm is ArmId.N0 else 1
    return AccuracyBudgetSpec(
        requested_tokens=0 if physical == 0 else 256,
        deadline_ms=100,
        physical_calls=physical,
    )


def policy_fixture(
    arm: ArmId,
    registry: CAPActionRegistry,
    schema: CausalPacketSchema,
    budget: AccuracyBudgetSpec,
) -> PolicySpec:
    return PolicySpec(
        policy_id=f"capact-{arm.value.lower()}",
        generation=1,
        protocol=ProtocolId.ACCURACY_V1,
        arm=arm,
        provider_rule_hash="8" * 64,
        model_version_rule_hash="9" * 64,
        prompt_hash="a" * 64,
        packet_schema_hash=schema.schema_hash,
        response_schema_hash="b" * 64,
        grammar_hash=registry.action_manifest_hash,
        registry_hash=registry.registry_hash,
        decode_parameters_hash="c" * 64,
        one_call_budget_hash=budget.budget_hash,
        verifier_hash=CAP_M2_VERIFIER_HASH,
        fallback_hash=registry.numerical.fallback_bundle.bundle_hash,
        capability_snapshot_hash="d" * 64,
    )


def direct_response(registry: CAPActionRegistry) -> str:
    return json.dumps(
        {
            "schema_version": DIRECT_RESPONSE_SCHEMA_VERSION,
            "forecasts": [item.payload() for item in registry.numerical.fallback_bundle.forecasts],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def arm_response(arm: ArmId, registry: CAPActionRegistry) -> str | None:
    if arm is ArmId.N0:
        return None
    if arm in {ArmId.D1_RAW, ArmId.D1_PACKET}:
        return direct_response(registry)
    selections = []
    for key in registry.numerical.planned_keys:
        space = ActionSpace.COMPOSITIONAL96 if arm is ArmId.ACT_COMP96 else ActionSpace.PRIMARY19
        actions = registry.actions_for(key.token, space)
        if key.target == "rul":
            chosen = actions[0]
        elif arm is ArmId.H1:
            chosen = next(item for item in actions if item.transform is None and item.base.operator is BaseOperator.EMIT)
        elif arm is ArmId.RF1:
            chosen = next(item for item in actions if item.transform is None and item.base.operator is BaseOperator.FUSE)
        elif arm is ArmId.RC1:
            chosen = next(item for item in actions if item.transform is None and item.base.operator is BaseOperator.FALLBACK)
        else:
            chosen = next(item for item in actions if item.transform is None and item.base.operator is BaseOperator.EMIT)
        selections.append({"key": key.token, "action_id": chosen.action_id})
    if arm is ArmId.IF1:
        payload = {
            "schema_version": IF_RESPONSE_SCHEMA_VERSION,
            "artifacts": selections,
        }
    else:
        payload = {
            "schema_version": ACTION_RESPONSE_SCHEMA_VERSION,
            "selections": selections,
        }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def test_causal_builder_rejects_identity_alias_and_time_reversal() -> None:
    with pytest.raises(Exception, match="identity"):
        CausalPacketSchema(
            measurement_fields=("specimen_alias",),
            missingness_fields=("specimen_alias",),
        )
    with pytest.raises(ValueError, match="before"):
        RevealedObservation(
            event_index=0,
            observed_at=2.0,
            available_at=1.0,
            measurements={"capacity": 1.0},
            missingness={"capacity": False},
        )


def test_typed_direct_run_binds_registry_and_forced_rul_na(tmp_path) -> None:
    registry = registry_fixture()
    packet, schema = packet_fixture(registry)
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    provider = MockProvider(
        response_text=direct_response(registry),
        input_tokens=10,
        output_tokens=20,
        provider_response_id="mock-response-1",
    )
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        result = run.run_origin(
            provider=provider,
            policy=policy,
            packet=packet,
            registry=registry,
            budget=budget,
            started_unix_ms=1000,
        )
        assert result.provider_called
        assert provider.physical_attempts == 1
        rows = result.commit.prediction["key_executions"]
        rul = next(item for item in rows if item["forecast_status"] == "RUL_NA")
        assert rul["forced_rul_na"]
        assert not rul["active_coverage_eligible"]
        run.seal_prediction_phase()
    report = verify_prediction_phase(run_dir)
    assert report == {
        "status": "PASS",
        "attempt_count": 1,
        "prediction_count": 1,
        "execution_count": 2,
        "checkpoint_count": 1,
        "phase_seal_hash": report["phase_seal_hash"],
    }


@pytest.mark.parametrize(
    "arm",
    (
        ArmId.N0,
        ArmId.D1_RAW,
        ArmId.D1_PACKET,
        ArmId.H1,
        ArmId.RF1,
        ArmId.RC1,
        ArmId.ACT1,
        ArmId.IF1,
        ArmId.ACT_COMP96,
    ),
)
def test_every_typed_arm_runs_through_same_durable_path(tmp_path, arm: ArmId) -> None:
    registry = registry_fixture()
    kind = PacketKind.RAW if arm is ArmId.D1_RAW else PacketKind.HYBRID
    packet, schema = packet_fixture(registry, kind=kind)
    budget = budget_fixture(arm)
    policy = policy_fixture(arm, registry, schema, budget)
    response = arm_response(arm, registry)
    provider = None if arm is ArmId.N0 else MockProvider(response_text=response)
    run_dir = tmp_path / arm.value.replace("/", "_")
    with CAPAccuracyRun(run_dir) as run:
        result = run.run_origin(
            provider=provider,
            policy=policy,
            packet=packet,
            registry=registry,
            budget=budget,
            started_unix_ms=1000,
        )
        assert len(result.commit.prediction["key_executions"]) == 2
        run.seal_prediction_phase()
    assert verify_prediction_phase(run_dir)["status"] == "PASS"
    if provider is not None:
        assert provider.physical_attempts == 1


def test_binding_mismatch_is_rejected_before_provider(tmp_path) -> None:
    registry = registry_fixture()
    packet, schema = packet_fixture(registry)
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    wrong = PolicySpec(
        **{
            **{name: getattr(policy, name) for name in policy.__dataclass_fields__ if name != "registry_hash"},
            "registry_hash": "e" * 64,
        }
    )
    provider = MockProvider(response_text=direct_response(registry))
    with CAPAccuracyRun(tmp_path / "run") as run:
        with pytest.raises(CAPM2Error, match="registry"):
            run.run_origin(
                provider=provider,
                policy=wrong,
                packet=packet,
                registry=registry,
                budget=budget,
                started_unix_ms=1000,
            )
    assert provider.physical_attempts == 0


def test_crash_left_started_is_consumed_without_resend(tmp_path) -> None:
    registry = registry_fixture()
    packet, schema = packet_fixture(registry)
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)

    def crash(_attempt) -> None:
        raise KeyboardInterrupt()

    run_dir = tmp_path / "run"
    first = MockProvider(response_text=direct_response(registry), before_return=crash)
    with pytest.raises(KeyboardInterrupt):
        with CAPAccuracyRun(run_dir) as run:
            run.run_origin(
                provider=first,
                policy=policy,
                packet=packet,
                registry=registry,
                budget=budget,
                started_unix_ms=1000,
            )
    assert first.physical_attempts == 1

    second = MockProvider(response_text=direct_response(registry))
    with CAPAccuracyRun(run_dir, resume=True) as run:
        recovered = run.run_origin(
            provider=second,
            policy=policy,
            packet=packet,
            registry=registry,
            budget=budget,
            started_unix_ms=1100,
        )
        assert recovered.recovered_without_resend
        assert not recovered.provider_called
        assert recovered.commit.reason_code.value == "CRASH_RECOVERY"
        run.seal_prediction_phase()
    assert second.physical_attempts == 0
    assert verify_prediction_phase(run_dir)["status"] == "PASS"


def test_recomputed_execution_chain_still_fails_cross_ledger_check(tmp_path) -> None:
    registry = registry_fixture()
    packet, schema = packet_fixture(registry)
    budget = budget_fixture(ArmId.N0)
    policy = policy_fixture(ArmId.N0, registry, schema, budget)
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        run.run_origin(
            provider=None,
            policy=policy,
            packet=packet,
            registry=registry,
            budget=budget,
            started_unix_ms=1000,
        )

    path = run_dir / "EXECUTION_LEDGER.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["payload"]["prediction_record_hash"] = "f" * 64
    previous = "0" * 64
    for sequence, row in enumerate(rows):
        row["sequence"] = sequence
        row["previous_record_hash"] = previous
        body = {key: value for key, value in row.items() if key != "record_hash"}
        row["record_hash"] = canonical_sha256(body)
        previous = row["record_hash"]
    path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))

    with CAPAccuracyRun(run_dir, resume=True) as run:
        with pytest.raises(CAPM2Error, match="execution row differs"):
            run.seal_prediction_phase()


def test_provider_canary_is_never_persisted(tmp_path) -> None:
    registry = registry_fixture()
    packet, schema = packet_fixture(registry)
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    canary = "CANARY_DO_NOT_PERSIST_7b3d8b"
    provider = MockProvider(
        response_text=json.dumps({"secret": canary}),
        error_code=canary,
        provider_response_id=canary,
        observed_model_hash=canary,
    )
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        result = run.run_origin(
            provider=provider,
            policy=policy,
            packet=packet,
            registry=registry,
            budget=budget,
            started_unix_ms=1000,
        )
        assert result.commit.disposition.value == "FALLBACK"
        run.seal_prediction_phase()
    assert canary.encode() not in b"".join(path.read_bytes() for path in run_dir.iterdir())


def test_crash_after_finished_recovers_fallback_without_resend(tmp_path, monkeypatch) -> None:
    registry = registry_fixture()
    packet, schema = packet_fixture(registry)
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    run_dir = tmp_path / "run"
    provider = MockProvider(response_text=direct_response(registry))

    def crash_execute(*_args, **_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner_module, "execute_arm", crash_execute)
    with pytest.raises(KeyboardInterrupt):
        with CAPAccuracyRun(run_dir) as run:
            run.run_origin(
                provider=provider,
                policy=policy,
                packet=packet,
                registry=registry,
                budget=budget,
                started_unix_ms=1000,
            )
    monkeypatch.undo()
    assert provider.physical_attempts == 1
    no_resend = MockProvider(response_text=direct_response(registry))
    with CAPAccuracyRun(run_dir, resume=True) as run:
        result = run.run_origin(
            provider=no_resend,
            policy=policy,
            packet=packet,
            registry=registry,
            budget=budget,
            started_unix_ms=1100,
        )
        assert result.commit.reason_code.value == "CRASH_RECOVERY"
        run.seal_prediction_phase()
    assert no_resend.physical_attempts == 0


@pytest.mark.parametrize("fault_method", ("append_execution", "append_checkpoint"))
def test_crash_after_prediction_or_execution_resumes_without_resend(
    tmp_path, monkeypatch, fault_method: str
) -> None:
    registry = registry_fixture()
    packet, schema = packet_fixture(registry)
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    run_dir = tmp_path / fault_method
    provider = MockProvider(response_text=direct_response(registry))
    original = getattr(CanonicalJSONLLedger, fault_method)
    triggered = False

    def crash_once(self, payload):
        nonlocal triggered
        expected_kind = LedgerKind.EXECUTION if fault_method == "append_execution" else LedgerKind.CHECKPOINT
        if self.ledger_kind is expected_kind and not triggered:
            triggered = True
            raise KeyboardInterrupt()
        return original(self, payload)

    monkeypatch.setattr(CanonicalJSONLLedger, fault_method, crash_once)
    with pytest.raises(KeyboardInterrupt):
        with CAPAccuracyRun(run_dir) as run:
            run.run_origin(
                provider=provider,
                policy=policy,
                packet=packet,
                registry=registry,
                budget=budget,
                started_unix_ms=1000,
            )
    monkeypatch.undo()
    no_resend = MockProvider(response_text=direct_response(registry))
    with CAPAccuracyRun(run_dir, resume=True) as run:
        result = run.run_origin(
            provider=no_resend,
            policy=policy,
            packet=packet,
            registry=registry,
            budget=budget,
            started_unix_ms=1100,
        )
        assert result.recovered_without_resend
        run.seal_prediction_phase()
    assert provider.physical_attempts == 1
    assert no_resend.physical_attempts == 0
    assert verify_prediction_phase(run_dir)["status"] == "PASS"


def hidden_events(*, altered_suffix: bool = False) -> tuple[HiddenEvent, ...]:
    values = [1.0, 0.99, 0.98, 0.97, 0.96]
    if altered_suffix:
        values[3:] = [0.42, 0.31]
    return tuple(
        HiddenEvent(
            event_index=index,
            observed_at=float(index),
            available_at=float(index),
            measurements={"capacity": value},
            missingness={"capacity": False},
        )
        for index, value in enumerate(values)
    )


def test_hidden_event_detaches_caller_owned_measurements() -> None:
    measurements = {"capacity": 1.0}
    missingness = {"capacity": False}
    event = HiddenEvent(0, 0.0, 0.0, measurements, missingness)
    before = event.event_hash
    measurements["capacity"] = 0.1
    missingness["capacity"] = True
    assert event.event_hash == before
    assert event.revealed().measurements["capacity"] == 1.0
    assert event.revealed().missingness["capacity"] is False


def replay_service(run_dir, registry, schema, *, altered_suffix: bool = False):
    return BlindReplayService(
        run_dir,
        events=hidden_events(altered_suffix=altered_suffix),
        context=3,
        causal_schema=schema,
        split=split_fixture(),
        registry=registry,
        packet_kind=PacketKind.HYBRID,
        diagnostic_bins={f"f{index}": "a" for index in range(5)},
    )


def test_blind_replay_rejects_a_bootstrap_equal_to_the_full_stream(tmp_path) -> None:
    registry = registry_fixture()
    schema = CausalPacketSchema(
        measurement_fields=("capacity",),
        missingness_fields=("capacity",),
        diagnostic_fields=("f0", "f1", "f2", "f3", "f4"),
    )
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir):
        with pytest.raises(CAPM2Error, match="proper non-empty prefix"):
            BlindReplayService(
                run_dir,
                events=hidden_events(),
                context=len(hidden_events()),
                causal_schema=schema,
                split=split_fixture(),
                registry=registry,
                packet_kind=PacketKind.HYBRID,
                diagnostic_bins={f"f{index}": "a" for index in range(5)},
            )


def test_blind_replay_requires_checkpoint_and_matures_only_after_prediction_seal(tmp_path) -> None:
    registry = registry_fixture()
    schema = CausalPacketSchema(
        measurement_fields=("capacity",),
        missingness_fields=("capacity",),
        diagnostic_fields=("f0", "f1", "f2", "f3", "f4"),
    )
    budget = budget_fixture(ArmId.D1_PACKET)
    policy = policy_fixture(ArmId.D1_PACKET, registry, schema, budget)
    provider = MockProvider(response_text=direct_response(registry))
    run_dir = tmp_path / "run"
    with CAPAccuracyRun(run_dir) as run:
        with replay_service(run_dir, registry, schema) as service:
            with pytest.raises(CAPM2Error, match="absent"):
                service.reveal_next_after_checkpoint("f" * 64)
            first = run.run_origin(
                provider=provider,
                policy=policy,
                packet=service.build_current_packet(),
                registry=registry,
                budget=budget,
                started_unix_ms=1000,
            )
            service.reveal_next_after_checkpoint(first.checkpoint_record_hash)
            second = run.run_origin(
                provider=provider,
                policy=policy,
                packet=service.build_current_packet(),
                registry=registry,
                budget=budget,
                started_unix_ms=1100,
            )
            service.reveal_next_after_checkpoint(second.checkpoint_record_hash)
            third = run.run_origin(
                provider=provider,
                policy=policy,
                packet=service.build_current_packet(),
                registry=registry,
                budget=budget,
                started_unix_ms=1200,
            )
            assert provider.physical_attempts == 3
            run.seal_prediction_phase()
            service.seal_access_and_mature()
    report = verify_complete_run(run_dir, context=3)
    assert report["prediction_count"] == 3
    assert report["execution_count"] == report["maturity_count"] == 6
    assert report["matured_count"] == 2
    assert report["never_matured_count"] == 4


def test_future_suffix_mutation_cannot_change_current_packet(tmp_path) -> None:
    registry = registry_fixture()
    schema = CausalPacketSchema(
        measurement_fields=("capacity",),
        missingness_fields=("capacity",),
        diagnostic_fields=("f0", "f1", "f2", "f3", "f4"),
    )
    with CAPAccuracyRun(tmp_path / "a") as run_a:
        with replay_service(tmp_path / "a", registry, schema) as service_a:
            packet_a = service_a.build_current_packet()
    with CAPAccuracyRun(tmp_path / "b") as run_b:
        with replay_service(tmp_path / "b", registry, schema, altered_suffix=True) as service_b:
            packet_b = service_b.build_current_packet()
    assert packet_a.packet_bytes == packet_b.packet_bytes
    assert packet_a.packet_hash == packet_b.packet_hash


def test_formal_enum_requires_outer_train_crossfit_binding() -> None:
    registry = registry_fixture()
    packet, _schema = packet_fixture(registry)
    key = registry.numerical.planned_keys[0].token
    stratum = packet_context_stratum(packet)
    records = tuple(
        LossRecord(key, action.action_id, f"{cluster + 10:064x}", stratum, 0.1 + index / 1000)
        for index, action in enumerate(registry.primary_actions(key))
        for cluster in range(2)
    )
    table = SealedDevelopmentLossTable.seal_outer_bound(
        records,
        loss_name="unit_macro_mase",
        feature_registry_hash=registry.features.feature_registry_hash,
        action_manifest_hash=registry.action_manifest_hash,
        action_space=ActionSpace.PRIMARY19,
        split=split_fixture(),
    )
    selected = enumerate_action_outer_bound(
        table=table,
        registry=registry,
        packet=packet,
        key_token=key,
        config=EnumSearchConfig(n_min=1, lambda_z=1.0, kappa=0.0, eta=0.0),
    )
    assert selected.context_stratum == stratum
    with pytest.raises(SearchError, match="outer-training"):
        enumerate_action_outer_bound(
            table=table,
            registry=registry,
            packet=replace(packet, held_out_member_hash="e" * 64),
            key_token=key,
            config=EnumSearchConfig(n_min=1, lambda_z=1.0, kappa=0.0, eta=0.0),
        )
