"""One read-only call per invocation, immutable receipts and raw envelope capture."""
import json
from pathlib import Path

from cadkin.errors import success, failure, ToolFailure
from cadkin.tools.files import json_path, read_json
from cadkin.tools.followup import replay_plan
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.matching import recheck
from cadkin.followup.execution import assess, skip_reason, execution_state


def record_data(plan_binding, plan, records, previous=None):
    return {'evidence_execution_schema_version':1,'algorithm_version':1,
            'plan_source':plan_binding,'previous_execution_source':previous,'records':records,
            **execution_state(plan,records),'solidworks_modified':False,'requires_human_review':False,
            'snapshot_atomic':False,'mechanically_verified':False,
            'limitations':['One existing read-only CAD tool per invocation; no automatic start/open/rebuild, retry or budget escalation.',
                'Pre/post context checks do not prove unchanged full geometry or atomic capture. Keep the assembly unchanged.',
                'Partial/failed captures are retained but not automatically reintegrated; all guards must pass.',
                'Hashes validate file consistency, not source authorship or proof that a file came from real SolidWorks.']}


def replay_execution(root, execution_path, loaded_plan=None):
    path = json_path(root,execution_path); raw,digest = read_json(path)
    require(isinstance(raw,dict) and raw.get('evidence_execution_schema_version')==1 and raw.get('algorithm_version')==1 and
            isinstance(raw.get('plan_source'),dict) and isinstance(raw.get('records'),list),
            'Use an original execution receipt.','INVALID_EXECUTION')
    plan,check,target,pb = loaded_plan or replay_plan(root,raw['plan_source'].get('path',''))
    require(raw['plan_source']==pb,'Execution plan binding changed.','EVIDENCE_MISMATCH')
    require(1<=len(raw['records'])<=len(plan['tasks']),'Invalid execution prefix.','INVALID_EXECUTION')
    records, bindings, total = [],[],0
    for row,task in zip(raw['records'],plan['tasks']):
        require(isinstance(row,dict) and row.get('task_id')==task['id'],'Execution order differs.','EVIDENCE_MISMATCH')
        reason = skip_reason(task,records)
        if reason:
            expected={'task_id':task['id'],'state':'skipped','reason':reason,'codes':[],'fatal':False,'envelope_source':None}
        else:
            binding=row.get('envelope_source')
            require(isinstance(binding,dict) and binding.get('path')==task['save_envelope_path'],'Wrong task envelope path.','EVIDENCE_MISMATCH')
            file=json_path(root,binding['path']);total+=file.stat().st_size
            require(total<=128*1024*1024,'Execution sources exceed 128 MiB.','EXECUTION_SOURCE_LIMIT')
            envelope,sha=read_json(file);require(sha==binding.get('sha256'),'Execution observation changed.','EVIDENCE_MISMATCH')
            state,codes,fatal=assess(task,envelope,plan['document'])
            expected={'task_id':task['id'],'state':state,'reason':None,'codes':codes,'fatal':fatal,'envelope_source':binding}
            bindings.append(binding)
        require(row==expected,'Execution state differs from original envelopes.','EVIDENCE_MISMATCH');records.append(expected)
    previous=raw.get('previous_execution_source')
    if previous is not None:
        require(isinstance(previous,dict),'Invalid previous receipt.','INVALID_EXECUTION')
        old,sha=read_json(json_path(root,previous.get('path','')))
        require(sha==previous.get('sha256') and isinstance(old,dict) and old.get('plan_source')==pb and
                isinstance(old.get('records'),list) and 0<len(old['records'])<len(records) and
                records[:len(old['records'])]==old['records'],'Previous receipt prefix changed.','EVIDENCE_MISMATCH')
        bindings.append(previous)
    expected=record_data(pb,plan,records,previous);check_fields(raw,expected)
    recheck(root,plan['input_files']+[pb]+bindings)
    return expected,plan,check,target,{'path':str(path),'sha256':digest}


def execute_task(root, call, plan_path, output_path, previous_execution_path=None, *, plan_cache=None):
    output=json_path(root,output_path,output=True)
    loaded=plan_cache.load(root,plan_path) if plan_cache is not None else replay_plan(root,plan_path)
    plan,check,target,pb=loaded
    require(plan.get('continuation', {}).get('action') != 'stop',
            'This plan explicitly stops; no CAD calls are scheduled.', 'NO_CAPTURE_TASKS')
    previous=None;records=[]
    if previous_execution_path is not None:
        old,_,_,_,previous=replay_execution(root,previous_execution_path,loaded)
        records=list(old['records'])
    require(len(records)<len(plan['tasks']),'This execution is already complete.','EXECUTION_COMPLETE')
    # Reserve all paths before COM; crashes leave occupied files, never an invitation to blindly retry.
    task=plan['tasks'][len(records)]
    while task and skip_reason(task,records):
        records.append({'task_id':task['id'],'state':'skipped','reason':skip_reason(task,records),'codes':[], 'fatal':False,'envelope_source':None})
        task=plan['tasks'][len(records)] if len(records)<len(plan['tasks']) else None
    envelope_path=json_path(root,task['save_envelope_path'],output=True) if task else None
    require(envelope_path!=output,'Receipt and capture paths must differ.','INVALID_PATH')
    output.parent.mkdir(parents=True,exist_ok=True)
    try:
        with output.open('x',encoding='utf-8') as receipt:
            if task:
                envelope_path.parent.mkdir(parents=True,exist_ok=True)
                with envelope_path.open('x',encoding='utf-8') as capture:
                    try: envelope=call(task['tool'],task['arguments'])
                    except Exception as exc: envelope=failure(exc)
                    json.dump(envelope,capture,ensure_ascii=False,indent=2,allow_nan=False);capture.write('\n')
                _,sha=read_json(envelope_path)
                state,codes,fatal=assess(task,envelope,plan['document'])
                records.append({'task_id':task['id'],'state':state,'reason':None,'codes':codes,'fatal':fatal,
                                'envelope_source':{'path':str(envelope_path),'sha256':sha}})
            # Materialize blocked successors without queuing another API call.
            while len(records)<len(plan['tasks']):
                next_task=plan['tasks'][len(records)];reason=skip_reason(next_task,records)
                if not reason: break
                records.append({'task_id':next_task['id'],'state':'skipped','reason':reason,'codes':[], 'fatal':False,'envelope_source':None})
            data=record_data(pb,plan,records,previous)
            json.dump(data,receipt,ensure_ascii=False,indent=2,allow_nan=False);receipt.write('\n')
    except FileExistsError as exc:
        raise ToolFailure('OUTPUT_EXISTS','A receipt/capture path is occupied. Inspect the prior result; do not blindly retry.') from exc
    errors=[]
    if any(r['state']!='passed' for r in records):errors.append({'code':'EXECUTION_INCOMPLETE_EVIDENCE','message':'Retain partial, failed or skipped observations; collection does not certify mechanics.'})
    return success({'output_path':str(output),**data},errors)


def run_plan(service, plan_path, output_path):
    """CLI orchestrator: bounded calls to the same single-step tool, no hidden CAD backend."""
    output=json_path(service.root,output_path,output=True)
    plan,_,_,_=replay_plan(service.root,plan_path)
    require(plan.get('continuation', {}).get('action') != 'stop',
            'This plan explicitly stops; retain remaining risks.', 'NO_CAPTURE_TASKS')
    require(str(output) not in {t['save_envelope_path'] for t in plan['tasks']},'Receipt cannot replace a planned capture.','INVALID_PATH')
    steps=output.parent/(output.stem+'-steps')
    require(not steps.exists(),'Choose a new execution directory.','OUTPUT_EXISTS')
    steps.mkdir(parents=True,exist_ok=False)
    previous=None;result=None
    for index in range(len(plan['tasks'])):
        arguments={'plan_path':plan_path,'output_path':str(steps/f'step-{index+1:03d}.json')}
        if previous is not None:arguments['previous_execution_path']=previous
        result=service.call('sw_execute_evidence_task',arguments)
        if result['status']=='error':return result
        previous=result['data']['output_path']
        if result['data']['execution_complete']:break
    require(result is not None and result['data']['execution_complete'],'Execution budget exhausted.','EXECUTION_LIMIT')
    raw,_=read_json(Path(previous))
    from cadkin.tools.proximity import write_result
    write_result(output,raw)
    return success({'output_path':str(output),**raw},result['errors'])
