"""Pure step-summary observations; no XLS access, target, tolerance or Gate.

Canonical summary: (cycle, step, status, time_us, mAh, mWh[, initial_V, end_V]).
The future XLS adapter must verify units/types/provenance independently. Input
rows use ren_step_evidence's eight-field canonical record representation.
Energy is retained but NOT compared: that representation has no energy field.
Memory is proportional to step segments and summaries, not raw record count.
"""
import math

from experiments.audit_cap.ren_step_evidence import iter_step_evidence


def _summary(raw):
    if not isinstance(raw, (tuple, list)) or len(raw) not in (6, 8):
        raise ValueError("summary must have six or eight fields")
    if any(type(v) is not int for v in raw[:4]):
        raise ValueError("summary key/time must be integers")
    if any(raw[i] < 0 for i in (0, 1, 3)):
        raise ValueError("negative summary identifier/time")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in raw[4:]):
        raise ValueError("invalid summary measurement")
    return tuple(raw)


def _difference(summary, record):
    value = summary - record
    if not math.isfinite(value):
        raise ValueError("nonfinite comparison")
    return value


def join_step_summaries(rows, summaries):
    """Fully consume both sources before returning any observations.

    Duplicate keys on either side are ambiguous: preserve every member index,
    never choose the first, aggregate, or form Cartesian numeric comparisons.
    Time comparisons expose BOTH last local time and sampled elapsed time;
    neither is silently interpreted as the instrument's step duration.
    Returned indices are zero-based within these two fully consumed streams.
    """
    segments = list(iter_step_evidence(rows))
    table = [_summary(row) for row in summaries]
    groups = {}
    for i, segment in enumerate(segments):
        groups.setdefault(tuple(segment['key']), [[], []])[0].append(i)
    for i, summary in enumerate(table):
        groups.setdefault(summary[:3], [[], []])[1].append(i)
    joins = []
    for key, (record_ids, summary_ids) in groups.items():
        entry = dict(key=list(key), segment_indices=record_ids,
                     summary_indices=summary_ids, comparison=None)
        if len(record_ids) > 1 or len(summary_ids) > 1:
            entry['status'] = 'AMBIGUOUS_KEY'
        elif not record_ids:
            entry['status'] = 'SUMMARY_ONLY'
        elif not summary_ids:
            entry['status'] = 'RECORD_ONLY'
        else:
            segment, summary = segments[record_ids[0]], table[summary_ids[0]]
            first, last = segment['first'], segment['last']
            entry['status'] = 'UNIQUE_KEY_OBSERVATION'
            entry['comparison'] = dict(
                summary_minus_last_time_us=summary[3] - last[4],
                summary_minus_sampled_elapsed_us=summary[3] - (last[4] - first[4]),
                summary_minus_last_charge_mAh=_difference(summary[4], last[7]),
                summary_minus_first_voltage_V=(
                    _difference(summary[6], first[5]) if len(summary) == 8 else None),
                summary_minus_last_voltage_V=(
                    _difference(summary[7], last[5]) if len(summary) == 8 else None),
                voltage_endpoints_available=len(summary) == 8,
                energy_comparison='UNAVAILABLE_RECORD_ENERGY')
        joins.append(entry)
    return dict(segments=segments, summaries=[list(s) for s in table], joins=joins,
                numeric_target_emitted=False, target_verified=False,
                data_gate_pass=False)
