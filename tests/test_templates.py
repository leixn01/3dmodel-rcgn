import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cadkin.errors import ToolFailure
from cadkin.templates.catalog import catalog, find_template, list_templates
from cadkin.templates.compare import compare_graphs
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.templates import extract_template, compare_templates

HAS_USD=importlib.util.find_spec('pxr') is not None


def graph():
    return {'mechanism_template_schema_version':1,'complete':True,'risks':[],
            'bodies':[{'id':x,'enabled':True} for x in ('base','slide','shaft')],
            'joints':[{'id':name,'kind':kind,'enabled':True,'endpoints':[
                {'body_id':a,'frame_kind':'body'}, {'body_id':b,'frame_kind':'body'}]}
                for name,kind,a,b in [('j1','prismatic','base','slide'),('j2','revolute','slide','shaft')]]}


def mapping():
    return {'body_correspondence_schema_version':1,'reference_sha256':'a','candidate_sha256':'b',
            'body_map':[{'candidate_body':x,'reference_body':x} for x in ('base','slide','shaft')]}


class ComparisonTests(unittest.TestCase):
    def score(self,c=None,m=None,r=None):
        return compare_graphs(r or graph(),c if c is not None else graph(),m if m is not None else mapping(),'a','b')

    def test_identical_graph_and_reversed_endpoints(self):
        c=graph();c['joints'][0]['endpoints'].reverse()
        d=self.score(c);self.assertEqual(d['typed_joints']['recall'],1);self.assertEqual(d['connections']['precision'],1)
        self.assertFalse(d['requires_human_review']);self.assertIn('Axis alignment and location',d['unassessed'])

    def test_wrong_joint_type_keeps_topology_but_lowers_typed_score(self):
        c=graph();c['joints'][0]['kind']='revolute';d=self.score(c)
        self.assertEqual(d['connections']['recall'],1);self.assertEqual(d['typed_joints']['recall'],.5)
        self.assertEqual(d['missing_typed_joints'][0]['kind'],'prismatic')

    def test_missing_joint_and_extra_parallel_joint(self):
        c=graph();c['joints'].pop();d=self.score(c)
        self.assertEqual(d['typed_joints']['recall'],.5);self.assertEqual(d['typed_joints']['precision'],1)
        c=graph();extra=copy.deepcopy(c['joints'][0]);extra['id']='j3';c['joints'].append(extra)
        d=self.score(c);self.assertAlmostEqual(d['typed_joints']['precision'],2/3);self.assertEqual(d['connections']['precision'],1)

    def test_unmapped_body_does_not_disappear_from_denominator(self):
        m=mapping();m['body_map'].pop();d=self.score(m=m)
        self.assertEqual(d['typed_joints']['recall'],.5);self.assertEqual(d['typed_joints']['precision'],.5)
        self.assertEqual(d['body_coverage']['unmapped_candidate'],['shaft'])

    def test_empty_graph_scores_are_null(self):
        g=graph();g['bodies']=[];g['joints']=[];m=mapping();m['body_map']=[]
        d=self.score(g,m,g);self.assertIsNone(d['typed_joints']['recall']);self.assertIsNone(d['body_coverage']['reference_recall'])

    def test_stale_mapping_and_many_to_one_rejected(self):
        for change,code in [(lambda m:m.update(reference_sha256='old'),'EVIDENCE_MISMATCH'),
                            (lambda m:m['body_map'].append(m['body_map'][0]),'INVALID_GRAPH')]:
            m=mapping();change(m)
            with self.assertRaises(ToolFailure) as e:self.score(m=m)
            self.assertEqual(e.exception.code,code)

    def test_malformed_ids_endpoints_and_enabled_rejected(self):
        changes=[lambda c:c['bodies'].append(c['bodies'][0]),
                 lambda c:c['joints'][0]['endpoints'][0].update(body_id='absent'),
                 lambda c:c['joints'][0].update(enabled='false'),
                 lambda c:c['joints'][0]['endpoints'][0].update(frame_kind='world')]
        for change in changes:
            with self.subTest(change=change):
                c=graph();change(c)
                with self.assertRaises(ToolFailure):self.score(c)

    def test_disabled_unsupported_and_unresolved_are_explicit(self):
        changes=[lambda c:c['joints'][0].update(enabled=False), lambda c:c['joints'][0].update(kind='unsupported'),
                 lambda c:c['joints'][0]['endpoints'][0].update(body_id=None,frame_kind='unresolved'),
                 lambda c:c['bodies'][0].update(enabled=False)]
        for change in changes:
            c=graph();change(c);d=self.score(c)
            self.assertEqual(len(d['excluded']['candidate']),1);self.assertEqual(d['typed_joints']['recall'],.5)

    def test_renamed_body_ids_require_explicit_correspondence(self):
        c=graph();c['bodies'][0]['id']='platform'
        c['joints'][0]['endpoints'][0]['body_id']='platform'
        m=mapping();m['body_map'][0]['candidate_body']='platform'
        self.assertEqual(self.score(c,m)['typed_joints']['precision'],1)

    def test_stale_summary_cannot_override_graph_records(self):
        c=graph();c['summary']={'body_count':3,'joint_count':0,'joint_types':{}}
        d=self.score(c);self.assertEqual(d['typed_joints']['true_positive'],2)
        self.assertIn('STALE_GRAPH_SUMMARY',[r['code'] for r in d['risks']])

    def test_partial_source_risks_and_self_comparison_retained(self):
        c=graph();c['complete']=False;c['risks']=[{'code':'X'}]
        d=self.score(c);self.assertEqual(d['source_risks']['candidate'],[{'code':'X'}])
        m=mapping();m['candidate_sha256']='a'
        d=compare_graphs(graph(),graph(),m,'a','a');self.assertIn('SELF_COMPARISON',[r['code'] for r in d['risks']])


class CatalogTests(unittest.TestCase):
    def test_split_filter_and_pinned_hashes(self):
        self.assertEqual(list_templates()['count'],6);self.assertEqual(list_templates(include_heldout=True)['count'],8)
        self.assertEqual(list_templates('lifting')['templates'][0]['id'],'gas_lift_bar_stool')
        self.assertEqual(list_templates('planetary')['count'],0)
        for item in catalog()['templates']:
            entry,path=find_template(item['id']);self.assertEqual(entry['license'],'CC-BY-4.0')
            self.assertEqual(len(entry['source_files']),4);self.assertLess(path.stat().st_size,30000)

    def test_catalog_without_usd_or_com(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=SolidWorksTools(tmp,factory=lambda:self.fail('COM must not initialize'))
            try:
                with patch.dict(sys.modules,{'pxr':None}):
                    self.assertEqual(service.call('cad_list_mechanism_templates')['data']['count'],6)
            finally:service.close()

    def test_unknown_template_and_schema_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=SolidWorksTools(tmp,factory=lambda:self.fail('COM must not initialize'))
            try:
                for args,code in [({'template_id':'missing','output_path':'outputs/a.json'},'TEMPLATE_NOT_FOUND'),
                    ({'output_path':'outputs/a.json'},'INVALID_ARGUMENTS'),
                    ({'template_id':'bench_vise','asset_path':'a.usda','output_path':'outputs/a.json'},'INVALID_ARGUMENTS'),
                    ({'asset_path':'../a.usda','output_path':'outputs/a.json'},'INVALID_PATH')]:
                    self.assertEqual(service.call('cad_extract_mechanism_template',args)['errors'][0]['code'],code)
            finally:service.close()


@unittest.skipUnless(HAS_USD,'Install .[templates] for real USD extraction tests')
class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def fixture(self):
        from pxr import Usd,UsdGeom,UsdPhysics,Gf
        s=Usd.Stage.CreateInMemory();UsdGeom.SetStageMetersPerUnit(s,.001);UsdGeom.SetStageUpAxis(s,'Z')
        top=UsdGeom.Xform.Define(s,'/Assembly');top.AddTranslateOp().Set((1000,0,0));top.AddRotateZOp().Set(90)
        for name in ('A','B'):
            body=UsdGeom.Xform.Define(s,'/Assembly/'+name);UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
            UsdGeom.Cube.Define(s,body.GetPath().AppendChild('shape'))
        j=UsdPhysics.PrismaticJoint.Define(s,'/Assembly/joint')
        j.CreateBody0Rel().SetTargets(['/Assembly/A']);j.CreateBody1Rel().SetTargets(['/Assembly/B'])
        j.CreateAxisAttr('X');j.CreateLocalPos0Attr((100,0,0));j.CreateLowerLimitAttr(0);j.CreateUpperLimitAttr(250)
        return s

    def extract(self,s):
        from cadkin.templates.usd import read_template
        path=self.root/'sample.usda';s.GetRootLayer().Export(str(path));return read_template(path)

    def test_world_frames_units_limits_and_geometry_members(self):
        d=self.extract(self.fixture());j=d['joints'][0]
        for v,e in zip(j['endpoints'][0]['anchor_m'],[1,.1,0]):self.assertAlmostEqual(v,e)
        for v,e in zip(j['endpoints'][0]['axis_world'],[0,1,0]):self.assertAlmostEqual(v,e)
        self.assertAlmostEqual(j['limits']['upper'],.25);self.assertEqual(j['limits']['unit'],'m')
        self.assertEqual(d['bodies'][0]['geometry_members'],['/Assembly/A/shape'])

    def test_joint_local_rotation_changes_world_axis(self):
        from pxr import Gf
        s=self.fixture();j=s.GetPrimAtPath('/Assembly/joint')
        j.GetAttribute('physics:localRot0').Set(Gf.Quatf(Gf.Rotation(Gf.Vec3d(0,0,1),90).GetQuat()))
        axis=self.extract(s)['joints'][0]['endpoints'][0]['axis_world']
        for v,e in zip(axis,[-1,0,0]):self.assertAlmostEqual(v,e,places=6)

    def test_scaled_frame_axis_is_unknown(self):
        from pxr import UsdGeom
        s=self.fixture();UsdGeom.Xformable(s.GetPrimAtPath('/Assembly/A')).AddScaleOp().Set((2,1,1))
        d=self.extract(s);self.assertFalse(d['complete']);self.assertIsNone(d['joints'][0]['endpoints'][0]['axis_world'])

    def test_missing_target_and_non_xform_target_not_world(self):
        from pxr import UsdGeom
        for target in ('/Missing','/Scope'):
            s=self.fixture();UsdGeom.Scope.Define(s,'/Scope');s.GetPrimAtPath('/Assembly/joint').GetRelationship('physics:body0').SetTargets([target])
            d=self.extract(s);self.assertFalse(d['complete']);self.assertEqual(d['joints'][0]['endpoints'][0]['frame_kind'],'unresolved')
            self.assertIsNone(d['joints'][0]['endpoints'][0]['anchor_m'])

    def test_world_endpoint_and_below_body_target(self):
        from pxr import UsdGeom
        s=self.fixture();s.GetPrimAtPath('/Assembly/joint').GetRelationship('physics:body0').ClearTargets(True)
        sub=UsdGeom.Xform.Define(s,'/Assembly/B/frame');sub.AddTranslateOp().Set((0,10,0))
        s.GetPrimAtPath('/Assembly/joint').GetRelationship('physics:body1').SetTargets([sub.GetPath()])
        d=self.extract(s);self.assertEqual(d['joints'][0]['endpoints'][0]['frame_kind'],'world')
        self.assertEqual(d['joints'][0]['endpoints'][1]['body_id'],'/Assembly/B')

    def test_invalid_quaternion_rejected(self):
        from pxr import Gf
        s=self.fixture();s.GetPrimAtPath('/Assembly/joint').GetAttribute('physics:localRot0').Set(Gf.Quatf(0))
        with self.assertRaises(ToolFailure):self.extract(s)

    def test_variants_and_external_composition_rejected(self):
        s=self.fixture();s.GetPrimAtPath('/Assembly').GetVariantSets().AddVariantSet('mode').AddVariant('a')
        with self.assertRaises(ToolFailure) as e:self.extract(s)
        self.assertEqual(e.exception.code,'USD_COMPOSITION_UNSUPPORTED')
        path=self.root/'external.usda';path.write_text('#usda 1.0\n( subLayers = [@missing.usda@] )\n')
        from cadkin.templates.usd import read_template
        with self.assertRaises(ToolFailure) as e:read_template(path)
        self.assertEqual(e.exception.code,'USD_COMPOSITION_UNSUPPORTED')

    def test_no_bodies_and_prim_budget_rejected(self):
        from pxr import UsdGeom,Usd
        from cadkin.templates.usd import read_template
        s=Usd.Stage.CreateInMemory();UsdGeom.Cube.Define(s,'/Visual')
        with self.assertRaises(ToolFailure) as e:self.extract(s)
        self.assertEqual(e.exception.code,'NO_RIGID_BODIES')
        self.extract(self.fixture())
        with self.assertRaises(ToolFailure) as e:read_template(self.root/'sample.usda',max_prims=1)
        self.assertEqual(e.exception.code,'TEMPLATE_LIMIT')

    def test_animated_source_and_disabled_flags_retained(self):
        from pxr import UsdPhysics
        s=self.fixture();s.GetPrimAtPath('/Assembly').GetAttribute('xformOp:translate').Set((0,0,0),1)
        UsdPhysics.RigidBodyAPI(s.GetPrimAtPath('/Assembly/B')).CreateRigidBodyEnabledAttr(False)
        d=self.extract(s);self.assertFalse(d['complete']);self.assertFalse(d['bodies'][1]['enabled'])
        self.assertIn('ANIMATED_SOURCE',[r['code'] for r in d['risks']])

    def test_all_real_assets_and_no_joint_negative_references(self):
        from cadkin.templates.usd import read_template
        for entry in catalog()['templates']:
            _,p=find_template(entry['id']);d=read_template(p)
            self.assertEqual(d['summary']['body_count'],entry['expected']['body_count'])
            self.assertEqual(d['summary']['joint_count'],entry['expected']['joint_count'])
            self.assertTrue(all(b['geometry_scope']=='source_paths_only_geometry_omitted' for b in d['bodies']))
            self.assertTrue(all(e['frame_kind']!='unresolved' for j in d['joints'] for e in j['endpoints']))
            if not d['joints']:
                self.assertFalse(d['complete']);self.assertIn('NO_JOINTS',[r['code'] for r in d['risks']])
        d=read_template(find_template('bench_vise')[1]);jaw=next(j for j in d['joints'] if j['label']=='jaw')
        self.assertAlmostEqual(jaw['limits']['upper'],.125);self.assertAlmostEqual(abs(jaw['endpoints'][0]['axis_world'][1]),1)

    def test_fresh_parse_detects_source_edit(self):
        s=self.fixture();d=self.extract(s)
        s.GetPrimAtPath('/Assembly/joint').GetAttribute('physics:upperLimit').Set(500)
        e=self.extract(s);self.assertNotEqual(d['source']['sha256'],e['source']['sha256']);self.assertEqual(e['joints'][0]['limits']['upper'],.5)

    def test_missing_dependency_and_new_output_only(self):
        with patch.dict(sys.modules,{'pxr':None}):
            with self.assertRaises(ToolFailure) as e:extract_template(self.root,'outputs/a.json',template_id='bench_vise')
            self.assertEqual(e.exception.code,'USD_DEPENDENCY_MISSING')
        extract_template(self.root,'outputs/a.json',template_id='bench_vise')
        with self.assertRaises(ToolFailure) as e:extract_template(self.root,'outputs/a.json',template_id='bench_vise')
        self.assertEqual(e.exception.code,'OUTPUT_EXISTS')

    def test_file_hash_bound_comparison_and_cli(self):
        subprocess.run([sys.executable,'-m','cadkin','template-extract','--template-id','bench_vise','--output','outputs/a.json'],cwd=self.root,check=True,capture_output=True)
        p=self.root/'outputs/a.json';g=json.loads(p.read_text());digest=hashlib.sha256(p.read_bytes()).hexdigest()
        m={'body_correspondence_schema_version':1,'reference_sha256':digest,'candidate_sha256':digest,
           'body_map':[{'candidate_body':b['id'],'reference_body':b['id']} for b in g['bodies']]}
        (self.root/'map.json').write_text(json.dumps(m))
        d=compare_templates(self.root,'outputs/a.json','outputs/a.json','map.json','outputs/score.json')['data']
        self.assertEqual(d['typed_joints']['recall'],1)
        p.write_text(p.read_text()+'\n')
        with self.assertRaises(ToolFailure) as e:compare_templates(self.root,'outputs/a.json','outputs/a.json','map.json','outputs/stale.json')
        self.assertEqual(e.exception.code,'EVIDENCE_MISMATCH');self.assertFalse((self.root/'outputs/stale.json').exists())


if __name__=='__main__':unittest.main()
