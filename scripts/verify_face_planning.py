"""0.19 acceptance: synthetic missing catalogs -> automatic finite-face probes -> indexed stop."""
import argparse
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
    base = dest/'synthetic-cad'; app = write_execution_fixture(base, include_face_review=False)
    original = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
    live = live_service(base, app)
    offline = SolidWorksTools(base, factory=lambda: (_ for _ in ()).throw(AssertionError('Offline operation attempted CAD')))
    def call(name, args):
        result = offline.call(name, args); filename = f'calls/{len(calls):03d}-{name}.json'; save(filename, result)
        calls.append({'tool': name, 'arguments': args, 'response_path': filename, 'status': result['status']})
        assert result['status'] != 'error', result
        return result['data']
    def index(run_path, name):
        return call('cad_index_evidence', dict(draft_check_path='outputs/check.json', execution_path=run_path, output_path=name))
    def plan(index_path, name, **options):
        return call('cad_plan_face_probes', dict(draft_check_path='outputs/check.json', evidence_index_path=index_path,
            output_path=name, max_component_gap_mm=30, surface_tolerance_mm=.1, **options))
    try:
        call('cad_plan_evidence_tasks', dict(draft_check_path='outputs/check.json', output_path='outputs/bootstrap-plan.json', max_tasks=9))
        initial = run_plan(live, 'outputs/bootstrap-plan.json', 'outputs/run1.json'); save('initial-execution.json', initial)
        check('initial guards passed', initial['data']['guards_passed'])
        first_index = index('outputs/run1.json', 'outputs/index1.json')
        first = plan('outputs/index1.json', 'outputs/faces-plan.json')
        check('versioned face plan', first['algorithm_version'] == 3 and first['plan_kind'] == 'witness_guided_face_probes')
        check('only two missing catalogs scheduled', [t['tool'] for t in first['tasks'] if t['phase'] == 'capture'] == ['sw_component_faces'] * 2)
        check('unbound files are not scanned for existing faces', first['face_candidates'] == [] and (base/'faces0.json').exists())
        check('planning never calls CAD or creates captures', all(not Path(t['save_envelope_path']).exists() for t in first['tasks']))
        check('catalog guard cost included', first['summary']['total_tool_calls'] == 8 and first['summary']['guard_tasks'] == 6)
        collected = run_plan(live, 'outputs/faces-plan.json', 'outputs/run2.json'); save('catalog-execution.json', collected)
        check('catalog capture completed with guards', collected['data']['execution_complete'] and collected['data']['guards_passed'])
        second_index = index('outputs/run2.json', 'outputs/index2.json')
        check('history retained across planner families', second_index['rounds_completed'] == 2 and len(second_index['observations']) == len(first_index['observations']) + 2)
        probes = plan('outputs/index2.json', 'outputs/probe-plan.json')
        check('three component pairs screened', probes['coverage']['examined_component_pairs'] == 3)
        check('all competing plane pairs retained', probes['coverage']['returned_face_pairs'] == 12)
        check('cylinder with incompatible witness is not guessed', all(c['surface_residuals_mm'] == [0, 0] for c in probes['face_candidates']))
        check('probe budget includes eight guards', probes['summary']['total_tool_calls'] == 20 and probes['summary']['guard_tasks'] == 8)
        check('seeds trace to distance endpoints and midpoint', all(c['seed_derivation'] == 'component_distance_endpoints_then_midpoint_unique' and len(c['seed_points_root_mm']) == 3 for c in probes['face_candidates']))
        check('no offline finite-face membership claim', all(not c['finite_face_membership_tested'] and not c['live_face_identity_verified'] for c in probes['face_candidates']))
        check('saved source hashes all match', all(hashlib.sha256(Path(b['path']).read_bytes()).hexdigest() == b['sha256'] for b in probes['input_files']))
        limited = plan('outputs/index2.json', 'outputs/limited.json', max_face_candidates=1, max_face_pairs=1)
        check('tied-face cutoff disclosed', limited['output_truncated'] and limited['coverage']['face_candidates_omitted'] > 0)
        tiny = plan('outputs/index2.json', 'outputs/tiny.json', max_tasks=6)
        check('no guard-only execution when budget too small', tiny['tasks'] == [] and tiny['continuation']['action'] == 'stop')
        measured = run_plan(live, 'outputs/probe-plan.json', 'outputs/run3.json'); save('probe-execution.json', measured)
        check('finite-face probes finish with guards', measured['data']['guards_passed'] and len(measured['data']['eligible_capture_ids']) == 12)
        third_index = index('outputs/run3.json', 'outputs/index3.json')
        observed = [o for o in third_index['observations'] if o['family'] == 'face_probes']
        check('all successful probes indexed', len(observed) == 12 and all(o['usable'] for o in observed))
        check('probe observations associated with exact component pairs', all(p['face_pair_selected'] and len(p['usable_probe_observation_ids']) == 4 for p in third_index['pair_contexts']))
        review = call('cad_review_face_contacts', {'probe_paths': [o['source']['path'] for o in observed],
            'output_path': 'outputs/contact-review.json', 'contact_tolerance_mm': .1, 'angle_tolerance_deg': 5})
        check('explicit-threshold review covers all probes', sum(review['counts'].values()) == 12)
        check('review never certifies contact or joint', not review['contact_confirmed'] and not review['mechanical_relation_confirmed'])
        stopped = plan('outputs/index3.json', 'outputs/stop.json', max_iterations=50)
        check('new iteration budget does not repeat tested pairs', stopped['tasks'] == [] and stopped['coverage']['previously_attempted_face_pairs'] == 12)
        check('stop retains risks and third-round lineage', stopped['continuation']['action'] == 'stop' and stopped['continuation']['rounds_completed'] == 3 and bool(stopped['remaining_findings']))
        rejected = offline.call('sw_execute_evidence_task', {'plan_path': 'outputs/stop.json', 'output_path': 'outputs/no-call.json'})
        save('stop-rejection.json', rejected)
        check('stopped executor makes no receipt or CAD call', rejected['errors'][0]['code'] == 'NO_CAPTURE_TASKS' and not (base/'outputs/no-call.json').exists())
        forged = json.loads((base/'outputs/probe-plan.json').read_text(encoding='utf-8')); forged['face_candidates'][0]['seed_points_root_mm'][0][0] += 1
        (base/'outputs/forged.json').write_text(json.dumps(forged), encoding='utf-8')
        rejected = offline.call('sw_execute_evidence_task', {'plan_path': 'outputs/forged.json', 'output_path': 'outputs/forged-receipt.json'})
        save('tamper-rejection.json', rejected)
        check('edited candidate rejected before CAD', rejected['errors'][0]['code'] == 'EVIDENCE_MISMATCH' and not (base/'outputs/forged-receipt.json').exists())
        check('original files unchanged', all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p,h in original.items()))
        check('no model mutation', app.ActiveDoc.dirty is False)
        check('no human gate or mechanical verdict', not stopped['requires_human_review'] and not stopped['mechanically_verified'])
        check('service remains usable after rejection', offline.call('cad_list_mechanism_templates', {})['status'] == 'ok')
    finally:
        live.close(); offline.close()
    report = {'passed': all(c['passed'] for c in checks), 'checks': checks, 'calls': calls, 'synthetic_backend': True,
              'limitations': ['Synthetic CAD, not user SolidWorks. Analytic candidates preserve trim ambiguity.',
                             'Finite-face local samples are not global minimum, contact patch, mechanical joint or disassembly verification.']}
    save('report.json', report)
    return report, dest/'report.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True); args = parser.parse_args()
    try:
        report, path = run(Path.cwd(), args.output)
        print(json.dumps({'passed': report['passed'], 'checks': len(report['checks']), 'report': str(path)}, ensure_ascii=False))
        raise SystemExit(0 if report['passed'] else 1)
    except (RuntimeError, OSError, ValueError, KeyError, AssertionError) as exc: parser.exit(2, f'{exc}\n')
