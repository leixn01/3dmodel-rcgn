"""0.26 first-chain acceptance, explicitly synthetic CAD with production orchestration."""
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
from cadkin.tools.observation_index import replay_index
from tests.chain_session_fakes import session_fixture


def run(root, output):
    dest = (root / output).resolve()
    if not dest.is_relative_to(root.resolve()/'outputs') or dest == root.resolve()/'outputs':
        raise ValueError('Use a fresh directory below outputs/.')
    dest.mkdir(parents=True, exist_ok=False)
    checks, cases = [], []
    def check(name, condition): checks.append({'name': name, 'passed': bool(condition)})
    for mode in ('chain_closed', 'no_mates', 'partial_enhanced', 'timeout'):
        base = dest / mode
        service, _, mates, _ = session_fixture(base, 'no_mates' if mode == 'no_mates' else 'chain_closed')
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        if mode == 'partial_enhanced': mates[0].GetDefinition = lambda: None
        original = service.worker.call; names = []
        def call(name, args):
            names.append(name)
            if mode == 'timeout' and name == 'sw_mate_inventory': return failure(ToolFailure('TIMEOUT', 'Synthetic timeout'))
            return original(name, args)
        try:
            with patch.object(service.worker, 'call', side_effect=call):
                result = run_chain_session(service, 'config.json', 'outputs/session.json')
            (base/'response.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            d = result['data']; h = d['handoffs']; report = json.loads(Path(d['report_source']['path']).read_text(encoding='utf-8'))
            cases.append({'mode': mode, 'response_path': str(base/'response.json'), 'report_source': d['report_source']})
            check(mode+' preserves original files', all(hashlib.sha256(p.read_bytes()).hexdigest() == s for p, s in before.items()))
            check(mode+' actual raw calls timed', len(names) == len(report['cad_capture_tool_timings']) +
                  sum(s['tool'] in ('sw_active_document', 'sw_spatial_inventory') for s in report['steps']))
            check(mode+' no physical assertion', not d['mechanically_verified'] and d['target_degrees_of_freedom'] is None and not d['finite_motion_verified'])
            check(mode+' no writes to CAD', set(names) <= {'sw_active_document', 'sw_spatial_inventory', 'sw_component_spatial', 'sw_mate_inventory', 'sw_component_cylinders'})
            if mode == 'timeout':
                check('timeout halts and keeps original receipt', result['status'] == 'error' and 'execution' in h and 'solution' not in h)
                check('timeout no retry or later CAD call', names[-1] == 'sw_mate_inventory' and names.count('sw_mate_inventory') == 1)
            else:
                solution, _ = replay_chain_solution(base, h['solution']['path'])
                index, _ = replay_index(base, h['index']['path'])
                check(mode+' original source graph replays', solution['evidence_index_source'] == h['index'])
                check(mode+' capture history retained', index['rounds_completed'] == (1 if mode == 'no_mates' else 2))
                check(mode+' no blind third mate scan', names.count('sw_mate_inventory') == (1 if mode == 'no_mates' else 2))
                check(mode+' final check and target agree', solution['check_source'] == h['check'] and solution['target_source'] == h['target'])
                snap = solution['snapshots'][0]
                if mode == 'chain_closed':
                    check('closed synthetic chain restricts two loop directions', snap['modeled_chain_instantaneous_dof'] == 0 and snap['spanning_forest_diagnostics']['additional_loop_rank'] == 2)
                    check('single command completes two bounded capture rounds', d['workflow_complete'] and d['rounds_completed'] == 2 and 2 <= len(report['batch_sources']) <= 21)
                elif mode == 'no_mates':
                    check('no mates is unknown not free', snap['known_constraint_nullity'] is None and not snap['motion_modes'])
                else:
                    check('partial enhanced attempt retained', any(o['tool'] == 'sw_mate_inventory' and not o['usable'] for o in index['observations']))
                    check('partial enhanced stops', d['stop_reason'] == 'PRIOR_ENHANCED_ATTEMPT_NO_AUTOMATIC_RETRY')
        finally: service.close()
    report = {'version': '0.26.0', 'scope': 'Synthetic CAD/production workflow; not the real lift or COM acceptance',
              'checks': checks, 'cases': cases, 'passed': all(c['passed'] for c in checks)}
    (dest/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'passed': report['passed'], 'checks': len(checks), 'report': str(dest/'report.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    args = parser.parse_args(); result = run(Path.cwd(), args.output)
    print(json.dumps(result, ensure_ascii=False)); raise SystemExit(0 if result['passed'] else 1)
