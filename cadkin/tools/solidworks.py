"""Transport-independent SOLIDWORKS tool catalogue and dispatch."""
from pathlib import Path

from cadkin.adapters.sta import StaWorker
from cadkin.errors import ToolFailure, failure
from cadkin._vendor.sw_mcp import NAMED_VIEWS
from cadkin.adapters.display import DISPLAY_PREFERENCES, ALL_REFERENCE

TOKEN = {"type": "string", "minLength": 24, "maxLength": 24,
         "description": "document_token returned by sw_active_document or sw_component_tree; binds the operation to that document/configuration."}


def spec(name, description, properties=None, required=None, read_only=True):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties or {},
                            "required": required or [], "additionalProperties": False},
            "annotations": {"readOnlyHint": read_only, "destructiveHint": False,
                            "idempotentHint": read_only, "openWorldHint": False}}


TOOLS = [
    spec("sw_session_status", "Attach to one existing SOLIDWORKS process; return revision and active-document availability. Does not launch SOLIDWORKS."),
    spec("sw_active_document", "Read the actual active document, type, configuration, dirty flag and target token. No active document is an error."),
    spec("sw_component_tree", "Read assembly occurrence hierarchy without resolving components. Retains unreadable nodes and marks partial results; not a motion model.",
         {"max_components": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 10000},
          "max_depth": {"type": "integer", "minimum": 1, "maximum": 128, "default": 64}}),
    spec("sw_open_document", "Open/import a STEP or native SOLIDWORKS file and verify the active document. Path is relative to the project or an allowed absolute path. Does not save or close documents; STEP import follows local import settings.",
         {"path": {"type": "string", "minLength": 1}}, ["path"], False),
    spec("sw_set_view", "Set a standard view and optionally zoom to fit in the expected active document. Completes API calls; visual verification remains necessary.",
         {"expected_document_token": TOKEN, "view": {"type": "string", "enum": list(NAMED_VIEWS), "default": "isometric"},
          "fit": {"type": "boolean", "default": True}}, ["expected_document_token"], False),
    spec("sw_select_component", "Replace selection with one assembly component by its full occurrence_path from the tree; verify selection by readback. Does not move geometry.",
         {"expected_document_token": TOKEN, "occurrence_path": {"type": "string", "minLength": 1}},
         ["expected_document_token", "occurrence_path"], False),
    spec("sw_clear_selection", "Clear selections in the expected active document and verify zero selected objects.",
         {"expected_document_token": TOKEN}, ["expected_document_token"], False),
    spec("sw_rebuild", "Rebuild the expected active document and check the API return. May update in-memory geometry and dirty the document; does not save.",
         {"expected_document_token": TOKEN}, ["expected_document_token"], False),
    spec("sw_get_display_state", "Read document visibility filters for planes, axes, temporary axes, sketches, origins and coordinate systems, plus Hide All Types. Does not change individually hidden features."),
    spec("sw_set_display_visibility", "Show/hide a reference category in the current part/assembly, e.g. hide planes (隐藏基准面): target=planes, visible=false. Set an explicit state and verify readback. all_reference_geometry controls the Hide All Types master switch, including annotations; does not force individually hidden features visible or save.",
         {"expected_document_token": TOKEN, "target": {"type": "string", "enum": [*DISPLAY_PREFERENCES, ALL_REFERENCE]},
          "visible": {"type": "boolean"}}, ["expected_document_token", "target", "visible"], False),
    spec("sw_zoom_to_fit", "Fit the current model in the window without requesting a new view orientation. Visual verification remains necessary.",
         {"expected_document_token": TOKEN}, ["expected_document_token"], False),
    spec("sw_get_component_visibility", "Read a uniquely identified assembly occurrence's own visibility and hidden parents. Use the full occurrence_path from the tree. Rejects unresolved targets/parents.",
         {"expected_document_token": TOKEN, "occurrence_path": {"type": "string", "minLength": 1}},
         ["expected_document_token", "occurrence_path"]),
    spec("sw_set_component_visibility", "Show/hide one assembly occurrence by full occurrence_path and verify readback. Does not suppress, resolve, move, delete or save. Showing a child with hidden parents is rejected until the intended parents are explicitly shown.",
         {"expected_document_token": TOKEN, "occurrence_path": {"type": "string", "minLength": 1},
          "visible": {"type": "boolean"}}, ["expected_document_token", "occurrence_path", "visible"], False),
    spec("sw_component_spatial", "Read one assembly occurrence's root/parent transforms, origin and approximate root-axis bounding box in meters and millimeters. Use full occurrence_path. Keeps unavailable fields null; no move, resolve, select, rebuild or save. Origin is not center of mass; box size is not precision part dimensions.",
         {"expected_document_token": TOKEN, "occurrence_path": {"type": "string", "minLength": 1}},
         ["expected_document_token", "occurrence_path"]),
    spec("sw_spatial_inventory", "Read a bounded assembly spatial inventory with instance hierarchy, transforms and approximate bounding boxes. Repeated files remain separate. Partial/truncated/unresolved results are explicit; no auto-resolve or model modification. Save actual returned JSON with file tools, or use CLI --output.",
         {"expected_document_token": TOKEN,
          "max_components": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500},
          "max_depth": {"type": "integer", "minimum": 1, "maximum": 128, "default": 64}},
         ["expected_document_token"]),
]
CATALOG = {tool["name"]: tool for tool in TOOLS}


class SolidWorksTools:
    def __init__(self, root=None, factory=None, timeout=60.0):
        if factory is None:
            from cadkin.adapters.solidworks import SolidWorksAdapter
            root = Path(root or Path.cwd()).resolve()
            factory = lambda: SolidWorksAdapter(root=root)
        self.worker = StaWorker(factory, timeout=timeout)

    def call(self, name, arguments=None):
        try:
            if name not in CATALOG:
                raise ToolFailure("UNKNOWN_TOOL", f"Unknown tool: {name}")
            from jsonschema import Draft202012Validator
            arguments = {} if arguments is None else arguments
            error = next(Draft202012Validator(CATALOG[name]["inputSchema"]).iter_errors(arguments), None)
            if error:
                raise ToolFailure("INVALID_ARGUMENTS", error.message)
            return self.worker.call(name, arguments)
        except Exception as exc:
            return failure(exc)

    def close(self):
        self.worker.close()
