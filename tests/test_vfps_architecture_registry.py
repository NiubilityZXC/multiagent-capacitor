from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from experiments.vfps_agent.architecture_registry import (
    ArchitectureCellContext,
    ArchitectureRegistryError,
    append_late_response_event,
    execute_final_decision,
    load_registry,
    validate_a03_specialist_output,
    validate_artifact_instance,
    validate_final_decision,
    validate_registry,
    validate_route_plan,
    validate_slot_closure,
    validate_workflow_closures,
)
from experiments.vfps_agent.canonical import canonical_sha256


ZERO = "0" * 64
ONE = "1" * 64
TWO = "2" * 64


def identity() -> dict[str, str]:
    return {
        "generation_id": "generation-1",
        "outer_fold_id": "fold-1",
        "origin_id_hash": ZERO,
        "request_hash": ONE,
        "data_hash": TWO,
        "schema_hash": canonical_sha256(load_registry()["artifact_schemas"]),
    }


def planned_key_manifest() -> dict[str, object]:
    return {
        "schema_version": "PlannedKeyManifest.v1",
        "keys": [
            {
                "key_id": "k1",
                "target_id": "CAPACITY",
                "unit": "F",
                "minimum": 0.0,
                "maximum": 100.0,
            }
        ],
    }


def context(candidate: str = "A01-HIER-VERIFY-4H") -> ArchitectureCellContext:
    return ArchitectureCellContext(
        identity=identity(),
        candidate_id=candidate,
        planned_key_manifest=planned_key_manifest(),
    )


def route_r01(ctx: ArchitectureCellContext) -> dict[str, object]:
    return {
        "schema_version": "RoutePlan.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "role_id": "w1_typed_router",
        "parent_artifact_hashes": [],
        "route_id": "R01_PERSISTENCE_DRIFT_BASE_INTERVALS",
        "assignments": [
            {"specialist_role_id": "w2_trend_specialist", "view_id": "T_PERSISTENCE_DRIFT"},
            {"specialist_role_id": "w3_uncertainty_specialist", "view_id": "U_BASE_INTERVALS"},
        ],
        "route_origin": "PROVIDER_ROUTER",
    }


def route_r00(
    ctx: ArchitectureCellContext, w1_failure: dict[str, object]
) -> dict[str, object]:
    return {
        "schema_version": "RoutePlan.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "role_id": "local_route_default",
        "parent_artifact_hashes": [canonical_sha256(w1_failure)],
        "route_id": "R00_DEFAULT_N0_GLOBAL",
        "assignments": [
            {"specialist_role_id": "w2_trend_specialist", "view_id": "T_DEFAULT_N0_GLOBAL"},
            {"specialist_role_id": "w3_uncertainty_specialist", "view_id": "U_DEFAULT_N0_GLOBAL"},
        ],
        "route_origin": "LOCAL_DEFAULT_AFTER_W1_FAILURE",
    }


def direct_bundle(ctx: ArchitectureCellContext, offset: float = 0.0) -> dict[str, object]:
    return {
        "payload_type": "DIRECT_BUNDLE",
        "planned_key_manifest_hash": ctx.planned_key_manifest_hash,
        "forecasts": [
            {
                "key_id": "k1",
                "point": 10.0 + offset,
                "quantiles": {
                    "q10": 8.0 + offset,
                    "q25": 9.0 + offset,
                    "q75": 11.0 + offset,
                    "q90": 12.0 + offset,
                },
                "confidence_bin": "MEDIUM",
            }
        ],
    }


def forecast_proposal(
    ctx: ArchitectureCellContext, role: str, offset: float
) -> dict[str, object]:
    bundle = direct_bundle(ctx, offset)
    return {
        "schema_version": "ForecastProposal.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "role_id": role,
        "parent_artifact_hashes": [],
        "planned_key_manifest_hash": bundle["planned_key_manifest_hash"],
        "forecasts": bundle["forecasts"],
        "status": "VALID_PROPOSAL",
    }


def critique(
    ctx: ArchitectureCellContext,
    w1: dict[str, object],
    w2: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": "Critique.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "role_id": "w3_constraint_critic",
        "parent_artifact_hashes": [canonical_sha256(w1), canonical_sha256(w2)],
        "assessments": [
            {"proposal_hash": canonical_sha256(w1), "flags": ["PASS"]},
            {"proposal_hash": canonical_sha256(w2), "flags": ["PASS"]},
        ],
        "recommendation": "MEDIAN_W1_W2_N0",
    }


def final_decision(
    ctx: ArchitectureCellContext,
    parents: dict[str, dict[str, object]],
    code: str,
    role: str,
    aggregation: str,
    refs: list[str],
) -> dict[str, object]:
    return {
        "schema_version": "FinalDecision.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "role_id": role,
        "parent_artifact_hashes": [
            canonical_sha256(parents[slot]) for slot in ("w1", "w2", "w3")
        ],
        "decision_code": code,
        "aggregation_id": aggregation,
        "source_refs": refs,
    }


def specialist_envelope(
    ctx: ArchitectureCellContext,
    route: dict[str, object],
    *,
    role: str = "w2_trend_specialist",
) -> dict[str, object]:
    view = next(
        item["view_id"]
        for item in route["assignments"]
        if item["specialist_role_id"] == role
    )
    action_id = "FALLBACK" if view.endswith("DEFAULT_N0_GLOBAL") else "EMIT_M_LAST_VALUE"
    diagnostic = {
        "schema_version": "DiagnosticEvidence.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "role_id": role,
        "parent_artifact_hashes": [canonical_sha256(route)],
        "evidence": [
            {
                "key_id": "k1",
                "packet_field_hashes": ["8" * 64],
                "trend": "WEAK_DOWN",
                "curvature": "LINEAR",
                "noise": "LOW",
                "change": "NONE",
            }
        ],
    }
    diagnostic_hash = canonical_sha256(diagnostic)
    action = {
        "schema_version": "ActionProposal.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "role_id": role,
        "parent_route_hash": canonical_sha256(route),
        "diagnostic_evidence_hash": diagnostic_hash,
        "planned_key_manifest_hash": ctx.planned_key_manifest_hash,
        "actions": [{"key_id": "k1", "action_id": action_id}],
        "status": "VALID_ACTION_PROPOSAL",
    }
    return {
        "schema_version": "A03SpecialistOutput.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "role_id": role,
        "parent_route_hash": canonical_sha256(route),
        "assigned_view_id": view,
        "diagnostic_evidence": diagnostic,
        "diagnostic_evidence_hash": diagnostic_hash,
        "action_proposal": action,
        "action_proposal_hash": canonical_sha256(action),
    }


def worker_failure(
    registry: dict[str, object],
    ctx: ArchitectureCellContext,
    slot_id: str,
    *,
    parent_artifacts: dict[str, dict[str, object]],
    state: str = "NOT_STARTED_DEADLINE",
) -> dict[str, object]:
    candidate = registry["candidates"][ctx.candidate_id]
    slot = next(item for item in candidate["slots"] if item["slot_id"] == slot_id)
    code = {
        "FINISHED_SCHEMA_INVALID": "SCHEMA_INVALID",
        "PROVIDER_ERROR": "PROVIDER_ERROR",
        "TRANSPORT_FAILURE_CONSUMED": "TRANSPORT_FAILURE_CONSUMED",
        "TIMEOUT_CONSUMED": "TIMEOUT_CONSUMED",
        "NOT_STARTED_DEADLINE": "NOT_STARTED_DEADLINE",
    }[state]
    return {
        "schema_version": "WorkerFailure.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "slot_id": slot_id,
        "role_id": slot["role_id"],
        "prompt_sha256": registry["prompt_registry"][ctx.candidate_id][slot_id]["prompt_sha256"],
        "failure_code": code,
        "provider_send_attempts": 0 if state == "NOT_STARTED_DEADLINE" else 1,
        "slot_closure_state": state,
        "parent_artifact_hashes": [
            canonical_sha256(parent_artifacts[item]) for item in slot["parents"]
        ],
    }


def slot_closure(
    ctx: ArchitectureCellContext,
    artifact: dict[str, object],
    slot_id: str,
    role_id: str,
    state: str,
) -> dict[str, object]:
    return {
        "schema_version": "SlotClosure.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "slot_id": slot_id,
        "role_id": role_id,
        "provider_send_attempts": 0 if state == "NOT_STARTED_DEADLINE" else 1,
        "slot_closure_state": state,
        "output_artifact_schema": artifact["schema_version"],
        "output_artifact_hash": canonical_sha256(artifact),
    }


def workflow_records(
    registry: dict[str, object],
    ctx: ArchitectureCellContext,
    parents: dict[str, dict[str, object]],
    w4_output: dict[str, object],
    *,
    durable_w1: dict[str, object] | None = None,
) -> list[tuple[dict[str, object], dict[str, object]]]:
    outputs = {
        "w1": durable_w1 if durable_w1 is not None else parents["w1"],
        "w2": parents["w2"],
        "w3": parents["w3"],
        "w4": w4_output,
    }
    records = []
    for slot_id in ("w1", "w2", "w3", "w4"):
        slot = next(
            item
            for item in registry["candidates"][ctx.candidate_id]["slots"]
            if item["slot_id"] == slot_id
        )
        artifact = outputs[slot_id]
        state = (
            artifact["slot_closure_state"]
            if artifact["schema_version"] == "WorkerFailure.v1"
            else "FINISHED_VALID"
        )
        records.append(
            (
                slot_closure(ctx, artifact, slot_id, slot["role_id"], state),
                artifact,
            )
        )
    return records


def execute_artifacts(
    registry: dict[str, object],
    ctx: ArchitectureCellContext,
    parents: dict[str, dict[str, object]],
    *,
    n0: dict[str, object],
    decision: dict[str, object] | None = None,
    w4_failure: dict[str, object] | None = None,
    durable_w1: dict[str, object] | None = None,
    local_route_default: dict[str, object] | None = None,
    numerical_bundles: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    assert (decision is None) != (w4_failure is None)
    w4_output = decision if decision is not None else w4_failure
    assert w4_output is not None
    return execute_final_decision(
        registry,
        ctx,
        workflow_records(
            registry,
            ctx,
            parents,
            w4_output,
            durable_w1=durable_w1,
        ),
        n0=n0,
        local_route_default=local_route_default,
        numerical_bundles=numerical_bundles,
    )


def test_registry_static_contract_and_bound_hashes() -> None:
    registry = load_registry()
    validate_registry(registry)


def test_registry_rejects_prompt_hash_drift_and_late_terminal_state() -> None:
    registry = load_registry()
    broken = deepcopy(registry)
    broken["prompt_registry"]["A01-HIER-VERIFY-4H"]["w1"]["prompt_sha256"] = ZERO
    with pytest.raises(ArchitectureRegistryError, match="prompt hash"):
        validate_registry(broken, verify_bound_files=False)

    broken = deepcopy(registry)
    broken["slot_failure_state_machine"]["states"].append("LATE_DISCARDED")
    with pytest.raises(ArchitectureRegistryError, match="late response"):
        validate_registry(broken, verify_bound_files=False)


def test_route_plan_is_schema_context_and_assignment_bound() -> None:
    registry = load_registry()
    ctx = context("A03-TYPED-ROUTE-4X")
    failure = worker_failure(registry, ctx, "w1", parent_artifacts={})
    validate_route_plan(registry, route_r01(ctx), ctx, provider_output=True)
    validate_route_plan(
        registry,
        route_r00(ctx, failure),
        ctx,
        provider_output=False,
        w1_failure=failure,
    )
    with pytest.raises(ArchitectureRegistryError, match="provider router"):
        validate_route_plan(
            registry, route_r00(ctx, failure), ctx, provider_output=True
        )

    broken = route_r01(ctx)
    broken["assignments"] = list(reversed(broken["assignments"]))
    with pytest.raises(ArchitectureRegistryError, match="schema oneOf|exactly match"):
        validate_route_plan(registry, broken, ctx, provider_output=True)

    broken = route_r01(ctx)
    broken["candidate_id"] = "A01-HIER-VERIFY-4H"
    with pytest.raises(ArchitectureRegistryError, match="schema const|sealed cell"):
        validate_route_plan(registry, broken, ctx, provider_output=True)

    broken = route_r01(ctx)
    broken["identity"]["data_hash"] = "9" * 64
    with pytest.raises(ArchitectureRegistryError, match="identity"):
        validate_route_plan(registry, broken, ctx, provider_output=True)

    bad_identity = deepcopy(identity())
    bad_identity["schema_hash"] = "3" * 64
    bad_ctx = ArchitectureCellContext(
        identity=bad_identity,
        candidate_id="A03-TYPED-ROUTE-4X",
        planned_key_manifest=planned_key_manifest(),
    )
    with pytest.raises(ArchitectureRegistryError, match="pinned schema resource"):
        validate_route_plan(
            registry,
            route_r01(bad_ctx),
            bad_ctx,
            provider_output=True,
        )


def test_a03_specialist_envelope_binds_children_route_actions_and_keys() -> None:
    registry = load_registry()
    ctx = context("A03-TYPED-ROUTE-4X")
    route = route_r01(ctx)
    envelope = specialist_envelope(ctx, route)
    validate_a03_specialist_output(registry, route, envelope, ctx)

    broken = deepcopy(envelope)
    broken["action_proposal"]["actions"][0]["action_id"] = "INFLATE_2_00"
    broken["action_proposal_hash"] = canonical_sha256(broken["action_proposal"])
    with pytest.raises(ArchitectureRegistryError, match="outside its assigned view"):
        validate_a03_specialist_output(registry, route, broken, ctx)

    broken = deepcopy(envelope)
    broken["diagnostic_evidence_hash"] = ZERO
    with pytest.raises(ArchitectureRegistryError, match="diagnostic child hash"):
        validate_a03_specialist_output(registry, route, broken, ctx)


def test_final_decision_is_reference_only_and_ordered_parent_bound() -> None:
    registry = load_registry()
    ctx = context()
    w1 = forecast_proposal(ctx, "w1_trend_forecaster", -1.0)
    w2 = forecast_proposal(ctx, "w2_robust_risk_forecaster", 1.0)
    parents = {"w1": w1, "w2": w2, "w3": critique(ctx, w1, w2)}
    decision = final_decision(
        ctx,
        parents,
        "A01_SELECT_W1",
        "w4_arbiter",
        "AGG_NONE_SELECT_PARENT",
        ["w1"],
    )
    validate_final_decision(registry, decision, ctx, parents)
    broken = deepcopy(decision)
    broken["parent_artifact_hashes"] = list(reversed(broken["parent_artifact_hashes"]))
    with pytest.raises(ArchitectureRegistryError, match="ordered closure"):
        validate_final_decision(registry, broken, ctx, parents)
    broken = deepcopy(decision)
    broken["payload"] = direct_bundle(ctx)
    with pytest.raises(ArchitectureRegistryError, match="additional property"):
        validate_final_decision(registry, broken, ctx, parents)


def test_local_executor_selects_and_aggregates_only_valid_full_bundles() -> None:
    registry = load_registry()
    ctx = context()
    w1 = forecast_proposal(ctx, "w1_trend_forecaster", -1.0)
    w2 = forecast_proposal(ctx, "w2_robust_risk_forecaster", 1.0)
    parents = {"w1": w1, "w2": w2, "w3": critique(ctx, w1, w2)}
    select = final_decision(
        ctx, parents, "A01_SELECT_W1", "w4_arbiter", "AGG_NONE_SELECT_PARENT", ["w1"]
    )
    selected = execute_artifacts(
        registry, ctx, parents, n0=direct_bundle(ctx), decision=select
    )
    assert selected["execution_status"] == "ACTIVE"
    assert selected["payload"]["forecasts"][0]["point"] == 9.0

    aggregate = final_decision(
        ctx,
        parents,
        "A01_MEDIAN_W1_W2_N0",
        "w4_arbiter",
        "AGG_COMPONENTWISE_MEDIAN_W1_W2_N0",
        ["w1", "w2", "N0"],
    )
    output = execute_artifacts(
        registry, ctx, parents, n0=direct_bundle(ctx), decision=aggregate
    )
    assert output["payload"]["forecasts"][0]["point"] == 10.0

    malformed = deepcopy(parents)
    malformed["w1"]["forecasts"][0]["quantiles"]["q10"] = float("nan")
    with pytest.raises((ArchitectureRegistryError, ValueError), match="schema type|nonnumeric|non-finite"):
        execute_artifacts(
            registry, ctx, malformed, n0=direct_bundle(ctx), decision=select
        )


@pytest.mark.parametrize("defect", ["missing", "duplicate", "extra", "quantile", "domain"])
def test_full_planned_key_and_numeric_domain_defects_never_commit_active(
    defect: str,
) -> None:
    registry = load_registry()
    ctx = context()
    w1 = forecast_proposal(ctx, "w1_trend_forecaster", 0.0)
    if defect == "missing":
        w1["forecasts"] = []
    elif defect == "duplicate":
        w1["forecasts"].append(deepcopy(w1["forecasts"][0]))
    elif defect == "extra":
        extra = deepcopy(w1["forecasts"][0])
        extra["key_id"] = "k2"
        w1["forecasts"].append(extra)
    elif defect == "quantile":
        w1["forecasts"][0]["quantiles"]["q10"] = 20.0
    else:
        w1["forecasts"][0]["quantiles"]["q90"] = 101.0
    w2 = forecast_proposal(ctx, "w2_robust_risk_forecaster", 1.0)
    parents = {"w1": w1, "w2": w2, "w3": critique(ctx, w1, w2)}
    decision = final_decision(
        ctx, parents, "A01_SELECT_W1", "w4_arbiter", "AGG_NONE_SELECT_PARENT", ["w1"]
    )
    with pytest.raises(ArchitectureRegistryError):
        execute_artifacts(
            registry, ctx, parents, n0=direct_bundle(ctx), decision=decision
        )


def test_a03_local_executor_uses_assigned_action_and_sealed_numerical_bundle() -> None:
    registry = load_registry()
    ctx = context("A03-TYPED-ROUTE-4X")
    route = route_r01(ctx)
    w2 = specialist_envelope(ctx, route, role="w2_trend_specialist")
    w3 = specialist_envelope(ctx, route, role="w3_uncertainty_specialist")
    parents = {"w1": route, "w2": w2, "w3": w3}
    decision = final_decision(
        ctx,
        parents,
        "A03_SELECT_TREND_ACTION",
        "w4_typed_arbiter",
        "AGG_NONE_SELECT_PARENT",
        ["w2.action_proposal"],
    )
    output = execute_artifacts(
        registry,
        ctx,
        parents,
        n0=direct_bundle(ctx),
        decision=decision,
        numerical_bundles={"M_LAST_VALUE": direct_bundle(ctx, -2.0)},
    )
    assert output["execution_status"] == "ACTIVE"
    assert output["payload"]["forecasts"][0]["point"] == 8.0

    wrong_manifest = direct_bundle(ctx, -2.0)
    wrong_manifest["planned_key_manifest_hash"] = "9" * 64
    fallback = execute_artifacts(
        registry,
        ctx,
        parents,
        n0=direct_bundle(ctx),
        decision=decision,
        numerical_bundles={"M_LAST_VALUE": wrong_manifest},
    )
    assert fallback["execution_status"] == "ERROR_FALLBACK"
    assert fallback["finalization_trigger_type"] == "INVALID_FINAL_DECISION"


def test_a02_minimum_workers_and_source_order_are_frozen() -> None:
    registry = load_registry()
    ctx = context("A02-PAR-DEBATE-4X")
    w1 = forecast_proposal(ctx, "w1_extrapolation_forecaster", 0.0)
    w2 = worker_failure(registry, ctx, "w2", parent_artifacts={})
    w3 = worker_failure(registry, ctx, "w3", parent_artifacts={})
    parents = {"w1": w1, "w2": w2, "w3": w3}
    decision = final_decision(
        ctx,
        parents,
        "A02_MEDIAN_VALID_WORKERS",
        "w4_bounded_adjudicator",
        "AGG_COMPONENTWISE_MEDIAN_VALID_WORKERS",
        ["VALID_W1_W2_W3"],
    )
    output = execute_artifacts(
        registry, ctx, parents, n0=direct_bundle(ctx), decision=decision
    )
    assert output["execution_status"] == "ERROR_FALLBACK"

    w2_valid = forecast_proposal(ctx, "w2_robust_change_forecaster", 2.0)
    parents = {"w1": w1, "w2": w2_valid, "w3": w3}
    decision = final_decision(
        ctx,
        parents,
        "A02_MEDIAN_VALID_WORKERS",
        "w4_bounded_adjudicator",
        "AGG_COMPONENTWISE_MEDIAN_VALID_WORKERS",
        ["VALID_W1_W2_W3"],
    )
    first = execute_artifacts(
        registry, ctx, parents, n0=direct_bundle(ctx), decision=decision
    )
    reordered = {"w3": w3, "w2": w2_valid, "w1": w1}
    second = execute_artifacts(
        registry, ctx, reordered, n0=direct_bundle(ctx), decision=decision
    )
    assert canonical_sha256(first) == canonical_sha256(second)
    assert first["source_artifact_hashes"][:2] == [
        canonical_sha256(w1),
        canonical_sha256(w2_valid),
    ]


def test_invalid_w4_cannot_close_valid_and_typed_failure_commits_error_fallback() -> None:
    registry = load_registry()
    ctx = context()
    w1 = forecast_proposal(ctx, "w1_trend_forecaster", -1.0)
    w2 = forecast_proposal(ctx, "w2_robust_risk_forecaster", 1.0)
    parents = {"w1": w1, "w2": w2, "w3": critique(ctx, w1, w2)}
    decision = final_decision(
        ctx, parents, "A01_SELECT_W1", "w4_arbiter", "AGG_NONE_SELECT_PARENT", ["w1"]
    )
    decision["aggregation_id"] = "AGG_COMMON_FALLBACK"
    with pytest.raises(ArchitectureRegistryError):
        execute_artifacts(
            registry, ctx, parents, n0=direct_bundle(ctx), decision=decision
        )

    failure = worker_failure(
        registry,
        ctx,
        "w4",
        parent_artifacts=parents,
        state="TIMEOUT_CONSUMED",
    )
    failed = execute_artifacts(
        registry, ctx, parents, n0=direct_bundle(ctx), w4_failure=failure
    )
    assert failed["execution_status"] == "ERROR_FALLBACK"
    assert failed["finalization_trigger_type"] == "W4_WORKER_FAILURE"
    assert failed["payload"] == {
        "payload_type": "COMMON_FALLBACK",
        "fallback_id": "N0=b_star=FALLBACK",
    }


def test_closure_schema_rejects_impossible_state_attempt_role_and_output() -> None:
    registry = load_registry()
    ctx = context("A02-PAR-DEBATE-4X")
    failure = worker_failure(registry, ctx, "w1", parent_artifacts={})
    closure = slot_closure(
        ctx,
        failure,
        "w1",
        "w1_extrapolation_forecaster",
        "NOT_STARTED_DEADLINE",
    )
    validate_slot_closure(
        registry, closure, failure, ctx, parent_artifacts={}
    )

    broken = deepcopy(closure)
    broken["provider_send_attempts"] = 1
    with pytest.raises(ArchitectureRegistryError, match="oneOf"):
        validate_artifact_instance(registry, "SlotClosure.v1", broken)
    broken = deepcopy(closure)
    broken["output_artifact_schema"] = "ForecastProposal.v1"
    with pytest.raises(ArchitectureRegistryError, match="oneOf"):
        validate_artifact_instance(registry, "SlotClosure.v1", broken)
    broken = deepcopy(closure)
    broken["role_id"] = "w2_robust_change_forecaster"
    with pytest.raises(ArchitectureRegistryError, match="oneOf"):
        validate_artifact_instance(registry, "SlotClosure.v1", broken)


def test_late_event_is_append_only_and_binds_original_terminal_closure() -> None:
    registry = load_registry()
    ctx = context("A02-PAR-DEBATE-4X")
    failure = worker_failure(
        registry,
        ctx,
        "w1",
        parent_artifacts={},
        state="TIMEOUT_CONSUMED",
    )
    closure = slot_closure(
        ctx,
        failure,
        "w1",
        "w1_extrapolation_forecaster",
        "TIMEOUT_CONSUMED",
    )
    before = canonical_sha256(closure)
    event = {
        "schema_version": "LateResponseEvent.v1",
        "identity": deepcopy(dict(ctx.identity)),
        "candidate_id": ctx.candidate_id,
        "slot_id": "w1",
        "event_state": "LATE_RESPONSE_DISCARDED",
        "original_terminal_closure_hash": before,
        "late_response_sha256": "9" * 64,
        "observed_at_monotonic_ns": 123,
        "closure_mutation_allowed": False,
        "provider_send_delta": 0,
        "prediction_overwrite_allowed": False,
    }
    events = append_late_response_event(
        registry,
        closure,
        failure,
        event,
        [],
        ctx,
        parent_artifacts={},
    )
    assert len(events) == 1
    assert canonical_sha256(closure) == before
    with pytest.raises(ArchitectureRegistryError, match="duplicate late event"):
        append_late_response_event(
            registry,
            closure,
            failure,
            event,
            events,
            ctx,
            parent_artifacts={},
        )
    repeated_response = deepcopy(event)
    repeated_response["observed_at_monotonic_ns"] = 124
    with pytest.raises(ArchitectureRegistryError, match="duplicate late response"):
        append_late_response_event(
            registry,
            closure,
            failure,
            repeated_response,
            events,
            ctx,
            parent_artifacts={},
        )
    orphan = deepcopy(event)
    orphan["original_terminal_closure_hash"] = ZERO
    with pytest.raises(ArchitectureRegistryError, match="original terminal closure"):
        append_late_response_event(
            registry,
            closure,
            failure,
            orphan,
            [],
            ctx,
            parent_artifacts={},
        )

    no_send_failure = worker_failure(registry, ctx, "w1", parent_artifacts={})
    no_send_closure = slot_closure(
        ctx,
        no_send_failure,
        "w1",
        "w1_extrapolation_forecaster",
        "NOT_STARTED_DEADLINE",
    )
    impossible = deepcopy(event)
    impossible["original_terminal_closure_hash"] = canonical_sha256(no_send_closure)
    with pytest.raises(ArchitectureRegistryError, match="sent slot"):
        append_late_response_event(
            registry,
            no_send_closure,
            no_send_failure,
            impossible,
            [],
            ctx,
            parent_artifacts={},
        )


def test_workflow_closure_validator_rejects_duplicate_or_missing_slots() -> None:
    registry = load_registry()
    ctx = context("A02-PAR-DEBATE-4X")
    failure = worker_failure(registry, ctx, "w1", parent_artifacts={})
    closure = slot_closure(
        ctx,
        failure,
        "w1",
        "w1_extrapolation_forecaster",
        "NOT_STARTED_DEADLINE",
    )
    record = (closure, failure)
    with pytest.raises(ArchitectureRegistryError, match="duplicated or incomplete"):
        validate_workflow_closures(registry, ctx, [record, record, record, record])


def test_workflow_ledger_rejects_shadow_w4_parents_before_active() -> None:
    registry = load_registry()
    ctx = context()
    durable_w1 = forecast_proposal(ctx, "w1_trend_forecaster", -1.0)
    durable_w2 = forecast_proposal(ctx, "w2_robust_risk_forecaster", 1.0)
    durable = {
        "w1": durable_w1,
        "w2": durable_w2,
        "w3": critique(ctx, durable_w1, durable_w2),
    }
    shadow_w1 = forecast_proposal(ctx, "w1_trend_forecaster", 20.0)
    shadow_w2 = forecast_proposal(ctx, "w2_robust_risk_forecaster", 22.0)
    shadow = {
        "w1": shadow_w1,
        "w2": shadow_w2,
        "w3": critique(ctx, shadow_w1, shadow_w2),
    }
    shadow_decision = final_decision(
        ctx,
        shadow,
        "A01_SELECT_W1",
        "w4_arbiter",
        "AGG_NONE_SELECT_PARENT",
        ["w1"],
    )
    records = workflow_records(registry, ctx, durable, shadow_decision)
    with pytest.raises(ArchitectureRegistryError, match="ordered closure outputs"):
        execute_final_decision(registry, ctx, records, n0=direct_bundle(ctx))


@pytest.mark.parametrize(
    "state",
    [
        "FINISHED_SCHEMA_INVALID",
        "PROVIDER_ERROR",
        "TRANSPORT_FAILURE_CONSUMED",
        "TIMEOUT_CONSUMED",
        "NOT_STARTED_DEADLINE",
    ],
)
def test_a03_r00_requires_and_accepts_exact_durable_w1_failure(state: str) -> None:
    registry = load_registry()
    ctx = context("A03-TYPED-ROUTE-4X")
    failure = worker_failure(
        registry, ctx, "w1", parent_artifacts={}, state=state
    )
    route = route_r00(ctx, failure)
    w2 = specialist_envelope(ctx, route, role="w2_trend_specialist")
    w3 = specialist_envelope(ctx, route, role="w3_uncertainty_specialist")
    parents = {"w1": route, "w2": w2, "w3": w3}
    decision = final_decision(
        ctx,
        parents,
        "A03_SELECT_TREND_ACTION",
        "w4_typed_arbiter",
        "AGG_NONE_SELECT_PARENT",
        ["w2.action_proposal"],
    )
    output = execute_artifacts(
        registry,
        ctx,
        parents,
        n0=direct_bundle(ctx),
        decision=decision,
        durable_w1=failure,
        local_route_default=route,
    )
    assert output["execution_status"] == "ACTIVE"
    assert output["payload"]["forecasts"][0]["point"] == 10.0

    with pytest.raises(ArchitectureRegistryError, match="lacks its durable w1 failure"):
        validate_route_plan(registry, route, ctx, provider_output=False)

    other_identity = deepcopy(identity())
    other_identity["outer_fold_id"] = "fold-other"
    other_ctx = ArchitectureCellContext(
        identity=other_identity,
        candidate_id=ctx.candidate_id,
        planned_key_manifest=planned_key_manifest(),
    )
    other_failure = worker_failure(
        registry, other_ctx, "w1", parent_artifacts={}, state=state
    )
    with pytest.raises(ArchitectureRegistryError, match="sealed cell|durable w1"):
        validate_route_plan(
            registry,
            route,
            ctx,
            provider_output=False,
            w1_failure=other_failure,
        )


@pytest.mark.parametrize(
    "defect",
    ["missing", "duplicate", "extra", "manifest", "quantile", "domain"],
)
def test_finished_valid_forecast_closure_rejects_semantic_defects(defect: str) -> None:
    registry = load_registry()
    ctx = context("A02-PAR-DEBATE-4X")
    proposal = forecast_proposal(ctx, "w1_extrapolation_forecaster", 0.0)
    if defect == "missing":
        proposal["forecasts"] = []
    elif defect == "duplicate":
        proposal["forecasts"].append(deepcopy(proposal["forecasts"][0]))
    elif defect == "extra":
        extra = deepcopy(proposal["forecasts"][0])
        extra["key_id"] = "k2"
        proposal["forecasts"].append(extra)
    elif defect == "manifest":
        proposal["planned_key_manifest_hash"] = "9" * 64
    elif defect == "quantile":
        proposal["forecasts"][0]["quantiles"]["q10"] = 20.0
    else:
        proposal["forecasts"][0]["quantiles"]["q90"] = 101.0
    closure = slot_closure(
        ctx,
        proposal,
        "w1",
        "w1_extrapolation_forecaster",
        "FINISHED_VALID",
    )
    with pytest.raises(ArchitectureRegistryError):
        validate_slot_closure(
            registry, closure, proposal, ctx, parent_artifacts={}
        )


def test_nonfinite_forecast_cannot_receive_a_canonical_closure_hash() -> None:
    ctx = context("A02-PAR-DEBATE-4X")
    proposal = forecast_proposal(ctx, "w1_extrapolation_forecaster", 0.0)
    proposal["forecasts"][0]["point"] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        canonical_sha256(proposal)


def test_validator_is_offline_and_registry_path_is_project_local() -> None:
    assert Path(load_registry.__globals__["REGISTRY_PATH"]).is_file()
