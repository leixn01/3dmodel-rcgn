"""Source-replayed face task planning. No CAD access, guessed locators or folder scanning."""
from cadkin.adapters.face_identity import decode_reference
from cadkin.distance import distance_result
from cadkin.errors import success
from cadkin.face_geometry import descriptor
from cadkin.geometry import numbers
from cadkin.followup.execution import document_matches, pose_matches
from cadkin.followup.face_planning import FACE_READ_TOOLS, plan_face_tasks, probe_key
from cadkin.followup.observations import reuse_facts
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.comparison import replay_check
from cadkin.tools.face_contacts import review_probe, same_derived
from cadkin.tools.face_sources import face_source
from cadkin.tools.files import json_path, read_json
from cadkin.tools.matching import recheck
from cadkin.tools.observation_index import replay_index, unique_bindings
from cadkin.tools.proximity import write_result


def catalog(raw, binding, nodes, document):
    data = raw['data']; target = data.get('target', {})
    require(document_matches(data.get('document'), document) and pose_matches(target, nodes.get(target.get('occurrence_path'))),
            'Face catalog differs from target document/instance.', 'EVIDENCE_MISMATCH')
    require(data.get('geometry_scope') == 'referenced_part_definition' and data.get('assembly_instance_features_evaluated') is False and
            isinstance(target.get('source_part'), dict) and target['source_part'].get('document_type') == 'part' and
            target['source_part'].get('configuration') == target['referenced_configuration'],
            'Unsupported catalog part scope.', 'INVALID_FACE_PROBE_SOURCE')
    rows = data.get('faces')
    require(isinstance(rows, list) and len(rows) <= 1000 and type(data.get('face_count')) is int and len(rows) == data['face_count'],
            'Invalid face count.', 'INVALID_FACE_PROBE_SOURCE')
    seen, sources, unsupported = set(), [], 0
    for row in rows:
        require(isinstance(row, dict) and not row.get('errors'), 'Invalid complete face row.', 'INVALID_FACE_PROBE_SOURCE')
        bi, fi = row.get('body_index'), row.get('face_index')
        require(type(bi) is int and type(fi) is int and bi >= 0 and fi >= 0 and (bi, fi) not in seen,
                'Duplicate/invalid face locator.', 'INVALID_FACE_PROBE_SOURCE')
        seen.add((bi, fi)); shape = descriptor(row.get('descriptor'))
        if shape['surface_type'] == 'other' or row.get('face_reference') is None:
            unsupported += 1; continue
        decode_reference(row['face_reference'])
        sources.append({**binding, 'document': data['document'], 'target': target, 'face': row, 'complete': True, 'errors': []})
    return {'binding': binding, 'target': target, 'rows': rows, 'sources': sources, 'unsupported': unsupported}


def witness(raw, binding, nodes, document):
    data = raw['data']
    require(document_matches(data.get('document'), document), 'Distance document changed.', 'EVIDENCE_MISMATCH')
    require(data.get('scope') == 'two_resolved_part_occurrences' and data.get('geometry_scope') == 'assembly_component_context' and
            data.get('method') == 'IModelDoc2.ClosestDistance(IComponent2,IComponent2)' and
            data.get('units') == {'api_length': 'm', 'display_length': 'mm'} and data.get('measurement_status') == 'ok',
            'Unsupported distance witness scope.', 'INVALID_DISTANCE_SOURCE')
    targets = data.get('targets')
    require(isinstance(targets, list) and len(targets) == 2 and all(isinstance(t, dict) for t in targets),
            'Expected two target contexts.', 'INVALID_DISTANCE_SOURCE')
    order = [t.get('occurrence_path') for t in targets]
    require(all(isinstance(p, str) and p in nodes for p in order) and len(set(order)) == 2 and
            all(pose_matches(t, nodes[t['occurrence_path']]) and isinstance(t.get('source_part'), dict) and
                t['source_part'].get('document_type') == 'part' and t['source_part'].get('configuration') == t['referenced_configuration'] for t in targets),
            'Distance instance identity/pose/configuration changed.', 'EVIDENCE_MISMATCH')
    m = data.get('measurement')
    require(isinstance(m, dict), 'Missing complete distance measurement.', 'INVALID_DISTANCE_SOURCE')
    expected = distance_result(m.get('distance_m'), m.get('point_left_m'), m.get('point_right_m'))
    require(same_derived(m, expected), 'Distance derived fields differ from raw meter points.', 'INVALID_DISTANCE_SOURCE')
    return tuple(sorted(order)), {'source': binding, 'distance_mm': expected['distance_mm'],
                                'point_by_occurrence_mm': dict(zip(order, (expected['point_left_mm'], expected['point_right_mm'])))}


def face_facts(root, target, index):
    nodes = {n['id']: n for n in target['nodes']}
    facts = {'faces': {}, 'face_conflicts': set(), 'distances': {}, 'distance_conflicts': set(),
             'attempted_requests': reuse_facts(index)['attempted_requests'], 'attempted_probes': {}}
    bindings = unique_bindings(root, target['input_files'] + [o['source'] for o in index['observations'] if o['usable']])
    for binding in bindings:
        raw, digest = read_json(json_path(root, binding['path']))
        require(digest == binding['sha256'], 'Source changed during face planning.', 'EVIDENCE_MISMATCH')
        data = raw.get('data') if isinstance(raw, dict) else None
        if not isinstance(data, dict): continue
        if data.get('face_probe_schema_version') == 1:
            review_probe(root, raw, 0, 0)
            facts['attempted_probes'].setdefault(probe_key(data['sources']), []).append(binding)
        if raw.get('status') != 'ok' or raw.get('errors') or data.get('complete') is not True or data.get('truncated', False): continue
        if data.get('face_inventory_schema_version') == 1 and data.get('target', {}).get('occurrence_path') in nodes:
            value = catalog(raw, binding, nodes, target['document']); path = value['target']['occurrence_path']
            previous = facts['faces'].get(path)
            if previous and (previous['target'] != value['target'] or previous['rows'] != value['rows']): facts['face_conflicts'].add(path)
            else: facts['faces'].setdefault(path, value)
        elif data.get('component_distance_schema_version') == 1:
            # Chain provenance can include boundary pairs outside the explicit target scope.
            targets = data.get('targets', [])
            if any(t.get('occurrence_path') not in nodes for t in targets if isinstance(t, dict)): continue
            pair, value = witness(raw, binding, nodes, target['document'])
            previous = facts['distances'].get(pair)
            if previous and any(previous[k] != value[k] for k in ('distance_mm', 'point_by_occurrence_mm')): facts['distance_conflicts'].add(pair)
            else: facts['distances'].setdefault(pair, value)
    # Failed and partial attempts are also remembered, regardless of changed seeds/budgets or argument ordering.
    for row in index['observations']:
        if row['tool'] != 'sw_probe_face_pair': continue
        sources = [face_source(root, row['arguments'][side]) for side in ('left', 'right')]
        facts['attempted_probes'].setdefault(probe_key(sources), []).append(row['source'])
    return facts


def build_face_plan(root, draft_check_path, evidence_index_path, output_path, max_component_gap_mm, surface_tolerance_mm,
                    max_component_pairs=20, max_face_candidates=20, max_face_pairs=100, max_tasks=20,
                    max_iterations=20, convergence_tolerance_mm=0.001, check_destinations=True):
    from jsonschema import Draft202012Validator
    from cadkin.tools.solidworks import CATALOG
    options = dict(max_component_gap_mm=max_component_gap_mm, surface_tolerance_mm=surface_tolerance_mm,
        max_component_pairs=max_component_pairs, max_face_candidates=max_face_candidates, max_face_pairs=max_face_pairs,
        max_tasks=max_tasks, max_iterations=max_iterations, convergence_tolerance_mm=convergence_tolerance_mm)
    numbers([max_component_gap_mm, surface_tolerance_mm, convergence_tolerance_mm], 3, 'INVALID_ARGUMENTS')
    params = dict(draft_check_path=draft_check_path, evidence_index_path=evidence_index_path, **options)
    require(Draft202012Validator(CATALOG['cad_plan_face_probes']['inputSchema']).is_valid({**params, 'output_path': output_path}),
            'Invalid face planning parameters.', 'INVALID_ARGUMENTS')
    output = json_path(root, output_path, output=check_destinations)
    check, target, _, _, cb = replay_check(root, draft_check_path)
    index, ib = replay_index(root, evidence_index_path)
    require(index['check_source'] == cb, 'Index belongs to another check; reassociate it first.', 'EVIDENCE_MISMATCH')
    facts = face_facts(root, target, index)
    data = plan_face_tasks(target, check, facts, index, output.parent / (output.stem + '-captures'), **options)
    data.update(parameters=dict(draft_check_path=cb['path'], evidence_index_path=ib['path'], **options),
                check_source=cb, evidence_index_source=ib,
                input_files=unique_bindings(root, check['input_files'] + index['input_files'] + [cb, ib]))
    data['prior_face_attempts'] = [{'pair_key': key, 'sources': values} for key, values in sorted(facts['attempted_probes'].items())]
    for task in data['tasks']:
        require(task['tool'] in FACE_READ_TOOLS and CATALOG[task['tool']]['annotations']['readOnlyHint'] and
                Draft202012Validator(CATALOG[task['tool']]['inputSchema']).is_valid(task['arguments']),
                'Invalid/read-write face plan task.', 'INVALID_TASK_PLAN')
        json_path(root, task['save_envelope_path'], output=check_destinations)
    recheck(root, data['input_files'])
    return data, check, target


def replay_face_plan(root, path, original, digest):
    keys = {'draft_check_path', 'evidence_index_path', 'max_component_gap_mm', 'surface_tolerance_mm',
            'max_component_pairs', 'max_face_candidates', 'max_face_pairs', 'max_tasks', 'max_iterations', 'convergence_tolerance_mm'}
    require(original.get('evidence_task_plan_schema_version') == 1 and original.get('plan_kind') == 'witness_guided_face_probes' and
            isinstance(original.get('parameters'), dict) and set(original['parameters']) == keys,
            'Use an original face task plan.', 'INVALID_TASK_PLAN')
    data, check, target = build_face_plan(root, output_path=str(path), check_destinations=False, **original['parameters'])
    check_fields(original, data)
    return data, check, target, {'path': str(path), 'sha256': digest}


def face_task_plan(root, **arguments):
    data, check, _ = build_face_plan(root, **arguments)
    output = json_path(root, arguments['output_path'], output=True)
    write_result(output, data)
    errors = []
    if data['output_truncated']: errors.append({'code': 'FACE_PLAN_LIMIT', 'message': 'Retain omitted faces/pairs, deferred calls and unreturned findings.'})
    if not check['structural_checks_passed']: errors.append({'code': 'INVALID_DRAFT_STRUCTURE', 'message': 'Regenerate invalid derivations before capture.'})
    return success({'output_path': str(output), **data}, errors)
