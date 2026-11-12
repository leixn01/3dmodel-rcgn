"""Associate guarded observations with retained hypotheses without inferring contact."""
from collections import Counter
from cadkin.followup import stable_id
from cadkin.face_geometry import descriptor
from cadkin.errors import ToolFailure


def require(condition, message, code):
    if not condition: raise ToolFailure(code, message)

FAMILIES = {'sw_component_constraints': 'constraints', 'sw_component_faces': 'faces',
            'sw_component_cylinders': 'cylinders', 'sw_component_distance': 'distance',
            'sw_mate_inventory': 'root_mates'}
MAX_ROUNDS = 4


def request_key(tool, paths):
    # Budget changes alone must not silently turn a failed/partial scan into a retry.
    return stable_id('request-', [tool, sorted(set(paths))])


def describe_capture(tool, data):
    """Summarize only verified complete observations, retaining the original source elsewhere."""
    if tool == 'sw_component_constraints':
        fixed, mates = data.get('fixed_state'), data.get('mates')
        require(isinstance(fixed, dict) and type(fixed.get('value')) is bool and
                fixed.get('scope') == 'root_assembly_top_level' and data.get('parent_occurrence_path') is None,
                'Missing top-level fixed-state context.', 'INVALID_OBSERVATION')
        require(isinstance(mates, list) and data.get('read_mate_count') == data.get('reported_mate_count') == len(mates) and
                all(isinstance(m, dict) and not m.get('errors') and isinstance(m.get('entities'), list) for m in mates),
                'Incomplete attached mate records.', 'INVALID_OBSERVATION')
        return {'fixed_state': fixed, 'attached_mate_count': len(mates),
                'attached_mate_type_codes': sorted({m['type_code'] for m in mates if type(m.get('type_code')) is int}),
                'reference_component_names': sorted({e['reference_component_name'] for m in mates for e in m['entities']
                    if isinstance(e, dict) and isinstance(e.get('reference_component_name'), str)}),
                'reference_names_resolved_to_occurrences': False, 'mate_activity_known': False}
    if tool == 'sw_component_faces':
        rows = data.get('faces')
        require(isinstance(rows, list) and type(data.get('face_count')) is int and len(rows) == data['face_count'] and
                data.get('geometry_scope') == 'referenced_part_definition' and data.get('assembly_instance_features_evaluated') is False,
                'Invalid face catalog scope/count.', 'INVALID_OBSERVATION')
        faces, seen = [], set()
        for row in rows:
            require(isinstance(row, dict) and not row.get('errors'), 'Invalid face record.', 'INVALID_OBSERVATION')
            bi, fi = row.get('body_index'), row.get('face_index')
            require(type(bi) is int and type(fi) is int and bi >= 0 and fi >= 0 and (bi, fi) not in seen,
                    'Invalid or duplicate face locator.', 'INVALID_OBSERVATION')
            seen.add((bi, fi)); shape = descriptor(row.get('descriptor'))
            faces.append({'body_index': bi, 'face_index': fi, 'surface_type': shape['surface_type'],
                          'has_saved_reference': isinstance(row.get('face_reference'), dict)})
        return {'face_count': len(faces), 'surface_counts': dict(Counter(f['surface_type'] for f in faces)),
                'faces': faces, 'geometry_scope': data['geometry_scope'], 'live_face_identity_verified': False}
    return {'available_for_existing_reintegration': True}


def associate(observations, target, check, draft, max_contexts):
    by_node = {n['id']: [] for n in target['nodes']}
    by_id = {o['id']: o for o in observations}
    for observation in observations:
        for path in observation['occurrence_paths']:
            if path in by_node: by_node[path].append(observation['id'])
    def references(paths, family=None):
        return sorted({oid for p in paths for oid in by_node.get(p, [])
                       if family is None or by_id[oid]['family'] == family})
    fixed = {}
    for observation in observations:
        if observation['usable'] and observation['family'] == 'constraints':
            path = observation['occurrence_paths'][0]
            fixed.setdefault(path, []).append(observation['details']['fixed_state']['value'])
    # Conflicting snapshots stay unknown, never use last-writer-wins.
    known_fixed = {p: values[0] for p, values in fixed.items() if len(set(values)) == 1}
    joints, total = [], 0
    for run in draft['partition_results']:
        if not run['match']: continue
        for candidate in run['match']['candidates']:
            for joint in candidate['joint_hypotheses']:
                total += 1
                if len(joints) >= max_contexts: continue
                members = sorted({p for group in joint['member_occurrence_paths'] for p in group})
                all_fixed = all(known_fixed[p] for p in members) if all(p in known_fixed for p in members) else None
                joints.append({'id': stable_id('joint-context-', [run['partition_id'], candidate['template_id'], candidate['rank'], joint['reference_joint_id']]),
                    'partition_id': run['partition_id'], 'template_id': candidate['template_id'], 'candidate_rank': candidate['rank'],
                    'reference_joint_id': joint['reference_joint_id'], 'hypothesis_kind': joint['hypothesis_kind'],
                    'member_occurrence_paths': joint['member_occurrence_paths'], 'observation_ids': references(members),
                    'fixed_members': [p for p in members if known_fixed.get(p) is True],
                    'unknown_fixed_members': [p for p in members if p not in known_fixed],
                    'all_endpoint_members_fixed': all_fixed,
                    'signals': ['FIXED_MEMBERS_VS_MOVING_HYPOTHESIS'] if all_fixed is True and joint['hypothesis_kind'] in ('prismatic', 'revolute') else [],
                    'meaning': 'Configured fixed flags constrain this snapshot; no solver verdict, physical grouping or joint rejection is asserted.'})
    return {'node_observations': by_node,
            'pair_contexts': [{'pair_id': p['id'], 'occurrence_paths': p['node_ids'],
                               'endpoint_observation_ids': [references([n]) for n in p['node_ids']],
                               'face_pair_selected': False, 'connection_confirmed': False} for p in target['pairs']],
            'finding_contexts': [{'finding_id': f['id'], 'observation_ids': references(f['occurrence_paths']),
                                  'resolved': False} for f in check['findings']],
            'joint_contexts': joints, 'joint_contexts_found': total, 'joint_contexts_truncated': total > len(joints),
            'conflicting_fixed_occurrences': sorted(p for p, values in fixed.items() if len(set(values)) > 1)}


def reuse_facts(index):
    facts = {'constraints': {}, 'faces': {}, 'cylinders': {}, 'distance': {}, 'root_mates': [],
             'attempted_requests': {}, 'rounds_completed': index['rounds_completed']}
    for row in index['observations']:
        facts['attempted_requests'].setdefault(request_key(row['tool'], row['occurrence_paths']), []).append(row)
        if not row['usable']: continue
        family = row['family']
        if family == 'root_mates': facts[family].append(row['source'])
        elif family == 'distance': facts[family].setdefault(tuple(row['occurrence_paths']), []).append(row['source'])
        else: facts[family].setdefault(row['occurrence_paths'][0], []).append(row['source'])
    return facts
