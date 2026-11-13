"""Bind finite planar reads to verified original adjacency; never invent catalog indices."""
from cadkin.adapters.face_identity import decode_reference
from cadkin.tools.chain_sources import require
from cadkin.tools.engagement_sources import validate_engagement_capture,load_engagement_boundary
from cadkin.tools.face_contacts import same_derived
from cadkin.tools.files import json_path,read_json
from cadkin.tools.relations import _document
from cadkin.planar_regions import region_from_loops


def load_planar_source(root,expected_document_token,adjacency_path,face_reference,**options):
    decode_reference(face_reference)
    path=json_path(root,adjacency_path);raw,digest=read_json(path);d=validate_engagement_capture(root,raw)
    require(d.get('face_adjacency_schema_version')==1 and d['complete'] and not d['truncated'],
        'Use complete original adjacency.','INVALID_PLANAR_SOURCE')
    require(d['document']['document_token']==expected_document_token,'Adjacency token differs.','EVIDENCE_MISMATCH')
    matches=[n for e in d['adjacency'] for n in e['neighbors'] if n and not n['is_selected_face'] and n['face_reference']==face_reference]
    require(matches and all(n==matches[0] for n in matches) and matches[0]['same_body'] and matches[0]['descriptor']['surface_type']=='plane',
        'Choose a unique planar neighbor from the original adjacency.','INVALID_PLANAR_SOURCE')
    binding={'path':str(path),'sha256':digest}
    source={'document':d['document'],'target':d['source']['target'],
        'face':{'face_reference':face_reference,'descriptor':matches[0]['descriptor']},'adjacency_source':binding}
    b=load_engagement_boundary(root,expected_document_token,d['boundary_source']['path'])
    require(b['boundary_source']==d['boundary_source'],'Adjacency boundary changed.','EVIDENCE_MISMATCH')
    return {'expected_document_token':expected_document_token,'source':source,'adjacency':d,'cylinder_boundary':b['boundary'],**options}


def validate_planar_capture(root,raw):
    require(isinstance(raw,dict) and raw.get('status') in ('ok','partial') and isinstance(raw.get('data'),dict),
        'Use an original planar region envelope.','INVALID_PLANAR_SOURCE')
    d=raw['data'];s=d.get('source');require(isinstance(s,dict) and d.get('planar_region_schema_version')==1,'Invalid planar schema.','INVALID_PLANAR_SOURCE')
    original=load_planar_source(root,d.get('document',{}).get('document_token'),s['adjacency_source']['path'],s['face']['face_reference'])
    require(s==original['source'] and _document(d['document'])==_document(s['document']),'Planar source changed.','EVIDENCE_MISMATCH')
    require(d.get('method')=='IFace2.GetLoops_with_IEdge.GetCurveParams3' and d.get('geometry_scope')=='referenced_part_definition' and
        d.get('assembly_instance_features_evaluated') is False and d.get('snapshot_atomic') is False and
        d.get('solidworks_modified') is False and d.get('contact_confirmed') is False,'Unsupported method/scope.','INVALID_PLANAR_SOURCE')
    errors=raw.get('errors');params=d.get('parameters');loops=d.get('loops')
    require(isinstance(errors,list) and all(isinstance(e,dict) for e in errors) and type(d.get('complete')) is bool and
        d['complete']==(not errors) and (raw['status']=='ok')==(not errors),'Invalid completeness.','INVALID_PLANAR_SOURCE')
    require(isinstance(params,dict) and set(params)=={'max_loops','max_edges'} and
        type(params['max_loops']) is int and 1<=params['max_loops']<=8 and type(params['max_edges']) is int and 3<=params['max_edges']<=128,
        'Invalid planar budgets.','INVALID_PLANAR_SOURCE')
    count=d.get('reported_loop_count');require(type(count) is int and count>0 and isinstance(loops,list) and len(loops)==min(count,params['max_loops']),
        'Invalid loop coverage.','INVALID_PLANAR_SOURCE')
    total=0
    for i,l in enumerate(loops):
        require(isinstance(l,dict) and l.get('loop_index')==i and isinstance(l.get('errors'),list) and isinstance(l.get('edges'),list),
            'Invalid loop row.','INVALID_PLANAR_SOURCE')
        require(not l['errors'] or errors,'Missing loop error.','INVALID_PLANAR_SOURCE')
        if not l['errors']:
            require(type(l.get('is_outer')) is bool and type(l.get('reported_edge_count')) is int and l['reported_edge_count']==len(l['edges']) and len(l['edges'])>0,
                'Invalid loop edge count.','INVALID_PLANAR_SOURCE')
        for j,e in enumerate(l['edges']):require(isinstance(e,dict) and e.get('edge_index')==j,'Invalid edge index.','INVALID_PLANAR_SOURCE')
        total+=len(l['edges'])
    require(total<=params['max_edges'] and type(d.get('truncated')) is bool and (not d['truncated'] or errors) and
        (count<=params['max_loops'] or d['truncated']),'Invalid capture limit.','INVALID_PLANAR_SOURCE')
    if d.get('region') is None:require(errors,'Missing region without error.','INVALID_PLANAR_SOURCE')
    else:
        require(not d['truncated'] and count==len(loops),'Incomplete regions cannot be derived.','INVALID_PLANAR_SOURCE')
        require(same_derived(d['region'],region_from_loops(s['face']['descriptor'],loops)),'Derived region differs.','INVALID_PLANAR_SOURCE')
    return d
