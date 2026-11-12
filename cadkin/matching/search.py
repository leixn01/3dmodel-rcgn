"""Bounded, deterministic subgraph hypotheses; no CAD calls, learned confidence or type certification."""
import itertools
import math
from cadkin.errors import ToolFailure
from cadkin.matching.target import axis_angle


def require(ok,message):
    if not ok:raise ToolFailure('INVALID_MATCH_ARGUMENTS',message)


def connected(nodes,edges):
    if not nodes:return False
    reached={next(iter(nodes))}
    while True:
        before=len(reached)
        for a,b in edges:
            if a in reached or b in reached:reached.update((a,b))
        if len(reached)==before:return set(nodes)<=reached


def reference_patterns(references,size):
    patterns=[];coverage=[];limited=False
    for entry,graph in references:
        active={b['id'] for b in graph['bodies'] if b['enabled']}
        joints=[];excluded=[]
        for joint in graph['joints']:
            ids=[e['body_id'] for e in joint['endpoints']]
            if not joint['enabled'] or joint['kind']=='unsupported' or any(i not in active for i in ids) or ids[0]==ids[1]:
                excluded.append(joint['id']);continue
            axes=[e['axis_world'] for e in joint['endpoints']]
            axis=axes[0] if joint['kind'] in ('revolute','prismatic') and all(a is not None for a in axes) and axis_angle(*axes)<=1 else None
            joints.append({'id':joint['id'],'node_ids':ids,'kind':joint['kind'],'axis_unit':axis})
        count_before=len(patterns)
        if 2<=size<=len(active)<=12:
            for ids in itertools.combinations(sorted(active),size):
                inside=[j for j in joints if set(j['node_ids'])<=set(ids)]
                if not connected(ids,[j['node_ids'] for j in inside]):continue
                if len(patterns)>=1024:limited=True;break
                patterns.append({'template_id':entry['id'],'template_sha256':entry['sha256'],'body_ids':list(ids),'joints':inside,
                    'boundary_joint_ids':[j['id'] for j in graph['joints'] if any(e['body_id'] in ids for e in j['endpoints']) and j['id'] not in {x['id'] for x in inside}],
                    'template_risks':graph['risks']})
        coverage.append({'template_id':entry['id'],'eligible_bodies':len(active),'usable_internal_joints':len(joints),
            'pattern_count':len(patterns)-count_before,'excluded_joint_ids':excluded,
            'skip_reason':'template_body_limit' if len(active)>12 else 'no_connected_pattern_of_requested_size' if count_before==len(patterns) else None})
        if len(active)>12:limited=True
    return patterns,coverage,limited


def partial_score(pattern,mapping,pairs):
    return sum(pairs[tuple(sorted(mapping[n] for n in j['node_ids']))]['link_support']
               for j in pattern['joints'] if all(n in mapping for n in j['node_ids']))


def describe_candidate(pattern,mapping,pairs,angle_tolerance_deg):
    edges=[];axis_edges=[];expected_pairs=set();positive=[]
    for joint in pattern['joints']:
        target_ids=[mapping[n] for n in joint['node_ids']];key=tuple(sorted(target_ids));pair=pairs[key];expected_pairs.add(key)
        if pair['link_support']>0:positive.append(key)
        edge={'reference_joint_id':joint['id'],'occurrence_paths':target_ids,'hypothesis_kind':joint['kind'],
              'kind_basis':'reference_template_only','mechanical_relation_confirmed':False,
              'target_pair_id':pair['id'],'link_support':pair['link_support'],
              'target_geometric_axis_unit':pair['representative_axis_unit'],'joint_axis_verified':False,
              'axis_origin_m':None,'limits':None,'flags':pair['flags'],
              'evidence_ids':sorted({s['source']['evidence_id'] for s in pair['signals'] if s.get('source')}),
              'axis_evidence':[{'source':a['source'],'candidate_index':a['candidate_index']} for a in pair['axis_relations']]}
        edges.append(edge)
        if joint['kind'] in ('prismatic','revolute'):axis_edges.append((joint,edge))
    # Every mapped occurrence needs a connected positive-evidence path; don't arbitrarily fill unknown slots.
    if not connected(set(mapping.values()),positive):return None
    angle_checks=[];angle_sum=0.;possible=0
    for (a,ta),(b,tb) in itertools.combinations(axis_edges,2):
        possible+=1
        if a['axis_unit'] is None or b['axis_unit'] is None or ta['target_geometric_axis_unit'] is None or tb['target_geometric_axis_unit'] is None:continue
        reference_angle=axis_angle(a['axis_unit'],b['axis_unit'])
        target_angle=axis_angle(ta['target_geometric_axis_unit'],tb['target_geometric_axis_unit'])
        residual=abs(reference_angle-target_angle);fit=max(0.,1-residual/angle_tolerance_deg);angle_sum+=fit
        angle_checks.append({'reference_joint_ids':[a['id'],b['id']],'target_pair_ids':[ta['target_pair_id'],tb['target_pair_id']],
                             'reference_angle_deg':reference_angle,'target_angle_deg':target_angle,'residual_deg':residual,'fit':fit})
    extra=[]
    for a,b in itertools.combinations(sorted(mapping.values()),2):
        pair=pairs[(a,b)]
        if (a,b) not in expected_pairs and pair['link_support']>0:
            extra.append({'node_ids':[a,b],'target_pair_id':pair['id'],'link_support':pair['link_support']})
    support=sum(e['link_support'] for e in edges)/len(edges)
    axis_score=angle_sum/possible if possible else 0.
    extra_penalty=.1*sum(p['link_support'] for p in extra)/max(1,math.comb(len(mapping),2))
    score=max(0.,.7*support+.3*axis_score-extra_penalty)
    return {'template_id':pattern['template_id'],'template_sha256':pattern['template_sha256'],
            'mapping':[{'template_body_id':n,'occurrence_path':mapping[n]} for n in sorted(mapping)],
            'score':round(score,12),'score_components':{'mean_link_support':support,'relative_axis_fit_with_coverage':axis_score,'extra_support_penalty':extra_penalty},
            'joint_hypotheses':edges,'axis_relation_checks':angle_checks,
            'coverage':{'pattern_bodies':len(mapping),'pattern_joints':len(edges),'supported_joints':sum(e['link_support']>0 for e in edges),
                        'possible_axis_checks':possible,'completed_axis_checks':len(angle_checks)},
            'unsupported_template_joint_ids':[e['reference_joint_id'] for e in edges if e['link_support']==0],
            'extra_supported_pairs':extra,'unmatched_reference_boundary_joint_ids':pattern['boundary_joint_ids'],
            'template_risks':pattern['template_risks'],'scope':'local_template_subgraph','mechanical_relation_confirmed':False,
            'risk_codes':sorted({'TEMPLATE_HYPOTHESIS','ONE_OCCURRENCE_PER_REFERENCE_BODY','JOINT_TYPE_NOT_VERIFIED'} |
                ({'AXIS_RELATIONS_UNASSESSED'} if len(angle_checks)<possible or possible==0 else set()) |
                ({'CONFLICTING_EVIDENCE'} if any(e['flags'] for e in edges) else set()) |
                ({'EXTRA_SUPPORTED_PAIRS'} if extra else set()) |
                ({'MISSING_EDGE_SUPPORT'} if any(e['link_support']==0 for e in edges) else set()))}


def candidate_key(c):
    return (-c['score'],c['template_id'],tuple((m['template_body_id'],m['occurrence_path']) for m in c['mapping']))


def match_patterns(target,references,pattern_size=3,max_candidates=5,max_states=20000,beam_width=50,angle_tolerance_deg=10):
    require(type(pattern_size) is int and 2<=pattern_size<=6,'pattern_size must be 2–6.')
    require(type(max_candidates) is int and 1<=max_candidates<=20,'max_candidates must be 1–20.')
    require(type(max_states) is int and 1<=max_states<=100000,'max_states must be 1–100000.')
    require(type(beam_width) is int and 1<=beam_width<=1000,'beam_width must be 1–1000.')
    require(type(angle_tolerance_deg) in (int,float) and math.isfinite(angle_tolerance_deg) and 0<angle_tolerance_deg<=45,'angle_tolerance_deg must be finite in (0,45].')
    ids=sorted(n['id'] for n in target['nodes'] if n['eligible']);size=min(pattern_size,len(ids))
    patterns,reference_coverage,pattern_limit=reference_patterns(references,size)
    pairs={tuple(p['node_ids']):p for p in target['pairs']};kept=[];search_rows=[];score_counts={};valid_count=0
    by_template={e['id']:{'template_id':e['id'],'best_score_found':None,'supported_candidates_found':0} for e,_ in references}
    for index,pattern in enumerate(patterns):
        quota=max_states//len(patterns)+(index<max_states%len(patterns));evaluated=0;pruned=0;budget_hit=False
        degree={n:sum(n in j['node_ids'] for j in pattern['joints']) for n in pattern['body_ids']}
        order=sorted(pattern['body_ids'],key=lambda n:(-degree[n],n));beam=[{}];completed=0;accepted=0
        for depth,node in enumerate(order):
            expanded=[];stop=False
            for mapping in beam:
                for tid in ids:
                    if tid in mapping.values():continue
                    if evaluated>=quota:budget_hit=True;stop=True;break
                    evaluated+=1;new={**mapping,node:tid}
                    if depth==len(order)-1:
                        completed+=1;candidate=describe_candidate(pattern,new,pairs,angle_tolerance_deg)
                        if candidate is not None:
                            accepted+=1;valid_count+=1
                            summary=by_template[pattern['template_id']];summary['supported_candidates_found']+=1
                            summary['best_score_found']=max(candidate['score'],summary['best_score_found'] or 0.)
                            score_counts[candidate['score']]=score_counts.get(candidate['score'],0)+1
                            kept.append(candidate);kept.sort(key=candidate_key)
                            if len(kept)>max_candidates:kept.pop()
                    else:expanded.append(new)
                if stop:break
            if depth==len(order)-1 or budget_hit:break
            expanded.sort(key=lambda m:(-partial_score(pattern,m,pairs),tuple(sorted(m.items()))))
            pruned+=max(0,len(expanded)-beam_width);beam=expanded[:beam_width]
            if not beam:break
        search_rows.append({'template_id':pattern['template_id'],'body_ids':pattern['body_ids'],'state_budget':quota,
            'evaluated_states':evaluated,'completed_mappings':completed,'supported_mappings':accepted,'beam_pruned_states':pruned,'state_budget_hit':budget_hit})
    exhaustive=not pattern_limit and not any(r['state_budget_hit'] or r['beam_pruned_states'] for r in search_rows)
    for summary in by_template.values():
        summary['returned_candidates']=sum(c['template_id']==summary['template_id'] for c in kept)
    best_score=kept[0]['score'] if kept else None;ties=score_counts.get(best_score,0)
    for rank,candidate in enumerate(kept,1):
        candidate['rank']=rank;candidate['equal_score_candidates_found']=score_counts[candidate['score']]
    return {'mechanism_match_schema_version':1,'algorithm_version':1,
            'parameters':{'pattern_size':pattern_size,'max_candidates':max_candidates,'max_states':max_states,'beam_width':beam_width,'angle_tolerance_deg':angle_tolerance_deg},
            'effective_pattern_size':size,'candidates':kept,'supported_candidates_found':valid_count,
            'returned_candidates':len(kept),'output_truncated':valid_count>len(kept),'best_score':best_score,
            'best_score_ties_found':ties,'ambiguous':ties>1 or not exhaustive,
            'search_exhaustive':exhaustive,'search_scope':'selected template windows and eligible explicit target occurrences',
            'search':{'pattern_limit':pattern_limit,'evaluated_states':sum(r['evaluated_states'] for r in search_rows),'patterns':search_rows},
            'template_rankings':sorted(by_template.values(),key=lambda r:(-(r['best_score_found'] or 0.),r['template_id'])),
            'reference_coverage':reference_coverage,'target_coverage':target['coverage'],'target_errors':target['errors'],
            'target_boundary_evidence':target['boundary_evidence'],
            'requires_human_review':False,'solidworks_modified':False,'mechanical_relation_confirmed':False,
            'score_definition':{'formula':'max(0, 0.7 * mean_link_support + 0.3 * relative_axis_fit_with_coverage - extra_support_penalty)',
                'axis_fit':'max(0, 1 - abs(reference_angle - target_angle) / angle_tolerance_deg); unoriented angles, absent/ambiguous axes contribute zero.',
                'extra_penalty':'0.1 * sum(extra pair support) / number of possible mapped pairs',
                'meaning':'Uncalibrated hypothesis ranking only; no probability, joint-type accuracy or motion validation.'},
            'limitations':['Template windows are connected subgraphs; every mapped occurrence must have a positive-evidence path. No complete-machine recognition claim.',
                'One occurrence maps to one reference body. Multi-part rigid groups are not merged; missing bodies can prevent a candidate.',
                'Axis angle relations are rotation-invariant necessary clues, not a solved frame alignment or verified joint axis; distances/limits are not transferred.',
                'Names, role labels, reference node IDs and dimensions do not contribute to score; IDs only make ties/order deterministic.',
                'Kinds are template hypotheses. Concentric/parallel/contact/mate evidence alone does not identify a revolute/prismatic/fixed joint.',
                'Beam pruning and per-pattern state budgets can miss better mappings; ties/symmetries remain explicit; no supported result is not proof of absence.']}
