"""Transport-independent SOLIDWORKS tool catalogue and dispatch."""
from pathlib import Path

from cadkin.adapters.sta import StaWorker
from cadkin.errors import ToolFailure, failure
from cadkin._vendor.sw_mcp import NAMED_VIEWS

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
