"""Finite cylindrical ranges and local end-plane context; source lineage stays explicit."""
import math
from cadkin.errors import success
from cadkin.finite_geometry import cylinder, compare_boundaries
from cadkin.followup import stable_id
from cadkin.matching.target import axis_angle
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.face_boundaries import validate_boundary, selection
from cadkin.tools.face_planning import face_facts
from cadkin.tools.files import json_path, read_json, replay_reads
from cadkin.tools.geometric_connections import replay_geometry_analysis, geometry_facts
from cadkin.tools.matching import replay_target, recheck
from cadkin.tools.observation_index import replay_index, unique_bindings
from cadkin.tools.comparison import replay_check
from cadkin.tools.proximity import write_result


def face_key(source):
    return stable_id('finite-face-',[source['path'],source['sha256'],source['face']['body_index'],source['face']['face_index']])


def end_context(observations,axis,origin,intervals,angle_tolerance_deg,distance_tolerance_mm):
    result=[]
    for row in observations:
        m=row.get('metrics')
        if row['surface_types']!=['plane','plane'] or row['review_state']!='near_face_contact_candidate' or not row['converged'] or not m:continue
        normals=[m['normal_left_root_unit'],m['normal_right_root_unit']]
        if any(n is None or axis_angle(n,axis)>angle_tolerance_deg for n in normals):continue
        coords=[sum((p[i]/1000-origin[i])*axis[i] for i in range(3))*1000 for p in (m['point_left_root_mm'],m['point_right_root_mm'])]
        result.append({'source':row['source'],'axial_coordinates_mm':coords,'sample_gap_mm':m['gap_mm'],
            'near_any_cylinder_interval_endpoint':any(abs(v-e)<=distance_tolerance_mm for v in coords for interval in intervals for e in interval),
            'source_complete':row['complete'],'probe_faces':row.get('faces'),
            'adjacency_to_selected_cylinders_verified':False,'same_body_as_cylinders_verified':False,'normal_signs':[1 if sum(a*b for a,b in zip(n,axis))>0 else -1 for n in normals],
            'assessment':'local_opposed_axial_plane_samples','retention_confirmed':False,'travel_limit_mm':None})
    return result


@replay_reads
def build_finite_analysis(root,geometry_analysis_path,max_face_pairs=20,evidence_index_path=None):
    require(type(max_face_pairs) is int and 1<=max_face_pairs<=100,'max_face_pairs must be 1–100.','INVALID_ARGUMENTS')
    geometry,gb=replay_geometry_analysis(root,geometry_analysis_path)
    target,tb=replay_target(root,geometry['target_source']['path'])
    inherited=geometry['evidence_index_source']
    if evidence_index_path is None and inherited:evidence_index_path=inherited['path']
    index,ib=(None,None) if evidence_index_path is None else replay_index(root,evidence_index_path)
    if index:
        _,_,draft,_,cb=replay_check(root,index['check_source']['path'])
        require(draft['target_source']==tb,'Index and geometry target differ.','EVIDENCE_MISMATCH')
        require(not inherited or ib==inherited or inherited in index['input_files'],
                'Index is not a continuation of the geometry report history.','EVIDENCE_MISMATCH')
    else:cb=None
    facts=face_facts(root,target,index or {'observations':[],'rounds_completed':0})
    parameters=geometry['parameters'];dt,at=parameters['distance_tolerance_mm'],parameters['angle_tolerance_deg']
    observed=geometry_facts(root,target,index,dt,at)
    boundaries={};attempts={}
    for o in ([] if index is None else index['observations']):
        if o['tool']!='sw_read_face_boundary':continue
        from cadkin.tools.face_sources import face_source
        source=face_source(root,o['arguments']['face']);key=face_key(source)
        attempts.setdefault(key,[]).append({'source':o['source'],'state':o['state'],'usable':o['usable']})
        if o['usable']:
            raw,digest=read_json(json_path(root,o['source']['path']));require(digest==o['source']['sha256'],'Boundary changed.','EVIDENCE_MISMATCH')
            d=validate_boundary(root,raw);boundaries.setdefault(key,[]).append((d,o['source']))
    rows=[];gaps=[];found=0;omitted_faces=0
    for pair in geometry['pairs']:
        paths=pair['occurrence_paths']; catalogs=[facts['faces'].get(p) for p in paths]
        if not any(p['kind'] in ('coaxial_lines','multiple_parallel_coaxial_lines') for p in pair['patterns']):continue
        if any(p in facts['face_conflicts'] for p in paths):
            gaps.append({'pair_id':pair['pair_id'],'code':'CONFLICTING_FACE_CATALOGS','occurrence_paths':paths});continue
        if not all(catalogs):
            gaps.append({'pair_id':pair['pair_id'],'code':'FACE_CATALOG_MISSING','occurrence_paths':[p for p,c in zip(paths,catalogs) if not c],
                'next_tool':'cad_plan_face_probes','note':'Use measured witnesses and existing catalog planner/history; do not scan or invent face IDs here.'});continue
        faces=[[s for s in c['sources'] if s['face']['descriptor']['surface_type']=='cylinder'] for c in catalogs]
        omitted_faces+=sum(max(0,len(fs)-20) for fs in faces)
        for left in faces[0][:20]:
            for right in faces[1][:20]:
                empty=lambda s:{'source':s,'complete':False,'truncated':False,'edges':[]}
                alignment=compare_boundaries(empty(left),empty(right),dt,at)
                if alignment['assessment']=='axis_alignment_unconfirmed':continue
                found+=1
                if len(rows)>=max_face_pairs:continue
                keys=[face_key(s) for s in (left,right)];values=[boundaries.get(k,[]) for k in keys]
                data=[v[0][0] if len(v)==1 else empty(s) for s,v in zip((left,right),values)]
                result=compare_boundaries(*data,dt,at)
                intervals=[p['interval_mm'] for p in (result['left_projection'],result['right_projection']) if p and p['interval_mm'] is not None]
                endpoints=end_context(observed['face_observations'].get(tuple(sorted(paths)),[]),result['axis_direction_root_unit'],
                    result['axis_origin_root_m'],intervals,at,dt)
                row={'id':stable_id('finite-pair-',keys),'pair_id':pair['pair_id'],'occurrence_paths':paths,
                    'face_sources':[left,right],'face_keys':keys,'boundary_sources':[[b for _,b in v] for v in values],
                    'attempts':[attempts.get(k,[]) for k in keys],'comparison':result,'axial_plane_observations':endpoints,
                    'alternatives':pair['alternatives'],'missing_boundaries':[k for k,v in zip(keys,values) if len(v)!=1],
                    'flags':list(pair['flags'])}
                if any(len(v)>1 for v in values):row['flags'].append({'code':'MULTIPLE_BOUNDARY_SNAPSHOTS'})
                rows.append(row)
    inputs=geometry['input_files']+[gb]+([] if index is None else index['input_files']+[ib])
    data={'finite_connection_schema_version':1,'algorithm_version':1,'geometry_analysis_source':gb,'target_source':tb,
        'evidence_index_source':ib,'check_source':cb,'document':target['document'],
        'parameters':{'geometry_analysis_path':gb['path'],'max_face_pairs':max_face_pairs},'pairs':rows,'gaps':gaps,
        'inherited_geometry_coverage':geometry['coverage'],
        'inherited_boundary_evidence':target['boundary_evidence'],
        'coverage':{'candidate_face_pairs':found,'returned_face_pairs':len(rows),'omitted_face_pairs':found-len(rows),
            'catalog_faces_omitted':omitted_faces,'pairs_with_finite_ranges':sum(r['comparison']['signed_interval_overlap_mm'] is not None for r in rows)},
        'rounds_completed':None if index is None else index['rounds_completed'],'max_rounds':4,
        'input_files':unique_bindings(root,inputs),'source_errors':geometry['source_errors'],
        'requires_human_review':False,'solidworks_modified':False,'physical_joint_types_determined':False,'finite_motion_verified':False,
        'limitations':['Analytic boundary projections are enclosures, not proven shaft/hole engagement or angular trim overlap.',
            'Positive overlap does not establish contact, complementary solid surfaces, rotation freedom, axial retention or stroke.',
            'Separated enclosures concern only these selected part-definition faces, not every possible direct or indirect component connection.',
            'Local opposed axial plane samples retain separate sources; adjacency/body identity relative to selected cylinders is unverified. They cannot establish bilateral retention or finite travel limits.',
            'No CAD movement, fitted constraints, templates, arbitrary scans or physical joint decisions. All inherited uncertainty remains.',
            'Only up to 20 cylindrical faces per catalog and explicit max_face_pairs are inspected; omitted scope remains unknown.']}
    if ib:data['parameters']['evidence_index_path']=ib['path']
    recheck(root,data['input_files']);return data


@replay_reads
def replay_finite_analysis(root,finite_analysis_path):
    path=json_path(root,finite_analysis_path);raw,digest=read_json(path)
    keys={'geometry_analysis_path','max_face_pairs'}
    require(isinstance(raw,dict) and raw.get('finite_connection_schema_version')==1 and raw.get('algorithm_version')==1 and
        isinstance(raw.get('parameters'),dict) and set(raw['parameters']) in (keys,keys|{'evidence_index_path'}),
        'Use an original finite connection report.','INVALID_FINITE_SOURCE')
    data=build_finite_analysis(root,**raw['parameters']);check_fields(raw,data)
    return data,{'path':str(path),'sha256':digest}


def analyze_finite_connections(root,output_path,**params):
    output=json_path(root,output_path,output=True);data=build_finite_analysis(root,**params);write_result(output,data)
    errors=list(data['source_errors'])
    if (data['coverage']['omitted_face_pairs'] or data['coverage']['catalog_faces_omitted'] or
        data['inherited_geometry_coverage']['omitted_pairs'] or data['inherited_geometry_coverage']['pairs_with_observation_limits']):
        errors.append({'code':'FINITE_ANALYSIS_LIMIT','message':'Face/pair bounds omit geometry; preserve unknowns.'})
    return success({'analysis_source':{'path':str(output),'sha256':read_json(output)[1]},'coverage':data['coverage'],
        'rounds_completed':data['rounds_completed'],'detail_saved':True,'physical_joint_types_determined':False,
        'finite_motion_verified':False,'requires_human_review':False},errors)
