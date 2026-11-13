import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cadkin.errors import ToolFailure,failure
from cadkin.tools.engagement import replay_engagement
from cadkin.tools.engagement_sources import validate_engagement_capture
from cadkin.tools.followup import replay_plan
from tests.engagement_fakes import engagement_fixture
from tests.geometry_connection_fakes import run_batch


class EngagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.service,self.app,self.faces=engagement_fixture(self.root)
    def tearDown(self):self.service.close();self.tmp.cleanup()
    def read(self,path):return json.loads((self.root/path).read_text())
    def call(self,name,**args):
        r=self.service.call(name,args);self.assertNotEqual(r['status'],'error',r);return r
    def analyze(self,path='outputs/engagement.json',**args):
        return self.call('cad_analyze_surface_engagement',finite_analysis_path='outputs/finite.json',output_path=path,**args)
    def plan(self,path='outputs/inspection-plan.json',report='outputs/engagement.json',**args):
        return self.call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',engagement_analysis_path=report,output_path=path,**args)
    def capture(self):
        self.analyze();self.plan();receipt=run_batch(self.service,'outputs/inspection-plan.json','inspect')
        self.call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/inspection-index.json')
        self.analyze('outputs/after.json',evidence_index_path='outputs/inspection-index.json')
        return replay_engagement(self.root,'outputs/after.json')[0]
    def source_args(self,side=0):
        self.analyze();d=self.read('outputs/engagement.json');face=d['faces'][side]
        return {'expected_document_token':d['document']['document_token'],'boundary_path':face['boundary_sources'][0]['path']}

    def test_guarded_samples_adjacency_index_and_stop(self):
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        d=self.capture();pair=d['pairs'][0]
        self.assertEqual(d['rounds_completed'],2)
        self.assertEqual(pair['sampled_support']['opposite_solid_side_queries'],16)
        self.assertEqual([len(p) for p in pair['adjacent_axial_planes']],[2,2])
        self.assertEqual(len(pair['opposed_adjacent_plane_candidates']),2)
        self.assertEqual(pair['target_joint_kind'],'unknown');self.assertIsNone(pair['target_degrees_of_freedom'])
        self.assertIsNone(pair['motion_limits_mm']);self.assertFalse(pair['retention_confirmed'])
        self.assertFalse(pair['sampled_support']['continuous_angular_coverage_proven'])
        plan,*_=replay_plan(self.root,'outputs/inspection-plan.json')
        self.assertEqual(len(plan['tasks']),10);self.assertEqual(plan['summary']['guard_tasks'],6)
        self.assertEqual(len({t['arguments']['boundary_path'] for t in plan['tasks'] if t['phase']=='capture'}),2)
        self.assertEqual(self.plan('outputs/stop.json','outputs/after.json')['data']['tasks'],[])
        for p,h in hashes.items():self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),h)

    def test_partial_angular_face_is_not_full_circle(self):
        face=self.faces[1];original=face.GetClosestPointOn
        def half(x,y,z):return original(x,max(0,y),z)
        face.GetClosestPointOn=half
        d=self.capture();support=d['pairs'][0]['sampled_support']
        self.assertEqual(support['paired_queries_observed'],16)
        self.assertEqual(support['both_query_memberships'],10)
        self.assertFalse(support['continuous_angular_coverage_proven'])

    def test_same_orientation_no_inner_outer_support(self):
        self.service.close()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);service,app,faces=engagement_fixture(root,inner=False)
            old=self.root,self.service;self.root,self.service=root,service
            try:d=self.capture();self.assertEqual(d['coverage']['pairs_with_sampled_support'],0)
            finally:service.close();self.root,self.service=old

    def test_failed_normal_retained_adjacency_independent_no_retry(self):
        self.faces[1].surface.normal_failure=True
        d=self.capture();self.assertEqual(d['coverage']['pairs_with_sampled_support'],0)
        self.assertEqual(len(d['pairs'][0]['adjacent_axial_planes'][1]),2)
        self.assertEqual(self.read('outputs/inspection-index.json')['summary']['retained_unsuccessful_attempts'],1)
        self.assertEqual(self.plan('outputs/stop.json','outputs/after.json')['data']['tasks'],[])

    def test_null_and_seam_not_end_planes(self):
        face=self.faces[0];face.edges[0].GetTwoAdjacentFaces2=lambda:[face,None]
        d=self.capture();self.assertEqual(len(d['pairs'][0]['adjacent_axial_planes'][0]),1)

    def test_raw_sampling_metrics_tamper_rejected(self):
        args=self.source_args();r=self.call('sw_sample_cylinder_face',**args,query_points_root_mm=[[10,0,500]],membership_tolerance_mm=.01)
        self.assertTrue(validate_engagement_capture(self.root,r)['complete'])
        r['data']['samples'][0]['metrics']['solid_surface_side']='inner'
        with self.assertRaises(ToolFailure):validate_engagement_capture(self.root,r)

    def test_boundary_geometry_change_rejected(self):
        args=self.source_args();self.faces[0].edges[0].CircleParams[2]=.2
        r=self.service.call('sw_read_face_adjacency',args)
        self.assertEqual(r['status'],'error');self.assertEqual(r['errors'][0]['code'],'GEOMETRY_CHANGED')

    def test_adjacency_wrong_body_halts_batch(self):
        self.analyze();self.plan();face=self.faces[0];other=self.faces[1]
        face.edges[0].GetTwoAdjacentFaces2=lambda:[face,other]
        r=self.call('sw_execute_evidence_batch',plan_path='outputs/inspection-plan.json',output_path='outputs/failed.json',time_budget_seconds=60)
        self.assertFalse(r['data']['guards_passed']);self.assertEqual(r['data']['summary']['eligible_captures'],0)

    def test_low_budget_preserves_guards(self):
        self.analyze();p=self.plan(max_tasks=4)['data'];self.assertEqual(p['tasks'],[])
        p=self.plan('outputs/one.json',max_tasks=5)['data']
        self.assertEqual(p['summary']['planned_capture_tasks'],1);self.assertEqual(p['summary']['guard_tasks'],4)

    def test_report_and_plan_tamper_rejected(self):
        self.analyze();self.plan();p=self.root/'outputs/engagement.json';d=self.read(p);d['pairs'][0]['target_joint_kind']='revolute';p.write_text(json.dumps(d))
        with self.assertRaises(ToolFailure):replay_engagement(self.root,str(p))
        with self.assertRaises(ToolFailure):replay_plan(self.root,'outputs/inspection-plan.json')

    def test_latest_index_requires_reanalysis(self):
        self.capture()
        r=self.service.call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','engagement_analysis_path':'outputs/engagement.json',
            'evidence_index_path':'outputs/inspection-index.json','output_path':'outputs/stale.json'})
        self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_offline_no_worker_or_solver_calls(self):
        with patch.object(self.service.worker,'call',side_effect=AssertionError('No COM in offline analysis')):
            self.analyze();self.plan()
        self.assertEqual(self.read('outputs/inspection-plan.json')['algorithm_version'],8)

    def test_invalid_arguments_no_com(self):
        args=self.source_args()
        for extra in ({'query_points_root_mm':[],'membership_tolerance_mm':.01},
            {'query_points_root_mm':[[10,0,500]]*33,'membership_tolerance_mm':.01},
            {'query_points_root_mm':[[10,0,500]],'membership_tolerance_mm':1}):
            with patch.object(self.service.worker,'call',side_effect=AssertionError('No COM on invalid input')):
                r=self.service.call('sw_sample_cylinder_face',{**args,**extra})
            self.assertEqual(r['errors'][0]['code'],'INVALID_ARGUMENTS')

    def test_separate_profiles_rejected(self):
        self.analyze()
        r=self.service.call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','engagement_analysis_path':'outputs/engagement.json',
            'finite_analysis_path':'outputs/finite.json','output_path':'outputs/invalid.json'})
        self.assertEqual(r['errors'][0]['code'],'INVALID_ARGUMENTS')

    def test_limited_adjacency_keeps_partial(self):
        args=self.source_args();r=self.call('sw_read_face_adjacency',**args,max_edges=1)
        self.assertEqual(r['status'],'partial');self.assertTrue(validate_engagement_capture(self.root,r)['truncated'])

    def test_shared_four_round_limit_even_with_missing_inspection(self):
        self.analyze();report='outputs/engagement.json'
        for n in range(3):
            plan=f'outputs/limited-plan-{n}.json';self.plan(plan,report,max_tasks=5)
            receipt=run_batch(self.service,plan,f'limited-{n}')
            index=f'outputs/limited-index-{n}.json'
            self.call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path=index)
            report=f'outputs/limited-report-{n}.json';self.analyze(report,evidence_index_path=index)
        p=self.plan('outputs/stop.json',report)['data']
        self.assertEqual(p['tasks'],[]);self.assertEqual(p['continuation']['rounds_completed'],4)
        self.assertTrue(any(r['reason']=='ROUND_LIMIT' for r in p['blocked_requests']))

    def test_sheet_normals_do_not_determine_material_side(self):
        from cadkin.engagement import sample_metrics
        args=self.source_args();raw=self.call('sw_sample_cylinder_face',**args,query_points_root_mm=[[10,0,500]],membership_tolerance_mm=.01)
        d=raw['data'];source=copy.deepcopy(d['source']);source['face']['descriptor']['body_type']=1
        r=d['samples'][0];m=sample_metrics(source,r['query_root_mm'],r['sample'],r['normal'],.01)
        self.assertEqual(m['solid_surface_side'],'sheet_orientation_only')

    def test_rigid_transform_and_grid_dedup_budget(self):
        from cadkin.engagement import sampling_grid,sample_metrics
        from cadkin.finite_geometry import compare_boundaries
        from cadkin.tools.finite_connections import replay_finite_analysis
        d,_=replay_finite_analysis(self.root,'outputs/finite.json');pair=copy.deepcopy(d['pairs'][0])
        boundaries=[json.loads(Path(v[0]['path']).read_text())['data'] for v in pair['boundary_sources']]
        for i,b in enumerate(boundaries):
            b['source']['target']['transform']['to_root']=[[0,0,2,4],[0,2,0,5],[-2,0,0,6-i*.0001],[0,0,0,1]]
        pair['face_sources']=[b['source'] for b in boundaries];pair['comparison']=compare_boundaries(*boundaries,.1,.1)
        grid=sampling_grid(pair);self.assertEqual(len(grid['points_root_mm'][0]),16)
        for side in range(2):
            for p in grid['points_root_mm'][side]:
                self.assertAlmostEqual(math.hypot(p[1]-5000,p[2]-(6000-side*.1)),20)
        self.analyze();report=self.read('outputs/engagement.json')
        self.assertTrue(all(len(f['query_points_root_mm'])==16 for f in report['faces']))

    def test_post_capture_pose_change_invalidates_batch(self):
        self.analyze();self.plan();original=self.service.worker.call
        def moved(name,args):
            r=original(name,args)
            if name=='sw_read_face_adjacency':self.app.ActiveDoc.root.children[0].Transform2.ArrayData[9]+=.01
            return r
        with patch.object(self.service.worker,'call',side_effect=moved):
            r=self.call('sw_execute_evidence_batch',plan_path='outputs/inspection-plan.json',output_path='outputs/moved.json',time_budget_seconds=60)
        self.assertFalse(r['data']['guards_passed']);self.assertEqual(r['data']['summary']['eligible_captures'],0)

    def test_adjacency_readback_change_rejected(self):
        args=self.source_args();face=self.faces[0];count=[]
        def changing():
            count.append(1);return [face,face.body.faces[3] if len(count)==1 else None]
        face.edges[0].GetTwoAdjacentFaces2=changing
        r=self.service.call('sw_read_face_adjacency',args);self.assertEqual(r['errors'][0]['code'],'GEOMETRY_CHANGED')
