"""Normalize replayed CAD evidence into an occurrence graph; never manufacture joints."""
import math
from cadkin.geometry import transform_from_sw, bounding_box

# These weights order evidence usefulness, not probabilities of mechanical connectivity.
SUPPORT_WEIGHTS = {'active_mate':1.0, 'near_face_sample':0.65, 'near_component':0.55,
                   'coaxial_candidate':0.3, 'parallel_candidate':0.2}


def axis_angle(a,b):
    dot=sum(x*y for x,y in zip(a,b)); cross=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    return math.degrees(math.atan2(math.hypot(*cross),abs(dot)))


def adapt_target(chain, spatial_nodes, relations):
    nodes=[]
    for member in chain['members']:
        raw=spatial_nodes[member['occurrence_path']]
        transform=transform_from_sw(raw['transform']['raw_array']) if raw.get('transform') else None
        box=bounding_box(raw['bounding_box']['raw_array_m']) if raw.get('bounding_box') else None
        nodes.append({'id':member['occurrence_path'],'parent_id':member['parent_occurrence_path'],
                      'file_path':member['file_path'],'configuration':member['referenced_configuration'],
                      'role_context':member['role'],
                      'eligible':raw.get('is_suppressed') is False and raw.get('suppression_state') in (2,3),
                      'origin_m':transform['origin_root_m'] if transform else None,
                      'to_root_column_vectors_m':transform['to_root'] if transform else None,
                      'box_size_m':box['size_m'] if box else None,
                      'box_scope':'approximate_root_axis_aligned','source_errors':raw.get('errors',[])+raw.get('spatial_errors',[])})
    pairs={}
    for source in chain['pairs']:
        pair={'id':source['pair_id'],'node_ids':source['occurrence_paths'],'signals':[],
              'flags':list(source['review_flags']),'axis_relations':[],'axis_relation_count':0,
              'evidence_status':source['evidence_status'],'missing_evidence_families':source['missing_evidence_families']}
        for evidence in source['evidence']:
            row=evidence['record']; binding={k:evidence[k] for k in ('evidence_id','source_path','source_sha256','replayed_pair_index')}
            if evidence['kind']=='connection':
                for mate in row['mate_evidence']:
                    # Individual mates describe constraints, not necessarily a solved motion joint.
                    pair['signals'].append({'kind':'active_mate' if mate['category']=='unsuppressed_no_feature_error' else 'inactive_or_unknown_mate',
                        'mate_type':mate['type_name'],'category':mate['category'],'record_errors':mate['record_errors'],
                        'feature_id':mate['feature_id'],'face_match_confirmed':mate['face_match_confirmed'],'source':binding})
            elif evidence['kind']=='component_proximity':
                pair['signals'].append({'kind':'near_component' if row['review_state']=='near_contact_candidate' else 'distance_observation',
                    'state':row['review_state'],'measurement':row.get('distance_evidence'),'source':binding})
            elif evidence['kind']=='face_contact':
                pair['signals'].append({'kind':'near_face_sample' if row['review_state']=='near_face_contact_candidate' else 'local_face_observation',
                    'state':row['review_state'],'metrics':row['metrics'],'converged':row['converged'],'source':binding})
        if any(s.get('record_errors') for s in pair['signals']):
            pair['flags'].append({'code':'MATE_RECORD_INCOMPLETE','message':'A mate record has errors; retain them and reduce ranking support.'})
        pairs[tuple(source['occurrence_paths'])]=pair
    relation_errors=[]
    for graph,binding in relations:
        if not graph['complete']:
            relation_errors.append({'code':'SOURCE_INCOMPLETE','source':binding,'errors':graph['errors']})
        for index,row in enumerate(graph['candidates']):
            key=tuple(sorted((row['left']['occurrence_path'],row['right']['occurrence_path'])))
            if key not in pairs:continue
            pair=pairs[key];pair['axis_relation_count']+=1
            if len(pair['axis_relations'])>=32:continue
            pair['axis_relations'].append({'kind':row['kind'],'source':binding,'candidate_index':index,'parameters':graph['parameters'],
                'angle_deg':row['angle_deg'],'offset_at_reference_m':row['axis_offset_at_reference_mm']/1000,
                'left':{'node_id':row['left']['occurrence_path'],'axis_unit':row['left']['axis_root_unit'],
                        'origin_m':[x/1000 for x in row['left']['origin_root_mm']], 'radius_m':row['left']['radius_root_mm']/1000},
                'right':{'node_id':row['right']['occurrence_path'],'axis_unit':row['right']['axis_root_unit'],
                         'origin_m':[x/1000 for x in row['right']['origin_root_mm']], 'radius_m':row['right']['radius_root_mm']/1000}})
    for pair in pairs.values():
        pair['axes_truncated']=pair['axis_relation_count']>len(pair['axis_relations'])
        kinds=[s['kind'] for s in pair['signals']]+[a['kind'] for a in pair['axis_relations']]
        pair['link_support']=max((SUPPORT_WEIGHTS.get(k,0.) for k in kinds),default=0.)
        thresholds={(a['parameters']['distance_tolerance_mm'],a['parameters']['angle_tolerance_deg']) for a in pair['axis_relations']}
        if len(thresholds)>1:pair['flags'].append({'code':'MULTIPLE_AXIS_THRESHOLDS','message':'Axis classifications use different tolerances; preserve source parameters.'})
        if pair['flags']:pair['link_support']*=.5
        directions=[]
        for axis in pair['axis_relations']:
            direction=axis['left']['axis_unit']
            if not any(axis_angle(direction,d)<1e-6 for d in directions):directions.append(direction)
        pair['axis_direction_count']=len(directions)
        pair['representative_axis_unit']=directions[0] if len(directions)==1 and not pair['axes_truncated'] else None
        # Multiple axes stay ambiguous; do not independently pick a convenient axis for each comparison.
        pair['axis_basis']='left cylinder direction; unoriented' if pair['representative_axis_unit'] else None
    rows=list(pairs.values());truncated=sum(p['axes_truncated'] for p in rows)
    errors=list(chain['errors'])+relation_errors
    if truncated:errors.append({'code':'TARGET_AXIS_LIMIT','count':truncated,'message':'At most 32 axis relations per pair retained; ambiguous/truncated axes are not scored.'})
    observed=sum(p['link_support']>0 for p in rows)
    return {'target_graph_schema_version':1,'algorithm_version':1,'document':chain['document'],'chain_name':chain['chain_name'],
            'units':{'length':'m','angle':'degree','frame':'root_assembly'},'nodes':nodes,'pairs':rows,
            'support_weights':SUPPORT_WEIGHTS,'coverage':{'nodes':len(nodes),'eligible_nodes':sum(n['eligible'] for n in nodes),
                'possible_pairs':len(rows),'pairs_with_positive_support':observed,'pairs_without_positive_support':len(rows)-observed,
                'pairs_with_single_axis':sum(p['representative_axis_unit'] is not None for p in rows),
                'pairs_with_flags':sum(bool(p['flags']) for p in rows)},
            'chain_coverage':chain['coverage'],'source_coverage':chain['sources'],
            'boundary_evidence':chain['boundary_evidence'],'outside_scope_records':chain['outside_scope_records'],
            'complete':not errors,'errors':errors,'requires_human_review':False,'mechanical_relation_confirmed':False,'solidworks_modified':False,
            'limitations':['One node is one leaf occurrence, not an inferred rigid group; multiple CAD parts may form one real moving body.',
                'Weights are disclosed ranking heuristics, not probabilities; names, roles and box dimensions are context only.',
                'No/large distance evidence does not prove no mechanical connection; partial and conflicting scopes remain explicit.',
                'A representative cylinder direction is geometric evidence, not a verified joint axis.',
                'Hash replay verifies derivations and snapshot bindings, not source authenticity, atomic capture or physical truth.']}
