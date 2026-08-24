"""Topology orchestration and deterministic fusion for API forecasting agents."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
from typing import Any, Mapping, Protocol

from .schemas import (
    AgentDecision,
    CausalForecastRequest,
    ROLES,
    SchemaError,
    TOPOLOGIES,
    agent_json_schema,
    parse_agent_decision,
)


ROLE_INSTRUCTIONS = {
    "regime_analyst": (
        "Classify the revealed degradation regime using only the supplied causal prefix, "
        "training-only error summaries, and candidate forecasts. Return strict JSON. "
        "Do not invent observations or point forecasts."
    ),
    "forecast_critic": (
        "Stress-test the frozen numerical candidates using only the supplied causal evidence. "
        "Assign weights or abstain. Return strict JSON without prose or new point forecasts."
    ),
    "fusion_judge": (
        "Select a convex combination of the whitelisted numerical candidates. Use no future "
        "labels. Return strict JSON; never directly revise a candidate value."
    ),
}

NUMERIC_COMPLEXITY_ORDER = (
    "last_value",
    "global_drift",
    "local_linear",
    "exponential",
    "local_trend_kf",
    "ridge",
    "gpr",
)


@dataclass(frozen=True)
class ProviderResult:
    status: str
    decision: Mapping[str, Any] | None
    model: str | None = None
    usage: Mapping[str, Any] | None = None
    latency_ms: float | None = None
    error_code: str | None = None


class AgentProvider(Protocol):
    def invoke(
        self,
        *,
        role: str,
        payload: Mapping[str, Any],
        json_schema: Mapping[str, Any],
        instructions: str,
    ) -> ProviderResult: ...


@dataclass(frozen=True)
class CallRecord:
    role: str
    status: str
    model: str | None
    latency_ms: float | None
    error_code: str | None


@dataclass(frozen=True)
class HybridResult:
    origin_key: str
    topology: str
    status: str
    weights: dict[str, float]
    forecast: dict[str, float]
    risk_score: float
    fallback_reason: str | None
    calls: tuple[CallRecord, ...]


def fallback_weights(request: CausalForecastRequest) -> dict[str, float]:
    """Choose the lowest training-only macro error with a deterministic tie-break."""

    complexity = {model: index for index, model in enumerate(NUMERIC_COMPLEXITY_ORDER)}
    ranked: list[tuple[float, int, str]] = []
    for model in request.candidate_models:
        errors = request.train_only_error_summary[model]
        ranked.append(
            (
                sum(errors.values()) / len(errors),
                complexity.get(model, len(NUMERIC_COMPLEXITY_ORDER)),
                model,
            )
        )
    _, _, winner = min(ranked)
    return {model: 1.0 if model == winner else 0.0 for model in request.candidate_models}


def convex_fuse(request: CausalForecastRequest, weights: Mapping[str, float]) -> dict[str, float]:
    if set(weights) != set(request.candidate_models):
        raise SchemaError("fusion weights do not cover the candidate whitelist")
    normalised: dict[str, float] = {}
    for model in request.candidate_models:
        value = float(weights[model])
        if value < 0.0 or value > 1.0:
            raise SchemaError("fusion weights must lie in [0, 1]")
        normalised[model] = value
    if abs(sum(normalised.values()) - 1.0) > 1e-6:
        raise SchemaError("fusion weights must sum to one")
    fused: dict[str, float] = {}
    for forecast_key in request.forecast_keys:
        points = {
            model: request.candidate_forecasts[model][forecast_key]
            for model in request.candidate_models
        }
        value = sum(normalised[model] * points[model] for model in request.candidate_models)
        lower, upper = min(points.values()), max(points.values())
        if value < lower - 1e-12 or value > upper + 1e-12:
            raise SchemaError("convex fusion escaped the candidate hull")
        fused[forecast_key] = value
    return fused


class HybridOrchestrator:
    def __init__(
        self,
        provider: AgentProvider,
        *,
        disagreement_threshold: float,
        ood_threshold: float,
    ) -> None:
        if disagreement_threshold < 0.0 or ood_threshold < 0.0:
            raise ValueError("routing thresholds must be training-side non-negative values")
        self.provider = provider
        self.disagreement_threshold = float(disagreement_threshold)
        self.ood_threshold = float(ood_threshold)

    def _call(
        self,
        role: str,
        request: CausalForecastRequest,
        upstream: Mapping[str, Any] | None = None,
    ) -> tuple[AgentDecision | None, CallRecord]:
        payload = request.as_payload()
        if upstream is not None:
            # Upstream agent decisions are themselves label-blind and validated.
            payload = {**payload, "upstream_agent_decisions": upstream}
        result = self.provider.invoke(
            role=role,
            payload=payload,
            json_schema=agent_json_schema(request, role),
            instructions=ROLE_INSTRUCTIONS[role],
        )
        record = CallRecord(
            role=role,
            status=result.status,
            model=result.model,
            latency_ms=result.latency_ms,
            error_code=result.error_code,
        )
        if result.status != "OK" or result.decision is None:
            return None, record
        try:
            decision = parse_agent_decision(result.decision, request=request, expected_role=role)
        except (SchemaError, TypeError, ValueError):
            return None, CallRecord(
                role=role,
                status="INVALID_DECISION",
                model=result.model,
                latency_ms=result.latency_ms,
                error_code="SCHEMA_OR_SEMANTIC_FAILURE",
            )
        return decision, record

    def _fallback(
        self,
        request: CausalForecastRequest,
        topology: str,
        calls: list[CallRecord],
        reason: str,
    ) -> HybridResult:
        weights = fallback_weights(request)
        return HybridResult(
            origin_key=request.origin_key,
            topology=topology,
            status="FALLBACK",
            weights=weights,
            forecast=convex_fuse(request, weights),
            risk_score=1.0,
            fallback_reason=reason,
            calls=tuple(calls),
        )

    def _numeric_only(self, request: CausalForecastRequest, topology: str) -> HybridResult:
        weights = fallback_weights(request)
        return HybridResult(
            origin_key=request.origin_key,
            topology=topology,
            status="NUMERIC_ONLY",
            weights=weights,
            forecast=convex_fuse(request, weights),
            risk_score=min(1.0, max(request.disagreement_score, request.ood_score)),
            fallback_reason=None,
            calls=(),
        )

    def _single(self, request: CausalForecastRequest, topology: str) -> HybridResult:
        decision, record = self._call("fusion_judge", request)
        if decision is None or decision.abstain:
            return self._fallback(request, topology, [record], "judge_failure_or_abstention")
        return HybridResult(
            origin_key=request.origin_key,
            topology=topology,
            status="OK",
            weights=decision.weights,
            forecast=convex_fuse(request, decision.weights),
            risk_score=decision.risk_score,
            fallback_reason=None,
            calls=(record,),
        )

    def _hierarchy(self, request: CausalForecastRequest, topology: str) -> HybridResult:
        calls: list[CallRecord] = []
        analyst, analyst_record = self._call("regime_analyst", request)
        calls.append(analyst_record)
        if analyst is None:
            return self._fallback(request, topology, calls, "regime_agent_failure")
        critic, critic_record = self._call(
            "forecast_critic", request, {"regime_analyst": analyst.as_payload()}
        )
        calls.append(critic_record)
        if critic is None:
            return self._fallback(request, topology, calls, "critic_agent_failure")
        judge, judge_record = self._call(
            "fusion_judge",
            request,
            {
                "regime_analyst": analyst.as_payload(),
                "forecast_critic": critic.as_payload(),
            },
        )
        calls.append(judge_record)
        if judge is None or judge.abstain:
            return self._fallback(request, topology, calls, "judge_failure_or_abstention")
        return HybridResult(
            origin_key=request.origin_key,
            topology=topology,
            status="OK",
            weights=judge.weights,
            forecast=convex_fuse(request, judge.weights),
            risk_score=max(analyst.risk_score, critic.risk_score, judge.risk_score),
            fallback_reason=None,
            calls=tuple(calls),
        )

    def _parallel(self, request: CausalForecastRequest, topology: str) -> HybridResult:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="cap-agent") as executor:
            analyst_future = executor.submit(self._call, "regime_analyst", request)
            critic_future = executor.submit(self._call, "forecast_critic", request)
            analyst, analyst_record = analyst_future.result()
            critic, critic_record = critic_future.result()
        calls = [analyst_record, critic_record]
        if analyst is None or critic is None:
            return self._fallback(request, topology, calls, "parallel_debate_member_failure")
        judge, judge_record = self._call(
            "fusion_judge",
            request,
            {
                "regime_analyst": analyst.as_payload(),
                "forecast_critic": critic.as_payload(),
            },
        )
        calls.append(judge_record)
        if judge is None or judge.abstain:
            return self._fallback(request, topology, calls, "judge_failure_or_abstention")
        return HybridResult(
            origin_key=request.origin_key,
            topology=topology,
            status="OK",
            weights=judge.weights,
            forecast=convex_fuse(request, judge.weights),
            risk_score=max(analyst.risk_score, critic.risk_score, judge.risk_score),
            fallback_reason=None,
            calls=tuple(calls),
        )

    def run(self, request: CausalForecastRequest, topology: str) -> HybridResult:
        if topology not in TOPOLOGIES:
            raise ValueError(f"unsupported topology: {topology}")
        if topology == "dynamic_route":
            triggered = (
                request.disagreement_score > self.disagreement_threshold
                or request.ood_score > self.ood_threshold
            )
            if not triggered:
                return self._numeric_only(request, topology)
            return self._single(request, topology)
        if topology == "single_agent":
            return self._single(request, topology)
        if topology == "fixed_hierarchy":
            return self._hierarchy(request, topology)
        return self._parallel(request, topology)


def canonical_prompt(payload: Mapping[str, Any]) -> str:
    """Canonical JSON prevents free-form prompt interpolation and injection."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
