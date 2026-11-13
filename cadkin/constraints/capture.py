"""Validate saved enhanced mate results before permitting guarded reuse."""
from cadkin.constraints.analysis import require, read_geometry
from cadkin.adapters.mate_records import MATE_TYPES


def validate_enhanced_capture(data, arguments):
    capture = data.get('reference_geometry_capture')
    require(isinstance(capture, dict) and capture.get('schema_version') == 1 and
        capture.get('frame') == 'root_assembly' and capture.get('scope') == 'direct_root_mate_face_references' and
        capture.get('identity_rechecked') is True, 'Enhanced mate identity recheck is missing.')
    require(data.get('parameters') == {k: v for k, v in arguments.items() if k != 'expected_document_token'},
        'Enhanced mate capture parameters differ from the plan.')
    rows = data.get('mates')
    require(isinstance(rows, list) and len(rows) <= arguments['max_mates'] and data.get('mate_count') == len(rows),
        'Invalid enhanced mate count.')
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and type(row.get('feature_id')) is int and row['feature_id'] not in seen,
            'Missing or duplicate enhanced mate feature identity.')
        seen.add(row['feature_id'])
        require(row.get('owning_assembly') == 'active_root_assembly' and row.get('entity_params_frame') == 'root_assembly' and
            row.get('owner_configuration') == data['document']['configuration'] and row.get('type_name') == MATE_TYPES.get(row.get('type_code')),
            'Enhanced mate type, owner or frame differs.')
        opts = row.get('constraint_options')
        # A failed mate interface may have no optional fields, but must carry the original error.
        if opts is None:
            require(bool(row.get('errors')), 'Missing enhanced mate options without an error.')
        else:
            require(isinstance(opts, dict) and opts.get('status') in ('read', 'unavailable', 'not_applicable'), 'Invalid enhanced options.')
            if opts['status'] == 'read':
                require(row.get('type_code') == 1 and type(opts.get('concentric_lock_rotation')) is bool and
                    opts.get('api') == 'IConcentricMateFeatureData.LockRotation', 'Invalid rotation lock evidence.')
            elif opts['status'] == 'unavailable':
                require(opts.get('concentric_lock_rotation') is None and bool(row.get('errors')), 'Unknown lock state must retain its error.')
            else:
                require(row.get('type_code') != 1 and opts.get('concentric_lock_rotation') is None, 'Concentric lock state was omitted.')
        entities = row.get('entities')
        require(entities is None and bool(row.get('errors')) or isinstance(entities, list) and len(entities) <= arguments['max_entities'], 'Invalid entity list.')
        if data.get('complete') is True:
            require(not row.get('errors') and row.get('read_status') == 'ok' and isinstance(entities, list) and
                type(row.get('entity_count')) is int and row['entity_count'] == len(entities),
                'Complete enhanced capture contains an incomplete mate.')
        indices = set()
        for entity in entities or []:
            require(isinstance(entity, dict) and type(entity.get('entity_index')) is int and entity['entity_index'] >= 0 and
                entity['entity_index'] not in indices, 'Invalid or duplicate entity locator.')
            indices.add(entity['entity_index'])
            geometry = entity.get('reference_geometry')
            require(geometry is None or isinstance(geometry, dict), 'Invalid enhanced entity geometry.')
            if data.get('complete') is True:
                require(not entity.get('errors'), 'Complete enhanced capture contains entity errors.')
            if entity.get('reference_status') == 'verified_root_occurrence' and not entity.get('errors'):
                require(isinstance(geometry, dict) and geometry.get('status') in ('read', 'unsupported_reference_type'),
                    'Enhanced entity geometry is absent without an error.')
            if isinstance(geometry, dict) and geometry.get('status') == 'read':
                require(entity.get('reference_status') == 'verified_root_occurrence', 'Unverified occurrence claims face geometry.')
                read_geometry(entity, capture)
