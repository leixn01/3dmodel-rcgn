import copy
import math
import os
import sys
import unittest
from unittest.mock import Mock, patch

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.geometry import cylinder_from_sw, transform_from_sw
from cadkin.tools.solidworks import CATALOG, SolidWorksTools
from tests.evidence_fakes import Body, Mate, MateEntity, Part, Surface, evidence_document
from tests.sw_fakes import App, Component, Document, pose, runtime


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.doc = evidence_document()
        self.app = App(self.doc)
        self.adapter = SolidWorksAdapter(app=self.app, runtime=runtime())
        self.service = SolidWorksTools(factory=lambda: self.adapter)
        self.addCleanup(self.service.close)
        self.first = self.doc.root.children[0]

    def invoke(self, name='sw_component_constraints', path='rail-1', **kwargs):
        token = self.service.call('sw_active_document')['data']['document_token']
        return self.service.call(name, {'expected_document_token': token, 'occurrence_path': path, **kwargs})

    def test_fixed_flag_and_raw_mates_keep_entity_context(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'ok', result)
        data = result['data']
        self.assertTrue(data['fixed_state']['value'])
        self.assertEqual(data['reported_mate_count'], 1)
        mate = data['mates'][0]
        self.assertEqual((mate['type_code'], mate['alignment_code'], mate['entity_count']), (1, 0, 2))
        self.assertEqual(mate['entities'][1]['reference_component_name'], 'rail-2')
        self.assertEqual(mate['entities'][0]['entity_params_raw'], [0, 0, 0, 0, 0, 1, .01, 0])
        self.assertNotIn('axis_root_unit', mate['entities'][0])
        self.assertFalse(data['snapshot_atomic'])

    def test_nested_fixed_state_is_unknown_without_calling_isfixed(self):
        child = self.doc.root.children[2].children[0]
        child.IsFixed = Mock(side_effect=AssertionError('Nested flag must not be trusted'))
        result = self.invoke(path=child.Name2)
        self.assertEqual(result['status'], 'partial')
        self.assertIsNone(result['data']['fixed_state']['value'])
        self.assertEqual(result['errors'][0]['code'], 'FIXED_STATE_CONTEXT_UNAVAILABLE')
        child.IsFixed.assert_not_called()

    def test_empty_mates_and_read_failure_are_distinct(self):
        self.first.mates = None
        data = self.invoke()['data']
        self.assertEqual((data['mates'], data['reported_mate_count']), ([], 0))
        self.first.GetMates = Mock(side_effect=RuntimeError('COM unavailable'))
        result = self.invoke()
        self.assertEqual(result['status'], 'partial')
        self.assertIsNone(result['data']['mates'])
        self.assertIsNone(result['data']['reported_mate_count'])
        self.assertTrue(result['data']['fixed_state']['value'])

    def test_mate_and_entity_limits_are_explicit(self):
        self.first.mates *= 3
        result = self.invoke(max_mates=1, max_entities=1)
        self.assertTrue(result['data']['truncated'])
        self.assertEqual(result['data']['reported_mate_count'], 3)
        self.assertEqual(len(result['data']['mates'][0]['entities']), 1)
        self.assertEqual({e['code'] for e in result['errors']}, {'MATE_LIMIT', 'MATE_ENTITY_LIMIT'})

    def test_unsupported_mate_and_bad_entity_keep_readable_records(self):
        self.first.mates.append(object())
        self.first.mates[0].entities[1] = None
        result = self.invoke()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['data']['read_mate_count'], 2)
        self.assertIsNone(result['data']['mates'][1]['entities'])
        self.assertTrue(result['data']['mates'][0]['entities'][1]['errors'])

    def test_missing_reference_and_invalid_params_are_not_invented(self):
        entity = MateEntity(None)
        entity.EntityParams[0] = float('nan')
        self.first.mates = [Mate([entity])]
        result = self.invoke()
        record = result['data']['mates'][0]['entities'][0]
        self.assertEqual(record['reference_status'], 'root_or_unavailable')
        self.assertIsNone(record['entity_params_raw'])
        self.assertEqual(result['status'], 'partial')

    def test_document_switch_during_mates_discards_result(self):
        mate = self.first.mates[0]
        def change(index):
            self.app.ActiveDoc = Document(title='Other')
            return mate.entities[index]
        mate.MateEntity = change
        result = self.invoke()
        self.assertEqual(result['errors'][0]['code'], 'DOCUMENT_CHANGED')
        self.assertIsNone(result['data'])

    def test_cylinder_root_transform_uses_occurrence_once(self):
        self.first.Transform2 = pose(1, 2, 3, quarter_turn=True, scale=2)
        self.first.model_doc = Part([Body([Surface([.1, .2, .3, 1, 0, 0, .01])])])
        result = self.invoke('sw_component_cylinders')
        self.assertEqual(result['status'], 'ok', result)
        data = result['data']
        cylinder = data['cylinders'][0]
        for actual, expected in zip(cylinder['origin_root_mm'], [600, 2200, 3600]): self.assertAlmostEqual(actual, expected)
        self.assertEqual(cylinder['axis_root_unit'], [0, 1, 0])
        self.assertAlmostEqual(cylinder['radius_root_mm'], 20)
        self.assertFalse(data['assembly_instance_features_evaluated'])
        self.assertEqual(data['geometry_scope'], 'referenced_part_definition')
        self.assertEqual(self.first.model_doc.body_calls, [(-1, False)])

    def test_negative_scale_radius_positive_and_direction_is_unoriented(self):
        transform = transform_from_sw(pose(1, 0, 0, scale=-2).ArrayData)
        data = cylinder_from_sw([.1, 0, 0, 0, 0, 3, .005], transform)
        self.assertEqual(data['axis_root_unit'], [0, 0, -1])
        self.assertAlmostEqual(data['radius_root_mm'], 10)
        self.assertTrue(data['axis_is_unoriented'])

    def test_repeated_file_instances_have_distinct_root_axes(self):
        left = self.invoke('sw_component_cylinders')['data']
        right = self.invoke('sw_component_cylinders', path='rail-2')['data']
        self.assertNotEqual(left['occurrence_path'], right['occurrence_path'])
        self.assertEqual(left['cylinders'][0]['origin_root_mm'], [0, 0, 0])
        self.assertEqual(right['cylinders'][0]['origin_root_mm'], [500, 0, 0])

    def test_configuration_mismatch_subassembly_and_unloaded_model_rejected(self):
        self.first.model_doc.ConfigurationManager.ActiveConfiguration.Name = 'Wrong'
        result = self.invoke('sw_component_cylinders')
        self.assertEqual(result['errors'][0]['code'], 'COMPONENT_CONFIGURATION_MISMATCH')
        self.assertEqual(self.first.model_doc.body_calls, [])
        self.first.model_doc = None
        self.assertEqual(self.invoke('sw_component_cylinders')['errors'][0]['code'], 'COMPONENT_MODEL_UNAVAILABLE')
        self.assertEqual(self.invoke('sw_component_cylinders', path='slide-1')['errors'][0]['code'], 'NOT_PART_COMPONENT')

    def test_noncylindrical_and_empty_bodies_are_valid_empty_not_unknown(self):
        for bodies in ([], [Body([Surface(cylindrical=False)])]):
            self.first.model_doc = Part(bodies)
            result = self.invoke('sw_component_cylinders')
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['data']['cylinders'], [])
            self.assertTrue(result['data']['complete'])

    def test_face_and_cylinder_and_body_limits_preserve_partial(self):
        for args, code in [({'max_faces': 1}, 'FACE_LIMIT'), ({'max_cylinders': 1}, 'CYLINDER_LIMIT'), ({'max_bodies': 1}, 'BODY_LIMIT')]:
            self.first.model_doc = Part([Body([Surface(), Surface()]), Body([Surface()])])
            result = self.invoke('sw_component_cylinders', **args)
            self.assertEqual(result['status'], 'partial', result)
            self.assertTrue(result['data']['truncated'])
            self.assertIn(code, [e['code'] for e in result['errors']])
        self.first.model_doc = Part([Body([Surface()])])
        exact = self.invoke('sw_component_cylinders', max_faces=1, max_cylinders=1, max_bodies=1)
        self.assertTrue(exact['data']['complete'])
        self.assertFalse(exact['data']['truncated'])

    def test_invalid_cylinder_and_face_failure_keep_other_axes(self):
        bad = Surface([0, 0, 0, 0, 0, 0, .01])
        self.first.model_doc = Part([Body([bad, Surface(), None])])
        result = self.invoke('sw_component_cylinders')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['data']['cylinder_count'], 1)
        self.assertEqual(result['data']['scanned_face_count'], 3)
        self.assertEqual({e['code'] for e in result['errors']}, {'INVALID_CYLINDER', 'SURFACE_UNAVAILABLE'})

    def test_changed_part_configuration_or_transform_discards_mixed_data(self):
        part = self.first.model_doc
        surface = part.bodies[0].faces[1].surface
        def change():
            part.ConfigurationManager.ActiveConfiguration.Name = 'Other'
            return True
        surface.IsCylinder = change
        self.assertEqual(self.invoke('sw_component_cylinders')['errors'][0]['code'], 'COMPONENT_CONFIGURATION_MISMATCH')
        part.ConfigurationManager.ActiveConfiguration.Name = 'Default'
        def move():
            self.first.Transform2 = pose(1, 0, 0)
            return True
        surface.IsCylinder = move
        self.assertEqual(self.invoke('sw_component_cylinders')['errors'][0]['code'], 'COMPONENT_CHANGED')

    def test_read_only_preserves_selection_visibility_and_dirty_state(self):
        self.doc.SelectionManager.selected = [self.first]
        self.doc.dirty = True
        self.first._visible = 0
        self.doc.EditRebuild3 = Mock(side_effect=AssertionError('No rebuild'))
        for name in ('sw_component_constraints', 'sw_component_cylinders'):
            self.assertTrue(CATALOG[name]['annotations']['readOnlyHint'])
            self.assertEqual(self.invoke(name)['status'], 'ok')
        self.assertEqual(self.doc.SelectionManager.selected, [self.first])
        self.assertTrue(self.doc.dirty)
        self.assertEqual(self.first.Visible, 0)
        self.doc.EditRebuild3.assert_not_called()

    def test_limits_schema_target_identity_and_unresolved_paths(self):
        for name, args in [('sw_component_constraints', {'max_mates': 0}), ('sw_component_constraints', {'max_entities': True}),
                           ('sw_component_cylinders', {'max_faces': 5001}), ('sw_component_cylinders', {'max_bodies': 0})]:
            self.assertEqual(self.invoke(name, **args)['errors'][0]['code'], 'INVALID_ARGUMENTS')
        for name in ('sw_component_constraints', 'sw_component_cylinders'):
            self.assertEqual(self.invoke(name, path='missing')['errors'][0]['code'], 'COMPONENT_NOT_FOUND')
            self.first.state = 1
            self.assertEqual(self.invoke(name)['errors'][0]['code'], 'UNRESOLVED_COMPONENT')
            self.first.state = 2
            token = self.service.call('sw_active_document')['data']['document_token']
            self.assertEqual(self.service.call(name, {'expected_document_token': '0' * 24, 'occurrence_path': 'rail-1'})['errors'][0]['code'], 'DOCUMENT_CHANGED')
        self.app.ActiveDoc = Document(kind=1)
        self.assertEqual(self.invoke()['errors'][0]['code'], 'NOT_ASSEMBLY')

    def test_runtime_reports_actual_python_and_conda_match(self):
        with patch.dict(os.environ, {'CONDA_PREFIX': sys.prefix}):
            data = self.service.call('sw_session_status')['data']['runtime']
            self.assertEqual(data['python_executable'], sys.executable)
            self.assertTrue(data['matches_conda_prefix'])
        with patch.dict(os.environ, {'CONDA_PREFIX': os.path.join(sys.prefix, 'other-env')}):
            self.assertFalse(self.service.call('sw_session_status')['data']['runtime']['matches_conda_prefix'])
