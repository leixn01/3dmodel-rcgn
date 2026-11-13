"""0.28 conditional geometry and guarded follow-up acceptance; synthetic CAD only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from cadkin.errors import ToolFailure,failure
from cadkin.tools.geometric_connections import replay_geometry_analysis
from cadkin.tools.observation_index import replay_index
from tests.geometry_connection_fakes import geometry_fixture,run_batch


def run(root,output):
    root=root.resolve();dest=(root/output).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a fresh directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False)
    checks,cases=[],[]
    def check(name,value):checks.append({'name':name,'passed':bool(value)})
    for mode in ('geometry_only','known_faces_and_distance','failed_distance'):
        base=dest/mode;service,_=geometry_fixture(base,distances=mode=='known_faces_and_distance',faces=mode=='known_faces_and_distance')
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        calls=[];original=service.worker.call
        def cad(name,args):
            calls.append(name)
            if mode=='failed_distance' and name=='sw_component_distance':return failure(ToolFailure('API_ERROR','Synthetic failure'))
            return original(name,args)
        def call(name,args):
            result=service.call(name,args)
            assert result['status']!='error',result
            return result
        def analyze(name,index=None):
            args={'target_graph_path':'outputs/target.json','distance_tolerance_mm':.1,'angle_tolerance_deg':.1,'output_path':name}
            if index:args['evidence_index_path']=index
            return call('cad_analyze_geometric_connections',args)
        def plan(name,analysis):
            return call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','geometry_analysis_path':analysis,'output_path':name})
        def index(plan_path,prefix):
            receipt=run_batch(service,plan_path,prefix)
            path=f'outputs/{prefix}-index.json'
            call('cad_index_evidence',{'draft_check_path':'outputs/check.json','execution_path':receipt,'output_path':path})
            return path
        try:
            with patch.object(service.worker,'call',side_effect=cad):
                response=analyze('outputs/geometry.json');first,_=replay_geometry_analysis(base,'outputs/geometry.json')
                check(mode+' analysis makes no CAD calls',calls==[])
                check(mode+' response is compact','pairs' not in response['data'] and response['data']['detail_saved'])
                kinds={x['candidate_kind'] for x in first['pairs'][0]['alternatives']}
                check(mode+' coaxial geometry retains alternatives',{'revolute','prismatic','cylindrical','fixed','no_direct_joint'}<=kinds)
                check(mode+' no native mate or template inference',not first['template_search_requested'] and not first['pairs'][0]['native_mate_context'])
                planned=plan('outputs/plan.json','outputs/geometry.json')['data']
                if mode=='known_faces_and_distance':
                    check('existing distance is reused',planned['tasks']==[] and calls==[])
                    check('source-bound planes have planar alternative','planar' in kinds)
                    check('plane samples not converted into constraints',not first['constraint_equations_created'])
                    latest=first;latest_path='outputs/geometry.json'
                else:
                    check(mode+' seven guarded calls',len(planned['tasks'])==7 and planned['summary']['guard_tasks']==6)
                    check(mode+' only one distance requested',[t['tool'] for t in planned['tasks'] if t['phase']=='capture']==['sw_component_distance'])
                    latest_index=index('outputs/plan.json','distance')
                    analyze('outputs/after-distance.json',latest_index)
                    stopped=plan('outputs/distance-stop.json','outputs/after-distance.json')['data']
                    check(mode+' distance not repeated',stopped['tasks']==[] and calls.count('sw_component_distance')==1)
                    indexed,_=replay_index(base,latest_index)
                    check(mode+' first round retained',indexed['rounds_completed']==1)
                    if mode=='failed_distance':
                        check('failed distance remains unsuccessful',indexed['summary']['retained_unsuccessful_attempts']==1)
                        check('failure blocks automatic retry',stopped['blocked_requests'][0]['reason']=='PRIOR_DISTANCE_ATTEMPT_NO_AUTOMATIC_RETRY')
                        latest_path='outputs/after-distance.json'
                    else:
                        check('face verification handoff is explicit',any(x['next_tool']=='cad_plan_face_probes' for x in stopped['unresolved_findings']))
                        for phase in ('catalogs','probes'):
                            path=f'outputs/{phase}-plan.json'
                            p=call('cad_plan_face_probes',{'draft_check_path':'outputs/check.json','evidence_index_path':latest_index,
                                'max_component_gap_mm':.1,'surface_tolerance_mm':.1,'max_face_pairs':4,'output_path':path})['data']
                            check(phase+' preserves prior history',p['continuation']['rounds_completed']==(1 if phase=='catalogs' else 2))
                            latest_index=index(path,phase)
                        analyze('outputs/after-probes.json',latest_index)
                        latest_path='outputs/after-probes.json'
                        indexed,_=replay_index(base,latest_index)
                        check('three rounds share the same history',indexed['rounds_completed']==3 and len(indexed['execution_sources'])==3)
                        check('face catalogs collected once each',calls.count('sw_component_faces')==2)
                        check('four candidate face pairs measured',calls.count('sw_probe_face_pair')==4)
                        final_plan=call('cad_plan_face_probes',{'draft_check_path':'outputs/check.json','evidence_index_path':latest_index,
                            'max_component_gap_mm':.1,'surface_tolerance_mm':.1,'max_face_pairs':4,'output_path':'outputs/face-stop.json'})['data']
                        check('already probed faces are not repeated',final_plan['tasks']==[])
                    latest,_=replay_geometry_analysis(base,latest_path)
                check(mode+' final type and DOF stay unknown',all(p['target_joint_kind']=='unknown' and p['target_degrees_of_freedom'] is None for p in latest['pairs']))
                check(mode+' no motion or human gate',not latest['finite_motion_verified'] and not latest['requires_human_review'])
                check(mode+' all original files preserved',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items()))
                check(mode+' no body rescan or CAD edit',set(calls)<={'sw_active_document','sw_component_spatial','sw_component_distance','sw_component_faces','sw_probe_face_pair'})
                cases.append({'mode':mode,'analysis_path':str(base/latest_path),'cad_calls':calls})
        finally:service.close()
    report={'version':'0.28.0','scope':'Explicit synthetic CAD with production analysis/planning/execution. Not real lift motion recognition or SolidWorks acceptance.',
        'checks':checks,'cases':cases,'passed':all(c['passed'] for c in checks)}
    path=dest/'report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':report['passed'],'checks':len(checks),'report':str(path)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    result=run(Path.cwd(),p.parse_args().output);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
