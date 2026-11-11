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
from cadkin.tools.grouping import group_inventory
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.spatial import collect_spatial
from tests.sw_fakes import App, Component, Document, runtime


def fixture():
    children = [Component('frame-1'), Component('lift-1', [Component('lift-1/platform-1'),
                Component('lift-1/servo-1'), Component('lift-1/servo-2'), Component('lift-1/123456-1'),
                Component('lift-1/base-platform-1')])]
    adapter = SolidWorksAdapter(app=App(Document(children=children)), runtime=runtime())
    service = SolidWorksTools(factory=lambda: adapter)
    try:
        return collect_spatial(service, page_size=2)
    finally:
        service.close()


class GroupingTests(unittest.TestCase):
    def setUp(self):
        self.envelope = fixture()
        self.digest = 'a' * 64

    def group(self, **kwargs):
        return group_inventory(self.envelope, self.digest, **kwargs)

    def members(self, result):
        return {m['occurrence_path']: (group['role'], m) for group in result['groups'] for m in group['members']}

    def test_role_evidence_ambiguity_and_repeated_instances(self):
        data = self.group()
        self.assertEqual(data['counts'], {'fixed_base': 1, 'moving_platform': 1, 'transmission_related': 2, 'pending': 2})
        members = self.members(data)
        self.assertNotIn('lift-1', members)
        self.assertEqual(members['lift-1/base-platform-1'][0], 'pending')
        self.assertEqual(members['lift-1/123456-1'][0], 'pending')
        self.assertEqual(members['lift-1/servo-1'][1]['file_path'], members['lift-1/servo-2'][1]['file_path'])
        self.assertTrue(data['coverage']['assigned_once'])
        self.assertTrue(data['requires_review'])
        self.assertEqual(data['manual_confirmed_count'], 0)
        self.assertTrue(all(not m['rigid_body_confirmed'] for _, m in members.values()))
        self.assertTrue(members['frame-1'][1]['evidence'])

    def test_scope_uses_hierarchy_and_does_not_inherit_parent_name(self):
        result = self.group(scope_occurrence_path='lift-1')
        self.assertEqual(result['coverage']['scoped_leaf_occurrences'], 5)
        self.assertNotIn('frame-1', self.members(result))
        # Parent 'platform' must never classify anonymous children by inheritance.
        nodes = self.envelope['data']['components']
        for n in nodes:
            n['occurrence_path'] = n['occurrence_path'].replace('lift-1', 'platform-1')
            if n['parent_occurrence_path']:
                n['parent_occurrence_path'] = n['parent_occurrence_path'].replace('lift-1', 'platform-1')
        self.assertEqual(self.members(self.group())['platform-1/123456-1'][0], 'pending')

    def test_spatial_hints_do_not_become_role_or_rigid_body_proof(self):
        nodes = self.envelope['data']['components']
        for i, n in enumerate(nodes):
            n['bounding_box']['center_mm'] = [i * 100, 0, 0]
        members = self.members(self.group())
        self.assertEqual(members['frame-1'][1]['nearest_box_centers'][0]['box_center_distance_mm'], 200)
        self.assertEqual(members['lift-1/123456-1'][0], 'pending')
        for n in nodes:
            n['bounding_box'] = None
            n['bounding_box_status'] = 'not_requested'
        self.assertTrue(all(m['nearest_box_centers'] == [] for _, m in self.members(self.group()).values()))

    def test_geometry_failure_is_retained_but_partial_hierarchy_or_single_page_rejected(self):
        self.envelope['status'] = 'partial'
        self.envelope['errors'] = [{'code': 'BOUNDING_BOX_UNAVAILABLE', 'message': 'missing'}]
        self.envelope['data']['complete'] = False
        self.assertTrue(self.group()['source_errors'])
        for field in ('collection_complete', 'hierarchy_complete'):
            self.envelope['data'][field] = False
            with self.assertRaises(ToolFailure) as caught:
                self.group()
            self.assertEqual(caught.exception.code, 'GROUPING_REQUIRES_COMPLETE_INVENTORY')
            self.envelope['data'][field] = True

    def test_invalid_parent_duplicate_count_and_cycle_fail(self):
        for mutation in ('missing', 'duplicate', 'count', 'cycle'):
            with self.subTest(mutation=mutation):
                envelope = copy.deepcopy(self.envelope)
                nodes = envelope['data']['components']
                if mutation == 'missing': nodes[0]['parent_occurrence_path'] = 'missing'
                if mutation == 'duplicate': nodes[1]['occurrence_path'] = nodes[0]['occurrence_path']
                if mutation == 'count': envelope['data']['component_count'] += 1
                if mutation == 'cycle': nodes[0]['parent_occurrence_path'] = nodes[0]['occurrence_path']
                with self.assertRaises(ToolFailure):
                    group_inventory(envelope, self.digest)

    def test_manual_review_is_hash_bound_and_only_confirms_requested_leaf(self):
        item = {'occurrence_path': 'lift-1/123456-1', 'role': 'moving_platform', 'decision': 'confirmed', 'reason': 'User verified this occurrence in the assembly.'}
        review = {'inventory_sha256': self.digest, 'assignments': [item]}
        data = self.group(review=review)
        self.assertEqual(data['manual_confirmed_count'], 1)
        self.assertEqual(self.members(data)[item['occurrence_path']][1]['role_status'], 'manual_confirmed')
        self.assertTrue(data['requires_review'])
        bad_reviews = [{**review, 'inventory_sha256': 'b' * 64}, {**review, 'assignments': [item, item]},
                       {**review, 'assignments': [{**item, 'occurrence_path': 'lift-1'}]},
                       {**review, 'assignments': [{**item, 'reason': ''}]},
                       {**review, 'assignments': [{**item, 'decision': 'pending'}]}]
        for bad in bad_reviews:
            with self.assertRaises(ToolFailure): self.group(review=bad)
        with self.assertRaises(ToolFailure):
            self.group(scope_occurrence_path='frame-1', review=review)

    def test_empty_complete_inventory_is_valid_and_has_no_fake_groups(self):
        self.envelope['data']['components'] = []
        self.envelope['data']['component_count'] = 0
        data = self.group()
        self.assertEqual(sum(data['counts'].values()), 0)
        self.assertFalse(data['requires_review'])

    def test_file_tool_is_offline_preserves_source_and_refuses_overwrite_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.dumps(self.envelope).encode()
            (root / 'input.json').write_bytes(raw)
            factory = Mock(side_effect=AssertionError('Offline grouping must not connect to COM'))
            service = SolidWorksTools(root=root, factory=factory)
            self.addCleanup(service.close)
            args = {'inventory_path': 'input.json', 'output_path': 'outputs/groups.json'}
            result = service.call('cad_group_components', args)
            self.assertEqual(result['status'], 'ok', result)
            self.assertEqual(result['data']['inventory_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertTrue((root / 'outputs/groups.json').is_file())
            self.assertEqual((root / 'input.json').read_bytes(), raw)
            self.assertEqual(service.call('cad_group_components', args)['errors'][0]['code'], 'OUTPUT_EXISTS')
            for path in ('../outside.json', 'input.json'):
                self.assertEqual(service.call('cad_group_components', {**args, 'output_path': path})['errors'][0]['code'], 'INVALID_PATH')
            (root / 'bad.json').write_text('{"v":1e999}')
            failed = service.call('cad_group_components', {**args, 'inventory_path': 'bad.json', 'output_path': 'outputs/bad.json'})
            self.assertEqual(failed['errors'][0]['code'], 'INVALID_INPUT')
            self.assertFalse((root / 'outputs/bad.json').exists())
            factory.assert_not_called()

    def test_real_cli_offline_group_and_output_are_usable(self):
        root = Path.cwd()
        (root / 'outputs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory:
            source = Path(directory) / 'inventory.json'
            output = Path(directory) / 'groups.json'
            source.write_text(json.dumps(self.envelope), encoding='utf-8')
            run = subprocess.run([sys.executable, '-m', 'cadkin', 'group', str(source), '--output', str(output)],
                                 capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertFalse(result['data']['solidworks_modified'])
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['coverage']['scoped_leaf_occurrences'], 6)
