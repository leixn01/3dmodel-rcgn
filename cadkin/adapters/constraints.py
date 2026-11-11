"""Component fixed flag and attached mate records; no constraint solving or editing."""
from datetime import datetime, timezone

from cadkin._vendor.sw_mcp import value
from cadkin.adapters.evidence import boolean, evidence_error, sequence
from cadkin.errors import ToolFailure, success


from cadkin.adapters.mate_records import read_mate

class ConstraintOperations:
    def sw_component_constraints(self, expected_document_token, occurrence_path, max_mates=100, max_entities=16):
        _, info, node, component, errors = self._evidence_target(expected_document_token, occurrence_path)
        fixed = {"value": None, "scope": "root_assembly_top_level", "source": "IComponent2.IsFixed"}
        if node["parent_occurrence_path"] is not None:
            fixed["scope"] = "unavailable_nested_context"
            errors.append({"code": "FIXED_STATE_CONTEXT_UNAVAILABLE", "occurrence_path": occurrence_path,
                           "message": "IsFixed applies to top-level components; nested fixed state requires its owning subassembly/configuration. No document was activated."})
        else:
            try:
                fixed["value"] = boolean(value(component, "IsFixed"), "IsFixed")
            except Exception as exc:
                errors.append(evidence_error(exc, field="fixed_state", occurrence_path=occurrence_path))
        mates, reported_count, truncated = None, None, False
        try:
            raw_mates = sequence(value(component, "GetMates"), "GetMates")
            reported_count = len(raw_mates)
            mates = []
            if reported_count > max_mates:
                truncated = True
                errors.append({"code": "MATE_LIMIT", "message": "Stopped at max_mates; attached mate list is incomplete."})
            for index, mate in enumerate(raw_mates[:max_mates]):
                self._check_evidence_target(info, node, component)
                item, entity_truncated = read_mate(mate, index, max_entities,
                                                   lambda: self._check_evidence_target(info, node, component))
                truncated = truncated or entity_truncated
                errors.extend(item["errors"])
                mates.append(item)
        except ToolFailure as exc:
            if exc.code in {"DOCUMENT_CHANGED", "COMPONENT_CHANGED"}:
                raise
            errors.append(evidence_error(exc, field="mates"))
        except Exception as exc:
            errors.append(evidence_error(exc, field="mates"))
        self._check_evidence_target(info, node, component)
        return success({"constraint_schema_version": 1, "document": info, "occurrence_path": occurrence_path,
                        "parent_occurrence_path": node["parent_occurrence_path"], "fixed_state": fixed,
                        "captured_at_utc": datetime.now(timezone.utc).isoformat(), "snapshot_atomic": False,
                        "mates": mates, "reported_mate_count": reported_count,
                        "read_mate_count": len(mates) if mates is not None else 0,
                        "complete": not errors, "truncated": truncated,
                        "enum_types": {"type_code": "swMateType_e", "alignment_code": "swMateAlign_e", "reference_type_code": "swSelectType_e"},
                        "entity_params_frame": "Owning assembly of each mate, not assumed to be the active root assembly.",
                        "limitations": ["ReferenceComponent.Name2 is retained in its API context; it is not automatically resolved to a root occurrence path.",
                                        "EntityParams are raw parameters: positions/radii in meters; vectors are not automatically interpreted as joint axes.",
                                        "GetMates may include IMateInPlace; unsupported records stay partial instead of being discarded.",
                                        "No mates does not prove free motion. Fixed/floating is not the component's mechanical role; no DOF/rigid-body inference."]}, errors)
