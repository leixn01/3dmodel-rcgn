"""Small finite-box CAD substitute; never part of production or real-CAD evidence."""
import math

from tests.evidence_fakes import Part
from tests.sw_fakes import Component, Document, App, pose


def distance_document():
    children = [Component(name) for name in ('base-1', 'slider-1', 'shaft-1', 'cap-1')]
    geometry = [[0, 0, 0, 1, 1, 1], [1.00005, 0, 0, 2, 1, 1], [2.02, 0, 0, 3, 1, 1], [5, 0, 0, 6, 1, 1]]
    part = Part()
    for component, box in zip(children, geometry):
        component.model_doc = part
        component.Transform2 = pose(x=box[0])
        component.box, component.geometry_box = list(box), list(box)
    doc = Document(children=children)
    doc.editing_self = True
    doc.IsEditingSelf = lambda: doc.editing_self
    doc.distance_calls = []
    def closest(left, right, p1, p2):
        doc.distance_calls.append((left.Name2, right.Name2))
        a, b = left.geometry_box, right.geometry_box
        x, y = [], []
        for i in range(3):
            if a[i + 3] < b[i]: x.append(a[i + 3]); y.append(b[i])
            elif b[i + 3] < a[i]: x.append(a[i]); y.append(b[i + 3])
            else: x.append(max(a[i], b[i])); y.append(max(a[i], b[i]))
        p1.value, p2.value = tuple(x), tuple(y)
        return math.dist(x, y)
    doc.ClosestDistance = closest
    return doc, App(doc)
