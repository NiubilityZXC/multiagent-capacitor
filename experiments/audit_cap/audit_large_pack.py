#!/usr/bin/env python3
"""Deterministic, metadata-first audit for the NASA capacitor stress archive.

The audit deliberately does not infer physical semantics from HDF5 path names.
Datasets remain quarantined until a separately reviewed source-field mapping is
frozen.  Numeric payloads are not read unless ``--scan-numeric`` is supplied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import stat
import tempfile
import zlib
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence
from zipfile import BadZipFile, ZipFile, ZipInfo


SCHEMA_VERSION = "audit-cap.b0.v2"
TARGET_MAT_FILES = ("ES10.mat", "ES12.mat", "ES14.mat")
ATTRIBUTE_INLINE_LIMIT = 1_024

OBJECT_COLUMNS = (
    "source_file",
    "object_path",
    "object_type",
    "link_type",
    "link_target",
    "object_address",
    "shape_json",
    "ndim",
    "element_count",
    "dtype",
    "dtype_kind",
    "reference_dtype_json",
    "chunks_json",
    "compression",
    "compression_opts_json",
    "external_storage_json",
    "is_virtual",
    "virtual_sources_json",
    "storage_layout_status",
    "shuffle",
    "fletcher32",
    "scaleoffset",
    "maxshape_json",
    "matlab_class",
    "attrs_json",
    "semantic_status",
    "semantic_evidence",
    "traversal_status",
)

QUARANTINE_COLUMNS = (
    "source_file",
    "object_path",
    "object_type",
    "reason",
    "evidence",
    "blocks_evaluation_use",
)

NUMERIC_SCAN_COLUMNS = (
    "source_file",
    "object_path",
    "dtype",
    "element_count",
    "scanned_element_count",
    "finite_count",
    "nan_count",
    "inf_count",
    "posinf_count",
    "neginf_count",
    "min",
    "max",
    "min_abs",
    "max_abs",
    "status",
    "detail",
)


class AuditError(RuntimeError):
    """Raised when archive integrity or audit preconditions fail."""


def _strict_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_and_crc32(path: Path, block_bytes: int = 8 * 1024 * 1024) -> tuple[str, str, int]:
    digest = hashlib.sha256()
    crc = 0
    total = 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(block_bytes)
            if not block:
                break
            digest.update(block)
            crc = zlib.crc32(block, crc)
            total += len(block)
    return digest.hexdigest(), f"{crc & 0xFFFFFFFF:08x}", total


def _safe_member_name(info: ZipInfo) -> str:
    raw_name = info.filename
    if not raw_name or "\x00" in raw_name:
        raise AuditError(f"unsafe empty/NUL ZIP member name: {raw_name!r}")

    unified = raw_name.replace("\\", "/")
    if unified.startswith("/") or re.match(r"^[A-Za-z]:", unified):
        raise AuditError(f"absolute ZIP member path is forbidden: {raw_name!r}")

    raw_parts = unified.split("/")
    if info.is_dir() and raw_parts and raw_parts[-1] == "":
        raw_parts = raw_parts[:-1]
    if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
        raise AuditError(f"ambiguous/traversing ZIP member path: {raw_name!r}")

    normalized = "/".join(raw_parts)
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise AuditError(f"traversing ZIP member path is forbidden: {raw_name!r}")

    unix_mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if file_type == stat.S_IFLNK:
        raise AuditError(f"ZIP symlink is forbidden: {raw_name!r}")
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise AuditError(f"ZIP special file is forbidden: {raw_name!r}")
    if info.flag_bits & 0x1:
        raise AuditError(f"encrypted ZIP member is unsupported: {raw_name!r}")
    return normalized


def _inspect_archive(
    zip_path: Path,
    source_url: str | None,
) -> tuple[dict[str, Any], dict[str, ZipInfo], dict[str, str]]:
    if not zip_path.is_file() or zip_path.is_symlink():
        raise AuditError(f"ZIP input must be a regular, non-symlink file: {zip_path}")

    try:
        with ZipFile(zip_path, "r") as archive:
            infos = archive.infolist()
            if not infos:
                raise AuditError("ZIP archive is empty")

            normalized_seen: set[str] = set()
            casefold_seen: dict[str, str] = {}
            target_infos: dict[str, ZipInfo] = {}
            target_member_sha256: dict[str, str] = {}
            member_rows_by_name: dict[str, dict[str, Any]] = {}
            members: list[dict[str, Any]] = []
            for info in infos:
                normalized = _safe_member_name(info)
                if normalized in normalized_seen:
                    raise AuditError(f"duplicate normalized ZIP member: {normalized!r}")
                normalized_seen.add(normalized)
                folded = normalized.casefold()
                if folded in casefold_seen:
                    raise AuditError(
                        "case-colliding ZIP members are forbidden: "
                        f"{casefold_seen[folded]!r}, {normalized!r}"
                    )
                casefold_seen[folded] = normalized

                basename = PurePosixPath(normalized).name
                if basename in TARGET_MAT_FILES:
                    if info.is_dir():
                        raise AuditError(f"required MAT target is a directory: {normalized!r}")
                    if basename in target_infos:
                        raise AuditError(f"multiple archive members match {basename}")
                    target_infos[basename] = info

                member_row = {
                    "name": normalized,
                    "is_dir": info.is_dir(),
                    "uncompressed_size_bytes": info.file_size,
                    "compressed_size_bytes": info.compress_size,
                    "declared_crc32": f"{info.CRC:08x}",
                    "compression_method": info.compress_type,
                    "streamed_uncompressed_sha256": None,
                }
                members.append(member_row)
                member_rows_by_name[normalized] = member_row

            missing = sorted(set(TARGET_MAT_FILES) - set(target_infos))
            if missing:
                raise AuditError(f"required MAT members missing from ZIP: {missing}")

            # Stream every member once.  Reading ZipExtFile to EOF triggers
            # zipfile's CRC verification; the explicit CRC below makes that
            # check independently visible.  SHA-256 is retained for each target
            # MAT and is the primary extracted-byte comparison.
            for info in infos:
                if info.is_dir():
                    continue
                normalized = _safe_member_name(info)
                basename = PurePosixPath(normalized).name
                target_digest = hashlib.sha256() if basename in TARGET_MAT_FILES else None
                streamed_crc = 0
                streamed_size = 0
                with archive.open(info, "r") as member_stream:
                    while True:
                        block = member_stream.read(8 * 1024 * 1024)
                        if not block:
                            break
                        streamed_crc = zlib.crc32(block, streamed_crc)
                        streamed_size += len(block)
                        if target_digest is not None:
                            target_digest.update(block)
                streamed_crc_hex = f"{streamed_crc & 0xFFFFFFFF:08x}"
                if streamed_size != info.file_size or streamed_crc_hex != f"{info.CRC:08x}":
                    raise AuditError(
                        f"ZIP member integrity failed for {normalized!r}: "
                        f"size={streamed_size}/{info.file_size}, "
                        f"crc={streamed_crc_hex}/{info.CRC:08x}"
                    )
                if target_digest is not None:
                    digest_hex = target_digest.hexdigest()
                    target_member_sha256[basename] = digest_hex
                    member_rows_by_name[normalized]["streamed_uncompressed_sha256"] = digest_hex
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise AuditError(f"invalid ZIP archive or CRC failure: {exc}") from exc

    zip_sha256, zip_crc32, zip_size = _sha256_and_crc32(zip_path)
    members.sort(key=lambda row: row["name"])
    manifest = {
        "source_url": source_url,
        "archive_name": zip_path.name,
        "size_bytes": zip_size,
        "sha256": zip_sha256,
        "file_crc32": zip_crc32,
        "member_crc_status": "passed",
        "member_count": len(members),
        "total_uncompressed_bytes": sum(row["uncompressed_size_bytes"] for row in members),
        "total_compressed_bytes": sum(row["compressed_size_bytes"] for row in members),
        "members": members,
    }
    return manifest, target_infos, target_member_sha256


def _resolve_input_targets(input_root: Path) -> dict[str, Path]:
    if not input_root.is_dir() or input_root.is_symlink():
        raise AuditError(f"--input must be a regular directory, not a symlink: {input_root}")
    resolved_root = input_root.resolve(strict=True)
    result: dict[str, Path] = {}
    for target in TARGET_MAT_FILES:
        matches = sorted(input_root.rglob(target), key=lambda path: path.as_posix())
        if len(matches) != 1:
            raise AuditError(
                f"expected exactly one extracted {target} under {input_root}, found {len(matches)}"
            )
        candidate = matches[0]
        if not candidate.is_file() or candidate.is_symlink():
            raise AuditError(f"MAT input must be a regular, non-symlink file: {candidate}")
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise AuditError(f"MAT input escapes --input root: {candidate}") from exc
        result[target] = resolved
    return result


def _load_hdf5_dependencies() -> tuple[Any, Any]:
    try:
        import h5py  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise AuditError(
            "h5py and numpy are required; install requirements-audit-cap.txt in the frozen environment"
        ) from exc
    return h5py, np


def _float_or_marker(value: float) -> float | str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    return value


def _reference_target(value: Any, h5_file: Any, h5py: Any) -> dict[str, Any]:
    kind = "region" if isinstance(value, h5py.RegionReference) else "object"
    try:
        if not value:
            return {"reference_kind": kind, "target": None}
        return {"reference_kind": kind, "target": h5_file[value].name}
    except Exception as exc:  # h5py raises several low-level exception types.
        return {
            "reference_kind": kind,
            "target": None,
            "resolution_error": type(exc).__name__,
        }


def _jsonable_attr(value: Any, h5_file: Any, h5py: Any, np: Any) -> Any:
    if isinstance(value, h5py.RegionReference) or isinstance(value, h5py.Reference):
        return _reference_target(value, h5_file, h5py)
    if isinstance(value, (bytes, np.bytes_)):
        raw = bytes(value)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return {"encoding": "hex", "value": raw.hex()}
    if isinstance(value, (str, np.str_)):
        return str(value)
    if isinstance(value, np.void):
        return {"dtype": str(value.dtype), "encoding": "hex", "value": bytes(value).hex()}
    if isinstance(value, np.generic):
        if np.issubdtype(value.dtype, np.complexfloating):
            return {
                "real": _float_or_marker(float(value.real)),
                "imag": _float_or_marker(float(value.imag)),
            }
        if np.issubdtype(value.dtype, np.floating):
            return _float_or_marker(float(value))
        return value.item()
    if isinstance(value, np.ndarray):
        reference_kind = h5py.check_dtype(ref=value.dtype)
        if reference_kind is not None:
            flat = value.reshape(-1)
            inline = [
                _reference_target(item, h5_file, h5py)
                for item in flat[:ATTRIBUTE_INLINE_LIMIT]
            ]
            return {
                "dtype": str(value.dtype),
                "shape": list(value.shape),
                "references": inline,
                "omitted_references": max(0, int(value.size) - len(inline)),
            }
        if value.size > ATTRIBUTE_INLINE_LIMIT:
            if value.dtype.hasobject:
                sample = [
                    _jsonable_attr(item, h5_file, h5py, np)
                    for item in value.reshape(-1)[:ATTRIBUTE_INLINE_LIMIT]
                ]
                return {
                    "dtype": str(value.dtype),
                    "shape": list(value.shape),
                    "sample": sample,
                    "omitted_values": int(value.size) - len(sample),
                }
            return {
                "dtype": str(value.dtype),
                "shape": list(value.shape),
                "sha256": hashlib.sha256(value.tobytes(order="C")).hexdigest(),
                "values_omitted": int(value.size),
            }
        if value.shape == ():
            return _jsonable_attr(value[()], h5_file, h5py, np)
        return [
            _jsonable_attr(item, h5_file, h5py, np)
            for item in value.tolist()
        ]
    if isinstance(value, (list, tuple)):
        return [_jsonable_attr(item, h5_file, h5py, np) for item in value]
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return _float_or_marker(value)
    return {"unsupported_python_type": f"{type(value).__module__}.{type(value).__qualname__}"}


def _decode_matlab_class(value: Any, np: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, np.bytes_)):
        return bytes(value).rstrip(b"\x00").decode("utf-8", errors="replace")
    if isinstance(value, (str, np.str_)):
        return str(value).rstrip("\x00")
    if isinstance(value, np.ndarray):
        flat = value.reshape(-1)
        if value.dtype.kind in {"u", "i"} and flat.size <= 256:
            try:
                return "".join(chr(int(code)) for code in flat if int(code) != 0)
            except (ValueError, OverflowError):
                return _strict_json({"dtype": str(value.dtype), "shape": list(value.shape)})
        if value.dtype.kind in {"S", "U"} and flat.size <= 256:
            return "".join(
                _decode_matlab_class(item, np) for item in flat
            ).rstrip("\x00")
    return _strict_json({"python_type": type(value).__name__})


def _attrs_metadata(obj: Any, h5_file: Any, h5py: Any, np: Any) -> tuple[str, str, list[str]]:
    metadata: dict[str, Any] = {}
    errors: list[str] = []
    matlab_class = ""
    for raw_key in sorted(obj.attrs.keys(), key=lambda item: str(item)):
        key = str(raw_key)
        try:
            raw_value = obj.attrs[raw_key]
            metadata[key] = _jsonable_attr(raw_value, h5_file, h5py, np)
            if key == "MATLAB_class":
                matlab_class = _decode_matlab_class(raw_value, np)
        except Exception as exc:
            metadata[key] = {"read_error": type(exc).__name__}
            errors.append(f"attribute_read_error:{key}:{type(exc).__name__}")
    return matlab_class, _strict_json(metadata), errors


def _reference_dtype(dtype: Any, h5py: Any) -> dict[str, Any] | None:
    direct = h5py.check_dtype(ref=dtype)
    if direct is not None:
        name = getattr(direct, "__name__", str(direct))
        return {"kind": "direct", "reference_class": name}
    if dtype.fields:
        fields: dict[str, Any] = {}
        for field_name in sorted(dtype.fields):
            field_dtype = dtype.fields[field_name][0]
            nested = _reference_dtype(field_dtype, h5py)
            if nested is not None:
                fields[field_name] = nested
        if fields:
            return {"kind": "compound", "fields": fields}
    if dtype.subdtype is not None:
        base_dtype, subshape = dtype.subdtype
        nested = _reference_dtype(base_dtype, h5py)
        if nested is not None:
            return {"kind": "subarray", "shape": list(subshape), "base": nested}
    return None


def _object_address(obj: Any, h5py: Any) -> int | None:
    try:
        return int(h5py.h5o.get_info(obj.id).addr)
    except Exception:
        return None


def _empty_object_row(source_file: str, object_path: str) -> dict[str, Any]:
    return {column: "" for column in OBJECT_COLUMNS} | {
        "source_file": source_file,
        "object_path": object_path,
    }


def _metadata_text(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return f"hex:{value.hex()}"
    return str(value)


def _dataspace_metadata(space: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key, method_name in (
        ("selection_type", "get_select_type"),
        ("selected_points", "get_select_npoints"),
        ("bounds", "get_select_bounds"),
    ):
        try:
            value = getattr(space, method_name)()
            if key == "bounds":
                value = [list(bound) for bound in value]
            else:
                value = int(value)
            metadata[key] = value
        except Exception as exc:
            metadata[f"{key}_error"] = type(exc).__name__
    return metadata


def _dataset_storage_metadata(
    dataset: Any,
) -> tuple[list[dict[str, Any]], bool | None, list[dict[str, Any]], list[str]]:
    external_entries: list[dict[str, Any]] = []
    virtual_sources: list[dict[str, Any]] = []
    errors: list[str] = []
    is_virtual: bool | None = None
    try:
        raw_external = dataset.external
        external_entries = [
            {
                "filename": _metadata_text(filename),
                "offset_bytes": int(offset),
                "size_bytes": int(size),
            }
            for filename, offset, size in (raw_external or ())
        ]
    except Exception as exc:
        errors.append(f"external_storage_metadata_error:{type(exc).__name__}")
    try:
        is_virtual = bool(dataset.is_virtual)
    except Exception as exc:
        errors.append(f"virtual_layout_metadata_error:{type(exc).__name__}")
    if is_virtual:
        try:
            virtual_sources = [
                {
                    "filename": _metadata_text(source.file_name),
                    "dataset_path": _metadata_text(source.dset_name),
                    "virtual_selection": _dataspace_metadata(source.vspace),
                    "source_selection": _dataspace_metadata(source.src_space),
                }
                for source in dataset.virtual_sources()
            ]
        except Exception as exc:
            errors.append(f"virtual_source_metadata_error:{type(exc).__name__}")
    return external_entries, is_virtual, virtual_sources, errors


def _make_object_row(
    source_file: str,
    object_path: str,
    obj: Any,
    link_type: str,
    link_target: str,
    traversal_status: str,
    h5_file: Any,
    h5py: Any,
    np: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row = _empty_object_row(source_file, object_path)
    quarantines: list[dict[str, Any]] = []
    if isinstance(obj, h5py.Group):
        object_type = "group"
    elif isinstance(obj, h5py.Dataset):
        object_type = "dataset"
    elif isinstance(obj, h5py.Datatype):
        object_type = "named_datatype"
    else:
        object_type = f"unknown:{type(obj).__module__}.{type(obj).__qualname__}"

    matlab_class, attrs_json, attr_errors = _attrs_metadata(obj, h5_file, h5py, np)
    row.update(
        {
            "object_type": object_type,
            "link_type": link_type,
            "link_target": link_target,
            "object_address": _object_address(obj, h5py),
            "matlab_class": matlab_class,
            "attrs_json": attrs_json,
            "traversal_status": traversal_status,
        }
    )

    if isinstance(obj, h5py.Dataset):
        reference_info = _reference_dtype(obj.dtype, h5py)
        external_entries, is_virtual, virtual_sources, storage_errors = (
            _dataset_storage_metadata(obj)
        )
        is_internal = "#refs#" in PurePosixPath(object_path).parts
        if storage_errors:
            storage_layout_status = "metadata_error"
        elif external_entries:
            storage_layout_status = "external_payload_not_read"
        elif is_virtual:
            storage_layout_status = "virtual_payload_not_read"
        else:
            storage_layout_status = "local"
        row.update(
            {
                "shape_json": _strict_json(list(obj.shape)),
                "ndim": obj.ndim,
                "element_count": int(obj.size),
                "dtype": str(obj.dtype),
                "dtype_kind": obj.dtype.kind,
                "reference_dtype_json": "" if reference_info is None else _strict_json(reference_info),
                "chunks_json": "" if obj.chunks is None else _strict_json(list(obj.chunks)),
                "compression": "" if obj.compression is None else str(obj.compression),
                "compression_opts_json": (
                    "" if obj.compression_opts is None else _strict_json(obj.compression_opts)
                ),
                "external_storage_json": (
                    "" if not external_entries else _strict_json(external_entries)
                ),
                "is_virtual": "unknown" if is_virtual is None else is_virtual,
                "virtual_sources_json": (
                    "" if not virtual_sources else _strict_json(virtual_sources)
                ),
                "storage_layout_status": storage_layout_status,
                "shuffle": bool(obj.shuffle),
                "fletcher32": bool(obj.fletcher32),
                "scaleoffset": "" if obj.scaleoffset is None else obj.scaleoffset,
                "maxshape_json": (
                    ""
                    if obj.maxshape is None
                    else _strict_json([dimension for dimension in obj.maxshape])
                ),
                "semantic_status": "matlab_internal" if is_internal else "quarantined_unknown",
                "semantic_evidence": (
                    "Path is inside MATLAB #refs# storage; not an evaluation field."
                    if is_internal
                    else "No frozen source-field mapping supplied; path tokens are not treated as semantic proof."
                ),
            }
        )
        if not is_internal:
            quarantines.append(
                {
                    "source_file": source_file,
                    "object_path": object_path,
                    "object_type": object_type,
                    "reason": "unknown_semantics",
                    "evidence": row["semantic_evidence"],
                    "blocks_evaluation_use": True,
                }
            )
        if external_entries:
            quarantines.append(
                {
                    "source_file": source_file,
                    "object_path": object_path,
                    "object_type": object_type,
                    "reason": "external_storage_payload_not_audited",
                    "evidence": (
                        "External-storage filenames/offsets/sizes were recorded from HDF5 metadata; "
                        "external payload bytes were not opened."
                    ),
                    "blocks_evaluation_use": True,
                }
            )
        if is_virtual:
            quarantines.append(
                {
                    "source_file": source_file,
                    "object_path": object_path,
                    "object_type": object_type,
                    "reason": "virtual_dataset_payload_not_audited",
                    "evidence": (
                        "VDS source mappings were recorded from HDF5 metadata; source payloads were not opened."
                    ),
                    "blocks_evaluation_use": True,
                }
            )
        for error in storage_errors:
            quarantines.append(
                {
                    "source_file": source_file,
                    "object_path": object_path,
                    "object_type": object_type,
                    "reason": error,
                    "evidence": (
                        "Storage layout could not be fully classified; numeric payload access is forbidden."
                    ),
                    "blocks_evaluation_use": True,
                }
            )
    elif isinstance(obj, h5py.Group):
        row.update(
            {
                "semantic_status": "structural_only",
                "semantic_evidence": "Group membership is structural metadata, not a physical-field mapping.",
            }
        )
    else:
        row.update(
            {
                "semantic_status": "quarantined_unknown",
                "semantic_evidence": "Object type has no frozen interpretation.",
            }
        )
        quarantines.append(
            {
                "source_file": source_file,
                "object_path": object_path,
                "object_type": object_type,
                "reason": "unknown_object_type",
                "evidence": row["semantic_evidence"],
                "blocks_evaluation_use": True,
            }
        )

    for error in attr_errors:
        quarantines.append(
            {
                "source_file": source_file,
                "object_path": object_path,
                "object_type": object_type,
                "reason": error,
                "evidence": "HDF5 attribute could not be deterministically serialized.",
                "blocks_evaluation_use": True,
            }
        )
    return row, quarantines


def _link_row(
    source_file: str,
    object_path: str,
    object_type: str,
    link_type: str,
    link_target: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = _empty_object_row(source_file, object_path)
    row.update(
        {
            "object_type": object_type,
            "link_type": link_type,
            "link_target": link_target,
            "semantic_status": "quarantined_unknown",
            "semantic_evidence": "Link target was recorded but not dereferenced during the metadata audit.",
            "traversal_status": "not_dereferenced",
        }
    )
    quarantine = {
        "source_file": source_file,
        "object_path": object_path,
        "object_type": object_type,
        "reason": f"{link_type}_link_not_dereferenced",
        "evidence": row["semantic_evidence"],
        "blocks_evaluation_use": True,
    }
    return row, quarantine


def _hyperslabs(
    shape: Sequence[int],
    preferred_shape: Sequence[int] | None,
    max_elements: int,
) -> Iterator[tuple[slice, ...]]:
    if not shape:
        yield ()
        return
    if any(dimension == 0 for dimension in shape):
        return
    block = list(preferred_shape if preferred_shape is not None else shape)
    if len(block) != len(shape):
        raise AuditError("internal scan error: block rank does not match dataset rank")
    for axis in range(len(block)):
        trailing = math.prod(block[axis + 1 :])
        allowed = max(1, max_elements // max(1, trailing))
        block[axis] = max(1, min(int(block[axis]), int(shape[axis]), allowed))
    starts = [range(0, int(size), int(step)) for size, step in zip(shape, block)]
    for origin in itertools.product(*starts):
        yield tuple(
            slice(start, min(start + block[axis], int(shape[axis])))
            for axis, start in enumerate(origin)
        )


def _scan_dataset(
    source_file: str,
    object_path: str,
    dataset: Any,
    max_chunk_bytes: int,
    h5py: Any,
    np: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {column: "" for column in NUMERIC_SCAN_COLUMNS}
    row.update(
        {
            "source_file": source_file,
            "object_path": object_path,
            "dtype": str(dataset.dtype),
            "element_count": int(dataset.size),
            "scanned_element_count": 0,
            "finite_count": 0,
            "nan_count": 0,
            "inf_count": 0,
            "posinf_count": 0,
            "neginf_count": 0,
        }
    )
    try:
        external_entries = list(dataset.external or ())
        is_virtual = bool(dataset.is_virtual)
    except Exception as exc:
        row.update(
            status="skipped_storage_layout_unknown",
            detail=f"{type(exc).__name__}: storage metadata unreadable; payload not accessed",
        )
        return row
    if external_entries:
        row.update(
            status="skipped_external_storage",
            detail="External-storage payload access is forbidden by the metadata-first audit.",
        )
        return row
    if is_virtual:
        row.update(
            status="skipped_virtual_dataset",
            detail="Virtual source payload access is forbidden by the metadata-first audit.",
        )
        return row
    if _reference_dtype(dataset.dtype, h5py) is not None:
        row.update(status="skipped_reference_dtype", detail="Reference payloads are metadata, not numeric values.")
        return row
    if dataset.dtype.fields or dataset.dtype.hasobject or dataset.dtype.kind not in {"b", "i", "u", "f", "c"}:
        row.update(status="skipped_non_numeric", detail="Only fixed-width primitive numeric dtypes are scanned.")
        return row
    if dataset.size == 0:
        row.update(status="passed", detail="empty_dataset")
        return row

    itemsize = max(1, int(dataset.dtype.itemsize))
    max_elements = max(1, max_chunk_bytes // itemsize)
    value_min: float | int | None = None
    value_max: float | int | None = None
    abs_min: float | None = None
    abs_max: float | None = None
    try:
        for selection in _hyperslabs(dataset.shape, dataset.chunks, max_elements):
            raw = dataset[()] if selection == () else dataset[selection]
            values = np.asarray(raw)
            count = int(values.size)
            row["scanned_element_count"] += count
            if dataset.dtype.kind in {"f", "c"}:
                finite_mask = np.isfinite(values)
                nan_mask = np.isnan(values)
                inf_mask = np.isinf(values)
                row["finite_count"] += int(np.count_nonzero(finite_mask))
                row["nan_count"] += int(np.count_nonzero(nan_mask))
                row["inf_count"] += int(np.count_nonzero(inf_mask))
                if dataset.dtype.kind == "f":
                    row["posinf_count"] += int(np.count_nonzero(np.isposinf(values)))
                    row["neginf_count"] += int(np.count_nonzero(np.isneginf(values)))
                finite_values = values[finite_mask]
            else:
                row["finite_count"] += count
                finite_values = values.reshape(-1)

            if finite_values.size:
                if dataset.dtype.kind != "c":
                    local_min = finite_values.min().item()
                    local_max = finite_values.max().item()
                    value_min = local_min if value_min is None else min(value_min, local_min)
                    value_max = local_max if value_max is None else max(value_max, local_max)
                absolute = np.abs(finite_values)
                local_abs_min = float(absolute.min())
                local_abs_max = float(absolute.max())
                abs_min = local_abs_min if abs_min is None else min(abs_min, local_abs_min)
                abs_max = local_abs_max if abs_max is None else max(abs_max, local_abs_max)
    except Exception as exc:
        row.update(status="read_error", detail=type(exc).__name__)
        return row

    row.update(
        {
            "min": "" if value_min is None else value_min,
            "max": "" if value_max is None else value_max,
            "min_abs": "" if abs_min is None else abs_min,
            "max_abs": "" if abs_max is None else abs_max,
            "status": "passed",
            "detail": "",
        }
    )
    return row


def _audit_hdf5_file(
    source_name: str,
    path: Path,
    scan_numeric: bool,
    max_chunk_bytes: int,
    h5py: Any,
    np: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    object_rows: list[dict[str, Any]] = []
    quarantine_rows: list[dict[str, Any]] = []
    scan_rows: list[dict[str, Any]] = []
    canonical_by_address: dict[int, str] = {}
    expanded_groups: set[int] = set()
    scanned_datasets: set[int] = set()

    try:
        h5_file = h5py.File(path, "r")
    except Exception as exc:
        raise AuditError(f"HDF5 open failed for {source_name}: {type(exc).__name__}: {exc}") from exc

    with h5_file:
        root_row, root_quarantine = _make_object_row(
            source_name,
            "/",
            h5_file["/"],
            "root",
            "",
            "expanded",
            h5_file,
            h5py,
            np,
        )
        object_rows.append(root_row)
        quarantine_rows.extend(root_quarantine)
        root_address = _object_address(h5_file["/"], h5py)
        if root_address is not None:
            canonical_by_address[root_address] = "/"
            expanded_groups.add(root_address)

        def walk(group: Any, group_path: str, ancestor_addresses: frozenset[int]) -> None:
            for name in sorted(group.keys()):
                object_path = f"/{name}" if group_path == "/" else f"{group_path}/{name}"
                try:
                    link = group.get(name, getlink=True)
                except Exception as exc:
                    row, quarantine = _link_row(
                        source_name, object_path, "unreadable_link", "unknown", ""
                    )
                    row["traversal_status"] = f"link_read_error:{type(exc).__name__}"
                    object_rows.append(row)
                    quarantine_rows.append(quarantine)
                    continue

                if isinstance(link, h5py.SoftLink):
                    row, quarantine = _link_row(
                        source_name, object_path, "soft_link", "soft", str(link.path)
                    )
                    object_rows.append(row)
                    quarantine_rows.append(quarantine)
                    continue
                if isinstance(link, h5py.ExternalLink):
                    target = _strict_json({"filename": str(link.filename), "path": str(link.path)})
                    row, quarantine = _link_row(
                        source_name, object_path, "external_link", "external", target
                    )
                    object_rows.append(row)
                    quarantine_rows.append(quarantine)
                    continue

                try:
                    obj = group.get(name, getlink=False)
                except Exception as exc:
                    row, quarantine = _link_row(
                        source_name, object_path, "unreadable_hard_link", "hard", ""
                    )
                    row["traversal_status"] = f"target_read_error:{type(exc).__name__}"
                    object_rows.append(row)
                    quarantine_rows.append(quarantine)
                    continue
                if obj is None:
                    row, quarantine = _link_row(
                        source_name, object_path, "broken_hard_link", "hard", ""
                    )
                    object_rows.append(row)
                    quarantine_rows.append(quarantine)
                    continue

                address = _object_address(obj, h5py)
                canonical = canonical_by_address.get(address) if address is not None else None
                traversal_status = "expanded"
                link_target = ""
                if canonical is not None and canonical != object_path:
                    link_target = canonical
                    traversal_status = "hard_link_alias"
                elif address is not None:
                    canonical_by_address[address] = object_path

                row, quarantines = _make_object_row(
                    source_name,
                    object_path,
                    obj,
                    "hard",
                    link_target,
                    traversal_status,
                    h5_file,
                    h5py,
                    np,
                )
                object_rows.append(row)
                quarantine_rows.extend(quarantines)

                if isinstance(obj, h5py.Dataset) and scan_numeric:
                    if address is not None and address in scanned_datasets:
                        scan_row = {column: "" for column in NUMERIC_SCAN_COLUMNS}
                        scan_row.update(
                            {
                                "source_file": source_name,
                                "object_path": object_path,
                                "dtype": str(obj.dtype),
                                "element_count": int(obj.size),
                                "status": "skipped_hard_link_alias",
                                "detail": link_target,
                            }
                        )
                    else:
                        scan_row = _scan_dataset(
                            source_name,
                            object_path,
                            obj,
                            max_chunk_bytes,
                            h5py,
                            np,
                        )
                        if address is not None:
                            scanned_datasets.add(address)
                    scan_rows.append(scan_row)

                if isinstance(obj, h5py.Group):
                    if address is not None and address in ancestor_addresses:
                        row["traversal_status"] = "hard_link_cycle_not_expanded"
                        quarantine_rows.append(
                            {
                                "source_file": source_name,
                                "object_path": object_path,
                                "object_type": "group",
                                "reason": "hard_link_cycle",
                                "evidence": "Group address already exists in the current ancestor chain.",
                                "blocks_evaluation_use": True,
                            }
                        )
                    elif address is not None and address in expanded_groups:
                        row["traversal_status"] = "hard_link_alias_not_reexpanded"
                    else:
                        next_ancestors = ancestor_addresses
                        if address is not None:
                            expanded_groups.add(address)
                            next_ancestors = frozenset(set(ancestor_addresses) | {address})
                        walk(obj, object_path, next_ancestors)

        initial_ancestors = frozenset({root_address}) if root_address is not None else frozenset()
        walk(h5_file["/"], "/", initial_ancestors)

        file_metadata = {
            "hdf5_lib_version": h5py.version.hdf5_version,
            "h5py_version": h5py.version.version,
            "root_userblock_size": int(h5_file.userblock_size),
            "object_count": len(object_rows),
            "dataset_count": sum(row["object_type"] == "dataset" for row in object_rows),
            "reference_dtype_dataset_count": sum(
                row["object_type"] == "dataset" and bool(row["reference_dtype_json"])
                for row in object_rows
            ),
            "external_storage_dataset_count": sum(
                row["object_type"] == "dataset" and bool(row["external_storage_json"])
                for row in object_rows
            ),
            "virtual_dataset_count": sum(
                row["object_type"] == "dataset" and row["is_virtual"] is True
                for row in object_rows
            ),
            "quarantine_count": len(quarantine_rows),
            "numeric_scan_requested": scan_numeric,
            "numeric_scan_row_count": len(scan_rows),
        }

    object_rows.sort(key=lambda row: (row["source_file"], row["object_path"]))
    quarantine_rows.sort(
        key=lambda row: (row["source_file"], row["object_path"], row["reason"])
    )
    scan_rows.sort(key=lambda row: (row["source_file"], row["object_path"]))
    return object_rows, quarantine_rows, scan_rows, file_metadata


def _prepare_output_directory(output_dir: Path) -> None:
    if output_dir.exists():
        if not output_dir.is_dir() or output_dir.is_symlink():
            raise AuditError(f"--output must be a non-symlink directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise AuditError(
                f"append-only policy: output directory must be empty or new: {output_dir}"
            )
    else:
        output_dir.mkdir(parents=True, exist_ok=False)


def _atomic_json(path: Path, value: Any) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        json.dump(
            value,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def _atomic_csv(path: Path, rows: Iterable[dict[str, Any]], columns: Sequence[str]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        temporary = Path(stream.name)
    temporary.replace(path)


def run_audit(
    zip_path: Path,
    input_root: Path,
    output_dir: Path,
    *,
    source_url: str | None = None,
    scan_numeric: bool = False,
    scan_chunk_bytes: int = 64 * 1024 * 1024,
) -> dict[str, Any]:
    """Run a byte-integrity and HDF5 metadata audit without extracting files."""
    zip_path = Path(zip_path)
    input_root = Path(input_root)
    output_dir = Path(output_dir)
    if scan_chunk_bytes <= 0:
        raise AuditError("--scan-chunk-bytes must be positive")

    archive_manifest, target_zip_infos, target_archive_sha256 = _inspect_archive(
        zip_path, source_url
    )
    input_targets = _resolve_input_targets(input_root)
    h5py, np = _load_hdf5_dependencies()

    target_manifests: list[dict[str, Any]] = []
    all_object_rows: list[dict[str, Any]] = []
    all_quarantine_rows: list[dict[str, Any]] = []
    all_scan_rows: list[dict[str, Any]] = []
    hdf5_files: dict[str, Any] = {}

    resolved_input_root = input_root.resolve(strict=True)
    for target in TARGET_MAT_FILES:
        path = input_targets[target]
        input_sha256, input_crc32, input_size_bytes = _sha256_and_crc32(path)
        zip_info = target_zip_infos[target]
        archive_member = _safe_member_name(zip_info)
        archive_sha256 = target_archive_sha256[target]
        sha256_match = input_sha256 == archive_sha256
        size_match = input_size_bytes == zip_info.file_size
        crc32_match = input_crc32 == f"{zip_info.CRC:08x}"
        if not sha256_match:
            raise AuditError(
                f"extracted SHA-256 does not match streamed archive member for {target}: "
                f"input={input_sha256}, archive={archive_sha256}; "
                f"aux_size={input_size_bytes}/{zip_info.file_size}, "
                f"aux_crc={input_crc32}/{zip_info.CRC:08x}"
            )
        if not size_match or not crc32_match:
            raise AuditError(
                f"target SHA-256 matched but auxiliary archive metadata was inconsistent for {target}: "
                f"size={input_size_bytes}/{zip_info.file_size}, "
                f"crc={input_crc32}/{zip_info.CRC:08x}"
            )

        object_rows, quarantine_rows, scan_rows, file_metadata = _audit_hdf5_file(
            target,
            path,
            scan_numeric,
            scan_chunk_bytes,
            h5py,
            np,
        )
        all_object_rows.extend(object_rows)
        all_quarantine_rows.extend(quarantine_rows)
        all_scan_rows.extend(scan_rows)
        hdf5_files[target] = file_metadata
        target_manifests.append(
            {
                "target": target,
                "archive_member": archive_member,
                "archive_member_size_bytes": zip_info.file_size,
                "archive_member_crc32": f"{zip_info.CRC:08x}",
                "archive_member_streamed_sha256": archive_sha256,
                "input_relative_path": path.relative_to(resolved_input_root).as_posix(),
                "input_size_bytes": input_size_bytes,
                "input_crc32": input_crc32,
                "input_sha256": input_sha256,
                "sha256_match": True,
                "auxiliary_size_match": True,
                "auxiliary_crc32_match": True,
                "hdf5_open_status": "passed",
            }
        )

    all_object_rows.sort(key=lambda row: (row["source_file"], row["object_path"]))
    all_quarantine_rows.sort(
        key=lambda row: (row["source_file"], row["object_path"], row["reason"])
    )
    all_scan_rows.sort(key=lambda row: (row["source_file"], row["object_path"]))

    object_type_counts = Counter(row["object_type"] for row in all_object_rows)
    matlab_class_counts = Counter(
        row["matlab_class"] for row in all_object_rows if row["matlab_class"]
    )
    quarantine_reason_counts = Counter(row["reason"] for row in all_quarantine_rows)
    scan_status_counts = Counter(row["status"] for row in all_scan_rows)

    data_manifest = {
        "schema_version": SCHEMA_VERSION,
        "archive": archive_manifest,
        "targets": target_manifests,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "mode": "numeric_scan" if scan_numeric else "metadata_only",
        "scan_chunk_bytes": scan_chunk_bytes if scan_numeric else None,
        "integrity": {
            "zip_member_crc": "passed",
            "required_target_count": len(target_manifests),
            "all_target_streamed_sha256_match": True,
            "all_target_auxiliary_size_and_crc32_match": True,
            "all_targets_hdf5_readable": True,
        },
        "hdf5_files": hdf5_files,
        "object_count": len(all_object_rows),
        "object_type_counts": dict(sorted(object_type_counts.items())),
        "matlab_class_counts": dict(sorted(matlab_class_counts.items())),
        "reference_dtype_dataset_count": sum(
            row["object_type"] == "dataset" and bool(row["reference_dtype_json"])
            for row in all_object_rows
        ),
        "quarantine_count": len(all_quarantine_rows),
        "quarantine_reason_counts": dict(sorted(quarantine_reason_counts.items())),
        "numeric_scan_status_counts": dict(sorted(scan_status_counts.items())),
        "data_gate": {
            "byte_integrity": "passed",
            "hdf5_readability": "passed",
            "physical_semantic_mapping": "blocked_pending_review",
            "termination_and_rul_eligibility": "not_assessed",
            "benchmark_l_modeling": "blocked",
            "overall": "partial_integrity_only",
        },
    }

    _prepare_output_directory(output_dir)
    _atomic_json(output_dir / "DATA_MANIFEST.json", data_manifest)
    _atomic_csv(output_dir / "HDF5_OBJECTS.csv", all_object_rows, OBJECT_COLUMNS)
    _atomic_csv(output_dir / "QUARANTINE.csv", all_quarantine_rows, QUARANTINE_COLUMNS)
    if scan_numeric:
        _atomic_csv(output_dir / "HDF5_NUMERIC_SCAN.csv", all_scan_rows, NUMERIC_SCAN_COLUMNS)
    _atomic_json(output_dir / "AUDIT_SUMMARY.json", summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the capacitor stress ZIP and audit extracted ES10/12/14 HDF5 metadata. "
            "The script never extracts archive members."
        )
    )
    parser.add_argument("--zip", required=True, type=Path, help="Original Electrical Stress ZIP")
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Directory containing exactly one each of ES10.mat, ES12.mat, and ES14.mat",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New or empty append-only output directory",
    )
    parser.add_argument(
        "--source-url",
        default=None,
        help="Optional public provenance URL stored verbatim in DATA_MANIFEST.json",
    )
    parser.add_argument(
        "--scan-numeric",
        action="store_true",
        help="Explicitly stream fixed-width numeric datasets to count NaN/Inf and ranges",
    )
    parser.add_argument(
        "--scan-chunk-bytes",
        type=int,
        default=64 * 1024 * 1024,
        help="Maximum requested numeric hyperslab bytes (default: 67108864)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = run_audit(
        args.zip,
        args.input,
        args.output,
        source_url=args.source_url,
        scan_numeric=args.scan_numeric,
        scan_chunk_bytes=args.scan_chunk_bytes,
    )
    print(
        _strict_json(
            {
                "status": "passed",
                "output": str(args.output),
                "mode": summary["mode"],
                "object_count": summary["object_count"],
                "quarantine_count": summary["quarantine_count"],
                "data_gate": summary["data_gate"]["overall"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
