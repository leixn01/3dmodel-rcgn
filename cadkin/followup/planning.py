"""Concrete, bounded read-only calls with explicit guards; generating a plan never runs it."""
from pathlib import Path

from cadkin.errors import ToolFailure
from cadkin.followup import stable_id
from cadkin.followup.observations import request_key, MAX_ROUNDS

READ_TOOLS = {'sw_active_document', 'sw_component_spatial', 'sw_component_constraints',
              'sw_component_cylinders', 'sw_component_faces', 'sw_component_distance', 'sw_mate_inventory'}


def plan_initial_root_mates(target, check, capture_directory, max_tasks):
    """Explicit first-run profile: one enhanced root capture plus unchanged guards."""
    nodes = {n['id']: n for n in target['nodes']}
    requests, blocked = {}, {}
    available = check['structural_checks_passed'] and all(n['eligible'] and not n.get('source_errors') and
        n.get('to_root_column_vectors_m') for n in nodes.values())
    args = {'expected_document_token': target['document']['document_token'], 'max_features': 2000,
            'max_mates': 200, 'max_entities': 16, 'max_depth': 32, 'include_reference_geometry': True}
    key = stable_id('capture-', ['sw_mate_inventory', args])
    if available:
        requests[key] = {'id': key, 'tool': 'sw_mate_inventory', 'arguments': args,
            'occurrence_paths': sorted(nodes), 'finding_ids': [], 'priority': 10,
            'integration': 'create_initial_root_mate_basis'}
    else:
        blocked[key] = {'tool': 'sw_mate_inventory', 'occurrence_paths': sorted(nodes),
                        'finding_ids': [], 'reason': 'SOURCE_CONTEXT_UNAVAILABLE'}
    result = assemble_plan(target, check, {'_indexed': True, 'rounds_completed': 0},
                           capture_directory, max_tasks, requests, {}, [], blocked)
    result.update(algorithm_version=5, plan_kind='initial_root_mates')
    result['parameters']['initial_capture_profile'] = 'root_mates'
    result['limitations'].extend([
        'First empty-evidence chain only; use the existing index/constraint-gap planner for subsequent capture.',
        'Collects root mates and direct reference geometry once. No cylinder/body scan, inferred joint or CAD edit.',
        'All document and instance guards remain in the call budget; missing/partial data is not retried.'])
    return result


def plan_tasks(target, check, facts, capture_directory, max_tasks=20):
    if type(max_tasks) is not int or not 3 <= max_tasks <= 200:
        raise ToolFailure('INVALID_ARGUMENTS', 'max_tasks must be 3–200, including before/after guards.')
    nodes = {n['id']: n for n in target['nodes']}
    pairs = {p['id']: p for p in target['pairs']}
    token = target['document']['document_token']
    requests, reused, unresolved, blocked = {}, {}, [], {}

    def request(tool, paths, issue, priority, options=None, integration='recompute_dependent_evidence'):
        paths = sorted(set(paths))
        if facts.get('_indexed'):
            key = request_key(tool, paths)
            attempts = facts['attempted_requests'].get(key, [])
            if attempts or facts['rounds_completed'] >= MAX_ROUNDS:
                row = blocked.setdefault(key, {'tool': tool, 'occurrence_paths': paths, 'finding_ids': [],
                    'reason': 'PRIOR_ATTEMPT_NO_AUTOMATIC_RETRY' if attempts else 'ROUND_LIMIT',
                    'observation_ids': [a['id'] for a in attempts]})
                if issue['id'] not in row['finding_ids']: row['finding_ids'].append(issue['id'])
                return
        if not paths or any(p not in nodes or not nodes[p]['eligible'] or nodes[p].get('source_errors') or
                            nodes[p].get('to_root_column_vectors_m') is None for p in paths):
            unresolved.append({'finding_id': issue['id'], 'reason': 'SOURCE_CONTEXT_UNAVAILABLE', 'occurrence_paths': paths})
            return
        arguments = {'expected_document_token': token, **(options or {})}
        if tool == 'sw_component_distance':
            arguments.update(left_occurrence_path=paths[0], right_occurrence_path=paths[1])
        elif tool != 'sw_mate_inventory':
            arguments['occurrence_path'] = paths[0]
        key = stable_id('capture-', [tool, arguments])
        row = requests.setdefault(key, {'id': key, 'tool': tool, 'arguments': arguments, 'occurrence_paths': paths,
            'finding_ids': [], 'priority': priority, 'integration': integration})
        row['priority'] = min(priority, row['priority'])
        if issue['id'] not in row['finding_ids']: row['finding_ids'].append(issue['id'])

    def collect_or_reuse(family, tool, path, issue, priority, options=None, integration='recompute_dependent_evidence'):
        known = facts.get(family, {}).get(path, [])
        if known:
            key = stable_id('reuse-', [family, path])
            row = reused.setdefault(key, {'family': family, 'occurrence_path': path, 'sources': known, 'finding_ids': []})
            if issue['id'] not in row['finding_ids']: row['finding_ids'].append(issue['id'])
        else:
            request(tool, [path], issue, priority, options, integration)

    for issue in check['findings']:
        code, paths = issue['code'], issue['occurrence_paths']
        if not check['structural_checks_passed']:
            unresolved.append({'finding_id': issue['id'], 'reason': 'REGENERATE_INVALID_DERIVATION'})
            continue
        if code in {'JOINT_KIND_ALTERNATIVES', 'JOINT_LINK_UNSUPPORTED', 'SOURCE_INCOMPLETE'}:
            if facts.get('root_mates'):
                reused['root_mates'] = {'family': 'root_mates', 'sources': facts['root_mates'],
                                        'reason': 'Complete scoped root mate capture already exists; no blind repeat.'}
            else:
                request('sw_mate_inventory', nodes, issue, 10,
                        {'max_features': 2000, 'max_mates': 200, 'max_entities': 16, 'max_depth': 32})
        if code == 'RIGID_GROUP_UNVERIFIED':
            for path in paths:
                collect_or_reuse('constraints', 'sw_component_constraints', path, issue, 30,
                                {'max_mates': 100, 'max_entities': 16}, 'supplemental_context_only_not_consumed_by_chain')
        if code in {'JOINT_DIRECTION_UNKNOWN', 'TARGET_GEOMETRY_MISSING'}:
            for path in paths:
                collect_or_reuse('cylinders', 'sw_component_cylinders', path, issue, 20,
                    {'max_bodies': 50, 'max_faces': 1000, 'max_cylinders': 200, 'include_face_references': True})
            unresolved.append({'finding_id': issue['id'], 'reason': 'GEOMETRY_MAY_HAVE_NO_CYLINDERS_OR_MULTIPLE_AXES',
                               'meaning': 'A complete existing scan is reused even when empty; absence does not certify absent joints.'})
        if code == 'AXIS_LINES_AMBIGUOUS':
            for path in paths:
                collect_or_reuse('faces', 'sw_component_faces', path, issue, 40,
                                {'max_bodies': 20, 'max_faces': 200})
            unresolved.append({'finding_id': issue['id'], 'reason': 'FACE_PAIR_AND_SEEDS_NOT_YET_SELECTED',
                'next_capability': 'face-gap-probing or mate-face-matching',
                'meaning': 'Face catalogs alone do not choose the mating faces or resolve the joint. No invented face IDs/seeds.'})
        if code == 'JOINT_LINK_UNSUPPORTED':
            for pair_id in issue['pair_ids']:
                pair = pairs.get(pair_id)
                if not pair: continue
                observed = [s for s in pair['signals'] if s.get('measurement') and not s['measurement'].get('source_errors')]
                indexed = facts.get('distance', {}).get(tuple(sorted(pair['node_ids'])), [])
                if observed:
                    reused['distance-'+pair_id] = {'family': 'distance', 'pair_id': pair_id,
                        'sources': [s['measurement'] for s in observed], 'reason': 'Existing measured distance retained, including separated pairs.'}
                elif indexed:
                    reused['distance-'+pair_id] = {'family': 'distance', 'pair_id': pair_id,
                        'sources': indexed, 'reason': 'Complete guarded distance retained; may still need compatible reintegration.'}
                else:
                    request('sw_component_distance', pair['node_ids'], issue, 25)
        if code in {'ACTIVE_LOCK_VS_MOVING_HYPOTHESIS', 'MOTION_MATE_INSIDE_GROUP', 'REFERENCE_AXIS_RELATION_MISMATCH',
                    'SOURCE_PAIR_FLAGS', 'JOINT_PHYSICS_UNVERIFIED', 'JOINT_KIND_ALTERNATIVES',
                    'GROUP_MEMBERSHIP_ALTERNATIVES', 'BOUNDARY_LINKS_OUTSIDE_SCOPE', 'MATCH_COVERAGE_LIMIT',
                    'PARTITION_NOT_SEARCHED', 'NO_RETURNED_CANDIDATE', 'GROUP_ALTERNATIVES_OMITTED',
                    'MULTIPLE_JOINTS_SAME_GROUP_PAIR', 'LOCAL_CANDIDATE_UNMATCHED_GROUPS', 'OCCURRENCE_CONTEXT_UNAVAILABLE',
                    'TARGET_JOINT_TYPE_UNDETERMINED', 'TARGET_PAIR_COVERAGE_LIMIT', 'TARGET_RELATIONSHIP_CONFLICT'}:
            unresolved.append({'finding_id': issue['id'], 'reason': code,
                'meaning': 'Retain this finding; collection success alone does not resolve it. Recompute/reconcile scopes, search or constraints as applicable.'})

    return assemble_plan(target, check, facts, capture_directory, max_tasks, requests, reused, unresolved, blocked)


def assemble_plan(target, check, facts, capture_directory, max_tasks, requests, reused, unresolved, blocked):
    """Shared task budget, dependencies and guards for independently generated requests."""
    if type(max_tasks) is not int or not 3 <= max_tasks <= 200:
        raise ToolFailure('INVALID_ARGUMENTS', 'max_tasks must be 3–200, including before/after guards.')
    nodes = {n['id']: n for n in target['nodes']}
    token = target['document']['document_token']
    ordered = sorted(requests.values(), key=lambda r: (r['priority'], r['tool'], r['id']))
    selected, deferred, guarded = [], [], set()
    for request_row in ordered:
        proposed = guarded | set(request_row['occurrence_paths'])
        # Two document guards and before/after pose guards are part of the call budget.
        cost = 2 + 2*len(proposed) + len(selected) + 1
        if cost <= max_tasks:
            selected.append(request_row); guarded = proposed
        else:
            deferred.append({**request_row, 'reason': 'TASK_BUDGET_INCLUDING_GUARDS'})
    directory = Path(capture_directory)
    tasks = []
    def add(task_id, tool, arguments, phase, depends, expected=None, **extra):
        tasks.append({'id': task_id, 'tool': tool, 'arguments': arguments, 'phase': phase,
                      'depends_on': depends, 'save_envelope_path': str(directory/(task_id+'.json')),
                      'expected_context': expected, 'executed': False, **extra})
    add('document-before', 'sw_active_document', {}, 'preflight', [], target['document'])
    for path in sorted(guarded):
        key = stable_id('pose-before-', path)
        add(key, 'sw_component_spatial', {'expected_document_token': token, 'occurrence_path': path},
            'preflight', ['document-before'], nodes[path])
    for row in selected:
        add(row['id'], row['tool'], row['arguments'], 'capture',
            ['document-before']+[stable_id('pose-before-', p) for p in row['occurrence_paths']],
            [nodes[p] for p in row['occurrence_paths']], finding_ids=sorted(row['finding_ids']),
            priority=row['priority'], integration=row['integration'])
    capture_ids = [r['id'] for r in selected]
    for path in sorted(guarded):
        add(stable_id('pose-after-', path), 'sw_component_spatial',
            {'expected_document_token': token, 'occurrence_path': path}, 'postflight', capture_ids,
            nodes[path])
    add('document-after', 'sw_active_document', {}, 'postflight',
        [t['id'] for t in tasks if t['phase'] == 'postflight'] or capture_ids or ['document-before'], target['document'])
    result = {'evidence_task_plan_schema_version': 1, 'algorithm_version': 1,
            'parameters': {'max_tasks': max_tasks}, 'document': target['document'],
            'tasks': tasks, 'deferred_tasks': deferred, 'reused_evidence': list(reused.values()),
            'unresolved_findings': unresolved,
            'summary': {'requested_capture_tasks': len(ordered), 'planned_capture_tasks': len(selected),
                        'guard_tasks': len(tasks)-len(selected), 'total_tool_calls': len(tasks),
                        'deferred_capture_tasks': len(deferred), 'reused_evidence_groups': len(reused)},
            'check_output_truncated': check['output_truncated'], 'output_truncated': bool(deferred) or check['output_truncated'],
            'heldout_exposed': check['heldout_exposed'],
            'executed': False, 'requires_human_review': False, 'solidworks_modified': False,
            'execution_policy': {'serial_only': True, 'save_original_envelopes': True,
                'on_document_or_pose_mismatch': 'Stop dependent capture; collect a fresh spatial snapshot and rebuild derived files. Never replace tokens or hashes in old evidence.',
                'on_task_error_or_partial': 'Retain raw result and errors; stop dependent tasks if identity/pose is unavailable. Continue independent tasks only when their guards passed.',
                'guard_validation': 'Compare document token/path/type/configuration and dirty flag, then occurrence file/parent/configuration, resolved state and root column transform against expected_context. Missing required fields fail the guard; compare postflight again.',
                'postflight_failure': 'Keep observations as diagnostic artifacts; do not integrate them into the old source snapshot.',
                'retry_policy': 'No blind retries, no automatic budget escalation and no assumption of physical confirmation.',
                'tool_scope': sorted(READ_TOOLS)},
            'recompute_handoffs': [
                {'family': 'cylinders', 'next_tools': ['cad_component_relations','cad_review_connections'], 'note': 'Use newly captured raw files, same inventory snapshot and explicit original tolerances; rebuild bindings.'},
                {'family': 'distance', 'next_tools': ['cad_review_proximity'], 'note': 'Requires its source-bound proximity worklist and explicit tolerance; no automatic contact certification.'},
                {'family': 'faces', 'next_tools': ['sw_probe_face_pair','cad_review_face_contacts'], 'note': 'Only after actual face references and explicit seeds are available; catalogs alone are not face contact evidence.'},
                {'family': 'root_mates', 'next_tools': ['cad_review_connections'], 'note': 'Recompute against consistent relation/inventory files; raw component constraints remain context only.'},
                {'family': 'derived_chain', 'next_tools': ['cad_build_chain_evidence','cad_build_target_graph','cad_build_rigid_candidates','cad_draft_joints','cad_check_joint_draft'], 'note': 'Write fresh outputs; retain old candidates for comparison. Disappearing findings do not by themselves prove resolution.'}],
            'limitations': ['This is a plan, not executed CAD collection, pose validation or automatic evidence reintegration.',
                'Plans use the source token and require unchanged document/poses; timestamps/hashes do not certify an atomic geometry revision.',
                'Guard calls count toward max_tasks. High-cost root mate tasks may be deferred while smaller independent tasks fit.',
                'Existing complete observations are reused even if empty/ambiguous; missing DOF, stroke, pitch and motion solvers cannot be replaced by repeated scans.',
                'Only returned check findings are planned; skipped findings/search spaces remain unknown. No arbitrary scripts, CAD edits, human gate or invented face selections.']}
    if facts.get('_indexed'):
        if not selected: result['tasks'] = []
        reason = ('NEW_SUPPORTED_CAPTURE' if selected else
                  'INVALID_DERIVATION' if not check['structural_checks_passed'] else
                  'ROUND_LIMIT' if facts['rounds_completed'] >= MAX_ROUNDS else
                  'CAPTURE_BUDGET_UNAVAILABLE' if deferred else
                  'NO_NEW_CAPTURE_AFTER_ATTEMPTS' if blocked else 'NO_NEW_SUPPORTED_CAPTURE')
        result.update(algorithm_version=2, blocked_requests=list(blocked.values()),
            remaining_findings=check['findings'],
            continuation={'action': 'collect' if selected else 'stop', 'reason': reason,
                'rounds_completed': facts['rounds_completed'], 'max_rounds': MAX_ROUNDS,
                'remaining_findings': check['summary']['findings_found'], 'mechanically_verified': False})
        result['summary'].update(guard_tasks=len(result['tasks'])-len(selected),
                                 total_tool_calls=len(result['tasks']), blocked_capture_requests=len(blocked))
        result['limitations'].append('Stopping means no new supported capture in this bounded lineage, never resolved physics. No guard-only loop or automatic retries.')
    return result
