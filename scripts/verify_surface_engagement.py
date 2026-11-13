"""0.30 synthetic surface inspection acceptance; preserves original evidence and receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cadkin.tools.engagement import replay_engagement
from tests.engagement_fakes import engagement_fixture
from tests.geometry_connection_fakes import run_batch


def run(root,output):
    root=root.resolve();dest=(root/output).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a fresh outputs/ directory.')
    dest.mkdir(parents=True,exist_ok=False);checks=[];cases=[]
    def check(name,value):checks.append({'name':name,'passed':bool(value)})
    for mode in ('complete','half_circle','same_orientation','normal_failure','adjacency_failure'):
        base=dest/mode;service,app,faces=engagement_fixture(base,inner=mode!='same_orientation')
        if mode=='half_circle':
            original_projection=faces[1].GetClosestPointOn
            faces[1].GetClosestPointOn=lambda x,y,z:original_projection(x,max(0,y),z)
        if mode=='normal_failure':faces[1].surface.normal_failure=True
        if mode=='adjacency_failure':
            def unavailable():raise RuntimeError('Explicit synthetic unavailable edge adjacency')
            faces[1].edges[0].GetTwoAdjacentFaces2=unavailable
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        calls=[];original=service.worker.call
        def cad(name,args):calls.append(name);return original(name,args)
        def call(name,**args):
            r=service.call(name,args);assert r['status']!='error',r;return r
        try:
            with patch.object(service.worker,'call',side_effect=cad):
                first=call('cad_analyze_surface_engagement',finite_analysis_path='outputs/finite.json',output_path='outputs/engagement.json')
                check(mode+' offline analysis',not calls);check(mode+' compact response','pairs' not in first['data'])
                plan=call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',engagement_analysis_path='outputs/engagement.json',output_path='outputs/plan.json')['data']
                check(mode+' four targeted captures',plan['summary']['planned_capture_tasks']==4)
                check(mode+' six guards retained',plan['summary']['guard_tasks']==6 and len(plan['tasks'])==10)
                check(mode+' plan does not execute',plan['executed'] is False and not calls)
                receipt=run_batch(service,'outputs/plan.json','inspection')
                index=call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/index.json')['data']
                call('cad_analyze_surface_engagement',finite_analysis_path='outputs/finite.json',evidence_index_path='outputs/index.json',output_path='outputs/after.json')
                d,_=replay_engagement(base,'outputs/after.json');pair=d['pairs'][0];support=pair['sampled_support']
                check(mode+' shared history',d['rounds_completed']==2 and index['rounds_completed']==2)
                check(mode+' exactly two sample calls',calls.count('sw_sample_cylinder_face')==2)
                check(mode+' exactly two adjacency calls',calls.count('sw_read_face_adjacency')==2)
                check(mode+' failed attempts retained',index['summary']['retained_unsuccessful_attempts']==(1 if mode.endswith('failure') else 0))
                expected=10 if mode=='half_circle' else 0 if mode in ('same_orientation','normal_failure') else 16
                check(mode+' correct sampled complementary count',support['opposite_solid_side_queries']==expected)
                check(mode+' no continuous coverage claim',not support['continuous_angular_coverage_proven'])
                check(mode+' adjacency independently evaluated',[len(x) for x in pair['adjacent_axial_planes']]==[2,0 if mode=='adjacency_failure' else 2])
                check(mode+' seams excluded and planes deduplicated',len(pair['opposed_adjacent_plane_candidates'])==(0 if mode=='adjacency_failure' else 2))
                check(mode+' joint unknown',pair['target_joint_kind']=='unknown' and pair['target_degrees_of_freedom'] is None)
                check(mode+' no motion or stop invention',pair['motion_limits_mm'] is None and not pair['retention_confirmed'] and not pair['physical_engagement_confirmed'])
                check(mode+' no human gate',not d['requires_human_review'])
                count=len(calls)
                stop=call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',engagement_analysis_path='outputs/after.json',output_path='outputs/stop.json')['data']
                check(mode+' no repeated capture',stop['tasks']==[] and len(calls)==count)
                check(mode+' only bounded reads',set(calls)<={'sw_sample_cylinder_face','sw_read_face_adjacency','sw_active_document','sw_component_spatial'})
                check(mode+' sources unchanged',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items()))
                cases.append({'mode':mode,'analysis_path':str(base/'outputs/after.json'),'cad_calls':calls})
        finally:service.close()
    data={'version':'0.30.0','scope':'Explicit synthetic CAD with production guarded execution, indexing and replay. Not live SolidWorks or lift motion acceptance.',
        'checks':checks,'cases':cases,'passed':all(c['passed'] for c in checks)}
    path=dest/'report.json';path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':data['passed'],'checks':len(checks),'report':str(path)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    r=run(Path.cwd(),p.parse_args().output);print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['passed'] else 1)
