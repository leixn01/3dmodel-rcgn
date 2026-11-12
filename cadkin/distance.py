"""Unit-explicit validation of a CAD distance and its two witness points."""
import math

from cadkin.errors import ToolFailure
from cadkin.geometry import numbers, millimeters


def distance_result(distance, point_left, point_right):
    distance = numbers([distance], 1, 'INVALID_DISTANCE_RESULT')[0]
    if distance == -1.0:
        raise ToolFailure('DISTANCE_NO_SOLUTION', 'ClosestDistance returned -1; no distance was inferred.')
    if distance < 0:
        raise ToolFailure('INVALID_DISTANCE_RESULT', 'Expected a nonnegative distance in meters.')
    left = numbers(point_left, 3, 'INVALID_DISTANCE_RESULT')
    right = numbers(point_right, 3, 'INVALID_DISTANCE_RESULT')
    witness_distance = math.dist(left, right)
    numbers([witness_distance, distance * 1000], 2, 'INVALID_DISTANCE_RESULT')
    if not math.isclose(distance, witness_distance, rel_tol=1e-7, abs_tol=1e-8):
        raise ToolFailure('DISTANCE_POINT_MISMATCH', 'Returned distance and witness-point separation disagree.')
    return {'distance_m': distance, 'distance_mm': distance * 1000,
            'point_left_m': left, 'point_right_m': right,
            'point_left_mm': millimeters(left), 'point_right_mm': millimeters(right),
            'point_separation_m': witness_distance, 'frame': 'root_assembly'}
