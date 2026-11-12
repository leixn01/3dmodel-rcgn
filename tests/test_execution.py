import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from cadkin.errors import ToolFailure, failure
from cadkin.followup.execution import document_matches, pose_matches, assess
from cadkin.tools.execution import execute_task, run_plan, replay_execution
from cadkin.tools.solidworks import SolidWorksTools
from tests.execution_fakes import write_execution_fixture, live_service
from tests.sw_fakes import pose


@unittest.skipUnless(importlib.util.find_spec('pxr'),'Install .[templates]')
class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app=write_execution_fixture(self.root);self.live=live_service(self.root,self.app)
        self.plan=self.read('outputs/plan.json')
    def tearDown(self):self.live.close();self.temp.cleanup()
    def read(self,path):return json.loads((self.root/path).read_text(encoding='utf-8'))
    def write(self,path,data):(self.root/path).write_text(json.dumps(data),encoding='utf-8')
    def step(self,previous=None,index=1,call=None):
        args={'plan_path':'outputs/plan.json','output_path':f'outputs/step-{index}.json'}
        if previous:args['previous_execution_path']=previous
        return execute_task(self.root,call or self.live.call,**args)
    def full(self):return run_plan(self.live,'outputs/plan.json','outputs/run.json')
    def replay(self,path='outputs/run.json'):return replay_execution(self.root,path)[0]

    def test_one_invocation_executes_one_existing_readonly_call(self):
        call=Mock(wraps=self.live.call);r=self.step(call=call)
        self.assertEqual(call.call_count,1);self.assertEqual(call.call_args.args[0],'sw_active_document')
        self.assertEqual(r['data']['summary']['calls_executed'],1);self.assertFalse(r['data']['execution_complete'])
        self.assertTrue(Path(r['data']['records'][0]['envelope_source']['path']).exists())

    def test_full_plan_guards_raw_envelopes_and_no_cad_mutation(self):
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        r=self.full();self.assertEqual(r['status'],'ok',r);d=self.replay()
        self.assertTrue(d['execution_complete']);self.assertTrue(d['guards_passed']);self.assertEqual(len(d['eligible_capture_ids']),3)
        self.assertEqual(d['summary']['calls_executed'],len(self.plan['tasks']));self.assertFalse(self.app.ActiveDoc.dirty)
        self.assertEqual(before,{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before})

    def test_replaying_a_consumed_prefix_does_not_repeat_com(self):
        self.step();call=Mock(wraps=self.live.call)
        with self.assertRaises(ToolFailure) as error:self.step(index=2,call=call)
        self.assertEqual(error.exception.code,'OUTPUT_EXISTS');call.assert_not_called()

    def test_terminal_receipt_rejects_another_execution(self):
        self.full();call=Mock(wraps=self.live.call)
        with self.assertRaises(ToolFailure) as error:self.step('outputs/run.json',2,call)
        self.assertEqual(error.exception.code,'EXECUTION_COMPLETE');call.assert_not_called()

    def test_changed_document_dirty_stops_capture_and_blocks_reintegration(self):
        self.app.ActiveDoc.dirty=True;r=self.full()
        self.assertEqual(r['status'],'partial');self.assertEqual(r['data']['summary']['calls_executed'],1)
        self.assertFalse(r['data']['guards_passed']);self.assertTrue(r['data']['execution_complete'])
        offline=SolidWorksTools(self.root)
        try:
            result=offline.call('cad_reintegrate_evidence',{'execution_path':'outputs/run.json','output_path':'outputs/updated.json'})
            self.assertEqual(result['errors'][0]['code'],'EXECUTION_GUARDS_FAILED')
        finally:offline.close()

    def test_pose_change_before_capture_stops_remaining_calls(self):
        self.step();self.app.ActiveDoc.root.children[0].Transform2=pose(x=3)
        r=self.step('outputs/step-1.json',2)
        self.assertFalse(r['data']['guards_passed']);self.assertTrue(r['data']['execution_complete'])
        self.assertEqual(r['data']['summary']['calls_executed'],2)

    def test_postflight_pose_change_quarantines_successful_captures(self):
        original=self.live.call;capture_count=sum(t['phase']=='capture' for t in self.plan['tasks']);seen=0
        def call(name,args=None):
            nonlocal seen
            r=original(name,args)
            if name in ('sw_component_constraints','sw_component_faces'):
                seen+=1
                if seen==capture_count:self.app.ActiveDoc.root.children[0].Transform2=pose(x=2)
            return r
        self.live.call=call;r=self.full();self.assertFalse(r['data']['guards_passed'])
        self.assertEqual(r['data']['eligible_capture_ids'],[])

    def test_nonfatal_capture_failure_retained_and_other_captures_continue(self):
        original=self.live.call
        def call(name,args=None):
            if name=='sw_component_constraints' and args['occurrence_path']=='base-1':return failure(ToolFailure('API_ERROR','synthetic read failure'))
            return original(name,args)
        self.live.call=call;r=self.full();d=self.replay()
        self.assertTrue(d['guards_passed']);self.assertEqual(d['summary']['failed'],1);self.assertEqual(len(d['eligible_capture_ids']),2)
        self.assertEqual(r['status'],'partial')

    def test_timeout_stops_all_later_calls_without_retry(self):
        original=self.live.call;attempts=[]
        def call(name,args=None):
            if name=='sw_component_constraints':attempts.append(name);return failure(ToolFailure('TIMEOUT','synthetic timeout'))
            return original(name,args)
        self.live.call=call;r=self.full();d=self.replay()
        self.assertEqual(len(attempts),1);self.assertFalse(d['guards_passed']);self.assertTrue(d['execution_complete'])
        self.assertGreater(d['summary']['skipped'],0)

    def test_partial_capture_saved_but_not_eligible(self):
        original=self.live.call
        def call(name,args=None):
            r=original(name,args)
            if name=='sw_component_faces':
                r['status']='partial';r['errors']=[{'code':'FACE_LIMIT'}];r['data']['complete']=False;r['data']['truncated']=True
            return r
        self.live.call=call;self.full();d=self.replay()
        self.assertTrue(d['guards_passed']);self.assertEqual(d['summary']['partial'],1);self.assertEqual(len(d['eligible_capture_ids']),2)

    def test_missing_document_fields_fail_closed(self):
        doc=self.plan['document'];self.assertTrue(document_matches(doc,doc))
        for field in ('document_token','path','configuration','document_type','dirty'):
            modified=dict(doc);modified.pop(field);self.assertFalse(document_matches(modified,doc))

    def test_bbox_error_does_not_hide_valid_pose(self):
        task=next(t for t in self.plan['tasks'] if t['tool']=='sw_component_spatial')
        raw=self.live.call(task['tool'],task['arguments']);raw['status']='partial';raw['errors']=[{'code':'BBOX_UNAVAILABLE'}]
        raw['data']['component']['bounding_box']=None
        self.assertEqual(assess(task,raw,self.plan['document'])[0],'passed')
        raw['data']['component']['transform']=None
        self.assertEqual(assess(task,raw,self.plan['document'])[0],'failed')

    def test_plan_tamper_rejected_before_com(self):
        p=self.plan;p['tasks'][0]['tool']='sw_rebuild';self.write('outputs/plan.json',p);call=Mock()
        with self.assertRaises(ToolFailure):self.step(call=call)
        call.assert_not_called();self.assertFalse((self.root/'outputs/step-1.json').exists())

    def test_forged_receipt_state_and_observation_hash_rejected(self):
        self.full();raw=self.read('outputs/run.json');raw['guards_passed']=False;self.write('outputs/forged.json',raw)
        with self.assertRaises(ToolFailure):self.replay('outputs/forged.json')
        raw=self.read('outputs/run.json');path=Path(raw['records'][0]['envelope_source']['path']);data=json.loads(path.read_text());data['data']['dirty']=True;path.write_text(json.dumps(data))
        with self.assertRaises(ToolFailure):self.replay()

    def test_receipt_output_cannot_replace_planned_capture(self):
        call=Mock()
        with self.assertRaises(ToolFailure) as error:
            execute_task(self.root,call,'outputs/plan.json',self.plan['tasks'][0]['save_envelope_path'])
        self.assertEqual(error.exception.code,'INVALID_PATH');call.assert_not_called()

    def test_source_changed_between_steps_is_rejected(self):
        self.step();data=self.read('mates.json');data['data']['mate_count']=200;self.write('mates.json',data);call=Mock()
        with self.assertRaises(ToolFailure):self.step('outputs/step-1.json',2,call)
        call.assert_not_called()


@unittest.skipUnless(importlib.util.find_spec('pxr'),'Install .[templates]')
class ReintegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app=write_execution_fixture(self.root,degraded=True);self.live=live_service(self.root,self.app)
        run_plan(self.live,'outputs/plan.json','outputs/run.json')
        self.offline=SolidWorksTools(self.root,factory=lambda:(_ for _ in ()).throw(AssertionError('Offline must not connect')))
    def tearDown(self):self.live.close();self.offline.close();self.temp.cleanup()
    def read(self,path):return json.loads((self.root/path).read_text(encoding='utf-8'))
    def update(self,path='outputs/updated.json'):
        return self.offline.call('cad_reintegrate_evidence',{'execution_path':'outputs/run.json','output_path':path})
    def compare(self,after,output='outputs/compared.json'):
        return self.offline.call('cad_compare_draft_checks',{'before_check_path':'outputs/check.json','after_check_path':after,'output_path':output})

    def test_supported_capture_recomputes_dependencies_and_preserves_originals(self):
        paths=list(self.root.rglob('*.json'));before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        r=self.update();self.assertNotEqual(r['status'],'error',r);d=r['data']
        self.assertTrue(d['recomputation_complete']);self.assertGreaterEqual(len(d['applied_capture_ids']),3)
        self.assertTrue(d['superseded_sources']);self.assertTrue(d['supplemental_captures'])
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
        self.assertTrue(any(s['tool']=='cad_component_relations' for s in d['steps']))
        self.assertTrue(any(s['tool']=='cad_review_connections' for s in d['steps']))

    def test_thresholds_templates_and_search_budgets_preserved(self):
        d=self.update()['data'];original=self.read('outputs/drafts.json')
        after=self.read(Path(d['after_check_source']['path']).parent/'joints.json')
        self.assertEqual(original['parameters'],after['parameters']);self.assertEqual(original['template_sources'],after['template_sources'])
        old=self.read('outputs/relations.json');new=self.read('outputs/updated-derived/relations-00.json')
        self.assertEqual(old['parameters'],new['parameters'])

    def test_comparison_reports_changes_without_resolving_physics(self):
        d=self.update()['data'];r=self.compare(d['after_check_source']['path']);self.assertEqual(r['status'],'ok',r)
        c=r['data'];self.assertTrue(c['settings_equal']);self.assertTrue(c['occurrence_scope_equal'])
        self.assertFalse(c['resolved_findings_asserted']);self.assertFalse(c['mechanically_verified'])
        self.assertTrue(c['findings']['no_longer_observed_ids'] or c['findings']['changed_ids'])
        self.assertTrue(c['findings']['still_observed_ids'])

    def test_tampered_execution_blocks_recompute(self):
        data=self.read('outputs/run.json');data['eligible_capture_ids']=[];(self.root/'outputs/run.json').write_text(json.dumps(data))
        r=self.update();self.assertEqual(r['status'],'error');self.assertFalse((self.root/'outputs/updated-derived').exists())

    def test_incomplete_execution_rejected(self):
        r=self.offline.call('cad_reintegrate_evidence',{'execution_path':'outputs/run-steps/step-001.json','output_path':'outputs/updated.json'})
        self.assertEqual(r['errors'][0]['code'],'EXECUTION_NOT_COMPLETE')

    def test_occupied_destinations_refused(self):
        self.update();r=self.update();self.assertEqual(r['errors'][0]['code'],'OUTPUT_EXISTS')
        (self.root/'outputs/new-derived').mkdir();self.assertEqual(self.update('outputs/new.json')['errors'][0]['code'],'OUTPUT_EXISTS')

    def test_tampered_new_check_rejected_and_service_recovers(self):
        d=self.update()['data'];p=Path(d['after_check_source']['path']);raw=json.loads(p.read_text());raw['findings']=[];p.write_text(json.dumps(raw))
        r=self.compare(str(p));self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH')
        self.assertEqual(self.offline.call('cad_list_mechanism_templates',{})['status'],'ok')

    def test_truncated_comparison_keeps_unobserved_as_unknown(self):
        self.offline.call('cad_check_joint_draft',{'joint_draft_path':'outputs/drafts.json','max_findings':1,'output_path':'outputs/limited.json'})
        r=self.compare('outputs/limited.json');self.assertEqual(r['status'],'partial')
        self.assertIn('COMPARISON_SCOPE_CHANGED',[e['code'] for e in r['errors']])
        self.assertIn('COMPARISON_FINDINGS_LIMIT',[e['code'] for e in r['errors']])
        self.assertTrue(r['data']['findings']['no_longer_observed_ids']);self.assertFalse(r['data']['resolved_findings_asserted'])

    def test_recompute_failure_retains_diagnostics_and_no_applied_claim(self):
        from unittest.mock import patch
        with patch('cadkin.tools.reintegration.component_relations',side_effect=ToolFailure('SYNTHETIC_FAILURE','test')):
            r=self.update()
        self.assertEqual(r['status'],'partial');self.assertFalse(r['data']['recomputation_complete'])
        self.assertIsNone(r['data']['after_check_source']);self.assertEqual(r['data']['applied_capture_ids'],[])
        self.assertEqual(r['data']['pipeline_error']['code'],'SYNTHETIC_FAILURE')

    def test_distance_router_uses_existing_bound_worklist_and_tolerance(self):
        # Isolate the router after its separately tested replay boundary. This is not a planner scenario.
        from unittest.mock import patch
        from cadkin.tools.proximity import write_result
        loaded=list(replay_execution(self.root,'outputs/run.json'))
        execution,plan,check,target,binding=copy.deepcopy(loaded)
        args={'expected_document_token':plan['document']['document_token'],'left_occurrence_path':'base-1','right_occurrence_path':'rail-1'}
        observation=self.live.call('sw_component_distance',args);path=self.root/'outputs/extra-distance.json';write_result(path,observation)
        task_id='isolated-distance-router'
        plan['tasks'].append({'id':task_id,'phase':'capture','tool':'sw_component_distance'})
        execution['records'].append({'task_id':task_id,'state':'passed','envelope_source':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}})
        execution['eligible_capture_ids'].append(task_id)
        with patch('cadkin.tools.reintegration.replay_execution',return_value=(execution,plan,check,target,binding)):
            r=self.update()
        self.assertTrue(r['data']['recomputation_complete'],r);self.assertIn(task_id,r['data']['applied_capture_ids'])
        step=next(s for s in r['data']['steps'] if s['tool']=='cad_review_proximity')
        new=self.read(step['output_source']['path']);old=self.read('outputs/proximity-review.json')
        self.assertEqual(new['contact_tolerance_mm'],old['contact_tolerance_mm'])
        self.assertIn(str(path),[s['path'] for s in new['distance_sources']])

    def test_unlisted_distance_is_left_unintegrated(self):
        # A genuine measured pair is not automatically added outside the original bounded worklist.
        from cadkin.tools.proximity_review import review_proximity
        from cadkin.tools.proximity import proximity_candidates
        inventory=self.read('inventory.json');sha=hashlib.sha256((self.root/'inventory.json').read_bytes()).hexdigest()
        work=proximity_candidates(inventory,sha,0,occurrence_paths=['base-1','carriage-1'])
        raw=self.read('distance2.json')
        with self.assertRaises(ToolFailure) as error:review_proximity(work,inventory,sha,[(raw,'distance2.json','x')],.1)
        self.assertEqual(error.exception.code,'DISTANCE_OUTSIDE_SCOPE')

    def test_cli_offline_reintegration_and_comparison(self):
        package=str(Path(__file__).resolve().parents[1]);import os
        env={**os.environ,'PYTHONPATH':package+os.pathsep+os.environ.get('PYTHONPATH','')}
        p=subprocess.run([sys.executable,'-m','cadkin','reintegrate-evidence','outputs/run.json','--output','outputs/updated.json'],cwd=self.root,env=env,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        q=subprocess.run([sys.executable,'-m','cadkin','compare-checks','outputs/check.json','outputs/updated-derived/check.json','--output','outputs/compare.json'],cwd=self.root,env=env,capture_output=True,text=True)
        self.assertEqual(q.returncode,0,q.stderr+q.stdout)


if __name__=='__main__':unittest.main()
