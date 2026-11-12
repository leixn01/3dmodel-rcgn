import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.errors import ToolFailure
from cadkin.face_geometry import pair_metrics, classify, root_normal, point, part_point
from cadkin.geometry import transform_from_sw
from cadkin.tools.solidworks import SolidWorksTools
from tests.face_probe_fakes import probe_document
from tests.sw_fakes import runtime, pose, Component, Document


class FaceProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.doc, self.part, app = probe_document()
        self.service = SolidWorksTools(root=self.root, factory=lambda: SolidWorksAdapter(app=app,runtime=runtime()))
        self.addCleanup(self.service.close)
        self.token = self.service.call('sw_active_document')['data']['document_token']
        self.capture()

    def save(self, name, value):
        path=self.root/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_text(json.dumps(value),encoding='utf-8');return str(path)

    def capture(self):
        self.files=[]
        for index, child in enumerate(self.doc.root.children):
            result=self.service.call('sw_component_faces', {'expected_document_token':self.token,'occurrence_path':child.Name2})
            self.assertEqual(result['status'],'ok',result)
            self.files.append(self.save(f'face{index}.json',result))
        self.args={'expected_document_token':self.token,
            'left':{'face_inventory_path':self.files[0],'body_index':0,'face_index':0},
            'right':{'face_inventory_path':self.files[1],'body_index':0,'face_index':1},
            'seed_points_root_mm':[[0,500,500]]}

    def probe(self, **kwargs): return self.service.call('sw_probe_face_pair',{**self.args,**kwargs})
    def review(self, result, output='outputs/review.json', **kwargs):
        source=self.save('probe.json',result)
        return self.service.call('cad_review_face_contacts',{'probe_paths':[source],'output_path':output,
            'contact_tolerance_mm':.1,'angle_tolerance_deg':5,**kwargs})

    def test_catalog_persistent_identity_and_finite_metadata(self):
        envelope=json.loads(Path(self.files[0]).read_text());data=envelope['data']
        self.assertEqual(data['face_count'],3)
        self.assertEqual([r['descriptor']['surface_type'] for r in data['faces']],['plane','plane','cylinder'])
        self.assertTrue(all(r['face_reference']['id'] for r in data['faces']))
        self.assertFalse(data['assembly_instance_features_evaluated'])

    def test_pair_gap_oriented_normals_and_readonly(self):
        before=(self.doc.dirty,list(self.doc.SelectionManager.selected),self.doc.rebuilt)
        result=self.probe();self.assertEqual(result['status'],'ok',result)
        data=result['data'];m=data['samples'][0]['metrics']
        self.assertAlmostEqual(m['gap_mm'],.05)
        self.assertEqual(m['normal_left_root_unit'],[1,0,0]);self.assertEqual(m['normal_right_root_unit'],[-1,0,0])
        self.assertEqual(m['opposition_error_deg'],0);self.assertEqual(m['gap_alignment_error_deg'],[0,0])
        self.assertTrue(data['samples'][0]['converged']);self.assertFalse(data['global_minimum_proven'])
        self.assertEqual(before,(self.doc.dirty,self.doc.SelectionManager.selected,self.doc.rebuilt))
        reviewed=self.review(result);self.assertEqual(reviewed['status'],'ok',reviewed)
        self.assertEqual(reviewed['data']['counts']['near_face_contact_candidate'],1)
        self.assertFalse(reviewed['data']['contact_confirmed'])

    def test_finite_patch_not_extended_plane(self):
        self.doc.root.children[1].Transform2=pose(x=.00005,y=2);self.capture()
        result=self.probe();self.assertEqual(result['status'],'ok',result)
        gap=result['data']['samples'][0]['metrics']['gap_mm'];self.assertGreater(gap,999)
        review=self.review(result);self.assertEqual(review['data']['counts']['sample_gap_above_tolerance'],1)
        self.assertFalse(review['data']['global_minimum_proven'])

    def test_cylinder_queries_points_on_surface_not_axis(self):
        for side in ('left','right'):self.args[side]['face_index']=2
        result=self.probe(seed_points_root_mm=[[20,0,500]])
        self.assertEqual(result['status'],'ok',result)
        sample=result['data']['samples'][0]
        for side in ('left','right'):
            p=sample[side]['point_part_m'];self.assertAlmostEqual(math.hypot(*p[:2]),.01)
        self.assertEqual(self.review(result)['data']['counts']['near_points_orientation_unconfirmed'],1)

    def test_reverse_input_preserves_pair_gap_and_normal_ownership(self):
        original=self.probe()['data']['samples'][0]['metrics']
        reversed_result=self.probe(left=self.args['right'],right=self.args['left'])
        m=reversed_result['data']['samples'][0]['metrics']
        self.assertEqual(m['gap_mm'],original['gap_mm'])
        self.assertEqual(m['normal_left_root_unit'],original['normal_right_root_unit'])

    def test_rotation_translation_scale_and_nested_paths(self):
        self.doc.root.children[0].Name2='sub-1/plate-1';self.doc.root.children[1].Name2='sub-1/plate-2'
        self.doc.root.children[0].Transform2=pose(x=1,y=2,z=3,quarter_turn=True,scale=2)
        self.doc.root.children[1].Transform2=pose(x=1,y=2.00005,z=3,quarter_turn=True,scale=2)
        # A true parent node is inserted after sources capture to exercise real hierarchy lookup.
        children=list(self.doc.root.children);parent=Component('sub-1',children=children);parent.model_doc=Document(title='Sub')
        self.doc.root.children=[parent]
        self.files=[]
        for i,c in enumerate(children):
            result=self.service.call('sw_component_faces',{'expected_document_token':self.token,'occurrence_path':c.Name2})
            self.assertEqual(result['status'],'ok',result);self.files.append(self.save(f'nested{i}.json',result))
        for i,side in enumerate(('left','right')):self.args[side]['face_inventory_path']=self.files[i]
        result=self.probe(seed_points_root_mm=[[500,2000,3500]])
        self.assertEqual(result['status'],'ok',result);m=result['data']['samples'][0]['metrics']
        self.assertAlmostEqual(m['gap_mm'],.05);self.assertEqual(m['normal_left_root_unit'],[0,1,0])
        self.assertEqual(m['point_left_root_mm'],[500,2000,3500])

    def test_point_transform_roundtrip_reflection_and_normal(self):
        for scale in (2,-2):
            t=transform_from_sw(pose(x=3,y=4,z=5,quarter_turn=True,scale=scale).ArrayData)
            local=[.1,.2,.3];back=part_point(t,point(t['to_root'],local))
            for a,b in zip(back,local):self.assertAlmostEqual(a,b)
            self.assertEqual(root_normal(t,[1,0,0],False),[0,1 if scale>0 else -1,0])
            self.assertEqual(root_normal(t,[1,0,0],True),[0,-1 if scale>0 else 1,0])

    def test_failed_normal_preserves_points_not_fake_normal(self):
        self.part.bodies[0].faces[0].surface.normal_failure=True
        result=self.probe();self.assertEqual(result['status'],'partial',result)
        row=result['data']['samples'][0];self.assertIsNone(row['normal_left']);self.assertAlmostEqual(row['metrics']['gap_mm'],.05)
        review=self.review(result);self.assertEqual(review['status'],'partial',review)
        self.assertEqual(review['data']['counts']['near_points_orientation_unconfirmed'],1)

    def test_failed_projection_and_invalid_values_never_zero(self):
        face=self.part.bodies[0].faces[0];original=face.GetClosestPointOn
        for raw in (None,[0,0,0],[False,0,0,0,0],[float('nan'),0,0,0,0]):
            face.GetClosestPointOn=lambda *a:raw
            result=self.probe();self.assertEqual(result['status'],'partial',result)
            self.assertIsNone(result['data']['samples'][0]['metrics']);self.assertIsNone(result['data']['best_seed_index'])
        self.assertEqual(self.review(result)['data']['counts']['unresolved'],1)
        face.GetClosestPointOn=original;self.assertEqual(self.probe()['status'],'ok')

    def test_invalid_point_revalidation_not_on_face(self):
        face=self.part.bodies[0].faces[0];n=[0]
        def drift(*args):n[0]+=1;return [n[0],0,0,0,0]
        face.GetClosestPointOn=drift
        result=self.probe(max_iterations=2);self.assertEqual(result['status'],'partial',result)
        self.assertIsNone(result['data']['samples'][0]['metrics'])
        self.assertIn('FACE_POINT_NOT_ON_FACE',[e['code'] for e in result['errors']])

    def test_iteration_limit_keeps_valid_sample_and_partial(self):
        result=self.probe(max_iterations=1);self.assertEqual(result['status'],'partial',result)
        self.assertAlmostEqual(result['data']['samples'][0]['metrics']['gap_mm'],.05)
        self.assertFalse(result['data']['samples'][0]['converged'])
        self.assertEqual(self.review(result)['status'],'partial')

    def test_multiple_seeds_keep_failures_and_choose_usable(self):
        f=self.part.bodies[0].faces[0];original=f.GetClosestPointOn
        f.GetClosestPointOn=lambda x,y,z: None if y<0 else original(x,y,z)
        result=self.probe(seed_points_root_mm=[[0,-1,0],[0,500,500]])
        self.assertEqual(result['status'],'partial',result);self.assertEqual(result['data']['best_seed_index'],1)
        self.assertEqual(self.review(result)['data']['counts']['near_face_contact_candidate'],1)

    def test_sheet_face_is_not_assumed_solid_outward_normal(self):
        self.part.bodies[0].kind=1;self.capture()
        result=self.probe();self.assertEqual(result['status'],'ok',result)
        self.assertEqual(self.review(result)['data']['counts']['near_points_orientation_unconfirmed'],1)

    def test_invalid_args_unknown_face_same_occurrence_and_source_hash(self):
        for patch in ({'seed_points_root_mm':[]},{'max_iterations':0},{'convergence_tolerance_mm':0},{'seed_points_root_mm':[[True,0,0]]}):
            self.assertEqual(self.probe(**patch)['status'],'error')
        self.assertEqual(self.probe(right=self.args['left'])['errors'][0]['code'],'INVALID_ARGUMENTS')
        bad={**self.args['left'],'face_index':100};self.assertEqual(self.probe(left=bad)['errors'][0]['code'],'FACE_NOT_IN_SOURCE')
        result=self.probe();raw=json.loads(Path(self.files[0]).read_text());raw['data']['captured_at_utc']='changed';self.save('face0.json',raw)
        self.assertEqual(self.review(result)['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_stale_pose_part_configuration_and_edit_context(self):
        self.doc.root.children[1].Transform2=pose(x=10)
        self.assertEqual(self.probe()['errors'][0]['code'],'EVIDENCE_MISMATCH')
        self.doc.root.children[1].Transform2=pose(x=.00005)
        self.doc.editing_self=False;self.assertEqual(self.probe()['errors'][0]['code'],'IN_CONTEXT_EDIT_ACTIVE')
        self.doc.editing_self=True;self.part.ConfigurationManager.ActiveConfiguration.Name='Other'
        self.assertEqual(self.probe()['errors'][0]['code'],'COMPONENT_CONFIGURATION_MISMATCH')

    def test_face_geometry_changed_or_reference_missing(self):
        self.part.bodies[0].faces[0].area=2
        self.assertEqual(self.probe()['errors'][0]['code'],'FACE_GEOMETRY_MISMATCH')
        self.part.bodies[0].faces[0].area=1;self.part.Extension.state=1
        self.assertEqual(self.probe()['errors'][0]['code'],'FACE_REFERENCE_UNRESOLVED')

    def test_change_during_probe_discards_entire_snapshot(self):
        face=self.part.bodies[0].faces[0];original=face.GetClosestPointOn
        def changed(*a):
            p=original(*a);face.area=2;return p
        face.GetClosestPointOn=changed
        result=self.probe();self.assertEqual(result['status'],'error',result);self.assertIsNone(result['data'])
        self.assertEqual(result['errors'][0]['code'],'GEOMETRY_CHANGED')

    def test_budget_missing_reference_and_unsupported_catalog(self):
        limited=self.service.call('sw_component_faces',{'expected_document_token':self.token,'occurrence_path':'plate-1','max_faces':1})
        self.assertEqual(limited['status'],'partial');self.assertTrue(limited['data']['truncated']);self.assertEqual(limited['data']['face_count'],1)
        path=self.save('limited.json',limited);result=self.probe(left={**self.args['left'],'face_inventory_path':path})
        self.assertEqual(result['status'],'partial',result)
        self.part.bodies[0].faces[0].surface.kind='other';self.capture()
        self.assertEqual(self.probe()['errors'][0]['code'],'UNSUPPORTED_FACE_SURFACE')

    def test_offline_rejects_modified_gap_normal_best_and_source(self):
        result=self.probe()
        for mutate in (lambda d:d['samples'][0]['metrics'].update(gap_mm=0),
                       lambda d:d['samples'][0]['left'].update(point_root_m=[1,2,3]),
                       lambda d:d['samples'][0]['normal_left'].update(face_normal_root_unit=[0,1,0]),
                       lambda d:d.update(best_seed_index=None)):
            bad=copy.deepcopy(result);mutate(bad['data']);review=self.review(bad)
            self.assertEqual(review['status'],'error',review);self.assertFalse((self.root/'outputs/review.json').exists())

    def test_offline_only_no_overwrite_duplicates_and_thresholds(self):
        result=self.probe();path=self.save('probe.json',result)
        def forbidden():raise AssertionError('Offline task started CAD')
        offline=SolidWorksTools(root=self.root,factory=forbidden);self.addCleanup(offline.close)
        args={'probe_paths':[path],'output_path':'outputs/offline.json','contact_tolerance_mm':.1,'angle_tolerance_deg':5}
        self.assertEqual(offline.call('cad_review_face_contacts',args)['status'],'ok')
        self.assertEqual(offline.call('cad_review_face_contacts',args)['errors'][0]['code'],'OUTPUT_EXISTS')
        second=self.save('duplicate.json',result)
        self.assertEqual(offline.call('cad_review_face_contacts',{**args,'output_path':'outputs/duplicate.json','probe_paths':[path,second]})['errors'][0]['code'],'DUPLICATE_FACE_PROBE')
        self.assertEqual(self.review(result,output='outputs/tight.json',contact_tolerance_mm=.01)['data']['counts']['sample_gap_above_tolerance'],1)

    def test_cli_offline_review(self):
        source=self.save('probe.json',self.probe())
        command=[sys.executable,'-m','cadkin','review-face-contacts','--probes',source,'--output','outputs/cli.json','--contact-tolerance-mm','.1','--angle-tolerance-deg','5']
        run=subprocess.run(command,cwd=self.root,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout);self.assertTrue((self.root/'outputs/cli.json').exists())

    def test_catalog_failed_reference_and_descriptor_keep_rows(self):
        self.part.Extension.state = 1
        result = self.service.call('sw_component_faces', {'expected_document_token': self.token, 'occurrence_path': 'plate-1'})
        self.assertEqual(result['status'], 'partial'); self.assertEqual(result['data']['face_count'], 3)
        self.assertIsNone(result['data']['faces'][0]['face_reference'])
        self.assertIsNotNone(result['data']['faces'][0]['descriptor'])
        self.part.Extension.state = 0
        self.part.bodies[0].faces[0].area = float('nan')
        result = self.service.call('sw_component_faces', {'expected_document_token': self.token, 'occurrence_path': 'plate-1'})
        self.assertEqual(result['status'], 'partial'); self.assertEqual(result['data']['face_count'], 3)
        self.assertIsNone(result['data']['faces'][0]['descriptor'])
        self.assertIsNotNone(result['data']['faces'][0]['face_reference'])

    def test_catalog_exact_budget_is_not_truncated(self):
        result = self.service.call('sw_component_faces', {'expected_document_token': self.token, 'occurrence_path': 'plate-1', 'max_faces': 3})
        self.assertEqual(result['status'], 'ok'); self.assertFalse(result['data']['truncated'])

    def test_probe_changed_document_and_unresolved_target(self):
        self.doc.root.children[0].state = 1
        self.assertEqual(self.probe()['errors'][0]['code'], 'UNRESOLVED_COMPONENT')
        self.doc.root.children[0].state = 2
        self.doc.GetTitle = lambda: 'Changed assembly'
        result = self.probe(); self.assertEqual(result['status'], 'error'); self.assertIsNone(result['data'])

    def test_angles_zero_gap_and_facing_direction(self):
        good=pair_metrics([0,0,0],[0,0,0],[1,0,0],[-1,0,0])
        self.assertEqual(classify(good,.1,5),'near_face_contact_candidate')
        self.assertEqual(classify(pair_metrics([0,0,0],[.00001,0,0],[-1,0,0],[1,0,0]),.1,5),'near_points_orientation_unconfirmed')
        self.assertEqual(classify(pair_metrics([0,0,0],[0,0,0],[1,0,0],[0,1,0]),.1,5),'near_points_orientation_unconfirmed')
        for args in ((-.1,5),(.1,91),(.1,float('nan'))):
            with self.assertRaises(ToolFailure):classify(None,*args)
