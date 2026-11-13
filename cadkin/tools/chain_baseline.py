"""Initialize compatible relation bases from a first guarded capture, offline only."""
from cadkin.errors import failure, success
from cadkin.tools.chain_sources import require
from cadkin.tools.execution import replay_execution
from cadkin.tools.files import read_json, json_path
from cadkin.tools.matching import recheck
from cadkin.tools.workflow_log import WorkflowLog, binding


def create_chain_baseline(root, call, execution_path, output_path,
                          distance_tolerance_mm, angle_tolerance_deg):
    execution, plan, check, target, eb = replay_execution(root, execution_path)
    require(execution['execution_complete'] and execution['guards_passed'],
            'Only a complete first execution with passed guards can initialize a baseline.', 'EXECUTION_GUARDS_FAILED')
    require(plan['algorithm_version'] == 1 and not plan.get('evidence_index_source') and
            not target['relation_sources'] and not target['source_coverage'],
            'Use an initial empty-evidence chain only; existing bases/history require reintegration.', 'BASELINE_ALREADY_EXISTS')
    chain, _ = read_json(json_path(root, target['source_chain']['path']))
    require(not chain['sources'] and 2 <= len(chain['members']) <= 20,
            'Baseline requires an explicit 2–20-component scope without prior evidence.', 'INVALID_CHAIN_SCOPE')
    log = WorkflowLog(root, output_path, call)
    tasks = {t['id']: t for t in plan['tasks']}
    eligible = [r for r in execution['records'] if r['task_id'] in execution['eligible_capture_ids']]
    cylinders = [r for r in eligible if tasks[r['task_id']]['tool'] == 'sw_component_cylinders']
    mates = [r for r in eligible if tasks[r['task_id']]['tool'] == 'sw_mate_inventory']
    used, sources, relations = [], [], []
    outputs, error = {}, None
    inputs = plan['input_files'] + [eb, execution['plan_source']] + [
        r['envelope_source'] for r in execution['records'] if r['envelope_source']]
    try:
        if len(cylinders) >= 2:
            path = log.path('relations')
            log.run('cad_component_relations', {'inventory_path': chain['parameters']['inventory_path'],
                'cylinder_paths': [r['envelope_source']['path'] for r in cylinders], 'output_path': path,
                'distance_tolerance_mm': distance_tolerance_mm, 'angle_tolerance_deg': angle_tolerance_deg})
            relations.append(path)
            used.extend(r['task_id'] for r in cylinders)
            require(len(mates) <= 1, 'Multiple root mate snapshots in one baseline.', 'INVALID_EXECUTION')
            if mates:
                path = log.path('connections')
                log.run('cad_review_connections', {'relations_path': relations[0],
                    'mate_inventory_path': mates[0]['envelope_source']['path'], 'output_path': path})
                sources.append(path)
                used.append(mates[0]['task_id'])
        pipeline = [
            ('cad_build_chain_evidence', 'chain', {**chain['parameters'], 'evidence_paths': sources}),
            ('cad_build_target_graph', 'target', {'chain_path': log.path('chain'), 'relation_paths': relations}),
            ('cad_build_rigid_candidates', 'rigid', {'target_graph_path': log.path('target'), 'include_contact_hypotheses': False}),
            ('cad_draft_joints', 'draft', {'rigid_candidates_path': log.path('rigid'), 'max_target_pairs': 2000}),
            ('cad_check_joint_draft', 'check', {'joint_draft_path': log.path('draft'), 'max_findings': 2000}),
            ('cad_index_evidence', 'index', {'draft_check_path': log.path('check'), 'execution_path': eb['path'], 'max_contexts': 2000}),
            ('cad_analyze_constraints', 'constraints', {'target_graph_path': log.path('target'),
                'evidence_index_path': log.path('index'), 'distance_tolerance_mm': distance_tolerance_mm,
                'angle_tolerance_deg': angle_tolerance_deg})]
        for tool, name, args in pipeline:
            log.run(tool, {**{k: v for k, v in args.items() if v is not None}, 'output_path': log.path(name)})
            outputs[name] = binding(root, log.path(name))
        recheck(root, inputs)
    except Exception as exc:
        error = failure(exc)['errors'][0]
        outputs = {}
    report = {'chain_baseline_schema_version': 1, 'algorithm_version': 1,
        'execution_source': eb, 'input_files': inputs,
        'parameters': {'distance_tolerance_mm': distance_tolerance_mm, 'angle_tolerance_deg': angle_tolerance_deg},
        'baseline_created': error is None, 'outputs': outputs, 'pipeline_error': error,
        'applied_capture_ids': used if not error else [],
        'unapplied_capture_ids': [r['task_id'] for r in execution['records']
            if tasks[r['task_id']]['phase'] == 'capture' and (error or r['task_id'] not in used)],
        'rounds_completed': 1 if not error else None, 'solidworks_modified': False,
        'mechanically_verified': False, 'requires_human_review': False,
        'limitations': ['Initialization creates the first compatible relation/connection bases; it never replaces existing bases or history.',
            'Only complete captures from passed guards are applied. All attempts and supplemental captures remain in the observation index.',
            'At least two cylinder envelopes, even complete empty scans, are required by the current relation pipeline. Otherwise root mates remain indexed context.',
            'No template, CAD call, invented face, contact, physical joint or motion assertion is introduced.',
            'Source hashes/guards do not certify atomic geometry. Failed intermediate files are diagnostic only.']}
    rb = log.finish(report)
    return success({k: report[k] for k in ('baseline_created', 'outputs', 'pipeline_error',
        'applied_capture_ids', 'unapplied_capture_ids', 'rounds_completed', 'mechanically_verified')}
        | {'baseline_source': rb, 'detail_saved': True}, [error] if error else [])
