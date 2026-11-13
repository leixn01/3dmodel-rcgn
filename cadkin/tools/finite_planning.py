"""Missing face-boundary plans; existing guards, batch receipts and history are reused."""
from cadkin.followup import stable_id
from cadkin.followup.planning import assemble_plan, READ_TOOLS
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.comparison import replay_check
from cadkin.tools.face_boundaries import selection
from cadkin.tools.files import json_path, read_json, replay_reads
from cadkin.tools.finite_connections import replay_finite_analysis
from cadkin.tools.matching import recheck
from cadkin.tools.observation_index import replay_index, unique_bindings


@replay_reads
def build_finite_plan(root,draft_check_path,finite_analysis_path,output_path,max_tasks=20,evidence_index_path=None,check_destinations=True):
    from cadkin.tools.solidworks import CATALOG
    from jsonschema import Draft202012Validator
    output=json_path(root,output_path,output=check_destinations)
    check,target,draft,_,cb=replay_check(root,draft_check_path)
    report,rb=replay_finite_analysis(root,finite_analysis_path)
    require(report['target_source']==draft['target_source'],'Finite report and check target differ.','EVIDENCE_MISMATCH')
    inherited=report['evidence_index_source']
    if inherited and evidence_index_path is None:evidence_index_path=inherited['path']
    index,ib=(None,None) if evidence_index_path is None else replay_index(root,evidence_index_path)
    require(ib==inherited and (not index or index['check_source']==cb),
        'Reanalyze finite geometry with the latest same-check index before planning.','EVIDENCE_MISMATCH')
    rounds=0 if index is None else index['rounds_completed'];nodes={n['id']:n for n in target['nodes']}
    requests={};blocked={};reused={};expected={}
    for pair in report['pairs']:
        for i,source in enumerate(pair['face_sources']):
            key=pair['face_keys'][i];path=source['target']['occurrence_path']
            if pair['boundary_sources'][i] or pair['attempts'][i]:
                reused[key]={'face_key':key,'sources':pair['boundary_sources'][i],'attempts':pair['attempts'][i],
                    'reason':'PRIOR_BOUNDARY_ATTEMPT_NO_AUTOMATIC_RETRY'};continue
            reason=('INVALID_DERIVATION' if not check['structural_checks_passed'] else 'ROUND_LIMIT' if rounds>=4 else
                'SOURCE_CONTEXT_UNAVAILABLE' if not nodes[path]['eligible'] or nodes[path].get('source_errors') or
                not nodes[path].get('to_root_column_vectors_m') else None)
            if reason:blocked[key]={'face_key':key,'occurrence_paths':[path],'reason':reason};continue
            args={'expected_document_token':target['document']['document_token'],'face':selection(source),'max_edges':64}
            task_id=stable_id('capture-',['sw_read_face_boundary',args])
            requests[task_id]={'id':task_id,'tool':'sw_read_face_boundary','arguments':args,'occurrence_paths':[path],
                'finding_ids':[pair['id']],'priority':20,'integration':'index_then_analyze_finite_connections'}
            expected[task_id]=source
    data=assemble_plan(target,check,{'_indexed':True,'rounds_completed':rounds},output.parent/(output.stem+'-captures'),
        max_tasks,requests,reused,list(report['gaps']),blocked)
    allowed=READ_TOOLS|{'sw_read_face_boundary'}
    data.update(algorithm_version=7,plan_kind='finite_face_boundaries',finite_analysis_source=rb,
        check_source=cb,parameters={'draft_check_path':cb['path'],'finite_analysis_path':rb['path'],'max_tasks':max_tasks},
        input_files=unique_bindings(root,check['input_files']+report['input_files']+[cb,rb]))
    data['execution_policy']['tool_scope']=sorted(allowed)
    data['finite_coverage']=report['coverage']
    data['output_truncated'] |= bool(report['coverage']['omitted_face_pairs'] or report['coverage']['catalog_faces_omitted'] or
        report['inherited_geometry_coverage']['omitted_pairs'] or report['inherited_geometry_coverage']['pairs_with_observation_limits'])
    if ib:
        data['evidence_index_source']=ib;data['parameters']['evidence_index_path']=ib['path']
        data['heldout_exposed'] |= index['heldout_exposed']
    for task in data['tasks']:
        if task['id'] in expected:task['expected_boundary_source']=expected[task['id']]
        require(task['tool'] in allowed and CATALOG[task['tool']]['annotations']['readOnlyHint'] and
            Draft202012Validator(CATALOG[task['tool']]['inputSchema']).is_valid(task['arguments']),
            'Invalid boundary capture task.','INVALID_TASK_PLAN')
        json_path(root,task['save_envelope_path'],output=check_destinations)
    data['recompute_handoffs']=[{'next_tools':['cad_index_evidence','cad_analyze_finite_connections'],
        'note':'Index the complete guarded receipt with the same check, then analyze the original geometry report with that latest index. Keep all previous attempts and the shared four rounds.'}]
    data['limitations'].append('Boundaries are acquired only for explicit source-bound cylindrical face candidates, once per face. Complete or unsuccessful attempts are never automatically repeated. Extents are not motion limits.')
    recheck(root,data['input_files']);return data,check,target


def replay_finite_plan(root,path,raw,digest):
    keys={'draft_check_path','finite_analysis_path','max_tasks'}
    require(raw.get('evidence_task_plan_schema_version')==1 and raw.get('plan_kind')=='finite_face_boundaries' and
        isinstance(raw.get('parameters'),dict) and set(raw['parameters']) in (keys,keys|{'evidence_index_path'}),
        'Use an original finite boundary plan.','INVALID_TASK_PLAN')
    data,check,target=build_finite_plan(root,output_path=str(path),check_destinations=False,**raw['parameters'])
    check_fields(raw,data);return data,check,target,{'path':str(path),'sha256':digest}
