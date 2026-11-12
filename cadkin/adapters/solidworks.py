"""Windows SOLIDWORKS COM adapter. Construct and use only on the STA worker."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from cadkin._vendor.sw_mcp import NAMED_VIEWS, call, value
from cadkin.errors import ToolFailure, success
from cadkin.adapters.display import DisplayOperations
from cadkin.adapters.spatial import SpatialOperations
from cadkin.adapters.session import SessionOperations
from cadkin.adapters.evidence import EvidenceOperations
from cadkin.adapters.constraints import ConstraintOperations
from cadkin.adapters.cylinders import CylinderOperations
from cadkin.adapters.mate_inventory import MateInventoryOperations
from cadkin.adapters.mate_faces import MateFaceOperations
from cadkin.adapters.component_distance import ComponentDistanceOperations
from cadkin.adapters.faces import FaceOperations
from cadkin.adapters.face_probe import FaceProbeOperations

DOC_TYPES = {1: "part", 2: "assembly", 3: "drawing"}
NATIVE_TYPES = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}


class SolidWorksAdapter(DisplayOperations, SpatialOperations, SessionOperations, EvidenceOperations, ConstraintOperations, CylinderOperations, MateInventoryOperations, MateFaceOperations, ComponentDistanceOperations, FaceOperations, FaceProbeOperations):
    def __init__(self, root=None, app=None, runtime=None):
        self.root = Path(root or Path.cwd()).resolve()
        self.app = app
        self.runtime = runtime
        self.process_id = "test" if app is not None else None
        self._owns_com = False
        self._launch_uncertain = False
        if app is None:
            if sys.platform != "win32":
                raise ToolFailure("UNSUPPORTED_PLATFORM", "Run this MCP server with Windows Python on the computer running SOLIDWORKS.")
            try:
                import pythoncom
                import win32com.client
                import win32com.client.dynamic
            except ImportError as exc:
                raise ToolFailure("MISSING_DEPENDENCY", 'Install dependencies with python -m pip install -e ".[solidworks]".') from exc
            self.runtime = (pythoncom, win32com.client)
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
            self._owns_com = True

    def close(self):
        self.app = None
        if self._owns_com:
            self.runtime[0].CoUninitialize()
            self._owns_com = False

    def _running_processes(self):
        tasklist = Path(os.environ["SystemRoot"]) / "System32" / "tasklist.exe"
        try:
            completed = subprocess.run([str(tasklist), "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
                                       capture_output=True, text=True, encoding="mbcs", check=True, timeout=10)
            processes = [row for row in csv.reader(completed.stdout.splitlines())
                         if row and row[0].casefold() == "sldworks.exe"]
        except (OSError, subprocess.SubprocessError) as exc:
            raise ToolFailure("PROCESS_QUERY_FAILED", "Could not enumerate SOLIDWORKS processes; connection was not attempted.") from exc
        if any(len(row) < 2 or not row[1].isdigit() for row in processes):
            raise ToolFailure("PROCESS_QUERY_FAILED", "SOLIDWORKS process identifiers could not be read reliably.")
        return [row[1] for row in processes]

    def _connect(self):
        if not self._owns_com:  # Explicit injected adapter, only used by tests.
            return self.app
        processes = self._running_processes()
        if len(processes) > 1:
            raise ToolFailure("MULTIPLE_SESSIONS", "This version requires one SOLIDWORKS process. Choose the intended session manually.")
        if not processes:
            self.app = None
            self.process_id = None
            raise ToolFailure("NOT_RUNNING", "SOLIDWORKS is not running. Use sw_start_application to start it, then open the model.")
        detected_pid = processes[0]
        # A newly created COM server may not yet be registered in the ROT. Reuse the
        # retained same-PID reference; never depend on GetActiveObject immediately after launch.
        if self.app is not None and self.process_id == detected_pid:
            try:
                if str(value(self.app, "GetProcessID")) == detected_pid:
                    return self.app
            except Exception:
                pass
            self.app = None
        self.process_id = detected_pid
        _, client = self.runtime
        try:
            active = client.GetActiveObject("SldWorks.Application")
            self.app = client.dynamic.Dispatch(active._oleobj_)
            if str(value(self.app, "GetProcessID")) != self.process_id:
                self.app = None
                raise ToolFailure("SESSION_MISMATCH", "The registered COM instance differs from the detected SOLIDWORKS process.")
        except ToolFailure:
            raise
        except Exception as exc:
            self.app = None
            raise ToolFailure("CONNECT_FAILED", "SOLIDWORKS is running but COM attach failed. Use the same Windows user/elevation and dismiss startup dialogs.", reason=str(exc)) from exc
        return self.app

    def _info(self, doc):
        kind = int(value(doc, "GetType"))
        config = None
        if kind in (1, 2):
            manager = value(doc, "ConfigurationManager")
            active = value(manager, "ActiveConfiguration")
            if active is None:
                raise ToolFailure("NO_CONFIGURATION", "The active model has no readable active configuration.")
            config = str(value(active, "Name"))
        dirty = value(doc, "GetSaveFlag")
        if not isinstance(dirty, (bool, int)):
            raise ToolFailure("DOCUMENT_READ_FAILED", "GetSaveFlag did not return a readable document state.")
        data = {"title": str(value(doc, "GetTitle")), "path": str(value(doc, "GetPathName") or ""),
                "document_type": DOC_TYPES.get(kind, "unknown"), "document_type_code": kind,
                "configuration": config, "dirty": bool(dirty)}
        identity = [self.process_id, data["path"], data["title"], config]
        data["document_token"] = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:24]
        return data

    def _document(self, expected_document_token=None):
        app = self._connect()
        doc = value(app, "ActiveDoc")
        if doc is None:
            raise ToolFailure("NO_ACTIVE_DOCUMENT", "SOLIDWORKS has no active document. Open a model first.")
        info = self._info(doc)
        if expected_document_token is not None and info["document_token"] != expected_document_token:
            raise ToolFailure("DOCUMENT_CHANGED", "The active document/configuration differs from the requested target. Read it again before acting.", document=info)
        return doc, info

    def _check_current(self, info):
        current = value(self.app, "ActiveDoc")
        if current is None or self._info(current)["document_token"] != info["document_token"]:
            raise ToolFailure("DOCUMENT_CHANGED", "The active document/configuration changed during this call; inspect SOLIDWORKS before continuing.")

    def sw_session_status(self):
        conda_prefix = os.environ.get("CONDA_PREFIX")
        runtime = {"python_executable": sys.executable, "python_version": sys.version.split()[0],
                   "python_prefix": sys.prefix, "conda_prefix": conda_prefix,
                   "matches_conda_prefix": (os.path.normcase(os.path.abspath(sys.prefix)) ==
                       os.path.normcase(os.path.abspath(conda_prefix))) if conda_prefix else None}
        try:
            app = self._connect()
        except ToolFailure as exc:
            if exc.code == "NOT_RUNNING":
                return success({"connected": False, "reason": exc.code, "runtime": runtime})
            raise
        return success({"connected": True, "runtime": runtime, "process_id": self.process_id,
                        "revision": str(value(app, "RevisionNumber")),
                        "has_active_document": value(app, "ActiveDoc") is not None})

    def sw_active_document(self):
        _, info = self._document()
        return success(info)

    def _walk(self, doc, max_components, max_depth):
        configuration = value(value(doc, "ConfigurationManager"), "ActiveConfiguration")
        root = call(configuration, "GetRootComponent3", False)
        if root is None:
            raise ToolFailure("ROOT_UNAVAILABLE", "Could not read the active assembly root without resolving extra components.")
        nodes, errors, objects, duplicates = [], [], {}, set()
        def read_children(component):
            result = value(component, "GetChildren")
            if result is None:
                return []
            if not isinstance(result, (tuple, list)):
                raise ToolFailure("INVALID_CHILDREN", "GetChildren returned an unexpected value.")
            return list(result)
        stack = [(component, None, 1) for component in reversed(read_children(root))]
        while stack:
            if len(nodes) >= max_components:
                errors.append({"code": "COMPONENT_LIMIT", "message": "Traversal stopped at max_components; result is incomplete."})
                break
            component, parent, depth = stack.pop()
            node = {"occurrence_path": None, "parent_occurrence_path": parent,
                    "name": None, "file_path": None, "referenced_configuration": None,
                    "suppression_state": None, "is_suppressed": None, "read_status": "ok"}
            def read(field, member):
                try:
                    node[field] = value(component, member)
                except Exception as exc:
                    node["read_status"] = "partial"
                    errors.append({"code": "COMPONENT_READ_FAILED", "field": field,
                                   "node_index": len(nodes), "message": str(exc)})
            for field, member in (("name", "Name2"), ("file_path", "GetPathName"),
                                  ("referenced_configuration", "ReferencedConfiguration"),
                                  ("suppression_state", "GetSuppression2"), ("is_suppressed", "IsSuppressed")):
                read(field, member)
            name = node["name"]
            if not isinstance(name, str) or not name or name in objects or name in duplicates:
                if isinstance(name, str):
                    objects.pop(name, None)
                    duplicates.add(name)
                node["occurrence_path"] = f"@unreadable/{len(nodes)}"
                node["read_status"] = "partial"
                errors.append({"code": "INVALID_INSTANCE_NAME", "node_index": len(nodes),
                               "message": "Missing or duplicate full Name2; synthetic path is not selectable."})
            else:
                node["occurrence_path"] = name
                objects[name] = component
            nodes.append(node)
            try:
                if node["is_suppressed"] is True or node["suppression_state"] in (0, 1, 4, 5):
                    node["read_status"] = "unresolved"
                    errors.append({"code": "UNRESOLVED_COMPONENT", "occurrence_path": node["occurrence_path"],
                                   "message": "Suppressed/lightweight/invalid component retained; subtree completeness is unverified."})
                children = read_children(component)
                if children and depth >= max_depth:
                    node["read_status"] = "partial"
                    errors.append({"code": "DEPTH_LIMIT", "occurrence_path": node["occurrence_path"],
                                   "message": "Child traversal stopped at max_depth."})
                else:
                    stack.extend((child, node["occurrence_path"], depth + 1) for child in reversed(children))
            except Exception as exc:
                node["read_status"] = "partial"
                errors.append({"code": "CHILDREN_READ_FAILED", "occurrence_path": node["occurrence_path"], "message": str(exc)})
        return nodes, errors, objects

    def sw_component_tree(self, max_components=10000, max_depth=64):
        doc, info = self._document()
        if info["document_type"] != "assembly":
            raise ToolFailure("NOT_ASSEMBLY", "The active document is not an assembly. STEP may have imported as a multibody part.", document=info)
        nodes, errors, _ = self._walk(doc, max_components, max_depth)
        self._check_current(info)
        return success({"document": info, "components": nodes, "component_count": len(nodes),
                        "complete": not errors, "counting": "Read occurrence nodes, including subassemblies and unresolved nodes; root excluded."}, errors)

    def sw_set_view(self, expected_document_token, view="isometric", fit=True):
        doc, info = self._document(expected_document_token)
        call(doc, "ShowNamedView2", "", NAMED_VIEWS[view])
        if fit:
            value(doc, "ViewZoomtofit2")
        value(doc, "GraphicsRedraw2")
        self._check_current(info)
        return success({"document": info, "requested_view": view, "fit": fit,
                        "verification": "API calls completed; visual orientation must be checked in SOLIDWORKS."})

    def sw_clear_selection(self, expected_document_token):
        doc, info = self._document(expected_document_token)
        call(doc, "ClearSelection2", True)
        count = int(call(value(doc, "SelectionManager"), "GetSelectedObjectCount2", -1))
        if count:
            raise ToolFailure("SELECTION_NOT_CLEARED", "SOLIDWORKS still reports selected objects.", selected_count=count)
        self._check_current(info)
        return success({"document": info, "selected_count": count})

    def sw_select_component(self, expected_document_token, occurrence_path):
        doc, info = self._document(expected_document_token)
        if info["document_type"] != "assembly":
            raise ToolFailure("NOT_ASSEMBLY", "Component selection requires an assembly.")
        _, errors, objects = self._walk(doc, 10000, 64)
        component = objects.get(occurrence_path)
        if component is None:
            raise ToolFailure("COMPONENT_NOT_FOUND", "No uniquely readable component matches this full occurrence path.", traversal_errors=errors)
        self._check_current(info)
        manager = value(doc, "SelectionManager")
        selection_data = value(manager, "CreateSelectData")
        # IComponent2.Select4 has THREE arguments, unlike IEntity.Select4.
        if not call(component, "Select4", False, selection_data, False):
            raise ToolFailure("SELECTION_FAILED", "SOLIDWORKS refused component selection.")
        count = int(call(manager, "GetSelectedObjectCount2", -1))
        selected = call(manager, "GetSelectedObjectsComponent4", 1, -1)
        if count != 1 or selected is None or value(selected, "Name2") != occurrence_path:
            raise ToolFailure("SELECTION_MISMATCH", "Selection readback does not match the requested component.", selected_count=count)
        self._check_current(info)
        return success({"document": info, "occurrence_path": occurrence_path, "selected_count": count})

    def sw_rebuild(self, expected_document_token):
        doc, info = self._document(expected_document_token)
        if not value(doc, "EditRebuild3"):
            raise ToolFailure("REBUILD_FAILED", "SOLIDWORKS reported rebuild failure; no save was performed.")
        self._check_current(info)
        return success({"document": self._info(doc), "rebuilt": True, "saved": False})

    def _input_path(self, path):
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        try:
            candidate = candidate.resolve(strict=True)
        except OSError as exc:
            raise ToolFailure("INPUT_NOT_FOUND", "The input file does not exist or cannot be accessed.", path=str(candidate)) from exc
        roots = [self.root]
        roots.extend(Path(p).expanduser().resolve() for p in os.environ.get("CADKIN_ALLOWED_ROOTS", "").split(os.pathsep) if p)
        if not any(candidate.is_relative_to(root) for root in roots):
            raise ToolFailure("PATH_OUTSIDE_ROOT", "Input must be under the project or CADKIN_ALLOWED_ROOTS.")
        if not candidate.is_file() or candidate.suffix.lower() not in {*NATIVE_TYPES, ".step", ".stp"}:
            raise ToolFailure("UNSUPPORTED_FILE", "Open a STEP, SLDPRT, SLDASM or SLDDRW file, not a ZIP.")
        return candidate

    def sw_open_document(self, path):
        path = self._input_path(path)
        app = self._connect()
        if self.runtime is None:
            raise ToolFailure("MISSING_RUNTIME", "COM variant support is unavailable.")
        pythoncom, client = self.runtime
        errors = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        suffix = path.suffix.lower()
        if suffix in NATIVE_TYPES:
            doc = call(app, "OpenDoc6", str(path), NATIVE_TYPES[suffix], 1, "", errors, warnings)
        else:
            imported = call(app, "GetImportFileData", str(path))
            if imported is None:
                imported = client.VARIANT(pythoncom.VT_DISPATCH, None)
            doc = call(app, "LoadFile4", str(path), "r", imported, errors)
        if doc is None or int(errors.value):
            raise ToolFailure("OPEN_FAILED", "SOLIDWORKS did not report a clean open/import. Inspect its window before retrying.", load_error=int(errors.value), load_warning=int(warnings.value))
        opened = self._info(doc)
        active = value(app, "ActiveDoc")
        if active is None or self._info(active)["document_token"] != opened["document_token"]:
            activation_error = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            # swDontRebuildActiveDoc = 1; 0 would prompt the user to rebuild.
            activated = call(app, "ActivateDoc3", opened["path"] or opened["title"], False, 1, activation_error)
            if activated is None:
                raise ToolFailure("ACTIVATION_FAILED", "Document opened but could not be activated.", document=opened, activation_error=int(activation_error.value))
        self._check_current(opened)
        notices = []
        if warnings.value:
            notices.append({"code": "LOAD_WARNING", "message": "SOLIDWORKS returned load warnings.", "value": int(warnings.value)})
        return success({"document": opened, "source_path": str(path), "saved": False}, notices)
