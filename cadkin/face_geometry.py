"""Pure transforms and local face-probe interpretation; no COM or topology guesses."""
import math

from cadkin.errors import ToolFailure
from cadkin.geometry import numbers, millimeters, inverse_similarity, transform_from_sw


def require(condition, message, code='INVALID_FACE_PROBE_SOURCE'):
    if not condition:
        raise ToolFailure(code, message)


def unit(vector):
    vector = numbers(vector, 3, 'INVALID_FACE_NORMAL')
    length = math.hypot(*vector)
    require(math.isfinite(length) and length > 0, 'Normal is zero or invalid.', 'INVALID_FACE_NORMAL')
    return [x / length for x in vector]


def point(matrix, xyz):
    xyz = numbers(xyz, 3, 'INVALID_FACE_POINT')
    return numbers([sum(matrix[i][j] * xyz[j] for j in range(3)) + matrix[i][3] for i in range(3)], 3, 'INVALID_FACE_POINT')


def part_point(transform, root_m):
    return point(inverse_similarity(transform['to_root']), root_m)


def root_normal(transform, surface_normal, reversed_sense):
    require(type(reversed_sense) is bool, 'Face orientation must be Boolean.')
    n = unit(surface_normal)
    if reversed_sense:
        n = [-x for x in n]
    # For a uniform-scale orthogonal map, normalized inverse-transpose equals
    # normalized M*n, including negative scales/reflections. Never transform a normal as a point.
    return unit([sum(transform['to_root'][i][j] * n[j] for j in range(3)) for i in range(3)])


def descriptor(raw):
    require(isinstance(raw, dict), 'Missing face descriptor.')
    kind = raw.get('surface_type')
    require(kind in ('plane', 'cylinder', 'other'), 'Unknown face surface type.')
    require(type(raw.get('body_type')) is int and raw['body_type'] in (0, 1), 'Only solid/sheet face geometry is supported.')
    require(type(raw.get('face_in_surface_sense')) is bool, 'Missing face sense.')
    area = numbers([raw.get('area_part_m2')], 1, 'INVALID_FACE_GEOMETRY')[0]
    require(area > 0, 'Face area must be positive.', 'INVALID_FACE_GEOMETRY')
    uv = numbers(raw.get('uv_bounds'), 4, 'INVALID_FACE_GEOMETRY')
    require(uv[0] < uv[1] and uv[2] < uv[3], 'Invalid UV bounds.', 'INVALID_FACE_GEOMETRY')
    params = raw.get('surface_parameters_part')
    if kind == 'plane':
        params = numbers(params, 6, 'INVALID_FACE_GEOMETRY'); unit(params[:3])
    elif kind == 'cylinder':
        params = numbers(params, 7, 'INVALID_FACE_GEOMETRY'); unit(params[3:6])
        require(params[6] > 0, 'Invalid cylinder radius.', 'INVALID_FACE_GEOMETRY')
    else:
        require(params is None, 'Unsupported surfaces do not carry guessed analytic parameters.')
    return {'surface_type': kind, 'surface_parameters_part': params, 'area_part_m2': area,
            'uv_bounds': uv, 'body_type': raw['body_type'], 'face_in_surface_sense': raw['face_in_surface_sense']}


def pair_metrics(left, right, left_normal=None, right_normal=None):
    left = numbers(left, 3, 'INVALID_FACE_POINT'); right = numbers(right, 3, 'INVALID_FACE_POINT')
    gap = math.dist(left, right)
    numbers([gap, gap * 1000], 2, 'INVALID_FACE_POINT')
    a = None if left_normal is None else unit(left_normal)
    b = None if right_normal is None else unit(right_normal)
    opposition = None
    alignments = None
    if a is not None and b is not None:
        dot = max(-1., min(1., -sum(x * y for x, y in zip(a, b))))
        opposition = math.degrees(math.acos(dot))
        if gap > 0:
            direction = [(right[i] - left[i]) / gap for i in range(3)]
            alignments = [math.degrees(math.acos(max(-1., min(1., sum(a[i] * direction[i] for i in range(3)))))),
                          math.degrees(math.acos(max(-1., min(1., -sum(b[i] * direction[i] for i in range(3))))))]
    return {'point_left_root_m': left, 'point_right_root_m': right,
            'point_left_root_mm': millimeters(left), 'point_right_root_mm': millimeters(right),
            'gap_m': gap, 'gap_mm': gap * 1000, 'normal_left_root_unit': a, 'normal_right_root_unit': b,
            'opposition_error_deg': opposition, 'gap_alignment_error_deg': alignments}


def classify(metrics, contact_tolerance_mm, angle_tolerance_deg, solid_faces=True):
    for v in (contact_tolerance_mm, angle_tolerance_deg):
        numbers([v], 1, 'INVALID_ARGUMENTS')
    require(contact_tolerance_mm >= 0 and 0 <= angle_tolerance_deg <= 90, 'Use nonnegative gap and 0–90 degree angle thresholds.', 'INVALID_ARGUMENTS')
    if metrics is None:
        return 'unresolved'
    if metrics['gap_mm'] > contact_tolerance_mm:
        return 'sample_gap_above_tolerance'  # Does NOT prove that the entire faces are separated.
    opposition, alignments = metrics['opposition_error_deg'], metrics['gap_alignment_error_deg']
    if solid_faces and opposition is not None and opposition <= angle_tolerance_deg and (alignments is None or max(alignments) <= angle_tolerance_deg):
        return 'near_face_contact_candidate'
    return 'near_points_orientation_unconfirmed'
