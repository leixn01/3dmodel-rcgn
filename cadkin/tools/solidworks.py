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
          "max_depth": {"type": "integer", "minimum": 1, "maximum": 64, "default": 32},
          "include_reference_geometry": {"type": "boolean", "default": False, "description": "Read direct mate face surface kinds/root parameters with persistent identity round-trip and concentric LockRotation. Extra COM reads; failures remain unknown."}},
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
    spec('sw_component_distance', 'Read the current minimum distance and two witness points for two resolved leaf part occurrences, without changing selection. Uses root-document ClosestDistance with component objects; rejects subassemblies and in-context editing. API failures remain unavailable, never zero. Small/zero distance is not contact, interference or joint confirmation.',
         {'expected_document_token': TOKEN, 'left_occurrence_path': {'type': 'string', 'minLength': 1},
          'right_occurrence_path': {'type': 'string', 'minLength': 1}},
         ['expected_document_token', 'left_occurrence_path', 'right_occurrence_path']),
    spec('cad_proximity_candidates', 'Build an offline measurement worklist from complete spatial inventory approximate root boxes. Explicit box-gap threshold is a screening hint only, not clearance or contact. Keeps unknown boxes, separate occurrences and pair/output limits; writes a new outputs JSON. No COM or mate data required.',
         {'inventory_path': {'type': 'string', 'minLength': 1}, 'output_path': {'type': 'string', 'minLength': 1},
          'max_box_gap_mm': {'type': 'number', 'minimum': 0},
          'occurrence_paths': {'type': 'array', 'minItems': 2, 'maxItems': 200, 'uniqueItems': True, 'items': {'type': 'string', 'minLength': 1}},
          'max_pairs': {'type': 'integer', 'minimum': 1, 'maximum': 200000, 'default': 20000},
          'max_candidates': {'type': 'integer', 'minimum': 1, 'maximum': 2000, 'default': 200}},
         ['inventory_path', 'output_path', 'max_box_gap_mm'], False),
    spec('cad_review_proximity', 'Review saved component-distance envelopes against a source-bound proximity worklist, offline. Explicit contact tolerance classifies near-contact candidates, separated measurements, unresolved and unmeasured pairs. Does not prove contact/interference/fit or motion joints and does not match specific cylinder faces. Writes a new outputs JSON.',
         {'proximity_path': {'type': 'string', 'minLength': 1}, 'output_path': {'type': 'string', 'minLength': 1},
          'distance_paths': {'type': 'array', 'minItems': 1, 'maxItems': 200, 'uniqueItems': True, 'items': {'type': 'string', 'minLength': 1}},
          'contact_tolerance_mm': {'type': 'number', 'minimum': 0}},
         ['proximity_path', 'distance_paths', 'output_path', 'contact_tolerance_mm'], False),
    spec('sw_component_faces', 'Read a bounded face catalog for one resolved part occurrence: plane/cylinder parameters, area, UV bounds, face sense and verified persistent IDs. Other surfaces are catalogued but not probed. Definition geometry excludes assembly-level features; does not change selection.',
         {'expected_document_token': TOKEN, 'occurrence_path': {'type': 'string', 'minLength': 1},
          'max_bodies': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20},
          'max_faces': {'type': 'integer', 'minimum': 1, 'maximum': 1000, 'default': 200}},
         ['expected_document_token', 'occurrence_path']),
    spec('sw_probe_face_pair', 'Probe one source-bound plane/cylinder face on each of two occurrences using finite-face closest-point queries from explicit root-frame seeds. Returns sampled gaps and oriented point normals, NOT a certified global minimum or contact. Uses part definitions placed by occurrence transforms; no assembly cuts, selection changes or model edits.',
         {'expected_document_token': TOKEN,
          'left': {'type': 'object', 'additionalProperties': False, 'properties': {'face_inventory_path': {'type': 'string', 'minLength': 1}, 'body_index': {'type': 'integer', 'minimum': 0}, 'face_index': {'type': 'integer', 'minimum': 0}}, 'required': ['face_inventory_path', 'body_index', 'face_index']},
          'right': {'type': 'object', 'additionalProperties': False, 'properties': {'face_inventory_path': {'type': 'string', 'minLength': 1}, 'body_index': {'type': 'integer', 'minimum': 0}, 'face_index': {'type': 'integer', 'minimum': 0}}, 'required': ['face_inventory_path', 'body_index', 'face_index']},
          'seed_points_root_mm': {'type': 'array', 'minItems': 1, 'maxItems': 8, 'items': {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': {'type': 'number'}}},
          'max_iterations': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
          'convergence_tolerance_mm': {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 1, 'default': 0.001}},
         ['expected_document_token', 'left', 'right', 'seed_points_root_mm']),
    spec('cad_review_face_contacts', 'Review saved local face probes offline using explicit gap/angle thresholds and verified raw source hashes. Recomputes coordinates, normals and gaps; never treats a large sampled gap as proof of separation. Writes a new outputs JSON; no CAD connection or automatic contact/joint confirmation.',
         {'probe_paths': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'uniqueItems': True, 'items': {'type': 'string', 'minLength': 1}},
          'output_path': {'type': 'string', 'minLength': 1}, 'contact_tolerance_mm': {'type': 'number', 'minimum': 0},
          'angle_tolerance_deg': {'type': 'number', 'minimum': 0, 'maximum': 90}},
         ['probe_paths', 'output_path', 'contact_tolerance_mm', 'angle_tolerance_deg'], False),
    spec('cad_build_chain_evidence', 'Compile an explicit 2–50 leaf-occurrence scope into an offline chain evidence dossier. Replays source grouping/connection/proximity/face reviews and hashes; preserves every scope pair, unknowns, boundary links and differing measurement scopes. No CAD, rigid-body merge, joint inference or removal planning.',
         {'inventory_path': {'type': 'string', 'minLength': 1}, 'output_path': {'type': 'string', 'minLength': 1},
          'chain_name': {'type': 'string', 'minLength': 1, 'maxLength': 100},
          'occurrence_paths': {'type': 'array', 'minItems': 2, 'maxItems': 50, 'uniqueItems': True, 'items': {'type': 'string', 'minLength': 1}},
          'evidence_paths': {'type': 'array', 'maxItems': 20, 'uniqueItems': True, 'items': {'type': 'string', 'minLength': 1}},
          'grouping_path': {'type': 'string', 'minLength': 1}, 'grouping_review_path': {'type': 'string', 'minLength': 1}},
         ['inventory_path', 'occurrence_paths', 'chain_name', 'output_path'], False),
    spec('cad_apply_chain_review', 'Legacy optional compatibility tool, excluded from the automatic decomposition workflow. Apply explicit attributed human confirmed/rejected/pending/conflict declarations to an exact chain dossier SHA256, offline. Revalidates evidence and acknowledges review flags; unmentioned pairs stay pending. Human confirmation does not certify CAD geometry/joints or clear partial evidence. Writes a new file, never moves parts.',
         {'chain_path': {'type': 'string', 'minLength': 1}, 'review_path': {'type': 'string', 'minLength': 1}, 'output_path': {'type': 'string', 'minLength': 1}},
         ['chain_path', 'review_path', 'output_path'], False),
    spec('cad_list_mechanism_templates', 'List bundled pinned structural reference assets; no CAD, USD import or network. Heldout evaluation assets are excluded by default. Tags are retrieval hints, not inferred joints.',
         {'query': {'type':'string','maxLength':200}, 'include_heldout': {'type':'boolean'}}, [], True),
    spec('cad_extract_mechanism_template', 'Extract authored rigid bodies, fixed/prismatic/revolute joints, endpoint frames and limits from one bundled template ID or standalone project USD file, offline. Writes a new JSON graph with provenance and risks. Does not infer CAD mechanisms.',
         {'template_id': {'type':'string','minLength':1}, 'asset_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1}}, ['output_path'], False),
    spec('cad_compare_mechanism_graphs', 'Score graph connections and typed joints using explicit hash-bound one-to-one body correspondence, offline. Retains missing/extra joints and coverage; does not infer matches or assess axes, limits, motion or physical correctness.',
         {key: {'type':'string','minLength':1} for key in ('reference_path','candidate_path','correspondence_path','output_path')},
         ['reference_path','candidate_path','correspondence_path','output_path'], False),

    spec('cad_build_target_graph', 'Replay a base chain dossier and its CAD sources into an occurrence graph with evidence support, geometric axes, source coverage and conflicts. Automatically includes relations bound by connection files; optional standalone relation files. Offline; no joint confirmation, human review or rigid merging.',
         {'chain_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1},
          'relation_paths': {'type':'array','maxItems':20,'uniqueItems':True,'items':{'type':'string','minLength':1}}},
         ['chain_path','output_path'], False),
    spec('cad_match_mechanism_templates', 'Replay a target graph and search bounded connected windows of pinned reference mechanisms for ranked occurrence mappings and conditional joint hypotheses. Discloses support, relative-axis checks, ties, source gaps and search limits. Scores are not probabilities; no motion validation or copied target limits.',
         {'target_graph_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1},
          'template_ids': {'type':'array','minItems':1,'maxItems':8,'uniqueItems':True,'items':{'type':'string','minLength':1}},
          'include_heldout': {'type':'boolean'}, 'pattern_size': {'type':'integer','minimum':2,'maximum':6,'default':3},
          'max_candidates': {'type':'integer','minimum':1,'maximum':20,'default':5},
          'max_states': {'type':'integer','minimum':1,'maximum':100000,'default':20000},
          'beam_width': {'type':'integer','minimum':1,'maximum':1000,'default':50},
          'angle_tolerance_deg': {'type':'number','exclusiveMinimum':0,'maximum':45,'default':10}},
         ['target_graph_path','output_path'], False),

    spec('cad_build_rigid_candidates', 'Replay a target graph into bounded alternative rigid membership hypotheses. Always retains the unmerged baseline; clean active lock mates can form groups, contact bridges remain weak alternatives. Preserves every occurrence, conflicts and omitted groups. Offline, no CAD mutation or human review.',
         {'target_graph_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1},
          'max_group_size': {'type':'integer','minimum':2,'maximum':20,'default':8},
          'max_partitions': {'type':'integer','minimum':1,'maximum':12,'default':8},
          'include_contact_hypotheses': {'type':'boolean','default':True}},
         ['target_graph_path','output_path'], False),
    spec('cad_analyze_constraints', 'Replay a target graph and combine exact root mate constraints per occurrence pair and per source snapshot. Produces traceable local fixed/revolute/prismatic candidates, conflicts and missing evidence; target type/DOF remain unknown. Templates and geometric proximity cannot supply constraints. Offline; writes a new outputs JSON without CAD edits.',
         {'target_graph_path': {'type': 'string', 'minLength': 1}, 'output_path': {'type': 'string', 'minLength': 1},
          'distance_tolerance_mm': {'type': 'number', 'exclusiveMinimum': 0},
          'angle_tolerance_deg': {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 5},
          'max_pairs': {'type': 'integer', 'minimum': 1, 'maximum': 1225, 'default': 200}},
         ['target_graph_path', 'output_path', 'distance_tolerance_mm', 'angle_tolerance_deg'], False),
    spec('cad_draft_joints', 'Build source-bound target relationship evidence for each conditional partition WITHOUT requiring templates. Target joint types and DOF remain unknown. Only explicit nonempty template_ids add optional structural analogies; reference kind/DOF never become target conclusions. Preserve constraints, geometry, conflicts and shared pair/search budgets. Offline; no CAD edits or motion solving.',
         {'rigid_candidates_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1},
          'template_ids': {'type':'array','minItems':0,'maxItems':8,'uniqueItems':True,'items':{'type':'string','minLength':1}},
          'max_target_pairs': {'type':'integer','minimum':1,'maximum':2000,'default':200},
          'include_heldout': {'type':'boolean'}, 'pattern_size': {'type':'integer','minimum':2,'maximum':6,'default':3},
          'max_candidates': {'type':'integer','minimum':1,'maximum':10,'default':5},
          'max_states': {'type':'integer','minimum':1,'maximum':100000,'default':20000},
          'beam_width': {'type':'integer','minimum':1,'maximum':1000,'default':50},
          'angle_tolerance_deg': {'type':'number','exclusiveMinimum':0,'maximum':45,'default':10},
          'axis_distance_tolerance_mm': {'type':'number','exclusiveMinimum':0,'maximum':10,'default':0.1},
          'axis_angle_tolerance_deg': {'type':'number','exclusiveMinimum':0,'maximum':5,'default':1}},
         ['rigid_candidates_path','output_path'], False),
    spec('cad_check_joint_draft', 'Replay a joint draft and its original sources; check membership, endpoints, active-lock versus moving hypotheses, axis-fit disagreements, competing types and omitted scope. Writes traceable findings, not a physical solver verdict. Offline; no CAD or human-review gate.',
         {'joint_draft_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1},
          'max_findings': {'type':'integer','minimum':1,'maximum':2000,'default':200}},
         ['joint_draft_path','output_path'], False),
    spec('cad_plan_evidence_tasks', 'Replay a draft check and produce concrete bounded read-only CAD calls with before/after document and pose guards, dependencies and new raw-envelope paths. Optionally replay an evidence index to reuse captures, block repeated failed scans and return an explicit collect/stop decision within four rounds. Preserve capability gaps and deferred tasks. Does not execute or reintegrate evidence.',
         {'draft_check_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1},
          'max_tasks': {'type':'integer','minimum':3,'maximum':200,'default':20},
          'evidence_index_path': {'type':'string','minLength':1}},
         ['draft_check_path','output_path'], False),
    spec('sw_execute_evidence_task', 'Replay an evidence plan and optional previous receipt, then execute at most ONE next existing read-only CAD tool. Validate context, save original envelope and immutable receipt; block dependent tasks and stop on timeouts or context mismatch. Never start/open/edit/save CAD or retry. Reinvoke with the returned receipt until execution_complete.',
         {'plan_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1},
          'previous_execution_path': {'type':'string','minLength':1}}, ['plan_path','output_path'], False),
    spec('cad_reintegrate_evidence', 'Replay a completed guarded execution and recompute compatible cylinder, root-mate, distance and finite-face reviews, chain, target, rigid candidates, joints and check into fresh files. Preserve existing thresholds, budgets and old observations. Optional face_review_path supplies explicit replayed thresholds for uncovered component pairs and only its matching guarded captures. Partial captures, face catalogs, constraints and incompatible probes remain supplemental. Offline; no physical confirmation.',
         {'execution_path': {'type':'string','minLength':1}, 'output_path': {'type':'string','minLength':1},
          'face_review_path': {'type':'string','minLength':1}}, ['execution_path','output_path'], False),
    spec('cad_compare_draft_checks', 'Replay before/after draft checks and compare returned candidates, findings, settings and coverage. Face evidence separates semantic observations, thresholds and support from provenance-only rewrites. Disappearing entries are no_longer_observed, never mechanically resolved. Reject changed document or shared occurrence poses. Offline; no CAD modification.',
         {'before_check_path': {'type':'string','minLength':1}, 'after_check_path': {'type':'string','minLength':1},
          'output_path': {'type':'string','minLength':1}}, ['before_check_path','after_check_path','output_path'], False),
    spec('cad_index_evidence', 'Replay a completed guarded execution and current draft check into an observation index. Associate constraints and face catalogs with occurrences, pairs, findings and retained joint candidates; preserve unsuccessful attempts and prior indexed lineage. Input context must match. Offline, no reranking, face selection or mechanical confirmation. Pass index to cad_plan_evidence_tasks for reuse and explicit bounded stopping.',
         {'draft_check_path': {'type':'string','minLength':1}, 'execution_path': {'type':'string','minLength':1},
          'output_path': {'type':'string','minLength':1}, 'max_contexts': {'type':'integer','minimum':1,'maximum':2000,'default':200}},
         ['draft_check_path','execution_path','output_path'], False),
    spec('cad_plan_face_probes', 'Replay a draft check and latest observation index; use existing component-distance witnesses to rank saved plane/cylinder face candidates and derive seeds. Schedule missing catalogs or guarded finite-face probes within explicit budgets. Preserve competing/omitted faces and previous attempts. Offline; analytic residuals do not establish finite-face membership, live identity, contact or mechanical joints.',
         {'draft_check_path': {'type': 'string', 'minLength': 1}, 'evidence_index_path': {'type': 'string', 'minLength': 1},
          'output_path': {'type': 'string', 'minLength': 1}, 'max_component_gap_mm': {'type': 'number', 'minimum': 0},
          'surface_tolerance_mm': {'type': 'number', 'minimum': 0},
          'max_component_pairs': {'type': 'integer', 'minimum': 1, 'maximum': 200, 'default': 20},
          'max_face_candidates': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20},
          'max_face_pairs': {'type': 'integer', 'minimum': 1, 'maximum': 2000, 'default': 100},
          'max_tasks': {'type': 'integer', 'minimum': 3, 'maximum': 200, 'default': 20},
          'max_iterations': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
          'convergence_tolerance_mm': {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 1, 'default': 0.001}},
         ['draft_check_path', 'evidence_index_path', 'output_path', 'max_component_gap_mm', 'surface_tolerance_mm'], False),
]
CATALOG = {tool["name"]: tool for tool in TOOLS}


class SolidWorksTools:
    def __init__(self, root=None, factory=None, timeout=180.0):
        self.root = Path(root or Path.cwd()).resolve()
        if factory is None:
            from cadkin.adapters.solidworks import SolidWorksAdapter
            factory = lambda: SolidWorksAdapter(root=self.root)
        self.worker = StaWorker(factory, timeout=timeout)
        from cadkin.tools.plan_cache import PlanReplayCache
        self.plan_cache = PlanReplayCache()

    def call(self, name, arguments=None):
        try:
            if name not in CATALOG:
                raise ToolFailure("UNKNOWN_TOOL", f"Unknown tool: {name}")
            from jsonschema import Draft202012Validator
            arguments = {} if arguments is None else arguments
            error = next(Draft202012Validator(CATALOG[name]["inputSchema"]).iter_errors(arguments), None)
            if error:
                raise ToolFailure("INVALID_ARGUMENTS", error.message)
            if name in ('cad_list_mechanism_templates','cad_extract_mechanism_template','cad_compare_mechanism_graphs'):
                from cadkin.tools.templates import template_catalog, extract_template, compare_templates
                handler = {'cad_list_mechanism_templates':template_catalog, 'cad_extract_mechanism_template':extract_template,
                           'cad_compare_mechanism_graphs':compare_templates}[name]
                return handler(self.root, **arguments)
            if name in ('cad_build_target_graph','cad_match_mechanism_templates'):
                from cadkin.tools.matching import build_target_graph, match_templates
                handler = build_target_graph if name == 'cad_build_target_graph' else match_templates
                return handler(self.root, **arguments)
            if name == 'cad_analyze_constraints':
                from cadkin.tools.constraint_analysis import analyze_constraints
                return analyze_constraints(self.root, **arguments)
            if name in ('cad_build_rigid_candidates','cad_draft_joints'):
                from cadkin.tools.rigid import rigid_candidates, joint_drafts
                handler = rigid_candidates if name == 'cad_build_rigid_candidates' else joint_drafts
                return handler(self.root, **arguments)
            if name in ('cad_check_joint_draft','cad_plan_evidence_tasks'):
                from cadkin.tools.followup import check_joint_draft, evidence_task_plan
                handler = check_joint_draft if name == 'cad_check_joint_draft' else evidence_task_plan
                return handler(self.root, **arguments)
            if name == 'sw_execute_evidence_task':
                from cadkin.tools.execution import execute_task
                return execute_task(self.root, self.call, plan_cache=self.plan_cache, **arguments)
            if name == 'cad_reintegrate_evidence':
                from cadkin.tools.reintegration import reintegrate
                return reintegrate(self.root, **arguments)
            if name == 'cad_compare_draft_checks':
                from cadkin.tools.comparison import compare_draft_checks
                return compare_draft_checks(self.root, **arguments)
            if name == 'cad_index_evidence':
                from cadkin.tools.observation_index import index_evidence
                return index_evidence(self.root, **arguments)
            if name == 'cad_plan_face_probes':
                from cadkin.tools.face_planning import face_task_plan
                return face_task_plan(self.root, **arguments)
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
            if name == 'cad_proximity_candidates':
                from cadkin.tools.proximity import component_proximity
                return component_proximity(self.root, **arguments)
            if name == 'cad_review_proximity':
                from cadkin.tools.proximity_review import proximity_review
                return proximity_review(self.root, **arguments)
            if name == 'sw_probe_face_pair':
                from cadkin.tools.face_sources import load_probe_sources
                arguments = load_probe_sources(self.root, **arguments)
            if name == 'cad_review_face_contacts':
                from cadkin.tools.face_contacts import face_contact_review
                return face_contact_review(self.root, **arguments)
            if name == 'cad_build_chain_evidence':
                from cadkin.tools.chain import chain_dossier
                return chain_dossier(self.root, **arguments)
            if name == 'cad_apply_chain_review':
                from cadkin.tools.chain_review import apply_chain_review
                return apply_chain_review(self.root, **arguments)
            return self.worker.call(name, arguments)
        except Exception as exc:
            return failure(exc)

    def close(self):
        self.worker.close()
