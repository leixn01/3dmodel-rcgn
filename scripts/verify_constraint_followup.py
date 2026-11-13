"""0.23 acceptance: bounded enhanced mate collection, reintegration, lineage and stop."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cadkin.errors import ToolFailure, failure
from cadkin.tools.execution import run_plan, replay_execution
from cadkin.tools.constraint_analysis import replay_analysis
from cadkin.tools.observation_index import replay_index
from cadkin.tools.solidworks import SolidWorksTools
from tests.constraint_fakes import write_constraint_followup_fixture
from tests.execution_fakes import live_service


def run(root, destination):
    root = root.resolve(); dest = (root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest == root/'outputs': raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True, exist_ok=False)
    checks, calls = [], []
    def check(name, ok): checks.append({'name': name, 'passed': bool(ok)})
    for mode in ('complete', 'partial', 'failed', 'no_mates', 'already_enhanced', 'changed'):
        base = dest/mode
        app, mates, _ = write_constraint_followup_fixture(base, 'no_mates' if mode == 'no_mates' else 'revolute', mode == 'already_enhanced')
        original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        before = (app.ActiveDoc.dirty, app.ActiveDoc.rebuilt, list(app.ActiveDoc.SelectionManager.selected))
        live = live_service(base, app)
        offline = SolidWorksTools(base, factory=lambda: (_ for _ in ()).throw(AssertionError('Offline tool connected to CAD')))
        def read(path): return json.loads((base/path).read_text(encoding='utf-8'))
        def call(name, **args):
            result = offline.call(name, args)
            response = base/f'response-{len(calls):03d}.json'
            response.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            calls.append({'mode': mode, 'tool': name, 'arguments': args, 'response_path': str(response)})
            assert result['status'] != 'error', result
            return result['data']
        try:
            plan = read('outputs/plan.json')
            if mode in ('no_mates', 'already_enhanced'):
                check(mode+' no capture and no guard loop', plan['continuation']['action']=='stop' and plan['tasks']==[])
                check(mode+' remaining unknown evidence kept', bool(plan['constraint_findings']))
                result = offline.call('sw_execute_evidence_task', {'plan_path':'outputs/plan.json','output_path':'outputs/rejected.json'})
                check(mode+' executor refuses stopped plan', result['errors'][0]['code']=='NO_CAPTURE_TASKS' and not (base/'outputs/rejected.json').exists())
                continue
            check(mode+' basic scan permits bounded enhancement', plan['algorithm_version']==4 and plan['summary']['planned_capture_tasks']==1 and
                plan['summary']['total_tool_calls']==9 and next(t for t in plan['tasks'] if t['phase']=='capture')['arguments']['include_reference_geometry'])
            if mode == 'partial': mates[0].GetDefinition = lambda: None
            if mode == 'failed':
                original_call = live.call
                def fail(name, args=None):
                    return failure(ToolFailure('API_ERROR','Synthetic failure')) if name=='sw_mate_inventory' else original_call(name,args)
                live.call = fail
            if mode == 'changed':
                from types import SimpleNamespace
                seen = []
                def changed(): seen.append(1); return SimpleNamespace(LockRotation=len(seen)>1)
                mates[0].GetDefinition = changed
            result = run_plan(live, 'outputs/plan.json', 'outputs/run.json')
            execution = replay_execution(base, 'outputs/run.json')[0]
            calls.append({'mode':mode,'tool':'CLI execute-evidence / sw_execute_evidence_task','plan_path':str(base/'outputs/plan.json'),
                'execution_path':str(base/'outputs/run.json'),'original_envelopes':[r['envelope_source'] for r in execution['records'] if r['envelope_source']]})
            if mode == 'changed':
                check('changed lock stops after one capture', not execution['guards_passed'] and execution['summary']['calls_executed']==5 and not execution['eligible_capture_ids'])
                result = offline.call('cad_reintegrate_evidence', {'execution_path':'outputs/run.json','output_path':'outputs/rejected.json'})
                check('changed lock prohibits reuse', result['errors'][0]['code']=='EXECUTION_GUARDS_FAILED')
                continue
            check(mode+' complete guards and serial receipt replay', execution['guards_passed'] and execution['summary']['calls_executed']==9)
            update = call('cad_reintegrate_evidence', execution_path='outputs/run.json', output_path='outputs/updated.json')
            check(mode+' automatic reanalysis and index outputs', update['recomputation_complete'] and update['after_constraint_analysis_source'] and update['after_evidence_index_source'])
            analysis, _ = replay_analysis(base, update['after_constraint_analysis_source']['path'])
            index, ib = replay_index(base, update['after_evidence_index_source']['path'])
            check(mode+' history and exact source binding', index['rounds_completed']==1 and analysis['evidence_index_source']==ib)
            check(mode+' thresholds and unknown target retained', analysis['parameters']['distance_tolerance_mm']==.1 and
                analysis['parameters']['angle_tolerance_deg']==.1 and all(p['target_joint_kind']=='unknown' and p['target_degrees_of_freedom'] is None for p in analysis['pairs']))
            if mode == 'complete':
                check('complete enhanced source produces local candidate', analysis['coverage']['candidate_patterns']==1 and len(update['applied_capture_ids'])==1)
                check('comparison retains snapshot separation', all(not p['feature_identity_matched'] for p in update['constraint_changes']['pairs']))
                limited = call('cad_plan_evidence_tasks', draft_check_path='outputs/check.json', constraint_analysis_path='outputs/constraints.json',
                    output_path='outputs/limited.json', max_tasks=8)
                check('budget cannot drop guards', not limited['tasks'] and limited['continuation']['reason']=='CAPTURE_BUDGET_UNAVAILABLE')
            else:
                check(mode+' failed evidence stays diagnostic', index['summary']['retained_unsuccessful_attempts']==1 and
                    not update['applied_capture_ids'] and analysis['coverage']['candidate_patterns']==0 and len(update['excluded_captures'])==1)
            stopped = call('cad_plan_evidence_tasks', draft_check_path=update['after_check_source']['path'],
                constraint_analysis_path=update['after_constraint_analysis_source']['path'], output_path='outputs/stop.json', max_tasks=200)
            check(mode+' index inherited without explicit argument', stopped['evidence_index_source']==ib and stopped['continuation']['rounds_completed']==1)
            check(mode+' new filename and bigger budget cannot retry', not stopped['tasks'] and stopped['continuation']['reason']=='PRIOR_ENHANCED_ATTEMPT_NO_AUTOMATIC_RETRY')
            check(mode+' sources and CAD unchanged', all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in original.items()) and
                before==(app.ActiveDoc.dirty,app.ActiveDoc.rebuilt,app.ActiveDoc.SelectionManager.selected))
        finally:
            live.close(); offline.close()
    report = {'version':'0.23.0','scope':'Synthetic CAD adapter plus real offline/execution implementation; no installed SolidWorks or lift validation',
        'passed':all(c['passed'] for c in checks),'checks':checks,'calls':calls}
    (dest/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':report['passed'],'checks':len(checks),'report':str(dest/'report.json')}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    result=run(Path.cwd(),args.output);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
