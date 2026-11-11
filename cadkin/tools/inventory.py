"""Shared validation of exported occurrence identity and complete hierarchy."""
from cadkin.errors import ToolFailure


def spatial_inventory(envelope, incomplete_code="INCOMPLETE_INVENTORY"):
    if not isinstance(envelope, dict) or envelope.get("status") not in ("ok", "partial"):
        raise ToolFailure("INVALID_INVENTORY", "Input must be an actual spatial inventory result envelope.")
    data = envelope.get("data")
    if not isinstance(data, dict) or data.get("spatial_schema_version") != 1 or not isinstance(data.get("components"), list):
        raise ToolFailure("INVALID_INVENTORY", "Expected spatial_schema_version=1 and components.")
    if (data.get("truncated") or not data.get("collection_complete", data.get("complete", False)) or
            not data.get("hierarchy_complete", data.get("complete", False))):
        raise ToolFailure(incomplete_code, "Collect all pages and resolve hierarchy errors before analysis. Missing geometry may remain explicit.")
    nodes = data["components"]
    by_path = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ToolFailure("INVALID_INVENTORY", "Every component must be an object.")
        path = node.get("occurrence_path")
        if not isinstance(path, str) or not path or path.startswith("@") or path in by_path:
            raise ToolFailure("INVALID_INVENTORY", "Occurrence paths must be nonempty, readable and unique.")
        by_path[path] = node
    if data.get("component_count") != len(nodes):
        raise ToolFailure("INVALID_INVENTORY", "Component count does not match the records.")
    for path, node in by_path.items():
        seen = {path}
        parent = node.get("parent_occurrence_path")
        while parent is not None:
            if not isinstance(parent, str) or parent not in by_path or parent in seen:
                raise ToolFailure("INVALID_INVENTORY", "Parent hierarchy is incomplete or cyclic.")
            seen.add(parent)
            parent = by_path[parent].get("parent_occurrence_path")
    return data, by_path
