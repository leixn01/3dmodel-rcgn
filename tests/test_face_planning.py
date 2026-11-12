import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cadkin.errors import ToolFailure, failure
from cadkin.followup.face_planning import surface_residual_mm, plan_face_tasks, probe_key
from cadkin.geometry import transform_from_sw
from cadkin.tools.execution import run_plan
from cadkin.tools.face_planning import face_facts, build_face_plan, catalog, witness
from cadkin.tools.files import read_json
from cadkin.tools.followup import replay_plan
from cadkin.tools.solidworks import SolidWorksTools
from tests.execution_fakes import write_execution_fixture, live_service
from tests.sw_fakes import pose


class ResidualTests(unittest.TestCase):
    def face(self, kind, parameters):
        return {'descriptor': {'surface_type': kind, 'surface_parameters_part': parameters, 'body_type': 0,
                              'face_in_surface_sense': False, 'uv_bounds': [0, 1, 0, 1], 'area_part_m2': 1}}

    def test_plane_rotation_translation_scale_and_reflection(self):
        face = self.face('plane', [1, 0, 0, 0, 0, 0])
        for scale in (2, -2):
            t = transform_from_sw(pose(x=1, y=2, quarter_turn=True, scale=scale).ArrayData)
            self.assertAlmostEqual(surface_residual_mm(face, t, [1000, 2003, 500]), 3)

    def test_cylinder_axis_offset_and_scaled_radius(self):
        face = self.face('cylinder', [.1, 0, 0, 0, 0, 4, .01])
        t = transform_from_sw(pose(x=1, scale=2).ArrayData)
        self.assertAlmostEqual(surface_residual_mm(face, t, [1223, 0, 9000]), 3)

    def test_analytic_match_does_not_claim_trim_membership(self):
        face = self.face('plane', [1, 0, 0, 0, 0, 0])
        self.assertEqual(surface_residual_mm(face, transform_from_sw(pose().ArrayData), [0, 1e6, -1e6]), 0)
        self.assertIsNone(surface_residual_mm(self.face('other', None), transform_from_sw(pose().ArrayData), [0, 0, 0]))

    def test_nonfinite_input_rejected(self):
        with self.assertRaises(ToolFailure): surface_residual_mm(self.face('plane', [1, 0, 0, 0, 0, 0]), transform_from_sw(pose().ArrayData), [math.nan, 0, 0])


@unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates]')
class FacePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name).resolve()
        cls.app = write_execution_fixture(cls.root); cls.live = live_service(cls.root, cls.app)
        cls.offline = SolidWorksTools(cls.root, factory=lambda: (_ for _ in ()).throw(AssertionError('Offline tool attempted CAD')))
        run_plan(cls.live, 'outputs/plan.json', 'outputs/run.json')
        r = cls.offline.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': 'outputs/run.json', 'output_path': 'outputs/index.json'})
        assert r['status'] != 'error', r
        cls.index = r['data']
        cls.base = dict(draft_check_path='outputs/check.json', evidence_index_path='outputs/index.json', max_component_gap_mm=30, surface_tolerance_mm=.1)
        cls.built_plan, cls.check, cls.target = build_face_plan(cls.root, **cls.base, output_path='outputs/not-created.json')
        cls.facts = face_facts(cls.root, cls.target, cls.index)

    @classmethod
    def tearDownClass(cls):
        cls.live.close(); cls.offline.close(); cls.temp.cleanup()

    def path(self, suffix): return f'outputs/{self._testMethodName}-{suffix}.json'
    def plan(self, **changes):
        return self.offline.call('cad_plan_face_probes', {**self.base, 'output_path': self.path('plan'), **changes})
    def pure(self, facts=None, index=None, **changes):
        return plan_face_tasks(self.target, self.check, copy.deepcopy(facts or self.facts), index or self.index,
                               self.root/'outputs/future', max_component_gap_mm=30, surface_tolerance_mm=.1, **changes)

    def test_source_binding_and_competing_faces(self):
        r = self.plan(); self.assertEqual(r['status'], 'ok', r); p = r['data']
        self.assertEqual(p['algorithm_version'], 3)
        self.assertEqual(p['coverage']['candidate_pairs_before_limits'], 12)
        self.assertEqual(p['coverage']['previously_attempted_face_pairs'], 1)
        self.assertEqual(len(p['face_candidates']), 11)
        self.assertEqual(p['summary']['total_tool_calls'], 19)
        for c in p['face_candidates']:
            self.assertFalse(c['finite_face_membership_tested']); self.assertFalse(c['live_face_identity_verified'])
            self.assertFalse(c['connection_confirmed']); self.assertEqual(c['surface_residuals_mm'], [0, 0])
            raw, sha = read_json(Path(c['witness_source']['path'])); self.assertEqual(sha, c['witness_source']['sha256'])
            m = raw['data']['measurement']
            self.assertEqual(c['seed_points_root_mm'], [m['point_left_mm'], m['point_right_mm'],
                [x/2+y/2 for x,y in zip(m['point_left_mm'], m['point_right_mm'])]])
        self.assertEqual(replay_plan(self.root, p['output_path'])[0]['tasks'], p['tasks'])

    def test_budget_includes_guards_and_never_creates_guard_only_loop(self):
        p = self.plan(max_tasks=6)['data']
        self.assertEqual(p['tasks'], []); self.assertEqual(p['continuation']['reason'], 'CAPTURE_BUDGET_UNAVAILABLE')
        stopped = self.offline.call('sw_execute_evidence_task', {'plan_path': p['output_path'], 'output_path': self.path('receipt')})
        self.assertEqual(stopped['errors'][0]['code'], 'NO_CAPTURE_TASKS')
        p = self.plan(max_tasks=7, output_path=self.path('small'))['data']
        self.assertEqual(p['summary']['planned_capture_tasks'], 1); self.assertEqual(p['summary']['guard_tasks'], 6)

    def test_each_search_limit_is_visible(self):
        p = self.plan(max_component_pairs=1, max_face_candidates=1, max_face_pairs=1)['data']
        self.assertTrue(p['output_truncated']); self.assertEqual(p['coverage']['examined_component_pairs'], 1)
        self.assertGreater(p['coverage']['face_candidates_omitted'], 0)
        self.assertTrue(any(e['equal_residual_at_cutoff'] for c in p['pair_contexts'] for e in c.get('endpoints', [])))
        q = self.plan(max_face_pairs=2, output_path=self.path('pairs'))['data']
        self.assertEqual(len(q['face_candidates']), 2); self.assertGreater(q['coverage']['candidate_pairs_unattempted'], 2)

    def test_missing_catalog_schedules_only_missing_instance_then_replans(self):
        facts = copy.deepcopy(self.facts); del facts['faces']['rail-1']
        # This test represents a scope with no prior rail scan; the real fixture has one.
        facts['attempted_requests'] = {}
        p = self.pure(facts)
        capture = [t for t in p['tasks'] if t['phase'] == 'capture']
        self.assertEqual(sum(t['tool'] == 'sw_component_faces' for t in capture), 1)
        self.assertEqual(capture[0]['arguments']['occurrence_path'], 'rail-1')
        self.assertTrue(all('rail-1' not in [n['id'] for n in t['expected_context']] for t in capture if t['tool'] == 'sw_probe_face_pair'))

    def test_missing_catalog_failed_attempt_is_not_retried(self):
        facts = copy.deepcopy(self.facts); del facts['faces']['rail-1']
        p = self.pure(facts)
        self.assertTrue(p['blocked_requests']); self.assertFalse(any(t['tool'] == 'sw_component_faces' for t in p['tasks']))

    def test_conflicts_and_missing_distance_remain_unknown(self):
        facts = copy.deepcopy(self.facts)
        facts['distances'].pop(('base-1', 'rail-1'))
        facts['distance_conflicts'].add(('base-1', 'carriage-1')); facts['face_conflicts'].add('rail-1')
        p = self.pure(facts); reasons = {c['reason'] for c in p['pair_contexts']}
        self.assertTrue({'NO_COMPLETE_DISTANCE_WITNESS', 'CONFLICTING_DISTANCE_SNAPSHOTS', 'CONFLICTING_FACE_CATALOGS'} <= reasons)
        self.assertEqual(p['tasks'], [])

    def test_four_round_limit(self):
        p = self.pure(index={**self.index, 'rounds_completed': 4})
        self.assertEqual(p['tasks'], []); self.assertEqual(p['continuation']['reason'], 'ROUND_LIMIT')
        self.assertEqual(p['remaining_findings'], self.check['findings'])

    def test_live_execution_index_review_and_stop(self):
        p = self.plan()['data']; result = run_plan(self.live, p['output_path'], self.path('run'))
        self.assertEqual(result['status'], 'ok', result); self.assertTrue(result['data']['guards_passed'])
        self.assertEqual(len(result['data']['eligible_capture_ids']), 11)
        indexed = self.offline.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': self.path('run'), 'output_path': self.path('index')})
        self.assertEqual(indexed['status'], 'ok', indexed)
        probes = [o for o in indexed['data']['observations'] if o['family'] == 'face_probes']
        self.assertEqual(len(probes), 11); self.assertTrue(all(o['usable'] for o in probes))
        self.assertTrue(all(p['face_pair_selected'] and not p['connection_confirmed'] for p in indexed['data']['pair_contexts']))
        reviewed = self.offline.call('cad_review_face_contacts', {'probe_paths': [o['source']['path'] for o in probes],
            'output_path': self.path('review'), 'contact_tolerance_mm': .1, 'angle_tolerance_deg': 5})
        self.assertEqual(reviewed['status'], 'ok', reviewed); self.assertFalse(reviewed['data']['contact_confirmed'])
        stopped = self.plan(evidence_index_path=self.path('index'), output_path=self.path('stop'), max_iterations=30)['data']
        self.assertEqual(stopped['continuation']['action'], 'stop'); self.assertEqual(stopped['tasks'], [])
        general = self.offline.call('cad_plan_evidence_tasks', {'draft_check_path': 'outputs/check.json', 'evidence_index_path': self.path('index'), 'output_path': self.path('general')})
        self.assertNotEqual(general['status'], 'error', general)

    def test_partial_probe_retained_no_retry_and_independent_guards_run(self):
        p = self.plan(max_tasks=7)['data']; capture = next(t for t in p['tasks'] if t['phase'] == 'capture')
        original = self.live.call
        def call(name, args=None):
            r = original(name, args)
            if name == 'sw_probe_face_pair':
                r['status'] = 'partial'; r['errors'] = [{'code': 'SYNTHETIC_PARTIAL'}]; r['data']['complete'] = False
            return r
        self.live.call = call
        try: r = run_plan(self.live, p['output_path'], self.path('run'))
        finally: self.live.call = original
        self.assertTrue(r['data']['guards_passed']); self.assertEqual(r['data']['summary']['partial'], 1)
        r = self.offline.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': self.path('run'), 'output_path': self.path('index')})
        self.assertEqual(r['data']['summary']['retained_unsuccessful_attempts'], 1)
        q = self.plan(evidence_index_path=self.path('index'), output_path=self.path('next'), max_iterations=50)['data']
        self.assertNotIn(capture['id'], [c['id'] for c in q['face_candidates']])

    def test_pose_change_stops_before_probes(self):
        p = self.plan(max_tasks=7)['data']; old = self.app.ActiveDoc.root.children[0].Transform2
        self.app.ActiveDoc.root.children[0].Transform2 = pose(x=7)
        try: r = run_plan(self.live, p['output_path'], self.path('run'))
        finally: self.app.ActiveDoc.root.children[0].Transform2 = old
        self.assertFalse(r['data']['guards_passed']); self.assertEqual(r['data']['eligible_capture_ids'], [])
        self.assertTrue(all(x['state'] == 'skipped' for x in r['data']['records'] if x['task_id'].startswith('probe-pair-')))

    def test_failed_probe_is_retained_but_does_not_block_post_guards(self):
        p = self.plan(max_tasks=7)['data']; original = self.live.call
        def call(name, args=None):
            return failure(ToolFailure('API_ERROR', 'Synthetic read failure')) if name == 'sw_probe_face_pair' else original(name, args)
        self.live.call = call
        try: r = run_plan(self.live, p['output_path'], self.path('run'))
        finally: self.live.call = original
        self.assertTrue(r['data']['guards_passed']); self.assertEqual(r['data']['summary']['failed'], 1)
        r = self.offline.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': self.path('run'), 'output_path': self.path('index')})
        self.assertEqual(r['data']['summary']['retained_unsuccessful_attempts'], 1)
        q = self.plan(evidence_index_path=self.path('index'), output_path=self.path('next'))['data']
        self.assertEqual(q['coverage']['previously_attempted_face_pairs'], 2)

    def test_invalid_probe_metrics_halt_and_never_become_eligible(self):
        p = self.plan(max_tasks=7)['data']; original = self.live.call
        def call(name, args=None):
            r = original(name, args)
            if name == 'sw_probe_face_pair': r['data']['samples'][0]['metrics']['gap_mm'] += 1
            return r
        self.live.call = call
        try: r = run_plan(self.live, p['output_path'], self.path('run'))
        finally: self.live.call = original
        self.assertFalse(r['data']['guards_passed']); self.assertEqual(r['data']['eligible_capture_ids'], [])
        self.assertTrue(any('INVALID_FACE_PROBE_SOURCE' in x['codes'] for x in r['data']['records']))

    def test_tampered_plan_and_source_rejected(self):
        p = self.plan()['data']; path = Path(p['output_path']); raw = json.loads(path.read_text())
        raw['tasks'][0]['tool'] = 'sw_set_view'; path.write_text(json.dumps(raw))
        with self.assertRaises(ToolFailure): replay_plan(self.root, str(path))
        source = Path(p['face_candidates'][0]['face_sources'][0]['path']); saved = source.read_bytes()
        try:
            source.write_bytes(saved + b' ')
            r = self.plan(output_path=self.path('bad-source')); self.assertEqual(r['errors'][0]['code'], 'EVIDENCE_MISMATCH')
        finally: source.write_bytes(saved)

    def test_thresholds_finite_and_output_exclusive(self):
        for key, value in [('surface_tolerance_mm', math.nan), ('max_component_gap_mm', math.inf), ('max_tasks', 0)]:
            self.assertEqual(self.plan(**{key: value})['errors'][0]['code'], 'INVALID_ARGUMENTS')
        self.plan(); self.assertEqual(self.plan()['errors'][0]['code'], 'OUTPUT_EXISTS')

    def test_index_requires_exact_check_binding(self):
        self.offline.call('cad_check_joint_draft', {'joint_draft_path': 'outputs/drafts.json', 'output_path': self.path('check'), 'max_findings': 1})
        r = self.plan(draft_check_path=self.path('check')); self.assertEqual(r['errors'][0]['code'], 'EVIDENCE_MISMATCH')

    def test_catalog_and_distance_context_validation(self):
        b = self.facts['faces']['base-1']['binding']; raw, _ = read_json(Path(b['path']))
        raw['data']['target']['referenced_configuration'] = 'OTHER'
        with self.assertRaises(ToolFailure): catalog(raw, b, {n['id']: n for n in self.target['nodes']}, self.target['document'])
        b = next(iter(self.facts['distances'].values()))['source']; raw, _ = read_json(Path(b['path']))
        raw['data']['measurement']['distance_mm'] += 1
        with self.assertRaises(ToolFailure): witness(raw, b, {n['id']: n for n in self.target['nodes']}, self.target['document'])

    def test_cli_and_original_files_unchanged(self):
        before = {b['path']: hashlib.sha256(Path(b['path']).read_bytes()).hexdigest() for b in self.index['input_files']}
        env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get('PYTHONPATH', '')}
        p = subprocess.run([sys.executable, '-m', 'cadkin', 'plan-face-probes', 'outputs/check.json', '--evidence-index', 'outputs/index.json',
            '--max-component-gap-mm', '30', '--surface-tolerance-mm', '.1', '--output', self.path('cli')], cwd=self.root, env=env,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(before, {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before})


if __name__ == '__main__': unittest.main()
