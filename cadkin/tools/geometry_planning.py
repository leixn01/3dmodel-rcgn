"""Source-bound geometry gap plans, sharing the existing guarded batch executor."""
from cadkin.followup.geometry_planning import plan_geometry_tasks
from cadkin.followup.planning import READ_TOOLS
from cadkin.tools.chain_sources import require,check_fields
from cadkin.tools.comparison import replay_check
from cadkin.tools.files import json_path,read_json,replay_reads
from cadkin.tools.geometric_connections import replay_geometry_analysis
from cadkin.tools.matching import recheck
from cadkin.tools.observation_index import replay_index,unique_bindings


@replay_reads
def build_geometry_plan(root,draft_check_path,geometry_analysis_path,output_path,max_tasks=20,evidence_index_path=None,check_destinations=True):
    from jsonschema import Draft202012Validator
    from cadkin.tools.solidworks import CATALOG
    output=json_path(root,output_path,output=check_destinations)
    check,target,draft,_,cb=replay_check(root,draft_check_path)
    analysis,ab=replay_geometry_analysis(root,geometry_analysis_path)
    require(analysis['target_source']==draft['target_source'],'Geometry analysis and check use different targets.','EVIDENCE_MISMATCH')
    inherited=analysis['evidence_index_source']
    if inherited and evidence_index_path is None:evidence_index_path=inherited['path']
    index,ib=(None,None) if evidence_index_path is None else replay_index(root,evidence_index_path)
    # A newer index must first be incorporated into a new analysis; do not plan from stale missing-distance gaps.
    require(ib==inherited,'Reanalyze geometry with the latest index before planning; do not replace or bypass report history.','EVIDENCE_MISMATCH')
    if index:require(index['check_source']==cb,'Index belongs to another check.','EVIDENCE_MISMATCH')
    data=plan_geometry_tasks(target,check,analysis,index,output.parent/(output.stem+'-captures'),max_tasks)
    data.update(parameters={'draft_check_path':cb['path'],'geometry_analysis_path':ab['path'],'max_tasks':max_tasks},
        check_source=cb,geometry_analysis_source=ab,
        input_files=check['input_files']+analysis['input_files']+[cb,ab])
    if ib:
        data['parameters']['evidence_index_path']=ib['path'];data['evidence_index_source']=ib
        data['heldout_exposed'] |= index['heldout_exposed']
    data['input_files']=unique_bindings(root,data['input_files'])
    for task in data['tasks']:
        require(task['tool'] in READ_TOOLS and CATALOG[task['tool']]['annotations']['readOnlyHint'] and
            Draft202012Validator(CATALOG[task['tool']]['inputSchema']).is_valid(task['arguments']),
            'Invalid geometry evidence task.','INVALID_TASK_PLAN')
        json_path(root,task['save_envelope_path'],output=check_destinations)
    recheck(root,data['input_files'])
    return data,check,target


def replay_geometry_plan(root,path,original,digest):
    keys={'draft_check_path','geometry_analysis_path','max_tasks'}
    require(original.get('evidence_task_plan_schema_version')==1 and original.get('plan_kind')=='geometric_connection_gaps' and
        isinstance(original.get('parameters'),dict) and set(original['parameters']) in (keys,keys|{'evidence_index_path'}),
        'Use the original geometry evidence plan.','INVALID_TASK_PLAN')
    data,check,target=build_geometry_plan(root,output_path=str(path),check_destinations=False,**original['parameters'])
    check_fields(original,data)
    return data,check,target,{'path':str(path),'sha256':digest}
