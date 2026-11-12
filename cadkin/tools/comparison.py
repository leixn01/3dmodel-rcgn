"""Independent replay boundary for before/after draft comparisons."""
from cadkin.errors import success
from cadkin.tools.files import json_path,read_json, replay_reads
from cadkin.tools.chain_sources import require,check_fields
from cadkin.tools.followup import build_check
from cadkin.tools.rigid import replay_draft
from cadkin.tools.matching import recheck
from cadkin.tools.proximity import write_result
from cadkin.followup.comparison import compare_checks
from cadkin.followup.execution import document_matches
from cadkin.followup.face_comparison import compare_faces


@replay_reads
def replay_check(root,name):
    path=json_path(root,name);raw,sha=read_json(path)
    require(isinstance(raw,dict) and raw.get('draft_check_schema_version')==1 and raw.get('algorithm_version') in (1, 2) and
            isinstance(raw.get('parameters'),dict) and set(raw['parameters'])=={'joint_draft_path','max_findings'},
            'Use original draft checks.','INVALID_DRAFT_CHECK')
    check,target=build_check(root,**raw['parameters']);check_fields(raw,check)
    draft,rigid,_,_=replay_draft(root,check['draft_source']['path'])
    return check,target,draft,rigid,{'path':str(path),'sha256':sha}


def compare_draft_checks(root,before_check_path,after_check_path,output_path):
    output=json_path(root,output_path,output=True)
    before,bt,bd,br,bb=replay_check(root,before_check_path)
    after,at,ad,ar,ab=replay_check(root,after_check_path)
    require(document_matches(before['document'],after['document']),'Different document/configuration snapshots cannot be compared as an evidence-only update.','EVIDENCE_MISMATCH')
    fields=('id','parent_id','file_path','configuration','to_root_column_vectors_m')
    bnodes={n['id']:n for n in bt['nodes']};anodes={n['id']:n for n in at['nodes']}
    require(all(all(bnodes[p][k]==anodes[p][k] for k in fields) for p in bnodes.keys()&anodes.keys()),
            'Shared occurrences changed identity or pose.','EVIDENCE_MISMATCH')
    data=compare_checks(before,after,bd,ad,bt,at)
    chains = []
    for target in (bt, at):
        raw, digest = read_json(json_path(root, target['source_chain']['path']))
        require(digest == target['source_chain']['sha256'], 'Chain changed during comparison.', 'EVIDENCE_MISMATCH')
        chains.append(raw)
    data.update(algorithm_version=2, face_evidence=compare_faces(*chains, bt, at))
    data['settings_equal']=data['settings_equal'] and {k:v for k,v in br['parameters'].items() if k!='target_graph_path'}=={k:v for k,v in ar['parameters'].items() if k!='target_graph_path'}
    data.update(before_check_source=bb,after_check_source=ab,
                before_findings=before['findings'],after_findings=after['findings'])
    recheck(root,before['input_files']+after['input_files']+[bb,ab]);write_result(output,data)
    errors=[]
    if not data['settings_equal'] or not data['occurrence_scope_equal']:
        errors.append({'code':'COMPARISON_SCOPE_CHANGED','message':'Settings or occurrence scope differs; changes cannot be attributed only to added evidence.'})
    if before['output_truncated'] or after['output_truncated']:
        errors.append({'code':'COMPARISON_FINDINGS_LIMIT','message':'Finding lists are truncated; absent entries remain unknown.'})
    return success({'output_path':str(output),**data},errors)
