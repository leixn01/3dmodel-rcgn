"""Small COM-shaped fakes for unit/transport tests, never production fallback."""
from types import SimpleNamespace

# Arbitrary test-only IDs: production must load names from the installed typelib.
TEST_CONSTANTS = {name: 1000 + index for index, name in enumerate((
    'swDisplayPlanes', 'swDisplayAxes', 'swDisplayTemporaryAxes', 'swDisplaySketches',
    'swDisplayOrigins', 'swDisplayCoordSystems', 'swViewDisplayHideAllTypes',
    'swDetailingNoOptionSpecified'))}


class ConstantLibrary:
    def __init__(self, constants=None):
        self.constants = list((TEST_CONSTANTS if constants is None else constants).items())

    def GetTypeInfoCount(self): return 1
    def GetTypeInfo(self, index): return self
    def GetTypeAttr(self): return SimpleNamespace(cVars=len(self.constants))
    def GetVarDesc(self, index): return SimpleNamespace(memid=index, value=self.constants[index][1])
    def GetDocumentation(self, index): return (self.constants[index][0],)


class DisplayExtension:
    def __init__(self):
        self.settings = {number: True for name, number in TEST_CONSTANTS.items()}
        self.settings[TEST_CONSTANTS['swViewDisplayHideAllTypes']] = False
        self.writes = []
        self.ignore_writes = False

    def GetUserPreferenceToggle(self, enum, option):
        assert option == TEST_CONSTANTS['swDetailingNoOptionSpecified']
        return self.settings[enum]

    def SetUserPreferenceToggle(self, enum, option, enabled):
        assert option == TEST_CONSTANTS['swDetailingNoOptionSpecified']
        self.writes.append((enum, enabled))
        if not self.ignore_writes:
            self.settings[enum] = enabled
        return enabled  # A successful hide returns False.


class Component:
    def __init__(self, name, children=(), state=2, fail_children=False):
        self.Name2 = name
        self.children = children
        self.state = state
        self.fail_children = fail_children
        self.ReferencedConfiguration = 'Default'
        self.selection = None
        self._visible = 1
        self.visibility_writes = []
        self.ignore_visibility_writes = False

    @property
    def Visible(self): return self._visible

    @Visible.setter
    def Visible(self, state):
        self.visibility_writes.append(state)
        if not self.ignore_visibility_writes:
            self._visible = state

    def GetPathName(self):
        return 'C:/model/repeated.sldprt'

    def GetSuppression2(self):
        return self.state

    def IsSuppressed(self):
        return self.state == 0

    def GetChildren(self):
        if self.fail_children:
            raise RuntimeError('test unreadable children')
        return self.children

    def Select4(self, append, data, popup):
        assert not append and not popup
        self.selection.selected = [self]
        return True


class Selection:
    def __init__(self):
        self.selected = []

    def GetSelectedObjectCount2(self, mark):
        assert mark == -1
        return len(self.selected)

    def CreateSelectData(self):
        return object()

    def GetSelectedObjectsComponent4(self, index, mark):
        assert (index, mark) == (1, -1)
        return self.selected[0] if self.selected else None


class Document:
    def __init__(self, kind=2, title='Assembly', children=None):
        self.kind, self.title = kind, title
        self.path = ''
        self.dirty = False
        self.view = None
        self.rebuilt = False
        self.zoom_count = 0
        self.Extension = DisplayExtension()
        self.SelectionManager = Selection()
        if children is None:
            children = [Component('rail-1'), Component('rail-2'),
                        Component('slide-1', [Component('slide-1/block-1')])]
        self.root = Component('root', children)
        self.ConfigurationManager = SimpleNamespace(ActiveConfiguration=SimpleNamespace(
            Name='Default', GetRootComponent3=lambda resolve: None if resolve else self.root))
        stack = list(children)
        while stack:
            child = stack.pop()
            child.selection = self.SelectionManager
            stack.extend(child.children)

    def GetType(self):
        return self.kind

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return self.path

    def GetSaveFlag(self):
        return self.dirty

    def ShowNamedView2(self, name, number):
        assert name == ''
        self.view = number

    def ViewZoomtofit2(self):
        self.zoom_count += 1

    def GraphicsRedraw2(self):
        pass

    def ClearSelection2(self, all):
        assert all
        self.SelectionManager.selected = []

    def EditRebuild3(self):
        self.rebuilt = self.dirty = True
        return True


class App:
    RevisionNumber = 'test-only'

    def GetExecutablePath(self):
        return 'C:/SOLIDWORKS/sldworks.exe'

    def __init__(self, doc):
        self.ActiveDoc = doc
        self.opened = Document()
        self.activation_options = None
        self.load_args = None
        self.fail_activation = False

    def OpenDoc6(self, path, kind, options, config, errors, warnings):
        assert options == 1
        self.opened.path = path
        self.opened.kind = kind
        return self.opened

    def GetImportFileData(self, path):
        return None

    def LoadFile4(self, path, args, imported, errors):
        self.load_args = args
        self.opened.path = path
        self.ActiveDoc = self.opened
        return self.opened

    def ActivateDoc3(self, name, preferences, options, errors):
        self.activation_options = options
        if self.fail_activation:
            return None
        self.ActiveDoc = self.opened
        return self.opened


def runtime():
    def load_library(path, kind):
        assert path.replace('\\', '/') == 'C:/SOLIDWORKS/swconst.tlb'
        assert kind == 2
        return ConstantLibrary()
    pythoncom = SimpleNamespace(VT_BYREF=16384, VT_I4=3, VT_DISPATCH=9,
                                REGKIND_NONE=2, LoadTypeLibEx=load_library)
    client = SimpleNamespace(VARIANT=lambda kind, val: SimpleNamespace(value=val))
    return pythoncom, client
