"""Pure, unit-explicit conversions; no COM, MCP or skill dependencies."""
import math

from cadkin.errors import ToolFailure


def numbers(raw, count, code):
    if not isinstance(raw, (tuple, list)) or len(raw) != count:
        raise ToolFailure(code, f"Expected {count} numeric values, not a missing or malformed array.")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in raw):
        raise ToolFailure(code, "The array contains non-numeric or non-finite values.")
    return [float(x) for x in raw]


def millimeters(vector):
    return numbers([x * 1000.0 for x in vector], 3, "INVALID_SPATIAL_VALUE")


def transform_from_sw(raw):
    """SW row-axis storage -> column-vector affine matrix: p_root = T @ p_local."""
    data = numbers(raw, 16, "INVALID_TRANSFORM")
    rows = [data[3 * i:3 * i + 3] for i in range(3)]
    for i in range(3):
        for j in range(3):
            dot = sum(rows[i][k] * rows[j][k] for k in range(3))
            if not math.isclose(dot, float(i == j), abs_tol=1e-7, rel_tol=1e-7):
                raise ToolFailure("INVALID_TRANSFORM", "Rotation axes are not orthonormal; no automatic repair was applied.")
    scale = data[12]
    if scale == 0:
        raise ToolFailure("INVALID_TRANSFORM", "The transform scale is zero.")
    # Rotation, then scale, then translation. Translation is NOT scaled.
    matrix = [[scale * data[3 * column + row] for column in range(3)] + [data[9 + row]]
              for row in range(3)] + [[0.0, 0.0, 0.0, 1.0]]
    numbers([x for row in matrix for x in row], 16, "INVALID_TRANSFORM")
    origin = data[9:12]
    return {"source": "IComponent2.Transform2.ArrayData", "raw_array": data,
            "to_root": matrix, "scale": scale, "origin_root_m": origin,
            "origin_root_mm": millimeters(origin)}


def multiply(left, right):
    result = [[sum(left[i][k] * right[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    numbers([x for row in result for x in row], 16, "INVALID_TRANSFORM")
    return result


def inverse_similarity(matrix):
    # Matrices come from validated orthonormal axes with a uniform nonzero scale.
    scale = math.hypot(*(matrix[i][0] for i in range(3)))
    if not math.isfinite(scale) or scale == 0:
        raise ToolFailure("INVALID_TRANSFORM", "Cannot invert the parent transform.")
    inverse = [[(matrix[j][i] / scale) / scale for j in range(3)] for i in range(3)]
    result = [row + [-sum(row[j] * matrix[j][3] for j in range(3))] for row in inverse]
    result.append([0.0, 0.0, 0.0, 1.0])
    numbers([x for row in result for x in row], 16, "INVALID_TRANSFORM")
    return result


def bounding_box(raw):
    data = numbers(raw, 6, "INVALID_BOUNDING_BOX")
    low = [min(data[i], data[i + 3]) for i in range(3)]
    high = [max(data[i], data[i + 3]) for i in range(3)]
    size = numbers([high[i] - low[i] for i in range(3)], 3, "INVALID_BOUNDING_BOX")
    center = [low[i] / 2 + high[i] / 2 for i in range(3)]
    return {"source": "IComponent2.GetBox(false,false)", "raw_array_m": data,
            "frame": "root_assembly", "approximate": True,
            "min_m": low, "max_m": high, "size_m": size, "center_m": center,
            "min_mm": millimeters(low), "max_mm": millimeters(high),
            "size_mm": millimeters(size), "center_mm": millimeters(center),
            "limitation": "Approximate root-axis-aligned enclosure, not intrinsic part dimensions, center of mass, precision metrology or collision evidence; may change after rebuild."}
