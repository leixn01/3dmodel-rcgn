"""Finite primitive cap fixtures; explicit synthetic CAD, never a kernel fallback."""
import math
from types import SimpleNamespace
from unittest.mock import patch
from tests.engagement_fakes import engagement_fixture,inspection_document
from tests.geometry_connection_fakes import run_batch


class CircleEdge:
    def __init__(self,r,z,center=(0,0),span=2*math.pi):
        self.CircleParams=[*center,z,0,0,1,r];self.span=span
    def GetCurve(self):return self
    def IsLine(self):return False
    def IsCircle(self):return True
    def GetCurveParams3(self):
        x,y,z,_,_,_,r=self.CircleParams
        return SimpleNamespace(UMinValue=0,UMaxValue=self.span,StartPoint=[x+r,y,z],EndPoint=[x+r*math.cos(self.span),y+r*math.sin(self.span),z])


class LineEdge:
    def __init__(self,a,b):self.a=a;self.b=b
    def GetCurve(self):return self
    def IsLine(self):return True
    def IsCircle(self):return False
    def GetStartVertex(self):return SimpleNamespace(GetPoint=lambda:self.a)
    def GetEndVertex(self):return SimpleNamespace(GetPoint=lambda:self.b)


class Loop:
    def __init__(self,edges,outer=True):self.edges=edges;self.outer=outer
    def IsOuter(self):return self.outer
    def GetEdges(self):return self.edges
    def GetEdgeCount(self):return len(self.edges)


def planar_document(mode):
    doc,part,app=inspection_document()
    for side,component in enumerate(doc.root.children[:2]):
        for cap in component.model_doc.bodies[0].faces[3:5]:
            z=cap.surface.PlaneParams[-1];r=.02
            if mode=='polygon':
                pts=[[-r,-r,z],[r,-r,z],[r,r,z],[-r,r,z]]
                cap.loops=[Loop([LineEdge(a,b) for a,b in zip(pts,pts[1:]+pts[:1])])];cap.area=4*r*r
            else:
                r=.005 if mode=='hole_gap' and side==0 else .02
                cap.loops=[Loop([CircleEdge(r,z)])];cap.area=math.pi*r*r
                if mode in ('annulus','hole_gap') and (mode=='annulus' or side==1):
                    cap.loops.append(Loop([CircleEdge(.01,z)],False));cap.area-=math.pi*.01**2
                if mode=='arc' and side==1:cap.loops[0].edges[0].span=math.pi
            cap.GetLoops=lambda cap=cap:cap.loops;cap.GetLoopCount=lambda cap=cap:len(cap.loops)
    return doc,part,app


def planar_fixture(root,mode='disk'):
    with patch('tests.engagement_fakes.inspection_document',side_effect=lambda inner=True:planar_document(mode)):
        service,app,cylinders=engagement_fixture(root)
    def call(tool,**args):
        r=service.call(tool,args);assert r['status']!='error',r;return r
    call('cad_analyze_surface_engagement',finite_analysis_path='outputs/finite.json',output_path='outputs/engagement-before.json')
    call('cad_plan_evidence_tasks',draft_check_path='outputs/check.json',engagement_analysis_path='outputs/engagement-before.json',output_path='outputs/inspection-plan.json')
    receipt=run_batch(service,'outputs/inspection-plan.json','inspection')
    call('cad_index_evidence',draft_check_path='outputs/check.json',execution_path=receipt,output_path='outputs/inspection-index.json')
    call('cad_analyze_surface_engagement',finite_analysis_path='outputs/finite.json',evidence_index_path='outputs/inspection-index.json',output_path='outputs/engagement.json')
    return service,app
