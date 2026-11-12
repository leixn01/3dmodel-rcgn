"""Offline 0.16 acceptance with explicit fake CAD; plans do not execute production CAD calls."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jsonschema import Draft202012Validator
from cadkin.tools.solidworks import SolidWorksTools, CATALOG
from cadkin.followup.planning import READ_TOOLS
from tests.followup_fakes import write_draft_fixture


def run(root,destination):
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False)
    checks=[];calls=[]
    def save(name,data):
        with (dest/name).open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    fixture=dest/'synthetic-cad';write_draft_fixture(fixture,lambda r:SolidWorksTools(r))
    original={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.rglob('*.json')}
    def forbidden():raise AssertionError('Planning must not initialize SolidWorks')
    service=SolidWorksTools(fixture,factory=forbidden)
    def call(name,params,label):
        result=service.call(name,params);save(label+'.response.json',result)
        calls.append({'tool':name,'parameters':params,'status':result['status']});return result
    try:
        args={'joint_draft_path':'outputs/drafts.json','output_path':'outputs/check.json'}
        checked=call('cad_check_joint_draft',args,'check');data=checked['data']
        check('check output preserves known conflict as partial',checked['status']=='partial')
        check('membership and endpoints structurally valid',data['structural_checks_passed'])
        check('lock versus moving hypothesis identified',any(f['code']=='ACTIVE_LOCK_VS_MOVING_HYPOTHESIS' for f in data['findings']))
        check('physical correctness and human review not asserted',not data['physical_consistency_verified'] and not data['requires_human_review'])
        check('findings retain source and candidate location',bool(data['draft_source']['sha256']) and any(f['candidate_refs'] for f in data['findings']))
        params={'draft_check_path':'outputs/check.json','output_path':'outputs/plan.json'}
        planned=call('cad_plan_evidence_tasks',params,'plan');plan=planned['data']
        check('plan generation succeeds',planned['status']=='ok')
        check('concrete capture tasks are proposed',plan['summary']['planned_capture_tasks']>0)
        check('planning never executes calls',not plan['executed'] and all(not t['executed'] and not Path(t['save_envelope_path']).exists() for t in plan['tasks']))
        check('only allowlisted readonly tools',all(t['tool'] in READ_TOOLS and CATALOG[t['tool']]['annotations']['readOnlyHint'] for t in plan['tasks']))
        check('all arguments validate against production catalog',all(Draft202012Validator(CATALOG[t['tool']]['inputSchema']).is_valid(t['arguments']) for t in plan['tasks']))
        seen=set();valid=True
        for t in plan['tasks']:valid=valid and set(t['depends_on'])<=seen;seen.add(t['id'])
        check('dependency graph ordered without missing parents',valid)
        check('document and pose guards surround capture',plan['tasks'][0]['tool']=='sw_active_document' and plan['tasks'][-1]['tool']=='sw_active_document' and any(t['phase']=='postflight' and t['tool']=='sw_component_spatial' for t in plan['tasks']))
        check('all guard calls included in budget',len(plan['tasks'])==plan['summary']['total_tool_calls']<=20)
        check('freshness and mismatch policy explicit','Never replace tokens' in plan['execution_policy']['on_document_or_pose_mismatch'])
        check('complete known evidence reused',bool(plan['reused_evidence']))
        check('unknown physics and manual face choices remain explicit',bool(plan['unresolved_findings']) and not any(t['tool']=='sw_probe_face_pair' for t in plan['tasks']))
        check('raw captures and source bindings preserved',all(t['save_envelope_path'].endswith('.json') for t in plan['tasks']) and bool(plan['check_source']['sha256']))
        small=call('cad_plan_evidence_tasks',{**params,'output_path':'outputs/small-plan.json','max_tasks':3},'small-plan')
        check('insufficient budget defers whole guarded task',small['status']=='partial' and small['data']['summary']['planned_capture_tasks']==0 and bool(small['data']['deferred_tasks']))
        cut=call('cad_check_joint_draft',{**args,'output_path':'outputs/cut-check.json','max_findings':1},'cut-check')
        check('finding limit preserves full count',cut['data']['output_truncated'] and cut['data']['summary']['findings_found']>1)
        cutplan=call('cad_plan_evidence_tasks',{**params,'draft_check_path':'outputs/cut-check.json','output_path':'outputs/cut-plan.json'},'cut-plan')
        check('check truncation propagated to plan',cutplan['status']=='partial' and cutplan['data']['check_output_truncated'])
        tampered=copy.deepcopy(data);tampered.pop('output_path',None);tampered['findings']=[]
        (fixture/'outputs/tampered.json').write_text(json.dumps(tampered),encoding='utf-8')
        bad=call('cad_plan_evidence_tasks',{**params,'draft_check_path':'outputs/tampered.json','output_path':'outputs/bad-plan.json'},'tampered')
        check('removed findings rejected',bad['status']=='error' and bad['errors'][0]['code']=='EVIDENCE_MISMATCH')
        again=call('cad_plan_evidence_tasks',params,'overwrite')
        check('existing output not overwritten',again['status']=='error' and again['errors'][0]['code']=='OUTPUT_EXISTS')
        check('service remains usable',call('cad_list_mechanism_templates',{},'recovery')['status']=='ok')
        check('original source files unchanged',all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in original.items()))
    finally:service.close()
    report={'passed':all(c['passed'] for c in checks),'checks':checks,'calls':calls,'requires_human_review':False,
        'purpose':'Synthetic source-replayed consistency checks and task planning, not live lift verification.',
        'limitations':['No real SolidWorks calls were executed; generating a plan is not evidence collection.',
            'Structural correctness does not prove rigidity, DOF, stroke or collision-free motion.',
            'Plan guards require agent validation at execution; automatic capture runner and evidence reintegration are not provided.']}
    save('report.json',report);return report,dest/'report.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    try:
        report,path=run(Path.cwd(),args.output)
        print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'report':str(path)},ensure_ascii=False))
        sys.exit(0 if report['passed'] else 1)
    except (OSError,ValueError,KeyError) as exc:parser.exit(2,f'Acceptance could not finish: {exc}\n')
