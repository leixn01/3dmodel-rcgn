"""Bounded first-chain CLI orchestration through the existing public tool service."""
from pathlib import Path

from cadkin.errors import ToolFailure, failure, success
from cadkin.followup.execution import document_matches
from cadkin.tools.chain_sources import require
from cadkin.tools.files import json_path, read_json
from cadkin.tools.inventory import spatial_inventory
from cadkin.tools.matching import recheck
from cadkin.tools.proximity import write_result
from cadkin.tools.spatial import collect_spatial
from cadkin.tools.workflow_log import WorkflowLog, binding


CONFIG_SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'expected_document_token': {'type': 'string', 'pattern': '^[0-9a-f]{24}$'},
    'occurrence_paths': {'type': 'array', 'minItems': 2, 'maxItems': 20, 'uniqueItems': True,
                         'items': {'type': 'string', 'minLength': 1}},
    'chain_name': {'type': 'string', 'minLength': 1, 'maxLength': 100},
    'reference_occurrence_path': {'type': 'string', 'minLength': 1},
    'characteristic_length_mm': {'type': 'number', 'minimum': .001, 'maximum': 1000000},
    'distance_tolerance_mm': {'type': 'number', 'exclusiveMinimum': 0},
    'angle_tolerance_deg': {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 5},
    'capture_profile': {'type': 'string', 'enum': ['geometry_and_mates', 'root_mates']},
    'inventory_path': {'type': 'string', 'minLength': 1}},
    'required': ['expected_document_token', 'occurrence_paths', 'chain_name',
        'reference_occurrence_path', 'characteristic_length_mm', 'distance_tolerance_mm', 'angle_tolerance_deg']}


def run_chain_session(service, config_path, output_path):
    """Run at most an initial guarded round and one enhanced-mate follow-up. No retries."""
    from jsonschema import Draft202012Validator
    root = service.root
    config, digest = read_json(json_path(root, config_path))
    invalid = next(Draft202012Validator(CONFIG_SCHEMA).iter_errors(config), None)
    require(invalid is None, invalid.message if invalid else '', 'INVALID_ARGUMENTS')
    require(config['reference_occurrence_path'] in config['occurrence_paths'],
            'Reference must belong to the explicit scope.', 'INVALID_CHAIN_SCOPE')
    cb = {'path': str(json_path(root, config_path)), 'sha256': digest}
    if not service.operation_gate.acquire(blocking=False):
        raise ToolFailure('BUSY', 'Another operation is active; no session was started.')
    try:
        return _run(service, config, cb, output_path)
    finally:
        service.operation_gate.release()


def _run(service, config, config_binding, output_path):
    root = service.root
    log = WorkflowLog(root, output_path, service.call)
    current, batches, stop, error = {}, [], 'not_started', None
    rounds, inventory_binding = 0, None
    class LoggedService:
        def call(self, tool, arguments=None):
            log.run(tool, arguments or {})
            return read_json(Path(log.steps[-1]['response_source']['path']))[0]

    def execute(plan_path, label):
        previous = None
        # Each batch executes >=1 previously unprocessed task; the plan has <=200 tasks.
        plan = read_json(json_path(root, plan_path))[0]
        require(plan['summary']['planned_capture_tasks'] > 0, 'No supported capture to execute.', 'NO_CAPTURE_TASKS')
        for number in range(len(plan['tasks'])):
            args = {'plan_path': plan_path, 'output_path': log.path(f'{label}-batch-{number+1:03d}'),
                    'max_steps': 20, 'time_budget_seconds': 30}
            if previous: args['previous_execution_path'] = previous['path']
            data = log.run('sw_execute_evidence_batch', args)
            batches.append(data['batch_report_source'])
            previous = data['execution_source']
            current['execution'] = previous
            current['plan'] = binding(root, plan_path)
            if data['execution_complete']:
                require(data['guards_passed'], 'Capture guards failed; retain diagnostic receipts without reintegration.', 'EXECUTION_GUARDS_FAILED')
                return previous['path']
            require(data['continuation']['action'] == 'continue' and previous is not None,
                    'Batch stopped; do not retry or start a new baseline.', 'EXECUTION_HALTED')
        raise ToolFailure('EXECUTION_HALTED', 'No execution completion within the original task count.')

    try:
        active = log.run('sw_active_document', {})
        require(active['document_type'] == 'assembly' and active['document_token'] == config['expected_document_token'],
                'Active assembly differs from the selected scope. Refresh identity before a new run.', 'DOCUMENT_CHANGED')
        if config.get('inventory_path'):
            inventory_path = str(json_path(root, config['inventory_path']))
            inventory = read_json(Path(inventory_path))[0]
        else:
            inventory_path = log.path('inventory')
            inventory = collect_spatial(LoggedService(), include_bounding_boxes=False)
            write_result(Path(inventory_path), inventory)
        spatial, nodes = spatial_inventory(inventory)
        require(document_matches(spatial['document'], active), 'Inventory belongs to another document/configuration.', 'DOCUMENT_CHANGED')
        parents = {n.get('parent_occurrence_path') for n in nodes.values()}
        require(all(p in nodes and p not in parents for p in config['occurrence_paths']),
                'Scope must contain exact leaf occurrence paths from the current assembly.', 'INVALID_CHAIN_SCOPE')
        inventory_binding = binding(root, inventory_path)
        current['inventory'] = inventory_binding
        pipeline = [
            ('cad_build_chain_evidence', 'initial-chain', {'inventory_path': inventory_path,
                'occurrence_paths': config['occurrence_paths'], 'chain_name': config['chain_name']}),
            ('cad_build_target_graph', 'initial-target', {'chain_path': log.path('initial-chain')}),
            ('cad_build_rigid_candidates', 'initial-rigid', {'target_graph_path': log.path('initial-target'), 'include_contact_hypotheses': False}),
            ('cad_draft_joints', 'initial-draft', {'rigid_candidates_path': log.path('initial-rigid'), 'max_target_pairs': 2000}),
            ('cad_check_joint_draft', 'initial-check', {'joint_draft_path': log.path('initial-draft'), 'max_findings': 2000}),
            ('cad_plan_evidence_tasks', 'initial-plan', {'draft_check_path': log.path('initial-check'),
                # Reserve exactly enough for root mates, N cylinders and all guards.
                # Existing planner priorities choose the actual tasks; no task is edited.
                'max_tasks': 3 * len(config['occurrence_paths']) + 3})]
        if config.get('capture_profile') == 'root_mates':
            pipeline[-1][2].update(initial_capture_profile='root_mates', max_tasks=2 * len(config['occurrence_paths']) + 3)
        for tool, name, args in pipeline:
            log.run(tool, {**args, 'output_path': log.path(name)})
        receipt = execute(log.path('initial-plan'), 'initial')
        baseline = log.run('cad_create_chain_baseline', {'execution_path': receipt,
            'output_path': log.path('baseline'), 'distance_tolerance_mm': config['distance_tolerance_mm'],
            'angle_tolerance_deg': config['angle_tolerance_deg']})
        current['baseline'] = baseline['baseline_source']
        require(baseline['baseline_created'], 'Baseline pipeline failed; intermediate files are diagnostic.', 'BASELINE_FAILED')
        current.update(baseline['outputs'])
        rounds = baseline['rounds_completed']
        # Ask only for supported constraint gaps, preserving the newly created index.
        for attempt in range(2):
            path = log.path(f'constraint-plan-{attempt+1}')
            plan = log.run('cad_plan_evidence_tasks', {'draft_check_path': current['check']['path'],
                'constraint_analysis_path': current['constraints']['path'], 'output_path': path,
                'max_tasks': 2 * len(config['occurrence_paths']) + 3})
            current['plan'] = binding(root, path)
            if plan['continuation']['action'] == 'stop':
                stop = plan['continuation']['reason']
                break
            if attempt:
                stop = 'SESSION_CAPTURE_LIMIT'
                break
            receipt = execute(path, 'enhanced')
            updated = log.run('cad_reintegrate_evidence', {'execution_path': receipt,
                'output_path': log.path('enhanced-reintegration')})
            require(updated['recomputation_complete'] and updated.get('after_constraint_analysis_source'),
                    'Follow-up pipeline failed; do not accept intermediate results.', 'REINTEGRATION_FAILED')
            current.update(check=updated['after_check_source'], index=updated['after_evidence_index_source'],
                           constraints=updated['after_constraint_analysis_source'])
            names = {'cad_build_chain_evidence': 'chain', 'cad_build_target_graph': 'target',
                     'cad_build_rigid_candidates': 'rigid', 'cad_draft_joints': 'draft'}
            for step in updated['steps']:
                if step['tool'] in names:
                    current[names[step['tool']]] = step['output_source']
            analysis = read_json(Path(current['constraints']['path']))[0]
            current['target'] = analysis['target_source']
            rounds = analysis['rounds_completed']
        solution = log.run('cad_solve_chain_constraints', {'constraint_analysis_path': current['constraints']['path'],
            'reference_occurrence_path': config['reference_occurrence_path'],
            'characteristic_length_mm': config['characteristic_length_mm'], 'output_path': log.path('chain-solution')})
        current['solution'] = solution['solution_source']
        recheck(root, [config_binding, inventory_binding])
    except Exception as exc:
        error = failure(exc)['errors'][0]
        stop = error['code']
    # Read saved timing reports without repeating CAD calls or replaying whole histories for presentation.
    tool_timings = []
    try:
        for b in batches:
            report, digest = read_json(Path(b['path']))
            require(digest == b['sha256'], 'Batch report changed.', 'EVIDENCE_MISMATCH')
            tool_timings.extend(report['performance']['tool_timings'])
    except Exception as exc:
        error = failure(exc)['errors'][0]
        stop = error['code']
    evidence_summary, findings_summary = None, None
    if error is None:
        evidence_summary = read_json(Path(current['index']['path']))[0]['summary']
        findings_summary = read_json(Path(current['check']['path']))[0]['summary']
    result = {'chain_session_schema_version': 1, 'algorithm_version': 1, 'config_source': config_binding,
        'workflow_complete': error is None, 'stop_reason': stop, 'pipeline_error': error,
        'capture_profile': config.get('capture_profile', 'geometry_and_mates'),
        'handoffs': current, 'rounds_completed': rounds, 'max_rounds': 4,
        'batch_sources': batches, 'cad_capture_tool_timings': tool_timings,
        'evidence_summary': evidence_summary, 'remaining_findings_summary': findings_summary,
        'requires_human_review': False, 'solidworks_modified': False, 'mechanically_verified': False,
        'target_degrees_of_freedom': None, 'finite_motion_verified': False,
        'limitations': ['First-run workflow only. Reuse its latest check/analysis/index for follow-up; do not restart to bypass capture history.',
            'Explicit scope is not automatically recognized. Root mates exclude subassembly-internal constraints.',
            'At most initial plus enhanced-mate rounds. root_mates captures enhancement in the first round; no failure retry or invented constraint.',
            'Inventory omits slow bounding boxes. Each capture retains the existing document/pose guards and all raw receipts.',
            'Timing excludes agent thinking/network. Stage totals include nested batches; do not add them again to CAD timings.',
            'An error preserves handoffs for diagnosis/continuation, not a completed analysis. No assembly edits, motion or disassembly are executed.']}
    rb = log.finish(result)
    compact = {k: result[k] for k in ('workflow_complete', 'stop_reason', 'pipeline_error', 'handoffs',
        'rounds_completed', 'max_rounds', 'mechanically_verified', 'target_degrees_of_freedom', 'finite_motion_verified',
        'evidence_summary', 'remaining_findings_summary', 'capture_profile')}
    compact.update(report_source=rb, detail_saved=True, performance=result['performance'])
    if error:
        return {'schema_version': 1, 'status': 'error', 'data': compact, 'errors': [error]}
    compact['solution_summary'] = {k: solution[k] for k in ('coverage', 'snapshots')}
    return success(compact)
