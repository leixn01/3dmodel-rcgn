"""0.18 acceptance: synthetic collection, offline association, bounded reuse and stopping."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cadkin.tools.execution import run_plan
from cadkin.tools.solidworks import SolidWorksTools
from tests.execution_fakes import write_execution_fixture, live_service


def run(root, destination):
    root = root.resolve(); dest = (root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest == root/'outputs': raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True, exist_ok=False)
    checks, calls = [], []
    def check(name, ok): checks.append({'name': name, 'passed': bool(ok)})
    def save(name, data):
        path = dest/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream: json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    base = dest/'synthetic-cad'; app = write_execution_fixture(base)
    original = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
    live = live_service(base, app)
    offline = SolidWorksTools(base, factory=lambda: (_ for _ in ()).throw(AssertionError('Offline operation attempted CAD')))
    def call(name, args):
        result = offline.call(name, args)
        filename = f'calls/{len(calls):03d}-{name}.json'; save(filename, result)
        calls.append({'tool': name, 'arguments': args, 'response_path': filename, 'status': result['status']})
        return result
    try:
        executed = run_plan(live, 'outputs/plan.json', 'outputs/run.json'); save('execution.response.json', executed)
        check('synthetic collection guards passed', executed['data']['guards_passed'])
        result = call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': 'outputs/run.json', 'output_path': 'outputs/index.json'})
        data = result['data']
        check('offline index accepted', result['status'] == 'ok')
        check('all three complete observations are reusable', data['summary']['reusable'] == 3)
        check('first round explicitly counted', data['rounds_completed'] == 1)
        check('constraints and face catalog both indexed', {o['family'] for o in data['observations']} == {'constraints', 'faces'})
        check('three occurrence identities retained', len(data['node_observations']) == 3)
        check('every scope pair retained', len(data['pair_contexts']) == 3)
        check('returned findings associated', len(data['finding_contexts']) == data['remaining_findings_summary']['findings_returned'])
        check('retained joints associated', bool(data['joint_contexts']))
        ids = {o['id'] for o in data['observations']}
        check('joint context points to indexed sources', all(set(j['observation_ids']) <= ids for j in data['joint_contexts']))
        check('no invented face pair or connection', all(not p['face_pair_selected'] and not p['connection_confirmed'] for p in data['pair_contexts']))
        check('unverified mate names remain unresolved', all(not o['details']['reference_names_resolved_to_occurrences'] for o in data['observations'] if o['family'] == 'constraints'))
        check('saved faces are not live identity proof', all(not o['details']['live_face_identity_verified'] for o in data['observations'] if o['family'] == 'faces'))
        check('all input hashes match', all(hashlib.sha256(Path(b['path']).read_bytes()).hexdigest() == b['sha256'] for b in data['input_files']))
        planned = call('cad_plan_evidence_tasks', {'draft_check_path': 'outputs/check.json', 'evidence_index_path': 'outputs/index.json', 'output_path': 'outputs/next.json'})['data']
        check('follow-up uses versioned index binding', planned['algorithm_version'] == 2 and bool(planned['evidence_index_source']))
        check('complete observations reused without repeated capture', planned['summary']['planned_capture_tasks'] == 0)
        check('explicit stop with no guard-only loop', planned['continuation']['action'] == 'stop' and planned['tasks'] == [])
        check('remaining risks are not cleared by stopping', planned['continuation']['remaining_findings'] > 0 and len(planned['remaining_findings']) == data['remaining_findings_summary']['findings_returned'] and not planned['continuation']['mechanically_verified'])
        stopped = call('sw_execute_evidence_task', {'plan_path': 'outputs/next.json', 'output_path': 'outputs/stop-receipt.json'})
        check('executor refuses a stopped plan before CAD', stopped['errors'][0]['code'] == 'NO_CAPTURE_TASKS' and not (base/'outputs/stop-receipt.json').exists())
        check('no CAD mutation', app.ActiveDoc.dirty is False)
        check('original input files unchanged', all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p, sha in original.items()))
        limited = call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': 'outputs/run.json', 'max_contexts': 1, 'output_path': 'outputs/limited.json'})
        check('context truncation stays explicit', limited['status'] == 'partial' and limited['data']['joint_contexts_truncated'])
        check('context limit preserves reusable captures', limited['data']['summary']['reusable'] == 3)
        forged = json.loads((base/'outputs/index.json').read_text(encoding='utf-8')); forged['observations'][0]['usable'] = False
        (base/'outputs/forged.json').write_text(json.dumps(forged), encoding='utf-8')
        rejected = call('cad_plan_evidence_tasks', {'draft_check_path': 'outputs/check.json', 'evidence_index_path': 'outputs/forged.json', 'output_path': 'outputs/rejected.json'})
        check('edited index rejected', rejected['errors'][0]['code'] == 'EVIDENCE_MISMATCH')
        check('no human gate or mechanical verdict', data['requires_human_review'] is False and data['mechanically_verified'] is False)
        check('offline service recovers after rejection', call('cad_list_mechanism_templates', {})['status'] == 'ok')
    finally:
        live.close(); offline.close()
    report = {'passed': all(c['passed'] for c in checks), 'checks': checks, 'calls': calls, 'synthetic_backend': True,
        'requires_human_review': False, 'limitations': ['Explicit synthetic CAD, not the user SolidWorks model.',
            'Associations do not select faces, solve mechanics or change candidate scores.',
            'Stopped capture retains uncertainty; only the supplied lineage is known.']}
    save('report.json', report)
    return report, dest/'report.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True); args = parser.parse_args()
    try:
        report, path = run(Path.cwd(), args.output)
        print(json.dumps({'passed': report['passed'], 'checks': len(report['checks']), 'report': str(path)}, ensure_ascii=False))
        raise SystemExit(0 if report['passed'] else 1)
    except (RuntimeError, OSError, ValueError, KeyError, AssertionError) as exc: parser.exit(2, f'{exc}\n')
