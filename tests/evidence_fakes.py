"""Explicit evidence fixtures, never used by the installed package."""
from types import SimpleNamespace
from tests.sw_fakes import Document


class Surface:
    def __init__(self, params=None, cylindrical=True):
        self.CylinderParams = [0, 0, 0, 0, 0, 1, 0.01] if params is None else params
        self.cylindrical = cylindrical

    def IsCylinder(self): return self.cylindrical


class Face:
    def __init__(self, surface):
        self.surface = surface
        self.next = None

    def GetSurface(self): return self.surface
    def GetNextFace(self): return self.next


class Body:
    def __init__(self, surfaces):
        self.faces = [Face(s) for s in surfaces]
        for left, right in zip(self.faces, self.faces[1:]): left.next = right

    def GetFirstFace(self): return self.faces[0] if self.faces else None


class Part(Document):
    def __init__(self, bodies=None):
        super().__init__(kind=1, title='Definition', children=[])
        self.bodies = [Body([Surface(cylindrical=False), Surface()])] if bodies is None else bodies
        self.body_calls = []

    def GetBodies2(self, body_type, visible_only):
        assert (body_type, visible_only) == (-1, False)
        self.body_calls.append((body_type, visible_only))
        return self.bodies


class MateEntity:
    def __init__(self, component=None, params=None):
        self.ReferenceType2 = 2  # swSelFACES; not a cylinder/plane classifier.
        self.ReferenceComponent = component
        self.EntityParams = [0, 0, 0, 0, 0, 1, 0.01, 0] if params is None else params

    def GetEntityParamsSize(self): return len(self.EntityParams)


class Mate:
    Type = 1
    Alignment = 0

    def __init__(self, entities): self.entities = entities
    def GetMateEntityCount(self): return len(self.entities)
    def MateEntity(self, index): return self.entities[index]


def evidence_document():
    doc = Document()
    first, second, parent = doc.root.children
    first.fixed = True
    first.mates = [Mate([MateEntity(first), MateEntity(second)])]
    first.model_doc = Part()
    second.model_doc = first.model_doc
    parent.model_doc = Document(title='Subassembly')
    parent.children[0].model_doc = Part()
    return doc
