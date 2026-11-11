"""Explainable occurrence-role candidates from exported data; never touches COM."""
import heapq
import json
import math
import re

from cadkin.errors import ToolFailure, success
from cadkin.tools.files import json_path, read_json

ROLES = {"fixed_base": "固定基体候选", "moving_platform": "移动平台候选",
         "transmission_related": "传动/导向相关件候选", "pending": "待确认"}
RULES = {
    "fixed_base": (r"机架|底座|底板|(?<![a-z0-9])(?:frame|base|baseplate)(?![a-z0-9])",),
    "moving_platform": (r"升降台|移动平台|滑台|滑座|(?<![a-z0-9])(?:platform|carriage)(?![a-z0-9])",),
    "transmission_related": (r"电机|伺服|减速机|丝杠|丝杆|联轴器|同步轮|导轨|(?<![a-z0-9])(?:motor|servo|gearbox|coupling|belt|pulley|rail|ball[ _-]?screw|lead[ _-]?screw)(?![a-z0-9])",),
}


def _inventory(envelope):
    if not isinstance(envelope, dict) or envelope.get("status") not in ("ok", "partial"):
        raise ToolFailure("INVALID_INVENTORY", "Input must be an actual spatial inventory result envelope.")
    data = envelope.get("data")
    if not isinstance(data, dict) or data.get("spatial_schema_version") != 1 or not isinstance(data.get("components"), list):
        raise ToolFailure("INVALID_INVENTORY", "Expected spatial_schema_version=1 and components.")
    if (data.get("truncated") or not data.get("collection_complete", data.get("complete", False)) or
            not data.get("hierarchy_complete", data.get("complete", False))):
        raise ToolFailure("GROUPING_REQUIRES_COMPLETE_INVENTORY", "Collect all pages and resolve hierarchy errors before grouping. Missing geometry may remain explicit.")
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


def _center(node):
    box = node.get("bounding_box")
    values = box.get("center_mm") if isinstance(box, dict) else None
    if not isinstance(values, list) or len(values) != 3 or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values):
        return None
    return values


def group_inventory(envelope, source_sha256, scope_occurrence_path=None, review=None):
    data, by_path = _inventory(envelope)
    if scope_occurrence_path is not None and scope_occurrence_path not in by_path:
        raise ToolFailure("COMPONENT_NOT_FOUND", "Grouping scope must be an exact occurrence path.")
    children = {path: [] for path in by_path}
    for path, node in by_path.items():
        parent = node.get("parent_occurrence_path")
        if parent is not None:
            children[parent].append(path)
    scoped = set()
    queue = [scope_occurrence_path] if scope_occurrence_path else [p for p, n in by_path.items() if n.get("parent_occurrence_path") is None]
    while queue:
        path = queue.pop()
        scoped.add(path)
        queue.extend(children[path])
    leaves = sorted(path for path in scoped if not children[path])
    assignments = {}
    if review is not None:
        if not isinstance(review, dict) or review.get("inventory_sha256") != source_sha256 or not isinstance(review.get("assignments"), list):
            raise ToolFailure("INVALID_REVIEW", "Review must bind to this exact inventory_sha256 and contain assignments.")
        for item in review["assignments"]:
            if (not isinstance(item, dict) or not isinstance(item.get("occurrence_path"), str) or
                    item["occurrence_path"] not in leaves or item["occurrence_path"] in assignments or
                    item.get("role") not in ROLES or item.get("decision") not in ("confirmed", "pending") or
                    not isinstance(item.get("reason"), str) or not item["reason"].strip() or
                    (item["decision"] == "confirmed" and item["role"] == "pending") or
                    (item["decision"] == "pending" and item["role"] != "pending")):
                raise ToolFailure("INVALID_REVIEW", "Each review needs one unique scoped leaf, a valid role/decision, and a reason; pending decisions use role=pending.")
            assignments[item["occurrence_path"]] = item
    groups = {role: [] for role in ROLES}
    centers = {path: _center(by_path[path]) for path in leaves}
    neighbors_enabled = len(leaves) <= 2000
    for path in leaves:
        node = by_path[path]
        basename = path.rsplit("/", 1)[-1].lower()
        evidence, matches = [], []
        for role, patterns in RULES.items():
            for pattern in patterns:
                match = re.search(pattern, basename)
                if match:
                    matches.append(role)
                    evidence.append({"kind": "name_keyword", "rule": role + ":v1", "text": match.group(),
                                     "source": "occurrence basename", "supports": "role candidate only"})
                    break
        role = matches[0] if len(matches) == 1 else "pending"
        status = "candidate" if role != "pending" else "pending"
        reason = "One name-rule match; human confirmation required." if role != "pending" else (
            "Conflicting name clues." if matches else "No reliable role clue; do not infer motion from position.")
        if path in assignments:
            item = assignments[path]
            role = item["role"]
            status = "manual_confirmed" if item["decision"] == "confirmed" else "pending"
            reason = item["reason"]
            evidence.append({"kind": "review_file", "decision": item["decision"], "reason": item["reason"]})
        nearby = []
        if neighbors_enabled and centers[path] is not None:
            distances = ((math.dist(centers[path], center), other) for other, center in centers.items()
                         if other != path and center is not None)
            nearby = [{"occurrence_path": other, "box_center_distance_mm": distance}
                      for distance, other in heapq.nsmallest(3, distances)]
        groups[role].append({"occurrence_path": path, "parent_occurrence_path": node.get("parent_occurrence_path"),
                             "file_path": node.get("file_path"), "referenced_configuration": node.get("referenced_configuration"),
                             "role_status": status, "reason": reason, "evidence": evidence,
                             "candidate_roles": matches, "rigid_body_confirmed": False,
                             "spatial_context": {"transform": node.get("transform"), "bounding_box": node.get("bounding_box"),
                                                 "spatial_errors": node.get("spatial_errors", [])},
                             "nearest_box_centers": nearby})
    counts = {role: len(members) for role, members in groups.items()}
    confirmed = sum(member["role_status"] == "manual_confirmed" for members in groups.values() for member in members)
    return {"grouping_schema_version": 1, "rules_version": 1,
            "source": {"inventory_sha256": source_sha256, "document": data.get("document"),
                       "inventory_signature": data.get("inventory_signature"), "captured_at_utc": data.get("captured_at_utc")},
            "scope_occurrence_path": scope_occurrence_path,
            "groups": [{"role": role, "label": ROLES[role], "members": members} for role, members in groups.items()],
            "coverage": {"inventory_occurrences": len(by_path), "scoped_occurrences": len(scoped),
                         "scoped_leaf_occurrences": len(leaves), "container_occurrences": len(scoped) - len(leaves),
                         "assigned_once": sum(counts.values()) == len(leaves)},
            "counts": counts, "manual_confirmed_count": confirmed, "requires_review": confirmed < len(leaves),
            "source_errors": envelope.get("errors", []),
            "neighbor_hints_computed": neighbors_enabled,
            "limitations": ["Role candidates are not rigid-body groups, fixed-state proof or motion relations.",
                            "Nearest approximate box centers are review hints, not contact/collision evidence.",
                            "Only leaf occurrences are assigned; subassembly containers are counted separately.",
                            "Anonymous STEP names remain pending. For more than 2000 leaves, choose a scope for neighbor hints."]}


def group_components(root, inventory_path, output_path, scope_occurrence_path=None, review_path=None):
    source = json_path(root, inventory_path)
    output = json_path(root, output_path, output=True)
    envelope, digest = read_json(source)
    review, review_digest = read_json(json_path(root, review_path)) if review_path is not None else (None, None)
    data = group_inventory(envelope, digest, scope_occurrence_path, review)
    data["source"]["inventory_path"] = str(source)
    data["review_sha256"] = review_digest
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise ToolFailure("OUTPUT_EXISTS", "Choose a new output filename.") from exc
    return success({"output_path": str(output), "inventory_sha256": digest, "counts": data["counts"],
                    "coverage": data["coverage"], "manual_confirmed_count": data["manual_confirmed_count"],
                    "requires_review": data["requires_review"], "solidworks_modified": False}, envelope.get("errors"))
