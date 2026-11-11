"""Associate existing geometry candidates with verified root mate evidence; no solver."""
from datetime import datetime, timezone
import json

from cadkin.errors import ToolFailure, success
from cadkin.geometry import transform_from_sw
from cadkin.tools.files import json_path, read_json
from cadkin.tools.inventory import spatial_inventory
from cadkin.tools.face_matches import validate_face_matching, candidate_face_matches


def require(condition, message, code='INVALID_CONNECTION_SOURCE'):
    if not condition:
        raise ToolFailure(code, message)


def identity(info):
    fields = ('document_token', 'path', 'title', 'configuration', 'document_type')
    require(isinstance(info, dict) and all(isinstance(info.get(k), str) for k in fields), 'Missing document identity.')
    require(info['document_type'] == 'assembly', 'Expected an assembly document.')
    return tuple(info[k] for k in fields)


def review_connections(relations, mates, inventory, expected_inventory_sha256):
    require(isinstance(relations, dict) and relations.get('relation_schema_version') == 1 and
            isinstance(relations.get('candidates'), list) and len(relations['candidates']) <= 5000,
            'Expected a bounded cad_component_relations result file.')
    spatial, nodes = spatial_inventory(inventory)
    require(relations.get('inventory_sha256') == expected_inventory_sha256 and
            identity(relations.get('document')) == identity(spatial.get('document')), 'Relation inventory binding differs.', 'EVIDENCE_MISMATCH')
    require(isinstance(mates, dict) and mates.get('status') in ('ok', 'partial') and isinstance(mates.get('data'), dict),
            'Use the original sw_mate_inventory envelope.')
    data = mates['data']
    require(data.get('mate_inventory_schema_version') == 1 and data.get('scope') == 'active_root_assembly' and
            data.get('subassembly_internal_mates_included') is False and isinstance(data.get('mates'), list) and
            len(data['mates']) <= 1000 and data.get('mate_count') == len(data['mates']), 'Unsupported mate source scope/schema/count.')
    require(identity(data.get('document')) == identity(spatial['document']), 'Mate document/configuration differs.', 'EVIDENCE_MISMATCH')
    require(isinstance(data.get('component_contexts'), list), 'Missing mate occurrence contexts.')
    contexts = {}
    for item in data['component_contexts']:
        require(isinstance(item, dict), 'Invalid mate occurrence context.')
        path = item.get('occurrence_path')
        require(isinstance(path, str) and path in nodes and path not in contexts, 'Missing or duplicate mate occurrence.', 'EVIDENCE_MISMATCH')
        node = nodes[path]
        require(item.get('referenced_configuration') == node.get('referenced_configuration') and
                item.get('file_path') == node.get('file_path') and item.get('parent_occurrence_path') == node.get('parent_occurrence_path'),
                'Mate occurrence identity differs from inventory.', 'EVIDENCE_MISMATCH')
        require(isinstance(item.get('transform'), dict) and isinstance(node.get('transform'), dict), 'Missing occurrence pose.')
        require(transform_from_sw(item['transform'].get('raw_array'))['raw_array'] ==
                transform_from_sw(node['transform'].get('raw_array'))['raw_array'], 'Mate occurrence pose differs from inventory.', 'EVIDENCE_MISMATCH')
        contexts[path] = item
    pairs = {}
    for index, candidate in enumerate(relations['candidates']):
        require(isinstance(candidate, dict) and candidate.get('kind') in ('coaxial_candidate', 'parallel_candidate') and
                isinstance(candidate.get('left'), dict) and isinstance(candidate.get('right'), dict), 'Invalid geometric candidate.')
        paths = [candidate[side].get('occurrence_path') for side in ('left', 'right')]
        require(all(isinstance(p, str) and p in nodes for p in paths) and paths[0] != paths[1], 'Candidate occurrences differ.', 'EVIDENCE_MISMATCH')
        pair = pairs.setdefault(tuple(sorted(paths)), {'geometric_candidate_indices': [], 'mate_evidence': []})
        pair['geometric_candidate_indices'].append(index)
    face_evidence = validate_face_matching(data, relations, expected_inventory_sha256)
    ids, unmatched = set(), []
    for record in data['mates']:
        require(isinstance(record, dict) and type(record.get('feature_id')) is int and record['feature_id'] not in ids,
                'Mate feature IDs must be unique within this source.')
        ids.add(record['feature_id'])
        require(record.get('owning_assembly') == 'active_root_assembly' and record.get('entity_params_frame') == 'root_assembly' and
                record.get('owner_configuration') == spatial['document']['configuration'], 'Mate owner frame/configuration differs.', 'EVIDENCE_MISMATCH')
        entities = record.get('entities')
        refs = set()
        fully_mapped = isinstance(entities, list) and type(record.get('entity_count')) is int and len(entities) == record['entity_count']
        if entities is not None:
            require(isinstance(entities, list), 'Invalid mate entity list.')
            for entity in entities:
                require(isinstance(entity, dict), 'Invalid mate entity.')
                path = entity.get('reference_occurrence_path')
                if entity.get('reference_status') == 'verified_root_occurrence':
                    require(isinstance(path, str) and path in contexts, 'Verified reference has no matching context.', 'EVIDENCE_MISMATCH')
                    refs.add(path)
                else:
                    fully_mapped = False
        pair = tuple(sorted(refs))
        # Multi-component mates and root/unmapped references never become pair constraints by guesswork.
        if len(pair) != 2 or pair not in pairs:
            unmatched.append({'feature_id': record['feature_id'], 'reason': 'No exact two-occurrence candidate pair.',
                              'verified_reference_paths': sorted(refs)})
            continue
        activity = record.get('activity')
        require(isinstance(activity, dict), 'Missing mate activity evidence.')
        issue_code = activity.get('feature_error_code')
        record_errors = record.get('errors', [])
        require(isinstance(record_errors, list) and all(isinstance(e, dict) for e in record_errors), 'Invalid mate error list.')
        mate_errors = [e for e in record_errors if e.get('field') != 'face_match']
        # Additional face work may be incomplete while the original mate state is fully known.
        state_read = record.get('read_status') == 'ok' or (
            face_evidence is not None and record.get('read_status') == 'partial' and record_errors and not mate_errors)
        if not fully_mapped or mate_errors or not state_read:
            category = 'unresolved'
        elif activity.get('suppressed') is True:
            category = 'suppressed'
        elif activity.get('rolled_back') is True:
            category = 'rolled_back'
        elif type(issue_code) is int and issue_code > 0:
            category = 'feature_issue'
        elif (activity.get('suppressed') is False and activity.get('rolled_back') is False and
              type(issue_code) is int and issue_code == 0 and activity.get('state') == 'unsuppressed_no_feature_error'):
            category = 'unsuppressed_no_feature_error'
        else:
            category = 'unresolved'
        matches = candidate_face_matches(record, pairs[pair]['geometric_candidate_indices'], relations['candidates']) if face_evidence else []
        pairs[pair]['mate_evidence'].append({'feature_id': record['feature_id'], 'feature_name': record.get('feature_name'),
                                            'type_code': record.get('type_code'), 'type_name': record.get('type_name'),
                                            'category': category, 'activity': activity, 'record_errors': record.get('errors', []),
                                            'face_matching_errors': [e for e in record_errors if e.get('field') == 'face_match'],
                                            'association_level': 'candidate_face_pair' if matches else 'occurrence_pair_only',
                                            'face_match_confirmed': bool(matches), 'candidate_face_matches': matches})
    reviewed = []
    for pair, item in sorted(pairs.items()):
        categories = {m['category'] for m in item['mate_evidence']}
        state = ('has_unsuppressed_mate_evidence' if 'unsuppressed_no_feature_error' in categories else
                 ('unresolved_mate_evidence' if 'unresolved' in categories else
                  ('only_suppressed_or_feature_issue' if categories else 'geometry_only')))
        reviewed.append({'occurrence_paths': list(pair), **item, 'review_state': state,
                         'requires_review': True, 'mechanical_relation_confirmed': False})
    source_errors = []
    for name, complete, errors in [('relations', relations.get('complete'), relations.get('errors')),
                                  ('mates', data.get('complete'), mates.get('errors')),
                                  ('inventory', spatial.get('complete'), inventory.get('errors'))]:
        require(isinstance(errors, list) and all(isinstance(e, dict) for e in errors), 'Missing source errors.')
        if complete is not True or errors or (name == 'mates' and (mates['status'] != 'ok' or data.get('truncated'))):
            source_errors.append({'code': 'SOURCE_INCOMPLETE', 'source': name, 'message': 'Source is incomplete; retain unknown relationships.', 'source_errors': errors})
    counts = {state: sum(p['review_state'] == state for p in reviewed) for state in (
        'has_unsuppressed_mate_evidence', 'unresolved_mate_evidence', 'only_suppressed_or_feature_issue', 'geometry_only')}
    return {'connection_review_schema_version': 1, 'document': spatial['document'],
            'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'snapshot_atomic': False,
            'pairs': reviewed, 'counts': counts, 'unmatched_mates': unmatched,
            'coverage': {'scope': 'provided_geometric_candidates_and_active_root_mates',
                         'candidate_face_pairs': len(relations['candidates']), 'occurrence_pairs': len(reviewed),
                         'read_mate_records': len(data['mates']), 'unmatched_mate_records': len(unmatched),
                         'face_matched_mate_records': sum(m['face_match_confirmed'] for p in reviewed for m in p['mate_evidence'])},
            'face_matching': face_evidence,
            'complete': not source_errors, 'errors': source_errors, 'requires_review': True, 'mechanical_relation_confirmed': False,
            'solidworks_modified': False,
            'limitations': ['Default association is occurrence-pair only. Candidate-face matches require both exact faces to have source-bound live CAD identity evidence; absent matches remain unknown.',
                            'Unsuppressed with no reported feature error is not solver validation, DOF analysis, confirmed contact or a motion joint.',
                            'Internal subassembly mates, unmapped/root references and multi-component mate relationships are not resolved here.',
                            'No matching mate or geometric candidate does not prove absent connections/free motion. Source completeness covers only the stated scopes.',
                            'Source hashes and pose matching do not prove atomic capture or unchanged geometry; capture in an unchanged session.']}


def connection_review(root, relations_path, mate_inventory_path, output_path):
    output = json_path(root, output_path, output=True)
    relation_file, mate_file = json_path(root, relations_path), json_path(root, mate_inventory_path)
    relations, relation_hash = read_json(relation_file)
    mates, mate_hash = read_json(mate_file)
    require(isinstance(relations, dict) and isinstance(relations.get('inventory_path'), str), 'Missing inventory file binding.')
    inventory_file = json_path(root, relations['inventory_path'])
    inventory, inventory_hash = read_json(inventory_file)
    require(isinstance(relations.get('sources'), list) and 2 <= len(relations['sources']) <= 32, 'Missing cylinder source bindings.')
    for source in relations['sources']:
        require(isinstance(source, dict) and isinstance(source.get('source_path'), str), 'Invalid cylinder source binding.')
        _, digest = read_json(json_path(root, source['source_path']))
        require(digest == source.get('source_sha256'), 'Cylinder source changed since relation generation.', 'EVIDENCE_MISMATCH')
    data = review_connections(relations, mates, inventory, inventory_hash)
    data['sources'] = {'relations': {'path': str(relation_file), 'sha256': relation_hash},
                       'mates': {'path': str(mate_file), 'sha256': mate_hash},
                       'inventory': {'path': str(inventory_file), 'sha256': inventory_hash}}
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open('x', encoding='utf-8') as stream: stream.write(payload)
    except FileExistsError as exc:
        raise ToolFailure('OUTPUT_EXISTS', 'Choose a new output filename.') from exc
    return success({'output_path': str(output), 'counts': data['counts'], 'coverage': data['coverage'],
                    'complete': data['complete'], 'requires_review': True, 'mechanical_relation_confirmed': False,
                    'solidworks_modified': False}, data['errors'])
