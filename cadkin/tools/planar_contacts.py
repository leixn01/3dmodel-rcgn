"""Replay actual adjacent finite regions and report projected overlap and oriented gaps."""
from cadkin.errors import success
from cadkin.followup import stable_id
from cadkin.planar_regions import compare_regions
from cadkin.tools.chain_sources import require,check_fields
from cadkin.tools.engagement import replay_engagement,build_engagement
from cadkin.tools.files import json_path,read_json,replay_reads
from cadkin.tools.observation_index import replay_index,unique_bindings
from cadkin.tools.planar_sources import load_planar_source,validate_planar_capture
from cadkin.tools.matching import recheck
from cadkin.tools.proximity import write_result


def plane_key(source):return stable_id('planar-face-',[source['adjacency_source'],source['face']['face_reference']])


@replay_reads
def build_planar_contacts(root,engagement_analysis_path,evidence_index_path=None,max_plane_pairs=20):
    require(type(max_plane_pairs) is int and 1<=max_plane_pairs<=100,'max_plane_pairs must be 1–100.','INVALID_ARGUMENTS')
    old,eb=replay_engagement(root,engagement_analysis_path);inherited=old['evidence_index_source']
    if evidence_index_path is None and inherited:evidence_index_path=inherited['path']
    # replay_engagement already validated its exact inherited index. Reuse that
    # validation within this call, rechecking original bytes, not a mutable cache.
    if inherited and evidence_index_path is not None and json_path(root,evidence_index_path)==json_path(root,inherited['path']):
        index,digest=read_json(json_path(root,evidence_index_path));ib={'path':inherited['path'],'sha256':digest}
        require(ib==inherited,'Inherited index changed.','EVIDENCE_MISMATCH')
    else:index,ib=(None,None) if evidence_index_path is None else replay_index(root,evidence_index_path)
    require(not inherited or (index and (ib==inherited or inherited in index['input_files'])),
        'Continue the engagement history.','EVIDENCE_MISMATCH')
    params=dict(old['parameters'])
    if ib:params['evidence_index_path']=ib['path']
    engagement=old if ib==inherited else build_engagement(root,**params)
    finite,_=read_json(json_path(root,engagement['finite_analysis_source']['path']))
    geometry,_=read_json(json_path(root,finite['geometry_analysis_source']['path']));dt=geometry['parameters']['distance_tolerance_mm']
    ef={f['face_key']:f for f in engagement['faces']};faces={};pairs=[];candidates=0
    for pair in engagement['pairs']:
        for candidate in pair['opposed_adjacent_plane_candidates']:
            candidates+=1
            if len(pairs)>=max_plane_pairs:continue
            keys=[]
            for i,reference in enumerate((candidate['left_face_reference'],candidate['right_face_reference'])):
                refs=ef[pair['face_keys'][i]]['observations']['sw_read_face_adjacency'];require(len(refs)==1,'Ambiguous adjacency.','EVIDENCE_MISMATCH')
                source=load_planar_source(root,engagement['document']['document_token'],refs[0]['path'],reference)['source'];key=plane_key(source);keys.append(key)
                faces.setdefault(key,{'face_key':key,'source':source,'region_sources':[],'attempts':[]})
            pairs.append({'id':stable_id('planar-pair-',keys),'engagement_pair_id':pair['id'],'occurrence_paths':pair['occurrence_paths'],
                'face_keys':keys,'adjacent_plane_candidate':candidate,'comparison':None,'alternatives':pair['alternatives'],'flags':pair['flags']})
    captures={}
    for observation in ([] if index is None else index['observations']):
        if observation['tool']!='sw_read_planar_face':continue
        args=observation['arguments'];source=load_planar_source(root,args['expected_document_token'],args['adjacency_path'],args['face_reference'])['source'];key=plane_key(source)
        if key not in faces:continue
        f=faces[key];f['attempts'].append({'source':observation['source'],'state':observation['state'],'usable':observation['usable']})
        if observation['usable']:
            raw,digest=read_json(json_path(root,observation['source']['path']));require(digest==observation['source']['sha256'],'Planar capture changed.','EVIDENCE_MISMATCH')
            data=validate_planar_capture(root,raw);require(data['source']==source,'Capture source differs.','EVIDENCE_MISMATCH')
            f['region_sources'].append(observation['source']);captures[observation['source']['path']]=data
    for pair in pairs:
        fs=[faces[k] for k in pair['face_keys']]
        if all(len(f['region_sources'])==1 for f in fs):pair['comparison']=compare_regions(*[captures[f['region_sources'][0]['path']] for f in fs],dt)
        if any(len(f['region_sources'])>1 for f in fs):pair['flags']=pair['flags']+[{'code':'MULTIPLE_PLANAR_SNAPSHOTS'}]
    coverage={'candidate_plane_pairs':candidates,'returned_plane_pairs':len(pairs),'omitted_plane_pairs':max(0,candidates-len(pairs)),
        'faces':len(faces),'missing_regions':sum(len(f['region_sources'])!=1 for f in faces.values()),
        'compared_pairs':sum(p['comparison'] is not None for p in pairs),
        'near_opposed_region_pairs':sum(p['comparison'] is not None and p['comparison']['assessment']=='opposed_regions_near_tolerance' for p in pairs)}
    data={'planar_contact_schema_version':1,'algorithm_version':1,'parameters':{'engagement_analysis_path':eb['path'],'max_plane_pairs':max_plane_pairs},
        'engagement_analysis_source':eb,'target_source':engagement['target_source'],'evidence_index_source':ib,'check_source':engagement['check_source'],
        'document':engagement['document'],'faces':list(faces.values()),'pairs':pairs,'coverage':coverage,'gaps':engagement['gaps'],
        'inherited_coverage':{'engagement':engagement['coverage'],'finite':engagement['inherited_finite_coverage'],'geometry':engagement['inherited_geometry_coverage']},
        'source_errors':engagement['source_errors'],'boundary_evidence':engagement['boundary_evidence'],
        'capture_parameters':{'max_loops':8,'max_edges':64},'distance_tolerance_mm':dt,
        'rounds_completed':None if index is None else index['rounds_completed'],'max_rounds':4,
        'input_files':unique_bindings(root,old['input_files']+engagement['input_files']+[eb]),
        'requires_human_review':False,'solidworks_modified':False,'contact_confirmed':False,'retention_confirmed':False,'finite_motion_verified':False,
        'limitations':['Only complete guarded disk/annulus or convex straight-loop regions are used. Mixed shape comparisons remain unknown.',
            'Projected finite area is computed within documented geometric/numeric tolerances; zero resolved area does not exclude boundary contact.',
            'Positive area and an opposed small signed gap give local contact candidates, not contact, global interference, retention, a travel limit or a joint.',
            'The conditional closing direction is relative translation of the right occurrence with the left held fixed; no velocity constraint is created.',
            'Part definitions omit assembly features; source errors, alternatives, failed/partial attempts and the shared four rounds remain.']}
    if ib:data['parameters']['evidence_index_path']=ib['path']
    recheck(root,data['input_files']);return data


def limited(data):
    c=data['inherited_coverage']
    return bool(data['coverage']['omitted_plane_pairs'] or c['engagement']['queries_omitted'] or c['engagement']['adjacent_plane_candidates_omitted'] or
        c['finite']['omitted_face_pairs'] or c['finite']['catalog_faces_omitted'] or c['geometry']['omitted_pairs'] or c['geometry']['pairs_with_observation_limits'])


@replay_reads
def replay_planar_contacts(root,planar_analysis_path):
    path=json_path(root,planar_analysis_path);raw,digest=read_json(path);keys={'engagement_analysis_path','max_plane_pairs'}
    require(isinstance(raw,dict) and raw.get('planar_contact_schema_version')==1 and raw.get('algorithm_version')==1 and
        isinstance(raw.get('parameters'),dict) and set(raw['parameters']) in (keys,keys|{'evidence_index_path'}),
        'Use an original planar contact report.','INVALID_PLANAR_SOURCE')
    data=build_planar_contacts(root,**raw['parameters']);check_fields(raw,data);return data,{'path':str(path),'sha256':digest}


def analyze_planar_contacts(root,output_path,**params):
    output=json_path(root,output_path,output=True);data=build_planar_contacts(root,**params);write_result(output,data)
    errors=list(data['source_errors'])
    if limited(data):errors.append({'code':'PLANAR_ANALYSIS_LIMIT','message':'Retain inherited limits and omitted plane pairs.'})
    return success({'analysis_source':{'path':str(output),'sha256':read_json(output)[1]},'coverage':data['coverage'],
        'rounds_completed':data['rounds_completed'],'detail_saved':True,'contact_confirmed':False,'retention_confirmed':False,
        'finite_motion_verified':False,'requires_human_review':False},errors)
