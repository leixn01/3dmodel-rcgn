"""Replay file boundaries for independent rigid grouping and joint drafting tools."""
from cadkin.errors import success
from cadkin.tools.files import json_path, read_json
from cadkin.tools.chain_sources import check_fields, require
from cadkin.tools.matching import replay_target, recheck, load_references
from cadkin.tools.proximity import write_result
from cadkin.rigid.groups import candidate_partitions
from cadkin.rigid.joints import draft_partitions


def build_rigid(root, target_graph_path, **parameters):
    target, binding = replay_target(root, target_graph_path)
    data = candidate_partitions(target, **parameters)
    data['parameters']['target_graph_path'] = binding['path']
    data['target_source'] = binding
    data['input_files'] = target['input_files'] + [binding]
    recheck(root, data['input_files'])
    return data, target


def rigid_candidates(root, target_graph_path, output_path, **parameters):
    output = json_path(root, output_path, output=True)
    data, _ = build_rigid(root, target_graph_path, **parameters)
    write_result(output, data)
    errors = list(data['source_errors'])
    if data['output_truncated'] or data['omitted_groups']:
        errors.append({'code': 'RIGID_CANDIDATE_LIMIT', 'message': 'Some generated partitions/groups were omitted; inspect limits and conflicts.'})
    return success({'output_path': str(output), 'coverage': data['coverage'], 'output_truncated': data['output_truncated'],
                    'requires_human_review': False, 'rigidity_confirmed': False, 'solidworks_modified': False}, errors)


def build_draft(root, rigid_candidates_path, template_ids=None, include_heldout=False, **parameters):
    from cadkin.templates.catalog import find_template
    path = json_path(root, rigid_candidates_path)
    original, digest = read_json(path)
    require(isinstance(original, dict) and original.get('rigid_candidates_schema_version') == 1 and
            original.get('algorithm_version') == 1 and isinstance(original.get('parameters'), dict) and
            set(original['parameters']) == {'target_graph_path', 'max_group_size', 'max_partitions', 'include_contact_hypotheses'},
            'Use original cad_build_rigid_candidates output.', 'INVALID_RIGID_SOURCE')
    rigid, target = build_rigid(root, **original['parameters'])
    check_fields(original, rigid)
    references, bindings = load_references(template_ids, include_heldout)
    data = draft_partitions(target, rigid, references, **parameters)
    data.update(rigid_source={'path': str(path), 'sha256': digest}, target_source=rigid['target_source'],
                template_sources=bindings, heldout_exposed=any(b['split'] == 'heldout' for b in bindings))
    recheck(root, rigid['input_files'] + [data['rigid_source']])
    for b in bindings: find_template(b['id'])
    return data, rigid, target


def replay_draft(root, joint_draft_path):
    path = json_path(root, joint_draft_path)
    original, digest = read_json(path)
    keys = {'pattern_size','max_candidates','max_states','beam_width','angle_tolerance_deg',
            'axis_distance_tolerance_mm','axis_angle_tolerance_deg'}
    require(isinstance(original, dict) and original.get('joint_draft_schema_version') == 1 and
            original.get('algorithm_version') == 1 and isinstance(original.get('parameters'), dict) and
            set(original['parameters']) == keys and isinstance(original.get('rigid_source'), dict) and
            isinstance(original.get('template_sources'), list) and 1 <= len(original['template_sources']) <= 8 and
            all(isinstance(b, dict) and isinstance(b.get('id'), str) for b in original['template_sources']) and
            type(original.get('heldout_exposed')) is bool,
            'Use an original cad_draft_joints result.', 'INVALID_DRAFT_SOURCE')
    bound = original['rigid_source']
    require(read_json(json_path(root, bound.get('path', '')))[1] == bound.get('sha256'),
            'Rigid source changed.', 'EVIDENCE_MISMATCH')
    data, rigid, target = build_draft(root, bound['path'],
        template_ids=[b['id'] for b in original['template_sources']],
        include_heldout=original['heldout_exposed'], **original['parameters'])
    check_fields(original, data)
    binding = {'path': str(path), 'sha256': digest}
    recheck(root, rigid['input_files'] + [data['rigid_source'], binding])
    return data, rigid, target, binding


def joint_drafts(root, rigid_candidates_path, output_path, template_ids=None, include_heldout=False, **parameters):
    output = json_path(root, output_path, output=True)
    data, rigid, target = build_draft(root, rigid_candidates_path, template_ids, include_heldout, **parameters)
    write_result(output, data)
    errors = []
    if not target['complete']: errors.append({'code': 'SOURCE_INCOMPLETE', 'message': 'Original source errors remain unresolved.'})
    if rigid['output_truncated'] or rigid['omitted_groups']:
        errors.append({'code': 'RIGID_CANDIDATE_LIMIT', 'message': 'Grouping alternatives were limited; inspect original rigid candidates.'})
    if not data['search_exhaustive_within_retained_partitions']:
        errors.append({'code': 'MATCH_SEARCH_LIMIT', 'message': 'Search budget/beam omitted mappings; see per-partition coverage.'})
    if not data['summary']['returned_candidates']:
        errors.append({'code': 'NO_SUPPORTED_MATCH', 'message': 'No supported candidate in searched windows; not proof of absent mechanisms.'})
    return success({'output_path': str(output), **data}, errors)
