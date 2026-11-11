"""File validation for live face matching. Only plain data crosses into the STA."""
from cadkin.errors import ToolFailure
from cadkin.tools.files import json_path, read_json
from cadkin.tools.inventory import spatial_inventory
from cadkin.tools.relations import _cylinders, _document


def load_face_sources(root, expected_document_token, inventory_path, cylinder_paths, **budgets):
    inventory_file = json_path(root, inventory_path)
    inventory, digest = read_json(inventory_file)
    data, nodes = spatial_inventory(inventory)
    document = _document(data.get('document'))
    if data['document']['document_token'] != expected_document_token:
        raise ToolFailure('EVIDENCE_MISMATCH', 'The inventory token differs from the requested live document.')
    sources, seen = [], set()
    for name in cylinder_paths:
        path = json_path(root, name)
        envelope, source_hash = read_json(path)
        normalized = _cylinders(envelope, nodes, document, str(path), source_hash)
        occurrence = normalized['occurrence_path']
        if occurrence in seen:
            raise ToolFailure('INVALID_FACE_SOURCE', 'Use one cylinder snapshot per occurrence.')
        seen.add(occurrence)
        if envelope['data'].get('face_references_requested') is not True:
            raise ToolFailure('FACE_REFERENCE_UNAVAILABLE', 'Recollect cylinders with include_face_references=true, then regenerate relations.')
        sources.append({'data': envelope['data'], 'node': nodes[occurrence], 'binding': normalized})
    return {'expected_document_token': expected_document_token, 'sources': sources,
            'inventory_binding': {'path': str(inventory_file), 'sha256': digest, 'document': data['document'],
                                  'complete': inventory['status'] == 'ok' and data.get('complete') is True,
                                  'errors': inventory.get('errors', [])}, **budgets}
