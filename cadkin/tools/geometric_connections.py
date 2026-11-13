"""Replay-bound geometry explanations, separate from CAD capture and motion solvers."""
from cadkin.errors import success
from cadkin.face_geometry import descriptor
from cadkin.followup.execution import document_matches, pose_matches
from cadkin.geometric_connections import analyze, options
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.comparison import replay_check
from cadkin.tools.face_contacts import review_probe
from cadkin.tools.face_planning import witness
from cadkin.tools.files import json_path, read_json, replay_reads
from cadkin.tools.matching import replay_target, recheck
from cadkin.tools.observation_index import replay_index, unique_bindings
from cadkin.tools.proximity import write_result


def geometry_facts(root, target, index, distance_tolerance_mm, angle_tolerance_deg):
    nodes = {n['id']:n for n in target['nodes']}
    facts = {'distances':{}, 'face_observations':{}}
    bindings = unique_bindings(root, target['input_files'] + ([] if index is None else
        [o['source'] for o in index['observations'] if o['usable']]))
    seen = set()
    for binding in bindings:
        raw, digest = read_json(json_path(root,binding['path']))
        require(digest==binding['sha256'],'Geometry source changed.','EVIDENCE_MISMATCH')
        if digest in seen: continue
        seen.add(digest)
        data = raw.get('data') if isinstance(raw,dict) else None
        if not isinstance(data,dict): continue
        complete = raw.get('status')=='ok' and not raw.get('errors') and data.get('complete') is True and not data.get('truncated',False)
        if data.get('component_distance_schema_version')==1:
            paths = [t.get('occurrence_path') for t in data.get('targets',[]) if isinstance(t,dict)]
            if len(paths)!=2 or len(set(paths))!=2 or any(p not in nodes for p in paths): continue
            if complete:
                key,value = witness(raw,binding,nodes,target['document'])
                row = {'source':binding,'distance_mm':value['distance_mm'], 'points_root_mm':value['point_by_occurrence_mm'],
                       'complete':True,'geometry_scope':data['geometry_scope'],'errors':[]}
            else:
                key = tuple(sorted(paths))
                row = {'source':binding,'distance_mm':None,'points_root_mm':None,'complete':False,
                       'geometry_scope':data.get('geometry_scope'),'errors':raw.get('errors',[])}
            facts['distances'].setdefault(key,[]).append(row)
        elif data.get('face_probe_schema_version')==1:
            sources = data.get('sources',[])
            paths = [s.get('target',{}).get('occurrence_path') for s in sources if isinstance(s,dict)]
            if len(paths)!=2 or len(set(paths))!=2 or any(p not in nodes for p in paths): continue
            require(document_matches(data.get('document'),target['document']) and all(
                pose_matches(s.get('target'),nodes[p]) for s,p in zip(sources,paths)),
                'Face observation differs from target context.','EVIDENCE_MISMATCH')
            row,_ = review_probe(root,raw,distance_tolerance_mm,angle_tolerance_deg)
            row.update(source=binding,complete=bool(complete),
                surface_types=[descriptor(s['face']['descriptor'])['surface_type'] for s in sources])
            facts['face_observations'].setdefault(tuple(sorted(paths)),[]).append(row)
    return facts


@replay_reads
def build_geometry_analysis(root,target_graph_path,distance_tolerance_mm,angle_tolerance_deg,max_pairs=100,evidence_index_path=None):
    options(distance_tolerance_mm,angle_tolerance_deg,max_pairs)
    target,tb = replay_target(root,target_graph_path)
    index,ib = (None,None) if evidence_index_path is None else replay_index(root,evidence_index_path)
    if index is not None:
        _,_,draft,_,cb = replay_check(root,index['check_source']['path'])
        require(index['check_source']==cb and draft['target_source']==tb,
                'Geometry index belongs to another target graph.','EVIDENCE_MISMATCH')
    facts = geometry_facts(root,target,index,distance_tolerance_mm,angle_tolerance_deg)
    data = analyze(target,facts,distance_tolerance_mm,angle_tolerance_deg,max_pairs)
    data['parameters']['target_graph_path']=tb['path']
    data.update(target_source=tb,evidence_index_source=ib,check_source=None if index is None else index['check_source'],
        rounds_completed=None if index is None else index['rounds_completed'],max_rounds=4,
        input_files=target['input_files']+[tb])
    if ib:
        data['parameters']['evidence_index_path']=ib['path']
        data['input_files']=unique_bindings(root,data['input_files']+index['input_files']+[ib])
    recheck(root,data['input_files'])
    return data


@replay_reads
def replay_geometry_analysis(root,geometry_analysis_path):
    path=json_path(root,geometry_analysis_path);raw,digest=read_json(path)
    keys={'target_graph_path','distance_tolerance_mm','angle_tolerance_deg','max_pairs'}
    require(isinstance(raw,dict) and raw.get('geometry_connection_schema_version')==1 and raw.get('algorithm_version')==1 and
        isinstance(raw.get('parameters'),dict) and set(raw['parameters']) in (keys,keys|{'evidence_index_path'}),
        'Use an original geometric connection analysis.','INVALID_GEOMETRY_SOURCE')
    expected=build_geometry_analysis(root,**raw['parameters']);check_fields(raw,expected)
    recheck(root,expected['input_files']+[{'path':str(path),'sha256':digest}])
    return expected,{'path':str(path),'sha256':digest}


def analyze_geometric_connections(root,output_path,**parameters):
    output=json_path(root,output_path,output=True)
    data=build_geometry_analysis(root,**parameters)
    errors=list(data['source_errors'])
    if data['coverage']['omitted_pairs'] or data['coverage']['pairs_with_observation_limits']:
        errors.append({'code':'GEOMETRY_ANALYSIS_LIMIT','message':'Omitted pairs/observations remain unknown.'})
    write_result(output,data)
    return success({'output_path':str(output),'analysis_source':{'path':str(output),'sha256':read_json(output)[1]},
        'coverage':data['coverage'],'evidence_index_source':data['evidence_index_source'],'rounds_completed':data['rounds_completed'],
        'detail_saved':True,'physical_joint_types_determined':False,'constraint_equations_created':False,
        'requires_human_review':False,'solidworks_modified':False},errors)
