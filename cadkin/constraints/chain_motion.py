"""Assemble supported pair velocity equations in one common frame, per source snapshot."""
from copy import deepcopy
import math

from cadkin.constraints.linear import decompose
from cadkin.constraints.motion import model_snapshot, cross
from cadkin.errors import ToolFailure
from cadkin.geometry import numbers

MAX_EQUATIONS = 6000

def internal_boundary(record, nodes):
    locators=record['entity_locators'];paths=record['verified_reference_paths']
    return len(locators)==2 and len(paths)==2 and set(paths)<=set(nodes) and all(
        x['reference_status']=='verified_root_occurrence' and x['occurrence_path'] in nodes for x in locators)


def assemble_snapshot(analysis, nodes, source, reference, length_m, tolerance, max_constraints):
    models=[];handled=set();blockers=[];conflicts=[];equation_count=0
    for pair in sorted(analysis['pairs'],key=lambda p:p['pair_id']):
        matches=[s for s in pair['snapshots'] if s['source']==source]
        if len(matches)!=1:raise ToolFailure('INVALID_CONSTRAINT_SOURCE','Pair snapshots do not share the same bound source set.')
        original=matches[0];snapshot=deepcopy(original)
        inside={r['id'] for r in original['boundary_evidence'] if internal_boundary(r,nodes)}
        for missing in snapshot['missing_evidence']:
            if missing['code']=='BOUNDARY_OR_UNRESOLVED_MATES':
                missing['evidence_ids']=[x for x in missing['evidence_ids'] if x not in inside]
        snapshot['missing_evidence']=[m for m in snapshot['missing_evidence'] if
            m['code']!='NO_USABLE_ACTIVE_PAIR_MATES' and not (m['code']=='BOUNDARY_OR_UNRESOLVED_MATES' and not m['evidence_ids'])]
        handled.update(inside)
        paths=sorted(pair['occurrence_paths'])
        model=model_snapshot(paths,snapshot,length_m,tolerance,max_constraints,[])
        equation_count+=len(model['rows'])
        if equation_count>MAX_EQUATIONS:
            raise ToolFailure('CHAIN_EQUATION_LIMIT','A snapshot exceeds 6000 equations. Use an explicitly smaller chain or lower the per-pair constraint budget; do not silently omit equations.')
        # Pair rank is diagnostic; the assembled system gets its own rank sensitivity test.
        pair_missing=[m for m in model['unresolved_evidence'] if m['code'] not in ('NUMERICAL_RANK_SENSITIVE','TRANSLATION_SUBSPACE_SENSITIVE')]
        blockers.extend({'pair_id':pair['pair_id'],**m} for m in pair_missing)
        conflicts.extend({'pair_id':pair['pair_id'],**c} for c in model['source_conflicts'])
        models.append((pair,model))
    if analysis['coverage']['omitted_pairs']:blockers.append({'code':'ANALYSIS_PAIR_LIMIT','omitted_pairs':analysis['coverage']['omitted_pairs']})
    if analysis['source_errors']:blockers.append({'code':'TARGET_SOURCE_ERRORS','errors':deepcopy(analysis['source_errors'])})
    unmapped=[r for r in analysis['unmapped_mates'] if r['source']==source and r['feature_ids']]
    if unmapped:blockers.append({'code':'UNMAPPED_MATE_REFERENCES','sources':deepcopy(unmapped)})
    points=[s['idealization_face']['point_root_m'] for _,m in models for s in m['modeled_constraints'] if s['idealization_face']]
    origin=[sum(p[i]/len(points) for p in points) for i in range(3)] if points else [0.,0.,0.]
    numbers(origin,3,'NUMERICAL_SOLUTION_INVALID')
    variables=[n for n in nodes if n!=reference];columns=6*len(variables);positions={n:6*i for i,n in enumerate(variables)}
    parents={n:n for n in nodes}
    def find(n):
        while parents[n]!=n:n=parents[n]
        return n
    rows=[];tree_rows=[];edges=[]
    for pair,model in models:
        if not model['rows']:continue
        paths=sorted(pair['occurrence_paths']);a,b=paths;first=find(a);second=find(b);loop=first==second
        if not loop:parents[second]=first
        start=len(rows);shift=[(p-o)/length_m for p,o in zip(model['velocity_origin_root_m'],origin)]
        for local in model['rows']:
            v=local['coefficients'][:3];w=[x+y for x,y in zip(local['coefficients'][3:],cross(shift,v))]
            coefficients=[0.]*columns
            for name,sign in ((a,-1),(b,1)):
                if name==reference:continue
                offset=positions[name]
                for i,x in enumerate(v+w):coefficients[offset+i]=sign*x
            norm=math.hypot(*coefficients)
            if not math.isfinite(norm) or norm==0:raise ToolFailure('NUMERICAL_SOLUTION_INVALID','Invalid assembled row.')
            coefficients=[x/norm for x in coefficients]
            rows.append({'coefficients':coefficients,'pair_id':pair['pair_id'],'occurrence_paths':paths,
                'equation':local['equation'],'evidence_ids':local['evidence_ids']})
            if not loop:tree_rows.append(coefficients)
        edges.append({'pair_id':pair['pair_id'],'occurrence_paths':paths,'closes_spanning_forest_cycle':loop,
            'row_indices':list(range(start,len(rows))),'pair_velocity_origin_root_m':model['velocity_origin_root_m'],
            'modeled_constraints':model['modeled_constraints'],'omitted_constraints':model['coverage']['omitted_constraints']})
    groups={}
    for n in nodes:groups.setdefault(find(n),[]).append(n)
    components=sorted(groups.values())
    if len(components)>1:blockers.append({'code':'DISCONNECTED_CONSTRAINT_GRAPH','components':components})
    numeric=decompose([r['coefficients'] for r in rows],columns,tolerance) if rows else None
    tree=decompose(tree_rows,columns,tolerance) if tree_rows else None
    stable=bool(numeric and numeric['rank_stable'])
    if numeric and not stable:blockers.append({'code':'NUMERICAL_RANK_SENSITIVE','rank_range':numeric['rank_range']})
    loop_rank=numeric['rank']-tree['rank'] if stable and tree and tree['rank_stable'] else None
    if loop_rank is not None and loop_rank<0:
        blockers.append({'code':'LOOP_RANK_COMPARISON_SENSITIVE'});loop_rank=None
    modes=[]
    if stable and not conflicts:
        for vector in numeric['basis']:
            bodies=[]
            for n in nodes:
                twist=[0.]*6 if n==reference else vector[positions[n]:positions[n]+6]
                bodies.append({'occurrence_path':n,'scaled_twist':twist,'linear_velocity_at_origin_m_per_unit_time':[v*length_m for v in twist[:3]],
                    'angular_velocity_rad_per_unit_time':twist[3:]})
            modes.append({'components':bodies})
    complete=bool(stable and not blockers and not conflicts)
    return {'source':source,'reference_occurrence_path':reference,'reference_is_physical_ground':False,
        'frame':'root_assembly_axes','velocity_origin_root_m':origin,'characteristic_length_m':length_m,
        'variable_occurrence_order':variables,'twist_order':['vx_over_length','vy_over_length','vz_over_length','wx','wy','wz'],
        'rows':rows,'edges':edges,'constraint_graph_components':components,'graph_cycle_count':len(edges)-len(nodes)+len(components),
        'linear_solution':numeric,'known_constraint_nullity':numeric['nullity'] if numeric else None,
        'modeled_chain_instantaneous_dof':numeric['nullity'] if complete else None,
        'spanning_forest_diagnostics':{'rank':tree['rank'] if tree else None,'rank_stable':tree['rank_stable'] if tree else None,
            'known_constraint_nullity':tree['nullity'] if tree else None,
            'additional_loop_rank':loop_rank,
            'scope':'Deterministic pair-order spanning forest; threshold-sensitive counts are not compared.'},
        'motion_modes':modes,'mode_scope':'known_supported_chain_constraint_subset_only',
        'status':'conflicting_source' if conflicts else 'no_supported_constraint_model' if not rows else
            'numerically_sensitive' if not stable else 'partial_constraint_model' if blockers else 'modeled_chain_snapshot',
        'chain_constraint_system_solved':complete,'unresolved_evidence':blockers,'source_conflicts':conflicts,
        'internal_boundary_mates_handled':sorted(handled),
        'pair_diagnostics':[{'pair_id':p['pair_id'],'status':m['status'],'source_missing_evidence':p['snapshots'][next(i for i,s in enumerate(p['snapshots']) if s['source']==source)]['missing_evidence'],
            'pattern_gaps_addressed':m['pattern_gaps_addressed']} for p,m in models],
        'coverage':{'components':len(nodes),'variables':columns,'modeled_edges':len(edges),'equations':len(rows),
            'omitted_constraints':sum(m['coverage']['omitted_constraints'] for _,m in models)},
        'target_joint_kind':'unknown','target_degrees_of_freedom':None,'finite_motion_verified':False,'assembly_dof_solved':False}


def solve_chain(analysis, node_paths, reference_occurrence_path, characteristic_length_mm, relative_rank_tolerance=1e-8,max_constraints_per_pair=200):
    nodes=sorted(node_paths)
    if not 2<=len(nodes)<=20 or len(nodes)!=len(set(nodes)):raise ToolFailure('CHAIN_SCOPE_LIMIT','Use an original explicit chain with 2–20 distinct leaf occurrences.')
    if reference_occurrence_path not in nodes:raise ToolFailure('INVALID_ARGUMENTS','Reference occurrence must belong to the original target chain.')
    numbers([characteristic_length_mm,relative_rank_tolerance],2,'INVALID_ARGUMENTS')
    if not (1e-3<=characteristic_length_mm<=1e6 and 1e-10<=relative_rank_tolerance<=1e-3 and type(max_constraints_per_pair) is int and 1<=max_constraints_per_pair<=200):
        raise ToolFailure('INVALID_ARGUMENTS','Use length 0.001–1000000 mm, tolerance 1e-10–1e-3 and pair constraint budget 1–200.')
    snapshots=[assemble_snapshot(analysis,nodes,s,reference_occurrence_path,characteristic_length_mm/1000,relative_rank_tolerance,max_constraints_per_pair) for s in analysis['mate_sources']]
    return {'chain_constraint_solution_schema_version':1,'algorithm_version':1,'document':analysis['document'],
        'parameters':{'reference_occurrence_path':reference_occurrence_path,'characteristic_length_mm':characteristic_length_mm,
            'relative_rank_tolerance':relative_rank_tolerance,'max_constraints_per_pair':max_constraints_per_pair},
        'occurrence_paths':nodes,'snapshots':snapshots,'analysis_coverage':deepcopy(analysis['coverage']),
        'source_errors':deepcopy(analysis['source_errors']), 'missing_evidence':[] if snapshots else [{'code':'NO_ROOT_MATE_SOURCE'}],
        'coverage':{'components':len(nodes),'snapshots':len(snapshots),'modeled_snapshots':sum(s['chain_constraint_system_solved'] for s in snapshots),
            'partial_snapshots':sum(s['status']=='partial_constraint_model' for s in snapshots),'conflicting_snapshots':sum(bool(s['source_conflicts']) for s in snapshots),
            'numerically_sensitive':sum(s['status']=='numerically_sensitive' for s in snapshots),
            'omitted_pairs':analysis['coverage']['omitted_pairs'],'omitted_constraints':sum(s['coverage']['omitted_constraints'] for s in snapshots)},
        'target_degrees_of_freedom':None,'assembly_dof_solved':False,'mechanically_verified':False,'finite_motion_verified':False,
        'solidworks_modified':False,'requires_human_review':False,
        'limitations':['Only explicit supported two-occurrence root mates are assembled; no contacts, names, templates or IsFixed constraints.',
            'The reference body removes common rigid motion as a coordinate convention, not proof of physical grounding.',
            'Disconnected or incomplete models retain diagnostic nullspaces, not verified chain mobility.',
            'All equations share root axes and one velocity origin. Pair nullities cannot be added to obtain chain mobility.',
            'Cycles and dependent equations are topology/linear diagnostics, not nonlinear loop feasibility, removable mates or finite travel.',
            'Each mate snapshot is solved separately; geometric idealization, original tolerances, missing evidence and capture history remain relevant.',
            'Outputs do not confirm target joints, full assembly DOF, collision clearance or disassembly paths.']}
