"""Conditional geometry explanations; never manufacture physical constraints."""
from copy import deepcopy
import math

from cadkin.errors import ToolFailure
from cadkin.followup import stable_id
from cadkin.matching.target import axis_angle
from cadkin.rigid.joints import canonical_line


def options(distance_tolerance_mm, angle_tolerance_deg, max_pairs):
    for name, value, upper in [('distance_tolerance_mm', distance_tolerance_mm, 10), ('angle_tolerance_deg', angle_tolerance_deg, 5)]:
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= upper:
            raise ToolFailure('INVALID_ARGUMENTS', f'{name} must be finite in (0,{upper}].')
    if type(max_pairs) is not int or not 1 <= max_pairs <= 200:
        raise ToolFailure('INVALID_ARGUMENTS', 'max_pairs must be 1–200.')


def axis_patterns(pair, distance_mm, angle_deg):
    groups = {}
    for row in pair['axis_relations']:
        key = (row['source']['path'], row['source']['sha256'])
        groups.setdefault(key, []).append(row)
    patterns = []
    for key, rows in sorted(groups.items()):
        lines = []
        for row in rows:
            if (row['kind'] != 'coaxial_candidate' or row['angle_deg'] > angle_deg or
                    row['offset_at_reference_m']*1000 > distance_mm): continue
            line = canonical_line(row['left']['origin_m'], row['left']['axis_unit'])
            match = next((x for x in lines if axis_angle(line['direction_root_unit'], x['direction_root_unit']) <= angle_deg and
                math.dist(line['point_on_line_root_m'], x['point_on_line_root_m']) <= distance_mm/1000), None)
            ref = {'source': row['source'], 'candidate_index': row['candidate_index'], 'parameters': row['parameters'],
                   'angle_deg':row['angle_deg'], 'axis_offset_at_reference_mm':row['offset_at_reference_m']*1000,
                   'radius_difference_mm': abs(row['left']['radius_m']-row['right']['radius_m'])*1000}
            if match is None:
                match = {**line, 'observations': []}; lines.append(match)
            match['observations'].append(ref)
        if lines:
            parallel = len(lines) > 1 and all(axis_angle(a['direction_root_unit'], b['direction_root_unit']) <= angle_deg
                for i,a in enumerate(lines) for b in lines[i+1:])
            kind = 'multiple_parallel_coaxial_lines' if parallel else 'coaxial_lines'
            patterns.append({'id': stable_id('geometry-pattern-', [pair['id'], key, kind]), 'kind': kind,
                'source': rows[0]['source'], 'lines': lines, 'distinct_lines': len(lines),
                'observation_count': sum(len(x['observations']) for x in lines),
                'finite_engagement_verified': False, 'complementary_surfaces_verified': False,
                'meaning': 'Repeated split faces do not add votes. Infinite axes do not establish shaft/hole engagement, retention or a joint.'})
        parallel_only = [r['candidate_index'] for r in rows if r['kind'] == 'parallel_candidate']
        if parallel_only:
            patterns.append({'id': stable_id('geometry-pattern-', [pair['id'], key, 'parallel']),
                'kind': 'parallel_axis_context', 'source': rows[0]['source'], 'candidate_indices': parallel_only,
                'meaning': 'Parallel axes alone do not identify guides or connected components.'})
        outside = [r['candidate_index'] for r in rows if r['kind']=='coaxial_candidate' and
            (r['angle_deg']>angle_deg or r['offset_at_reference_m']*1000>distance_mm)]
        if outside:
            patterns.append({'id':stable_id('geometry-pattern-',[pair['id'],key,'outside_tolerance']),
                'kind':'axis_alignment_outside_analysis_tolerance','source':rows[0]['source'],'candidate_indices':outside,
                'meaning':'Source classified these axes with its own tolerances; they do not support coaxial explanations under this report threshold.'})
    return patterns


def explanations(patterns):
    by_kind = {}
    def add(kind, pattern, requirements):
        row = by_kind.setdefault(kind, {'candidate_kind': kind, 'supporting_geometry_ids': [],
            'required_unverified_conditions': requirements, 'conditional_conflicts': [], 'confirmed': False})
        row['supporting_geometry_ids'].append(pattern['id'])
    for p in patterns:
        if p['kind'] in ('coaxial_lines', 'multiple_parallel_coaxial_lines'):
            add('cylindrical', p, ['finite shaft/hole engagement', 'independent axial slide and rotation', 'no additional restraint'])
            add('revolute', p, ['finite engagement', 'axial retention', 'rotation remains available'])
            add('prismatic', p, ['finite engagement', 'rotation prevented', 'axial translation remains available'])
            add('fixed', p, ['physical attachment or clamping prevents relative motion'])
            if p['kind'] == 'multiple_parallel_coaxial_lines':
                for kind in ('revolute', 'cylindrical'):
                    by_kind[kind]['conditional_conflicts'].append({'pattern_id': p['id'],
                        'condition': 'If both offset axis pairs are simultaneously engaged as rigid guides, free relative rotation is incompatible. Engagement is not established.'})
        elif p['kind'] == 'opposed_planar_samples':
            add('planar', p, ['finite face engagement persists', 'normal separation and tilt are restrained', 'in-plane motion remains available'])
            add('fixed', p, ['physical attachment or clamping prevents relative motion'])
    if by_kind:
        by_kind['no_direct_joint'] = {'candidate_kind': 'no_direct_joint', 'supporting_geometry_ids': [],
            'required_unverified_conditions': ['alignment or proximity is incidental, or connection is indirect'],
            'conditional_conflicts': [], 'confirmed': False}
        by_kind['other_relationship'] = {'candidate_kind': 'other_relationship', 'supporting_geometry_ids': [],
            'required_unverified_conditions': ['unmodeled contact, transmission, compliance or geometry'],
            'conditional_conflicts': [], 'confirmed': False}
    return [by_kind[k] for k in sorted(by_kind)]


def analyze(target, facts, distance_tolerance_mm, angle_tolerance_deg, max_pairs=100):
    options(distance_tolerance_mm, angle_tolerance_deg, max_pairs)
    rows = []
    for pair in target['pairs']:
        key = tuple(sorted(pair['node_ids']))
        patterns = axis_patterns(pair, distance_tolerance_mm, angle_tolerance_deg)
        faces = facts['face_observations'].get(key, [])
        for face in faces[:32]:
            if face['surface_types'] == ['plane', 'plane'] and face['review_state'] == 'near_face_contact_candidate' and face['converged']:
                patterns.append({'id': stable_id('geometry-pattern-', [pair['id'], face['source']]),
                    'kind': 'opposed_planar_samples', 'source': face['source'], 'faces': face['faces'],
                    'metrics': face['metrics'], 'source_complete': face['complete'],
                    'meaning': 'Local opposed planar samples are not a contact patch or a bilateral kinematic constraint.'})
        distances = facts['distances'].get(key, [])
        complete_distances = [x for x in distances if x['complete']]
        nearby = any(x['distance_mm'] <= distance_tolerance_mm for x in complete_distances)
        if nearby:
            patterns.append({'id': stable_id('geometry-pattern-', [pair['id'], 'proximity']),
                'kind': 'component_proximity', 'sources': [x['source'] for x in complete_distances if x['distance_mm'] <= distance_tolerance_mm],
                'meaning': 'Small component distance cannot identify contact, collision, attachment or a motion type.'})
        flags = deepcopy(pair['flags'])
        if any(a['parameters']['distance_tolerance_mm']!=distance_tolerance_mm or
               a['parameters']['angle_tolerance_deg']!=angle_tolerance_deg for a in pair['axis_relations']):
            flags.append({'code':'SOURCE_AXIS_TOLERANCES_DIFFER',
                'message':'Coaxial evidence must also pass report thresholds; looser analysis never recovers pairs omitted by the original relation scan.'})
        if pair['axes_truncated'] or len(faces)>32: flags.append({'code': 'GEOMETRY_OBSERVATION_LIMIT'})
        if any(not x['complete'] for x in faces+distances): flags.append({'code': 'PARTIAL_GEOMETRY_OBSERVATION'})
        if len({x['distance_mm'] for x in complete_distances}) > 1: flags.append({'code': 'MULTIPLE_DISTANCE_OBSERVATIONS'})
        if nearby and any(x['distance_mm']>distance_tolerance_mm for x in complete_distances):
            flags.append({'code':'DISTANCE_THRESHOLD_DISAGREEMENT'})
        if any(x['distance_mm']>distance_tolerance_mm for x in complete_distances) and any(p['kind']=='opposed_planar_samples' for p in patterns):
            flags.append({'code':'ASSEMBLY_DISTANCE_VS_PART_FACE_SCOPE_DISAGREEMENT'})
        cues = bool(patterns or faces)
        verification = []
        def gap(code, action, **extra):
            verification.append({'id': stable_id('geometry-gap-', [pair['id'], code]), 'code': code, 'action': action,
                                 'occurrence_paths': pair['node_ids'], **extra})
        if cues and not complete_distances:
            gap('COMPONENT_DISTANCE_MISSING', 'collect_component_distance', tool='sw_component_distance')
        if nearby and not faces:
            gap('FINITE_FACE_SAMPLES_MISSING', 'handoff_face_probe_planner', tool='cad_plan_face_probes',
                note='Use the latest index and explicit thresholds. Existing face planner selects bound catalogs/seeds; do not invent them.')
        if cues:
            gap('PHYSICAL_ATTACHMENT_AND_FINITE_MOTION_UNVERIFIED', 'unsupported_verification',
                note='Existing read-only geometric probes cannot certify physical joints, restraint, finite motion or disassembly.')
        else:
            gap('GEOMETRY_BASIS_MISSING', 'source_gap',
                note='Use existing source-bound cylinder relations or face probes. This analysis does not scan CAD or fabricate empty geometry.')
        native = [s for s in pair['signals'] if s['kind'] in ('active_mate', 'inactive_or_unknown_mate')]
        if native: gap('NATIVE_MATE_CONTEXT_AVAILABLE', 'handoff_constraint_analysis', tool='cad_analyze_constraints')
        rows.append({'pair_id': pair['id'], 'occurrence_paths': pair['node_ids'],
            'assessment': 'conditional_geometry_explanations' if explanations(patterns) else 'geometric_context_only' if cues else 'insufficient_geometry',
            'patterns': patterns, 'alternatives': explanations(patterns), 'alternatives_exhaustive': False,
            'distance_observations': distances, 'face_observations': faces[:32], 'native_mate_context': native,
            'flags': flags, 'verification_gaps': verification, 'target_joint_kind': 'unknown', 'target_degrees_of_freedom': None,
            'connection_confirmed': False, 'constraint_equations_created': False})
    rows.sort(key=lambda p: (p['assessment']=='insufficient_geometry', -len(p['patterns']), p['pair_id']))
    available = len(rows); rows = rows[:max_pairs]
    return {'geometry_connection_schema_version':1, 'algorithm_version':1,
        'document':target['document'], 'units':target['units'],
        'parameters':{'distance_tolerance_mm':distance_tolerance_mm,'angle_tolerance_deg':angle_tolerance_deg,'max_pairs':max_pairs},
        'pairs':rows, 'coverage':{'available_pairs':available,'returned_pairs':len(rows),'omitted_pairs':available-len(rows),
            'pairs_with_alternatives':sum(bool(p['alternatives']) for p in rows),
            'pairs_without_geometry':sum(p['assessment']=='insufficient_geometry' for p in rows),
            'pairs_with_observation_limits':sum(any(f['code']=='GEOMETRY_OBSERVATION_LIMIT' for f in p['flags']) for p in rows)},
        'source_errors':deepcopy(target['errors']), 'boundary_evidence':deepcopy(target['boundary_evidence']),
        'requires_human_review':False, 'solidworks_modified':False, 'template_search_requested':False,
        'physical_joint_types_determined':False, 'finite_motion_verified':False, 'constraint_equations_created':False,
        'limitations':['Geometry supplies competing conditional explanations, not constraints or ranked probabilities. Names, templates and fixed flags do not determine types.',
            'Each axis-source pattern and local face observation remains separate. Observations are not fused into a kinematic model or counted as independent votes.',
            'Axis clustering uses unoriented directions and root-origin canonical line points with explicit tolerances; points are not physical pivots.',
            'Positive distance does not rule out indirect connections. Local near samples cannot prove finite engagement, contact, interference or persistence during motion.',
            'Only source-bound target data and usable guarded observations are read. Failed attempts and budgets remain in the inherited index.',
            'Geometry and proximity have different scopes; source/coverage conflicts stay visible. No automatic CAD movement, joint creation, human gate or motion-solver input.']}
