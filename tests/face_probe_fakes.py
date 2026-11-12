"""Finite analytic patches for isolated tests; not a CAD kernel or production fallback."""
import math
from types import SimpleNamespace
from tests.sw_fakes import Component, Document, pose
from tests.evidence_fakes import Part
from tests.face_fakes import PersistentExtension
from tests.mate_fakes import MateApp


class ProbeSurface:
    def __init__(self, kind='plane'):
        self.kind = kind
        self.PlaneParams = [1, 0, 0, 0, 0, 0]
        self.CylinderParams = [0, 0, 0, 0, 0, 1, .01]
        self.normal_failure = False

    def IsPlane(self): return self.kind == 'plane'
    def IsCylinder(self): return self.kind == 'cylinder'
    def EvaluateAtPoint(self, x, y, z):
        if self.normal_failure: raise RuntimeError('test normal unavailable')
        n = [1, 0, 0] if self.kind == 'plane' else [x / math.hypot(x, y), y / math.hypot(x, y), 0]
        return n + [0] * 8


class ProbeFace:
    def __init__(self, body, kind='plane', sense=False):
        self.surface, self.body, self.sense, self.next = ProbeSurface(kind), body, sense, None
        self.calls, self.uv_bounds, self.area = [], [0, 1, 0, 1], 1.

    def GetSurface(self): return self.surface
    def GetBody(self): return self.body
    def GetArea(self): return self.area
    def GetUVBounds(self): return self.uv_bounds
    def FaceInSurfaceSense(self): return self.sense
    def GetNextFace(self): return self.next
    def GetClosestPointOn(self, x, y, z):
        self.calls.append((x, y, z))
        if self.surface.kind == 'plane':
            a,b = min(1., max(0., y)), min(1., max(0., z))
            return [0, a, b, a, b]
        r = math.hypot(x, y); radius = self.surface.CylinderParams[-1]
        a,b = (radius, 0) if not r else (radius*x/r, radius*y/r)
        c = min(1., max(0., z))
        return [a,b,c,math.atan2(b,a),c]


class ProbeBody:
    def __init__(self):
        self.kind = 0
        self.faces = [ProbeFace(self), ProbeFace(self, sense=True), ProbeFace(self, 'cylinder')]
        self.faces[-1].uv_bounds = [-math.pi, math.pi, 0, 1]
        for a,b in zip(self.faces,self.faces[1:]): a.next=b
    def GetType(self): return self.kind
    def GetFirstFace(self): return self.faces[0]


def probe_document():
    left, right = Component('plate-1'), Component('plate-2')
    right.Transform2 = pose(x=.00005)
    part = Part([ProbeBody()]); part.Extension = PersistentExtension(part)
    left.model_doc = right.model_doc = part
    doc = Document(children=[left,right]); doc.editing_self = True; doc.IsEditingSelf = lambda:doc.editing_self
    return doc, part, MateApp(doc)
