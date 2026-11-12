"""Replay guarded execution history into an offline, source-bound observation index."""
from copy import deepcopy
from pathlib import Path

from cadkin.errors import success
from cadkin.tools.files import json_path, read_json
from cadkin.tools.proximity import write_result
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.matching import recheck
from cadkin.tools.comparison import replay_check
from cadkin.tools.execution import replay_execution
from cadkin.tools.replay_guard import bounded_replay
from cadkin.followup import stable_id
from cadkin.followup.execution import document_matches
from cadkin.followup.observations import FAMILIES, MAX_ROUNDS, describe_capture, associate


def same_context(left, right):
    fields = ('id', 'parent_id', 'file_path', 'configuration', 'to_root_column_vectors_m', 'eligible')
    def nodes(target):
        return {n['id']: {k: n[k] for k in fields} for n in target['nodes']}
    return document_matches(left['document'], right['document']) and nodes(left) == nodes(right)


def unique_bindings(root, bindings):
    result = {}
    for binding in bindings:
        path = str(json_path(root, binding['path']))
        normalized = {'path': path, 'sha256': binding['sha256']}
        require(path not in result or result[path] == normalized, 'Mixed source versions.', 'EVIDENCE_MISMATCH')
        result[path] = normalized
    require(len(result) <= 512 and sum(Path(p).stat().st_size for p in result) <= 128*1024*1024,
            'Observation provenance exceeds 512 files or 128 MiB.', 'OBSERVATION_SOURCE_LIMIT')
    return [result[k] for k in sorted(result)]


def build_index(root, draft_check_path, execution_path, max_contexts=200):
    require(type(max_contexts) is int and 1 <= max_contexts <= 2000,
            'max_contexts must be 1–2000.', 'INVALID_ARGUMENTS')
    check, target, draft, _, cb = replay_check(root, draft_check_path)
    execution, plan, _, previous_target, eb = replay_execution(root, execution_path)
    require(execution['execution_complete'], 'Finish the bounded execution first.', 'EXECUTION_NOT_COMPLETE')
    require(execution['guards_passed'], 'Failed guards prohibit observation reuse.', 'EXECUTION_GUARDS_FAILED')
    require(same_context(target, previous_target), 'Document, occurrence scope or poses changed.', 'EVIDENCE_MISMATCH')
    observations, history, sources = [], [], []
    previous = plan.get('evidence_index_source')
    if previous:
        # replay_execution -> replay_plan already reconstructed this index recursively.
        old, digest = read_json(json_path(root, previous['path']))
        require(digest == previous['sha256'], 'Prior index changed.', 'EVIDENCE_MISMATCH')
        observations = deepcopy(old['observations']); history = list(old['execution_sources'])
        sources.extend(old['input_files'] + [previous])
    require(all(b['sha256'] != eb['sha256'] for b in history), 'Execution is already indexed.', 'DUPLICATE_EXECUTION')
    history.append(eb)
    require(len(history) <= MAX_ROUNDS, 'Automatic follow-up is limited to four guarded rounds.', 'OBSERVATION_ROUND_LIMIT')
    tasks = {t['id']: t for t in plan['tasks']}
    for record in execution['records']:
        task = tasks[record['task_id']]
        if record['envelope_source']: sources.append(record['envelope_source'])
        if task['phase'] != 'capture' or record['envelope_source'] is None: continue
        usable = record['task_id'] in execution['eligible_capture_ids']
        raw, digest = read_json(json_path(root, record['envelope_source']['path']))
        require(digest == record['envelope_source']['sha256'], 'Observation changed.', 'EVIDENCE_MISMATCH')
        observations.append({'id': stable_id('observation-', [eb, task['id']]), 'execution_source': eb,
            'task_id': task['id'], 'tool': task['tool'], 'family': FAMILIES[task['tool']],
            'arguments': task['arguments'], 'occurrence_paths': sorted(n['id'] for n in task['expected_context']),
            'source': record['envelope_source'], 'state': record['state'], 'codes': record['codes'],
            'usable': usable, 'details': describe_capture(task['tool'], raw['data']) if usable else None,
            'reason': 'COMPLETE_GUARDED_OBSERVATION' if usable else 'RETAINED_ATTEMPT_NO_AUTOMATIC_RETRY'})
    sources.extend(check['input_files'] + plan['input_files'] + [cb, eb, execution['plan_source']])
    if execution['previous_execution_source']: sources.append(execution['previous_execution_source'])
    sources = unique_bindings(root, sources)
    contexts = associate(observations, target, check, draft, max_contexts)
    data = {'evidence_index_schema_version': 1, 'algorithm_version': 1,
        'parameters': {'draft_check_path': cb['path'], 'execution_path': eb['path'], 'max_contexts': max_contexts},
        'document': target['document'], 'check_source': cb, 'execution_sources': history,
        'previous_index_source': previous, 'rounds_completed': len(history), 'max_rounds': MAX_ROUNDS,
        'observations': observations, **contexts, 'input_files': sources,
        'remaining_findings_summary': check['summary'], 'check_output_truncated': check['output_truncated'],
        'summary': {'observations': len(observations), 'reusable': sum(o['usable'] for o in observations),
                    'retained_unsuccessful_attempts': sum(not o['usable'] for o in observations),
                    'joint_contexts_returned': len(contexts['joint_contexts'])},
        'heldout_exposed': check['heldout_exposed'] or plan.get('heldout_exposed', False),
        'requires_human_review': False, 'solidworks_modified': False, 'mechanically_verified': False,
        'limitations': ['An index associates saved observations with current occurrences, findings and retained joint hypotheses; it does not rerank or accept joints.',
            'Component mate reference names have no verified root identity or activity; never infer a component pair from those names.',
            'Face locators address one hashed catalog. Two endpoint catalogs do not select mating faces or seeds; persistent references need live verification.',
            'Fixed state describes this configured assembly, not an intrinsic mechanical joint or solved motion.',
            'Complete empty observations are reusable. Failed/partial attempts remain diagnostic and block identical automatic scans; budgets are not automatically raised.',
            'Reuse requires the same document and full occurrence scope/poses. Hashes and pre/post checks cannot certify an atomic geometry snapshot.',
            'Only this explicit execution lineage is known; files elsewhere in outputs are never scanned. Retain and pass the latest index.']}
    recheck(root, sources)
    return data


@bounded_replay
def replay_index(root, name):
    path = json_path(root, name); raw, digest = read_json(path)
    require(isinstance(raw, dict) and raw.get('evidence_index_schema_version') == 1 and raw.get('algorithm_version') == 1 and
            isinstance(raw.get('parameters'), dict) and set(raw['parameters']) == {'draft_check_path', 'execution_path', 'max_contexts'},
            'Use the original evidence index.', 'INVALID_EVIDENCE_INDEX')
    data = build_index(root, **raw['parameters']); check_fields(raw, data)
    return data, {'path': str(path), 'sha256': digest}


def index_evidence(root, draft_check_path, execution_path, output_path, max_contexts=200):
    output = json_path(root, output_path, output=True)
    data = build_index(root, draft_check_path, execution_path, max_contexts)
    write_result(output, data)
    errors = []
    if data['summary']['retained_unsuccessful_attempts']:
        errors.append({'code': 'OBSERVATIONS_NOT_REUSABLE', 'message': 'Failed/partial attempts are diagnostic; no automatic retry.'})
    if data['joint_contexts_truncated'] or data['check_output_truncated']:
        errors.append({'code': 'ASSOCIATION_CONTEXT_LIMIT', 'message': 'Only returned findings/joint contexts are associated; omitted hypotheses remain unknown.'})
    return success({'output_path': str(output), **data}, errors)
