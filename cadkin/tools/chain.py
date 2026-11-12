"""Compile an explicit occurrence scope into an evidence dossier, without inferring joints."""
from datetime import datetime, timezone
import hashlib
import itertools
import json

from cadkin.errors import success
from cadkin.tools.chain_sources import ChainSources, require
from cadkin.tools.files import json_path
from cadkin.tools.proximity import write_result


def stable_id(prefix, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return prefix + hashlib.sha256(raw).hexdigest()[:24]


def has_observation(item):
    if item['kind'] == 'connection':
        return bool(item['record']['geometric_candidate_indices'] or item['record']['mate_evidence'])
    if item['kind'] == 'component_proximity':
        return item['record']['review_state'] in ('near_contact_candidate', 'separated_at_measurement')
    return item['record']['metrics'] is not None


def review_flags(evidence):
    flags = []
    distances = [item for item in evidence if item['kind'] == 'component_proximity' and has_observation(item)]
    for left, right in itertools.combinations(distances, 2):
        if left['parameters'] != right['parameters']:
            flags.append({'code':'DIFFERENT_DISTANCE_THRESHOLDS','evidence_ids':[left['evidence_id'],right['evidence_id']],
                          'message':'Classification thresholds differ; labels cannot be compared directly.'})
        elif left['record']['review_state'] != right['record']['review_state']:
            flags.append({'code':'DISTANCE_CLASSIFICATION_DISAGREEMENT','evidence_ids':[left['evidence_id'],right['evidence_id']],
                          'message':'Same-threshold component snapshots disagree; inspect capture times and geometry.'})
    for distance in distances:
        gap = distance['record']['distance_evidence']['measurement']['distance_mm']
        for face in (e for e in evidence if e['kind'] == 'face_contact' and e['record']['metrics'] is not None):
            face_gap = face['record']['metrics']['gap_mm']
            if gap > face_gap + max(1e-6, abs(gap)*1e-9):
                flags.append({'code':'GEOMETRY_SCOPE_REQUIRES_REVIEW','evidence_ids':[distance['evidence_id'],face['evidence_id']],
                              'message':'Component-context distance exceeds a placed-definition face sample gap; inspect scope/cuts/times, not an automatic contradiction verdict.'})
    return flags


def build_chain(root, inventory_path, occurrence_paths, chain_name, evidence_paths=None, grouping_path=None, grouping_review_path=None):
    require(isinstance(chain_name,str) and 1 <= len(chain_name.strip()) <= 100, 'Provide a descriptive chain name.', 'INVALID_ARGUMENTS')
    require(isinstance(occurrence_paths,list) and 2 <= len(occurrence_paths) <= 50 and
            all(isinstance(p,str) and p for p in occurrence_paths) and len(set(occurrence_paths)) == len(occurrence_paths),
            'Choose 2–50 unique explicit leaf occurrences.', 'INVALID_ARGUMENTS')
    evidence_paths = [] if evidence_paths is None else evidence_paths
    require(isinstance(evidence_paths,list) and len(evidence_paths) <= 20 and all(isinstance(p,str) and p for p in evidence_paths), 'Use at most 20 evidence review files.', 'INVALID_ARGUMENTS')
    require(grouping_path is not None or grouping_review_path is None, 'A grouping review requires a grouping file.', 'INVALID_ARGUMENTS')
    reader = ChainSources(root, inventory_path, grouping_review_path)
    nodes = reader.nodes; parents = {n.get('parent_occurrence_path') for n in nodes.values()}
    scope = sorted(occurrence_paths)
    require(all(p in nodes and p not in parents for p in scope), 'Scope must contain current inventory leaf occurrences.', 'INVALID_CHAIN_SCOPE')
    errors = []
    if reader.inventory['status'] != 'ok' or reader.spatial.get('complete') is not True or reader.inventory.get('errors'):
        errors.append({'code':'SOURCE_INCOMPLETE','source':'inventory','message':'Spatial source is partial.','source_errors':reader.inventory.get('errors',[])})
    roles, grouping_binding = {}, None
    if grouping_path is not None:
        grouping, grouping_binding = reader.grouping(grouping_path)
        for group in grouping['groups']:
            for member in group['members']:
                roles[member['occurrence_path']] = {'role':group['role'], 'role_status':member['role_status'],
                    'reason':member['reason'], 'source':grouping_binding}
    members = [{**{k:nodes[p].get(k) for k in ('occurrence_path','parent_occurrence_path','file_path','referenced_configuration')},
                'role':roles.get(p, {'role':'pending','role_status':'pending','reason':'No grouping evidence in the supplied scope.','source':None})} for p in scope]
    pairs = {pair:{'pair_id':stable_id('pair-',pair), 'occurrence_paths':list(pair),'evidence':[], 'review_state':'pending',
                   'mechanical_relation_confirmed':False} for pair in itertools.combinations(scope,2)}
    sources, boundaries, skipped, seen = [], [], [], set()
    for path in evidence_paths:
        kind, data, parameters, coverage, binding = reader.evidence(path)
        require(binding['sha256'] not in seen, 'Duplicate evidence file/content.', 'DUPLICATE_CHAIN_SOURCE'); seen.add(binding['sha256'])
        sources.append({'kind':kind, **binding, 'parameters':parameters, 'complete':data['complete'], 'coverage':coverage, 'errors':data['errors']})
        if not data['complete']:
            errors.append({'code':'SOURCE_INCOMPLETE','source':binding['path'],'message':'Evidence review is partial.','source_errors':data['errors']})
        outside = 0
        for index, record in enumerate(data['pairs']):
            paths = record['occurrence_paths'] if kind != 'face_contact' else [f['occurrence_path'] for f in record['faces']]
            require(len(paths)==2 and paths[0]!=paths[1] and all(p in nodes for p in paths), 'Invalid evidence occurrence pair.', 'EVIDENCE_MISMATCH')
            pair = tuple(sorted(paths))
            item = {'evidence_id':stable_id('evidence-', [kind,binding['sha256'],index]), 'kind':kind,
                    'source_path':binding['path'],'source_sha256':binding['sha256'],'replayed_pair_index':index,
                    'parameters':parameters,'record':record}
            if pair in pairs:
                pairs[pair]['evidence'].append(item)
            elif any(p in scope for p in pair):
                boundaries.append({'occurrence_paths':list(pair),'evidence':item})
            else:
                outside += 1
        skipped.append({'source_path':binding['path'],'outside_scope_pair_records':outside})
    for row in pairs.values():
        row['review_flags'] = review_flags(row['evidence'])
        row['evidence_status'] = ('needs_reconciliation' if row['review_flags'] else
                                  'candidate_evidence' if any(has_observation(e) for e in row['evidence']) else 'unknown')
        row['missing_evidence_families'] = sorted({'connection','component_proximity','face_contact'} - {e['kind'] for e in row['evidence']})
    rows = list(pairs.values())
    unknown = sum(r['evidence_status']=='unknown' for r in rows)
    if unknown:
        errors.append({'code':'UNASSESSED_CHAIN_PAIRS','count':unknown,'message':'Some scope pairs have no usable observations; absence is not disconnection.'})
    files = reader.finish()
    return {'chain_dossier_schema_version':1,'algorithm_version':1,'chain_name':chain_name.strip(),'document':reader.spatial['document'],
            'captured_at_utc':datetime.now(timezone.utc).isoformat(),'snapshot_atomic':False,
            'parameters':{'inventory_path':reader.inventory_binding['path'],'occurrence_paths':scope,'chain_name':chain_name.strip(),
                'evidence_paths':[s['path'] for s in sources],'grouping_path':None if grouping_binding is None else grouping_binding['path'],
                'grouping_review_path':None if grouping_review_path is None else str(json_path(root,grouping_review_path))},
            'inventory_source':reader.inventory_binding,'input_files':files,'members':members,'pairs':rows,'sources':sources,
            'boundary_evidence':boundaries,'outside_scope_records':skipped,
            'coverage':{'scope':'explicit_leaf_occurrences','occurrences':len(scope),'possible_pairs':len(rows),
                'pairs_with_observations':len(rows)-unknown,'unknown_pairs':unknown,
                'pairs_needing_reconciliation':sum(bool(r['review_flags']) for r in rows),
                'boundary_records':len(boundaries),'role_pending_occurrences':[m['occurrence_path'] for m in members if m['role']['role_status']!='manual_confirmed']},
            'compilation_complete':True,'complete':not errors,'errors':errors,'requires_review':True,
            'mechanical_relation_confirmed':False,'solidworks_modified':False,
            'limitations':['Scope membership is explicit user/agent selection, not an automatically recognized kinematic chain or traversal order.',
                'Every scope pair is retained; no evidence, unmeasured or unresolved never means no mechanical connection.',
                'Axes, mates, component minimums and local face samples keep separate scopes; flags request reconciliation, not automatic conflict resolution.',
                'Root mate scope gaps and unmatched records remain attached to source coverage; boundary connections are not discarded.',
                'No rigid grouping, joint axis, DOF, stroke, pitch, removal order or collision-free path is inferred.',
                'Source replay/hashes bind files and detect changes, not authorship, atomic CAD capture or unchanged full geometry.']}


def chain_dossier(root, inventory_path, occurrence_paths, chain_name, output_path, evidence_paths=None, grouping_path=None, grouping_review_path=None):
    output = json_path(root,output_path,output=True)
    data = build_chain(root,inventory_path,occurrence_paths,chain_name,evidence_paths,grouping_path,grouping_review_path)
    write_result(output,data)
    return success({'output_path':str(output),'coverage':data['coverage'],'complete':data['complete'],
                    'requires_review':True,'mechanical_relation_confirmed':False,'solidworks_modified':False},data['errors'])
