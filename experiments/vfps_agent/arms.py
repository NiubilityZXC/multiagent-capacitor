"""Arm-specific CAP-ACT M1 permissions and all-or-fallback execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .actions import (
    ACTION_CARDINALITY,
    IF1_ORIGIN_SPECIFIC_QUOTIENT,
    PRIMARY_ACTION_CARDINALITY,
    RC1_ACTION_CARDINALITY,
)
from .contracts import ArmId as CAPArmId, CommitDisposition, PacketKind
from .registry import CAPActionRegistry, ForecastBundle
from .verifier import (
    ActionAuthority,
    VerificationCertificate,
    VerificationError,
    parse_direct_bundle,
    verify_and_execute_actions,
    verify_and_execute_if_representation,
)


class CAPResponsePermission(str, Enum):
    NONE = "none"
    DIRECT_BUNDLE = "direct_bundle"
    EMIT_ONLY = "emit_only"
    FUSE_ONLY = "fuse_only"
    CHAMPION_CORRECTION = "champion_correction"
    PRIMARY_ACTION = "primary_action"
    IF_REPRESENTATION = "if_representation"
    COMPOSITIONAL_ACTION = "compositional_action"


@dataclass(frozen=True, slots=True)
class CAPArmSpec:
    arm_id: CAPArmId
    packet_kind: PacketKind | None
    response_permission: CAPResponsePermission
    physical_calls: int
    action_cardinality: int | None = None
    representation_only: bool = False
    origin_specific_quotient: int | None = None

    def __post_init__(self) -> None:
        if self.physical_calls not in (0, 1):
            raise ValueError("CAP-ACT M1 primary arms permit zero or one physical call")
        if self.representation_only and self.arm_id is not CAPArmId.IF1:
            raise ValueError("only IF1 is a representation-only arm")


FROZEN_CAP_ARM_SPECS: Mapping[CAPArmId, CAPArmSpec] = MappingProxyType(
    {
        CAPArmId.N0: CAPArmSpec(CAPArmId.N0, None, CAPResponsePermission.NONE, 0),
        CAPArmId.D1_RAW: CAPArmSpec(
            CAPArmId.D1_RAW,
            PacketKind.RAW,
            CAPResponsePermission.DIRECT_BUNDLE,
            1,
        ),
        CAPArmId.D1_PACKET: CAPArmSpec(
            CAPArmId.D1_PACKET,
            PacketKind.HYBRID,
            CAPResponsePermission.DIRECT_BUNDLE,
            1,
        ),
        CAPArmId.H1: CAPArmSpec(
            CAPArmId.H1,
            PacketKind.HYBRID,
            CAPResponsePermission.EMIT_ONLY,
            1,
            action_cardinality=6,
        ),
        CAPArmId.RF1: CAPArmSpec(
            CAPArmId.RF1,
            PacketKind.HYBRID,
            CAPResponsePermission.FUSE_ONLY,
            1,
            action_cardinality=5,
        ),
        CAPArmId.RC1: CAPArmSpec(
            CAPArmId.RC1,
            PacketKind.HYBRID,
            CAPResponsePermission.CHAMPION_CORRECTION,
            1,
            action_cardinality=RC1_ACTION_CARDINALITY,
        ),
        CAPArmId.ACT1: CAPArmSpec(
            CAPArmId.ACT1,
            PacketKind.HYBRID,
            CAPResponsePermission.PRIMARY_ACTION,
            1,
            action_cardinality=PRIMARY_ACTION_CARDINALITY,
        ),
        CAPArmId.IF1: CAPArmSpec(
            CAPArmId.IF1,
            PacketKind.HYBRID,
            CAPResponsePermission.IF_REPRESENTATION,
            1,
            action_cardinality=PRIMARY_ACTION_CARDINALITY,
            representation_only=True,
            origin_specific_quotient=IF1_ORIGIN_SPECIFIC_QUOTIENT,
        ),
        CAPArmId.ACT_COMP96: CAPArmSpec(
            CAPArmId.ACT_COMP96,
            PacketKind.HYBRID,
            CAPResponsePermission.COMPOSITIONAL_ACTION,
            1,
            action_cardinality=ACTION_CARDINALITY,
        ),
    }
)


@dataclass(frozen=True, slots=True)
class ArmExecution:
    arm_id: CAPArmId
    disposition: CommitDisposition
    bundle: ForecastBundle
    reason_code: str
    certificate: VerificationCertificate | None = None
    selected_abstention: bool = False
    error_fallback: bool = False

    @property
    def fallback_used(self) -> bool:
        return self.disposition is CommitDisposition.FALLBACK

    @property
    def prediction_hash(self) -> str:
        return self.bundle.bundle_hash


_ACTION_AUTHORITY = {
    CAPArmId.H1: ActionAuthority.H1,
    CAPArmId.RF1: ActionAuthority.RF1,
    CAPArmId.RC1: ActionAuthority.RC1,
    CAPArmId.ACT1: ActionAuthority.ACT1,
    CAPArmId.ACT_COMP96: ActionAuthority.ACT_COMP96,
}


def _fallback(arm_id: CAPArmId, registry: CAPActionRegistry, reason_code: str) -> ArmExecution:
    # Return the exact sealed object.  No failed arm is allowed to patch,
    # partially retain, re-tag, or reconstruct a different fallback bundle.
    return ArmExecution(
        arm_id=arm_id,
        disposition=CommitDisposition.FALLBACK,
        bundle=registry.numerical.fallback_bundle,
        reason_code=reason_code,
        selected_abstention=False,
        error_fallback=True,
    )


def execute_arm(
    arm_id: CAPArmId,
    response_payload: str | bytes | bytearray | Mapping[str, Any] | None,
    *,
    registry: CAPActionRegistry,
    feature_bins: Mapping[str, str] | None = None,
) -> ArmExecution:
    """Execute one frozen arm; every verifier failure returns exact fallback."""

    if arm_id not in FROZEN_CAP_ARM_SPECS:
        raise ValueError("unknown CAP-ACT arm")
    if arm_id is CAPArmId.N0:
        if response_payload is not None:
            return _fallback(arm_id, registry, "UNAUTHORIZED_RESPONSE")
        return ArmExecution(
            arm_id=arm_id,
            disposition=CommitDisposition.PREDICTION,
            bundle=registry.numerical.fallback_bundle,
            reason_code="NUMERICAL_CHAMPION",
        )
    if response_payload is None:
        return _fallback(arm_id, registry, "MISSING_RESPONSE")

    try:
        if arm_id in {CAPArmId.D1_RAW, CAPArmId.D1_PACKET}:
            verified = parse_direct_bundle(response_payload, registry=registry)
        elif arm_id is CAPArmId.IF1:
            if feature_bins is None:
                raise VerificationError("IF1 requires the committed packet feature bins")
            verified = verify_and_execute_if_representation(
                response_payload,
                feature_bins=feature_bins,
                registry=registry,
            )
        else:
            verified = verify_and_execute_actions(
                response_payload,
                authority=_ACTION_AUTHORITY[arm_id],
                registry=registry,
            )
    except Exception:
        # Parser details or response content are not copied into public result
        # records.  The same complete fallback is used for every failure mode.
        return _fallback(arm_id, registry, "INVALID_OR_UNAUTHORIZED_RESPONSE")
    return ArmExecution(
        arm_id=arm_id,
        disposition=CommitDisposition.PREDICTION,
        bundle=verified.bundle,
        reason_code="VERIFIED_RESPONSE",
        certificate=verified.certificate,
        selected_abstention=verified.selected_abstention,
        error_fallback=False,
    )
