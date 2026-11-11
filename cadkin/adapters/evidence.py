"""Read-only component evidence helpers. COM references stay on the STA."""
from cadkin._vendor.sw_mcp import value
from cadkin.errors import ToolFailure


def integer(raw, field, minimum=None):
    if isinstance(raw, bool) or not isinstance(raw, int) or (minimum is not None and raw < minimum):
        raise ToolFailure("INVALID_EVIDENCE", f"{field} is not a valid integer.")
    return raw


def boolean(raw, field):
    if not isinstance(raw, (bool, int)) or raw not in (0, 1, -1):
        raise ToolFailure("INVALID_EVIDENCE", f"{field} is not a Boolean.")
    return bool(raw)


def sequence(raw, field):
    if raw is None:
        return []
    if not isinstance(raw, (tuple, list)):
        raise ToolFailure("INVALID_EVIDENCE", f"{field} is not an array.")
    return raw


def evidence_error(exc, **context):
    return {"code": getattr(exc, "code", "EVIDENCE_READ_FAILED"), "message": str(exc), **context}


class EvidenceOperations:
    def _evidence_target(self, token, path):
        doc, info, nodes, errors, objects = self._spatial_tree(token, 20000, 128)
        structural = {"COMPONENT_LIMIT", "DEPTH_LIMIT", "CHILDREN_READ_FAILED", "INVALID_INSTANCE_NAME"}
        if any(e["code"] in structural or (e["code"] == "COMPONENT_READ_FAILED" and e.get("field") == "name") for e in errors):
            raise ToolFailure("COMPONENT_LOOKUP_INCOMPLETE", "Cannot establish a unique component occurrence.", traversal_errors=errors)
        if path not in objects:
            raise ToolFailure("COMPONENT_NOT_FOUND", "Use the exact occurrence_path from the current tree.")
        node = next(n for n in nodes if n["occurrence_path"] == path)
        if node["suppression_state"] not in (2, 3) or node["is_suppressed"] != False:
            raise ToolFailure("UNRESOLVED_COMPONENT", "Resolve the target explicitly before reading its evidence.")
        self._check_evidence_target(info, node, objects[path])
        return doc, info, node, objects[path], list(errors)

    def _check_evidence_target(self, info, node, component):
        self._check_current(info)
        if (value(component, "Name2") != node["occurrence_path"] or
                value(component, "ReferencedConfiguration") != node["referenced_configuration"] or
                value(component, "GetSuppression2") not in (2, 3)):
            raise ToolFailure("COMPONENT_CHANGED", "Component identity, referenced configuration or resolution changed during the read.")
