import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cadkin.errors import ToolFailure
from cadkin.rigid.groups import candidate_partitions, aggregate_target
from cadkin.rigid.joints import axis_draft, canonical_line, draft_partitions
from cadkin.tools.solidworks import SolidWorksTools
from tests.rigid_fakes import rigid_target, mate_signal, axis_relation
from tests.matching_fakes import toy_reference
from tests.chain_fakes import write_chain_fixture


class RigidTests(unittest.TestCase):
    def test_baseline_and_lock_closure_preserve_all_instances(self):
        t=rigid_target();r=candidate_partitions(t)
        self.assertEqual(len(r['partitions']),2)
        self.assertEqual(r['partitions'][0]['basis'],'unmerged_baseline')
        merged=r['partitions'][1]
        self.assertIn(['a','d'],[g['member_occurrence_paths'] for g in merged['groups']])
        for p in r['partitions']:
            self.assertEqual(sorted(n for g in p['groups'] for n in g['member_occurrence_paths']),['a','b','c','d'])
            self.assertTrue(all(not g['rigidity_confirmed'] for g in p['groups']))
        self.assertFalse(r['partition_space_exhaustive']);self.assertFalse(r['requires_human_review'])

    def test_labels_parent_axes_and_ordinary_mates_do_not_merge(self):
        t=rigid_target()
        for n in t['nodes']:n.update(file_path='same',parent_id='same',role_context='fixed')
        for p in t['pairs']:p['signals']=[mate_signal('concentric')]
        self.assertEqual(len(candidate_partitions(t)['partitions']),1)

    def test_suppressed_and_error_lock_mates_do_not_merge(self):
        for signal in [mate_signal(active=False),{**mate_signal(),'record_errors':[{'code':'failure'}]}]:
            t=rigid_target();t['pairs'][3]['signals']=[signal]
            self.assertEqual(len(candidate_partitions(t)['partitions']),1)

    def test_ineligible_and_error_nodes_block_merge(self):
        for update in [{'eligible':False},{'source_errors':[{'code':'failure'}]}]:
            t=rigid_target();t['nodes'][3].update(update)
            r=candidate_partitions(t);self.assertEqual(len(r['partitions']),1)
            self.assertEqual(r['coverage']['blocked_proposals'],1)

    def test_pair_flags_and_motion_mates_block_pair(self):
        t=rigid_target();t['pairs'][3]['flags']=[{'code':'conflict'}]
        self.assertEqual(len(candidate_partitions(t)['partitions']),1)
        t['pairs'][3]['flags']=[];t['pairs'][3]['signals'].append(mate_signal('hinge'))
        r=candidate_partitions(t);self.assertIn('MOTION_MATE_PRESENT',r['pair_proposals'][0]['blocking_reasons'])

    def test_lock_transitivity_conflicting_motion_and_size_limit(self):
        t=rigid_target();t['pairs'][0]['signals']=[mate_signal()]
        r=candidate_partitions(t);self.assertIn(['a','b','d'],[g['member_occurrence_paths'] for g in r['partitions'][1]['groups']])
        limited=candidate_partitions(t,max_group_size=2)
        self.assertTrue(limited['omitted_groups']);self.assertTrue(all(len(g['member_occurrence_paths'])<=2 for p in limited['partitions'] for g in p['groups']))
        t['pairs'][4]['signals']=[mate_signal('slider')]
        r=candidate_partitions(t)
        self.assertTrue(any('INTERNAL_MOTION_MATE' in g['reasons'] for g in r['omitted_groups']))
        self.assertFalse(any(set(['a','b','d'])<=set(g['member_occurrence_paths']) for p in r['partitions'] for g in p['groups']))

    def test_contact_is_weak_single_bridge_and_optional(self):
        t=rigid_target();t['pairs'][0]['signals']=[{'kind':'near_component'}]
        t['pairs'][2]['signals']=[{'kind':'near_face_sample','converged':True}]
        r=candidate_partitions(t)
        weak=[p for p in r['partitions'] if p['basis']=='single_contact_bridge']
        self.assertEqual(len(weak),2)
        self.assertTrue(all('CONTACT_DOES_NOT_PROVE_RIGIDITY' in p['risk_codes'] for p in weak))
        self.assertFalse(any(len(p['groups'])==1 for p in r['partitions']))
        self.assertEqual(len(candidate_partitions(t,include_contact_hypotheses=False)['partitions']),2)

    def test_unconverged_face_and_distance_only_do_not_merge(self):
        t=rigid_target();t['pairs'][3]['signals']=[{'kind':'near_face_sample','converged':False},{'kind':'distance_observation'}]
        self.assertEqual(len(candidate_partitions(t)['partitions']),1)

    def test_output_limit_keeps_baseline_and_counts_omissions(self):
        r=candidate_partitions(rigid_target(),max_partitions=1)
        self.assertTrue(r['output_truncated']);self.assertEqual(r['coverage']['generated_partitions'],2)
        self.assertEqual(r['partitions'][0]['basis'],'unmerged_baseline')

    def test_partition_ids_and_order_stable(self):
        t=rigid_target();a=candidate_partitions(t)
        t['nodes'].reverse();t['pairs'].reverse();b=candidate_partitions(t)
        self.assertEqual(a,b)

    def test_group_support_not_inflated_by_repeated_member_edges(self):
        t=rigid_target();t['pairs'][4].update(link_support=.8,representative_axis_unit=[1,0,0],axis_relations=[axis_relation('b','d')])
        r=candidate_partitions(t);g=aggregate_target(t,r['partitions'][1])
        self.assertLessEqual(max(p['link_support'] for p in g['pairs']),1)
        self.assertTrue(any(len(p['source_pair_ids'])==2 for p in g['pairs']))

    def test_competing_group_axes_stay_unknown(self):
        t=rigid_target();t['pairs'][4].update(link_support=.8,representative_axis_unit=[0,1,0],axis_relations=[axis_relation('b','d',direction=[0,1,0])])
        p=next(p for p in aggregate_target(t,candidate_partitions(t)['partitions'][1])['pairs'] if 'ab' in p['source_pair_ids'])
        self.assertIsNone(p['representative_axis_unit'])

    def test_parameters_strict_and_bounded(self):
        for args in [{'max_group_size':True},{'max_group_size':21},{'max_partitions':0},{'max_partitions':13},{'include_contact_hypotheses':1}]:
            with self.assertRaises(ToolFailure):candidate_partitions(rigid_target(),**args)

    def test_aggregated_axis_budget_preserves_all_pair_ids(self):
        t=rigid_target();t['pairs'][0]['axis_relations']*=129
        graph=aggregate_target(t,candidate_partitions(t)['partitions'][1])
        p=next(p for p in graph['pairs'] if 'ab' in p['source_pair_ids'])
        self.assertEqual(len(p['axis_relations']),128);self.assertEqual(p['axis_relation_count'],129)
        self.assertTrue(p['axes_truncated']);self.assertIsNone(p['representative_axis_unit'])
        self.assertIn('bd',p['source_pair_ids']);self.assertIsNone(axis_draft(p,.1,1)['axis_line_candidate'])


class DraftTests(unittest.TestCase):
    def draft(self,**args):
        t=rigid_target();return draft_partitions(t,candidate_partitions(t),[toy_reference()],**args)

    def test_group_mapping_and_joint_unknowns(self):
        r=self.draft();rows=[c for p in r['partition_results'] if p['match'] for c in p['match']['candidates']]
        self.assertTrue(any(len(m['member_occurrence_paths'])==2 for c in rows for m in c['mapping']))
        for c in rows:
            self.assertNotIn('ONE_OCCURRENCE_PER_REFERENCE_BODY',c['risk_codes'])
            for e in c['joint_hypotheses']:
                self.assertNotIn('occurrence_paths',e);self.assertIsNone(e['limits']);self.assertIsNone(e['axis_origin_m'])
                self.assertFalse(e['dof_verified']);self.assertFalse(e['joint_axis_verified']);self.assertIsNone(e['pitch_m_per_revolution'])
        self.assertLessEqual(r['summary']['evaluated_states'],20000)

    def test_partition_budget_is_shared_and_zero_skips_explicit(self):
        r=self.draft(max_states=1)
        self.assertEqual(r['summary']['evaluated_states'],1)
        self.assertEqual(r['partition_results'][1]['skip_reason'],'partition_state_budget_zero')
        self.assertFalse(r['search_exhaustive_within_retained_partitions'])

    def test_window_size_never_shrinks_for_grouping(self):
        r=self.draft(pattern_size=4)
        self.assertEqual(r['partition_results'][1]['skip_reason'],'insufficient_eligible_groups')
        self.assertIsNone(r['partition_results'][1]['match'])

    def test_line_sign_and_shift_invariance_and_metres(self):
        a=canonical_line([.3,.002,0],[1,0,0]);b=canonical_line([-.9,.002,0],[-1,0,0])
        self.assertEqual(a,b);self.assertEqual(a['point_on_line_root_m'],[0.,.002,0.])

    def test_multiple_parallel_offset_lines_do_not_become_pivot(self):
        p=rigid_target()['pairs'][0];p['axis_relations'].append(axis_relation(origin=[0,.005,0]))
        d=axis_draft(p,.1,1);self.assertEqual(len(d['geometric_line_candidates']),2);self.assertIsNone(d['axis_line_candidate'])
        self.assertIn('not a joint pivot',d['point_semantics'])

    def test_parallel_relation_never_certifies_unique_axis(self):
        p=rigid_target()['pairs'][0];p['axis_relations'][0]['kind']='parallel_candidate'
        self.assertIsNone(axis_draft(p,.1,1)['axis_line_candidate'])

    def test_geometry_limits_and_flags_keep_axis_unknown(self):
        p=rigid_target()['pairs'][0];p['axis_relations']*=129
        d=axis_draft(p,.1,1);self.assertTrue(d['line_candidates_truncated']);self.assertIsNone(d['axis_line_candidate'])
        p=rigid_target()['pairs'][0];p['flags']=[{'code':'conflict'}]
        self.assertIsNone(axis_draft(p,.1,1)['axis_line_candidate'])

    def test_distinct_axis_line_cap_and_provenance_cap_explicit(self):
        p=rigid_target()['pairs'][0]
        p['axis_relations']=[axis_relation(origin=[0,i*.005,0]) for i in range(17)]
        d=axis_draft(p,.1,1);self.assertEqual(len(d['geometric_line_candidates']),16)
        self.assertTrue(d['line_candidates_truncated']);self.assertIsNone(d['axis_line_candidate'])
        p['axis_relations']=[axis_relation()]*40;d=axis_draft(p,.1,1)
        self.assertEqual(d['axis_line_candidate']['observation_count'],80)
        self.assertTrue(d['axis_line_candidate']['source_list_truncated'])

    def test_no_axes_and_fixed_drafts_do_not_invent_parameters(self):
        t=rigid_target()
        for p in t['pairs']:p['axis_relations']=[];p['representative_axis_unit']=None
        r=draft_partitions(t,candidate_partitions(t),[toy_reference(kind='fixed')])
        for row in r['partition_results']:
            for c in row['match']['candidates']:
                for e in c['joint_hypotheses']:
                    self.assertIsNone(e['geometry']);self.assertIsNone(e['direction_candidate_root_unit']);self.assertEqual(e['dof_hypothesis'],0)

    def test_no_positive_links_remain_without_candidates(self):
        t=rigid_target()
        for p in t['pairs']:p['signals']=[];p['link_support']=0.
        r=draft_partitions(t,candidate_partitions(t),[toy_reference()])
        self.assertEqual(r['summary']['returned_candidates'],0)

    def test_draft_parameters_reject_nan_bool_and_bounds(self):
        for args in [{'pattern_size':True},{'max_candidates':11},{'max_states':0},{'beam_width':True},
                     {'axis_distance_tolerance_mm':float('nan')},{'axis_angle_tolerance_deg':0},{'angle_tolerance_deg':True}]:
            with self.assertRaises(ToolFailure):self.draft(**args)


@unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates]')
class RigidToolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        args=write_chain_fixture(self.root,with_lock=True)
        def forbidden():raise AssertionError('No COM in offline tools')
        self.service=SolidWorksTools(self.root,factory=forbidden)
        self.assertEqual(self.service.call('cad_build_chain_evidence',args)['status'],'ok')
        self.target_args={'chain_path':'outputs/chain.json','output_path':'outputs/target.json'}
        self.assertEqual(self.service.call('cad_build_target_graph',self.target_args)['status'],'ok')
        self.args={'target_graph_path':'outputs/target.json','output_path':'outputs/rigid.json'}
        self.assertEqual(self.service.call('cad_build_rigid_candidates',self.args)['status'],'ok')
        self.draft_args={'rigid_candidates_path':'outputs/rigid.json','template_ids':['gas_lift_bar_stool'],
                         'pattern_size':2,'output_path':'outputs/drafts.json'}

    def tearDown(self):self.service.close();self.temp.cleanup()
    def read(self,name):return json.loads((self.root/name).read_text(encoding='utf-8'))
    def write(self,name,data):(self.root/name).write_text(json.dumps(data),encoding='utf-8')

    def test_source_replayed_one_to_many_and_bindings(self):
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        r=self.service.call('cad_draft_joints',self.draft_args);self.assertEqual(r['status'],'ok',r.get('errors'))
        d=r['data'];self.assertTrue(d['rigid_source']['sha256']);self.assertTrue(d['template_sources'])
        self.assertTrue(any(len(m['member_occurrence_paths'])==2 for p in d['partition_results'] for c in p['match']['candidates'] for m in c['mapping']))
        self.assertEqual(before,{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before})

    def test_target_and_rigid_tampering_rejected(self):
        d=self.read('outputs/target.json');d['nodes'][0]['eligible']=False;self.write('outputs/bad-target.json',d)
        r=self.service.call('cad_build_rigid_candidates',{**self.args,'target_graph_path':'outputs/bad-target.json','output_path':'outputs/bad-rigid.json'})
        self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')
        d=self.read('outputs/rigid.json');d['partitions'][0]['groups'][0]['member_occurrence_paths']=['made-up'];self.write('outputs/rigid.json',d)
        r=self.service.call('cad_draft_joints',self.draft_args);self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')
        self.assertFalse((self.root/'outputs/drafts.json').exists())

    def test_changed_upstream_source_rejected(self):
        d=self.read('mates.json');d['data']['mates'][0]['type_name']='concentric';self.write('mates.json',d)
        r=self.service.call('cad_draft_joints',self.draft_args);self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_path_overwrite_and_invalid_parameters(self):
        self.assertEqual(self.service.call('cad_build_rigid_candidates',self.args)['errors'][0]['code'],'OUTPUT_EXISTS')
        for update in [{'output_path':'../outside.json'},{'max_partitions':0,'output_path':'outputs/bad.json'}]:
            self.assertEqual(self.service.call('cad_build_rigid_candidates',{**self.args,**update})['status'],'error')

    def test_heldout_negative_and_budget_recovery(self):
        held=self.service.call('cad_draft_joints',{**self.draft_args,'template_ids':['bar_clamp']})
        self.assertEqual(held['errors'][0]['code'],'HELDOUT_TEMPLATE')
        empty=self.service.call('cad_draft_joints',{**self.draft_args,'template_ids':['gear_meshing_kit']})
        self.assertEqual(empty['status'],'partial');self.assertEqual(empty['data']['summary']['returned_candidates'],0)
        limited=self.service.call('cad_draft_joints',{**self.draft_args,'output_path':'outputs/limited.json','max_states':1})
        self.assertIn('MATCH_SEARCH_LIMIT',[e['code'] for e in limited['errors']])
        self.assertEqual(self.service.call('cad_list_mechanism_templates',{})['status'],'ok')

    def test_cli_new_tools(self):
        for args in [['rigid-candidates','outputs/target.json','--output','outputs/cli-rigid.json'],
                     ['draft-joints','outputs/cli-rigid.json','--pattern-size','2','--template-ids','gas_lift_bar_stool','--output','outputs/cli-draft.json']]:
            r=subprocess.run([sys.executable,'-m','cadkin',*args],cwd=self.root,text=True,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertIn(json.loads(r.stdout)['status'],('ok','partial'))


if __name__=='__main__':unittest.main()
