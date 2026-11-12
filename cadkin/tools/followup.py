"""Replay and validate draft-check and evidence-plan file boundaries."""
from cadkin.errors import success
from cadkin.tools.files import json_path, read_json
from cadkin.tools.proximity import write_result
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.matching import recheck
from cadkin.tools.rigid import replay_draft
from cadkin.followup.checks import check_draft
from cadkin.followup.planning import plan_tasks, READ_TOOLS


def build_check(root, joint_draft_path, max_findings=200):
    draft, rigid, target, binding = replay_draft(root, joint_draft_path)
    data = check_draft(target, rigid, draft, max_findings)
    data['parameters']['joint_draft_path'] = binding['path']
    data['draft_source'] = binding
    data['input_files'] = rigid['input_files'] + [draft['rigid_source'], binding]
    recheck(root, data['input_files'])
    return data, target


def check_joint_draft(root, joint_draft_path, output_path, max_findings=200):
    output = json_path(root, output_path, output=True)
    data, _ = build_check(root, joint_draft_path, max_findings)
    write_result(output, data)
    errors = []
    if data['output_truncated']: errors.append({'code': 'DRAFT_CHECK_LIMIT', 'message': 'Some findings were omitted; retained scope is explicit.'})
    if data['summary']['severity_counts'].get('evidence_conflict') or not data['structural_checks_passed']:
        errors.append({'code': 'DRAFT_CONFLICTS', 'message': 'Inspect source/structural conflicts; no physical consistency verdict was made.'})
    if data['source_errors']: errors.append({'code': 'SOURCE_INCOMPLETE', 'message': 'Original source gaps remain.'})
    return success({'output_path': str(output), **data}, errors)


def source_facts(root, target):
    facts = {'cylinders': {}, 'faces': {}, 'constraints': {}, 'root_mates': []}
    paths = {n['id'] for n in target['nodes']}
    # These files have already been verified through the source graph; never scan arbitrary project JSON.
    for binding in target['input_files']:
        raw, digest = read_json(json_path(root, binding['path']))
        require(digest == binding['sha256'], 'Source changed during planning.', 'EVIDENCE_MISMATCH')
        data = raw.get('data') if isinstance(raw, dict) else None
        if (not isinstance(data, dict) or raw.get('status') != 'ok' or raw.get('errors') or
                data.get('complete') is not True or data.get('truncated')):
            continue
        if data.get('mate_inventory_schema_version') == 1:
            facts['root_mates'].append(binding)
        elif data.get('cylinder_schema_version') == 1 and data.get('occurrence_path') in paths:
            facts['cylinders'].setdefault(data['occurrence_path'], []).append(binding)
        elif data.get('face_inventory_schema_version') == 1 and data.get('target', {}).get('occurrence_path') in paths:
            facts['faces'].setdefault(data['target']['occurrence_path'], []).append(binding)
        elif data.get('constraint_schema_version') == 1 and data.get('occurrence_path') in paths:
            facts['constraints'].setdefault(data['occurrence_path'], []).append(binding)
    return facts


def evidence_task_plan(root, draft_check_path, output_path, max_tasks=20):
    from jsonschema import Draft202012Validator
    from cadkin.tools.solidworks import CATALOG
    output = json_path(root, output_path, output=True)
    source = json_path(root, draft_check_path)
    original, digest = read_json(source)
    require(isinstance(original, dict) and original.get('draft_check_schema_version') == 1 and
            original.get('algorithm_version') == 1 and isinstance(original.get('parameters'), dict) and
            set(original['parameters']) == {'joint_draft_path', 'max_findings'},
            'Use the raw cad_check_joint_draft result.', 'INVALID_DRAFT_CHECK')
    check, target = build_check(root, **original['parameters'])
    check_fields(original, check)
    capture_dir = output.parent/(output.stem+'-captures')
    data = plan_tasks(target, check, source_facts(root, target), capture_dir, max_tasks)
    # Validate every concrete call against the production catalog, not a parallel copy of its schema.
    for task in data['tasks']:
        require(task['tool'] in READ_TOOLS and CATALOG[task['tool']]['annotations']['readOnlyHint'],
                'Planner emitted a non-read-only tool.', 'INVALID_TASK_PLAN')
        require(Draft202012Validator(CATALOG[task['tool']]['inputSchema']).is_valid(task['arguments']),
                'Planner emitted invalid tool arguments.', 'INVALID_TASK_PLAN')
        json_path(root, task['save_envelope_path'], output=True)
    data['parameters']['draft_check_path'] = str(source)
    data['check_source'] = {'path': str(source), 'sha256': digest}
    data['input_files'] = check['input_files'] + [data['check_source']]
    recheck(root, data['input_files'])
    write_result(output, data)
    errors = []
    if data['output_truncated']:
        errors.append({'code': 'EVIDENCE_PLAN_LIMIT', 'message': 'Some tasks/findings were omitted; retain deferred work and check coverage.'})
    if not check['structural_checks_passed']:
        errors.append({'code': 'INVALID_DRAFT_STRUCTURE', 'message': 'Regenerate invalid derivations before planning capture.'})
    return success({'output_path': str(output), **data}, errors)
