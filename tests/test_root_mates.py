import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cadkin.errors import ToolFailure, failure
from cadkin.tools.chain_motion import replay_chain_solution
from cadkin.tools.chain_session import run_chain_session
from cadkin.tools.followup import replay_plan
from cadkin.tools.observation_index import replay_index
from tests.chain_session_fakes import session_fixture


class RootMateTests(unittest.TestCase):
    def test_root_profile_through_production_cli(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run([sys.executable, '-m', 'tests.chain_session_cli_fixture', '--root', directory,
                '--profile', 'root_mates'], capture_output=True, text=True, timeout=120)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result['data']['capture_profile'], 'root_mates')
            self.assertEqual(result['data']['rounds_completed'], 1)
            replay_chain_solution(Path(directory), result['data']['handoffs']['solution']['path'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.service, self.app, self.mates, self.config = session_fixture(self.root)

    def tearDown(self):
        self.service.close(); self.temp.cleanup()

    def raw(self, enhanced=True):
        r = self.service.call('sw_mate_inventory', {'expected_document_token': self.config['expected_document_token'],
            'include_reference_geometry': enhanced})
        self.assertEqual(r['status'], 'ok', r)
        (self.root/'raw-mates.json').write_text(json.dumps(r), encoding='utf-8')
        return r

    def review(self, output='outputs/root-review.json'):
        return self.service.call('cad_review_root_mates', {'inventory_path': 'inventory.json',
            'mate_inventory_path': 'raw-mates.json', 'output_path': output})

    def read(self, name):
        return json.loads((self.root/name).read_text(encoding='utf-8'))

    def session(self, profile='root_mates', scope=None):
        self.config['capture_profile'] = profile
        if scope: self.config['occurrence_paths'] = scope
        (self.root/'config.json').write_text(json.dumps(self.config), encoding='utf-8')
        return run_chain_session(self.service, 'config.json', 'outputs/session.json')

    def test_direct_pair_graph_without_any_cylinder_source(self):
        self.raw()
        with patch.object(self.service.worker, 'call') as cad:
            r = self.review(); self.assertEqual(r['status'], 'ok', r); cad.assert_not_called()
        data = self.read('outputs/root-review.json')
        self.assertEqual(data['connection_review_schema_version'], 2)
        self.assertEqual(set(data['sources']), {'inventory', 'mates'})
        self.assertEqual(len(data['pairs']), 3)
        self.assertFalse(data['geometry_candidates_evaluated'])
        self.assertTrue(all(not p['geometric_candidate_indices'] for p in data['pairs']))
        self.assertEqual(data['coverage']['candidate_face_pairs'], 0)

    def test_root_profile_solves_with_nine_guarded_calls_and_no_body_scan(self):
        original = self.service.worker.call; seen = []
        def call(name, args):
            seen.append(name)
            self.assertNotIn(name, ('sw_component_cylinders', 'sw_component_faces', 'sw_component_distance'))
            return original(name, args)
        with patch.object(self.service.worker, 'call', side_effect=call): r = self.session()
        self.assertEqual(r['status'], 'ok', r); d = r['data']
        self.assertEqual(d['rounds_completed'], 1)
        report = self.read(d['report_source']['path'])
        self.assertEqual(len(report['cad_capture_tool_timings']), 9)
        self.assertEqual(seen.count('sw_mate_inventory'), 1)
        solution, _ = replay_chain_solution(self.root, d['handoffs']['solution']['path'])
        self.assertEqual(solution['snapshots'][0]['modeled_chain_instantaneous_dof'], 0)
        self.assertEqual(solution['snapshots'][0]['spanning_forest_diagnostics']['additional_loop_rank'], 2)
        self.assertEqual(self.read(d['handoffs']['target']['path'])['relation_sources'], [])
        self.assertIsNone(solution['target_degrees_of_freedom'])
        initial = self.read('outputs/session-files/initial-plan.json')
        self.assertEqual(initial['algorithm_version'], 5)
        self.assertEqual(initial['summary']['guard_tasks'], 8)
        replay_plan(self.root, 'outputs/session-files/initial-plan.json')

    def test_failed_all_cylinder_scans_do_not_block_native_constraints(self):
        original = self.service.worker.call; count = []
        def fail(name, args):
            if name == 'sw_component_cylinders':
                count.append(args['occurrence_path']); return failure(ToolFailure('API_ERROR', 'Synthetic body scan unavailable'))
            return original(name, args)
        with patch.object(self.service.worker, 'call', side_effect=fail): r = self.session('geometry_and_mates')
        self.assertEqual(r['status'], 'ok', r); h = r['data']['handoffs']
        self.assertEqual(len(count), 3); self.assertEqual(r['data']['rounds_completed'], 2)
        solution, _ = replay_chain_solution(self.root, h['solution']['path'])
        self.assertEqual(solution['snapshots'][0]['modeled_chain_instantaneous_dof'], 0)
        index, _ = replay_index(self.root, h['index']['path'])
        self.assertEqual(index['summary']['retained_unsuccessful_attempts'], 3)
        self.assertEqual(self.read(h['target']['path'])['relation_sources'], [])
        self.assertEqual(self.read('outputs/session-files/enhanced-reintegration-derived/connections-00.json')['connection_review_schema_version'], 2)

    def test_plane_pair_does_not_require_cylindrical_parts(self):
        from tests.constraint_fakes import attach_constraint_mates
        attach_constraint_mates(self.app, 'plane')
        r = self.session(scope=['base-1', 'carriage-1'])
        self.assertEqual(r['status'], 'ok', r)
        solution, _ = replay_chain_solution(self.root, r['data']['handoffs']['solution']['path'])
        self.assertEqual(solution['snapshots'][0]['modeled_chain_instantaneous_dof'], 3)
        self.assertFalse(solution['finite_motion_verified'])

    def test_empty_mates_are_complete_unknown_not_six_or_twelve_dof(self):
        from tests.constraint_fakes import attach_constraint_mates
        attach_constraint_mates(self.app, 'no_mates')
        r = self.session(); self.assertEqual(r['status'], 'ok', r)
        h = r['data']['handoffs']; data, _ = replay_chain_solution(self.root, h['solution']['path'])
        self.assertEqual(data['snapshots'][0]['status'], 'no_supported_constraint_model')
        self.assertIsNone(data['snapshots'][0]['known_constraint_nullity'])
        self.assertEqual(r['data']['rounds_completed'], 1)
        index, _ = replay_index(self.root, h['index']['path'])
        self.assertEqual(index['summary']['reusable'], 1)

    def test_partial_enhanced_attempt_does_not_trigger_another_scan(self):
        self.mates[0].GetDefinition = lambda: None
        r = self.session(); self.assertEqual(r['status'], 'ok', r)
        self.assertEqual(r['data']['rounds_completed'], 1)
        index, _ = replay_index(self.root, r['data']['handoffs']['index']['path'])
        self.assertEqual(len(index['observations']), 1); self.assertFalse(index['observations'][0]['usable'])
        self.assertEqual(r['data']['solution_summary']['coverage']['modeled_snapshots'], 0)

    def test_unknown_and_multi_entity_refs_remain_unmatched(self):
        raw = self.raw(); first, second = raw['data']['mates'][:2]
        first['entities'][0]['reference_status'] = 'unmapped'
        second['entities'].append(copy.deepcopy(second['entities'][0])); second['entity_count'] = 3
        (self.root/'raw-mates.json').write_text(json.dumps(raw), encoding='utf-8')
        r = self.review(); self.assertNotEqual(r['status'], 'error', r)
        data = self.read('outputs/root-review.json')
        self.assertEqual(len(data['pairs']), 1); self.assertEqual(len(data['unmatched_mates']), 2)

    def test_suppressed_pair_retained_without_active_claim(self):
        raw = self.raw(); row = raw['data']['mates'][0]
        row['activity']['suppressed'] = True; row['activity']['state'] = 'suppressed'
        (self.root/'raw-mates.json').write_text(json.dumps(raw), encoding='utf-8')
        self.assertEqual(self.review()['status'], 'ok')
        rows = self.read('outputs/root-review.json')['pairs']
        evidence = [m for p in rows for m in p['mate_evidence'] if m['feature_id'] == row['feature_id']]
        self.assertEqual(evidence[0]['category'], 'suppressed')

    def test_existing_pair_does_not_absorb_ambiguous_or_multi_entity_mates(self):
        raw = self.raw()
        for number in range(2):
            duplicate = copy.deepcopy(raw['data']['mates'][0])
            duplicate['feature_id'] += 100 + number
            duplicate['entities'].append(copy.deepcopy(duplicate['entities'][0]))
            duplicate['entity_count'] = 3
            if number:
                duplicate['entities'][-1]['reference_status'] = 'unmapped'
            raw['data']['mates'].append(duplicate)
        raw['data']['mate_count'] = len(raw['data']['mates'])
        (self.root/'raw-mates.json').write_text(json.dumps(raw), encoding='utf-8')
        self.assertEqual(self.review()['status'], 'ok')
        result = self.read('outputs/root-review.json')
        self.assertEqual(len(result['unmatched_mates']), 2)
        self.assertEqual(sum(len(p['mate_evidence']) for p in result['pairs']), 3)

    def test_document_and_pose_mismatch_rejected(self):
        original = self.raw()
        for kind in ('document', 'pose'):
            raw = copy.deepcopy(original)
            if kind == 'document': raw['data']['document']['configuration'] = 'different'
            else: raw['data']['component_contexts'][0]['transform']['raw_array'][9] += 1
            (self.root/'raw-mates.json').write_text(json.dumps(raw), encoding='utf-8')
            self.assertEqual(self.review()['errors'][0]['code'], 'EVIDENCE_MISMATCH')

    def test_face_matched_capture_cannot_hide_missing_geometric_basis(self):
        raw = self.raw(); raw['data']['face_matching'] = {'schema_version': 1}
        (self.root/'raw-mates.json').write_text(json.dumps(raw), encoding='utf-8')
        self.assertEqual(self.review()['errors'][0]['code'], 'FACE_MATCH_BASIS_REQUIRED')

    def test_forged_pair_and_modified_source_fail_replay(self):
        self.raw(); self.assertEqual(self.review()['status'], 'ok')
        raw = self.read('outputs/root-review.json'); raw['pairs'].clear()
        (self.root/'outputs/forged.json').write_text(json.dumps(raw), encoding='utf-8')
        args = {'inventory_path': 'inventory.json', 'occurrence_paths': self.config['occurrence_paths'],
                'chain_name': 'Synthetic chain', 'evidence_paths': ['outputs/forged.json'], 'output_path': 'outputs/rejected-chain.json'}
        r = self.service.call('cad_build_chain_evidence', args)
        self.assertEqual(r['errors'][0]['code'], 'EVIDENCE_MISMATCH')
        with (self.root/'raw-mates.json').open('a') as stream: stream.write('\n')
        r = self.service.call('cad_build_chain_evidence', {**args, 'evidence_paths': ['outputs/root-review.json']})
        self.assertEqual(r['errors'][0]['code'], 'EVIDENCE_MISMATCH')

    def test_profile_budget_and_history_do_not_bypass_guards(self):
        r = self.session(); self.assertEqual(r['status'], 'ok', r)
        args = {'draft_check_path': 'outputs/session-files/initial-check.json', 'initial_capture_profile': 'root_mates',
                'max_tasks': 8, 'output_path': 'outputs/too-small.json'}
        planned = self.service.call('cad_plan_evidence_tasks', args)
        self.assertNotEqual(planned['status'], 'error', planned)
        self.assertEqual(planned['data']['tasks'], [])
        with patch.object(self.service.worker, 'call') as calls:
            blocked = self.service.call('sw_execute_evidence_batch', {'plan_path': 'outputs/too-small.json', 'output_path': 'outputs/blocked.json'})
            self.assertEqual(blocked['errors'][0]['code'], 'NO_CAPTURE_TASKS'); calls.assert_not_called()
        h = r['data']['handoffs']
        bad = self.service.call('cad_plan_evidence_tasks', {**args, 'output_path': 'outputs/reset.json',
            'draft_check_path': h['check']['path'], 'evidence_index_path': h['index']['path']})
        self.assertEqual(bad['errors'][0]['code'], 'INVALID_ARGUMENTS')
        bad = self.service.call('cad_plan_evidence_tasks', {**args, 'output_path': 'outputs/reset.json', 'draft_check_path': h['check']['path']})
        self.assertEqual(bad['errors'][0]['code'], 'BASELINE_ALREADY_EXISTS')


if __name__ == '__main__': unittest.main()
