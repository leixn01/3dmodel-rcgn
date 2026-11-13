"""Analytic boundary projections, never a physical fit or contact solver."""
import math
from cadkin.face_geometry import descriptor, point, unit, require
from cadkin.geometry import numbers
from cadkin.matching.target import axis_angle


def edge_record(raw):
    require(isinstance(raw, dict) and type(raw.get('edge_index')) is int and raw['edge_index'] >= 0 and
            isinstance(raw.get('errors'), list), 'Invalid boundary edge.', 'INVALID_BOUNDARY_SOURCE')
    kind = raw.get('curve_kind')
    require(kind in ('line', 'circle', 'unsupported', 'unavailable'), 'Invalid edge type.', 'INVALID_BOUNDARY_SOURCE')
    if kind == 'line':
        points = raw.get('endpoints_part_m')
        require(isinstance(points, list) and len(points) == 2, 'Missing line endpoints.', 'INVALID_BOUNDARY_SOURCE')
        for p in points: numbers(p, 3, 'INVALID_BOUNDARY_SOURCE')
        require(math.dist(*points) > 0, 'Degenerate straight edge.', 'INVALID_BOUNDARY_SOURCE')
    elif kind == 'circle':
        p = numbers(raw.get('circle_parameters_part'), 7, 'INVALID_BOUNDARY_SOURCE')
        unit(p[3:6]); require(p[6] > 0, 'Invalid circle radius.', 'INVALID_BOUNDARY_SOURCE')
    return raw


def direction(matrix, vector):
    return unit([sum(matrix[i][j]*vector[j] for j in range(3)) for i in range(3)])


def cylinder(source):
    d = descriptor(source['face']['descriptor'])
    require(d['surface_type'] == 'cylinder', 'Use a cylindrical face.', 'INVALID_BOUNDARY_SOURCE')
    p = d['surface_parameters_part']; matrix = source['target']['transform']['to_root']
    scale = math.hypot(*(matrix[i][0] for i in range(3)))
    return {'origin_root_m': point(matrix,p[:3]), 'axis_root_unit':direction(matrix,p[3:6]), 'radius_mm':p[6]*scale*1000}


def project_boundary(data, axis, origin):
    """Every circular arc is enclosed by its full circle, not silently treated as full."""
    if not data['complete'] or data['truncated'] or not data['edges']:
        return {'state':'unavailable','interval_mm':None,'reason':'INCOMPLETE_BOUNDARY'}
    source = data['source']; matrix = source['target']['transform']['to_root']
    axis = unit(axis); intervals=[]; conservative_arcs=[]
    def coordinate(p): return sum((p[i]-origin[i])*axis[i] for i in range(3))*1000
    for raw in data['edges']:
        row=edge_record(raw)
        if row['errors'] or row['curve_kind'] not in ('line','circle'):
            return {'state':'unavailable','interval_mm':None,'reason':'UNSUPPORTED_BOUNDARY_EDGE'}
        if row['curve_kind']=='line':
            values=[coordinate(point(matrix,p)) for p in row['endpoints_part_m']]
            intervals.append([min(values),max(values)])
        else:
            p=row['circle_parameters_part']; normal=direction(matrix,p[3:6]); center=coordinate(point(matrix,p[:3]))
            scale=math.hypot(*(matrix[i][0] for i in range(3)))
            # Cross-product avoids cancellation near parallel directions.
            cross=[axis[1]*normal[2]-axis[2]*normal[1],axis[2]*normal[0]-axis[0]*normal[2],axis[0]*normal[1]-axis[1]*normal[0]]
            half_width=p[6]*scale*1000*math.hypot(*cross)
            intervals.append([center-half_width,center+half_width])
            if half_width>1e-9:conservative_arcs.append(row['edge_index'])
    return {'state':'analytic_boundary_enclosure','interval_mm':[min(x[0] for x in intervals),max(x[1] for x in intervals)],
            'circular_arc_enclosures':conservative_arcs,'trimmed_angular_coverage_known':False,
            'meaning':'Projection of all captured boundaries; circular arcs use enclosing full circles. Interval overlap does not establish common trimmed surface area.'}


def compare_boundaries(left, right, distance_tolerance_mm, angle_tolerance_deg):
    a,b=cylinder(left['source']),cylinder(right['source']); axis=a['axis_root_unit']; origin=a['origin_root_m']
    angle=axis_angle(axis,b['axis_root_unit'])
    delta=[b['origin_root_m'][i]-origin[i] for i in range(3)]; along=sum(x*y for x,y in zip(delta,axis))
    offset=math.hypot(*(delta[i]-along*axis[i] for i in range(3)))*1000
    result={'axis_origin_root_m':origin,'axis_direction_root_unit':axis,'axis_angle_deg':angle,'axis_offset_at_reference_mm':offset,
        'radius_difference_mm':abs(a['radius_mm']-b['radius_mm']), 'radii_mm':[a['radius_mm'],b['radius_mm']],
        'left_projection':None,'right_projection':None,'signed_interval_overlap_mm':None,'assessment':'axis_alignment_unconfirmed',
        'physical_engagement_confirmed':False,'motion_limits_mm':None,'target_joint_kind':'unknown','target_degrees_of_freedom':None}
    if angle>angle_tolerance_deg or offset>distance_tolerance_mm:return result
    # A projection along this axis has no interior extremum on a cylinder while its axial component is nonzero.
    p,q=project_boundary(left,axis,origin),project_boundary(right,axis,origin)
    result.update(left_projection=p,right_projection=q,assessment='finite_extent_unavailable')
    if p['interval_mm'] is None or q['interval_mm'] is None:return result
    x,y=p['interval_mm'],q['interval_mm']; overlap=min(x[1],y[1])-max(x[0],y[0])
    result.update(signed_interval_overlap_mm=overlap,assessment='axially_separated_face_enclosures' if overlap < -distance_tolerance_mm else
        'axial_enclosures_overlap' if overlap > distance_tolerance_mm else 'axial_endpoint_near_tolerance')
    result['axial_gap_mm']=max(0,-overlap)
    return result
