"""Compare retained hypotheses; disappearing entries never prove physical resolution."""
from cadkin.followup import stable_id


def candidates(draft):
    result={}
    for run in draft['partition_results']:
        for row in run.get('connection_candidates', []):
            mapping = sorted(tuple(sorted(paths)) for paths in row['member_occurrence_paths'])
            key = stable_id('target-relationship-', mapping)
            result[key] = {'basis': 'target_evidence', 'mapping': mapping, 'target_joint_kind': row['target_joint_kind'],
                'target_degrees_of_freedom': row['target_degrees_of_freedom'], 'assessment': row['assessment'],
                'signals': row['signals'], 'flags': row['flags'], 'geometry': row['geometry']}
        if run['match'] is None:continue
        for row in run['match']['candidates']:
            mapping=sorted((m['template_body_id'],tuple(sorted(m['member_occurrence_paths']))) for m in row['mapping'])
            key=stable_id('candidate-', [row['template_id'],mapping])
            result[key]={'template_id':row['template_id'],'mapping':mapping,'score':row['score'],
                         'joint_hypotheses':[{k:j[k] for k in ('reference_joint_id','hypothesis_kind','member_occurrence_paths','direction_candidate_root_unit','geometry')} for j in row['joint_hypotheses']]}
            if draft.get('algorithm_version') == 2:
                result[key]['basis'] = 'optional_reference_analogy'
                for new, old in zip(result[key]['joint_hypotheses'], row['joint_hypotheses']):
                    new.update(reference_joint_kind=old['reference_joint_kind'], reference_compatibility=old['reference_compatibility'])
    return result


def compare_checks(before,after,before_draft,after_draft,before_target,after_target):
    left={f['id']:f for f in before['findings']};right={f['id']:f for f in after['findings']}
    a,b=candidates(before_draft),candidates(after_draft)
    def delta(old,new):
        return {'newly_observed_ids':sorted(new.keys()-old.keys()),'still_observed_ids':sorted(old.keys()&new.keys()),
                'no_longer_observed_ids':sorted(old.keys()-new.keys()),
                'changed_ids':sorted(k for k in old.keys()&new.keys() if old[k]!=new[k])}
    settings_equal=(before_draft['parameters']==after_draft['parameters'] and before_draft['template_sources']==after_draft['template_sources'] and before['parameters']['max_findings']==after['parameters']['max_findings'])
    before_scope=sorted(n['id'] for n in before_target['nodes']);after_scope=sorted(n['id'] for n in after_target['nodes'])
    return {'draft_comparison_schema_version':1,'algorithm_version':1,
            'settings_equal':settings_equal,'occurrence_scope_equal':before_scope==after_scope,
            'findings':delta(left,right),'candidates':delta(a,b),
            'before_candidates':a,'after_candidates':b,
            'summary':{'before_findings':before['summary'],'after_findings':after['summary'],
                       'before_candidates':len(a),'after_candidates':len(b)},
            'coverage':{'before_check_truncated':before['output_truncated'],'after_check_truncated':after['output_truncated'],
                        'before_draft_search_exhaustive':before_draft['search_exhaustive_within_retained_partitions'],
                        'after_draft_search_exhaustive':after_draft['search_exhaustive_within_retained_partitions'],
                        'before_target':before_target['coverage'],'after_target':after_target['coverage']},
            'heldout_exposed':before['heldout_exposed'] or after['heldout_exposed'],
            'requires_human_review':False,'solidworks_modified':False,'mechanically_verified':False,
            'resolved_findings_asserted':False,
            'limitations':['Comparisons concern returned candidates and findings, not every possible mechanism.',
                'New evidence, grouping changes, ranking, search budgets and output truncation can remove entries; no_longer_observed is never a resolved verdict.',
                'Scores rank hypotheses, not probabilities. Same settings do not guarantee identical searched spaces after evidence changes.',
                'Capture/recomputation success does not certify rigidity, joint type, DOF, stroke, collision or disassembly feasibility.']}
