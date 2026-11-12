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
from cadkin.followup.checks import check_draft
from cadkin.followup.planning import plan_tasks, READ_TOOLS
from cadkin.tools.solidworks import SolidWorksTools, CATALOG
from tests.followup_fakes import draft_fixture, write_draft_fixture
from tests.rigid_fakes import mate_signal


class CheckTests(unittest.TestCase):
    def setUp(self): self.target,self.rigid,self.draft=draft_fixture()
    def check(self,**kwargs):return check_draft(self.target,self.rigid,self.draft,**kwargs)
    def codes(self,result):return {f['code'] for f in result['findings']}

    def test_valid_structure_does_not_certify_mechanics(self):
        d=self.check();self.assertTrue(d['structural_checks_passed']);self.assertFalse(d['physical_consistency_verified'])
        self.assertIn('JOINT_PHYSICS_UNVERIFIED',self.codes(d));self.assertFalse(d['requires_human_review'])

    def test_duplicate_and_missing_members_are_structural_errors(self):
        group=self.rigid['partitions'][0]['groups'][0];group['member_occurrence_paths']+=['a']
        d=self.check();self.assertFalse(d['structural_checks_passed']);self.assertIn('PARTITION_MEMBERSHIP_INVALID',self.codes(d))

    def test_candidate_map_and_endpoint_errors(self):
        c=self.draft['partition_results'][0]['match']['candidates'][0]
        c['mapping'][0]['member_occurrence_paths']=['invented']
        c['joint_hypotheses'][0]['group_ids'][1]=c['joint_hypotheses'][0]['group_ids'][0]
        d=self.check();self.assertIn('CANDIDATE_MEMBERSHIP_INVALID',self.codes(d));self.assertIn('JOINT_ENDPOINT_INVALID',self.codes(d))

    def test_active_lock_vs_motion_is_conflict_not_solver_verdict(self):
        self.target['pairs'][0]['signals']=[mate_signal()]
        d=self.check();f=next(f for f in d['findings'] if f['code']=='ACTIVE_LOCK_VS_MOVING_HYPOTHESIS')
        self.assertEqual(f['severity'],'evidence_conflict');self.assertFalse(f['mechanically_verified']);self.assertTrue(f['candidate_refs'])

    def test_inactive_lock_does_not_create_motion_conflict(self):
        for pair in self.target['pairs']:
            pair['signals']=[mate_signal(active=False)]
        self.assertNotIn('ACTIVE_LOCK_VS_MOVING_HYPOTHESIS',self.codes(self.check()))

    def test_alternative_joint_types_are_uncertainty(self):
        d=self.check();items=[f for f in d['findings'] if f['code']=='JOINT_KIND_ALTERNATIVES']
        self.assertTrue(items);self.assertTrue(all(f['severity']=='uncertainty' for f in items))

    def test_source_conflicts_boundary_and_omitted_groups_retained(self):
        self.target['pairs'][0]['flags']=[{'code':'different-thresholds'}]
        self.target['errors']=[{'code':'partial'}];self.target['boundary_evidence']=[{'outside':'x'}]
        self.rigid['omitted_groups']=[{'reasons':['limit']}]
        self.assertTrue({'SOURCE_PAIR_FLAGS','SOURCE_INCOMPLETE','BOUNDARY_LINKS_OUTSIDE_SCOPE','GROUP_ALTERNATIVES_OMITTED'}<=self.codes(self.check()))

    def test_reference_axis_mismatch_is_separate_from_physical_conflict(self):
        c=self.draft['partition_results'][0]['match']['candidates'][0]
        c['axis_relation_checks'][0]['residual_deg']=40
        self.assertIn('REFERENCE_AXIS_RELATION_MISMATCH',self.codes(self.check()))

    def test_truncation_counts_full_findings_and_prioritizes_conflicts(self):
        self.target['pairs'][0]['flags']=[{'code':'conflict'}]
        d=self.check(max_findings=1);self.assertTrue(d['output_truncated'])
        self.assertGreater(d['summary']['findings_found'],1);self.assertEqual(d['findings'][0]['severity'],'evidence_conflict')

    def test_stable_ids_ignore_candidate_rank(self):
        a={f['id'] for f in self.check()['findings']}
        for r in self.draft['partition_results']:
            for c in r['match']['candidates']:c['rank']+=10
        self.assertEqual(a,{f['id'] for f in self.check()['findings']})

    def test_invalid_findings_budget(self):
        for value in [True,0,2001,float('nan')]:
            with self.assertRaises(ToolFailure):self.check(max_findings=value)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.target,self.rigid,self.draft=draft_fixture();self.check=check_draft(self.target,self.rigid,self.draft)
    def plan(self,**kwargs):return plan_tasks(self.target,self.check,{},Path('outputs/captures'),**kwargs)
    def issue(self,code,paths=None,pair_ids=None):
        return {'id':'f-'+code,'code':code,'occurrence_paths':paths or ['a','b'],'pair_ids':pair_ids or ['ab']}

    def test_catalog_valid_read_only_tasks_and_dag(self):
        from jsonschema import Draft202012Validator
        plan=self.plan();seen=set()
        for task in plan['tasks']:
            self.assertIn(task['tool'],READ_TOOLS);self.assertTrue(CATALOG[task['tool']]['annotations']['readOnlyHint'])
            self.assertTrue(Draft202012Validator(CATALOG[task['tool']]['inputSchema']).is_valid(task['arguments']))
            self.assertTrue(set(task['depends_on'])<=seen);seen.add(task['id']);self.assertFalse(task['executed'])
        self.assertFalse(plan['executed']);self.assertLessEqual(len(plan['tasks']),20)

    def test_guarded_budget_does_not_leave_orphan_observations(self):
        p=self.plan(max_tasks=3);self.assertEqual(p['summary']['planned_capture_tasks'],0)
        self.assertTrue(p['output_truncated']);self.assertLessEqual(len(p['tasks']),3)
        self.assertEqual([t['phase'] for t in p['tasks']],['preflight','postflight'])

    def test_dedup_preserves_reasons(self):
        issue=self.issue('RIGID_GROUP_UNVERIFIED',['a','b'])
        self.check['findings']=[issue,{**issue,'id':'second'}]
        p=self.plan();rows=[t for t in p['tasks'] if t['phase']=='capture']
        self.assertEqual(len(rows),2);self.assertTrue(all(len(t['finding_ids'])==2 for t in rows))

    def test_complete_empty_cylinder_evidence_is_not_recaptured(self):
        self.check['findings']=[self.issue('JOINT_DIRECTION_UNKNOWN')]
        facts={'cylinders':{'a':[{'path':'a.json','sha256':'a'*64}],'b':[{'path':'b.json','sha256':'b'*64}]}}
        p=plan_tasks(self.target,self.check,facts,Path('outputs/captures'))
        self.assertEqual(p['summary']['planned_capture_tasks'],0);self.assertEqual(len(p['reused_evidence']),2)
        self.assertTrue(p['unresolved_findings'])

    def test_missing_cylinders_requests_bounded_face_reference_capture(self):
        self.check['findings']=[self.issue('JOINT_DIRECTION_UNKNOWN')]
        p=self.plan();cs=[t for t in p['tasks'] if t['phase']=='capture']
        self.assertEqual(len(cs),2);self.assertTrue(all(t['arguments']['include_face_references'] for t in cs))

    def test_unknown_pair_requests_exact_distance_and_root_mates(self):
        self.check['findings']=[self.issue('JOINT_LINK_UNSUPPORTED')]
        p=self.plan();tools=[t['tool'] for t in p['tasks'] if t['phase']=='capture']
        self.assertIn('sw_component_distance',tools);self.assertIn('sw_mate_inventory',tools)

    def test_existing_distance_is_reused_even_when_separated(self):
        self.target['pairs'][0]['signals']=[{'kind':'distance_observation','measurement':{'source_errors':[],'measurement':{'distance_m':1}}}]
        self.check['findings']=[self.issue('JOINT_LINK_UNSUPPORTED')]
        p=self.plan();self.assertNotIn('sw_component_distance',[t['tool'] for t in p['tasks']])
        self.assertTrue(any(r['family']=='distance' for r in p['reused_evidence']))

    def test_face_catalog_does_not_invent_probe_ids_or_seeds(self):
        self.check['findings']=[self.issue('AXIS_LINES_AMBIGUOUS')]
        p=self.plan();self.assertNotIn('sw_probe_face_pair',[t['tool'] for t in p['tasks']])
        self.assertTrue(any(r['reason']=='FACE_PAIR_AND_SEEDS_NOT_YET_SELECTED' for r in p['unresolved_findings']))

    def test_unavailable_context_and_structural_error_prevent_capture(self):
        self.check['findings']=[self.issue('RIGID_GROUP_UNVERIFIED',['a'])];self.target['nodes'][0]['eligible']=False
        p=self.plan();self.assertEqual(p['summary']['planned_capture_tasks'],0)
        self.check['structural_checks_passed']=False
        self.assertEqual(self.plan()['unresolved_findings'][0]['reason'],'REGENERATE_INVALID_DERIVATION')

    def test_source_token_is_not_freshness_claim_and_context_is_preserved(self):
        p=self.plan();self.assertIn('Never replace tokens',p['execution_policy']['on_document_or_pose_mismatch'])
        self.assertTrue(all(t['arguments'].get('expected_document_token','a'*24)=='a'*24 for t in p['tasks']))
        self.assertTrue(any(t['expected_context'] for t in p['tasks'] if t['tool']=='sw_component_spatial'))

    def test_no_solver_substitution_or_unbounded_retry(self):
        self.check['findings']=[self.issue('JOINT_PHYSICS_UNVERIFIED')]
        p=self.plan();self.assertEqual(p['summary']['planned_capture_tasks'],0);self.assertTrue(p['unresolved_findings'])
        self.assertIn('No blind retries',p['execution_policy']['retry_policy'])

    def test_findings_truncation_and_invalid_task_budget(self):
        self.check['output_truncated']=True;self.assertTrue(self.plan()['check_output_truncated'])
        for value in [True,2,201]:
            with self.assertRaises(ToolFailure):self.plan(max_tasks=value)


@unittest.skipUnless(importlib.util.find_spec('pxr'),'Install .[templates]')
class FollowupToolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app=write_draft_fixture(self.root,lambda r:SolidWorksTools(r))
        def forbidden():raise AssertionError('Offline tools cannot connect CAD')
        self.service=SolidWorksTools(self.root,factory=forbidden)
        self.args={'joint_draft_path':'outputs/drafts.json','output_path':'outputs/check.json'}
        c=self.service.call('cad_check_joint_draft',self.args);self.assertEqual(c['status'],'partial',c)
        self.plan_args={'draft_check_path':'outputs/check.json','output_path':'outputs/plan.json'}
    def tearDown(self):self.service.close();self.temp.cleanup()
    def read(self,name):return json.loads((self.root/name).read_text(encoding='utf-8'))
    def write(self,name,data):(self.root/name).write_text(json.dumps(data),encoding='utf-8')

    def test_replay_provenance_readonly_schema_and_no_execution(self):
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        r=self.service.call('cad_plan_evidence_tasks',self.plan_args);self.assertEqual(r['status'],'ok',r)
        d=r['data'];self.assertFalse(d['executed']);self.assertTrue(d['check_source']['sha256'])
        self.assertTrue(all(not Path(t['save_envelope_path']).exists() for t in d['tasks']))
        self.assertEqual(before,{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before})

    def test_generated_calls_execute_on_same_explicit_fake_backend(self):
        from cadkin.adapters.solidworks import SolidWorksAdapter
        from tests.sw_fakes import runtime
        plan=self.service.call('cad_plan_evidence_tasks',self.plan_args)['data']
        live=SolidWorksTools(self.root,factory=lambda:SolidWorksAdapter(app=self.app,runtime=runtime()))
        seen=set()
        try:
            for task in plan['tasks']:
                self.assertTrue(set(task['depends_on'])<=seen)
                r=live.call(task['tool'],task['arguments']);self.assertEqual(r['status'],'ok',(task,r))
                if task['tool']=='sw_active_document':self.assertEqual(r['data'],task['expected_context'])
                if task['tool']=='sw_component_spatial':
                    actual=r['data']['component'];expected=task['expected_context']
                    self.assertEqual(actual['occurrence_path'],expected['id']);self.assertEqual(actual['transform']['to_root'],expected['to_root_column_vectors_m'])
                seen.add(task['id'])
        finally:live.close()
        self.assertFalse(self.app.ActiveDoc.GetSaveFlag())

    def test_draft_tampering_and_upstream_change_rejected(self):
        d=self.read('outputs/drafts.json');d['partition_results'][0]['match']['candidates'][0]['score']=1.123
        self.write('outputs/tampered.json',d)
        bad=self.service.call('cad_check_joint_draft',{**self.args,'joint_draft_path':'outputs/tampered.json','output_path':'outputs/bad.json'})
        self.assertEqual(bad['errors'][0]['code'],'EVIDENCE_MISMATCH')
        d=self.read('mates.json');d['data']['mates'][0]['type_name']='hinge';self.write('mates.json',d)
        bad=self.service.call('cad_plan_evidence_tasks',self.plan_args);self.assertEqual(bad['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_removed_findings_rejected(self):
        d=self.read('outputs/check.json');d['findings']=[];self.write('outputs/check.json',d)
        r=self.service.call('cad_plan_evidence_tasks',self.plan_args)
        self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH');self.assertFalse((self.root/'outputs/plan.json').exists())

    def test_paths_existing_capture_and_overwrite_protection(self):
        self.assertEqual(self.service.call('cad_check_joint_draft',self.args)['errors'][0]['code'],'OUTPUT_EXISTS')
        bad=self.service.call('cad_plan_evidence_tasks',{**self.plan_args,'output_path':'../outside.json'})
        self.assertEqual(bad['errors'][0]['code'],'INVALID_PATH')
        capture=self.root/'outputs/plan-captures/document-before.json';capture.parent.mkdir();capture.write_text('{}')
        self.assertEqual(self.service.call('cad_plan_evidence_tasks',self.plan_args)['errors'][0]['code'],'OUTPUT_EXISTS')

    def test_limited_check_propagates_to_plan_and_error_recovery(self):
        c=self.service.call('cad_check_joint_draft',{**self.args,'output_path':'outputs/small-check.json','max_findings':1})
        self.assertIn('DRAFT_CHECK_LIMIT',[e['code'] for e in c['errors']])
        p=self.service.call('cad_plan_evidence_tasks',{**self.plan_args,'draft_check_path':'outputs/small-check.json'})
        self.assertEqual(p['status'],'partial');self.assertTrue(p['data']['check_output_truncated'])
        self.assertEqual(self.service.call('cad_list_mechanism_templates',{})['status'],'ok')

    def test_task_budget_is_partial_and_dag_complete(self):
        p=self.service.call('cad_plan_evidence_tasks',{**self.plan_args,'max_tasks':3})
        self.assertEqual(p['status'],'partial');self.assertEqual(p['data']['summary']['planned_capture_tasks'],0)
        self.assertTrue(p['data']['deferred_tasks'])

    def test_cli_two_new_tools(self):
        for args in [['check-joints','outputs/drafts.json','--output','outputs/cli-check.json'],
                     ['plan-evidence','outputs/cli-check.json','--output','outputs/cli-plan.json']]:
            r=subprocess.run([sys.executable,'-m','cadkin',*args],cwd=self.root,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertIn(json.loads(r.stdout)['status'],('ok','partial'))


if __name__=='__main__':unittest.main()
