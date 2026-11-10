import os
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.adapters.sta import StaWorker
from cadkin._vendor.sw_mcp import value, call
from cadkin.errors import ToolFailure
from cadkin.tools.solidworks import SolidWorksTools
from tests.sw_fakes import App, Component, Document, runtime


class SolidWorksTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.doc = Document()
        self.app = App(self.doc)
        self.adapter = SolidWorksAdapter(root=self.directory.name, app=self.app, runtime=runtime())
        self.service = SolidWorksTools(factory=lambda: self.adapter)
        self.addCleanup(self.service.close)

    def token(self):
        return self.service.call('sw_active_document')['data']['document_token']

    def test_no_document_and_part_are_explicit_errors(self):
        self.app.ActiveDoc = None
        result = self.service.call('sw_active_document')
        self.assertEqual(result['errors'][0]['code'], 'NO_ACTIVE_DOCUMENT')
        self.app.ActiveDoc = Document(kind=1)
        result = self.service.call('sw_component_tree')
        self.assertEqual(result['errors'][0]['code'], 'NOT_ASSEMBLY')
        self.assertIsNone(result['data'])

    def test_tree_keeps_occurrences_and_parent_paths(self):
        result = self.service.call('sw_component_tree')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['data']['component_count'], 4)
        nodes = result['data']['components']
        self.assertEqual(nodes[0]['file_path'], nodes[1]['file_path'])
        self.assertNotEqual(nodes[0]['occurrence_path'], nodes[1]['occurrence_path'])
        self.assertEqual(nodes[3]['parent_occurrence_path'], 'slide-1')

    def test_unresolved_and_failed_children_are_partial_not_zero(self):
        self.app.ActiveDoc = Document(children=[Component('suppressed-1', state=0),
                                               Component('light-1', state=1),
                                               Component('broken-1', fail_children=True)])
        result = self.service.call('sw_component_tree')
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['data']['complete'])
        self.assertEqual(result['data']['component_count'], 3)
        self.assertIn('CHILDREN_READ_FAILED', [e['code'] for e in result['errors']])

    def test_limits_preserve_partial_result(self):
        result = self.service.call('sw_component_tree', {'max_components': 2})
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['data']['component_count'], 2)
        result = self.service.call('sw_component_tree', {'max_depth': 1})
        self.assertIn('DEPTH_LIMIT', [e['code'] for e in result['errors']])

    def test_duplicate_name_cannot_be_selected(self):
        self.app.ActiveDoc = Document(children=[Component('same-1'), Component('same-1')])
        result = self.service.call('sw_select_component', {'expected_document_token': self.token(), 'occurrence_path': 'same-1'})
        self.assertEqual(result['errors'][0]['code'], 'COMPONENT_NOT_FOUND')

    def test_stale_document_and_configuration_reject_actions(self):
        token = self.token()
        self.doc.ConfigurationManager.ActiveConfiguration.Name = 'Other'
        result = self.service.call('sw_rebuild', {'expected_document_token': token})
        self.assertEqual(result['errors'][0]['code'], 'DOCUMENT_CHANGED')
        self.assertFalse(self.doc.rebuilt)
        token = self.token()
        self.app.ActiveDoc = Document(title='Different')
        result = self.service.call('sw_set_view', {'expected_document_token': token})
        self.assertEqual(result['errors'][0]['code'], 'DOCUMENT_CHANGED')
        self.assertIsNone(self.app.ActiveDoc.view)

    def test_selection_readback_clear_view_and_rebuild(self):
        args = {'expected_document_token': self.token()}
        result = self.service.call('sw_select_component', {**args, 'occurrence_path': 'rail-2'})
        self.assertEqual(result['data']['occurrence_path'], 'rail-2')
        self.assertEqual(self.service.call('sw_clear_selection', args)['data']['selected_count'], 0)
        self.assertEqual(self.service.call('sw_set_view', {**args, 'view': 'top'})['status'], 'ok')
        self.assertEqual(self.doc.view, 5)
        result = self.service.call('sw_rebuild', args)
        self.assertTrue(result['data']['document']['dirty'])
        self.assertFalse(result['data']['saved'])

    def test_failed_rebuild_is_not_success(self):
        self.doc.EditRebuild3 = lambda: False
        result = self.service.call('sw_rebuild', {'expected_document_token': self.token()})
        self.assertEqual(result['errors'][0]['code'], 'REBUILD_FAILED')

    def test_open_import_and_activation_are_verified(self):
        path = Path(self.directory.name) / '测试模型.STEP'
        path.write_text('test input only')
        result = self.service.call('sw_open_document', {'path': str(path)})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(self.app.load_args, 'r')
        path = path.with_suffix('.SLDASM')
        path.write_text('test input only')
        self.app.ActiveDoc = self.doc
        result = self.service.call('sw_open_document', {'path': str(path)})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(self.app.activation_options, 1)  # swDontRebuildActiveDoc, NOT prompt (0).
        self.app.ActiveDoc = self.doc
        self.app.fail_activation = True
        result = self.service.call('sw_open_document', {'path': str(path)})
        self.assertEqual(result['errors'][0]['code'], 'ACTIVATION_FAILED')

    def test_paths_unknown_tools_and_invalid_arguments(self):
        with tempfile.TemporaryDirectory() as outside, patch.dict(os.environ, {'CADKIN_ALLOWED_ROOTS': ''}):
            path = Path(outside) / 'outside.step'
            path.write_text('not opened')
            result = self.service.call('sw_open_document', {'path': str(path)})
            self.assertEqual(result['errors'][0]['code'], 'PATH_OUTSIDE_ROOT')
        for name, args in [('sw_component_tree', {'max_depth': 0}), ('sw_component_tree', {'max_depth': True}),
                           ('sw_rebuild', {}), ('sw_set_view', {'expected_document_token': self.token(), 'view': 'bogus'}),
                           ('sw_active_document', {'extra': 1})]:
            self.assertEqual(self.service.call(name, args)['errors'][0]['code'], 'INVALID_ARGUMENTS')
        self.assertEqual(self.service.call('__getattribute__')['errors'][0]['code'], 'UNKNOWN_TOOL')

    def test_connection_uses_existing_object_and_refuses_multiple_processes(self):
        fake_app = SimpleNamespace(GetProcessID=lambda: 1234, RevisionNumber='test-revision', ActiveDoc=None)
        client = SimpleNamespace(dynamic=SimpleNamespace(Dispatch=lambda obj: obj))
        from unittest.mock import Mock
        client.GetActiveObject = Mock(return_value=SimpleNamespace(_oleobj_=fake_app))
        self.adapter.runtime = (SimpleNamespace(CoUninitialize=lambda: None), client)
        self.adapter._owns_com = True
        with patch.dict(os.environ, {'SystemRoot': self.directory.name}):
            with patch('cadkin.adapters.solidworks.subprocess.run', return_value=SimpleNamespace(stdout='"SLDWORKS.exe","1234"\n')):
                result = self.service.call('sw_session_status')
                self.assertTrue(result['data']['connected'])
                client.GetActiveObject.assert_called_once_with('SldWorks.Application')
            client.GetActiveObject.reset_mock()
            with patch('cadkin.adapters.solidworks.subprocess.run', return_value=SimpleNamespace(stdout='"SLDWORKS.exe","1234"\n"SLDWORKS.exe","5678"\n')):
                result = self.service.call('sw_session_status')
                self.assertEqual(result['errors'][0]['code'], 'MULTIPLE_SESSIONS')
                client.GetActiveObject.assert_not_called()
            with patch('cadkin.adapters.solidworks.subprocess.run', return_value=SimpleNamespace(stdout='INFO: no tasks')):
                result = self.service.call('sw_session_status')
                self.assertFalse(result['data']['connected'])
                client.GetActiveObject.assert_not_called()


class WorkerTests(unittest.TestCase):
    def test_construction_calls_and_cleanup_share_one_thread(self):
        threads = []
        class Adapter:
            def __init__(self): threads.append(threading.get_ident())
            def check(self): threads.append(threading.get_ident()); return {'plain': True}
            def close(self): threads.append(threading.get_ident())
        worker = StaWorker(Adapter)
        self.assertEqual(worker.call('check', {}), {'plain': True})
        worker.close()
        self.assertEqual(len(threads), 3)
        self.assertEqual(len(set(threads)), 1)
        self.assertNotEqual(threads[0], threading.get_ident())

    def test_timeout_blocks_new_calls_instead_of_queueing_a_late_action(self):
        finish, began = threading.Event(), threading.Event()
        calls = []
        class Adapter:
            def slow(self):
                calls.append('slow'); began.set(); finish.wait(2); return {}
            def next(self): calls.append('next'); return {}
            def close(self): pass
        worker = StaWorker(Adapter, timeout=0.03)
        self.addCleanup(worker.close)
        self.addCleanup(finish.set)
        with self.assertRaises(ToolFailure) as caught:
            worker.call('slow', {})
        self.assertEqual(caught.exception.code, 'TIMEOUT')
        self.assertTrue(began.is_set())
        with self.assertRaises(ToolFailure) as caught:
            worker.call('next', {})
        self.assertEqual(caught.exception.code, 'OUTCOME_UNKNOWN')
        finish.set()
        worker.close()
        self.assertEqual(calls, ['slow'])

    def test_com_dispatch_not_invoked_as_default_callable(self):
        class Dispatch:
            _oleobj_ = object()
            def __call__(self): raise AssertionError('COM default member must not run')
        parent = type('Parent', (), {'child': Dispatch()})()
        self.assertIs(value(parent, 'child'), parent.child)

    def test_failed_method_flagging_never_accesses_unsafe_member(self):
        class Dispatch:
            _oleobj_ = object()
            def _FlagAsMethod(self, name): raise RuntimeError('missing member')
            @property
            def dangerous(self): raise AssertionError('member must not be accessed')
        with self.assertRaises(RuntimeError):
            call(Dispatch(), 'dangerous', 1)
