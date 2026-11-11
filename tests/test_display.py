import unittest
from unittest.mock import Mock

from cadkin.adapters.display import read_constants
from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.tools.solidworks import SolidWorksTools
from tests.sw_fakes import App, Component, ConstantLibrary, Document, TEST_CONSTANTS, runtime


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.doc = Document()
        self.app = App(self.doc)
        self.runtime = runtime()
        self.adapter = SolidWorksAdapter(app=self.app, runtime=self.runtime)
        self.service = SolidWorksTools(factory=lambda: self.adapter)
        self.addCleanup(self.service.close)

    def args(self, **extra):
        token = self.service.call('sw_active_document')['data']['document_token']
        return {'expected_document_token': token, **extra}

    def test_hide_show_readback_and_repeat_do_not_toggle_or_touch_other_categories(self):
        args = self.args(target='planes', visible=False)
        first = self.service.call('sw_set_display_visibility', args)
        self.assertEqual(first['status'], 'ok')
        self.assertTrue(first['data']['changed'])
        again = self.service.call('sw_set_display_visibility', args)
        self.assertFalse(again['data']['changed'])
        self.assertEqual(len(self.doc.Extension.writes), 1)
        settings = self.service.call('sw_get_display_state')['data']
        self.assertFalse(settings['visibility']['planes'])
        self.assertTrue(settings['visibility']['axes'])
        self.assertFalse(settings['hide_all_reference_geometry'])
        shown = self.service.call('sw_set_display_visibility', {**args, 'visible': True})
        self.assertEqual(shown['status'], 'ok')
        self.assertTrue(shown['data']['visible'])
        self.assertFalse(shown['data']['saved'])

    def test_master_hide_is_inverted_and_show_category_is_blocked(self):
        result = self.service.call('sw_set_display_visibility', self.args(target='all_reference_geometry', visible=False))
        self.assertEqual(result['status'], 'ok')
        state = self.service.call('sw_get_display_state')['data']
        self.assertTrue(state['hide_all_reference_geometry'])
        self.assertTrue(state['visibility']['planes'])
        self.assertFalse(state['display_allowed']['planes'])
        blocked = self.service.call('sw_set_display_visibility', self.args(target='planes', visible=True))
        self.assertEqual(blocked['errors'][0]['code'], 'DISPLAY_BLOCKED')
        self.assertEqual(len(self.doc.Extension.writes), 1)
        self.service.call('sw_set_display_visibility', self.args(target='all_reference_geometry', visible=True))
        self.assertFalse(self.service.call('sw_get_display_state')['data']['hide_all_reference_geometry'])

    def test_every_category_works_on_parts_without_assembly_tree(self):
        self.app.ActiveDoc = Document(kind=1)
        for target in ('planes', 'axes', 'temporary_axes', 'sketches', 'origins', 'coordinate_systems'):
            with self.subTest(target=target):
                result = self.service.call('sw_set_display_visibility', self.args(target=target, visible=False))
                self.assertEqual(result['status'], 'ok')
                self.assertFalse(self.service.call('sw_get_display_state')['data']['visibility'][target])

    def test_rejected_or_unreadable_display_state_is_not_success(self):
        self.doc.Extension.ignore_writes = True
        result = self.service.call('sw_set_display_visibility', self.args(target='planes', visible=False))
        self.assertEqual(result['errors'][0]['code'], 'DISPLAY_MISMATCH')
        self.doc.Extension.settings[TEST_CONSTANTS['swDisplayPlanes']] = None
        result = self.service.call('sw_get_display_state')
        self.assertEqual(result['errors'][0]['code'], 'DISPLAY_READ_FAILED')

    def test_typelib_failures_never_change_display(self):
        self.runtime[0].LoadTypeLib = Mock(side_effect=RuntimeError('missing swconst.tlb'))
        result = self.service.call('sw_set_display_visibility', self.args(target='planes', visible=False))
        self.assertEqual(result['errors'][0]['code'], 'DISPLAY_CONSTANTS_UNAVAILABLE')
        self.assertEqual(self.doc.Extension.writes, [])
        with self.assertRaises(ValueError):
            read_constants(ConstantLibrary({'unrelated': 42}), {'swDisplayPlanes'})
        with self.assertRaises(ValueError):
            read_constants(ConstantLibrary({'swDisplayPlanes': 'bad'}), {'swDisplayPlanes'})

    def test_typelib_values_are_loaded_once_without_registration(self):
        loader = self.runtime[0].LoadTypeLib
        self.runtime[0].LoadTypeLib = Mock(wraps=loader)
        self.service.call('sw_get_display_state')
        self.service.call('sw_get_display_state')
        self.runtime[0].LoadTypeLib.assert_called_once()
        self.assertTrue(all(isinstance(x, int) for x in self.adapter._display_constant_cache[1].values()))

    def test_stale_target_invalid_arguments_and_drawing_never_mutate(self):
        args = self.args(target='planes', visible=False)
        self.doc.ConfigurationManager.ActiveConfiguration.Name = 'Other'
        result = self.service.call('sw_set_display_visibility', args)
        self.assertEqual(result['errors'][0]['code'], 'DOCUMENT_CHANGED')
        for extra in ({'target': 'unknown', 'visible': False}, {'target': 'planes', 'visible': 'false'},
                      {'target': 'planes'}, {'target': 'planes', 'visible': False, 'script': 'x'}):
            result = self.service.call('sw_set_display_visibility', self.args(**extra))
            self.assertEqual(result['errors'][0]['code'], 'INVALID_ARGUMENTS')
        self.assertEqual(self.doc.Extension.writes, [])
        self.app.ActiveDoc = Document(kind=3)
        result = self.service.call('sw_get_display_state')
        self.assertEqual(result['errors'][0]['code'], 'UNSUPPORTED_DOCUMENT_TYPE')

    def test_zoom_does_not_reset_orientation(self):
        self.doc.view = 5
        result = self.service.call('sw_zoom_to_fit', self.args())
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(self.doc.zoom_count, 1)
        self.assertEqual(self.doc.view, 5)

    def test_component_visibility_preserves_other_instances_and_selection(self):
        first, second = self.doc.root.children[:2]
        self.doc.SelectionManager.selected = [first]
        args = self.args(occurrence_path='rail-2', visible=False)
        result = self.service.call('sw_set_component_visibility', args)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(first.Visible, 1)
        self.assertEqual(second.Visible, 0)
        self.assertEqual(self.doc.SelectionManager.selected, [first])
        self.assertFalse(self.service.call('sw_set_component_visibility', args)['data']['changed'])
        self.assertEqual(second.visibility_writes, [0])
        result = self.service.call('sw_get_component_visibility', self.args(occurrence_path='rail-2'))
        self.assertFalse(result['data']['visible_with_parents'])
        self.assertEqual(self.service.call('sw_set_component_visibility', {**args, 'visible': True})['status'], 'ok')
        self.assertEqual(second.Visible, 1)

    def test_hidden_parent_blocks_showing_child_without_side_effects(self):
        parent = self.doc.root.children[2]
        parent._visible = 0
        args = self.args(occurrence_path='slide-1/block-1')
        state = self.service.call('sw_get_component_visibility', args)['data']
        self.assertTrue(state['visible'])
        self.assertFalse(state['visible_with_parents'])
        self.assertEqual(state['hidden_parent_paths'], ['slide-1'])
        result = self.service.call('sw_set_component_visibility', {**args, 'visible': True})
        self.assertEqual(result['errors'][0]['code'], 'PARENT_HIDDEN')
        self.assertEqual(parent.visibility_writes, [])
        self.assertEqual(parent.children[0].visibility_writes, [])

    def test_unresolved_ambiguous_missing_and_part_targets_are_rejected(self):
        for children, path, code in [([Component('x', state=0)], 'x', 'UNRESOLVED_COMPONENT'),
                                     ([Component('x', state=1)], 'x', 'UNRESOLVED_COMPONENT'),
                                     ([Component('x'), Component('x')], 'x', 'COMPONENT_LOOKUP_INCOMPLETE'),
                                     ([Component('x')], 'missing', 'COMPONENT_NOT_FOUND')]:
            self.app.ActiveDoc = Document(children=children)
            result = self.service.call('sw_set_component_visibility', self.args(occurrence_path=path, visible=False))
            self.assertEqual(result['errors'][0]['code'], code)
            self.assertTrue(all(not child.visibility_writes for child in children))
        self.app.ActiveDoc = Document(kind=1)
        result = self.service.call('sw_get_component_visibility', self.args(occurrence_path='rail-1'))
        self.assertEqual(result['errors'][0]['code'], 'NOT_ASSEMBLY')

    def test_incomplete_tree_cannot_claim_unique_visibility_target(self):
        target = Component('target-1')
        self.app.ActiveDoc = Document(children=[target, Component('unreadable-1', fail_children=True)])
        result = self.service.call('sw_set_component_visibility', self.args(occurrence_path='target-1', visible=False))
        self.assertEqual(result['errors'][0]['code'], 'COMPONENT_LOOKUP_INCOMPLETE')
        self.assertEqual(target.visibility_writes, [])

    def test_component_readback_mismatch_and_stale_token_are_errors(self):
        second = self.doc.root.children[1]
        second.ignore_visibility_writes = True
        args = self.args(occurrence_path='rail-2', visible=False)
        result = self.service.call('sw_set_component_visibility', args)
        self.assertEqual(result['errors'][0]['code'], 'DISPLAY_MISMATCH')
        second.visibility_writes.clear()
        self.app.ActiveDoc = Document(title='Different')
        result = self.service.call('sw_set_component_visibility', args)
        self.assertEqual(result['errors'][0]['code'], 'DOCUMENT_CHANGED')
        self.assertEqual(second.visibility_writes, [])

    def test_visibility_uses_one_traversal_and_no_forced_redraw(self):
        self.adapter._walk = Mock(wraps=self.adapter._walk)
        self.doc.GraphicsRedraw2 = Mock(side_effect=AssertionError('Forced redraw must not block a setter'))
        result = self.service.call('sw_set_component_visibility', self.args(occurrence_path='rail-2', visible=False))
        self.assertEqual(result['status'], 'ok', result)
        self.adapter._walk.assert_called_once()
        self.assertFalse(result['data']['redraw_requested'])
        result = self.service.call('sw_set_display_visibility', self.args(target='planes', visible=False))
        self.assertEqual(result['status'], 'ok', result)
        self.doc.GraphicsRedraw2.assert_not_called()

    def test_relative_typelib_path_is_rejected_before_loading(self):
        self.app.GetExecutablePath = lambda: 'relative/sldworks.exe'
        self.runtime[0].LoadTypeLib = Mock()
        result = self.service.call('sw_get_display_state')
        self.assertEqual(result['errors'][0]['code'], 'DISPLAY_CONSTANTS_UNAVAILABLE')
        self.runtime[0].LoadTypeLib.assert_not_called()


@unittest.skipUnless(__import__('sys').platform == 'win32', 'Real Windows type library test')
class WindowsTypeLibraryTests(unittest.TestCase):
    def test_real_pywin32_load_and_integer_descriptors(self):
        import os
        from pathlib import Path
        import pythoncom
        pythoncom.CoInitialize()
        try:
            path = Path(os.environ['SystemRoot']) / 'System32' / 'stdole2.tlb'
            self.assertTrue(path.is_file())
            library = pythoncom.LoadTypeLib(str(path))
            # Real SDK/OLE enums exercise cVars, memid and value, not COM-shaped fakes.
            values = read_constants(library, {'Unchecked', 'Checked', 'Gray'})
            self.assertEqual(values, {'Unchecked': 0, 'Checked': 1, 'Gray': 2})
            del library
        finally:
            pythoncom.CoUninitialize()
