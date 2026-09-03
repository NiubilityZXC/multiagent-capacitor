from __future__ import annotations

from pathlib import Path

import pytest

from experiments.vfps_agent.canonical import canonical_bytes, canonical_sha256
from experiments.vfps_agent.contracts import ArmId, CausalPacketSchema, PacketKind
from experiments.vfps_agent.generation_barrier import (
    CANONICAL_GENERATION_ARM_IDS,
    FrozenGenerationCell,
    FrozenGenerationArmAdmission,
    FrozenGenerationPlan,
    GenerationArmStatus,
    GenerationBarrierError,
    GenerationRunBinding,
    bind_formal_generation,
    generation_cell_id,
    make_finalize_permit,
    seal_generation_plan,
    seal_generation_prediction_barrier,
    seal_generation_score_inputs,
    verify_finalize_permit,
    verify_generation_plan,
    verify_generation_prediction_barrier,
)
from experiments.vfps_agent.evaluator_service import (
    EvaluatorProtocolError,
    issue_generation_joint_unseal_authorization,
    start_isolated_evaluator,
)
from experiments.vfps_agent.provider import MockProvider
from experiments.vfps_agent.replay import BlindReplayService, verify_complete_run
from experiments.vfps_agent.runner import CAPAccuracyRun
from tests.test_capact_m2_runner import (
    budget_fixture,
    direct_response,
    hidden_events,
    policy_fixture,
    registry_fixture,
    split_fixture,
)


GENERATION_ID = "a" * 64
MASTER_SEAL_HASH = "b" * 64
HUMAN_APPROVAL_HASH = "c" * 64
OUTCOME_AVAILABILITY_HASH = "d" * 64
STATISTICS_EXECUTABLE_HASH = "e" * 64


def _schema() -> CausalPacketSchema:
    return CausalPacketSchema(
        measurement_fields=("capacity",),
        missingness_fields=("capacity",),
        diagnostic_fields=("f0", "f1", "f2", "f3", "f4"),
    )


def _cell(
    root: Path,
    *,
    fold_id: str,
    arm: ArmId,
    run_name: str | None = None,
) -> FrozenGenerationCell:
    registry = registry_fixture()
    schema = _schema()
    policy = policy_fixture(arm, registry, schema, budget_fixture(arm))
    split = split_fixture()
    run_dir = root / (run_name or f"{fold_id}-{arm.name.lower()}")
    return FrozenGenerationCell(
        cell_id=generation_cell_id(GENERATION_ID, fold_id, arm.value),
        fold_id=fold_id,
        arm_id=arm.value,
        run_dir=str(run_dir),
        context=3,
        expected_revealed_count=5,
        expected_post_commit_reveal_count=2,
        policy_hash=policy.policy_hash,
        split_hash=split.seal_hash,
        registry_hash=registry.registry_hash,
        planned_manifest_hash=canonical_sha256(
            [item.token for item in registry.numerical.planned_keys]
        ),
    )


def _plan(
    root: Path,
    *,
    folds: tuple[str, ...] = ("fold0",),
    arms: tuple[ArmId, ...] = (ArmId.D1_PACKET,),
) -> FrozenGenerationPlan:
    arm_ids = tuple(sorted(item.value for item in arms))
    cells = tuple(
        sorted(
            (
                _cell(root, fold_id=fold_id, arm=ArmId(arm_id))
                for fold_id in folds
                for arm_id in arm_ids
            ),
            key=lambda item: (item.fold_id, item.arm_id),
        )
    )
    return FrozenGenerationPlan(
        generation_id=GENERATION_ID,
        fold_ids=tuple(sorted(folds)),
        arm_ids=arm_ids,
        cells=cells,
    )


def _formal_plan(
    root: Path,
    *,
    folds: tuple[str, ...] = ("fold0",),
    admitted: tuple[ArmId, ...] = (ArmId.N0,),
) -> FrozenGenerationPlan:
    admitted_ids = {item.value for item in admitted}
    admissions = tuple(
        FrozenGenerationArmAdmission(
            arm_id=arm_id,
            status=(
                GenerationArmStatus.ADMITTED
                if arm_id in admitted_ids
                else GenerationArmStatus.BLOCKED
            ),
            reason_code=("ADMITTED_BY_TEST_SEAL" if arm_id in admitted_ids else "BLOCKED_BY_TEST_GATE"),
            requires_attested_ark=arm_id not in {"N0", "ENUM-ACTION"},
            physical_slots_per_origin=(
                4 if arm_id in {"D4-H", "D4-X", "ARCH1"}
                else 0 if arm_id in {"N0", "ENUM-ACTION"}
                else 1
            ),
            authorization_artifact_hash=canonical_sha256(
                {"arm_id": arm_id, "admitted": arm_id in admitted_ids}
            ),
        )
        for arm_id in CANONICAL_GENERATION_ARM_IDS
    )
    cells = tuple(
        sorted(
            (
                _cell(root, fold_id=fold_id, arm=arm)
                for fold_id in folds
                for arm in admitted
            ),
            key=lambda item: (item.fold_id, item.arm_id),
        )
    )
    return FrozenGenerationPlan(
        generation_id=GENERATION_ID,
        fold_ids=tuple(sorted(folds)),
        arm_ids=CANONICAL_GENERATION_ARM_IDS,
        cells=cells,
        formal_mode=True,
        master_seal_hash=MASTER_SEAL_HASH,
        human_approval_hash=HUMAN_APPROVAL_HASH,
        outcome_availability_hash=OUTCOME_AVAILABILITY_HASH,
        statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
        arm_admissions=admissions,
    )
def _bindings(plan: FrozenGenerationPlan) -> tuple[GenerationRunBinding, ...]:
    return tuple(
        GenerationRunBinding(cell_id=item.cell_id, run_dir=item.run_dir)
        for item in plan.cells
    )


def _prepare_prediction(cell: FrozenGenerationCell, *, complete_replay: bool) -> None:
    registry = registry_fixture()
    schema = _schema()
    split = split_fixture()
    arm = ArmId(cell.arm_id)
    budget = budget_fixture(arm)
    policy = policy_fixture(arm, registry, schema, budget)
    provider = MockProvider(response_text=direct_response(registry))
    run_dir = Path(cell.run_dir)
    with CAPAccuracyRun(run_dir) as run:
        with BlindReplayService(
            run_dir,
            events=hidden_events(),
            context=cell.context,
            causal_schema=schema,
            split=split,
            registry=registry,
            packet_kind=PacketKind.HYBRID,
            diagnostic_bins={f"f{index}": "a" for index in range(5)},
        ) as service:
            origins = 3 if complete_replay else 1
            for index in range(origins):
                result = run.run_origin(
                    provider=provider,
                    policy=policy,
                    packet=service.build_current_packet(),
                    registry=registry,
                    budget=budget,
                    started_unix_ms=1000 + index * 100,
                )
                if complete_replay and index < origins - 1:
                    service.reveal_next_after_checkpoint(result.checkpoint_record_hash)
            run.seal_prediction_phase()


def _finalize(cell: FrozenGenerationCell) -> str:
    registry = registry_fixture()
    schema = _schema()
    with BlindReplayService(
        cell.run_dir,
        events=hidden_events(),
        context=cell.context,
        causal_schema=schema,
        split=split_fixture(),
        registry=registry,
        packet_kind=PacketKind.HYBRID,
        diagnostic_bins={f"f{index}": "a" for index in range(5)},
        resume=True,
    ) as service:
        return service.seal_access_and_mature()


def _prepare_formal_prediction(cell: FrozenGenerationCell, plan_path: Path, barrier_path: Path):
    registry = registry_fixture()
    schema = _schema()
    split = split_fixture()
    arm = ArmId(cell.arm_id)
    budget = budget_fixture(arm)
    policy = policy_fixture(arm, registry, schema, budget)
    provider = MockProvider(response_text=direct_response(registry))
    binding = bind_formal_generation(
        plan_path,
        barrier_path,
        cell_id=cell.cell_id,
        run_dir=cell.run_dir,
    )
    supervisor = None
    client = None
    with CAPAccuracyRun(cell.run_dir) as run:
        supervisor, client = start_isolated_evaluator(
            cell.run_dir,
            events=hidden_events(),
            context=cell.context,
            causal_schema=schema,
            split=split,
            registry=registry,
            packet_kind=PacketKind.HYBRID,
            allowed_policy_hashes=(policy.policy_hash,),
            diagnostic_bins={f"f{index}": "a" for index in range(5)},
            formal_generation=binding,
        )
        try:
            for index in range(3):
                result = run.run_origin(
                    provider=provider,
                    policy=policy,
                    packet=client.build_current_packet(),
                    registry=registry,
                    budget=budget,
                    started_unix_ms=1000 + index * 100,
                )
                if index < 2:
                    client.reveal_next_after_checkpoint(result.checkpoint_record_hash)
            run.seal_prediction_phase()
        except Exception:
            client.close()
            supervisor.close()
            raise
    assert supervisor is not None and client is not None
    return supervisor, client


@pytest.mark.parametrize("case", ["missing", "extra", "duplicate"])
def test_plan_rejects_non_cartesian_cells_before_any_write(tmp_path, case) -> None:
    generation_dir = tmp_path / case
    generation_dir.mkdir()
    first = _cell(generation_dir, fold_id="fold0", arm=ArmId.N0, run_name="r0")
    second = _cell(
        generation_dir,
        fold_id="fold0" if case == "duplicate" else "fold1",
        arm=ArmId.N0,
        run_name="r1",
    )
    cells = {
        "missing": (first,),
        "extra": (first, second),
        "duplicate": (first, second),
    }[case]
    plan_path = generation_dir / "GENERATION_PLAN.json"
    with pytest.raises(GenerationBarrierError):
        plan = FrozenGenerationPlan(
            generation_id=GENERATION_ID,
            fold_ids=("fold0", "fold1") if case != "extra" else ("fold0",),
            arm_ids=(ArmId.N0.value,),
            cells=cells,
        )
        seal_generation_plan(plan_path, plan)
    assert not plan_path.exists()


def test_plan_seal_is_canonical_exclusive_and_round_trips(tmp_path) -> None:
    generation_dir = tmp_path / "generation"
    generation_dir.mkdir()
    plan = _plan(generation_dir)
    plan_path = generation_dir / "GENERATION_PLAN.json"
    assert seal_generation_plan(plan_path, plan) == plan.plan_hash
    assert verify_generation_plan(plan_path) == plan
    expected_record = plan.payload()
    expected_record["plan_hash"] = plan.plan_hash
    assert plan_path.read_bytes() == canonical_bytes(expected_record)
    with pytest.raises(GenerationBarrierError, match="pre-existing"):
        seal_generation_plan(plan_path, plan)


def test_formal_binding_rejects_local_subset_and_missing_root_hashes(tmp_path) -> None:
    generation_dir = tmp_path / "formal-plan"
    generation_dir.mkdir()
    local = _plan(generation_dir, arms=(ArmId.N0,))
    local_path = generation_dir / "LOCAL_PLAN.json"
    seal_generation_plan(local_path, local)
    with pytest.raises(GenerationBarrierError, match="local/subset"):
        bind_formal_generation(
            local_path,
            generation_dir / "BARRIER.json",
            cell_id=local.cells[0].cell_id,
            run_dir=local.cells[0].run_dir,
        )

    admission = FrozenGenerationArmAdmission(
        arm_id="N0",
        status=GenerationArmStatus.ADMITTED,
        reason_code="ADMITTED_BY_TEST_SEAL",
        requires_attested_ark=False,
        physical_slots_per_origin=0,
        authorization_artifact_hash="f" * 64,
    )
    with pytest.raises(GenerationBarrierError, match=r"canonical 11\+ARCH1"):
        FrozenGenerationPlan(
            generation_id=GENERATION_ID,
            fold_ids=("fold0",),
            arm_ids=("N0",),
            cells=(local.cells[0],),
            formal_mode=True,
            master_seal_hash=MASTER_SEAL_HASH,
            human_approval_hash=HUMAN_APPROVAL_HASH,
            outcome_availability_hash=OUTCOME_AVAILABILITY_HASH,
            statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
            arm_admissions=(admission,),
        )

    valid = _formal_plan(generation_dir)
    with pytest.raises(GenerationBarrierError, match="master_seal_hash"):
        FrozenGenerationPlan(
            generation_id=valid.generation_id,
            fold_ids=valid.fold_ids,
            arm_ids=valid.arm_ids,
            cells=valid.cells,
            formal_mode=True,
            master_seal_hash=None,
            human_approval_hash=valid.human_approval_hash,
            outcome_availability_hash=valid.outcome_availability_hash,
            statistics_executable_hash=valid.statistics_executable_hash,
            arm_admissions=valid.arm_admissions,
        )


@pytest.mark.parametrize("case", ["missing", "extra", "duplicate"])
def test_prediction_barrier_rejects_inexact_runtime_cells_before_write(
    tmp_path, case
) -> None:
    generation_dir = tmp_path / case
    generation_dir.mkdir()
    plan = _plan(
        generation_dir,
        folds=("fold0",),
        arms=(ArmId.D1_PACKET, ArmId.N0),
    )
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    seal_generation_plan(plan_path, plan)
    bindings = list(_bindings(plan))
    if case == "missing":
        bindings.pop()
    elif case == "extra":
        bindings.append(
            GenerationRunBinding(cell_id="f" * 64, run_dir=str(generation_dir / "extra"))
        )
    else:
        bindings.append(bindings[0])
    with pytest.raises(GenerationBarrierError, match="bindings"):
        seal_generation_prediction_barrier(plan_path, barrier_path, bindings)
    assert not barrier_path.exists()


def test_unfinished_replay_blocks_whole_generation_before_label_writes(tmp_path) -> None:
    generation_dir = tmp_path / "generation"
    generation_dir.mkdir()
    plan = _plan(generation_dir)
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    seal_generation_plan(plan_path, plan)
    _prepare_prediction(plan.cells[0], complete_replay=False)

    with pytest.raises(GenerationBarrierError, match="unfinished"):
        seal_generation_prediction_barrier(plan_path, barrier_path, _bindings(plan))
    assert not barrier_path.exists()
    run_dir = Path(plan.cells[0].run_dir)
    assert not (run_dir / "ACCESS_LEDGER.seal.json").exists()
    assert not (run_dir / "MATURITY_LEDGER.jsonl").exists()
    assert not (run_dir / "RUN_SEAL.json").exists()


def test_finalize_permit_rejects_tamper_and_cross_cell_use(tmp_path) -> None:
    generation_dir = tmp_path / "generation"
    generation_dir.mkdir()
    plan = _plan(
        generation_dir,
        folds=("fold0",),
        arms=(ArmId.D1_PACKET, ArmId.N0),
    )
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    seal_generation_plan(plan_path, plan)
    for cell in plan.cells:
        _prepare_prediction(cell, complete_replay=True)
    barrier = seal_generation_prediction_barrier(
        plan_path, barrier_path, _bindings(plan)
    )
    assert verify_generation_prediction_barrier(plan_path, barrier_path) == barrier

    first, second = plan.cells
    permit = make_finalize_permit(plan_path, barrier_path, cell_id=first.cell_id)
    assert (
        verify_finalize_permit(
            plan_path,
            barrier_path,
            permit,
            expected_cell_id=first.cell_id,
        ).cell_id
        == first.cell_id
    )
    tampered = permit.record()
    tampered["cell_receipt_hash"] = "f" * 64
    with pytest.raises(GenerationBarrierError, match="permit hash"):
        verify_finalize_permit(
            plan_path,
            barrier_path,
            tampered,
            expected_cell_id=first.cell_id,
        )
    with pytest.raises(GenerationBarrierError, match="differs"):
        verify_finalize_permit(
            plan_path,
            barrier_path,
            permit,
            expected_cell_id=second.cell_id,
        )
    for cell in plan.cells:
        assert not (Path(cell.run_dir) / "MATURITY_LEDGER.jsonl").exists()


def test_formal_evaluator_requires_global_barrier_and_state_key_authorization(
    tmp_path,
) -> None:
    generation_dir = tmp_path / "formal"
    generation_dir.mkdir()
    plan = _formal_plan(generation_dir)
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    seal_generation_plan(plan_path, plan)
    cell = plan.cells[0]
    supervisor, client = _prepare_formal_prediction(cell, plan_path, barrier_path)
    joint_key = b"joint-unseal-test-key-32-bytes!!"
    joint_path = generation_dir / "GENERATION_JOINT_UNSEAL.json"
    try:
        with pytest.raises(EvaluatorProtocolError, match="supervisor authorization"):
            client.finalize_and_score()
        with pytest.raises(EvaluatorProtocolError, match="not ready"):
            issue_generation_joint_unseal_authorization(
                (supervisor,),
                joint_key=joint_key,
                statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
                authorization_path=joint_path,
            )
        assert not (Path(cell.run_dir) / "MATURITY_LEDGER.jsonl").exists()

        seal_generation_prediction_barrier(
            plan_path, barrier_path, _bindings(plan)
        )
        joint = issue_generation_joint_unseal_authorization(
            (supervisor,),
            joint_key=joint_key,
            statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
            authorization_path=joint_path,
        )
        authorization = supervisor.issue_formal_finalize_authorization(
            joint_unseal=joint, joint_key=joint_key
        )
        assert not hasattr(client, "_state_key")
        result = client.finalize_and_score(formal_authorization=authorization)
        assert result.prediction_count == 3
        assert result.execution_count == result.maturity_count == 6
    finally:
        client.close()
        supervisor.close()
    assert (Path(cell.run_dir) / "MATURITY_LEDGER.jsonl").exists()
    assert verify_complete_run(cell.run_dir, context=cell.context)["status"] == "PASS"


def test_formal_physical_cell_rejects_mock_provider_before_any_label_write(
    tmp_path,
) -> None:
    generation_dir = tmp_path / "formal-mock"
    generation_dir.mkdir()
    plan = _formal_plan(generation_dir, admitted=(ArmId.D1_PACKET,))
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    seal_generation_plan(plan_path, plan)
    supervisor, client = _prepare_formal_prediction(
        plan.cells[0], plan_path, barrier_path
    )
    try:
        with pytest.raises(GenerationBarrierError, match="mock/unattested"):
            seal_generation_prediction_barrier(
                plan_path, barrier_path, _bindings(plan)
            )
    finally:
        client.close()
        supervisor.close()
    assert not barrier_path.exists()
    assert not (Path(plan.cells[0].run_dir) / "MATURITY_LEDGER.jsonl").exists()


def test_joint_unseal_rejects_partial_set_and_statistics_hmac_drift(
    tmp_path,
) -> None:
    generation_dir = tmp_path / "formal-joint"
    generation_dir.mkdir()
    plan = _formal_plan(
        generation_dir, folds=("fold0", "fold1"), admitted=(ArmId.N0,)
    )
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    joint_path = generation_dir / "GENERATION_JOINT_UNSEAL.json"
    seal_generation_plan(plan_path, plan)
    handles = [
        _prepare_formal_prediction(cell, plan_path, barrier_path)
        for cell in plan.cells
    ]
    seal_generation_prediction_barrier(plan_path, barrier_path, _bindings(plan))
    joint_key = b"joint-unseal-test-key-32-bytes!!"
    try:
        with pytest.raises(EvaluatorProtocolError, match="exact complete"):
            issue_generation_joint_unseal_authorization(
                (handles[0][0],),
                joint_key=joint_key,
                statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
                authorization_path=joint_path,
            )
        assert not joint_path.exists()

        with pytest.raises(EvaluatorProtocolError, match="frozen generation path"):
            issue_generation_joint_unseal_authorization(
                tuple(item[0] for item in handles),
                joint_key=joint_key,
                statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
                authorization_path=generation_dir / "ALTERNATE_UNSEAL.json",
            )
        with pytest.raises(EvaluatorProtocolError, match="statistics executable"):
            issue_generation_joint_unseal_authorization(
                tuple(item[0] for item in handles),
                joint_key=joint_key,
                statistics_executable_hash="f" * 64,
                authorization_path=joint_path,
            )
        assert not joint_path.exists()

        joint = issue_generation_joint_unseal_authorization(
            tuple(item[0] for item in handles),
            joint_key=joint_key,
            statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
            authorization_path=joint_path,
        )
        tampered = joint.record()
        tampered["statistics_executable_hash"] = "f" * 64
        tampered_body = {
            key: value
            for key, value in tampered.items()
            if key not in {"joint_unseal_hash", "auth_tag"}
        }
        tampered["joint_unseal_hash"] = canonical_sha256(tampered_body)
        with pytest.raises(EvaluatorProtocolError, match="HMAC mismatch"):
            handles[0][0].issue_formal_finalize_authorization(
                joint_unseal=tampered, joint_key=joint_key
            )
        for cell in plan.cells:
            assert not (Path(cell.run_dir) / "MATURITY_LEDGER.jsonl").exists()
        with pytest.raises(EvaluatorProtocolError, match="already (exists|issued)"):
            issue_generation_joint_unseal_authorization(
                tuple(item[0] for item in handles),
                joint_key=joint_key,
                statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
                authorization_path=joint_path,
            )
    finally:
        for supervisor, client in handles:
            client.close()
            supervisor.close()


def test_formal_evaluators_reject_bad_hmac_and_cross_cell_authorization_before_labels(
    tmp_path,
) -> None:
    generation_dir = tmp_path / "formal"
    generation_dir.mkdir()
    plan = _formal_plan(
        generation_dir,
        folds=("fold0", "fold1"),
        admitted=(ArmId.N0,),
    )
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    seal_generation_plan(plan_path, plan)
    handles = [
        _prepare_formal_prediction(cell, plan_path, barrier_path)
        for cell in plan.cells
    ]
    seal_generation_prediction_barrier(plan_path, barrier_path, _bindings(plan))
    joint_key = b"joint-unseal-test-key-32-bytes!!"
    joint = issue_generation_joint_unseal_authorization(
        tuple(item[0] for item in handles),
        joint_key=joint_key,
        statistics_executable_hash=STATISTICS_EXECUTABLE_HASH,
        authorization_path=generation_dir / "GENERATION_JOINT_UNSEAL.json",
    )
    first_supervisor, first_client = handles[0]
    second_supervisor, second_client = handles[1]
    authorization = first_supervisor.issue_formal_finalize_authorization(
        joint_unseal=joint, joint_key=joint_key
    )
    try:
        tampered = authorization.record()
        tampered["auth_tag"] = (
            "e" * 64 if authorization.auth_tag != "e" * 64 else "f" * 64
        )
        with pytest.raises(EvaluatorProtocolError, match="FINALIZE_REJECTED"):
            first_client.finalize_and_score(formal_authorization=tampered)

        # Bypass the prediction-side convenience check to exercise the second
        # evaluator's session/cell/state-key verification directly.
        with pytest.raises(EvaluatorProtocolError, match="FINALIZE_REJECTED"):
            second_client._request("FINALIZE", authorization.record())
    finally:
        for supervisor, client in handles:
            client.close()
            supervisor.close()
    for cell in plan.cells:
        run_dir = Path(cell.run_dir)
        assert not (run_dir / "ACCESS_LEDGER.seal.json").exists()
        assert not (run_dir / "MATURITY_LEDGER.jsonl").exists()
        assert not (run_dir / "RUN_SEAL.json").exists()


def test_full_two_by_two_generation_seals_score_inputs_only_after_all_runs(
    tmp_path,
) -> None:
    generation_dir = tmp_path / "generation"
    generation_dir.mkdir()
    plan = _plan(
        generation_dir,
        folds=("fold0", "fold1"),
        arms=(ArmId.D1_PACKET, ArmId.N0),
    )
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    score_path = generation_dir / "GENERATION_SCORE_INPUT_SEAL.json"
    seal_generation_plan(plan_path, plan)
    for cell in plan.cells:
        _prepare_prediction(cell, complete_replay=True)
    barrier = seal_generation_prediction_barrier(
        plan_path, barrier_path, _bindings(plan)
    )
    assert len(barrier.cell_receipts) == 4
    assert not score_path.exists()
    for cell in plan.cells:
        permit = make_finalize_permit(plan_path, barrier_path, cell_id=cell.cell_id)
        verify_finalize_permit(
            plan_path,
            barrier_path,
            permit,
            expected_cell_id=cell.cell_id,
        )
    for cell in plan.cells:
        _finalize(cell)

    score_seal = seal_generation_score_inputs(
        plan_path, barrier_path, score_path, _bindings(plan)
    )
    assert score_path.exists()
    assert len(score_seal.cells) == 4
    assert {item.cell_id for item in score_seal.cells} == {
        item.cell_id for item in plan.cells
    }
    for cell in plan.cells:
        assert verify_complete_run(cell.run_dir, context=cell.context)["status"] == "PASS"


def test_missing_final_run_seal_blocks_score_input_seal_before_write(tmp_path) -> None:
    generation_dir = tmp_path / "generation"
    generation_dir.mkdir()
    plan = _plan(generation_dir)
    plan_path = generation_dir / "GENERATION_PLAN.json"
    barrier_path = generation_dir / "GENERATION_BARRIER.json"
    score_path = generation_dir / "GENERATION_SCORE_INPUT_SEAL.json"
    seal_generation_plan(plan_path, plan)
    _prepare_prediction(plan.cells[0], complete_replay=True)
    seal_generation_prediction_barrier(plan_path, barrier_path, _bindings(plan))
    permit = make_finalize_permit(
        plan_path, barrier_path, cell_id=plan.cells[0].cell_id
    )
    verify_finalize_permit(
        plan_path,
        barrier_path,
        permit,
        expected_cell_id=plan.cells[0].cell_id,
    )

    with pytest.raises(GenerationBarrierError, match="final run seal"):
        seal_generation_score_inputs(
            plan_path, barrier_path, score_path, _bindings(plan)
        )
    assert not score_path.exists()
