"""Target-first relationship drafts, independent of whether any template fits."""
from copy import deepcopy

from cadkin.matching.analogy import separate_reference_types
from cadkin.rigid.groups import aggregate_target, require, MOTION_MATES
from cadkin.rigid.joints import draft_partitions, axis_draft


def assess_pair(pair, groups, distance_tol, angle_tol):
    active = [s for s in pair['signals'] if s['kind'] == 'active_mate' and not s.get('record_errors')]
    kinds = {s.get('mate_type') for s in active}
    flags = deepcopy(pair['flags'])
    if 'lock' in kinds and kinds & MOTION_MATES:
        flags.append({'code': 'LOCK_AND_MOTION_MATE_EVIDENCE',
            'message': 'Active feature records suggest incompatible constraints; no solver verdict.'})
    geometry = axis_draft(pair, distance_tol, angle_tol)
    geometric = any(s['kind'] in ('near_component', 'near_face_sample') for s in pair['signals']) or bool(pair['axis_relations'])
    state = ('conflicting_evidence' if flags else 'constraint_feature_evidence' if active else
             'geometric_candidate' if geometric else 'insufficient_evidence')
    return {'id': pair['id'], 'group_ids': pair['node_ids'],
        'member_occurrence_paths': [groups[g]['member_occurrence_paths'] for g in pair['node_ids']],
        'source_occurrence_pair_ids': pair['source_pair_ids'],
        'target_joint_kind': 'unknown', 'target_degrees_of_freedom': None,
        'assessment': state, 'signals': deepcopy(pair['signals']), 'flags': flags,
        'geometry': geometry, 'evidence_ranking_weight': pair['link_support'],
        'reference_required': False, 'connection_confirmed': False, 'mechanically_verified': False,
        'unknowns': ['physical_connection', 'joint_kind', 'degrees_of_freedom', 'pivot', 'limits', 'motion_feasibility'],
        'meaning': 'Evidence of constraints or geometry is retained without assigning a joint type. Missing evidence does not establish disconnection.'}


def target_draft(target, rigid, references, max_target_pairs=200, **parameters):
    require(type(max_target_pairs) is int and 1 <= max_target_pairs <= 2000, 'max_target_pairs must be 1–2000.')
    # Preserve the legacy implementation for old-file replay; only explicit references run its search.
    data = draft_partitions(target, rigid, references, **parameters)
    count = len(rigid['partitions']); total = returned = 0
    for index, (partition, run) in enumerate(zip(rigid['partitions'], data['partition_results'])):
        graph = aggregate_target(target, partition); groups = {g['id']: g for g in partition['groups']}
        quota = max_target_pairs // count + (index < max_target_pairs % count)
        ordered = sorted(graph['pairs'], key=lambda p: (not bool(p['flags']), -p['link_support'], p['id']))
        run['connection_candidates'] = [assess_pair(p, groups, data['parameters']['axis_distance_tolerance_mm'],
            data['parameters']['axis_angle_tolerance_deg']) for p in ordered[:quota]]
        run['target_pair_coverage'] = {'available': len(ordered), 'returned': len(run['connection_candidates']),
            'omitted': max(0, len(ordered)-quota), 'budget': quota}
        total += len(ordered); returned += len(run['connection_candidates'])
        if not references:
            run.update(match=None, skip_reason='templates_not_requested', state_budget=0)
        elif run['match'] is not None:
            run['match'] = separate_reference_types(run['match'], {p['id']: p for p in graph['pairs']})
    data['parameters']['max_target_pairs'] = max_target_pairs
    data.update(algorithm_version=2, analysis_basis='target_evidence_first',
        template_search_requested=bool(references), target_pairs_truncated=returned < total,
        target_joint_types_inferred=False)
    data['summary'].update(target_pairs_available=total, target_pairs_returned=returned,
        target_pairs_omitted=total-returned, determined_target_joint_types=0)
    if not references:
        data['summary'].update(searched_partitions=0, evaluated_states=0)
        data['search_exhaustive_within_retained_partitions'] = True
    data['limitations'] = [
        'Target relationship evidence is produced independently of reference matches; every target type and DOF remains unknown in this release.',
        'Templates run only when explicitly selected. Reference types/DOF remain separate and never populate target conclusions.',
        'Constraint feature activity, coaxial cylinders, close faces and names cannot certify physical connectivity, rigid motion or joint kind.',
        'Target pairs have a shared output budget across conditional partitions; omitted pairs and grouping alternatives remain unknown.',
        'Reference scores compare topology and relative axes only. Revolute and prismatic references can tie on the same target evidence.',
        'Original evidence, geometry scopes and conflicting explanations remain available. No CAD edits or motion solving.']
    return data
