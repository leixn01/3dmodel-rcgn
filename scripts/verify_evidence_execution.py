"""0.17 acceptance: explicit synthetic CAD execution, offline reintegration and comparison."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cadkin.errors import failure,ToolFailure
from cadkin.tools.execution import run_plan,execute_task,replay_execution
from cadkin.tools.solidworks import CATALOG
from tests.execution_fakes import write_execution_fixture,live_service


def run(root,destination):
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False)
    checks=[];calls=[]
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    def save(name,data):
        path=dest/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
    fixture=dest/'synthetic-cad';app=write_execution_fixture(fixture,degraded=True)
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.rglob('*.json')}
    service=live_service(fixture,app);original=service.call
    def call(name,args=None):
        index=len(calls);item={'tool':name,'arguments':args};calls.append(item)
        result=original(name,args);item['status']=result['status'];item['response_path']=f'calls/{index:03d}-{name}.json'
        save(item['response_path'],result);return result
    service.call=call
    try:
        executed=run_plan(service,'outputs/plan.json','outputs/run.json');save('execution.response.json',executed);e=executed['data']
        check('bounded execution completes',e['execution_complete'])
        check('all context guards pass',e['guards_passed'])
        check('eligible captures are explicitly listed',len(e['eligible_capture_ids'])>0)
        check('no failed or skipped normal tasks',e['summary']['failed']==e['summary']['skipped']==0)
        raw_calls=[c for c in calls if c['tool'].startswith('sw_') and c['tool']!='sw_execute_evidence_task']
        step_calls=[c for c in calls if c['tool']=='sw_execute_evidence_task']
        check('each invocation executes one CAD read',len(raw_calls)==len(step_calls)==e['summary']['calls_executed'])
        check('all underlying CAD calls are read only',all(CATALOG[c['tool']]['annotations']['readOnlyHint'] for c in raw_calls))
        check('raw envelopes saved and hash bound',all(hashlib.sha256(Path(r['envelope_source']['path']).read_bytes()).hexdigest()==r['envelope_source']['sha256'] for r in e['records'] if r['envelope_source']))
        check('receipt replays from raw observations',replay_execution(fixture,'outputs/run.json')[0]['records']==e['records'])
        check('no model dirty mutation',app.ActiveDoc.dirty is False)
        update=call('cad_reintegrate_evidence',{'execution_path':'outputs/run.json','output_path':'outputs/updated.json'});u=update['data']
        check('compatible evidence recomputed to final check',u['recomputation_complete'] and u['after_check_source'] is not None)
        check('new cylinder and root mate evidence applied',len(u['applied_capture_ids'])>=3)
        check('previous sources retained and mapped',bool(u['superseded_sources']) and all(Path(s['old_path']).exists() for s in u['superseded_sources']))
        check('supplemental observations explicitly excluded from mechanical inference',bool(u['supplemental_captures']))
        check('partial findings remain explicit',any(x['code']=='DERIVATION_REMAINS_PARTIAL' for x in update['errors']))
        check('recomputed chain target rigid joints check all present',{'cad_build_chain_evidence','cad_build_target_graph','cad_build_rigid_candidates','cad_draft_joints','cad_check_joint_draft'}<={s['tool'] for s in u['steps']})
        old=json.loads((fixture/'outputs/drafts.json').read_text());new=json.loads((fixture/'outputs/updated-derived/joints.json').read_text())
        check('original joint search and geometry tolerances retained',old['parameters']==new['parameters'])
        check('original reference set retained',old['template_sources']==new['template_sources'])
        compared=call('cad_compare_draft_checks',{'before_check_path':'outputs/check.json','after_check_path':u['after_check_source']['path'],'output_path':'outputs/comparison.json'});c=compared['data']
        check('before after comparison succeeds',compared['status']=='ok')
        check('scope and settings comparable',c['settings_equal'] and c['occurrence_scope_equal'])
        check('changed or no longer observed findings identified',bool(c['findings']['changed_ids'] or c['findings']['no_longer_observed_ids']))
        check('remaining findings retained',bool(c['findings']['still_observed_ids']))
        check('no physical resolution asserted',not c['resolved_findings_asserted'] and not c['mechanically_verified'])
        check('candidate details remain traceable',bool(c['before_candidates']) and bool(c['after_candidates']))
        check('all original input files unchanged',all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in before.items()))
        bad=copy.deepcopy(e);bad.pop('output_path',None);bad['guards_passed']=False
        (fixture/'outputs/forged.json').write_text(json.dumps(bad),encoding='utf-8')
        rejected=call('cad_reintegrate_evidence',{'execution_path':'outputs/forged.json','output_path':'outputs/rejected.json'})
        check('forged receipt rejected',rejected['status']=='error' and rejected['errors'][0]['code']=='EVIDENCE_MISMATCH')
        occupied=call('cad_reintegrate_evidence',{'execution_path':'outputs/run.json','output_path':'outputs/updated.json'})
        check('existing report never overwritten',occupied['errors'][0]['code']=='OUTPUT_EXISTS')
        call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','output_path':'outputs/dirty-plan.json'})
        app.ActiveDoc.dirty=True
        dirty=run_plan(service,'outputs/dirty-plan.json','outputs/dirty-run.json')
        check('changed document stops before capture',not dirty['data']['guards_passed'] and dirty['data']['summary']['calls_executed']==1)
        blocked=call('cad_reintegrate_evidence',{'execution_path':'outputs/dirty-run.json','output_path':'outputs/dirty-update.json'})
        check('failed guards prevent reintegration',blocked['errors'][0]['code']=='EXECUTION_GUARDS_FAILED')
        app.ActiveDoc.dirty=False
        call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','output_path':'outputs/timeout-plan.json'})
        attempts=[]
        def timeout(name,args):attempts.append(name);return failure(ToolFailure('TIMEOUT','Explicit synthetic timeout'))
        timed=execute_task(fixture,timeout,'outputs/timeout-plan.json','outputs/timeout-run.json');save('timeout.response.json',timed)
        check('timeout halts without retry',len(attempts)==1 and timed['data']['execution_complete'] and not timed['data']['guards_passed'])
        check('service recovers from rejected offline input',call('cad_list_mechanism_templates',{})['status']=='ok')
    finally:service.close()
    report={'passed':all(c['passed'] for c in checks),'checks':checks,'calls':calls,'synthetic_backend':True,
            'requires_human_review':False,'limitations':['Executed CAD calls used an explicit test backend, not user SolidWorks.',
            'Only compatible complete captures are reintegrated; constraints/faces may remain supplemental.',
            'Guards and hashes do not certify atomic geometry, physical joints, motion or disassembly.']}
    save('report.json',report);return report,dest/'report.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    try:
        report,path=run(Path.cwd(),args.output)
        print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'report':str(path)},ensure_ascii=False))
        raise SystemExit(0 if report['passed'] else 1)
    except (RuntimeError,OSError,ValueError,KeyError,AssertionError) as exc:parser.exit(2,f'{exc}\n')
