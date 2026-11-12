"""Compare local face evidence separately from its provenance and joint hypotheses."""
import json
from cadkin.followup import stable_id


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def observations(pair):
    groups = {}
    for evidence in pair['evidence']:
        if evidence['kind'] != 'face_contact': continue
        row = evidence['record']
        faces = sorted(row['faces'], key=lambda f: f['occurrence_path'])
        locators = [{k: f[k] for k in ('occurrence_path', 'source_sha256', 'body_index', 'face_index')} for f in faces]
        key = stable_id('face-observation-', [locators, evidence['parameters']])
        bucket = groups.setdefault(key, {'faces': locators, 'parameters': evidence['parameters'], 'versions': [], 'sources': []})
        # Keep the API left/right orientation: reversing a saved probe is a different numerical observation.
        version = {k: row[k] for k in ('review_state', 'metrics', 'converged', 'source_errors', 'solid_face_normals')}
        version['ordered_occurrence_paths'] = [f['occurrence_path'] for f in row['faces']]
        if version not in bucket['versions']: bucket['versions'].append(version)
        binding = {'review_path': evidence['source_path'], 'review_sha256': evidence['source_sha256'],
                   'probe_path': row['probe_path'], 'probe_sha256': row['probe_sha256']}
        if binding not in bucket['sources']: bucket['sources'].append(binding)
    for bucket in groups.values():
        bucket['versions'].sort(key=canonical); bucket['sources'].sort(key=canonical)
    return groups


def compare_faces(before_chain, after_chain, before_target, after_target):
    chains = [{p['pair_id']: p for p in c['pairs']} for c in (before_chain, after_chain)]
    targets = [{p['id']: p for p in t['pairs']} for t in (before_target, after_target)]
    pairs = []
    def semantic(row): return {k: v for k, v in row.items() if k != 'sources'}
    for pair_id in sorted(chains[0].keys() | chains[1].keys()):
        old, new = [observations(c[pair_id]) if pair_id in c else {} for c in chains]
        common = old.keys() & new.keys()
        thresholds = [sorted({canonical(v['parameters']) for v in rows.values()}) for rows in (old, new)]
        pair = chains[1].get(pair_id, chains[0].get(pair_id))
        before, after = [t.get(pair_id) for t in targets]
        pairs.append({'pair_id': pair_id, 'occurrence_paths': pair['occurrence_paths'],
            'newly_observed_ids': sorted(new.keys() - old.keys()), 'still_observed_ids': sorted(common),
            'no_longer_observed_ids': sorted(old.keys() - new.keys()),
            'changed_ids': sorted(k for k in common if semantic(old[k]) != semantic(new[k])),
            'provenance_changed_ids': sorted(k for k in common if old[k]['sources'] != new[k]['sources']),
            'before_observations': old, 'after_observations': new,
            'before_thresholds': [json.loads(v) for v in thresholds[0]], 'after_thresholds': [json.loads(v) for v in thresholds[1]],
            'threshold_profiles_equal': thresholds[0] == thresholds[1],
            'before_link_support': None if before is None else before['link_support'],
            'after_link_support': None if after is None else after['link_support'],
            'before_flags': [] if before is None else before['flags'], 'after_flags': [] if after is None else after['flags'],
            'connection_confirmed': False, 'resolved_findings_asserted': False})
    return {'pairs': pairs, 'summary': {
        'before_face_observations': sum(len(p['before_observations']) for p in pairs),
        'after_face_observations': sum(len(p['after_observations']) for p in pairs),
        **{key: sum(len(p[key]) for p in pairs) for key in ('newly_observed_ids', 'no_longer_observed_ids', 'changed_ids', 'provenance_changed_ids')},
        'pairs_with_threshold_profile_changes': sum(not p['threshold_profiles_equal'] for p in pairs)},
        'identity_scope': 'exact_saved_catalog_hash_and_record_locator; no cross-catalog CAD identity inferred',
        'meaning': 'Local observation and threshold coverage changes are separate from source-file rewrites. Support is a ranking weight, not contact/joint confirmation.'}
