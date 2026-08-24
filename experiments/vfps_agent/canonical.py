"""Canonical, strict JSON helpers for the mock-only VFPS harness.

The module intentionally has no provider or filesystem side effects.  It is the
single serialization boundary used by contracts and durable ledgers.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping


class StrictJSONError(ValueError):
    """Raised when JSON is ambiguous, non-finite, or non-canonicalizable."""


class ForbiddenProxyError(StrictJSONError):
    """Raised when a packet contains a future or identity proxy."""


_FORBIDDEN_KEY_FRAGMENTS = frozenset(
    {
        # Future/outcome proxies.
        "future",
        "future_timestamp",
        "suffix",
        "suffix_length",
        "full_series",
        "complete_series",
        "full_trajectory",
        "series_length",
        "total_cycles",
        "final_length",
        "final_index",
        "row_count",
        "file_size",
        "byte_size",
        "max_cycle",
        "max_event",
        "max_timestamp",
        "last_timestamp",
        "realized_timestamp",
        "future_available_at",
        "end_of_life",
        "eol",
        "eol_label",
        "termination",
        "terminated_at",
        "remaining_cycles",
        "true_rul",
        "actual_rul",
        "rul_label",
        "ground_truth",
        "actual_target",
        "target_label",
        "outer_error",
        "outer_test_rank",
        "outer_test_error",
        "shadow_error",
        "test_rank",
        "test_error",
        "held_out_error",
        # Physical/file identity proxies.
        "unit_id",
        "unit_name",
        "device_id",
        "capacitor_id",
        "cell_id",
        "serial_number",
        "specimen_id",
        "specimen_alias",
        "unit_alias",
        "device_alias",
        "capacitor_alias",
        "cell_alias",
        "member_id",
        "private_identity",
        "source_uri",
        "source_url",
        "file_path",
        "filepath",
        "filename",
        "source_path",
        "sheet_name",
        "raw_header",
        # Secret-bearing fields are never part of a scientific packet or ledger.
        "api_key",
        "apikey",
        "authorization",
        "credential",
        "credentials",
        "client_secret",
        "access_key",
        "private_key",
    }
)

_FORBIDDEN_VALUE_PATTERNS = (
    ("future", re.compile(r"\b(?:future|suffix|eol|end[ _-]?of[ _-]?life|termination)\b", re.I)),
    (
        "identity",
        re.compile(
            r"\b(?:unit|device|capacitor|cell|serial)[ _:#-]*(?:id[ _:#-]*)?[0-9]{1,}\b",
            re.I,
        ),
    ),
    (
        "path",
        re.compile(
            r"(?:^|\s)(?:/[^\s]+|[A-Za-z]:\\[^\s]+|[^\s]+\.(?:csv|mat|xlsx?|h5|hdf5|zip|rar))(?:$|\s)",
            re.I,
        ),
    ),
    ("secret", re.compile(r"CANARY[_-]DO[_-]NOT[_-]PERSIST", re.I)),
    ("secret", re.compile(r"\bark-[A-Za-z0-9_-]{20,}\b", re.I)),
    ("secret", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b", re.I)),
    ("secret", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*\b", re.I)),
)


def _reject_constant(token: str) -> None:
    raise StrictJSONError(f"non-finite JSON constant is forbidden: {token}")


def _parse_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise StrictJSONError("non-finite JSON number is forbidden")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError("duplicate JSON object key is forbidden")
        result[key] = value
    return result


def strict_json_loads(payload: str | bytes | bytearray) -> Any:
    """Parse JSON while rejecting duplicate keys and every non-finite number."""

    if isinstance(payload, (bytes, bytearray)):
        try:
            text = bytes(payload).decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise StrictJSONError("JSON must be valid UTF-8") from exc
    elif isinstance(payload, str):
        text = payload
    else:
        raise TypeError("strict_json_loads accepts str or bytes")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_parse_float,
        )
    except StrictJSONError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise StrictJSONError("invalid strict JSON") from exc
    _validate_finite(value)
    return value


def _validate_finite(value: Any) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StrictJSONError("non-finite number is forbidden")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise StrictJSONError("JSON object keys must be strings")
            _validate_finite(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_finite(item)
        return
    raise StrictJSONError(f"unsupported JSON value type: {type(value).__name__}")


def to_primitive(value: Any) -> Any:
    """Convert typed contracts to deterministic JSON-compatible primitives."""

    if isinstance(value, Enum):
        return to_primitive(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise StrictJSONError("JSON object keys must be strings")
            result[key] = to_primitive(item)
        return result
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StrictJSONError("non-finite number is forbidden")
        return value
    raise StrictJSONError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize a value with one canonical byte representation."""

    primitive = to_primitive(value)
    _validate_finite(primitive)
    return json.dumps(
        primitive,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _normalise_key(key: str) -> str:
    step = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^a-z0-9]+", "_", step.lower()).strip("_")


def _scan_string(value: str) -> None:
    # A fixed public protocol route is part of the typed Ark request contract,
    # not a local/private filesystem locator.  Keep the exception exact so no
    # caller-controlled path prefix or suffix is admitted.
    if value == "/responses":
        return
    normalised = _normalise_key(value)
    for proxy in _FORBIDDEN_KEY_FRAGMENTS:
        if proxy in normalised:
            category = "identity" if proxy in {
                "unit_id", "unit_name", "device_id", "capacitor_id", "cell_id",
                "serial_number", "specimen_id", "specimen_alias", "unit_alias",
                "device_alias", "capacitor_alias", "cell_alias", "member_id", "private_identity",
                "file_path", "filepath", "filename", "source_path", "source_uri",
                "source_url", "sheet_name", "raw_header",
            } else "secret" if proxy in {
                "api_key", "apikey", "authorization", "credential", "credentials",
                "client_secret", "access_key", "private_key",
            } else "future"
            raise ForbiddenProxyError(f"forbidden {category} proxy")
    for category, pattern in _FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(value):
            raise ForbiddenProxyError(f"forbidden {category} proxy")


def scan_forbidden_proxies(value: Any) -> None:
    """Recursively scan *both object keys and string values*.

    Error messages deliberately omit offending values so a secret canary is not
    copied into logs by an exception handler.
    """

    primitive = to_primitive(value)

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                _scan_string(key)
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            _scan_string(item)

    visit(primitive)


def strict_canonical_loads(payload: str | bytes | bytearray) -> Any:
    """Parse strict JSON and require its input bytes to already be canonical."""

    value = strict_json_loads(payload)
    raw = bytes(payload) if isinstance(payload, (bytes, bytearray)) else payload.encode("utf-8")
    if raw != canonical_bytes(value):
        raise StrictJSONError("JSON is valid but not canonical")
    return value
