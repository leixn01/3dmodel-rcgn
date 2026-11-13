"""Source replay and compact result routing for chain instantaneous constraints."""
from copy import deepcopy
from collections import Counter
from cadkin.errors import success
from cadkin.tools.files import json_path,read_json,replay_reads
from cadkin.tools.chain_sources import require,check_fields
from cadkin.tools.constraint_analysis import replay_analysis
from cadkin.tools.matching import replay_target,recheck
from cadkin.tools.observation_index import unique_bindings
from cadkin.tools.proximity import write_result
from cadkin.tools.local_motion import numerical_equal
from cadkin.constraints.chain_motion import solve_chain


@replay_reads
def build_chain_solution(root,constraint_analysis_path,**parameters):
    analysis,binding=replay_analysis(root,constraint_analysis_path)
    target,tb=replay_target(root,analysis['target_source']['path'])
    require(tb==analysis['target_source'],'Target source differs.','EVIDENCE_MISMATCH')
    data=solve_chain(analysis,[n['id'] for n in target['nodes']],**parameters)
    data['parameters']['constraint_analysis_path']=binding['path']
    data.update(constraint_analysis_source=binding,target_source=tb,analysis_parameters=deepcopy(analysis['parameters']),
        input_files=unique_bindings(root,analysis['input_files']+[binding]))
    for key in ('evidence_index_source','check_source','rounds_completed','max_rounds'):
        if key in analysis:data[key]=deepcopy(analysis[key])
    recheck(root,data['input_files']);return data


@replay_reads
def replay_chain_solution(root,chain_constraints_path):
    path=json_path(root,chain_constraints_path);raw,digest=read_json(path)
    keys={'constraint_analysis_path','reference_occurrence_path','characteristic_length_mm','relative_rank_tolerance','max_constraints_per_pair'}
    require(isinstance(raw,dict) and raw.get('chain_constraint_solution_schema_version')==1 and raw.get('algorithm_version')==1 and
        isinstance(raw.get('parameters'),dict) and set(raw['parameters'])==keys,'Use the original chain constraint solution.','INVALID_CHAIN_CONSTRAINT_SOURCE')
    expected=build_chain_solution(root,**raw['parameters']);checked=deepcopy(raw)
    require(isinstance(checked.get('snapshots'),list) and len(checked['snapshots'])==len(expected['snapshots']),'Snapshot scope differs.','EVIDENCE_MISMATCH')
    for actual,computed in zip(checked['snapshots'],expected['snapshots']):
        require(isinstance(actual,dict),'Invalid chain snapshot.','EVIDENCE_MISMATCH')
        for key in ('linear_solution','motion_modes'):
            require(numerical_equal(actual.get(key),computed[key]),'Chain numeric solution differs.','EVIDENCE_MISMATCH');actual[key]=computed[key]
    check_fields(checked,expected);recheck(root,expected['input_files']+[{'path':str(path),'sha256':digest}])
    return expected,{'path':str(path),'sha256':digest}


def solve_chain_constraints(root,output_path,**parameters):
    output=json_path(root,output_path,output=True);data=build_chain_solution(root,**parameters);write_result(output,data)
    _,digest=read_json(output);errors=list(data['source_errors'])
    if data['coverage']['omitted_pairs'] or data['coverage']['omitted_constraints']:errors.append({'code':'CHAIN_CONSTRAINT_LIMIT','message':'Omitted constraints/pairs remain unknown.'})
    if data['coverage']['numerically_sensitive']:errors.append({'code':'NUMERICAL_RANK_SENSITIVE','message':'Chain rank is threshold-sensitive.'})
    compact={k:data[k] for k in ('coverage','parameters','target_degrees_of_freedom','assembly_dof_solved','finite_motion_verified','solidworks_modified','requires_human_review')}
    compact.update(output_path=str(output),solution_source={'path':str(output),'sha256':digest},detail_saved=True,
        snapshots=[{**{k:s[k] for k in ('source','status','modeled_chain_instantaneous_dof','known_constraint_nullity','graph_cycle_count','spanning_forest_diagnostics')},
            'unresolved_evidence_counts':dict(sorted(Counter(m['code'] for m in s['unresolved_evidence']).items())),
            'source_conflict_counts':dict(sorted(Counter(m['code'] for m in s['source_conflicts']).items()))} for s in data['snapshots']])
    for key in ('evidence_index_source','check_source','rounds_completed','max_rounds'):
        if key in data:compact[key]=data[key]
    return success(compact,errors)
