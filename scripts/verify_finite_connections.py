"""0.29 synthetic finite-boundary acceptance with persisted original evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cadkin.errors import ToolFailure,failure
from cadkin.finite_geometry import compare_boundaries
from cadkin.tools.finite_connections import replay_finite_analysis
from cadkin.tools.face_boundaries import validate_boundary
from tests.finite_connection_fakes import finite_fixture,Edge
from tests.geometry_connection_fakes import run_batch


def run(root,output):
    root=root.resolve();dest=(root/output).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a fresh outputs/ directory.')
    dest.mkdir(parents=True,exist_ok=False);checks=[];cases=[]
    def check(name,value):checks.append({'name':name,'passed':bool(value)})
    for mode in ('complete','unsupported','failed'):
        base=dest/mode;service,app,face=finite_fixture(base)
        if mode=='unsupported':face.edges[0]=Edge('spline')
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        calls=[];original=service.worker.call
        def cad(name,args):
            calls.append(name)
            if mode=='failed' and name=='sw_read_face_boundary':return failure(ToolFailure('API_ERROR','Synthetic boundary failure'))
            return original(name,args)
        def call(name,**args):
            r=service.call(name,args);assert r['status']!='error',r;return r
        try:
            with patch.object(service.worker,'call',side_effect=cad):
                first=call('cad_analyze_finite_connections',geometry_analysis_path='outputs/geometry.json',output_path='outputs/finite.json')
                check(mode+' offline analysis',calls==[])
                check(mode+' compact response','pairs' not in first['data'])
                plan=call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',finite_analysis_path='outputs/finite.json',output_path='outputs/plan.json')['data']
                check(mode+' two source-bound boundary captures',plan['summary']['planned_capture_tasks']==2)
                check(mode+' all six guards preserved',plan['summary']['guard_tasks']==6 and len(plan['tasks'])==8)
                check(mode+' immutable plan not executed',plan['executed'] is False)
                receipt=run_batch(service,'outputs/plan.json','boundary')
                index=call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/index.json')['data']
                call('cad_analyze_finite_connections',geometry_analysis_path='outputs/geometry.json',evidence_index_path='outputs/index.json',output_path='outputs/after.json')
                report,_=replay_finite_analysis(base,'outputs/after.json');row=report['pairs'][0]
                check(mode+' shared history retained',report['rounds_completed']==1 and index['rounds_completed']==1)
                check(mode+' exactly two boundary calls',calls.count('sw_read_face_boundary')==2)
                if mode=='complete':
                    check('complete analytic axial overlap',row['comparison']['signed_interval_overlap_mm']==1000)
                    check('complete interval enclosure state',row['comparison']['assessment']=='axial_enclosures_overlap')
                    boundaries=[validate_boundary(base,json.loads(Path(v[0]['path']).read_text())) for v in row['boundary_sources']]
                    import copy
                    moved=copy.deepcopy(boundaries[1]);moved['source']['target']['transform']['to_root'][2][3]=2
                    pure=compare_boundaries(boundaries[0],moved,.1,.1)
                    check('separated analytic projection',pure['assessment']=='axially_separated_face_enclosures' and pure['axial_gap_mm']==1000)
                    moved['source']['target']['transform']['to_root'][2][3]=1
                    check('endpoint proximity is not a motion limit',compare_boundaries(boundaries[0],moved,.1,.1)['assessment']=='axial_endpoint_near_tolerance')
                else:
                    check(mode+' no fabricated interval',row['comparison']['signed_interval_overlap_mm'] is None)
                    check(mode+' unsuccessful observations retained',index['summary']['retained_unsuccessful_attempts']==2)
                stop=call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',finite_analysis_path='outputs/after.json',output_path='outputs/stop.json')['data']
                check(mode+' prior attempts not repeated',stop['tasks']==[] and stop['summary']['planned_capture_tasks']==0)
                check(mode+' target remains unknown',row['comparison']['target_joint_kind']=='unknown' and row['comparison']['target_degrees_of_freedom'] is None)
                check(mode+' stroke and retention not invented',row['comparison']['motion_limits_mm'] is None and not row['comparison']['physical_engagement_confirmed'])
                check(mode+' no human gate or motion claim',not report['requires_human_review'] and not report['finite_motion_verified'])
                check(mode+' no rescan or CAD edits',set(calls)<={'sw_read_face_boundary','sw_active_document','sw_component_spatial'})
                check(mode+' original files unchanged',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items()))
                cases.append({'mode':mode,'analysis_path':str(base/'outputs/after.json'),'cad_calls':calls})
        finally:service.close()
    report={'version':'0.29.0','scope':'Explicit synthetic CAD, production guarded capture and offline replay. Not live SolidWorks or lift motion acceptance.',
            'checks':checks,'cases':cases,'passed':all(c['passed'] for c in checks)}
    path=dest/'report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':report['passed'],'checks':len(checks),'report':str(path)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    result=run(Path.cwd(),p.parse_args().output);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
