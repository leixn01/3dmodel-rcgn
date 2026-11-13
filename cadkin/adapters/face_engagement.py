"""Independent finite-face samples and source-bound edge adjacency reads."""
from datetime import datetime,timezone
import math
from cadkin._vendor.sw_mcp import value
from cadkin.adapters.evidence import sequence,evidence_error
from cadkin.adapters.face_probe import ProbeFace
from cadkin.adapters.face_boundary import read_edges
from cadkin.adapters.face_identity import same_object,capture_face_reference
from cadkin.adapters.faces import read_descriptor
from cadkin.engagement import sample_metrics
from cadkin.errors import success
from cadkin.face_geometry import require
from cadkin.geometry import numbers


def check_boundary(face,boundary):
    face.check();rows,count,errors=read_edges(face.face,boundary['parameters']['max_edges'])
    require(not errors and rows==boundary['edges'] and count==boundary['reported_edge_count'],
        'Live boundary differs from the saved finite face.','GEOMETRY_CHANGED')


def base_data(face,binding,schema):
    return {schema:1,'document':face.context.info,'source':face.source,'boundary_source':binding,
        'captured_at_utc':datetime.now(timezone.utc).isoformat(),'snapshot_atomic':False,
        'geometry_scope':'referenced_part_definition','assembly_instance_features_evaluated':False,
        'solidworks_modified':False,'physical_engagement_confirmed':False,'finite_motion_verified':False}


def read_adjacency(adapter,face,max_edges):
    edges=sequence(value(face.face,'GetEdges'),'GetEdges');rows=[];errors=[]
    for i,edge in enumerate(edges[:max_edges]):
        row={'edge_index':i,'neighbors':[],'errors':[]}
        try:
            neighbors=sequence(value(edge,'GetTwoAdjacentFaces2'),'GetTwoAdjacentFaces2')
            require(len(neighbors)==2,'Expected two adjacency slots, including possible null.','INVALID_ADJACENCY')
            selected=False
            for neighbor in neighbors:
                if neighbor is None:row['neighbors'].append(None);continue
                is_self=same_object(adapter.app,face.face,neighbor);selected |= is_self
                same_body=same_object(adapter.app,value(face.face,'GetBody'),value(neighbor,'GetBody'))
                require(same_body,'Adjacent face belongs to another body.','GEOMETRY_CHANGED')
                row['neighbors'].append({'is_selected_face':is_self,'same_body':same_body,
                    'face_reference':capture_face_reference(face.context.part,neighbor,adapter.app,adapter.runtime),
                    'descriptor':read_descriptor(neighbor)})
            require(selected,'Edge adjacency does not contain the selected face.','GEOMETRY_CHANGED')
        except Exception as exc:row['errors'].append(evidence_error(exc))
        rows.append(row);errors.extend({**e,'edge_index':i} for e in row['errors'])
    if len(edges)>max_edges:errors.append({'code':'ADJACENCY_EDGE_LIMIT','message':'Uninspected adjacency remains unknown.'})
    return rows,len(edges),errors


class FaceEngagementOperations:
    def sw_sample_cylinder_face(self,expected_document_token,boundary,boundary_source,query_points_root_mm,membership_tolerance_mm):
        require(isinstance(query_points_root_mm,list) and 1<=len(query_points_root_mm)<=32,'Use 1–32 explicit query points.','INVALID_ARGUMENTS')
        queries=[numbers(p,3,'INVALID_ARGUMENTS') for p in query_points_root_mm]
        t=numbers([membership_tolerance_mm],1,'INVALID_ARGUMENTS')[0]
        require(0<t<=.1,'Membership tolerance must be in (0,.1] mm.','INVALID_ARGUMENTS')
        face=ProbeFace(self,expected_document_token,boundary['source']);check_boundary(face,boundary)
        rows=[];errors=list(face.context.errors)
        for i,q in enumerate(queries):
            row={'query_index':i,'query_root_mm':q,'sample':None,'normal':None,'metrics':None,'errors':[]}
            try:
                sample=face.project([v/1000 for v in q]);verified=face.project(sample['point_root_m'])
                require(math.dist(sample['point_root_m'],verified['point_root_m'])<=1e-8,'Sample failed same-face reprojection.','FACE_POINT_NOT_ON_FACE')
                normal=face.normal(sample);row.update(sample=sample,normal=normal,
                    metrics=sample_metrics(face.source,q,sample,normal,t))
            except Exception as exc:row['errors'].append(evidence_error(exc))
            rows.append(row);errors.extend({**e,'query_index':i} for e in row['errors'])
        check_boundary(face,boundary)
        data=base_data(face,boundary_source,'cylinder_sample_schema_version')
        data.update(method='IFace2.GetClosestPointOn_and_oriented_surface_normal',
            parameters={'query_points_root_mm':queries,'membership_tolerance_mm':t},samples=rows,complete=not errors,
            continuous_angular_coverage_proven=False,
            limitations=['Only explicit point memberships and oriented local normals; points between queries remain unknown.',
                'Sheet orientation does not identify material inside/outside. Sample fraction is not angular or area coverage.',
                'No contact, interference, finite motion, fit or retention proof. Boundary readback is not an atomic topology snapshot.'])
        return success(data,errors)

    def sw_read_face_adjacency(self,expected_document_token,boundary,boundary_source,max_edges=64):
        require(type(max_edges) is int and 1<=max_edges<=256,'max_edges must be 1–256.','INVALID_ARGUMENTS')
        face=ProbeFace(self,expected_document_token,boundary['source']);check_boundary(face,boundary)
        rows,count,errors=read_adjacency(self,face,max_edges)
        require(count==boundary['reported_edge_count'],'Boundary count changed.','GEOMETRY_CHANGED')
        face.check();latest=read_adjacency(self,face,max_edges)
        require((rows,count,errors)==latest,'Adjacency changed during reading.','GEOMETRY_CHANGED')
        check_boundary(face,boundary);errors=list(face.context.errors)+errors
        data=base_data(face,boundary_source,'face_adjacency_schema_version')
        data.update(method='IEdge.GetTwoAdjacentFaces2_with_identity_and_body_checks',parameters={'max_edges':max_edges},
            adjacency=rows,reported_edge_count=count,read_edge_count=len(rows),truncated=count>max_edges,complete=not errors,
            limitations=['A shared edge and body are topological facts, not contact with another occurrence or a travel stop.',
                'Null neighbors and seams are retained. Plane parameters do not establish finite planar overlap.',
                'Reference round-trip, face/boundary/adjacency readback do not prove an atomic snapshot or evaluate assembly features.'])
        return success(data,errors)
