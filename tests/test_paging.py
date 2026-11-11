import copy
import unittest
from unittest.mock import Mock

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.spatial import collect_spatial
from tests.sw_fakes import App, Component, Document, runtime


class PagingTests(unittest.TestCase):
    def setUp(self):
        self.doc = Document(children=[Component(f'part-{i:03}') for i in range(254)])
        self.app = App(self.doc)
        self.adapter = SolidWorksAdapter(app=self.app, runtime=runtime())
        self.service = SolidWorksTools(factory=lambda: self.adapter)
        self.addCleanup(self.service.close)
        self.token = self.service.call('sw_active_document')['data']['document_token']

    def page(self, **kwargs):
        return self.service.call('sw_spatial_inventory', {'expected_document_token': self.token, **kwargs})

    def test_default_page_reads_only_twenty_boxes_and_reports_more(self):
        result = self.page()
        self.assertEqual(result['status'], 'ok', result)
        data = result['data']
        self.assertEqual(data['component_count'], 20)
        self.assertEqual(sum(len(x.box_calls) for x in self.doc.root.children), 20)
        self.assertEqual(data['pagination']['total_components'], 254)
        self.assertEqual(data['pagination']['next_offset'], 20)
        self.assertFalse(data['collection_complete'])
        self.assertFalse(data['complete'])
        self.assertTrue(data['hierarchy_complete'])

    def test_all_pages_cover_254_unique_occurrences_and_read_each_box_once(self):
        result = collect_spatial(self.service, page_size=5)
        self.assertEqual(result['status'], 'ok', result)
        data = result['data']
        self.assertEqual((data['component_count'], data['pages_collected']), (254, 51))
        self.assertTrue(data['complete'])
        self.assertEqual(len({n['occurrence_path'] for n in data['components']}), 254)
        self.assertTrue(all(len(x.box_calls) == 1 for x in self.doc.root.children))

    def test_continuations_require_matching_signature_scope_and_offset(self):
        first = self.page(page_size=5)['data']
        signature = first['inventory_signature']
        self.assertEqual(self.page(offset=5)['errors'][0]['code'], 'INVALID_ARGUMENTS')
        for args, code in [({'offset': 254}, 'PAGE_OUT_OF_RANGE'),
                           ({'offset': 5, 'max_depth': 1}, 'INVENTORY_CHANGED'),
                           ({'offset': 5, 'include_bounding_boxes': False}, 'INVENTORY_CHANGED')]:
            result = self.page(expected_inventory_signature=signature, **args)
            self.assertEqual(result['errors'][0]['code'], code)
        self.doc.root.children[0].Name2 = 'renamed-1'
        self.assertEqual(self.page(offset=5, expected_inventory_signature=signature)['errors'][0]['code'], 'INVENTORY_CHANGED')

    def test_last_page_alone_is_not_complete_inventory(self):
        first = self.page()['data']
        data = self.page(offset=250, expected_inventory_signature=first['inventory_signature'])['data']
        self.assertFalse(data['pagination']['has_more'])
        self.assertFalse(data['collection_complete'])
        self.assertFalse(data['complete'])

    def test_without_boxes_never_calls_getbox_and_preserves_unknowns(self):
        for node in self.doc.root.children:
            node.GetBox = Mock(side_effect=AssertionError('No geometry read'))
        result = collect_spatial(self.service, include_bounding_boxes=False)
        self.assertEqual(result['status'], 'ok', result)
        self.assertTrue(result['data']['complete'])
        for node, record in zip(self.doc.root.children, result['data']['components']):
            node.GetBox.assert_not_called()
            self.assertIsNone(record['bounding_box'])
            self.assertEqual(record['bounding_box_status'], 'not_requested')

    def test_mid_collection_change_preserves_evidence_but_marks_incomplete(self):
        original = self.service.call
        def changing(name, args=None):
            if args and args.get('offset') == 5:
                self.doc.root.children.pop()
            return original(name, args)
        self.service.call = changing
        result = collect_spatial(self.service, page_size=5)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['data']['component_count'], 5)
        self.assertFalse(result['data']['collection_complete'])
        self.assertEqual(result['errors'][0]['code'], 'INVENTORY_CHANGED')

    def test_geometry_failure_keeps_complete_hierarchy_and_truncation_does_not(self):
        self.doc.root.children[0].box = None
        result = collect_spatial(self.service)
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['data']['collection_complete'])
        self.assertTrue(result['data']['hierarchy_complete'])
        self.assertFalse(result['data']['complete'])
        limited = collect_spatial(self.service, max_components=2)
        self.assertTrue(limited['data']['truncated'])
        self.assertFalse(limited['data']['hierarchy_complete'])

    def test_empty_assembly_and_invalid_paging_arguments(self):
        self.doc.root.children = []
        data = collect_spatial(self.service)['data']
        self.assertTrue(data['complete'])
        self.assertEqual(data['component_count'], 0)
        for args in ({'page_size': 0}, {'page_size': 101}, {'offset': -1}, {'include_bounding_boxes': 1}):
            self.assertEqual(self.page(**args)['errors'][0]['code'], 'INVALID_ARGUMENTS')

    def test_collector_rejects_repeated_records_and_bad_page_coverage(self):
        first = self.page(page_size=5)
        bad = copy.deepcopy(first)
        bad['data']['pagination']['offset'] = 5
        for mutation in ('duplicate', 'bad_next'):
            if mutation == 'bad_next':
                bad = copy.deepcopy(first)
                bad['data']['pagination']['next_offset'] = 7
            fake = Mock()
            fake.call.side_effect = [{'status': 'ok', 'data': {'document_token': self.token}}, first, bad]
            result = collect_spatial(fake, page_size=5)
            self.assertFalse(result['data']['collection_complete'])
            self.assertEqual(result['status'], 'partial')

    def test_hierarchy_failure_on_later_page_cannot_claim_complete_collection(self):
        original = self.service.call
        def failing_child(name, args=None):
            if args and args.get('offset') == 5:
                self.doc.root.children[0].fail_children = True
            return original(name, args)
        self.service.call = failing_child
        result = collect_spatial(self.service, page_size=5)
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['data']['collection_complete'])
        self.assertFalse(result['data']['complete'])
        self.assertEqual(result['errors'][0]['code'], 'INVENTORY_CHANGED')

    def test_spatial_export_cli_writes_collected_json_not_only_one_page(self):
        from contextlib import redirect_stdout
        import io
        import json
        from pathlib import Path
        import sys
        import tempfile
        from unittest.mock import patch
        from cadkin.__main__ import main
        root = Path.cwd()
        (root / 'outputs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory:
            output = Path(directory) / 'spatial.json'
            args = ['cadkin', 'spatial-export', '--page-size', '5', '--without-boxes', '--output', str(output)]
            with patch.object(sys, 'argv', args), patch('cadkin.tools.solidworks.SolidWorksTools', return_value=self.service), redirect_stdout(io.StringIO()):
                main()
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['data']['component_count'], 254)
            self.assertEqual(result['data']['pages_collected'], 51)
            self.assertTrue(result['data']['collection_complete'])
            self.assertFalse(result['data']['bounding_boxes_requested'])
