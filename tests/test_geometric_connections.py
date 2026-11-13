import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cadkin.errors import ToolFailure,failure
from cadkin.geometric_connections import analyze
from cadkin.tools.geometric_connections import replay_geometry_analysis
from cadkin.tools.followup import replay_plan
from cadkin.tools.observation_index import replay_index
from tests.geometry_connection_fakes import geometry_fixture,run_batch


class GeometricConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.service,self.app=geometry_fixture(self.root)
    def tearDown(self):self.service.close();self.tmp.cleanup()
    def read(self,path):return json.loads((self.root/path).read_text(encoding='utf-8'))
    def analysis(self,output='outputs/geometry.json',**extra):
        return self.service.call('cad_analyze_geometric_connections',{'target_graph_path':'outputs/target.json',
            'distance_tolerance_mm':.1,'angle_tolerance_deg':.1,'output_path':output,**extra})
    def plan(self,analysis='outputs/geometry.json',output='outputs/geometry-plan.json',**extra):
        return self.service.call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json',
            'geometry_analysis_path':analysis,'output_path':output,**extra})
    def indexed(self,plan='outputs/geometry-plan.json',prefix='distance'):
        receipt=run_batch(self.service,plan,prefix)
        r=self.service.call('cad_index_evidence',{'draft_check_path':'outputs/check.json','execution_path':receipt,'output_path':f'outputs/{prefix}-index.json'})
        self.assertNotEqual(r['status'],'error',r)
        return f'outputs/{prefix}-index.json'

    def test_coaxial_alternatives_without_template_or_mate_sources(self):
        with patch.object(self.service.worker,'call') as cad:
            r=self.analysis();self.assertEqual(r['status'],'partial',r);cad.assert_not_called()
        d,b=replay_geometry_analysis(self.root,'outputs/geometry.json');p=d['pairs'][0]
        kinds={a['candidate_kind'] for a in p['alternatives']}
        self.assertTrue({'fixed','revolute','prismatic','cylindrical','no_direct_joint','other_relationship'}<=kinds)
        self.assertEqual(p['native_mate_context'],[]);self.assertIsNone(p['target_degrees_of_freedom'])
        self.assertFalse(d['constraint_equations_created']);self.assertFalse(d['template_search_requested'])
        self.assertNotIn('pairs',r['data']);self.assertEqual(r['data']['analysis_source'],b)
        self.assertFalse(any(Path(x['path']).name=='mates.json' for x in d['input_files']))

    def test_duplicate_cylinder_faces_do_not_become_multiple_guides(self):
        target=self.read('outputs/target.json');original=copy.deepcopy(target)
        target['pairs'][0]['axis_relations']*=3
        facts={'distances':{},'face_observations':{}}
        one=analyze(original,facts,.1,.1)['pairs'][0];many=analyze(target,facts,.1,.1)['pairs'][0]
        self.assertEqual(one['alternatives'],many['alternatives'])
        self.assertEqual(many['patterns'][0]['distinct_lines'],1)
        self.assertEqual(many['patterns'][0]['observation_count'],3)

    def test_loose_source_alignment_does_not_bypass_stricter_report_tolerance(self):
        target=self.read('outputs/target.json')
        d=analyze(target,{'distances':{},'face_observations':{}},.01,.1)['pairs'][0]
        self.assertEqual(d['alternatives'],[])
        self.assertEqual(d['patterns'][0]['kind'],'axis_alignment_outside_analysis_tolerance')
        self.assertIn('SOURCE_AXIS_TOLERANCES_DIFFER',[f['code'] for f in d['flags']])

    def test_offset_guides_have_conditional_not_proven_conflicts(self):
        target=self.read('outputs/target.json');p=target['pairs'][0]
        row=copy.deepcopy(p['axis_relations'][0]);row['candidate_index']+=100
        for side in ('left','right'):row[side]['origin_m'][0]+=.01
        p['axis_relations'].append(row)
        d=analyze(target,{'distances':{},'face_observations':{}},.1,.1)['pairs'][0]
        self.assertEqual(d['patterns'][0]['kind'],'multiple_parallel_coaxial_lines')
        r=next(a for a in d['alternatives'] if a['candidate_kind']=='revolute')
        self.assertEqual(len(r['conditional_conflicts']),1);self.assertFalse(r['confirmed'])
        self.assertFalse(d['connection_confirmed'])

    def test_axis_direction_sign_and_origin_shift_do_not_change_line_geometry(self):
        target=self.read('outputs/target.json');changed=copy.deepcopy(target)
        for r in changed['pairs'][0]['axis_relations']:
            for side in ('left','right'):
                r[side]['origin_m']=[p+3*d for p,d in zip(r[side]['origin_m'],r[side]['axis_unit'])]
                r[side]['axis_unit']=[-x for x in r[side]['axis_unit']]
        facts={'distances':{},'face_observations':{}}
        a=analyze(target,facts,.1,.1)['pairs'][0];b=analyze(changed,facts,.1,.1)['pairs'][0]
        self.assertEqual(a['patterns'],b['patterns']);self.assertEqual(a['alternatives'],b['alternatives'])

    def test_plan_distance_capture_index_and_stop_without_rescan(self):
        self.analysis();r=self.plan();self.assertEqual(r['status'],'ok',r)
        p,_,_,_=replay_plan(self.root,'outputs/geometry-plan.json')
        self.assertEqual(p['algorithm_version'],6);self.assertEqual(len(p['tasks']),7)
        self.assertEqual([t['tool'] for t in p['tasks'] if t['phase']=='capture'],['sw_component_distance'])
        index=self.indexed();self.assertEqual(self.analysis('outputs/after.json',evidence_index_path=index)['status'],'partial')
        a,_=replay_geometry_analysis(self.root,'outputs/after.json')
        self.assertEqual(a['rounds_completed'],1);self.assertAlmostEqual(a['pairs'][0]['distance_observations'][0]['distance_mm'],.05)
        r=self.plan('outputs/after.json','outputs/stop.json');self.assertNotEqual(r['status'],'error',r)
        self.assertEqual(r['data']['tasks'],[])
        self.assertIn('cad_plan_face_probes',[x['next_tool'] for x in r['data']['unresolved_findings']])
        with patch.object(self.service.worker,'call') as cad:
            blocked=self.service.call('sw_execute_evidence_batch',{'plan_path':'outputs/stop.json','output_path':'outputs/blocked.json'})
            self.assertEqual(blocked['errors'][0]['code'],'NO_CAPTURE_TASKS');cad.assert_not_called()

    def test_plan_budget_never_drops_guards(self):
        self.analysis();r=self.plan(max_tasks=6)
        self.assertEqual(r['data']['tasks'],[]);self.assertEqual(r['data']['continuation']['reason'],'CAPTURE_BUDGET_UNAVAILABLE')
        self.assertEqual(r['data']['summary']['deferred_capture_tasks'],1)

    def test_distance_to_face_catalogs_and_probes_reuses_three_rounds(self):
        self.analysis();self.plan();index=self.indexed()
        for name in ('catalogs','probes'):
            plan=f'outputs/{name}-plan.json'
            r=self.service.call('cad_plan_face_probes',{'draft_check_path':'outputs/check.json','evidence_index_path':index,
                'max_component_gap_mm':.1,'surface_tolerance_mm':.1,'max_face_pairs':4,'output_path':plan})
            self.assertNotEqual(r['status'],'error',r)
            wanted='sw_component_faces' if name=='catalogs' else 'sw_probe_face_pair'
            self.assertTrue(all(t['tool']==wanted for t in r['data']['tasks'] if t['phase']=='capture'))
            index=self.indexed(plan,name)
        r=self.analysis('outputs/with-probes.json',evidence_index_path=index);self.assertNotEqual(r['status'],'error',r)
        d,_=replay_geometry_analysis(self.root,'outputs/with-probes.json')
        self.assertEqual(d['rounds_completed'],3)
        self.assertTrue(any(p['kind']=='opposed_planar_samples' for p in d['pairs'][0]['patterns']))
        self.assertEqual(len(d['pairs'][0]['face_observations']),4)
        i,_=replay_index(self.root,index)
        self.assertEqual(sum(o['tool']=='sw_component_distance' for o in i['observations']),1)
        self.assertEqual(sum(o['tool']=='sw_component_faces' for o in i['observations']),2)
        stop=self.service.call('cad_plan_face_probes',{'draft_check_path':'outputs/check.json','evidence_index_path':index,
            'max_component_gap_mm':.1,'surface_tolerance_mm':.1,'max_face_pairs':4,'output_path':'outputs/face-stop.json'})
        self.assertEqual(stop['data']['tasks'],[])
        self.assertFalse(d['physical_joint_types_determined'])

    def test_four_round_limit_and_failed_postguard(self):
        self.analysis();d,_=replay_geometry_analysis(self.root,'outputs/geometry.json')
        from cadkin.followup.geometry_planning import plan_geometry_tasks
        limited=plan_geometry_tasks(self.read('outputs/target.json'),self.read('outputs/check.json'),d,
            {'rounds_completed':4,'observations':[]},self.root/'outputs/unused',20)
        self.assertEqual(limited['tasks'],[]);self.assertEqual(limited['continuation']['reason'],'ROUND_LIMIT')
        self.plan();original=self.service.worker.call
        def moved(name,args):
            r=original(name,args)
            if name=='sw_component_distance':self.app.ActiveDoc.root.children[0].Transform2.ArrayData[9]+=.01
            return r
        with patch.object(self.service.worker,'call',side_effect=moved):
            batch=self.service.call('sw_execute_evidence_batch',{'plan_path':'outputs/geometry-plan.json','output_path':'outputs/moved.json','time_budget_seconds':60})
        self.assertFalse(batch['data']['guards_passed'])
        r=self.service.call('cad_index_evidence',{'draft_check_path':'outputs/check.json',
            'execution_path':batch['data']['execution_source']['path'],'output_path':'outputs/bad-index.json'})
        self.assertEqual(r['errors'][0]['code'],'EXECUTION_GUARDS_FAILED')

    def test_failed_distance_retained_and_not_retried(self):
        self.analysis();self.plan();original=self.service.worker.call;calls=[]
        def fail(name,args):
            calls.append(name)
            return failure(ToolFailure('API_ERROR','Synthetic distance unavailable')) if name=='sw_component_distance' else original(name,args)
        with patch.object(self.service.worker,'call',side_effect=fail):index=self.indexed()
        self.analysis('outputs/after.json',evidence_index_path=index)
        r=self.plan('outputs/after.json','outputs/stopped.json')
        self.assertEqual(r['data']['tasks'],[]);self.assertEqual(calls.count('sw_component_distance'),1)
        self.assertEqual(r['data']['blocked_requests'][0]['reason'],'PRIOR_DISTANCE_ATTEMPT_NO_AUTOMATIC_RETRY')
        i,_=replay_index(self.root,index);self.assertEqual(i['summary']['retained_unsuccessful_attempts'],1)

    def test_stale_index_and_conflicting_profiles_rejected(self):
        self.analysis();self.plan();index=self.indexed()
        r=self.plan(output='outputs/stale.json',evidence_index_path=index)
        self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')
        r=self.plan(output='outputs/conflict.json',initial_capture_profile='root_mates')
        self.assertEqual(r['errors'][0]['code'],'INVALID_ARGUMENTS')

    def test_plane_probes_are_conditional_and_different_scopes_remain_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            s,_=geometry_fixture(Path(directory),distances=True,faces=True)
            try:
                r=s.call('cad_analyze_geometric_connections',{'target_graph_path':'outputs/target.json','distance_tolerance_mm':.1,
                    'angle_tolerance_deg':.1,'output_path':'outputs/result.json'})
                self.assertNotEqual(r['status'],'error',r)
                d,_=replay_geometry_analysis(Path(directory),'outputs/result.json')
                p=d['pairs'][0];self.assertIn('opposed_planar_samples',[x['kind'] for x in p['patterns']])
                self.assertIn('planar',[x['candidate_kind'] for x in p['alternatives']])
                self.assertFalse(p['constraint_equations_created'])
                target=json.loads((Path(directory)/'outputs/target.json').read_text())
                from cadkin.tools.geometric_connections import geometry_facts
                facts=geometry_facts(Path(directory),target,None,.1,.1)
                facts['distances'][('base-1','carriage-1')][0]['distance_mm']=10
                p=analyze(target,facts,.1,.1)['pairs'][0]
                self.assertIn('ASSEMBLY_DISTANCE_VS_PART_FACE_SCOPE_DISAGREEMENT',[f['code'] for f in p['flags']])
            finally:s.close()

    def test_empty_geometry_and_parallel_only_do_not_imply_motion(self):
        target=self.read('outputs/target.json');p=target['pairs'][0]
        for r in p['axis_relations']:r['kind']='parallel_candidate'
        facts={'distances':{},'face_observations':{}}
        d=analyze(target,facts,.1,.1)['pairs'][0]
        self.assertEqual(d['alternatives'],[])
        p['axis_relations']=[];p['axis_relation_count']=0
        d=analyze(target,facts,.1,.1)['pairs'][0]
        self.assertEqual(d['assessment'],'insufficient_geometry');self.assertIsNone(d['target_degrees_of_freedom'])
        self.assertEqual(d['verification_gaps'][0]['action'],'source_gap')

    def test_limits_and_invalid_parameters(self):
        target=self.read('outputs/target.json');target['pairs'].append(copy.deepcopy(target['pairs'][0]));target['pairs'][-1]['id']='second'
        d=analyze(target,{'distances':{},'face_observations':{}},.1,.1,1)
        self.assertEqual(d['coverage']['omitted_pairs'],1)
        for extra in ({'max_pairs':0},{'distance_tolerance_mm':float('nan')},{'angle_tolerance_deg':0}):
            self.assertEqual(self.analysis(**extra)['errors'][0]['code'],'INVALID_ARGUMENTS')

    def test_derived_and_transitive_source_tampering_rejected(self):
        self.analysis();p=self.root/'outputs/geometry.json';d=self.read('outputs/geometry.json');d['pairs'][0]['target_joint_kind']='revolute';p.write_text(json.dumps(d))
        r=self.plan();self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')
        self.analysis('outputs/clean.json')
        with (self.root/'cylinder0.json').open('a') as f:f.write('\n')
        r=self.plan('outputs/clean.json');self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_output_protection_and_cli(self):
        self.analysis();self.assertEqual(self.analysis()['errors'][0]['code'],'OUTPUT_EXISTS')
        args={'target_graph_path':'outputs/target.json','distance_tolerance_mm':.1,'angle_tolerance_deg':.1,'output_path':'outputs/cli.json'}
        p=subprocess.run([sys.executable,'-m','cadkin','sw','cad_analyze_geometric_connections','--arguments',json.dumps(args)],cwd=self.root,capture_output=True,text=True,timeout=120)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['status'],'partial')
        p=subprocess.run([sys.executable,'-m','cadkin','plan-evidence','outputs/check.json','--geometry-analysis','outputs/cli.json','--output','outputs/cli-plan.json'],cwd=self.root,capture_output=True,text=True,timeout=120)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['data']['algorithm_version'],6)


if __name__=='__main__':unittest.main()
