"""Deterministic graph scoring given explicit body correspondence; never infers a match."""
from collections import Counter
from cadkin.errors import ToolFailure


def need(ok, message):
    if not ok:
        raise ToolFailure('INVALID_GRAPH', message)


def validate_graph(graph):
    need(isinstance(graph,dict) and graph.get('mechanism_template_schema_version') == 1, 'Expected mechanism graph schema version 1.')
    bodies, joints = graph.get('bodies'), graph.get('joints')
    need(isinstance(bodies,list) and len(bodies)<=20000 and isinstance(joints,list) and len(joints)<=20000, 'Invalid graph lists or graph budget exceeded.')
    ids=set(); jids=set()
    for b in bodies:
        need(isinstance(b,dict) and isinstance(b.get('id'),str) and b['id'] and b['id'] not in ids, 'Body IDs must be unique nonempty strings.')
        need(type(b.get('enabled')) is bool, 'Body enabled must be a boolean.')
        ids.add(b['id'])
    for j in joints:
        need(isinstance(j,dict) and isinstance(j.get('id'),str) and j['id'] and j['id'] not in jids, 'Joint IDs must be unique nonempty strings.')
        jids.add(j['id'])
        need(j.get('kind') in ('fixed','prismatic','revolute','unsupported') and type(j.get('enabled')) is bool, 'Invalid joint kind or enabled value.')
        need(isinstance(j.get('endpoints'),list) and len(j['endpoints']) == 2, 'Each joint must have two endpoints.')
        for e in j['endpoints']:
            need(isinstance(e,dict) and e.get('frame_kind') in ('body','world','static_xform','unresolved'), 'Invalid endpoint frame kind.')
            bid=e.get('body_id')
            need((e['frame_kind']=='body' and isinstance(bid,str) and bid in ids) or (e['frame_kind']!='body' and bid is None), 'Endpoint body ID is inconsistent or missing.')
    return {b['id']:b for b in bodies}


def compare_graphs(reference, candidate, mapping, reference_sha, candidate_sha):
    rb, cb = validate_graph(reference), validate_graph(candidate)
    need(isinstance(mapping,dict) and mapping.get('body_correspondence_schema_version')==1, 'Expected body correspondence schema version 1.')
    if mapping.get('reference_sha256') != reference_sha or mapping.get('candidate_sha256') != candidate_sha:
        raise ToolFailure('EVIDENCE_MISMATCH', 'Body correspondence must bind the exact graph file hashes.')
    pairs=mapping.get('body_map'); need(isinstance(pairs,list) and len(pairs)<=20000, 'body_map must be a bounded list.')
    body_map={}; used=set()
    for pair in pairs:
        need(isinstance(pair,dict), 'Invalid body correspondence row.')
        c,r=pair.get('candidate_body'),pair.get('reference_body')
        need(isinstance(c,str) and c in cb and isinstance(r,str) and r in rb, 'Correspondence refers to a missing body.')
        need(c not in body_map and r not in used, 'Correspondence must be one-to-one; merge/split hypotheses must be evaluated separately.')
        body_map[c]=r;used.add(r)
    active_r={b for b in rb if rb[b]['enabled']}; active_c={b for b in cb if cb[b]['enabled']}
    def endpoint(e, is_candidate):
        if e['frame_kind']=='unresolved':return None
        if e['frame_kind'] in ('world','static_xform'):return ('ground','')
        b=e['body_id']
        if is_candidate:return ('body',body_map[b]) if b in body_map else ('unmapped_candidate',b)
        return ('body',b)
    def edges(graph,bodies,is_candidate):
        counts=Counter(); excluded=[]
        for joint in graph['joints']:
            reason=None
            if not joint['enabled']:reason='disabled_joint'
            elif joint['kind']=='unsupported':reason='unsupported_joint'
            elif any(e['body_id'] and not bodies[e['body_id']]['enabled'] for e in joint['endpoints']):reason='disabled_body'
            ends=[endpoint(e,is_candidate) for e in joint['endpoints']]
            if None in ends:reason='unresolved_endpoint'
            if reason:
                excluded.append({'joint_id':joint['id'],'reason':reason});continue
            key=(*sorted(ends),joint['kind']);counts[key]+=1
        return counts,excluded
    re,rx=edges(reference,rb,False);ce,cx=edges(candidate,cb,True)
    # Connection score uses unique undirected pairs. Typed score preserves parallel joint multiplicity.
    rp={k[:2] for k in re}; cp={k[:2] for k in ce}
    def scores(tp,predicted,expected):
        return {'true_positive':tp,'predicted':predicted,'expected':expected,
                'precision':tp/predicted if predicted else None, 'recall':tp/expected if expected else None}
    def describe(counter):
        return [{'endpoints':[list(k[0]),list(k[1])],'kind':k[2],'count':n} for k,n in sorted(counter.items()) if n]
    mapped_active={c:r for c,r in body_map.items() if c in active_c and r in active_r}
    body_recall=len(set(mapped_active.values()))/len(active_r) if active_r else None
    risks=[]
    for side,graph in (('reference',reference),('candidate',candidate)):
        summary=graph.get('summary')
        expected={'body_count':len(graph['bodies']),'joint_count':len(graph['joints']),
                  'joint_types':dict(Counter(j['kind'] for j in graph['joints']))}
        if summary is not None and summary != expected:
            risks.append({'code':'STALE_GRAPH_SUMMARY','message':'Summary differs from graph records; scoring uses body/joint records only.','side':side})
    if len(mapped_active)!=len(active_c) or len(mapped_active)!=len(active_r):
        risks.append({'code':'INCOMPLETE_BODY_CORRESPONDENCE','message':'Unmapped candidate edges count as extra; unmapped reference edges remain missing. No automatic correspondence was inferred.'})
    if rx or cx:risks.append({'code':'EXCLUDED_JOINTS','message':'Scores cover enabled supported joints with resolved endpoints only; exclusions are listed.'})
    if reference.get('complete') is not True or candidate.get('complete') is not True:
        risks.append({'code':'PARTIAL_INPUT','message':'At least one input does not claim a complete extraction; scores do not erase its gaps.'})
    if reference_sha == candidate_sha:
        risks.append({'code':'SELF_COMPARISON','message':'Identical graph bytes test the scoring pipeline only, not mechanism recognition accuracy.'})
    return {'mechanism_comparison_schema_version':1,
            'measurement':'graph_comparison_given_body_correspondence',
            'body_coverage':{'mapped_active':len(mapped_active),'reference_active':len(active_r),'candidate_active':len(active_c),'reference_recall':body_recall,
                             'unmapped_reference':sorted(active_r-set(mapped_active.values())),'unmapped_candidate':sorted(active_c-set(mapped_active))},
            'connections':scores(len(rp & cp),len(cp),len(rp)),
            'typed_joints':scores(sum((re & ce).values()),sum(ce.values()),sum(re.values())),
            'missing_typed_joints':describe(re-ce),'extra_typed_joints':describe(ce-re),
            'excluded':{'reference':rx,'candidate':cx},
            'source_risks':{'reference':reference.get('risks',[]),'candidate':candidate.get('risks',[])},
            'unassessed':['Rigid-body merging correctness','Axis alignment and location','Travel limits','Coupling ratios','Collision/disassembly feasibility','Generalization to SolidWorks'],
            'requires_human_review':False,'risks':risks,
            'limitations':['Static Xform and world endpoints are treated as grounded for topology only.',
                           'Explicit correspondence is an input to scoring, not proof of correct automatic matching. Zero denominators return null.']}
