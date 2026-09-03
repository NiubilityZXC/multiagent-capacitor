"""Process-isolated hidden-event replay and maturity evaluation.

The prediction-side :class:`EvaluatorClient` owns only an authenticated pipe,
the already revealed causal prefix, and public/frozen packet construction
metadata.  The complete event stream exists only in a separately spawned
evaluator process.  Pipe messages use ``send_bytes``/``recv_bytes`` (a framed,
length-prefixed transport) and canonical JSON with an exact schema, monotone
sequence, nonces, request/response hash chains, and HMAC-SHA256 binding.

The launcher/supervisor is a trusted evaluation-plane component.  It must not
be handed to prediction code: it retains the independent state-sealing key and
is the only component that can restart the evaluator with the hidden stream.
Only :class:`EvaluatorClient` is intended to cross into the prediction plane.
"""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import hmac
import multiprocessing
from multiprocessing.connection import Connection
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes, canonical_sha256, strict_canonical_loads, to_primitive
from .contracts import (
    CausalPacketSchema,
    PacketKind,
    RevealedObservation,
    SealedSplitProvenance,
)
from .generation_barrier import (
    FormalGenerationBinding,
    GenerationBarrierError,
    GenerationFinalizePermit,
    make_finalize_permit,
    verify_generation_plan,
    verify_generation_prediction_barrier,
    verify_finalize_permit,
    verify_formal_generation_binding,
)
from .registry import CAPActionRegistry
from .replay import BlindReplayService, HiddenEvent, verify_complete_run
from .runner import CAPM2Error, build_causal_packet


class EvaluatorProtocolError(CAPM2Error):
    """The isolated evaluator transport or durable session failed closed."""


_MAX_FRAME_BYTES = 256 * 1024
_ZERO_HASH = "0" * 64
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "session_id",
        "request_id",
        "sequence",
        "nonce",
        "previous_request_hash",
        "operation",
        "payload",
        "request_hash",
        "auth_tag",
    }
)
_RESPONSE_KEYS = frozenset(
    {
        "schema_version",
        "session_id",
        "request_id",
        "sequence",
        "request_hash",
        "status",
        "payload",
        "error_code",
        "response_nonce",
        "previous_response_hash",
        "response_hash",
        "auth_tag",
    }
)
_STATE_KEYS = frozenset(
    {
        "schema_version",
        "session_id",
        "state_sequence",
        "phase",
        "operation",
        "request_sequence",
        "request_id",
        "request_nonce",
        "request_payload",
        "request_hash",
        "previous_request_hash",
        "response_hash",
        "hidden_binding_tag",
        "capability_hash",
        "previous_state_hash",
        "state_hash",
        "state_auth_tag",
    }
)
_OPERATIONS = frozenset({"BOOTSTRAP", "REVEAL", "FINALIZE"})
_STATE_OPERATIONS = _OPERATIONS | {"PROTOCOL"}
_STATE_PHASES = frozenset({"INIT", "IN_FLIGHT", "COMPLETED", "ABORTED"})
_ERROR_CODES = frozenset(
    {
        "BOOTSTRAP_REJECTED",
        "REVEAL_REJECTED",
        "FINALIZE_REJECTED",
        "INTERNAL_REJECTED",
    }
)
_JOINT_CELL_KEYS = frozenset(
    {"schema_version", "cell_id", "session_id", "formal_binding_hash"}
)
_JOINT_UNSEAL_BODY_KEYS = frozenset(
    {
        "schema_version",
        "generation_id",
        "generation_plan_hash",
        "generation_barrier_hash",
        "master_seal_hash",
        "human_approval_hash",
        "outcome_availability_hash",
        "statistics_executable_hash",
        "joint_key_id",
        "cells",
    }
)
_JOINT_UNSEAL_KEYS = _JOINT_UNSEAL_BODY_KEYS | frozenset(
    {"joint_unseal_hash", "auth_tag"}
)
_FORMAL_FINALIZE_KEYS = frozenset(
    {
        "schema_version",
        "session_id",
        "formal_binding_hash",
        "permit",
        "joint_unseal",
        "auth_tag",
    }
)


def _is_nonnegative_int(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise EvaluatorProtocolError(f"{label} must be lowercase SHA-256")
    return value


def _hmac_hex(key: bytes, value: Mapping[str, Any]) -> str:
    return hmac.new(key, canonical_bytes(value), hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True)
class GenerationJointUnsealCell:
    """One evaluator session admitted into the single generation unseal."""

    cell_id: str
    session_id: str
    formal_binding_hash: str

    def __post_init__(self) -> None:
        _require_hash(self.cell_id, "joint cell_id")
        _require_hash(self.session_id, "joint session_id")
        _require_hash(self.formal_binding_hash, "joint formal_binding_hash")

    def record(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPGenerationJointUnsealCell.v1",
            "cell_id": self.cell_id,
            "session_id": self.session_id,
            "formal_binding_hash": self.formal_binding_hash,
        }

    @classmethod
    def from_record(cls, record: Any) -> "GenerationJointUnsealCell":
        if not isinstance(record, Mapping) or set(record) != _JOINT_CELL_KEYS:
            raise EvaluatorProtocolError("joint-unseal cell schema mismatch")
        if record["schema_version"] != "CAPGenerationJointUnsealCell.v1":
            raise EvaluatorProtocolError("joint-unseal cell version mismatch")
        return cls(
            cell_id=record["cell_id"],
            session_id=record["session_id"],
            formal_binding_hash=record["formal_binding_hash"],
        )


@dataclass(frozen=True, slots=True)
class GenerationJointUnsealAuthorization:
    """Single HMAC-authorized transition from all-prediction to label access.

    The authorization binds the complete admitted cell/session set and the
    frozen aggregate-statistics executable.  It is issued once to an
    exclusive durable path by the trusted evaluation plane.  Per-cell state
    keys subsequently wrap this same immutable record; they cannot substitute
    a different statistics program or a partial generation.
    """

    generation_id: str
    generation_plan_hash: str
    generation_barrier_hash: str
    master_seal_hash: str
    human_approval_hash: str
    outcome_availability_hash: str
    statistics_executable_hash: str
    joint_key_id: str
    cells: tuple[GenerationJointUnsealCell, ...]
    auth_tag: str

    def __post_init__(self) -> None:
        for name in (
            "generation_id",
            "generation_plan_hash",
            "generation_barrier_hash",
            "master_seal_hash",
            "human_approval_hash",
            "outcome_availability_hash",
            "statistics_executable_hash",
            "joint_key_id",
            "auth_tag",
        ):
            _require_hash(getattr(self, name), name)
        if not isinstance(self.cells, tuple) or not self.cells or not all(
            isinstance(item, GenerationJointUnsealCell) for item in self.cells
        ):
            raise EvaluatorProtocolError("joint-unseal requires typed cells")
        if self.cells != tuple(sorted(self.cells, key=lambda item: item.cell_id)):
            raise EvaluatorProtocolError("joint-unseal cells are not canonical")
        if len({item.cell_id for item in self.cells}) != len(self.cells):
            raise EvaluatorProtocolError("joint-unseal contains duplicate cells")
        if len({item.session_id for item in self.cells}) != len(self.cells):
            raise EvaluatorProtocolError("joint-unseal contains duplicate sessions")

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPGenerationJointUnsealAuthorization.v1",
            "generation_id": self.generation_id,
            "generation_plan_hash": self.generation_plan_hash,
            "generation_barrier_hash": self.generation_barrier_hash,
            "master_seal_hash": self.master_seal_hash,
            "human_approval_hash": self.human_approval_hash,
            "outcome_availability_hash": self.outcome_availability_hash,
            "statistics_executable_hash": self.statistics_executable_hash,
            "joint_key_id": self.joint_key_id,
            "cells": [item.record() for item in self.cells],
        }

    @property
    def joint_unseal_hash(self) -> str:
        return canonical_sha256(self.body())

    def record(self) -> dict[str, Any]:
        result = self.body()
        result["joint_unseal_hash"] = self.joint_unseal_hash
        result["auth_tag"] = self.auth_tag
        return result

    @classmethod
    def from_record(cls, record: Any) -> "GenerationJointUnsealAuthorization":
        if not isinstance(record, Mapping) or set(record) != _JOINT_UNSEAL_KEYS:
            raise EvaluatorProtocolError("joint-unseal authorization schema mismatch")
        if record["schema_version"] != "CAPGenerationJointUnsealAuthorization.v1":
            raise EvaluatorProtocolError("joint-unseal authorization version mismatch")
        if not isinstance(record["cells"], list):
            raise EvaluatorProtocolError("joint-unseal cells must be a list")
        value = cls(
            generation_id=record["generation_id"],
            generation_plan_hash=record["generation_plan_hash"],
            generation_barrier_hash=record["generation_barrier_hash"],
            master_seal_hash=record["master_seal_hash"],
            human_approval_hash=record["human_approval_hash"],
            outcome_availability_hash=record["outcome_availability_hash"],
            statistics_executable_hash=record["statistics_executable_hash"],
            joint_key_id=record["joint_key_id"],
            cells=tuple(
                GenerationJointUnsealCell.from_record(item)
                for item in record["cells"]
            ),
            auth_tag=record["auth_tag"],
        )
        if record["joint_unseal_hash"] != value.joint_unseal_hash:
            raise EvaluatorProtocolError("joint-unseal authorization hash mismatch")
        return value

    def cell_by_id(self, cell_id: str) -> GenerationJointUnsealCell:
        matches = [item for item in self.cells if item.cell_id == cell_id]
        if len(matches) != 1:
            raise EvaluatorProtocolError("joint-unseal cell is not exactly once")
        return matches[0]


@dataclass(frozen=True, slots=True)
class EvaluatorFormalFinalizeAuthorization:
    """Supervisor-authenticated release of one frozen generation cell.

    The evaluator ``state_key`` authenticates this wrapper, which must contain
    the already verified generation-wide joint-unseal record. Prediction code
    receives neither signing key and cannot turn the HMAC-free deterministic
    permit into a formal FINALIZE authorization by itself.
    """

    session_id: str
    formal_binding_hash: str
    permit: GenerationFinalizePermit
    joint_unseal: GenerationJointUnsealAuthorization
    auth_tag: str

    def __post_init__(self) -> None:
        _require_hash(self.session_id, "formal authorization session_id")
        _require_hash(self.formal_binding_hash, "formal_binding_hash")
        if not isinstance(self.permit, GenerationFinalizePermit):
            raise EvaluatorProtocolError("formal authorization permit is not typed")
        if not isinstance(self.joint_unseal, GenerationJointUnsealAuthorization):
            raise EvaluatorProtocolError("formal authorization joint unseal is not typed")
        _require_hash(self.auth_tag, "formal authorization auth_tag")

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPEvaluatorFormalFinalizeAuthorization.v1",
            "session_id": self.session_id,
            "formal_binding_hash": self.formal_binding_hash,
            "permit": self.permit.record(),
            "joint_unseal": self.joint_unseal.record(),
        }

    def record(self) -> dict[str, Any]:
        result = self.body()
        result["auth_tag"] = self.auth_tag
        return result

    @classmethod
    def from_record(cls, record: Any) -> "EvaluatorFormalFinalizeAuthorization":
        if not isinstance(record, Mapping) or set(record) != _FORMAL_FINALIZE_KEYS:
            raise EvaluatorProtocolError("formal FINALIZE authorization schema mismatch")
        if record["schema_version"] != "CAPEvaluatorFormalFinalizeAuthorization.v1":
            raise EvaluatorProtocolError("formal FINALIZE authorization version mismatch")
        try:
            permit = GenerationFinalizePermit.from_record(record["permit"])
            joint_unseal = GenerationJointUnsealAuthorization.from_record(
                record["joint_unseal"]
            )
        except GenerationBarrierError as exc:
            raise EvaluatorProtocolError("formal FINALIZE permit is invalid") from exc
        return cls(
            session_id=record["session_id"],
            formal_binding_hash=record["formal_binding_hash"],
            permit=permit,
            joint_unseal=joint_unseal,
            auth_tag=record["auth_tag"],
        )


def _formal_finalize_payload_shape(payload: Any) -> bool:
    return (
        isinstance(payload, Mapping)
        and set(payload) == _FORMAL_FINALIZE_KEYS
        and isinstance(payload.get("permit"), Mapping)
        and isinstance(payload.get("joint_unseal"), Mapping)
    )


def _launch_binding_payload(
    *,
    event_payloads: Sequence[Mapping[str, Any]],
    context: int,
    causal_schema: CausalPacketSchema,
    split: SealedSplitProvenance,
    registry: CAPActionRegistry,
    packet_kind: PacketKind,
    allowed_policy_hashes: Sequence[str],
    normalization: Mapping[str, Any],
    allowed_conditions: Mapping[str, Any],
    train_error_summaries: Mapping[str, Any],
    diagnostic_bins: Mapping[str, Any],
    formal_generation: FormalGenerationBinding | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "CAPEvaluatorLaunchBinding.v1",
        "events": list(event_payloads),
        "context": context,
        "causal_schema": to_primitive(causal_schema),
        "split": to_primitive(split),
        "registry": {
            "registry_hash": registry.registry_hash,
            "action_manifest_hash": registry.action_manifest_hash,
            "numerical_registry_hash": registry.numerical.numerical_registry_hash,
            "feature_registry_hash": registry.features.feature_registry_hash,
            "fallback_bundle_hash": registry.numerical.fallback_bundle.bundle_hash,
        },
        "packet_kind": packet_kind.value,
        "allowed_policy_hashes": sorted(allowed_policy_hashes),
        "normalization": dict(normalization),
        "allowed_conditions": dict(allowed_conditions),
        "train_error_summaries": dict(train_error_summaries),
        "diagnostic_bins": dict(diagnostic_bins),
    }
    if formal_generation is not None:
        payload["formal_generation"] = formal_generation.payload()
    return payload


def _secure_read(path: Path) -> bytes:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise EvaluatorProtocolError("evaluator state must be a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class _SessionJournal:
    """Evaluator-private, append-only authenticated state transition chain."""

    def __init__(
        self,
        path: Path,
        *,
        session_id: str,
        capability_hash: str,
        hidden_binding_tag: str,
        state_key: bytes,
        resume: bool,
    ) -> None:
        self.path = path
        self.head_path = path.with_name("EVALUATOR_SESSION.head.json")
        self.session_id = session_id
        self.capability_hash = capability_hash
        self.hidden_binding_tag = hidden_binding_tag
        self.state_key = state_key
        self._records: list[dict[str, Any]] = []
        if path.exists():
            if not resume:
                raise EvaluatorProtocolError("evaluator state already exists")
            raw = _secure_read(path)
            self._records = list(self._verify_records(raw))
            self._verify_head(raw)
            flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
        else:
            if self.head_path.exists() or self.head_path.is_symlink():
                raise EvaluatorProtocolError("orphaned evaluator authenticated head exists")
            if resume:
                # Resume after a crash before first durable initialization is
                # safe only when no state artifact exists yet.
                pass
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags, 0o600)
            _fsync_directory(path.parent)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(descriptor)
            raise EvaluatorProtocolError("another evaluator owns this session state") from exc
        self._stream = os.fdopen(descriptor, "ab", buffering=0)
        self._closed = False
        if not self._records:
            self.append(
                phase="INIT",
                operation=None,
                request_sequence=None,
                request_id=None,
                request_nonce=None,
                request_payload=None,
                request_hash=None,
                previous_request_hash=_ZERO_HASH,
                response_hash=_ZERO_HASH,
            )
        else:
            last = self._records[-1]
            if last["phase"] == "ABORTED":
                self.close()
                raise EvaluatorProtocolError(
                    "evaluator restart found an aborted request; manual audit is required"
                )
            if last["phase"] == "IN_FLIGHT" and last["operation"] != "REVEAL":
                self.close()
                raise EvaluatorProtocolError(
                    "only an interrupted REVEAL has a uniquely recoverable effect"
                )
            completed_ops = [
                item["operation"] for item in self._records if item["phase"] == "COMPLETED"
            ]
            if "FINALIZE" in completed_ops:
                self.close()
                raise EvaluatorProtocolError("a finalized evaluator session cannot restart")

    def _head_record(self, journal_raw: bytes) -> dict[str, Any]:
        final_state_hash = self._records[-1]["state_hash"] if self._records else _ZERO_HASH
        body = {
            "schema_version": "CAPEvaluatorJournalHead.v1",
            "session_id": self.session_id,
            "record_count": len(self._records),
            "journal_size": len(journal_raw),
            "journal_sha256": hashlib.sha256(journal_raw).hexdigest(),
            "final_state_hash": final_state_hash,
            "hidden_binding_tag": self.hidden_binding_tag,
            "capability_hash": self.capability_hash,
        }
        record = dict(body)
        record["head_hash"] = canonical_sha256(body)
        record["head_auth_tag"] = _hmac_hex(self.state_key, record)
        return record

    def _verify_head(self, journal_raw: bytes) -> None:
        try:
            raw = _secure_read(self.head_path)
            head = strict_canonical_loads(raw)
        except Exception as exc:
            raise EvaluatorProtocolError("evaluator authenticated head is missing or invalid") from exc
        expected = self._head_record(journal_raw)
        if not isinstance(head, dict) or head != expected or canonical_bytes(head) != raw:
            raise EvaluatorProtocolError(
                "evaluator journal/head mismatch detects truncation or rollback"
            )

    def _write_head(self) -> None:
        journal_raw = _secure_read(self.path)
        raw = canonical_bytes(self._head_record(journal_raw))
        temporary = self.head_path.with_name(
            f".{self.head_path.name}.{secrets.token_hex(8)}.tmp"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise EvaluatorProtocolError("short evaluator authenticated-head write")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            if self.head_path.is_symlink():
                raise EvaluatorProtocolError("evaluator authenticated head cannot be a symlink")
            os.replace(temporary, self.head_path)
            _fsync_directory(self.head_path.parent)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _verify_records(self, raw: bytes) -> tuple[dict[str, Any], ...]:
        if not raw or not raw.endswith(b"\n"):
            raise EvaluatorProtocolError("evaluator state journal is empty or crash-truncated")
        records: list[dict[str, Any]] = []
        previous_state_hash = _ZERO_HASH
        for expected_sequence, line in enumerate(raw.splitlines()):
            try:
                record = strict_canonical_loads(line)
            except Exception as exc:
                raise EvaluatorProtocolError("evaluator state is not strict canonical JSON") from exc
            if not isinstance(record, dict) or set(record) != _STATE_KEYS:
                raise EvaluatorProtocolError("evaluator state schema mismatch")
            body = {
                key: value
                for key, value in record.items()
                if key not in {"state_hash", "state_auth_tag"}
            }
            authenticated = dict(body)
            authenticated["state_hash"] = record["state_hash"]
            if (
                record["schema_version"] != "CAPEvaluatorState.v1"
                or record["session_id"] != self.session_id
                or record["state_sequence"] != expected_sequence
                or record["phase"] not in _STATE_PHASES
                or record["previous_state_hash"] != previous_state_hash
                or record["capability_hash"] != self.capability_hash
                or record["hidden_binding_tag"] != self.hidden_binding_tag
                or canonical_sha256(body) != record["state_hash"]
                or not hmac.compare_digest(
                    _hmac_hex(self.state_key, authenticated), record["state_auth_tag"]
                )
            ):
                raise EvaluatorProtocolError("evaluator state binding or hash chain mismatch")
            operation = record["operation"]
            request_sequence = record["request_sequence"]
            request_id = record["request_id"]
            request_nonce = record["request_nonce"]
            request_payload = record["request_payload"]
            request_hash = record["request_hash"]
            if record["phase"] == "INIT":
                if (
                    expected_sequence != 0
                    or operation is not None
                    or request_sequence is not None
                    or request_id is not None
                    or request_nonce is not None
                    or request_payload is not None
                    or request_hash is not None
                ):
                    raise EvaluatorProtocolError("invalid evaluator INIT state")
            else:
                if operation not in _STATE_OPERATIONS or not _is_nonnegative_int(request_sequence):
                    raise EvaluatorProtocolError("invalid evaluator request state")
                if not isinstance(request_id, str) or _HEX32.fullmatch(request_id) is None:
                    raise EvaluatorProtocolError("invalid evaluator request ID state")
                if not isinstance(request_nonce, str) or _HEX64.fullmatch(request_nonce) is None:
                    raise EvaluatorProtocolError("invalid evaluator request nonce state")
                if not isinstance(request_payload, dict):
                    raise EvaluatorProtocolError("invalid evaluator request payload state")
                if operation == "REVEAL":
                    if set(request_payload) != {"checkpoint_record_hash"}:
                        raise EvaluatorProtocolError("invalid REVEAL payload in evaluator state")
                    _require_hash(
                        request_payload["checkpoint_record_hash"],
                        "state checkpoint_record_hash",
                    )
                elif operation == "FINALIZE":
                    if request_payload and not _formal_finalize_payload_shape(request_payload):
                        raise EvaluatorProtocolError(
                            "invalid formal FINALIZE payload in evaluator state"
                        )
                elif request_payload:
                    raise EvaluatorProtocolError("non-REVEAL evaluator state payload must be empty")
                _require_hash(request_hash, "state request hash")
            _require_hash(record["previous_request_hash"], "state previous request hash")
            _require_hash(record["response_hash"], "state response hash")
            previous_state_hash = record["state_hash"]
            records.append(record)
        self._verify_transitions(records)
        return tuple(records)

    @staticmethod
    def _verify_transitions(records: Sequence[Mapping[str, Any]]) -> None:
        expected_request_sequence = 0
        previous_request_hash = _ZERO_HASH
        bootstrap_seen = False
        finalize_seen = False
        used_request_ids: set[str] = set()
        used_request_nonces: set[str] = set()
        index = 1
        while index < len(records):
            inflight = records[index]
            if inflight["phase"] != "IN_FLIGHT":
                raise EvaluatorProtocolError("each evaluator request must begin IN_FLIGHT")
            if (
                inflight["request_sequence"] != expected_request_sequence
                or inflight["previous_request_hash"] != previous_request_hash
                or inflight["response_hash"] != _ZERO_HASH
            ):
                raise EvaluatorProtocolError("evaluator request sequence/hash chain is broken")
            operation = inflight["operation"]
            if inflight["request_id"] in used_request_ids or inflight["request_nonce"] in used_request_nonces:
                raise EvaluatorProtocolError("evaluator request ID or nonce was reused")
            used_request_ids.add(inflight["request_id"])
            used_request_nonces.add(inflight["request_nonce"])
            if operation == "PROTOCOL":
                if index + 1 >= len(records) or records[index + 1]["phase"] != "ABORTED":
                    raise EvaluatorProtocolError("protocol violation must terminate ABORTED")
            elif operation == "BOOTSTRAP":
                if bootstrap_seen or expected_request_sequence != 0:
                    raise EvaluatorProtocolError("BOOTSTRAP must be the first and only bootstrap")
                bootstrap_seen = True
            elif not bootstrap_seen:
                raise EvaluatorProtocolError("evaluator operation preceded BOOTSTRAP")
            if finalize_seen:
                raise EvaluatorProtocolError("operation follows FINALIZE")
            if index + 1 >= len(records):
                # A crash can leave this exact terminal state.  Constructor
                # rejects it after structural verification.
                return
            terminal = records[index + 1]
            if terminal["phase"] not in {"COMPLETED", "ABORTED"}:
                raise EvaluatorProtocolError("IN_FLIGHT lacks one terminal transition")
            if any(
                terminal[key] != inflight[key]
                for key in (
                    "operation",
                    "request_sequence",
                    "request_id",
                    "request_nonce",
                    "request_payload",
                    "request_hash",
                    "previous_request_hash",
                )
            ):
                raise EvaluatorProtocolError("terminal evaluator transition changed request identity")
            if terminal["phase"] == "ABORTED":
                if index + 2 != len(records):
                    raise EvaluatorProtocolError("ABORTED evaluator state is not terminal")
                return
            _require_hash(terminal["response_hash"], "completed response hash")
            if terminal["response_hash"] == _ZERO_HASH:
                raise EvaluatorProtocolError("COMPLETED evaluator state lacks a response")
            if operation == "FINALIZE":
                finalize_seen = True
            previous_request_hash = inflight["request_hash"]
            expected_request_sequence += 1
            index += 2

    @property
    def expected_sequence(self) -> int:
        return sum(1 for item in self._records if item["phase"] == "COMPLETED")

    @property
    def previous_request_hash(self) -> str:
        completed = [item for item in self._records if item["phase"] == "COMPLETED"]
        return completed[-1]["request_hash"] if completed else _ZERO_HASH

    @property
    def previous_response_hash(self) -> str:
        completed = [item for item in self._records if item["phase"] == "COMPLETED"]
        return completed[-1]["response_hash"] if completed else _ZERO_HASH

    @property
    def completed_operations(self) -> tuple[str, ...]:
        return tuple(item["operation"] for item in self._records if item["phase"] == "COMPLETED")

    @property
    def unresolved_request(self) -> Mapping[str, Any] | None:
        last = self._records[-1]
        return last if last["phase"] == "IN_FLIGHT" else None

    @property
    def last_completed_request(self) -> Mapping[str, Any] | None:
        completed = [item for item in self._records if item["phase"] == "COMPLETED"]
        return completed[-1] if completed else None

    def response_hash_before(self, request_sequence: int) -> str:
        completed = [
            item
            for item in self._records
            if item["phase"] == "COMPLETED" and item["request_sequence"] < request_sequence
        ]
        return completed[-1]["response_hash"] if completed else _ZERO_HASH

    @property
    def used_request_ids(self) -> frozenset[str]:
        return frozenset(item["request_id"] for item in self._records if item["phase"] == "IN_FLIGHT")

    @property
    def used_request_nonces(self) -> frozenset[str]:
        return frozenset(item["request_nonce"] for item in self._records if item["phase"] == "IN_FLIGHT")

    def append(
        self,
        *,
        phase: str,
        operation: str | None,
        request_sequence: int | None,
        request_id: str | None,
        request_nonce: str | None,
        request_payload: Mapping[str, Any] | None,
        request_hash: str | None,
        previous_request_hash: str,
        response_hash: str,
    ) -> str:
        if self._closed:
            raise EvaluatorProtocolError("evaluator journal is closed")
        if phase not in _STATE_PHASES:
            raise EvaluatorProtocolError("unknown evaluator state phase")
        previous_state_hash = self._records[-1]["state_hash"] if self._records else _ZERO_HASH
        body: dict[str, Any] = {
            "schema_version": "CAPEvaluatorState.v1",
            "session_id": self.session_id,
            "state_sequence": len(self._records),
            "phase": phase,
            "operation": operation,
            "request_sequence": request_sequence,
            "request_id": request_id,
            "request_nonce": request_nonce,
            "request_payload": dict(request_payload) if request_payload is not None else None,
            "request_hash": request_hash,
            "previous_request_hash": previous_request_hash,
            "response_hash": response_hash,
            "hidden_binding_tag": self.hidden_binding_tag,
            "capability_hash": self.capability_hash,
            "previous_state_hash": previous_state_hash,
        }
        record = dict(body)
        record["state_hash"] = canonical_sha256(body)
        record["state_auth_tag"] = _hmac_hex(self.state_key, record)
        raw = canonical_bytes(record) + b"\n"
        try:
            written = self._stream.write(raw)
            self._stream.flush()
            os.fsync(self._stream.fileno())
        except OSError as exc:
            raise EvaluatorProtocolError("durable evaluator state append failed") from exc
        if written != len(raw):
            raise EvaluatorProtocolError("short evaluator state append")
        self._records.append(record)
        self._write_head()
        return record["state_hash"]

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._stream.flush()
            os.fsync(self._stream.fileno())
        finally:
            try:
                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            self._stream.close()
            self._closed = True


def _observation_payload(observation: RevealedObservation) -> dict[str, Any]:
    return {
        "event_index": observation.event_index,
        "observed_at": observation.observed_at,
        "available_at": observation.available_at,
        "measurements": to_primitive(observation.measurements),
        "missingness": to_primitive(observation.missingness),
    }


def _parse_observation(payload: Any) -> RevealedObservation:
    if not isinstance(payload, dict) or set(payload) != {
        "event_index", "observed_at", "available_at", "measurements", "missingness"
    }:
        raise EvaluatorProtocolError("revealed observation schema mismatch")
    try:
        return RevealedObservation(
            event_index=payload["event_index"],
            observed_at=payload["observed_at"],
            available_at=payload["available_at"],
            measurements=payload["measurements"],
            missingness=payload["missingness"],
        )
    except Exception as exc:
        raise EvaluatorProtocolError("invalid revealed observation") from exc


def _events_from_payload(payload: Sequence[Mapping[str, Any]]) -> tuple[HiddenEvent, ...]:
    events: list[HiddenEvent] = []
    for item in payload:
        if not isinstance(item, Mapping) or set(item) != {
            "event_index", "observed_at", "available_at", "measurements", "missingness"
        }:
            raise EvaluatorProtocolError("hidden event launch schema mismatch")
        events.append(
            HiddenEvent(
                event_index=item["event_index"],
                observed_at=item["observed_at"],
                available_at=item["available_at"],
                measurements=item["measurements"],
                missingness=item["missingness"],
            )
        )
    return tuple(events)


def _validate_request(
    raw: bytes,
    *,
    capability: bytes,
    session_id: str,
    expected_sequence: int | None,
    previous_request_hash: str | None,
) -> dict[str, Any]:
    try:
        request = strict_canonical_loads(raw)
    except Exception as exc:
        raise EvaluatorProtocolError("request is not strict canonical JSON") from exc
    if not isinstance(request, dict) or set(request) != _REQUEST_KEYS:
        raise EvaluatorProtocolError("request schema mismatch")
    body = {key: value for key, value in request.items() if key not in {"request_hash", "auth_tag"}}
    authenticated = dict(body)
    authenticated["request_hash"] = request["request_hash"]
    if (
        request["schema_version"] != "CAPEvaluatorRequest.v1"
        or request["session_id"] != session_id
        or not isinstance(request["request_id"], str)
        or _HEX32.fullmatch(request["request_id"]) is None
        or (expected_sequence is not None and request["sequence"] != expected_sequence)
        or not isinstance(request["nonce"], str)
        or _HEX64.fullmatch(request["nonce"]) is None
        or (
            previous_request_hash is not None
            and request["previous_request_hash"] != previous_request_hash
        )
        or request["operation"] not in _OPERATIONS
        or not isinstance(request["payload"], dict)
        or canonical_sha256(body) != request["request_hash"]
        or not hmac.compare_digest(_hmac_hex(capability, authenticated), request["auth_tag"])
    ):
        raise EvaluatorProtocolError("request identity, order, chain, hash, or HMAC mismatch")
    operation = request["operation"]
    payload = request["payload"]
    if operation == "BOOTSTRAP":
        if payload:
            raise EvaluatorProtocolError(f"{operation} request payload must be empty")
    elif operation == "FINALIZE":
        if payload and not _formal_finalize_payload_shape(payload):
            raise EvaluatorProtocolError("formal FINALIZE request payload schema mismatch")
    elif set(payload) != {"checkpoint_record_hash"}:
        raise EvaluatorProtocolError("REVEAL request payload schema mismatch")
    else:
        _require_hash(payload["checkpoint_record_hash"], "checkpoint_record_hash")
    return request


def _make_response(
    *,
    capability: bytes,
    session_id: str,
    request: Mapping[str, Any],
    previous_response_hash: str,
    status: str,
    payload: Mapping[str, Any],
    error_code: str | None,
    response_nonce: str,
) -> dict[str, Any]:
    if status == "OK":
        if error_code is not None:
            raise EvaluatorProtocolError("OK evaluator response cannot carry an error code")
    elif status == "ERROR":
        if error_code not in _ERROR_CODES:
            raise EvaluatorProtocolError("evaluator error code is outside the closed allowlist")
    else:
        raise EvaluatorProtocolError("evaluator response status is outside the closed allowlist")
    body: dict[str, Any] = {
        "schema_version": "CAPEvaluatorResponse.v1",
        "session_id": session_id,
        "request_id": request["request_id"],
        "sequence": request["sequence"],
        "request_hash": request["request_hash"],
        "status": status,
        "payload": dict(payload),
        "error_code": error_code,
        "response_nonce": response_nonce,
        "previous_response_hash": previous_response_hash,
    }
    response = dict(body)
    response["response_hash"] = canonical_sha256(body)
    response["auth_tag"] = _hmac_hex(capability, response)
    return response


def _closed_operation_error_code(operation: str) -> str:
    return {
        "BOOTSTRAP": "BOOTSTRAP_REJECTED",
        "REVEAL": "REVEAL_REJECTED",
        "FINALIZE": "FINALIZE_REJECTED",
    }.get(operation, "INTERNAL_REJECTED")


def _deterministic_response_nonce(state_key: bytes, request_hash: str) -> str:
    """Make crash-reconstructed replies byte-identical for one request."""

    return hmac.new(
        state_key,
        b"CAPEvaluatorResponseNonce.v1\x00" + request_hash.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def _ready_frame(capability: bytes, session_id: str, pid: int) -> bytes:
    body = {
        "schema_version": "CAPEvaluatorReady.v1",
        "session_id": session_id,
        "pid": pid,
        "nonce": secrets.token_hex(32),
    }
    frame = dict(body)
    frame["auth_tag"] = _hmac_hex(capability, body)
    return canonical_bytes(frame)


def _validate_ready(raw: bytes, capability: bytes, session_id: str) -> int:
    try:
        frame = strict_canonical_loads(raw)
    except Exception as exc:
        raise EvaluatorProtocolError("invalid evaluator READY frame") from exc
    if not isinstance(frame, dict) or set(frame) != {
        "schema_version", "session_id", "pid", "nonce", "auth_tag"
    }:
        raise EvaluatorProtocolError("evaluator READY schema mismatch")
    body = {key: value for key, value in frame.items() if key != "auth_tag"}
    if (
        frame["schema_version"] != "CAPEvaluatorReady.v1"
        or frame["session_id"] != session_id
        or not isinstance(frame["pid"], int)
        or frame["pid"] <= 0
        or not isinstance(frame["nonce"], str)
        or _HEX64.fullmatch(frame["nonce"]) is None
        or not hmac.compare_digest(_hmac_hex(capability, body), frame["auth_tag"])
    ):
        raise EvaluatorProtocolError("evaluator READY binding mismatch")
    return frame["pid"]


def _verify_formal_launch(
    formal_generation: FormalGenerationBinding | None,
    *,
    run_dir: str | os.PathLike[str],
    context: int,
    event_count: int,
    split: SealedSplitProvenance,
    registry: CAPActionRegistry,
    allowed_policy_hashes: Sequence[str],
) -> None:
    if formal_generation is None:
        return
    try:
        cell = verify_formal_generation_binding(formal_generation, run_dir=run_dir)
    except GenerationBarrierError as exc:
        raise EvaluatorProtocolError("formal generation launch binding is invalid") from exc
    planned_manifest_hash = canonical_sha256(
        [item.token for item in registry.numerical.planned_keys]
    )
    if (
        cell.context != context
        or cell.expected_revealed_count != event_count
        or cell.split_hash != split.seal_hash
        or cell.registry_hash != registry.registry_hash
        or cell.planned_manifest_hash != planned_manifest_hash
        or tuple(allowed_policy_hashes) != (cell.policy_hash,)
    ):
        raise EvaluatorProtocolError(
            "formal generation launch configuration differs from its frozen cell"
        )


def _write_joint_unseal_exclusive(
    path: str | os.PathLike[str],
    authorization: GenerationJointUnsealAuthorization,
) -> None:
    target = Path(path)
    parent = target.parent
    try:
        parent_metadata = parent.lstat()
    except OSError as exc:
        raise EvaluatorProtocolError("joint-unseal artifact parent is unavailable") from exc
    if stat.S_ISLNK(parent_metadata.st_mode) or not stat.S_ISDIR(
        parent_metadata.st_mode
    ):
        raise EvaluatorProtocolError("joint-unseal artifact parent is unsafe")
    if target.exists() or target.is_symlink():
        raise EvaluatorProtocolError("joint-unseal authorization already exists")
    raw = canonical_bytes(authorization.record())
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise EvaluatorProtocolError("short joint-unseal artifact write")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _fsync_directory(parent)
    except FileExistsError as exc:
        raise EvaluatorProtocolError("joint-unseal authorization already exists") from exc


def verify_generation_joint_unseal_authorization(
    authorization: GenerationJointUnsealAuthorization | Mapping[str, Any],
    *,
    joint_key: bytes,
) -> GenerationJointUnsealAuthorization:
    """Verify the one global HMAC without exposing the key to predictors."""

    if not isinstance(joint_key, bytes) or len(joint_key) < 32:
        raise EvaluatorProtocolError("joint-unseal key must contain at least 256 bits")
    typed = (
        authorization
        if isinstance(authorization, GenerationJointUnsealAuthorization)
        else GenerationJointUnsealAuthorization.from_record(authorization)
    )
    if (
        typed.joint_key_id != hashlib.sha256(joint_key).hexdigest()
        or not hmac.compare_digest(_hmac_hex(joint_key, typed.body()), typed.auth_tag)
    ):
        raise EvaluatorProtocolError("joint-unseal HMAC mismatch")
    return typed


def issue_generation_joint_unseal_authorization(
    supervisors: Sequence["EvaluatorSupervisor"],
    *,
    joint_key: bytes,
    statistics_executable_hash: str,
    authorization_path: str | os.PathLike[str],
) -> GenerationJointUnsealAuthorization:
    """Atomically authorize the exact complete generation once.

    No cell receives a maturity permit here.  This function first proves that
    every admitted cell has a distinct live evaluator session and that the
    label-free generation barrier is complete, then publishes one HMAC-bound
    artifact.  Individual supervisors may wrap only this exact artifact.
    """

    _require_hash(statistics_executable_hash, "statistics_executable_hash")
    if not isinstance(joint_key, bytes) or len(joint_key) < 32:
        raise EvaluatorProtocolError("joint-unseal key must contain at least 256 bits")
    if not isinstance(supervisors, Sequence) or isinstance(supervisors, (str, bytes)):
        raise EvaluatorProtocolError("joint-unseal supervisors must be a sequence")
    typed_supervisors = tuple(supervisors)
    if not typed_supervisors or not all(
        isinstance(item, EvaluatorSupervisor) for item in typed_supervisors
    ):
        raise EvaluatorProtocolError("joint-unseal supervisors are not typed")
    formal_bindings = [item._formal_generation for item in typed_supervisors]
    if any(item is None for item in formal_bindings):
        raise EvaluatorProtocolError("joint-unseal cannot include a local evaluator")
    first = formal_bindings[0]
    assert first is not None
    if any(
        item is None
        or item.plan_path != first.plan_path
        or item.barrier_path != first.barrier_path
        or item.generation_plan_hash != first.generation_plan_hash
        for item in formal_bindings
    ):
        raise EvaluatorProtocolError("joint-unseal evaluators differ by generation")

    try:
        plan = verify_generation_plan(first.plan_path)
        barrier = verify_generation_prediction_barrier(
            first.plan_path, first.barrier_path
        )
    except GenerationBarrierError as exc:
        raise EvaluatorProtocolError("joint-unseal generation barrier is not ready") from exc
    expected_cell_ids = {item.cell_id for item in plan.cells}
    actual_cell_ids = {
        item.cell_id for item in formal_bindings if item is not None
    }
    if len(actual_cell_ids) != len(formal_bindings) or actual_cell_ids != expected_cell_ids:
        raise EvaluatorProtocolError(
            "joint-unseal requires the exact complete admitted cell/session set"
        )
    if statistics_executable_hash != plan.statistics_executable_hash:
        raise EvaluatorProtocolError(
            "joint-unseal statistics executable differs from the frozen plan"
        )
    expected_authorization_path = Path(first.plan_path).parent / "GENERATION_JOINT_UNSEAL.json"
    try:
        supplied_authorization_path = Path(authorization_path)
    except TypeError as exc:
        raise EvaluatorProtocolError("joint-unseal authorization path is invalid") from exc
    if (
        not supplied_authorization_path.is_absolute()
        or os.path.normpath(os.fspath(supplied_authorization_path))
        != os.fspath(supplied_authorization_path)
        or supplied_authorization_path != expected_authorization_path
    ):
        raise EvaluatorProtocolError(
            "joint-unseal authorization must use the frozen generation path"
        )
    if any(item._joint_unseal_hash is not None for item in typed_supervisors):
        raise EvaluatorProtocolError("generation joint-unseal was already issued")

    cells: list[GenerationJointUnsealCell] = []
    for supervisor in typed_supervisors:
        binding = supervisor._formal_generation
        assert binding is not None
        if not supervisor._process.is_alive():
            raise EvaluatorProtocolError("joint-unseal evaluator process is not alive")
        try:
            cell = verify_formal_generation_binding(
                binding, run_dir=supervisor._run_dir
            )
        except GenerationBarrierError as exc:
            raise EvaluatorProtocolError("joint-unseal formal binding drifted") from exc
        _verify_formal_launch(
            binding,
            run_dir=supervisor._run_dir,
            context=supervisor._context_length,
            event_count=cell.expected_revealed_count,
            split=supervisor._split,
            registry=supervisor._registry,
            allowed_policy_hashes=supervisor._allowed_policy_hashes,
        )
        cells.append(
            GenerationJointUnsealCell(
                cell_id=binding.cell_id,
                session_id=supervisor._session_id,
                formal_binding_hash=canonical_sha256(binding.payload()),
            )
        )
    unsigned = GenerationJointUnsealAuthorization(
        generation_id=plan.generation_id,
        generation_plan_hash=plan.plan_hash,
        generation_barrier_hash=barrier.barrier_hash,
        master_seal_hash=plan.master_seal_hash,
        human_approval_hash=plan.human_approval_hash,
        outcome_availability_hash=plan.outcome_availability_hash,
        statistics_executable_hash=statistics_executable_hash,
        joint_key_id=hashlib.sha256(joint_key).hexdigest(),
        cells=tuple(sorted(cells, key=lambda item: item.cell_id)),
        auth_tag=_ZERO_HASH,
    )
    authorization = GenerationJointUnsealAuthorization(
        generation_id=unsigned.generation_id,
        generation_plan_hash=unsigned.generation_plan_hash,
        generation_barrier_hash=unsigned.generation_barrier_hash,
        master_seal_hash=unsigned.master_seal_hash,
        human_approval_hash=unsigned.human_approval_hash,
        outcome_availability_hash=unsigned.outcome_availability_hash,
        statistics_executable_hash=unsigned.statistics_executable_hash,
        joint_key_id=unsigned.joint_key_id,
        cells=unsigned.cells,
        auth_tag=_hmac_hex(joint_key, unsigned.body()),
    )
    _write_joint_unseal_exclusive(authorization_path, authorization)
    for supervisor in typed_supervisors:
        supervisor._joint_unseal_hash = authorization.joint_unseal_hash
    return authorization


def _issue_formal_finalize_authorization(
    *,
    formal_generation: FormalGenerationBinding,
    state_key: bytes,
    session_id: str,
    joint_unseal: GenerationJointUnsealAuthorization,
) -> EvaluatorFormalFinalizeAuthorization:
    try:
        permit = make_finalize_permit(
            formal_generation.plan_path,
            formal_generation.barrier_path,
            cell_id=formal_generation.cell_id,
        )
        verify_finalize_permit(
            formal_generation.plan_path,
            formal_generation.barrier_path,
            permit,
            expected_cell_id=formal_generation.cell_id,
            reverify_cell=True,
        )
    except GenerationBarrierError as exc:
        raise EvaluatorProtocolError(
            "formal generation prediction barrier is not ready"
        ) from exc
    binding_hash = canonical_sha256(formal_generation.payload())
    unsigned = EvaluatorFormalFinalizeAuthorization(
        session_id=session_id,
        formal_binding_hash=binding_hash,
        permit=permit,
        joint_unseal=joint_unseal,
        auth_tag="0" * 64,
    )
    return EvaluatorFormalFinalizeAuthorization(
        session_id=session_id,
        formal_binding_hash=binding_hash,
        permit=permit,
        joint_unseal=joint_unseal,
        auth_tag=_hmac_hex(state_key, unsigned.body()),
    )


def _verify_formal_finalize_authorization(
    payload: Mapping[str, Any],
    *,
    formal_generation: FormalGenerationBinding,
    state_key: bytes,
    session_id: str,
    run_dir: str | os.PathLike[str],
) -> None:
    authorization = EvaluatorFormalFinalizeAuthorization.from_record(payload)
    binding_hash = canonical_sha256(formal_generation.payload())
    joint_cell = authorization.joint_unseal.cell_by_id(formal_generation.cell_id)
    if (
        authorization.session_id != session_id
        or authorization.formal_binding_hash != binding_hash
        or joint_cell.session_id != session_id
        or joint_cell.formal_binding_hash != binding_hash
        or authorization.joint_unseal.generation_id
        != formal_generation.generation_id
        or authorization.joint_unseal.generation_plan_hash
        != formal_generation.generation_plan_hash
        or authorization.joint_unseal.master_seal_hash
        != formal_generation.master_seal_hash
        or authorization.joint_unseal.human_approval_hash
        != formal_generation.human_approval_hash
        or authorization.joint_unseal.outcome_availability_hash
        != formal_generation.outcome_availability_hash
        or authorization.joint_unseal.statistics_executable_hash
        != formal_generation.statistics_executable_hash
        or not hmac.compare_digest(
            _hmac_hex(state_key, authorization.body()), authorization.auth_tag
        )
    ):
        raise EvaluatorProtocolError("formal FINALIZE authorization HMAC mismatch")
    try:
        verify_formal_generation_binding(formal_generation, run_dir=run_dir)
        verify_finalize_permit(
            formal_generation.plan_path,
            formal_generation.barrier_path,
            authorization.permit,
            expected_cell_id=formal_generation.cell_id,
            reverify_cell=True,
        )
    except GenerationBarrierError as exc:
        raise EvaluatorProtocolError(
            "formal FINALIZE plan, barrier, or cell receipt is invalid"
        ) from exc


def _run_operation(
    service: BlindReplayService,
    operation: str,
    payload: Mapping[str, Any],
    *,
    context: int,
    formal_generation: FormalGenerationBinding | None,
    state_key: bytes,
    session_id: str,
) -> dict[str, Any]:
    if operation == "BOOTSTRAP":
        return {
            "observations": [_observation_payload(item) for item in service.current_prefix()]
        }
    if operation == "REVEAL":
        observation = service.reveal_next_after_checkpoint(payload["checkpoint_record_hash"])
        return {"observation": _observation_payload(observation)}
    if operation == "FINALIZE":
        if formal_generation is None:
            if payload:
                raise EvaluatorProtocolError(
                    "legacy FINALIZE cannot carry formal generation authorization"
                )
        else:
            if not payload:
                raise EvaluatorProtocolError(
                    "formal generation FINALIZE requires supervisor authorization"
                )
            _verify_formal_finalize_authorization(
                payload,
                formal_generation=formal_generation,
                state_key=state_key,
                session_id=session_id,
                run_dir=service.paths.root,
            )
        run_seal_hash = service.seal_access_and_mature()
        report = verify_complete_run(service.paths.root, context=context)
        return {
            "run_seal_hash": run_seal_hash,
            "prediction_count": report["prediction_count"],
            "execution_count": report["execution_count"],
            "maturity_count": report["maturity_count"],
            "matured_count": report["matured_count"],
            "never_matured_count": report["never_matured_count"],
        }
    raise EvaluatorProtocolError("unknown evaluator operation")


def _state_request_matches(
    state: Mapping[str, Any] | None, request: Mapping[str, Any]
) -> bool:
    return state is not None and all(
        (
            state["operation"] == request["operation"],
            state["request_sequence"] == request["sequence"],
            state["request_id"] == request["request_id"],
            state["request_nonce"] == request["nonce"],
            state["request_payload"] == request["payload"],
            state["request_hash"] == request["request_hash"],
            state["previous_request_hash"] == request["previous_request_hash"],
        )
    )


def _abort_authenticated_protocol_request(
    journal: _SessionJournal,
    *,
    raw: bytes,
) -> None:
    """Durably terminate an authenticated sequence/phase violation."""

    unresolved = journal.unresolved_request
    abort_hash = canonical_sha256(
        {
            "schema_version": "CAPEvaluatorProtocolAbort.v1",
            "frame_sha256": hashlib.sha256(raw).hexdigest(),
        }
    )
    if unresolved is not None:
        journal.append(
            phase="ABORTED",
            operation=unresolved["operation"],
            request_sequence=unresolved["request_sequence"],
            request_id=unresolved["request_id"],
            request_nonce=unresolved["request_nonce"],
            request_payload=unresolved["request_payload"],
            request_hash=unresolved["request_hash"],
            previous_request_hash=unresolved["previous_request_hash"],
            response_hash=abort_hash,
        )
        return
    protocol_hash = hashlib.sha256(raw).hexdigest()
    journal.append(
        phase="IN_FLIGHT",
        operation="PROTOCOL",
        request_sequence=journal.expected_sequence,
        request_id=protocol_hash[:32],
        request_nonce=protocol_hash,
        request_payload={},
        request_hash=protocol_hash,
        previous_request_hash=journal.previous_request_hash,
        response_hash=_ZERO_HASH,
    )
    journal.append(
        phase="ABORTED",
        operation="PROTOCOL",
        request_sequence=journal.expected_sequence,
        request_id=protocol_hash[:32],
        request_nonce=protocol_hash,
        request_payload={},
        request_hash=protocol_hash,
        previous_request_hash=journal.previous_request_hash,
        response_hash=abort_hash,
    )


def _evaluator_main(
    connection: Connection,
    *,
    run_dir: str,
    event_payloads: Sequence[Mapping[str, Any]],
    context: int,
    causal_schema: CausalPacketSchema,
    split: SealedSplitProvenance,
    registry: CAPActionRegistry,
    packet_kind: PacketKind,
    allowed_policy_hashes: Sequence[str],
    normalization: Mapping[str, Any],
    allowed_conditions: Mapping[str, Any],
    train_error_summaries: Mapping[str, Any],
    diagnostic_bins: Mapping[str, Any],
    formal_generation: FormalGenerationBinding | None,
    session_id: str,
    capability: bytes,
    state_key: bytes,
    resume: bool,
    fault_after_inflight: str | None,
    fault_after_completed: str | None,
) -> None:
    service: BlindReplayService | None = None
    journal: _SessionJournal | None = None
    try:
        events = _events_from_payload(event_payloads)
        _verify_formal_launch(
            formal_generation,
            run_dir=run_dir,
            context=context,
            event_count=len(events),
            split=split,
            registry=registry,
            allowed_policy_hashes=allowed_policy_hashes,
        )
        launch_binding = _launch_binding_payload(
            event_payloads=event_payloads,
            context=context,
            causal_schema=causal_schema,
            split=split,
            registry=registry,
            packet_kind=packet_kind,
            allowed_policy_hashes=allowed_policy_hashes,
            normalization=normalization,
            allowed_conditions=allowed_conditions,
            train_error_summaries=train_error_summaries,
            diagnostic_bins=diagnostic_bins,
            formal_generation=formal_generation,
        )
        hidden_binding_tag = hmac.new(
            state_key, canonical_bytes(launch_binding), hashlib.sha256
        ).hexdigest()
        state_path = Path(run_dir) / "EVALUATOR_SESSION.jsonl"
        journal = _SessionJournal(
            state_path,
            session_id=session_id,
            capability_hash=hashlib.sha256(capability).hexdigest(),
            hidden_binding_tag=hidden_binding_tag,
            state_key=state_key,
            resume=resume,
        )
        service = BlindReplayService(
            run_dir,
            events=events,
            context=context,
            causal_schema=causal_schema,
            split=split,
            registry=registry,
            packet_kind=packet_kind,
            allowed_policy_hashes=allowed_policy_hashes,
            normalization=normalization,
            allowed_conditions=allowed_conditions,
            train_error_summaries=train_error_summaries,
            diagnostic_bins=diagnostic_bins,
            resume=True,
        )
        # Drop the launch serialization after validated HiddenEvent objects are
        # resident exclusively in this evaluator address space.
        del event_payloads
        connection.send_bytes(_ready_frame(capability, session_id, os.getpid()))
        while True:
            try:
                raw = connection.recv_bytes(_MAX_FRAME_BYTES)
            except EOFError:
                return
            except OSError as exc:
                raise EvaluatorProtocolError("oversized or broken evaluator request frame") from exc
            request: dict[str, Any]
            try:
                request = _validate_request(
                    raw,
                    capability=capability,
                    session_id=session_id,
                    expected_sequence=None,
                    previous_request_hash=None,
                )
            except Exception:
                # Unauthenticated/tampered/cross-session bytes cannot mutate
                # evaluator state.  Closing this channel rejects them while an
                # exact pending request can still recover on a fresh channel.
                return
            unresolved = journal.unresolved_request
            last_completed = journal.last_completed_request
            recovering_inflight = _state_request_matches(unresolved, request)
            replaying_completed = _state_request_matches(last_completed, request)
            try:
                if unresolved is not None and not recovering_inflight:
                    raise EvaluatorProtocolError("request differs from the unresolved durable request")
                if replaying_completed:
                    if request["operation"] != "REVEAL":
                        raise EvaluatorProtocolError("only REVEAL has an idempotent completed replay")
                elif not recovering_inflight:
                    if (
                        request["sequence"] != journal.expected_sequence
                        or request["previous_request_hash"] != journal.previous_request_hash
                    ):
                        raise EvaluatorProtocolError("request sequence or hash chain is out of order")
                    if (
                        request["request_id"] in journal.used_request_ids
                        or request["nonce"] in journal.used_request_nonces
                    ):
                        raise EvaluatorProtocolError("request ID or nonce was already consumed")
                    completed = journal.completed_operations
                    if request["operation"] == "BOOTSTRAP":
                        if completed:
                            raise EvaluatorProtocolError("BOOTSTRAP may execute exactly once")
                    elif not completed or completed[0] != "BOOTSTRAP" or "FINALIZE" in completed:
                        raise EvaluatorProtocolError("evaluator operation violates session phase")
            except Exception:
                _abort_authenticated_protocol_request(journal, raw=raw)
                return
            if not recovering_inflight and not replaying_completed:
                journal.append(
                    phase="IN_FLIGHT",
                    operation=request["operation"],
                    request_sequence=request["sequence"],
                    request_id=request["request_id"],
                    request_nonce=request["nonce"],
                    request_payload=request["payload"],
                    request_hash=request["request_hash"],
                    previous_request_hash=request["previous_request_hash"],
                    response_hash=_ZERO_HASH,
                )
            try:
                result = _run_operation(
                    service,
                    request["operation"],
                    request["payload"],
                    context=context,
                    formal_generation=formal_generation,
                    state_key=state_key,
                    session_id=session_id,
                )
                if fault_after_inflight == request["operation"] and not replaying_completed:
                    # Test hook: the operation's durable side effect (notably
                    # ACCESS fsync) exists, but no COMPLETED state or reply does.
                    os._exit(93)
                response = _make_response(
                    capability=capability,
                    session_id=session_id,
                    request=request,
                    previous_response_hash=journal.response_hash_before(request["sequence"]),
                    status="OK",
                    payload=result,
                    error_code=None,
                    response_nonce=_deterministic_response_nonce(
                        state_key, request["request_hash"]
                    ),
                )
                if replaying_completed:
                    if response["response_hash"] != last_completed["response_hash"]:
                        raise EvaluatorProtocolError(
                            "reconstructed idempotent response differs from durable state"
                        )
                else:
                    journal.append(
                        phase="COMPLETED",
                        operation=request["operation"],
                        request_sequence=request["sequence"],
                        request_id=request["request_id"],
                        request_nonce=request["nonce"],
                        request_payload=request["payload"],
                        request_hash=request["request_hash"],
                        previous_request_hash=request["previous_request_hash"],
                        response_hash=response["response_hash"],
                    )
                    if fault_after_completed == request["operation"]:
                        os._exit(94)
                connection.send_bytes(canonical_bytes(response))
                if request["operation"] == "FINALIZE":
                    return
            except Exception:
                if replaying_completed:
                    return
                response = _make_response(
                    capability=capability,
                    session_id=session_id,
                    request=request,
                    previous_response_hash=journal.response_hash_before(request["sequence"]),
                    status="ERROR",
                    payload={},
                    error_code=_closed_operation_error_code(request["operation"]),
                    response_nonce=_deterministic_response_nonce(
                        state_key, request["request_hash"]
                    ),
                )
                journal.append(
                    phase="ABORTED",
                    operation=request["operation"],
                    request_sequence=request["sequence"],
                    request_id=request["request_id"],
                    request_nonce=request["nonce"],
                    request_payload=request["payload"],
                    request_hash=request["request_hash"],
                    previous_request_hash=request["previous_request_hash"],
                    response_hash=response["response_hash"],
                )
                connection.send_bytes(canonical_bytes(response))
                return
    except BaseException:
        # Startup and protocol failures are deliberately indistinguishable to
        # the prediction plane beyond a closed/broken authenticated channel.
        return
    finally:
        if service is not None:
            service.close()
        if journal is not None:
            journal.close()
        connection.close()


@dataclass(frozen=True, slots=True)
class EvaluatorResult:
    run_seal_hash: str
    prediction_count: int
    execution_count: int
    maturity_count: int
    matured_count: int
    never_matured_count: int


class EvaluatorClient:
    """Prediction-plane handle containing no hidden suffix or label store."""

    __slots__ = (
        "_connection",
        "_capability",
        "_session_id",
        "_sequence",
        "_previous_request_hash",
        "_previous_response_hash",
        "_seen_response_nonces",
        "_pending_request",
        "_prefix",
        "_causal_schema",
        "_split",
        "_registry",
        "_packet_kind",
        "_normalization",
        "_conditions",
        "_train",
        "_diagnostics",
        "_formal_generation_plan_hash",
        "_formal_generation_cell_id",
        "_formal_binding_hash",
        "_closed",
        "_evaluator_pid",
    )

    def __init__(
        self,
        connection: Connection,
        *,
        capability: bytes,
        session_id: str,
        causal_schema: CausalPacketSchema,
        split: SealedSplitProvenance,
        registry: CAPActionRegistry,
        packet_kind: PacketKind,
        normalization: Mapping[str, Any],
        allowed_conditions: Mapping[str, Any],
        train_error_summaries: Mapping[str, Any],
        diagnostic_bins: Mapping[str, Any],
        formal_generation: FormalGenerationBinding | None,
        evaluator_pid: int,
    ) -> None:
        self._connection = connection
        self._capability = bytes(capability)
        self._session_id = session_id
        self._sequence = 0
        self._previous_request_hash = _ZERO_HASH
        self._previous_response_hash = _ZERO_HASH
        self._seen_response_nonces: set[str] = set()
        self._pending_request: tuple[bytes, dict[str, Any]] | None = None
        self._prefix: tuple[RevealedObservation, ...] = ()
        self._causal_schema = causal_schema
        self._split = split
        self._registry = registry
        self._packet_kind = packet_kind
        self._normalization = dict(normalization)
        self._conditions = dict(allowed_conditions)
        self._train = dict(train_error_summaries)
        self._diagnostics = dict(diagnostic_bins)
        self._formal_generation_plan_hash = (
            formal_generation.generation_plan_hash
            if formal_generation is not None
            else None
        )
        self._formal_generation_cell_id = (
            formal_generation.cell_id if formal_generation is not None else None
        )
        self._formal_binding_hash = (
            canonical_sha256(formal_generation.payload())
            if formal_generation is not None
            else None
        )
        self._closed = False
        self._evaluator_pid = evaluator_pid

    @property
    def evaluator_pid(self) -> int:
        return self._evaluator_pid

    @property
    def revealed_count(self) -> int:
        return len(self._prefix)

    def current_prefix(self) -> tuple[RevealedObservation, ...]:
        return tuple(self._prefix)

    def _encode_request(self, operation: str, payload: Mapping[str, Any]) -> tuple[bytes, dict[str, Any]]:
        body: dict[str, Any] = {
            "schema_version": "CAPEvaluatorRequest.v1",
            "session_id": self._session_id,
            "request_id": secrets.token_hex(16),
            "sequence": self._sequence,
            "nonce": secrets.token_hex(32),
            "previous_request_hash": self._previous_request_hash,
            "operation": operation,
            "payload": dict(payload),
        }
        request = dict(body)
        request["request_hash"] = canonical_sha256(body)
        request["auth_tag"] = _hmac_hex(self._capability, request)
        return canonical_bytes(request), request

    def _receive_response(self, request: Mapping[str, Any], *, timeout: float) -> dict[str, Any]:
        if not self._connection.poll(timeout):
            self._closed = True
            raise EvaluatorProtocolError("isolated evaluator response timed out")
        try:
            raw = self._connection.recv_bytes(_MAX_FRAME_BYTES)
            response = strict_canonical_loads(raw)
        except Exception as exc:
            self._closed = True
            raise EvaluatorProtocolError("isolated evaluator channel closed or returned invalid JSON") from exc
        if not isinstance(response, dict) or set(response) != _RESPONSE_KEYS:
            self._closed = True
            raise EvaluatorProtocolError("evaluator response schema mismatch")
        body = {
            key: value for key, value in response.items() if key not in {"response_hash", "auth_tag"}
        }
        authenticated = dict(body)
        authenticated["response_hash"] = response["response_hash"]
        if (
            response["schema_version"] != "CAPEvaluatorResponse.v1"
            or response["session_id"] != self._session_id
            or response["request_id"] != request["request_id"]
            or response["sequence"] != self._sequence
            or response["request_hash"] != request["request_hash"]
            or response["status"] not in {"OK", "ERROR"}
            or not isinstance(response["payload"], dict)
            or (
                response["error_code"] is not None
                and response["error_code"] not in _ERROR_CODES
            )
            or (response["status"] == "OK") != (response["error_code"] is None)
            or not isinstance(response["response_nonce"], str)
            or _HEX64.fullmatch(response["response_nonce"]) is None
            or response["response_nonce"] in self._seen_response_nonces
            or response["previous_response_hash"] != self._previous_response_hash
            or canonical_sha256(body) != response["response_hash"]
            or not hmac.compare_digest(
                _hmac_hex(self._capability, authenticated), response["auth_tag"]
            )
        ):
            self._closed = True
            raise EvaluatorProtocolError("evaluator response identity, chain, hash, or HMAC mismatch")
        self._sequence += 1
        self._previous_request_hash = request["request_hash"]
        self._previous_response_hash = response["response_hash"]
        self._seen_response_nonces.add(response["response_nonce"])
        self._pending_request = None
        if response["status"] == "ERROR":
            self._closed = True
            raise EvaluatorProtocolError(
                f"isolated evaluator rejected the committed operation: {response['error_code']}"
            )
        return response

    def _request(
        self, operation: str, payload: Mapping[str, Any], *, timeout: float = 10.0
    ) -> dict[str, Any]:
        if self._closed:
            raise EvaluatorProtocolError("isolated evaluator client is closed")
        if self._pending_request is None:
            raw, request = self._encode_request(operation, payload)
            self._pending_request = (raw, request)
        else:
            raw, request = self._pending_request
            if request["operation"] != operation or request["payload"] != dict(payload):
                raise EvaluatorProtocolError(
                    "a different operation cannot replace an unresolved durable request"
                )
        try:
            self._connection.send_bytes(raw)
        except (BrokenPipeError, EOFError, OSError) as exc:
            self._closed = True
            raise EvaluatorProtocolError("isolated evaluator request channel is closed") from exc
        return self._receive_response(request, timeout=timeout)["payload"]

    def bootstrap(self) -> tuple[RevealedObservation, ...]:
        if self._prefix or self._sequence != 0:
            raise EvaluatorProtocolError("bootstrap may execute exactly once")
        payload = self._request("BOOTSTRAP", {})
        if set(payload) != {"observations"} or not isinstance(payload["observations"], list):
            self._closed = True
            raise EvaluatorProtocolError("bootstrap response schema mismatch")
        observations = tuple(_parse_observation(item) for item in payload["observations"])
        if not observations or tuple(item.event_index for item in observations) != tuple(range(len(observations))):
            self._closed = True
            raise EvaluatorProtocolError("bootstrap response is not a proper causal prefix")
        self._prefix = observations
        return self.current_prefix()

    def build_current_packet(self) -> Any:
        if not self._prefix:
            raise EvaluatorProtocolError("bootstrap is required before packet construction")
        return build_causal_packet(
            packet_kind=self._packet_kind,
            origin_event_index=self._prefix[-1].event_index,
            availability_cutoff=self._prefix[-1].available_at,
            revealed_observations=self._prefix,
            causal_schema=self._causal_schema,
            split=self._split,
            registry=self._registry,
            normalization=self._normalization,
            allowed_conditions=self._conditions,
            train_error_summaries=self._train,
            diagnostic_bins=self._diagnostics,
        )

    def reveal_next_after_checkpoint(
        self, checkpoint_record_hash: str, *, timeout: float = 10.0
    ) -> RevealedObservation:
        _require_hash(checkpoint_record_hash, "checkpoint_record_hash")
        payload = self._request(
            "REVEAL", {"checkpoint_record_hash": checkpoint_record_hash}, timeout=timeout
        )
        if set(payload) != {"observation"}:
            self._closed = True
            raise EvaluatorProtocolError("reveal response schema mismatch")
        observation = _parse_observation(payload["observation"])
        if not self._prefix:
            self._closed = True
            raise EvaluatorProtocolError("evaluator returned a reveal before bootstrap")
        if observation.event_index == self._prefix[-1].event_index + 1:
            self._prefix = (*self._prefix, observation)
        elif observation.event_index < len(self._prefix):
            existing = self._prefix[observation.event_index]
            if canonical_sha256(_observation_payload(existing)) != canonical_sha256(
                _observation_payload(observation)
            ):
                self._closed = True
                raise EvaluatorProtocolError("idempotent reveal differs from the causal prefix")
            observation = existing
        else:
            self._closed = True
            raise EvaluatorProtocolError("evaluator returned a non-causal reveal")
        return observation

    def finalize_and_score(
        self,
        *,
        formal_authorization: (
            EvaluatorFormalFinalizeAuthorization | Mapping[str, Any] | None
        ) = None,
        timeout: float = 30.0,
    ) -> EvaluatorResult:
        if self._formal_generation_plan_hash is None:
            if formal_authorization is not None:
                raise EvaluatorProtocolError(
                    "legacy evaluator cannot accept formal generation authorization"
                )
            request_payload: dict[str, Any] = {}
        else:
            if formal_authorization is None:
                raise EvaluatorProtocolError(
                    "formal generation evaluator requires supervisor authorization"
                )
            authorization = (
                formal_authorization
                if isinstance(
                    formal_authorization, EvaluatorFormalFinalizeAuthorization
                )
                else EvaluatorFormalFinalizeAuthorization.from_record(
                    formal_authorization
                )
            )
            if (
                authorization.session_id != self._session_id
                or authorization.formal_binding_hash != self._formal_binding_hash
                or authorization.permit.generation_plan_hash
                != self._formal_generation_plan_hash
                or authorization.permit.cell_id
                != self._formal_generation_cell_id
                or authorization.joint_unseal.generation_plan_hash
                != self._formal_generation_plan_hash
            ):
                raise EvaluatorProtocolError(
                    "formal generation authorization differs from this client"
                )
            request_payload = authorization.record()
        payload = self._request("FINALIZE", request_payload, timeout=timeout)
        expected = {
            "run_seal_hash", "prediction_count", "execution_count", "maturity_count",
            "matured_count", "never_matured_count",
        }
        if set(payload) != expected:
            self._closed = True
            raise EvaluatorProtocolError("final evaluator result schema mismatch")
        _require_hash(payload["run_seal_hash"], "run_seal_hash")
        for key in expected - {"run_seal_hash"}:
            if not _is_nonnegative_int(payload[key]):
                self._closed = True
                raise EvaluatorProtocolError("final evaluator counts must be non-negative integers")
        self._closed = True
        return EvaluatorResult(**payload)

    def _replace_connection(self, connection: Connection, evaluator_pid: int) -> None:
        if not self._closed:
            try:
                self._connection.close()
            except OSError:
                pass
        self._connection = connection
        self._evaluator_pid = evaluator_pid
        self._closed = False

    def close(self) -> None:
        try:
            self._connection.close()
        finally:
            self._closed = True


class EvaluatorSupervisor:
    """Trusted evaluation-plane process lifecycle; never hand to predictors."""

    __slots__ = (
        "_process", "_context", "_capability", "_state_key", "_session_id", "_run_dir",
        "_context_length", "_causal_schema", "_split", "_registry", "_packet_kind",
        "_allowed_policy_hashes",
        "_normalization", "_conditions", "_train", "_diagnostics", "_fault_after_inflight",
        "_fault_after_completed", "_formal_generation",
        "_formal_authorization_issued", "_joint_unseal_hash",
    )

    def __init__(
        self,
        process: multiprocessing.Process,
        process_context: Any,
        *,
        capability: bytes,
        state_key: bytes,
        session_id: str,
        run_dir: Path,
        context_length: int,
        causal_schema: CausalPacketSchema,
        split: SealedSplitProvenance,
        registry: CAPActionRegistry,
        packet_kind: PacketKind,
        allowed_policy_hashes: Sequence[str],
        normalization: Mapping[str, Any],
        allowed_conditions: Mapping[str, Any],
        train_error_summaries: Mapping[str, Any],
        diagnostic_bins: Mapping[str, Any],
        formal_generation: FormalGenerationBinding | None,
        fault_after_inflight: str | None,
        fault_after_completed: str | None,
    ) -> None:
        self._process = process
        self._context = process_context
        self._capability = capability
        self._state_key = state_key
        self._session_id = session_id
        self._run_dir = run_dir
        self._context_length = context_length
        self._causal_schema = causal_schema
        self._split = split
        self._registry = registry
        self._packet_kind = packet_kind
        self._allowed_policy_hashes = tuple(allowed_policy_hashes)
        self._normalization = dict(normalization)
        self._conditions = dict(allowed_conditions)
        self._train = dict(train_error_summaries)
        self._diagnostics = dict(diagnostic_bins)
        self._formal_generation = formal_generation
        self._formal_authorization_issued = False
        self._joint_unseal_hash: str | None = None
        self._fault_after_inflight = fault_after_inflight
        self._fault_after_completed = fault_after_completed

    @property
    def pid(self) -> int | None:
        return self._process.pid

    @property
    def exitcode(self) -> int | None:
        return self._process.exitcode

    def crash(self) -> None:
        if self._process.is_alive():
            self._process.kill()
        self._process.join(timeout=5.0)

    def issue_formal_finalize_authorization(
        self,
        *,
        joint_unseal: GenerationJointUnsealAuthorization | Mapping[str, Any],
        joint_key: bytes,
    ) -> EvaluatorFormalFinalizeAuthorization:
        """Sign one FINALIZE only after the complete generation barrier passes.

        The supervisor is trusted and must not cross into prediction code.  The
        returned authorization is session/cell/barrier bound and cannot be
        generated from the prediction client's capability.
        """

        if self._formal_generation is None:
            raise EvaluatorProtocolError("evaluator was not launched in formal generation mode")
        if self._formal_authorization_issued:
            raise EvaluatorProtocolError("formal FINALIZE authorization was already issued")
        if not self._process.is_alive():
            raise EvaluatorProtocolError("formal evaluator process is not alive")
        try:
            cell = verify_formal_generation_binding(
                self._formal_generation, run_dir=self._run_dir
            )
        except GenerationBarrierError as exc:
            raise EvaluatorProtocolError("formal generation binding is no longer valid") from exc
        _verify_formal_launch(
            self._formal_generation,
            run_dir=self._run_dir,
            context=self._context_length,
            event_count=cell.expected_revealed_count,
            split=self._split,
            registry=self._registry,
            allowed_policy_hashes=self._allowed_policy_hashes,
        )
        verified_joint = verify_generation_joint_unseal_authorization(
            joint_unseal, joint_key=joint_key
        )
        if self._joint_unseal_hash != verified_joint.joint_unseal_hash:
            raise EvaluatorProtocolError(
                "formal FINALIZE does not use this generation's issued joint unseal"
            )
        joint_cell = verified_joint.cell_by_id(self._formal_generation.cell_id)
        binding_hash = canonical_sha256(self._formal_generation.payload())
        try:
            plan = verify_generation_plan(self._formal_generation.plan_path)
            barrier = verify_generation_prediction_barrier(
                self._formal_generation.plan_path,
                self._formal_generation.barrier_path,
            )
        except GenerationBarrierError as exc:
            raise EvaluatorProtocolError("formal generation barrier drifted") from exc
        if (
            verified_joint.generation_id != plan.generation_id
            or verified_joint.generation_plan_hash != plan.plan_hash
            or verified_joint.generation_barrier_hash != barrier.barrier_hash
            or verified_joint.master_seal_hash != plan.master_seal_hash
            or verified_joint.human_approval_hash != plan.human_approval_hash
            or verified_joint.outcome_availability_hash
            != plan.outcome_availability_hash
            or {item.cell_id for item in verified_joint.cells}
            != {item.cell_id for item in plan.cells}
            or joint_cell.session_id != self._session_id
            or joint_cell.formal_binding_hash != binding_hash
        ):
            raise EvaluatorProtocolError(
                "joint-unseal authorization differs from the complete generation"
            )
        result = _issue_formal_finalize_authorization(
            formal_generation=self._formal_generation,
            state_key=self._state_key,
            session_id=self._session_id,
            joint_unseal=verified_joint,
        )
        self._formal_authorization_issued = True
        return result

    def restart(
        self,
        client: EvaluatorClient,
        *,
        events: Sequence[HiddenEvent],
        timeout: float = 10.0,
    ) -> None:
        if self._process.is_alive():
            raise EvaluatorProtocolError("cannot restart a live evaluator")
        parent_connection, child_connection = self._context.Pipe(duplex=True)
        process = self._spawn(
            child_connection,
            event_payloads=_event_launch_payloads(events),
            resume=True,
            fault_after_inflight=None,
            fault_after_completed=None,
        )
        child_connection.close()
        try:
            evaluator_pid = _await_ready(parent_connection, self._capability, self._session_id, timeout)
        except Exception:
            parent_connection.close()
            process.join(timeout=2.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
            raise
        self._process = process
        client._replace_connection(parent_connection, evaluator_pid)

    def _spawn(
        self,
        child_connection: Connection,
        *,
        event_payloads: Sequence[Mapping[str, Any]],
        resume: bool,
        fault_after_inflight: str | None,
        fault_after_completed: str | None,
    ) -> multiprocessing.Process:
        process = self._context.Process(
            target=_evaluator_main,
            kwargs={
                "connection": child_connection,
                "run_dir": str(self._run_dir),
                "event_payloads": event_payloads,
                "context": self._context_length,
                "causal_schema": self._causal_schema,
                "split": self._split,
                "registry": self._registry,
                "packet_kind": self._packet_kind,
                "allowed_policy_hashes": self._allowed_policy_hashes,
                "normalization": self._normalization,
                "allowed_conditions": self._conditions,
                "train_error_summaries": self._train,
                "diagnostic_bins": self._diagnostics,
                "formal_generation": self._formal_generation,
                "session_id": self._session_id,
                "capability": self._capability,
                "state_key": self._state_key,
                "resume": resume,
                "fault_after_inflight": fault_after_inflight,
                "fault_after_completed": fault_after_completed,
            },
            name="cap-hidden-evaluator",
            daemon=False,
        )
        process.start()
        return process

    def close(self) -> None:
        self._process.join(timeout=2.0)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5.0)


def _event_launch_payloads(events: Sequence[HiddenEvent]) -> tuple[dict[str, Any], ...]:
    payloads = tuple(_observation_payload(event.revealed()) for event in events)
    # Reconstruct once in the trusted launcher to reject malformed input before
    # creating any session files or evaluator process.
    _events_from_payload(payloads)
    return payloads


def _await_ready(
    connection: Connection, capability: bytes, session_id: str, timeout: float
) -> int:
    if not connection.poll(timeout):
        connection.close()
        raise EvaluatorProtocolError("isolated evaluator failed to become ready")
    try:
        raw = connection.recv_bytes(_MAX_FRAME_BYTES)
    except (EOFError, OSError) as exc:
        connection.close()
        raise EvaluatorProtocolError("isolated evaluator failed during startup") from exc
    return _validate_ready(raw, capability, session_id)


def start_isolated_evaluator(
    run_dir: str | os.PathLike[str],
    *,
    events: Sequence[HiddenEvent],
    context: int,
    causal_schema: CausalPacketSchema,
    split: SealedSplitProvenance,
    registry: CAPActionRegistry,
    packet_kind: PacketKind,
    allowed_policy_hashes: Sequence[str],
    normalization: Mapping[str, Any] | None = None,
    allowed_conditions: Mapping[str, Any] | None = None,
    train_error_summaries: Mapping[str, Any] | None = None,
    diagnostic_bins: Mapping[str, Any] | None = None,
    formal_generation: FormalGenerationBinding | None = None,
    start_method: str = "spawn",
    timeout: float = 10.0,
    _fault_after_inflight: str | None = None,
    _fault_after_completed: str | None = None,
) -> tuple[EvaluatorSupervisor, EvaluatorClient]:
    """Launch an evaluator and return separate trusted/untrusted handles.

    The caller is the trusted launcher and therefore necessarily supplies the
    hidden stream.  Prediction code must receive only the returned client.
    ``run_dir`` must already be the safe directory created by ``CAPAccuracyRun``.
    """

    root = Path(run_dir)
    if not root.exists() or root.is_symlink() or not root.is_dir():
        raise EvaluatorProtocolError("CAPAccuracyRun must create the evaluator run directory first")
    if _fault_after_inflight is not None and _fault_after_inflight not in _OPERATIONS:
        raise EvaluatorProtocolError("unknown evaluator fault-injection operation")
    if _fault_after_completed is not None and _fault_after_completed not in _OPERATIONS:
        raise EvaluatorProtocolError("unknown completed fault-injection operation")
    event_payloads = _event_launch_payloads(events)
    policy_hashes = tuple(
        _require_hash(value, "allowed_policy_hash") for value in allowed_policy_hashes
    )
    if not policy_hashes or len(policy_hashes) != len(set(policy_hashes)):
        raise EvaluatorProtocolError(
            "isolated evaluator requires a non-empty unique frozen policy-hash authority"
        )
    _verify_formal_launch(
        formal_generation,
        run_dir=root,
        context=context,
        event_count=len(event_payloads),
        split=split,
        registry=registry,
        allowed_policy_hashes=policy_hashes,
    )
    process_context = multiprocessing.get_context(start_method)
    parent_connection, child_connection = process_context.Pipe(duplex=True)
    capability = secrets.token_bytes(32)
    state_key = secrets.token_bytes(32)
    session_id = secrets.token_hex(32)
    normalized = dict(normalization or {})
    conditions = dict(allowed_conditions or {})
    train = dict(train_error_summaries or {})
    diagnostics = dict(diagnostic_bins or {})

    # Construct a temporary supervisor so the same spawn path is used for
    # initial launch and restart.  It retains no hidden events.
    placeholder_process = process_context.Process()
    supervisor = EvaluatorSupervisor(
        placeholder_process,
        process_context,
        capability=capability,
        state_key=state_key,
        session_id=session_id,
        run_dir=root,
        context_length=context,
        causal_schema=causal_schema,
        split=split,
        registry=registry,
        packet_kind=packet_kind,
        allowed_policy_hashes=policy_hashes,
        normalization=normalized,
        allowed_conditions=conditions,
        train_error_summaries=train,
        diagnostic_bins=diagnostics,
        formal_generation=formal_generation,
        fault_after_inflight=_fault_after_inflight,
        fault_after_completed=_fault_after_completed,
    )
    process = supervisor._spawn(
        child_connection,
        event_payloads=event_payloads,
        resume=False,
        fault_after_inflight=_fault_after_inflight,
        fault_after_completed=_fault_after_completed,
    )
    supervisor._process = process
    child_connection.close()
    try:
        evaluator_pid = _await_ready(parent_connection, capability, session_id, timeout)
    except Exception:
        parent_connection.close()
        supervisor.close()
        raise
    client = EvaluatorClient(
        parent_connection,
        capability=capability,
        session_id=session_id,
        causal_schema=causal_schema,
        split=split,
        registry=registry,
        packet_kind=packet_kind,
        normalization=normalized,
        allowed_conditions=conditions,
        train_error_summaries=train,
        diagnostic_bins=diagnostics,
        formal_generation=formal_generation,
        evaluator_pid=evaluator_pid,
    )
    try:
        client.bootstrap()
    except Exception:
        client.close()
        supervisor.close()
        raise
    return supervisor, client
