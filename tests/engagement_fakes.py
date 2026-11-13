"""Explicit synthetic solids for sampled surface and edge topology tests."""
from unittest.mock import patch
from tests.face_probe_fakes import probe_document,ProbeBody,ProbeFace
from tests.evidence_fakes import Part
from tests.face_fakes import PersistentExtension
from tests.finite_connection_fakes import finite_fixture,Edge
from tests.geometry_connection_fakes import run_batch


def inspection_document(inner=True):
    doc,part,app=probe_document()
    right=Part([ProbeBody()]);right.Extension=PersistentExtension(right)
    doc.root.children[1].model_doc=right
    right.bodies[0].faces[2].sense=inner
    for index,p in enumerate((part,right)):
        body=p.bodies[0]
        for z in (0,1):
            cap=ProbeFace(body,sense=(z==0) != (index==1))
            cap.surface.PlaneParams=[0,0,1,0,0,z]
            cap.surface.EvaluateAtPoint=lambda x,y,z:[0,0,1]+[0]*8
            cap.GetClosestPointOn=lambda x,y,w,z=z:[x,y,z,x,y]
            body.faces[-1].next=cap;body.faces.append(cap)
        p.Extension=PersistentExtension(p)
    return doc,part,app


def engagement_fixture(root,inner=True):
    with patch('tests.chain_fakes.probe_document',side_effect=lambda:inspection_document(inner)):
        service,app,_=finite_fixture(root)
    cylinders=[]
    for component in app.ActiveDoc.root.children[:2]:
        body=component.model_doc.bodies[0];face=body.faces[2];cylinders.append(face)
        face.edges=[Edge(z=0),Edge(z=1),Edge('line')]
        for edge,cap in zip(face.edges,body.faces[3:5]+[face]):edge.GetTwoAdjacentFaces2=lambda face=face,cap=cap:[face,cap]
        face.GetEdges=lambda face=face:list(face.edges);face.GetEdgeCount=lambda face=face:len(face.edges)
    def call(name,**args):
        r=service.call(name,args);assert r['status']!='error',r;return r
    call('cad_analyze_finite_connections',geometry_analysis_path='outputs/geometry.json',output_path='outputs/finite-before.json')
    call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',finite_analysis_path='outputs/finite-before.json',output_path='outputs/boundary-plan.json')
    receipt=run_batch(service,'outputs/boundary-plan.json','boundaries')
    call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/boundary-index.json')
    call('cad_analyze_finite_connections',geometry_analysis_path='outputs/geometry.json',evidence_index_path='outputs/boundary-index.json',output_path='outputs/finite.json')
    return service,app,cylinders
