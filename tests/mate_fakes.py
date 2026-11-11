"""Explicit root-feature fixtures; not installed or used by production."""
from tests.sw_fakes import App
from tests.evidence_fakes import Mate, MateEntity


class Feature:
    def __init__(self, fid, name, kind, mate=None, children=(), suppressed=False, error=0, rolled_back=False):
        self.fid, self.Name, self.kind, self.mate = fid, name, kind, mate
        self.children = list(children)
        self.next = None
        self.subnext = None
        self.suppressed, self.error, self.rolled_back = suppressed, error, rolled_back
        self.state_calls = 0
        for a, b in zip(self.children, self.children[1:]): a.subnext = b

    def GetID(self): return self.fid
    def GetTypeName2(self): return self.kind
    def GetNextFeature(self): return self.next
    def GetFirstSubFeature(self): return self.children[0] if self.children else None
    def GetNextSubFeature(self): return self.subnext
    def GetSpecificFeature2(self): return self.mate
    def IsSuppressed2(self, config, empty):
        assert config == 1 and empty.value is None
        self.state_calls += 1
        return [self.suppressed]
    def GetErrorCode2(self, warning):
        warning.value = bool(self.error)
        return self.error
    def IsRolledBack(self): return self.rolled_back


class MateApp(App):
    def IsSame(self, a, b): return 1 if a is b else 0


def attach_features(doc):
    a, b, parent = doc.root.children
    records = [Feature(11, 'Concentric1', 'MateConcentric', Mate([MateEntity(a), MateEntity(b)])),
               Feature(12, 'Parallel1', 'MateParallel', Mate([MateEntity(a), MateEntity(b)]), suppressed=True),
               Feature(13, 'Distance1', 'MateDistanceDim', Mate([MateEntity(b), MateEntity(parent)]), error=7)]
    records[1].mate.Type = 3
    records[2].mate.Type = 5
    group = Feature(10, 'Mates', 'MateGroup', children=records)
    first = Feature(1, 'Origin', 'OriginProfileFeature')
    first.next = group
    doc.FirstFeature = lambda: first
    return group, records
