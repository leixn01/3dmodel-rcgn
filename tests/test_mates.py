import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.errors import ToolFailure
from cadkin.tools.connections import review_connections
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.spatial import collect_spatial
from tests.evidence_fakes import evidence_document, MateEntity
from tests.mate_fakes import attach_features, Feature, MateApp
from tests.sw_fakes import runtime, Component, pose
from tests.test_relations import write_fixture


class MateInventoryTests(unittest.TestCase):
    def setUp(self):
        self.doc = evidence_document()
        self.group, self.features = attach_features(self.doc)
        self.app = MateApp(self.doc)
        self.adapter = SolidWorksAdapter(app=self.app, runtime=runtime())
        self.service = SolidWorksTools(factory=lambda: self.adapter)
        self.addCleanup(self.service.close)
        self.token = self.service.call('sw_active_document')['data']['document_token']

    def read(self, **args):
        return self.service.call('sw_mate_inventory', {'expected_document_token': self.token, **args})

    def test_root_scope_states_identity_and_raw_coordinates(self):
        result = self.read()
        self.assertEqual(result['status'], 'ok', result)
        data = result['data']
        self.assertEqual(data['mate_count'], 3)
        self.assertFalse(data['subassembly_internal_mates_included'])
        self.assertEqual([m['activity']['state'] for m in data['mates']],
                         ['unsuppressed_no_feature_error', 'suppressed', 'unsuppressed_feature_issue'])
        entity = data['mates'][0]['entities'][0]
        self.assertEqual(entity['reference_occurrence_path'], 'rail-1')
        self.assertEqual(entity['reference_status'], 'verified_root_occurrence')
        self.assertEqual(data['mates'][0]['entity_params_frame'], 'root_assembly')
        self.assertEqual(entity['entity_params_raw'], self.features[0].mate.entities[0].EntityParams)
        self.assertTrue(all(m['activity']['solver_validity'] == 'not_evaluated' for m in data['mates']))

    def test_feature_failure_is_unknown_not_unsuppressed(self):
        for raw in (None, [], False, [False, False], ['false']):
            self.features[0].IsSuppressed2 = lambda *args: raw
            result = self.read()
            self.assertEqual(result['status'], 'partial', result)
            self.assertEqual(result['data']['mates'][0]['activity']['state'], 'unknown')

    def test_null_and_unverified_references_are_preserved(self):
        self.features[0].mate.entities[0].ReferenceComponent = None
        self.features[1].mate.entities[0].ReferenceComponent = Component('rail-1')  # same name, different COM object
        result = self.read()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['data']['mates'][0]['entities'][0]['reference_status'], 'root_or_unavailable')
        ref = result['data']['mates'][1]['entities'][0]
        self.assertNotIn('reference_occurrence_path', ref)
        self.assertIn('MATE_REFERENCE_UNRESOLVED', [e['code'] for e in ref['errors']])

    def test_unsupported_equality_and_missing_mate_keep_partial(self):
        self.app.IsSame = lambda a,b: 2
        self.features[1].mate = None
        result = self.read()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['data']['mate_count'], 3)
        self.assertEqual(result['data']['component_contexts'], [])
        self.assertIn('MATE_INTERFACE_UNAVAILABLE', [e['code'] for e in result['errors']])

    def test_limits_and_exact_budget(self):
        for args in ({'max_mates':1}, {'max_features':2}, {'max_entities':1}, {'max_depth':1}):
            result = self.read(**args)
            self.assertEqual(result['status'], 'partial', result)
            self.assertTrue(result['data']['truncated'])
        self.assertEqual(self.read(max_mates=3, max_features=5)['status'], 'ok')

    def test_empty_group_and_failed_tree_are_different(self):
        self.group.children = []
        self.assertEqual(self.read()['data']['mates'], [])
        self.group.GetFirstSubFeature = lambda: (_ for _ in ()).throw(RuntimeError('read failed'))
        self.assertEqual(self.read()['status'], 'partial')
        self.doc.FirstFeature = lambda: (_ for _ in ()).throw(RuntimeError('read failed'))
        self.assertEqual(self.read()['status'], 'error')

    def test_folders_revisited_features_and_nested_component_scope(self):
        folder = Feature(20, 'Folder', 'FtrFolder', children=self.features)
        self.group.children = [folder]
        self.features[0].mate.entities[0].ReferenceComponent = self.doc.root.children[2].children[0]
        result = self.read()
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(result['data']['mates'][0]['entities'][0]['reference_occurrence_path'], 'slide-1/block-1')
        self.assertFalse(result['data']['subassembly_internal_mates_included'])
        self.features[-1].subnext = self.features[0]
        result = self.read()
        self.assertEqual(result['status'], 'partial')
        self.assertIn('FEATURE_REVISIT', [e['code'] for e in result['errors']])
        self.assertEqual(result['data']['mate_count'], 3)

    def test_rolled_back_and_warning_not_healthy(self):
        self.features[0].rolled_back = True
        result = self.read()
        self.assertEqual(result['data']['mates'][0]['activity']['state'], 'rolled_back')
        self.assertTrue(result['data']['mates'][2]['activity']['error_is_warning'])

    def test_state_component_and_document_change_fatal(self):
        self.features[0].IsSuppressed2 = lambda *args: [self.features[0].state_calls > 0]
        # Explicit state change on second call.
        calls = []
        def changing(*args): calls.append(1); return [len(calls)>1]
        self.features[0].IsSuppressed2 = changing
        self.assertEqual(self.read()['errors'][0]['code'], 'MATE_STATE_CHANGED')
        self.features[0].IsSuppressed2 = lambda *args: [False]
        original = self.features[2].GetSpecificFeature2
        def moved():
            self.doc.root.children[0].Transform2 = pose(x=5)
            return original()
        self.features[2].GetSpecificFeature2 = moved
        self.assertEqual(self.read()['errors'][0]['code'], 'COMPONENT_CHANGED')
        self.features[2].GetSpecificFeature2 = lambda: (setattr(self.doc, 'title', 'Changed'), original())[1]
        self.assertEqual(self.read()['errors'][0]['code'], 'DOCUMENT_CHANGED')

    def test_readonly_and_invalid_arguments(self):
        before = (self.doc.dirty, list(self.doc.SelectionManager.selected), self.doc.rebuilt)
        self.assertEqual(self.read()['status'], 'ok')
        self.assertEqual(before, (self.doc.dirty, self.doc.SelectionManager.selected, self.doc.rebuilt))
        self.assertEqual(self.read(max_mates=0)['errors'][0]['code'], 'INVALID_ARGUMENTS')
        self.assertEqual(self.read()['status'], 'ok')


def connection_fixture(root):
    args = write_fixture(root)
    service = SolidWorksTools(root=root)
    try:
        assert service.call('cad_component_relations', args)['status'] == 'ok'
    finally: service.close()
    # Matching explicit test assembly, preserving the same title/configuration/PID and occurrence poses.
    from tests.sw_fakes import Document
    children = [Component('shaft-1'), Component('shaft-2'), Component('rail-1')]
    children[1].Transform2 = pose(z=3); children[2].Transform2 = pose(x=0.1)
    doc = Document(children=children)
    attach_features(doc)
    service = SolidWorksTools(root=root, factory=lambda: SolidWorksAdapter(app=MateApp(doc), runtime=runtime()))
    try:
        token=service.call('sw_active_document')['data']['document_token']
        mates=service.call('sw_mate_inventory', {'expected_document_token':token})
        assert mates['status']=='ok',mates
    finally:service.close()
    (root/'mates.json').write_text(json.dumps(mates),encoding='utf-8')
    return {'relations_path':'outputs/relations.json','mate_inventory_path':'mates.json','output_path':'outputs/connections.json'}


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.args=connection_fixture(self.root)
        self.relations=json.loads((self.root/'outputs/relations.json').read_text())
        self.inventory=json.loads((self.root/'inventory.json').read_text())
        self.mates=json.loads((self.root/'mates.json').read_text())
        self.digest=hashlib.sha256((self.root/'inventory.json').read_bytes()).hexdigest()

    def review(self):return review_connections(self.relations,self.mates,self.inventory,self.digest)

    def test_pair_review_preserves_issue_and_no_face_or_joint_confirmation(self):
        data=self.review()
        self.assertEqual(data['counts'],{'has_unsuppressed_mate_evidence':1,'unresolved_mate_evidence':0,'only_suppressed_or_feature_issue':1,'geometry_only':1})
        self.assertTrue(data['complete'])
        self.assertTrue(all(not p['mechanical_relation_confirmed'] for p in data['pairs']))
        self.assertTrue(all(not m['face_match_confirmed'] for p in data['pairs'] for m in p['mate_evidence']))
        pair=next(p for p in data['pairs'] if p['review_state']=='has_unsuppressed_mate_evidence')
        self.assertEqual(len(pair['mate_evidence']),2)  # suppressed evidence retained alongside other mate

    def test_partial_and_zero_mates_do_not_imply_free_motion(self):
        self.mates.update(status='partial',errors=[{'code':'MATE_LIMIT','message':'limit'}]);self.mates['data']['complete']=False
        self.assertFalse(self.review()['complete'])
        self.mates.update(status='ok',errors=[]);self.mates['data'].update(complete=True,mates=[],mate_count=0)
        self.assertEqual(self.review()['counts']['geometry_only'],3)
        self.assertTrue(self.review()['requires_review'])

    def test_null_unmapped_and_multi_entity_mates_not_pair_proof(self):
        record=self.mates['data']['mates'][0]
        record['entities'].append({'reference_status':'root_or_unavailable'});record['entity_count']=3
        data=self.review()
        self.assertEqual(data['counts']['has_unsuppressed_mate_evidence'],0)
        self.assertEqual(data['counts']['unresolved_mate_evidence'],1)
        record['entities'][-1]={'reference_status':'verified_root_occurrence','reference_occurrence_path':'rail-1'}
        self.assertTrue(self.review()['unmatched_mates'])

    def test_pose_configuration_document_and_frame_mismatches(self):
        original=copy.deepcopy(self.mates)
        for mode in ('pose','config','doc','frame'):
            self.mates=copy.deepcopy(original)
            d=self.mates['data']
            if mode=='pose':d['component_contexts'][0]['transform']['raw_array'][9]+=1
            if mode=='config':d['component_contexts'][0]['referenced_configuration']='Other'
            if mode=='doc':d['document']['document_token']='f'*24
            if mode=='frame':d['mates'][0]['entity_params_frame']='unverified'
            with self.assertRaises(ToolFailure) as caught:self.review()
            self.assertEqual(caught.exception.code,'EVIDENCE_MISMATCH')

    def test_offline_file_bindings_no_com_and_no_overwrite(self):
        factory=Mock(side_effect=AssertionError('Must not connect COM'))
        service=SolidWorksTools(root=self.root,factory=factory);self.addCleanup(service.close)
        result=service.call('cad_review_connections',self.args)
        self.assertEqual(result['status'],'ok',result)
        self.assertEqual(service.call('cad_review_connections',self.args)['errors'][0]['code'],'OUTPUT_EXISTS')
        # Hash guard must detect edits to the actual cylinder source, not only relation headers.
        with (self.root/'shaft-1.json').open('a') as f:f.write('\n')
        result=service.call('cad_review_connections',{**self.args,'output_path':'outputs/new.json'})
        self.assertEqual(result['errors'][0]['code'],'EVIDENCE_MISMATCH')
        self.assertFalse((self.root/'outputs/new.json').exists())
        factory.assert_not_called()

    def test_cli_roundtrip(self):
        (Path.cwd()/'outputs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path.cwd()/'outputs') as folder:
            root=Path(folder);args=connection_fixture(root)
            run=subprocess.run([sys.executable,'-m','cadkin','review-connections',str(root/args['relations_path']),str(root/args['mate_inventory_path']),
                                '--output',str(root/args['output_path'])],capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertEqual(json.loads(run.stdout)['data']['coverage']['occurrence_pairs'],3)
