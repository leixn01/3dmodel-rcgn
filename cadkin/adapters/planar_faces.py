"""Bounded exact primitive loops on one persisted neighbor; no temporary CAD bodies."""
from datetime import datetime,timezone
from cadkin._vendor.sw_mcp import value
from cadkin.adapters.evidence import sequence,integer,boolean,evidence_error
from cadkin.adapters.face_probe import ProbeFace
from cadkin.adapters.face_identity import same_object
from cadkin.adapters.face_engagement import check_boundary,read_adjacency
from cadkin.errors import success
from cadkin.geometry import numbers
from cadkin.face_geometry import require
from cadkin.planar_regions import region_from_loops


def read_loops(face,max_loops,max_edges):
    count=integer(value(face,'GetLoopCount'),'loop count',1)
    loops=sequence(value(face,'GetLoops'),'GetLoops')
    require(count==len(loops),'Loop count changed.','GEOMETRY_CHANGED')
    rows=[];errors=[];remaining=max_edges;truncated=count>max_loops
    for i,loop in enumerate(loops[:max_loops]):
        row={'loop_index':i,'is_outer':None,'reported_edge_count':None,'edges':[],'errors':[]}
        try:
            row['is_outer']=boolean(value(loop,'IsOuter'),'IsOuter');n=integer(value(loop,'GetEdgeCount'),'loop edges',1)
            edges=sequence(value(loop,'GetEdges'),'loop GetEdges');require(n==len(edges),'Loop edge count differs.','GEOMETRY_CHANGED')
            row['reported_edge_count']=n
            if n>remaining:truncated=True;row['errors'].append({'code':'PLANAR_EDGE_LIMIT','message':'Total edge budget reached.'})
            for j,edge in enumerate(edges[:remaining]):
                curve=value(edge,'GetCurve');record={'edge_index':j,'kind':'unsupported'}
                if boolean(value(curve,'IsLine'),'IsLine'):
                    record.update(kind='line',start_point_part_m=numbers(value(value(edge,'GetStartVertex'),'GetPoint'),3,'INVALID_PLANAR_SOURCE'),
                        end_point_part_m=numbers(value(value(edge,'GetEndVertex'),'GetPoint'),3,'INVALID_PLANAR_SOURCE'))
                elif boolean(value(curve,'IsCircle'),'IsCircle'):
                    params=value(edge,'GetCurveParams3')
                    record.update(kind='circle',circle_parameters_part=numbers(value(curve,'CircleParams'),7,'INVALID_PLANAR_SOURCE'),
                        start_point_part_m=numbers(value(params,'StartPoint'),3,'INVALID_PLANAR_SOURCE'),
                        end_point_part_m=numbers(value(params,'EndPoint'),3,'INVALID_PLANAR_SOURCE'),
                        u_min=numbers([value(params,'UMinValue')],1,'INVALID_PLANAR_SOURCE')[0],
                        u_max=numbers([value(params,'UMaxValue')],1,'INVALID_PLANAR_SOURCE')[0])
                row['edges'].append(record);remaining-=1
        except Exception as exc:row['errors'].append(evidence_error(exc))
        rows.append(row);errors.extend({**e,'loop_index':i} for e in row['errors'])
    if count>max_loops:errors.append({'code':'PLANAR_LOOP_LIMIT','message':'Loop budget reached.'})
    return rows,count,truncated,errors


class PlanarFaceOperations:
    def sw_read_planar_face(self,expected_document_token,source,adjacency,cylinder_boundary,max_loops=8,max_edges=64):
        require(type(max_loops) is int and 1<=max_loops<=8 and type(max_edges) is int and 3<=max_edges<=128,'Invalid loop/edge budget.','INVALID_ARGUMENTS')
        cylinder=ProbeFace(self,expected_document_token,adjacency['source']);face=ProbeFace(self,expected_document_token,source)
        def context_check():
            check_boundary(cylinder,cylinder_boundary);face.check()
            require(same_object(self.app,value(face.face,'GetBody'),value(cylinder.face,'GetBody')),'Neighbor body changed.','GEOMETRY_CHANGED')
            rows,count,errors=read_adjacency(self,cylinder,adjacency['parameters']['max_edges'])
            require(not errors and rows==adjacency['adjacency'] and count==adjacency['reported_edge_count'],'Saved adjacency changed.','GEOMETRY_CHANGED')
        context_check();rows,count,truncated,errors=read_loops(face.face,max_loops,max_edges)
        face.check();require((rows,count,truncated,errors)==read_loops(face.face,max_loops,max_edges),'Planar loops changed.','GEOMETRY_CHANGED')
        context_check();errors=list(face.context.errors)+errors;region=None
        if not errors and not truncated:
            try:region=region_from_loops(face.descriptor,rows)
            except Exception as exc:errors.append(evidence_error(exc))
        return success({'planar_region_schema_version':1,'document':face.context.info,'source':source,
            'captured_at_utc':datetime.now(timezone.utc).isoformat(),'snapshot_atomic':False,'method':'IFace2.GetLoops_with_IEdge.GetCurveParams3',
            'geometry_scope':'referenced_part_definition','assembly_instance_features_evaluated':False,
            'parameters':{'max_loops':max_loops,'max_edges':max_edges},'loops':rows,'reported_loop_count':count,
            'truncated':truncated,'complete':not errors,'region':region,'solidworks_modified':False,'contact_confirmed':False,
            'limitations':['Only full circular disks/concentric annuli or a single convex straight-edge loop are interpreted; no tessellation.',
                'Area is checked against GetArea. Numeric closure tolerance is not physical contact tolerance.',
                'Readback is not atomic. Part definitions omit assembly features; regions do not certify contact, retention or motion.']},errors)
