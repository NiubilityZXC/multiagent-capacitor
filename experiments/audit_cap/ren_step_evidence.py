"""Pure contiguous-step evidence reducer; no I/O, targets, or eligibility decision.

Input canonical rows: (cycle, step, status, record_number, time_us, V, mA, mAh).
An approved caller must independently verify source coverage and exhaust the
iterator before accepting output. Repeated noncontiguous step keys are retained
as separate segments, never overwritten; summary-table joins must check them.
"""
import math


def _row(value):
    if not isinstance(value, (tuple, list)) or len(value) != 8:
        raise ValueError("canonical row must contain eight fields")
    if any(type(x) is not int for x in value[:5]):
        raise ValueError("canonical key/time must be integers")
    if any(value[i] < 0 for i in (0, 1, 3, 4)):
        raise ValueError("negative identifier or time")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in value[5:]):
        raise ValueError("nonfinite or nonnumeric measurement")
    return tuple(value)


def iter_step_evidence(rows):
    """Bounded-memory summaries of contiguous native keys, in source order.

    No sorting, gap repair, status-to-charge assumptions, rounding, tolerances,
    capacity conversion, or final Data Gate. Time/voltage/charge changes are
    observations within each segment, not automatic quality decisions.
    """
    previous = None
    evidence = None
    for raw in rows:
        row = _row(raw)
        if previous is not None:
            if row[3] != previous[3] + 1:
                raise ValueError("record number discontinuity")
            if row[0] < previous[0]:
                raise ValueError("cycle reversal")
        if evidence is None or row[:3] != previous[:3]:
            if evidence is not None:
                yield evidence
            evidence = dict(key=list(row[:3]), first=list(row), last=list(row), rows=0,
                current_min_mA=row[6], current_max_mA=row[6],
                positive_current_rows=0, negative_current_rows=0, zero_current_rows=0,
                time_decreases=0, equal_time_pairs=0, voltage_increases=0,
                voltage_decreases=0, current_changes=0, charge_decreases=0,
                numeric_target_emitted=False, target_verified=False)
        else:
            evidence["time_decreases"] += int(row[4] < previous[4])
            evidence["equal_time_pairs"] += int(row[4] == previous[4])
            evidence["voltage_increases"] += int(row[5] > previous[5])
            evidence["voltage_decreases"] += int(row[5] < previous[5])
            evidence["current_changes"] += int(row[6] != previous[6])
            evidence["charge_decreases"] += int(row[7] < previous[7])
        evidence["rows"] += 1
        evidence["last"] = list(row)
        evidence["current_min_mA"] = min(evidence["current_min_mA"], row[6])
        evidence["current_max_mA"] = max(evidence["current_max_mA"], row[6])
        evidence["positive_current_rows"] += int(row[6] > 0)
        evidence["negative_current_rows"] += int(row[6] < 0)
        evidence["zero_current_rows"] += int(row[6] == 0)
        previous = row
    if evidence is None:
        raise ValueError("empty record stream")
    yield evidence
