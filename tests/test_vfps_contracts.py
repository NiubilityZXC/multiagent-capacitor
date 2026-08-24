from __future__ import annotations

import inspect

import pytest

from experiments.vfps_agent.canonical import (
    ForbiddenProxyError,
    StrictJSONError,
    canonical_json,
    scan_forbidden_proxies,
    strict_json_loads,
)
from experiments.vfps_agent.contracts import (
    ArmId,
    CandidateBundle,
    FROZEN_ARM_SPECS,
    ForecastEstimate,
    ForecastKey,
    OriginPacketV2,
    PacketKind,
    ResponsePermission,
    RevealedObservation,
)


H = "a" * 64


def _estimate() -> ForecastEstimate:
    return ForecastEstimate(
        key=ForecastKey("capacity", 1, "F"),
        point=0.95,
        lower=0.90,
        median=0.95,
        upper=1.00,
    )


def _observation(index: int = 0, *, available_at: float = 10.0) -> RevealedObservation:
    return RevealedObservation(
        event_index=index,
        observed_at=float(index),
        available_at=available_at,
        measurements={"capacity": 1.0 - 0.01 * index},
        missingness={"capacity": False},
    )


@pytest.mark.parametrize(
    "payload",
    [
        '{"a":1,"a":2}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
        '{"x":1e9999}',
    ],
)
def test_strict_json_rejects_duplicate_keys_and_nonfinite(payload: str) -> None:
    with pytest.raises(StrictJSONError):
        strict_json_loads(payload)


def test_canonical_json_is_sorted_and_rejects_constructed_nonfinite() -> None:
    assert canonical_json({"z": 1, "a": [2, 3]}) == '{"a":[2,3],"z":1}'
    with pytest.raises(StrictJSONError):
        canonical_json({"x": float("nan")})


@pytest.mark.parametrize(
    "value",
    [
        {"final_length": 300},
        {"safe": "the future suffix"},
        {"unit_id": "opaque"},
        {"safe": "capacitor-17"},
        {"safe": "/private/raw/device.mat"},
    ],
)
def test_proxy_scan_covers_keys_and_string_values(value: object) -> None:
    with pytest.raises(ForbiddenProxyError):
        scan_forbidden_proxies(value)


def test_origin_packet_signature_cannot_receive_full_series_or_final_length() -> None:
    parameter_names = set(inspect.signature(OriginPacketV2).parameters)
    assert "full_series" not in parameter_names
    assert "final_length" not in parameter_names
    assert "suffix" not in parameter_names


def test_raw_packet_is_past_only_and_rejects_unavailable_observation() -> None:
    caller_owned = {"scale": 1.0}
    packet = OriginPacketV2(
        packet_kind=PacketKind.RAW,
        opaque_origin_hash=H,
        availability_cutoff=10.0,
        forecast_keys=(_estimate().key,),
        revealed_observations=(_observation(),),
        normalization=caller_owned,
    )
    frozen_hash = packet.packet_hash
    caller_owned["scale"] = 999.0
    assert packet.packet_hash == packet.packet_hash
    assert packet.packet_hash == frozen_hash
    with pytest.raises(TypeError):
        packet.normalization["scale"] = 2.0  # type: ignore[index]
    assert b"final_length" not in packet.packet_bytes

    with pytest.raises(ValueError, match="unavailable"):
        OriginPacketV2(
            packet_kind=PacketKind.RAW,
            opaque_origin_hash=H,
            availability_cutoff=9.0,
            forecast_keys=(_estimate().key,),
            revealed_observations=(_observation(available_at=10.0),),
        )


def test_hybrid_packet_binds_candidate_and_all_manifest_hashes() -> None:
    candidate = CandidateBundle(model_id="local-linear", registry_hash=H, estimates=(_estimate(),))
    packet = OriginPacketV2(
        packet_kind=PacketKind.HYBRID,
        opaque_origin_hash="b" * 64,
        availability_cutoff=10.0,
        forecast_keys=(_estimate().key,),
        revealed_observations=(_observation(),),
        candidate_bundles=(candidate,),
        train_error_summaries={"local_linear": {"mae_bin": "low"}},
        diagnostic_bins={"sampling_gap": "short"},
        action_manifest_hash="c" * 64,
        predicate_manifest_hash="d" * 64,
        registry_hash=H,
        fallback_bundle_hash="e" * 64,
    )
    assert packet.packet_kind is PacketKind.HYBRID
    assert candidate.bundle_hash in canonical_json(candidate.bundle_hash)


def test_arm_permissions_are_typed_and_isolated() -> None:
    assert FROZEN_ARM_SPECS[ArmId.D1_RAW].packet_kind is PacketKind.RAW
    assert FROZEN_ARM_SPECS[ArmId.D1_PACKET].packet_kind is PacketKind.HYBRID
    assert FROZEN_ARM_SPECS[ArmId.H1].permission is ResponsePermission.EMIT_ONLY
    assert FROZEN_ARM_SPECS[ArmId.ACT1].permission is ResponsePermission.PRIMARY_ACTION
    assert FROZEN_ARM_SPECS[ArmId.IF1].permission is ResponsePermission.IF_REPRESENTATION
    assert FROZEN_ARM_SPECS[ArmId.N0].physical_calls == 0
