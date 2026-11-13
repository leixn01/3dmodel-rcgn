"""Idealized two-body instantaneous constraint models; no CAD or assembly-wide solve."""
from copy import deepcopy
import math

from cadkin.errors import ToolFailure
from cadkin.geometry import numbers
from cadkin.face_geometry import unit
from cadkin.constraints.linear import decompose

PATTERN_GAPS = {'NONPARALLEL_AXIS_COMBINATION_NOT_IMPLEMENTED', 'OBLIQUE_PLANE_COMBINATION_NOT_IMPLEMENTED',
    'AXIAL_TRANSLATION_OR_ROTATION_NOT_RESOLVED', 'NO_SUPPORTED_CONSTRAINT_COMBINATION'}
SUPPORTED = {'relative_pose_lock', 'coincident_axis', 'coincident_plane'}


def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def tangents(direction):
    index = min(range(3), key=lambda i: abs(direction[i]))
    axis = [float(i==index) for i in range(3)]
    first = unit(cross(direction, axis))
    return first, unit(cross(direction, first))


def model_snapshot(pair, snapshot, length_m, relative_tolerance, max_constraints, source_errors):
    facts = snapshot['constraint_facts']
    unknown = [f['kind'] for f in facts if f['kind'] not in SUPPORTED | {'inconsistent_geometry'}]
    if unknown: raise ToolFailure('INVALID_CONSTRAINT_SOURCE', 'Unsupported constraint-fact schema.')
    records = {r['id']: r for r in snapshot['mate_evidence']}
    selected = [f for f in facts if f['kind'] in SUPPORTED][:max_constraints]
    available = sum(f['kind'] in SUPPORTED for f in facts)
    omitted = available-len(selected)
    geometries = {}
    for fact in selected:
        if fact['kind'] == 'relative_pose_lock': continue
        # Use the first (fixed-for-analysis) occurrence's face, independent of COM entity ordering.
        record = records[fact['evidence_ids'][0]]
        geometry = next((g for g in record['entity_geometry'] if g and g['occurrence_path']==pair[0]), None)
        if geometry is None: raise ToolFailure('INVALID_CONSTRAINT_SOURCE', 'Constraint lacks its fixed occurrence face.')
        geometries[fact['evidence_ids'][0]] = geometry
    points = [g['point_root_m'] for g in geometries.values()]
    origin = [sum(p[i]/len(points) for p in points) for i in range(3)] if points else [0.,0.,0.]
    numbers(origin, 3, 'NUMERICAL_SOLUTION_INVALID')
    rows, statements = [], []
    def add_row(coefficients, equation, fact):
        coefficients = numbers(coefficients, 6, 'NUMERICAL_SOLUTION_INVALID')
        norm = math.hypot(*coefficients)
        if not math.isfinite(norm) or norm==0: raise ToolFailure('NUMERICAL_SOLUTION_INVALID', 'Invalid constraint equation.')
        rows.append({'coefficients': [x/norm for x in coefficients], 'equation': equation,
            'evidence_ids': fact['evidence_ids'], 'normalization_norm': norm})
    for fact in selected:
        start = len(rows); kind = fact['kind']; geometry = None
        if kind == 'relative_pose_lock':
            for i in range(6): add_row([float(j==i) for j in range(6)], 'relative_pose_lock', fact)
        else:
            geometry = geometries[fact['evidence_ids'][0]]
            direction = unit(geometry['direction_root_unit'])
            relative = [(p-o)/length_m for p,o in zip(geometry['point_root_m'], origin)]
            numbers(relative,3,'NUMERICAL_SOLUTION_INVALID')
            first, second = tangents(direction)
            for tangent in (first,second): add_row([0.,0.,0.]+tangent, 'parallel_direction_velocity', fact)
            for normal in (first,second) if kind=='coincident_axis' else (direction,):
                add_row(normal+cross(relative,normal), 'transverse_point_velocity' if kind=='coincident_axis' else 'plane_normal_velocity', fact)
            if kind=='coincident_axis' and fact['rotation_locked'] is True:
                add_row([0.,0.,0.]+direction, 'locked_axial_rotation', fact)
        statements.append({'kind':kind,'evidence_ids':fact['evidence_ids'],
            'row_indices':list(range(start,len(rows))), 'idealization_face':deepcopy(geometry),
            'measured_pair_residuals':deepcopy(fact.get('metrics')),
            'rotation_locked':fact.get('rotation_locked')})
    blockers = [deepcopy(m) for m in snapshot['missing_evidence'] if m['code'] not in PATTERN_GAPS]
    if omitted: blockers.append({'code':'LOCAL_CONSTRAINT_LIMIT','omitted_constraints':omitted})
    if source_errors: blockers.append({'code':'TARGET_SOURCE_ERRORS','errors':deepcopy(source_errors)})
    numeric = decompose([r['coefficients'] for r in rows],6,relative_tolerance) if rows else None
    stable = bool(numeric and numeric['rank_stable'])
    if numeric and not stable: blockers.append({'code':'NUMERICAL_RANK_SENSITIVE','rank_range':numeric['rank_range']})
    conflict = bool(snapshot['conflicts'])
    modes = []
    if stable and not conflict:
        for vector in numeric['basis']:
            modes.append({'scaled_twist':vector,
                'linear_velocity_at_origin_m_per_unit_time':[v*length_m for v in vector[:3]],
                'angular_velocity_rad_per_unit_time':vector[3:]})
    # Pure translations are the omega=0 slice, not the translational projection of coupled twists.
    translations = decompose([r['coefficients'][:3] for r in rows],3,relative_tolerance) if stable and not conflict else None
    if translations and (not translations['rank_stable'] or translations['nullity']>numeric['nullity']):
        blockers.append({'code':'TRANSLATION_SUBSPACE_SENSITIVE'}); translations=None
    complete = bool(numeric and stable and not blockers and not conflict)
    return {'source':snapshot['source'], 'fixed_for_analysis_occurrence':pair[0], 'moving_relative_occurrence':pair[1],
        'frame':'root_assembly_axes', 'velocity_origin_root_m':origin, 'origin_rule':'mean_of_selected_fixed_occurrence_face_points_or_root_origin_for_locks',
        'twist_order':['vx_over_length','vy_over_length','vz_over_length','wx','wy','wz'],
        'characteristic_length_m':length_m, 'rows':rows, 'modeled_constraints':statements,
        'coverage':{'available_supported_constraints':available,'modeled_constraints':len(selected),'omitted_constraints':omitted,'equations':len(rows)},
        'linear_solution':numeric, 'known_constraint_nullity':numeric['nullity'] if numeric else None,
        'dependent_linear_equations':len(rows)-numeric['rank'] if numeric else None,
        'modeled_instantaneous_dof':numeric['nullity'] if complete else None,
        'status':'conflicting_source' if conflict else 'no_supported_constraint_model' if not rows else
            'numerically_sensitive' if not stable else 'partial_constraint_model' if blockers else 'modeled_local_snapshot',
        'motion_modes':modes, 'mode_scope':'known_supported_constraint_subset_only',
        'pure_translation_directions_root':translations['basis'] if translations else [],
        'pure_translation_dimension':translations['nullity'] if translations else None,
        'source_missing_evidence':deepcopy(snapshot['missing_evidence']), 'unresolved_evidence':blockers,
        'pattern_gaps_addressed':[deepcopy(m) for m in snapshot['missing_evidence'] if m['code'] in PATTERN_GAPS] if rows else [],
        'source_conflicts':deepcopy(snapshot['conflicts']), 'source_pattern_candidates':deepcopy(snapshot['candidates']),
        'constraint_system_solved':complete, 'assembly_dof_solved':False,'finite_motion_verified':False,
        'target_joint_kind':'unknown','target_degrees_of_freedom':None}


def solve_analysis(analysis, characteristic_length_mm, relative_rank_tolerance=1e-8, max_pairs=200, max_constraints_per_snapshot=200):
    numbers([characteristic_length_mm, relative_rank_tolerance],2,'INVALID_ARGUMENTS')
    if not (1e-3 <= characteristic_length_mm <= 1e6 and 1e-10 <= relative_rank_tolerance <= 1e-3 and
        type(max_pairs) is int and 1 <= max_pairs <= 1225 and type(max_constraints_per_snapshot) is int and 1 <= max_constraints_per_snapshot <= 2000):
        raise ToolFailure('INVALID_ARGUMENTS','Length must be 0.001–1000000 mm, relative rank tolerance 1e-10–1e-3, pairs 1–1225, constraints 1–2000.')
    pairs=[]
    for pair in analysis['pairs'][:max_pairs]:
        paths=sorted(pair['occurrence_paths'])
        pairs.append({'pair_id':pair['pair_id'],'occurrence_paths':paths,
            'snapshots':[model_snapshot(paths,s,characteristic_length_mm/1000,relative_rank_tolerance,max_constraints_per_snapshot,analysis['source_errors']) for s in pair['snapshots']],
            'flags':deepcopy(pair['flags']),'missing_evidence':deepcopy(pair['missing_evidence']),
            'target_joint_kind':'unknown','target_degrees_of_freedom':None,'snapshots_combined':False})
    snapshots=[s for p in pairs for s in p['snapshots']]
    return {'local_constraint_solution_schema_version':1,'algorithm_version':1,'document':analysis['document'],
        'parameters':{'characteristic_length_mm':characteristic_length_mm,'relative_rank_tolerance':relative_rank_tolerance,
            'max_pairs':max_pairs,'max_constraints_per_snapshot':max_constraints_per_snapshot},
        'pairs':pairs, 'analysis_coverage':deepcopy(analysis['coverage']),
        'coverage':{'available_pairs':analysis['coverage']['available_pairs'],'input_pairs':len(analysis['pairs']),
            'returned_pairs':len(pairs),'omitted_pairs':analysis['coverage']['available_pairs']-len(pairs),
            'snapshots':len(snapshots),'modeled_local_snapshots':sum(s['constraint_system_solved'] for s in snapshots),
            'partial_models':sum(s['status']=='partial_constraint_model' for s in snapshots),
            'numerically_sensitive':sum(s['status']=='numerically_sensitive' for s in snapshots),
            'conflicting_snapshots':sum(s['status']=='conflicting_source' for s in snapshots),
            'omitted_constraints':sum(s['coverage']['omitted_constraints'] for s in snapshots)},
        'source_errors':deepcopy(analysis['source_errors']), 'numeric_method':'row-normalized scaled twist Jacobian; NumPy SVD; relative threshold sensitivity x0.1/x10',
        'assembly_dof_solved':False,'mechanically_verified':False,'finite_motion_verified':False,
        'solidworks_modified':False,'requires_human_review':False,
        'limitations':['Only explicit supported two-occurrence root mates contribute equations. Names, templates, proximity, IsFixed and geometric similarity do not.',
            'Each source snapshot is solved separately. Other pairs, loops, internal-subassembly mates and physical contacts are not solved.',
            'The first occurrence is stationary only as a relative-motion coordinate convention, not a claim that CAD fixed or grounded it.',
            'Accepted faces are idealized as exact coincident axes/planes at the fixed occurrence geometry. Saved geometric residuals and original analysis tolerances remain relevant.',
            'Known-constraint nullity is the dimension of the modeled instantaneous velocity subset; incomplete evidence does not establish target DOF.',
            'An empty constraint model has unknown DOF, not six verified free motions. Numerical rank sensitivity suppresses a definitive count.',
            'Basis vectors parameterize a subspace, not independent physical joints, pivot locations, motor rates or travel limits. Angular motion can require coupled linear velocity.',
            'Current-pose first-order motion is not proof of finite travel, absence of singularity, collision clearance or disassembly feasibility.',
            'Solving is offline and consumes no capture round. Any inherited index/check binding is retained; never discard it to restart collection.']}
