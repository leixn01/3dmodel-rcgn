"""Original finite-boundary bindings and independently replayed sample/adjacency records."""
from cadkin.adapters.face_identity import decode_reference
from cadkin.engagement import sample_metrics
from cadkin.face_geometry import descriptor,point,root_normal
from cadkin.geometry import numbers,transform_from_sw
from cadkin.tools.chain_sources import require
from cadkin.tools.face_boundaries import validate_boundary
from cadkin.tools.face_contacts import same_derived
from cadkin.tools.files import json_path,read_json
from cadkin.tools.relations import _document


METHODS={'cylinder_sample_schema_version':'IFace2.GetClosestPointOn_and_oriented_surface_normal',
         'face_adjacency_schema_version':'IEdge.GetTwoAdjacentFaces2_with_identity_and_body_checks'}


def load_engagement_boundary(root,expected_document_token,boundary_path,**options):
    path=json_path(root,boundary_path);raw,digest=read_json(path);data=validate_boundary(root,raw)
    require(data['complete'] and not data['truncated'],'Use a complete original boundary.','INCOMPLETE_BOUNDARY')
    require(data['document']['document_token']==expected_document_token,'Boundary token differs.','EVIDENCE_MISMATCH')
    return {'expected_document_token':expected_document_token,'boundary':data,
        'boundary_source':{'path':str(path),'sha256':digest},**options}


def validate_engagement_capture(root,raw):
    require(isinstance(raw,dict) and raw.get('status') in ('ok','partial') and isinstance(raw.get('data'),dict),
        'Use an original surface inspection envelope.','INVALID_ENGAGEMENT_SOURCE')
    d=raw['data'];schemas=[k for k in METHODS if d.get(k)==1]
    require(len(schemas)==1,'Invalid inspection schema.','INVALID_ENGAGEMENT_SOURCE');schema=schemas[0]
    b=d.get('boundary_source');require(isinstance(b,dict),'Missing boundary binding.','INVALID_ENGAGEMENT_SOURCE')
    original=load_engagement_boundary(root,d.get('document',{}).get('document_token'),b['path'])
    require(original['boundary_source']==b and original['boundary']['source']==d.get('source') and
        _document(d['document'])==_document(original['boundary']['document']),'Inspection source/context changed.','EVIDENCE_MISMATCH')
    require(d.get('method')==METHODS[schema] and d.get('geometry_scope')=='referenced_part_definition' and
        d.get('assembly_instance_features_evaluated') is False and d.get('solidworks_modified') is False and
        d.get('physical_engagement_confirmed') is False and d.get('finite_motion_verified') is False,
        'Unsupported inspection method/scope.','INVALID_ENGAGEMENT_SOURCE')
    errors=raw.get('errors');require(isinstance(errors,list) and all(isinstance(e,dict) for e in errors) and
        type(d.get('complete')) is bool and d['complete']==(not errors) and (raw['status']=='ok')==(not errors),
        'Inconsistent inspection completeness.','INVALID_ENGAGEMENT_SOURCE')
    params=d.get('parameters');require(isinstance(params,dict),'Missing parameters.','INVALID_ENGAGEMENT_SOURCE')
    if schema=='cylinder_sample_schema_version':
        require(set(params)=={'query_points_root_mm','membership_tolerance_mm'} and d.get('continuous_angular_coverage_proven') is False,
            'Invalid sampling parameters.','INVALID_ENGAGEMENT_SOURCE')
        tolerance=numbers([params['membership_tolerance_mm']],1,'INVALID_ENGAGEMENT_SOURCE')[0]
        queries=params['query_points_root_mm'];rows=d.get('samples')
        require(0<tolerance<=.1 and isinstance(queries,list) and 1<=len(queries)<=32 and isinstance(rows,list) and len(rows)==len(queries),
            'Invalid sample count/tolerance.','INVALID_ENGAGEMENT_SOURCE')
        transform=transform_from_sw(d['source']['target']['transform']['raw_array'])
        require(transform==d['source']['target']['transform'],'Source transform differs.','EVIDENCE_MISMATCH')
        for i,(q,row) in enumerate(zip(queries,rows)):
            numbers(q,3,'INVALID_ENGAGEMENT_SOURCE')
            require(isinstance(row,dict) and row.get('query_index')==i and row.get('query_root_mm')==q and isinstance(row.get('errors'),list),
                'Invalid sample row.','INVALID_ENGAGEMENT_SOURCE')
            if row.get('metrics') is None:
                require(row['errors'] and errors,'Missing failed query.','INVALID_ENGAGEMENT_SOURCE');continue
            sample,normal=row.get('sample'),row.get('normal')
            require(isinstance(sample,dict) and isinstance(normal,dict),'Missing raw point/normal.','INVALID_ENGAGEMENT_SOURCE')
            numbers(sample.get('uv'),2,'INVALID_ENGAGEMENT_SOURCE')
            expected=point(transform['to_root'],numbers(sample.get('point_part_m'),3,'INVALID_ENGAGEMENT_SOURCE'))
            require(same_derived(sample.get('point_root_m'),expected),'Sample transform differs.','INVALID_ENGAGEMENT_SOURCE')
            sense=d['source']['face']['descriptor']['face_in_surface_sense']
            n=numbers(normal.get('evaluation_part_raw'),11,'INVALID_ENGAGEMENT_SOURCE')
            require(normal.get('face_in_surface_sense') is sense and same_derived(normal.get('face_normal_root_unit'),root_normal(transform,n[:3],sense)),
                'Oriented normal differs.','INVALID_ENGAGEMENT_SOURCE')
            require(same_derived(row['metrics'],sample_metrics(d['source'],q,sample,normal,tolerance)),
                'Derived membership/orientation differs.','INVALID_ENGAGEMENT_SOURCE')
            require(not row['errors'] or bool(errors),'Lost sample errors.','INVALID_ENGAGEMENT_SOURCE')
    else:
        require(set(params)=={'max_edges'} and type(params['max_edges']) is int and 1<=params['max_edges']<=256,
            'Invalid adjacency budget.','INVALID_ENGAGEMENT_SOURCE')
        rows=d.get('adjacency');count=original['boundary']['reported_edge_count']
        require(isinstance(rows,list) and len(rows)==min(count,params['max_edges']) and d.get('reported_edge_count')==count and
            d.get('read_edge_count')==len(rows) and type(d.get('truncated')) is bool and d['truncated']==(count>params['max_edges']),
            'Invalid adjacency coverage.','INVALID_ENGAGEMENT_SOURCE')
        require(not d['truncated'] or bool(errors),'Lost truncation error.','INVALID_ENGAGEMENT_SOURCE')
        for i,row in enumerate(rows):
            require(isinstance(row,dict) and row.get('edge_index')==i and isinstance(row.get('errors'),list) and isinstance(row.get('neighbors'),list),
                'Invalid adjacency record.','INVALID_ENGAGEMENT_SOURCE')
            if row['errors']:require(bool(errors),'Lost adjacency errors.','INVALID_ENGAGEMENT_SOURCE');continue
            require(len(row['neighbors'])==2 and any(n and n.get('is_selected_face') is True for n in row['neighbors']),
                'Selected face absent from edge adjacency.','INVALID_ENGAGEMENT_SOURCE')
            for n in row['neighbors']:
                if n is None:continue
                require(isinstance(n,dict) and type(n.get('is_selected_face')) is bool and n.get('same_body') is True,
                    'Invalid body/identity facts.','INVALID_ENGAGEMENT_SOURCE')
                decode_reference(n.get('face_reference'));descriptor(n.get('descriptor'))
                if n['is_selected_face']:
                    require(n['descriptor']==d['source']['face']['descriptor'],'Selected face descriptor differs.','EVIDENCE_MISMATCH')
    return d
