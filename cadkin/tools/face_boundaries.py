"""Validate original boundary captures against their persisted face catalogs."""
from cadkin.face_geometry import require
from cadkin.finite_geometry import edge_record
from cadkin.tools.face_sources import face_source
from cadkin.tools.relations import _document


def selection(source):
    return {'face_inventory_path':source['path'],'body_index':source['face']['body_index'],'face_index':source['face']['face_index']}


def load_boundary_source(root,expected_document_token,face,max_edges=64):
    source=face_source(root,face)
    require(source['document']['document_token']==expected_document_token,'Face source uses another document.','EVIDENCE_MISMATCH')
    return {'expected_document_token':expected_document_token,'source':source,'max_edges':max_edges}


def validate_boundary(root,raw):
    require(isinstance(raw,dict) and raw.get('status') in ('ok','partial') and isinstance(raw.get('data'),dict),
            'Use an original boundary envelope.','INVALID_BOUNDARY_SOURCE')
    d=raw['data']; errors=raw.get('errors'); source=d.get('source')
    require(d.get('face_boundary_schema_version')==1 and d.get('method')=='IFace2.GetEdges_analytic_curves_and_line_vertices' and
        d.get('geometry_scope')=='referenced_part_definition' and d.get('assembly_instance_features_evaluated') is False and
        d.get('solidworks_modified') is False and d.get('physical_engagement_confirmed') is False and isinstance(source,dict),
        'Unsupported boundary scope/method.','INVALID_BOUNDARY_SOURCE')
    require(face_source(root,selection(source))==source and _document(d.get('document'))==_document(source['document']),
            'Boundary source changed.','EVIDENCE_MISMATCH')
    require(source['face']['descriptor']['surface_type']=='cylinder','Expected cylindrical boundary.','INVALID_BOUNDARY_SOURCE')
    params=d.get('parameters');rows=d.get('edges');total=d.get('reported_edge_count')
    require(isinstance(params,dict) and set(params)=={'max_edges'} and type(params['max_edges']) is int and 1<=params['max_edges']<=256 and
        isinstance(rows,list) and type(total) is int and total>0 and len(rows)==min(total,params['max_edges']) and
        type(d.get('read_edge_count')) is int and d['read_edge_count']==len(rows) and type(d.get('truncated')) is bool and
        d['truncated']==(total>params['max_edges']), 'Invalid boundary coverage.','INVALID_BOUNDARY_SOURCE')
    require(isinstance(errors,list) and all(isinstance(e,dict) for e in errors) and type(d.get('complete')) is bool and
        d['complete']==(not errors) and (raw['status']=='ok')==(not errors),'Invalid boundary status.','INVALID_BOUNDARY_SOURCE')
    for i,row in enumerate(rows):
        edge_record(row)
        require(row['edge_index']==i and (not row['errors'] or bool(errors)) and
            (row['curve_kind'] in ('line','circle') or bool(row['errors'])), 'Missing edge/error record.','INVALID_BOUNDARY_SOURCE')
    require(not (d['truncated'] or not source['complete']) or bool(errors),'Incomplete boundary cannot be complete.','INVALID_BOUNDARY_SOURCE')
    return d
