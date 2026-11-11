import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.errors import ToolFailure
from cadkin.geometry import cylinder_from_sw
from cadkin.tools.grouping import group_inventory
from cadkin.tools.relations import relate_axes, axis_metrics
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.spatial import collect_spatial
from tests.evidence_fakes import Part
from tests.sw_fakes import App, Component, Document, pose, runtime


def fixtures():
    children = [Component('shaft-1'), Component('shaft-2'), Component('rail-1')]
    children[1].Transform2 = pose(z=3)
    children[2].Transform2 = pose(x=0.1)
    part = Part()
    for child in children: child.model_doc = part
    service = SolidWorksTools(factory=lambda: SolidWorksAdapter(app=App(Document(children=children)), runtime=runtime()))
    try:
        inventory = collect_spatial(service, page_size=2, include_bounding_boxes=False)
        token = inventory['data']['document']['document_token']
        sources = []
        for child in children:
            result = service.call('sw_component_cylinders', {'expected_document_token': token, 'occurrence_path': child.Name2})
            assert result['status'] == 'ok', result
            sources.append((result, child.Name2 + '.json', hashlib.sha256(json.dumps(result).encode()).hexdigest()))
        return inventory, sources
    finally:
        service.close()


def write_fixture(root):
    inventory, sources = fixtures()
    raw = json.dumps(inventory).encode()
    (root / 'inventory.json').write_bytes(raw)
    for envelope, name, _ in sources:
        (root / name).write_text(json.dumps(envelope), encoding='utf-8')
    groups = group_inventory(inventory, hashlib.sha256(raw).hexdigest())
    (root / 'groups.json').write_text(json.dumps(groups), encoding='utf-8')
    return {'inventory_path': 'inventory.json', 'cylinder_paths': [s[1] for s in sources],
            'output_path': 'outputs/relations.json', 'distance_tolerance_mm': 0.1, 'angle_tolerance_deg': 0.1,
            'grouping_path': 'groups.json'}


class RelationsTests(unittest.TestCase):
    def setUp(self):
        self.inventory, self.sources = fixtures()
        self.digest = 'a' * 64

    def run_relations(self, **kwargs):
        return relate_axes(self.inventory, self.digest, self.sources, **{
            'distance_tolerance_mm': 0.1, 'angle_tolerance_deg': 0.1, **kwargs})

    def error(self, code):
        with self.assertRaises(ToolFailure) as caught: self.run_relations()
        self.assertEqual(caught.exception.code, code)

    def change_axis(self, index, raw):
        data = self.sources[index][0]['data']
        row = data['cylinders'][0]
        row.update(cylinder_from_sw(raw, data['transform']))

    def test_coaxial_parallel_instances_and_provenance(self):
        data = self.run_relations()
        self.assertEqual(data['counts'], {'coaxial_candidate': 1, 'parallel_candidate': 2})
        self.assertTrue(data['complete'])
        self.assertEqual(data['coverage']['checked_pairs'], 3)
        self.assertEqual(len(data['sources']), 3)  # same file, distinct occurrences
        self.assertEqual(len({s['file_path'] for s in data['sources']}), 1)
        coaxial = next(c for c in data['candidates'] if c['kind'] == 'coaxial_candidate')
        self.assertEqual(coaxial['axis_offset_at_reference_mm'], 0)
        self.assertEqual(coaxial['reference_root_mm'], [0, 0, 1500])
        self.assertTrue(data['requires_review'])
        self.assertFalse(data['mechanical_relation_confirmed'])
        self.assertTrue(all(not c['mechanical_relation_confirmed'] for c in data['candidates']))

    def test_axis_sign_point_choice_and_radius_do_not_define_a_joint(self):
        self.change_axis(1, [0, 0, -7, 0, 0, -2, 0.25])
        data = self.run_relations()
        self.assertEqual(data['counts']['coaxial_candidate'], 1)
        pair = next(c for c in data['candidates'] if c['kind'] == 'coaxial_candidate')
        self.assertEqual(pair['angle_deg'], 0)
        self.assertEqual(pair['right']['radius_root_mm'], 250)
        self.assertFalse(pair['mechanical_relation_confirmed'])

    def test_near_parallel_offset_is_reference_based_and_origin_invariant(self):
        angle = math.radians(0.05)
        u = [0, 0, 1]
        v = [math.sin(angle), 0, math.cos(angle)]
        a = {'origin_root_mm': [0, 0, 0], 'axis_root_unit': u}
        b = {'origin_root_mm': [0, 0, 0], 'axis_root_unit': v}
        first = axis_metrics(a, b, [0, 0, 1000])
        b['origin_root_mm'] = [q * 5000 for q in v]
        second = axis_metrics(a, b, [0, 0, 1000])
        self.assertAlmostEqual(first['axis_offset_at_reference_mm'], 1000 * math.sin(angle), places=8)
        self.assertAlmostEqual(first['axis_offset_at_reference_mm'], second['axis_offset_at_reference_mm'], places=8)
        self.assertAlmostEqual(second['angle_deg'], 0.05)
        # Axes intersect at zero, but offset at the assembly reference is not zero.
        self.assertGreater(second['axis_offset_at_reference_mm'], 0.1)

    def test_thresholds_and_perpendicular_exclusion(self):
        self.change_axis(1, [0.001, 0, 0, 0, 0, 1, 0.01])
        self.assertEqual(self.run_relations()['counts']['coaxial_candidate'], 0)
        self.assertEqual(self.run_relations(distance_tolerance_mm=1)['counts']['coaxial_candidate'], 1)
        self.change_axis(1, [0, 0, 0, 1, 0, 0, 0.01])
        data = self.run_relations()
        self.assertEqual(data['coverage']['nonparallel_pairs'], 2)
        self.assertEqual(len(data['candidates']), 1)

    def test_partial_source_retains_candidates_and_errors(self):
        env = self.sources[0][0]
        env.update(status='partial', errors=[{'code': 'FACE_LIMIT', 'message': 'fixture budget'}])
        env['data'].update(complete=False, truncated=True)
        data = self.run_relations()
        self.assertFalse(data['complete'])
        self.assertTrue(data['comparison_complete'])
        self.assertFalse(data['truncated'])  # comparison limit distinct from source limit
        self.assertEqual(data['errors'][0]['source_errors'][0]['code'], 'FACE_LIMIT')
        self.assertEqual(len(data['candidates']), 3)

    def test_zero_cylinders_and_empty_candidates_are_not_absent_joints(self):
        for e, _, _ in self.sources: e['data'].update(cylinders=[], cylinder_count=0)
        data = self.run_relations()
        self.assertTrue(data['complete'])
        self.assertTrue(data['comparison_complete'])
        self.assertEqual(data['candidates'], [])
        self.assertEqual(len(data['coverage']['zero_cylinder_occurrences']), 3)
        self.assertTrue(data['requires_review'])

    def test_budgets_and_exact_completion(self):
        for options in ({'max_pairs': 1}, {'max_candidates': 1}):
            data = self.run_relations(**options)
            self.assertEqual(data['coverage']['checked_pairs'], 1)
            self.assertFalse(data['comparison_complete'])
            self.assertTrue(data['truncated'])
            self.assertEqual(data['errors'][-1]['code'], 'RELATION_LIMIT')
        self.assertTrue(self.run_relations(max_pairs=3, max_candidates=3)['complete'])

    def test_split_faces_are_retained_not_counted_as_unique_connections(self):
        data = self.sources[0][0]['data']
        extra = copy.deepcopy(data['cylinders'][0]); extra['face_index'] += 1
        data['cylinders'].append(extra); data['cylinder_count'] += 1
        result = self.run_relations()
        self.assertEqual(result['coverage']['total_possible_pairs'], 5)
        self.assertEqual(result['counts']['coaxial_candidate'], 2)
        self.assertEqual(result['coverage']['input_occurrences'], 3)

    def test_duplicate_snapshots_rejected(self):
        self.sources[1] = self.sources[0]
        self.error('INVALID_RELATION_SOURCE')

    def test_mixed_document_config_transform_and_missing_path_rejected(self):
        original = copy.deepcopy(self.sources)
        for change in ('document', 'configuration', 'transform', 'path'):
            self.sources = copy.deepcopy(original)
            data = self.sources[0][0]['data']
            if change == 'document': data['document']['document_token'] = 'b' * 24
            if change == 'configuration': data['referenced_configuration'] = 'Other'
            if change == 'transform': data['transform']['raw_array'][9] += 0.01
            if change == 'path': data['occurrence_path'] = 'missing'
            with self.subTest(change=change): self.error('EVIDENCE_MISMATCH')

    def test_bad_units_scope_derived_values_and_missing_raw_rejected(self):
        original = copy.deepcopy(self.sources)
        for change in ('units', 'scope', 'derived', 'raw', 'duplicate_face', 'count'):
            self.sources = copy.deepcopy(original)
            data = self.sources[0][0]['data']
            if change == 'units': data['units']['api_length'] = 'mm'
            if change == 'scope': data['geometry_scope'] = 'unknown'
            if change == 'derived': data['cylinders'][0]['origin_root_mm'][0] += 1
            if change == 'raw': data['cylinders'][0]['raw_array'] = None
            if change == 'duplicate_face':
                data['cylinders'].append(copy.deepcopy(data['cylinders'][0])); data['cylinder_count'] += 1
            if change == 'count': data['cylinder_count'] = 99
            with self.subTest(change=change):
                with self.assertRaises(ToolFailure): self.run_relations()

    def test_incomplete_inventory_and_unavailable_transform_rejected(self):
        self.inventory['data']['collection_complete'] = False
        self.error('INCOMPLETE_INVENTORY')
        self.inventory['data']['collection_complete'] = True
        self.inventory['data']['components'][0]['transform'] = None
        self.error('INVALID_RELATION_SOURCE')

    def test_grouping_hash_bound_context_not_promoted(self):
        group = group_inventory(self.inventory, self.digest)
        result = self.run_relations(grouping=group)
        rail = next(s for s in result['sources'] if s['occurrence_path'] == 'rail-1')
        self.assertEqual(rail['role_context']['role'], 'transmission_related')
        self.assertEqual(rail['role_context']['role_status'], 'candidate')
        group['source']['inventory_sha256'] = 'b' * 64
        with self.assertRaises(ToolFailure) as caught: self.run_relations(grouping=group)
        self.assertEqual(caught.exception.code, 'EVIDENCE_MISMATCH')

    def test_invalid_tolerances_and_budgets(self):
        for args in ({'angle_tolerance_deg': 0}, {'angle_tolerance_deg': 6}, {'distance_tolerance_mm': -1},
                     {'distance_tolerance_mm': float('inf')}, {'angle_tolerance_deg': float('nan')},
                     {'distance_tolerance_mm': True}, {'max_pairs': 0}, {'max_candidates': 5001}):
            with self.subTest(args=args):
                with self.assertRaises(ToolFailure) as caught: self.run_relations(**args)
                self.assertEqual(caught.exception.code, 'INVALID_ARGUMENTS')

    def test_file_tool_offline_source_hash_immutability_and_path_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); args = write_fixture(root)
            before = {p.name: p.read_bytes() for p in root.glob('*.json')}
            factory = Mock(side_effect=AssertionError('Offline tool connected to COM'))
            service = SolidWorksTools(root=root, factory=factory); self.addCleanup(service.close)
            result = service.call('cad_component_relations', args)
            self.assertEqual(result['status'], 'ok', result)
            output = json.loads((root / args['output_path']).read_text(encoding='utf-8'))
            self.assertEqual(output['inventory_sha256'], hashlib.sha256(before['inventory.json']).hexdigest())
            self.assertTrue(all(s['source_sha256'] == hashlib.sha256(before[Path(s['source_path']).name]).hexdigest() for s in output['sources']))
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.glob('*.json')})
            self.assertEqual(service.call('cad_component_relations', args)['errors'][0]['code'], 'OUTPUT_EXISTS')
            for override in ({'output_path': 'elsewhere.json'}, {'output_path': '../outside.json'},
                             {'output_path': 'outputs/new.json', 'inventory_path': '../outside.json'}):
                self.assertEqual(service.call('cad_component_relations', {**args, **override})['errors'][0]['code'], 'INVALID_PATH')
            bad = {**args, 'output_path': 'outputs/bad.json'}; del bad['angle_tolerance_deg']
            self.assertEqual(service.call('cad_component_relations', bad)['errors'][0]['code'], 'INVALID_ARGUMENTS')
            self.assertFalse((root / 'outputs/bad.json').exists())
            factory.assert_not_called()

    def test_cli_offline_roundtrip_and_error_exit(self):
        (Path.cwd() / 'outputs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path.cwd() / 'outputs') as directory:
            root = Path(directory); args = write_fixture(root)
            command = [sys.executable, '-m', 'cadkin', 'relations', str(root / 'inventory.json'), '--cylinders',
                       *[str(root / p) for p in args['cylinder_paths']], '--output', str(root / 'outputs/relations.json'),
                       '--distance-tolerance-mm', '0.1', '--angle-tolerance-deg', '0.1', '--grouping', str(root / 'groups.json')]
            run = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            self.assertEqual(json.loads(run.stdout)['data']['counts']['coaxial_candidate'], 1)
            repeat = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(repeat.returncode, 2)
            self.assertEqual(json.loads(repeat.stdout)['errors'][0]['code'], 'OUTPUT_EXISTS')
