import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cadkin.errors import ToolFailure
from cadkin.geometry import transform_from_sw
from cadkin.planar_regions import region_from_loops,compare_regions,disk_intersection
from cadkin.adapters.planar_faces import read_loops
from cadkin.tools.planar_contacts import replay_planar_contacts
from cadkin.tools.planar_sources import validate_planar_capture
from cadkin.tools.followup import replay_plan
from tests.planar_fakes import planar_fixture,planar_document,CircleEdge,LineEdge,Loop
from tests.geometry_connection_fakes import run_batch
from tests.sw_fakes import pose


def planar_data(mode='disk',side=0):
    doc,_,_=planar_document(mode);face=doc.root.children[side].model_doc.bodies[0].faces[3]
    from cadkin.adapters.faces import read_descriptor
    shape=read_descriptor(face);loops,_,_,_=read_loops(face,8,64)
    return {'source':{'target':{'transform':transform_from_sw(pose().ArrayData)},'face':{'descriptor':shape}},
        'loops':loops,'region':region_from_loops(shape,loops)}


class PlanarMathTests(unittest.TestCase):
    def test_disk_area_and_hole_exclusion(self):
        a,b=planar_data('disk',0),planar_data('disk',1)
        r=compare_regions(a,b,.1);self.assertAlmostEqual(r['projected_overlap_area_mm2'],math.pi*400)
        a,b=planar_data('hole_gap',0),planar_data('hole_gap',1)
        r=compare_regions(a,b,.1);self.assertEqual(r['projected_overlap_area_mm2'],0)
        self.assertEqual(r['assessment'],'no_resolved_positive_area');self.assertIsNone(r['hypothetical_closing_direction_right_wrt_left'])

    def test_annulus_area_subtracts_hole(self):
        r=compare_regions(planar_data('annulus',0),planar_data('annulus',1),.1)
        self.assertAlmostEqual(r['projected_overlap_area_mm2'],math.pi*300)

    def test_circle_intersection_known_lens_tangent_contained(self):
        self.assertAlmostEqual(disk_intersection(1,1,1),2*math.pi/3-math.sqrt(3)/2)
        self.assertEqual(disk_intersection(1,1,2),0);self.assertEqual(disk_intersection(1,1,3),0)
        self.assertAlmostEqual(disk_intersection(2,1,.5),math.pi)

    def test_polygon_clipping_disjoint_touch_and_overlap(self):
        a,b=planar_data('polygon',0),planar_data('polygon',1)
        for offset,expected in ((0,1600),(.02,800),(.04,0),(.05,0)):
            b['source']['target']['transform']=transform_from_sw(pose(x=offset).ArrayData)
            self.assertAlmostEqual(compare_regions(a,b,.1)['projected_overlap_area_mm2'],expected)

    def test_tiny_sliver_below_closure_margin_not_positive_evidence(self):
        a,b=planar_data('polygon',0),planar_data('polygon',1)
        b['source']['target']['transform']=transform_from_sw(pose(x=.04-1e-10).ArrayData)
        r=compare_regions(a,b,.1)
        self.assertGreater(r['projected_overlap_area_mm2'],0)
        self.assertLess(r['projected_overlap_area_mm2'],r['resolved_area_threshold_mm2'])
        self.assertEqual(r['assessment'],'no_resolved_positive_area')
        self.assertIsNone(r['hypothetical_closing_direction_right_wrt_left'])

    def test_unordered_reversed_edges_reconstruct(self):
        d=planar_data('polygon');edges=d['loops'][0]['edges'];edges[0]['start_point_part_m'],edges[0]['end_point_part_m']=edges[0]['end_point_part_m'],edges[0]['start_point_part_m']
        d['loops'][0]['edges']=[edges[i] for i in (2,0,3,1)]
        self.assertAlmostEqual(region_from_loops(d['source']['face']['descriptor'],d['loops'])['area_part_m2'],.0016)

    def test_loop_budget_retains_partial_prefix(self):
        doc,_,_=planar_document('polygon');face=doc.root.children[0].model_doc.bodies[0].faces[3]
        loops,count,truncated,errors=read_loops(face,8,3)
        self.assertEqual(count,1);self.assertTrue(truncated);self.assertEqual(len(loops[0]['edges']),3)
        self.assertEqual(errors[0]['code'],'PLANAR_EDGE_LIMIT')

    def test_arc_area_mismatch_and_nonconcentric_hole_rejected(self):
        for mode in ('arc','area','offcenter'):
            d=planar_data('annulus');shape=d['source']['face']['descriptor']
            if mode=='arc':d['loops'][0]['edges'][0]['u_max']=math.pi
            elif mode=='area':shape['area_part_m2']*=2
            else:d['loops'][1]['edges'][0]['circle_parameters_part'][0]=.001
            with self.assertRaises(ToolFailure):region_from_loops(shape,d['loops'])

    def test_concave_self_intersecting_open_loops_rejected(self):
        d=planar_data('polygon');shape=d['source']['face']['descriptor']
        for points in ([[-.02,-.02,0],[.02,-.02,0],[0,0,0],[.02,.02,0],[-.02,.02,0]],
            [[-.02,-.02,0],[.02,.02,0],[.02,-.02,0],[-.02,.02,0]]):
            loops=[{'is_outer':True,'errors':[],'edges':[{'kind':'line','start_point_part_m':a,'end_point_part_m':b} for a,b in zip(points,points[1:]+points[:1])]}]
            with self.assertRaises(ToolFailure):region_from_loops(shape,loops)
        d['loops'][0]['edges'][0]['start_point_part_m'][0]+=.001
        with self.assertRaises(ToolFailure):region_from_loops(shape,d['loops'])

    def test_gap_direction_negative_gap_and_mixed_shapes(self):
        a,b=planar_data('disk',0),planar_data('disk',1)
        # Left cap normal -Z, so right moving +Z closes a positive signed gap.
        for z,expected in ((-.00005,'opposed_regions_near_tolerance'),(-.001,'opposed_regions_separated'),(.001,'negative_oriented_plane_gap')):
            b['source']['target']['transform']=transform_from_sw(pose(z=z).ArrayData)
            r=compare_regions(a,b,.1);self.assertEqual(r['assessment'],expected)
            self.assertEqual(r['hypothetical_closing_direction_right_wrt_left'],None if z>0 else [-0.,-0.,1.])
            self.assertFalse(r['contact_confirmed']);self.assertFalse(r['retention_confirmed']);self.assertIsNone(r['motion_limits_mm'])
        self.assertIsNone(compare_regions(a,planar_data('polygon',1),.1)['projected_overlap_area_mm2'])

    def test_transform_scale_rotation_and_tilt_guard(self):
        a,b=planar_data('annulus',0),planar_data('annulus',1)
        for d in (a,b):d['source']['target']['transform']['to_root']=[[0,0,-2,4],[0,2,0,5],[2,0,0,6],[0,0,0,1]]
        self.assertAlmostEqual(compare_regions(a,b,.1)['projected_overlap_area_mm2'],math.pi*1200)
        b['source']['face']['descriptor']['surface_parameters_part'][:3]=[0,.001,1]
        self.assertIsNone(compare_regions(a,b,.1)['projected_overlap_area_mm2'])


class PlanarWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.service,self.app=planar_fixture(self.root)
    def tearDown(self):self.service.close();self.tmp.cleanup()
    def read(self,name):return json.loads((self.root/name).read_text())
    def call(self,tool,**args):
        r=self.service.call(tool,args);self.assertNotEqual(r['status'],'error',r);return r
    def analyze(self,name='outputs/planar.json',**args):
        return self.call('cad_analyze_planar_contacts',engagement_analysis_path='outputs/engagement.json',output_path=name,**args)
    def plan(self,name='outputs/planar-plan.json',report='outputs/planar.json',**args):
        return self.call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',planar_analysis_path=report,output_path=name,**args)
    def capture(self):
        self.analyze();self.plan();receipt=run_batch(self.service,'outputs/planar-plan.json','planar')
        self.call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/planar-index.json')
        self.analyze('outputs/after.json',evidence_index_path='outputs/planar-index.json');return replay_planar_contacts(self.root,'outputs/after.json')[0]
    def capture_args(self):
        self.analyze();self.plan();p,*_=replay_plan(self.root,'outputs/planar-plan.json')
        return next(t['arguments'] for t in p['tasks'] if t['phase']=='capture')

    def test_guarded_regions_and_no_retry(self):
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        d=self.capture();self.assertEqual(d['coverage']['near_opposed_region_pairs'],2);self.assertEqual(d['rounds_completed'],3)
        p=self.read('outputs/planar-plan.json');self.assertEqual(len(p['tasks']),10);self.assertEqual(p['summary']['guard_tasks'],6)
        self.assertEqual(self.plan('outputs/stop.json','outputs/after.json')['data']['tasks'],[])
        for p,h in before.items():self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),h)

    def test_failed_loop_read_retained_without_retry(self):
        def fail():raise RuntimeError('Synthetic loop read failure')
        self.app.ActiveDoc.root.children[1].model_doc.bodies[0].faces[3].GetLoops=fail
        d=self.capture();self.assertEqual(d['coverage']['compared_pairs'],1)
        self.assertEqual(self.read('outputs/planar-index.json')['summary']['retained_unsuccessful_attempts'],1)
        self.assertEqual(self.plan('outputs/stop.json','outputs/after.json')['data']['tasks'],[])

    def test_changed_topology_rejected(self):
        args=self.capture_args();path=self.read(args['adjacency_path'])['data']['source']['target']['occurrence_path']
        face=next(c for c in self.app.ActiveDoc.root.children[:2] if c.Name2==path).model_doc.bodies[0].faces[3]
        # Change a referenced neighbor descriptor, invalidating the entire original adjacency.
        face.area*=2
        r=self.service.call('sw_read_planar_face',args);self.assertEqual(r['status'],'error')

    def test_raw_region_tamper_rejected(self):
        args=self.capture_args();r=self.call('sw_read_planar_face',**args);validate_planar_capture(self.root,r)
        r['data']['region']['outer_radius_m']*=2
        with self.assertRaises(ToolFailure):validate_planar_capture(self.root,r)

    def test_report_tamper_and_stale_index_rejected(self):
        self.capture()
        r=self.service.call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','planar_analysis_path':'outputs/planar.json',
            'evidence_index_path':'outputs/planar-index.json','output_path':'outputs/stale.json'})
        self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')
        p=self.root/'outputs/after.json';d=self.read(p);d['pairs'][0]['comparison']['contact_confirmed']=True;p.write_text(json.dumps(d))
        with self.assertRaises(ToolFailure):replay_planar_contacts(self.root,str(p))

    def test_four_rounds_stops_remaining_regions(self):
        self.analyze();report='outputs/planar.json'
        for i in range(2):
            plan=f'outputs/plan-{i}.json';self.plan(plan,report,max_tasks=5);receipt=run_batch(self.service,plan,f'limited-{i}')
            index=f'outputs/index-{i}.json';self.call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path=index)
            report=f'outputs/report-{i}.json';self.analyze(report,evidence_index_path=index)
        p=self.plan('outputs/stop.json',report)['data'];self.assertEqual(p['tasks'],[])
        self.assertEqual(p['continuation']['rounds_completed'],4);self.assertTrue(all(r['reason']=='ROUND_LIMIT' for r in p['blocked_requests']))

    def test_offline_limits_and_profile_isolation(self):
        with patch.object(self.service.worker,'call',side_effect=AssertionError('No CAD for offline tools')):
            r=self.analyze(max_plane_pairs=1);self.assertEqual(r['status'],'partial')
            p=self.plan(max_tasks=4)['data'];self.assertEqual(p['tasks'],[])
        r=self.service.call('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','planar_analysis_path':'outputs/planar.json',
            'engagement_analysis_path':'outputs/engagement.json','output_path':'outputs/invalid.json'})
        self.assertEqual(r['errors'][0]['code'],'INVALID_ARGUMENTS')

    def test_invalid_face_reference_and_budget_do_not_call_com(self):
        args=self.capture_args()
        for extra in ({'max_loops':0},{'face_reference':{**args['face_reference'],'id':'AQM='}}):
            with patch.object(self.service.worker,'call',side_effect=AssertionError('No CAD for invalid sources')):
                r=self.service.call('sw_read_planar_face',{**args,**extra})
            self.assertEqual(r['status'],'error')
