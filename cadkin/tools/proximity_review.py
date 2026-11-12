"""Offline, source-bound interpretation of measured component pairs; no CAD connection."""
from datetime import datetime, timezone
import math

from cadkin.distance import distance_result
from cadkin.errors import success
from cadkin.geometry import numbers, transform_from_sw
from cadkin.tools.connections import identity
from cadkin.tools.files import json_path, read_json
from cadkin.tools.inventory import spatial_inventory
from cadkin.tools.proximity import require, nonnegative, proximity_candidates, write_result


def review_proximity(proximity, inventory, inventory_sha256, distance_sources, contact_tolerance_mm):
    require(nonnegative(contact_tolerance_mm), 'Specify a finite nonnegative contact-candidate tolerance in millimeters.', 'INVALID_ARGUMENTS')
    require(isinstance(proximity, dict) and proximity.get('proximity_schema_version') == 1 and
            proximity.get('algorithm_version') == 1 and isinstance(proximity.get('parameters'), dict), 'Expected a proximity worklist file.')
    require(set(proximity['parameters']) == {'max_box_gap_mm', 'occurrence_paths', 'max_pairs', 'max_candidates'}, 'Invalid worklist parameters.')
    # Recompute bounded hints to reject edited pair lists, hidden limits, or mixed inventory data.
    expected = proximity_candidates(inventory, inventory_sha256, **proximity['parameters'])
    for field in ('document', 'inventory_sha256', 'scope_occurrence_paths', 'candidates', 'unranked_occurrences',
                  'coverage', 'complete', 'truncated', 'errors', 'pair_scan_complete'):
        require(proximity.get(field) == expected[field], 'Worklist no longer matches its inventory/parameters.', 'EVIDENCE_MISMATCH')
    spatial, nodes = spatial_inventory(inventory)
    pairs = {tuple(c['occurrence_paths']): {**c, 'review_state': 'unmeasured', 'distance_evidence': None,
                                          'contact_confirmed': False, 'mechanical_relation_confirmed': False} for c in expected['candidates']}
    require(1 <= len(distance_sources) <= 200, 'Provide 1–200 saved distance envelopes.', 'INVALID_ARGUMENTS')
    errors, sources, seen = [], [], set()
    if not expected['complete']:
        errors.append({'code': 'SOURCE_INCOMPLETE', 'source': 'proximity', 'message': 'Worklist is incomplete.', 'source_errors': expected['errors']})
    for envelope, path, digest in distance_sources:
        require(isinstance(envelope, dict) and envelope.get('status') in ('ok', 'partial') and isinstance(envelope.get('data'), dict),
                'Use original distance envelopes; fatal errors have no usable pair evidence.', 'INVALID_DISTANCE_SOURCE')
        data = envelope['data']
        source_errors = envelope.get('errors')
        require(isinstance(source_errors, list) and all(isinstance(e, dict) for e in source_errors), 'Missing distance source errors.', 'INVALID_DISTANCE_SOURCE')
        require(data.get('component_distance_schema_version') == 1 and data.get('scope') == 'two_resolved_part_occurrences' and
                data.get('geometry_scope') == 'assembly_component_context' and
                data.get('method') == 'IModelDoc2.ClosestDistance(IComponent2,IComponent2)' and
                data.get('units') == {'api_length': 'm', 'display_length': 'mm'}, 'Unsupported distance source scope/method/units.', 'INVALID_DISTANCE_SOURCE')
        require(identity(data.get('document')) == identity(spatial['document']), 'Distance document/configuration differs.', 'EVIDENCE_MISMATCH')
        targets = data.get('targets')
        require(isinstance(targets, list) and len(targets) == 2 and all(isinstance(t, dict) for t in targets), 'Expected two distance target contexts.', 'INVALID_DISTANCE_SOURCE')
        order = [t.get('occurrence_path') for t in targets]
        require(all(isinstance(p, str) and p in nodes for p in order) and order[0] != order[1], 'Invalid distance occurrence pair.', 'EVIDENCE_MISMATCH')
        pair = tuple(sorted(order))
        require(pair in pairs, 'Measured pair is outside this worklist; use a matching worklist or review the measurement separately.', 'DISTANCE_OUTSIDE_SCOPE')
        require(pair not in seen, 'Use one distance snapshot per pair; reverse order is still the same pair.', 'DUPLICATE_DISTANCE_SOURCE')
        seen.add(pair)
        for target in targets:
            node = nodes[target['occurrence_path']]
            require(all(target.get(k) == node.get(k) for k in ('parent_occurrence_path', 'file_path', 'referenced_configuration')),
                    'Distance occurrence identity differs from inventory.', 'EVIDENCE_MISMATCH')
            require(isinstance(target.get('transform'), dict) and isinstance(node.get('transform'), dict), 'Missing distance/inventory pose.', 'INVALID_DISTANCE_SOURCE')
            require(transform_from_sw(target['transform'].get('raw_array'))['raw_array'] == transform_from_sw(node['transform'].get('raw_array'))['raw_array'],
                    'Distance occurrence pose differs from inventory.', 'EVIDENCE_MISMATCH')
            part = target.get('source_part')
            require(isinstance(part, dict) and part.get('document_type') == 'part' and part.get('configuration') == node.get('referenced_configuration'),
                    'Distance target is not a matching part configuration.', 'EVIDENCE_MISMATCH')
        require(type(data.get('complete')) is bool, 'Missing distance completeness flag.', 'INVALID_DISTANCE_SOURCE')
        measurement = data.get('measurement')
        if data.get('measurement_status') == 'ok':
            require(isinstance(measurement, dict) and measurement.get('frame') == 'root_assembly', 'Invalid measurement frame.', 'INVALID_DISTANCE_SOURCE')
            normalized = distance_result(measurement.get('distance_m'), measurement.get('point_left_m'), measurement.get('point_right_m'))
            for field in ('distance_mm', 'point_separation_m', 'point_left_mm', 'point_right_mm'):
                expected_values = normalized[field] if isinstance(normalized[field], list) else [normalized[field]]
                raw = measurement.get(field) if isinstance(normalized[field], list) else [measurement.get(field)]
                actual = numbers(raw, len(expected_values), 'INVALID_DISTANCE_SOURCE')
                require(all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9) for a, b in zip(actual, expected_values)),
                        'Distance derived values disagree with meter data.', 'INVALID_DISTANCE_SOURCE')
            state = 'near_contact_candidate' if normalized['distance_mm'] <= contact_tolerance_mm else 'separated_at_measurement'
            points = dict(zip(order, (normalized['point_left_mm'], normalized['point_right_mm'])))
        else:
            require(data.get('measurement_status') == 'unavailable' and measurement is None and source_errors and
                    envelope['status'] == 'partial' and data['complete'] is False, 'Unavailable distance must retain errors/partial, never a zero.', 'INVALID_DISTANCE_SOURCE')
            normalized, points, state = None, None, 'unresolved'
        evidence = {'source_path': path, 'source_sha256': digest, 'measurement': normalized,
                    'point_by_occurrence_mm': points, 'source_errors': source_errors,
                    'captured_at_utc': data.get('captured_at_utc')}
        pairs[pair].update(review_state=state, distance_evidence=evidence)
        sources.append({'path': path, 'sha256': digest, 'occurrence_paths': list(pair)})
        if envelope['status'] != 'ok' or not data['complete'] or source_errors:
            errors.append({'code': 'SOURCE_INCOMPLETE', 'source': path, 'message': 'Distance evidence is incomplete.', 'source_errors': source_errors})
    rows = list(pairs.values())
    counts = {state: sum(r['review_state'] == state for r in rows) for state in
              ('near_contact_candidate', 'separated_at_measurement', 'unresolved', 'unmeasured')}
    if counts['unmeasured']:
        errors.append({'code': 'UNMEASURED_CANDIDATES', 'message': 'Some worklist pairs have no distance evidence.', 'count': counts['unmeasured']})
    return {'proximity_review_schema_version': 1, 'document': spatial['document'],
            'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'snapshot_atomic': False,
            'contact_tolerance_mm': contact_tolerance_mm, 'pairs': rows, 'counts': counts, 'distance_sources': sources,
            'unranked_occurrences': expected['unranked_occurrences'], 'worklist_coverage': expected['coverage'],
            'complete': not errors, 'errors': errors, 'requires_review': True,
            'solidworks_modified': False, 'contact_confirmed': False, 'mechanical_relation_confirmed': False,
            'limitations': ['Near-contact means only that the API distance is within the explicitly supplied tolerance; no contact/interference/containment distinction is inferred.',
                            'A component-level minimum says nothing about which cylindrical candidate face is nearby; no joining with axis/face evidence is implied.',
                            'Pairs omitted by approximate-box screening, missing boxes or budgets remain unknown. Separated measured components may still be mechanically related.',
                            'Witness points are model-frame coordinates, not persistent faces or a contact patch. Hashes/poses do not prove unchanged geometry or atomic collection.']}


def proximity_review(root, proximity_path, distance_paths, output_path, contact_tolerance_mm):
    output = json_path(root, output_path, output=True)
    worklist_file = json_path(root, proximity_path)
    worklist, worklist_hash = read_json(worklist_file)
    require(isinstance(worklist, dict) and isinstance(worklist.get('inventory_path'), str), 'Missing worklist inventory binding.')
    inventory_file = json_path(root, worklist['inventory_path'])
    inventory, inventory_hash = read_json(inventory_file)
    sources = []
    for name in distance_paths:
        file = json_path(root, name)
        envelope, digest = read_json(file)
        sources.append((envelope, str(file), digest))
    data = review_proximity(worklist, inventory, inventory_hash, sources, contact_tolerance_mm)
    data['sources'] = {'proximity': {'path': str(worklist_file), 'sha256': worklist_hash},
                       'inventory': {'path': str(inventory_file), 'sha256': inventory_hash}}
    write_result(output, data)
    return success({'output_path': str(output), 'counts': data['counts'], 'complete': data['complete'],
                    'requires_review': True, 'contact_confirmed': False, 'mechanical_relation_confirmed': False,
                    'solidworks_modified': False}, data['errors'])
