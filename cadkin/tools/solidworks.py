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
    spec("sw_start_application", "Start the registered desktop SOLIDWORKS on Windows when absent, or reuse the single existing process; show the window, retain it after MCP exits, and check StartupProcessCompleted. Use before opening a model when not running. Does not open, save or close documents. Never launch another process after attach failure; inspect licence/recovery dialogs on errors.",
         {"wait_seconds": {"type": "integer", "minimum": 1, "maximum": 120, "default": 120}}, read_only=False),
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
    spec("sw_spatial_inventory", "Read one bounded page of assembly spatial data (default 20). Continue with next_offset and expected_inventory_signature until has_more=false, or use CLI spatial-export to collect all pages. Keep geometry unchanged during collection. include_bounding_boxes=false skips slow GetBox calls. No model modification; a page is not the full inventory.",
         {"expected_document_token": TOKEN,
          "max_components": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500},
          "max_depth": {"type": "integer", "minimum": 1, "maximum": 128, "default": 64},
          "offset": {"type": "integer", "minimum": 0, "maximum": 5000, "default": 0},
          "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
          "include_bounding_boxes": {"type": "boolean", "default": True},
          "expected_inventory_signature": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
         ["expected_document_token"]),
    spec("sw_component_constraints", "Read one occurrence's top-level fixed flag and attached mate records. Nested fixed state stays unknown; raw mate entities remain in their owning-assembly frame with reference names unverified against root paths. Does not solve DOF, infer joints, resolve, select or edit. GetMates failures stay distinct from a valid empty list.",
         {"expected_document_token": TOKEN, "occurrence_path": {"type": "string", "minLength": 1},
          "max_mates": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
          "max_entities": {"type": "integer", "minimum": 1, "maximum": 64, "default": 16}},
         ["expected_document_token", "occurrence_path"]),
    spec("sw_component_cylinders", "Read analytic cylindrical-face axis/radius candidates from a resolved part occurrence. Requires loaded part configuration to match its referenced configuration; never switches it. Definition geometry excludes assembly-level cuts. Returns part and root-frame data with bounded body/face scans, not motion joints or hole classification.",
         {"expected_document_token": TOKEN, "occurrence_path": {"type": "string", "minLength": 1},
          "max_bodies": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
          "max_faces": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500},
          "max_cylinders": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
          "include_face_references": {"type": "boolean", "default": False, "description": "Capture and round-trip persistent part-face references for later live mate-face matching; adds COM reads."}},
         ["expected_document_token", "occurrence_path"]),
    spec("cad_group_components", "Create explainable role candidates from a complete exported spatial inventory JSON. No SOLIDWORKS connection or model modification. Classifies leaf occurrences, retains ambiguous names as pending, and writes a new JSON under outputs/. Optional review_path binds manual decisions to the inventory SHA256; never invent user confirmation.",
         {"inventory_path": {"type": "string", "minLength": 1},
          "output_path": {"type": "string", "minLength": 1},
          "scope_occurrence_path": {"type": "string", "minLength": 1},
          "review_path": {"type": "string", "minLength": 1}},
         ["inventory_path", "output_path"], False),
    spec("sw_mate_inventory", "Read mate features owned by the active root assembly, including suppressed records. Returns feature suppression/error/rollback states, root-frame raw entities and root occurrence identities verified by IsSame. Does not include internal subassembly mates, solve, rebuild or edit. No feature error is not proof that a mate is solved.",
         {"expected_document_token": TOKEN,
          "max_features": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 2000},
          "max_mates": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
          "max_entities": {"type": "integer", "minimum": 1, "maximum": 64, "default": 16},
          "max_depth": {"type": "integer", "minimum": 1, "maximum": 64, "default": 32}},
         ["expected_document_token"]),
    spec("sw_match_mate_faces", "Read current root mates and compare their referenced faces against 1-8 saved cylinder envelopes captured with include_face_references=true. Requires a complete spatial inventory and unchanged document/configuration/poses. Resolves persistent IDs in the referenced part, maps to the occurrence, then compares live CAD object identity. Preserves partial/unsupported evidence; does not infer contact or joints. Save the original envelope for offline cad_review_connections.",
         {"expected_document_token": TOKEN, "inventory_path": {"type": "string", "minLength": 1},
          "cylinder_paths": {"type": "array", "minItems": 1, "maxItems": 8, "uniqueItems": True, "items": {"type": "string", "minLength": 1}},
          "max_candidate_faces": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
          "max_comparisons": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 2000},
          "max_features": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 2000},
          "max_mates": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
          "max_entities": {"type": "integer", "minimum": 1, "maximum": 64, "default": 16},
          "max_depth": {"type": "integer", "minimum": 1, "maximum": 64, "default": 32}},
         ["expected_document_token", "inventory_path", "cylinder_paths"]),
    spec("cad_review_connections", "Associate a saved geometric relation file with a sw_mate_inventory or sw_match_mate_faces envelope. Verifies source hashes, root document/configuration and mapped occurrence poses. Adds candidate-face-pair matches only when both mate entities have live identity evidence bound to the exact cylinder source files. Separates mate feature states; never confirms contact, solving or mechanical joints. Writes a new outputs JSON without connecting COM.",
         {"relations_path": {"type": "string", "minLength": 1},
          "mate_inventory_path": {"type": "string", "minLength": 1},
          "output_path": {"type": "string", "minLength": 1}},
         ["relations_path", "mate_inventory_path", "output_path"], False),
    spec("cad_component_relations", "Compare root-frame cylindrical axes from 2-32 saved sw_component_cylinders envelopes against a complete spatial inventory. Explicit millimeter/degree tolerances produce coaxial/parallel geometric candidates, never confirmed joints. Offline; writes a new outputs JSON with source hashes, metrics and limits. Partial evidence remains partial. Optional grouping_path copies role context bound to the same inventory hash. Keep the source assembly unchanged during capture.",
         {"inventory_path": {"type": "string", "minLength": 1},
          "cylinder_paths": {"type": "array", "minItems": 2, "maxItems": 32, "uniqueItems": True,
                             "items": {"type": "string", "minLength": 1}},
          "output_path": {"type": "string", "minLength": 1},
          "distance_tolerance_mm": {"type": "number", "exclusiveMinimum": 0},
          "angle_tolerance_deg": {"type": "number", "exclusiveMinimum": 0, "maximum": 5},
          "max_pairs": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 10000},
          "max_candidates": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 1000},
          "grouping_path": {"type": "string", "minLength": 1}},
         ["inventory_path", "cylinder_paths", "output_path", "distance_tolerance_mm", "angle_tolerance_deg"], False),
]
CATALOG = {tool["name"]: tool for tool in TOOLS}


class SolidWorksTools:
    def __init__(self, root=None, factory=None, timeout=180.0):
        self.root = Path(root or Path.cwd()).resolve()
        if factory is None:
            from cadkin.adapters.solidworks import SolidWorksAdapter
            factory = lambda: SolidWorksAdapter(root=self.root)
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
            if name == "cad_group_components":
                from cadkin.tools.grouping import group_components
                return group_components(self.root, **arguments)
            if name == "cad_component_relations":
                from cadkin.tools.relations import component_relations
                return component_relations(self.root, **arguments)
            if name == "cad_review_connections":
                from cadkin.tools.connections import connection_review
                return connection_review(self.root, **arguments)
            if name == "sw_match_mate_faces":
                from cadkin.tools.mate_faces import load_face_sources
                arguments = load_face_sources(self.root, **arguments)
            return self.worker.call(name, arguments)
        except Exception as exc:
            return failure(exc)

    def close(self):
        self.worker.close()
