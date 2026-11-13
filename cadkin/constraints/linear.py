"""Small SVD nullspaces with explicit scaling, sensitivity and deterministic bases."""
import math
from cadkin.errors import ToolFailure


def numpy_module():
    try:
        import numpy as np
        return np
    except ImportError as exc:
        raise ToolFailure('DEPENDENCY_MISSING', 'Install project dependencies with python -m pip install -e ".[solidworks,templates]".') from exc


def canonical_basis(projector, dimension):
    np = numpy_module(); size = len(projector); basis = []
    for _ in range(dimension):
        candidates = []
        for index in range(size):
            vector = projector[:, index].copy()
            for _pass in range(2):
                for previous in basis: vector -= np.dot(previous, vector)*previous
            candidates.append((float(np.linalg.norm(vector)), index, vector))
        largest = max(row[0] for row in candidates)
        if not math.isfinite(largest) or largest < 1e-8:
            raise ToolFailure('NUMERICAL_SOLUTION_INVALID', 'Nullspace basis could not be resolved.')
        length, _, vector = next(row for row in candidates if row[0] >= largest-1e-12)
        vector /= length
        first = next((v for v in vector if abs(v)>1e-12), 1.)
        if first < 0: vector *= -1
        basis.append(vector)
    return np.array(basis, dtype=float).reshape((dimension, size))


def decompose(rows, columns, relative_tolerance):
    np = numpy_module()
    matrix = np.asarray(rows, dtype=float).reshape((-1, columns))
    if not np.isfinite(matrix).all(): raise ToolFailure('NUMERICAL_SOLUTION_INVALID', 'Non-finite constraint matrix.')
    # Pad short matrices only. Reduced SVD never allocates an m-by-m matrix for long inventories.
    padded = np.vstack((matrix, np.zeros((max(0, columns-len(matrix)), columns))))
    try:
        _, singular, vh = np.linalg.svd(padded, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise ToolFailure('NUMERICAL_SOLUTION_INVALID', 'Constraint SVD did not converge.') from exc
    if not np.isfinite(singular).all() or not np.isfinite(vh).all():
        raise ToolFailure('NUMERICAL_SOLUTION_INVALID', 'Constraint SVD returned non-finite results.')
    peak = float(singular[0]) if len(singular) else 0.
    floor = np.finfo(float).eps*max(padded.shape)*max(peak, 1.)
    thresholds = [max(peak*relative_tolerance*factor, floor) for factor in (.1, 1., 10.)]
    ranks = [int(np.count_nonzero(singular > threshold)) for threshold in thresholds]
    rank = ranks[1]; nullity = columns-rank
    projector = vh[rank:].T @ vh[rank:]
    basis = canonical_basis(projector, nullity)
    residual = float(np.linalg.norm(matrix @ basis.T, ord=2)) if len(matrix) and nullity else 0.
    orthogonal_error = float(np.linalg.norm(basis @ basis.T-np.eye(nullity))) if nullity else 0.
    if residual > max(thresholds[1]*10, 1e-10) or orthogonal_error > 1e-8:
        raise ToolFailure('NUMERICAL_SOLUTION_INVALID', 'Nullspace residual or orthogonality check failed.')
    return {'rank': rank, 'nullity': nullity, 'rank_stable': ranks[0] == ranks[2],
        'singular_values': singular.tolist(), 'threshold': float(thresholds[1]),
        'rank_at_tenth_threshold': ranks[0], 'rank_at_tenfold_threshold': ranks[2],
        'rank_range': [min(ranks), max(ranks)], 'nullity_range': [columns-max(ranks), columns-min(ranks)],
        'nullspace_projector': projector.tolist(), 'basis': basis.tolist(),
        'max_nullspace_residual': residual, 'orthogonality_error': orthogonal_error}
