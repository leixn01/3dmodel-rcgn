import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from cadkin.errors import ToolFailure, failure
from cadkin.constraints.capture import validate_enhanced_capture
from cadkin.followup.constraint_planning import plan_constraint_tasks
from cadkin.tools.constraint_analysis import replay_analysis
from cadkin.tools.execution import run_plan, replay_execution, execute_task
from cadkin.tools.followup import replay_plan
from cadkin.tools.observation_index import replay_index
from cadkin.tools.solidworks import SolidWorksTools
from tests.constraint_fakes import write_constraint_followup_fixture
from tests.execution_fakes import live_service


class ConstraintFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app, self.mates, _ = write_constraint_followup_fixture(self.root)
        self.live = live_service(self.root, self.app); self.addCleanup(self.live.close)
        self.factory = Mock(side_effect=AssertionError('Offline tool connected to CAD'))
        self.offline = SolidWorksTools(self.root, factory=self.factory); self.addCleanup(self.offline.close)

    def read(self, name): return json.loads((self.root/name).read_text(encoding='utf-8'))
    def call(self, name, **args):
        result = self.offline.call(name, args)
        self.assertNotEqual(result['status'], 'error', result)
        return result['data']
    def plan(self, name='next', **args):
        return self.call('cad_plan_evidence_tasks', draft_check_path='outputs/check.json',
            constraint_analysis_path='outputs/constraints.json', output_path=f'outputs/{name}.json', **args)
    def execute(self): return run_plan(self.live, 'outputs/plan.json', 'outputs/run.json')['data']
    def reintegrate(self):
        return self.call('cad_reintegrate_evidence', execution_path='outputs/run.json', output_path='outputs/updated.json')
    def replan(self, update, **args):
        return self.call('cad_plan_evidence_tasks', draft_check_path=update['after_check_source']['path'],
            constraint_analysis_path=update['after_constraint_analysis_source']['path'], output_path='outputs/stop.json', **args)

    def test_basic_capture_allows_one_enhanced_call_with_all_guards(self):
        plan = self.read('outputs/plan.json')
        self.assertEqual(plan['algorithm_version'], 4); self.assertEqual(len(plan['tasks']), 9)
        captures = [t for t in plan['tasks'] if t['phase'] == 'capture']
        self.assertEqual(len(captures), 1); self.assertEqual(captures[0]['tool'], 'sw_mate_inventory')
        self.assertTrue(captures[0]['arguments']['include_reference_geometry'])
        self.assertEqual(len(captures[0]['expected_context']), 3)
        self.assertEqual(plan, replay_plan(self.root, 'outputs/plan.json')[0])
        limited = self.plan(max_tasks=8)
        self.assertEqual(limited['tasks'], []); self.assertEqual(len(limited['deferred_tasks']), 1)
        self.assertEqual(limited['continuation']['reason'], 'CAPTURE_BUDGET_UNAVAILABLE')

    def test_full_update_recomputes_constraints_inherits_history_and_stops(self):
        original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        before = (self.app.ActiveDoc.dirty, self.app.ActiveDoc.rebuilt, list(self.app.ActiveDoc.SelectionManager.selected))
        execution = self.execute(); self.assertTrue(execution['guards_passed'])
        update = self.reintegrate(); self.assertTrue(update['recomputation_complete'], update)
        self.assertEqual(update['algorithm_version'], 3); self.assertEqual(update['applied_capture_ids'], execution['eligible_capture_ids'])
        after, _ = replay_analysis(self.root, update['after_constraint_analysis_source']['path'])
        index, ib = replay_index(self.root, update['after_evidence_index_source']['path'])
        self.assertEqual(after['evidence_index_source'], ib); self.assertEqual(index['rounds_completed'], 1)
        self.assertEqual(after['parameters']['distance_tolerance_mm'], .1)
        self.assertEqual(after['parameters']['angle_tolerance_deg'], .1)
        self.assertEqual(after['parameters']['max_pairs'], 200)
        changed = next(p for p in update['constraint_changes']['pairs'] if p['occurrence_paths'] == ['base-1','carriage-1'])
        self.assertEqual(changed['before']['candidate_patterns'], [])
        self.assertEqual([p['kind'] for p in changed['after']['candidate_patterns']], ['revolute'])
        self.assertIn('MATE_REFERENCE_GEOMETRY_MISSING_OR_UNSUPPORTED', changed['missing_codes_no_longer_observed'])
        self.assertFalse(changed['feature_identity_matched']); self.assertEqual(changed['target_joint_kind'], 'unknown')
        stopped = self.replan(update, max_tasks=200)
        self.assertEqual(stopped['continuation']['action'], 'stop'); self.assertEqual(stopped['continuation']['rounds_completed'], 1)
        self.assertEqual(stopped['evidence_index_source'], ib)
        result = self.offline.call('sw_execute_evidence_task', {'plan_path': 'outputs/stop.json', 'output_path': 'outputs/blocked.json'})
        self.assertEqual(result['errors'][0]['code'], 'NO_CAPTURE_TASKS'); self.factory.assert_not_called()
        self.assertEqual(before, (self.app.ActiveDoc.dirty, self.app.ActiveDoc.rebuilt, self.app.ActiveDoc.SelectionManager.selected))
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p,h in original.items()))

    def test_partial_enhanced_capture_is_retained_and_not_retried(self):
        self.mates[0].GetDefinition = lambda: None
        execution = self.execute(); self.assertTrue(execution['guards_passed'])
        self.assertEqual(execution['eligible_capture_ids'], [])
        capture = next(r for r in execution['records'] if r['state'] == 'partial')
        raw = self.read(capture['envelope_source']['path'])
        self.assertIsNone(raw['data']['mates'][0]['constraint_options']['concentric_lock_rotation'])
        update = self.reintegrate(); self.assertTrue(update['recomputation_complete'], update)
        self.assertEqual(update['applied_capture_ids'], []); self.assertEqual(len(update['excluded_captures']), 1)
        index, _ = replay_index(self.root, update['after_evidence_index_source']['path'])
        self.assertEqual(index['summary']['retained_unsuccessful_attempts'], 1)
        after, _ = replay_analysis(self.root, update['after_constraint_analysis_source']['path'])
        self.assertEqual(after['coverage']['candidate_patterns'], 0)
        stopped = self.replan(update, max_tasks=200)
        self.assertEqual(stopped['tasks'], []); self.assertEqual(stopped['continuation']['reason'], 'PRIOR_ENHANCED_ATTEMPT_NO_AUTOMATIC_RETRY')

    def test_nonfatal_api_failure_retains_round_and_guards(self):
        original = self.live.call
        def call(name, args=None):
            if name == 'sw_mate_inventory': return failure(ToolFailure('API_ERROR', 'Synthetic read failure'))
            return original(name, args)
        self.live.call = call
        execution = self.execute(); self.assertTrue(execution['guards_passed']); self.assertEqual(execution['summary']['calls_executed'], 9)
        update = self.reintegrate(); self.assertTrue(update['recomputation_complete'])
        stop = self.replan(update); self.assertEqual(stop['continuation']['rounds_completed'], 1); self.assertFalse(stop['tasks'])

    def test_enhanced_request_rejects_basic_or_malformed_response(self):
        task = next(t for t in self.read('outputs/plan.json')['tasks'] if t['phase'] == 'capture')
        raw = self.live.call(task['tool'], task['arguments'])
        validate_enhanced_capture(raw['data'], task['arguments'])
        for kind in ('marker', 'params', 'count', 'geometry', 'numeric', 'partial_claim', 'duplicate'):
            data = copy.deepcopy(raw['data'])
            if kind == 'marker': data.pop('reference_geometry_capture')
            elif kind == 'params': data['parameters']['include_reference_geometry'] = False
            elif kind == 'count': data['mate_count'] += 1
            elif kind == 'geometry': data['mates'][0]['entities'][0]['reference_geometry'] = ['bad']
            elif kind == 'numeric': data['mates'][0]['entities'][0]['reference_geometry']['point_root_m'] = [9,9,9]
            elif kind == 'partial_claim': data['mates'][0]['errors'] = [{'code':'API_ERROR'}]
            elif kind == 'duplicate': data['mates'][1]['feature_id'] = data['mates'][0]['feature_id']
            with self.subTest(kind=kind), self.assertRaises(ToolFailure): validate_enhanced_capture(data, task['arguments'])
        original = self.live.call
        def basic(name, args=None):
            if name == 'sw_mate_inventory': return original(name, {**args, 'include_reference_geometry': False})
            return original(name, args)
        self.live.call = basic
        execution = self.execute(); self.assertFalse(execution['guards_passed']); self.assertEqual(execution['summary']['calls_executed'], 5)
        self.assertEqual(execution['eligible_capture_ids'], [])
        self.assertTrue(any('INVALID_CONSTRAINT_SOURCE' in r['codes'] and r['fatal'] for r in execution['records']))
        self.assertEqual(replay_execution(self.root, 'outputs/run.json')[0], {k:v for k,v in execution.items() if k!='output_path'})

    def test_mate_change_is_fatal_and_blocks_reintegration(self):
        from types import SimpleNamespace
        seen = []
        def definition(): seen.append(1); return SimpleNamespace(LockRotation=len(seen)>1)
        self.mates[0].GetDefinition = definition
        execution = self.execute(); self.assertFalse(execution['guards_passed'])
        self.assertTrue(any('MATE_STATE_CHANGED' in r['codes'] and r['fatal'] for r in execution['records']))
        result = self.offline.call('cad_reintegrate_evidence', {'execution_path':'outputs/run.json','output_path':'outputs/invalid.json'})
        self.assertEqual(result['errors'][0]['code'], 'EXECUTION_GUARDS_FAILED')
        self.assertFalse((self.root/'outputs/invalid-derived').exists())

    def test_reintegration_failure_does_not_publish_final_links(self):
        self.execute()
        with patch('cadkin.tools.constraint_reintegration.analyze_constraints', side_effect=ToolFailure('SYNTHETIC_FAILURE','failed')):
            update = self.reintegrate()
        self.assertFalse(update['recomputation_complete']); self.assertEqual(update['applied_capture_ids'], [])
        self.assertIsNone(update['after_check_source']); self.assertIsNone(update['after_constraint_analysis_source'])
        self.assertIsNone(update['after_evidence_index_source']); self.assertIsNone(update['constraint_changes'])
        self.assertIsNotNone(update['pipeline_error'])

    def test_plan_and_source_tampering_rejected_before_cad(self):
        plan = self.read('outputs/plan.json'); plan['tasks'][4]['arguments']['include_reference_geometry'] = False
        (self.root/'outputs/forged.json').write_text(json.dumps(plan), encoding='utf-8')
        call = Mock()
        with self.assertRaises(ToolFailure): execute_task(self.root, call, 'outputs/forged.json', 'outputs/receipt.json')
        call.assert_not_called()
        with (self.root/'constraint-mates.json').open('a') as stream: stream.write('\n')
        result = self.offline.call('cad_plan_evidence_tasks', {'draft_check_path':'outputs/check.json',
            'constraint_analysis_path':'outputs/constraints.json','output_path':'outputs/bad.json'})
        self.assertEqual(result['errors'][0]['code'], 'EVIDENCE_MISMATCH'); self.factory.assert_not_called()

    def test_fourth_round_shares_history_with_generic_collection(self):
        index = None
        for number in range(1,4):
            params = {'evidence_index_path': index} if index else {}
            plan = self.call('cad_plan_evidence_tasks', draft_check_path='outputs/check.json', max_tasks=5,
                output_path=f'outputs/generic{number}.json', **params)
            self.assertEqual(plan['summary']['planned_capture_tasks'], 1)
            run_plan(self.live, plan['output_path'], f'outputs/run{number}.json')
            data = self.call('cad_index_evidence', draft_check_path='outputs/check.json', execution_path=f'outputs/run{number}.json',
                output_path=f'outputs/index{number}.json', max_contexts=17)
            index = data['output_path']; self.assertEqual(data['rounds_completed'], number)
        plan = self.plan('fourth', evidence_index_path=index)
        self.assertEqual(plan['continuation']['rounds_completed'], 3)
        run_plan(self.live, plan['output_path'], 'outputs/run.json')
        update = self.reintegrate(); self.assertTrue(update['recomputation_complete'], update)
        new_index, _ = replay_index(self.root, update['after_evidence_index_source']['path'])
        self.assertEqual(new_index['rounds_completed'], 4); self.assertEqual(len(new_index['observations']), 4)
        self.assertEqual(new_index['parameters']['max_contexts'], 17)
        stopped = self.replan(update)
        self.assertEqual(stopped['continuation']['reason'], 'ROUND_LIMIT'); self.assertEqual(stopped['tasks'], [])
        replay_plan(self.root, stopped['output_path'])
        result = self.offline.call('cad_plan_evidence_tasks', {'draft_check_path':update['after_check_source']['path'],
            'constraint_analysis_path':update['after_constraint_analysis_source']['path'],'evidence_index_path':index,
            'output_path':'outputs/old-index.json'})
        self.assertEqual(result['errors'][0]['code'], 'EVIDENCE_MISMATCH')

    def test_cli_uses_constraint_report_and_inherits_current_index(self):
        command = [sys.executable, '-m', 'cadkin', 'plan-evidence', 'outputs/check.json',
            '--constraint-analysis','outputs/constraints.json','--max-tasks','9','--output','outputs/cli.json']
        process = subprocess.run(command, cwd=self.root, capture_output=True, text=True, timeout=60)
        self.assertEqual(process.returncode, 0, process.stdout+process.stderr)
        self.assertEqual(self.read('outputs/cli.json')['algorithm_version'], 4)
        self.execute(); update = self.reintegrate()
        process = subprocess.run([sys.executable,'-m','cadkin','analyze-constraints', str(self.root/'outputs/updated-derived/target.json'),
            '--evidence-index',update['after_evidence_index_source']['path'],'--distance-tolerance-mm','.1','--angle-tolerance-deg','.1',
            '--output','outputs/bound.json'],cwd=self.root,capture_output=True,text=True,timeout=60)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        self.assertEqual(self.read('outputs/bound.json')['rounds_completed'],1)

    def test_no_mates_and_enhanced_source_stop_without_cad(self):
        for mode, enriched in [('no_mates',False),('revolute',True),('conflict',True)]:
            root = self.root/mode; write_constraint_followup_fixture(root, mode, enriched)
            plan = json.loads((root/'outputs/plan.json').read_text())
            self.assertFalse(plan['tasks']); self.assertEqual(plan['continuation']['action'],'stop')
            if mode=='conflict': self.assertTrue(plan['retained_constraint_conflicts'])

    def test_distinct_snapshots_missing_basis_and_basic_index_capability(self):
        target = self.read('outputs/target.json'); check = self.read('outputs/check.json'); analysis = self.read('outputs/constraints.json')
        other = copy.deepcopy(analysis); other['mate_sources'].append({'path':'different.json','sha256':'f'*64})
        plan = plan_constraint_tasks(target,check,other,None,[],'outputs/raw',20)
        self.assertFalse(plan['tasks']); self.assertEqual(plan['continuation']['reason'],'MULTIPLE_MATE_SNAPSHOTS_NOT_COMBINED')
        other['mate_sources'] = []
        self.assertEqual(plan_constraint_tasks(target,check,other,None,[],'outputs/raw',20)['continuation']['reason'],'NO_EXISTING_CONNECTION_BASIS')
        # Capability distinction: a previous basic scan must not suppress a first enhanced scan.
        index={'rounds_completed':1,'observations':[{'tool':'sw_mate_inventory','arguments':{'max_mates':200},'usable':True,'id':'basic'}]}
        plan=plan_constraint_tasks(target,check,analysis,index,[],'outputs/raw',20)
        self.assertEqual(plan['continuation']['action'],'collect'); self.assertEqual(plan['continuation']['rounds_completed'],1)


if __name__ == '__main__': unittest.main()
