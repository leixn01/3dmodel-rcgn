"""Request only missing enhanced mate evidence; share the existing bounded executor."""
from cadkin.followup import stable_id
from cadkin.followup.observations import MAX_ROUNDS
from cadkin.followup.planning import assemble_plan

GAPS = {'MATE_REFERENCE_GEOMETRY_MISSING_OR_UNSUPPORTED', 'CONCENTRIC_ROTATION_LOCK_UNKNOWN'}


def plan_constraint_tasks(target, check, analysis, index, source_attempts, directory, max_tasks):
    rounds = index['rounds_completed'] if index else 0
    observations = index['observations'] if index else []
    attempts = [o for o in observations if o['tool'] == 'sw_mate_inventory' and o['arguments'].get('include_reference_geometry') is True]
    findings = []
    for pair in analysis['pairs']:
        for snapshot in pair['snapshots']:
            for gap in snapshot['missing_evidence']:
                findings.append({'id': stable_id('constraint-gap-', [pair['pair_id'], snapshot['source'], gap]),
                    'pair_id': pair['pair_id'], 'occurrence_paths': pair['occurrence_paths'], 'source': snapshot['source'], **gap})
        findings.extend({'id': stable_id('constraint-gap-', [pair['pair_id'], gap]), 'pair_id': pair['pair_id'],
            'occurrence_paths': pair['occurrence_paths'], **gap} for gap in pair['missing_evidence'])
    actionable = [f for f in findings if f['code'] in GAPS]
    requests, reused, unresolved, blocked = {}, {}, [], {}
    for row in findings:
        if row not in actionable: unresolved.append({'finding_id': row['id'], 'reason': row['code']})
    reason = None
    if rounds >= MAX_ROUNDS: reason = 'ROUND_LIMIT'
    elif len(analysis['mate_sources']) > 1: reason = 'MULTIPLE_MATE_SNAPSHOTS_NOT_COMBINED'
    elif not analysis['mate_sources']: reason = 'NO_EXISTING_CONNECTION_BASIS'
    elif attempts: reason = 'PRIOR_ENHANCED_ATTEMPT_NO_AUTOMATIC_RETRY'
    elif source_attempts: reason = 'ENHANCED_SOURCE_ALREADY_OBSERVED'
    elif not check['structural_checks_passed']: reason = 'INVALID_DERIVATION'
    nodes = {n['id']: n for n in target['nodes']}
    if actionable and not reason and any(not n['eligible'] or n.get('source_errors') or not n.get('to_root_column_vectors_m') for n in nodes.values()):
        reason = 'SOURCE_CONTEXT_UNAVAILABLE'
    if attempts or source_attempts:
        reused['enhanced_mates'] = {'family': 'root_mates', 'capture_profile': 'reference_geometry',
            'sources': [o['source'] for o in attempts if o['usable']] + source_attempts,
            'attempted_observation_ids': [o['id'] for o in attempts],
            'meaning': 'Keep failed/partial attempts and complete empty captures. Reintegrate a compatible guarded receipt when needed; never retry automatically.'}
    if actionable:
        if reason:
            blocked['enhanced_mates'] = {'tool': 'sw_mate_inventory', 'occurrence_paths': sorted(nodes),
                'finding_ids': [f['id'] for f in actionable], 'reason': reason,
                'observation_ids': [o['id'] for o in attempts]}
        else:
            args = {'expected_document_token': target['document']['document_token'], 'max_features': 2000,
                'max_mates': 200, 'max_entities': 16, 'max_depth': 32, 'include_reference_geometry': True}
            key = stable_id('capture-', ['sw_mate_inventory', args])
            requests[key] = {'id': key, 'tool': 'sw_mate_inventory', 'arguments': args,
                'occurrence_paths': sorted(nodes), 'finding_ids': [f['id'] for f in actionable], 'priority': 10,
                'integration': 'recompute_target_constraint_analysis'}
    facts = {'_indexed': True, 'rounds_completed': rounds}
    result = assemble_plan(target, check, facts, directory, max_tasks, requests, reused, unresolved, blocked)
    result.update(algorithm_version=4, plan_kind='target_constraint_gaps', constraint_findings=findings,
        constraint_coverage=analysis['coverage'], retained_constraint_conflicts=[{'pair_id': p['pair_id'], 'source': s['source'],
            'conflicts': s['conflicts']} for p in analysis['pairs'] for s in p['snapshots'] if s['conflicts']],
        constraint_pair_flags=[{'pair_id': p['pair_id'], 'flags': p['flags']} for p in analysis['pairs'] if p['flags']],
        enhanced_capture_already_attempted=bool(attempts or source_attempts))
    if not result['tasks'] and reason:
        result['continuation']['reason'] = reason
    result['continuation']['remaining_constraint_findings'] = len(findings)
    result['output_truncated'] |= bool(analysis['coverage']['omitted_pairs'])
    result['limitations'].extend([
        'Basic mates and enhanced reference-geometry captures are distinct capabilities; a basic capture does not satisfy enhancement.',
        'An enhanced attempt, even partial/failed, is not retried. Changing output paths or scan budgets does not reset history.',
        'No-mate STEP, unsupported geometry, conflicts and missing solvers do not trigger repeated enhanced scans.',
        'Constraint gaps schedule at most one root-mate call. All scoped instance guards count toward the shared call budget.'])
    return result
