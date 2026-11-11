"""Shared bounded mate/entity reads; context and identity resolution are supplied by callers."""
from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import evidence_error, integer
from cadkin.errors import ToolFailure
from cadkin.geometry import numbers

# Interpretation only; codes retained verbatim. Source: official swMateType_e (2021/2026).
MATE_TYPES = {0: "coincident", 1: "concentric", 2: "perpendicular", 3: "parallel",
              4: "tangent", 5: "distance", 6: "angle", 7: "unknown", 8: "symmetric",
              9: "cam_follower", 10: "gear", 11: "width", 12: "lock_to_sketch", 13: "rack_pinion",
              15: "path", 16: "lock", 17: "screw", 18: "linear_coupler", 19: "universal_joint",
              20: "coordinate", 21: "slot", 22: "hinge", 23: "slider", 24: "profile_center", 25: "magnetic"}



def read_mate(mate, index, max_entities, check_context, resolve_reference=None):
    truncated = False
    item = {"mate_index": index, "type_code": None, "alignment_code": None,
            "entity_count": None, "entities": None, "errors": [],
            "constraint_activity": "unknown; suppression/solver state is not evaluated"}
    for key, member in (("type_code", "Type"), ("alignment_code", "Alignment")):
        try:
            item[key] = integer(value(mate, member), member)
        except Exception as exc:
            item["errors"].append(evidence_error(exc, mate_index=index, field=key))
    try:
        count = integer(value(mate, "GetMateEntityCount"), "GetMateEntityCount", 0)
        item["entity_count"] = count
        item["entities"] = []
        if count > max_entities:
            truncated = True
            item["errors"].append({"code": "MATE_ENTITY_LIMIT", "message": "Stopped at max_entities.", "mate_index": index})
        for entity_index in range(min(count, max_entities)):
            check_context()
            record = {"entity_index": entity_index, "reference_type_code": None,
                      "reference_component_name": None, "reference_status": "unavailable",
                      "entity_params_raw": None, "errors": []}
            try:
                entity = call(mate, "MateEntity", entity_index)
                if entity is None:
                    raise ToolFailure("MATE_ENTITY_UNAVAILABLE", "SOLIDWORKS returned a null mate entity.")
                try:
                    record["reference_type_code"] = integer(value(entity, "ReferenceType2"), "ReferenceType2")
                except Exception as exc:
                    record["errors"].append(evidence_error(exc, field="reference_type_code"))
                try:
                    reference = value(entity, "ReferenceComponent")
                    if reference is None:
                        record["reference_status"] = "root_or_unavailable"
                    else:
                        name = value(reference, "Name2")
                        if not isinstance(name, str) or not name:
                            raise ToolFailure("MATE_REFERENCE_UNAVAILABLE", "Mate reference name is unreadable.")
                        record.update(reference_component_name=name, reference_status="name_read_context_unverified")
                        if resolve_reference is not None:
                            record.update(resolve_reference(reference, name))
                except Exception as exc:
                    record["errors"].append(evidence_error(exc, field="reference_component_name"))
                try:
                    size = integer(value(entity, "GetEntityParamsSize"), "GetEntityParamsSize", 0)
                    if size > 64:
                        raise ToolFailure("INVALID_EVIDENCE", "Mate parameter array is unexpectedly large.")
                    raw = value(entity, "EntityParams")
                    record["entity_params_raw"] = numbers([] if raw is None and size == 0 else raw, size, "INVALID_MATE_PARAMS")
                except Exception as exc:
                    record["errors"].append(evidence_error(exc, field="entity_params_raw"))
            except Exception as exc:
                record["errors"].append(evidence_error(exc, field="entity"))
            for error in record["errors"]:
                error.update(mate_index=index, entity_index=entity_index)
            item["errors"].extend(record["errors"])
            item["entities"].append(record)
    except ToolFailure as exc:
        if exc.code in {"DOCUMENT_CHANGED", "COMPONENT_CHANGED"}:
            raise
        item["errors"].append(evidence_error(exc, mate_index=index, field="entities"))
    except Exception as exc:
        item["errors"].append(evidence_error(exc, mate_index=index, field="entities"))
    item["type_name"] = MATE_TYPES.get(item["type_code"])
    item["read_status"] = "partial" if item["errors"] else "ok"
    return item, truncated
