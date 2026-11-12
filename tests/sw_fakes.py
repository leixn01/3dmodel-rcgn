"""Small COM-shaped fakes for unit/transport tests, never production fallback."""
from types import SimpleNamespace


def pose(x=0, y=0, z=0, quarter_turn=False, scale=1):
    axes = [0, 1, 0, -1, 0, 0, 0, 0, 1] if quarter_turn else [1, 0, 0, 0, 1, 0, 0, 0, 1]
    return SimpleNamespace(ArrayData=axes + [x, y, z, scale, 0, 0, 0])

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
        self.Transform2 = pose()
        self.box = [0, 0, 0, 0.1, 0.2, 0.3]
        self.box_calls = []
        self.fixed = False
        self.mates = []
        self.model_doc = None

    def IsFixed(self): return self.fixed

    def GetMates(self): return self.mates

    def GetModelDoc2(self): return self.model_doc

    def GetBox(self, include_reference_planes, include_sketches):
        assert (include_reference_planes, include_sketches) == (False, False)
        self.box_calls.append((include_reference_planes, include_sketches))
        return self.box

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
            children[1].Transform2 = pose(x=0.5)
            children[1].box = [0.5, 0, 0, 0.6, 0.2, 0.3]
            children[2].Transform2 = pose(1, 2, 0, quarter_turn=True)
            children[2].children[0].Transform2 = pose(1, 2.2, 0, quarter_turn=True)
            children[2].children[0].box = [0.9, 2.1, 0, 1.1, 2.3, 0.2]
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
    StartupProcessCompleted = True
    Visible = True
    UserControl = True

    def GetProcessID(self): return 1234

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
    def load_library(path):
        assert path.replace('\\', '/') == 'C:/SOLIDWORKS/swconst.tlb'
        return ConstantLibrary()
    pythoncom = SimpleNamespace(VT_BYREF=16384, VT_I4=3, VT_DISPATCH=9, VT_BOOL=11, VT_EMPTY=0, VT_ARRAY=8192, VT_UI1=17, VT_VARIANT=12,
                                REGKIND_NONE=2, LoadTypeLib=load_library)
    client = SimpleNamespace(VARIANT=lambda kind, val: SimpleNamespace(value=val))
    return pythoncom, client


class SessionHarness:
    """Explicit test-only COM activation/OS process inventory; no real launch."""
    def __init__(self, running=False):
        from unittest.mock import Mock
        from cadkin.adapters.solidworks import SolidWorksAdapter
        self.app = App(None)
        self.running = running
        pythoncom, client = runtime()
        pythoncom.CLSCTX_LOCAL_SERVER = 4
        pythoncom.IID_IDispatch = 'test-IDispatch'
        pythoncom.CoCreateInstance = Mock(side_effect=self.create)
        pythoncom.PumpWaitingMessages = Mock()
        pythoncom.CoUninitialize = Mock()
        client.dynamic = SimpleNamespace(Dispatch=lambda dispatch: dispatch)
        client.GetActiveObject = Mock(side_effect=self.attach)
        self.adapter = SolidWorksAdapter(app=self.app, runtime=(pythoncom, client))
        self.adapter._resolve_application_clsid = Mock(return_value='test-SolidWorks-CLSID')
        self.adapter.app = None
        self.adapter.process_id = None
        self.adapter._owns_com = True
        self.adapter._running_processes = Mock(side_effect=lambda: ['1234'] if self.running else [])
        self.pythoncom, self.client = pythoncom, client

    def create(self, clsid, outer, context, iid):
        assert (clsid, outer, context, iid) == ('test-SolidWorks-CLSID', None, 4, 'test-IDispatch')
        self.running = True
        return self.app

    def attach(self, progid):
        assert progid == 'SldWorks.Application' and self.running
        return SimpleNamespace(_oleobj_=self.app)
