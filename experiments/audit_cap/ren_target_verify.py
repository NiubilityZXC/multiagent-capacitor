"""Independent streaming reconstruction of group observations from native events.

Shares only the already reviewed Workbook decoding boundary with the producer.
Does not call collect_group, iter_step_evidence or join_step_summaries. A future
released caller must supply the same approved source set and isolated bytes.
This verifies observations, not physical identity, targets or Data Gate.
"""
import math

from experiments.audit_cap.ren_target_workbook import events


def equal_fields(actual, expected, path='group'):
    """Exact JSON-domain comparison, including bool/int and extra fields."""
    if type(actual) is not type(expected):
        raise ValueError(f'{path}: type mismatch')
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError(f'{path}: field mismatch')
        for key in expected:
            equal_fields(actual[key], expected[key], f'{path}.{key}')
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError(f'{path}: length mismatch')
        for i, (a, b) in enumerate(zip(actual, expected)):
            equal_fields(a, b, f'{path}[{i}]')
    elif actual != expected or (isinstance(actual, float) and not math.isfinite(actual)):
        raise ValueError(f'{path}: value mismatch')


def rebuild(members, schemas, allowed, load_workbook):
    members = list(members)
    if (not members or any(type(m) is not str or not m for m in members)
            or len(set(members)) != len(members) or any(m not in schemas for m in members)):
        raise ValueError('invalid reference sources')
    segments, extras, summaries, summary_positions = [], [], [], []
    cycles, cycle_positions, coverage = [], [], []
    previous = None
    for member in members:
        stream = events(load_workbook(member), allowed, schemas[member])
        counts = dict(record=0, step=0, cycle=0)
        try:
            for sheet in schemas[member]['sheets']:
                kind = sheet['name'] if sheet['name'] in ('step', 'cycle') else 'record'
                for row_number in range(2, sheet['nrows'] + 1):
                    event = next(stream, None)
                    position = [sheet['index'], sheet['name'], row_number]
                    if event is None or event['kind'] != kind or event['position'] != position:
                        raise ValueError('reference event coverage mismatch')
                    counts[kind] += 1
                    location = [member] + position
                    value = event['values']
                    if kind == 'step':
                        summaries.append(list(value)); summary_positions.append(location)
                        continue
                    if kind == 'cycle':
                        cycles.append(list(value)); cycle_positions.append(location)
                        continue
                    if previous is not None and (value[3] - previous[3] != 1 or value[0] < previous[0]):
                        raise ValueError('reference record chronology mismatch')
                    fresh = previous is None or value[:3] != previous[:3]
                    if fresh:
                        segments.append(dict(key=list(value[:3]), first=list(value), last=list(value),
                            rows=0, current_min_mA=value[6], current_max_mA=value[6],
                            positive_current_rows=0, negative_current_rows=0, zero_current_rows=0,
                            time_decreases=0, equal_time_pairs=0, voltage_increases=0,
                            voltage_decreases=0, current_changes=0, charge_decreases=0,
                            numeric_target_emitted=False, target_verified=False))
                        extras.append(dict(key=list(value[:3]), first_position=location,
                            last_position=location, rows=0, first_energy_mWh=event['energy_mWh'],
                            last_energy_mWh=event['energy_mWh'], energy_missing_rows=0))
                    s, x = segments[-1], extras[-1]
                    if not fresh:
                        changes = {'time_decreases': value[4] < previous[4],
                            'equal_time_pairs': value[4] == previous[4],
                            'voltage_increases': value[5] > previous[5],
                            'voltage_decreases': value[5] < previous[5],
                            'current_changes': value[6] != previous[6],
                            'charge_decreases': value[7] < previous[7]}
                        for name, changed in changes.items():
                            s[name] += int(changed)
                    s['rows'] += 1; s['last'] = list(value)
                    s['current_min_mA'] = min(s['current_min_mA'], value[6])
                    s['current_max_mA'] = max(s['current_max_mA'], value[6])
                    sign = 'positive' if value[6] > 0 else 'negative' if value[6] < 0 else 'zero'
                    s[sign + '_current_rows'] += 1
                    x['rows'] += 1; x['last_position'] = location
                    x['last_energy_mWh'] = event['energy_mWh']
                    x['energy_missing_rows'] += int(event['energy_mWh'] is None)
                    previous = list(value)
            if next(stream, None) is not None:
                raise ValueError('reference extra event')
        finally:
            stream.close()
        coverage.append(dict(member=member, **counts))
    if not segments:
        raise ValueError('reference empty records')
    # Index both sides independently; preserve first-observed order and duplicates.
    by_segment, by_summary = {}, {}
    for i, s in enumerate(segments):
        by_segment.setdefault(tuple(s['key']), []).append(i)
    for i, row in enumerate(summaries):
        by_summary.setdefault(tuple(row[:3]), []).append(i)
    keys = list(by_segment) + [key for key in by_summary if key not in by_segment]
    joins, energy_joins = [], []
    for key in keys:
        a, b = by_segment.get(key, []), by_summary.get(key, [])
        comparison, energy = None, None
        if len(a) > 1 or len(b) > 1:
            status = 'AMBIGUOUS_KEY'
        elif not a:
            status = 'SUMMARY_ONLY'
        elif not b:
            status = 'RECORD_ONLY'
        else:
            status = 'UNIQUE_KEY_OBSERVATION'
            s, row, x = segments[a[0]], summaries[b[0]], extras[a[0]]
            first, last = s['first'], s['last']
            comparison = dict(summary_minus_last_time_us=row[3]-last[4],
                summary_minus_sampled_elapsed_us=row[3]-last[4]+first[4],
                summary_minus_last_charge_mAh=row[4]-last[7],
                summary_minus_first_voltage_V=row[6]-first[5] if len(row)==8 else None,
                summary_minus_last_voltage_V=row[7]-last[5] if len(row)==8 else None,
                voltage_endpoints_available=len(row)==8,
                energy_comparison='UNAVAILABLE_RECORD_ENERGY')
            if x['energy_missing_rows'] == 0:
                energy = row[5] - x['last_energy_mWh']
        joins.append(dict(key=list(key), segment_indices=a, summary_indices=b,
                          comparison=comparison, status=status))
        energy_joins.append(dict(key=list(key), summary_minus_last_energy_mWh=energy,
                                 comparison_available=energy is not None))
    segment_cycles, table_cycles = {}, {}
    for i, s in enumerate(segments):
        segment_cycles.setdefault(s['key'][0], []).append(i)
    for i, row in enumerate(cycles):
        table_cycles.setdefault(row[0], []).append(i)
    cycle_keys = list(segment_cycles) + [k for k in table_cycles if k not in segment_cycles]
    observations = []
    for cycle in cycle_keys:
        a, b = segment_cycles.get(cycle, []), table_cycles.get(cycle, [])
        signs = dict(positive=[], negative=[], zero=[], mixed=[])
        for i in a:
            s = segments[i]
            category = 'mixed'
            for sign in ('positive', 'negative', 'zero'):
                if s[sign + '_current_rows'] == s['rows']:
                    category = sign
                    break
            signs[category].append(i)
        differences = None
        if a and len(b) == 1:
            differences = {sign: cycles[b[0]][column] - math.fsum(segments[i]['last'][7] for i in signs[sign])
                           if signs[sign] else None for sign, column in (('positive',1),('negative',2))}
        observations.append(dict(cycle=cycle, segment_indices=a, summary_indices=b,
            current_sign_segment_indices=signs,
            cycle_capacity_minus_current_sign_bucket_endpoint_sum_mAh=differences,
            sum_semantics_verified=False))
    return dict(segments=segments, summaries=summaries, joins=joins,
        numeric_target_emitted=False, target_verified=False, data_gate_pass=False,
        source_members=members, source_coverage=coverage, summary_positions=summary_positions,
        segment_source_energy=extras, energy_joins=energy_joins, cycle_summaries=cycles,
        cycle_positions=cycle_positions, cycle_observations=observations,
        last_observed_cycle=segments[-1]['key'][0], termination_reason_available=False,
        failure_event_verified=False, physical_identity_verified=False, p2_eligible=False)


def verify(saved, members, schemas, allowed, load_workbook):
    """Recompute from inputs, then compare every persisted field; raises on mismatch."""
    expected = rebuild(members, schemas, allowed, load_workbook)
    equal_fields(saved, expected)
