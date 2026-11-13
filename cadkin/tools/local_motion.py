"""Source-bound offline local constraint solving; independent of capture and drafting."""
from copy import deepcopy
import math

from cadkin.errors import success
from cadkin.tools.files import json_path, read_json, replay_reads
from cadkin.tools.chain_sources import require, check_fields
from cadkin.tools.constraint_analysis import replay_analysis
from cadkin.tools.matching import recheck
from cadkin.tools.observation_index import unique_bindings
from cadkin.tools.proximity import write_result
from cadkin.constraints.motion import solve_analysis


@replay_reads
def build_solution(root, constraint_analysis_path, **parameters):
    analysis, binding = replay_analysis(root, constraint_analysis_path)
    data = solve_analysis(analysis, **parameters)
    data['parameters']['constraint_analysis_path'] = binding['path']
    data.update(constraint_analysis_source=binding, target_source=analysis['target_source'],
        analysis_parameters=deepcopy(analysis['parameters']),
        input_files=unique_bindings(root, analysis['input_files']+[binding]))
    for key in ('evidence_index_source','check_source','rounds_completed','max_rounds'):
        if key in analysis: data[key] = deepcopy(analysis[key])
    recheck(root, data['input_files'])
    return data


def numerical_equal(actual, expected):
    """Only computed solver outputs tolerate LAPACK roundoff; inputs/bindings stay exact."""
    if type(expected) is float:
        return type(actual) in (int,float) and math.isfinite(actual) and math.isclose(actual,expected,rel_tol=1e-9,abs_tol=1e-10)
    if type(expected) is dict:
        return isinstance(actual,dict) and actual.keys()==expected.keys() and all(numerical_equal(actual[k],v) for k,v in expected.items())
    if type(expected) is list:
        return isinstance(actual,list) and len(actual)==len(expected) and all(numerical_equal(a,b) for a,b in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


@replay_reads
def replay_solution(root, local_constraints_path):
    path=json_path(root,local_constraints_path);raw,digest=read_json(path)
    keys={'constraint_analysis_path','characteristic_length_mm','relative_rank_tolerance','max_pairs','max_constraints_per_snapshot'}
    require(isinstance(raw,dict) and raw.get('local_constraint_solution_schema_version')==1 and raw.get('algorithm_version')==1 and
        isinstance(raw.get('parameters'),dict) and set(raw['parameters'])==keys,'Use the original local constraint solution.','INVALID_LOCAL_CONSTRAINT_SOURCE')
    expected=build_solution(root,**raw['parameters'])
    checked=deepcopy(raw)
    require(isinstance(checked.get('pairs'),list) and len(checked['pairs'])==len(expected['pairs']),'Local pair scope differs.','EVIDENCE_MISMATCH')
    for actual_pair,expected_pair in zip(checked['pairs'],expected['pairs']):
        require(isinstance(actual_pair,dict) and isinstance(actual_pair.get('snapshots'),list) and len(actual_pair['snapshots'])==len(expected_pair['snapshots']),
            'Local snapshot scope differs.','EVIDENCE_MISMATCH')
        for actual,computed in zip(actual_pair['snapshots'],expected_pair['snapshots']):
            require(isinstance(actual,dict),'Invalid local snapshot.','EVIDENCE_MISMATCH')
            for key in ('linear_solution','motion_modes','pure_translation_directions_root'):
                require(numerical_equal(actual.get(key),computed[key]),'Local numeric solution differs.','EVIDENCE_MISMATCH')
                actual[key]=computed[key]
    check_fields(checked,expected)
    recheck(root,expected['input_files']+[{'path':str(path),'sha256':digest}])
    return expected,{'path':str(path),'sha256':digest}


def solve_local_constraints(root, output_path, **parameters):
    output=json_path(root,output_path,output=True)
    data=build_solution(root,**parameters);write_result(output,data)
    errors=list(data['source_errors'])
    if data['coverage']['omitted_pairs'] or data['coverage']['omitted_constraints']:
        errors.append({'code':'LOCAL_CONSTRAINT_LIMIT','message':'Unreturned pairs or constraints remain unknown.'})
    if data['coverage']['numerically_sensitive']:
        errors.append({'code':'NUMERICAL_RANK_SENSITIVE','message':'Rank changes under threshold sensitivity; no definitive local count.'})
    return success({'output_path':str(output),**data},errors)
