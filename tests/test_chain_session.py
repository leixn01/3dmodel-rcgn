import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cadkin.errors import ToolFailure, failure
from cadkin.tools.chain_motion import replay_chain_solution
from cadkin.tools.chain_session import run_chain_session
from cadkin.tools.observation_index import replay_index
from tests.chain_session_fakes import session_fixture


class ChainSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.service, self.app, self.mates, self.config = session_fixture(self.root)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def run_session(self, output='outputs/session.json'):
        return run_chain_session(self.service, 'config.json', output)

    def config_update(self, **args):
        self.config.update(args)
        (self.root / 'config.json').write_text(json.dumps(self.config), encoding='utf-8')

    def read(self, binding):
        p = Path(binding['path'])
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), binding['sha256'])
        return json.loads(p.read_text(encoding='utf-8'))

    def test_first_session_initializes_then_enhances_and_retains_history(self):
        originals = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        r = self.run_session()
        self.assertEqual(r['status'], 'ok', r)
        d = r['data']; h = d['handoffs']
        self.assertTrue(d['workflow_complete']); self.assertEqual(d['rounds_completed'], 2)
        self.assertEqual(d['stop_reason'], 'PRIOR_ENHANCED_ATTEMPT_NO_AUTOMATIC_RETRY')
        solution, _ = replay_chain_solution(self.root, h['solution']['path'])
        self.assertEqual(solution['snapshots'][0]['modeled_chain_instantaneous_dof'], 0)
        self.assertEqual(solution['snapshots'][0]['spanning_forest_diagnostics']['additional_loop_rank'], 2)
        self.assertIsNone(solution['target_degrees_of_freedom']); self.assertFalse(solution['finite_motion_verified'])
        index, _ = replay_index(self.root, h['index']['path'])
        self.assertEqual(index['rounds_completed'], 2); self.assertEqual(len(index['observations']), 5)
        self.assertEqual(self.read(h['constraints'])['check_source'], h['check'])
        self.assertEqual(self.read(h['target'])['source_chain'], h['chain'])
        self.assertEqual(self.read(h['draft'])['rigid_source'], h['rigid'])
        self.assertEqual(self.read(h['index'])['check_source'], h['check'])
        report = self.read(d['report_source'])
        self.assertEqual(len(report['cad_capture_tool_timings']), 21)
        self.assertEqual(len(report['batch_sources']), 2)
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest() == s for p, s in originals.items()))
        self.assertFalse(self.read(h['inventory'])['data']['bounding_boxes_requested'])

    def test_empty_mates_stop_without_fabricating_free_motion(self):
        from tests.constraint_fakes import attach_constraint_mates
        attach_constraint_mates(self.app, 'no_mates')
        r = self.run_session(); self.assertEqual(r['status'], 'ok', r)
        self.assertEqual(r['data']['rounds_completed'], 1)
        solution = self.read(r['data']['handoffs']['solution'])
        self.assertEqual(solution['snapshots'][0]['status'], 'no_supported_constraint_model')
        self.assertIsNone(solution['snapshots'][0]['known_constraint_nullity'])
        report = self.read(r['data']['report_source'])
        self.assertEqual(sum(t['tool'] == 'sw_mate_inventory' for t in report['cad_capture_tool_timings']), 1)

    def test_provided_inventory_is_reused_and_existing_output_refused(self):
        self.config_update(inventory_path='inventory.json')
        original = self.service.worker.call
        with patch.object(self.service.worker, 'call', wraps=original) as calls:
            r = self.run_session(); self.assertEqual(r['status'], 'ok', r)
            self.assertNotIn('sw_spatial_inventory', [c.args[0] for c in calls.call_args_list])
        with patch.object(self.service.worker, 'call') as calls:
            with self.assertRaises(ToolFailure) as caught: self.run_session()
            self.assertEqual(caught.exception.code, 'OUTPUT_EXISTS'); calls.assert_not_called()

    def test_invalid_config_refuses_before_cad_or_output(self):
        for args in ({'characteristic_length_mm': 0}, {'reference_occurrence_path': 'missing'},
                     {'occurrence_paths': ['base-1', 'base-1']}, {'surprise': 'invalid'}):
            old = dict(self.config); self.config_update(**args)
            with patch.object(self.service.worker, 'call') as calls:
                with self.assertRaises(ToolFailure): self.run_session()
                calls.assert_not_called()
            self.config = old
        self.assertFalse((self.root / 'outputs/session.json').exists())

    def test_stale_token_saves_failure_before_capture(self):
        self.config_update(expected_document_token='a' * 24)
        original = self.service.worker.call
        with patch.object(self.service.worker, 'call', wraps=original) as calls:
            r = self.run_session()
            self.assertEqual([c.args[0] for c in calls.call_args_list], ['sw_active_document'])
        self.assertEqual(r['status'], 'error'); self.assertEqual(r['data']['stop_reason'], 'DOCUMENT_CHANGED')
        self.assertFalse(self.read(r['data']['report_source'])['workflow_complete'])

    def test_timeout_retains_receipt_without_further_cad_or_reintegration(self):
        original = self.service.worker.call; seen = []
        def timeout(name, args):
            seen.append(name)
            if name == 'sw_mate_inventory': return failure(ToolFailure('TIMEOUT', 'Synthetic timeout'))
            return original(name, args)
        with patch.object(self.service.worker, 'call', side_effect=timeout): r = self.run_session()
        self.assertEqual(seen[-1], 'sw_mate_inventory'); self.assertEqual(seen.count('sw_mate_inventory'), 1)
        self.assertEqual(r['status'], 'error'); self.assertNotIn('solution', r['data']['handoffs'])
        receipt = self.read(r['data']['handoffs']['execution'])
        self.assertFalse(receipt['guards_passed'])
        self.assertTrue(any(x['fatal'] for x in receipt['records']))

    def test_changed_pose_fails_postguard_and_does_not_integrate(self):
        from tests.sw_fakes import pose
        original = self.service.worker.call
        def change(name, args):
            r = original(name, args)
            if name == 'sw_component_cylinders': self.app.ActiveDoc.root.children[0].Transform2 = pose(x=.9)
            return r
        with patch.object(self.service.worker, 'call', side_effect=change): r = self.run_session()
        self.assertEqual(r['status'], 'error'); self.assertNotIn('baseline', r['data']['handoffs'])
        self.assertFalse(self.read(r['data']['handoffs']['execution'])['guards_passed'])

    def test_failed_cylinder_is_indexed_and_never_retried(self):
        original = self.service.worker.call; seen = []
        def failed(name, args):
            if name == 'sw_component_cylinders':
                seen.append(args['occurrence_path'])
                if args['occurrence_path'] == 'base-1': return failure(ToolFailure('API_ERROR', 'Synthetic failure'))
            return original(name, args)
        with patch.object(self.service.worker, 'call', side_effect=failed): r = self.run_session()
        self.assertEqual(r['status'], 'ok', r)
        index, _ = replay_index(self.root, r['data']['handoffs']['index']['path'])
        self.assertEqual(seen.count('base-1'), 1)
        self.assertTrue(any(o['tool'] == 'sw_component_cylinders' and not o['usable'] for o in index['observations']))

    def test_baseline_rejects_existing_history_and_changed_raw_source(self):
        r = self.run_session(); self.assertEqual(r['status'], 'ok', r)
        args = {'execution_path': r['data']['handoffs']['execution']['path'], 'output_path': 'outputs/invalid.json',
                'distance_tolerance_mm': .1, 'angle_tolerance_deg': .1}
        with patch.object(self.service.worker, 'call') as calls:
            invalid = self.service.call('cad_create_chain_baseline', args)
            self.assertEqual(invalid['errors'][0]['code'], 'BASELINE_ALREADY_EXISTS'); calls.assert_not_called()
        initial = self.read(r['data']['handoffs']['baseline'])['execution_source']
        receipt = self.read(initial)
        raw = next(x['envelope_source'] for x in receipt['records'] if x['envelope_source'])
        with Path(raw['path']).open('a') as f: f.write('\n')
        invalid = self.service.call('cad_create_chain_baseline', {**args, 'execution_path': initial['path']})
        self.assertEqual(invalid['errors'][0]['code'], 'EVIDENCE_MISMATCH')

    def test_cli_returns_nonzero_for_newer_offline_tool_errors(self):
        p = subprocess.run([sys.executable, '-m', 'cadkin', 'solve-chain-constraints', 'absent.json',
            '--reference-occurrence-path', 'missing', '--characteristic-length-mm', '100',
            '--output', 'outputs/not-created.json'], cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertEqual(json.loads(p.stdout)['status'], 'error')

    def test_production_cli_with_explicit_synthetic_backend(self):
        p = subprocess.run([sys.executable, '-m', 'tests.chain_session_cli_fixture', '--root', str(self.root/'cli')],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)['data']
        self.assertTrue(data['workflow_complete']); self.assertEqual(data['rounds_completed'], 2)

    def test_partial_enhancement_keeps_index_and_blocks_retry(self):
        self.mates[0].GetDefinition = lambda: None
        r = self.run_session(); self.assertEqual(r['status'], 'ok', r)
        self.assertEqual(r['data']['rounds_completed'], 2)
        self.assertEqual(r['data']['stop_reason'], 'PRIOR_ENHANCED_ATTEMPT_NO_AUTOMATIC_RETRY')
        index, _ = replay_index(self.root, r['data']['handoffs']['index']['path'])
        self.assertTrue(any(o['tool'] == 'sw_mate_inventory' and not o['usable'] for o in index['observations']))
        self.assertIsNone(self.read(r['data']['handoffs']['solution'])['snapshots'][0]['modeled_chain_instantaneous_dof'])


if __name__ == '__main__': unittest.main()
