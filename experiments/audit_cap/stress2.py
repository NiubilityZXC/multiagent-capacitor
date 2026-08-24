"""Strict parser and label builder for the NASA Stress-2 capacitor data.

The MAT file contains relative percentage changes, not physical capacitance or
resistance.  Its six columns have no embedded physical-unit identifiers.  This
module therefore uses stable column-surrogate keys and carries the identity and
termination limitations into every derived row.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat

EXPECTED_ZIP_SHA256 = "944cd2284cd01925088e97e5f5e2f337ee8b37800346fd2610d1bbaa6accacfb"
EXPECTED_MAT_SHA256 = "9db651a10f92d2046a477838c08fe1cdbaf27d7bc4062a856a373721400cb4a3"
EXPECTED_MEMBER = "EOS_DataSet.mat"
REQUIRED_VARIABLES = frozenset({"aging_time", "C", "ESR"})
CAPACITY_LOSS_THRESHOLD_PCT = 20.0
ESR_INCREASE_THRESHOLD_PCT = 100.0


@dataclass(frozen=True)
class Stress2Data:
    """Canonical Stress-2 representation."""

    aging_time_h: np.ndarray
    capacity_loss_pct: np.ndarray
    esr_increase_pct: np.ndarray
    events: pd.DataFrame
    endpoints: pd.DataFrame
    source_zip_sha256: str
    source_mat_sha256: str


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_member(zip_path: Path, verify_hash: bool) -> tuple[bytes, str]:
    zip_hash = sha256_file(zip_path)
    if verify_hash and zip_hash != EXPECTED_ZIP_SHA256:
        raise ValueError(f"unexpected Stress-2 ZIP SHA-256: {zip_hash}")
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"Stress-2 ZIP CRC failure: {bad}")
        names = set(archive.namelist())
        if EXPECTED_MEMBER not in names:
            raise ValueError(f"missing required member: {EXPECTED_MEMBER}")
        info = archive.getinfo(EXPECTED_MEMBER)
        if info.is_dir() or Path(info.filename).is_absolute() or ".." in Path(info.filename).parts:
            raise ValueError("unsafe Stress-2 member path")
        payload = archive.read(info)
    mat_hash = sha256_bytes(payload)
    if verify_hash and mat_hash != EXPECTED_MAT_SHA256:
        raise ValueError(f"unexpected Stress-2 MAT SHA-256: {mat_hash}")
    return payload, zip_hash


def _validate_arrays(raw: dict[str, object]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    keys = {key for key in raw if not key.startswith("__")}
    missing = REQUIRED_VARIABLES - keys
    if missing:
        raise ValueError(f"missing Stress-2 variables: {sorted(missing)}")
    unexpected = keys - REQUIRED_VARIABLES
    if unexpected:
        raise ValueError(f"unexpected Stress-2 variables: {sorted(unexpected)}")

    time_h = np.asarray(raw["aging_time"], dtype=np.float64).reshape(-1)
    c_loss = np.asarray(raw["C"], dtype=np.float64)
    esr_inc = np.asarray(raw["ESR"], dtype=np.float64)
    if time_h.shape != (11,):
        raise ValueError(f"unexpected aging_time shape: {time_h.shape}")
    if c_loss.shape != (11, 6) or esr_inc.shape != (11, 6):
        raise ValueError(f"unexpected C/ESR shapes: {c_loss.shape}, {esr_inc.shape}")
    if not np.all(np.isfinite(time_h)) or not np.all(np.isfinite(c_loss)) or not np.all(np.isfinite(esr_inc)):
        raise ValueError("Stress-2 contains NaN or Inf")
    if not np.all(np.diff(time_h) > 0):
        raise ValueError("aging_time must be strictly increasing")
    if not np.all(c_loss[0] == 0.0) or not np.all(esr_inc[0] == 0.0):
        raise ValueError("first row must be the relative-change baseline")
    return time_h, c_loss, esr_inc


def _event_table(time_h: np.ndarray, c_loss: np.ndarray, esr_inc: np.ndarray) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in range(c_loss.shape[1]):
        unit_key = f"stress2:column:{column + 1:02d}"
        first_c = np.flatnonzero(c_loss[:, column] >= CAPACITY_LOSS_THRESHOLD_PCT)
        first_r = np.flatnonzero(esr_inc[:, column] >= ESR_INCREASE_THRESHOLD_PCT)
        first_c_idx = int(first_c[0]) if first_c.size else None
        first_r_idx = int(first_r[0]) if first_r.size else None
        for event_idx, hour in enumerate(time_h):
            c_ratio = 1.0 - c_loss[event_idx, column] / 100.0
            r_ratio = 1.0 + esr_inc[event_idx, column] / 100.0
            margin_c = (c_ratio - 0.8) / 0.2
            margin_r = 2.0 - r_ratio
            rows.append(
                {
                    "dataset_unit_key": unit_key,
                    "physical_unit_id": None,
                    "unit_identity_status": "column_surrogate",
                    "possible_duplicate_group": "unknown",
                    "source_column_index_0based": column,
                    "event_index_0based": event_idx,
                    "aging_time_h": float(hour),
                    "measurement_time_h": float(hour),
                    "causal_availability_time_h": float(hour),
                    "availability_semantics": "same_event_assumption_not_in_raw",
                    "capacity_loss_pct": float(c_loss[event_idx, column]),
                    "esr_increase_pct": float(esr_inc[event_idx, column]),
                    "capacity_ratio": float(c_ratio),
                    "esr_ratio": float(r_ratio),
                    "soh_capacity": float(c_ratio),
                    "soh_esr_inverse": float(1.0 / r_ratio),
                    "composite_health_margin": float(np.clip(min(margin_c, margin_r), 0.0, 1.0)),
                    "is_at_risk_capacity": first_c_idx is None or event_idx < first_c_idx,
                    "is_at_risk_esr": first_r_idx is None or event_idx < first_r_idx,
                    "stress_voltage_v": 10.0,
                    "stress_voltage_source": "external_dataset_metadata_not_mat",
                    "termination_reason": "unknown",
                    "source_member": EXPECTED_MEMBER,
                }
            )
    return pd.DataFrame(rows)


def _one_endpoint(
    values: np.ndarray,
    time_h: np.ndarray,
    threshold: float,
    endpoint: str,
    unit_key: str,
) -> dict[str, object]:
    crossings = np.flatnonzero(values >= threshold)
    if crossings.size:
        upper_idx = int(crossings[0])
        if upper_idx == 0:
            lower_time = None
            lower_idx = None
        else:
            lower_idx = upper_idx - 1
            lower_time = float(time_h[lower_idx])
        return {
            "dataset_unit_key": unit_key,
            "endpoint": endpoint,
            "status": "interval_crossing",
            "lower_time_h": lower_time,
            "upper_time_h": float(time_h[upper_idx]),
            "lower_open": True,
            "upper_closed": True,
            "last_non_crossing_index_0based": lower_idx,
            "first_crossing_index_0based": upper_idx,
            "censor_time_h": None,
            "censor_type": None,
            "threshold": threshold,
            "termination_reason": "unknown",
            "rul_score_eligible": False,
        }
    return {
        "dataset_unit_key": unit_key,
        "endpoint": endpoint,
        "status": "not_observed_through_last_measurement",
        "lower_time_h": float(time_h[-1]),
        "upper_time_h": None,
        "lower_open": True,
        "upper_closed": False,
        "last_non_crossing_index_0based": int(len(time_h) - 1),
        "first_crossing_index_0based": None,
        "censor_time_h": float(time_h[-1]),
        "censor_type": "unknown_termination_not_administrative",
        "threshold": threshold,
        "termination_reason": "unknown",
        "rul_score_eligible": False,
    }


def _endpoint_table(time_h: np.ndarray, c_loss: np.ndarray, esr_inc: np.ndarray) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in range(c_loss.shape[1]):
        unit_key = f"stress2:column:{column + 1:02d}"
        cap = _one_endpoint(c_loss[:, column], time_h, CAPACITY_LOSS_THRESHOLD_PCT, "capacity_loss_20pct", unit_key)
        esr = _one_endpoint(esr_inc[:, column], time_h, ESR_INCREASE_THRESHOLD_PCT, "esr_increase_100pct", unit_key)
        rows.extend([cap, esr])
        cap_upper = cap["upper_time_h"]
        esr_upper = esr["upper_time_h"]
        if cap_upper is None and esr_upper is None:
            composite = _one_endpoint(np.minimum(c_loss[:, column] / 20.0, esr_inc[:, column] / 100.0), time_h, 1.0, "capacity_or_esr", unit_key)
        elif esr_upper is None or (cap_upper is not None and float(cap_upper) <= float(esr_upper)):
            composite = dict(cap)
            composite["endpoint"] = "capacity_or_esr"
        else:
            composite = dict(esr)
            composite["endpoint"] = "capacity_or_esr"
        rows.append(composite)
    return pd.DataFrame(rows)


def load_stress2(zip_path: str | Path, verify_hash: bool = True) -> Stress2Data:
    """Load the verified ZIP without extracting or trusting member order."""

    path = Path(zip_path)
    payload, zip_hash = _read_member(path, verify_hash=verify_hash)
    mat_hash = sha256_bytes(payload)
    raw = loadmat(io.BytesIO(payload), squeeze_me=False, struct_as_record=True)
    time_h, c_loss, esr_inc = _validate_arrays(raw)
    return Stress2Data(
        aging_time_h=time_h,
        capacity_loss_pct=c_loss,
        esr_increase_pct=esr_inc,
        events=_event_table(time_h, c_loss, esr_inc),
        endpoints=_endpoint_table(time_h, c_loss, esr_inc),
        source_zip_sha256=zip_hash,
        source_mat_sha256=mat_hash,
    )
