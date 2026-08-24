"""Immutable numerical, feature, and action registries for CAP-ACT M1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .actions import (
    ACTION_CARDINALITY,
    PRIMARY_ACTION_CARDINALITY,
    Action,
    ActionSpace,
    BaseAction,
    BaseOperator,
    TransformOperator,
    build_action_fixture,
    build_primary_action_fixture,
)
from .canonical import canonical_sha256
from .contracts import ForecastKey


class RegistryError(ValueError):
    """A frozen numerical or feature authority is internally inconsistent."""


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ForecastStatus(str, Enum):
    NUMERIC = "NUMERIC"
    RUL_NA = "RUL_NA"


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegistryError(f"{label} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise RegistryError(f"{label} must be finite")
    return result


def _is_rul_target(target: str) -> bool:
    normalized = "".join(character if character.isalnum() else "_" for character in target.casefold())
    return "rul" in tuple(part for part in normalized.split("_") if part)


@dataclass(frozen=True, slots=True)
class ForecastValue:
    key: ForecastKey
    status: ForecastStatus
    point: float | None = None
    lower: float | None = None
    median: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        names = ("point", "lower", "median", "upper")
        if self.status is ForecastStatus.RUL_NA:
            if not _is_rul_target(self.key.target) or any(getattr(self, name) is not None for name in names):
                raise RegistryError("RUL_NA is valid only for a RUL key and carries no numbers")
            return
        values = tuple(_finite(getattr(self, name), name) for name in names)
        object.__setattr__(self, "point", values[0])
        object.__setattr__(self, "lower", values[1])
        object.__setattr__(self, "median", values[2])
        object.__setattr__(self, "upper", values[3])
        if not values[1] <= values[2] <= values[3]:
            raise RegistryError("forecast quantiles must be monotone")
        if not values[1] <= values[0] <= values[3]:
            raise RegistryError("forecast point must lie inside its interval")

    @classmethod
    def numeric(
        cls,
        key: ForecastKey,
        *,
        point: float,
        lower: float,
        median: float,
        upper: float,
    ) -> "ForecastValue":
        return cls(key, ForecastStatus.NUMERIC, point, lower, median, upper)

    @classmethod
    def rul_na(cls, key: ForecastKey) -> "ForecastValue":
        return cls(key, ForecastStatus.RUL_NA)

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": self.key.token,
            "status": self.status.value,
        }
        if self.status is ForecastStatus.NUMERIC:
            payload.update(
                {
                    "point": self.point,
                    "lower": self.lower,
                    "median": self.median,
                    "upper": self.upper,
                }
            )
        return payload


@dataclass(frozen=True, slots=True)
class ForecastBundle:
    bundle_id: str
    forecasts: tuple[ForecastValue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_id, str) or not self.bundle_id:
            raise RegistryError("bundle_id must be non-empty")
        frozen = tuple(self.forecasts)
        object.__setattr__(self, "forecasts", frozen)
        if not frozen:
            raise RegistryError("forecast bundle cannot be empty")
        tokens = tuple(item.key.token for item in frozen)
        if len(tokens) != len(set(tokens)):
            raise RegistryError("forecast bundle contains duplicate keys")
        if tokens != tuple(sorted(tokens)):
            raise RegistryError("forecast bundle keys must use canonical lexical order")

    @property
    def by_key(self) -> Mapping[str, ForecastValue]:
        return MappingProxyType({item.key.token: item for item in self.forecasts})

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPForecastBundle.v1",
            "bundle_id": self.bundle_id,
            "forecasts": [item.payload() for item in self.forecasts],
        }

    @property
    def bundle_hash(self) -> str:
        return canonical_sha256(self.payload())


@dataclass(frozen=True, slots=True)
class WeightTemplate:
    template_id: str
    weights: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.template_id, str) or not self.template_id:
            raise RegistryError("weight template ID must be non-empty")
        frozen = tuple((model_id, _finite(weight, "weight")) for model_id, weight in self.weights)
        object.__setattr__(self, "weights", frozen)
        model_ids = tuple(model_id for model_id, _ in frozen)
        if not frozen or len(model_ids) != len(set(model_ids)) or model_ids != tuple(sorted(model_ids)):
            raise RegistryError("template weights require unique canonical model order")
        if any(weight < 0.0 for _, weight in frozen):
            raise RegistryError("convex weights cannot be negative")
        if not math.isclose(math.fsum(weight for _, weight in frozen), 1.0, abs_tol=1e-12):
            raise RegistryError("convex weights must sum to one")

    @classmethod
    def from_mapping(cls, template_id: str, weights: Mapping[str, float]) -> "WeightTemplate":
        return cls(template_id, tuple(sorted(weights.items())))

    @property
    def by_model(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self.weights))

    def payload(self) -> dict[str, Any]:
        return {"template_id": self.template_id, "weights": dict(self.weights)}


@dataclass(frozen=True, slots=True)
class ScaleSpec:
    key_token: str
    scale: float

    def __post_init__(self) -> None:
        if not isinstance(self.key_token, str) or not self.key_token:
            raise RegistryError("scale key token must be non-empty")
        value = _finite(self.scale, "training scale")
        if value <= 0.0:
            raise RegistryError("training scale must be positive")
        object.__setattr__(self, "scale", value)


@dataclass(frozen=True, slots=True)
class TargetContract:
    target: str
    unit: str
    numeric_allowed: bool
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if not self.target or not self.unit:
            raise RegistryError("target contract requires target and unit")
        if self.minimum is not None:
            object.__setattr__(self, "minimum", _finite(self.minimum, "contract minimum"))
        if self.maximum is not None:
            object.__setattr__(self, "maximum", _finite(self.maximum, "contract maximum"))
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise RegistryError("target contract minimum exceeds maximum")
        if not self.numeric_allowed and not _is_rul_target(self.target):
            raise RegistryError("only an unqualified RUL endpoint may disable numeric output")

    @property
    def token(self) -> str:
        return f"{self.target}|{self.unit}"

    def payload(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "unit": self.unit,
            "numeric_allowed": self.numeric_allowed,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }


@dataclass(frozen=True, slots=True)
class ChampionBaseSpec:
    """Per-key binding to the literal common FALLBACK/N0 correction anchor."""

    key_token: str
    base: BaseAction

    def __post_init__(self) -> None:
        if not isinstance(self.key_token, str) or not self.key_token:
            raise RegistryError("champion key token must be non-empty")
        if not isinstance(self.base, BaseAction):
            raise RegistryError("champion correction anchor must be a BaseAction")
        if self.base != BaseAction(BaseOperator.FALLBACK):
            raise RegistryError("b_star must be the literal common FALLBACK action")

    def payload(self) -> dict[str, Any]:
        return {"key": self.key_token, "base": self.base.payload()}


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    feature_id: str
    bin_ids: tuple[str, ...]
    lineage_hash: str
    past_only: bool = True

    def __post_init__(self) -> None:
        if not self.feature_id or _SHA256_RE.fullmatch(self.lineage_hash or "") is None:
            raise RegistryError("feature requires an ID and lineage hash")
        bins = tuple(self.bin_ids)
        object.__setattr__(self, "bin_ids", bins)
        if len(bins) != 3 or len(set(bins)) != 3 or bins != tuple(sorted(bins)):
            raise RegistryError("each M1 feature requires exactly three unique bins")
        if not self.past_only:
            raise RegistryError("CAP-ACT feature registry permits only past-only features")

    def payload(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "bin_ids": list(self.bin_ids),
            "lineage_hash": self.lineage_hash,
            "past_only": self.past_only,
        }


@dataclass(frozen=True, slots=True)
class FrozenFeatureRegistry:
    features: tuple[FeatureSpec, ...]

    def __post_init__(self) -> None:
        frozen = tuple(self.features)
        object.__setattr__(self, "features", frozen)
        if len(frozen) != 5:
            raise RegistryError("M1 feature registry requires exactly five features")
        identifiers = tuple(item.feature_id for item in frozen)
        if len(set(identifiers)) != 5 or identifiers != tuple(sorted(identifiers)):
            raise RegistryError("feature IDs must be unique and canonically ordered")

    @property
    def atomic_predicate_count(self) -> int:
        return sum(len(item.bin_ids) for item in self.features)

    @property
    def feature_registry_hash(self) -> str:
        return canonical_sha256(
            {
                "schema_version": "CAPFeatureRegistry.v1",
                "features": [item.payload() for item in self.features],
            }
        )

    @property
    def registry_hash(self) -> str:
        return self.feature_registry_hash

    @property
    def by_id(self) -> Mapping[str, FeatureSpec]:
        return MappingProxyType({item.feature_id: item for item in self.features})


@dataclass(frozen=True, slots=True)
class FrozenNumericalRegistry:
    model_bundles: tuple[ForecastBundle, ...]
    weight_templates: tuple[WeightTemplate, ...]
    fallback_bundle: ForecastBundle
    scales: tuple[ScaleSpec, ...]
    target_contracts: tuple[TargetContract, ...]
    champion_bases: tuple[ChampionBaseSpec, ...]

    def __post_init__(self) -> None:
        bundles = tuple(self.model_bundles)
        templates = tuple(self.weight_templates)
        scales = tuple(self.scales)
        contracts = tuple(self.target_contracts)
        champions = tuple(self.champion_bases)
        object.__setattr__(self, "model_bundles", bundles)
        object.__setattr__(self, "weight_templates", templates)
        object.__setattr__(self, "scales", scales)
        object.__setattr__(self, "target_contracts", contracts)
        object.__setattr__(self, "champion_bases", champions)

        model_ids = tuple(item.bundle_id for item in bundles)
        template_ids = tuple(item.template_id for item in templates)
        if len(model_ids) != 6 or len(set(model_ids)) != 6 or model_ids != tuple(sorted(model_ids)):
            raise RegistryError("M1 numerical registry requires six unique canonical model bundles")
        if len(template_ids) != 5 or len(set(template_ids)) != 5 or template_ids != tuple(sorted(template_ids)):
            raise RegistryError("M1 numerical registry requires five unique canonical weight templates")
        fallback_tokens = tuple(item.key.token for item in self.fallback_bundle.forecasts)
        for bundle in bundles:
            if tuple(item.key.token for item in bundle.forecasts) != fallback_tokens:
                raise RegistryError("every model and fallback must cover the same planned keys")
        for template in templates:
            if tuple(model_id for model_id, _ in template.weights) != model_ids:
                raise RegistryError("every template must assign all six frozen models")
        if tuple(item.key_token for item in scales) != fallback_tokens:
            raise RegistryError("training scales must cover every planned key in canonical order")
        if tuple(item.key_token for item in champions) != fallback_tokens:
            raise RegistryError("champion bases must cover every planned key in canonical order")
        literal_fallback = BaseAction(BaseOperator.FALLBACK)
        if any(item.base != literal_fallback for item in champions):
            raise RegistryError("every b_star must be the literal common FALLBACK action")
        contract_tokens = tuple(item.token for item in contracts)
        if len(contract_tokens) != len(set(contract_tokens)) or contract_tokens != tuple(sorted(contract_tokens)):
            raise RegistryError("target contracts must be unique and canonically ordered")
        for bundle in (*bundles, self.fallback_bundle):
            for forecast in bundle.forecasts:
                self.validate_forecast(forecast)
        key_by_token = {item.token: item for item in self.planned_keys}
        for champion in champions:
            champion_value = self.execute_base(champion.base, key_by_token[champion.key_token])
            fallback_value = self.fallback_bundle.by_key[champion.key_token]
            if canonical_sha256(champion_value.payload()) != canonical_sha256(fallback_value.payload()):
                raise RegistryError("each b_star must be numerically identical to common N0/fallback")

    @property
    def model_ids(self) -> tuple[str, ...]:
        return tuple(item.bundle_id for item in self.model_bundles)

    @property
    def template_ids(self) -> tuple[str, ...]:
        return tuple(item.template_id for item in self.weight_templates)

    @property
    def planned_keys(self) -> tuple[ForecastKey, ...]:
        return tuple(item.key for item in self.fallback_bundle.forecasts)

    @property
    def model_map(self) -> Mapping[str, ForecastBundle]:
        return MappingProxyType({item.bundle_id: item for item in self.model_bundles})

    @property
    def template_map(self) -> Mapping[str, WeightTemplate]:
        return MappingProxyType({item.template_id: item for item in self.weight_templates})

    @property
    def scale_map(self) -> Mapping[str, float]:
        return MappingProxyType({item.key_token: item.scale for item in self.scales})

    @property
    def contract_map(self) -> Mapping[str, TargetContract]:
        return MappingProxyType({item.token: item for item in self.target_contracts})

    @property
    def champion_map(self) -> Mapping[str, BaseAction]:
        return MappingProxyType({item.key_token: item.base for item in self.champion_bases})

    @property
    def numerical_registry_hash(self) -> str:
        return canonical_sha256(
            {
                "schema_version": "CAPNumericalRegistry.v1",
                "model_bundles": [item.payload() for item in self.model_bundles],
                "weight_templates": [item.payload() for item in self.weight_templates],
                "fallback_bundle_hash": self.fallback_bundle.bundle_hash,
                "scales": [{"key": item.key_token, "scale": item.scale} for item in self.scales],
                "target_contracts": [item.payload() for item in self.target_contracts],
                "champion_bases": [item.payload() for item in self.champion_bases],
            }
        )

    @property
    def registry_hash(self) -> str:
        return self.numerical_registry_hash

    def _contract(self, key: ForecastKey) -> TargetContract:
        try:
            return self.contract_map[f"{key.target}|{key.unit}"]
        except KeyError as exc:
            raise RegistryError("forecast key has no frozen target contract") from exc

    def validate_forecast(self, forecast: ForecastValue) -> None:
        contract = self._contract(forecast.key)
        if not contract.numeric_allowed:
            if forecast.status is not ForecastStatus.RUL_NA:
                raise RegistryError("blocked RUL endpoint must be RUL_NA")
            return
        if forecast.status is not ForecastStatus.NUMERIC:
            raise RegistryError("qualified numeric endpoint cannot silently become NA")
        values = (forecast.point, forecast.lower, forecast.median, forecast.upper)
        if contract.minimum is not None and any(value < contract.minimum for value in values if value is not None):
            raise RegistryError("forecast violates frozen target minimum")
        if contract.maximum is not None and any(value > contract.maximum for value in values if value is not None):
            raise RegistryError("forecast violates frozen target maximum")

    def execute_base(self, base: BaseAction, key: ForecastKey) -> ForecastValue:
        token = key.token
        if base.operator is BaseOperator.FALLBACK:
            return self.fallback_bundle.by_key[token]
        if base.operator is BaseOperator.EMIT:
            try:
                return self.model_map[base.reference_id or ""].by_key[token]
            except KeyError as exc:
                raise RegistryError("EMIT references an unavailable model or key") from exc
        try:
            template = self.template_map[base.reference_id or ""]
        except KeyError as exc:
            raise RegistryError("FUSE references an unavailable weight template") from exc
        inputs = [self.model_map[model_id].by_key[token] for model_id, _ in template.weights]
        if all(item.status is ForecastStatus.RUL_NA for item in inputs):
            return ForecastValue.rul_na(key)
        if any(item.status is not ForecastStatus.NUMERIC for item in inputs):
            raise RegistryError("convex fusion cannot mix numeric and NA forecasts")
        weights = [weight for _, weight in template.weights]

        def fused(field: str) -> float:
            raw = [float(getattr(item, field)) for item in inputs]
            value = math.fsum(weight * item for weight, item in zip(weights, raw))
            if value < min(raw) - 1e-12 or value > max(raw) + 1e-12:
                raise RegistryError("convex fusion escaped a candidate hull")
            return value

        result = ForecastValue.numeric(
            key,
            point=fused("point"),
            lower=fused("lower"),
            median=fused("median"),
            upper=fused("upper"),
        )
        self.validate_forecast(result)
        return result

    def execute(self, action: Action, key: ForecastKey) -> ForecastValue:
        base = self.execute_base(action.base, key)
        if action.transform is None or base.status is ForecastStatus.RUL_NA:
            return base
        if action.transform is TransformOperator.SHIFT:
            try:
                delta = float(action.parameter) * self.scale_map[key.token]
            except KeyError as exc:
                raise RegistryError("SHIFT key has no frozen training scale") from exc
            result = ForecastValue.numeric(
                key,
                point=float(base.point) + delta,
                lower=float(base.lower) + delta,
                median=float(base.median) + delta,
                upper=float(base.upper) + delta,
            )
        elif action.transform is TransformOperator.INFLATE:
            factor = float(action.parameter)
            point = float(base.point)
            result = ForecastValue.numeric(
                key,
                point=point,
                lower=point - factor * (point - float(base.lower)),
                median=float(base.median),
                upper=point + factor * (float(base.upper) - point),
            )
            if result.lower > base.lower or result.upper < base.upper:
                raise RegistryError("INFLATE is not allowed to shrink an interval")
        else:  # pragma: no cover - Action construction already closes the enum
            raise RegistryError("unknown action transform")
        self.validate_forecast(result)
        return result


@dataclass(frozen=True, slots=True)
class CAPActionRegistry:
    numerical: FrozenNumericalRegistry
    features: FrozenFeatureRegistry
    actions: tuple[Action, ...] = ()

    def __post_init__(self) -> None:
        actions = tuple(self.actions) or build_action_fixture(
            self.numerical.model_ids,
            self.numerical.template_ids,
        )
        object.__setattr__(self, "actions", actions)
        if len(actions) != ACTION_CARDINALITY or len({item.action_id for item in actions}) != ACTION_CARDINALITY:
            raise RegistryError("CAP-ACT registry must contain exactly 96 unique actions")
        expected = build_action_fixture(self.numerical.model_ids, self.numerical.template_ids)
        if tuple(item.action_id for item in actions) != tuple(item.action_id for item in expected):
            raise RegistryError("action registry differs from the frozen 96-Action fixture")

    @property
    def action_map(self) -> Mapping[str, Action]:
        return MappingProxyType({item.action_id: item for item in self.actions})

    def primary_actions(self, key_token: str) -> tuple[Action, ...]:
        try:
            champion = self.numerical.champion_map[key_token]
        except KeyError as exc:
            raise RegistryError("primary action lookup requires a planned key") from exc
        if self.numerical.fallback_bundle.by_key[key_token].status is ForecastStatus.RUL_NA:
            # An endpoint-gated key has one explicit forced action.  Exposing
            # nineteen syntactic choices that all collapse to RUL_NA would
            # fabricate action authority and active coverage.
            return (Action(BaseAction(BaseOperator.FALLBACK)),)
        return build_primary_action_fixture(
            self.numerical.model_ids,
            self.numerical.template_ids,
            champion,
        )

    def actions_for(self, key_token: str, action_space: ActionSpace) -> tuple[Action, ...]:
        if key_token not in {item.token for item in self.numerical.planned_keys}:
            raise RegistryError("action-space lookup requires a planned key")
        if action_space is ActionSpace.PRIMARY19:
            result = self.primary_actions(key_token)
            expected = (
                1
                if self.numerical.fallback_bundle.by_key[key_token].status is ForecastStatus.RUL_NA
                else PRIMARY_ACTION_CARDINALITY
            )
            if len(result) != expected:
                raise AssertionError("primary action quotient changed")
            return result
        if action_space is ActionSpace.COMPOSITIONAL96:
            if self.numerical.fallback_bundle.by_key[key_token].status is ForecastStatus.RUL_NA:
                return (Action(BaseAction(BaseOperator.FALLBACK)),)
            return self.actions
        raise RegistryError("unknown action space")

    @property
    def action_manifest_hash(self) -> str:
        return canonical_sha256(
            {
                "schema_version": "CAPActionRegistry.v1",
                "numerical_registry_hash": self.numerical.numerical_registry_hash,
                "feature_registry_hash": self.features.feature_registry_hash,
                "actions": [
                    {"action_id": item.action_id, "payload": item.payload()}
                    for item in self.actions
                ],
                "primary_actions_by_key": [
                    {
                        "key": key.token,
                        "action_ids": [item.action_id for item in self.primary_actions(key.token)],
                    }
                    for key in self.numerical.planned_keys
                ],
                "numeric_primary_cardinality": PRIMARY_ACTION_CARDINALITY,
                "numeric_compositional_ablation_cardinality": ACTION_CARDINALITY,
                "forced_rul_na_cardinality": 1,
            }
        )

    @property
    def registry_hash(self) -> str:
        return self.action_manifest_hash

    def resolve(
        self,
        action_id: str,
        *,
        key_token: str,
        action_space: ActionSpace = ActionSpace.PRIMARY19,
    ) -> Action:
        allowed = {item.action_id: item for item in self.actions_for(key_token, action_space)}
        try:
            action = allowed[action_id]
        except KeyError as exc:
            raise RegistryError("action ID is not in the selected frozen action space") from exc
        if action.action_hash != action_id:
            raise RegistryError("action ID does not bind canonical action semantics")
        return action
