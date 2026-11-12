"""Bounded witness-guided face candidates; analytic residuals are not finite-face tests."""
import heapq
import math
from pathlib import Path

from cadkin.face_geometry import descriptor, part_point, unit
from cadkin.geometry import numbers, transform_from_sw
from cadkin.followup import stable_id
from cadkin.followup.observations import MAX_ROUNDS, request_key

FACE_READ_TOOLS = {'sw_active_document', 'sw_component_spatial', 'sw_component_faces', 'sw_probe_face_pair'}


def surface_residual_mm(face, transform, witness_root_mm):
    shape = descriptor(face['descriptor'])
    if shape['surface_type'] == 'other': return None
    transform = transform_from_sw(transform['raw_array'])
    local = part_point(transform, [x / 1000 for x in numbers(witness_root_mm, 3, 'INVALID_FACE_POINT')])
    p = shape['surface_parameters_part']
    if shape['surface_type'] == 'plane':
        residual = abs(sum(a * (b - c) for a, b, c in zip(unit(p[:3]), local, p[3:])))
    else:
        axis = unit(p[3:6]); delta = [a - b for a, b in zip(local, p[:3])]
        axial = sum(a * b for a, b in zip(delta, axis))
        residual = abs(math.hypot(*(delta[i] - axial * axis[i] for i in range(3))) - p[6])
    return numbers([residual * abs(transform['scale']) * 1000], 1, 'INVALID_FACE_GEOMETRY')[0]


def face_key(source):
    # Opaque persisted bytes are used ONLY for conservative no-repeat bookkeeping.
    # A live identity claim still requires the existing resolver/IsSame checks.
    t = source['target']
    return [t['occurrence_path'], t['file_path'], t['referenced_configuration'], source['face']['face_reference']['id']]


def probe_key(sources):
    return stable_id('probe-pair-', sorted(face_key(s) for s in sources))


def selection(source):
    return {'face_inventory_path': source['path'], 'body_index': source['face']['body_index'],
            'face_index': source['face']['face_index']}


def plan_face_tasks(target, check, facts, index, capture_directory, *, max_component_gap_mm,
                    surface_tolerance_mm, max_component_pairs=20, max_face_candidates=20,
                    max_face_pairs=100, max_tasks=20, max_iterations=20, convergence_tolerance_mm=0.001):
    nodes = {n['id']: n for n in target['nodes']}
    token = target['document']['document_token']
    gaps, contexts, requests, blocked = [], [], {}, []
    for pair in target['pairs']:
        paths = tuple(sorted(pair['node_ids']))
        if any(not nodes[p]['eligible'] or nodes[p].get('source_errors') or
               nodes[p].get('to_root_column_vectors_m') is None for p in paths):
            contexts.append({'pair_id': pair['id'], 'occurrence_paths': list(paths), 'reason': 'OCCURRENCE_CONTEXT_UNAVAILABLE'})
        elif paths in facts['distance_conflicts']:
            contexts.append({'pair_id': pair['id'], 'occurrence_paths': list(paths), 'reason': 'CONFLICTING_DISTANCE_SNAPSHOTS'})
        elif paths not in facts['distances']:
            contexts.append({'pair_id': pair['id'], 'occurrence_paths': list(paths), 'reason': 'NO_COMPLETE_DISTANCE_WITNESS'})
        else:
            witness = facts['distances'][paths]
            if witness['distance_mm'] <= max_component_gap_mm:
                gaps.append((witness['distance_mm'], paths, pair['id'], witness))
            else:
                contexts.append({'pair_id': pair['id'], 'occurrence_paths': list(paths), 'reason': 'COMPONENT_GAP_SCREEN',
                                 'distance_mm': witness['distance_mm'], 'mechanically_disconnected': False})
    gaps.sort(key=lambda r: (r[0], r[1]))
    scoped = gaps[:max_component_pairs]
    counts = {'eligible_component_pairs': len(gaps), 'examined_component_pairs': len(scoped),
              'face_candidates_before_limits': 0, 'face_candidates_omitted': 0,
              'candidate_pairs_before_limits': 0, 'previously_attempted_face_pairs': 0,
              'candidate_pairs_unattempted': 0}
    pair_sets = []
    for _, paths, pair_id, witness in scoped:
        endpoint_sets, endpoint_stats = [], []
        for path in paths:
            if path in facts['face_conflicts']:
                contexts.append({'pair_id': pair_id, 'occurrence_path': path, 'reason': 'CONFLICTING_FACE_CATALOGS'})
                endpoint_sets.append([]); continue
            if path not in facts['faces']:
                prior = facts['attempted_requests'].get(request_key('sw_component_faces', [path]), [])
                if prior:
                    blocked.append({'tool': 'sw_component_faces', 'occurrence_paths': [path],
                                    'reason': 'PRIOR_ATTEMPT_NO_AUTOMATIC_RETRY', 'observation_ids': [o['id'] for o in prior]})
                else:
                    task_id = stable_id('face-catalog-', path)
                    requests[task_id] = {'id': task_id, 'tool': 'sw_component_faces',
                        'arguments': {'expected_document_token': token, 'occurrence_path': path, 'max_bodies': 20, 'max_faces': 200},
                        'occurrence_paths': [path], 'priority': 10, 'integration': 'index_then_replan_face_probes'}
                contexts.append({'pair_id': pair_id, 'occurrence_path': path, 'reason': 'FACE_CATALOG_REQUIRED'})
                endpoint_sets.append([]); continue
            catalog = facts['faces'][path]
            matches = []
            for source in catalog['sources']:
                residual = surface_residual_mm(source['face'], source['target']['transform'], witness['point_by_occurrence_mm'][path])
                if residual is not None and residual <= surface_tolerance_mm:
                    matches.append((residual, source['face']['body_index'], source['face']['face_index'], source))
            matches.sort(key=lambda r: r[:3])
            counts['face_candidates_before_limits'] += len(matches)
            counts['face_candidates_omitted'] += max(0, len(matches) - max_face_candidates)
            endpoint_stats.append({'occurrence_path': path, 'catalog_source': catalog['binding'],
                'analytic_matches': len(matches), 'retained_faces': min(len(matches), max_face_candidates),
                'unsupported_or_reference_missing_faces': catalog['unsupported'],
                'equal_residual_at_cutoff': len(matches) > max_face_candidates and matches[max_face_candidates - 1][0] == matches[max_face_candidates][0]})
            endpoint_sets.append(matches[:max_face_candidates])
            if not matches: contexts.append({'pair_id': pair_id, 'occurrence_path': path, 'reason': 'NO_SUPPORTED_ANALYTIC_MATCH',
                                             'finite_face_membership_tested': False})
        contexts.append({'pair_id': pair_id, 'occurrence_paths': list(paths), 'reason': 'WITNESS_SCREENING',
                         'witness_source': witness['source'], 'endpoints': endpoint_stats})
        if all(endpoint_sets): pair_sets.append((paths, pair_id, witness, endpoint_sets))

    def ranked_pairs():
        for paths, pair_id, witness, (lefts, rights) in pair_sets:
            for left in lefts:
                for right in rights:
                    sources = [left[3], right[3]]; key = probe_key(sources)
                    counts['candidate_pairs_before_limits'] += 1
                    if key in facts['attempted_probes']:
                        counts['previously_attempted_face_pairs'] += 1
                        continue
                    counts['candidate_pairs_unattempted'] += 1
                    rank = (max(left[0], right[0]), left[0] + right[0], witness['distance_mm'], paths, left[1:3], right[1:3])
                    yield rank, key, pair_id, witness, sources

    selected_pairs = heapq.nsmallest(max_face_pairs, ranked_pairs(), key=lambda row: row[0])
    candidates = []
    for rank, key, pair_id, witness, sources in selected_pairs:
        paths = [s['target']['occurrence_path'] for s in sources]
        a, b = [witness['point_by_occurrence_mm'][p] for p in paths]
        seeds = []
        for seed in (a, b, [x / 2 + y / 2 for x, y in zip(a, b)]):
            if seed not in seeds: seeds.append(seed)
        row = {'id': key, 'pair_id': pair_id, 'occurrence_paths': paths,
            'selections': [selection(s) for s in sources], 'face_sources': [{'path': s['path'], 'sha256': s['sha256']} for s in sources],
            'surface_residuals_mm': [surface_residual_mm(s['face'], s['target']['transform'], witness['point_by_occurrence_mm'][p]) for s, p in zip(sources, paths)],
            'witness_source': witness['source'], 'witness_points_root_mm': [a, b], 'seed_points_root_mm': seeds,
            'seed_derivation': 'component_distance_endpoints_then_midpoint_unique',
            'finite_face_membership_tested': False, 'live_face_identity_verified': False, 'connection_confirmed': False}
        candidates.append(row)
        requests[key] = {'id': key, 'tool': 'sw_probe_face_pair', 'arguments': {
            'expected_document_token': token, 'left': row['selections'][0], 'right': row['selections'][1],
            'seed_points_root_mm': seeds, 'max_iterations': max_iterations, 'convergence_tolerance_mm': convergence_tolerance_mm},
            'expected_face_sources': sources, 'occurrence_paths': paths, 'priority': 20,
            'integration': 'index_then_explicit_face_contact_review', 'candidate_id': key}
    ordered = sorted(requests.values(), key=lambda row: (row['priority'],
        next((i for i, c in enumerate(candidates) if c['id'] == row['id']), -1), row['id']))
    chosen, deferred, guarded = [], [], set()
    for row in ordered:
        proposed = guarded | set(row['occurrence_paths'])
        reason = ('INVALID_DERIVATION' if not check['structural_checks_passed'] else
                  'ROUND_LIMIT' if index['rounds_completed'] >= MAX_ROUNDS else
                  'TASK_BUDGET_INCLUDING_GUARDS' if 2 + 2 * len(proposed) + len(chosen) + 1 > max_tasks else None)
        if reason: deferred.append({**row, 'reason': reason})
        else: chosen.append(row); guarded = proposed
    tasks = []; directory = Path(capture_directory)
    def add(key, tool, args, phase, dependencies, expected, **extra):
        tasks.append({'id': key, 'tool': tool, 'arguments': args, 'phase': phase, 'depends_on': dependencies,
                      'save_envelope_path': str(directory / (key + '.json')), 'expected_context': expected, 'executed': False, **extra})
    if chosen:
        add('document-before', 'sw_active_document', {}, 'preflight', [], target['document'])
        for path in sorted(guarded):
            add(stable_id('pose-before-', path), 'sw_component_spatial', {'expected_document_token': token, 'occurrence_path': path},
                'preflight', ['document-before'], nodes[path])
        for row in chosen:
            add(row['id'], row['tool'], row['arguments'], 'capture', ['document-before'] + [stable_id('pose-before-', p) for p in row['occurrence_paths']],
                [nodes[p] for p in row['occurrence_paths']], **{k: v for k, v in row.items() if k in ('expected_face_sources', 'integration', 'candidate_id')})
        for path in sorted(guarded):
            add(stable_id('pose-after-', path), 'sw_component_spatial', {'expected_document_token': token, 'occurrence_path': path},
                'postflight', [r['id'] for r in chosen], nodes[path])
        add('document-after', 'sw_active_document', {}, 'postflight', [t['id'] for t in tasks if t['phase'] == 'postflight'], target['document'])
    counts['returned_face_pairs'] = len(candidates)
    limited = (len(gaps) > len(scoped) or counts['face_candidates_omitted'] > 0 or
               counts['candidate_pairs_unattempted'] > len(candidates) or bool(deferred))
    reason = ('NEW_SUPPORTED_CAPTURE' if chosen else 'INVALID_DERIVATION' if not check['structural_checks_passed'] else
              'ROUND_LIMIT' if index['rounds_completed'] >= MAX_ROUNDS else 'CAPTURE_BUDGET_UNAVAILABLE' if deferred else
              'NO_NEW_FACE_CAPTURE')
    return {'evidence_task_plan_schema_version': 1, 'algorithm_version': 3, 'plan_kind': 'witness_guided_face_probes',
        'document': target['document'], 'tasks': tasks, 'deferred_tasks': deferred, 'blocked_requests': blocked,
        'face_candidates': candidates, 'pair_contexts': contexts, 'coverage': counts,
        'summary': {'requested_capture_tasks': len(ordered), 'planned_capture_tasks': len(chosen),
                    'guard_tasks': len(tasks) - len(chosen), 'total_tool_calls': len(tasks), 'deferred_capture_tasks': len(deferred)},
        'remaining_findings': check['findings'], 'check_output_truncated': check['output_truncated'],
        'output_truncated': limited or check['output_truncated'], 'heldout_exposed': check['heldout_exposed'] or index['heldout_exposed'],
        'continuation': {'action': 'collect' if chosen else 'stop', 'reason': reason,
                         'rounds_completed': index['rounds_completed'], 'max_rounds': MAX_ROUNDS,
                         'remaining_findings': check['summary']['findings_found'], 'mechanically_verified': False},
        'executed': False, 'requires_human_review': False, 'solidworks_modified': False, 'mechanically_verified': False,
        'execution_policy': {'serial_only': True, 'tool_scope': sorted(FACE_READ_TOOLS), 'automatic_retry': False},
        'limitations': ['Witnesses are actual component-distance points. Analytic plane/cylinder residuals rank candidates; they do NOT test membership in trimmed faces.',
            'Coplanar, split, periodic or coaxial faces remain competing candidates. UV ranges do not certify trim membership. Ranking is not a probability.',
            'Saved persistent references bind locators; only the live probe resolves identity and tests finite-face points. Byte keys only prevent repeated attempts.',
            'No residual match may reflect assembly cuts, unsupported surfaces or source gaps; it never proves no connection. Definition-face probes exclude assembly-level features.',
            'Component-pair, endpoint-face, output-pair, call and four-round limits are explicit. Changing seeds or iteration budgets does not retry an attempted face pair.',
            'Continue with the newest index; only the supplied lineage is known. Stop retains all findings and omitted candidates; no human review gate or mechanical verdict.',
            'Probe results require independent explicit-threshold face-contact review; they do not automatically alter the joint draft.']}
