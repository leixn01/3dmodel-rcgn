"""Bounded analytic edges on one source-bound finite face; no tessellation or CAD edits."""
from datetime import datetime, timezone
from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import sequence, boolean, integer, evidence_error
from cadkin.adapters.face_probe import ProbeFace
from cadkin.errors import success
from cadkin.face_geometry import require
from cadkin.finite_geometry import edge_record
from cadkin.geometry import numbers


def read_edges(face, max_edges):
    reported=integer(value(face,'GetEdgeCount'),'face edge count')
    edges=sequence(value(face,'GetEdges'),'GetEdges')
    require(reported==len(edges) and reported>0,'Face edge enumeration/count is inconsistent.','BOUNDARY_TOPOLOGY_UNAVAILABLE')
    rows=[];errors=[]
    for i,edge in enumerate(edges[:max_edges]):
        row={'edge_index':i,'curve_kind':'unavailable','endpoints_part_m':None,'circle_parameters_part':None,'errors':[]}
        try:
            curve=value(edge,'GetCurve')
            require(curve is not None,'Missing edge curve.','BOUNDARY_CURVE_UNAVAILABLE')
            if boolean(value(curve,'IsLine'),'IsLine'):
                pts=[numbers(value(value(edge,name),'GetPoint'),3,'INVALID_BOUNDARY_SOURCE') for name in ('GetStartVertex','GetEndVertex')]
                row.update(curve_kind='line',endpoints_part_m=pts)
            elif boolean(value(curve,'IsCircle'),'IsCircle'):
                row.update(curve_kind='circle',circle_parameters_part=numbers(value(curve,'CircleParams'),7,'INVALID_BOUNDARY_SOURCE'))
            else:
                row['curve_kind']='unsupported'
                row['errors'].append({'code':'UNSUPPORTED_BOUNDARY_CURVE','message':'Only analytic lines and circles are read; no sampling approximation.'})
            edge_record(row)
        except Exception as exc:
            row.update(curve_kind='unavailable',endpoints_part_m=None,circle_parameters_part=None)
            row['errors'].append(evidence_error(exc))
        rows.append(row);errors.extend({**e,'edge_index':i} for e in row['errors'])
    if reported>max_edges:errors.append({'code':'BOUNDARY_EDGE_LIMIT','message':'Boundary edge budget reached; extent remains unknown.'})
    return rows,reported,errors


class FaceBoundaryOperations:
    def sw_read_face_boundary(self,expected_document_token,source,max_edges=64):
        require(type(max_edges) is int and 1<=max_edges<=256,'max_edges must be 1–256.','INVALID_ARGUMENTS')
        face=ProbeFace(self,expected_document_token,source)
        require(face.descriptor['surface_type']=='cylinder','This release reads cylindrical face boundaries.','UNSUPPORTED_FACE_SURFACE')
        rows,count,errors=read_edges(face.face,max_edges)
        face.check()
        latest=read_edges(face.face,max_edges)
        require((rows,count,errors)==latest,'Boundary changed during capture.','GEOMETRY_CHANGED')
        face.check();errors=list(face.context.errors)+errors
        if not source['complete']:errors.append({'code':'SOURCE_INCOMPLETE','message':'Face catalog is incomplete.'})
        return success({'face_boundary_schema_version':1,'document':face.context.info,'source':source,
            'captured_at_utc':datetime.now(timezone.utc).isoformat(),'snapshot_atomic':False,
            'geometry_scope':'referenced_part_definition','assembly_instance_features_evaluated':False,
            'method':'IFace2.GetEdges_analytic_curves_and_line_vertices','parameters':{'max_edges':max_edges},
            'edges':rows,'reported_edge_count':count,'read_edge_count':len(rows),'truncated':count>max_edges,
            'complete':not errors,'solidworks_modified':False,'physical_engagement_confirmed':False,
            'limitations':['Circular curves may be arcs; no full-circle or angular coverage assumption.',
                'Boundary readback and saved face identity/descriptor are not an atomic topology fingerprint.',
                'Referenced part geometry excludes assembly-level features. No fit, motion, retention or limit verification.']},errors)
