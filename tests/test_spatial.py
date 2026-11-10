"""Analytic coordinate fixtures and partial-result contracts, not live COM tests."""
import json
import unittest
from unittest.mock import Mock

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.errors import ToolFailure
from cadkin.geometry import bounding_box, inverse_similarity, multiply, transform_from_sw
from cadkin.tools.solidworks import CATALOG, SolidWorksTools
from tests.sw_fakes import App, Component, Document, pose, runtime


class GeometryTests(unittest.TestCase):
    def assertMatrix(self, actual, expected):
        for row, target in zip(actual, expected):
            for x, y in zip(row, target):
                self.assertAlmostEqual(x, y, places=10)

    def test_rotation_scale_then_translation_column_convention(self):
        data = transform_from_sw(pose(1, 2, 3, quarter_turn=True, scale=2).ArrayData)
        self.assertMatrix(data['to_root'], [[0, -2, 0, 1], [2, 0, 0, 2], [0, 0, 2, 3], [0, 0, 0, 1]])
        point = [1, 0, 0, 1]
        self.assertEqual([sum(a * b for a, b in zip(row, point)) for row in data['to_root']], [1, 4, 3, 1])
        self.assertEqual(data['origin_root_mm'], [1000, 2000, 3000])

    def test_inverse_handles_reflections_negative_and_nonunit_scale(self):
        for scale in (1, 2.5, -2):
            for reflection in (False, True):
                raw = pose(1, 2, 3, quarter_turn=True, scale=scale).ArrayData
                if reflection:
                    raw[:3] = [-x for x in raw[:3]]
                matrix = transform_from_sw(raw)['to_root']
                identity = [[int(i == j) for j in range(4)] for i in range(4)]
                self.assertMatrix(multiply(inverse_similarity(matrix), matrix), identity)
                self.assertMatrix(multiply(matrix, inverse_similarity(matrix)), identity)

    def test_nested_root_transform_is_not_composed_twice(self):
        parent = transform_from_sw(pose(1, 2, quarter_turn=True).ArrayData)['to_root']
        child = transform_from_sw(pose(1, 2.2, quarter_turn=True).ArrayData)['to_root']
        local = multiply(inverse_similarity(parent), child)
        self.assertMatrix(local, [[1, 0, 0, 0.2], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        self.assertMatrix(multiply(parent, local), child)

    def test_invalid_transform_never_becomes_identity(self):
        invalid = [None, [], [0] * 16, pose().ArrayData[:15]]
        for index, val in ((0, 2), (0, float('nan')), (9, float('inf')), (12, 0), (12, True), (3, '0')):
            raw = pose().ArrayData[:]
            raw[index] = val
            invalid.append(raw)
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ToolFailure):
                transform_from_sw(raw)

    def test_box_corner_order_units_zero_thickness_and_center(self):
        box = bounding_box([4, -2, 0, 1, 2, 0])
        self.assertEqual(box['min_m'], [1, -2, 0])
        self.assertEqual(box['size_mm'], [3000, 4000, 0])
        self.assertEqual(box['center_mm'], [2500, 0, 0])
        self.assertTrue(box['approximate'])
        for raw in (None, [], [0, 0, 0, float('nan'), 1, 1], [0, 0, 0, 1e308, 1, 1]):
            with self.subTest(raw=raw), self.assertRaises(ToolFailure):
                bounding_box(raw)


class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.doc = Document()
        self.app = App(self.doc)
        self.adapter = SolidWorksAdapter(app=self.app, runtime=runtime())
        self.service = SolidWorksTools(factory=lambda: self.adapter)
        self.addCleanup(self.service.close)

    def token(self):
        return self.service.call('sw_active_document')['data']['document_token']

    def invoke(self, path=None, **kwargs):
        name = 'sw_spatial_inventory' if path is None else 'sw_component_spatial'
        args = {'expected_document_token': self.token(), **kwargs}
        if path is not None:
            args['occurrence_path'] = path
        return self.service.call(name, args)

    def test_inventory_keeps_instances_and_matches_single_nested_record(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'ok', result)
        data = result['data']
        self.assertEqual((data['component_count'], data['spatial_ok_count']), (4, 4))
        self.assertTrue(data['complete'])
        self.assertFalse(data['truncated'])
        self.assertFalse(data['snapshot_atomic'])
        nodes = data['components']
        self.assertEqual(nodes[0]['file_path'], nodes[1]['file_path'])
        self.assertNotEqual(nodes[0]['occurrence_path'], nodes[1]['occurrence_path'])
        child = nodes[3]
        self.assertEqual(child['parent_occurrence_path'], 'slide-1')
        self.assertEqual(child['transform']['origin_root_mm'], [1000, 2200, 0])
        for actual, expected in zip(child['transform']['origin_parent_mm'], [200, 0, 0]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(child['bounding_box']['min_mm'], [900, 2100, 0])
        self.assertEqual(child, self.invoke('slide-1/block-1')['data']['component'])
        self.assertEqual(nodes[0]['transform']['to_parent'], nodes[0]['transform']['to_root'])
        json.dumps(result, allow_nan=False)

    def test_read_is_independent_of_display_and_preserves_document_state(self):
        selected = self.doc.root.children[1]
        self.doc.SelectionManager.selected = [selected]
        selected._visible = 0
        self.doc.dirty = True
        self.doc.view = 4
        self.doc.EditRebuild3 = Mock(side_effect=AssertionError('Read must not rebuild'))
        result = self.invoke()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(self.doc.SelectionManager.selected, [selected])
        self.assertTrue(self.doc.dirty)
        self.assertEqual(self.doc.view, 4)
        self.assertEqual(self.doc.zoom_count, 0)
        self.assertEqual(selected._visible, 0)
        self.assertEqual(selected.visibility_writes, [])
        self.assertEqual(self.doc.Extension.writes, [])
        self.doc.EditRebuild3.assert_not_called()

    def test_unresolved_nodes_are_retained_without_geometry_reads(self):
        nodes = [Component(f'node-{state}', state=state) for state in (0, 1, 4, 5)]
        for node in nodes:
            node.Transform2 = lambda: (_ for _ in ()).throw(AssertionError('Do not read unresolved transform'))
        self.app.ActiveDoc = Document(children=nodes)
        result = self.invoke()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['data']['component_count'], 4)
        self.assertEqual(result['data']['spatial_ok_count'], 0)
        for record, fake in zip(result['data']['components'], nodes):
            self.assertEqual(record['spatial_status'], 'unavailable')
            self.assertIsNone(record['transform'])
            self.assertIsNone(record['bounding_box'])
            self.assertEqual(fake.box_calls, [])
            self.assertTrue(all(e['code'] == 'UNRESOLVED_COMPONENT' for e in record['spatial_errors']))

    def test_missing_transform_or_box_preserves_other_field(self):
        first, second = self.doc.root.children[:2]
        first.Transform2 = None
        second.box = None
        nodes = self.invoke()['data']['components']
        self.assertIsNone(nodes[0]['transform'])
        self.assertIsNotNone(nodes[0]['bounding_box'])
        self.assertIsNone(nodes[1]['bounding_box'])
        self.assertIsNotNone(nodes[1]['transform'])
        self.assertEqual(nodes[0]['spatial_errors'][0]['code'], 'TRANSFORM_UNAVAILABLE')
        self.assertEqual(nodes[1]['spatial_errors'][0]['code'], 'BOUNDING_BOX_UNAVAILABLE')
        self.assertEqual(nodes[0]['spatial_status'], 'partial')

    def test_missing_parent_keeps_child_root_and_box_but_local_is_null(self):
        self.doc.root.children[2].Transform2 = None
        result = self.invoke('slide-1/block-1')
        self.assertEqual(result['status'], 'partial')
        node = result['data']['component']
        self.assertEqual(node['transform']['origin_root_mm'], [1000, 2200, 0])
        self.assertIsNone(node['transform']['to_parent'])
        self.assertIsNone(node['transform']['origin_parent_mm'])
        self.assertIsNotNone(node['bounding_box'])
        self.assertIn('PARENT_TRANSFORM_UNAVAILABLE', [e['code'] for e in result['errors']])

    def test_invalid_values_and_api_errors_are_partial_serializable(self):
        first, second, third = self.doc.root.children
        first.Transform2.ArrayData[9] = float('nan')
        first.box = [0, 0, 0, float('inf'), 1, 1]
        second.GetBox = lambda *args: (_ for _ in ()).throw(RuntimeError('box COM failure'))
        third.Transform2 = lambda: (_ for _ in ()).throw(RuntimeError('transform COM failure'))
        result = self.invoke()
        self.assertEqual(result['status'], 'partial')
        json.dumps(result, allow_nan=False)
        codes = {e['code'] for e in result['errors']}
        self.assertTrue({'INVALID_TRANSFORM', 'INVALID_BOUNDING_BOX', 'SPATIAL_READ_FAILED'} <= codes)

    def test_bounds_and_depth_preserve_partial_nodes(self):
        for kwargs, count, code in [({'max_components': 2}, 2, 'COMPONENT_LIMIT'),
                                    ({'max_depth': 1}, 3, 'DEPTH_LIMIT')]:
            result = self.invoke(**kwargs)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['data']['component_count'], count)
            self.assertFalse(result['data']['complete'])
            self.assertTrue(result['data']['truncated'])
            self.assertIn(code, [e['code'] for e in result['errors']])

    def test_ambiguous_or_incomplete_lookup_is_not_guessed(self):
        self.assertEqual(self.invoke('absent')['errors'][0]['code'], 'COMPONENT_NOT_FOUND')
        self.app.ActiveDoc = Document(children=[Component('same-1'), Component('same-1')])
        result = self.invoke('same-1')
        self.assertEqual(result['errors'][0]['code'], 'AMBIGUOUS_COMPONENT')
        result = self.invoke()
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(all(node['transform'] is None for node in result['data']['components']))
        self.app.ActiveDoc = Document(children=[Component('found-1'), Component('bad-1', fail_children=True)])
        self.assertEqual(self.invoke('found-1')['errors'][0]['code'], 'COMPONENT_LOOKUP_INCOMPLETE')

    def test_failed_metadata_and_unresolved_other_nodes_remain_in_errors(self):
        first, second = self.doc.root.children[:2]
        first.GetPathName = lambda: (_ for _ in ()).throw(RuntimeError('metadata unavailable'))
        second.state = 1
        result = self.invoke('rail-1')
        self.assertEqual(result['status'], 'partial')
        node = result['data']['component']
        self.assertIsNone(node['file_path'])
        self.assertIsNotNone(node['transform'])
        self.assertEqual(node['spatial_status'], 'partial')
        self.assertTrue({'COMPONENT_READ_FAILED', 'UNRESOLVED_COMPONENT'} <= {e['code'] for e in result['errors']})

    def test_no_document_part_stale_token_and_change_during_read(self):
        token = self.token()
        for name in ('sw_component_spatial', 'sw_spatial_inventory'):
            extra = {'occurrence_path': 'rail-1'} if name == 'sw_component_spatial' else {}
            self.app.ActiveDoc = None
            self.assertEqual(self.service.call(name, {'expected_document_token': token, **extra})['errors'][0]['code'], 'NO_ACTIVE_DOCUMENT')
            self.app.ActiveDoc = Document(kind=1)
            self.assertEqual(self.service.call(name, {'expected_document_token': self.token(), **extra})['errors'][0]['code'], 'NOT_ASSEMBLY')
        self.app.ActiveDoc = self.doc
        self.doc.ConfigurationManager.ActiveConfiguration.Name = 'Other'
        result = self.service.call('sw_spatial_inventory', {'expected_document_token': token})
        self.assertEqual(result['errors'][0]['code'], 'DOCUMENT_CHANGED')
        def switch(*args):
            self.app.ActiveDoc = Document(title='New document')
            return [0, 0, 0, 1, 1, 1]
        self.doc.root.children[0].GetBox = switch
        result = self.invoke()
        self.assertEqual(result['errors'][0]['code'], 'DOCUMENT_CHANGED')
        self.assertIsNone(result['data'])

    def test_read_only_schemas_and_argument_validation(self):
        for name in ('sw_component_spatial', 'sw_spatial_inventory'):
            self.assertTrue(CATALOG[name]['annotations']['readOnlyHint'])
            self.assertEqual(self.service.call(name, {})['errors'][0]['code'], 'INVALID_ARGUMENTS')
        for args in ({'max_components': 0}, {'max_components': 5001}, {'max_depth': 129}, {'max_depth': True}, {'extra': 1}):
            self.assertEqual(self.invoke(**args)['errors'][0]['code'], 'INVALID_ARGUMENTS')
