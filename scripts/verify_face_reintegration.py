"""0.20 acceptance: guarded face probes -> preserved-threshold rebuild -> evidence comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cadkin.tools.files import read_json
from cadkin.tools.solidworks import SolidWorksTools
from tests.face_reintegration_fakes import prepare


def run(root, destination):
    root = root.resolve(); dest = (root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest == root/'outputs': raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True, exist_ok=False)
    checks, calls = [], []
    def check(name, ok): checks.append({'name': name, 'passed': bool(ok)})
    def save(name, data):
        path = dest/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream: json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    base = dest/'synthetic-cad'; app, receipt, captures = prepare(base)
    original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
    service = SolidWorksTools(base, factory=lambda: (_ for _ in ()).throw(AssertionError('Offline operation attempted CAD')))
    def call(tool, **args):
        result = service.call(tool, args); name = f'calls/{len(calls):03d}-{tool}.json'; save(name, result)
        calls.append({'tool': tool, 'arguments': args, 'response_path': name, 'status': result['status']})
        assert result['status'] != 'error', result
        return result['data']
    try:
        check('complete execution and guards', receipt['execution_complete'] and receipt['guards_passed'])
        check('eleven new complete face probes', len(captures) == 11)
        automatic = call('cad_reintegrate_evidence', execution_path='outputs/face-run.json', output_path='outputs/automatic.json')
        check('automatic recomputation completed', automatic['recomputation_complete'])
        check('three probes fit existing component-pair basis', len(automatic['applied_capture_ids']) == 3)
        check('uncovered probes remain explicit supplements', len(automatic['supplemental_captures']) == 8 and
            {c['reason'] for c in automatic['supplemental_captures']} == {'NO_MATCHING_FACE_REVIEW'})
        updated = call('cad_reintegrate_evidence', execution_path='outputs/face-run.json',
            face_review_path='outputs/supplied-review.json', output_path='outputs/updated.json')
        check('provided basis recomputation completed', updated['recomputation_complete'])
        check('all eleven guarded probes integrated', len(updated['applied_capture_ids']) == 11 and not updated['supplemental_captures'])
        by_kind = {u['basis_kind']: u for u in updated['face_updates']}
        old_update = by_kind['existing_chain_review']; extra = by_kind['provided_review_for_uncovered_pairs']
        check('existing thresholds retained', old_update['parameters'] == {'contact_tolerance_mm': .1, 'angle_tolerance_deg': 5})
        check('provided thresholds only used for eight uncovered probes', extra['added_probes'] == 8 and
            extra['parameters'] == {'contact_tolerance_mm': .2, 'angle_tolerance_deg': 7})
        old = read_json(Path(old_update['basis_source']['path']))[0]; new = read_json(Path(old_update['output_source']['path']))[0]
        check('original face observation retained exactly', new['pairs'][0] == old['pairs'][0] and old_update['retained_previous_probes'] == 1)
        check('new review contains only guarded uncovered rows', len(read_json(Path(extra['output_source']['path']))[0]['pairs']) == 8)
        check('every supplied basis input hash bound', updated['supplied_face_review_source'] in updated['input_files'] and
            all(hashlib.sha256(Path(b['path']).read_bytes()).hexdigest() == b['sha256'] for b in updated['input_files']))
        compared = call('cad_compare_draft_checks', before_check_path='outputs/check.json',
            after_check_path=updated['after_check_source']['path'], output_path='outputs/comparison.json')
        summary = compared['face_evidence']['summary']
        check('face observation count changes from one to twelve', summary['before_face_observations'] == 1 and summary['after_face_observations'] == 12)
        check('eleven genuinely new face records', summary['newly_observed_ids'] == 11)
        check('no original semantic measurement changed', summary['changed_ids'] == 0 and summary['no_longer_observed_ids'] == 0)
        check('one rewritten provenance separated from semantics', summary['provenance_changed_ids'] == 1)
        check('threshold coverage differences disclosed', summary['pairs_with_threshold_profile_changes'] == 2)
        check('original search settings and scope retained', compared['settings_equal'] and compared['occurrence_scope_equal'])
        check('local evidence does not confirm connections', all(not p['connection_confirmed'] for p in compared['face_evidence']['pairs']))
        indexed = call('cad_index_evidence', draft_check_path=updated['after_check_source']['path'],
            execution_path='outputs/face-run.json', output_path='outputs/updated-index.json')
        check('index follows updated check and preserves rounds', indexed['check_source'] == updated['after_check_source'] and indexed['rounds_completed'] == 2)
        stopped = call('cad_plan_face_probes', draft_check_path=updated['after_check_source']['path'],
            evidence_index_path='outputs/updated-index.json', output_path='outputs/stop.json', max_component_gap_mm=30, surface_tolerance_mm=.1)
        check('no duplicate probe after reintegration', stopped['tasks'] == [] and stopped['coverage']['previously_attempted_face_pairs'] == 12)
        check('stop retains remaining findings', stopped['continuation']['action'] == 'stop' and bool(stopped['remaining_findings']))
        rejected = service.call('sw_execute_evidence_task', {'plan_path': 'outputs/stop.json', 'output_path': 'outputs/no-call.json'})
        save('stop-rejection.json', rejected)
        check('stopped executor calls no CAD', rejected['errors'][0]['code'] == 'NO_CAPTURE_TASKS' and not (base/'outputs/no-call.json').exists())
        forged = read_json(base/'outputs/supplied-review.json')[0]; forged['pairs'][0]['review_state'] = 'forged'
        (base/'outputs/forged-review.json').write_text(json.dumps(forged), encoding='utf-8')
        rejected = service.call('cad_reintegrate_evidence', dict(execution_path='outputs/face-run.json',
            face_review_path='outputs/forged-review.json', output_path='outputs/rejected.json'))
        save('tamper-rejection.json', rejected)
        check('changed interpretation rejected without report', rejected['errors'][0]['code'] == 'EVIDENCE_MISMATCH' and not (base/'outputs/rejected.json').exists())
        rejected = service.call('cad_reintegrate_evidence', dict(execution_path='outputs/face-run.json', output_path='outputs/updated.json'))
        save('overwrite-rejection.json', rejected)
        check('existing outputs never overwritten', rejected['errors'][0]['code'] == 'OUTPUT_EXISTS')
        check('all original evidence files unchanged', all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p,h in original.items()))
        check('no model mutation', app.ActiveDoc.dirty is False and not updated['solidworks_modified'])
        check('no human gate or mechanical verdict', not updated['requires_human_review'] and not updated['mechanically_verified'] and not compared['resolved_findings_asserted'])
    finally: service.close()
    report = {'passed': all(c['passed'] for c in checks), 'checks': checks, 'calls': calls, 'synthetic_backend': True,
        'limitations': ['Synthetic CAD, not the user SolidWorks model. Production offline tools rebuild source-bound evidence.',
                       'Local observations do not prove global clearance, physical joints, motion or disassembly paths.']}
    save('report.json', report); return report, dest/'report.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True); args = parser.parse_args()
    try:
        report, path = run(Path.cwd(), args.output)
        print(json.dumps({'passed': report['passed'], 'checks': len(report['checks']), 'report': str(path)}, ensure_ascii=False))
        raise SystemExit(0 if report['passed'] else 1)
    except (RuntimeError, OSError, ValueError, KeyError, AssertionError) as exc: parser.exit(2, f'{exc}\n')
