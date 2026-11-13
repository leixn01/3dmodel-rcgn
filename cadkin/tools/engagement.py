"""Source-replayed sampled complementarity and topological end-plane evidence."""
import math
from cadkin.engagement import sampling_grid,summarize_samples,adjacent_planes,dot
from cadkin.followup import stable_id
from cadkin.tools.chain_sources import require,check_fields
from cadkin.tools.comparison import replay_check
from cadkin.tools.engagement_sources import validate_engagement_capture,load_engagement_boundary
from cadkin.tools.files import json_path,read_json,replay_reads
from cadkin.tools.finite_connections import replay_finite_analysis,build_finite_analysis,face_key
from cadkin.tools.matching import recheck
from cadkin.tools.observation_index import replay_index,unique_bindings
from cadkin.tools.proximity import write_result
from cadkin.errors import success

CAPTURES=('sw_sample_cylinder_face','sw_read_face_adjacency')


@replay_reads
def build_engagement(root,finite_analysis_path,evidence_index_path=None):
    old,fb=replay_finite_analysis(root,finite_analysis_path);inherited=old['evidence_index_source']
    if evidence_index_path is None and inherited:evidence_index_path=inherited['path']
    index,ib=(None,None) if evidence_index_path is None else replay_index(root,evidence_index_path)
    if index:
        _,_,draft,_,cb=replay_check(root,index['check_source']['path'])
        require(draft['target_source']==old['target_source'] and (not inherited or ib==inherited or inherited in index['input_files']),
            'Inspection index must continue the finite report history and target.','EVIDENCE_MISMATCH')
    else:cb=None
    params=dict(old['parameters'])
    if ib:params['evidence_index_path']=ib['path']
    finite=build_finite_analysis(root,**params)
    geometry,_=read_json(json_path(root,finite['geometry_analysis_source']['path']))
    dt,at=geometry['parameters']['distance_tolerance_mm'],geometry['parameters']['angle_tolerance_deg']
    faces={};pairs=[]
    for pair in finite['pairs']:
        grid=sampling_grid(pair)
        row={'id':pair['id'],'occurrence_paths':pair['occurrence_paths'],'face_keys':pair['face_keys'],
            'finite_comparison':pair['comparison'],'alternatives':pair['alternatives'],'flags':pair['flags'],
            'grid':grid,'query_indices':[[],[]],'paired_samples':[],'adjacent_axial_planes':[[],[]],
            'opposed_adjacent_plane_candidates':[],'target_joint_kind':'unknown','target_degrees_of_freedom':None,
            'physical_engagement_confirmed':False,'retention_confirmed':False,'motion_limits_mm':None}
        for i,key in enumerate(pair['face_keys']):
            f=faces.setdefault(key,{'face_key':key,'source':pair['face_sources'][i],'boundary_sources':pair['boundary_sources'][i],
                'query_points_root_mm':[],'query_points_omitted':0,'attempts':{t:[] for t in CAPTURES},
                'observations':{t:[] for t in CAPTURES},'sample_summary':None,'flags':[]})
            if grid:
                for p in grid['points_root_mm'][i]:
                    if p not in f['query_points_root_mm'] and len(f['query_points_root_mm'])<32:f['query_points_root_mm'].append(p)
                    if p in f['query_points_root_mm']:row['query_indices'][i].append(f['query_points_root_mm'].index(p))
                    else:row['query_indices'][i].append(None);f['query_points_omitted']+=1
        pairs.append(row)
    records={}
    for o in ([] if index is None else index['observations']):
        if o['tool'] not in CAPTURES:continue
        b=load_engagement_boundary(root,finite['document']['document_token'],o['arguments']['boundary_path'])
        key=face_key(b['boundary']['source'])
        if key not in faces:continue
        f=faces[key];f['attempts'][o['tool']].append({'source':o['source'],'state':o['state'],'usable':o['usable']})
        if not o['usable']:continue
        raw,digest=read_json(json_path(root,o['source']['path']));require(digest==o['source']['sha256'],'Inspection changed.','EVIDENCE_MISMATCH')
        data=validate_engagement_capture(root,raw)
        if len(f['boundary_sources'])!=1 or data['boundary_source']!=f['boundary_sources'][0]:
            f['flags'].append({'code':'INSPECTION_BOUNDARY_DIFFERS','source':o['source']});continue
        f['observations'][o['tool']].append(o['source']);records[o['source']['path']]=data
    def one(f,tool):
        refs=f['observations'][tool]
        if len(refs)==1:return records[refs[0]['path']]
        if len(refs)>1:
            flag={'code':'MULTIPLE_INSPECTION_SNAPSHOTS','tool':tool}
            if flag not in f['flags']:f['flags'].append(flag)
        return None
    for f in faces.values():
        sample=one(f,'sw_sample_cylinder_face')
        if sample:f['sample_summary']=summarize_samples(sample)
    for row in pairs:
        fs=[faces[k] for k in row['face_keys']];samples=[one(f,'sw_sample_cylinder_face') for f in fs]
        if row['grid'] and all(samples):
            for j in range(16):
                observations=[]
                for side,d in enumerate(samples):
                    query=row['grid']['points_root_mm'][side][j];queries=d['parameters']['query_points_root_mm']
                    observations.append(d['samples'][queries.index(query)] if query in queries else None)
                a,b=observations;present=all(r and r['metrics'] is not None and not r['errors'] for r in observations)
                hit=present and all(r['metrics']['query_to_face_distance_mm']<=min(dt,.01) for r in observations)
                opposite=hit and {r['metrics']['solid_surface_side'] for r in observations}=={'inner','outer'}
                metric={'query_index':j,'both_queries_observed':present,'both_query_memberships':bool(hit),
                    'opposite_solid_sides':bool(opposite),'point_gap_mm':None,'normals_opposed':None}
                if present:
                    metric['point_gap_mm']=math.dist(a['sample']['point_root_m'],b['sample']['point_root_m'])*1000
                    metric['normals_opposed']=dot(a['normal']['face_normal_root_unit'],b['normal']['face_normal_root_unit'])<=-math.cos(math.radians(at))
                row['paired_samples'].append(metric)
        c=row['finite_comparison'];axis=c['axis_direction_root_unit'];origin=c['axis_origin_root_m']
        for side,f in enumerate(fs):
            d=one(f,'sw_read_face_adjacency')
            if d:row['adjacent_axial_planes'][side]=adjacent_planes(d,axis,origin,at)
        candidates=[]
        for a in row['adjacent_axial_planes'][0]:
            for b in row['adjacent_axial_planes'][1]:
                gap=abs(a['axial_coordinate_mm']-b['axial_coordinate_mm'])
                if gap<=dt and dot(a['normal_root_unit'],b['normal_root_unit'])<=-math.cos(math.radians(at)):
                    candidates.append({'left_face_reference':a['face_reference'],'right_face_reference':b['face_reference'],
                        'axial_plane_distance_mm':gap,'finite_planar_overlap_verified':False,'retention_confirmed':False})
        row['opposed_adjacent_plane_candidates']=candidates[:32];row['opposed_plane_candidates_omitted']=max(0,len(candidates)-32)
        row['sampled_support']={'paired_queries_observed':sum(p['both_queries_observed'] for p in row['paired_samples']),
            'both_query_memberships':sum(p['both_query_memberships'] for p in row['paired_samples']),
            'opposite_solid_side_queries':sum(p['opposite_solid_sides'] for p in row['paired_samples']),
            'continuous_angular_coverage_proven':False,'counts_are_not_probabilities':True}
    data={'surface_engagement_schema_version':1,'algorithm_version':1,'finite_analysis_source':fb,'target_source':finite['target_source'],
        'evidence_index_source':ib,'check_source':cb,'document':finite['document'],
        'parameters':{'finite_analysis_path':fb['path']},'faces':list(faces.values()),'pairs':pairs,'gaps':finite['gaps'],
        'coverage':{'face_pairs':len(pairs),'faces':len(faces),'pairs_with_sampled_support':sum(r['sampled_support']['opposite_solid_side_queries']>0 for r in pairs),
            'queries_omitted':sum(f['query_points_omitted'] for f in faces.values()),
            'adjacent_plane_candidates_omitted':sum(r['opposed_plane_candidates_omitted'] for r in pairs)},
        'inherited_finite_coverage':finite['coverage'],'inherited_geometry_coverage':finite['inherited_geometry_coverage'],
        'source_errors':finite['source_errors'],'boundary_evidence':finite['inherited_boundary_evidence'],
        'capture_parameters':{'membership_tolerance_mm':min(dt,.01),'max_edges':64},
        'rounds_completed':None if index is None else index['rounds_completed'],'max_rounds':4,
        'input_files':unique_bindings(root,old['input_files']+finite['input_files']+[fb]),
        'requires_human_review':False,'solidworks_modified':False,'physical_joint_types_determined':False,'finite_motion_verified':False,
        'limitations':['Finite queries do not prove continuous angular/axial trim coverage, engagement, collision clearance, fit or motion.',
            'An outward/inward solid-face normal is sampled material orientation; sheet normals do not determine shaft/hole roles.',
            'Matching angle/station queries are generated on each analytic cylinder in a common reference frame, not a contact-pair assertion.',
            'Adjacent faces are verified through live edge/body identity and reference round-trip; opposed planes still lack finite planar overlap/contact.',
            'Only bound complete observations are interpreted. Partial/failed attempts stop automatic retries, even with changed points/budgets.',
            'Referenced part definitions omit assembly features; all snapshot and inherited coverage limitations remain.']}
    if ib:data['parameters']['evidence_index_path']=ib['path']
    recheck(root,data['input_files']);return data


@replay_reads
def replay_engagement(root,engagement_analysis_path):
    path=json_path(root,engagement_analysis_path);raw,digest=read_json(path)
    require(isinstance(raw,dict) and raw.get('surface_engagement_schema_version')==1 and raw.get('algorithm_version')==1 and
        isinstance(raw.get('parameters'),dict) and set(raw['parameters']) in ({'finite_analysis_path'},{'finite_analysis_path','evidence_index_path'}),
        'Use an original surface engagement report.','INVALID_ENGAGEMENT_SOURCE')
    data=build_engagement(root,**raw['parameters']);check_fields(raw,data)
    return data,{'path':str(path),'sha256':digest}


def analyze_engagement(root,output_path,**params):
    output=json_path(root,output_path,output=True);data=build_engagement(root,**params);write_result(output,data)
    errors=list(data['source_errors'])
    if (data['coverage']['queries_omitted'] or data['coverage']['adjacent_plane_candidates_omitted'] or
        data['inherited_finite_coverage']['omitted_face_pairs'] or data['inherited_finite_coverage']['catalog_faces_omitted'] or
        data['inherited_geometry_coverage']['omitted_pairs'] or data['inherited_geometry_coverage']['pairs_with_observation_limits']):
        errors.append({'code':'ENGAGEMENT_ANALYSIS_LIMIT','message':'Retain omitted queries, faces and inherited evidence limits.'})
    return success({'analysis_source':{'path':str(output),'sha256':read_json(output)[1]},'coverage':data['coverage'],
        'rounds_completed':data['rounds_completed'],'detail_saved':True,'physical_joint_types_determined':False,
        'finite_motion_verified':False,'requires_human_review':False},errors)
