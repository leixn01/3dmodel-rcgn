"""Replay-bound local constraint analysis, separate from capture and joint drafting."""
from cadkin.errors import success
from cadkin.tools.files import json_path, read_json, replay_reads
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.matching import replay_target, recheck
from cadkin.tools.proximity import write_result
from cadkin.constraints.analysis import analyze


@replay_reads
def build_analysis(root, target_graph_path, distance_tolerance_mm, angle_tolerance_deg, max_pairs=200):
    target, binding = replay_target(root, target_graph_path)
    snapshots, seen = [], set()
    for source in target['source_coverage']:
        if source['kind'] != 'connection': continue
        bound = source['coverage']['root_mate_source']
        raw, digest = read_json(json_path(root, bound['path']))
        require(digest == bound['sha256'], 'Mate source changed.', 'EVIDENCE_MISMATCH')
        if digest not in seen:
            snapshots.append((bound, raw)); seen.add(digest)
    data = analyze(target, snapshots, distance_tolerance_mm, angle_tolerance_deg, max_pairs)
    data['parameters']['target_graph_path'] = binding['path']
    data.update(target_source=binding, input_files=target['input_files']+[binding])
    recheck(root, data['input_files'])
    return data


@replay_reads
def replay_analysis(root, constraint_analysis_path):
    path = json_path(root, constraint_analysis_path); raw, digest = read_json(path)
    require(isinstance(raw, dict) and raw.get('constraint_analysis_schema_version') == 1 and raw.get('algorithm_version') == 1 and
        isinstance(raw.get('parameters'), dict) and set(raw['parameters']) == {'target_graph_path','distance_tolerance_mm','angle_tolerance_deg','max_pairs'},
        'Use original cad_analyze_constraints output.', 'INVALID_CONSTRAINT_SOURCE')
    data = build_analysis(root, **raw['parameters']); check_fields(raw, data)
    recheck(root, data['input_files']+[{'path': str(path), 'sha256': digest}])
    return data, {'path': str(path), 'sha256': digest}


def analyze_constraints(root, output_path, **parameters):
    output = json_path(root, output_path, output=True)
    data = build_analysis(root, **parameters)
    errors = list(data['source_errors'])
    if data['coverage']['omitted_pairs']:
        errors.append({'code': 'CONSTRAINT_PAIR_LIMIT', 'message': 'Pair output budget omitted relationships; they remain unknown.'})
    write_result(output, data)
    return success({'output_path': str(output), **data}, errors)
