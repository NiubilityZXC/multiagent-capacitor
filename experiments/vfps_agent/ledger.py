"""Secure canonical JSONL ledgers for VFPS mock attempts and commits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import math
import os
from pathlib import Path
import stat
from typing import Any, Mapping

import fcntl

from .canonical import (
    canonical_bytes,
    canonical_sha256,
    scan_forbidden_proxies,
    strict_json_loads,
    to_primitive,
)
from .contracts import (
    ArmId,
    AttemptResult,
    AttemptStart,
    AttemptStatus,
    ClosedErrorCode,
    CommitDisposition,
    CommitReason,
    ExecutionState,
    KeyMaturity,
    MaturityState,
    PlannedKeyExecution,
    PredictionCommit,
    ProtocolId,
    UsageStatus,
)


class LedgerIntegrityError(RuntimeError):
    """Raised on any ambiguous, unsafe, or tampered ledger state."""


class LedgerKind(str, Enum):
    ATTEMPT = "attempt"
    PREDICTION = "prediction"
    ACCESS = "access"
    CHECKPOINT = "checkpoint"
    EXECUTION = "execution"
    MATURITY = "maturity"


@dataclass(frozen=True, slots=True)
class VerificationReport:
    ledger_kind: LedgerKind
    record_count: int
    final_record_hash: str
    sealed: bool
    incomplete_attempt_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "UNKNOWN_ATTEMPTS" if self.incomplete_attempt_ids else "PASS"


_ATTEMPT_START_KEYS = frozenset(
    {
        "attempt_id", "policy_hash", "origin_hash", "packet_hash", "arm",
        "protocol", "physical_slot", "requested_tokens", "deadline_unix_ms",
        "started_unix_ms",
    }
)
_ATTEMPT_RESULT_KEYS = frozenset(
    {
        "attempt_id", "status", "completed_unix_ms", "usage_status",
        "input_tokens", "output_tokens", "provider_response_id_hash",
        "error_code", "observed_model_hash", "late", "started_record_hash",
    }
)
_PREDICTION_COMMIT_KEYS = frozenset(
    {
        "commit_id", "attempt_id", "started_record_hash", "policy_hash",
        "origin_hash", "packet_hash", "disposition", "prediction",
        "prediction_hash", "committed_unix_ms", "reason_code",
        "late_response_ignored",
    }
)
_ACCESS_KEYS = frozenset(
    {
        "schema_version", "phase", "revealed_event_index", "observation_hash",
        "checkpoint_record_hash", "commit_id",
    }
)
_CHECKPOINT_KEYS = frozenset(
    {
        "schema_version", "attempt_id", "commit_id", "policy_hash",
        "origin_hash", "origin_event_index", "packet_hash",
        "attempt_final_record_hash", "prediction_record_hash",
        "execution_record_hashes", "planned_key_count",
    }
)
_EXECUTION_KEYS = frozenset(
    {"schema_version", "commit_id", "prediction_record_hash", "key_execution"}
)
_KEY_EXECUTION_KEYS = frozenset(
    {
        "key_token", "execution_state", "forecast_status", "forecast_hash",
        "selected_action_hash", "forced_rul_na", "active_coverage_eligible",
    }
)
_MATURITY_KEYS = frozenset(
    {"schema_version", "commit_id", "label_event_index", "key_maturity", "label"}
)
_KEY_MATURITY_KEYS = frozenset(
    {"key_token", "maturity_state", "execution_record_hash", "label_hash"}
)


def _require_exact_payload_keys(
    payload: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    if set(payload) != expected:
        raise LedgerIntegrityError(f"{label} payload schema mismatch")


def _require_sha256_text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise LedgerIntegrityError(f"{label} must be a lowercase SHA-256")
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LedgerIntegrityError(f"{label} must be a non-negative integer")
    return value


def _directory_fsync(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _secure_create(path: Path) -> int:
    if not path.parent.exists() or not path.parent.is_dir():
        raise FileNotFoundError("ledger parent directory must already exist")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except (FileExistsError, OSError) as exc:
        raise LedgerIntegrityError("refusing symlink or pre-existing output") from exc
    _directory_fsync(path.parent)
    return descriptor


def _secure_read(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise LedgerIntegrityError("required ledger artifact is missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise LedgerIntegrityError("ledger artifact must be a regular non-symlink file")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise LedgerIntegrityError("unable to securely open ledger artifact") from exc
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


def _secure_open_append(path: Path) -> int:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise LedgerIntegrityError("required resume ledger is missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise LedgerIntegrityError("resume ledger must be a regular non-symlink file")
    flags = os.O_WRONLY | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        return os.open(path, flags)
    except OSError as exc:
        raise LedgerIntegrityError("unable to securely resume ledger") from exc


def _decode_lines(ledger_bytes: bytes) -> tuple[dict[str, Any], ...]:
    if ledger_bytes and not ledger_bytes.endswith(b"\n"):
        raise LedgerIntegrityError("JSONL ledger must end with a newline")
    records: list[dict[str, Any]] = []
    for raw_line in ledger_bytes.splitlines():
        try:
            record = strict_json_loads(raw_line)
        except Exception as exc:
            raise LedgerIntegrityError("ledger contains invalid strict JSON") from exc
        if not isinstance(record, dict):
            raise LedgerIntegrityError("ledger record must be an object")
        records.append(record)
    return tuple(records)


class CanonicalJSONLLedger:
    """Append-only, fsync-before-return ledger with a SHA-256 record chain."""

    _RECORD_KEYS = frozenset(
        {"schema_version", "ledger_kind", "sequence", "event", "previous_record_hash", "payload", "record_hash"}
    )

    def __init__(
        self,
        path: str | os.PathLike[str],
        ledger_kind: LedgerKind,
        *,
        resume: bool = False,
    ) -> None:
        self.path = Path(path)
        self.ledger_kind = ledger_kind
        existing = self.path.exists()
        if existing and not resume:
            raise LedgerIntegrityError("refusing symlink or pre-existing output")
        descriptor = _secure_open_append(self.path) if existing else _secure_create(self.path)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(descriptor)
            raise LedgerIntegrityError("ledger is locked by another writer") from exc
        self._stream = os.fdopen(descriptor, "ab", buffering=0)
        self._sequence = 0
        self._previous_hash = "0" * 64
        self._sealed = False
        self._closed = False
        self._started: dict[str, str] = {}
        self._finished: set[str] = set()
        self._committed: set[str] = set()
        self._execution_keys: set[tuple[str, str]] = set()
        self._maturity_keys: set[tuple[str, str]] = set()
        if existing:
            try:
                verify_ledger(self.path, expected_kind=self.ledger_kind)
                records = _decode_lines(_secure_read(self.path))
                self._sequence = len(records)
                self._previous_hash = records[-1]["record_hash"] if records else "0" * 64
                for record in records:
                    payload = record["payload"]
                    event = record["event"]
                    if self.ledger_kind is LedgerKind.ATTEMPT:
                        attempt_id = payload["attempt_id"]
                        if event == "STARTED":
                            self._started[attempt_id] = record["record_hash"]
                        else:
                            self._finished.add(attempt_id)
                    elif self.ledger_kind is LedgerKind.PREDICTION:
                        self._committed.add(payload["attempt_id"])
                    elif self.ledger_kind is LedgerKind.EXECUTION:
                        self._execution_keys.add((payload["commit_id"], payload["key_execution"]["key_token"]))
                    elif self.ledger_kind is LedgerKind.MATURITY:
                        self._maturity_keys.add((payload["commit_id"], payload["key_maturity"]["key_token"]))
            except Exception:
                self.close()
                raise

    def __enter__(self) -> "CanonicalJSONLLedger":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @property
    def record_count(self) -> int:
        return self._sequence

    @property
    def final_record_hash(self) -> str:
        return self._previous_hash

    def _append(self, event: str, payload: Mapping[str, Any]) -> str:
        if self._closed or self._sealed:
            raise LedgerIntegrityError("cannot append to closed or sealed ledger")
        if not event or not event.replace("_", "").isalnum() or event.upper() != event:
            raise ValueError("ledger event must be an uppercase token")
        primitive = to_primitive(payload)
        scan_forbidden_proxies(primitive)
        body = {
            "schema_version": "VFPSCanonicalJSONL.v1",
            "ledger_kind": self.ledger_kind.value,
            "sequence": self._sequence,
            "event": event,
            "previous_record_hash": self._previous_hash,
            "payload": primitive,
        }
        record_hash = canonical_sha256(body)
        record = dict(body)
        record["record_hash"] = record_hash
        try:
            self._stream.write(canonical_bytes(record) + b"\n")
            self._stream.flush()
            os.fsync(self._stream.fileno())
        except OSError as exc:
            raise LedgerIntegrityError("durable ledger append failed") from exc
        self._sequence += 1
        self._previous_hash = record_hash
        return record_hash

    def append_started(self, attempt: AttemptStart) -> str:
        if self.ledger_kind is not LedgerKind.ATTEMPT:
            raise LedgerIntegrityError("STARTED records belong only in the attempt ledger")
        if attempt.attempt_id in self._started:
            raise LedgerIntegrityError("duplicate attempt STARTED record")
        record_hash = self._append("STARTED", to_primitive(attempt))
        self._started[attempt.attempt_id] = record_hash
        return record_hash

    def append_finished(self, started_record_hash: str, result: AttemptResult) -> str:
        if self.ledger_kind is not LedgerKind.ATTEMPT:
            raise LedgerIntegrityError("FINISHED records belong only in the attempt ledger")
        expected = self._started.get(result.attempt_id)
        if expected is None or expected != started_record_hash:
            raise LedgerIntegrityError("FINISHED does not reference its STARTED record")
        if result.attempt_id in self._finished:
            raise LedgerIntegrityError("attempt already has a FINISHED record")
        payload = dict(to_primitive(result))
        payload["started_record_hash"] = started_record_hash
        record_hash = self._append("FINISHED", payload)
        self._finished.add(result.attempt_id)
        return record_hash

    def append_prediction(self, commit: PredictionCommit) -> str:
        if self.ledger_kind is not LedgerKind.PREDICTION:
            raise LedgerIntegrityError("prediction commits belong only in the prediction ledger")
        if commit.attempt_id in self._committed:
            raise LedgerIntegrityError("late or duplicate result cannot overwrite a prediction commit")
        record_hash = self._append("COMMITTED", to_primitive(commit))
        self._committed.add(commit.attempt_id)
        return record_hash

    def append_access(self, payload: Mapping[str, Any]) -> str:
        if self.ledger_kind is not LedgerKind.ACCESS:
            raise LedgerIntegrityError("access records belong only in the access ledger")
        _typed_access(payload)
        return self._append("ACCESSED", payload)

    def append_checkpoint(self, payload: Mapping[str, Any]) -> str:
        if self.ledger_kind is not LedgerKind.CHECKPOINT:
            raise LedgerIntegrityError("checkpoint records belong only in the checkpoint ledger")
        _typed_checkpoint(payload)
        return self._append("CHECKPOINT", payload)

    def append_execution(self, payload: Mapping[str, Any]) -> str:
        if self.ledger_kind is not LedgerKind.EXECUTION:
            raise LedgerIntegrityError("execution rows belong only in the execution ledger")
        primitive = to_primitive(payload)
        key = _typed_execution(primitive)
        if key in self._execution_keys:
            raise LedgerIntegrityError("duplicate planned-key execution row")
        record_hash = self._append("EXECUTED", primitive)
        self._execution_keys.add(key)
        return record_hash

    def append_maturity(self, payload: Mapping[str, Any]) -> str:
        if self.ledger_kind is not LedgerKind.MATURITY:
            raise LedgerIntegrityError("maturity rows belong only in the maturity ledger")
        primitive = to_primitive(payload)
        key = _typed_maturity(primitive)
        if key in self._maturity_keys:
            raise LedgerIntegrityError("duplicate planned-key maturity row")
        record_hash = self._append("MATURED", primitive)
        self._maturity_keys.add(key)
        return record_hash

    def seal(self, seal_path: str | os.PathLike[str]) -> str:
        if self._closed or self._sealed:
            raise LedgerIntegrityError("ledger is already closed or sealed")
        self._stream.flush()
        os.fsync(self._stream.fileno())
        ledger_bytes = _secure_read(self.path)
        seal_body = {
            "schema_version": "VFPSLedgerSeal.v1",
            "ledger_kind": self.ledger_kind.value,
            "record_count": self._sequence,
            "final_record_hash": self._previous_hash,
            "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        }
        seal_hash = canonical_sha256(seal_body)
        seal_record = dict(seal_body)
        seal_record["seal_hash"] = seal_hash
        path = Path(seal_path)
        descriptor = _secure_create(path)
        try:
            payload = canonical_bytes(seal_record)
            offset = 0
            while offset < len(payload):
                written = os.write(descriptor, payload[offset:])
                if written <= 0:
                    raise LedgerIntegrityError("short seal write")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _directory_fsync(path.parent)
        self._sealed = True
        return seal_hash

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


def _typed_attempt_start(payload: Mapping[str, Any]) -> AttemptStart:
    _require_exact_payload_keys(payload, _ATTEMPT_START_KEYS, "STARTED")
    try:
        return AttemptStart(
            attempt_id=payload["attempt_id"],
            policy_hash=payload["policy_hash"],
            origin_hash=payload["origin_hash"],
            packet_hash=payload["packet_hash"],
            arm=ArmId(payload["arm"]),
            protocol=ProtocolId(payload["protocol"]),
            physical_slot=payload["physical_slot"],
            requested_tokens=payload["requested_tokens"],
            deadline_unix_ms=payload["deadline_unix_ms"],
            started_unix_ms=payload["started_unix_ms"],
        )
    except Exception as exc:
        raise LedgerIntegrityError("invalid typed STARTED payload") from exc


def _typed_attempt_result(payload: Mapping[str, Any]) -> AttemptResult:
    _require_exact_payload_keys(payload, _ATTEMPT_RESULT_KEYS, "FINISHED")
    try:
        error = payload.get("error_code")
        return AttemptResult(
            attempt_id=payload["attempt_id"],
            status=AttemptStatus(payload["status"]),
            completed_unix_ms=payload["completed_unix_ms"],
            usage_status=UsageStatus(payload["usage_status"]),
            input_tokens=payload.get("input_tokens"),
            output_tokens=payload.get("output_tokens"),
            provider_response_id_hash=payload.get("provider_response_id_hash"),
            error_code=ClosedErrorCode(error) if error is not None else None,
            observed_model_hash=payload.get("observed_model_hash"),
            late=payload.get("late", False),
        )
    except Exception as exc:
        raise LedgerIntegrityError("invalid typed FINISHED payload") from exc


def _typed_prediction_commit(payload: Mapping[str, Any]) -> PredictionCommit:
    _require_exact_payload_keys(payload, _PREDICTION_COMMIT_KEYS, "prediction commit")
    try:
        return PredictionCommit(
            commit_id=payload["commit_id"],
            attempt_id=payload["attempt_id"],
            started_record_hash=payload["started_record_hash"],
            policy_hash=payload["policy_hash"],
            origin_hash=payload["origin_hash"],
            packet_hash=payload["packet_hash"],
            disposition=CommitDisposition(payload["disposition"]),
            prediction=payload["prediction"],
            prediction_hash=payload["prediction_hash"],
            committed_unix_ms=payload["committed_unix_ms"],
            reason_code=CommitReason(payload["reason_code"]),
            late_response_ignored=payload.get("late_response_ignored", False),
        )
    except Exception as exc:
        raise LedgerIntegrityError("invalid typed prediction commit") from exc


def _typed_access(payload: Mapping[str, Any]) -> int:
    _require_exact_payload_keys(payload, _ACCESS_KEYS, "access")
    if payload["schema_version"] != "CAPEventAccess.v1":
        raise LedgerIntegrityError("unknown access payload schema")
    index = _require_nonnegative_int(payload["revealed_event_index"], "revealed_event_index")
    _require_sha256_text(payload["observation_hash"], "observation_hash")
    phase = payload["phase"]
    checkpoint = payload["checkpoint_record_hash"]
    commit = payload["commit_id"]
    if phase == "BOOTSTRAP":
        if checkpoint is not None or commit is not None:
            raise LedgerIntegrityError("bootstrap access cannot claim a prediction")
    elif phase == "POST_COMMIT":
        _require_sha256_text(checkpoint, "checkpoint_record_hash")
        _require_sha256_text(commit, "commit_id")
    else:
        raise LedgerIntegrityError("unknown access phase")
    return index


def _typed_checkpoint(payload: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    _require_exact_payload_keys(payload, _CHECKPOINT_KEYS, "checkpoint")
    if payload["schema_version"] != "CAPOriginCheckpoint.v1":
        raise LedgerIntegrityError("unknown checkpoint payload schema")
    _require_sha256_text(payload["attempt_id"], "attempt_id")
    commit_id = _require_sha256_text(payload["commit_id"], "commit_id")
    for field in (
        "policy_hash",
        "origin_hash",
        "packet_hash",
        "attempt_final_record_hash",
        "prediction_record_hash",
    ):
        _require_sha256_text(payload[field], field)
    _require_nonnegative_int(payload["origin_event_index"], "origin_event_index")
    count = _require_nonnegative_int(payload["planned_key_count"], "planned_key_count")
    references = payload["execution_record_hashes"]
    if not isinstance(references, list) or count < 1 or len(references) != count:
        raise LedgerIntegrityError("checkpoint execution reference count mismatch")
    key_tokens: list[str] = []
    for reference in references:
        if not isinstance(reference, Mapping) or set(reference) != {"key_token", "record_hash"}:
            raise LedgerIntegrityError("checkpoint execution reference schema mismatch")
        key_token = reference["key_token"]
        if not isinstance(key_token, str) or not key_token:
            raise LedgerIntegrityError("checkpoint key token must be non-empty")
        _require_sha256_text(reference["record_hash"], "execution record_hash")
        key_tokens.append(key_token)
    if key_tokens != sorted(key_tokens) or len(key_tokens) != len(set(key_tokens)):
        raise LedgerIntegrityError("checkpoint key references must be unique and canonical")
    return commit_id, tuple(key_tokens)


def _typed_execution(payload: Mapping[str, Any]) -> tuple[str, str]:
    _require_exact_payload_keys(payload, _EXECUTION_KEYS, "execution")
    if payload["schema_version"] != "CAPKeyExecutionRecord.v1":
        raise LedgerIntegrityError("unknown execution payload schema")
    commit_id = _require_sha256_text(payload["commit_id"], "commit_id")
    _require_sha256_text(payload["prediction_record_hash"], "prediction_record_hash")
    item = payload["key_execution"]
    if not isinstance(item, Mapping):
        raise LedgerIntegrityError("key_execution must be an object")
    _require_exact_payload_keys(item, _KEY_EXECUTION_KEYS, "key execution")
    try:
        execution = PlannedKeyExecution(
            key_token=item["key_token"],
            execution_state=ExecutionState(item["execution_state"]),
            forecast_status=item["forecast_status"],
            forecast_hash=item["forecast_hash"],
            selected_action_hash=item["selected_action_hash"],
            forced_rul_na=item["forced_rul_na"],
            active_coverage_eligible=item["active_coverage_eligible"],
        )
    except Exception as exc:
        raise LedgerIntegrityError("invalid typed execution row") from exc
    return commit_id, execution.key_token


def _typed_maturity(payload: Mapping[str, Any]) -> tuple[str, str]:
    _require_exact_payload_keys(payload, _MATURITY_KEYS, "maturity")
    if payload["schema_version"] != "CAPKeyMaturityRecord.v1":
        raise LedgerIntegrityError("unknown maturity payload schema")
    commit_id = _require_sha256_text(payload["commit_id"], "commit_id")
    label_event_index = _require_nonnegative_int(payload["label_event_index"], "label_event_index")
    item = payload["key_maturity"]
    if not isinstance(item, Mapping):
        raise LedgerIntegrityError("key_maturity must be an object")
    _require_exact_payload_keys(item, _KEY_MATURITY_KEYS, "key maturity")
    try:
        maturity = KeyMaturity(
            key_token=item["key_token"],
            maturity_state=MaturityState(item["maturity_state"]),
            execution_record_hash=item["execution_record_hash"],
            label_hash=item["label_hash"],
        )
    except Exception as exc:
        raise LedgerIntegrityError("invalid typed maturity row") from exc
    label = payload["label"]
    if maturity.maturity_state is MaturityState.MATURED:
        if not isinstance(label, Mapping) or set(label) != {
            "target", "unit", "event_index", "observed_value"
        }:
            raise LedgerIntegrityError("matured label schema mismatch")
        if label["event_index"] != label_event_index:
            raise LedgerIntegrityError("matured label event index mismatch")
        if not isinstance(label["target"], str) or not label["target"]:
            raise LedgerIntegrityError("matured target must be non-empty")
        if not isinstance(label["unit"], str) or not label["unit"]:
            raise LedgerIntegrityError("matured unit must be non-empty")
        observed = label["observed_value"]
        if (
            isinstance(observed, bool)
            or not isinstance(observed, (int, float))
            or not math.isfinite(float(observed))
        ):
            raise LedgerIntegrityError("matured observed value must be finite")
        if canonical_sha256(label) != maturity.label_hash:
            raise LedgerIntegrityError("matured label hash mismatch")
    elif label is not None:
        raise LedgerIntegrityError("NEVER_MATURED cannot carry a label")
    return commit_id, maturity.key_token


def verify_ledger(
    ledger_path: str | os.PathLike[str],
    *,
    expected_kind: LedgerKind,
    seal_path: str | os.PathLike[str] | None = None,
) -> VerificationReport:
    """Verify canonical bytes, record chain, references, and optional seal.

    Any ambiguity raises ``LedgerIntegrityError``.  A crash-left STARTED record
    is not erased: it is reported as an incomplete/unknown physical attempt.
    """

    ledger_bytes = _secure_read(Path(ledger_path))
    if ledger_bytes and not ledger_bytes.endswith(b"\n"):
        raise LedgerIntegrityError("JSONL ledger must end with a newline")
    lines = ledger_bytes.splitlines()
    previous = "0" * 64
    started: dict[str, str] = {}
    finished: set[str] = set()
    committed: set[str] = set()
    executed: set[tuple[str, str]] = set()
    matured: set[tuple[str, str]] = set()
    for sequence, raw_line in enumerate(lines):
        try:
            record = strict_json_loads(raw_line)
        except Exception as exc:
            raise LedgerIntegrityError("ledger contains invalid strict JSON") from exc
        if not isinstance(record, dict) or set(record) != CanonicalJSONLLedger._RECORD_KEYS:
            raise LedgerIntegrityError("ledger record schema mismatch")
        if canonical_bytes(record) != raw_line:
            raise LedgerIntegrityError("ledger line is not canonical JSON")
        if record["schema_version"] != "VFPSCanonicalJSONL.v1":
            raise LedgerIntegrityError("unknown ledger schema")
        if record["ledger_kind"] != expected_kind.value:
            raise LedgerIntegrityError("ledger kind mismatch")
        if record["sequence"] != sequence or record["previous_record_hash"] != previous:
            raise LedgerIntegrityError("ledger sequence or previous-hash chain is broken")
        body = {key: value for key, value in record.items() if key != "record_hash"}
        if canonical_sha256(body) != record["record_hash"]:
            raise LedgerIntegrityError("ledger record hash mismatch")
        payload = record["payload"]
        if not isinstance(payload, dict):
            raise LedgerIntegrityError("ledger payload must be an object")
        try:
            scan_forbidden_proxies(payload)
        except Exception as exc:
            raise LedgerIntegrityError("ledger payload contains a forbidden proxy") from exc
        event = record["event"]
        if expected_kind is LedgerKind.ATTEMPT:
            attempt_id = payload.get("attempt_id")
            if not isinstance(attempt_id, str) or not attempt_id:
                raise LedgerIntegrityError("attempt record lacks attempt_id")
            if event == "STARTED":
                if attempt_id in started:
                    raise LedgerIntegrityError("duplicate STARTED record")
                _typed_attempt_start(payload)
                started[attempt_id] = record["record_hash"]
            elif event == "FINISHED":
                if attempt_id in finished or payload.get("started_record_hash") != started.get(attempt_id):
                    raise LedgerIntegrityError("orphaned or duplicate FINISHED record")
                _typed_attempt_result(payload)
                finished.add(attempt_id)
            else:
                raise LedgerIntegrityError("unexpected attempt ledger event")
        elif expected_kind is LedgerKind.PREDICTION:
            if event != "COMMITTED":
                raise LedgerIntegrityError("unexpected prediction ledger event")
            attempt_id = payload.get("attempt_id")
            if not isinstance(attempt_id, str) or attempt_id in committed:
                raise LedgerIntegrityError("duplicate or invalid prediction commit")
            _typed_prediction_commit(payload)
            committed.add(attempt_id)
        elif expected_kind is LedgerKind.ACCESS:
            if event != "ACCESSED":
                raise LedgerIntegrityError("unexpected access ledger event")
            _typed_access(payload)
        elif expected_kind is LedgerKind.CHECKPOINT:
            if event != "CHECKPOINT":
                raise LedgerIntegrityError("unexpected checkpoint ledger event")
            _typed_checkpoint(payload)
        elif expected_kind is LedgerKind.EXECUTION:
            if event != "EXECUTED":
                raise LedgerIntegrityError("unexpected execution ledger event")
            key = _typed_execution(payload)
            if key in executed:
                raise LedgerIntegrityError("duplicate execution row")
            executed.add(key)
        elif expected_kind is LedgerKind.MATURITY:
            if event != "MATURED":
                raise LedgerIntegrityError("unexpected maturity ledger event")
            key = _typed_maturity(payload)
            if key in matured:
                raise LedgerIntegrityError("duplicate maturity row")
            matured.add(key)
        previous = record["record_hash"]

    sealed = seal_path is not None
    if seal_path is not None:
        seal_bytes = _secure_read(Path(seal_path))
        try:
            seal = strict_json_loads(seal_bytes)
        except Exception as exc:
            raise LedgerIntegrityError("invalid ledger seal") from exc
        if not isinstance(seal, dict) or canonical_bytes(seal) != seal_bytes:
            raise LedgerIntegrityError("seal is not canonical JSON")
        required = {
            "schema_version", "ledger_kind", "record_count", "final_record_hash",
            "ledger_sha256", "seal_hash",
        }
        if set(seal) != required:
            raise LedgerIntegrityError("seal schema mismatch")
        seal_body = {key: value for key, value in seal.items() if key != "seal_hash"}
        if canonical_sha256(seal_body) != seal["seal_hash"]:
            raise LedgerIntegrityError("seal hash mismatch")
        if (
            seal["schema_version"] != "VFPSLedgerSeal.v1"
            or seal["ledger_kind"] != expected_kind.value
            or seal["record_count"] != len(lines)
            or seal["final_record_hash"] != previous
            or seal["ledger_sha256"] != hashlib.sha256(ledger_bytes).hexdigest()
        ):
            raise LedgerIntegrityError("seal does not bind this ledger")

    return VerificationReport(
        ledger_kind=expected_kind,
        record_count=len(lines),
        final_record_hash=previous,
        sealed=sealed,
        incomplete_attempt_ids=tuple(sorted(set(started) - finished)),
    )


def read_verified_ledger_records(
    ledger_path: str | os.PathLike[str],
    *,
    expected_kind: LedgerKind,
    seal_path: str | os.PathLike[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return records only after the chain, typed payloads, and optional seal pass."""

    verify_ledger(ledger_path, expected_kind=expected_kind, seal_path=seal_path)
    return _decode_lines(_secure_read(Path(ledger_path)))
