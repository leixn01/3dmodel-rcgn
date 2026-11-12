"""Apply explicit human declarations to an exact chain dossier; never verify CAD by assertion."""
from datetime import datetime, timezone

from cadkin.errors import success, ToolFailure
from cadkin.tools.chain import build_chain
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.files import json_path, read_json
from cadkin.tools.proximity import write_result


def apply_chain_review(root, chain_path, review_path, output_path):
    output = json_path(root,output_path,output=True)
    path = json_path(root,chain_path); source,digest=read_json(path)
    require(isinstance(source,dict) and source.get('chain_dossier_schema_version')==1 and source.get('algorithm_version')==1 and
            isinstance(source.get('parameters'),dict), 'Use a base chain dossier, not a previously reviewed result.')
    require(set(source['parameters'])=={'inventory_path','occurrence_paths','chain_name','evidence_paths','grouping_path','grouping_review_path'}, 'Invalid dossier parameters.')
    expected = build_chain(root,**source['parameters'])
    check_fields(source,expected)
    review_file = json_path(root,review_path); review,review_sha=read_json(review_file)
    require(isinstance(review,dict) and review.get('chain_review_input_schema_version')==1 and
            isinstance(review.get('chain_sha256'),str) and review['chain_sha256'].lower()==digest and
            isinstance(review.get('decisions'),list) and len(review['decisions'])<=len(source['pairs']), 'Review must bind to this exact dossier SHA256.', 'INVALID_CHAIN_REVIEW')
    reviewer=review.get('reviewer');when=review.get('reviewed_at')
    require(isinstance(reviewer,str) and 1<=len(reviewer.strip())<=200 and isinstance(when,str), 'Record a named reviewer and timezone-aware timestamp.', 'INVALID_CHAIN_REVIEW')
    try:
        timestamp=datetime.fromisoformat(when.replace('Z','+00:00'))
        require(timestamp.tzinfo is not None and timestamp.utcoffset() is not None,'Review time needs timezone.','INVALID_CHAIN_REVIEW')
    except ValueError as exc:
        raise ToolFailure('INVALID_CHAIN_REVIEW', 'Invalid reviewed_at ISO timestamp.') from exc
    pairs={p['pair_id']:p for p in expected['pairs']};decisions={}
    for item in review['decisions']:
        require(isinstance(item,dict),'Invalid review decision.','INVALID_CHAIN_REVIEW')
        pid=item.get('pair_id');decision=item.get('decision');relation=item.get('relation_type');reason=item.get('reason');ids=item.get('evidence_ids')
        require(isinstance(pid,str) and pid in pairs and pid not in decisions and decision in ('confirmed','rejected','pending','conflict'), 'Unknown/duplicate pair or invalid decision.', 'INVALID_CHAIN_REVIEW')
        require(isinstance(reason,str) and 1<=len(reason.strip())<=4000 and isinstance(ids,list) and all(isinstance(i,str) for i in ids) and len(set(ids))==len(ids), 'Provide a reason and unique evidence IDs.', 'INVALID_CHAIN_REVIEW')
        known={e['evidence_id'] for e in pairs[pid]['evidence']}
        require(set(ids)<=known,'Evidence IDs must belong to this exact pair.','INVALID_CHAIN_REVIEW')
        require((decision=='confirmed' and relation in ('rigid_connection','revolute_joint','prismatic_joint','other_connection')) or
                (decision!='confirmed' and relation is None), 'Only a confirmed declaration has an explicit relation type.', 'INVALID_CHAIN_REVIEW')
        flags=pairs[pid]['review_flags']
        acknowledged=item.get('acknowledged_flags',[])
        require(isinstance(acknowledged,list) and all(isinstance(x,str) for x in acknowledged) and len(set(acknowledged))==len(acknowledged), 'Invalid acknowledged flags.', 'INVALID_CHAIN_REVIEW')
        flag_codes={f['code'] for f in flags}
        require(set(acknowledged)<=flag_codes and (decision not in ('confirmed','rejected') or set(acknowledged)==flag_codes),
                'A settled human declaration must explicitly acknowledge every pair review flag.', 'UNACKNOWLEDGED_CHAIN_FLAGS')
        decisions[pid]={'decision':decision,'relation_type':relation,'reason':reason.strip(),'evidence_ids':ids,
                       'acknowledged_flags':acknowledged,'reviewer':reviewer.strip(),'reviewed_at':when,
                       'basis':'human_declaration','human_confirmed':decision=='confirmed','cad_verified':False,
                       'motion_parameters_verified':False}
    rows=[]
    for pair in expected['pairs']:
        declaration=decisions.get(pair['pair_id'])
        rows.append({**pair,'review_state':'pending' if declaration is None else declaration['decision'],
                     'human_review':declaration,'mechanical_relation_confirmed':False})
    counts={s:sum(p['review_state']==s for p in rows) for s in ('confirmed','rejected','pending','conflict')}
    # Repeat reading the base/decision files after replay; no modification or implicit carry-over.
    require(read_json(path)[1]==digest and read_json(review_file)[1]==review_sha,'Review inputs changed during processing.','EVIDENCE_MISMATCH')
    for binding in expected['input_files']:
        require(read_json(json_path(root,binding['path']))[1]==binding['sha256'],'Evidence changed during human review application.','EVIDENCE_MISMATCH')
    data={'chain_review_schema_version':1,'chain_name':expected['chain_name'],'document':expected['document'],
          'captured_at_utc':datetime.now(timezone.utc).isoformat(),'base_chain':{'path':str(path),'sha256':digest},
          'review_source':{'path':str(review_file),'sha256':review_sha},'input_files':expected['input_files'],
          'members':expected['members'],'pairs':rows,'boundary_evidence':expected['boundary_evidence'],
          'sources':expected['sources'],'outside_scope_records':expected['outside_scope_records'],
          'coverage':expected['coverage'],'review_counts':counts,'human_review_complete':not(counts['pending'] or counts['conflict']),
          'complete':expected['complete'],'errors':expected['errors'],'requires_review':bool(counts['pending'] or counts['conflict'] or not expected['complete']),
          'mechanical_relation_confirmed':False,'solidworks_modified':False,
          'limitations':expected['limitations']+['Confirmed/rejected are attributed human declarations, not tool-verified CAD facts or solver results.',
              'Human review does not remove source errors/unknown geometry. Names/timestamps do not authenticate a person.',
              'Rejected means the proposed connection is not accepted by the reviewer; it is not CAD proof of disconnection.',
              'Even a human-confirmed joint lacks verified axes/limits; no movement, rigid-body merge or joint creation is executed.',
              'Unspecified pairs remain pending; new dossiers require fresh bound decisions, never index-based carry-over.']}
    write_result(output,data)
    return success({'output_path':str(output),'review_counts':counts,'human_review_complete':data['human_review_complete'],
                    'complete':data['complete'],'requires_review':data['requires_review'],'mechanical_relation_confirmed':False,
                    'solidworks_modified':False},data['errors'])
