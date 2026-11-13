"""0.27 root-mate acceptance with explicit synthetic CAD, never real lift evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cadkin.errors import ToolFailure, failure
from cadkin.tools.chain_session import run_chain_session
from cadkin.tools.chain_motion import replay_chain_solution
from cadkin.tools.followup import replay_plan
from cadkin.tools.observation_index import replay_index
from tests.chain_session_fakes import session_fixture


def run(root, output):
    root = root.resolve(); dest = (root/output).resolve()
    if not dest.is_relative_to(root/'outputs') or dest == root/'outputs':
        raise ValueError('Use a fresh directory below outputs/.')
    dest.mkdir(parents=True, exist_ok=False)
    checks, cases, results = [], [], {}
    def check(name, condition): checks.append({'name': name, 'passed': bool(condition)})
    for mode in ('chain_closed', 'plane', 'lock', 'no_mates', 'partial', 'default', 'failed_cylinders'):
        base = dest/mode
        fixture_mode = mode if mode in ('plane', 'lock', 'no_mates') else 'chain_closed'
        service, _, mates, config = session_fixture(base, fixture_mode)
        config['capture_profile'] = 'geometry_and_mates' if mode in ('default', 'failed_cylinders') else 'root_mates'
        if mode in ('plane', 'lock'): config['occurrence_paths'] = ['base-1', 'carriage-1']
        (base/'config.json').write_text(json.dumps(config), encoding='utf-8')
        if mode == 'partial': mates[0].GetDefinition = lambda: None
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        original = service.worker.call; calls = []
        def call(name, args):
            calls.append(name)
            if mode == 'failed_cylinders' and name == 'sw_component_cylinders':
                return failure(ToolFailure('API_ERROR', 'Explicit synthetic body scan failure'))
            return original(name, args)
        try:
            with patch.object(service.worker, 'call', side_effect=call):
                result = run_chain_session(service, 'config.json', 'outputs/session.json')
            (base/'response.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            d = result['data']; h = d['handoffs']
            report = json.loads(Path(d['report_source']['path']).read_text(encoding='utf-8'))
            solution, _ = replay_chain_solution(base, h['solution']['path'])
            index, _ = replay_index(base, h['index']['path'])
            plan, _, _, _ = replay_plan(base, 'outputs/session-files/initial-plan.json')
            target = json.loads(Path(h['target']['path']).read_text(encoding='utf-8'))
            cases.append({'mode': mode, 'report_source': d['report_source'], 'solution_source': h['solution']})
            results[mode] = {'solution': solution, 'capture_calls': len(report['cad_capture_tool_timings'])}
            check(mode+' completes bounded workflow', result['status'] == 'ok' and d['workflow_complete'])
            check(mode+' original files unchanged', all(hashlib.sha256(p.read_bytes()).hexdigest() == s for p, s in before.items()))
            check(mode+' sources and history replay', solution['evidence_index_source'] == h['index'] and solution['check_source'] == h['check'])
            check(mode+' no physical claim', solution['target_degrees_of_freedom'] is None and not solution['finite_motion_verified'])
            check(mode+' CAD calls remain read-only', set(calls) <= {'sw_active_document', 'sw_spatial_inventory', 'sw_component_spatial', 'sw_mate_inventory', 'sw_component_cylinders'})
            if config['capture_profile'] == 'root_mates':
                check(mode+' one enhanced scan without body queries', calls.count('sw_mate_inventory') == 1 and 'sw_component_cylinders' not in calls and target['relation_sources'] == [])
                check(mode+' full guards and one shared round', plan['algorithm_version'] == 5 and plan['summary']['guard_tasks'] == 2*len(config['occurrence_paths'])+2 and index['rounds_completed'] == 1)
            if mode in ('chain_closed', 'plane', 'lock'):
                snap = solution['snapshots'][0]
                check(mode+' expected modeled instantaneous dimension', snap['modeled_chain_instantaneous_dof'] == (3 if mode == 'plane' else 0))
            if mode == 'no_mates':
                check('empty mate source is unknown', solution['snapshots'][0]['known_constraint_nullity'] is None and not solution['snapshots'][0]['motion_modes'])
            if mode == 'partial':
                check('failed enhancement retained and not retried', index['summary']['retained_unsuccessful_attempts'] == 1 and d['stop_reason'] == 'NO_EXISTING_CONNECTION_BASIS')
            if mode == 'failed_cylinders':
                check('failed scans cannot block native constraints', target['relation_sources'] == [] and solution['snapshots'][0]['modeled_chain_instantaneous_dof'] == 0)
                check('all failed scans retained with two shared rounds', index['summary']['retained_unsuccessful_attempts'] == 3 and index['rounds_completed'] == 2)
        finally: service.close()
    native = results['chain_closed']; default = results['default']
    check('capture plus guard calls reduce from 21 to 9', default['capture_calls'] == 21 and native['capture_calls'] == 9)
    left, right = native['solution']['snapshots'][0], default['solution']['snapshots'][0]
    check('same supported closed-chain solution', left['modeled_chain_instantaneous_dof'] == right['modeled_chain_instantaneous_dof'] == 0 and
          left['spanning_forest_diagnostics']['additional_loop_rank'] == right['spanning_forest_diagnostics']['additional_loop_rank'] == 2)
    report = {'version': '0.27.0', 'scope': 'Synthetic CAD / production workflow. Not SolidWorks or real lift acceptance; call counts are not wall-time speedup.',
              'checks': checks, 'cases': cases, 'passed': all(c['passed'] for c in checks)}
    (dest/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'passed': report['passed'], 'checks': len(checks), 'report': str(dest/'report.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    args = parser.parse_args(); result = run(Path.cwd(), args.output)
    print(json.dumps(result, ensure_ascii=False)); raise SystemExit(0 if result['passed'] else 1)
