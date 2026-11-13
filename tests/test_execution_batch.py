import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from cadkin.errors import ToolFailure,failure
from cadkin.tools.execution import replay_execution
from cadkin.tools.execution_batch import execute_batch
from tests.constraint_fakes import write_constraint_followup_fixture
from tests.execution_fakes import live_service


class ExecutionBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app,self.mates,_=write_constraint_followup_fixture(self.root)
        self.service=live_service(self.root,self.app)
        self.args={'plan_path':'outputs/plan.json','output_path':'outputs/batch.json','time_budget_seconds':60}
    def tearDown(self):self.service.close();self.temp.cleanup()
    def call(self,**args):return self.service.call('sw_execute_evidence_batch',{**self.args,**args})
    def test_one_round_trip_keeps_nine_calls_and_reintegration(self):
        originals={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        r=self.call();self.assertEqual(r['status'],'ok',r);d=r['data']
        self.assertEqual(d['performance']['cad_tool_calls_this_batch'],9);self.assertTrue(d['execution_complete']);self.assertTrue(d['guards_passed'])
        self.assertNotIn('records',d);self.assertEqual(d['performance']['client_tool_round_trips'],1)
        receipt,_,_,_,binding=replay_execution(self.root,d['execution_source']['path']);self.assertEqual(binding,d['execution_source'])
        self.assertEqual(len(receipt['records']),9)
        updated=self.service.call('cad_reintegrate_evidence',{'execution_path':binding['path'],'output_path':'outputs/updated.json'})
        self.assertEqual(updated['status'],'ok',updated)
        analysis=json.loads(Path(updated['data']['after_constraint_analysis_source']['path']).read_text());self.assertEqual(analysis['rounds_completed'],1)
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in originals.items()))
    def test_step_budget_continues_exact_prefix_and_never_repeats(self):
        first=self.call(max_steps=3)['data'];self.assertFalse(first['execution_complete']);self.assertFalse(first['guards_passed']);self.assertEqual(first['eligible_capture_ids'],[])
        second=self.call(output_path='outputs/second.json',previous_execution_path=first['execution_source']['path'])['data']
        self.assertEqual(second['performance']['cad_tool_calls_this_batch'],6);self.assertTrue(second['guards_passed'])
        final=replay_execution(self.root,second['execution_source']['path'])[0];self.assertEqual(final['summary']['calls_executed'],9)
        r=self.call(output_path='outputs/again.json',previous_execution_path=second['execution_source']['path']);self.assertEqual(r['errors'][0]['code'],'EXECUTION_COMPLETE')
    def test_soft_time_budget_stops_between_steps(self):
        ticks=iter(range(0,200,2))
        r=execute_batch(self.root,self.service.call,clock=lambda:next(ticks),plan_cache=self.service.plan_cache,**{**self.args,'time_budget_seconds':1})
        self.assertEqual(r['data']['stop_reason'],'time_budget');self.assertEqual(r['data']['performance']['cad_tool_calls_this_batch'],1)
        self.assertEqual(r['data']['continuation']['action'],'continue')
    def test_partial_capture_retains_postguards_and_attempt_history(self):
        self.mates[0].GetDefinition=lambda:None
        r=self.call();self.assertEqual(r['status'],'partial');d=r['data'];self.assertTrue(d['guards_passed']);self.assertEqual(d['eligible_capture_ids'],[])
        receipt=replay_execution(self.root,d['execution_source']['path'])[0];self.assertEqual(receipt['summary']['partial'],1);self.assertEqual(receipt['summary']['calls_executed'],9)
    def test_timeout_halts_and_saves_prefix_without_retry(self):
        with patch.object(self.service.worker,'call',return_value=failure(ToolFailure('TIMEOUT','test'))) as worker:
            r=self.call();self.assertEqual(worker.call_count,1)
        d=r['data'];self.assertTrue(d['execution_complete']);self.assertFalse(d['guards_passed'])
        self.assertEqual(d['performance']['cad_tool_calls_this_batch'],1);self.assertEqual(d['summary']['skipped'],8)
    def test_cancellation_marker_prevents_further_cad_work(self):
        original=self.service.worker.call;seen=[]
        def cancel_after_first(name,args):
            seen.append(name)
            result=original(name,args)
            if len(seen)==1:self.service.worker.mark_uncertain()
            return result
        with patch.object(self.service.worker,'call',side_effect=cancel_after_first):r=self.call()
        self.assertEqual(len(seen),2)  # Second dispatch is refused by STA before queuing COM.
        d=r['data'];self.assertEqual(d['continuation']['action'],'blocked')
        self.assertIn('OUTCOME_UNKNOWN',d['observation_error_codes']);self.assertFalse(d['guards_passed'])
        self.assertEqual(d['summary']['skipped'],7)

    def test_occupied_and_changed_source_refuse_before_cad(self):
        first=self.call(max_steps=1)['data']
        with patch.object(self.service.worker,'call') as worker:
            r=self.call();self.assertEqual(r['errors'][0]['code'],'OUTPUT_EXISTS')
            with (self.root/'outputs/plan.json').open('a') as stream:stream.write('\n')
            r=self.call(output_path='outputs/changed.json',previous_execution_path=first['execution_source']['path'])
            self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH');worker.assert_not_called()
    def test_operation_gate_blocks_interleaving_and_recovers(self):
        entered=threading.Event();release=threading.Event();out=[];original=self.service.worker.call
        def blocked(name,args):
            entered.set();release.wait(10);return original(name,args)
        with patch.object(self.service.worker,'call',side_effect=blocked):
            thread=threading.Thread(target=lambda:out.append(self.call(max_steps=1)));thread.start()
            try:
                self.assertTrue(entered.wait(10))
                self.assertEqual(self.service.call('sw_active_document')['errors'][0]['code'],'BUSY')
            finally:release.set();thread.join(15)
        self.assertFalse(thread.is_alive());self.assertEqual(out[0]['status'],'ok')
        self.assertEqual(self.service.call('sw_active_document')['status'],'ok')
    def test_invalid_budgets_and_stopped_plan(self):
        for args in ({'max_steps':0},{'max_steps':21},{'time_budget_seconds':float('nan')},{'time_budget_seconds':61}):
            self.assertEqual(self.call(**args)['errors'][0]['code'],'INVALID_ARGUMENTS')
        base=self.root/'stopped';app,_,_=write_constraint_followup_fixture(base,'no_mates');service=live_service(base,app)
        try:
            r=service.call('sw_execute_evidence_batch',self.args);self.assertEqual(r['errors'][0]['code'],'NO_CAPTURE_TASKS')
            self.assertFalse((base/'outputs/batch.json').exists())
        finally:service.close()


if __name__=='__main__':unittest.main()
