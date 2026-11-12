import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from cadkin.errors import ToolFailure, failure
from cadkin.followup.observations import associate, describe_capture, reuse_facts, MAX_ROUNDS
from cadkin.followup.planning import plan_tasks
from cadkin.tools.execution import run_plan
from cadkin.tools.observation_index import replay_index, same_context
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.replay_guard import bounded_replay
from tests.execution_fakes import write_execution_fixture, live_service


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve(); app = write_execution_fixture(root); service = live_service(root, app)
        try: yield root, app, service
        finally: service.close()


@unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates]')
class ObservationIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name).resolve()
        cls.app = write_execution_fixture(cls.root); cls.live = live_service(cls.root, cls.app)
        run_plan(cls.live, 'outputs/plan.json', 'outputs/run.json')
        cls.offline = SolidWorksTools(cls.root, factory=lambda: (_ for _ in ()).throw(AssertionError('Offline tool attempted CAD')))
    @classmethod
    def tearDownClass(cls):
        cls.live.close(); cls.offline.close(); cls.temp.cleanup()
    def name(self, suffix): return f'outputs/{self._testMethodName}-{suffix}.json'
    def read(self, path): return json.loads((self.root/path).read_text(encoding='utf-8'))
    def index(self, **changes):
        return self.offline.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json',
            'execution_path': 'outputs/run.json', 'output_path': self.name('index'), **changes})
    def plan(self, index, **changes):
        return self.offline.call('cad_plan_evidence_tasks', {'draft_check_path': 'outputs/check.json',
            'evidence_index_path': index, 'output_path': self.name('next'), **changes})

    def test_associations_bind_nodes_pairs_findings_and_joint_contexts(self):
        r = self.index(); self.assertEqual(r['status'], 'ok', r); d = r['data']
        self.assertEqual(d['summary']['reusable'], 3); self.assertEqual(d['rounds_completed'], 1)
        ids = {o['id'] for o in d['observations']}
        self.assertTrue(d['joint_contexts']); self.assertTrue(d['finding_contexts'])
        self.assertTrue(all(set(j['observation_ids']) <= ids for j in d['joint_contexts']))
        self.assertTrue(all(not p['face_pair_selected'] and not p['connection_confirmed'] for p in d['pair_contexts']))
        self.assertFalse(d['mechanically_verified']); self.assertFalse(d['requires_human_review'])
        for b in d['input_files']: self.assertEqual(hashlib.sha256(Path(b['path']).read_bytes()).hexdigest(), b['sha256'])

    def test_face_locators_and_unresolved_mate_names_are_explicit(self):
        d = self.index()['data']
        constraints = [o for o in d['observations'] if o['family'] == 'constraints']
        face = next(o for o in d['observations'] if o['family'] == 'faces')
        self.assertTrue(all(not o['details']['reference_names_resolved_to_occurrences'] for o in constraints))
        self.assertTrue(all(not o['details']['mate_activity_known'] for o in constraints))
        self.assertFalse(face['details']['live_face_identity_verified'])
        self.assertEqual(face['details']['face_count'], len(face['details']['faces']))

    def test_complete_observations_stop_without_guard_only_calls(self):
        d = self.plan(self.index()['data']['output_path'])['data']
        self.assertEqual(d['algorithm_version'], 2); self.assertEqual(d['continuation']['action'], 'stop')
        self.assertGreater(d['continuation']['remaining_findings'], 0)
        self.assertEqual(d['remaining_findings'], self.read('outputs/check.json')['findings'])
        self.assertEqual(d['tasks'], []); self.assertEqual(d['summary']['total_tool_calls'], 0)
        self.assertGreaterEqual(d['summary']['reused_evidence_groups'], 3)
        r = self.offline.call('sw_execute_evidence_task', {'plan_path': d['output_path'], 'output_path': self.name('receipt')})
        self.assertEqual(r['errors'][0]['code'], 'NO_CAPTURE_TASKS')
        self.assertFalse((self.root/self.name('receipt')).exists())
        with self.assertRaises(ToolFailure): run_plan(self.offline, d['output_path'], self.name('run'))
        run_output = self.root/self.name('run')
        self.assertFalse((run_output.parent/(run_output.stem+'-steps')).exists())

    def test_index_cannot_be_reused_for_a_different_valid_check(self):
        index = self.index()['data']['output_path']
        r = self.offline.call('cad_check_joint_draft', {'joint_draft_path': 'outputs/drafts.json', 'max_findings': 1, 'output_path': self.name('limited')})
        self.assertNotEqual(r['status'], 'error')
        r = self.plan(index, draft_check_path=self.name('limited'))
        self.assertEqual(r['errors'][0]['code'], 'EVIDENCE_MISMATCH')

    def test_index_tampering_is_rejected(self):
        d = self.index()['data']; path = Path(d['output_path']); raw = json.loads(path.read_text(encoding='utf-8'))
        raw['observations'][0]['usable'] = False; path.write_text(json.dumps(raw), encoding='utf-8')
        r = self.plan(str(path)); self.assertEqual(r['errors'][0]['code'], 'EVIDENCE_MISMATCH')

    def test_original_capture_tampering_is_rejected_and_restored(self):
        d = self.index()['data']; path = Path(d['observations'][0]['source']['path']); original = path.read_bytes()
        try:
            raw = json.loads(original); raw['data']['complete'] = False; path.write_text(json.dumps(raw), encoding='utf-8')
            r = self.plan(d['output_path']); self.assertEqual(r['errors'][0]['code'], 'EVIDENCE_MISMATCH')
        finally: path.write_bytes(original)

    def test_output_exists_and_invalid_budget_are_rejected(self):
        self.index(); self.assertEqual(self.index()['errors'][0]['code'], 'OUTPUT_EXISTS')
        self.assertEqual(self.index(output_path=self.name('other'), max_contexts=0)['errors'][0]['code'], 'INVALID_ARGUMENTS')

    def test_context_limit_does_not_drop_collected_observations(self):
        r = self.index(max_contexts=1); self.assertEqual(r['status'], 'partial')
        self.assertTrue(r['data']['joint_contexts_truncated']); self.assertEqual(len(r['data']['observations']), 3)
        self.assertEqual(self.plan(r['data']['output_path'])['data']['continuation']['action'], 'stop')

    def test_original_files_remain_unchanged(self):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        self.plan(self.index()['data']['output_path'])
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})

    def test_incomplete_execution_rejected(self):
        r = self.index(execution_path='outputs/run-steps/step-001.json')
        self.assertEqual(r['errors'][0]['code'], 'EXECUTION_NOT_COMPLETE')

    def test_failed_guards_never_create_reusable_index(self):
        with fixture() as (root, app, service):
            app.ActiveDoc.dirty = True; run_plan(service, 'outputs/plan.json', 'outputs/run.json')
            r = service.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': 'outputs/run.json', 'output_path': 'outputs/index.json'})
            self.assertEqual(r['errors'][0]['code'], 'EXECUTION_GUARDS_FAILED')
            self.assertFalse((root/'outputs/index.json').exists())

    def test_partial_capture_is_retained_and_not_retried_even_with_larger_budget(self):
        with fixture() as (root, app, service):
            original = service.call
            def call(name, args=None):
                r = original(name, args)
                if name == 'sw_component_faces':
                    r['status'] = 'partial'; r['errors'] = [{'code': 'FACE_LIMIT'}]; r['data']['complete'] = False; r['data']['truncated'] = True
                return r
            service.call = call; run_plan(service, 'outputs/plan.json', 'outputs/run.json')
            r = service.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': 'outputs/run.json', 'output_path': 'outputs/index.json'})
            self.assertEqual(r['status'], 'partial'); self.assertEqual(r['data']['summary']['retained_unsuccessful_attempts'], 1)
            p = service.call('cad_plan_evidence_tasks', {'draft_check_path': 'outputs/check.json', 'evidence_index_path': 'outputs/index.json', 'max_tasks': 200, 'output_path': 'outputs/next.json'})
            self.assertEqual(p['data']['continuation']['action'], 'stop'); self.assertEqual(len(p['data']['blocked_requests']), 1)

    def test_failed_capture_is_diagnostic_and_blocks_repeat(self):
        with fixture() as (root, app, service):
            original = service.call
            def call(name, args=None):
                if name == 'sw_component_constraints': return failure(ToolFailure('API_ERROR', 'Synthetic failure'))
                return original(name, args)
            service.call = call; run_plan(service, 'outputs/plan.json', 'outputs/run.json')
            r = service.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': 'outputs/run.json', 'output_path': 'outputs/index.json'})
            self.assertEqual(r['data']['summary']['retained_unsuccessful_attempts'], 2)
            p = service.call('cad_plan_evidence_tasks', {'draft_check_path': 'outputs/check.json', 'evidence_index_path': 'outputs/index.json', 'output_path': 'outputs/next.json'})
            self.assertEqual(p['data']['summary']['planned_capture_tasks'], 0)
            self.assertEqual(p['data']['continuation']['reason'], 'NO_NEW_CAPTURE_AFTER_ATTEMPTS')

    def test_three_budgeted_rounds_preserve_lineage_and_do_not_repeat(self):
        with fixture() as (root, app, service):
            args = {'draft_check_path': 'outputs/check.json', 'max_tasks': 5, 'output_path': 'outputs/small1.json'}
            service.call('cad_plan_evidence_tasks', args); observed = []
            for number in range(1, 4):
                result = run_plan(service, f'outputs/small{number}.json', f'outputs/run{number}.json')
                observed.extend(result['data']['eligible_capture_ids'])
                r = service.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': f'outputs/run{number}.json', 'output_path': f'outputs/index{number}.json'})
                self.assertNotEqual(r['status'], 'error', r); self.assertEqual(r['data']['rounds_completed'], number)
                self.assertEqual(r['data']['summary']['observations'], number)
                next_plan = service.call('cad_plan_evidence_tasks', {**args, 'evidence_index_path': f'outputs/index{number}.json', 'output_path': f'outputs/small{number+1}.json'})
                self.assertNotEqual(next_plan['status'], 'error', next_plan)
            self.assertEqual(len(observed), len(set(observed)))
            self.assertEqual(next_plan['data']['continuation']['action'], 'stop')
            replay_index(root, 'outputs/index3.json')

    def test_cli_indexes_offline(self):
        env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get('PYTHONPATH', '')}
        p = subprocess.run([sys.executable, '-m', 'cadkin', 'index-evidence', 'outputs/check.json', 'outputs/run.json', '--output', self.name('index')], cwd=self.root, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        p = subprocess.run([sys.executable, '-m', 'cadkin', 'plan-evidence', 'outputs/check.json', '--evidence-index', self.name('index'), '--output', self.name('plan')], cwd=self.root, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(self.read(self.name('plan'))['continuation']['action'], 'stop')


class ObservationRulesTests(unittest.TestCase):
    def test_document_scope_and_pose_change_are_not_reusable(self):
        target = {'document': {'document_token': 'x', 'path': 'a', 'title': 'A', 'document_type': 'assembly', 'configuration': 'D', 'dirty': False},
                  'nodes': [{'id': 'a', 'parent_id': None, 'file_path': 'a', 'configuration': 'D', 'to_root_column_vectors_m': [], 'eligible': True}]}
        self.assertTrue(same_context(target, target))
        for field, value in [('file_path', 'b'), ('configuration', 'B'), ('to_root_column_vectors_m', [1])]:
            changed = copy.deepcopy(target); changed['nodes'][0][field] = value; self.assertFalse(same_context(target, changed))
        changed = copy.deepcopy(target); changed['nodes'] = []; self.assertFalse(same_context(target, changed))
        changed = copy.deepcopy(target); changed['document']['dirty'] = True; self.assertFalse(same_context(target, changed))

    def test_complete_empty_faces_are_reusable(self):
        d = describe_capture('sw_component_faces', {'faces': [], 'face_count': 0, 'geometry_scope': 'referenced_part_definition', 'assembly_instance_features_evaluated': False})
        self.assertEqual(d['face_count'], 0)
        i = {'rounds_completed': 1, 'observations': [{'id': 'o', 'tool': 'sw_component_faces', 'occurrence_paths': ['a'], 'usable': True, 'family': 'faces', 'source': {'path': 'x', 'sha256': 'a'}}]}
        self.assertTrue(reuse_facts(i)['faces']['a'])

    def test_invalid_constraint_summary_and_face_counts_rejected(self):
        with self.assertRaises(ToolFailure): describe_capture('sw_component_constraints', {'fixed_state': {'value': True, 'scope': 'unavailable_nested_context'}})
        with self.assertRaises(ToolFailure): describe_capture('sw_component_faces', {'faces': [], 'face_count': 1})

    def test_both_fixed_context_and_conflicting_snapshots_remain_conditional(self):
        observations = [{'id': p, 'occurrence_paths': [p], 'usable': True, 'family': 'constraints', 'details': {'fixed_state': {'value': True}}} for p in ('a', 'b')]
        target = {'nodes': [{'id': 'a'}, {'id': 'b'}], 'pairs': [{'id': 'p', 'node_ids': ['a', 'b']}]}
        check = {'findings': []}; draft = {'partition_results': [{'partition_id': 'p', 'match': {'candidates': [{'template_id': 't', 'rank': 1, 'joint_hypotheses': [{'reference_joint_id': 'j', 'hypothesis_kind': 'prismatic', 'member_occurrence_paths': [['a'], ['b']]}]}]}}]}
        d = associate(observations, target, check, draft, 200)
        self.assertEqual(d['joint_contexts'][0]['signals'], ['FIXED_MEMBERS_VS_MOVING_HYPOTHESIS'])
        other = copy.deepcopy(observations[0]); other['id'] = 'other'; other['details']['fixed_state']['value'] = False
        d = associate(observations+[other], target, check, draft, 200)
        self.assertEqual(d['conflicting_fixed_occurrences'], ['a']); self.assertIsNone(d['joint_contexts'][0]['all_endpoint_members_fixed'])

    def test_round_limit_stops_new_requests(self):
        from tests.followup_fakes import draft_fixture
        from cadkin.followup.checks import check_draft
        target, rigid, draft = draft_fixture(); check = check_draft(target, rigid, draft)
        facts = {'_indexed': True, 'rounds_completed': MAX_ROUNDS, 'attempted_requests': {}}
        d = plan_tasks(target, check, facts, 'outputs/captures')
        self.assertEqual(d['continuation']['reason'], 'ROUND_LIMIT'); self.assertFalse(d['tasks'])
        self.assertTrue(d['blocked_requests'])

    def test_cycle_and_depth_guard_reset_after_failure(self):
        with tempfile.TemporaryDirectory() as t:
            @bounded_replay
            def cycle(root, name): return cycle(root, name)
            with self.assertRaises(ToolFailure) as e: cycle(t, 'a.json')
            self.assertEqual(e.exception.code, 'EVIDENCE_CYCLE')
            @bounded_replay
            def depth(root, name, n=0): return depth(root, f'{n+1}.json', n+1)
            with self.assertRaises(ToolFailure) as e: depth(t, '0.json')
            self.assertEqual(e.exception.code, 'EVIDENCE_DEPTH_LIMIT')
            @bounded_replay
            def good(root, name): return True
            self.assertTrue(good(t, 'a.json'))


if __name__ == '__main__': unittest.main()
