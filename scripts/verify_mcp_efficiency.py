"""Compare real MCP round trips and payloads; synthetic CAD, no assumed agent latency."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


async def run(root,destination):
    from anyio import fail_after
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from cadkin.tools.execution import replay_execution
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False);results={};checks=[]
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    for mode in ('single','batch'):
        base=dest/mode;server=StdioServerParameters(command=sys.executable,args=['-m','tests.constraint_followup_mcp_fixture','--root',str(base)])
        responses=[];arguments=[];previous=None;wire_bytes=0;began=None
        with fail_after(240):
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize();began=time.perf_counter()
                    for i in range(20):
                        args={'plan_path':'outputs/plan.json','output_path':f'outputs/{mode}-{i:02d}.json'}
                        if previous:args['previous_execution_path']=previous
                        if mode=='batch':args.update(max_steps=12,time_budget_seconds=60)
                        response=await session.call_tool('sw_execute_evidence_task' if mode=='single' else 'sw_execute_evidence_batch',args)
                        assert not response.isError,response
                        wire_bytes+=len(response.model_dump_json().encode('utf-8'));result=response.structuredContent
                        arguments.append(args);responses.append(result);data=result['data']
                        previous=data['output_path'] if mode=='single' else data['execution_source']['path']
                        if data['execution_complete']:break
                    elapsed=time.perf_counter()-began
        receipt,_,_,_,binding=replay_execution(base,previous)
        check(mode+' completed guards',receipt['execution_complete'] and receipt['guards_passed'])
        check(mode+' nine required calls retained',receipt['summary']['calls_executed']==9)
        check(mode+' one capture eligible',len(receipt['eligible_capture_ids'])==1)
        envelope_contents=[]
        for record in receipt['records']:
            envelope=json.loads(Path(record['envelope_source']['path']).read_text(encoding='utf-8'))
            envelope_contents.append(envelope)
        (base/'protocol-responses.json').write_text(json.dumps({'arguments':arguments,'responses':responses},ensure_ascii=False,indent=2),encoding='utf-8')
        results[mode]={'round_trips':len(responses),'mcp_result_bytes':wire_bytes,'elapsed_seconds':elapsed,'execution_source':binding,
            'summary':receipt['summary'],'record_states':[(r['task_id'],r['state'],r['codes'],r['fatal']) for r in receipt['records']],
            'envelopes':envelope_contents}
    # Root paths differ between fixtures; source identities remain within their own immutable lineage.
    def normalized(value,base):
        def omit_timestamp(item):
            if isinstance(item,dict):return {k:omit_timestamp(v) for k,v in item.items() if k!='captured_at_utc'}
            if isinstance(item,list):return [omit_timestamp(v) for v in item]
            return item
        return json.dumps(omit_timestamp(value),sort_keys=True,ensure_ascii=False).replace(str(base).replace('\\','\\\\'),'<ROOT>')
    check('same state and guard semantics',results['single']['summary']==results['batch']['summary'] and results['single']['record_states']==results['batch']['record_states'])
    check('same CAD content except independent timestamps/root paths',normalized(results['single']['envelopes'],dest/'single')==normalized(results['batch']['envelopes'],dest/'batch'))
    check('round trips reduced',results['single']['round_trips']==9 and results['batch']['round_trips']<9)
    check('returned payload reduced',results['batch']['mcp_result_bytes']<results['single']['mcp_result_bytes']*.5)
    for r in results.values():r.pop('envelopes');r.pop('record_states')
    report={'version':'0.25.0','passed':all(c['passed'] for c in checks),'checks':checks,'comparison':results,
        'payload_reduction_fraction':1-results['batch']['mcp_result_bytes']/results['single']['mcp_result_bytes'],
        'scope':'Real SDK/stdio with explicit synthetic CAD. Measured duration excludes server startup and includes local protocol calls. No real CAD/agent thinking speedup claimed.'}
    (dest/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':report['passed'],'checks':len(checks),'comparison':results,'payload_reduction_fraction':report['payload_reduction_fraction'],'report':str(dest/'report.json')}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();r=asyncio.run(run(Path.cwd(),args.output));print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['passed'] else 1)
