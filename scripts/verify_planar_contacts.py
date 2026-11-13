"""0.31 finite planar region acceptance on explicit synthetic CAD fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cadkin.tools.planar_contacts import replay_planar_contacts
from tests.planar_fakes import planar_fixture
from tests.geometry_connection_fakes import run_batch


def run(root,output):
    root=root.resolve();dest=(root/output).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a fresh outputs/ directory.')
    dest.mkdir(parents=True,exist_ok=False);checks=[];cases=[]
    def check(name,condition):checks.append({'name':name,'passed':bool(condition)})
    for mode in ('disk','annulus','hole_gap','polygon','arc','failure'):
        base=dest/mode;service,app=planar_fixture(base,'disk' if mode=='failure' else mode)
        if mode=='failure':
            def fail():raise RuntimeError('Explicit synthetic loop read failure')
            app.ActiveDoc.root.children[1].model_doc.bodies[0].faces[3].GetLoops=fail
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        original=service.worker.call;calls=[]
        def cad(name,args):calls.append(name);return original(name,args)
        def call(tool,**args):
            r=service.call(tool,args);assert r['status']!='error',r;return r
        try:
            with patch.object(service.worker,'call',side_effect=cad):
                first=call('cad_analyze_planar_contacts',engagement_analysis_path='outputs/engagement.json',output_path='outputs/planar.json')
                check(mode+' offline compact analysis',not calls and 'pairs' not in first['data'])
                plan=call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',planar_analysis_path='outputs/planar.json',output_path='outputs/plan.json')['data']
                check(mode+' four bound region reads',plan['algorithm_version']==9 and plan['summary']['planned_capture_tasks']==4)
                check(mode+' guards retained',plan['summary']['guard_tasks']==6 and len(plan['tasks'])==10)
                receipt=run_batch(service,'outputs/plan.json','planar')
                index=call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/index.json')['data']
                call('cad_analyze_planar_contacts',engagement_analysis_path='outputs/engagement.json',evidence_index_path='outputs/index.json',output_path='outputs/after.json')
                d,_=replay_planar_contacts(base,'outputs/after.json');c=[p['comparison'] for p in d['pairs']]
                check(mode+' history retained',d['rounds_completed']==3 and index['rounds_completed']==3)
                check(mode+' one read per face',calls.count('sw_read_planar_face')==4)
                check(mode+' original failed observations retained',index['summary']['retained_unsuccessful_attempts']==(2 if mode=='arc' else 1 if mode=='failure' else 0))
                check(mode+' available comparisons',d['coverage']['compared_pairs']==(0 if mode=='arc' else 1 if mode=='failure' else 2))
                check(mode+' near-region count',d['coverage']['near_opposed_region_pairs']==(0 if mode in ('arc','hole_gap') else 1 if mode=='failure' else 2))
                if mode=='hole_gap':check('hole excludes contained small disk',all(x['projected_overlap_area_mm2']==0 and x['assessment']=='no_resolved_positive_area' for x in c))
                if mode=='arc':check('arcs never promoted to full disks',all(x is None for x in c))
                if mode=='annulus':check('annulus area excludes holes',all(900<x['projected_overlap_area_mm2']<950 for x in c))
                if mode=='polygon':check('polygon clipping preserves finite area',all(abs(x['projected_overlap_area_mm2']-1598)<1e-8 for x in c))
                check(mode+' no mechanical claims',all(x is None or (not x['contact_confirmed'] and not x['retention_confirmed'] and x['motion_limits_mm'] is None and x['target_joint_kind']=='unknown') for x in c))
                check(mode+' no human gate',not d['requires_human_review'])
                stop=call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',planar_analysis_path='outputs/after.json',output_path='outputs/stop.json')['data']
                check(mode+' attempted regions never repeated',stop['tasks']==[])
                check(mode+' bounded read-only calls',set(calls)<={'sw_read_planar_face','sw_active_document','sw_component_spatial'})
                check(mode+' input bytes unchanged',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items()))
                cases.append({'mode':mode,'analysis_path':str(base/'outputs/after.json'),'cad_calls':calls})
        finally:service.close()
    report={'version':'0.31.0','scope':'Explicit synthetic CAD, production bounded capture and replay. Not real SolidWorks or lift contact/motion acceptance.',
        'checks':checks,'cases':cases,'passed':all(c['passed'] for c in checks)}
    path=dest/'report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':report['passed'],'checks':len(checks),'report':str(path)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    r=run(Path.cwd(),p.parse_args().output);print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['passed'] else 1)
