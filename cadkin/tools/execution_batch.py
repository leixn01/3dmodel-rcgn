"""Bounded serial orchestration of existing guarded steps, with compact handoff and timing."""
import json
import time
from pathlib import Path

from cadkin.errors import success, failure, ToolFailure
from cadkin.tools.chain_sources import require
from cadkin.tools.files import json_path,read_json
from cadkin.tools.execution import execute_task,replay_execution
from cadkin.geometry import numbers


def execute_batch(root,call,plan_path,output_path,previous_execution_path=None,max_steps=12,time_budget_seconds=30,*,plan_cache,clock=time.perf_counter):
    numbers([time_budget_seconds],1,'INVALID_ARGUMENTS')
    require(type(max_steps) is int and 1<=max_steps<=20 and 1<=time_budget_seconds<=60,'Use 1–20 steps and 1–60 seconds.','INVALID_ARGUMENTS')
    started=clock();output=json_path(root,output_path,output=True)
    plan,_,_,binding=loaded=plan_cache.load(root,plan_path)
    require(plan.get('continuation',{}).get('action')!='stop','This plan explicitly stops.','NO_CAPTURE_TASKS')
    require(str(output) not in {t['save_envelope_path'] for t in plan['tasks']},'Batch report cannot replace a capture.','INVALID_PATH')
    previous=None;latest=None
    if previous_execution_path is not None:
        latest,_,_,_,previous=replay_execution(root,previous_execution_path,loaded)
        require(not latest['execution_complete'],'This execution is already complete.','EXECUTION_COMPLETE')
    steps=output.parent/(output.stem+'-steps')
    require(not steps.exists(),'Choose a new batch report/directory.','OUTPUT_EXISTS')
    output.parent.mkdir(parents=True,exist_ok=True)
    reports=[];timings=[];errors=[];reason='step_budget';fatal_error=False
    def timed_call(name,args):
        began=clock()
        try:return call(name,args)
        finally:timings.append({'tool':name,'elapsed_seconds':max(0.,clock()-began)})
    try:
        # Reserve report and step namespace before any CAD call. Interrupted paths stay occupied.
        with output.open('x',encoding='utf-8') as stream:
            steps.mkdir(exist_ok=False)
            for number in range(max_steps):
                if number and clock()-started>=time_budget_seconds:reason='time_budget';break
                step_path=steps/f'step-{number+1:03d}.json';before=len(timings);step_started=clock()
                try:
                    result=execute_task(root,timed_call,plan_path,str(step_path),
                        previous['path'] if previous else None,plan_cache=plan_cache)
                except Exception as exc:
                    errors.extend(failure(exc)['errors']);reason='step_error';fatal_error=True;break
                latest=result['data'];_,digest=read_json(step_path);previous={'path':str(step_path),'sha256':digest}
                reports.append({'source':previous,'elapsed_seconds':max(0.,clock()-step_started),'cad_tool_calls':len(timings)-before})
                errors.extend(result['errors'])
                if latest['execution_complete']:
                    fatal_error=any(r['fatal'] for r in latest['records'])
                    reason='fatal_observation' if fatal_error else 'execution_complete'
                    break
            elapsed=max(0.,clock()-started)
            summary={k:latest[k] for k in ('execution_complete','guards_passed','eligible_capture_ids','next_task_id','summary')} if latest else {
                'execution_complete':False,'guards_passed':False,'eligible_capture_ids':[],'next_task_id':plan['tasks'][0]['id'] if plan['tasks'] else None,'summary':None}
            can_continue=not fatal_error and not summary['execution_complete']
            data={'evidence_batch_schema_version':1,'algorithm_version':1,'plan_source':binding,
                'parameters':{'plan_path':binding['path'],'previous_execution_path':previous_execution_path,'max_steps':max_steps,'time_budget_seconds':time_budget_seconds},
                'execution_source':previous,'step_receipts':reports,**summary,'stop_reason':reason,
                'continuation':{'action':'continue' if can_continue else 'blocked' if fatal_error else 'complete','previous_execution_path':previous['path'] if can_continue and previous else None},
                'performance':{'elapsed_seconds':elapsed,'tool_elapsed_seconds':sum(t['elapsed_seconds'] for t in timings),
                    'orchestration_elapsed_seconds':max(0.,elapsed-sum(t['elapsed_seconds'] for t in timings)),
                    'steps_this_batch':len(reports),'cad_tool_calls_this_batch':len(timings),'client_tool_round_trips':1,'tool_timings':timings},
                'errors':errors,'observation_error_codes':sorted({c for r in latest['records'] for c in r['codes']}) if latest else [],
                'solidworks_modified':False,'requires_human_review':False,
                'limitations':['Time budget is checked between steps; an in-flight COM operation is never cancelled or retried to meet it.',
                    'Timing includes shared-tool validation, STA wait and adapter/COM work; it excludes agent thinking, transport and UI rendering.',
                    'Batching reduces client round trips, not required CAD calls or guards. Saved receipts/envelopes retain original semantics.',
                    'Only the latest execution_source is an execution receipt; this batch report is not reintegration input.',
                    'A partial prefix is not eligible evidence. Continue the same plan and previous receipt until guards complete.']}
            json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    except FileExistsError as exc:raise ToolFailure('OUTPUT_EXISTS','A batch path is occupied; inspect prior results before any retry.') from exc
    _,digest=read_json(output)
    compact={k:data[k] for k in ('execution_source','execution_complete','guards_passed','eligible_capture_ids','next_task_id','summary','stop_reason','continuation','observation_error_codes','solidworks_modified','requires_human_review')}
    compact.update(batch_report_source={'path':str(output),'sha256':digest},detail_saved=True,
        performance={k:v for k,v in data['performance'].items() if k!='tool_timings'})
    # Every detailed error remains on disk; do not repeat one accumulated warning per step in context.
    unique=[]
    for e in errors:
        if e not in unique:unique.append(e)
    return success(compact,unique)
