"""Document display and occurrence visibility operations, executed on the STA."""
from pathlib import Path

from cadkin._vendor.sw_mcp import call, value
from cadkin.errors import ToolFailure, success

# Resolve enum values from the running installation's swconst.tlb, not guessed IDs.
DISPLAY_PREFERENCES = {
    "planes": "swDisplayPlanes",
    "axes": "swDisplayAxes",
    "temporary_axes": "swDisplayTemporaryAxes",
    "sketches": "swDisplaySketches",
    "origins": "swDisplayOrigins",
    "coordinate_systems": "swDisplayCoordSystems",
}
ALL_REFERENCE = "all_reference_geometry"
HIDE_ALL = "swViewDisplayHideAllTypes"
NO_OPTION = "swDetailingNoOptionSpecified"


def read_constants(library, names):
    """Copy only requested integer constants; no type-library objects escape."""
    result = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        for variable in range(info.GetTypeAttr().cVars):
            descriptor = info.GetVarDesc(variable)
            name = info.GetDocumentation(descriptor.memid)[0]
            if name in names:
                number = descriptor.value
                if not isinstance(number, int) or isinstance(number, bool):
                    raise ValueError(f"Non-integer SOLIDWORKS constant: {name}")
                result[name] = number
        if names <= result.keys():
            return result
    raise ValueError(f"Missing SOLIDWORKS constants: {sorted(names - result.keys())}")


def boolean(raw, member):
    if not isinstance(raw, (bool, int)) or raw not in (0, 1, -1):
        raise ToolFailure("DISPLAY_READ_FAILED", f"{member} did not return a Boolean.")
    return bool(raw)


class DisplayOperations:
    def _display_constants(self):
        try:
            executable = value(self.app, "GetExecutablePath")
            if not isinstance(executable, str) or not executable:
                raise ValueError("SOLIDWORKS did not report its executable path")
            install = Path(executable)
            if install.suffix.lower() == ".exe":
                install = install.parent
            path = install / "swconst.tlb"
            cache = getattr(self, "_display_constant_cache", None)
            if cache is not None and cache[0] == str(path):
                return cache[1]
            if self.runtime is None:
                raise ValueError("COM type-library support is unavailable")
            pythoncom, _ = self.runtime
            # REGKIND_NONE: read the installed library without registration or makepy.
            library = pythoncom.LoadTypeLibEx(str(path), pythoncom.REGKIND_NONE)
            names = {*DISPLAY_PREFERENCES.values(), HIDE_ALL, NO_OPTION}
            constants = read_constants(library, names)
            self._display_constant_cache = (str(path), constants)
            return constants
        except Exception as exc:
            raise ToolFailure("DISPLAY_CONSTANTS_UNAVAILABLE", "Cannot read display enums from the running SOLIDWORKS installation's swconst.tlb. Check the installation; no display setting was changed.", reason=str(exc)) from exc

    def _display_document(self, token=None):
        doc, info = self._document(token)
        if info["document_type"] not in ("part", "assembly"):
            raise ToolFailure("UNSUPPORTED_DOCUMENT_TYPE", "Reference display tools support parts and assemblies.")
        constants = self._display_constants()
        return doc, info, value(doc, "Extension"), constants

    @staticmethod
    def _toggle(extension, constants, name):
        return boolean(call(extension, "GetUserPreferenceToggle", constants[name], constants[NO_OPTION]), name)

    def sw_get_display_state(self):
        doc, info, extension, constants = self._display_document()
        hidden = self._toggle(extension, constants, HIDE_ALL)
        settings = {name: self._toggle(extension, constants, enum) for name, enum in DISPLAY_PREFERENCES.items()}
        self._check_current(info)
        return success({"document": info, "hide_all_reference_geometry": hidden,
                        "visibility": settings,
                        "display_allowed": {name: shown and not hidden for name, shown in settings.items()},
                        "scope": "Document category filters, not individual feature visibility or pixel visibility."})

    def sw_set_display_visibility(self, expected_document_token, target, visible):
        doc, info, extension, constants = self._display_document(expected_document_token)
        enum = HIDE_ALL if target == ALL_REFERENCE else DISPLAY_PREFERENCES[target]
        hidden = self._toggle(extension, constants, HIDE_ALL)
        if visible and target != ALL_REFERENCE and hidden:
            raise ToolFailure("DISPLAY_BLOCKED", "Hide All Types is enabled. Explicitly enable all_reference_geometry first if desired; this can reveal other categories too.")
        before = self._toggle(extension, constants, enum)
        desired = not visible if target == ALL_REFERENCE else visible
        self._check_current(info)
        if before != desired:
            # False may be the resulting off state, NOT an API failure. Read back.
            call(extension, "SetUserPreferenceToggle", constants[enum], constants[NO_OPTION], desired)
        actual = self._toggle(extension, constants, enum)
        self._check_current(info)
        if actual != desired:
            raise ToolFailure("DISPLAY_MISMATCH", "The display preference readback differs from the requested state.", target=target, requested=visible, actual=not actual if target == ALL_REFERENCE else actual)
        value(doc, "GraphicsRedraw2")
        self._check_current(info)
        return success({"document": self._info(doc), "target": target,
                        "previous_visible": not before if target == ALL_REFERENCE else before,
                        "visible": visible, "changed": before != actual, "saved": False,
                        "verification": "Document filter readback matches; individually hidden features remain hidden. Check the graphics window."})

    def sw_zoom_to_fit(self, expected_document_token):
        doc, info = self._document(expected_document_token)
        value(doc, "ViewZoomtofit2")
        value(doc, "GraphicsRedraw2")
        self._check_current(info)
        return success({"document": self._info(doc), "saved": False,
                        "verification": "Zoom-to-fit API completed without requesting a new orientation; check the graphics window."})

    def _visibility_target(self, token, occurrence_path):
        doc, info = self._document(token)
        if info["document_type"] != "assembly":
            raise ToolFailure("NOT_ASSEMBLY", "Component visibility requires an assembly; multibody-part bodies are not components.")
        nodes, errors, objects = self._walk(doc, 10000, 64)
        incomplete = {"COMPONENT_LIMIT", "DEPTH_LIMIT", "CHILDREN_READ_FAILED", "INVALID_INSTANCE_NAME"}
        if any(error["code"] in incomplete or
               (error["code"] == "COMPONENT_READ_FAILED" and error.get("field") == "name")
               for error in errors):
            raise ToolFailure("COMPONENT_LOOKUP_INCOMPLETE", "The instance traversal is incomplete or ambiguous; cannot verify a unique visibility target.", traversal_errors=errors)
        component = objects.get(occurrence_path)
        if component is None:
            raise ToolFailure("COMPONENT_NOT_FOUND", "No unique component matches the full occurrence path.", traversal_errors=errors)
        by_path = {node["occurrence_path"]: node for node in nodes}
        chain, node = [], by_path[occurrence_path]
        while node is not None:
            if node["read_status"] != "ok" or node["suppression_state"] not in (2, 3):
                raise ToolFailure("UNRESOLVED_COMPONENT", "Resolve the target and its parents before changing visibility.", occurrence_path=node["occurrence_path"])
            current = objects.get(node["occurrence_path"])
            if current is None:
                raise ToolFailure("COMPONENT_NOT_FOUND", "A parent occurrence is ambiguous or unavailable.")
            raw = value(current, "Visible")
            if not isinstance(raw, int) or raw not in (0, 1):
                raise ToolFailure("DISPLAY_READ_FAILED", "Component visibility is unknown.", occurrence_path=node["occurrence_path"])
            chain.append((node["occurrence_path"], bool(raw)))
            node = by_path.get(node["parent_occurrence_path"])
        self._check_current(info)
        return doc, info, component, chain

    @staticmethod
    def _visibility_data(info, occurrence_path, chain):
        parents = [path for path, shown in chain[1:] if not shown]
        return {"document": info, "occurrence_path": occurrence_path, "visible": chain[0][1],
                "hidden_parent_paths": parents, "visible_with_parents": chain[0][1] and not parents,
                "scope": "Occurrence display flags in the active context, not occlusion or pixel visibility."}

    def sw_get_component_visibility(self, expected_document_token, occurrence_path):
        _, info, _, chain = self._visibility_target(expected_document_token, occurrence_path)
        return success(self._visibility_data(info, occurrence_path, chain))

    def sw_set_component_visibility(self, expected_document_token, occurrence_path, visible):
        doc, info, component, chain = self._visibility_target(expected_document_token, occurrence_path)
        parents = [path for path, shown in chain[1:] if not shown]
        if visible and parents:
            raise ToolFailure("PARENT_HIDDEN", "The parent assembly is hidden. Show the intended parent explicitly first.", hidden_parent_paths=parents)
        previous = chain[0][1]
        self._check_current(info)
        if previous != visible:
            # swComponentHidden=0, swComponentVisible=1 (IComponent2.Visible).
            component.Visible = 1 if visible else 0
        # Rewalk/read the actual occurrence, including parent state, after mutation.
        _, _, _, after = self._visibility_target(expected_document_token, occurrence_path)
        if after[0][1] != visible or (visible and any(not shown for _, shown in after[1:])):
            raise ToolFailure("DISPLAY_MISMATCH", "Component/parent visibility readback differs from the requested state.", occurrence_path=occurrence_path)
        value(doc, "GraphicsRedraw2")
        self._check_current(info)
        return success({**self._visibility_data(self._info(doc), occurrence_path, after),
                        "previous_visible": previous, "changed": previous != after[0][1], "saved": False})
