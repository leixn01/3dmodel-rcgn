"""Report structural errors, evidence conflicts and ambiguity without solving mechanics."""
from collections import Counter, defaultdict
import itertools

from cadkin.followup import stable_id
from cadkin.errors import ToolFailure

SEVERITIES = {'structural_error': 0, 'evidence_conflict': 1, 'coverage': 2, 'uncertainty': 3}


def check_draft(target, rigid, draft, max_findings=200):
    if type(max_findings) is not int or not 1 <= max_findings <= 2000:
        raise ToolFailure('INVALID_ARGUMENTS', 'max_findings must be 1–2000.')
    findings = {}
    nodes = {n['id']: n for n in target['nodes']}
    pairs = {p['id']: p for p in target['pairs']}
    counts = {'partitions_checked': 0, 'candidates_checked': 0, 'joint_drafts_checked': 0}

    def add(code, severity, occurrences=(), pair_ids=(), context=None, detail=None, candidate=None):
        paths, pids = sorted(set(occurrences)), sorted(set(pair_ids))
        key = stable_id('finding-', [code, paths, pids, context])
        if key not in findings:
            findings[key] = {'id': key, 'code': code, 'severity': severity,
                             'occurrence_paths': paths, 'pair_ids': pids, 'context': context,
                             'detail': detail or {}, 'candidate_refs': [], 'mechanically_verified': False}
        if candidate and candidate not in findings[key]['candidate_refs']:
            findings[key]['candidate_refs'].append(candidate)

    if target['errors']:
        add('SOURCE_INCOMPLETE', 'coverage', nodes, detail={'errors': target['errors']})
    if target['boundary_evidence']:
        add('BOUNDARY_LINKS_OUTSIDE_SCOPE', 'coverage', nodes, detail={'count': len(target['boundary_evidence'])})
    if rigid['output_truncated'] or rigid['omitted_groups']:
        add('GROUP_ALTERNATIVES_OMITTED', 'coverage', nodes,
            detail={'output_truncated': rigid['output_truncated'], 'omitted_groups': rigid['omitted_groups']})
    if len(rigid['partitions']) > 1:
        add('GROUP_MEMBERSHIP_ALTERNATIVES', 'uncertainty', nodes, detail={'partitions': len(rigid['partitions'])})
    for node in target['nodes']:
        if not node['eligible'] or node.get('source_errors'):
            add('OCCURRENCE_CONTEXT_UNAVAILABLE', 'coverage', [node['id']], detail={'errors': node.get('source_errors', [])})
    for pair in target['pairs']:
        if pair['flags']:
            add('SOURCE_PAIR_FLAGS', 'evidence_conflict', pair['node_ids'], [pair['id']], detail={'flags': pair['flags']})

    partitions = {p['id']: p for p in rigid['partitions']}
    memberships = {}
    for partition in rigid['partitions']:
        counts['partitions_checked'] += 1
        members = [n for g in partition['groups'] for n in g['member_occurrence_paths']]
        tally = Counter(members)
        if set(members) != set(nodes) or any(c != 1 for c in tally.values()):
            add('PARTITION_MEMBERSHIP_INVALID', 'structural_error', members,
                context=partition['id'], detail={'missing': sorted(set(nodes)-set(members)), 'counts': dict(tally)})
        memberships[partition['id']] = {g['id']: g for g in partition['groups']}
        for group in partition['groups']:
            members = group['member_occurrence_paths']
            if len(members) > 1:
                add('RIGID_GROUP_UNVERIFIED', 'uncertainty', members, group['internal_pair_ids'],
                    detail={'weak_contact_assumption': group['weak_contact_assumption']})
            for motion in rigid['motion_mate_pairs']:
                if set(motion['occurrence_paths']) <= set(members):
                    add('MOTION_MATE_INSIDE_GROUP', 'evidence_conflict', members, [motion['pair_id']],
                        context=partition['id'], detail={'mate_types': motion['mate_types']})

    alternatives = defaultdict(lambda: defaultdict(list))
    for run in draft['partition_results']:
        pid = run['partition_id']
        if pid not in partitions:
            add('UNKNOWN_PARTITION', 'structural_error', context=pid)
            continue
        match = run['match']
        if match is None:
            add('PARTITION_NOT_SEARCHED', 'coverage', context=pid, detail={'reason': run['skip_reason']})
            continue
        if not match['search_exhaustive'] or match['output_truncated']:
            add('MATCH_COVERAGE_LIMIT', 'coverage', context=pid,
                detail={'search_exhaustive': match['search_exhaustive'], 'output_truncated': match['output_truncated'],
                        'best_score_ties_found': match['best_score_ties_found']})
        if not match['candidates']:
            add('NO_RETURNED_CANDIDATE', 'coverage', context=pid)
        for candidate in match['candidates']:
            counts['candidates_checked'] += 1
            ref = {'partition_id': pid, 'template_id': candidate['template_id'], 'rank': candidate['rank'],
                   'candidate_id': stable_id('candidate-', [pid, candidate['template_id'], candidate['mapping']])}
            groups = memberships[pid]
            mapping = candidate['mapping']
            mapped = [m['group_id'] for m in mapping]
            members = [n for m in mapping for n in m['member_occurrence_paths']]
            valid = (len(set(mapped)) == len(mapped) and len(set(members)) == len(members) and
                     len({m['template_body_id'] for m in mapping}) == len(mapping) and
                     all(m['group_id'] in groups and m['member_occurrence_paths'] == groups[m['group_id']]['member_occurrence_paths'] for m in mapping))
            if not valid:
                add('CANDIDATE_MEMBERSHIP_INVALID', 'structural_error', members, context=ref['candidate_id'], candidate=ref)
            used = set(mapped)
            seen_edges = defaultdict(list)
            for edge in candidate['joint_hypotheses']:
                counts['joint_drafts_checked'] += 1
                paths = sorted(set(itertools.chain.from_iterable(edge['member_occurrence_paths'])))
                pids = edge['source_occurrence_pair_ids']
                group_ids = edge['group_ids']
                if (len(group_ids) != 2 or group_ids[0] == group_ids[1] or not set(group_ids) <= used or
                    any(g not in groups or members != groups[g]['member_occurrence_paths'] for g, members in zip(group_ids, edge['member_occurrence_paths']))):
                    add('JOINT_ENDPOINT_INVALID', 'structural_error', paths, pids, context=ref['candidate_id'], candidate=ref)
                seen_edges[tuple(sorted(group_ids))].append(edge['reference_joint_id'])
                source_pairs = [pairs[p] for p in pids if p in pairs]
                if len(source_pairs) != len(pids):
                    add('UNKNOWN_SOURCE_PAIR', 'structural_error', paths, pids, candidate=ref)
                if edge['hypothesis_kind'] in ('revolute', 'prismatic'):
                    locks = [p['id'] for p in source_pairs if any(s['kind']=='active_mate' and s.get('mate_type')=='lock' and not s.get('record_errors') for s in p['signals'])]
                    if locks:
                        add('ACTIVE_LOCK_VS_MOVING_HYPOTHESIS', 'evidence_conflict', paths, locks,
                            detail={'meaning': 'A root lock feature opposes the proposed relative motion; feature activity is not solver proof.'}, candidate=ref)
                    if edge['direction_candidate_root_unit'] is None:
                        add('JOINT_DIRECTION_UNKNOWN', 'uncertainty', paths, pids, candidate=ref)
                    geometry = edge['geometry']
                    if geometry and (len(geometry['geometric_line_candidates']) > 1 or geometry['line_candidates_truncated']):
                        add('AXIS_LINES_AMBIGUOUS', 'uncertainty', paths, pids,
                            detail={'line_candidates': len(geometry['geometric_line_candidates']), 'truncated': geometry['line_candidates_truncated']}, candidate=ref)
                if edge['link_support'] == 0:
                    add('JOINT_LINK_UNSUPPORTED', 'uncertainty', paths, pids, candidate=ref)
                endpoint_key = tuple(sorted(tuple(sorted(m)) for m in edge['member_occurrence_paths']))
                alternatives[endpoint_key][edge['hypothesis_kind']].append(ref)
            for ids, edges in seen_edges.items():
                if len(edges) > 1:
                    add('MULTIPLE_JOINTS_SAME_GROUP_PAIR', 'uncertainty', context=[ref['candidate_id'], list(ids)],
                        detail={'reference_joint_ids': edges, 'meaning': 'Concurrent constraints require analysis; not automatically an impossible mechanism.'}, candidate=ref)
            for axis in candidate['axis_relation_checks']:
                if axis['residual_deg'] > draft['parameters']['angle_tolerance_deg']:
                    add('REFERENCE_AXIS_RELATION_MISMATCH', 'evidence_conflict', members,
                        context=ref['candidate_id'], detail={'axis_check': axis}, candidate=ref)
            if candidate['unmatched_group_ids']:
                add('LOCAL_CANDIDATE_UNMATCHED_GROUPS', 'coverage', context=ref['candidate_id'],
                    detail={'group_ids': candidate['unmatched_group_ids']}, candidate=ref)
    for endpoints, kinds in alternatives.items():
        if len(kinds) > 1:
            add('JOINT_KIND_ALTERNATIVES', 'uncertainty', itertools.chain.from_iterable(endpoints),
                context=[list(x) for x in endpoints], detail={'kinds': sorted(kinds), 'scope': 'returned candidates only'})
    add('JOINT_PHYSICS_UNVERIFIED', 'uncertainty', nodes,
        detail={'unknown': ['degrees_of_freedom', 'pivot', 'limits', 'pitch', 'motion_feasibility'],
                'meaning': 'Current read-only geometry tools cannot certify these mechanical properties.'})
    rows = sorted(findings.values(), key=lambda r: (SEVERITIES[r['severity']], r['code'], r['id']))
    severity_counts = dict(Counter(r['severity'] for r in rows))
    return {'draft_check_schema_version': 1, 'algorithm_version': 1,
            'parameters': {'max_findings': max_findings}, 'document': target['document'],
            'findings': rows[:max_findings], 'summary': {**counts, 'findings_found': len(rows),
                'findings_returned': min(len(rows), max_findings), 'severity_counts': severity_counts},
            'output_truncated': len(rows) > max_findings, 'structural_checks_passed': not severity_counts.get('structural_error'),
            'physical_consistency_verified': False, 'requires_human_review': False, 'solidworks_modified': False,
            'scope': 'Source-replayed retained partitions and returned local candidates, not all mechanisms or physical DOF.',
            'source_errors': target['errors'], 'heldout_exposed': draft['heldout_exposed'],
            'limitations': ['Structural invariants are checked separately from physical hypotheses; no findings is not mechanical verification.',
                'Different candidate joint types are alternative explanations, not simultaneous constraints.',
                'Active lock/motion conflicts are source feature evidence, not a solver verdict. Reference axis mismatches are template-fit differences.',
                'Only returned candidates are inspected; omitted search/partition/output scopes remain unknown. No CAD writes or human-review gate.']}
