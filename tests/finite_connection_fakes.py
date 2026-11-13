"""Analytic boundary fixtures, explicit test-only CAD objects."""
from types import SimpleNamespace
from tests.geometry_connection_fakes import geometry_fixture


class Edge:
    def __init__(self,kind='circle',z=0):
        self.kind=kind; self.z=z
        self.CircleParams=[0,0,z,0,0,1,.01]
    def GetCurve(self):return self
    def IsLine(self):return self.kind=='line'
    def IsCircle(self):return self.kind=='circle'
    def GetStartVertex(self):return SimpleNamespace(GetPoint=lambda:[.01,0,0])
    def GetEndVertex(self):return SimpleNamespace(GetPoint=lambda:[.01,0,1])


def finite_fixture(root):
    service,app=geometry_fixture(root,distances=True,faces=True)
    face=app.ActiveDoc.root.children[0].model_doc.bodies[0].faces[2]
    face.edges=[Edge(z=0),Edge(z=1),Edge('line')]
    face.GetEdgeCount=lambda:len(face.edges)
    face.GetEdges=lambda:list(face.edges)
    r=service.call('cad_analyze_geometric_connections',{'target_graph_path':'outputs/target.json',
        'distance_tolerance_mm':.1,'angle_tolerance_deg':.1,'output_path':'outputs/geometry.json'})
    assert r['status']!='error',r
    return service,app,face
