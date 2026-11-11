"""Analytic cylindrical-face candidates from a component's matching part definition."""
from datetime import datetime, timezone

from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import boolean, evidence_error, sequence
from cadkin.errors import ToolFailure, success
from cadkin.geometry import cylinder_from_sw, transform_from_sw


class CylinderOperations:
    def sw_component_cylinders(self, expected_document_token, occurrence_path,
                               max_bodies=50, max_faces=500, max_cylinders=100):
        _, info, node, component, errors = self._evidence_target(expected_document_token, occurrence_path)
        part = value(component, "GetModelDoc2")
        if part is None:
            raise ToolFailure("COMPONENT_MODEL_UNAVAILABLE", "The component model document is not loaded; no document was opened or resolved.")
        part_info = self._info(part)
        if part_info["document_type"] != "part":
            raise ToolFailure("NOT_PART_COMPONENT", "Choose a leaf part occurrence, not a subassembly.")
        if not node["referenced_configuration"] or part_info["configuration"] != node["referenced_configuration"]:
            raise ToolFailure("COMPONENT_CONFIGURATION_MISMATCH", "Loaded part configuration differs from the occurrence reference; no configuration was switched.", referenced_configuration=node["referenced_configuration"], loaded_configuration=part_info["configuration"])
        transform_object = value(component, "Transform2")
        if transform_object is None:
            raise ToolFailure("TRANSFORM_UNAVAILABLE", "Cannot place cylinder evidence without the occurrence transform.")
        transform = transform_from_sw(value(transform_object, "ArrayData"))

        def check_context():
            self._check_evidence_target(info, node, component)
            current_part = self._info(part)
            if current_part["document_token"] != part_info["document_token"]:
                raise ToolFailure("COMPONENT_CONFIGURATION_MISMATCH", "Part document/configuration changed during the geometry read.")

        # swAllBodies=-1: all solid and sheet bodies; False includes hidden bodies.
        # These are definition bodies, not instance bodies with assembly-level cuts.
        bodies = sequence(call(part, "GetBodies2", -1, False), "GetBodies2")
        cylinders, scanned_faces, inspected_bodies, truncated = [], 0, 0, False
        if len(bodies) > max_bodies:
            truncated = True
            errors.append({"code": "BODY_LIMIT", "message": "Stopped at max_bodies; geometry scope is incomplete."})
        stop = False
        for body_index, body in enumerate(bodies[:max_bodies]):
            check_context()
            inspected_bodies += 1
            try:
                face = value(body, "GetFirstFace")
            except Exception as exc:
                errors.append(evidence_error(exc, body_index=body_index, field="faces"))
                continue
            face_index = 0
            while face is not None:
                if scanned_faces % 20 == 0:
                    check_context()
                if scanned_faces >= max_faces or len(cylinders) >= max_cylinders:
                    truncated, stop = True, True
                    errors.append({"code": "FACE_LIMIT" if scanned_faces >= max_faces else "CYLINDER_LIMIT",
                                   "message": "Stopped at the global per-call geometry budget; results are incomplete.",
                                   "body_index": body_index, "face_index": face_index})
                    break
                scanned_faces += 1
                try:
                    surface = value(face, "GetSurface")
                    if surface is None:
                        raise ToolFailure("SURFACE_UNAVAILABLE", "Face has no readable surface.")
                    if boolean(value(surface, "IsCylinder"), "IsCylinder"):
                        parameters = cylinder_from_sw(value(surface, "CylinderParams"), transform)
                        cylinders.append({"body_index": body_index, "face_index": face_index,
                                          "source": "ISurface.CylinderParams via IPartDoc.GetBodies2",
                                          "candidate_status": "geometry_only", **parameters})
                except Exception as exc:
                    errors.append(evidence_error(exc, body_index=body_index, face_index=face_index, field="surface"))
                try:
                    face = value(face, "GetNextFace")
                except Exception as exc:
                    errors.append(evidence_error(exc, body_index=body_index, face_index=face_index, field="next_face"))
                    break
                face_index += 1
            if stop:
                break
        check_context()
        latest = value(component, "Transform2")
        if latest is None or transform_from_sw(value(latest, "ArrayData"))["raw_array"] != transform["raw_array"]:
            raise ToolFailure("COMPONENT_CHANGED", "Occurrence transform changed during the read; mixed-frame evidence was discarded.")
        return success({"cylinder_schema_version": 1, "document": info, "occurrence_path": occurrence_path,
                        "source_part": part_info, "referenced_configuration": node["referenced_configuration"],
                        "captured_at_utc": datetime.now(timezone.utc).isoformat(), "snapshot_atomic": False,
                        "geometry_scope": "referenced_part_definition", "assembly_instance_features_evaluated": False,
                        "transform": transform, "cylinders": cylinders, "cylinder_count": len(cylinders),
                        "reported_body_count": len(bodies), "inspected_body_count": inspected_bodies,
                        "scanned_face_count": scanned_faces, "complete": not errors, "truncated": truncated,
                        "units": {"api_length": "m", "display_length": "mm", "axis_direction": "unit vector"},
                        "limitations": ["Part-definition geometry can differ from occurrence geometry after assembly-level features/cuts; verify before using it for assembly relationships.",
                                        "Only analytic cylindrical surfaces are recognized; NURBS approximations, cones, threads and reference axes are not inferred.",
                                        "One record per cylindrical face; split faces can share an axis. Body/face indices are snapshot-local, not persistent CAD IDs.",
                                        "Axis point is not a face center/end point; radius is not hole/shaft classification or length. Axis sign is not motion direction.",
                                        "A cylinder axis is a geometric candidate, not a confirmed rotation/prismatic joint, stroke or screw pitch."]}, errors)
