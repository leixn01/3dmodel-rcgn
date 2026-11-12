"""Offline face-probe review: verify raw sources/derived geometry, preserve local scope."""
from datetime import datetime, timezone
import math

from cadkin.face_geometry import require, descriptor, point, root_normal, pair_metrics, classify
from cadkin.geometry import numbers, transform_from_sw
from cadkin.tools.face_sources import face_source
from cadkin.tools.files import json_path, read_json
from cadkin.tools.proximity import write_result
from cadkin.tools.relations import _document
from cadkin.errors import success


def same_derived(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(same_derived(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(same_derived(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return type(actual) in (int, float) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-9)
    return type(actual) is type(expected) and actual == expected


def review_probe(root, envelope, contact_tolerance_mm, angle_tolerance_deg):
    require(isinstance(envelope, dict) and envelope.get('status') in ('ok', 'partial') and isinstance(envelope.get('data'), dict), 'Use original face probe envelopes.')
    data, errors = envelope['data'], envelope.get('errors')
    require(data.get('face_probe_schema_version') == 1 and data.get('geometry_scope') == 'placed_part_definition_faces' and
            data.get('assembly_instance_features_evaluated') is False and data.get('method') == 'bounded_alternating_IFace2.GetClosestPointOn' and
            data.get('global_minimum_proven') is False, 'Unsupported probe schema/method/scope.')
    require(isinstance(errors, list) and all(isinstance(e, dict) for e in errors) and type(data.get('complete')) is bool and
            data['complete'] == (not errors) and (envelope['status'] == 'ok') == (not errors), 'Inconsistent probe completeness/errors.')
    sources = data.get('sources')
    require(isinstance(sources, list) and len(sources) == 2 and all(isinstance(s, dict) and isinstance(s.get('face'), dict) for s in sources), 'Expected two face sources.')
    for source in sources:
        latest = face_source(root, {'face_inventory_path': source.get('path'), 'body_index': source['face'].get('body_index'), 'face_index': source['face'].get('face_index')})
        require(latest == source and _document(source['document']) == _document(data.get('document')), 'Face source/hash/context changed.', 'EVIDENCE_MISMATCH')
        require(descriptor(source['face']['descriptor'])['surface_type'] in ('plane', 'cylinder'), 'Unsupported probe surface.')
    require(sources[0]['target']['occurrence_path'] != sources[1]['target']['occurrence_path'], 'Probe must join two occurrences.')
    params = data.get('parameters')
    require(isinstance(params, dict) and type(params.get('max_iterations')) is int and 1 <= params['max_iterations'] <= 50, 'Invalid probe parameters.')
    tolerance = numbers([params.get('convergence_tolerance_mm')], 1, 'INVALID_FACE_PROBE_SOURCE')[0]
    require(0 < tolerance <= 1, 'Invalid convergence tolerance.')
    seeds = params.get('seed_points_root_mm')
    require(isinstance(seeds, list) and 1 <= len(seeds) <= 8, 'Invalid probe seeds.')
    for seed in seeds: numbers(seed, 3, 'INVALID_FACE_PROBE_SOURCE')
    samples = data.get('samples')
    require(isinstance(samples, list) and len(samples) == len(seeds), 'Missing sampled/failed seed records.')
    normalized = []
    for index, row in enumerate(samples):
        require(isinstance(row, dict) and row.get('seed_index') == index and row.get('seed_root_mm') == seeds[index] and
                type(row.get('iterations')) is int and 0 <= row['iterations'] <= params['max_iterations'] and
                type(row.get('converged')) is bool and isinstance(row.get('errors'), list), 'Invalid seed result.')
        metrics = row.get('metrics')
        if metrics is None:
            require(row['errors'] and errors, 'Unavailable sample must preserve errors.')
            normalized.append(None); continue
        require(row['iterations'] >= 1 and (row['converged'] or row['errors']), 'Missing iteration outcome.')
        points, normals = [], []
        for side, source in zip(('left', 'right'), sources):
            target = source['target']; transform = transform_from_sw(target['transform']['raw_array'])
            sample = row.get(side)
            require(isinstance(sample, dict), 'Missing on-face point.')
            local = numbers(sample.get('point_part_m'), 3, 'INVALID_FACE_POINT'); numbers(sample.get('uv'), 2, 'INVALID_FACE_POINT')
            p = point(transform['to_root'], local)
            require(same_derived(sample.get('point_root_m'), p), 'Point transform/units mismatch.', 'INVALID_FACE_POINT')
            points.append(p)
            normal = row.get('normal_' + side)
            if normal is None:
                require(row['errors'] and errors, 'Unavailable normal must preserve errors.'); normals.append(None)
            else:
                require(isinstance(normal, dict) and normal.get('face_in_surface_sense') is source['face']['descriptor']['face_in_surface_sense'], 'Face sense differs from source.')
                raw = numbers(normal.get('evaluation_part_raw'), 11, 'INVALID_FACE_NORMAL')
                n = root_normal(transform, raw[:3], normal['face_in_surface_sense'])
                require(same_derived(normal.get('face_normal_root_unit'), n), 'Normal transform mismatch.', 'INVALID_FACE_NORMAL')
                normals.append(n)
        expected = pair_metrics(*points, *normals)
        require(same_derived(metrics, expected), 'Derived gap/normal metrics differ from raw data.')
        normalized.append(expected)
    usable = [i for i, m in enumerate(normalized) if m is not None]
    best = min(usable, key=lambda i: (normalized[i]['gap_mm'], i)) if usable else None
    require(data.get('best_seed_index') == best and data.get('measurement_status') == ('unavailable' if best is None else 'sampled'), 'Best sample does not match the saved point results.')
    metrics = None if best is None else normalized[best]
    solid = all(s['face']['descriptor']['body_type'] == 0 for s in sources)
    state = classify(metrics, contact_tolerance_mm, angle_tolerance_deg, solid)
    key = tuple(sorted((s['target']['occurrence_path'], s['sha256'], s['face']['body_index'], s['face']['face_index']) for s in sources))
    return {'faces': [{'occurrence_path': s['target']['occurrence_path'], 'source_path': s['path'], 'source_sha256': s['sha256'],
                      'body_index': s['face']['body_index'], 'face_index': s['face']['face_index']} for s in sources],
            'best_seed_index': best, 'metrics': metrics, 'review_state': state, 'solid_face_normals': solid,
            'converged': False if best is None else samples[best]['converged'], 'source_errors': errors,
            'captured_at_utc': data.get('captured_at_utc'), 'global_minimum_proven': False, 'contact_confirmed': False,
            'mechanical_relation_confirmed': False}, key


def face_contact_review(root, probe_paths, output_path, contact_tolerance_mm, angle_tolerance_deg):
    classify(None, contact_tolerance_mm, angle_tolerance_deg)
    output = json_path(root, output_path, output=True)
    rows, errors, seen, document = [], [], set(), None
    for name in probe_paths:
        path = json_path(root, name); envelope, digest = read_json(path)
        row, key = review_probe(root, envelope, contact_tolerance_mm, angle_tolerance_deg)
        current = envelope['data']['document']
        require(document is None or _document(document) == _document(current), 'Mixed probe documents.', 'EVIDENCE_MISMATCH')
        document = current
        require(key not in seen, 'Use one probe per source-bound face pair; reverse order is the same pair.', 'DUPLICATE_FACE_PROBE')
        seen.add(key)
        rows.append({**row, 'probe_path': str(path), 'probe_sha256': digest})
        if envelope['status'] != 'ok':
            errors.append({'code': 'SOURCE_INCOMPLETE', 'message': 'Probe has partial/unknown evidence.', 'source_path': str(path), 'source_errors': envelope['errors']})
    counts = {state: sum(row['review_state'] == state for row in rows) for state in
              ('near_face_contact_candidate', 'near_points_orientation_unconfirmed', 'sample_gap_above_tolerance', 'unresolved')}
    data = {'face_contact_review_schema_version': 1, 'document': document, 'captured_at_utc': datetime.now(timezone.utc).isoformat(),
            'parameters': {'contact_tolerance_mm': contact_tolerance_mm, 'angle_tolerance_deg': angle_tolerance_deg},
            'scope': 'provided_local_face_probes_only', 'pairs': rows, 'counts': counts, 'complete': not errors, 'errors': errors,
            'requires_review': True, 'global_minimum_proven': False, 'contact_confirmed': False, 'mechanical_relation_confirmed': False,
            'solidworks_modified': False, 'limitations': ['Near/opposing solid-face sample points are candidates, not contact or interference confirmation.',
                'A large sampled gap never proves global face separation; unprobed seeds/faces/occurrences remain unknown.',
                'Point normals at edges/seams are local surface limits, not a contact patch normal or topology classification.',
                'Source hashes and descriptors cannot establish atomic or unchanged full geometry; assembly-level features are excluded.']}
    write_result(output, data)
    return success({'output_path': str(output), 'counts': counts, 'complete': data['complete'], 'requires_review': True,
                    'global_minimum_proven': False, 'contact_confirmed': False, 'mechanical_relation_confirmed': False, 'solidworks_modified': False}, errors)
