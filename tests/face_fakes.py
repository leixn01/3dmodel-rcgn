"""Persistent/corresponding faces with distinct occurrence objects; test-only."""
from types import SimpleNamespace
from tests.evidence_fakes import Body, Part, Surface
from tests.sw_fakes import Component, Document, pose
from tests.mate_fakes import attach_features, MateApp


class PersistentExtension:
    def __init__(self, part):
        self.refs = {bytes((body + 1, face + 1)): f for body, b in enumerate(part.bodies) for face, f in enumerate(b.faces)}
        self.state = 0

    def GetPersistReference3(self, face):
        return next((key for key, f in self.refs.items() if f is face), None)

    def GetObjectByPersistReference3(self, encoded, state):
        state.value = self.state
        return self.refs.get(bytes(encoded.value))


def face_document(existing=None):
    if existing is None:
        children = [Component('shaft-1'), Component('shaft-2'), Component('rail-1')]
        children[1].Transform2 = pose(z=3)
        children[2].Transform2 = pose(x=0.1)
        doc = Document(children=children)
    else:
        doc = existing
        children = doc.root.children
    # Two distinct cylinder faces with identical parameters: axes do not identify faces.
    part = Part([Body([Surface(), Surface()])])
    part.Extension = PersistentExtension(part)
    def bind(component):
        component.model_doc = part
        component.corresponding = {f: SimpleNamespace(part_face=f, component=component) for f in part.bodies[0].faces}
        component.GetCorrespondingEntity = lambda f: component.corresponding.get(f)
    for component in children[:2]: bind(component)
    if not children[2].children: bind(children[2])
    group, features = attach_features(doc)
    for feature in features:
        for entity in feature.mate.entities:
            component = entity.ReferenceComponent
            entity.Reference = component.GetCorrespondingEntity(part.bodies[0].faces[0]) if hasattr(component, 'GetCorrespondingEntity') else None
    # Second mate involves the other cylindrical face, while preserving suppression.
    for entity in features[1].mate.entities:
        entity.Reference = entity.ReferenceComponent.GetCorrespondingEntity(part.bodies[0].faces[1])
    return doc, part, group, features, MateApp(doc)
