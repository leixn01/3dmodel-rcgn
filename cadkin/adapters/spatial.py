"""Read-only assembly spatial inventory. COM objects remain in the STA."""
from datetime import datetime, timezone
import hashlib
import json

from cadkin._vendor.sw_mcp import call, value
from cadkin.errors import ToolFailure, success
from cadkin.geometry import bounding_box, transform_from_sw, inverse_similarity, multiply, millimeters


class SpatialOperations:
    def _spatial_tree(self, token, max_components, max_depth):
        doc, info = self._document(token)
        if info["document_type"] != "assembly":
            raise ToolFailure("NOT_ASSEMBLY", "Spatial occurrence tools require an assembly. A multibody STEP part is not an assembly.", document=info)
        nodes, errors, objects = self._walk(doc, max_components, max_depth)
        self._check_current(info)
        return doc, info, nodes, errors, objects

    def _read_spatial(self, info, nodes, traversal_errors, objects, requested=None, include_bounding_boxes=True):
        by_path = {node["occurrence_path"]: node for node in nodes}
        chosen = nodes if requested is None else [by_path[path] for path in requested]
        required = dict.fromkeys(node["occurrence_path"] for node in chosen)
        # Transform2 is already root-relative. Parents are read only to derive local transforms.
        for node in chosen:
            parent = node["parent_occurrence_path"]
            if parent is not None:
                required[parent] = None
        transforms, transform_errors = {}, {}

        def record_error(exc, path, field):
            return {"code": getattr(exc, "code", "SPATIAL_READ_FAILED"), "message": str(exc),
                    "occurrence_path": path, "field": field}

        def readable(node):
            path = node["occurrence_path"]
            if path not in objects:
                raise ToolFailure("COMPONENT_UNAVAILABLE", "The occurrence has no uniquely readable COM object.")
            suppressed = node["is_suppressed"]
            if not isinstance(suppressed, (bool, int)) or suppressed != 0 or node["suppression_state"] not in (2, 3):
                raise ToolFailure("UNRESOLVED_COMPONENT", "Suppressed, lightweight or unreadable occurrence was retained without loading/resolving it.")
            return objects[path]

        for path in required:
            self._check_current(info)
            try:
                node = by_path.get(path)
                if node is None:
                    raise ToolFailure("PARENT_TRANSFORM_UNAVAILABLE", "The parent occurrence was not read.")
                component = readable(node)
                transform = value(component, "Transform2")
                if transform is None:
                    raise ToolFailure("TRANSFORM_UNAVAILABLE", "SOLIDWORKS returned no transform; identity was not substituted.")
                transforms[path] = transform_from_sw(value(transform, "ArrayData"))
            except Exception as exc:
                transform_errors[path] = record_error(exc, path, "transform")

        records, errors = [], list(traversal_errors)
        for node in chosen:
            self._check_current(info)
            path, parent = node["occurrence_path"], node["parent_occurrence_path"]
            item = {**node, "transform": None, "bounding_box": None, "spatial_errors": []}
            if path in transform_errors:
                item["spatial_errors"].append(transform_errors[path])
            else:
                transform = dict(transforms[path])
                transform.update({"to_parent": None, "origin_parent_m": None, "origin_parent_mm": None})
                try:
                    if parent is None:
                        local = [row[:] for row in transform["to_root"]]
                    elif parent in transforms:
                        local = multiply(inverse_similarity(transforms[parent]["to_root"]), transform["to_root"])
                    else:
                        raise ToolFailure("PARENT_TRANSFORM_UNAVAILABLE", "Root transform is available but the parent transform is not; local transform remains null.")
                    origin = [local[i][3] for i in range(3)]
                    transform.update({"to_parent": local, "origin_parent_m": origin, "origin_parent_mm": millimeters(origin)})
                except Exception as exc:
                    item["spatial_errors"].append(record_error(exc, path, "transform.to_parent"))
                    if parent in transform_errors:
                        item["spatial_errors"].append(transform_errors[parent])
                item["transform"] = transform
            item["bounding_box_status"] = "not_requested"
            if include_bounding_boxes:
                item["bounding_box_status"] = "unavailable"
                try:
                    component = readable(node)
                    box = call(component, "GetBox", False, False)
                    if box is None:
                        raise ToolFailure("BOUNDING_BOX_UNAVAILABLE", "SOLIDWORKS returned no box; zero dimensions were not substituted.")
                    item["bounding_box"] = bounding_box(box)
                except Exception as exc:
                    item["spatial_errors"].append(record_error(exc, path, "bounding_box"))
                if item["bounding_box"] is not None:
                    item["bounding_box_status"] = "ok"
            item["spatial_status"] = "ok" if not item["spatial_errors"] and node["read_status"] == "ok" else (
                "unavailable" if item["transform"] is None and item["bounding_box"] is None else "partial")
            errors.extend(item["spatial_errors"])
            records.append(item)
        self._check_current(info)
        # These are metadata reads; no geometry, selection, display, resolve or save calls.
        revision = str(value(self.app, "RevisionNumber"))
        self._check_current(info)
        return {"spatial_schema_version": 1, "document": info,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "solidworks_revision": revision,
                "units": {"api_length": "m", "display_length": "mm", "matrix_translation": "m"},
                "convention": "Column vectors: p_root = to_root @ p_component; p_parent = to_parent @ p_component; to_root_child = to_root_parent @ to_parent_child.",
                "frame": "Active root assembly model coordinates; Transform2 excludes presentation transforms.",
                "snapshot_atomic": False, "bounding_boxes_requested": include_bounding_boxes,
                "components": records, "component_count": len(records),
                "spatial_ok_count": sum(item["spatial_status"] == "ok" for item in records),
                "complete": not errors and all(item["spatial_status"] == "ok" for item in records),
                "truncated": any(error["code"] in ("COMPONENT_LIMIT", "DEPTH_LIMIT") for error in traversal_errors),
                "counting": "Read occurrences including subassemblies and unresolved nodes; root excluded; repeated files are separate instances."}, errors

    def sw_spatial_inventory(self, expected_document_token, max_components=500, max_depth=64,
                             offset=0, page_size=20, include_bounding_boxes=True,
                             expected_inventory_signature=None):
        if offset and expected_inventory_signature is None:
            raise ToolFailure("INVALID_ARGUMENTS", "Continuation pages require expected_inventory_signature from the first page.")
        _, info, nodes, traversal_errors, objects = self._spatial_tree(expected_document_token, max_components, max_depth)
        nodes = sorted(nodes, key=lambda node: node["occurrence_path"])
        signature = hashlib.sha256(json.dumps(
            {"token": info["document_token"], "nodes": nodes, "max_components": max_components,
             "max_depth": max_depth, "include_bounding_boxes": include_bounding_boxes},
            sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        if expected_inventory_signature is not None and signature != expected_inventory_signature:
            raise ToolFailure("INVENTORY_CHANGED", "Assembly hierarchy, configuration or query scope changed; restart collection.")
        if offset > len(nodes) or (offset == len(nodes) and offset != 0):
            raise ToolFailure("PAGE_OUT_OF_RANGE", "Offset is outside the inventory.", total_components=len(nodes))
        chosen = [node["occurrence_path"] for node in nodes[offset:offset + page_size]]
        data, errors = self._read_spatial(info, nodes, traversal_errors, objects, chosen, include_bounding_boxes)
        next_offset = offset + len(chosen)
        has_more = next_offset < len(nodes)
        hierarchy_errors = {"COMPONENT_LIMIT", "DEPTH_LIMIT", "CHILDREN_READ_FAILED",
                            "INVALID_INSTANCE_NAME", "UNRESOLVED_COMPONENT"}
        hierarchy_complete = not any(error["code"] in hierarchy_errors or
            (error["code"] == "COMPONENT_READ_FAILED" and error.get("field") == "name")
            for error in traversal_errors)
        page_complete = data["complete"]
        data.update({"inventory_signature": signature, "hierarchy_complete": hierarchy_complete,
                     "page_complete": page_complete, "collection_complete": offset == 0 and not has_more,
                     "complete": page_complete and offset == 0 and not has_more,
                     "pagination": {"offset": offset, "page_size": page_size, "has_more": has_more,
                                    "next_offset": next_offset if has_more else None,
                                    "total_components": len(nodes)}})
        return success(data, errors)

    def sw_component_spatial(self, expected_document_token, occurrence_path):
        _, info, nodes, errors, objects = self._spatial_tree(expected_document_token, 20000, 128)
        matches = [node for node in nodes if node["name"] == occurrence_path]
        if len(matches) > 1:
            raise ToolFailure("AMBIGUOUS_COMPONENT", "Multiple occurrences have this name; no spatial target was guessed.")
        if not matches:
            code = "COMPONENT_LOOKUP_INCOMPLETE" if errors else "COMPONENT_NOT_FOUND"
            raise ToolFailure(code, "The requested full occurrence path was not found.", traversal_errors=errors)
        if any(error["code"] in ("COMPONENT_LIMIT", "DEPTH_LIMIT", "CHILDREN_READ_FAILED", "INVALID_INSTANCE_NAME") or
               (error["code"] == "COMPONENT_READ_FAILED" and error.get("field") == "name") for error in errors):
            raise ToolFailure("COMPONENT_LOOKUP_INCOMPLETE", "The traversal cannot establish a unique target; inspect traversal errors.", traversal_errors=errors)
        data, errors = self._read_spatial(info, nodes, errors, objects, [matches[0]["occurrence_path"]])
        data["component"] = data.pop("components")[0]
        return success(data, errors)
