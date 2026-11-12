import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cadkin.errors import ToolFailure
from cadkin.tools.files import read_json
from cadkin.tools.face_reintegration import route_face_captures
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.followup.face_comparison import compare_faces
from tests.face_reintegration_fakes import prepare


@unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates]')
class FaceReintegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name).resolve()
        cls.app, cls.receipt, cls.captures = prepare(cls.root)
        cls.service = SolidWorksTools(cls.root, factory=lambda: (_ for _ in ()).throw(AssertionError('Offline tool called CAD')))
        cls.chain = read_json(cls.root/'outputs/chain.json')[0]; cls.target = read_json(cls.root/'outputs/target.json')[0]
        cls.original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.root.rglob('*.json')}

    @classmethod
    def tearDownClass(cls):
        cls.service.close(); cls.temp.cleanup()

    def name(self, suffix): return f'outputs/{self._testMethodName}-{suffix}.json'
    def call(self, name, **args):
        result = self.service.call(name, args)
        self.assertNotEqual(result['status'], 'error', result); return result['data']
    def update(self, **options):
        return self.call('cad_reintegrate_evidence', execution_path='outputs/face-run.json', output_path=self.name('updated'), **options)
    def route(self, chain=None, captures=None, review=None):
        return route_face_captures(self.root, chain or self.chain, self.target,
            self.captures if captures is None else captures, review)

    def test_automatic_basis_preserves_old_rows_and_thresholds(self):
        data = self.update(); self.assertTrue(data['recomputation_complete'])
        self.assertEqual(len(data['applied_capture_ids']), 3); self.assertEqual(len(data['supplemental_captures']), 8)
        self.assertEqual({c['reason'] for c in data['supplemental_captures']}, {'NO_MATCHING_FACE_REVIEW'})
        update = data['face_updates'][0]
        self.assertEqual(update['parameters'], {'contact_tolerance_mm': .1, 'angle_tolerance_deg': 5})
        self.assertEqual(update['retained_previous_probes'], 1)
        old = read_json(Path(update['basis_source']['path']))[0]; new = read_json(Path(update['output_source']['path']))[0]
        self.assertEqual(new['pairs'][0], old['pairs'][0]); self.assertEqual(len(new['pairs']), 4)
        self.assertFalse(data['mechanically_verified']); self.assertFalse(data['requires_human_review'])

    def test_provided_basis_only_adds_uncovered_pairs_and_reindexes_current_check(self):
        data = self.update(face_review_path='outputs/supplied-review.json')
        self.assertTrue(data['recomputation_complete']); self.assertEqual(len(data['applied_capture_ids']), 11)
        self.assertEqual(data['supplemental_captures'], [])
        updates = {u['basis_kind']: u for u in data['face_updates']}
        self.assertEqual(updates['existing_chain_review']['parameters']['contact_tolerance_mm'], .1)
        self.assertEqual(updates['provided_review_for_uncovered_pairs']['parameters']['contact_tolerance_mm'], .2)
        self.assertEqual(updates['provided_review_for_uncovered_pairs']['added_probes'], 8)
        compared = self.call('cad_compare_draft_checks', before_check_path='outputs/check.json',
            after_check_path=data['after_check_source']['path'], output_path=self.name('compare'))
        summary = compared['face_evidence']['summary']
        self.assertEqual(summary['before_face_observations'], 1); self.assertEqual(summary['after_face_observations'], 12)
        self.assertEqual(summary['newly_observed_ids'], 11); self.assertEqual(summary['changed_ids'], 0)
        self.assertEqual(summary['provenance_changed_ids'], 1)
        self.assertTrue(compared['settings_equal']); self.assertFalse(compared['resolved_findings_asserted'])
        indexed = self.call('cad_index_evidence', draft_check_path=data['after_check_source']['path'],
            execution_path='outputs/face-run.json', output_path=self.name('index'))
        self.assertTrue(all(o['details']['available_for_existing_reintegration'] and o['details']['reintegration_requires_compatible_face_review']
            for o in indexed['observations'] if o['family'] == 'face_probes' and o['usable']))
        stopped = self.call('cad_plan_face_probes', draft_check_path=data['after_check_source']['path'],
            evidence_index_path=indexed['output_path'], max_component_gap_mm=30, surface_tolerance_mm=.1, output_path=self.name('stop'))
        self.assertEqual(stopped['tasks'], []); self.assertEqual(stopped['continuation']['rounds_completed'], 2)
        self.assertTrue(stopped['remaining_findings'])
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in self.original.items()))

    def test_supplied_review_cannot_import_unguarded_rows(self):
        selected = {k: v for k, v in self.captures.items() if 'rail-1' in [f['target']['occurrence_path'] for f in v['data']['sources']]}
        key = next(iter(selected)); selected = {key: selected[key]}
        routed = self.route(captures=selected, review='outputs/supplied-review.json')
        self.assertEqual(len(routed['jobs']), 1); self.assertEqual(routed['jobs'][0]['capture_ids'], [key])
        self.assertEqual(routed['jobs'][0]['probe_paths'], [selected[key]['source']['path']])

    def test_no_existing_basis_requires_explicit_review(self):
        chain = copy.deepcopy(self.chain); chain['sources'] = [s for s in chain['sources'] if s['kind'] != 'face_contact']
        routed = self.route(chain=chain)
        self.assertEqual(routed['jobs'], []); self.assertEqual({e['reason'] for e in routed['entries']}, {'NO_MATCHING_FACE_REVIEW'})
        supplied = self.route(chain=chain, review='outputs/supplied-review.json')
        self.assertEqual(len(supplied['jobs'][0]['capture_ids']), 11)

    def test_duplicate_guarded_face_pair_is_not_silently_selected(self):
        captures = copy.deepcopy(self.captures); key = next(iter(captures)); captures['duplicate'] = captures[key]
        routed = self.route(captures=captures, review='outputs/supplied-review.json')
        self.assertEqual(sum(e['reason'] == 'DUPLICATE_GUARDED_FACE_PAIR' for e in routed['entries']), 2)

    def test_existing_observation_is_reused_without_append(self):
        old = read_json(self.root/'outputs/face-review.json')[0]['pairs'][0]
        envelope, sha = read_json(Path(old['probe_path']))
        routed = self.route(captures={'old': {'tool': 'sw_probe_face_pair', 'source': {'path': old['probe_path'], 'sha256': sha}, 'data': envelope['data']}})
        self.assertEqual(routed['reused_capture_ids'], ['old']); self.assertEqual(routed['jobs'], [])

    def test_conflicting_thresholds_remain_supplemental(self):
        old = read_json(self.root/'outputs/face-review.json')[0]
        path = self.name('other-review')
        self.call('cad_review_face_contacts', probe_paths=[r['probe_path'] for r in old['pairs']],
            output_path=path, contact_tolerance_mm=.3, angle_tolerance_deg=8)
        _, sha = read_json(self.root/path)
        chain = copy.deepcopy(self.chain); chain['sources'].append({'kind': 'face_contact', 'path': str(self.root/path), 'sha256': sha})
        routed = self.route(chain=chain, review='outputs/supplied-review.json')
        self.assertEqual(sum(e['reason'] == 'AMBIGUOUS_FACE_REVIEW_THRESHOLDS' for e in routed['entries']), 3)
        self.assertEqual(len(routed['jobs'][0]['capture_ids']), 8)

    def test_source_capacity_is_not_automatically_expanded(self):
        chain = copy.deepcopy(self.chain)
        chain['sources'] += [next(s for s in chain['sources'] if s['kind'] != 'face_contact')] * (20-len(chain['sources']))
        routed = self.route(chain=chain, review='outputs/supplied-review.json')
        self.assertEqual(sum(e['reason'] == 'CHAIN_EVIDENCE_CAPACITY_LIMIT' for e in routed['entries']), 8)

    def test_wrong_review_kind_rejected_before_outputs(self):
        result = self.service.call('cad_reintegrate_evidence', dict(execution_path='outputs/face-run.json',
            face_review_path='outputs/chain.json', output_path=self.name('bad')))
        self.assertEqual(result['status'], 'error'); self.assertFalse((self.root/self.name('bad')).exists())
        self.assertFalse((self.root/self.name('bad')).with_suffix('').with_name(Path(self.name('bad')).stem+'-derived').exists())

    def test_tampered_review_and_failed_pipeline_cannot_claim_applied(self):
        path = self.root/self.name('forged'); raw = read_json(self.root/'outputs/supplied-review.json')[0]
        raw['pairs'][0]['review_state'] = 'forged'; path.write_text(json.dumps(raw), encoding='utf-8')
        result = self.service.call('cad_reintegrate_evidence', dict(execution_path='outputs/face-run.json',
            face_review_path=str(path), output_path=self.name('rejected')))
        self.assertEqual(result['status'], 'error'); self.assertEqual(result['errors'][0]['code'], 'EVIDENCE_MISMATCH')
        with patch('cadkin.tools.reintegration.chain_dossier', side_effect=ToolFailure('TEST_FAILURE', 'synthetic downstream failure')):
            data = self.update(face_review_path='outputs/supplied-review.json')
        self.assertFalse(data['recomputation_complete']); self.assertIsNone(data['after_check_source'])
        self.assertEqual(data['applied_capture_ids'], []); self.assertEqual(len(data['attempted_capture_ids']), 11)

    def test_output_is_exclusive(self):
        self.update()
        result = self.service.call('cad_reintegrate_evidence', dict(execution_path='outputs/face-run.json', output_path=self.name('updated')))
        self.assertEqual(result['errors'][0]['code'], 'OUTPUT_EXISTS')

    def test_comparison_separates_numerics_and_provenance_and_thresholds(self):
        after = copy.deepcopy(self.chain)
        evidence = next(e for p in after['pairs'] for e in p['evidence'] if e['kind'] == 'face_contact')
        evidence['source_path'] += '-changed'; evidence['record']['converged'] = not evidence['record']['converged']
        diff = compare_faces(self.chain, after, self.target, self.target)
        self.assertEqual(diff['summary']['changed_ids'], 1); self.assertEqual(diff['summary']['provenance_changed_ids'], 1)
        evidence['parameters']['contact_tolerance_mm'] += 1
        diff = compare_faces(self.chain, after, self.target, self.target)
        self.assertEqual(diff['summary']['newly_observed_ids'], 1); self.assertEqual(diff['summary']['no_longer_observed_ids'], 1)
        self.assertFalse(any(p['connection_confirmed'] for p in diff['pairs']))
