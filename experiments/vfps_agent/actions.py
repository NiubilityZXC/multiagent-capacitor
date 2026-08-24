"""Finite CAP-ACT action authority used by the mock-only M1 harness.

The action language is intentionally a tagged, non-recursive union.  An
``Action`` may contain one base action and at most one frozen transform.  Its
identifier is the SHA-256 digest of the exact canonical schema payload, so an
identifier cannot silently acquire new semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
import math
from typing import Any, Mapping, Sequence

from .canonical import (
    canonical_bytes,
    canonical_sha256,
    strict_canonical_loads,
    strict_json_loads,
)


ACTION_SCHEMA_VERSION = "CAPAction.v1"
MODEL_COUNT = 6
WEIGHT_TEMPLATE_COUNT = 5
BASE_ACTION_COUNT = MODEL_COUNT + WEIGHT_TEMPLATE_COUNT + 1
SHIFT_BINS = (-1.0, -0.5, 0.5, 1.0)
INFLATION_BINS = (1.25, 1.5, 2.0)
ACTION_CARDINALITY = BASE_ACTION_COUNT * (1 + len(SHIFT_BINS) + len(INFLATION_BINS))
PRIMARY_ACTION_CARDINALITY = BASE_ACTION_COUNT + len(SHIFT_BINS) + len(INFLATION_BINS)
RC1_ACTION_CARDINALITY = 1 + len(SHIFT_BINS) + len(INFLATION_BINS)
IF1_ORIGIN_SPECIFIC_QUOTIENT = PRIMARY_ACTION_CARDINALITY
IF1_COMP96_ORIGIN_SPECIFIC_QUOTIENT = ACTION_CARDINALITY
IF1_PREDICATE_CARDINALITY = 225
IF1_SYNTACTIC_CARDINALITY = (
    PRIMARY_ACTION_CARDINALITY
    + IF1_PREDICATE_CARDINALITY * PRIMARY_ACTION_CARDINALITY * (PRIMARY_ACTION_CARDINALITY - 1)
)

DEFAULT_MODEL_IDS = (
    "last_value",
    "held_prefix_drift",
    "local_linear",
    "log_linear_exponential",
    "causal_local_trend_kf",
    "ridge_causal_increment",
)
DEFAULT_WEIGHT_TEMPLATE_IDS = tuple(f"convex_template_{index}" for index in range(WEIGHT_TEMPLATE_COUNT))


class ActionSchemaError(ValueError):
    """An action is not a member of the frozen tagged union."""


class BaseOperator(str, Enum):
    EMIT = "EMIT"
    FUSE = "FUSE"
    FALLBACK = "FALLBACK"


class TransformOperator(str, Enum):
    SHIFT = "SHIFT"
    INFLATE = "INFLATE"


class ActionSpace(str, Enum):
    """Frozen scientific roles of the two finite action manifests."""

    PRIMARY19 = "PRIMARY19"
    COMPOSITIONAL96 = "COMPOSITIONAL96"


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ActionSchemaError(f"{label} keys do not match the frozen schema")


def _require_nonempty_token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ActionSchemaError(f"{label} must be a non-empty canonical token")
    return value


def _require_frozen_number(value: Any, allowed: Sequence[float], label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ActionSchemaError(f"{label} must be a frozen numeric enum")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized not in allowed:
        raise ActionSchemaError(f"{label} is outside the frozen enum")
    return normalized


@dataclass(frozen=True, slots=True)
class BaseAction:
    operator: BaseOperator
    reference_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.operator, BaseOperator):
            raise ActionSchemaError("base operator must use the frozen enum")
        if self.operator is BaseOperator.FALLBACK:
            if self.reference_id is not None:
                raise ActionSchemaError("FALLBACK cannot carry a reference")
        else:
            _require_nonempty_token(self.reference_id, "base action reference")

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": ACTION_SCHEMA_VERSION,
            "operator": self.operator.value,
        }
        if self.operator is BaseOperator.EMIT:
            payload["model_id"] = self.reference_id
        elif self.operator is BaseOperator.FUSE:
            payload["weight_template_id"] = self.reference_id
        return payload

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.payload())

    @property
    def action_hash(self) -> str:
        return canonical_sha256(self.payload())

    @property
    def action_id(self) -> str:
        return self.action_hash

    @property
    def complexity(self) -> int:
        return 1


@dataclass(frozen=True, slots=True)
class Action:
    """A base action with zero or one frozen transform."""

    base: BaseAction
    transform: TransformOperator | None = None
    parameter: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.base, BaseAction):
            raise ActionSchemaError("action base must be a BaseAction")
        if self.transform is None:
            if self.parameter is not None:
                raise ActionSchemaError("an untransformed action cannot carry a parameter")
            return
        if not isinstance(self.transform, TransformOperator):
            raise ActionSchemaError("transform operator must use the frozen enum")
        if self.transform is TransformOperator.SHIFT:
            normalized = _require_frozen_number(self.parameter, SHIFT_BINS, "shift_bin")
        elif self.transform is TransformOperator.INFLATE:
            normalized = _require_frozen_number(self.parameter, INFLATION_BINS, "inflation_bin")
        else:  # defensive against construction with a non-enum value
            raise ActionSchemaError("unknown transform operator")
        object.__setattr__(self, "parameter", normalized)

    def payload(self) -> dict[str, Any]:
        if self.transform is None:
            return self.base.payload()
        parameter_name = "shift_bin" if self.transform is TransformOperator.SHIFT else "inflation_bin"
        return {
            "schema_version": ACTION_SCHEMA_VERSION,
            "operator": self.transform.value,
            "base_action": self.base.payload(),
            parameter_name: self.parameter,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.payload())

    @property
    def action_hash(self) -> str:
        return canonical_sha256(self.payload())

    @property
    def action_id(self) -> str:
        return self.action_hash

    @property
    def complexity(self) -> int:
        return 1 if self.transform is None else 2


def _parse_base_mapping(value: Any) -> BaseAction:
    if not isinstance(value, Mapping):
        raise ActionSchemaError("base action must be an object")
    version = value.get("schema_version")
    if version != ACTION_SCHEMA_VERSION:
        raise ActionSchemaError("unknown action schema version")
    try:
        operator = BaseOperator(value.get("operator"))
    except (TypeError, ValueError) as exc:
        raise ActionSchemaError("unknown base operator") from exc
    if operator is BaseOperator.EMIT:
        _require_exact_keys(value, {"schema_version", "operator", "model_id"}, "EMIT")
        return BaseAction(operator, _require_nonempty_token(value["model_id"], "model_id"))
    if operator is BaseOperator.FUSE:
        _require_exact_keys(value, {"schema_version", "operator", "weight_template_id"}, "FUSE")
        return BaseAction(
            operator,
            _require_nonempty_token(value["weight_template_id"], "weight_template_id"),
        )
    _require_exact_keys(value, {"schema_version", "operator"}, "FALLBACK")
    return BaseAction(operator)


def parse_action(payload: str | bytes | bytearray | Mapping[str, Any], *, canonical: bool = True) -> Action:
    """Parse exactly one action and reject all unknown or extra fields.

    Bytes/strings default to the stricter artifact boundary: the input must
    already equal its canonical JSON encoding.  Provider response parsing can
    opt out with ``canonical=False`` while retaining duplicate-key, finite and
    exact-schema checks.
    """

    if isinstance(payload, Mapping):
        value: Any = dict(payload)
    elif canonical:
        value = strict_canonical_loads(payload)
    else:
        value = strict_json_loads(payload)
    if not isinstance(value, Mapping):
        raise ActionSchemaError("action must be a JSON object")
    if value.get("schema_version") != ACTION_SCHEMA_VERSION:
        raise ActionSchemaError("unknown action schema version")
    operator = value.get("operator")
    if operator in {item.value for item in BaseOperator}:
        return Action(_parse_base_mapping(value))
    if operator == TransformOperator.SHIFT.value:
        _require_exact_keys(
            value,
            {"schema_version", "operator", "base_action", "shift_bin"},
            "SHIFT",
        )
        return Action(
            _parse_base_mapping(value["base_action"]),
            TransformOperator.SHIFT,
            _require_frozen_number(value["shift_bin"], SHIFT_BINS, "shift_bin"),
        )
    if operator == TransformOperator.INFLATE.value:
        _require_exact_keys(
            value,
            {"schema_version", "operator", "base_action", "inflation_bin"},
            "INFLATE",
        )
        return Action(
            _parse_base_mapping(value["base_action"]),
            TransformOperator.INFLATE,
            _require_frozen_number(value["inflation_bin"], INFLATION_BINS, "inflation_bin"),
        )
    raise ActionSchemaError("unknown action operator")


def build_action_fixture(
    model_ids: Sequence[str] = DEFAULT_MODEL_IDS,
    weight_template_ids: Sequence[str] = DEFAULT_WEIGHT_TEMPLATE_IDS,
) -> tuple[Action, ...]:
    """Construct the exact M=6, W=5, S=4, Q=3 96-Action fixture."""

    models = tuple(model_ids)
    templates = tuple(weight_template_ids)
    if len(models) != MODEL_COUNT or len(set(models)) != MODEL_COUNT:
        raise ValueError("CAP-ACT M1 requires exactly six unique model IDs")
    if len(templates) != WEIGHT_TEMPLATE_COUNT or len(set(templates)) != WEIGHT_TEMPLATE_COUNT:
        raise ValueError("CAP-ACT M1 requires exactly five unique weight-template IDs")
    for token in (*models, *templates):
        _require_nonempty_token(token, "registry identifier")

    bases = (
        *(BaseAction(BaseOperator.EMIT, model_id) for model_id in models),
        *(BaseAction(BaseOperator.FUSE, template_id) for template_id in templates),
        BaseAction(BaseOperator.FALLBACK),
    )
    actions: list[Action] = [Action(base) for base in bases]
    actions.extend(Action(base, TransformOperator.SHIFT, shift) for base in bases for shift in SHIFT_BINS)
    actions.extend(
        Action(base, TransformOperator.INFLATE, inflation)
        for base in bases
        for inflation in INFLATION_BINS
    )
    result = tuple(actions)
    if len(result) != ACTION_CARDINALITY or len({item.action_hash for item in result}) != ACTION_CARDINALITY:
        raise AssertionError("96-Action construction is not injective")
    return result


def build_primary_action_fixture(
    model_ids: Sequence[str],
    weight_template_ids: Sequence[str],
    champion_base: BaseAction,
) -> tuple[Action, ...]:
    """Build the identifiable primary union for one target/horizon key.

    The union has all twelve untransformed base actions plus the seven
    non-identity corrections of the literal common ``FALLBACK``/N0 action.
    This makes H1 (six EMIT), RF1 (five FUSE), and RC1 (FALLBACK identity plus
    seven corrections) disjoint subsets whose exact union is ACT1.  It is
    deliberately *not* the 96-action compositional ablation.
    """

    compositional = build_action_fixture(model_ids, weight_template_ids)
    bases = tuple(item for item in compositional if item.transform is None)
    if champion_base != BaseAction(BaseOperator.FALLBACK):
        raise ValueError("champion_base must be the literal common FALLBACK action")
    corrections = (
        *(Action(champion_base, TransformOperator.SHIFT, value) for value in SHIFT_BINS),
        *(Action(champion_base, TransformOperator.INFLATE, value) for value in INFLATION_BINS),
    )
    result = (*bases, *corrections)
    if len(result) != PRIMARY_ACTION_CARDINALITY or len({item.action_id for item in result}) != len(result):
        raise AssertionError("primary action construction must contain exactly 19 unique actions")
    return result


def build_if1_predicate_fixture(
    feature_bins: Mapping[str, Sequence[str]],
) -> tuple[dict[str, Any], ...]:
    """Mechanically build the frozen 225 known-condition predicates.

    Five features with three bins yield 15 atoms.  The grammar then contains
    those atoms plus AND/OR over each unordered pair of distinct atoms:
    ``15 + 2*C(15,2) = 225``.  Child order is canonical, so syntactic aliases
    do not inflate the manifest.
    """

    if len(feature_bins) != 5:
        raise ValueError("IF1 requires exactly five frozen features")
    atoms: list[dict[str, Any]] = []
    for feature_id in sorted(feature_bins):
        bins = tuple(sorted(feature_bins[feature_id]))
        if len(bins) != 3 or len(set(bins)) != 3:
            raise ValueError("IF1 requires exactly three unique bins per feature")
        for bin_id in bins:
            _require_nonempty_token(feature_id, "feature_id")
            _require_nonempty_token(bin_id, "bin_id")
            atoms.append({"operator": "ATOM", "feature_id": feature_id, "bin_id": bin_id})
    atoms.sort(key=canonical_bytes)
    predicates: list[dict[str, Any]] = list(atoms)
    for left, right in combinations(atoms, 2):
        children = sorted((left, right), key=canonical_bytes)
        for operator in ("AND", "OR"):
            predicates.append({"operator": operator, "children": children})
    if (
        len(predicates) != IF1_PREDICATE_CARDINALITY
        or len({canonical_sha256(item) for item in predicates}) != IF1_PREDICATE_CARDINALITY
    ):
        raise AssertionError("IF1 predicate construction is not the frozen 225-element set")
    return tuple(predicates)


def build_if1_program_fixture(
    action_ids: Sequence[str],
    predicates: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Materialize 19 unconditional plus 76,950 conditional IF1 programs."""

    actions = tuple(action_ids)
    frozen_predicates = tuple(dict(item) for item in predicates)
    if len(actions) != PRIMARY_ACTION_CARDINALITY or len(set(actions)) != len(actions):
        raise ValueError("IF1 requires exactly 19 unique primary action IDs")
    if len(frozen_predicates) != IF1_PREDICATE_CARDINALITY:
        raise ValueError("IF1 requires exactly 225 frozen predicates")
    # These are the exact per-key response program bodies accepted by the
    # verifier: 19 unconditional choices plus ordered distinct branches for
    # every frozen predicate.  No second syntactic alias is accepted.
    programs: list[dict[str, Any]] = [{"action_id": action_id} for action_id in actions]
    programs.extend(
        {
            "predicate": predicate,
            "true_action_id": true_action,
            "false_action_id": false_action,
        }
        for predicate in frozen_predicates
        for true_action in actions
        for false_action in actions
        if true_action != false_action
    )
    if (
        len(programs) != IF1_SYNTACTIC_CARDINALITY
        or len({canonical_sha256(item) for item in programs}) != IF1_SYNTACTIC_CARDINALITY
    ):
        raise AssertionError("IF1 grammar is not the frozen 76,969-element set")
    return tuple(programs)


# A module-level fixture is useful for schema/hash tests.  Runtime registries
# rebuild it from their own sealed model/template identifiers.
EXACT_96_ACTION_FIXTURE = build_action_fixture()
