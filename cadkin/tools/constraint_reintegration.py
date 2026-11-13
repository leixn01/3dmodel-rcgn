"""Continue constraint analysis with the same thresholds and explicit execution history."""
from cadkin.tools.files import json_path, read_json
from cadkin.tools.constraint_analysis import replay_analysis, analyze_constraints
from cadkin.tools.observation_index import index_evidence
from cadkin.followup.constraint_changes import compare_constraints


def continue_constraints(root, plan, execution_path, target_path, check_path, run, dest, binding):
    before, before_binding = replay_analysis(root, plan['constraint_analysis_source']['path'])
    max_contexts = 200
    if plan.get('evidence_index_source'):
        old_index, _ = read_json(json_path(root, plan['evidence_index_source']['path']))
        max_contexts = old_index['parameters']['max_contexts']
    index_path = run('cad_index_evidence', index_evidence, {'draft_check_path': check_path,
        'execution_path': execution_path, 'output_path': dest('index'), 'max_contexts': max_contexts})
    parameters = {k: before['parameters'][k] for k in ('distance_tolerance_mm', 'angle_tolerance_deg', 'max_pairs')}
    analysis_path = run('cad_analyze_constraints', analyze_constraints, {**parameters,
        'target_graph_path': target_path, 'evidence_index_path': index_path, 'output_path': dest('constraints')})
    after, _ = read_json(json_path(root, analysis_path))
    return {'before_constraint_analysis_source': before_binding, 'after_constraint_analysis_source': binding(analysis_path),
        'after_evidence_index_source': binding(index_path), 'constraint_changes': compare_constraints(before, after)}
