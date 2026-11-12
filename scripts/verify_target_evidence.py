"""0.21 acceptance: target-first drafts and optional bench-vise analogies without type transfer."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.execution import run_plan
from tests.chain_fakes import write_chain_fixture
from tests.execution_fakes import live_service


def run(root, destination):
    root = root.resolve(); dest = (root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest == root/'outputs': raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True, exist_ok=False)
    checks, calls = [], []
    def check(name, ok): checks.append({'name': name, 'passed': bool(ok)})
    def save(name, data):
        path = dest/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream: json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    base = dest/'synthetic-cad'; args, app = write_chain_fixture(base, with_lock=True, return_app=True)
    original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
    offline = SolidWorksTools(base, factory=lambda: (_ for _ in ()).throw(AssertionError('Offline tool called CAD')))
    live = live_service(base, app)
    def call(tool, **arguments):
        result = offline.call(tool, arguments); name = f'calls/{len(calls):03d}-{tool}.json'; save(name, result)
        calls.append({'tool': tool, 'arguments': arguments, 'status': result['status'], 'response_path': name})
        assert result['status'] != 'error', result
        return result['data']
    try:
        call('cad_build_chain_evidence', **args)
        call('cad_build_target_graph', chain_path='outputs/chain.json', output_path='outputs/target.json')
        call('cad_build_rigid_candidates', target_graph_path='outputs/target.json', output_path='outputs/rigid.json')
        plain = call('cad_draft_joints', rigid_candidates_path='outputs/rigid.json', output_path='outputs/plain.json', pattern_size=2)
        rows = [p for r in plain['partition_results'] for p in r['connection_candidates']]
        check('versioned target-first output', plain['algorithm_version'] == 2 and plain['analysis_basis'] == 'target_evidence_first')
        check('default loads no reference', plain['template_sources'] == [] and not plain['template_search_requested'])
        check('no template search performed', plain['summary']['evaluated_states'] == 0 and all(r['match'] is None for r in plain['partition_results']))
        check('target evidence exists without matches', bool(rows) and plain['summary']['target_pairs_returned'] == len(rows))
        check('target types remain unknown', all(p['target_joint_kind'] == 'unknown' and p['target_degrees_of_freedom'] is None for p in rows))
        check('source instance-pair bindings retained', all(p['source_occurrence_pair_ids'] for p in rows))
        check('active constraints retained independently', any(p['assessment'] == 'constraint_feature_evidence' for p in rows))
        check('geometric lines are available without reference', any(p['geometry']['geometric_line_candidates'] for p in rows))
        check('no physical connectivity asserted', all(not p['connection_confirmed'] and not p['reference_required'] for p in rows))
        bench = call('cad_draft_joints', rigid_candidates_path='outputs/rigid.json', template_ids=['bench_vise'],
            pattern_size=2, max_candidates=10, output_path='outputs/bench.json')
        check('explicit template is source-bound', [b['id'] for b in bench['template_sources']] == ['bench_vise'])
        check('reference choice cannot change target baseline', [r['connection_candidates'] for r in plain['partition_results']] == [r['connection_candidates'] for r in bench['partition_results']])
        analogies = [e for r in bench['partition_results'] if r['match'] for c in r['match']['candidates'] for e in c['joint_hypotheses']]
        check('reference type never becomes target type or DOF', bool(analogies) and all(e['hypothesis_kind'] == 'unknown' and e['dof_hypothesis'] is None and not e['reference_type_transferred'] for e in analogies))
        matched = call('cad_match_mechanism_templates', target_graph_path='outputs/target.json', template_ids=['bench_vise'],
            pattern_size=2, max_candidates=20, output_path='outputs/bench-match.json')
        swivel = [e for c in matched['candidates'] for e in c['joint_hypotheses'] if e['reference_joint_id'].endswith('/swivel')]
        check('real bundled swivel retained as reference', bool(swivel) and all(e['reference_joint_kind'] == 'revolute' for e in swivel))
        check('swivel target is unknown', all(e['target_joint_kind'] == 'unknown' and e['target_degrees_of_freedom'] is None for e in swivel))
        check('reference movement opposed by active lock is explicit', any(e['reference_compatibility'] == 'opposed_by_active_lock' for e in swivel))
        limited = call('cad_draft_joints', rigid_candidates_path='outputs/rigid.json', max_target_pairs=1, output_path='outputs/limited.json')
        check('target budget shared across partitions', limited['summary']['target_pairs_returned'] == 1 and limited['target_pairs_truncated'])
        checked = call('cad_check_joint_draft', joint_draft_path='outputs/plain.json', output_path='outputs/check.json')
        check('no-template check does not report template absence as failure', 'PARTITION_NOT_SEARCHED' not in {f['code'] for f in checked['findings']})
        check('target uncertainty retained', 'TARGET_JOINT_TYPE_UNDETERMINED' in {f['code'] for f in checked['findings']})
        plan = call('cad_plan_evidence_tasks', draft_check_path='outputs/check.json', output_path='outputs/plan.json')
        check('template-free plan retains read-only calls', bool(plan['tasks']) and not plan['executed'])
        execution = run_plan(live, 'outputs/plan.json', 'outputs/run.json'); save('execution-return.json', execution)
        check('synthetic guarded execution completes', execution['data']['execution_complete'] and execution['data']['guards_passed'])
        updated = call('cad_reintegrate_evidence', execution_path='outputs/run.json', output_path='outputs/updated.json')
        check('template-free reintegration completes', updated['recomputation_complete'])
        compared = call('cad_compare_draft_checks', before_check_path='outputs/check.json', after_check_path=updated['after_check_source']['path'], output_path='outputs/comparison.json')
        check('target evidence compared without reference candidates', bool(compared['before_candidates']) and all(c['basis'] == 'target_evidence' for c in compared['before_candidates'].values()))
        index = call('cad_index_evidence', draft_check_path=updated['after_check_source']['path'], execution_path='outputs/run.json', output_path='outputs/index.json')
        check('target contexts indexed without template', bool(index['joint_contexts']) and all(c['template_id'] is None for c in index['joint_contexts']))
        stopped = call('cad_plan_evidence_tasks', draft_check_path=updated['after_check_source']['path'], evidence_index_path='outputs/index.json', output_path='outputs/stop.json')
        check('known evidence is not repeatedly captured', stopped['tasks'] == [] and stopped['continuation']['action'] == 'stop')
        bad = json.loads((base/'outputs/plain.json').read_text(encoding='utf-8')); bad['partition_results'][0]['connection_candidates'][0]['target_joint_kind'] = 'revolute'
        (base/'outputs/forged.json').write_text(json.dumps(bad), encoding='utf-8')
        rejected = offline.call('cad_check_joint_draft', dict(joint_draft_path='outputs/forged.json', output_path='outputs/rejected.json')); save('tamper-rejection.json', rejected)
        check('forged target revolute rejected', rejected['errors'][0]['code'] == 'EVIDENCE_MISMATCH' and not (base/'outputs/rejected.json').exists())
        check('all original inputs unchanged', all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p,h in original.items()))
        check('no human gate or CAD modification', not plain['requires_human_review'] and not plain['solidworks_modified'] and not app.ActiveDoc.dirty)
    finally: live.close(); offline.close()
    report = {'passed': all(c['passed'] for c in checks), 'checks': checks, 'calls': calls,
        'synthetic_target': True, 'reference': 'pinned bench_vise asset',
        'limitations': ['This reproduces type-transfer risk using synthetic target evidence, not the user STEP measurement.',
                       'Target joint kinds and DOF are unknown; this workflow does not solve motion or certify disassembly.']}
    save('report.json', report); return report, dest/'report.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True); args = parser.parse_args()
    try:
        report, path = run(Path.cwd(), args.output)
        print(json.dumps({'passed': report['passed'], 'checks': len(report['checks']), 'report': str(path)}, ensure_ascii=False))
        raise SystemExit(0 if report['passed'] else 1)
    except (RuntimeError, OSError, ValueError, KeyError, AssertionError) as exc: parser.exit(2, f'{exc}\n')
