"""Bounded alternative partitions. A candidate group never certifies rigidity."""
import hashlib
import itertools
import json

from cadkin.errors import ToolFailure
from cadkin.matching.target import axis_angle

MOTION_MATES = {'cam_follower', 'gear', 'rack_pinion', 'path', 'screw',
                'linear_coupler', 'universal_joint', 'slot', 'hinge', 'slider'}


def require(ok, message):
    if not ok:
        raise ToolFailure('INVALID_RIGID_ARGUMENTS', message)


def stable_id(prefix, members):
    payload = json.dumps(sorted(members), ensure_ascii=False, separators=(',', ':'))
    return prefix + hashlib.sha256(payload.encode()).hexdigest()[:20]


def join(parts, paths):
    selected = [p for p in parts if set(p) & set(paths)]
    merged = sorted(set().union(*map(set, selected)))
    return sorted([p for p in parts if p not in selected] + [merged])


def candidate_partitions(target, max_group_size=8, max_partitions=8,
                         include_contact_hypotheses=True):
    require(type(max_group_size) is int and 2 <= max_group_size <= 20, 'max_group_size must be 2–20.')
    require(type(max_partitions) is int and 1 <= max_partitions <= 12, 'max_partitions must be 1–12.')
    require(type(include_contact_hypotheses) is bool, 'include_contact_hypotheses must be boolean.')
    nodes = {n['id']: n for n in target['nodes']}
    pairs = sorted(target['pairs'], key=lambda p: tuple(p['node_ids']))
    proposals = []
    motion_pairs = []
    for pair in pairs:
        active = [s for s in pair['signals'] if s['kind'] == 'active_mate' and not s.get('record_errors')]
        motion = sorted({s['mate_type'] for s in active if s.get('mate_type') in MOTION_MATES})
        if motion:
            motion_pairs.append({'pair_id': pair['id'], 'occurrence_paths': pair['node_ids'], 'mate_types': motion})
        lock = any(s.get('mate_type') == 'lock' for s in active)
        contact = any(s['kind'] == 'near_component' or
                      (s['kind'] == 'near_face_sample' and s.get('converged') is True) for s in pair['signals'])
        if not lock and not (include_contact_hypotheses and contact):
            continue
        reasons = []
        if not all(nodes[n]['eligible'] for n in pair['node_ids']): reasons.append('INELIGIBLE_OCCURRENCE')
        if any(nodes[n].get('source_errors') for n in pair['node_ids']): reasons.append('OCCURRENCE_SOURCE_ERRORS')
        if pair['flags']: reasons.append('PAIR_FLAGS_PRESENT')
        if motion: reasons.append('MOTION_MATE_PRESENT')
        proposals.append({'pair_id': pair['id'], 'occurrence_paths': pair['node_ids'],
                          'basis': 'active_lock_mate' if lock else 'contact_only_hypothesis',
                          'status': 'blocked' if reasons else 'proposed', 'blocking_reasons': reasons,
                          'signal_evidence': pair['signals'], 'flags': pair['flags'],
                          'rigidity_confirmed': False})
    singles = [[n] for n in sorted(nodes)]
    lock_rows = [p for p in proposals if p['status'] == 'proposed' and p['basis'] == 'active_lock_mate']
    locked = singles
    for p in lock_rows: locked = join(locked, p['occurrence_paths'])
    omissions = []

    def admissible(group):
        if len(group) == 1: return True
        reasons = []
        if len(group) > max_group_size: reasons.append('GROUP_SIZE_LIMIT')
        if any(set(p['occurrence_paths']) <= set(group) for p in motion_pairs): reasons.append('INTERNAL_MOTION_MATE')
        if reasons:
            omissions.append({'occurrence_paths': group, 'reasons': reasons})
        return not reasons

    # Reject an oversized/conflicting closure as a whole; never silently split it into an accepted prefix.
    locked = sorted([piece for group in locked for piece in ([group] if admissible(group) else [[n] for n in group])])
    candidates = []
    seen = set()

    def add(parts, basis):
        key = tuple(tuple(g) for g in parts)
        if key in seen: return
        if any(not admissible(g) for g in parts): return
        seen.add(key)
        # Count omitted alternatives without materializing their repeated member/evidence records.
        if len(candidates) >= max_partitions: return
        groups = []
        for members in parts:
            internal = [p for p in pairs if set(p['node_ids']) <= set(members)]
            merge_rows = [p for p in proposals if p['status'] == 'proposed' and set(p['occurrence_paths']) <= set(members)]
            weak = len(members) > 1 and not all(
                any(set(q['occurrence_paths']) <= set(members) and n in q['occurrence_paths'] for q in lock_rows)
                for n in members)
            # Explicitly flag contact-bridge partitions even if each member belongs to a locked cluster.
            if basis == 'single_contact_bridge' and len(members) > 1 and members not in locked: weak = True
            groups.append({'id': stable_id('body-', members), 'member_occurrence_paths': members,
                           'eligible': all(nodes[n]['eligible'] for n in members),
                           'internal_pair_ids': [p['id'] for p in internal],
                           'merge_evidence_pair_ids': [p['pair_id'] for p in merge_rows],
                           'weak_contact_assumption': weak, 'rigidity_confirmed': False})
        candidates.append({'id': stable_id('partition-', key), 'basis': basis, 'groups': groups,
                           'multi_occurrence_groups': sum(len(g['member_occurrence_paths']) > 1 for g in groups),
                           'risk_codes': ['RIGIDITY_NOT_SOLVED'] + (['CONTACT_DOES_NOT_PROVE_RIGIDITY'] if any(g['weak_contact_assumption'] for g in groups) else [])})

    add(singles, 'unmerged_baseline')
    add(locked, 'lock_connected_components')
    for p in lock_rows: add(join(singles, p['occurrence_paths']), 'single_lock_pair')
    for p in proposals:
        if p['status'] == 'proposed' and p['basis'] == 'contact_only_hypothesis':
            add(join(locked, p['occurrence_paths']), 'single_contact_bridge')
    retained = candidates[:max_partitions]
    return {'rigid_candidates_schema_version': 1, 'algorithm_version': 1,
            'document': target['document'], 'chain_name': target['chain_name'],
            'parameters': {'max_group_size': max_group_size, 'max_partitions': max_partitions,
                           'include_contact_hypotheses': include_contact_hypotheses},
            'partitions': retained, 'pair_proposals': proposals, 'motion_mate_pairs': motion_pairs,
            'omitted_groups': list({json.dumps(o, sort_keys=True): o for o in omissions}.values()),
            'output_truncated': len(seen) > len(retained),
            'coverage': {'occurrences': len(nodes), 'proposals': len(proposals),
                         'blocked_proposals': sum(p['status'] == 'blocked' for p in proposals),
                         'generated_partitions': len(seen), 'returned_partitions': len(retained)},
            'source_complete': target['complete'], 'source_errors': target['errors'],
            'boundary_evidence': target['boundary_evidence'],
            'requires_human_review': False, 'solidworks_modified': False, 'rigidity_confirmed': False,
            'partition_space_exhaustive': False,
            'limitations': ['Partitions are bounded alternatives, not a solved rigid-body decomposition. The unmerged baseline is always retained.',
                'Only explicit active clean lock mates generate lock closures; ordinary mates, same parent/file, names and axes alone do not.',
                'A contact bridge is a weak alternative: proximity may mean sliding, rotation, penetration or coincident samples, not fixed attachment.',
                'At most one contact bridge is added to a lock partition; arbitrary combinations and all possible partitions are not enumerated.',
                'Root mates only; missing internal assembly constraints and partial sources remain unknown. No solver or motion evidence is available.']}


def aggregate_target(target, partition):
    """Collapse one hypothesis for matching, retaining every underlying occurrence pair."""
    original = {tuple(sorted(p['node_ids'])): p for p in target['pairs']}
    groups = sorted(partition['groups'], key=lambda g: g['id'])
    pairs = []
    for left, right in itertools.combinations(groups, 2):
        rows = [original[tuple(sorted((a, b)))] for a in left['member_occurrence_paths'] for b in right['member_occurrence_paths']]
        axes = [a for p in rows for a in p['axis_relations']]
        directions = [p['representative_axis_unit'] for p in rows if p['representative_axis_unit'] is not None]
        truncated = len(axes) > 128 or any(p.get('axes_truncated') for p in rows)
        ambiguous = truncated or any(p['axis_relations'] and p['representative_axis_unit'] is None for p in rows)
        representative = directions[0] if directions and not ambiguous and all(axis_angle(directions[0], d) < 1e-6 for d in directions) else None
        ids = [left['id'], right['id']]
        pairs.append({'id': stable_id('group-pair-', ids), 'node_ids': ids,
                      'link_support': max(p['link_support'] for p in rows),
                      'representative_axis_unit': representative,
                      'axis_relations': axes[:128], 'axes_truncated': truncated,
                      'axis_relation_count': sum(p.get('axis_relation_count', len(p['axis_relations'])) for p in rows),
                      'signals': [s for p in rows for s in p['signals']],
                      'flags': [f for p in rows for f in p['flags']] +
                               ([{'code': 'GROUP_AXIS_LIMIT', 'message': 'At most 128 group-pair axis records retained; all original pair IDs remain available.'}] if len(axes) > 128 else []),
                      'source_pair_ids': [p['id'] for p in rows]})
    return {'nodes': [{'id': g['id'], 'eligible': g['eligible']} for g in groups], 'pairs': pairs,
            'coverage': {'groups': len(groups), 'occurrences': len(target['nodes']), 'pairs': len(pairs)},
            'errors': target['errors'], 'complete': target['complete'], 'boundary_evidence': target['boundary_evidence']}
