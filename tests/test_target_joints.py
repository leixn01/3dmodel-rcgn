import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cadkin.errors import ToolFailure
from cadkin.rigid.groups import candidate_partitions
from cadkin.rigid.target_joints import target_draft
from cadkin.tools.rigid import build_draft, replay_draft
from cadkin.tools.comparison import replay_check
from cadkin.tools.followup import replay_plan
from cadkin.tools.solidworks import SolidWorksTools
from tests.rigid_fakes import rigid_target
from tests.matching_fakes import toy_reference
from tests.chain_fakes import write_chain_fixture


class TargetDraftTests(unittest.TestCase):
    def build(self, target=None, refs=(), **args):
        target = target or rigid_target()
        return target_draft(target, candidate_partitions(target), list(refs), **args)

    def test_target_pairs_exist_without_any_reference(self):
        data = self.build()
        self.assertEqual(data['algorithm_version'], 2); self.assertFalse(data['template_search_requested'])
        self.assertGreater(data['summary']['target_pairs_returned'], 0)
        self.assertEqual(data['summary']['evaluated_states'], 0)
        for run in data['partition_results']:
            self.assertIsNone(run['match']); self.assertEqual(run['skip_reason'], 'templates_not_requested')
            for pair in run['connection_candidates']:
                self.assertEqual(pair['target_joint_kind'], 'unknown'); self.assertIsNone(pair['target_degrees_of_freedom'])
                self.assertFalse(pair['reference_required']); self.assertFalse(pair['connection_confirmed'])

    def test_no_reference_can_change_target_baseline(self):
        plain = self.build(); revolute = self.build(refs=[toy_reference(kind='revolute')])
        prismatic = self.build(refs=[toy_reference(kind='prismatic')])
        for a, b, c in zip(plain['partition_results'], revolute['partition_results'], prismatic['partition_results']):
            self.assertEqual(a['connection_candidates'], b['connection_candidates'])
            self.assertEqual(a['connection_candidates'], c['connection_candidates'])

    def test_no_positive_link_preserves_unknown_pairs(self):
        target = rigid_target()
        for pair in target['pairs']:
            pair.update(signals=[], axis_relations=[], link_support=0., representative_axis_unit=None)
        data = self.build(target)
        rows = [p for run in data['partition_results'] for p in run['connection_candidates']]
        self.assertTrue(rows); self.assertEqual({p['assessment'] for p in rows}, {'insufficient_evidence'})

    def test_names_cannot_choose_joint_type(self):
        target = rigid_target(); before = self.build(target)
        for node in target['nodes']: node['role_context'] = {'label': '端座 导轨 旋转 丝杆 台钳'}
        after = self.build(target)
        self.assertEqual(before, after)

    def test_explicit_reference_type_and_dof_stay_separate(self):
        data = self.build(refs=[toy_reference(kind='revolute')])
        edges = [e for r in data['partition_results'] if r['match'] for c in r['match']['candidates'] for e in c['joint_hypotheses']]
        self.assertTrue(edges)
        for edge in edges:
            self.assertEqual(edge['reference_joint_kind'], 'revolute'); self.assertEqual(edge['hypothesis_kind'], 'unknown')
            self.assertIsNone(edge['dof_hypothesis']); self.assertEqual(edge['reference_dof'], 1)
            self.assertFalse(edge['reference_type_transferred']); self.assertEqual(edge['parameter_status']['kind'], 'unknown')

    def test_target_pair_budget_is_shared_and_omissions_visible(self):
        data = self.build(max_target_pairs=1)
        self.assertEqual(data['summary']['target_pairs_returned'], 1); self.assertTrue(data['target_pairs_truncated'])
        self.assertGreater(data['summary']['target_pairs_omitted'], 0)
        self.assertEqual(sum(r['target_pair_coverage']['budget'] for r in data['partition_results']), 1)

    def test_invalid_budget_rejected(self):
        for limit in (0, True, 2001):
            with self.assertRaises(ToolFailure): self.build(max_target_pairs=limit)


class TargetDraftToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)
        args = write_chain_fixture(self.root, with_lock=True)
        self.service = SolidWorksTools(self.root, factory=lambda: (_ for _ in ()).throw(AssertionError('Unexpected CAD call')))
        self.addCleanup(self.service.close)
        for tool, arguments in [
            ('cad_build_chain_evidence', args),
            ('cad_build_target_graph', dict(chain_path='outputs/chain.json', output_path='outputs/target.json')),
            ('cad_build_rigid_candidates', dict(target_graph_path='outputs/target.json', output_path='outputs/rigid.json'))]:
            self.assertNotEqual(self.service.call(tool, arguments)['status'], 'error')

    def call(self, tool, **arguments):
        result = self.service.call(tool, arguments); self.assertNotEqual(result['status'], 'error', result)
        return result['data']

    def test_default_skips_template_loading_and_supports_check_plan(self):
        with patch('cadkin.tools.rigid.load_references', side_effect=AssertionError('Default must not load templates')):
            data = self.call('cad_draft_joints', rigid_candidates_path='outputs/rigid.json', output_path='outputs/plain.json')
            self.assertEqual(data['template_sources'], []); self.assertFalse(data['heldout_exposed'])
            check = self.call('cad_check_joint_draft', joint_draft_path='outputs/plain.json', output_path='outputs/check.json')
            plan = self.call('cad_plan_evidence_tasks', draft_check_path='outputs/check.json', output_path='outputs/plan.json')
            self.assertEqual(check['algorithm_version'], 2)
            self.assertNotIn('PARTITION_NOT_SEARCHED', {f['code'] for f in check['findings']})
            self.assertIn('TARGET_JOINT_TYPE_UNDETERMINED', {f['code'] for f in check['findings']})
            self.assertEqual(replay_plan(self.root, 'outputs/plan.json')[0]['tasks'], plan['tasks'])

    @unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates]')
    def test_actual_bench_vise_swivel_never_becomes_target_revolute(self):
        matched = self.call('cad_match_mechanism_templates', target_graph_path='outputs/target.json',
            template_ids=['bench_vise'], pattern_size=2, max_candidates=20, output_path='outputs/match.json')
        edges = [e for c in matched['candidates'] for e in c['joint_hypotheses'] if e['reference_joint_id'].endswith('/swivel')]
        self.assertTrue(edges)
        self.assertTrue(all(e['reference_joint_kind'] == 'revolute' and e['target_joint_kind'] == 'unknown' and
            e['hypothesis_kind'] == 'unknown' and e['target_degrees_of_freedom'] is None for e in edges))
        self.assertTrue(any(e['reference_compatibility'] == 'opposed_by_active_lock' for e in edges))
        draft = self.call('cad_draft_joints', rigid_candidates_path='outputs/rigid.json', template_ids=['bench_vise'],
            pattern_size=2, max_candidates=10, output_path='outputs/bench-draft.json')
        self.assertTrue(draft['template_search_requested'])
        self.assertTrue(all(e['hypothesis_kind'] == 'unknown' and e['dof_hypothesis'] is None
            for r in draft['partition_results'] if r['match'] for c in r['match']['candidates'] for e in c['joint_hypotheses']))

    @unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates]')
    def test_legacy_draft_and_check_replay_stays_exact(self):
        legacy, _, _ = build_draft(self.root, 'outputs/rigid.json', template_ids=['bench_vise'],
            pattern_size=2, _algorithm_version=1)
        path = self.root/'outputs/legacy.json'; path.write_text(json.dumps(legacy), encoding='utf-8')
        replayed, _, _, _ = replay_draft(self.root, str(path))
        self.assertEqual(replayed, legacy)
        old = self.call('cad_check_joint_draft', joint_draft_path=str(path), output_path='outputs/legacy-check.json')
        self.assertEqual(old['algorithm_version'], 1)
        self.assertEqual(replay_check(self.root, 'outputs/legacy-check.json')[0]['findings'], old['findings'])

    def test_tampered_target_conclusion_is_rejected(self):
        self.call('cad_draft_joints', rigid_candidates_path='outputs/rigid.json', output_path='outputs/draft.json')
        path = self.root/'outputs/draft.json'; data = json.loads(path.read_text())
        data['partition_results'][0]['connection_candidates'][0]['target_joint_kind'] = 'revolute'
        path.write_text(json.dumps(data), encoding='utf-8')
        result = self.service.call('cad_check_joint_draft', dict(joint_draft_path=str(path), output_path='outputs/rejected.json'))
        self.assertEqual(result['errors'][0]['code'], 'EVIDENCE_MISMATCH'); self.assertFalse((self.root/'outputs/rejected.json').exists())
