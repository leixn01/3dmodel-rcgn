"""Public template output: reference semantics never become target joint types."""
from copy import deepcopy


def separate_reference_types(match, pairs):
    result = deepcopy(match)
    for candidate in result['candidates']:
        for edge in candidate['joint_hypotheses']:
            kind = edge['hypothesis_kind']
            pair = pairs[edge['target_pair_id']]
            locks = [s for s in pair['signals'] if s['kind'] == 'active_mate' and
                     s.get('mate_type') == 'lock' and not s.get('record_errors')]
            edge.update(reference_joint_kind=kind, hypothesis_kind='unknown', target_joint_kind='unknown',
                target_degrees_of_freedom=None, kind_basis='target_evidence_does_not_identify_joint_type',
                reference_type_transferred=False,
                reference_compatibility='opposed_by_active_lock' if locks and kind in ('revolute', 'prismatic') else 'not_established')
            if 'dof_hypothesis' in edge:
                edge['reference_dof'] = edge['dof_hypothesis']; edge['dof_hypothesis'] = None
                edge['parameter_status'].update(kind='unknown', degrees_of_freedom='unknown')
        candidate['scope'] = 'optional_reference_analogy_not_target_joint_identification'
        candidate['risk_codes'] = sorted(set(candidate['risk_codes']) | {'REFERENCE_TYPE_NOT_TRANSFERRED'})
    result.update(algorithm_version=2, target_joint_types_inferred=False,
        purpose='Optional structural analogy; topology/axis score cannot determine target joint kind or DOF.')
    return result
