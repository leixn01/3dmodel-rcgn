"""Offline, bounded axis-relation candidates with snapshot-bound source evidence."""
from datetime import datetime, timezone
import json
import math
import re

from cadkin.errors import ToolFailure, success
from cadkin.geometry import numbers, transform_from_sw, cylinder_from_sw
from cadkin.tools.files import json_path, read_json
from cadkin.tools.inventory import spatial_inventory


def _require(condition, message, code="INVALID_RELATION_SOURCE"):
    if not condition:
        raise ToolFailure(code, message)


def _number(value, low, high=None):
    return (not isinstance(value, bool) and isinstance(value, (int, float)) and
            math.isfinite(value) and value > low and (high is None or value <= high))


def _document(info):
    _require(isinstance(info, dict), "Missing source document.")
    fields = ("document_token", "path", "title", "configuration", "document_type")
    _require(all(isinstance(info.get(f), str) for f in fields) and
             re.fullmatch(r"[0-9a-f]{24}", info["document_token"]) is not None and
             info["document_type"] == "assembly", "Expected an assembly document identity.")
    return tuple(info[f] for f in fields)


def _same_numbers(actual, expected):
    actual = numbers(actual, len(expected), "INVALID_RELATION_SOURCE")
    _require(all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9) for a, b in zip(actual, expected)),
             "Derived geometry disagrees with raw cylinder/transform data.")


def _errors(envelope):
    errors = envelope.get("errors")
    _require(isinstance(errors, list) and all(isinstance(e, dict) for e in errors), "Missing source error list.")
    return errors


def _transform(record):
    value = record.get("transform")
    _require(isinstance(value, dict), "A selected occurrence has no transform.")
    return transform_from_sw(value.get("raw_array"))


def _cylinders(envelope, by_path, document, source_path, digest):
    _require(isinstance(envelope, dict) and envelope.get("status") in ("ok", "partial"),
             "Use the original sw_component_cylinders result envelope.")
    data = envelope.get("data")
    _require(isinstance(data, dict) and data.get("cylinder_schema_version") == 1,
             "Expected cylinder_schema_version=1.")
    _require(_document(data.get("document")) == document, "Document/configuration differs from inventory.", "EVIDENCE_MISMATCH")
    path = data.get("occurrence_path")
    _require(isinstance(path, str) and path in by_path, "Cylinder occurrence is absent from inventory.", "EVIDENCE_MISMATCH")
    node = by_path[path]
    _require(not any(n.get("parent_occurrence_path") == path for n in by_path.values()), "Cylinder target must be a leaf occurrence.")
    _require(node.get("is_suppressed") is False and node.get("suppression_state") in (2, 3), "Selected occurrence must be resolved.")
    config = data.get("referenced_configuration")
    part = data.get("source_part")
    _require(isinstance(config, str) and bool(config) and config == node.get("referenced_configuration") and
             isinstance(part, dict) and part.get("configuration") == config and part.get("document_type") == "part",
             "Referenced part configuration differs from inventory or source part.", "EVIDENCE_MISMATCH")
    _require(data.get("geometry_scope") == "referenced_part_definition" and data.get("assembly_instance_features_evaluated") is False,
             "Unsupported geometry scope; use part-definition cylinder evidence.")
    units = data.get("units", {})
    _require(isinstance(units, dict) and units.get("api_length") == "m" and units.get("display_length") == "mm" and
             units.get("axis_direction") == "unit vector", "Expected meter raw data and millimeter root geometry.")
    transform = _transform(data)
    _require(transform["raw_array"] == _transform(node)["raw_array"],
             "Occurrence transform differs from spatial inventory; recollect unchanged snapshots.", "EVIDENCE_MISMATCH")
    rows = data.get("cylinders")
    _require(isinstance(rows, list) and len(rows) <= 1000 and type(data.get("cylinder_count")) is int and
             data["cylinder_count"] == len(rows), "Invalid or excessive cylinder records/count.")
    axes, seen = [], set()
    for row in rows:
        _require(isinstance(row, dict), "Cylinder record must be an object.")
        body, face = row.get("body_index"), row.get("face_index")
        _require(type(body) is int and body >= 0 and type(face) is int and face >= 0 and (body, face) not in seen,
                 "Body/face indices must be unique nonnegative snapshot indices.")
        seen.add((body, face))
        cylinder = cylinder_from_sw(row.get("raw_array"), transform)
        for field in ("origin_root_mm", "axis_root_unit"):
            _same_numbers(row.get(field), cylinder[field])
        _same_numbers([row.get("radius_root_mm")], [cylinder["radius_root_mm"]])
        axes.append({"body_index": body, "face_index": face, "origin_root_mm": cylinder["origin_root_mm"],
                     "axis_root_unit": cylinder["axis_root_unit"], "radius_root_mm": cylinder["radius_root_mm"]})
    errors = _errors(envelope)
    _require(type(data.get("complete")) is bool and type(data.get("truncated")) is bool, "Missing source completeness flags.")
    complete = envelope["status"] == "ok" and data["complete"] and not data["truncated"] and not errors
    return {"occurrence_path": path, "file_path": node.get("file_path"), "referenced_configuration": config,
            "source_path": source_path, "source_sha256": digest, "captured_at_utc": data.get("captured_at_utc"),
            "source_part": part, "complete": complete, "truncated": data["truncated"], "errors": errors,
            "origin_root_mm": transform["origin_root_mm"], "axes": sorted(axes, key=lambda a: (a["body_index"], a["face_index"]))}


def axis_metrics(left, right, reference_mm):
    """Unoriented angle and line separation near a common, axis-origin-independent reference."""
    u, v = left["axis_root_unit"], right["axis_root_unit"]
    dot = sum(a * b for a, b in zip(u, v))
    cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    angle = math.degrees(math.atan2(math.hypot(*cross), abs(dot)))
    def projection(axis):
        point, direction = axis["origin_root_mm"], axis["axis_root_unit"]
        delta = [point[i] - reference_mm[i] for i in range(3)]
        along = sum(delta[i] * direction[i] for i in range(3))
        # Work relative to the reference to avoid subtracting two large root points.
        return [delta[i] - along * direction[i] for i in range(3)]
    offset = math.dist(projection(left), projection(right))
    numbers([angle, offset], 2, "INVALID_RELATION_GEOMETRY")
    return {"angle_deg": angle, "axis_offset_at_reference_mm": offset,
            "reference_root_mm": reference_mm}


def _role_context(grouping, digest, paths):
    if grouping is None:
        return {}
    _require(isinstance(grouping, dict) and grouping.get("grouping_schema_version") == 1 and
             isinstance(grouping.get("source"), dict) and grouping["source"].get("inventory_sha256") == digest and
             isinstance(grouping.get("groups"), list), "Grouping must bind to this exact inventory SHA256.", "EVIDENCE_MISMATCH")
    roles = {}
    for group in grouping["groups"]:
        _require(isinstance(group, dict) and group.get("role") in ("fixed_base", "moving_platform", "transmission_related", "pending") and
                 isinstance(group.get("members"), list), "Invalid grouping roles/members.")
        for member in group["members"]:
            _require(isinstance(member, dict), "Invalid grouping member.")
            path = member.get("occurrence_path")
            _require(isinstance(path, str) and path in paths and path not in roles and
                     member.get("role_status") in ("candidate", "pending", "manual_confirmed"), "Invalid/duplicate grouping occurrence or role status.")
            roles[path] = {"role": group["role"], "role_status": member["role_status"], "reason": member.get("reason")}
    return roles


def relate_axes(inventory, inventory_sha256, cylinder_sources, distance_tolerance_mm, angle_tolerance_deg,
                max_pairs=10000, max_candidates=1000, grouping=None):
    """Pure algorithm; cylinder_sources entries are (original envelope, path, SHA256)."""
    _require(_number(distance_tolerance_mm, 0) and _number(angle_tolerance_deg, 0, 5),
             "Specify finite distance_tolerance_mm > 0 and 0 < angle_tolerance_deg <= 5.", "INVALID_ARGUMENTS")
    _require(type(max_pairs) is int and 1 <= max_pairs <= 100000 and type(max_candidates) is int and 1 <= max_candidates <= 5000,
             "Invalid comparison/output budget.", "INVALID_ARGUMENTS")
    _require(2 <= len(cylinder_sources) <= 32, "Choose 2 to 32 cylinder evidence files.", "INVALID_ARGUMENTS")
    spatial, by_path = spatial_inventory(inventory)
    document = _document(spatial.get("document"))
    _require(spatial.get("units") == {"api_length": "m", "display_length": "mm", "matrix_translation": "m"}, "Unsupported inventory units.")
    components = [_cylinders(e, by_path, document, path, digest) for e, path, digest in cylinder_sources]
    components.sort(key=lambda c: c["occurrence_path"])
    _require(len({c["occurrence_path"] for c in components}) == len(components), "Use one cylinder snapshot per occurrence; repeated input is not another instance.")
    roles = _role_context(grouping, inventory_sha256, by_path)
    errors = [{"code": "SOURCE_INCOMPLETE", "message": "Inventory contains explicit source errors.", "source": "inventory",
               "source_errors": _errors(inventory)}] if inventory.get("status") != "ok" or not spatial.get("complete") or _errors(inventory) else []
    for component in components:
        component["role_context"] = roles.get(component["occurrence_path"])
        if not component["complete"]:
            errors.append({"code": "SOURCE_INCOMPLETE", "message": "Only available cylindrical faces are compared.",
                           "occurrence_path": component["occurrence_path"], "source_path": component["source_path"], "source_errors": component["errors"]})
    total_pairs = sum(len(a["axes"]) * len(b["axes"]) for i, a in enumerate(components) for b in components[i + 1:])
    checked, candidates = 0, []
    def pairs():
        for i, left in enumerate(components):
            for right in components[i + 1:]:
                reference = [a / 2 + b / 2 for a, b in zip(left["origin_root_mm"], right["origin_root_mm"])]
                for a in left["axes"]:
                    for b in right["axes"]:
                        yield left, right, a, b, reference
    for left, right, a, b, reference in pairs():
        if checked >= max_pairs or len(candidates) >= max_candidates:
            break
        metrics = axis_metrics(a, b, reference)
        checked += 1
        if metrics["angle_deg"] > angle_tolerance_deg:
            continue
        kind = "coaxial_candidate" if metrics["axis_offset_at_reference_mm"] <= distance_tolerance_mm else "parallel_candidate"
        candidates.append({"kind": kind, "status": "candidate", "mechanical_relation_confirmed": False,
                           "left": {"occurrence_path": left["occurrence_path"], **a},
                           "right": {"occurrence_path": right["occurrence_path"], **b}, **metrics})
    truncated = checked < total_pairs
    if truncated:
        errors.append({"code": "RELATION_LIMIT", "message": "Comparison/output budget reached; unexamined pairs remain unknown.",
                       "checked_pairs": checked, "total_possible_pairs": total_pairs})
    counts = {kind: sum(c["kind"] == kind for c in candidates) for kind in ("coaxial_candidate", "parallel_candidate")}
    return {"relation_schema_version": 1, "algorithm_version": 1, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "document": spatial["document"], "inventory_sha256": inventory_sha256, "snapshot_atomic": False,
            "parameters": {"distance_tolerance_mm": distance_tolerance_mm, "angle_tolerance_deg": angle_tolerance_deg,
                           "max_pairs": max_pairs, "max_candidates": max_candidates},
            "metric": "Unoriented atan2(|u cross v|, |u dot v|) angle. Offset is distance between projections of the midpoint of the two occurrence origins onto their infinite axes; exact parallel axes give ordinary line distance.",
            "sources": components, "candidates": candidates, "counts": counts,
            "coverage": {"scope": "provided_occurrences_only", "inventory_occurrences": len(by_path),
                         "input_occurrences": len(components), "input_cylindrical_faces": sum(len(c["axes"]) for c in components),
                         "total_possible_pairs": total_pairs, "checked_pairs": checked,
                         "nonparallel_pairs": checked - len(candidates),
                         "zero_cylinder_occurrences": [c["occurrence_path"] for c in components if not c["axes"]]},
            "comparison_complete": not truncated, "complete": not errors, "truncated": truncated, "errors": errors,
            "requires_review": True, "mechanical_relation_confirmed": False, "solidworks_modified": False,
            "limitations": ["Candidates concern infinite cylinder axes, not finite face overlap, contact, fit, connectivity or motion joints. Remote/disjoint coaxial faces can be candidates.",
                            "Near-parallel offset is evaluated at the recorded reference; it is not a global maximum offset over face length. Changing angle/distance thresholds changes candidates.",
                            "Part-definition geometry excludes assembly-instance cuts. Only supplied analytic cylindrical faces are analyzed; empty candidates do not prove absent joints.",
                            "Split cylindrical faces remain separate snapshot-local evidence pairs, not unique mechanical connections; repeated occurrence files are never merged.",
                            "Matching document/configuration/transforms does not prove atomic capture or unchanged shape. Collect in one unchanged session; timestamps and source hashes identify evidence, not authenticity.",
                            "Role labels are copied context only; mate activity, owning-assembly entity frames, rigid bodies, DOF, stroke and pitch are not inferred."]}


def component_relations(root, inventory_path, cylinder_paths, output_path, distance_tolerance_mm, angle_tolerance_deg,
                        max_pairs=10000, max_candidates=1000, grouping_path=None):
    output = json_path(root, output_path, output=True)
    source = json_path(root, inventory_path)
    inventory, digest = read_json(source)
    sources = []
    for name in cylinder_paths:
        path = json_path(root, name)
        envelope, sha = read_json(path)
        sources.append((envelope, str(path), sha))
    grouping, group_sha = read_json(json_path(root, grouping_path)) if grouping_path is not None else (None, None)
    data = relate_axes(inventory, digest, sources, distance_tolerance_mm, angle_tolerance_deg, max_pairs, max_candidates, grouping)
    data["inventory_path"] = str(source)
    data["grouping_source"] = {"path": str(json_path(root, grouping_path)), "sha256": group_sha} if grouping_path is not None else None
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise ToolFailure("OUTPUT_EXISTS", "Choose a new output filename.") from exc
    return success({"output_path": str(output), "inventory_sha256": digest, "counts": data["counts"],
                    "coverage": data["coverage"], "comparison_complete": data["comparison_complete"],
                    "complete": data["complete"], "truncated": data["truncated"],
                    "requires_review": True, "mechanical_relation_confirmed": False, "solidworks_modified": False}, data["errors"])
