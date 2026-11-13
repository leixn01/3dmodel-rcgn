"""Bounded inspection plans reusing immutable history and the shared round limit."""
from cadkin.followup import stable_id
from cadkin.followup.planning import assemble_plan,READ_TOOLS
from cadkin.tools.chain_sources import require,check_fields
from cadkin.tools.comparison import replay_check
from cadkin.tools.engagement import replay_engagement,CAPTURES
from cadkin.tools.files import json_path,replay_reads
from cadkin.tools.matching import recheck
from cadkin.tools.observation_index import replay_index,unique_bindings


@replay_reads
def build_engagement_plan(root,draft_check_path,engagement_analysis_path,output_path,max_tasks=20,evidence_index_path=None,check_destinations=True):
    from cadkin.tools.solidworks import CATALOG
    from jsonschema import Draft202012Validator
    output=json_path(root,output_path,output=check_destinations)
    check,target,draft,_,cb=replay_check(root,draft_check_path)
    report,rb=replay_engagement(root,engagement_analysis_path)
    require(report['target_source']==draft['target_source'],'Inspection and check target differ.','EVIDENCE_MISMATCH')
    inherited=report['evidence_index_source']
    if inherited and evidence_index_path is None:evidence_index_path=inherited['path']
    index,ib=(None,None) if evidence_index_path is None else replay_index(root,evidence_index_path)
    require(ib==inherited and (not index or index['check_source']==cb),
        'Reanalyze engagement with the latest same-check index before planning.','EVIDENCE_MISMATCH')
    rounds=0 if index is None else index['rounds_completed'];nodes={n['id']:n for n in target['nodes']}
    requests={};blocked={};reused={};expected={};unresolved=list(report['gaps'])
    for face in report['faces']:
        key=face['face_key'];source=face['source'];path=source['target']['occurrence_path']
        for tool in CAPTURES:
            request_key=stable_id('inspection-',[key,tool])
            if face['attempts'][tool]:
                reused[request_key]={'face_key':key,'tool':tool,'sources':face['observations'][tool],
                    'attempts':face['attempts'][tool],'reason':'PRIOR_INSPECTION_ATTEMPT_NO_AUTOMATIC_RETRY'};continue
            if len(face['boundary_sources'])!=1:
                unresolved.append({'face_key':key,'tool':tool,'reason':'UNIQUE_COMPLETE_BOUNDARY_REQUIRED',
                    'next_tool':'cad_analyze_finite_connections'});continue
            if tool=='sw_sample_cylinder_face' and not face['query_points_root_mm']:
                unresolved.append({'face_key':key,'tool':tool,'reason':'POSITIVE_COMMON_AXIAL_INTERVAL_REQUIRED'});continue
            reason=('INVALID_DERIVATION' if not check['structural_checks_passed'] else 'ROUND_LIMIT' if rounds>=4 else
                'SOURCE_CONTEXT_UNAVAILABLE' if not nodes[path]['eligible'] or nodes[path].get('source_errors') or
                not nodes[path].get('to_root_column_vectors_m') else None)
            if reason:blocked[request_key]={'face_key':key,'tool':tool,'occurrence_paths':[path],'reason':reason};continue
            args={'expected_document_token':target['document']['document_token'],'boundary_path':face['boundary_sources'][0]['path']}
            if tool=='sw_sample_cylinder_face':args.update(query_points_root_mm=face['query_points_root_mm'],
                membership_tolerance_mm=report['capture_parameters']['membership_tolerance_mm'])
            else:args['max_edges']=report['capture_parameters']['max_edges']
            task_id=stable_id('capture-',[tool,args])
            requests[task_id]={'id':task_id,'tool':tool,'arguments':args,'occurrence_paths':[path],
                'finding_ids':[p['id'] for p in report['pairs'] if key in p['face_keys']],
                'priority':20,'integration':'index_then_analyze_surface_engagement'}
            expected[task_id]=(source,face['boundary_sources'][0])
    data=assemble_plan(target,check,{'_indexed':True,'rounds_completed':rounds},output.parent/(output.stem+'-captures'),
        max_tasks,requests,reused,unresolved,blocked)
    allowed=READ_TOOLS|set(CAPTURES)
    data.update(algorithm_version=8,plan_kind='surface_engagement',engagement_analysis_source=rb,check_source=cb,
        parameters={'draft_check_path':cb['path'],'engagement_analysis_path':rb['path'],'max_tasks':max_tasks},
        input_files=unique_bindings(root,check['input_files']+report['input_files']+[cb,rb]),engagement_coverage=report['coverage'])
    data['execution_policy']['tool_scope']=sorted(allowed)
    data['output_truncated'] |= bool(report['coverage']['queries_omitted'] or report['coverage']['adjacent_plane_candidates_omitted'] or
        report['inherited_finite_coverage']['omitted_face_pairs'] or report['inherited_finite_coverage']['catalog_faces_omitted'] or
        report['inherited_geometry_coverage']['omitted_pairs'] or report['inherited_geometry_coverage']['pairs_with_observation_limits'])
    if ib:
        data['evidence_index_source']=ib;data['parameters']['evidence_index_path']=ib['path'];data['heldout_exposed'] |= index['heldout_exposed']
    for task in data['tasks']:
        if task['id'] in expected:task['expected_inspection_source'],task['expected_boundary_binding']=expected[task['id']]
        require(task['tool'] in allowed and CATALOG[task['tool']]['annotations']['readOnlyHint'] and
            Draft202012Validator(CATALOG[task['tool']]['inputSchema']).is_valid(task['arguments']),
            'Invalid inspection capture task.','INVALID_TASK_PLAN')
        json_path(root,task['save_envelope_path'],output=check_destinations)
    data['recompute_handoffs']=[{'next_tools':['cad_index_evidence','cad_analyze_surface_engagement'],
        'finite_analysis_path':report['finite_analysis_source']['path'],
        'note':'Index the complete guarded receipt with the same check, then analyze this original finite report using that latest index. Never reset the shared four rounds.'}]
    data['limitations'].append('Each face/tool is attempted once; changing queries, tolerances or budgets never retries it. Point membership and shared edges do not establish a joint, full angular coverage, fit or travel limits.')
    recheck(root,data['input_files']);return data,check,target


def replay_engagement_plan(root,path,raw,digest):
    keys={'draft_check_path','engagement_analysis_path','max_tasks'}
    require(raw.get('evidence_task_plan_schema_version')==1 and raw.get('plan_kind')=='surface_engagement' and
        isinstance(raw.get('parameters'),dict) and set(raw['parameters']) in (keys,keys|{'evidence_index_path'}),
        'Use an original engagement plan.','INVALID_TASK_PLAN')
    data,check,target=build_engagement_plan(root,output_path=str(path),check_destinations=False,**raw['parameters'])
    check_fields(raw,data);return data,check,target,{'path':str(path),'sha256':digest}
