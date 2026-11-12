"""Read-only file inputs for face probes; send only validated plain data to STA."""
from cadkin.face_geometry import descriptor, require
from cadkin.geometry import transform_from_sw
from cadkin.tools.files import json_path, read_json
from cadkin.tools.relations import _document


def face_source(root, selection):
    path = json_path(root, selection['face_inventory_path'])
    envelope, digest = read_json(path)
    require(isinstance(envelope, dict) and envelope.get('status') in ('ok', 'partial') and isinstance(envelope.get('data'), dict), 'Use an original face inventory envelope.')
    data, errors = envelope['data'], envelope.get('errors')
    require(data.get('face_inventory_schema_version') == 1 and data.get('geometry_scope') == 'referenced_part_definition' and
            data.get('assembly_instance_features_evaluated') is False, 'Unsupported face source schema/scope.')
    _document(data.get('document'))
    target = data.get('target')
    require(isinstance(target, dict) and all(isinstance(target.get(k), str) for k in ('occurrence_path', 'file_path', 'referenced_configuration')),
            'Missing occurrence context.')
    part = target.get('source_part')
    require(isinstance(part, dict) and part.get('document_type') == 'part' and part.get('configuration') == target['referenced_configuration'], 'Missing matching part context.')
    require(isinstance(target.get('transform'), dict), 'Missing transform.')
    transform_from_sw(target['transform'].get('raw_array'))
    rows = data.get('faces')
    require(isinstance(rows, list) and len(rows) <= 1000 and type(data.get('face_count')) is int and len(rows) == data['face_count'], 'Invalid face count.')
    seen, selected = set(), None
    for row in rows:
        require(isinstance(row, dict), 'Invalid face record.')
        bi, fi = row.get('body_index'), row.get('face_index')
        require(type(bi) is int and type(fi) is int and bi >= 0 and fi >= 0 and (bi, fi) not in seen, 'Duplicate or invalid face indices.')
        seen.add((bi, fi))
        if (bi, fi) == (selection['body_index'], selection['face_index']):
            selected = row
    require(selected is not None, 'Face indices are absent from this source.', 'FACE_NOT_IN_SOURCE')
    descriptor(selected.get('descriptor'))
    require(isinstance(selected.get('face_reference'), dict), 'Selected face has no persistent reference.', 'FACE_REFERENCE_UNAVAILABLE')
    require(isinstance(errors, list) and all(isinstance(e, dict) for e in errors) and
            type(data.get('complete')) is bool and type(data.get('truncated')) is bool, 'Missing source status/errors.')
    return {'path': str(path), 'sha256': digest, 'document': data['document'], 'target': target, 'face': selected,
            'complete': envelope['status'] == 'ok' and data['complete'] and not data['truncated'] and not errors,
            'errors': errors}


def load_probe_sources(root, expected_document_token, left, right, **options):
    sources = [face_source(root, selection) for selection in (left, right)]
    require(_document(sources[0]['document']) == _document(sources[1]['document']) and
            sources[0]['document']['document_token'] == expected_document_token, 'Face sources belong to another document/configuration.', 'EVIDENCE_MISMATCH')
    require(sources[0]['target']['occurrence_path'] != sources[1]['target']['occurrence_path'], 'Choose faces on two different occurrences.', 'INVALID_ARGUMENTS')
    return {'expected_document_token': expected_document_token, 'sources': sources, **options}
