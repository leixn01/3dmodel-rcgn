"""Replay-bound constraint gap plans using the existing execution and observation lineage."""
from cadkin.tools.files import json_path, read_json, replay_reads
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.constraint_analysis import replay_analysis
from cadkin.tools.comparison import replay_check
from cadkin.tools.observation_index import replay_index, unique_bindings
from cadkin.tools.matching import recheck
from cadkin.followup.constraint_planning import plan_constraint_tasks
from cadkin.followup.planning import READ_TOOLS


@replay_reads
def build_constraint_plan(root, draft_check_path, constraint_analysis_path, output_path, max_tasks=20,
                          evidence_index_path=None, check_destinations=True):
    from jsonschema import Draft202012Validator
    from cadkin.tools.solidworks import CATALOG
    output = json_path(root, output_path, output=check_destinations)
    check, target, draft, _, cb = replay_check(root, draft_check_path)
    analysis, ab = replay_analysis(root, constraint_analysis_path)
    require(analysis['target_source'] == draft['target_source'], 'Constraint analysis and draft check use different target graphs.', 'EVIDENCE_MISMATCH')
    inherited = analysis.get('evidence_index_source')
    if inherited and evidence_index_path is None: evidence_index_path = inherited['path']
    index, ib = (None, None) if evidence_index_path is None else replay_index(root, evidence_index_path)
    if index is not None:
        require(index['check_source'] == cb, 'Index belongs to another draft check; rebuild associations.', 'EVIDENCE_MISMATCH')
        if inherited: require(ib == inherited, 'Cannot replace the constraint report lineage with another index.', 'EVIDENCE_MISMATCH')
    attempts = []
    for bound in analysis['mate_sources']:
        raw, digest = read_json(json_path(root, bound['path']))
        require(digest == bound['sha256'], 'Mate source changed.', 'EVIDENCE_MISMATCH')
        if raw['data'].get('parameters', {}).get('include_reference_geometry') is True or raw['data'].get('reference_geometry_capture'):
            attempts.append(bound)
    data = plan_constraint_tasks(target, check, analysis, index, attempts, output.parent/(output.stem+'-captures'), max_tasks)
    data.update(parameters={'draft_check_path': cb['path'], 'constraint_analysis_path': ab['path'], 'max_tasks': max_tasks},
        check_source=cb, constraint_analysis_source=ab,
        input_files=check['input_files'] + analysis['input_files'] + [cb, ab])
    if ib:
        data['parameters']['evidence_index_path'] = ib['path']
        data['evidence_index_source'] = ib
        data['input_files'] += index['input_files'] + [ib]
        data['heldout_exposed'] |= index['heldout_exposed']
    data['input_files'] = unique_bindings(root, data['input_files'])
    for task in data['tasks']:
        require(task['tool'] in READ_TOOLS and CATALOG[task['tool']]['annotations']['readOnlyHint'] and
            Draft202012Validator(CATALOG[task['tool']]['inputSchema']).is_valid(task['arguments']), 'Invalid constraint task.', 'INVALID_TASK_PLAN')
        json_path(root, task['save_envelope_path'], output=check_destinations)
    recheck(root, data['input_files'])
    return data, check, target


def replay_constraint_plan(root, path, original, digest):
    keys = {'draft_check_path', 'constraint_analysis_path', 'max_tasks'}
    params = original.get('parameters')
    require(original.get('evidence_task_plan_schema_version') == 1 and original.get('plan_kind') == 'target_constraint_gaps' and
        isinstance(params, dict) and set(params) in (keys, keys | {'evidence_index_path'}),
        'Use the original constraint evidence plan.', 'INVALID_TASK_PLAN')
    data, check, target = build_constraint_plan(root, output_path=str(path), check_destinations=False, **params)
    check_fields(original, data)
    return data, check, target, {'path': str(path), 'sha256': digest}
