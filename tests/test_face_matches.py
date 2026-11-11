import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys
from types import SimpleNamespace

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.adapters.face_identity import decode_reference, resolve_face
from cadkin.errors import ToolFailure
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.spatial import collect_spatial
from tests.face_fakes import face_document
from tests.sw_fakes import Component, pose, runtime


def write_face_fixture(root, service):
    inventory = collect_spatial(service, include_bounding_boxes=False)
    assert inventory['status'] == 'ok', inventory
    token = inventory['data']['document']['document_token']
    (root / 'inventory.json').write_text(json.dumps(inventory), encoding='utf-8')
    paths = []
    for occurrence in ('shaft-1', 'shaft-2', 'rail-1'):
        result = service.call('sw_component_cylinders', {'expected_document_token': token, 'occurrence_path': occurrence,
                                                        'include_face_references': True})
        assert result['status'] == 'ok', result
        name = occurrence + '.json'
        (root / name).write_text(json.dumps(result), encoding='utf-8')
        paths.append(name)
    return {'expected_document_token': token, 'inventory_path': 'inventory.json', 'cylinder_paths': paths}


class FaceMatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc, self.part, self.group, self.features, self.app = face_document()
        self.service = SolidWorksTools(root=self.root, factory=lambda: SolidWorksAdapter(app=self.app, runtime=runtime()))
        self.addCleanup(self.service.close)
        self.args = write_face_fixture(self.root, self.service)

    def match(self, **args):
        return self.service.call('sw_match_mate_faces', {**self.args, **args})

    def source(self, update, index=0):
        path = self.root / self.args['cylinder_paths'][index]
        data = json.loads(path.read_text(encoding='utf-8'))
        update(data)
        path.write_text(json.dumps(data), encoding='utf-8')

    def review(self, mates):
        self.assertEqual(self.service.call('cad_component_relations', {
            'inventory_path': 'inventory.json', 'cylinder_paths': self.args['cylinder_paths'],
            'output_path': 'outputs/relations.json', 'distance_tolerance_mm': 0.1, 'angle_tolerance_deg': 0.1})['status'], 'ok')
        (self.root / 'mates.json').write_text(json.dumps(mates), encoding='utf-8')
        # Offline review must not construct a COM adapter.
        def forbidden(): raise AssertionError('Offline review attempted COM')
        offline = SolidWorksTools(root=self.root, factory=forbidden)
        try:
            result = offline.call('cad_review_connections', {'relations_path': 'outputs/relations.json',
                                   'mate_inventory_path': 'mates.json', 'output_path': 'outputs/review.json'})
        finally: offline.close()
        data = json.loads((self.root / 'outputs/review.json').read_text(encoding='utf-8')) if result['status'] != 'error' else None
        return result, data

    def test_exact_faces_distinguished_from_identical_axes_and_repeated_parts(self):
        before = (self.doc.dirty, self.doc.rebuilt, list(self.doc.SelectionManager.selected))
        result = self.match()
        self.assertEqual(result['status'], 'ok', result)
        records = result['data']['mates']
        for index, expected_face in ((0, 0), (1, 1)):
            for entity in records[index]['entities']:
                hits = entity['face_match']['matches']
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]['face_index'], expected_face)
                self.assertEqual(hits[0]['occurrence_path'], entity['reference_occurrence_path'])
        review, data = self.review(result)
        self.assertEqual(review['status'], 'ok', review)
        pair = next(p for p in data['pairs'] if p['occurrence_paths'] == ['shaft-1', 'shaft-2'])
        self.assertEqual(len(pair['geometric_candidate_indices']), 4)  # identical axes, four face pairs
        for mate in pair['mate_evidence']:
            self.assertTrue(mate['face_match_confirmed'])
            self.assertEqual(len(mate['candidate_face_matches']), 1)
        self.assertEqual(pair['mate_evidence'][1]['category'], 'suppressed')
        self.assertFalse(pair['mechanical_relation_confirmed'])
        self.assertEqual(before, (self.doc.dirty, self.doc.rebuilt, self.doc.SelectionManager.selected))

    def test_default_geometry_capture_remains_compatible(self):
        result = self.service.call('sw_component_cylinders', {'expected_document_token': self.args['expected_document_token'], 'occurrence_path': 'shaft-1'})
        self.assertEqual(result['status'], 'ok')
        self.assertFalse(result['data']['face_references_requested'])
        self.assertNotIn('face_reference', result['data']['cylinders'][0])
        self.source(lambda e: e['data'].pop('face_references_requested'))
        self.assertEqual(self.match()['errors'][0]['code'], 'FACE_REFERENCE_UNAVAILABLE')

    def test_reference_capture_roundtrip_failure_keeps_geometry(self):
        self.part.Extension.state = 4
        result = self.service.call('sw_component_cylinders', {'expected_document_token': self.args['expected_document_token'],
                                    'occurrence_path': 'shaft-1', 'include_face_references': True})
        self.assertEqual(result['status'], 'partial', result)
        self.assertEqual(result['data']['cylinder_count'], 2)
        self.assertIsNone(result['data']['cylinders'][0]['face_reference'])

    def test_reference_encoding_rejects_invalid_and_excessive_data(self):
        for ref in (None, {}, {'encoding': 'base64', 'scope': 'referenced_part_definition', 'id': '$$'},
                    {'encoding': 'base64', 'scope': 'referenced_part_definition', 'id': 'A' * 6000}):
            with self.assertRaises(ToolFailure): decode_reference(ref)

    @unittest.skipUnless(sys.platform == 'win32', 'Requires real Windows pywin32 VARIANT types')
    def test_real_pywin32_byte_array_and_byref_state_types(self):
        import pythoncom
        import win32com.client
        face = object()
        class Extension:
            def GetObjectByPersistReference3(self, encoded, state):
                assert encoded.varianttype == pythoncom.VT_ARRAY | pythoncom.VT_UI1
                assert bytes(encoded.value) == b'\x00\x7f\xff'
                assert state.varianttype == pythoncom.VT_BYREF | pythoncom.VT_I4
                state.value = 0
                return face
        part = SimpleNamespace(Extension=Extension())
        result = resolve_face(part, {'encoding': 'base64', 'scope': 'referenced_part_definition', 'id': 'AH//'},
                              (pythoncom, win32com.client))
        self.assertIs(result, face)

    def test_stale_or_suppressed_persistent_reference_is_unknown(self):
        for code in (1, 2, 4, 6):
            self.part.Extension.state = code
            result = self.match()
            self.assertEqual(result['status'], 'partial', result)
            self.assertIn('FACE_REFERENCE_UNRESOLVED', {e['code'] for e in result['errors']})
            self.assertFalse(any(e['face_match']['matches'] for m in result['data']['mates'] for e in m['entities']))

    def test_changed_radius_and_non_cylinder_are_not_identified(self):
        self.part.bodies[0].faces[0].surface.CylinderParams[-1] = 0.02
        result = self.match()
        self.assertEqual(result['status'], 'partial', result)
        self.assertIn('FACE_GEOMETRY_MISMATCH', {e['code'] for e in result['errors']})
        self.assertEqual(result['data']['mates'][0]['entities'][0]['face_match']['matches'], [])
        self.part.bodies[0].faces[0].surface.cylindrical = False
        self.assertEqual(self.match()['status'], 'partial')

    def test_unmapped_and_nonface_entities_do_not_gain_identity(self):
        self.features[0].mate.entities[0].ReferenceComponent = Component('shaft-1')
        self.features[1].mate.entities[0].ReferenceType2 = 1
        result = self.match()
        self.assertEqual(result['status'], 'partial', result)
        self.assertEqual(result['data']['mates'][0]['entities'][0]['face_match']['status'], 'unknown')
        self.assertEqual(result['data']['mates'][1]['entities'][0]['face_match']['status'], 'not_face')

    def test_wrong_instance_reference_has_no_match(self):
        entity = self.features[0].mate.entities[0]
        entity.Reference = self.doc.root.children[1].GetCorrespondingEntity(self.part.bodies[0].faces[0])
        result = self.match()
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(result['data']['mates'][0]['entities'][0]['face_match']['matches'], [])
        _, data = self.review(result)
        mate = next(m for p in data['pairs'] for m in p['mate_evidence'] if m['feature_id'] == 11)
        self.assertFalse(mate['face_match_confirmed'])

    def test_unsupported_comparison_and_missing_correspondence_remain_partial(self):
        original = self.app.IsSame
        self.app.IsSame = lambda a, b: 2 if hasattr(a, 'part_face') else original(a, b)
        result = self.match()
        self.assertEqual(result['status'], 'partial', result)
        self.assertIn('FACE_IDENTITY_UNAVAILABLE', {e['code'] for e in result['errors']})
        self.app.IsSame = original
        self.doc.root.children[0].GetCorrespondingEntity = lambda f: None
        result = self.match()
        self.assertEqual(result['status'], 'partial', result)
        self.assertIn('FACE_CORRESPONDENCE_UNAVAILABLE', {e['code'] for e in result['errors']})

    def test_limits_and_exact_budgets(self):
        for kwargs in ({'max_candidate_faces': 1}, {'max_comparisons': 1}, {'max_mates': 1}, {'max_entities': 1}):
            result = self.match(**kwargs)
            self.assertEqual(result['status'], 'partial', result)
            self.assertTrue(result['data']['truncated'])
        self.assertEqual(self.match(max_candidate_faces=6, max_comparisons=12, max_mates=3)['status'], 'ok')
        self.assertEqual(self.match(max_comparisons=0)['errors'][0]['code'], 'INVALID_ARGUMENTS')
        self.assertEqual(self.match()['status'], 'ok')

    def test_empty_mates_and_outside_scope_not_absent_connections(self):
        result = self.match(cylinder_paths=['shaft-1.json'])
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(result['data']['mates'][0]['entities'][1]['face_match']['status'], 'outside_scope')
        self.group.children = []
        result = self.match()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['data']['mate_count'], 0)
        self.assertEqual(result['data']['face_matching']['comparisons'], 0)
        self.assertEqual(len(result['data']['face_matching']['unvisited_occurrences']), 3)

    def test_pose_configuration_and_document_mismatches_rejected(self):
        self.doc.root.children[0].Transform2 = pose(x=1)
        self.assertEqual(self.match()['errors'][0]['code'], 'COMPONENT_CHANGED')
        self.doc.root.children[0].Transform2 = pose()
        self.part.ConfigurationManager.ActiveConfiguration.Name = 'Other'
        self.assertEqual(self.match()['errors'][0]['code'], 'COMPONENT_CONFIGURATION_MISMATCH')
        self.doc.title = 'OtherDoc'
        self.assertEqual(self.match()['errors'][0]['code'], 'DOCUMENT_CHANGED')

    def test_geometry_or_mate_reference_change_during_read_discards_result(self):
        original = self.features[-1].GetSpecificFeature2
        def changed():
            self.part.bodies[0].faces[0].surface.CylinderParams[-1] = .04
            return original()
        self.features[-1].GetSpecificFeature2 = changed
        result = self.match()
        self.assertEqual(result['errors'][0]['code'], 'GEOMETRY_CHANGED', result)
        self.part.bodies[0].faces[0].surface.CylinderParams[-1] = .01
        def ref_changed():
            entity = self.features[0].mate.entities[0]
            entity.Reference = entity.ReferenceComponent.GetCorrespondingEntity(self.part.bodies[0].faces[1])
            return original()
        self.features[-1].GetSpecificFeature2 = ref_changed
        result = self.match()
        self.assertEqual(result['errors'][0]['code'], 'MATE_REFERENCE_CHANGED', result)

    def test_partial_reference_keeps_other_verified_matches(self):
        self.source(lambda e: e['data']['cylinders'][1].update(face_reference=None))
        result = self.match()
        self.assertEqual(result['status'], 'partial', result)
        self.assertEqual(len(result['data']['mates'][0]['entities'][0]['face_match']['matches']), 1)
        review, data = self.review(result)
        self.assertEqual(review['status'], 'partial', review)
        self.assertFalse(data['complete'])
        self.assertTrue(any(m['face_match_confirmed'] for p in data['pairs'] for m in p['mate_evidence']))
        mate = next(m for p in data['pairs'] for m in p['mate_evidence'] if m['feature_id'] == 11)
        self.assertEqual(mate['category'], 'unsuppressed_no_feature_error')
        self.assertTrue(mate['face_matching_errors'])

    def test_offline_rejects_face_provenance_mismatch(self):
        result = self.match()
        result['data']['face_matching']['cylinder_sources'][0]['source_sha256'] = '0' * 64
        review, data = self.review(result)
        self.assertEqual(review['errors'][0]['code'], 'INVALID_FACE_MATCH_SOURCE', review)
        self.assertIsNone(data)

    def test_offline_rejects_identity_claim_without_live_provenance(self):
        result = self.match()
        del result['data']['face_matching']
        review, _ = self.review(result)
        self.assertEqual(review['errors'][0]['code'], 'INVALID_FACE_MATCH_SOURCE', review)

    def test_two_face_requirement_keeps_multi_entity_mate_unconfirmed(self):
        self.features[0].mate.entities.append(copy.copy(self.features[0].mate.entities[0]))
        result = self.match()
        review, data = self.review(result)
        self.assertEqual(review['status'], 'ok', review)
        mate = next(m for p in data['pairs'] for m in p['mate_evidence'] if m['feature_id'] == 11)
        self.assertFalse(mate['face_match_confirmed'])

    def test_duplicate_sources_and_wrong_inventory_fail_before_cad(self):
        self.assertEqual(self.match(cylinder_paths=['shaft-1.json', 'shaft-1.json'])['errors'][0]['code'], 'INVALID_ARGUMENTS')
        self.source(lambda e: e['data']['document'].update(document_token='0' * 24))
        self.assertEqual(self.match()['errors'][0]['code'], 'EVIDENCE_MISMATCH')


if __name__ == '__main__': unittest.main()
