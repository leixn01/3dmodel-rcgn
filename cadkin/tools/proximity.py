"""Offline approximate-box worklists; hints schedule measurements, never prove contact."""
from datetime import datetime, timezone
import math
import json

from cadkin.errors import ToolFailure, success
from cadkin.geometry import bounding_box, numbers
from cadkin.tools.files import json_path, read_json
from cadkin.tools.inventory import spatial_inventory


def require(condition, message, code='INVALID_PROXIMITY_SOURCE'):
    if not condition:
        raise ToolFailure(code, message)


def nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def box_gap(left, right):
    gaps = [max(0.0, left['min_mm'][i] - right['max_mm'][i], right['min_mm'][i] - left['max_mm'][i]) for i in range(3)]
    gap = math.hypot(*gaps)
    numbers([gap], 1, 'INVALID_BOUNDING_BOX')
    return gap


def proximity_candidates(inventory, inventory_sha256, max_box_gap_mm, occurrence_paths=None, max_pairs=20000, max_candidates=200):
    require(nonnegative(max_box_gap_mm), 'Specify a finite nonnegative box-gap screening threshold in millimeters.', 'INVALID_ARGUMENTS')
    require(type(max_pairs) is int and 1 <= max_pairs <= 200000 and type(max_candidates) is int and 1 <= max_candidates <= 2000,
            'Invalid pair/candidate budget.', 'INVALID_ARGUMENTS')
    spatial, nodes = spatial_inventory(inventory)
    require(spatial.get('units') == {'api_length': 'm', 'display_length': 'mm', 'matrix_translation': 'm'}, 'Expected meter raw / millimeter display inventory.')
    parents = {node.get('parent_occurrence_path') for node in nodes.values()}
    leaves = sorted(set(nodes) - parents)
    if occurrence_paths is not None:
        require(isinstance(occurrence_paths, list) and 2 <= len(occurrence_paths) <= 200 and
                all(isinstance(p, str) and p in leaves for p in occurrence_paths) and len(set(occurrence_paths)) == len(occurrence_paths),
                'Select 2–200 unique leaf occurrence paths from the inventory.', 'INVALID_ARGUMENTS')
        paths = sorted(occurrence_paths)
    else:
        paths = leaves
    require(len(paths) <= 5000, 'Choose a smaller explicit scope for more than 5000 leaves.', 'INVALID_ARGUMENTS')
    errors = []
    source_errors = inventory.get('errors')
    require(isinstance(source_errors, list) and all(isinstance(e, dict) for e in source_errors), 'Missing inventory errors.')
    if inventory['status'] != 'ok' or spatial.get('complete') is not True or source_errors:
        errors.append({'code': 'SOURCE_INCOMPLETE', 'message': 'Inventory has incomplete geometry or source errors.', 'source_errors': source_errors})
    boxes, unranked = {}, []
    for path in paths:
        node = nodes[path]
        try:
            require(node.get('suppression_state') in (2, 3) and node.get('is_suppressed') is False, 'Occurrence is not resolved.', 'UNRESOLVED_COMPONENT')
            box = node.get('bounding_box')
            require(isinstance(box, dict) and node.get('bounding_box_status') == 'ok', 'No readable bounding box; collect spatial data with boxes.', 'BOUNDING_BOX_UNAVAILABLE')
            require(box.get('frame') == 'root_assembly' and box.get('approximate') is True, 'Unsupported box frame/type.')
            normalized = bounding_box(box.get('raw_array_m'))
            for field in ('min_mm', 'max_mm'):
                values = numbers(box.get(field), 3, 'INVALID_BOUNDING_BOX')
                require(all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9) for a, b in zip(values, normalized[field])), 'Derived box differs from raw meter data.')
            boxes[path] = normalized
        except ToolFailure as exc:
            unranked.append({'occurrence_path': path, 'code': exc.code, 'message': str(exc)})
    if unranked:
        errors.append({'code': 'UNRANKED_OCCURRENCES', 'message': 'Missing/unreadable boxes remain unknown; no zero boxes substituted.', 'count': len(unranked)})
    eligible = sorted(boxes)
    possible = len(eligible) * (len(eligible) - 1) // 2
    checked, candidates = 0, []
    for i, left in enumerate(eligible):
        for right in eligible[i + 1:]:
            if checked >= max_pairs:
                break
            checked += 1
            gap = box_gap(boxes[left], boxes[right])
            if gap <= max_box_gap_mm:
                candidates.append({'occurrence_paths': [left, right], 'box_gap_hint_mm': gap,
                                   'basis': 'approximate_root_aabb', 'measurement_required': True})
        if checked >= max_pairs:
            break
    candidates.sort(key=lambda c: (c['box_gap_hint_mm'], c['occurrence_paths']))
    matching_count = len(candidates)
    truncated = checked < possible or matching_count > max_candidates
    if checked < possible:
        errors.append({'code': 'PROXIMITY_PAIR_LIMIT', 'message': 'Pair scan budget reached; unexamined pairs remain unknown.'})
    if matching_count > max_candidates:
        errors.append({'code': 'PROXIMITY_CANDIDATE_LIMIT', 'message': 'Output contains only the closest hints among examined pairs.'})
    return {'proximity_schema_version': 1, 'algorithm_version': 1, 'document': spatial['document'],
            'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'inventory_sha256': inventory_sha256,
            'parameters': {'max_box_gap_mm': max_box_gap_mm, 'occurrence_paths': occurrence_paths,
                           'max_pairs': max_pairs, 'max_candidates': max_candidates},
            'scope_occurrence_paths': paths, 'candidates': candidates[:max_candidates], 'unranked_occurrences': unranked,
            'coverage': {'scope': 'selected_leaf_occurrences' if occurrence_paths is not None else 'inventory_leaf_occurrences',
                         'scope_leaves': len(paths), 'scope_pairs': len(paths) * (len(paths) - 1) // 2,
                         'boxed_leaves': len(boxes), 'eligible_pairs': possible, 'checked_pairs': checked,
                         'matching_hints_before_output_limit': matching_count, 'returned_candidates': min(max_candidates, matching_count)},
            'pair_scan_complete': checked == possible, 'complete': not errors, 'truncated': truncated, 'errors': errors,
            'requires_review': True, 'solidworks_modified': False, 'contact_confirmed': False, 'mechanical_relation_confirmed': False,
            'limitations': ['Approximate GetBox values are only worklist hints, not engineering clearance or contact measurements.',
                            'Box overlap means a zero box gap, not geometric intersection or contact. Excluded/unranked pairs are not proven disconnected.',
                            'Pair budgets scan a stable path-order prefix, then rank that examined subset; they do not establish global nearest neighbors.',
                            'Leaf occurrences are not guaranteed to be part documents; the live distance tool verifies that requirement.',
                            'No atomic geometry snapshot or tolerance guarantee; no mates, rigid bodies or motion joints inferred.']}


def write_result(output, data):
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open('x', encoding='utf-8') as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise ToolFailure('OUTPUT_EXISTS', 'Choose a new output filename.') from exc


def component_proximity(root, inventory_path, output_path, **parameters):
    output, source = json_path(root, output_path, output=True), json_path(root, inventory_path)
    inventory, digest = read_json(source)
    data = proximity_candidates(inventory, digest, **parameters)
    data['inventory_path'] = str(source)
    write_result(output, data)
    return success({'output_path': str(output), 'coverage': data['coverage'], 'complete': data['complete'], 'truncated': data['truncated'],
                    'requires_review': True, 'contact_confirmed': False, 'mechanical_relation_confirmed': False,
                    'solidworks_modified': False}, data['errors'])
