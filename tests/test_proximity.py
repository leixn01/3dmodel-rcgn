import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.distance import distance_result
from cadkin.errors import ToolFailure
from cadkin.geometry import bounding_box
from cadkin.tools.proximity import proximity_candidates
from cadkin.tools.proximity_review import review_proximity
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.spatial import collect_spatial
from tests.distance_fakes import distance_document
from tests.sw_fakes import Component, Document, pose, runtime


def save_inventory(root, service, boxes=True):
    inventory = collect_spatial(service, page_size=2, include_bounding_boxes=boxes)
    raw = json.dumps(inventory).encode('utf-8')
    (root / 'inventory.json').write_bytes(raw)
    return inventory, hashlib.sha256(raw).hexdigest()


class DistanceTests(unittest.TestCase):
    def setUp(self):
        self.doc, app = distance_document()
        self.service = SolidWorksTools(factory=lambda: SolidWorksAdapter(app=app, runtime=runtime()))
        self.addCleanup(self.service.close)
        self.token = self.service.call('sw_active_document')['data']['document_token']

    def read(self, left='base-1', right='slider-1', **extra):
        return self.service.call('sw_component_distance', {'expected_document_token': self.token,
            'left_occurrence_path': left, 'right_occurrence_path': right, **extra})

    def test_minimum_gap_witness_units_and_readonly(self):
        before = (self.doc.dirty, self.doc.rebuilt, list(self.doc.SelectionManager.selected))
        result = self.read()
        self.assertEqual(result['status'], 'ok', result)
        data = result['data']; m = data['measurement']
        self.assertAlmostEqual(m['distance_mm'], .05)
        self.assertEqual(m['point_left_mm'], [1000, 0, 0])
        self.assertAlmostEqual(m['point_right_mm'][0], 1000.05)
        self.assertFalse(data['contact_confirmed'])
        self.assertEqual(before, (self.doc.dirty, self.doc.rebuilt, self.doc.SelectionManager.selected))
        self.assertEqual(self.doc.distance_calls, [('base-1', 'slider-1')])

    def test_reversed_pair_swaps_witnesses_not_distance(self):
        a = self.read()['data']['measurement']; b = self.read('slider-1', 'base-1')['data']['measurement']
        self.assertEqual(a['distance_mm'], b['distance_mm'])
        self.assertEqual(a['point_left_m'], b['point_right_m'])

    def test_touching_overlapping_and_contained_not_confirmed(self):
        for box in ([1, 0, 0, 2, 1, 1], [.9, 0, 0, 2, 1, 1], [.2, .2, .2, .8, .8, .8]):
            self.doc.root.children[1].geometry_box = box
            result = self.read()
            self.assertEqual(result['status'], 'ok', result)
            self.assertEqual(result['data']['measurement']['distance_mm'], 0)
            self.assertFalse(result['data']['contact_confirmed'])
            self.assertFalse(result['data']['mechanical_relation_confirmed'])

    def test_no_solution_nonfinite_and_missing_points_are_partial(self):
        for raw in (-1, -2, float('nan'), float('inf'), True, 0):
            self.doc.ClosestDistance = lambda *args: raw
            result = self.read()
            self.assertEqual(result['status'], 'partial', result)
            self.assertIsNone(result['data']['measurement'])
            self.assertEqual(result['data']['measurement_status'], 'unavailable')

    def test_api_failure_not_zero_and_service_recovers(self):
        original = self.doc.ClosestDistance
        self.doc.ClosestDistance = lambda *a: (_ for _ in ()).throw(RuntimeError('fixture API error'))
        result = self.read()
        self.assertEqual(result['status'], 'partial', result)
        self.assertIn('fixture API error', result['errors'][0]['message'])
        self.doc.ClosestDistance = original
        self.assertEqual(self.read()['status'], 'ok')

    def test_inconsistent_witness_distance_rejected(self):
        original = self.doc.ClosestDistance
        def bad(*a): original(*a); return 100
        self.doc.ClosestDistance = bad
        result = self.read()
        self.assertEqual(result['status'], 'partial', result)
        self.assertEqual(result['errors'][0]['code'], 'DISTANCE_POINT_MISMATCH')

    def test_same_missing_unresolved_and_subassembly_targets_rejected(self):
        self.assertEqual(self.read('base-1', 'base-1')['errors'][0]['code'], 'INVALID_ARGUMENTS')
        self.assertEqual(self.read('missing')['errors'][0]['code'], 'COMPONENT_NOT_FOUND')
        self.doc.root.children[0].state = 0
        self.assertEqual(self.read()['errors'][0]['code'], 'UNRESOLVED_COMPONENT')
        self.doc.root.children[0].state = 2
        self.doc.root.children[0].model_doc = Document()
        self.assertEqual(self.read()['errors'][0]['code'], 'NOT_PART_COMPONENT')
        self.assertEqual(len(self.doc.distance_calls), 0)

    def test_nested_occurrence_points_are_not_transformed_again(self):
        child = self.doc.root.children[0]
        child.Name2 = 'nested-1/base-1'; child.Transform2 = pose(x=2, quarter_turn=True)
        parent = Component('nested-1', [child]); parent.model_doc = Document()
        self.doc.root.children[0] = parent
        result = self.read(child.Name2)
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(result['data']['targets'][0]['parent_occurrence_path'], 'nested-1')
        self.assertEqual(result['data']['measurement']['point_left_mm'], [1000, 0, 0])

    def test_context_changes_discard_mixed_result(self):
        original = self.doc.ClosestDistance
        def moved(*a):
            d = original(*a); self.doc.root.children[0].Transform2 = pose(x=1); return d
        self.doc.ClosestDistance = moved
        self.assertEqual(self.read()['errors'][0]['code'], 'COMPONENT_CHANGED')
        def changed(*a):
            d = original(*a); self.doc.title = 'Different'; return d
        self.doc.ClosestDistance = changed
        self.assertEqual(self.read()['errors'][0]['code'], 'DOCUMENT_CHANGED')

    def test_loaded_configuration_and_in_context_edit_guards(self):
        self.doc.editing_self = False
        self.assertEqual(self.read()['errors'][0]['code'], 'IN_CONTEXT_EDIT_ACTIVE')
        self.doc.editing_self = True
        self.doc.root.children[0].model_doc.ConfigurationManager.ActiveConfiguration.Name = 'Other'
        self.assertEqual(self.read()['errors'][0]['code'], 'COMPONENT_CONFIGURATION_MISMATCH')

    def test_edit_target_change_after_measurement_rejected(self):
        original = self.doc.ClosestDistance
        def changed(*a):
            d = original(*a); self.doc.editing_self = False; return d
        self.doc.ClosestDistance = changed
        self.assertEqual(self.read()['errors'][0]['code'], 'IN_CONTEXT_EDIT_ACTIVE')

    @unittest.skipUnless(sys.platform == 'win32', 'Requires Windows pywin32')
    def test_real_pywin32_byref_variant_point_arrays(self):
        import pythoncom
        import win32com.client
        v = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
        self.assertEqual(v.varianttype, pythoncom.VT_BYREF | pythoncom.VT_VARIANT)
        v.value = (1., 2., 3.)
        self.assertEqual(list(v.value), [1., 2., 3.])


class ProximityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc, app = distance_document()
        self.service = SolidWorksTools(root=self.root, factory=lambda: SolidWorksAdapter(app=app, runtime=runtime()))
        self.addCleanup(self.service.close)
        self.inventory, self.digest = save_inventory(self.root, self.service)
        self.token = self.inventory['data']['document']['document_token']

    def candidates(self, **parameters):
        return proximity_candidates(self.inventory, self.digest, **{'max_box_gap_mm': 30, **parameters})

    def measure(self, left, right):
        return self.service.call('sw_component_distance', {'expected_document_token': self.token,
            'left_occurrence_path': left, 'right_occurrence_path': right})

    def sources(self):
        return [(self.measure(*pair), 'd' + str(i) + '.json', str(i) * 64)
                for i, pair in enumerate((('base-1', 'slider-1'), ('shaft-1', 'slider-1')))]

    def review(self, sources=None, **parameters):
        return review_proximity(self.candidates(), self.inventory, self.digest,
                                self.sources() if sources is None else sources, parameters.get('contact_tolerance_mm', .1))

    def test_hints_are_sorted_leaf_instance_pairs(self):
        data = self.candidates()
        self.assertEqual([c['occurrence_paths'] for c in data['candidates']], [['base-1', 'slider-1'], ['shaft-1', 'slider-1']])
        self.assertEqual(data['coverage']['checked_pairs'], 6)
        self.assertTrue(data['complete'])
        self.assertFalse(data['contact_confirmed'])

    def test_bounding_box_overlap_does_not_mean_zero_geometric_distance(self):
        self.inventory['data']['components'][1]['bounding_box'] = bounding_box([0, 0, 0, 6, 1, 1])  # cap-1
        data = self.candidates()
        pair = next(c for c in data['candidates'] if c['occurrence_paths'] == ['base-1', 'cap-1'])
        self.assertEqual(pair['box_gap_hint_mm'], 0)
        self.assertEqual(self.measure('base-1', 'cap-1')['data']['measurement']['distance_mm'], 4000)

    def test_missing_boxes_are_unranked_not_zero(self):
        for node in self.inventory['data']['components']: node['bounding_box'] = None
        data = self.candidates()
        self.assertEqual(data['candidates'], [])
        self.assertEqual(len(data['unranked_occurrences']), 4)
        self.assertFalse(data['complete'])

    def test_budget_prefix_and_output_limits_keep_partial(self):
        data = self.candidates(max_pairs=1, max_box_gap_mm=10000)
        self.assertEqual(data['coverage']['checked_pairs'], 1)
        self.assertFalse(data['pair_scan_complete'])
        self.assertTrue(data['truncated'])
        data = self.candidates(max_candidates=1)
        self.assertEqual(len(data['candidates']), 1)
        self.assertTrue(data['pair_scan_complete'])
        self.assertFalse(data['complete'])
        self.assertTrue(self.candidates(max_pairs=6, max_candidates=2)['complete'])

    def test_selected_scope_and_invalid_thresholds(self):
        data = self.candidates(occurrence_paths=['base-1', 'slider-1'])
        self.assertEqual(data['coverage']['scope_pairs'], 1)
        for args in ({'max_box_gap_mm': -1}, {'max_box_gap_mm': float('nan')}, {'max_pairs': 0},
                     {'occurrence_paths': ['base-1', 'base-1']}, {'occurrence_paths': ['missing', 'base-1']}):
            with self.assertRaises(ToolFailure): self.candidates(**args)

    def test_incomplete_hierarchy_rejected_and_source_partial_preserved(self):
        self.inventory['data']['collection_complete'] = False
        with self.assertRaises(ToolFailure): self.candidates()
        self.inventory['data']['collection_complete'] = True
        self.inventory['status'] = 'partial'; self.inventory['data']['complete'] = False
        self.inventory['errors'] = [{'code': 'SOURCE_FAILURE', 'message': 'fixture'}]
        self.assertFalse(self.candidates()['complete'])

    def test_box_units_and_derived_fields_validated(self):
        self.inventory['data']['components'][0]['bounding_box']['min_mm'][0] = 200
        data = self.candidates()
        self.assertEqual(len(data['unranked_occurrences']), 1)
        self.assertFalse(data['complete'])

    def test_review_near_contact_and_separated_without_mates(self):
        data = self.review()
        self.assertEqual(data['counts'], {'near_contact_candidate': 1, 'separated_at_measurement': 1, 'unresolved': 0, 'unmeasured': 0})
        self.assertTrue(data['complete'])
        self.assertFalse(data['contact_confirmed'])
        self.assertFalse(data['mechanical_relation_confirmed'])
        self.assertTrue(data['requires_review'])

    def test_review_explicit_tolerance_changes_candidates(self):
        data = self.review(contact_tolerance_mm=.01)
        self.assertEqual(data['counts']['near_contact_candidate'], 0)
        self.assertEqual(data['counts']['separated_at_measurement'], 2)
        with self.assertRaises(ToolFailure): self.review(contact_tolerance_mm=-.1)

    def test_unmeasured_and_failed_distances_stay_unknown(self):
        sources = self.sources()
        data = self.review(sources[:1])
        self.assertEqual(data['counts']['unmeasured'], 1)
        self.assertFalse(data['complete'])
        self.doc.ClosestDistance = lambda *a: -1
        data = self.review()
        self.assertEqual(data['counts']['unresolved'], 2)
        self.assertEqual(data['counts']['near_contact_candidate'], 0)

    def test_reverse_order_duplicate_and_outside_scope(self):
        sources = self.sources()
        sources[0] = (self.measure('slider-1', 'base-1'), 'reverse.json', 'f' * 64)
        self.assertTrue(self.review(sources)['complete'])
        with self.assertRaises(ToolFailure) as caught: self.review(sources + [sources[0]])
        self.assertEqual(caught.exception.code, 'DUPLICATE_DISTANCE_SOURCE')
        with self.assertRaises(ToolFailure) as caught: self.review([(self.measure('base-1', 'cap-1'), 'other.json', '0' * 64)])
        self.assertEqual(caught.exception.code, 'DISTANCE_OUTSIDE_SCOPE')

    def test_pose_document_and_units_mismatch_rejected(self):
        for change in (lambda d: d['document'].update(configuration='Other'),
                       lambda d: d['targets'][0]['transform']['raw_array'].__setitem__(9, 5),
                       lambda d: d['units'].update(api_length='mm')):
            sources = self.sources(); change(sources[0][0]['data'])
            with self.assertRaises(ToolFailure): self.review(sources)

    def test_edited_worklist_and_distance_numbers_rejected(self):
        worklist = self.candidates(); worklist['candidates'][0]['box_gap_hint_mm'] = 0
        with self.assertRaises(ToolFailure): review_proximity(worklist, self.inventory, self.digest, self.sources(), .1)
        sources = self.sources(); sources[0][0]['data']['measurement']['distance_mm'] = 0
        with self.assertRaises(ToolFailure): self.review(sources)

    def test_partial_source_keeps_valid_measured_value(self):
        sources = self.sources(); env = sources[0][0]
        env.update(status='partial', errors=[{'code': 'OTHER_METADATA_FAILURE', 'message': 'fixture'}]); env['data']['complete'] = False
        result = self.review(sources)
        self.assertFalse(result['complete'])
        self.assertEqual(result['counts']['near_contact_candidate'], 1)

    def test_offline_tools_files_hash_and_no_cad(self):
        def forbidden(): raise AssertionError('Offline tool connected COM')
        offline = SolidWorksTools(root=self.root, factory=forbidden)
        self.addCleanup(offline.close)
        args = {'inventory_path': 'inventory.json', 'output_path': 'outputs/proximity.json', 'max_box_gap_mm': 30}
        self.assertEqual(offline.call('cad_proximity_candidates', args)['status'], 'ok')
        self.assertEqual(offline.call('cad_proximity_candidates', args)['errors'][0]['code'], 'OUTPUT_EXISTS')
        for envelope, name, _ in self.sources(): (self.root / name).write_text(json.dumps(envelope), encoding='utf-8')
        review_args = {'proximity_path': 'outputs/proximity.json', 'distance_paths': ['d0.json', 'd1.json'],
                       'contact_tolerance_mm': .1, 'output_path': 'outputs/review.json'}
        result = offline.call('cad_review_proximity', review_args)
        self.assertEqual(result['status'], 'ok', result)
        worklist = json.loads((self.root / 'outputs/proximity.json').read_text())
        self.assertEqual(worklist['inventory_sha256'], self.digest)
        (self.root / 'inventory.json').write_text(json.dumps(self.inventory, indent=1), encoding='utf-8')
        result = offline.call('cad_review_proximity', {**review_args, 'output_path': 'outputs/invalid.json'})
        self.assertEqual(result['errors'][0]['code'], 'EVIDENCE_MISMATCH')
        self.assertFalse((self.root / 'outputs/invalid.json').exists())

    def test_shared_cli_roundtrip(self):
        for envelope, name, _ in self.sources(): (self.root / name).write_text(json.dumps(envelope), encoding='utf-8')
        for args in (['proximity', 'inventory.json', '--max-box-gap-mm', '30', '--output', 'outputs/proximity.json'],
                     ['review-proximity', 'outputs/proximity.json', '--distances', 'd0.json', 'd1.json', '--contact-tolerance-mm', '.1', '--output', 'outputs/review.json']):
            result = subprocess.run([sys.executable, '-m', 'cadkin', *args], cwd=self.root, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(json.loads(result.stdout)['status'], 'ok')


if __name__ == '__main__': unittest.main()
