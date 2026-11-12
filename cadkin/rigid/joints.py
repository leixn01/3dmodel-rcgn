"""Match alternative body partitions and draft source-bound geometric joint hypotheses."""
import copy
import math

from cadkin.matching.search import match_patterns
from cadkin.matching.target import axis_angle
from cadkin.rigid.groups import aggregate_target, require


def canonical_line(origin, direction):
    scale = math.hypot(*direction)
    axis = [v / scale for v in direction]
    pivot = max(range(3), key=lambda i: abs(axis[i]))
    if axis[pivot] < 0: axis = [-v for v in axis]
    projection = sum(p * d for p, d in zip(origin, axis))
    return {'direction_root_unit': axis,
            'point_on_line_root_m': [p - projection * d for p, d in zip(origin, axis)]}


def axis_draft(pair, distance_tolerance_mm, angle_tolerance_deg):
    axes = pair['axis_relations']
    lines = []
    truncated = len(axes) > 128 or pair.get('axes_truncated', False)
    for relation in axes[:128]:
        for side in ('left', 'right'):
            row = relation[side]
            line = canonical_line(row['origin_m'], row['axis_unit'])
            existing = next((v for v in lines if axis_angle(v['direction_root_unit'], line['direction_root_unit']) <= angle_tolerance_deg
                             and math.dist(v['point_on_line_root_m'], line['point_on_line_root_m']) <= distance_tolerance_mm / 1000), None)
            source = {'source': relation['source'], 'candidate_index': relation['candidate_index'],
                      'side': side, 'occurrence_path': row['node_id'], 'relation_kind': relation['kind']}
            if existing is None:
                if len(lines) >= 16:
                    truncated = True
                    continue
                existing = {**line, 'sources': [], 'observation_count': 0}
                lines.append(existing)
            existing['observation_count'] += 1
            if len(existing['sources']) < 32: existing['sources'].append(source)
    for line in lines: line['source_list_truncated'] = line['observation_count'] > len(line['sources'])
    unique = (len(lines) == 1 and not truncated and not pair['flags'] and
              all(a['kind'] == 'coaxial_candidate' for a in axes))
    return {'geometric_line_candidates': lines, 'line_candidates_truncated': truncated,
            'axis_relation_count': pair.get('axis_relation_count', len(axes)),
            'processed_axis_relations': min(128, len(axes)),
            'axis_line_candidate': copy.deepcopy(lines[0]) if unique else None,
            'point_semantics': 'Closest point on the observed infinite line to root origin; not a joint pivot or attachment location.',
            'line_merge_tolerances': {'distance_mm': distance_tolerance_mm, 'angle_deg': angle_tolerance_deg},
            'line_merge_scope': 'Root-origin canonical points and unoriented directions; finite faces, stroke and global frame alignment are not solved.'}


def draft_candidate(candidate, partition, graph, distance_tol, angle_tol):
    result = copy.deepcopy(candidate)
    groups = {g['id']: g for g in partition['groups']}
    pairs = {p['id']: p for p in graph['pairs']}
    result['partition_id'] = partition['id']
    result['mapping'] = [{'template_body_id': m['template_body_id'], 'group_id': m['occurrence_path'],
                          'member_occurrence_paths': groups[m['occurrence_path']]['member_occurrence_paths'],
                          'rigidity_confirmed': False} for m in candidate['mapping']]
    for edge in result['joint_hypotheses']:
        ids = edge.pop('occurrence_paths')
        edge['group_ids'] = ids
        edge['member_occurrence_paths'] = [groups[g]['member_occurrence_paths'] for g in ids]
        pair = pairs[edge['target_pair_id']]
        edge['source_occurrence_pair_ids'] = pair['source_pair_ids']
        edge['dof_hypothesis'] = 0 if edge['hypothesis_kind'] == 'fixed' else 1
        edge['dof_verified'] = False
        directional = edge['hypothesis_kind'] in ('revolute', 'prismatic')
        direction = edge.pop('target_geometric_axis_unit')
        edge['direction_candidate_root_unit'] = direction if directional else None
        edge['geometry'] = axis_draft(pair, distance_tol, angle_tol) if directional else None
        edge['limits'] = None
        edge['pitch_m_per_revolution'] = None
        edge['axis_origin_m'] = None
        edge['parameter_status'] = {'kind': 'reference_hypothesis', 'degrees_of_freedom': 'unverified_hypothesis',
            'direction': 'geometric_candidate' if edge['direction_candidate_root_unit'] else 'unknown' if directional else 'not_applicable',
            'axis_line': 'geometric_candidate' if edge['geometry'] and edge['geometry']['axis_line_candidate'] else 'unknown' if directional else 'not_applicable',
            'pivot': 'unknown', 'limits': 'unknown', 'motion': 'not_validated'}
        edge['automatic_followup'] = (['collect_component_constraints_for_group_members'] if any(len(groups[g]['member_occurrence_paths']) > 1 for g in ids) else [])
        if edge['link_support'] == 0: edge['automatic_followup'].append('collect_pair_distance_and_root_mates')
        if directional and edge['direction_candidate_root_unit'] is None: edge['automatic_followup'].append('collect_or_disambiguate_component_cylinders')
    result['risk_codes'] = sorted((set(result['risk_codes']) - {'ONE_OCCURRENCE_PER_REFERENCE_BODY'}) |
                                  set(partition['risk_codes']) | {'GROUP_MEMBERSHIP_CONDITIONAL', 'JOINT_PARAMETERS_NOT_SOLVED'})
    result['scope'] = 'local_template_subgraph_of_conditional_rigid_groups'
    result['unmatched_group_ids'] = sorted(set(groups) - {m['group_id'] for m in result['mapping']})
    return result


def draft_partitions(target, rigid, references, pattern_size=3, max_candidates=5,
                     max_states=20000, beam_width=50, angle_tolerance_deg=10,
                     axis_distance_tolerance_mm=0.1, axis_angle_tolerance_deg=1):
    require(type(pattern_size) is int and 2 <= pattern_size <= 6, 'pattern_size must be 2–6.')
    require(type(max_candidates) is int and 1 <= max_candidates <= 10, 'max_candidates must be 1–10 per partition.')
    require(type(max_states) is int and 1 <= max_states <= 100000, 'max_states must be 1–100000 in total.')
    require(type(beam_width) is int and 1 <= beam_width <= 1000, 'beam_width must be 1–1000.')
    for value, maximum, name in [(angle_tolerance_deg, 45, 'angle_tolerance_deg'),
                                  (axis_distance_tolerance_mm, 10, 'axis_distance_tolerance_mm'),
                                  (axis_angle_tolerance_deg, 5, 'axis_angle_tolerance_deg')]:
        require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= maximum,
                f'{name} must be finite in (0,{maximum}].')
    runs = []
    count = len(rigid['partitions'])
    for index, partition in enumerate(rigid['partitions']):
        quota = max_states // count + (index < max_states % count)
        graph = aggregate_target(target, partition)
        eligible = sum(n['eligible'] for n in graph['nodes'])
        # Fixed requested window size across alternatives; shrinking it would make scores incomparable.
        reason = 'insufficient_eligible_groups' if eligible < pattern_size else 'partition_state_budget_zero' if not quota else None
        row = {'partition_id': partition['id'], 'partition_basis': partition['basis'], 'state_budget': quota,
               'eligible_groups': eligible, 'skip_reason': reason, 'match': None}
        if reason is None:
            match = match_patterns(graph, references, pattern_size=pattern_size, max_candidates=max_candidates,
                                   max_states=quota, beam_width=beam_width, angle_tolerance_deg=angle_tolerance_deg)
            match['candidates'] = [draft_candidate(c, partition, graph, axis_distance_tolerance_mm, axis_angle_tolerance_deg) for c in match['candidates']]
            match['search_scope'] = 'selected reference windows over one conditional group partition'
            match['limitations'] = [s for s in match['limitations'] if not s.startswith('One occurrence maps')]
            row['match'] = match
        runs.append(row)
    candidates = [c for r in runs if r['match'] for c in r['match']['candidates']]
    evaluated = sum(r['match']['search']['evaluated_states'] for r in runs if r['match'])
    within_scope = all(r['skip_reason'] == 'insufficient_eligible_groups' or
                       (r['match'] is not None and r['match']['search_exhaustive']) for r in runs)
    return {'joint_draft_schema_version': 1, 'algorithm_version': 1, 'document': target['document'],
            'units': target['units'], 'parameters': {'pattern_size': pattern_size, 'max_candidates': max_candidates,
                'max_states': max_states, 'beam_width': beam_width, 'angle_tolerance_deg': angle_tolerance_deg,
                'axis_distance_tolerance_mm': axis_distance_tolerance_mm, 'axis_angle_tolerance_deg': axis_angle_tolerance_deg},
            'partition_results': runs,
            'summary': {'partitions': count, 'searched_partitions': sum(r['match'] is not None for r in runs),
                        'returned_candidates': len(candidates), 'evaluated_states': evaluated,
                        'returned_joint_drafts': sum(len(c['joint_hypotheses']) for c in candidates)},
            'search_exhaustive_within_retained_partitions': within_scope,
            'partition_output_truncated': rigid['output_truncated'], 'partition_space_exhaustive': False,
            'source_errors': target['errors'], 'boundary_evidence': target['boundary_evidence'],
            'requires_human_review': False, 'solidworks_modified': False,
            'rigidity_confirmed': False, 'mechanical_relation_confirmed': False,
            'limitations': ['Candidates are ranked separately per partition; matching score does not validate or choose rigid membership.',
                'A template body can map to multiple occurrences only under the explicitly recorded group hypothesis. Baseline alternatives remain available.',
                'Requested template window size is fixed across partitions; too few eligible groups are skipped, not silently matched at a smaller size.',
                'Joint types/DOF are reference hypotheses; line/direction candidates come only from target cylinders. Limits, screw pitch and pivot remain unknown.',
                'No template distances/limits are copied. Neither geometric alignment nor lock feature activity proves physical rigidity or motion feasibility.',
                'Search budget is shared across retained partitions, then across template windows. Missing candidates never prove absent mechanisms.']}
