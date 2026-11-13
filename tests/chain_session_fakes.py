"""Explicit synthetic chain-session inputs; no installed CAD or lift evidence."""
import json
from pathlib import Path

from tests.constraint_fakes import write_constraint_fixture
from tests.execution_fakes import live_service


def session_fixture(root, mode='chain_closed', reuse_inventory=False):
    root = Path(root).resolve()
    app, mates, _ = write_constraint_fixture(root, mode, enriched=False)
    service = live_service(root, app)
    config = {'expected_document_token': service.call('sw_active_document')['data']['document_token'],
        'occurrence_paths': ['base-1', 'carriage-1', 'rail-1'], 'chain_name': 'Explicit synthetic chain',
        'reference_occurrence_path': 'base-1', 'characteristic_length_mm': 100,
        'distance_tolerance_mm': .1, 'angle_tolerance_deg': .1}
    if reuse_inventory:
        config['inventory_path'] = 'inventory.json'
    (root / 'config.json').write_text(json.dumps(config), encoding='utf-8')
    return service, app, mates, config
