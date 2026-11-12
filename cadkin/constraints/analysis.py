"""Combine explicit two-occurrence constraints; this is not a DOF/assembly solver."""
from copy import deepcopy
import math

from cadkin.adapters.face_identity import decode_reference
from cadkin.adapters.mate_records import MATE_TYPES
from cadkin.errors import ToolFailure
from cadkin.face_geometry import unit
from cadkin.geometry import numbers
from cadkin.matching.target import axis_angle
from cadkin.rigid.groups import MOTION_MATES


def require(ok, message):
    if not ok:
        raise ToolFailure('INVALID_CONSTRAINT_SOURCE', message)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def offset(a, b):
    delta = [x-y for x, y in zip(a['point_root_m'], b['point_root_m'])]
    direction = a['direction_root_unit']
    return math.hypot(*(x-dot(delta, direction)*d for x, d in zip(delta, direction)))


def read_geometry(entity, capture):
    raw = entity.get('reference_geometry')
    require(raw is None or isinstance(raw, dict), 'Invalid mate reference geometry.')
    if not raw or raw.get('status') != 'read':
        return None
    require(isinstance(capture, dict) and capture.get('schema_version') == 1 and
            capture.get('scope') == 'direct_root_mate_face_references' and capture.get('frame') == 'root_assembly' and
            capture.get('identity_rechecked') is True, 'Mate geometry lacks live capture provenance.')
    require(entity.get('reference_type_code') == 2 and raw.get('frame') == 'root_assembly' and
            raw.get('identity_method') == 'root_persistent_reference_roundtrip_IsSame', 'Invalid mate face geometry scope.')
    decode_reference(raw.get('persistent_reference'), 'active_root_assembly')
    require(raw.get('entity_params_raw') == entity.get('entity_params_raw'), 'Mate geometry parameters differ from the raw entity.')
    kind = raw.get('surface_type')
    require(kind in ('plane', 'cylinder', 'other'), 'Unsupported mate surface classification.')
    if kind == 'other':
        return None
    params = raw['entity_params_raw']
    require(isinstance(params, list) and (7 if kind == 'cylinder' else 6) <= len(params) <= 64,
            'Missing analytic mate parameters.')
    params = numbers(params, len(params), 'INVALID_CONSTRAINT_SOURCE')
    expected = {'surface_type': kind, 'point_root_m': params[:3], 'direction_root_unit': unit(params[3:6]),
                'radius_m': params[6] if kind == 'cylinder' else None}
    require(all(raw.get(k) == v for k, v in expected.items()), 'Derived mate geometry differs from raw parameters.')
    require(kind != 'cylinder' or params[6] > 0, 'Invalid mate cylinder radius.')
    return {**expected, 'entity_index': entity['entity_index'],
            'occurrence_path': entity['reference_occurrence_path'], 'persistent_reference': deepcopy(raw['persistent_reference'])}


def record_evidence(record, source, pair, capture):
    entities = record.get('entities') or []
    paths = {e.get('reference_occurrence_path') for e in entities if e.get('reference_status') == 'verified_root_occurrence'}
    if not paths.intersection(pair):
        return None
    exact = (len(entities) == record.get('entity_count') == 2 and paths == set(pair) and
             all(e.get('reference_status') == 'verified_root_occurrence' for e in entities))
    activity = record.get('activity', {})
    active = (activity.get('state') == 'unsuppressed_no_feature_error' and activity.get('suppressed') is False and
              activity.get('rolled_back') is False and type(activity.get('feature_error_code')) is int and activity['feature_error_code'] == 0)
    inactive = activity.get('suppressed') is True or activity.get('rolled_back') is True
    kind = MATE_TYPES.get(record.get('type_code'))
    require(record.get('type_name') == kind, 'Mate type name and raw code differ.')
    geometries = [read_geometry(e, capture) for e in entities] if exact else []
    opts = record.get('constraint_options', {})
    require(isinstance(opts, dict), 'Invalid mate constraint options.')
    rotation = None
    if opts.get('status') == 'read':
        require(isinstance(capture, dict) and capture.get('identity_rechecked') is True and kind == 'concentric' and
                opts.get('api') == 'IConcentricMateFeatureData.LockRotation' and
                type(opts.get('concentric_lock_rotation')) is bool, 'Missing concentric option provenance.')
        rotation = opts['concentric_lock_rotation']
    clean = active and not record.get('errors') and record.get('read_status') == 'ok'
    return {'id': f"{source['sha256']}:{record['feature_id']}", 'source': source,
            'feature_id': record['feature_id'], 'feature_name': record.get('feature_name'), 'mate_type': kind,
            'activity': deepcopy(activity), 'errors': deepcopy(record.get('errors', [])),
            'binding': 'exact_two_occurrences' if exact else 'boundary_or_unresolved_entities',
            'verified_reference_paths': sorted(paths), 'usable': exact and clean,
            'inactive': inactive, 'entity_geometry': geometries, 'concentric_lock_rotation': rotation,
            'entity_locators': [{'entity_index': e.get('entity_index'), 'reference_status': e.get('reference_status'),
                                 'occurrence_path': e.get('reference_occurrence_path')} for e in entities]}


def analyze_snapshot(pair, source, envelope, distance_tolerance_mm, angle_tolerance_deg):
    data = envelope['data']; tolerance = distance_tolerance_mm/1000
    records = [r for m in data['mates'] if (r := record_evidence(m, source, pair, data.get('reference_geometry_capture'))) is not None]
    direct = [r for r in records if r['binding'] == 'exact_two_occurrences']
    boundary = [r for r in records if r['binding'] != 'exact_two_occurrences']
    active = [r for r in direct if r['usable']]
    missing, conflicts, constraints = [], [], []
    def gap(code, ids=()):
        item = {'code': code, 'evidence_ids': list(ids)}
        if item not in missing: missing.append(item)
    def conflict(code, ids): conflicts.append({'code': code, 'evidence_ids': list(ids)})
    if envelope['status'] != 'ok' or not data['complete'] or data['truncated']:
        gap('MATE_SOURCE_INCOMPLETE')
    if any(not r['inactive'] for r in boundary): gap('BOUNDARY_OR_UNRESOLVED_MATES', [r['id'] for r in boundary if not r['inactive']])
    for r in direct:
        if not r['usable'] and not r['inactive']: gap('MATE_STATE_OR_REFERENCE_UNRESOLVED', [r['id']])
    for r in active:
        kind, geometries = r['mate_type'], r['entity_geometry']
        if kind == 'lock':
            constraints.append({'kind': 'relative_pose_lock', 'evidence_ids': [r['id']]}); continue
        if kind not in ('concentric', 'coincident'):
            gap('UNSUPPORTED_ACTIVE_CONSTRAINT', [r['id']]); continue
        required = 'cylinder' if kind == 'concentric' else 'plane'
        if len(geometries) != 2 or any(g is None or g['surface_type'] != required for g in geometries):
            gap('MATE_REFERENCE_GEOMETRY_MISSING_OR_UNSUPPORTED', [r['id']]); continue
        a, b = geometries
        angle = axis_angle(a['direction_root_unit'], b['direction_root_unit'])
        separation = offset(a, b) if kind == 'concentric' else abs(dot([x-y for x,y in zip(a['point_root_m'], b['point_root_m'])], a['direction_root_unit']))
        metrics = {'angle_deg': angle, 'separation_mm': separation*1000}
        if angle > angle_tolerance_deg or separation > tolerance:
            conflict('MATE_GEOMETRY_OUTSIDE_TOLERANCE', [r['id']]);
            constraints.append({'kind': 'inconsistent_geometry', 'evidence_ids': [r['id']], 'metrics': metrics}); continue
        constraints.append({'kind': 'coincident_axis' if kind == 'concentric' else 'coincident_plane',
            'evidence_ids': [r['id']], 'geometry': a, 'metrics': metrics,
            'rotation_locked': r['concentric_lock_rotation'] if kind == 'concentric' else None})
        if kind == 'concentric' and r['concentric_lock_rotation'] is None: gap('CONCENTRIC_ROTATION_LOCK_UNKNOWN', [r['id']])
    locks = [c for c in constraints if c['kind'] == 'relative_pose_lock']
    axes = [c for c in constraints if c['kind'] == 'coincident_axis']
    planes = [c for c in constraints if c['kind'] == 'coincident_plane']
    motion = [r['id'] for r in active if r['mate_type'] in MOTION_MATES]
    if locks and motion: conflict('LOCK_WITH_MOTION_MATE', [e for c in locks for e in c['evidence_ids']]+motion)
    patterns = []
    if locks:
        patterns.append({'kind': 'fixed', 'rule': 'explicit_relative_pose_lock',
                         'evidence_ids': [e for c in locks for e in c['evidence_ids']]})
    elif axes:
        first = axes[0]; line = first['geometry']
        parallel = all(axis_angle(line['direction_root_unit'], c['geometry']['direction_root_unit']) <= angle_tolerance_deg for c in axes)
        # Duplicate/coincident axes do not add a constraint; separated parallel lines do.
        separated = parallel and any(offset(line, c['geometry']) > tolerance for c in axes[1:])
        if not parallel: gap('NONPARALLEL_AXIS_COMBINATION_NOT_IMPLEMENTED', [e for c in axes for e in c['evidence_ids']])
        axial_planes = [c for c in planes if axis_angle(line['direction_root_unit'], c['geometry']['direction_root_unit']) <= angle_tolerance_deg]
        other_planes = [c for c in planes if c not in axial_planes]
        if other_planes: gap('OBLIQUE_PLANE_COMBINATION_NOT_IMPLEMENTED', [e for c in other_planes for e in c['evidence_ids']])
        locked = separated or any(c['rotation_locked'] is True for c in axes)
        rotation_known_free = all(c['rotation_locked'] is False for c in axes)
        if parallel:
            kind = 'fixed' if locked and axial_planes else 'prismatic' if locked else 'revolute' if axial_planes and rotation_known_free else None
            rule = 'axis_with_rotation_lock_and_axial_stop' if locked and axial_planes else 'parallel_distinct_axes' if separated else 'axis_with_rotation_lock' if locked else 'axis_with_axial_stop'
            ids = [e for c in axes+axial_planes for e in c['evidence_ids']]
            if kind: patterns.append({'kind': kind, 'rule': rule, 'evidence_ids': ids})
            else: gap('AXIAL_TRANSLATION_OR_ROTATION_NOT_RESOLVED', ids)
    elif not locks:
        gap('NO_SUPPORTED_CONSTRAINT_COMBINATION')
    if not active: gap('NO_USABLE_ACTIVE_PAIR_MATES')
    # Unknown local/modelled constraints cannot become a fully supported local pattern.
    for p in patterns:
        p.update(status='opposed' if conflicts else 'conditional' if missing else 'supported_local_pattern',
                 mechanically_verified=False, degrees_of_freedom=None,
                 assumptions=['Only the explicitly modelled local constraints are considered.',
                              'Assembly-wide, internal-subassembly and physical constraints may remove motion.'])
    return {'source': source, 'mate_evidence': direct, 'boundary_evidence': boundary,
            'constraint_facts': constraints, 'candidates': patterns, 'missing_evidence': missing, 'conflicts': conflicts,
            'state': 'conflicting_evidence' if conflicts else 'candidate_with_gaps' if patterns and missing else
                     'supported_local_pattern' if patterns else 'insufficient_evidence',
            'target_joint_kind': 'unknown', 'target_degrees_of_freedom': None,
            'solver_verified': False, 'motion_tested': False}


def analyze(target, snapshots, distance_tolerance_mm, angle_tolerance_deg, max_pairs=200):
    numbers([distance_tolerance_mm, angle_tolerance_deg], 2, 'INVALID_ARGUMENTS')
    if not (distance_tolerance_mm > 0 and 0 < angle_tolerance_deg <= 5 and type(max_pairs) is int and 1 <= max_pairs <= 1225):
        raise ToolFailure('INVALID_ARGUMENTS', 'Use positive mm tolerance, (0,5] degree tolerance and max_pairs 1–1225.')
    pairs = []
    ordered = sorted(target['pairs'], key=lambda p: (not bool(p['flags']), -p['link_support'], p['id']))
    for pair in ordered[:max_pairs]:
        scenarios = [analyze_snapshot(pair['node_ids'], b, e, distance_tolerance_mm, angle_tolerance_deg) for b,e in snapshots]
        pairs.append({'pair_id': pair['id'], 'occurrence_paths': pair['node_ids'], 'snapshots': scenarios,
            'target_joint_kind': 'unknown', 'target_degrees_of_freedom': None,
            'geometry_context': {'signals': [deepcopy(s) for s in pair['signals'] if 'mate' not in s['kind']],
                                 'axis_relations': deepcopy(pair['axis_relations']), 'axes_truncated': pair['axes_truncated']},
            'flags': deepcopy(pair['flags']) + ([{'code': 'MULTIPLE_MATE_SNAPSHOTS_NOT_COMBINED'}] if len(scenarios)>1 else []),
            'missing_evidence': [] if scenarios else [{'code': 'NO_ROOT_MATE_SOURCE'}],
            'geometry_used_as_constraint': False, 'reference_required': False})
    return {'constraint_analysis_schema_version': 1, 'algorithm_version': 1, 'document': target['document'],
        'parameters': {'distance_tolerance_mm': distance_tolerance_mm, 'angle_tolerance_deg': angle_tolerance_deg, 'max_pairs': max_pairs},
        'pairs': pairs, 'mate_sources': [b for b,_ in snapshots],
        'unmapped_mates': [{'source': b, 'feature_ids': [m['feature_id'] for m in e['data']['mates'] if any(
            x.get('reference_status') != 'verified_root_occurrence' for x in m.get('entities') or []) or not m.get('entities')]} for b,e in snapshots],
        'coverage': {'available_pairs': len(ordered), 'returned_pairs': len(pairs), 'omitted_pairs': max(0,len(ordered)-max_pairs),
            'mate_snapshots': len(snapshots), 'candidate_patterns': sum(len(s['candidates']) for p in pairs for s in p['snapshots']),
            'conflicting_snapshots': sum(bool(s['conflicts']) for p in pairs for s in p['snapshots'])},
        'source_errors': deepcopy(target['errors']), 'solidworks_modified': False, 'requires_human_review': False,
        'mechanically_verified': False, 'degrees_of_freedom_solved': False,
        'limitations': ['Local constraint patterns are candidates, not assembly DOF solutions or demonstrated motion.',
            'Separate mate snapshots are never merged; feature IDs are scoped to their original source SHA256.',
            'Geometry proximity, axis similarity, names and templates do not supply constraint equations.',
            'Only exact two-occurrence root mates are combined. Boundary, multi-entity and unmapped references remain explicit.',
            'Reference geometry captures direct mate faces; these are not matches to a face-catalog index or a topology revision proof.',
            'Supported patterns: explicit lock, concentric cylinders with rotation lock, distinct parallel concentric axes, and axial coincident planes.',
            'Distance/limit mates, oblique planes, nonparallel axes and other mate types are retained but not solved.']}
