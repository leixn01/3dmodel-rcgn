"""Route guarded probes into compatible face reviews without inventing tolerances."""
from collections import defaultdict

from cadkin.tools.chain_sources import ChainSources, require
from cadkin.tools.face_contacts import review_probe
from cadkin.tools.files import json_path, read_json, replay_reads


@replay_reads
def route_face_captures(root, chain, target, captures, face_review_path=None):
    bases, inputs = [], []
    scope = {n['id'] for n in target['nodes']}
    def basis(raw, binding, existing):
        rows = {}
        for row in raw['pairs']:
            key = tuple(sorted((f['occurrence_path'], f['source_sha256'], f['body_index'], f['face_index']) for f in row['faces']))
            rows[key] = row
        return {'source': binding, 'parameters': raw['parameters'], 'existing': existing,
                'pairs': {tuple(sorted(f['occurrence_path'] for f in r['faces'])) for r in raw['pairs']},
                'rows': rows, 'probe_paths': [r['probe_path'] for r in raw['pairs']] if existing else [], 'capture_ids': []}
    for source in chain['sources']:
        if source['kind'] == 'face_contact':
            raw, digest = read_json(json_path(root, source['path']))
            require(digest == source['sha256'], 'Face review changed.', 'EVIDENCE_MISMATCH')
            bases.append(basis(raw, {'path': source['path'], 'sha256': digest}, True))
    supplied = None
    if face_review_path is not None:
        reader = ChainSources(root, chain['parameters']['inventory_path'])
        kind, data, _, _, binding = reader.evidence(face_review_path)
        require(kind == 'face_contact', 'Provide a source-replayed face contact review.', 'INVALID_FACE_REVIEW_BASIS')
        inputs = reader.finish() + [binding]
        supplied = basis(data, binding, False)
    entries, groups = [], defaultdict(list)
    for task_id, capture in sorted(captures.items()):
        if capture['tool'] != 'sw_probe_face_pair': continue
        raw, digest = read_json(json_path(root, capture['source']['path']))
        require(digest == capture['source']['sha256'], 'Guarded probe changed.', 'EVIDENCE_MISMATCH')
        row, key = review_probe(root, raw, 0, 0)
        pair = tuple(sorted(f['occurrence_path'] for f in row['faces']))
        require(set(pair) <= scope, 'Probe lies outside the original chain scope.', 'EVIDENCE_MISMATCH')
        entry = {'task_id': task_id, 'source': capture['source'], 'occurrence_paths': list(pair),
                 'face_key': key, 'basis_source': None, 'parameters': None, 'reason': None}
        entries.append(entry); groups[key].append(entry)
    reused = set(); pending = []
    for entry in entries:
        key, pair, capture_source = entry['face_key'], tuple(entry['occurrence_paths']), entry['source']
        if len(groups[key]) > 1:
            entry['reason'] = 'DUPLICATE_GUARDED_FACE_PAIR'; continue
        matches = [b for b in bases if pair in b['pairs']]
        represented = [b['rows'][key] for b in matches if key in b['rows']]
        if represented:
            if any(r['probe_sha256'] == capture_source['sha256'] for r in represented):
                entry['reason'] = 'ALREADY_INTEGRATED'; reused.add(entry['task_id'])
            else: entry['reason'] = 'FACE_PAIR_ALREADY_OBSERVED'
            continue
        settings = {(b['parameters']['contact_tolerance_mm'], b['parameters']['angle_tolerance_deg']) for b in matches}
        if len(settings) > 1:
            entry['reason'] = 'AMBIGUOUS_FACE_REVIEW_THRESHOLDS'; continue
        if matches:
            selected = min(matches, key=lambda b: b['source']['path'])
        elif supplied is not None and key in supplied['rows'] and supplied['rows'][key]['probe_sha256'] == capture_source['sha256']:
            if len(chain['sources']) >= 20:
                entry['reason'] = 'CHAIN_EVIDENCE_CAPACITY_LIMIT'; continue
            selected = supplied
        else:
            entry['reason'] = 'NO_MATCHING_FACE_REVIEW'; continue
        entry.update(basis_source=selected['source'], parameters=selected['parameters'])
        if len(selected['probe_paths']) >= 100:
            entry['reason'] = 'FACE_REVIEW_CAPACITY_LIMIT'; continue
        selected['probe_paths'].append(capture_source['path']); selected['capture_ids'].append(entry['task_id'])
        entry['reason'] = 'READY_FOR_RECOMPUTATION'; pending.append(entry['task_id'])
    jobs = [b for b in bases + ([supplied] if supplied else []) if b['capture_ids']]
    for job in jobs:
        job.pop('pairs'); job.pop('rows')
    return {'jobs': jobs, 'entries': entries, 'input_files': inputs, 'reused_capture_ids': sorted(reused),
            'candidate_capture_ids': pending, 'supplied_review_source': None if supplied is None else supplied['source']}
