"""Only missing pair-distance observations; face verification uses its separate planner."""
from cadkin.followup import stable_id
from cadkin.followup.observations import request_key, MAX_ROUNDS
from cadkin.followup.planning import assemble_plan


def plan_geometry_tasks(target,check,analysis,index,directory,max_tasks):
    rounds=0 if index is None else index['rounds_completed']
    attempts=[] if index is None else index['observations']
    nodes={n['id']:n for n in target['nodes']}
    requests,reused,blocked,unresolved={},{},{},[]
    for pair in analysis['pairs']:
        paths=sorted(pair['occurrence_paths']);key=request_key('sw_component_distance',paths)
        previous=[o for o in attempts if o['tool']=='sw_component_distance' and sorted(o['occurrence_paths'])==paths]
        distance=pair['distance_observations']
        if distance or previous:
            reused[key]={'family':'distance','occurrence_paths':paths,'sources':[o['source'] for o in distance],
                'attempted_observation_ids':[o['id'] for o in previous],
                'meaning':'Retain complete observations and unsuccessful attempts; do not repeat scans or change budgets to retry.'}
        for gap in pair['verification_gaps']:
            if gap['action']!='collect_component_distance':
                unresolved.append({'finding_id':gap['id'],'reason':gap['code'],'action':gap['action'],
                    'next_tool':gap.get('tool'),'occurrence_paths':paths})
                continue
            reason = ('INVALID_DERIVATION' if not check['structural_checks_passed'] else
                'ROUND_LIMIT' if rounds>=MAX_ROUNDS else
                'PRIOR_DISTANCE_ATTEMPT_NO_AUTOMATIC_RETRY' if distance or previous else
                'SOURCE_CONTEXT_UNAVAILABLE' if any(not nodes[p]['eligible'] or nodes[p].get('source_errors') or
                    nodes[p].get('to_root_column_vectors_m') is None for p in paths) else None)
            if reason:
                blocked[key]={'tool':'sw_component_distance','occurrence_paths':paths,'finding_ids':[gap['id']],
                    'reason':reason,'observation_ids':[o['id'] for o in previous]}
                continue
            args={'expected_document_token':target['document']['document_token'],
                  'left_occurrence_path':paths[0],'right_occurrence_path':paths[1]}
            task=stable_id('capture-',['sw_component_distance',args])
            requests[task]={'id':task,'tool':'sw_component_distance','arguments':args,'occurrence_paths':paths,
                'finding_ids':[gap['id']],'priority':20,'integration':'index_then_reanalyze_geometric_connections'}
    result=assemble_plan(target,check,{'_indexed':True,'rounds_completed':rounds},directory,max_tasks,
                         requests,reused,unresolved,blocked)
    result.update(algorithm_version=6,plan_kind='geometric_connection_gaps',geometry_coverage=analysis['coverage'],
        geometry_findings=[g for p in analysis['pairs'] for g in p['verification_gaps']],
        retained_geometry_flags=[{'pair_id':p['pair_id'],'flags':p['flags']} for p in analysis['pairs'] if p['flags']])
    result['output_truncated'] |= bool(analysis['coverage']['omitted_pairs'] or analysis['coverage']['pairs_with_observation_limits'])
    result['recompute_handoffs']=[
        {'family':'guarded_distance','next_tools':['cad_index_evidence','cad_analyze_geometric_connections'],
         'note':'Use the same check and new receipt to index all attempts, then reanalyze the same target with that latest index. No existing proximity review is required.'},
        {'family':'finite_face_samples','next_tools':['cad_plan_face_probes'],
         'note':'Only when measured witnesses and the latest index are available. The independent planner validates catalogs, seeds, attempts and the shared four-round limit.'}]
    result['limitations'].extend(['Geometry interpretations never enter the native constraint solver as invented mates.',
        'Only missing component distances are collected here. Read-only face probes can test local geometry, not certify physical joints or finite motion.',
        'Already observed separation, failed/partial captures and complete empty scans are retained; no repeated capture or automatic budget escalation.'])
    return result
