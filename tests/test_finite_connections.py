import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from cadkin.errors import ToolFailure,failure
from cadkin.finite_geometry import compare_boundaries,project_boundary
from cadkin.tools.face_boundaries import validate_boundary
from cadkin.tools.finite_connections import replay_finite_analysis,end_context
from cadkin.tools.followup import replay_plan
from tests.geometry_connection_fakes import run_batch
from tests.finite_connection_fakes import finite_fixture,Edge


class FiniteConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.service,self.app,self.face=finite_fixture(self.root)
    def tearDown(self):self.service.close();self.tmp.cleanup()
    def read(self,name):return json.loads((self.root/name).read_text())
    def call(self,name,**args):
        r=self.service.call(name,args);self.assertNotEqual(r['status'],'error',r);return r
    def analyze(self,name='outputs/finite.json',**extra):
        return self.call('cad_analyze_finite_connections',geometry_analysis_path='outputs/geometry.json',output_path=name,**extra)
    def plan(self,name='outputs/plan.json',analysis='outputs/finite.json',**extra):
        return self.call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',finite_analysis_path=analysis,output_path=name,**extra)
    def capture(self):
        self.analyze();self.plan();receipt=run_batch(self.service,'outputs/plan.json','boundaries')
        self.call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/index.json')
        self.analyze('outputs/after.json',evidence_index_path='outputs/index.json')
        return replay_finite_analysis(self.root,'outputs/after.json')[0]
    def boundary(self):
        token=self.read('outputs/target.json')['document']['document_token']
        raw=self.call('sw_read_face_boundary',expected_document_token=token,face={'face_inventory_path':'faces0.json','body_index':0,'face_index':2})
        return validate_boundary(self.root,raw)

    def test_guarded_capture_ranges_index_and_no_retry(self):
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        report=self.capture();row=report['pairs'][0];c=row['comparison']
        self.assertEqual(report['coverage']['pairs_with_finite_ranges'],1)
        self.assertEqual(c['assessment'],'axial_enclosures_overlap');self.assertEqual(c['signed_interval_overlap_mm'],1000)
        self.assertEqual(c['target_joint_kind'],'unknown');self.assertIsNone(c['motion_limits_mm']);self.assertFalse(c['physical_engagement_confirmed'])
        plan,*_=replay_plan(self.root,'outputs/plan.json');self.assertEqual(len(plan['tasks']),8)
        self.assertEqual(plan['summary']['guard_tasks'],6)
        stop=self.plan('outputs/stop.json','outputs/after.json')
        self.assertEqual(stop['data']['tasks'],[]);self.assertEqual(stop['data']['continuation']['rounds_completed'],1)
        self.assertTrue(all(p.read_bytes() and hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items()))

    def test_capture_is_read_only_and_analytic_not_bbox_or_mesh(self):
        self.face.GetTessTriangles=lambda:(_ for _ in ()).throw(AssertionError('mesh must not be read'))
        self.face.GetBox=lambda:(_ for _ in ()).throw(AssertionError('box must not be read'))
        d=self.boundary();self.assertTrue(d['complete']);self.assertEqual(d['reported_edge_count'],3)
        self.assertEqual([e['curve_kind'] for e in d['edges']],['circle','circle','line'])
        self.assertFalse(d['solidworks_modified'])

    def test_projection_separation_endpoint_and_overlap(self):
        a=self.boundary();b=copy.deepcopy(a)
        b['source']['target']['transform']['to_root'][2][3]=2
        c=compare_boundaries(a,b,.1,.1);self.assertEqual(c['assessment'],'axially_separated_face_enclosures');self.assertEqual(c['axial_gap_mm'],1000)
        b['source']['target']['transform']['to_root'][2][3]=1
        self.assertEqual(compare_boundaries(a,b,.1,.1)['assessment'],'axial_endpoint_near_tolerance')
        b['source']['target']['transform']['to_root'][2][3]=.4
        self.assertAlmostEqual(compare_boundaries(a,b,.1,.1)['signed_interval_overlap_mm'],600)

    def test_rigid_transform_and_axis_sign_preserve_overlap(self):
        a=self.boundary();b=copy.deepcopy(a);b['source']['target']['transform']['to_root'][2][3]=.4
        expected=compare_boundaries(a,b,.1,.1)['signed_interval_overlap_mm']
        for d,z in [(a,0),(b,.4)]:
            d['source']['target']['transform']['to_root']=[[0,0,1,2+z],[0,1,0,3],[-1,0,0,4],[0,0,0,1]]
            d['source']['face']['descriptor']['surface_parameters_part'][3:6]=[0,0,-1]
        self.assertAlmostEqual(compare_boundaries(a,b,.1,.1)['signed_interval_overlap_mm'],expected)

    def test_scale_and_radius_difference_are_not_fit_clearance(self):
        a=self.boundary();b=copy.deepcopy(a)
        for d in (a,b):d['source']['target']['transform']['to_root']=[[-2,0,0,0],[0,-2,0,0],[0,0,-2,0],[0,0,0,1]]
        b['source']['face']['descriptor']['surface_parameters_part'][-1]=.011
        c=compare_boundaries(a,b,.1,.1);self.assertEqual(c['signed_interval_overlap_mm'],2000)
        self.assertAlmostEqual(c['radius_difference_mm'],2);self.assertNotIn('fit_clearance_mm',c)

    def test_tilted_circle_uses_conservative_full_circle_enclosure(self):
        d=self.boundary();p=project_boundary(d,[.01,0,1],[0,0,0])
        self.assertEqual(p['circular_arc_enclosures'],[0,1]);self.assertLess(p['interval_mm'][0],0)
        self.assertFalse(p['trimmed_angular_coverage_known'])

    def test_unsupported_edges_partial_and_budget_preserved_no_retry(self):
        self.face.edges[0]=Edge('spline')
        report=self.capture();self.assertEqual(report['coverage']['pairs_with_finite_ranges'],0)
        index=self.read('outputs/index.json');self.assertEqual(index['summary']['retained_unsuccessful_attempts'],2)
        stop=self.plan('outputs/stop.json','outputs/after.json');self.assertEqual(stop['data']['tasks'],[])
        self.assertEqual(report['pairs'][0]['comparison']['assessment'],'finite_extent_unavailable')

    def test_edge_budget_partial_does_not_produce_projection(self):
        token=self.read('outputs/target.json')['document']['document_token']
        raw=self.call('sw_read_face_boundary',expected_document_token=token,face={'face_inventory_path':'faces0.json','body_index':0,'face_index':2},max_edges=1)
        self.assertEqual(raw['status'],'partial');d=validate_boundary(self.root,raw)
        self.assertIsNone(project_boundary(d,[0,0,1],[0,0,0])['interval_mm'])

    def test_boundary_changes_and_count_mismatch_fail(self):
        self.face.GetEdgeCount=lambda:99
        token=self.read('outputs/target.json')['document']['document_token']
        args={'expected_document_token':token,'face':{'face_inventory_path':'faces0.json','body_index':0,'face_index':2}}
        r=self.service.call('sw_read_face_boundary',args);self.assertEqual(r['errors'][0]['code'],'BOUNDARY_TOPOLOGY_UNAVAILABLE')
        self.face.GetEdgeCount=lambda:len(self.face.edges);calls=[]
        def changing():
            calls.append(1)
            if len(calls)==2:self.face.edges[0].CircleParams[2]=.1
            return self.face.edges
        self.face.GetEdges=changing
        r=self.service.call('sw_read_face_boundary',args);self.assertEqual(r['errors'][0]['code'],'GEOMETRY_CHANGED')

    def test_failed_capture_retained_without_retry(self):
        self.analyze();self.plan();original=self.service.worker.call
        def fail(name,args):return failure(ToolFailure('API_ERROR','Synthetic missing boundary')) if name=='sw_read_face_boundary' else original(name,args)
        with patch.object(self.service.worker,'call',side_effect=fail):receipt=run_batch(self.service,'outputs/plan.json','failed')
        self.call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/index.json')
        self.analyze('outputs/after.json',evidence_index_path='outputs/index.json')
        self.assertEqual(self.plan('outputs/stop.json','outputs/after.json')['data']['tasks'],[])

    def test_budget_and_new_index_require_new_analysis(self):
        self.capture()
        r=self.service.call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','finite_analysis_path':'outputs/finite.json',
            'evidence_index_path':'outputs/index.json','output_path':'outputs/stale.json'})
        self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')
        # A budget below the cost of even one guarded face capture cannot drop guards.
        self.assertEqual(self.plan('outputs/budget.json',max_tasks=4)['data']['tasks'],[])

    def test_derived_and_raw_tampering_rejected(self):
        self.capture();path=self.root/'outputs/after.json';d=self.read('outputs/after.json');d['pairs'][0]['comparison']['motion_limits_mm']=[0,100]
        path.write_text(json.dumps(d))
        with self.assertRaises(ToolFailure):replay_finite_analysis(self.root,'outputs/after.json')
        self.analyze('outputs/clean.json',evidence_index_path='outputs/index.json')
        boundary=Path(self.read('outputs/clean.json')['pairs'][0]['boundary_sources'][0][0]['path'])
        boundary.write_text(boundary.read_text()+'\n')
        with self.assertRaises(ToolFailure):replay_finite_analysis(self.root,'outputs/clean.json')

    def test_distance_catalog_probe_history_and_fourth_round_budget(self):
        from tests.geometry_connection_fakes import geometry_fixture
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);service,app=geometry_fixture(root)
            face=app.ActiveDoc.root.children[0].model_doc.bodies[0].faces[2]
            face.edges=[Edge(z=0),Edge(z=1),Edge('line')]
            face.GetEdges=lambda:face.edges;face.GetEdgeCount=lambda:len(face.edges)
            def call(tool,**args):
                r=service.call(tool,args);self.assertNotEqual(r['status'],'error',r);return r
            try:
                call('cad_analyze_geometric_connections',target_graph_path='outputs/target.json',distance_tolerance_mm=.1,
                    angle_tolerance_deg=.1,output_path='outputs/geometry.json')
                call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',geometry_analysis_path='outputs/geometry.json',output_path='outputs/distance-plan.json')
                index=None
                for stage in ('distance','catalogs','probes'):
                    plan=f'outputs/{stage}-plan.json'
                    if index:
                        call('cad_plan_face_probes',draft_check_path='outputs/check.json',evidence_index_path=index,
                            max_component_gap_mm=.1,surface_tolerance_mm=.1,max_face_pairs=4,output_path=plan)
                    receipt=run_batch(service,plan,stage);index=f'outputs/{stage}-index.json'
                    call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path=index)
                call('cad_analyze_finite_connections',geometry_analysis_path='outputs/geometry.json',evidence_index_path=index,output_path='outputs/finite.json')
                p=call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',finite_analysis_path='outputs/finite.json',max_tasks=5,output_path='outputs/boundary-plan.json')
                self.assertEqual(p['data']['continuation']['rounds_completed'],3)
                self.assertEqual(p['data']['summary']['planned_capture_tasks'],1)
                receipt=run_batch(service,'outputs/boundary-plan.json','boundary')
                call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/four-index.json')
                call('cad_analyze_finite_connections',geometry_analysis_path='outputs/geometry.json',evidence_index_path='outputs/four-index.json',output_path='outputs/after.json')
                p=call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',finite_analysis_path='outputs/after.json',output_path='outputs/stop.json')
                self.assertEqual(p['data']['tasks'],[]);self.assertEqual(p['data']['continuation']['rounds_completed'],4)
                self.assertEqual(p['data']['blocked_requests'][0]['reason'],'ROUND_LIMIT')
            finally:service.close()

    def test_changed_pose_invalidates_entire_boundary_batch(self):
        self.analyze();self.plan();original=self.service.worker.call
        def moved(name,args):
            r=original(name,args)
            if name=='sw_read_face_boundary':self.app.ActiveDoc.root.children[0].Transform2.ArrayData[9]+=.01
            return r
        with patch.object(self.service.worker,'call',side_effect=moved):
            r=self.call('sw_execute_evidence_batch',plan_path='outputs/plan.json',output_path='outputs/moved.json',time_budget_seconds=60)
        self.assertFalse(r['data']['guards_passed'])
        r=self.service.call('cad_index_evidence',{'draft_check_path':'outputs/check.json','execution_path':r['data']['execution_source']['path'],'output_path':'outputs/invalid.json'})
        self.assertEqual(r['errors'][0]['code'],'EXECUTION_GUARDS_FAILED')

    def test_local_axial_plane_context_never_assigns_travel(self):
        probe={'surface_types':['plane','plane'],'review_state':'near_face_contact_candidate','converged':True,'source':{'path':'p'},'complete':True,
            'metrics':{'normal_left_root_unit':[0,0,1],'normal_right_root_unit':[0,0,-1],'point_left_root_mm':[0,0,1],
                       'point_right_root_mm':[0,0,1.02],'gap_mm':.02}}
        rows=end_context([probe],[0,0,1],[0,0,0],[[1,100]],.1,.1)
        self.assertTrue(rows[0]['near_any_cylinder_interval_endpoint']);self.assertIsNone(rows[0]['travel_limit_mm']);self.assertFalse(rows[0]['retention_confirmed'])
        probe['metrics']['normal_left_root_unit']=[1,0,0]
        self.assertEqual(end_context([probe],[0,0,1],[0,0,0],[[1,100]],.1,.1),[])

    def test_offline_cli_output_protection_and_solver_isolation(self):
        with patch.object(self.service.worker,'call') as cad:
            self.analyze();cad.assert_not_called()
        r=self.service.call('cad_analyze_finite_connections',{'geometry_analysis_path':'outputs/geometry.json','output_path':'outputs/finite.json'})
        self.assertEqual(r['errors'][0]['code'],'OUTPUT_EXISTS')
        p=subprocess.run([sys.executable,'-m','cadkin','plan-evidence','outputs/check.json','--finite-analysis','outputs/finite.json',
            '--output','outputs/cli-plan.json'],cwd=self.root,capture_output=True,text=True,timeout=120)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['data']['algorithm_version'],7)
        r=self.service.call('cad_solve_chain_constraints',{'constraint_analysis_path':'outputs/finite.json','output_path':'outputs/no-solution.json',
            'reference_occurrence_path':'base-1','characteristic_length_mm':100})
        self.assertEqual(r['errors'][0]['code'],'INVALID_CONSTRAINT_SOURCE')


if __name__=='__main__':unittest.main()
