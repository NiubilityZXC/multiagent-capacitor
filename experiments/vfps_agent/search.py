"""Deterministic, label-blind online selection from a sealed loss table.

``ENUM-ACTION`` exhausts the identifiable 19-action primary space.
``ENUM-COMP96`` is an explicitly named compositional ablation that exhausts all
96 actions.  Neither selector receives an origin label at prediction time.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import statistics
from typing import Any, Mapping, Sequence

from .actions import ACTION_CARDINALITY, PRIMARY_ACTION_CARDINALITY, Action, ActionSpace
from .canonical import canonical_sha256, to_primitive
from .contracts import LabelScope, OriginPacketV2, SealedSplitProvenance
from .registry import CAPActionRegistry


class SearchError(ValueError):
    """The sealed table or frozen search policy is incomplete or inconsistent."""


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SearchError(f"{label} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise SearchError(f"{label} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class LossRecord:
    key_token: str
    action_id: str
    cluster_hash: str
    stratum: str
    loss: float

    def __post_init__(self) -> None:
        for name in ("key_token", "stratum"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise SearchError(f"{name} must be non-empty")
        for name in ("action_id", "cluster_hash"):
            if _SHA256_RE.fullmatch(getattr(self, name, "")) is None:
                raise SearchError(f"{name} must be a lowercase SHA-256 digest")
        value = _finite(self.loss, "development loss")
        if value < 0.0:
            raise SearchError("development loss cannot be negative")
        object.__setattr__(self, "loss", value)

    def payload(self) -> dict[str, Any]:
        return {
            "key": self.key_token,
            "action_id": self.action_id,
            "cluster_hash": self.cluster_hash,
            "stratum": self.stratum,
            "loss": self.loss,
        }


def _table_body(
    records: Sequence[LossRecord],
    *,
    loss_name: str,
    feature_registry_hash: str,
    action_manifest_hash: str,
    action_space: ActionSpace,
    outer_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body = {
        "schema_version": "CAPSealedDevelopmentLossTable.v1",
        "loss_name": loss_name,
        "feature_registry_hash": feature_registry_hash,
        "action_manifest_hash": action_manifest_hash,
        "action_space": action_space.value,
        "records": [item.payload() for item in records],
    }
    if outer_binding is not None:
        body["outer_binding"] = dict(outer_binding)
    return body


@dataclass(frozen=True, slots=True)
class SealedDevelopmentLossTable:
    records: tuple[LossRecord, ...]
    loss_name: str
    feature_registry_hash: str
    action_manifest_hash: str
    action_space: ActionSpace
    seal_hash: str
    outer_fold_hash: str | None = None
    outer_train_set_hash: str | None = None
    held_out_member_hash: str | None = None
    crossfit_manifest_hash: str | None = None
    additive_loss_spec_hash: str | None = None
    label_scope: LabelScope | None = None

    def __post_init__(self) -> None:
        frozen = tuple(self.records)
        object.__setattr__(self, "records", frozen)
        if (
            not frozen
            or not self.loss_name
            or not self.feature_registry_hash
            or not self.action_manifest_hash
            or not isinstance(self.action_space, ActionSpace)
        ):
            raise SearchError("sealed loss table metadata and records are required")
        for name in ("feature_registry_hash", "action_manifest_hash", "seal_hash"):
            if _SHA256_RE.fullmatch(getattr(self, name, "")) is None:
                raise SearchError(f"{name} must be a lowercase SHA-256 digest")
        binding_values = (
            self.outer_fold_hash,
            self.outer_train_set_hash,
            self.held_out_member_hash,
            self.crossfit_manifest_hash,
            self.additive_loss_spec_hash,
            self.label_scope,
        )
        if any(value is not None for value in binding_values):
            if any(value is None for value in binding_values):
                raise SearchError("formal outer binding must be complete")
            for name in (
                "outer_fold_hash",
                "outer_train_set_hash",
                "held_out_member_hash",
                "crossfit_manifest_hash",
                "additive_loss_spec_hash",
            ):
                if _SHA256_RE.fullmatch(getattr(self, name) or "") is None:
                    raise SearchError(f"{name} must be a lowercase SHA-256 digest")
            if self.outer_train_set_hash == self.held_out_member_hash:
                raise SearchError("outer training and held-out bindings must be disjoint")
            if self.label_scope is not LabelScope.OUTER_TRAIN_CROSSFIT:
                raise SearchError("formal ENUM labels must be outer-training cross-fit only")
        canonical_order = tuple(
            sorted(
                frozen,
                key=lambda item: (
                    item.key_token,
                    item.action_id,
                    item.stratum,
                    item.cluster_hash,
                    item.loss,
                ),
            )
        )
        if frozen != canonical_order:
            raise SearchError("sealed loss records must be in canonical order")
        record_keys = tuple(
            (item.key_token, item.action_id, item.cluster_hash, item.stratum)
            for item in frozen
        )
        if len(record_keys) != len(set(record_keys)):
            raise SearchError("unit-level loss table contains a duplicate record key")
        expected = canonical_sha256(
            _table_body(
                frozen,
                loss_name=self.loss_name,
                feature_registry_hash=self.feature_registry_hash,
                action_manifest_hash=self.action_manifest_hash,
                action_space=self.action_space,
                outer_binding=self.outer_binding,
            )
        )
        if self.seal_hash != expected:
            raise SearchError("development loss table seal does not match its contents")

    @classmethod
    def seal(
        cls,
        records: Sequence[LossRecord],
        *,
        loss_name: str,
        feature_registry_hash: str,
        action_manifest_hash: str,
        action_space: ActionSpace,
    ) -> "SealedDevelopmentLossTable":
        frozen = tuple(
            sorted(
                tuple(records),
                key=lambda item: (
                    item.key_token,
                    item.action_id,
                    item.stratum,
                    item.cluster_hash,
                    item.loss,
                ),
            )
        )
        seal_hash = canonical_sha256(
            _table_body(
                frozen,
                loss_name=loss_name,
                feature_registry_hash=feature_registry_hash,
                action_manifest_hash=action_manifest_hash,
                action_space=action_space,
            )
        )
        return cls(
            frozen,
            loss_name,
            feature_registry_hash,
            action_manifest_hash,
            action_space,
            seal_hash,
        )

    @classmethod
    def seal_outer_bound(
        cls,
        records: Sequence[LossRecord],
        *,
        loss_name: str,
        feature_registry_hash: str,
        action_manifest_hash: str,
        action_space: ActionSpace,
        split: SealedSplitProvenance,
    ) -> "SealedDevelopmentLossTable":
        frozen = tuple(
            sorted(
                tuple(records),
                key=lambda item: (
                    item.key_token,
                    item.action_id,
                    item.stratum,
                    item.cluster_hash,
                    item.loss,
                ),
            )
        )
        binding = {
            "outer_fold_hash": split.outer_fold_hash,
            "outer_train_set_hash": split.outer_train_set_hash,
            "held_out_member_hash": split.held_out_member_hash,
            "crossfit_manifest_hash": split.crossfit_manifest_hash,
            "additive_loss_spec_hash": split.additive_loss_spec_hash,
            "label_scope": LabelScope.OUTER_TRAIN_CROSSFIT.value,
        }
        seal_hash = canonical_sha256(
            _table_body(
                frozen,
                loss_name=loss_name,
                feature_registry_hash=feature_registry_hash,
                action_manifest_hash=action_manifest_hash,
                action_space=action_space,
                outer_binding=binding,
            )
        )
        return cls(
            frozen,
            loss_name,
            feature_registry_hash,
            action_manifest_hash,
            action_space,
            seal_hash,
            split.outer_fold_hash,
            split.outer_train_set_hash,
            split.held_out_member_hash,
            split.crossfit_manifest_hash,
            split.additive_loss_spec_hash,
            LabelScope.OUTER_TRAIN_CROSSFIT,
        )

    @property
    def outer_binding(self) -> dict[str, Any] | None:
        if self.outer_fold_hash is None:
            return None
        return {
            "outer_fold_hash": self.outer_fold_hash,
            "outer_train_set_hash": self.outer_train_set_hash,
            "held_out_member_hash": self.held_out_member_hash,
            "crossfit_manifest_hash": self.crossfit_manifest_hash,
            "additive_loss_spec_hash": self.additive_loss_spec_hash,
            "label_scope": self.label_scope.value if self.label_scope is not None else None,
        }

    def verify(self) -> None:
        expected = canonical_sha256(
            _table_body(
                self.records,
                loss_name=self.loss_name,
                feature_registry_hash=self.feature_registry_hash,
                action_manifest_hash=self.action_manifest_hash,
                action_space=self.action_space,
                outer_binding=self.outer_binding,
            )
        )
        if expected != self.seal_hash:
            raise SearchError("development loss table was modified after sealing")


@dataclass(frozen=True, slots=True)
class EnumSearchConfig:
    n_min: int
    lambda_z: float
    kappa: float
    eta: float

    def __post_init__(self) -> None:
        if isinstance(self.n_min, bool) or not isinstance(self.n_min, int) or self.n_min < 1:
            raise SearchError("n_min must be a positive independent-cluster count")
        for name in ("lambda_z", "kappa", "eta"):
            value = _finite(getattr(self, name), name)
            if value < 0.0:
                raise SearchError(f"{name} cannot be negative")
            object.__setattr__(self, name, value)

    @property
    def config_hash(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class ActionScore:
    action_id: str
    score: float
    global_mean: float
    stratum_mean: float | None
    chosen_cluster_se: float
    complexity: int
    independent_global_clusters: int
    independent_stratum_clusters: int
    stratum_unqualified: bool


@dataclass(frozen=True, slots=True)
class EnumSelection:
    policy_name: str
    key_token: str
    context_stratum: str
    action: Action
    selected_score: float
    stratum_unqualified: bool
    evaluated_action_count: int
    loss_table_seal_hash: str
    search_config_hash: str
    scores: tuple[ActionScore, ...]


def _cluster_means(records: Sequence[LossRecord]) -> dict[str, float]:
    by_cluster: dict[str, list[float]] = {}
    for record in records:
        by_cluster.setdefault(record.cluster_hash, []).append(record.loss)
    return {
        cluster: math.fsum(values) / len(values)
        for cluster, values in by_cluster.items()
    }


def _mean_and_cluster_se(records: Sequence[LossRecord]) -> tuple[float, float, int, frozenset[str]]:
    cluster_means = _cluster_means(records)
    if not cluster_means:
        raise SearchError("an enumerated action has no development records")
    values = tuple(cluster_means.values())
    mean = math.fsum(values) / len(values)
    se = statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return mean, se, len(values), frozenset(cluster_means)


def enumerate_action(
    *,
    table: SealedDevelopmentLossTable,
    registry: CAPActionRegistry,
    key_token: str,
    context_stratum: str,
    config: EnumSearchConfig,
    action_space: ActionSpace = ActionSpace.PRIMARY19,
) -> EnumSelection:
    """Exhaust every action, then apply the frozen score and exact tie rule."""

    if not isinstance(table, SealedDevelopmentLossTable):
        raise SearchError("ENUM requires a SealedDevelopmentLossTable")
    table.verify()
    if table.feature_registry_hash != registry.features.feature_registry_hash:
        raise SearchError("loss table feature hash differs from the frozen online registry")
    if table.action_manifest_hash != registry.action_manifest_hash:
        raise SearchError("loss table action hash differs from the frozen online registry")
    if table.action_space is not action_space:
        raise SearchError("loss table was sealed for a different action space")
    if not isinstance(context_stratum, str) or not context_stratum:
        raise SearchError("context stratum must be a frozen non-empty token")
    actions = registry.actions_for(key_token, action_space)
    expected_count = len(actions)
    allowed_counts = (
        {1, PRIMARY_ACTION_CARDINALITY}
        if action_space is ActionSpace.PRIMARY19
        else {1, ACTION_CARDINALITY}
    )
    if expected_count not in allowed_counts:
        raise SearchError("selected action space cardinality differs from protocol")

    key_rows = tuple(record for record in table.records if record.key_token == key_token)
    if not key_rows:
        raise SearchError("sealed table has no records for the requested key")
    action_ids = {item.action_id for item in actions}
    if any(record.action_id not in action_ids for record in key_rows):
        # A primary table and a compositional table are separate protocol
        # artifacts; silently ignoring extra action labels is prohibited.
        raise SearchError("loss table contains actions outside the selected protocol space")

    score_rows: list[ActionScore] = []
    reference_global_clusters: frozenset[str] | None = None
    reference_stratum_clusters: frozenset[str] | None = None
    for action in actions:
        rows = tuple(record for record in key_rows if record.action_id == action.action_id)
        global_mean, global_se, global_n, global_clusters = _mean_and_cluster_se(rows)
        if reference_global_clusters is None:
            reference_global_clusters = global_clusters
        elif global_clusters != reference_global_clusters:
            raise SearchError("actions were not scored on the same independent global clusters")

        stratum_rows = tuple(record for record in rows if record.stratum == context_stratum)
        if stratum_rows:
            stratum_mean, stratum_se, stratum_n, stratum_clusters = _mean_and_cluster_se(stratum_rows)
        else:
            stratum_mean, stratum_se, stratum_n, stratum_clusters = (None, 0.0, 0, frozenset())
        if reference_stratum_clusters is None:
            reference_stratum_clusters = stratum_clusters
        elif stratum_clusters != reference_stratum_clusters:
            raise SearchError("actions were not scored on the same independent stratum clusters")

        unqualified = stratum_n < config.n_min
        if unqualified:
            score = global_mean + config.kappa * global_se + config.eta * action.complexity
            chosen_se = global_se
        else:
            assert stratum_mean is not None
            score = (
                global_mean
                + config.lambda_z * (stratum_mean - global_mean)
                + config.kappa * stratum_se
                + config.eta * action.complexity
            )
            chosen_se = stratum_se
        score_rows.append(
            ActionScore(
                action_id=action.action_id,
                score=score,
                global_mean=global_mean,
                stratum_mean=stratum_mean,
                chosen_cluster_se=chosen_se,
                complexity=action.complexity,
                independent_global_clusters=global_n,
                independent_stratum_clusters=stratum_n,
                stratum_unqualified=unqualified,
            )
        )

    by_id = {item.action_id: item for item in actions}
    winner = min(score_rows, key=lambda item: (item.score, item.complexity, item.action_id))
    return EnumSelection(
        policy_name="ENUM-ACTION" if action_space is ActionSpace.PRIMARY19 else "ENUM-COMP96",
        key_token=key_token,
        context_stratum=context_stratum,
        action=by_id[winner.action_id],
        selected_score=winner.score,
        stratum_unqualified=winner.stratum_unqualified,
        evaluated_action_count=len(score_rows),
        loss_table_seal_hash=table.seal_hash,
        search_config_hash=config.config_hash,
        scores=tuple(score_rows),
    )


# Explicit descriptive alias used by protocol documents.
select_enum_action = enumerate_action


def packet_context_stratum(packet: OriginPacketV2) -> str:
    """Derive the only formal ENUM stratum from a committed causal packet."""

    if packet.packet_context_hash is None:
        raise SearchError("formal context requires an M2-bound packet")
    return canonical_sha256(
        {
            "packet_context_hash": packet.packet_context_hash,
            "diagnostic_bins": to_primitive(packet.diagnostic_bins),
        }
    )


def enumerate_action_outer_bound(
    *,
    table: SealedDevelopmentLossTable,
    registry: CAPActionRegistry,
    packet: OriginPacketV2,
    key_token: str,
    config: EnumSearchConfig,
    action_space: ActionSpace = ActionSpace.PRIMARY19,
) -> EnumSelection:
    """Formal ENUM entry point; unbound tables and free strata are rejected."""

    expected = {
        "outer_fold_hash": packet.outer_fold_hash,
        "outer_train_set_hash": packet.outer_train_set_hash,
        "held_out_member_hash": packet.held_out_member_hash,
        "crossfit_manifest_hash": packet.crossfit_manifest_hash,
        "additive_loss_spec_hash": packet.additive_loss_spec_hash,
        "label_scope": LabelScope.OUTER_TRAIN_CROSSFIT.value,
    }
    if table.outer_binding != expected:
        raise SearchError("ENUM table is not bound to this outer-training cross-fit packet")
    return enumerate_action(
        table=table,
        registry=registry,
        key_token=key_token,
        context_stratum=packet_context_stratum(packet),
        config=config,
        action_space=action_space,
    )
