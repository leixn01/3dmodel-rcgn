import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cadkin.errors import ToolFailure
from cadkin.tools.files import json_path, read_json, replay_reads, _REPLAY_READS


class ReplayReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.path = self.root/'input.json'
        self.path.write_text('{"value": [1]}', encoding='utf-8')

    def test_reuses_bytes_and_paths_but_not_mutable_values(self):
        from cadkin.tools.files import _resolve_json_path
        with patch('cadkin.tools.files._resolve_json_path', wraps=_resolve_json_path) as resolve:
            @replay_reads
            def replay():
                first, digest = read_json(json_path(self.root, 'input.json')); first['value'].append(9)
                second, again = read_json(json_path(self.root, 'input.json'))
                self.assertEqual(second, {'value': [1]}); self.assertEqual(digest, again)
                self.assertEqual(len(_REPLAY_READS.get().files), 1)
            replay()
            self.assertEqual(resolve.call_count, 2)  # Initial lookup plus fresh exit validation.
        self.assertIsNone(_REPLAY_READS.get())

    def test_same_size_mutation_is_rejected_before_result_returns(self):
        @replay_reads
        def replay():
            value = read_json(json_path(self.root, 'input.json'))
            self.path.write_text('{"value": [2]}', encoding='utf-8')
            return value
        with self.assertRaises(ToolFailure) as error: replay()
        self.assertEqual(error.exception.code, 'EVIDENCE_MISMATCH')
        self.assertIsNone(_REPLAY_READS.get())

    def test_deleted_input_is_rejected(self):
        @replay_reads
        def replay():
            read_json(json_path(self.root, 'input.json')); self.path.unlink()
        with self.assertRaises(ToolFailure) as error: replay()
        self.assertEqual(error.exception.code, 'EVIDENCE_MISMATCH')

    def test_changed_resolution_is_rejected(self):
        # Mock resolver to exercise remapping on Windows without requiring symlink privileges.
        @replay_reads
        def replay(): return read_json(json_path(self.root, 'input.json'))
        with patch('cadkin.tools.files._resolve_json_path', side_effect=[self.path, self.root/'other.json']):
            with self.assertRaises(ToolFailure) as error: replay()
        self.assertEqual(error.exception.code, 'EVIDENCE_MISMATCH')

    def test_next_call_refreshes_inputs_and_nested_calls_share_scope(self):
        @replay_reads
        def inner(): return read_json(json_path(self.root, 'input.json'))[0]
        @replay_reads
        def outer():
            state = _REPLAY_READS.get(); value = inner()
            self.assertIs(state, _REPLAY_READS.get()); return value
        self.assertEqual(outer()['value'], [1])
        self.path.write_text(json.dumps({'value': [2]}), encoding='utf-8')
        self.assertEqual(outer()['value'], [2])

    def test_exception_clears_scope(self):
        @replay_reads
        def replay():
            read_json(json_path(self.root, 'input.json')); raise RuntimeError('failed replay')
        with self.assertRaises(RuntimeError): replay()
        self.assertIsNone(_REPLAY_READS.get())
        self.path.write_text('{"value": [3]}', encoding='utf-8')
        self.assertEqual(read_json(self.path)[0]['value'], [3])
