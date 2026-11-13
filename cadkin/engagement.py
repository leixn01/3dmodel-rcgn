"""Bounded point membership, solid-face orientation and adjacent-plane context."""
import math
from cadkin.face_geometry import unit, point, root_normal, require
from cadkin.finite_geometry import cylinder
from cadkin.geometry import numbers


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]


def sampling_grid(pair):
    c=pair['comparison'];p,q=c['left_projection'],c['right_projection']
    if not p or not q or p['interval_mm'] is None or q['interval_mm'] is None:return None
    low=max(p['interval_mm'][0],q['interval_mm'][0]);high=min(p['interval_mm'][1],q['interval_mm'][1])
    if high-low<=1e-6:return None
    axis=c['axis_direction_root_unit'];origin=c['axis_origin_root_m']
    basis=[0.,0.,0.];basis[min(range(3),key=lambda i:abs(axis[i]))]=1.
    u=unit([basis[i]-dot(basis,axis)*axis[i] for i in range(3)]);v=cross(axis,u)
    stations=[low+(high-low)*f for f in (1/3,2/3)];angles=[45*i for i in range(8)]
    points=[[],[]]
    for side,source in enumerate(pair['face_sources']):
        cyl=cylinder(source);direction=cyl['axis_root_unit'];radius=cyl['radius_mm']/1000
        denominator=dot(direction,axis);require(abs(denominator)>.99,'Axes are not suitable for this sampling frame.','INVALID_ENGAGEMENT_SOURCE')
        for station in stations:
            for angle in angles:
                theta=math.radians(angle);ray=[math.cos(theta)*u[i]+math.sin(theta)*v[i] for i in range(3)]
                radial=unit([ray[i]-dot(ray,direction)*direction[i] for i in range(3)])
                along=(station/1000+dot([origin[i]-cyl['origin_root_m'][i] for i in range(3)],axis)-radius*dot(radial,axis))/denominator
                xyz=[(cyl['origin_root_m'][i]+along*direction[i]+radius*radial[i])*1000 for i in range(3)]
                points[side].append(numbers(xyz,3,'INVALID_ENGAGEMENT_SOURCE'))
    return {'axis_origin_root_m':origin,'axis_root_unit':axis,'zero_angle_root_unit':u,'stations_mm':stations,
        'angles_deg':angles,'points_root_mm':points,'coverage_kind':'two_stations_eight_projected_radial_directions',
        'continuous_angular_coverage_proven':False}


def sample_metrics(source,query_root_mm,sample,normal,membership_tolerance_mm):
    cyl=cylinder(source);q=[x/1000 for x in numbers(query_root_mm,3,'INVALID_SAMPLE_SOURCE')]
    actual=numbers(sample['point_root_m'],3,'INVALID_SAMPLE_SOURCE')
    delta=[actual[i]-cyl['origin_root_m'][i] for i in range(3)]
    radial=[delta[i]-dot(delta,cyl['axis_root_unit'])*cyl['axis_root_unit'][i] for i in range(3)]
    radius=math.hypot(*radial);require(radius>0,'Point lies on cylinder axis.','INVALID_SAMPLE_SOURCE')
    require(abs(radius*1000-cyl['radius_mm'])<=.001,'Returned point is not on the analytic cylinder.','INVALID_SAMPLE_SOURCE')
    error=math.dist(q,actual)*1000
    projection=dot(unit(radial),normal['face_normal_root_unit'])
    orientation=('outer' if projection>=math.cos(math.radians(1)) else 'inner' if projection<=-math.cos(math.radians(1)) else 'unresolved')
    if source['face']['descriptor']['body_type']!=0:orientation='sheet_orientation_only'
    return {'query_to_face_distance_mm':error,'membership_at_query':error<=membership_tolerance_mm,
        'radial_normal_dot':projection,'solid_surface_side':orientation,'continuous_coverage_proven':False}


def summarize_samples(data):
    rows=[r for r in data['samples'] if r['metrics'] is not None and not r['errors']]
    hits=[r for r in rows if r['metrics']['membership_at_query']]
    sides={r['metrics']['solid_surface_side'] for r in hits}
    return {'queries':len(data['samples']),'valid_queries':len(rows),'membership_hits':len(hits),
        'solid_surface_side':next(iter(sides)) if len(sides)==1 else 'unresolved',
        'continuous_angular_coverage_proven':False,'sample_fraction_is_area_fraction':False}


def adjacent_planes(data,axis,origin,angle_tolerance_deg):
    planes={}
    for edge in data['adjacency']:
        if edge['errors']:continue
        for neighbor in edge['neighbors']:
            if neighbor is None or neighbor['is_selected_face'] or not neighbor['same_body']:continue
            shape=neighbor['descriptor']
            if shape['surface_type']!='plane' or shape['body_type']!=0:continue
            params=shape['surface_parameters_part'];transform=data['source']['target']['transform']
            n=root_normal(transform,params[:3],shape['face_in_surface_sense'])
            if abs(dot(n,axis))<math.cos(math.radians(angle_tolerance_deg)):continue
            xyz=point(transform['to_root'],params[3:]);coordinate=dot([xyz[i]-origin[i] for i in range(3)],axis)*1000
            key=neighbor['face_reference']['id']
            row=planes.setdefault(key,{'face_reference':neighbor['face_reference'],'descriptor':shape,'edge_indices':[],
                'normal_root_unit':n,'axial_coordinate_mm':coordinate,'same_body_and_adjacency_verified':True,
                'retention_confirmed':False})
            row['edge_indices'].append(edge['edge_index'])
    return list(planes.values())
