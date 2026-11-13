"""Replay and validate draft-check and evidence-plan file boundaries."""
from cadkin.errors import success
from cadkin.tools.files import json_path, read_json, replay_reads
from cadkin.tools.proximity import write_result
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.matching import recheck
from cadkin.tools.rigid import replay_draft
from cadkin.followup.checks import check_draft
from cadkin.followup.planning import plan_tasks, READ_TOOLS
from cadkin.tools.replay_guard import bounded_replay


@replay_reads
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


@replay_reads
def build_plan(root, draft_check_path, output_path, max_tasks=20, check_destinations=True, evidence_index_path=None,
               constraint_analysis_path=None, initial_capture_profile=None, geometry_analysis_path=None):
    require(sum(x is not None for x in (initial_capture_profile, constraint_analysis_path, geometry_analysis_path)) <= 1,
            'Choose only one evidence planning profile.', 'INVALID_ARGUMENTS')
    require(initial_capture_profile in (None, 'root_mates') and not (initial_capture_profile and
            (evidence_index_path is not None or constraint_analysis_path is not None)),
            'The initial root-mate profile cannot replace an existing index or constraint history.', 'INVALID_ARGUMENTS')
    if geometry_analysis_path is not None:
        from cadkin.tools.geometry_planning import build_geometry_plan
        return build_geometry_plan(root, draft_check_path, geometry_analysis_path, output_path,
                                   max_tasks, evidence_index_path, check_destinations)
    if constraint_analysis_path is not None:
        from cadkin.tools.constraint_planning import build_constraint_plan
        return build_constraint_plan(root, draft_check_path, constraint_analysis_path, output_path,
                                     max_tasks, evidence_index_path, check_destinations)
    from jsonschema import Draft202012Validator
    from cadkin.tools.solidworks import CATALOG
    output = json_path(root, output_path, output=check_destinations)
    source = json_path(root, draft_check_path)
    original, digest = read_json(source)
    require(isinstance(original, dict) and original.get('draft_check_schema_version') == 1 and
            original.get('algorithm_version') in (1, 2) and isinstance(original.get('parameters'), dict) and
            set(original['parameters']) == {'joint_draft_path', 'max_findings'},
            'Use the raw cad_check_joint_draft result.', 'INVALID_DRAFT_CHECK')
    check, target = build_check(root, **original['parameters'])
    check_fields(original, check)
    capture_dir = output.parent/(output.stem+'-captures')
    facts = source_facts(root, target)
    indexed = None
    if evidence_index_path is not None:
        from cadkin.tools.observation_index import replay_index
        from cadkin.followup.observations import reuse_facts
        indexed, index_binding = replay_index(root, evidence_index_path)
        require(indexed['check_source'] == {'path': str(source), 'sha256': digest},
                'Index belongs to a different draft check; rebuild its associations.', 'EVIDENCE_MISMATCH')
        extra = reuse_facts(indexed)
        for family in ('constraints', 'faces', 'cylinders'):
            for key, values in extra[family].items(): facts[family].setdefault(key, []).extend(values)
        facts['root_mates'].extend(extra['root_mates'])
        facts.update({k: extra[k] for k in ('distance', 'attempted_requests', 'rounds_completed')}, _indexed=True)
    if initial_capture_profile == 'root_mates':
        require(not target['source_coverage'] and not target['relation_sources'] and 2 <= len(target['nodes']) <= 20,
                'Initial profile requires an empty-evidence 2–20-component chain.', 'BASELINE_ALREADY_EXISTS')
        from cadkin.followup.planning import plan_initial_root_mates
        data = plan_initial_root_mates(target, check, capture_dir, max_tasks)
    else:
        data = plan_tasks(target, check, facts, capture_dir, max_tasks)
    # Validate every concrete call against the production catalog, not a parallel copy of its schema.
    for task in data['tasks']:
        require(task['tool'] in READ_TOOLS and CATALOG[task['tool']]['annotations']['readOnlyHint'],
                'Planner emitted a non-read-only tool.', 'INVALID_TASK_PLAN')
        require(Draft202012Validator(CATALOG[task['tool']]['inputSchema']).is_valid(task['arguments']),
                'Planner emitted invalid tool arguments.', 'INVALID_TASK_PLAN')
        json_path(root, task['save_envelope_path'], output=check_destinations)
    data['parameters']['draft_check_path'] = str(source)
    data['check_source'] = {'path': str(source), 'sha256': digest}
    data['input_files'] = check['input_files'] + [data['check_source']]
    if indexed is not None:
        from cadkin.tools.observation_index import unique_bindings
        data['parameters']['evidence_index_path'] = index_binding['path']
        data['evidence_index_source'] = index_binding
        data['input_files'] = unique_bindings(root, data['input_files'] + indexed['input_files'] + [index_binding])
        data['heldout_exposed'] = data['heldout_exposed'] or indexed['heldout_exposed']
    recheck(root, data['input_files'])
    return data, check, target


@replay_reads
@bounded_replay
def replay_plan(root, plan_path):
    path = json_path(root, plan_path)
    original, digest = read_json(path)
    version = original.get('algorithm_version') if isinstance(original, dict) else None
    if version == 6:
        from cadkin.tools.geometry_planning import replay_geometry_plan
        return replay_geometry_plan(root, path, original, digest)
    if version == 4:
        from cadkin.tools.constraint_planning import replay_constraint_plan
        return replay_constraint_plan(root, path, original, digest)
    if version == 3:
        from cadkin.tools.face_planning import replay_face_plan
        return replay_face_plan(root, path, original, digest)
    keys = {'draft_check_path', 'max_tasks'} | ({'evidence_index_path'} if version == 2 else
           {'initial_capture_profile'} if version == 5 else set())
    require(isinstance(original, dict) and original.get('evidence_task_plan_schema_version') == 1 and
            version in (1, 2, 5) and isinstance(original.get('parameters'), dict) and set(original['parameters']) == keys,
            'Use the original evidence task plan.', 'INVALID_TASK_PLAN')
    data, check, target = build_plan(root, output_path=str(path), check_destinations=False, **original['parameters'])
    check_fields(original, data)
    return data, check, target, {'path': str(path), 'sha256': digest}


def evidence_task_plan(root, draft_check_path, output_path, max_tasks=20, evidence_index_path=None,
                       constraint_analysis_path=None, initial_capture_profile=None, geometry_analysis_path=None):
    output = json_path(root, output_path, output=True)
    data, check, _ = build_plan(root, draft_check_path, output_path, max_tasks, evidence_index_path=evidence_index_path,
                              constraint_analysis_path=constraint_analysis_path, initial_capture_profile=initial_capture_profile,
                              geometry_analysis_path=geometry_analysis_path)
    write_result(output, data)
    errors = []
    if data['output_truncated']:
        errors.append({'code': 'EVIDENCE_PLAN_LIMIT', 'message': 'Some tasks/findings were omitted; retain deferred work and check coverage.'})
    if not check['structural_checks_passed']:
        errors.append({'code': 'INVALID_DRAFT_STRUCTURE', 'message': 'Regenerate invalid derivations before planning capture.'})
    if data.get('blocked_requests'):
        errors.append({'code': 'AUTOMATIC_CAPTURE_BLOCKED', 'message': 'Prior attempts or round budget block repeated scans; retain remaining uncertainty.'})
    return success({'output_path': str(output), **data}, errors)
