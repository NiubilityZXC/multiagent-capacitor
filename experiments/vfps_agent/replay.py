"""Blind rolling reveal and post-seal maturity services for CAP-ACT M2."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes, canonical_sha256, strict_json_loads, to_primitive
from .contracts import (
    CausalPacketSchema,
    KeyMaturity,
    MaturityState,
    PacketKind,
    RevealedObservation,
    SealedSplitProvenance,
)
from .ledger import (
    CanonicalJSONLLedger,
    LedgerKind,
    read_verified_ledger_records,
    verify_ledger,
)
from .registry import CAPActionRegistry
from .runner import (
    CAPM2Error,
    CAPRunPaths,
    _artifact_hash,
    _read_regular,
    _write_exclusive,
    build_causal_packet,
    verify_durable_checkpoint,
    verify_prediction_phase,
)


@dataclass(frozen=True, slots=True)
class HiddenEvent:
    """One held-out event owned only by the blind event service."""

    event_index: int
    observed_at: float
    available_at: float
    measurements: Mapping[str, Any]
    missingness: Mapping[str, bool]

    def __post_init__(self) -> None:
        # Validate immediately and detach nested mappings from caller-owned
        # dictionaries before the blind service seals its hidden stream.
        snapshot = RevealedObservation(
            event_index=self.event_index,
            observed_at=self.observed_at,
            available_at=self.available_at,
            measurements=self.measurements,
            missingness=self.missingness,
        )
        object.__setattr__(self, "measurements", snapshot.measurements)
        object.__setattr__(self, "missingness", snapshot.missingness)

    def revealed(self) -> RevealedObservation:
        return RevealedObservation(
            event_index=self.event_index,
            observed_at=self.observed_at,
            available_at=self.available_at,
            measurements=self.measurements,
            missingness=self.missingness,
        )

    @property
    def event_hash(self) -> str:
        return canonical_sha256(self.revealed())


def _checkpoint_maps(paths: CAPRunPaths, *, sealed: bool) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    predictions = read_verified_ledger_records(
        paths.prediction,
        expected_kind=LedgerKind.PREDICTION,
        seal_path=paths.seal_path(LedgerKind.PREDICTION) if sealed else None,
    )
    executions = read_verified_ledger_records(
        paths.execution,
        expected_kind=LedgerKind.EXECUTION,
        seal_path=paths.seal_path(LedgerKind.EXECUTION) if sealed else None,
    )
    checkpoints = read_verified_ledger_records(
        paths.checkpoint,
        expected_kind=LedgerKind.CHECKPOINT,
        seal_path=paths.seal_path(LedgerKind.CHECKPOINT) if sealed else None,
    )
    prediction_by_hash = {record["record_hash"]: record for record in predictions}
    execution_by_hash = {record["record_hash"]: record for record in executions}
    checkpoint_by_hash = {record["record_hash"]: record for record in checkpoints}
    return prediction_by_hash, execution_by_hash, checkpoint_by_hash


def _verify_checkpoint_for_reveal(
    *,
    paths: CAPRunPaths,
    checkpoint_record_hash: str,
    expected_origin_index: int,
    expected_origin_hash: str,
    expected_packet_hash: str,
    allowed_policy_hashes: Sequence[str] = (),
) -> dict[str, Any]:
    return verify_durable_checkpoint(
        paths.root,
        checkpoint_record_hash=checkpoint_record_hash,
        expected_origin_index=expected_origin_index,
        expected_origin_hash=expected_origin_hash,
        expected_packet_hash=expected_packet_hash,
        allowed_policy_hashes=allowed_policy_hashes,
    )


class BlindReplayService:
    """Own the complete held-out stream and reveal exactly one event per checkpoint.

    Callers can request only the current prefix or the next single observation.
    No method returns the complete suffix, final length, or termination state.
    """

    def __init__(
        self,
        run_dir: str | os.PathLike[str],
        *,
        events: Sequence[HiddenEvent],
        context: int,
        causal_schema: CausalPacketSchema,
        split: SealedSplitProvenance,
        registry: CAPActionRegistry,
        packet_kind: PacketKind,
        normalization: Mapping[str, Any] | None = None,
        allowed_conditions: Mapping[str, Any] | None = None,
        train_error_summaries: Mapping[str, Any] | None = None,
        diagnostic_bins: Mapping[str, Any] | None = None,
        allowed_policy_hashes: Sequence[str] = (),
        resume: bool = False,
    ) -> None:
        self.paths = CAPRunPaths(Path(run_dir))
        if not self.paths.root.exists() or self.paths.root.is_symlink():
            raise CAPM2Error("CAPAccuracyRun must create the safe run directory first")
        self._events = tuple(events)
        if context < 1 or context >= len(self._events):
            raise CAPM2Error("context must reveal a proper non-empty prefix")
        if tuple(event.event_index for event in self._events) != tuple(range(len(self._events))):
            raise CAPM2Error("hidden events must have consecutive zero-based indices")
        revealed = tuple(event.revealed() for event in self._events)
        observed = tuple(item.observed_at for item in revealed)
        available = tuple(item.available_at for item in revealed)
        if observed != tuple(sorted(observed)) or available != tuple(sorted(available)):
            raise CAPM2Error("hidden event times must be chronological")
        for observation in revealed:
            if set(observation.measurements) != set(causal_schema.measurement_fields):
                raise CAPM2Error("hidden measurements differ from the causal schema")
            if set(observation.missingness) != set(causal_schema.missingness_fields):
                raise CAPM2Error("hidden missingness differs from the causal schema")
        self._context = context
        self._schema = causal_schema
        self._split = split
        self._registry = registry
        self._packet_kind = packet_kind
        self._normalization = dict(normalization or {})
        self._conditions = dict(allowed_conditions or {})
        self._train = dict(train_error_summaries or {})
        self._diagnostics = dict(diagnostic_bins or {})
        self._allowed_policy_hashes = tuple(allowed_policy_hashes)
        self._access = CanonicalJSONLLedger(self.paths.access, LedgerKind.ACCESS, resume=resume)
        self._closed = False
        access_records = read_verified_ledger_records(self.paths.access, expected_kind=LedgerKind.ACCESS)
        if access_records:
            indices = tuple(record["payload"]["revealed_event_index"] for record in access_records)
            if indices != tuple(range(len(indices))):
                self.close()
                raise CAPM2Error("access ledger reveal indices are not a contiguous prefix")
            self._revealed_count = len(indices)
            if self._revealed_count < context:
                self.close()
                raise CAPM2Error("resumed access ledger lacks the frozen bootstrap prefix")
        else:
            self._revealed_count = 0
            for index in range(context):
                event = self._events[index]
                self._access.append_access(
                    {
                        "schema_version": "CAPEventAccess.v1",
                        "phase": "BOOTSTRAP",
                        "revealed_event_index": index,
                        "observation_hash": event.event_hash,
                        "checkpoint_record_hash": None,
                        "commit_id": None,
                    }
                )
                self._revealed_count += 1

    def __enter__(self) -> "BlindReplayService":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @property
    def revealed_count(self) -> int:
        return self._revealed_count

    def current_prefix(self) -> tuple[RevealedObservation, ...]:
        return tuple(event.revealed() for event in self._events[: self._revealed_count])

    def build_current_packet(self) -> Any:
        return self._build_packet_for_origin(self._revealed_count - 1)

    def _build_packet_for_origin(self, origin_event_index: int) -> Any:
        if (
            isinstance(origin_event_index, bool)
            or not isinstance(origin_event_index, int)
            or origin_event_index < 0
            or origin_event_index >= self._revealed_count
        ):
            raise CAPM2Error("packet origin is outside the causally revealed prefix")
        prefix = tuple(
            event.revealed() for event in self._events[: origin_event_index + 1]
        )
        return build_causal_packet(
            packet_kind=self._packet_kind,
            origin_event_index=origin_event_index,
            availability_cutoff=prefix[-1].available_at,
            revealed_observations=prefix,
            causal_schema=self._schema,
            split=self._split,
            registry=self._registry,
            normalization=self._normalization,
            allowed_conditions=self._conditions,
            train_error_summaries=self._train,
            diagnostic_bins=self._diagnostics,
        )

    def reveal_next_after_checkpoint(self, checkpoint_record_hash: str) -> RevealedObservation:
        if self._closed:
            raise CAPM2Error("blind event service is closed")
        access_records = read_verified_ledger_records(
            self.paths.access, expected_kind=LedgerKind.ACCESS
        )
        used = {
            record["payload"].get("checkpoint_record_hash"): record
            for record in access_records
            if record["payload"].get("checkpoint_record_hash") is not None
        }
        if checkpoint_record_hash in used:
            # Transport retry (including crash after ACCESS fsync but before
            # reply) is idempotent: re-verify the full durable prediction chain
            # and return exactly the already committed observation without a
            # second ACCESS append or reveal-count change.
            access_payload = used[checkpoint_record_hash]["payload"]
            event_index = access_payload["revealed_event_index"]
            origin_index = event_index - 1
            packet = self._build_packet_for_origin(origin_index)
            checkpoint_record = _verify_checkpoint_for_reveal(
                paths=self.paths,
                checkpoint_record_hash=checkpoint_record_hash,
                expected_origin_index=origin_index,
                expected_origin_hash=packet.opaque_origin_hash,
                expected_packet_hash=packet.packet_hash,
                allowed_policy_hashes=self._allowed_policy_hashes,
            )
            event = self._events[event_index]
            if (
                event.event_hash != access_payload["observation_hash"]
                or checkpoint_record["payload"]["commit_id"] != access_payload["commit_id"]
            ):
                raise CAPM2Error("idempotent reveal differs from durable ACCESS evidence")
            return event.revealed()
        if self._revealed_count >= len(self._events):
            raise CAPM2Error("held-out stream has ended")
        origin_index = self._revealed_count - 1
        packet = self._build_packet_for_origin(origin_index)
        checkpoint_record = _verify_checkpoint_for_reveal(
            paths=self.paths,
            checkpoint_record_hash=checkpoint_record_hash,
            expected_origin_index=origin_index,
            expected_origin_hash=packet.opaque_origin_hash,
            expected_packet_hash=packet.packet_hash,
            allowed_policy_hashes=self._allowed_policy_hashes,
        )
        event = self._events[self._revealed_count]
        if event.event_index != origin_index + 1:
            raise CAPM2Error("next revealed event is not origin+1")
        self._access.append_access(
            {
                "schema_version": "CAPEventAccess.v1",
                "phase": "POST_COMMIT",
                "revealed_event_index": event.event_index,
                "observation_hash": event.event_hash,
                "checkpoint_record_hash": checkpoint_record_hash,
                "commit_id": checkpoint_record["payload"]["commit_id"],
            }
        )
        self._revealed_count += 1
        return event.revealed()

    def seal_access_and_mature(self) -> str:
        """Seal all prediction evidence, then let the label service write truth."""

        if self._closed:
            raise CAPM2Error("blind event service is closed")
        # This is a strict pre-write barrier.  In particular, never create a
        # maturity artifact containing a hidden suffix label and only later
        # discover through verify_complete_run that the label was not revealed.
        if self._revealed_count != len(self._events):
            raise CAPM2Error("complete replay is required before maturity evaluation")
        prediction_report = verify_prediction_phase(self.paths.root)
        prewrite_barrier = verify_access_barrier(
            self.paths.root,
            context=self._context,
            require_access_seal=False,
        )
        if (
            prewrite_barrier["revealed_count"] != len(self._events)
            or prewrite_barrier["post_commit_reveal_count"]
            != len(self._events) - self._context
        ):
            raise CAPM2Error("pre-write access barrier does not cover the complete hidden stream")
        self._access.seal(self.paths.seal_path(LedgerKind.ACCESS))
        self._access.close()
        verify_access_barrier(self.paths.root, context=self._context)

        maturity = CanonicalJSONLLedger(self.paths.maturity, LedgerKind.MATURITY)
        execution_records = read_verified_ledger_records(
            self.paths.execution,
            expected_kind=LedgerKind.EXECUTION,
            seal_path=self.paths.seal_path(LedgerKind.EXECUTION),
        )
        checkpoint_records = read_verified_ledger_records(
            self.paths.checkpoint,
            expected_kind=LedgerKind.CHECKPOINT,
            seal_path=self.paths.seal_path(LedgerKind.CHECKPOINT),
        )
        origin_by_commit = {
            record["payload"]["commit_id"]: record["payload"]["origin_event_index"]
            for record in checkpoint_records
        }
        key_map = {key.token: key for key in self._registry.numerical.planned_keys}
        for execution_record in execution_records:
            payload = execution_record["payload"]
            commit_id = payload["commit_id"]
            item = payload["key_execution"]
            key_token = item["key_token"]
            key = key_map[key_token]
            label_event_index = origin_by_commit[commit_id] + key.horizon
            matured = False
            label_payload: dict[str, Any] | None = None
            if label_event_index < len(self._events) and key.target in self._events[label_event_index].measurements:
                event = self._events[label_event_index]
                missing = bool(event.missingness.get(key.target, True))
                value = event.measurements[key.target]
                if not missing and isinstance(value, (int, float)) and not isinstance(value, bool):
                    label_payload = {
                        "target": key.target,
                        "unit": key.unit,
                        "event_index": label_event_index,
                        "observed_value": float(value),
                    }
                    matured = True
            label_hash = canonical_sha256(label_payload) if label_payload is not None else None
            key_maturity = KeyMaturity(
                key_token=key_token,
                maturity_state=MaturityState.MATURED if matured else MaturityState.NEVER_MATURED,
                execution_record_hash=execution_record["record_hash"],
                label_hash=label_hash,
            )
            record_payload: dict[str, Any] = {
                "schema_version": "CAPKeyMaturityRecord.v1",
                "commit_id": commit_id,
                "label_event_index": label_event_index,
                "key_maturity": to_primitive(key_maturity),
                "label": label_payload,
            }
            maturity.append_maturity(record_payload)
        maturity.seal(self.paths.seal_path(LedgerKind.MATURITY))
        maturity.close()
        complete_report = verify_complete_run(self.paths.root, context=self._context, require_final_seal=False)
        body = {
            "schema_version": "CAPCompleteRunSeal.v1",
            "prediction_phase_seal_hash": prediction_report["phase_seal_hash"],
            "access_ledger_sha256": _artifact_hash(self.paths.access),
            "access_seal_sha256": _artifact_hash(self.paths.seal_path(LedgerKind.ACCESS)),
            "maturity_ledger_sha256": _artifact_hash(self.paths.maturity),
            "maturity_seal_sha256": _artifact_hash(self.paths.seal_path(LedgerKind.MATURITY)),
            "barrier_hash": complete_report["barrier_hash"],
            "maturity_count": complete_report["maturity_count"],
        }
        final = dict(body)
        final["run_seal_hash"] = canonical_sha256(body)
        _write_exclusive(self.paths.final_run_seal, final)
        self._closed = True
        verify_complete_run(self.paths.root, context=self._context)
        return final["run_seal_hash"]

    def close(self) -> None:
        if self._closed:
            return
        self._access.close()
        self._closed = True


def verify_access_barrier(
    run_dir: str | os.PathLike[str],
    *,
    context: int,
    require_access_seal: bool = True,
) -> dict[str, Any]:
    paths = CAPRunPaths(Path(run_dir))
    access = read_verified_ledger_records(
        paths.access,
        expected_kind=LedgerKind.ACCESS,
        seal_path=paths.seal_path(LedgerKind.ACCESS) if require_access_seal else None,
    )
    prediction_by_hash, execution_by_hash, checkpoint_by_hash = _checkpoint_maps(paths, sealed=True)
    used_checkpoints: set[str] = set()
    for index, record in enumerate(access):
        payload = record["payload"]
        if payload["revealed_event_index"] != index:
            raise CAPM2Error("access ledger is not a contiguous reveal sequence")
        if index < context:
            if (
                payload["phase"] != "BOOTSTRAP"
                or payload["checkpoint_record_hash"] is not None
                or payload["commit_id"] is not None
            ):
                raise CAPM2Error("bootstrap access must not claim a prediction checkpoint")
            continue
        checkpoint_hash = payload["checkpoint_record_hash"]
        if payload["phase"] != "POST_COMMIT" or checkpoint_hash in used_checkpoints:
            raise CAPM2Error("post-commit access must use one new checkpoint")
        try:
            checkpoint = checkpoint_by_hash[checkpoint_hash]["payload"]
        except KeyError as exc:
            raise CAPM2Error("access ledger references an unknown checkpoint") from exc
        if (
            checkpoint["origin_event_index"] + 1 != index
            or checkpoint["commit_id"] != payload["commit_id"]
            or checkpoint["prediction_record_hash"] not in prediction_by_hash
        ):
            raise CAPM2Error("access reveal was not authorized by the preceding committed origin")
        for item in checkpoint["execution_record_hashes"]:
            if item["record_hash"] not in execution_by_hash:
                raise CAPM2Error("access checkpoint references missing execution evidence")
        used_checkpoints.add(checkpoint_hash)
    body = {
        "schema_version": "CAPAccessBarrierReport.v1",
        "context": context,
        "access_record_hashes": [record["record_hash"] for record in access],
        "used_checkpoint_hashes": sorted(used_checkpoints),
    }
    return {
        "status": "PASS",
        "revealed_count": len(access),
        "post_commit_reveal_count": len(used_checkpoints),
        "barrier_hash": canonical_sha256(body),
    }


def verify_complete_run(
    run_dir: str | os.PathLike[str],
    *,
    context: int,
    require_final_seal: bool = True,
) -> dict[str, Any]:
    paths = CAPRunPaths(Path(run_dir))
    prediction = verify_prediction_phase(paths.root)
    barrier = verify_access_barrier(paths.root, context=context)
    maturity = read_verified_ledger_records(
        paths.maturity,
        expected_kind=LedgerKind.MATURITY,
        seal_path=paths.seal_path(LedgerKind.MATURITY),
    )
    execution = read_verified_ledger_records(
        paths.execution,
        expected_kind=LedgerKind.EXECUTION,
        seal_path=paths.seal_path(LedgerKind.EXECUTION),
    )
    execution_by_key = {
        (record["payload"]["commit_id"], record["payload"]["key_execution"]["key_token"]): record
        for record in execution
    }
    maturity_by_key = {
        (record["payload"]["commit_id"], record["payload"]["key_maturity"]["key_token"]): record
        for record in maturity
    }
    if set(execution_by_key) != set(maturity_by_key):
        raise CAPM2Error("planned execution and maturity key sets differ")
    revealed_indices = {
        record["payload"]["revealed_event_index"]
        for record in read_verified_ledger_records(
            paths.access,
            expected_kind=LedgerKind.ACCESS,
            seal_path=paths.seal_path(LedgerKind.ACCESS),
        )
    }
    matured_count = 0
    never_count = 0
    for key, maturity_record in maturity_by_key.items():
        execution_record = execution_by_key[key]
        payload = maturity_record["payload"]
        item = payload["key_maturity"]
        if item["execution_record_hash"] != execution_record["record_hash"]:
            raise CAPM2Error("maturity row references the wrong execution record")
        if item["maturity_state"] == MaturityState.MATURED.value:
            label = payload["label"]
            if (
                not isinstance(label, dict)
                or canonical_sha256(label) != item["label_hash"]
                or payload["label_event_index"] not in revealed_indices
            ):
                raise CAPM2Error("matured label is unbound or was never causally revealed")
            matured_count += 1
        else:
            if payload["label"] is not None or item["label_hash"] is not None:
                raise CAPM2Error("NEVER_MATURED row contains a fabricated label")
            never_count += 1
    report = {
        "status": "PASS",
        "prediction_count": prediction["prediction_count"],
        "execution_count": len(execution),
        "maturity_count": len(maturity),
        "matured_count": matured_count,
        "never_matured_count": never_count,
        "barrier_hash": barrier["barrier_hash"],
    }
    if require_final_seal:
        raw = _read_regular(paths.final_run_seal)
        final = strict_json_loads(raw)
        if not isinstance(final, dict) or canonical_bytes(final) != raw:
            raise CAPM2Error("final run seal is not canonical")
        body = {key: value for key, value in final.items() if key != "run_seal_hash"}
        if (
            set(final) != {
                "schema_version", "prediction_phase_seal_hash", "access_ledger_sha256",
                "access_seal_sha256", "maturity_ledger_sha256", "maturity_seal_sha256",
                "barrier_hash", "maturity_count", "run_seal_hash",
            }
            or final["schema_version"] != "CAPCompleteRunSeal.v1"
            or final["run_seal_hash"] != canonical_sha256(body)
            or final["prediction_phase_seal_hash"] != prediction["phase_seal_hash"]
            or final["access_ledger_sha256"] != _artifact_hash(paths.access)
            or final["access_seal_sha256"] != _artifact_hash(paths.seal_path(LedgerKind.ACCESS))
            or final["maturity_ledger_sha256"] != _artifact_hash(paths.maturity)
            or final["maturity_seal_sha256"] != _artifact_hash(paths.seal_path(LedgerKind.MATURITY))
            or final["barrier_hash"] != barrier["barrier_hash"]
            or final["maturity_count"] != len(maturity)
        ):
            raise CAPM2Error("final run seal does not bind the complete replay")
        report["run_seal_hash"] = final["run_seal_hash"]
    return report
