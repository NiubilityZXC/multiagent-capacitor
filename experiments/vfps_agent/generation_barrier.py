"""Honest-launcher generation barriers for the local CAP evaluation harness.

This module is deliberately an integrity/workflow layer, not a permission
boundary.  It freezes one Cartesian fold-by-arm plan, verifies that every
planned run has completed and sealed its prediction phase without producing
labels, and only then materializes deterministic per-cell finalize permits.
The deterministic permits are intentionally HMAC-free; they detect mix-ups
and tampering but do not by themselves authorize a caller against a malicious
same-UID or shared-filesystem actor. Formal evaluator integration first
requires one generation-wide HMAC authorization over the exact cell/session
set and frozen statistics executable, then wraps that record and the cell
permit in the evaluator state-key HMAC before any label-bearing FINALIZE is
accepted.

All generation artifacts are canonical JSON written by an exclusive,
fsync-backed atomic link.  Scientific run verification is delegated to the
existing prediction, access, and complete-run verifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes, canonical_sha256, strict_json_loads
from .ledger import LedgerKind, read_verified_ledger_records
from .replay import verify_access_barrier, verify_complete_run
from .runner import CAPRunPaths, verify_prediction_phase


_HEX64 = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


# This registry is intentionally independent of ``contracts.ArmId``.  The
# latter describes executable M2 one-call policies, whereas a formal joint
# generation must also reserve the two four-call controls and the single Plan
# A architecture arm before those executors are admitted by later gates.
CANONICAL_GENERATION_ARM_IDS = tuple(
    sorted(
        (
            "N0",
            "D1-RAW",
            "D1-PACKET",
            "H1",
            "RF1",
            "RC1",
            "ACT1",
            "IF1",
            "ENUM-ACTION",
            "D4-H",
            "D4-X",
            "ARCH1",
        )
    )
)
_DETERMINISTIC_GENERATION_ARMS = frozenset({"N0", "ENUM-ACTION"})
_FOUR_SLOT_GENERATION_ARMS = frozenset({"D4-H", "D4-X", "ARCH1"})
_PHYSICAL_GENERATION_ARMS = frozenset(CANONICAL_GENERATION_ARM_IDS) - (
    _DETERMINISTIC_GENERATION_ARMS
)


class GenerationArmStatus(str, Enum):
    """Pre-result admission state frozen in the formal master plan."""

    ADMITTED = "ADMITTED"
    NA = "NA"
    BLOCKED = "BLOCKED"


class GenerationBarrierError(RuntimeError):
    """Raised when a frozen generation cannot advance without label access."""


def _require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise GenerationBarrierError(f"{label} must be lowercase SHA-256")
    return value


def _require_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise GenerationBarrierError(f"{label} is not a canonical identifier")
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GenerationBarrierError(f"{label} must be a non-negative integer")
    return value


def _normalize_run_dir(value: str | os.PathLike[str]) -> str:
    try:
        text = os.fspath(value)
    except TypeError as exc:
        raise GenerationBarrierError("run_dir must be path-like") from exc
    if not isinstance(text, str) or "\x00" in text:
        raise GenerationBarrierError("run_dir must be a text path without NUL")
    path = Path(text)
    if not path.is_absolute() or os.path.normpath(text) != text or ".." in path.parts:
        raise GenerationBarrierError("run_dir must be a normalized absolute path")
    return text


def generation_cell_id(generation_id: str, fold_id: str, arm_id: str) -> str:
    """Derive the immutable identity of one fold-by-arm generation cell."""

    return canonical_sha256(
        {
            "schema_version": "CAPGenerationCellIdentity.v1",
            "generation_id": _require_hash(generation_id, "generation_id"),
            "fold_id": _require_identifier(fold_id, "fold_id"),
            "arm_id": _require_identifier(arm_id, "arm_id"),
        }
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic_exclusive(path: Path, payload: Mapping[str, Any]) -> str:
    """Publish complete canonical bytes atomically without replacing a path."""

    parent = path.parent
    try:
        metadata = parent.lstat()
    except FileNotFoundError as exc:
        raise GenerationBarrierError("generation artifact directory is missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise GenerationBarrierError("generation artifact parent must be a regular directory")
    if path.exists() or path.is_symlink():
        raise GenerationBarrierError("refusing a pre-existing generation artifact")

    raw = canonical_bytes(dict(payload))
    temporary = parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    linked = False
    try:
        descriptor = os.open(temporary, flags, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise GenerationBarrierError("short generation artifact write")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise GenerationBarrierError("generation artifact appeared concurrently") from exc
        linked = True
        _fsync_directory(parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        _fsync_directory(parent)
    if not linked:  # pragma: no cover - defensive clarity after an OS failure
        raise GenerationBarrierError("generation artifact was not published")
    return hashlib.sha256(raw).hexdigest()


def _read_canonical_record(path: Path) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise GenerationBarrierError("required generation artifact is missing or unsafe") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise GenerationBarrierError("generation artifact must be a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
    finally:
        os.close(descriptor)
    try:
        record = strict_json_loads(raw)
    except Exception as exc:
        raise GenerationBarrierError("generation artifact is not strict JSON") from exc
    if not isinstance(record, dict) or canonical_bytes(record) != raw:
        raise GenerationBarrierError("generation artifact is not canonical JSON")
    return record


@dataclass(frozen=True, slots=True)
class FrozenGenerationCell:
    """One pre-label fold-by-arm binding in a frozen generation plan."""

    cell_id: str
    fold_id: str
    arm_id: str
    run_dir: str
    context: int
    expected_revealed_count: int
    expected_post_commit_reveal_count: int
    policy_hash: str
    split_hash: str
    registry_hash: str
    planned_manifest_hash: str

    def __post_init__(self) -> None:
        _require_hash(self.cell_id, "cell_id")
        _require_identifier(self.fold_id, "fold_id")
        _require_identifier(self.arm_id, "arm_id")
        object.__setattr__(self, "run_dir", _normalize_run_dir(self.run_dir))
        _require_nonnegative_int(self.context, "context")
        _require_nonnegative_int(self.expected_revealed_count, "expected_revealed_count")
        _require_nonnegative_int(
            self.expected_post_commit_reveal_count,
            "expected_post_commit_reveal_count",
        )
        if self.context < 1 or self.expected_revealed_count <= self.context:
            raise GenerationBarrierError("a generation cell requires a proper replay suffix")
        if (
            self.expected_post_commit_reveal_count
            != self.expected_revealed_count - self.context
        ):
            raise GenerationBarrierError("cell replay counts differ from context")
        for name in (
            "policy_hash",
            "split_hash",
            "registry_hash",
            "planned_manifest_hash",
        ):
            _require_hash(getattr(self, name), name)

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPFrozenGenerationCell.v1",
            "cell_id": self.cell_id,
            "fold_id": self.fold_id,
            "arm_id": self.arm_id,
            "run_dir": self.run_dir,
            "context": self.context,
            "expected_revealed_count": self.expected_revealed_count,
            "expected_post_commit_reveal_count": self.expected_post_commit_reveal_count,
            "policy_hash": self.policy_hash,
            "split_hash": self.split_hash,
            "registry_hash": self.registry_hash,
            "planned_manifest_hash": self.planned_manifest_hash,
        }

    @property
    def binding_hash(self) -> str:
        return canonical_sha256(self.payload())

    @classmethod
    def from_payload(cls, payload: Any) -> "FrozenGenerationCell":
        expected = {
            "schema_version",
            "cell_id",
            "fold_id",
            "arm_id",
            "run_dir",
            "context",
            "expected_revealed_count",
            "expected_post_commit_reveal_count",
            "policy_hash",
            "split_hash",
            "registry_hash",
            "planned_manifest_hash",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise GenerationBarrierError("generation cell schema mismatch")
        if payload["schema_version"] != "CAPFrozenGenerationCell.v1":
            raise GenerationBarrierError("generation cell version mismatch")
        return cls(**{key: payload[key] for key in expected - {"schema_version"}})


@dataclass(frozen=True, slots=True)
class FrozenGenerationArmAdmission:
    """One exact formal arm entry, including a mechanically frozen closure.

    ``physical_slots_per_origin`` describes the requested slot envelope even
    for ``NA``/``BLOCKED`` arms.  Consequently a later gate cannot quietly
    reinterpret a blocked four-call arm as a one-call arm or vice versa.
    """

    arm_id: str
    status: GenerationArmStatus
    reason_code: str
    requires_attested_ark: bool
    physical_slots_per_origin: int
    authorization_artifact_hash: str

    def __post_init__(self) -> None:
        _require_identifier(self.arm_id, "arm admission arm_id")
        if self.arm_id not in CANONICAL_GENERATION_ARM_IDS:
            raise GenerationBarrierError("arm admission is outside the canonical registry")
        if not isinstance(self.status, GenerationArmStatus):
            raise GenerationBarrierError("arm admission status is not typed")
        _require_identifier(self.reason_code, "arm admission reason_code")
        if not isinstance(self.requires_attested_ark, bool):
            raise GenerationBarrierError("requires_attested_ark must be Boolean")
        _require_nonnegative_int(
            self.physical_slots_per_origin, "physical_slots_per_origin"
        )
        _require_hash(self.authorization_artifact_hash, "authorization_artifact_hash")

        expected_attestation = self.arm_id in _PHYSICAL_GENERATION_ARMS
        expected_slots = (
            4
            if self.arm_id in _FOUR_SLOT_GENERATION_ARMS
            else 0
            if self.arm_id in _DETERMINISTIC_GENERATION_ARMS
            else 1
        )
        if (
            self.requires_attested_ark != expected_attestation
            or self.physical_slots_per_origin != expected_slots
        ):
            raise GenerationBarrierError(
                "arm admission transport/slot envelope differs from the canonical arm"
            )

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPFrozenGenerationArmAdmission.v1",
            "arm_id": self.arm_id,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "requires_attested_ark": self.requires_attested_ark,
            "physical_slots_per_origin": self.physical_slots_per_origin,
            "authorization_artifact_hash": self.authorization_artifact_hash,
        }

    @classmethod
    def from_payload(cls, payload: Any) -> "FrozenGenerationArmAdmission":
        expected = {
            "schema_version",
            "arm_id",
            "status",
            "reason_code",
            "requires_attested_ark",
            "physical_slots_per_origin",
            "authorization_artifact_hash",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise GenerationBarrierError("generation arm admission schema mismatch")
        if payload["schema_version"] != "CAPFrozenGenerationArmAdmission.v1":
            raise GenerationBarrierError("generation arm admission version mismatch")
        try:
            status = GenerationArmStatus(payload["status"])
        except (TypeError, ValueError) as exc:
            raise GenerationBarrierError("generation arm admission status is invalid") from exc
        return cls(
            arm_id=payload["arm_id"],
            status=status,
            reason_code=payload["reason_code"],
            requires_attested_ark=payload["requires_attested_ark"],
            physical_slots_per_origin=payload["physical_slots_per_origin"],
            authorization_artifact_hash=payload["authorization_artifact_hash"],
        )


@dataclass(frozen=True, slots=True)
class FrozenGenerationPlan:
    """Local plan or exact formal 11+ARCH1 master generation.

    Local plans remain available for offline component tests, but they cannot
    be attached to a formal evaluator.  ``bind_formal_generation`` accepts
    only ``formal_mode=True`` plans whose registry is exactly the canonical
    eleven Plan-B arms plus the unique ``ARCH1`` entry and whose root hashes
    are present.
    """

    generation_id: str
    fold_ids: tuple[str, ...]
    arm_ids: tuple[str, ...]
    cells: tuple[FrozenGenerationCell, ...]
    formal_mode: bool = False
    master_seal_hash: str | None = None
    human_approval_hash: str | None = None
    outcome_availability_hash: str | None = None
    statistics_executable_hash: str | None = None
    arm_admissions: tuple[FrozenGenerationArmAdmission, ...] = ()

    def __post_init__(self) -> None:
        _require_hash(self.generation_id, "generation_id")
        if not isinstance(self.fold_ids, tuple) or not isinstance(self.arm_ids, tuple):
            raise GenerationBarrierError("fold_ids and arm_ids must be tuples")
        if not isinstance(self.cells, tuple) or not isinstance(self.formal_mode, bool):
            raise GenerationBarrierError("generation cells/mode have the wrong type")
        if not self.fold_ids or not self.arm_ids:
            raise GenerationBarrierError("generation axes must be non-empty")
        for item in self.fold_ids:
            _require_identifier(item, "fold_id")
        for item in self.arm_ids:
            _require_identifier(item, "arm_id")
        if self.fold_ids != tuple(sorted(set(self.fold_ids))):
            raise GenerationBarrierError("fold_ids must be unique and canonical")
        if self.arm_ids != tuple(sorted(set(self.arm_ids))):
            raise GenerationBarrierError("arm_ids must be unique and canonical")
        if not all(isinstance(item, FrozenGenerationCell) for item in self.cells):
            raise GenerationBarrierError("generation plan contains an untyped cell")
        if self.cells != tuple(sorted(self.cells, key=lambda item: (item.fold_id, item.arm_id))):
            raise GenerationBarrierError("generation cells must be in canonical Cartesian order")

        if self.formal_mode:
            if self.arm_ids != CANONICAL_GENERATION_ARM_IDS:
                raise GenerationBarrierError(
                    "formal generation arm registry must be exact canonical 11+ARCH1"
                )
            if not isinstance(self.arm_admissions, tuple) or not all(
                isinstance(item, FrozenGenerationArmAdmission)
                for item in self.arm_admissions
            ):
                raise GenerationBarrierError("formal generation admissions are not typed")
            if tuple(item.arm_id for item in self.arm_admissions) != self.arm_ids:
                raise GenerationBarrierError(
                    "formal generation admissions must exactly follow the arm registry"
                )
            for name in (
                "master_seal_hash",
                "human_approval_hash",
                "outcome_availability_hash",
                "statistics_executable_hash",
            ):
                _require_hash(getattr(self, name), name)
            admitted_arm_ids = tuple(
                item.arm_id
                for item in self.arm_admissions
                if item.status is GenerationArmStatus.ADMITTED
            )
            if not admitted_arm_ids:
                raise GenerationBarrierError("formal generation has no admitted arm")
        else:
            if self.arm_admissions:
                raise GenerationBarrierError("local generation cannot carry formal admissions")
            if any(
                value is not None
                for value in (
                    self.master_seal_hash,
                    self.human_approval_hash,
                    self.outcome_availability_hash,
                    self.statistics_executable_hash,
                )
            ):
                raise GenerationBarrierError("local generation cannot carry formal root hashes")
            admitted_arm_ids = self.arm_ids

        expected_pairs = {
            (fold_id, arm_id)
            for fold_id in self.fold_ids
            for arm_id in admitted_arm_ids
        }
        actual_pairs = [(item.fold_id, item.arm_id) for item in self.cells]
        if len(actual_pairs) != len(set(actual_pairs)):
            raise GenerationBarrierError("generation contains a duplicate fold-by-arm cell")
        if set(actual_pairs) != expected_pairs:
            raise GenerationBarrierError("generation cells do not equal the Cartesian plan")
        if len({item.cell_id for item in self.cells}) != len(self.cells):
            raise GenerationBarrierError("generation contains a duplicate cell_id")
        if len({item.run_dir for item in self.cells}) != len(self.cells):
            raise GenerationBarrierError("generation cells must use distinct run directories")
        for item in self.cells:
            expected_id = generation_cell_id(
                self.generation_id, item.fold_id, item.arm_id
            )
            if item.cell_id != expected_id:
                raise GenerationBarrierError("generation cell_id differs from its axes")

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPFrozenGenerationPlan.v2",
            "generation_id": self.generation_id,
            "fold_ids": list(self.fold_ids),
            "arm_ids": list(self.arm_ids),
            "cells": [item.payload() for item in self.cells],
            "formal_mode": self.formal_mode,
            "master_seal_hash": self.master_seal_hash,
            "human_approval_hash": self.human_approval_hash,
            "outcome_availability_hash": self.outcome_availability_hash,
            "statistics_executable_hash": self.statistics_executable_hash,
            "arm_admissions": [item.payload() for item in self.arm_admissions],
        }

    @property
    def plan_hash(self) -> str:
        return canonical_sha256(self.payload())

    def cell_by_id(self, cell_id: str) -> FrozenGenerationCell:
        matches = [item for item in self.cells if item.cell_id == cell_id]
        if len(matches) != 1:
            raise GenerationBarrierError("cell_id is not exactly once in the frozen plan")
        return matches[0]

    def admission_by_arm(self, arm_id: str) -> FrozenGenerationArmAdmission | None:
        if not self.formal_mode:
            return None
        matches = [item for item in self.arm_admissions if item.arm_id == arm_id]
        if len(matches) != 1:
            raise GenerationBarrierError("formal arm admission is not exactly once")
        return matches[0]


def seal_generation_plan(path: str | os.PathLike[str], plan: FrozenGenerationPlan) -> str:
    """Durably publish a complete plan; all validation precedes filesystem writes."""

    if not isinstance(plan, FrozenGenerationPlan):
        raise GenerationBarrierError("plan must be a FrozenGenerationPlan")
    record = plan.payload()
    record["plan_hash"] = plan.plan_hash
    _write_atomic_exclusive(Path(path), record)
    return plan.plan_hash


def verify_generation_plan(path: str | os.PathLike[str]) -> FrozenGenerationPlan:
    record = _read_canonical_record(Path(path))
    expected = {
        "schema_version",
        "generation_id",
        "fold_ids",
        "arm_ids",
        "cells",
        "formal_mode",
        "master_seal_hash",
        "human_approval_hash",
        "outcome_availability_hash",
        "statistics_executable_hash",
        "arm_admissions",
        "plan_hash",
    }
    if set(record) != expected or record.get("schema_version") != "CAPFrozenGenerationPlan.v2":
        raise GenerationBarrierError("frozen generation plan schema mismatch")
    if not isinstance(record["fold_ids"], list) or not isinstance(record["arm_ids"], list):
        raise GenerationBarrierError("generation axes must be JSON lists")
    if not isinstance(record["cells"], list) or not isinstance(
        record["arm_admissions"], list
    ):
        raise GenerationBarrierError("generation cells/admissions must be JSON lists")
    plan = FrozenGenerationPlan(
        generation_id=record["generation_id"],
        fold_ids=tuple(record["fold_ids"]),
        arm_ids=tuple(record["arm_ids"]),
        cells=tuple(FrozenGenerationCell.from_payload(item) for item in record["cells"]),
        formal_mode=record["formal_mode"],
        master_seal_hash=record["master_seal_hash"],
        human_approval_hash=record["human_approval_hash"],
        outcome_availability_hash=record["outcome_availability_hash"],
        statistics_executable_hash=record["statistics_executable_hash"],
        arm_admissions=tuple(
            FrozenGenerationArmAdmission.from_payload(item)
            for item in record["arm_admissions"]
        ),
    )
    if record["plan_hash"] != plan.plan_hash:
        raise GenerationBarrierError("frozen generation plan hash mismatch")
    return plan


@dataclass(frozen=True, slots=True)
class FormalGenerationBinding:
    """Launch-time binding between one evaluator and one frozen generation cell.

    The paths and hashes become part of the evaluator launch HMAC.  The object
    contains no secret and does not itself authorize FINALIZE; an evaluator-
    owned authentication tag is still required by the formal process boundary.
    """

    plan_path: str
    barrier_path: str
    generation_id: str
    generation_plan_hash: str
    master_seal_hash: str
    human_approval_hash: str
    outcome_availability_hash: str
    statistics_executable_hash: str
    cell_id: str
    cell_binding_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_path", _normalize_run_dir(self.plan_path))
        object.__setattr__(self, "barrier_path", _normalize_run_dir(self.barrier_path))
        for name in (
            "generation_id",
            "generation_plan_hash",
            "master_seal_hash",
            "human_approval_hash",
            "outcome_availability_hash",
            "statistics_executable_hash",
            "cell_id",
            "cell_binding_hash",
        ):
            _require_hash(getattr(self, name), name)
        if self.plan_path == self.barrier_path:
            raise GenerationBarrierError("plan and prediction barrier paths must differ")

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPFormalGenerationBinding.v2",
            "plan_path": self.plan_path,
            "barrier_path": self.barrier_path,
            "generation_id": self.generation_id,
            "generation_plan_hash": self.generation_plan_hash,
            "master_seal_hash": self.master_seal_hash,
            "human_approval_hash": self.human_approval_hash,
            "outcome_availability_hash": self.outcome_availability_hash,
            "statistics_executable_hash": self.statistics_executable_hash,
            "cell_id": self.cell_id,
            "cell_binding_hash": self.cell_binding_hash,
        }


def bind_formal_generation(
    plan_path: str | os.PathLike[str],
    barrier_path: str | os.PathLike[str],
    *,
    cell_id: str,
    run_dir: str | os.PathLike[str],
) -> FormalGenerationBinding:
    """Create a non-secret formal binding after verifying the frozen plan."""

    normalized_plan_path = _normalize_run_dir(plan_path)
    normalized_barrier_path = _normalize_run_dir(barrier_path)
    normalized_run_dir = _normalize_run_dir(run_dir)
    plan = verify_generation_plan(normalized_plan_path)
    if not plan.formal_mode:
        raise GenerationBarrierError(
            "local/subset generation plans cannot bind a formal evaluator"
        )
    cell = plan.cell_by_id(cell_id)
    if cell.run_dir != normalized_run_dir:
        raise GenerationBarrierError("formal evaluator run differs from its frozen cell")
    return FormalGenerationBinding(
        plan_path=normalized_plan_path,
        barrier_path=normalized_barrier_path,
        generation_id=plan.generation_id,
        generation_plan_hash=plan.plan_hash,
        master_seal_hash=plan.master_seal_hash,
        human_approval_hash=plan.human_approval_hash,
        outcome_availability_hash=plan.outcome_availability_hash,
        statistics_executable_hash=plan.statistics_executable_hash,
        cell_id=cell.cell_id,
        cell_binding_hash=cell.binding_hash,
    )


def verify_formal_generation_binding(
    binding: FormalGenerationBinding,
    *,
    run_dir: str | os.PathLike[str],
) -> FrozenGenerationCell:
    """Re-open the plan and prove that a launch binding has not drifted."""

    if not isinstance(binding, FormalGenerationBinding):
        raise GenerationBarrierError("formal generation binding is not typed")
    plan = verify_generation_plan(binding.plan_path)
    cell = plan.cell_by_id(binding.cell_id)
    if (
        plan.generation_id != binding.generation_id
        or plan.plan_hash != binding.generation_plan_hash
        or plan.master_seal_hash != binding.master_seal_hash
        or plan.human_approval_hash != binding.human_approval_hash
        or plan.outcome_availability_hash != binding.outcome_availability_hash
        or plan.statistics_executable_hash != binding.statistics_executable_hash
        or cell.binding_hash != binding.cell_binding_hash
        or cell.run_dir != _normalize_run_dir(run_dir)
    ):
        raise GenerationBarrierError("formal generation binding differs from the frozen plan")
    return cell


@dataclass(frozen=True, slots=True)
class GenerationRunBinding:
    """Runtime path supplied for one already-frozen cell."""

    cell_id: str
    run_dir: str

    def __post_init__(self) -> None:
        _require_hash(self.cell_id, "cell_id")
        object.__setattr__(self, "run_dir", _normalize_run_dir(self.run_dir))


def _validated_bindings(
    plan: FrozenGenerationPlan,
    bindings: Sequence[GenerationRunBinding],
) -> dict[str, Path]:
    if not isinstance(bindings, Sequence) or isinstance(bindings, (str, bytes)):
        raise GenerationBarrierError("run bindings must be a sequence")
    typed = tuple(bindings)
    if not all(isinstance(item, GenerationRunBinding) for item in typed):
        raise GenerationBarrierError("run bindings contain an untyped item")
    ids = [item.cell_id for item in typed]
    if len(ids) != len(set(ids)):
        raise GenerationBarrierError("run bindings contain a duplicate cell")
    expected_ids = {item.cell_id for item in plan.cells}
    actual_ids = set(ids)
    if actual_ids != expected_ids:
        missing = len(expected_ids - actual_ids)
        extra = len(actual_ids - expected_ids)
        raise GenerationBarrierError(
            f"run bindings differ from the frozen cells (missing={missing}, extra={extra})"
        )
    result: dict[str, Path] = {}
    for binding in typed:
        cell = plan.cell_by_id(binding.cell_id)
        if binding.run_dir != cell.run_dir:
            raise GenerationBarrierError("runtime path differs from its frozen cell binding")
        result[binding.cell_id] = Path(binding.run_dir)
    return result


@dataclass(frozen=True, slots=True)
class GenerationCellReceipt:
    """Label-free proof summary for one completed prediction/reveal cell."""

    generation_id: str
    generation_plan_hash: str
    cell_id: str
    fold_id: str
    arm_id: str
    cell_binding_hash: str
    prediction_phase_seal_hash: str
    access_barrier_hash: str
    prediction_count: int
    execution_count: int
    checkpoint_count: int
    revealed_count: int
    post_commit_reveal_count: int
    requires_attested_ark: bool
    attested_attempt_count: int
    transport_receipt_set_hash: str

    def __post_init__(self) -> None:
        for name in (
            "generation_id",
            "generation_plan_hash",
            "cell_id",
            "cell_binding_hash",
            "prediction_phase_seal_hash",
            "access_barrier_hash",
            "transport_receipt_set_hash",
        ):
            _require_hash(getattr(self, name), name)
        _require_identifier(self.fold_id, "fold_id")
        _require_identifier(self.arm_id, "arm_id")
        for name in (
            "prediction_count",
            "execution_count",
            "checkpoint_count",
            "revealed_count",
            "post_commit_reveal_count",
            "attested_attempt_count",
        ):
            _require_nonnegative_int(getattr(self, name), name)
        if not isinstance(self.requires_attested_ark, bool):
            raise GenerationBarrierError("receipt attestation flag must be Boolean")
        if self.requires_attested_ark and self.attested_attempt_count <= 0:
            raise GenerationBarrierError("physical receipt lacks attested attempts")
        if not self.requires_attested_ark and self.attested_attempt_count != 0:
            raise GenerationBarrierError("deterministic receipt claims physical attempts")

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPGenerationCellReceipt.v1",
            "generation_id": self.generation_id,
            "generation_plan_hash": self.generation_plan_hash,
            "cell_id": self.cell_id,
            "fold_id": self.fold_id,
            "arm_id": self.arm_id,
            "cell_binding_hash": self.cell_binding_hash,
            "prediction_phase_seal_hash": self.prediction_phase_seal_hash,
            "access_barrier_hash": self.access_barrier_hash,
            "prediction_count": self.prediction_count,
            "execution_count": self.execution_count,
            "checkpoint_count": self.checkpoint_count,
            "revealed_count": self.revealed_count,
            "post_commit_reveal_count": self.post_commit_reveal_count,
            "requires_attested_ark": self.requires_attested_ark,
            "attested_attempt_count": self.attested_attempt_count,
            "transport_receipt_set_hash": self.transport_receipt_set_hash,
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_sha256(self.body())

    def record(self) -> dict[str, Any]:
        result = self.body()
        result["receipt_hash"] = self.receipt_hash
        return result

    @classmethod
    def from_record(cls, record: Any) -> "GenerationCellReceipt":
        expected_body = {
            "schema_version",
            "generation_id",
            "generation_plan_hash",
            "cell_id",
            "fold_id",
            "arm_id",
            "cell_binding_hash",
            "prediction_phase_seal_hash",
            "access_barrier_hash",
            "prediction_count",
            "execution_count",
            "checkpoint_count",
            "revealed_count",
            "post_commit_reveal_count",
            "requires_attested_ark",
            "attested_attempt_count",
            "transport_receipt_set_hash",
        }
        if not isinstance(record, dict) or set(record) != expected_body | {"receipt_hash"}:
            raise GenerationBarrierError("generation cell receipt schema mismatch")
        if record["schema_version"] != "CAPGenerationCellReceipt.v1":
            raise GenerationBarrierError("generation cell receipt version mismatch")
        receipt = cls(**{key: record[key] for key in expected_body - {"schema_version"}})
        if record["receipt_hash"] != receipt.receipt_hash:
            raise GenerationBarrierError("generation cell receipt hash mismatch")
        return receipt


def _artifact_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _verify_attested_attempt_records(
    attempts: Sequence[Mapping[str, Any]],
    *,
    expected_attempt_count: int,
) -> tuple[int, str]:
    """Require production one-shot evidence for every formal physical slot."""

    starts = [item for item in attempts if item.get("event") == "STARTED"]
    finishes = [item for item in attempts if item.get("event") == "FINISHED"]
    if len(starts) != expected_attempt_count or len(finishes) != expected_attempt_count:
        raise GenerationBarrierError(
            "formal physical cell lacks its exact attested attempt envelope"
        )
    try:
        from .ark_provider import ArkProviderEvidenceEnvelope

        receipt_hashes: list[str] = []
        for record in finishes:
            payload = record["payload"]
            evidence = payload.get("provider_evidence")
            evidence_hash = payload.get("provider_evidence_hash")
            if evidence is None or evidence_hash is None:
                raise GenerationBarrierError(
                    "formal physical cell contains mock/unattested provider output"
                )
            envelope = ArkProviderEvidenceEnvelope.from_mapping(evidence)
            audit = envelope.invocation_audit
            if (
                envelope.evidence_hash != evidence_hash
                or not envelope.binding_manifest.transport_receipt_required
                or audit.transport_receipt is None
                or audit.transport_receipt_hash is None
                or audit.transport_profile_hash is None
            ):
                raise GenerationBarrierError(
                    "formal physical cell lacks typed one-shot Ark transport evidence"
                )
            receipt_hashes.append(audit.transport_receipt_hash)
    except GenerationBarrierError:
        raise
    except Exception as exc:
        raise GenerationBarrierError(
            "formal physical provider evidence cannot be reconstructed"
        ) from exc
    return len(receipt_hashes), canonical_sha256(sorted(receipt_hashes))


def _build_cell_receipt(
    plan: FrozenGenerationPlan,
    cell: FrozenGenerationCell,
    run_dir: Path,
) -> GenerationCellReceipt:
    paths = CAPRunPaths(run_dir)
    forbidden = (
        paths.seal_path(LedgerKind.ACCESS),
        paths.maturity,
        paths.seal_path(LedgerKind.MATURITY),
        paths.final_run_seal,
    )
    if any(_artifact_exists(path) for path in forbidden):
        raise GenerationBarrierError("generation cell already contains post-prediction artifacts")
    try:
        prediction = verify_prediction_phase(run_dir)
        access = verify_access_barrier(
            run_dir, context=cell.context, require_access_seal=False
        )
        attempts = read_verified_ledger_records(
            paths.attempt,
            expected_kind=LedgerKind.ATTEMPT,
            seal_path=paths.seal_path(LedgerKind.ATTEMPT),
        )
    except Exception as exc:
        raise GenerationBarrierError("generation cell prediction preflight failed") from exc
    starts = [item for item in attempts if item["event"] == "STARTED"]
    if not starts or {item["payload"]["policy_hash"] for item in starts} != {
        cell.policy_hash
    }:
        raise GenerationBarrierError("generation cell policy differs from its frozen binding")
    if {item["payload"]["arm"] for item in starts} != {cell.arm_id}:
        raise GenerationBarrierError("generation cell arm differs from its frozen binding")
    if (
        access["revealed_count"] != cell.expected_revealed_count
        or access["post_commit_reveal_count"]
        != cell.expected_post_commit_reveal_count
    ):
        raise GenerationBarrierError("generation cell replay is unfinished")
    admission = plan.admission_by_arm(cell.arm_id)
    requires_attested_ark = bool(
        admission is not None and admission.requires_attested_ark
    )
    if requires_attested_ark:
        assert admission is not None
        attested_attempt_count, receipt_set_hash = _verify_attested_attempt_records(
            attempts,
            expected_attempt_count=(
                prediction["prediction_count"] * admission.physical_slots_per_origin
            ),
        )
    else:
        attested_attempt_count = 0
        receipt_set_hash = canonical_sha256([])
    return GenerationCellReceipt(
        generation_id=plan.generation_id,
        generation_plan_hash=plan.plan_hash,
        cell_id=cell.cell_id,
        fold_id=cell.fold_id,
        arm_id=cell.arm_id,
        cell_binding_hash=cell.binding_hash,
        prediction_phase_seal_hash=prediction["phase_seal_hash"],
        access_barrier_hash=access["barrier_hash"],
        prediction_count=prediction["prediction_count"],
        execution_count=prediction["execution_count"],
        checkpoint_count=prediction["checkpoint_count"],
        revealed_count=access["revealed_count"],
        post_commit_reveal_count=access["post_commit_reveal_count"],
        requires_attested_ark=requires_attested_ark,
        attested_attempt_count=attested_attempt_count,
        transport_receipt_set_hash=receipt_set_hash,
    )


@dataclass(frozen=True, slots=True)
class GenerationPredictionBarrier:
    """Whole-generation label-free barrier over every frozen Cartesian cell."""

    generation_id: str
    generation_plan_hash: str
    cell_receipts: tuple[GenerationCellReceipt, ...]

    def __post_init__(self) -> None:
        _require_hash(self.generation_id, "generation_id")
        _require_hash(self.generation_plan_hash, "generation_plan_hash")
        if not isinstance(self.cell_receipts, tuple) or not self.cell_receipts:
            raise GenerationBarrierError("generation barrier requires typed cell receipts")
        if not all(isinstance(item, GenerationCellReceipt) for item in self.cell_receipts):
            raise GenerationBarrierError("generation barrier contains an untyped receipt")
        if self.cell_receipts != tuple(
            sorted(self.cell_receipts, key=lambda item: (item.fold_id, item.arm_id))
        ):
            raise GenerationBarrierError("generation receipts are not in canonical order")
        ids = [item.cell_id for item in self.cell_receipts]
        if len(ids) != len(set(ids)):
            raise GenerationBarrierError("generation barrier contains duplicate receipts")

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPGenerationPredictionBarrier.v1",
            "generation_id": self.generation_id,
            "generation_plan_hash": self.generation_plan_hash,
            "cell_receipts": [item.record() for item in self.cell_receipts],
        }

    @property
    def barrier_hash(self) -> str:
        return canonical_sha256(self.body())

    def record(self) -> dict[str, Any]:
        result = self.body()
        result["barrier_hash"] = self.barrier_hash
        return result

    def receipt_by_cell(self, cell_id: str) -> GenerationCellReceipt:
        matches = [item for item in self.cell_receipts if item.cell_id == cell_id]
        if len(matches) != 1:
            raise GenerationBarrierError("barrier does not contain exactly one cell receipt")
        return matches[0]


def _parse_prediction_barrier(
    record: Mapping[str, Any], plan: FrozenGenerationPlan
) -> GenerationPredictionBarrier:
    expected = {
        "schema_version",
        "generation_id",
        "generation_plan_hash",
        "cell_receipts",
        "barrier_hash",
    }
    if set(record) != expected or record.get("schema_version") != "CAPGenerationPredictionBarrier.v1":
        raise GenerationBarrierError("generation prediction barrier schema mismatch")
    if not isinstance(record["cell_receipts"], list):
        raise GenerationBarrierError("generation prediction receipts must be a JSON list")
    barrier = GenerationPredictionBarrier(
        generation_id=record["generation_id"],
        generation_plan_hash=record["generation_plan_hash"],
        cell_receipts=tuple(
            GenerationCellReceipt.from_record(item) for item in record["cell_receipts"]
        ),
    )
    if record["barrier_hash"] != barrier.barrier_hash:
        raise GenerationBarrierError("generation prediction barrier hash mismatch")
    if (
        barrier.generation_id != plan.generation_id
        or barrier.generation_plan_hash != plan.plan_hash
        or [item.cell_id for item in barrier.cell_receipts]
        != [item.cell_id for item in plan.cells]
    ):
        raise GenerationBarrierError("generation barrier differs from the frozen plan")
    for cell, receipt in zip(plan.cells, barrier.cell_receipts, strict=True):
        admission = plan.admission_by_arm(cell.arm_id)
        if (
            receipt.generation_id != plan.generation_id
            or receipt.generation_plan_hash != plan.plan_hash
            or receipt.fold_id != cell.fold_id
            or receipt.arm_id != cell.arm_id
            or receipt.cell_binding_hash != cell.binding_hash
            or receipt.requires_attested_ark
            != bool(admission is not None and admission.requires_attested_ark)
        ):
            raise GenerationBarrierError("cell receipt differs from its frozen binding")
    return barrier


def seal_generation_prediction_barrier(
    plan_path: str | os.PathLike[str],
    barrier_path: str | os.PathLike[str],
    bindings: Sequence[GenerationRunBinding],
) -> GenerationPredictionBarrier:
    """Verify every cell before atomically publishing the no-label barrier."""

    plan = verify_generation_plan(plan_path)
    run_dirs = _validated_bindings(plan, bindings)
    receipts: list[GenerationCellReceipt] = []
    for cell in plan.cells:
        receipts.append(_build_cell_receipt(plan, cell, run_dirs[cell.cell_id]))
    barrier = GenerationPredictionBarrier(
        generation_id=plan.generation_id,
        generation_plan_hash=plan.plan_hash,
        cell_receipts=tuple(receipts),
    )
    _write_atomic_exclusive(Path(barrier_path), barrier.record())
    return barrier


def verify_generation_prediction_barrier(
    plan_path: str | os.PathLike[str],
    barrier_path: str | os.PathLike[str],
) -> GenerationPredictionBarrier:
    plan = verify_generation_plan(plan_path)
    return _parse_prediction_barrier(_read_canonical_record(Path(barrier_path)), plan)


@dataclass(frozen=True, slots=True)
class GenerationFinalizePermit:
    """Deterministic, HMAC-free cell permit for honest-launcher integration.

    This value proves only that fields match the frozen barrier.  It is not a
    secret and must not be described as evaluator authorization.
    """

    generation_id: str
    generation_plan_hash: str
    generation_barrier_hash: str
    cell_id: str
    cell_receipt_hash: str

    def __post_init__(self) -> None:
        for name in (
            "generation_id",
            "generation_plan_hash",
            "generation_barrier_hash",
            "cell_id",
            "cell_receipt_hash",
        ):
            _require_hash(getattr(self, name), name)

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPGenerationFinalizePermit.v1",
            "generation_id": self.generation_id,
            "generation_plan_hash": self.generation_plan_hash,
            "generation_barrier_hash": self.generation_barrier_hash,
            "cell_id": self.cell_id,
            "cell_receipt_hash": self.cell_receipt_hash,
        }

    @property
    def permit_hash(self) -> str:
        return canonical_sha256(self.body())

    def record(self) -> dict[str, Any]:
        result = self.body()
        result["permit_hash"] = self.permit_hash
        return result

    @classmethod
    def from_record(cls, record: Any) -> "GenerationFinalizePermit":
        expected_body = {
            "schema_version",
            "generation_id",
            "generation_plan_hash",
            "generation_barrier_hash",
            "cell_id",
            "cell_receipt_hash",
        }
        if not isinstance(record, Mapping) or set(record) != expected_body | {"permit_hash"}:
            raise GenerationBarrierError("generation finalize permit schema mismatch")
        if record["schema_version"] != "CAPGenerationFinalizePermit.v1":
            raise GenerationBarrierError("generation finalize permit version mismatch")
        permit = cls(**{key: record[key] for key in expected_body - {"schema_version"}})
        if record["permit_hash"] != permit.permit_hash:
            raise GenerationBarrierError("generation finalize permit hash mismatch")
        return permit


def make_finalize_permit(
    plan_path: str | os.PathLike[str],
    barrier_path: str | os.PathLike[str],
    *,
    cell_id: str,
) -> GenerationFinalizePermit:
    plan = verify_generation_plan(plan_path)
    barrier = _parse_prediction_barrier(_read_canonical_record(Path(barrier_path)), plan)
    plan.cell_by_id(cell_id)
    receipt = barrier.receipt_by_cell(cell_id)
    return GenerationFinalizePermit(
        generation_id=plan.generation_id,
        generation_plan_hash=plan.plan_hash,
        generation_barrier_hash=barrier.barrier_hash,
        cell_id=cell_id,
        cell_receipt_hash=receipt.receipt_hash,
    )


def verify_finalize_permit(
    plan_path: str | os.PathLike[str],
    barrier_path: str | os.PathLike[str],
    permit: GenerationFinalizePermit | Mapping[str, Any],
    *,
    expected_cell_id: str,
    reverify_cell: bool = True,
) -> GenerationCellReceipt:
    """Validate a deterministic permit and optionally re-run its preflight."""

    typed_permit = (
        permit
        if isinstance(permit, GenerationFinalizePermit)
        else GenerationFinalizePermit.from_record(permit)
    )
    plan = verify_generation_plan(plan_path)
    barrier = _parse_prediction_barrier(_read_canonical_record(Path(barrier_path)), plan)
    cell = plan.cell_by_id(expected_cell_id)
    receipt = barrier.receipt_by_cell(expected_cell_id)
    if (
        typed_permit.generation_id != plan.generation_id
        or typed_permit.generation_plan_hash != plan.plan_hash
        or typed_permit.generation_barrier_hash != barrier.barrier_hash
        or typed_permit.cell_id != expected_cell_id
        or typed_permit.cell_receipt_hash != receipt.receipt_hash
    ):
        raise GenerationBarrierError("finalize permit differs from its generation cell")
    if reverify_cell:
        current = _build_cell_receipt(plan, cell, Path(cell.run_dir))
        if current.record() != receipt.record():
            raise GenerationBarrierError("generation cell changed after the prediction barrier")
    return receipt


@dataclass(frozen=True, slots=True)
class GenerationScoreCell:
    cell_id: str
    fold_id: str
    arm_id: str
    cell_receipt_hash: str
    run_seal_hash: str

    def __post_init__(self) -> None:
        _require_hash(self.cell_id, "cell_id")
        _require_identifier(self.fold_id, "fold_id")
        _require_identifier(self.arm_id, "arm_id")
        _require_hash(self.cell_receipt_hash, "cell_receipt_hash")
        _require_hash(self.run_seal_hash, "run_seal_hash")

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPGenerationScoreCell.v1",
            "cell_id": self.cell_id,
            "fold_id": self.fold_id,
            "arm_id": self.arm_id,
            "cell_receipt_hash": self.cell_receipt_hash,
            "run_seal_hash": self.run_seal_hash,
        }


@dataclass(frozen=True, slots=True)
class GenerationScoreInputSeal:
    """All-cell final-run seal required before aggregate scoring may start."""

    generation_id: str
    generation_plan_hash: str
    generation_barrier_hash: str
    cells: tuple[GenerationScoreCell, ...]

    def __post_init__(self) -> None:
        for name in (
            "generation_id",
            "generation_plan_hash",
            "generation_barrier_hash",
        ):
            _require_hash(getattr(self, name), name)
        if not isinstance(self.cells, tuple) or not self.cells:
            raise GenerationBarrierError("score-input seal requires all typed cells")
        if not all(isinstance(item, GenerationScoreCell) for item in self.cells):
            raise GenerationBarrierError("score-input seal contains an untyped cell")
        if self.cells != tuple(sorted(self.cells, key=lambda item: (item.fold_id, item.arm_id))):
            raise GenerationBarrierError("score-input cells are not in canonical order")

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": "CAPGenerationScoreInputSeal.v1",
            "generation_id": self.generation_id,
            "generation_plan_hash": self.generation_plan_hash,
            "generation_barrier_hash": self.generation_barrier_hash,
            "cells": [item.payload() for item in self.cells],
        }

    @property
    def score_input_seal_hash(self) -> str:
        return canonical_sha256(self.body())

    def record(self) -> dict[str, Any]:
        result = self.body()
        result["score_input_seal_hash"] = self.score_input_seal_hash
        return result


def seal_generation_score_inputs(
    plan_path: str | os.PathLike[str],
    barrier_path: str | os.PathLike[str],
    score_input_path: str | os.PathLike[str],
    bindings: Sequence[GenerationRunBinding],
) -> GenerationScoreInputSeal:
    """Verify every final run before publishing the aggregate scoring input."""

    plan = verify_generation_plan(plan_path)
    barrier = _parse_prediction_barrier(_read_canonical_record(Path(barrier_path)), plan)
    run_dirs = _validated_bindings(plan, bindings)
    cells: list[GenerationScoreCell] = []
    for cell in plan.cells:
        receipt = barrier.receipt_by_cell(cell.cell_id)
        run_dir = run_dirs[cell.cell_id]
        try:
            complete = verify_complete_run(run_dir, context=cell.context)
            prediction = verify_prediction_phase(run_dir)
            access = verify_access_barrier(
                run_dir, context=cell.context, require_access_seal=True
            )
        except Exception as exc:
            raise GenerationBarrierError("generation cell lacks a verified final run seal") from exc
        if (
            prediction["phase_seal_hash"] != receipt.prediction_phase_seal_hash
            or access["barrier_hash"] != receipt.access_barrier_hash
            or prediction["prediction_count"] != receipt.prediction_count
            or prediction["execution_count"] != receipt.execution_count
            or access["revealed_count"] != receipt.revealed_count
            or access["post_commit_reveal_count"] != receipt.post_commit_reveal_count
        ):
            raise GenerationBarrierError("final run differs from its prediction-barrier receipt")
        cells.append(
            GenerationScoreCell(
                cell_id=cell.cell_id,
                fold_id=cell.fold_id,
                arm_id=cell.arm_id,
                cell_receipt_hash=receipt.receipt_hash,
                run_seal_hash=complete["run_seal_hash"],
            )
        )
    seal = GenerationScoreInputSeal(
        generation_id=plan.generation_id,
        generation_plan_hash=plan.plan_hash,
        generation_barrier_hash=barrier.barrier_hash,
        cells=tuple(cells),
    )
    _write_atomic_exclusive(Path(score_input_path), seal.record())
    return seal
