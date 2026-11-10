"""Startup decision and readback tests with explicit COM/process test doubles."""
import sys
import unittest
from unittest.mock import Mock, patch

from cadkin.errors import ToolFailure
from cadkin.tools.solidworks import CATALOG, SolidWorksTools
from tests.sw_fakes import Document, SessionHarness


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.harness = SessionHarness()
        self.adapter = self.harness.adapter
        self.service = SolidWorksTools(factory=lambda: self.adapter)
        self.addCleanup(self.service.close)

    def start(self, **args):
        return self.service.call('sw_start_application', args)

    def test_status_only_does_not_launch_then_cold_start_is_ready_and_retained(self):
        h = self.harness
        result = self.service.call('sw_session_status')
        self.assertFalse(result['data']['connected'])
        h.pythoncom.CoCreateInstance.assert_not_called()
        h.app.Visible = h.app.UserControl = False
        result = self.start()
        self.assertEqual(result['status'], 'ok', result)
        data = result['data']
        self.assertTrue(data['started'])
        self.assertFalse(data['reused_existing'])
        self.assertTrue(data['startup_completed'])
        self.assertEqual(data['process_id'], '1234')
        self.assertFalse(data['has_active_document'])
        h.pythoncom.CoCreateInstance.assert_called_once_with('test-SolidWorks-CLSID', None, 4, 'test-IDispatch')
        h.client.GetActiveObject.assert_not_called()  # Fresh servers need not appear in ROT yet.
        self.assertTrue(h.app.Visible and h.app.UserControl)
        self.service.close()
        self.assertTrue(h.running and h.app.UserControl)  # No ExitApp/kill path.

    def test_existing_session_and_repeat_start_do_not_create_or_change_document(self):
        h = self.harness
        h.running = True
        doc = Document()
        doc.dirty = True
        selected = doc.root.children[0]
        doc.SelectionManager.selected = [selected]
        h.app.ActiveDoc = doc
        for _ in range(2):
            result = self.start()
            self.assertEqual(result['status'], 'ok', result)
            self.assertFalse(result['data']['started'])
            self.assertTrue(result['data']['reused_existing'])
        h.pythoncom.CoCreateInstance.assert_not_called()
        self.assertIs(h.app.ActiveDoc, doc)
        self.assertTrue(doc.dirty)
        self.assertEqual(doc.SelectionManager.selected, [selected])
        self.assertFalse(doc.rebuilt)

    def test_attach_query_and_multiple_session_failures_never_launch(self):
        h = self.harness
        h.running = True
        h.client.GetActiveObject.side_effect = RuntimeError('ROT unavailable')
        self.assertEqual(self.start()['errors'][0]['code'], 'CONNECT_FAILED')
        h.adapter._running_processes.side_effect = ToolFailure('PROCESS_QUERY_FAILED', 'failed query')
        self.assertEqual(self.start()['errors'][0]['code'], 'PROCESS_QUERY_FAILED')
        h.adapter._running_processes.side_effect = lambda: ['1234', '5678']
        self.assertEqual(self.start()['errors'][0]['code'], 'MULTIPLE_SESSIONS')
        h.pythoncom.CoCreateInstance.assert_not_called()

    def test_unregistered_application_is_explicit_and_does_not_activate(self):
        h = self.harness
        h.adapter._resolve_application_clsid.side_effect = RuntimeError('class not registered')
        self.assertEqual(self.start()['errors'][0]['code'], 'APPLICATION_NOT_REGISTERED')
        h.pythoncom.CoCreateInstance.assert_not_called()
        self.assertFalse(self.adapter._launch_uncertain)

    def test_failed_activation_is_not_blindly_repeated(self):
        h = self.harness
        h.pythoncom.CoCreateInstance.side_effect = RuntimeError('activation failed')
        first = self.start()
        self.assertEqual(first['errors'][0]['code'], 'START_FAILED')
        self.assertTrue(first['errors'][0]['details']['activation_attempted'])
        self.assertEqual(self.start()['errors'][0]['code'], 'START_OUTCOME_UNKNOWN')
        self.assertEqual(h.pythoncom.CoCreateInstance.call_count, 1)

    def test_pending_startup_keeps_process_and_next_call_reuses_it(self):
        h = self.harness
        h.app.StartupProcessCompleted = False
        with patch('cadkin.adapters.session.time.monotonic', side_effect=[0, 2]):
            result = self.start(wait_seconds=1)
        self.assertEqual(result['errors'][0]['code'], 'STARTUP_PENDING')
        self.assertTrue(h.running)
        h.app.StartupProcessCompleted = True
        result = self.start()
        self.assertEqual(result['status'], 'ok', result)
        self.assertTrue(result['data']['reused_existing'])
        self.assertEqual(h.pythoncom.CoCreateInstance.call_count, 1)

    def test_wait_pumps_sta_messages_until_startup_addins_complete(self):
        h = self.harness
        ready = iter([False, True])
        h.app.StartupProcessCompleted = lambda: next(ready)
        with patch('cadkin.adapters.session.time.sleep') as sleep:
            result = self.start()
        self.assertEqual(result['status'], 'ok', result)
        h.pythoncom.PumpWaitingMessages.assert_called_once()
        sleep.assert_called_once()

    def test_external_start_between_checks_is_reused(self):
        h = self.harness
        def resolve():
            h.running = True
            return 'test-SolidWorks-CLSID'
        h.adapter._resolve_application_clsid.side_effect = resolve
        result = self.start()
        self.assertEqual(result['status'], 'ok', result)
        self.assertTrue(result['data']['reused_existing'])
        h.pythoncom.CoCreateInstance.assert_not_called()

    def test_racing_external_launcher_is_detected_without_killing_processes(self):
        h = self.harness
        h.adapter._running_processes.side_effect = [[], [], ['1234', '5678']]
        result = self.start()
        self.assertEqual(result['errors'][0]['code'], 'MULTIPLE_SESSIONS')
        self.assertTrue(h.running and h.app.UserControl)
        self.assertEqual(h.pythoncom.CoCreateInstance.call_count, 1)

    def test_unreadable_or_rejected_visibility_is_not_success(self):
        h = self.harness
        h.app.StartupProcessCompleted = None
        self.assertEqual(self.start()['errors'][0]['code'], 'STARTUP_READ_FAILED')
        h.app.StartupProcessCompleted = True
        with patch('cadkin.adapters.session.boolean_property', return_value=False):
            self.assertEqual(self.start()['errors'][0]['code'], 'STARTUP_STATE_MISMATCH')
        self.assertEqual(h.pythoncom.CoCreateInstance.call_count, 1)

    def test_pid_mismatch_does_not_start_another_process(self):
        h = self.harness
        h.running = True
        h.app.GetProcessID = lambda: 5678
        self.assertEqual(self.start()['errors'][0]['code'], 'SESSION_MISMATCH')
        h.pythoncom.CoCreateInstance.assert_not_called()

    def test_cached_dead_handle_reattaches_without_activation(self):
        h = self.harness
        h.running = True
        dead = Mock()
        dead.GetProcessID.side_effect = RuntimeError('disconnected')
        self.adapter.app = dead
        self.adapter.process_id = '1234'
        result = self.start()
        self.assertEqual(result['status'], 'ok', result)
        h.client.GetActiveObject.assert_called_once()
        h.pythoncom.CoCreateInstance.assert_not_called()

    def test_schema_rejects_arbitrary_paths_and_invalid_wait(self):
        self.assertFalse(CATALOG['sw_start_application']['annotations']['readOnlyHint'])
        for args in ({'wait_seconds': 0}, {'wait_seconds': 121}, {'wait_seconds': True}, {'path': 'anything.exe'}):
            self.assertEqual(self.start(**args)['errors'][0]['code'], 'INVALID_ARGUMENTS')
        self.harness.pythoncom.CoCreateInstance.assert_not_called()


@unittest.skipUnless(sys.platform == 'win32', 'Native Windows COM dependency check')
class WindowsRuntimeTests(unittest.TestCase):
    def test_native_process_query_and_clsid_resolution_without_launch(self):
        import pythoncom
        import pywintypes
        from cadkin.adapters.solidworks import SolidWorksAdapter
        adapter = SolidWorksAdapter()
        try:
            self.assertTrue(callable(pythoncom.CoCreateInstance))
            self.assertTrue(callable(pythoncom.PumpWaitingMessages))
            self.assertEqual(pythoncom.CLSCTX_LOCAL_SERVER, 4)
            self.assertTrue(all(pid.isdigit() for pid in adapter._running_processes()))
            # A CI host need not have SOLIDWORKS installed. Its actual pywin32 API
            # must resolve a registration or raise a COM error, not a missing-member error.
            try:
                clsid = adapter._resolve_application_clsid()
            except pywintypes.com_error:
                pass
            else:
                self.assertEqual(len(str(clsid)), 38)
        finally:
            adapter.close()
