"""Collect bounded STA pages without turning a long export into one COM job."""
import json

from cadkin.errors import ToolFailure, failure, success


def collect_spatial(service, page_size=20, max_components=5000, max_depth=64, include_bounding_boxes=True):
    active = service.call("sw_active_document")
    if active["status"] == "error":
        return active
    arguments = {"expected_document_token": active["data"]["document_token"],
                 "page_size": page_size, "max_components": max_components, "max_depth": max_depth,
                 "include_bounding_boxes": include_bounding_boxes, "offset": 0}
    records, errors, seen, error_keys = [], [], set(), set()
    first, finished, pages = None, False, 0
    hierarchy_complete, truncated = True, False
    try:
        while True:
            result = service.call("sw_spatial_inventory", arguments)
            if result["status"] == "error":
                if first is None:
                    return result
                errors.extend(result["errors"])
                break
            data = result["data"]
            pagination = data["pagination"]
            if first is None:
                first = data
            if (data["inventory_signature"] != first["inventory_signature"] or
                    data["document"]["document_token"] != arguments["expected_document_token"] or
                    pagination["offset"] != len(records) or
                    pagination["total_components"] != first["pagination"]["total_components"]):
                raise ToolFailure("PAGE_MISMATCH", "Page identity, scope or sequence changed; collection is incomplete.")
            paths = [item["occurrence_path"] for item in data["components"]]
            total = pagination["total_components"]
            end = len(records) + len(paths)
            if (len(set(paths)) != len(paths) or seen.intersection(paths) or
                    len(paths) != data["component_count"] or len(paths) > page_size or end > total or
                    pagination["has_more"] != (end < total) or
                    pagination["next_offset"] != (end if end < total else None) or
                    (not paths and total)):
                raise ToolFailure("PAGE_MISMATCH", "Page coverage is inconsistent; no complete snapshot was claimed.")
            seen.update(paths)
            records.extend(data["components"])
            pages += 1
            hierarchy_complete = hierarchy_complete and data["hierarchy_complete"]
            truncated = truncated or data["truncated"]
            for error in result["errors"]:
                key = json.dumps(error, sort_keys=True, ensure_ascii=False)
                if key not in error_keys:
                    errors.append(error)
                    error_keys.add(key)
            if not pagination["has_more"]:
                finished = True
                break
            arguments.update(offset=pagination["next_offset"],
                             expected_inventory_signature=first["inventory_signature"])
    except (ToolFailure, KeyError, TypeError, ValueError) as exc:
        if first is None:
            return failure(exc)
        errors.extend(failure(exc)["errors"])
    data = {**first, "components": records, "component_count": len(records),
            "spatial_ok_count": sum(item["spatial_status"] == "ok" for item in records),
            "complete": finished and not errors and hierarchy_complete,
            "hierarchy_complete": hierarchy_complete, "truncated": truncated,
            "collection_complete": finished, "pages_collected": pages,
            "next_offset": None if finished else len(records),
            "total_components": first["pagination"]["total_components"],
            "collection_note": "Sequential non-atomic pages; keep the document/configuration and geometry unchanged throughout collection."}
    data.pop("pagination", None)
    data.pop("page_complete", None)
    return success(data, errors)
