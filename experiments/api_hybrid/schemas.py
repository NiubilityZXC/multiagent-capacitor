"""Strict, label-blind contracts for hybrid forecasting agents.

The LLM never supplies the production point forecast.  It may only assign
weights to forecasts already produced by frozen numerical candidates.  This
keeps the online result inside the numerical candidates' convex hull and makes
an API failure recoverable without looking at a future label.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping, Sequence


REQUEST_SCHEMA_VERSION = "cap.hybrid.request.v1"
DECISION_SCHEMA_VERSION = "cap.hybrid.decision.v1"
ROLES = ("regime_analyst", "forecast_critic", "fusion_judge")
TOPOLOGIES = ("single_agent", "fixed_hierarchy", "parallel_debate", "dynamic_route")
REASON_CODES = (
    "LOW_DISAGREEMENT",
    "HIGH_DISAGREEMENT",
    "OOD_PREFIX",
    "STABLE_TREND",
    "CHANGE_POINT_RISK",
    "CANDIDATE_CONSENSUS",
    "TRAIN_ERROR_PRIOR",
    "ABSTAIN",
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}$")
_FORBIDDEN_KEYS = {
    "actual",
    "actual_value",
    "label",
    "labels",
    "future",
    "future_values",
    "suffix",
    "test_suffix",
    "eol",
    "rul",
    "termination",
    "termination_reason",
    "failure_time",
    "failure_status",
    "final_length",
    "final_cycle",
    "row_count",
    "unit_id",
    "physical_unit_id",
    "file_path",
    "source_file",
    "target_observation",
}
_FORBIDDEN_KEY_PARTS = {
    "actual",
    "label",
    "future",
    "suffix",
    "eol",
    "rul",
    "termination",
    "failure",
    "final",
}


class SchemaError(ValueError):
    """Raised when an agent request or response violates the frozen contract."""


def _normalised_key(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _reject_tainted_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalised = _normalised_key(key)
            key_parts = set(normalised.split("_"))
            if normalised in _FORBIDDEN_KEYS or key_parts & _FORBIDDEN_KEY_PARTS:
                raise SchemaError(f"future/label-tainted key is forbidden at {path}.{key}")
            _reject_tainted_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_tainted_keys(child, f"{path}[{index}]")


def _safe_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise SchemaError(f"{label} must be a short safe identifier")
    return value


def _finite_number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise SchemaError(f"{label} must be finite")
    if minimum is not None and result < minimum:
        raise SchemaError(f"{label} must be >= {minimum}")
    return result


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise SchemaError(f"{label} keys mismatch; missing={missing}, extra={extra}")


@dataclass(frozen=True)
class CausalForecastRequest:
    """A fully numeric, causal request passed to every online agent."""

    origin_key: str
    prefix: dict[str, tuple[float, ...]]
    horizons: tuple[int, ...]
    candidate_forecasts: dict[str, dict[str, float]]
    train_only_error_summary: dict[str, dict[str, float]]
    disagreement_score: float
    ood_score: float

    @property
    def candidate_models(self) -> tuple[str, ...]:
        return tuple(sorted(self.candidate_forecasts))

    @property
    def forecast_keys(self) -> tuple[str, ...]:
        return tuple(
            f"{target}@h{horizon}"
            for target in sorted(self.prefix)
            for horizon in self.horizons
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "origin_key": self.origin_key,
            "prefix": {key: list(self.prefix[key]) for key in sorted(self.prefix)},
            "horizons": list(self.horizons),
            "candidate_forecasts": {
                model: {key: self.candidate_forecasts[model][key] for key in self.forecast_keys}
                for model in self.candidate_models
            },
            "train_only_error_summary": {
                model: {key: self.train_only_error_summary[model][key] for key in self.forecast_keys}
                for model in self.candidate_models
            },
            "disagreement_score": self.disagreement_score,
            "ood_score": self.ood_score,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CausalForecastRequest":
        if not isinstance(raw, Mapping):
            raise SchemaError("request must be an object")
        _reject_tainted_keys(raw)
        expected = {
            "schema_version",
            "origin_key",
            "prefix",
            "horizons",
            "candidate_forecasts",
            "train_only_error_summary",
            "disagreement_score",
            "ood_score",
        }
        _exact_keys(raw, expected, "request")
        if raw["schema_version"] != REQUEST_SCHEMA_VERSION:
            raise SchemaError("unsupported request schema version")
        origin_key = _safe_id(raw["origin_key"], "origin_key")

        prefix_raw = raw["prefix"]
        if not isinstance(prefix_raw, Mapping) or not prefix_raw:
            raise SchemaError("prefix must be a non-empty object")
        prefix: dict[str, tuple[float, ...]] = {}
        prefix_length: int | None = None
        for target_raw, values_raw in sorted(prefix_raw.items()):
            target = _safe_id(target_raw, "target")
            if not isinstance(values_raw, Sequence) or isinstance(values_raw, (str, bytes)):
                raise SchemaError(f"prefix[{target}] must be an array")
            values = tuple(_finite_number(item, f"prefix[{target}]") for item in values_raw)
            if not values:
                raise SchemaError(f"prefix[{target}] cannot be empty")
            prefix_length = len(values) if prefix_length is None else prefix_length
            if len(values) != prefix_length:
                raise SchemaError("all target prefixes must have the same causal length")
            prefix[target] = values

        horizons_raw = raw["horizons"]
        if not isinstance(horizons_raw, Sequence) or isinstance(horizons_raw, (str, bytes)):
            raise SchemaError("horizons must be an array")
        horizons: list[int] = []
        for item in horizons_raw:
            if isinstance(item, bool) or not isinstance(item, int) or item < 1:
                raise SchemaError("horizons must contain positive integers")
            horizons.append(item)
        if not horizons or len(set(horizons)) != len(horizons) or tuple(sorted(horizons)) != tuple(horizons):
            raise SchemaError("horizons must be unique, non-empty, and sorted")
        forecast_keys = tuple(
            f"{target}@h{horizon}" for target in sorted(prefix) for horizon in horizons
        )

        candidates_raw = raw["candidate_forecasts"]
        if not isinstance(candidates_raw, Mapping) or not candidates_raw:
            raise SchemaError("candidate_forecasts must be a non-empty object")
        candidates: dict[str, dict[str, float]] = {}
        for model_raw, forecasts_raw in sorted(candidates_raw.items()):
            model = _safe_id(model_raw, "candidate model")
            if not isinstance(forecasts_raw, Mapping):
                raise SchemaError(f"candidate_forecasts[{model}] must be an object")
            _exact_keys(forecasts_raw, set(forecast_keys), f"candidate_forecasts[{model}]")
            candidates[model] = {
                key: _finite_number(forecasts_raw[key], f"candidate_forecasts[{model}][{key}]")
                for key in forecast_keys
            }

        errors_raw = raw["train_only_error_summary"]
        if not isinstance(errors_raw, Mapping):
            raise SchemaError("train_only_error_summary must be an object")
        _exact_keys(errors_raw, set(candidates), "train_only_error_summary")
        errors: dict[str, dict[str, float]] = {}
        for model in sorted(candidates):
            model_errors = errors_raw[model]
            if not isinstance(model_errors, Mapping):
                raise SchemaError(f"train_only_error_summary[{model}] must be an object")
            _exact_keys(model_errors, set(forecast_keys), f"train_only_error_summary[{model}]")
            errors[model] = {
                key: _finite_number(
                    model_errors[key], f"train_only_error_summary[{model}][{key}]", minimum=0.0
                )
                for key in forecast_keys
            }

        disagreement = _finite_number(raw["disagreement_score"], "disagreement_score", minimum=0.0)
        ood = _finite_number(raw["ood_score"], "ood_score", minimum=0.0)
        return cls(
            origin_key=origin_key,
            prefix=prefix,
            horizons=tuple(horizons),
            candidate_forecasts=candidates,
            train_only_error_summary=errors,
            disagreement_score=disagreement,
            ood_score=ood,
        )


@dataclass(frozen=True)
class AgentDecision:
    schema_version: str
    role: str
    origin_key: str
    abstain: bool
    weights: dict[str, float]
    risk_score: float
    reason_codes: tuple[str, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "role": self.role,
            "origin_key": self.origin_key,
            "abstain": self.abstain,
            "weights": dict(sorted(self.weights.items())),
            "risk_score": self.risk_score,
            "reason_codes": list(self.reason_codes),
        }


def parse_agent_decision(
    raw: Mapping[str, Any],
    *,
    request: CausalForecastRequest,
    expected_role: str,
) -> AgentDecision:
    if expected_role not in ROLES:
        raise SchemaError(f"unknown expected role: {expected_role}")
    if not isinstance(raw, Mapping):
        raise SchemaError("agent decision must be an object")
    expected = {
        "schema_version",
        "role",
        "origin_key",
        "abstain",
        "weights",
        "risk_score",
        "reason_codes",
    }
    _exact_keys(raw, expected, "agent decision")
    if raw["schema_version"] != DECISION_SCHEMA_VERSION:
        raise SchemaError("unsupported agent decision schema version")
    if raw["role"] != expected_role:
        raise SchemaError("agent role echo mismatch")
    if raw["origin_key"] != request.origin_key:
        raise SchemaError("agent origin echo mismatch")
    if not isinstance(raw["abstain"], bool):
        raise SchemaError("abstain must be boolean")
    abstain = raw["abstain"]

    weights_raw = raw["weights"]
    if not isinstance(weights_raw, Mapping):
        raise SchemaError("weights must be an object")
    _exact_keys(weights_raw, set(request.candidate_models), "weights")
    weights = {
        model: _finite_number(weights_raw[model], f"weights[{model}]", minimum=0.0)
        for model in request.candidate_models
    }
    if any(value > 1.0 for value in weights.values()):
        raise SchemaError("weights must be <= 1")
    total = sum(weights.values())
    if abstain:
        if abs(total) > 1e-9:
            raise SchemaError("an abstaining agent must emit zero weights")
    elif abs(total - 1.0) > 1e-6:
        raise SchemaError("non-abstaining weights must sum to one")

    risk = _finite_number(raw["risk_score"], "risk_score", minimum=0.0)
    if risk > 1.0:
        raise SchemaError("risk_score must be <= 1")
    codes_raw = raw["reason_codes"]
    if not isinstance(codes_raw, Sequence) or isinstance(codes_raw, (str, bytes)):
        raise SchemaError("reason_codes must be an array")
    codes: list[str] = []
    for code in codes_raw:
        if code not in REASON_CODES:
            raise SchemaError(f"unsupported reason code: {code}")
        codes.append(str(code))
    if len(codes) > 8 or len(set(codes)) != len(codes):
        raise SchemaError("reason_codes must be unique and bounded")
    return AgentDecision(
        schema_version=DECISION_SCHEMA_VERSION,
        role=expected_role,
        origin_key=request.origin_key,
        abstain=abstain,
        weights=weights,
        risk_score=risk,
        reason_codes=tuple(codes),
    )


def agent_json_schema(request: CausalForecastRequest, role: str) -> dict[str, Any]:
    """Return the strict JSON Schema sent to the Responses API."""

    if role not in ROLES:
        raise SchemaError(f"unknown role: {role}")
    weight_properties = {
        model: {"type": "number", "minimum": 0.0, "maximum": 1.0}
        for model in request.candidate_models
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "role",
            "origin_key",
            "abstain",
            "weights",
            "risk_score",
            "reason_codes",
        ],
        "properties": {
            "schema_version": {"const": DECISION_SCHEMA_VERSION},
            "role": {"const": role},
            "origin_key": {"const": request.origin_key},
            "abstain": {"type": "boolean"},
            "weights": {
                "type": "object",
                "additionalProperties": False,
                "required": list(request.candidate_models),
                "properties": weight_properties,
            },
            "risk_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "reason_codes": {
                "type": "array",
                "maxItems": 8,
                "uniqueItems": True,
                "items": {"enum": list(REASON_CODES)},
            },
        },
    }
