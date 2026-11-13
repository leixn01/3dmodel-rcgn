"""Validated finite planar primitives and projected area; no contact/constraint solver."""
import math
import sys
from cadkin.engagement import dot,cross
from cadkin.face_geometry import descriptor,point,root_normal,unit,require
from cadkin.geometry import numbers

EPS=1e-8  # metres for closure/plane checks, not a contact tolerance


def basis(normal):
    n=unit(normal);e=[0.,0.,0.];e[min(range(3),key=lambda i:abs(n[i]))]=1.
    u=unit([e[i]-dot(e,n)*n[i] for i in range(3)])
    return u,cross(n,u)


def area(poly):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))/2

def turn(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def region_from_loops(shape,loops):
    d=descriptor(shape);require(d['surface_type']=='plane','A planar face is required.','INVALID_PLANAR_SOURCE')
    require(isinstance(loops,list) and 1<=len(loops)<=8,'Unsupported loop count.','UNSUPPORTED_PLANAR_REGION')
    p=d['surface_parameters_part'];n=unit(p[:3]);origin=p[3:];u,v=basis(n)
    require(all(type(l.get('is_outer')) is bool and not l.get('errors') and isinstance(l.get('edges'),list) and l['edges'] for l in loops),
        'Incomplete loops.','INVALID_PLANAR_SOURCE')
    outer=[l for l in loops if l['is_outer']];require(len(outer)==1,'Exactly one outer loop required.','UNSUPPORTED_PLANAR_REGION')
    def on_plane(x):require(abs(dot([x[i]-origin[i] for i in range(3)],n))<=EPS,'Boundary outside plane.','INVALID_PLANAR_SOURCE')
    circles=[]
    for loop in loops:
        if len(loop['edges'])!=1 or loop['edges'][0]['kind']!='circle':break
        edge=loop['edges'][0];q=numbers(edge['circle_parameters_part'],7,'INVALID_PLANAR_SOURCE')
        start=numbers(edge['start_point_part_m'],3,'INVALID_PLANAR_SOURCE');end=numbers(edge['end_point_part_m'],3,'INVALID_PLANAR_SOURCE')
        lo,hi=numbers([edge['u_min'],edge['u_max']],2,'INVALID_PLANAR_SOURCE')
        require(q[6]>0 and abs(abs(dot(unit(q[3:6]),n))-1)<=1e-10,'Invalid circle plane.','INVALID_PLANAR_SOURCE');on_plane(q[:3]);on_plane(start);on_plane(end)
        require(hi>lo and abs((hi-lo)-2*math.pi)<=1e-9 and math.dist(start,end)<=EPS,
            'A circular curve is not a complete circular edge.','UNSUPPORTED_PLANAR_REGION')
        require(abs(math.dist(start,q[:3])-q[6])<=EPS,'Circle endpoint differs.','INVALID_PLANAR_SOURCE')
        circles.append((loop['is_outer'],q[:3],q[6]))
    if len(circles)==len(loops):
        require(len(circles)<=2,'Only disk or single concentric annulus supported.','UNSUPPORTED_PLANAR_REGION')
        _,center,radius=next(c for c in circles if c[0]);inner=0.
        for is_outer,c,r in circles:
            if not is_outer:
                require(math.dist(center,c)<=EPS and 0<r<radius,'Hole must be concentric and inside.','UNSUPPORTED_PLANAR_REGION');inner=r
        result={'kind':'annulus' if inner else 'disk','center_part_m':center,'outer_radius_m':radius,'inner_radius_m':inner}
        computed=math.pi*(radius-inner)*(radius+inner)
    else:
        require(len(loops)==1 and len(loops[0]['edges'])>=3 and all(e['kind']=='line' for e in loops[0]['edges']),
            'Only complete circles or one convex straight-edge loop supported.','UNSUPPORTED_PLANAR_REGION')
        edges=[]
        for e in loops[0]['edges']:
            a=numbers(e['start_point_part_m'],3,'INVALID_PLANAR_SOURCE');b=numbers(e['end_point_part_m'],3,'INVALID_PLANAR_SOURCE')
            on_plane(a);on_plane(b);require(math.dist(a,b)>EPS,'Degenerate line edge.','INVALID_PLANAR_SOURCE');edges.append((a,b))
        # Do not assume COM edge ordering or edge orientation matches the loop.
        vertices=list(edges.pop(0));first=vertices[0]
        while edges:
            matches=[(i,j) for i,e in enumerate(edges) for j in (0,1) if math.dist(vertices[-1],e[j])<=EPS]
            require(len(matches)==1,'Loop is disconnected or branching.','UNSUPPORTED_PLANAR_REGION')
            i,j=matches[0];e=edges.pop(i);vertices.append(e[1-j])
        require(math.dist(vertices[-1],first)<=EPS,'Loop is open.','UNSUPPORTED_PLANAR_REGION');vertices.pop()
        xy=[[dot([x[i]-origin[i] for i in range(3)],b) for b in (u,v)] for x in vertices]
        # Every nonincident vertex must lie on one consistent side of every edge.
        signs=[turn(a,b,c) for i,(a,b) in enumerate(zip(xy,xy[1:]+xy[:1])) for j,c in enumerate(xy) if j not in (i,(i+1)%len(xy))]
        tolerance=EPS*max(math.dist(a,b) for a,b in zip(xy,xy[1:]+xy[:1]))
        require((all(x>=-tolerance for x in signs) or all(x<=tolerance for x in signs)) and area(xy)>EPS**2,
            'Nonconvex, intersecting or degenerate loop.','UNSUPPORTED_PLANAR_REGION')
        # Repeated vertices and overlapping edges are not valid convex topology.
        require(all(math.dist(a,b)>EPS for i,a in enumerate(vertices) for b in vertices[i+1:]),'Repeated polygon vertex.','UNSUPPORTED_PLANAR_REGION')
        result={'kind':'convex_polygon','vertices_part_m':vertices};computed=area(xy)
    require(abs(computed-d['area_part_m2'])<=max(1e-12,computed*1e-6),'Loop area differs from face area.','PLANAR_AREA_MISMATCH')
    return {**result,'area_part_m2':computed,'plane_origin_part_m':origin,'plane_normal_part_unit':n,
        'closure_tolerance_m':EPS,'area_relative_tolerance':1e-6}


def disk_intersection(r,s,d):
    if min(r,s)<=0 or d>=r+s:return 0.
    if d<=abs(r-s):return math.pi*min(r,s)**2
    x=max(-1.,min(1.,(d*d+r*r-s*s)/(2*d*r)))
    y=max(-1.,min(1.,(d*d+s*s-r*r)/(2*d*s)))
    radical=max(0.,(-d+r+s)*(d+r-s)*(d-r+s)*(d+r+s))
    return r*r*math.acos(x)+s*s*math.acos(y)-.5*math.sqrt(radical)


def clip_polygon(subject,clip):
    if sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(clip,clip[1:]+clip[:1]))<0:clip=list(reversed(clip))
    out=subject
    for a,b in zip(clip,clip[1:]+clip[:1]):
        src=out;out=[]
        if not src:break
        for p,q in zip(src,src[1:]+src[:1]):
            dp,dq=turn(a,b,p),turn(a,b,q)
            if dp>=0:out.append(p)
            if (dp<0<dq) or (dq<0<dp):
                t=dp/(dp-dq);out.append([p[i]+t*(q[i]-p[i]) for i in (0,1)])
    return out


def compare_regions(left,right,distance_tolerance_mm):
    a,b=left['region'],right['region'];sources=[d['source'] for d in (left,right)]
    ns=[root_normal(s['target']['transform'],s['face']['descriptor']['surface_parameters_part'][:3],s['face']['descriptor']['face_in_surface_sense']) for s in sources]
    matrices=[s['target']['transform']['to_root'] for s in sources]
    origins=[point(m,r['plane_origin_part_m']) for m,r in zip(matrices,(a,b))]
    n=ns[0];offset=[origins[1][i]-origins[0][i] for i in range(3)];gap=dot(offset,n)*1000
    result={'assessment':'orientation_or_shape_unsupported','projected_overlap_area_mm2':None,'numeric_area_tolerance_mm2':None,'geometry_area_margin_mm2':None,'resolved_area_threshold_mm2':None,
        'signed_plane_gap_mm':gap,'normal_opposition_dot':dot(*ns),'projection_normal_root_unit':n,
        'hypothetical_closing_direction_right_wrt_left':None,'contact_confirmed':False,'retention_confirmed':False,
        'motion_limits_mm':None,'target_joint_kind':'unknown','target_degrees_of_freedom':None}
    # Tilted circles project as ellipses. Do not use circle-area formulas for them.
    if dot(*ns)>-1+1e-12:return result
    u,v=basis(n)
    def xy(m,x):return [dot([q-origins[0][i] for i,q in enumerate(point(m,x))],w)*1000 for w in (u,v)]
    scales=[math.hypot(*(m[i][0] for i in range(3)))*1000 for m in matrices]
    terms=[]
    if a['kind'] in ('disk','annulus') and b['kind'] in ('disk','annulus'):
        centers=[xy(m,r['center_part_m']) for m,r in zip(matrices,(a,b))];d=math.dist(*centers)
        ro,ri=[a[k]*scales[0] for k in ('outer_radius_m','inner_radius_m')]
        so,si=[b[k]*scales[1] for k in ('outer_radius_m','inner_radius_m')]
        terms=[disk_intersection(ro,so,d),-disk_intersection(ri,so,d),-disk_intersection(ro,si,d),disk_intersection(ri,si,d)]
        intersection=math.fsum(terms)
    elif a['kind']==b['kind']=='convex_polygon':
        polys=[[xy(m,x) for x in r['vertices_part_m']] for m,r in zip(matrices,(a,b))]
        clipped=clip_polygon(*polys);intersection=area(clipped) if len(clipped)>=3 else 0.;terms=[area(p) for p in polys]
    else:return result
    tolerance=max(1e-8,256*sys.float_info.epsilon*sum(abs(t) for t in terms))
    require(intersection>=-tolerance,'Numerically invalid intersection area.','INVALID_PLANAR_COMPARISON')
    # Near-tangent/sliver intersections must also exceed the primitive closure
    # margin. A floating-point cancellation threshold alone is insufficient.
    geometry_margin=0.
    for region,scale in zip((a,b),scales):
        perimeter=(2*math.pi*(region['outer_radius_m']+region['inner_radius_m']) if region['kind'] in ('disk','annulus') else
            sum(math.dist(x,y) for x,y in zip(region['vertices_part_m'],region['vertices_part_m'][1:]+region['vertices_part_m'][:1])))
        delta=EPS*scale
        geometry_margin+=4*(perimeter*scale*delta+math.pi*delta*delta)+1e-10*region['area_part_m2']*scale*scale
    threshold=tolerance+geometry_margin
    result.update(projected_overlap_area_mm2=max(0.,intersection),numeric_area_tolerance_mm2=tolerance,
        geometry_area_margin_mm2=geometry_margin,resolved_area_threshold_mm2=threshold)
    result['assessment']='positive_projected_area' if intersection>threshold else 'no_resolved_positive_area'
    if intersection>threshold:
        result['assessment']=('negative_oriented_plane_gap' if gap < -distance_tolerance_mm else
            'opposed_regions_near_tolerance' if gap<=distance_tolerance_mm else 'opposed_regions_separated')
        if gap>=-distance_tolerance_mm:result['hypothetical_closing_direction_right_wrt_left']=[-x for x in n]
    return result
