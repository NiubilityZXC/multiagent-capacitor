"""Compose source-bound Workbook events into group observations, never targets.

The outer caller owns approval, member ordering, container checks, and loading
isolated Workbook bytes. This module neither opens paths nor grants a release.
"""
from itertools import zip_longest
import math

from experiments.audit_cap.ren_target_workbook import events
from experiments.audit_cap.ren_step_summary_join import join_step_summaries


def _finite_difference(a, b):
    value = a - b
    if not math.isfinite(value):
        raise ValueError('nonfinite group comparison')
    return value


def collect_group(members, schemas, allowed, load_workbook):
    """Consume each named member exactly once and verify every event position.

    members is the already-approved ordered sequence; load_workbook(member)
    supplies isolated bytes. Source identity stays attached to every summary
    and segment endpoint. Memory scales with steps/summaries, not record rows.
    The returned source list is NOT a physical-device identity claim.
    """
    members = list(members)
    if (not members or any(type(m) is not str or not m for m in members)
            or len(set(members)) != len(members)):
        raise ValueError('empty or duplicate source members')
    if any(m not in schemas for m in members):
        raise ValueError('missing source schema')
    summaries, summary_positions, cycles, cycle_positions = [], [], [], []
    extras, coverage = [], []

    def record_rows():
        previous = None
        for member in members:
            schema = schemas[member]
            def positions():
                for sheet in schema['sheets']:
                    name = sheet['name']
                    kind = name if name in ('step', 'cycle') else 'record'
                    for row in range(2, sheet['nrows'] + 1):
                        yield kind, [sheet['index'], name, row]
            stream = events(load_workbook(member), allowed, schema)
            counts = dict(record=0, step=0, cycle=0)
            try:
                for event, expected in zip_longest(stream, positions()):
                    if (event is None or expected is None
                            or (event['kind'], event['position']) != expected):
                        raise ValueError('group event coverage mismatch')
                    kind, value = event['kind'], event['values']
                    location = [member] + event['position']
                    counts[kind] += 1
                    if kind == 'step':
                        summaries.append(value)
                        summary_positions.append(location)
                    elif kind == 'cycle':
                        cycles.append(value)
                        cycle_positions.append(location)
                    else:
                        energy = event['energy_mWh']
                        if previous != value[:3]:
                            extras.append(dict(key=value[:3], first_position=location,
                                last_position=location, rows=0, first_energy_mWh=energy,
                                last_energy_mWh=energy, energy_missing_rows=0))
                        item = extras[-1]
                        item['last_position'] = location
                        item['last_energy_mWh'] = energy
                        item['rows'] += 1
                        item['energy_missing_rows'] += int(energy is None)
                        previous = value[:3]
                        yield value
            finally:
                stream.close()
            coverage.append(dict(member=member, **counts))

    iterator = record_rows()
    try:
        result = join_step_summaries(iterator, summaries)
    finally:
        iterator.close()
    if len(result['segments']) != len(extras):
        raise ValueError('group segment reconstruction mismatch')
    for segment, extra in zip(result['segments'], extras):
        if segment['key'] != extra['key'] or segment['rows'] != extra['rows']:
            raise ValueError('group segment reconstruction mismatch')
    energy_joins = []
    for joined in result['joins']:
        difference = None
        if joined['status'] == 'UNIQUE_KEY_OBSERVATION':
            segment = extras[joined['segment_indices'][0]]
            summary = summaries[joined['summary_indices'][0]]
            if segment['energy_missing_rows'] == 0:
                difference = _finite_difference(summary[5], segment['last_energy_mWh'])
        energy_joins.append(dict(key=joined['key'],
            summary_minus_last_energy_mWh=difference,
            comparison_available=difference is not None))

    # Retain every member of each native cycle, including multiple charge steps.
    grouped = {}
    for i, segment in enumerate(result['segments']):
        grouped.setdefault(segment['key'][0], [[], []])[0].append(i)
    for i, row in enumerate(cycles):
        grouped.setdefault(row[0], [[], []])[1].append(i)
    cycle_observations = []
    for cycle, (segment_ids, summary_ids) in grouped.items():
        signs = dict(positive=[], negative=[], zero=[], mixed=[])
        for i in segment_ids:
            s = result['segments'][i]
            category = ('positive' if s['positive_current_rows'] == s['rows'] else
                        'negative' if s['negative_current_rows'] == s['rows'] else
                        'zero' if s['zero_current_rows'] == s['rows'] else 'mixed')
            signs[category].append(i)
        # These are explicit arithmetic hypotheses, not instrument semantics.
        differences = None
        if len(summary_ids) == 1 and segment_ids:
            row = cycles[summary_ids[0]]
            differences = {}
            for column, sign in ((1, 'positive'), (2, 'negative')):
                ids = signs[sign]
                total = math.fsum(result['segments'][i]['last'][7] for i in ids) if ids else None
                differences[sign] = (None if total is None else _finite_difference(row[column], total))
        cycle_observations.append(dict(cycle=cycle, segment_indices=segment_ids,
            summary_indices=summary_ids, current_sign_segment_indices=signs,
            cycle_capacity_minus_current_sign_bucket_endpoint_sum_mAh=differences,
            sum_semantics_verified=False))
    result.update(source_members=members, source_coverage=coverage,
        summary_positions=summary_positions, segment_source_energy=extras,
        energy_joins=energy_joins, cycle_summaries=cycles, cycle_positions=cycle_positions,
        cycle_observations=cycle_observations,
        last_observed_cycle=result['segments'][-1]['key'][0],
        termination_reason_available=False, failure_event_verified=False,
        physical_identity_verified=False, p2_eligible=False)
    return result
