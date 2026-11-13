"""Compare pair-level observations without matching feature IDs across snapshots."""


def summarize(pair):
    return {
        'snapshot_sources': [s['source'] for s in pair['snapshots']],
        'candidate_patterns': [{'kind': c['kind'], 'rule': c['rule'], 'status': c['status'],
            'source': s['source'], 'evidence_ids': c['evidence_ids']}
            for s in pair['snapshots'] for c in s['candidates']],
        'missing_codes': sorted({m['code'] for m in pair['missing_evidence']} |
            {m['code'] for s in pair['snapshots'] for m in s['missing_evidence']}),
        'conflict_codes': sorted({c['code'] for s in pair['snapshots'] for c in s['conflicts']}),
        'flags': pair['flags'],
    }


def compare_constraints(before, after):
    left = {tuple(sorted(p['occurrence_paths'])): p for p in before['pairs']}
    right = {tuple(sorted(p['occurrence_paths'])): p for p in after['pairs']}
    rows = []
    for paths in sorted(left.keys() | right.keys()):
        a = summarize(left[paths]) if paths in left else None
        b = summarize(right[paths]) if paths in right else None
        rows.append({'occurrence_paths': list(paths), 'before': a, 'after': b,
            'missing_codes_no_longer_observed': sorted(set(a['missing_codes']) - set(b['missing_codes'])) if a and b else [],
            'missing_codes_newly_observed': sorted(set(b['missing_codes']) - set(a['missing_codes'])) if a and b else [],
            'comparison_scope': 'pair_level_separate_snapshots', 'feature_identity_matched': False,
            'target_joint_kind': 'unknown', 'target_degrees_of_freedom': None})
    return {'before_coverage': before['coverage'], 'after_coverage': after['coverage'], 'pairs': rows,
        'mechanically_verified': False,
        'limitations': ['Feature IDs and evidence IDs belong to their source hash; no cross-snapshot identity is inferred.',
            'A missing code no longer observed is not proof of resolved mechanics. Compare coverage, conflicts and candidate assumptions.']}
