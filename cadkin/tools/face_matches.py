"""Offline interpretation of live face-identity evidence, independent of COM."""
from cadkin.errors import ToolFailure


def require(condition, message):
    if not condition:
        raise ToolFailure('INVALID_FACE_MATCH_SOURCE', message)


def validate_face_matching(data, relations, inventory_sha256):
    evidence = data.get('face_matching')
    require(all(isinstance(m, dict) and (m.get('entities') is None or
            isinstance(m['entities'], list) and all(isinstance(e, dict) for e in m['entities'])) for m in data['mates']), 'Invalid mate/entity records.')
    if evidence is None:
        require(not any('face_match' in e for m in data['mates'] for e in (m.get('entities') or [])), 'Face matches lack collection provenance.')
        return None
    require(isinstance(evidence, dict) and evidence.get('schema_version') == 1 and
            evidence.get('scope') == 'provided_part_faces_and_active_root_mate_entities' and
            evidence.get('inventory_sha256') == inventory_sha256, 'Face evidence uses a different scope/inventory.')
    require(type(evidence.get('complete')) is bool and type(evidence.get('truncated')) is bool and
            (evidence['complete'] or data.get('complete') is not True) and
            (not evidence['truncated'] or data.get('truncated') is True), 'Inconsistent face completeness flags.')
    sources = evidence.get('cylinder_sources')
    require(isinstance(sources, list) and 1 <= len(sources) <= 8, 'Missing face source bindings.')
    relation_sources = {s['occurrence_path']: s for s in relations['sources']}
    bound = {}
    for source in sources:
        require(isinstance(source, dict), 'Invalid face source.')
        path = source.get('occurrence_path')
        require(isinstance(path, str) and path in relation_sources and path not in bound, 'Face source occurrence is missing or repeated.')
        original = relation_sources[path]
        require(source.get('source_sha256') == original.get('source_sha256') and source.get('source_path') == original.get('source_path'),
                'Face matches must bind to the exact cylinder files used by relations; regenerate after recollection.')
        bound[path] = source
    for mate in data['mates']:
        indices = [e.get('entity_index') for e in mate.get('entities') or []]
        require(all(type(i) is int and i >= 0 for i in indices) and len(set(indices)) == len(indices), 'Invalid or repeated mate entity indices.')
        for entity in mate.get('entities') or []:
            match = entity.get('face_match')
            if match is None:  # A failed mate/entity read remains unknown.
                continue
            require(isinstance(match, dict) and match.get('status') in ('checked', 'partial', 'unknown', 'not_face', 'outside_scope') and
                    isinstance(match.get('matches'), list) and len(match['matches']) <= 500, 'Invalid entity face-match record.')
            require(type(match.get('compared_faces')) is int and match['compared_faces'] >= len(match['matches']), 'Invalid comparison count.')
            seen = set()
            for row in match['matches']:
                require(isinstance(row, dict), 'Invalid matched face.')
                path, body, face = row.get('occurrence_path'), row.get('body_index'), row.get('face_index')
                require(isinstance(path, str) and path in bound and entity.get('reference_occurrence_path') == path and
                        entity.get('reference_status') == 'verified_root_occurrence' and entity.get('reference_type_code') == 2 and
                        match['status'] in ('checked', 'partial'), 'Matched face is not a verified face entity in the source scope.')
                require(type(body) is int and body >= 0 and type(face) is int and face >= 0 and (body, face) not in seen, 'Invalid or repeated face index.')
                seen.add((body, face))
                require(row.get('source_path') == bound[path]['source_path'] and row.get('source_sha256') == bound[path]['source_sha256'] and
                        row.get('identity_check') == 'resolved_part_face_to_occurrence_IsSame', 'Missing live face identity provenance.')
                require(any(a['body_index'] == body and a['face_index'] == face for a in relation_sources[path]['axes']), 'Matched face is absent from its cylinder source.')
    return evidence


def candidate_face_matches(record, candidate_indices, candidates):
    entities = record.get('entities')
    # A three-/multi-entity mate is not reduced to a two-face relation.
    if not isinstance(entities, list) or len(entities) != 2 or record.get('entity_count') != 2:
        return []
    entity_faces = []
    for entity in entities:
        match = entity.get('face_match', {})
        entity_faces.append({(m['occurrence_path'], m['body_index'], m['face_index']) for m in match.get('matches', [])})
    results = []
    for index in candidate_indices:
        sides = [candidates[index][s] for s in ('left', 'right')]
        keys = [(s['occurrence_path'], s.get('body_index'), s.get('face_index')) for s in sides]
        for order in ((0, 1), (1, 0)):
            if keys[0] in entity_faces[order[0]] and keys[1] in entity_faces[order[1]]:
                results.append({'geometric_candidate_index': index, 'left_entity_index': entities[order[0]]['entity_index'],
                                'right_entity_index': entities[order[1]]['entity_index'], 'face_match_confirmed': True})
                break
    return results
