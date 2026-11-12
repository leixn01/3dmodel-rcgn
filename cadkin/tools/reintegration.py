"""Recompute existing evidence derivations with guarded captures; retain older versions."""
from pathlib import Path

from cadkin.errors import success, failure, ToolFailure
from cadkin.tools.files import json_path, read_json
from cadkin.tools.proximity import write_result
from cadkin.tools.chain_sources import require
from cadkin.tools.execution import replay_execution
from cadkin.tools.rigid import replay_draft, rigid_candidates, joint_drafts
from cadkin.tools.relations import component_relations
from cadkin.tools.connections import connection_review
from cadkin.tools.proximity_review import proximity_review
from cadkin.tools.chain import chain_dossier
from cadkin.tools.matching import build_target_graph, recheck
from cadkin.tools.followup import check_joint_draft
from cadkin.tools.face_contacts import face_contact_review
from cadkin.tools.face_reintegration import route_face_captures
from cadkin.tools.observation_index import unique_bindings


def reintegrate(root, execution_path, output_path, face_review_path=None):
    output=json_path(root,output_path,output=True)
    execution,plan,check,target,eb=replay_execution(root,execution_path)
    require(execution['execution_complete'],'Finish all planned guards and tasks first.','EXECUTION_NOT_COMPLETE')
    require(execution['guards_passed'],'Failed/missing guards prohibit evidence reintegration.','EXECUTION_GUARDS_FAILED')
    draft,rigid,_,_=replay_draft(root,check['draft_source']['path'])
    chain,_=read_json(json_path(root,target['source_chain']['path']))
    folder=output.parent/(output.stem+'-derived')
    require(not folder.exists(),'Choose a new derived-output directory.','OUTPUT_EXISTS')
    tasks={t['id']:t for t in plan['tasks']}
    captures={};excluded=[]
    for record in execution['records']:
        task=tasks[record['task_id']]
        if task['phase']!='capture':continue
        if record['task_id'] not in execution['eligible_capture_ids']:
            excluded.append({'task_id':task['id'],'reason':'PARTIAL_FAILED_OR_SKIPPED','state':record['state']});continue
        raw,_=read_json(json_path(root,record['envelope_source']['path']))
        captures[task['id']]={'tool':task['tool'],'data':raw['data'],'source':record['envelope_source']}
    cylinders={c['data']['occurrence_path']:(i,c['source']['path']) for i,c in captures.items() if c['tool']=='sw_component_cylinders'}
    mates=[(i,c['source']['path']) for i,c in captures.items() if c['tool']=='sw_mate_inventory']
    distances={tuple(sorted(t['occurrence_path'] for t in c['data']['targets'])):(i,c['source']['path']) for i,c in captures.items() if c['tool']=='sw_component_distance'}
    require(len(mates)<=1,'Plan contains multiple root mate snapshots.','INVALID_EXECUTION')
    routed = route_face_captures(root, chain, target, captures, face_review_path)
    face_jobs = {j['source']['path']: j for j in routed['jobs'] if j['existing']}
    face_reasons = {e['task_id']: e['reason'] for e in routed['entries']}
    reused = set(routed['reused_capture_ids']); face_updates = []
    steps=[];used=set();superseded=[];relation_map={};evidence=[];final_check=None;pipeline_error=None
    folder.mkdir(parents=True,exist_ok=False)

    def run(name,handler,arguments):
        result=handler(root,**arguments)
        steps.append({'tool':name,'arguments':arguments,'status':result['status'],'errors':result['errors'],
                      'output_source':binding(arguments['output_path'])})
        return arguments['output_path']
    def binding(path):
        p=json_path(root,str(path));_,sha=read_json(p);return {'path':str(p),'sha256':sha}
    def dest(name):return str(folder/(name+'.json'))
    def update_faces(job, index):
        new = run('cad_review_face_contacts', face_contact_review, {'probe_paths': job['probe_paths'],
            'output_path': dest(f'faces-{index:02d}'), **job['parameters']})
        used.update(job['capture_ids'])
        face_updates.append({'basis_source': job['source'], 'output_source': binding(new),
            'basis_kind': 'existing_chain_review' if job['existing'] else 'provided_review_for_uncovered_pairs',
            'parameters': job['parameters'], 'capture_ids': job['capture_ids'],
            'retained_previous_probes': len(job['probe_paths']) - len(job['capture_ids']),
            'added_probes': len(job['capture_ids'])})
        return new

    try:
        for index,source in enumerate(target['relation_sources']):
            old,_=read_json(json_path(root,source['path']))
            paths={s['occurrence_path']:s['source_path'] for s in old['sources']}
            changed=False
            for occurrence,(task_id,path) in cylinders.items():
                if occurrence in paths:superseded.append({'task_id':task_id,'old_path':paths[occurrence],'new_path':path,'family':'cylinders'})
                paths[occurrence]=path;used.add(task_id);changed=True
            if changed:
                require(2<=len(paths)<=32,'Updated cylinder set exceeds existing relation limits; keep captures for a smaller explicit scope.','REINTEGRATION_SCOPE_LIMIT')
                new=run('cad_component_relations',component_relations,{
                    'inventory_path':chain['parameters']['inventory_path'],'cylinder_paths':[paths[p] for p in sorted(paths)],
                    'output_path':dest(f'relations-{index:02d}'),'grouping_path':old.get('grouping_source',{}).get('path') if old.get('grouping_source') else None,
                    **old['parameters']})
            else:new=source['path']
            relation_map[source['path']]=new
        for index,source in enumerate(chain['sources']):
            old,_=read_json(json_path(root,source['path']));new=source['path']
            if source['kind']=='connection':
                original_relation=old['sources']['relations']['path']
                relation=relation_map.get(original_relation,original_relation)
                mate=mates[0][1] if mates else old['sources']['mates']['path']
                if relation!=original_relation or mates:
                    new=run('cad_review_connections',connection_review,{'relations_path':relation,'mate_inventory_path':mate,'output_path':dest(f'connections-{index:02d}')})
                    if mates:
                        used.add(mates[0][0]);superseded.append({'task_id':mates[0][0],'old_path':old['sources']['mates']['path'],'new_path':mate,'family':'root_mates'})
            elif source['kind']=='component_proximity' and distances:
                work,_=read_json(json_path(root,old['sources']['proximity']['path']))
                allowed={tuple(sorted(p['occurrence_paths'])) for p in work['candidates']}
                paths={tuple(sorted(s['occurrence_paths'])):s['path'] for s in old['distance_sources']}
                changed=False
                for pair,(task_id,path) in distances.items():
                    if pair not in allowed:continue
                    if pair in paths:superseded.append({'task_id':task_id,'old_path':paths[pair],'new_path':path,'family':'distance'})
                    paths[pair]=path;used.add(task_id);changed=True
                if changed:
                    require(len(paths)<=200,'Distance set exceeds existing review limit.','REINTEGRATION_SCOPE_LIMIT')
                    new=run('cad_review_proximity',proximity_review,{'proximity_path':old['sources']['proximity']['path'],
                        'distance_paths':[paths[p] for p in sorted(paths)],'contact_tolerance_mm':old['contact_tolerance_mm'],
                        'output_path':dest(f'proximity-{index:02d}')})
            elif source['kind']=='face_contact' and source['path'] in face_jobs:
                new = update_faces(face_jobs[source['path']], index)
            evidence.append(new)
        for job in routed['jobs']:
            if not job['existing']: evidence.append(update_faces(job, len(evidence)))
        new_chain=run('cad_build_chain_evidence',chain_dossier,{**chain['parameters'],'evidence_paths':evidence,'output_path':dest('chain')})
        new_target=run('cad_build_target_graph',build_target_graph,{'chain_path':new_chain,
            'relation_paths':sorted(set(relation_map.values())),'output_path':dest('target')})
        new_rigid=run('cad_build_rigid_candidates',rigid_candidates,{**rigid['parameters'],'target_graph_path':new_target,'output_path':dest('rigid')})
        new_draft=run('cad_draft_joints',joint_drafts,{'rigid_candidates_path':new_rigid,
            'template_ids':[s['id'] for s in draft['template_sources']],'include_heldout':draft['heldout_exposed'],
            **draft['parameters'],'output_path':dest('joints')})
        final_check=run('cad_check_joint_draft',check_joint_draft,{'joint_draft_path':new_draft,
            'max_findings':check['parameters']['max_findings'],'output_path':dest('check')})
        recheck(root,plan['input_files']+[plan['check_source'],execution['plan_source'],eb]+[c['source'] for c in captures.values()]+routed['input_files'])
    except Exception as exc:
        pipeline_error=failure(exc)['errors'][0]
        final_check=None
    supplemental=[]
    for task_id,capture in captures.items():
        if task_id not in used and task_id not in reused:
            reason={'sw_component_constraints':'CONSTRAINTS_CONTEXT_ONLY','sw_component_faces':'FACE_CATALOG_REQUIRES_PAIR_SELECTION_AND_PROBING',
                    'sw_component_distance':'NO_MATCHING_BOUND_WORKLIST','sw_component_cylinders':'NO_EXISTING_RELATION_BASIS',
                    'sw_mate_inventory':'NO_EXISTING_CONNECTION_BASIS',
                    'sw_probe_face_pair':face_reasons.get(task_id, 'NO_MATCHING_FACE_REVIEW')}[capture['tool']]
            supplemental.append({'task_id':task_id,'tool':capture['tool'],'source':capture['source'],'reason':reason})
    inputs = unique_bindings(root, plan['input_files'] + [execution['plan_source'], eb] + routed['input_files'] +
        [r['envelope_source'] for r in execution['records'] if r['envelope_source']] +
        ([execution['previous_execution_source']] if execution['previous_execution_source'] else []))
    data={'evidence_reintegration_schema_version':1,'algorithm_version':2,'execution_source':eb,
          'before_check_source':plan['check_source'],'after_check_source':binding(final_check) if final_check else None,
          'recomputation_complete':final_check is not None,'applied_capture_ids':sorted(used) if final_check else [],
          'attempted_capture_ids':sorted(used),'supplemental_captures':supplemental,'excluded_captures':excluded,
          'reused_capture_ids': sorted(reused), 'face_routing': routed['entries'], 'face_updates': face_updates,
          'supplied_face_review_source': routed['supplied_review_source'], 'input_files': inputs,
          'superseded_sources':superseded,'steps':steps,'pipeline_error':pipeline_error,
          'deferred_plan_tasks':plan['deferred_tasks'],'check_output_truncated':plan['check_output_truncated'],
          'remaining_findings_summary':read_json(json_path(root,final_check))[0]['summary'] if final_check else None,
          'heldout_exposed':check['heldout_exposed'],'requires_human_review':False,'solidworks_modified':False,
          'mechanically_verified':False,'snapshot_atomic':False,
          'limitations':['Only complete captures under passed guards enter existing compatible derivations. Partial and failed results remain diagnostic.',
              'Original thresholds, inventory, grouping options, template set and search budgets are preserved; raw originals are never edited.',
              'Cylinders/root mates/component distances require existing compatible relation/review bases; no thresholds or face pairs are invented.',
              'Face probes retain existing review thresholds for covered component pairs; an explicit replayed face review can supply thresholds only for uncovered pairs and its matching guarded probes. Existing probe rows are never replaced silently.',
              'Face thresholds with multiple interpretations, already-observed face snapshots and capacity limits remain supplemental. Local near points still do not confirm contact or joints.',
              'Constraints and face catalogs remain supplemental; they do not directly establish joints or resolve findings. Use cad_index_evidence to associate guarded observations and pass its index to subsequent planning; this report alone is not an index.',
              'Completed recomputation is not physical confirmation. Compare before/after checks separately; disappeared findings do not prove resolution.']}
    write_result(output,data)
    errors=[]
    if pipeline_error:errors.append({'code':'REINTEGRATION_FAILED','message':'Derived files before failure remain diagnostic; no final draft is accepted.','cause':pipeline_error})
    if any(step['status']=='partial' for step in steps):errors.append({'code':'DERIVATION_REMAINS_PARTIAL','message':'Recomputed sources/candidates retain errors, conflicts or limited coverage; inspect the resulting check.'})
    if plan['deferred_tasks'] or plan['check_output_truncated']:errors.append({'code':'PLAN_SCOPE_INCOMPLETE','message':'Original deferred tasks or omitted findings remain outside this execution.'})
    if supplemental or excluded:errors.append({'code':'CAPTURES_NOT_INTEGRATED','message':'Some captures remain supplemental or diagnostic; see reasons.'})
    return success({'output_path':str(output),**data},errors)
