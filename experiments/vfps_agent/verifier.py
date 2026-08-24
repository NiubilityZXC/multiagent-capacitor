"""Strict CAP-ACT response verification and deterministic local execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping, Sequence

from .actions import Action, ActionSpace, BaseOperator, TransformOperator
from .canonical import canonical_sha256, strict_json_loads
from .contracts import ForecastKey
from .registry import (
    CAPActionRegistry,
    ForecastBundle,
    ForecastStatus,
    ForecastValue,
    RegistryError,
)


ACTION_RESPONSE_SCHEMA_VERSION = "CAPActionSelectionResponse.v1"
DIRECT_RESPONSE_SCHEMA_VERSION = "CAPDirectForecastResponse.v1"
IF_RESPONSE_SCHEMA_VERSION = "CAPIFRepresentationResponse.v1"


class VerificationError(ValueError):
    """A response has no authority to produce a committed prediction."""


class ActionAuthority(str, Enum):
    H1 = "H1"
    RF1 = "RF1"
    RC1 = "RC1"
    ACT1 = "ACT1"
    ACT_COMP96 = "ACT-COMP96"


@dataclass(frozen=True, slots=True)
class VerifiedSelection:
    key: ForecastKey
    action: Action


@dataclass(frozen=True, slots=True)
class VerificationCertificate:
    response_schema_version: str
    registry_hash: str
    action_space: str
    selected_action_hashes: tuple[tuple[str, str], ...]
    prediction_hash: str

    @property
    def certificate_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class VerifiedBundle:
    bundle: ForecastBundle
    certificate: VerificationCertificate
    selected_abstention: bool = False


def _parse_payload(payload: str | bytes | bytearray | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        value: Any = dict(payload)
    else:
        value = strict_json_loads(payload)
    if not isinstance(value, Mapping):
        raise VerificationError("response must be a JSON object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise VerificationError(f"{label} keys do not match the frozen schema")


def _planned_map(planned_keys: Sequence[ForecastKey]) -> dict[str, ForecastKey]:
    result = {item.token: item for item in planned_keys}
    if not result or len(result) != len(tuple(planned_keys)):
        raise VerificationError("planned forecast keys must be non-empty and unique")
    return result


def _authority_space(authority: ActionAuthority) -> ActionSpace:
    if authority is ActionAuthority.ACT_COMP96:
        return ActionSpace.COMPOSITIONAL96
    return ActionSpace.PRIMARY19


def _check_authority(
    action: Action,
    *,
    authority: ActionAuthority,
    key_token: str,
    registry: CAPActionRegistry,
) -> None:
    if registry.numerical.fallback_bundle.by_key[key_token].status is ForecastStatus.RUL_NA:
        if action.transform is not None or action.base.operator is not BaseOperator.FALLBACK:
            raise VerificationError("endpoint-gated RUL has one forced RUL_NA action")
        return
    if authority is ActionAuthority.H1:
        if action.transform is not None or action.base.operator is not BaseOperator.EMIT:
            raise VerificationError("H1 may select only one frozen EMIT model per key")
        return
    if authority is ActionAuthority.RF1:
        if action.transform is not None or action.base.operator is not BaseOperator.FUSE:
            raise VerificationError("RF1 may select only one frozen convex template per key")
        return
    if authority is ActionAuthority.RC1:
        champion = registry.numerical.champion_map[key_token]
        if action.base.action_id != champion.action_id:
            raise VerificationError("RC1 may correct only the literal common FALLBACK")
        if action.transform not in {None, TransformOperator.SHIFT, TransformOperator.INFLATE}:
            raise VerificationError("RC1 correction is outside the frozen trust region")
        return
    # ACT1 and ACT-COMP96 are already restricted by registry.resolve.


def parse_action_selections(
    payload: str | bytes | bytearray | Mapping[str, Any],
    *,
    authority: ActionAuthority,
    registry: CAPActionRegistry,
    planned_keys: Sequence[ForecastKey] | None = None,
) -> tuple[VerifiedSelection, ...]:
    value = _parse_payload(payload)
    _exact_keys(value, {"schema_version", "selections"}, "action response")
    if value["schema_version"] != ACTION_RESPONSE_SCHEMA_VERSION:
        raise VerificationError("unknown action response schema")
    selections = value["selections"]
    if not isinstance(selections, list):
        raise VerificationError("action selections must be a list")
    keys = tuple(planned_keys or registry.numerical.planned_keys)
    planned = _planned_map(keys)
    seen: set[str] = set()
    verified: list[VerifiedSelection] = []
    space = _authority_space(authority)
    for item in selections:
        if not isinstance(item, Mapping):
            raise VerificationError("each action selection must be an object")
        _exact_keys(item, {"key", "action_id"}, "action selection")
        key_token = item["key"]
        action_id = item["action_id"]
        if not isinstance(key_token, str) or key_token not in planned or key_token in seen:
            raise VerificationError("action response has an unknown or duplicate key")
        if not isinstance(action_id, str):
            raise VerificationError("action_id must be a canonical hash string")
        try:
            action = registry.resolve(action_id, key_token=key_token, action_space=space)
        except RegistryError as exc:
            raise VerificationError("action_id is outside the selected authority") from exc
        _check_authority(action, authority=authority, key_token=key_token, registry=registry)
        verified.append(VerifiedSelection(planned[key_token], action))
        seen.add(key_token)
    if seen != set(planned):
        raise VerificationError("action response must cover every planned key")
    return tuple(sorted(verified, key=lambda item: item.key.token))


def execute_action_selections(
    selections: Sequence[VerifiedSelection],
    *,
    authority: ActionAuthority,
    registry: CAPActionRegistry,
) -> VerifiedBundle:
    expected = tuple(key.token for key in registry.numerical.planned_keys)
    actual = tuple(item.key.token for item in selections)
    if actual != expected:
        raise VerificationError("verified selections do not exactly cover the registry keys")
    forecasts: list[ForecastValue] = []
    try:
        for selection in selections:
            forecast = registry.numerical.execute(selection.action, selection.key)
            registry.numerical.validate_forecast(forecast)
            forecasts.append(forecast)
    except (RegistryError, KeyError, ValueError, OverflowError) as exc:
        raise VerificationError("deterministic action execution failed") from exc
    selected_abstention = any(
        item.action.transform is None
        and item.action.base.operator is BaseOperator.FALLBACK
        and registry.numerical.fallback_bundle.by_key[item.key.token].status is not ForecastStatus.RUL_NA
        for item in selections
    )
    all_abstain = all(
        (
            registry.numerical.fallback_bundle.by_key[item.key.token].status is ForecastStatus.RUL_NA
            or (item.action.transform is None and item.action.base.operator is BaseOperator.FALLBACK)
        )
        for item in selections
    )
    bundle = (
        registry.numerical.fallback_bundle
        if all_abstain
        else ForecastBundle("capact_verified", tuple(forecasts))
    )
    space = _authority_space(authority)
    certificate = VerificationCertificate(
        response_schema_version=ACTION_RESPONSE_SCHEMA_VERSION,
        registry_hash=registry.action_manifest_hash,
        action_space=space.value,
        selected_action_hashes=tuple((item.key.token, item.action.action_hash) for item in selections),
        prediction_hash=bundle.bundle_hash,
    )
    return VerifiedBundle(
        bundle,
        certificate,
        selected_abstention=selected_abstention,
    )


def verify_and_execute_actions(
    payload: str | bytes | bytearray | Mapping[str, Any],
    *,
    authority: ActionAuthority,
    registry: CAPActionRegistry,
) -> VerifiedBundle:
    selections = parse_action_selections(payload, authority=authority, registry=registry)
    return execute_action_selections(selections, authority=authority, registry=registry)


def parse_direct_bundle(
    payload: str | bytes | bytearray | Mapping[str, Any],
    *,
    registry: CAPActionRegistry,
) -> VerifiedBundle:
    value = _parse_payload(payload)
    _exact_keys(value, {"schema_version", "forecasts"}, "direct response")
    if value["schema_version"] != DIRECT_RESPONSE_SCHEMA_VERSION:
        raise VerificationError("unknown direct response schema")
    records = value["forecasts"]
    if not isinstance(records, list):
        raise VerificationError("direct forecasts must be a list")
    planned = _planned_map(registry.numerical.planned_keys)
    seen: set[str] = set()
    forecasts: list[ForecastValue] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise VerificationError("direct forecast entries must be objects")
        key_token = record.get("key")
        if not isinstance(key_token, str) or key_token not in planned or key_token in seen:
            raise VerificationError("direct response has an unknown or duplicate key")
        status = record.get("status")
        if status == ForecastStatus.RUL_NA.value:
            _exact_keys(record, {"key", "status"}, "RUL_NA forecast")
            forecast = ForecastValue.rul_na(planned[key_token])
        elif status == ForecastStatus.NUMERIC.value:
            _exact_keys(
                record,
                {"key", "status", "point", "lower", "median", "upper"},
                "numeric forecast",
            )
            raw_numbers = tuple(record[name] for name in ("point", "lower", "median", "upper"))
            if any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(float(item))
                for item in raw_numbers
            ):
                raise VerificationError("direct forecast numbers must all be finite")
            forecast = ForecastValue.numeric(
                planned[key_token],
                point=float(record["point"]),
                lower=float(record["lower"]),
                median=float(record["median"]),
                upper=float(record["upper"]),
            )
        else:
            raise VerificationError("direct forecast has an unknown status")
        try:
            registry.numerical.validate_forecast(forecast)
        except RegistryError as exc:
            raise VerificationError("direct forecast violates the target contract") from exc
        forecasts.append(forecast)
        seen.add(key_token)
    if seen != set(planned):
        raise VerificationError("direct response must cover every planned key")
    bundle = ForecastBundle("capact_direct", tuple(sorted(forecasts, key=lambda item: item.key.token)))
    certificate = VerificationCertificate(
        response_schema_version=DIRECT_RESPONSE_SCHEMA_VERSION,
        registry_hash=registry.action_manifest_hash,
        action_space="DIRECT_NUMERIC",
        selected_action_hashes=(),
        prediction_hash=bundle.bundle_hash,
    )
    return VerifiedBundle(bundle, certificate, selected_abstention=False)


def _parse_atom(value: Any, registry: CAPActionRegistry) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        raise VerificationError("predicate atom must be an object")
    _exact_keys(value, {"operator", "feature_id", "bin_id"}, "predicate atom")
    if value["operator"] != "ATOM":
        raise VerificationError("IF1 children must be atomic predicates")
    feature_id, bin_id = value["feature_id"], value["bin_id"]
    try:
        feature = registry.features.by_id[feature_id]
    except (KeyError, TypeError) as exc:
        raise VerificationError("predicate references an unknown feature") from exc
    if bin_id not in feature.bin_ids:
        raise VerificationError("predicate references an unknown frozen bin")
    return feature_id, bin_id


def _evaluate_predicate(
    value: Any,
    *,
    feature_bins: Mapping[str, str],
    registry: CAPActionRegistry,
) -> bool:
    if not isinstance(value, Mapping):
        raise VerificationError("predicate must be an object")
    operator = value.get("operator")
    if operator == "ATOM":
        feature_id, bin_id = _parse_atom(value, registry)
        if feature_id not in feature_bins:
            raise VerificationError("current packet lacks a referenced feature bin")
        return feature_bins[feature_id] == bin_id
    if operator not in {"AND", "OR"}:
        raise VerificationError("unknown IF1 predicate operator")
    _exact_keys(value, {"operator", "children"}, "compound predicate")
    children = value["children"]
    if not isinstance(children, list) or len(children) != 2:
        raise VerificationError("compound predicate requires exactly two atoms")
    parsed = tuple(_parse_atom(child, registry) for child in children)
    hashes = tuple(canonical_sha256(child) for child in children)
    if hashes != tuple(sorted(hashes)) or hashes[0] == hashes[1]:
        raise VerificationError("compound predicate children must be distinct and canonical")
    results = tuple(feature_bins.get(feature) == bin_id for feature, bin_id in parsed)
    if any(feature not in feature_bins for feature, _ in parsed):
        raise VerificationError("current packet lacks a referenced feature bin")
    return all(results) if operator == "AND" else any(results)


def verify_and_execute_if_representation(
    payload: str | bytes | bytearray | Mapping[str, Any],
    *,
    feature_bins: Mapping[str, str],
    registry: CAPActionRegistry,
) -> VerifiedBundle:
    """Execute IF1 as a representation ablation with a primary quotient of 19."""

    value = _parse_payload(payload)
    _exact_keys(value, {"schema_version", "artifacts"}, "IF1 response")
    if value["schema_version"] != IF_RESPONSE_SCHEMA_VERSION:
        raise VerificationError("unknown IF1 response schema")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list):
        raise VerificationError("IF1 artifacts must be a list")
    planned = _planned_map(registry.numerical.planned_keys)
    selections: list[dict[str, str]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise VerificationError("IF1 artifact must be an object")
        key_token = artifact.get("key")
        if not isinstance(key_token, str) or key_token not in planned or key_token in seen:
            raise VerificationError("IF1 response has an unknown or duplicate key")
        if set(artifact) == {"key", "action_id"}:
            active = artifact["action_id"]
            if not isinstance(active, str):
                raise VerificationError("IF1 unconditional action must be a hash string")
            try:
                registry.resolve(active, key_token=key_token, action_space=ActionSpace.PRIMARY19)
            except RegistryError as exc:
                raise VerificationError("IF1 action is outside the frozen quotient") from exc
        elif set(artifact) == {"key", "predicate", "true_action_id", "false_action_id"}:
            true_id, false_id = artifact["true_action_id"], artifact["false_action_id"]
            if not isinstance(true_id, str) or not isinstance(false_id, str) or true_id == false_id:
                raise VerificationError("IF1 branches require two distinct action hashes")
            # Resolve both branches even though only one is active; invalid dormant
            # authority is not allowed to hide in the artifact.
            try:
                registry.resolve(true_id, key_token=key_token, action_space=ActionSpace.PRIMARY19)
                registry.resolve(false_id, key_token=key_token, action_space=ActionSpace.PRIMARY19)
            except RegistryError as exc:
                raise VerificationError("IF1 branch is outside the frozen quotient") from exc
            active = true_id if _evaluate_predicate(
                artifact["predicate"], feature_bins=feature_bins, registry=registry
            ) else false_id
        else:
            raise VerificationError("IF1 artifact keys do not match the frozen grammar")
        selections.append({"key": key_token, "action_id": active})
        seen.add(key_token)
    if seen != set(planned):
        raise VerificationError("IF1 response must cover every planned key")
    action_payload = {
        "schema_version": ACTION_RESPONSE_SCHEMA_VERSION,
        "selections": selections,
    }
    # IF1 has the same committed primary action quotient as ACT1.  The distinct
    # response schema is retained only to measure representation behavior.
    selections_verified = parse_action_selections(
        action_payload,
        authority=ActionAuthority.ACT1,
        registry=registry,
    )
    executed = execute_action_selections(
        selections_verified,
        authority=ActionAuthority.ACT1,
        registry=registry,
    )
    certificate = VerificationCertificate(
        response_schema_version=IF_RESPONSE_SCHEMA_VERSION,
        registry_hash=registry.action_manifest_hash,
        action_space=ActionSpace.PRIMARY19.value,
        selected_action_hashes=executed.certificate.selected_action_hashes,
        prediction_hash=executed.bundle.bundle_hash,
    )
    return VerifiedBundle(
        executed.bundle,
        certificate,
        selected_abstention=executed.selected_abstention,
    )
